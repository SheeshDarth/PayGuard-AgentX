import json

import pandas as pd
import streamlit as st

from dashboard.services.session import latest_records
from dashboard.ui.components import empty_state
from dashboard.ui.navigation import shell
from src.core import audit

user, storage = shell("Evidence", "Search signed records and inspect the reasoning behind each decision.")
evidence = latest_records(storage)["evidence"]
if not evidence:
    empty_state("No evidence yet", "Run an analysis from Action Inbox to create signed evidence.")
    st.stop()

query = st.text_input("Search evidence")
filtered = [e for e in evidence if not query or query.lower() in json.dumps(e, default=str).lower()]
st.dataframe(pd.DataFrame([{"Evidence ID": e["evidence_id"], "Subject": e["subject_id"],
                           "Type": e["evidence_type"], "Verified": audit.verify_dossier_dict(e["dossier"])}
                          for e in filtered]), use_container_width=True, hide_index=True)

with st.expander("Demo tools: tamper verification"):
    if not filtered:
        st.info("No evidence matches this search.")
        st.stop()
    selected = st.selectbox("Evidence record", [e["evidence_id"] for e in filtered])
    item = next(e for e in filtered if e["evidence_id"] == selected)
    tamper = st.checkbox("Tamper with payload")
    dossier = json.loads(json.dumps(item["dossier"], default=str))
    if tamper:
        dossier["payload"]["_injected"] = "attacker-controlled"
    valid = audit.verify_dossier_dict(dossier)
    (st.success if valid else st.error)("Signature valid" if valid else "Signature invalid: payload changed")

