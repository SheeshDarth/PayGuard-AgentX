"""Session and persistence orchestration for Streamlit pages."""

import streamlit as st

from dashboard.services.auth import current_user
from dashboard.services.storage import get_storage
from dashboard.services.workflows import plain_alerts, run_scenario
from src.models.product import Case, EvidenceRecord, RunSummary
from src.core import audit


def boot(page_title="PayGuard Operations"):
    user = current_user()
    return user, get_storage()


def run_and_save(preset):
    state = run_scenario(preset)
    storage = get_storage()
    alerts = plain_alerts(state)
    for alert in alerts:
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
    summary = RunSummary(run_id=state["run_id"], route=state.get("route", "noop"),
                         preset=preset, rejected_count=len(state.get("rejected", [])),
                         alert_count=len(alerts), ring_count=len(state.get("mule_rings", []))).model_dump()
    storage.save_run(state["run_id"], summary)
    st.session_state["state"] = state
    st.session_state["last_run"] = summary
    return state


def current_state():
    return st.session_state.get("state")


def latest_records(storage):
    return {"runs": storage.list_runs(), "alerts": storage.list_alerts(),
            "cases": storage.list_cases(), "decisions": storage.list_decisions(),
            "evidence": storage.list_evidence()}


def record_operator_decision(storage, user, subject_kind, subject_id, action, state=None):
    """Persist a role-authorized decision and its signed evidence."""
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
    return payload
