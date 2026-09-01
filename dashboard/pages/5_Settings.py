import os

import streamlit as st

from dashboard.services.auth import ROLES
from dashboard.ui.navigation import shell

user, storage = shell("Settings", "Review workspace, access, storage, and runtime configuration.")
st.subheader("Current workspace")
st.write("**Demo workspace**")
st.caption("Seeded synthetic data is clearly labeled and can be reset by clearing the local .payguard store.")
st.subheader("Access")
st.write(f"Current user: **{user.display_name}**")
st.write(f"Role: **{user.role}**")
st.caption("Published mode uses OIDC/SSO. Local mode uses an explicit demo-user selector only when PAYGUARD_DEMO_MODE=true.")
st.write("Supported roles: " + ", ".join(ROLES))
st.subheader("Runtime")
st.write(f"Storage backend: **{storage.backend}**")
st.write(f"LLM backend: **{os.getenv('PAYGUARD_LLM_BACKEND', 'offline')}**")
st.warning("No payment, supplier submission, or external financial execution is available from this product.")

