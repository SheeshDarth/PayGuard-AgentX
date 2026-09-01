"""Small, readable UI primitives shared by all pages."""

import streamlit as st


RISK = {"CRITICAL": "#991B1B", "HIGH": "#C2410C", "MEDIUM": "#A16207",
        "LOW": "#1D4ED8", "NORMAL": "#166534"}


def page_header(title, subtitle, user):
    st.markdown(f'<div class="pg-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pg-muted">{subtitle}</div>', unsafe_allow_html=True)
    st.caption(f"Workspace: Demo workspace · Signed in as {user.display_name} · Role: {user.role}")


def kpi(label, value, help_text=""):
    st.metric(label, value, help=help_text or None)


def risk_badge(level):
    color = RISK.get(level, RISK["NORMAL"])
    st.markdown(f'<span style="color:{color};font-weight:700">● {level.title()}</span>',
                unsafe_allow_html=True)


def empty_state(title, message, action_label=None):
    st.info(f"**{title}**\n\n{message}")
    return action_label


def technical_details(title, value):
    with st.expander(title):
        st.json(value)
