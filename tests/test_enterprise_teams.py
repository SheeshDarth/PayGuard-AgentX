"""Enterprise retail profiles and agent-team safety contracts."""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from dashboard.services.storage import SQLiteStorage
from dashboard.services.workflows import RETAILER_PROFILES, run_scenario
from src.agents.teams import default_teams, team_plan, validate_custom_team
from web.server import Handler, bootstrap_payload


def _post(base, path, body):
    request = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


def test_retailer_profiles_are_explicit_about_public_vs_representative_data():
    assert {"GENERIC", "WALMART", "DMART", "TARGET"}.issubset(RETAILER_PROFILES)
    assert "public" in RETAILER_PROFILES["WALMART"]["data_note"].lower()
    assert "representative" in RETAILER_PROFILES["DMART"]["data_note"].lower()
    assert "representative" in RETAILER_PROFILES["TARGET"]["data_note"].lower()


def test_supervised_run_exposes_active_and_standby_enterprise_teams():
    state = run_scenario("3 · Fraud Ring", retailer_profile="TARGET")
    by_id = {team["team_id"]: team for team in state["team_plan"]}
    assert state["retailer_profile"] == "TARGET"
    assert by_id["TEAM_RISK"]["status"] == "ACTIVE"
    assert by_id["TEAM_STORE_OPS"]["status"] == "STANDBY"
    assert by_id["TEAM_CONTROL"]["status"] == "ACTIVE"


def test_custom_team_validation_only_accepts_known_agents():
    name, mission, agents = validate_custom_team(
        "Freshness Response", "Own high-priority fresh-goods availability and escalation.",
        ["DQ-Sentinel", "Stock-Watcher", "HITL Controller"],
    )
    assert name == "Freshness Response"
    assert agents == ["DQ-Sentinel", "Stock-Watcher", "HITL Controller"]
    try:
        validate_custom_team("Bad team", "This should fail because its agent is invented.", ["Auto-Buyer"])
    except ValueError as error:
        assert "Unknown agent" in str(error)
    else:
        raise AssertionError("an invented agent must be rejected")


def test_team_configuration_persists_but_workspace_reset_keeps_it(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "teams.sqlite"))
    team = {**default_teams()[0], "team_id": "TEAM_CUSTOM_FRESH", "is_custom": True}
    storage.save_team(team)
    storage.reset()
    assert storage.list_teams()[0]["team_id"] == "TEAM_CUSTOM_FRESH"


def test_team_endpoint_requires_admin_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYGUARD_SQLITE_PATH", str(tmp_path / "team-api.sqlite"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    payload = {"name": "Freshness Response", "mission": "Own critical availability and safe escalation.",
               "agents": ["DQ-Sentinel", "Stock-Watcher"], "role": "ADMIN"}
    try:
        denied, _ = _post(base, "/api/teams", {**payload, "role": "VIEWER"})
        created, data = _post(base, "/api/teams", payload)
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert denied == 403
    assert created == 201
    assert any(team["name"] == "Freshness Response" for team in data["agent_teams"])


def test_bootstrap_includes_built_in_agent_teams():
    payload = bootstrap_payload("OPERATIONS")
    names = {team["name"] for team in payload["agent_teams"]}
    assert {"Store Operations Team", "Procurement Integrity Team", "Risk Intelligence Team"}.issubset(names)

