import os

from dashboard.services.auth import can
from dashboard.services.config import load_settings
from dashboard.services.storage import SQLiteStorage
from dashboard.services.workflows import plain_alerts, run_scenario
from dashboard.ui.theme import DARK, LIGHT
from src.models.product import User


def test_product_presets_are_readable_and_seed_alerts():
    state = run_scenario("Procurement mismatch")
    alerts = plain_alerts(state)
    assert state["preset"] == "Procurement mismatch"
    assert alerts
    assert all(alert["title"] and alert["summary"] for alert in alerts)


def test_sqlite_product_records_survive_new_connection(tmp_path):
    path = tmp_path / "workspace.sqlite"
    first = SQLiteStorage(str(path))
    first.save_alert({"alert_id": "A1", "title": "Invoice needs review"})
    second = SQLiteStorage(str(path))
    assert second.list_alerts()[0]["alert_id"] == "A1"


def test_role_permissions_are_explicit():
    ops = User(user_id="ops", display_name="Ops", role="OPERATIONS")
    analyst = User(user_id="analyst", display_name="Analyst", role="ANALYST")
    viewer = User(user_id="viewer", display_name="Viewer", role="VIEWER")
    assert can(ops, "approve_po") and not can(ops, "review_fraud")
    assert can(analyst, "review_fraud") and not can(analyst, "approve_po")
    assert not can(viewer, "approve_po") and not can(viewer, "review_fraud")


def test_theme_tokens_include_accessible_semantic_values():
    for tokens in (LIGHT, DARK):
        assert {"bg", "surface", "text", "muted", "border", "primary"}.issubset(tokens)


def test_env_process_values_are_preserved(monkeypatch):
    monkeypatch.setenv("PAYGUARD_LLM_BACKEND", "offline")
    monkeypatch.setenv("PAYGUARD_AUDIT_KEY", "private-test-key")
    settings = load_settings()
    assert settings.llm_backend == "offline"
    assert settings.audit_key == "private-test-key"
