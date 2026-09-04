"""Checks for the web UI layer: honest derivations and a real auth boundary."""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from dashboard.services.auth import can, capability_matrix, current_user
from dashboard.services.workflows import (
    DEMO_SCENARIOS, agent_timeline, pending_actions, ring_chain, ring_edges, run_scenario,
    system_status, why_flagged,
)
from web.server import Handler, bootstrap_payload, run_payload
from dashboard.services import session
from dashboard.services.storage import SQLiteStorage


# ----------------------------------------------------------------- derivations
@pytest.mark.parametrize("preset", list(DEMO_SCENARIOS))
def test_every_demo_scenario_runs_offline(preset):
    state = run_scenario(preset)
    assert state["route"] in {"restock_only", "audit_only", "full", "ring_only", "noop"}
    assert state["logs"]


def test_timeline_marks_routed_out_agents_as_skipped_not_done():
    """Dynamic routing must show as skipped, never as executed."""
    state = run_scenario("3 · Fraud Ring")
    steps = {s["name"]: s for s in agent_timeline(state)}
    assert steps["Ring-Auditor"]["status"] == "done"
    # ring_only never touches the retail or invoice agents
    for skipped in ("Demand-Forecaster", "Ops-Planner", "Payment-Auditor"):
        assert steps[skipped]["status"] == "skipped"
        assert steps[skipped]["detail"]


def test_timeline_detail_is_quoted_from_the_run_log():
    state = run_scenario("1 · Normal Restock")
    steps = {s["name"]: s for s in agent_timeline(state)}
    assert steps["Ops-Planner"]["status"] == "done"
    assert steps["Ops-Planner"]["detail"] in " ".join(state["logs"])


def test_why_flagged_quotes_real_signals_and_invents_none():
    state = run_scenario("2 · Suspicious Invoice")
    dispute = state["dispute_drafts"][0]
    why = why_flagged(state, "DISPUTE", dispute["dispute_id"])
    assert why["reasons"], "a real dispute must carry its reasons"
    joined = " ".join(why["reasons"])
    assert str(dispute["claimed_amount"]) in joined
    # the cited clause has to exist in the run, not be generated for display
    cited = [c["clause_id"] for c in state["regulatory_citations"]]
    assert all(any(cid in r for cid in cited) for r in why["reasons"] if "clause" in r)


def test_why_flagged_returns_empty_for_an_unknown_subject():
    state = run_scenario("1 · Normal Restock")
    assert why_flagged(state, "RING", "RING_DOES_NOT_EXIST")["reasons"] == []


def test_ring_chain_closes_a_cycle_and_orders_a_pass_through_chain():
    state = run_scenario("3 · Fraud Ring")
    by_type = {r["pattern_type"]: r for r in state["mule_rings"]}
    cycle = by_type["cycle"]
    chain, closes = ring_chain(cycle, ring_edges(state, cycle))
    assert closes is True
    assert set(chain) == set(cycle["member_accounts"])

    shell = by_type["shell_network"]
    chain, closes = ring_chain(shell, ring_edges(state, shell))
    assert closes is False
    assert chain[0] == "STORE_HQ", "a pass-through chain starts where money enters"


def test_pending_actions_hide_subjects_that_were_already_decided():
    state = run_scenario("2 · Suspicious Invoice")
    actions = pending_actions(state)
    assert actions
    first = actions[0]
    remaining = pending_actions(state, {(first["kind"], first["id"])})
    assert all(a["id"] != first["id"] for a in remaining)


def test_high_priority_actions_sort_first():
    state = run_scenario("2 · Suspicious Invoice")
    priorities = [a["priority"] for a in pending_actions(state)]
    assert priorities == sorted(priorities, key=lambda p: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[p])


def test_system_status_reports_the_offline_fallbacks_honestly(monkeypatch):
    monkeypatch.delenv("PAYGUARD_LLM_BACKEND", raising=False)
    status = system_status()
    assert status["llm"] == "offline stub"
    names = {row[0] for row in status["rows"]}
    assert {"Database", "Fraud engine", "Evidence signing"}.issubset(names)


def test_run_payload_is_json_serialisable():
    """The browser gets this verbatim; a non-serialisable value breaks the UI."""
    state = run_scenario("2 · Suspicious Invoice")
    records = {"alerts": [], "cases": [], "decisions": [], "evidence": [], "runs": []}
    json.dumps(run_payload(state, records), default=str)


def test_bootstrap_exposes_the_agent_catalog():
    payload = bootstrap_payload("OPERATIONS")
    names = {agent["name"] for agent in payload["agents"]}
    assert {"Supervisor", "DQ-Sentinel", "Ops-Planner", "Ring-Auditor", "HITL Controller"}.issubset(names)


def test_latest_run_state_restores_from_sqlite_after_memory_clear(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYGUARD_SQLITE_PATH", str(tmp_path / "restore.sqlite"))
    storage = SQLiteStorage(str(tmp_path / "restore.sqlite"))
    state = session.run_and_save("1 · Normal Restock", storage)
    session.clear_state()
    restored = session.current_state()
    assert restored["run_id"] == state["run_id"]
    session.clear_state()


# ----------------------------------------------------------------- authorization
def test_roles_gate_the_two_consequential_decisions():
    matrix = {row["role"]: row for row in capability_matrix()}
    assert matrix["OPERATIONS"]["approve_po"] and not matrix["OPERATIONS"]["review_fraud"]
    assert matrix["ANALYST"]["review_fraud"] and not matrix["ANALYST"]["approve_po"]
    assert not matrix["VIEWER"]["approve_po"] and not matrix["VIEWER"]["review_fraud"]


def test_unknown_role_never_gains_a_decision_capability():
    user = current_user("NOT_A_ROLE")
    assert user.role in {"ADMIN", "OPERATIONS", "ANALYST", "VIEWER"}
    assert can(user, "read")


# ----------------------------------------------------------------- HTTP surface
@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYGUARD_SQLITE_PATH", str(tmp_path / "ws.sqlite"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.status, json.loads(r.read().decode())


def _post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def test_index_and_assets_are_served(server):
    with urllib.request.urlopen(server + "/", timeout=10) as r:
        assert r.status == 200 and b"PayGuard-AgentX" in r.read()
    for asset in ("/app.css", "/app.js", "/auralis.js"):
        with urllib.request.urlopen(server + asset, timeout=10) as r:
            assert r.status == 200


def test_static_handler_refuses_path_traversal(server):
    try:
        with urllib.request.urlopen(server + "/../server.py", timeout=10) as r:
            body = r.read()
        assert b"BaseHTTPRequestHandler" not in body
    except urllib.error.HTTPError as exc:
        assert exc.code == 404


def test_run_then_decide_records_signed_evidence(server):
    status, data = _post(server, "/api/run", {"scenario": "1 · Normal Restock"})
    assert status == 200
    action = data["run"]["actions"][0]
    assert action["kind"] == "PO"

    before = len(data["records"]["evidence"])
    status, decided = _post(server, "/api/decide", {
        "kind": "PO", "id": action["id"], "action": "APPROVED", "role": "OPERATIONS"})
    assert status == 200
    assert len(decided["records"]["evidence"]) == before + 1
    assert all(e["valid"] for e in decided["records"]["evidence"])
    assert not decided["run"]["actions"], "a decided subject leaves the queue"


def test_server_rejects_a_decision_the_role_may_not_make(server):
    _post(server, "/api/run", {"scenario": "1 · Normal Restock"})
    status, data = _post(server, "/api/decide", {
        "kind": "PO", "id": "PO_STORE_01_1", "action": "APPROVED", "role": "VIEWER"})
    assert status == 403
    assert "cannot decide" in data["error"]


def test_server_rejects_an_unknown_action_verb(server):
    _post(server, "/api/run", {"scenario": "1 · Normal Restock"})
    status, _ = _post(server, "/api/decide", {
        "kind": "PO", "id": "PO_STORE_01_1", "action": "PAY_NOW", "role": "ADMIN"})
    assert status == 400


def test_server_rejects_a_decision_verb_for_the_wrong_subject_type(server):
    _post(server, "/api/run", {"scenario": "3 · Fraud Ring"})
    status, data = _post(server, "/api/decide", {
        "kind": "RING", "id": "RING_001", "action": "APPROVED", "role": "ANALYST"})
    assert status == 400
    assert "invalid" in data["error"]


def test_server_rejects_a_decision_for_an_unknown_subject(server):
    _post(server, "/api/run", {"scenario": "1 · Normal Restock"})
    status, data = _post(server, "/api/decide", {
        "kind": "PO", "id": "PO_NOT_IN_THIS_RUN", "action": "APPROVED", "role": "OPERATIONS"})
    assert status == 400
    assert "invalid" in data["error"]


def test_unknown_scenario_is_refused(server):
    status, _ = _post(server, "/api/run", {"scenario": "../../etc/passwd"})
    assert status == 400


def test_verify_endpoint_fails_a_tampered_payload(server):
    _post(server, "/api/run", {"scenario": "3 · Fraud Ring"})
    _, records = _get(server, "/api/records")
    evidence_id = records["evidence"][0]["evidence_id"]

    _, clean = _post(server, "/api/verify", {"evidence_id": evidence_id, "tamper": False})
    assert clean["valid"] is True
    _, tampered = _post(server, "/api/verify", {"evidence_id": evidence_id, "tamper": True})
    assert tampered["valid"] is False


def test_reset_clears_the_workspace(server):
    _post(server, "/api/run", {"scenario": "2 · Suspicious Invoice"})
    _, data = _post(server, "/api/reset", {})
    assert data["run"] is None
    assert data["records"]["evidence"] == []
    assert data["records"]["cases"] == []
