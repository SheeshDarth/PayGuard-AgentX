from pathlib import Path

from dashboard.services.auth import can
from dashboard.services.config import load_settings
from dashboard.services.storage import SQLiteStorage
from dashboard.services.workflows import plain_alerts, run_scenario
from src.models.product import User

WEB = Path(__file__).resolve().parent.parent / "web" / "static"


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


def test_ui_defines_semantic_theme_tokens_for_light_and_dark():
    css = (WEB / "app.css").read_text(encoding="utf-8")
    for token in ("--bg", "--surface", "--text", "--muted", "--border", "--primary"):
        assert f"{token}:" in css, f"missing semantic token {token}"
    # Dark must be reachable both by system preference and by the explicit toggle,
    # or one of the two paths silently renders unreadable text.
    assert "prefers-color-scheme: dark" in css
    assert '[data-theme="dark"]' in css


def test_ui_is_self_contained_and_offline():
    """The dashboard must not load anything off-machine: the offline guarantee
    fails the moment a CDN font or script is needed to render."""
    # The SVG/XHTML namespace URIs are identifiers, not fetches -- the browser
    # never requests them, so they are the one allowed absolute URL.
    namespaces = ("http://www.w3.org/2000/svg", "http://www.w3.org/1999/xhtml")
    for name in ("index.html", "app.css", "app.js", "auralis.js"):
        body = (WEB / name).read_text(encoding="utf-8")
        for ns in namespaces:
            body = body.replace(ns, "")
        for scheme in ("http://", "https://", 'src="//', "url(//"):
            assert scheme not in body, f"{name} references an external URL ({scheme})"


def test_env_process_values_are_preserved(monkeypatch):
    monkeypatch.setenv("PAYGUARD_LLM_BACKEND", "offline")
    monkeypatch.setenv("PAYGUARD_AUDIT_KEY", "private-test-key")
    settings = load_settings()
    assert settings.llm_backend == "offline"
    assert settings.audit_key == "private-test-key"
