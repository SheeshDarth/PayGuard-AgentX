"""Minimal OIDC boundary with an explicit local demo fallback."""

import os
import streamlit as st

from src.models.product import User
from dashboard.services.config import load_settings


ROLES = ["ADMIN", "OPERATIONS", "ANALYST", "VIEWER"]


def current_user() -> User:
    settings = load_settings()
    if hasattr(st, "user") and getattr(st.user, "is_logged_in", False):
        email = getattr(st.user, "email", "") or ""
        name = getattr(st.user, "name", "") or email or "SSO user"
        role = os.getenv("PAYGUARD_DEFAULT_ROLE", "VIEWER")
        return User(user_id=email or "oidc-user", display_name=name, email=email,
                    role=role if role in ROLES else "VIEWER")
    if settings.demo_mode:
        role = st.sidebar.selectbox("Demo role", ROLES, index=1, key="demo_role")
        return User(user_id="demo-operator", display_name="Demo Operator", role=role)
    if hasattr(st, "login"):
        st.info("Sign in with your organization account to continue.")
        if st.button("Sign in with SSO"):
            st.login("oidc")
    st.error("Sign-in is required. Configure OIDC or enable PAYGUARD_DEMO_MODE for local use.")
    st.stop()


def can(user, capability):
    permissions = {
        "manage_settings": {"ADMIN"},
        "approve_po": {"ADMIN", "OPERATIONS"},
        "review_fraud": {"ADMIN", "ANALYST"},
        "read": set(ROLES),
    }
    return user.role in permissions.get(capability, set())
