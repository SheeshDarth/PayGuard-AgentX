"""Run and persistence orchestration, independent of any UI framework.

Holds the last run in memory so a browser refresh does not lose it; everything
durable (runs, alerts, cases, decisions, evidence) goes through the storage
boundary.
"""

from dashboard.services.storage import get_storage
from dashboard.services.workflows import plain_alerts, run_scenario
from datetime import datetime, timezone
import uuid
from src.core import audit
from src.models.product import Case, EvidenceRecord, RunSummary


_LAST_RUN = {"state": None}


def current_state():
    if _LAST_RUN["state"] is None:
        records = latest_records(get_storage())
        if records["runs"]:
            _LAST_RUN["state"] = records["runs"][0].get("state")
    return _LAST_RUN["state"]


def set_state(state):
    _LAST_RUN["state"] = state
    return state


def clear_state():
    _LAST_RUN["state"] = None


def run_and_save(preset, storage=None):
    """Execute a scenario and persist everything consequential it produced."""
    storage = storage or get_storage()
    state = run_scenario(preset)
    for alert in plain_alerts(state):
        alert["status"] = "OPEN"
        alert["run_id"] = state["run_id"]
        storage.save_alert(alert)
        storage.save_case(Case(case_id="CASE_" + alert["alert_id"], title=alert["title"],
                               summary=alert["summary"], severity=alert["severity"],
                               related_ids=[alert["subject_id"]]).model_dump())
    for dossier in state.get("dossiers", []):
        storage.save_evidence(EvidenceRecord(
            evidence_id=dossier["dossier_id"], subject_id=dossier.get("subject_id", ""),
            evidence_type="Pipeline evidence", summary=dossier.get("summary", ""),
            verified=True, dossier=dossier).model_dump())
    summary = RunSummary(
        run_id=state["run_id"], route=state.get("route", "noop"), preset=preset,
        rejected_count=len(state.get("rejected", [])),
        alert_count=len(plain_alerts(state)),
        ring_count=len(state.get("mule_rings", []))).model_dump()
    summary["state"] = state
    storage.save_run(state["run_id"], summary)
    storage.save_audit_event({"event_id": "EVENT_" + uuid.uuid4().hex[:12],
                              "event_type": "RUN_COMPLETED", "actor_id": "system",
                              "subject_id": state["run_id"],
                              "created_at": datetime.now(timezone.utc).isoformat()})
    return set_state(state)


def latest_records(storage):
    return {"runs": storage.list_runs(), "alerts": storage.list_alerts(),
            "cases": storage.list_cases(), "decisions": storage.list_decisions(),
            "evidence": storage.list_evidence(), "audit_events": storage.list_audit_events()}


def record_operator_decision(storage, user, subject_kind, subject_id, action, state=None):
    """Persist a decision and its signed evidence, and reflect it in the run."""
    decision_id = f"DECISION_{subject_kind}_{subject_id}"
    payload = {"decision_id": decision_id, "subject_kind": subject_kind,
               "subject_id": subject_id, "action": action, "actor_id": user.user_id,
               "workspace_id": user.workspace_id}
    dossier = audit.build_dossier("DOS_" + decision_id, subject_id,
                                  f"Operator disposition: {action}", payload).model_dump()
    payload["dossier_id"] = dossier["dossier_id"]
    storage.save_decision(payload)
    storage.save_evidence(EvidenceRecord(
        evidence_id=dossier["dossier_id"], subject_id=subject_id,
        evidence_type="Operator decision", summary=dossier["summary"],
        verified=True, dossier=dossier).model_dump())
    storage.save_audit_event({"event_id": "EVENT_" + uuid.uuid4().hex[:12],
                              "event_type": "OPERATOR_DECISION", "actor_id": user.user_id,
                              "subject_id": subject_id, "action": action,
                              "created_at": datetime.now(timezone.utc).isoformat()})
    if state is not None:
        if subject_kind == "PO" and state.get("po_draft", {}).get("po_id") == subject_id:
            state["po_draft"]["status"] = action
        for dispute in state.get("dispute_drafts", []):
            if subject_kind == "DISPUTE" and dispute.get("dispute_id") == subject_id:
                dispute["status"] = action
        for ring in state.get("mule_rings", []):
            if subject_kind == "RING" and ring.get("ring_id") == subject_id:
                ring["disposition"] = action
    # Keep the persisted case view aligned with the operator disposition.
    for case in storage.list_cases():
        if subject_id in case.get("related_ids", []):
            case["status"] = "ESCALATED" if action == "ESCALATED" else (
                "DISMISSED" if action == "DISMISSED" else "RESOLVED")
            storage.save_case(case)
    if state is not None and state.get("run_id"):
        prior = next((run for run in storage.list_runs() if run.get("run_id") == state["run_id"]), {})
        prior["state"] = state
        storage.save_run(state["run_id"], prior)
    return payload


def reset(storage):
    storage.reset()
    storage.save_audit_event({"event_id": "EVENT_" + uuid.uuid4().hex[:12],
                              "event_type": "WORKSPACE_RESET", "actor_id": "operator",
                              "subject_id": "workspace", "created_at": datetime.now(timezone.utc).isoformat()})
    clear_state()
