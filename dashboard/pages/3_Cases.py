import streamlit as st

from dashboard.services.session import latest_records
from dashboard.ui.components import empty_state, risk_badge
from dashboard.ui.navigation import shell

user, storage = shell("Cases", "Track investigations, ownership, decisions, and next steps.")
cases = latest_records(storage)["cases"]
if not cases:
    empty_state("No cases yet", "Run an analysis from Action Inbox to create the first case.")
    st.stop()

query = st.text_input("Search cases")
filtered = [c for c in cases if not query or query.lower() in (c.get("title", "") + c.get("summary", "")).lower()]
st.caption(f"Showing {len(filtered)} of {len(cases)} case(s)")
for case in filtered:
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.markdown(f"**{case['title']}** · {case['case_id']}")
            st.write(case["summary"])
            st.caption(f"Status: {case.get('status', 'OPEN')} · Related: {', '.join(case.get('related_ids', []))}")
        with right:
            risk_badge(case.get("severity", "LOW"))

