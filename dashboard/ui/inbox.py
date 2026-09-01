"""Action-first inbox page."""

import streamlit as st

from dashboard.services.auth import can
from dashboard.services.session import latest_records, record_operator_decision, run_and_save
from dashboard.ui.components import empty_state, kpi, risk_badge, technical_details


PRESETS = {
    "Procurement mismatch": "Find low stock and reconcile an inflated supplier invoice.",
    "Fraud-ring investigation": "Surface a cycle and shell network for analyst review.",
    "Data-quality quarantine": "Show malformed and checksum-failed records before processing.",
    "Clean operations run": "Run a normal low-risk operations batch.",
}


def render(user, storage):
    st.info("Start here: run an analysis, then work the decisions that need you.")
    records = latest_records(storage)
    open_alerts = [a for a in records["alerts"] if a.get("status", "OPEN") == "OPEN"]
    state = st.session_state.get("state")
    procurement_queue = state.get("hitl_queue", {}).get("human", []) if state else []
    ring_queue = state.get("ring_hitl", {}).get("review", []) if state else []
    pending_subjects = {(d.get("subject_kind"), d.get("subject_id")) for d in records["decisions"]}
    pending_actions = [item for item in procurement_queue
                       if (item.get("kind"), item.get("id")) not in pending_subjects]
    pending_actions += [{"kind": "RING", "id": item.get("ring_id"),
                         "risk_score": item.get("risk_score"),
                         "pattern_type": item.get("pattern_type")}
                        for item in ring_queue
                        if ("RING", item.get("ring_id")) not in pending_subjects]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Needs your decision", len(pending_actions))
    with c2:
        kpi("Open investigations", len(open_alerts))
    with c3:
        kpi("Data quality issues", len(st.session_state.get("state", {}).get("rejected", [])))
    with c4:
        kpi("Evidence records", len(records["evidence"]))

    st.subheader("Run an analysis")
    preset = st.selectbox("Choose a starting scenario", list(PRESETS))
    st.caption(PRESETS[preset])
    if st.button("Run analysis", type="primary"):
        with st.spinner("Checking data, operations, and risk signals..."):
            run_and_save(preset)
        st.success("Analysis complete. Review the actions below.")
        st.rerun()

    st.subheader("What needs attention")
    queue = pending_actions
    if queue:
        st.markdown("#### Decisions awaiting you")
        for item in queue:
            key = f"{item['kind']}_{item['id']}"
            already = any(d.get("subject_kind") == item["kind"] and d.get("subject_id") == item["id"]
                          for d in records["decisions"])
            with st.container(border=True):
                verb = "review" if item["kind"] == "RING" else "approval"
                st.write(f"**{item['kind'].title()} {item['id']}** needs human {verb}.")
                st.caption("Approval records your decision only; it does not execute a payment or send a purchase order.")
                approve, reject = st.columns(2)
                capability = "review_fraud" if item["kind"] == "RING" else "approve_po"
                if approve.button("Approve", key="inbox-approve-" + key,
                                  disabled=already or not can(user, capability)):
                    action = "ESCALATED" if item["kind"] == "RING" else "APPROVED"
                    record_operator_decision(storage, user, item["kind"], item["id"], action, state)
                    st.success("Decision saved and signed.")
                    st.rerun()
                if reject.button("Reject", key="inbox-reject-" + key,
                                 disabled=already or not can(user, capability)):
                    action = "DISMISSED" if item["kind"] == "RING" else "REJECTED"
                    record_operator_decision(storage, user, item["kind"], item["id"], action, state)
                    st.success("Decision saved and signed.")
                    st.rerun()
    if not open_alerts and not st.session_state.get("state"):
        empty_state("Nothing is waiting", "Run an analysis to create a review queue.")
    elif not open_alerts:
        empty_state("No open alerts", "The latest analysis did not create an open investigation.")
    else:
        for alert in open_alerts[:10]:
            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"**{alert['title']}**")
                    st.write(alert["summary"])
                    st.caption(f"Type: {alert['alert_type']} · Subject: {alert['subject_id']}")
                with right:
                    risk_badge(alert.get("severity", "LOW"))
                    st.page_link("pages/3_Cases.py", label="Open case")

    if state:
        st.subheader("Latest analysis")
        steps = [
            ("Data checked", True),
            ("Operations analyzed", bool(state.get("demand_forecast") or state.get("route") == "audit_only")),
            ("Risk alerts generated", bool(state.get("payment_flags") or state.get("mule_rings"))),
            ("Decisions awaiting review", bool(state.get("hitl_queue", {}).get("human"))),
        ]
        cols = st.columns(4)
        for col, (label, done) in zip(cols, steps):
            col.metric(label, "Complete" if done else "Pending")
        technical_details("Technical agent trace", state.get("logs", []))
