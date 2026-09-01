"""Accessible semantic theme tokens for the product shell."""

import streamlit as st


LIGHT = {"bg": "#F8FAFC", "surface": "#FFFFFF", "text": "#0F172A", "muted": "#475569",
         "border": "#CBD5E1", "primary": "#1D4ED8", "success": "#166534", "warning": "#92400E",
         "danger": "#991B1B"}
DARK = {"bg": "#020617", "surface": "#0F172A", "text": "#F8FAFC", "muted": "#CBD5E1",
        "border": "#475569", "primary": "#60A5FA", "success": "#86EFAC", "warning": "#FCD34D",
        "danger": "#FCA5A5"}


def apply_theme(mode="light"):
    tokens = DARK if mode == "dark" else LIGHT
    st.markdown(f"""
    <style>
    :root {{ color-scheme: {mode}; }}
    html, body, [class*="st-"] {{ font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .stApp {{ background: {tokens['bg']}; color: {tokens['text']}; font-size: 16px; line-height: 1.5; }}
    [data-testid="stSidebar"] {{ background: {tokens['surface']}; border-right: 1px solid {tokens['border']}; }}
    .pg-card {{ background: {tokens['surface']}; border: 1px solid {tokens['border']}; border-radius: 12px;
                padding: 1rem; margin-bottom: .75rem; }}
    .pg-muted {{ color: {tokens['muted']}; }}
    .pg-title {{ font-size: 2rem; font-weight: 700; letter-spacing: -.02em; }}
    .pg-kpi {{ font-size: 1.75rem; font-weight: 700; font-variant-numeric: tabular-nums; }}
    .pg-action {{ border-left: 4px solid {tokens['primary']}; }}
    button {{ min-height: 44px; }}
    </style>
    """, unsafe_allow_html=True)
