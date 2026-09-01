"""Shared product shell navigation."""

import streamlit as st

from dashboard.services.session import boot
from dashboard.ui.theme import apply_theme


def shell(page_title, subtitle):
    st.set_page_config(page_title=page_title, layout="wide", initial_sidebar_state="expanded")
    user, storage = boot(page_title)
    theme = st.sidebar.radio("Theme", ["Light", "Dark"], horizontal=True)
    apply_theme(theme.lower())
    st.sidebar.markdown("### PayGuard Operations")
    st.sidebar.caption("Guarded retail, procurement, and risk workflows")
    st.sidebar.page_link("app.py", label="Action Inbox")
    st.sidebar.page_link("pages/1_Operations.py", label="Operations")
    st.sidebar.page_link("pages/2_Analyst_Workspace.py", label="Analyst Workspace")
    st.sidebar.page_link("pages/3_Cases.py", label="Cases")
    st.sidebar.page_link("pages/4_Evidence.py", label="Evidence")
    st.sidebar.page_link("pages/5_Settings.py", label="Settings")
    st.sidebar.divider()
    st.sidebar.caption(f"{user.display_name} · {user.role} · {storage.backend}")
    st.sidebar.caption("Ready · No external payment execution")
    st.markdown(f'<div class="pg-title">{page_title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pg-muted">{subtitle}</div>', unsafe_allow_html=True)
    return user, storage
