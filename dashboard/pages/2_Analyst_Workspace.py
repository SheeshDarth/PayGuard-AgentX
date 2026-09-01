import pandas as pd
import streamlit as st

from dashboard.services.session import current_state
from dashboard.ui.components import empty_state, risk_badge, technical_details
from dashboard.ui.navigation import shell

user, storage = shell("Analyst Workspace", "Investigate suspicious networks and explain why they were flagged.")
state = current_state()
if not state:
    empty_state("No investigation yet", "Run the Fraud-ring investigation scenario from Action Inbox.")
    st.stop()

rings = state.get("mule_rings", [])
accounts = state.get("mule_suspicious_accounts", [])
if not rings:
    empty_state("No rings detected", "Try the Fraud-ring investigation scenario to load the seeded network.")
    st.stop()

st.subheader("Investigation summary")
c1, c2, c3 = st.columns(3)
c1.metric("Fraud rings", len(rings))
c2.metric("Suspicious accounts", len(accounts))
c3.metric("False-positive control", "Payroll not flagged")

for ring in rings:
    with st.container(border=True):
        st.markdown(f"### {ring['ring_id']} · {ring['pattern_type'].replace('_', ' ').title()}")
        risk_badge("HIGH" if ring["risk_score"] >= 60 else "MEDIUM")
        st.write(f"This finding connects **{len(ring['member_accounts'])} accounts** with a risk score of **{ring['risk_score']:.1f}/100**.")
        st.write("Recommended next step: review supporting transactions and decide whether to escalate or dismiss.")
        st.dataframe(pd.DataFrame({"Account": ring["member_accounts"]}), use_container_width=True, hide_index=True)
        technical_details("Detection signals", ring)

st.subheader("Payment network")
if state.get("mule_transactions"):
    st.dataframe(pd.DataFrame(state["mule_transactions"]), use_container_width=True, hide_index=True)

