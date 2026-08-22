"""Phase-3 tests for the Ring-Auditor agent.

A fast circular-billing ring must be detected, signed into a verifiable dossier,
and routed to the human-review queue by risk. Deterministic, offline.
"""

from datetime import datetime, timedelta

from src.core import audit
from src.agents.ring_auditor import ring_auditor
from src.agents.orchestrator import run_supervised
from src.utils.retail_simulator import RetailSimulator

BASE = datetime(2024, 1, 1, 9, 0, 0)


def _cycle_txns():
    # A -> B -> C -> A, rapid (velocity signal) => a high-risk cycle ring.
    return [
        {"tx_id": "R1", "sender": "A", "receiver": "B", "amount": 5000, "timestamp": BASE},
        {"tx_id": "R2", "sender": "B", "receiver": "C", "amount": 5000, "timestamp": BASE + timedelta(minutes=10)},
        {"tx_id": "R3", "sender": "C", "receiver": "A", "amount": 5000, "timestamp": BASE + timedelta(minutes=20)},
    ]


def test_ring_auditor_flags_and_signs_ring():
    state = ring_auditor({"mule_transactions": _cycle_txns()})
    assert state["mule_rings"], "expected at least one fraud ring"
    ring = state["mule_rings"][0]
    assert ring["pattern_type"] == "cycle"
    assert "confidence" in ring
    # The ring dossier is HMAC-signed and verifies.
    dossiers = [d for d in state["dossiers"] if d["dossier_id"] == "DOS_RING_" + ring["ring_id"]]
    assert len(dossiers) == 1
    assert audit.verify_dossier_dict(dossiers[0]) is True
    assert dossiers[0]["payload"] == ring


def test_high_risk_ring_routed_to_review():
    state = ring_auditor({"mule_transactions": _cycle_txns()})
    review_ids = {q["ring_id"] for q in state["ring_hitl"]["review"]}
    assert review_ids, "high-risk ring should land in the human-review queue"
    for q in state["ring_hitl"]["review"]:
        assert q["risk_score"] >= 60.0


def test_ring_auditor_no_transactions_is_safe():
    state = ring_auditor({})
    assert state["mule_rings"] == []


def test_run_supervised_audit_route_invokes_ring_auditor():
    # Audit route must run the Ring-Auditor; with the mule graph supplied it flags a ring.
    invoices = [RetailSimulator.supplier_invoice(sku="SKU_MILK", amount=120.0)]
    state = run_supervised({"invoices_raw": invoices, "mule_transactions": _cycle_txns()})
    assert state["route"] == "audit_only"
    assert "mule_rings" in state and state["mule_rings"]
    assert "ring_hitl" in state


def test_payment_graph_alone_still_reaches_the_ring_auditor():
    """Review finding A: route() used to inspect only sales/inventory/invoices, so a
    mule-only state fell through to 'noop' and the Ring-Auditor silently never ran."""
    from src.agents.orchestrator import route
    state_in = {"mule_transactions": _cycle_txns()}
    assert route(state_in) == "ring_only"

    state = run_supervised(dict(state_in))
    assert state["mule_rings"], "ring detection must run without invoices present"
    assert state["ring_hitl"]["review"]


def test_empty_scan_populates_the_whole_state_contract():
    """Review finding B: the early-return path set only mule_rings, so consumers
    could KeyError depending purely on input shape."""
    state = ring_auditor({})
    assert state["mule_rings"] == []
    assert state["mule_suspicious_accounts"] == []
    assert state["ring_hitl"] == {"review": [], "monitor": []}
    assert state["mule_scan_truncated"] is False


def test_truncated_cycle_search_is_reported_not_hidden():
    """Review finding E: a wall-clock-truncated search must be marked, so a partial
    result is never signed as though it were exhaustive."""
    from src.core.mule.cycle_detector import detect_cycles_status
    from src.core.mule.graph_model import build_graph
    g = build_graph(_cycle_txns())

    results, truncated = detect_cycles_status(g)
    assert truncated is False and results

    # An already-exhausted budget must abort and say so, rather than claiming "no
    # cycles found". A negative budget is used because time.time() on Windows has
    # ~15ms resolution, so a 0.0 budget can measure elapsed == 0.0 and not trip.
    _partial, truncated = detect_cycles_status(g, time_budget_s=-1.0)
    assert truncated is True


def test_scan_truncation_flag_reaches_agent_state():
    state = ring_auditor({"mule_transactions": _cycle_txns()})
    assert state["mule_scan_truncated"] is False


def test_ring_and_finding_schemas_validate():
    from src.models.schemas import MuleRing, RingFinding
    state = ring_auditor({"mule_transactions": _cycle_txns()})
    ring = MuleRing.model_validate(state["mule_rings"][0])
    assert ring.pattern_type == "cycle"
    for a in state["mule_suspicious_accounts"]:
        f = RingFinding.model_validate(a)
        assert 0.0 <= f.suspicion_score <= 100.0
