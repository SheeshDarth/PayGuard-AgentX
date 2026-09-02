"""Identity and role authorization for the operator UI.

UI-framework independent: the web layer passes a role in, this module owns who
may decide what. `can()` is enforced server-side on every decision endpoint, so
the browser cannot approve a purchase order by editing its own request.
"""

import os

from src.models.product import User
from dashboard.services.config import load_settings


ROLES = ["ADMIN", "OPERATIONS", "ANALYST", "VIEWER"]

PERMISSIONS = {
    "manage_settings": {"ADMIN"},
    "approve_po": {"ADMIN", "OPERATIONS"},
    "review_fraud": {"ADMIN", "ANALYST"},
    "read": set(ROLES),
}


def current_user(role=None) -> User:
    """Resolve the acting user.

    Demo mode trusts the role the UI selected -- that selector only exists when
    PAYGUARD_DEMO_MODE is on. Otherwise the role comes from the environment and
    the UI cannot raise its own privileges.
    """
    settings = load_settings()
    if settings.demo_mode and role in ROLES:
        return User(user_id="demo-operator", display_name="Demo Operator", role=role)
    default = os.getenv("PAYGUARD_DEFAULT_ROLE", "OPERATIONS")
    return User(user_id="operator", display_name="Operator",
                role=default if default in ROLES else "VIEWER")


def can(user, capability):
    return user.role in PERMISSIONS.get(capability, set())


def capability_matrix():
    """Role -> capability table, for the Settings screen."""
    return [{"role": role,
             "approve_po": role in PERMISSIONS["approve_po"],
             "review_fraud": role in PERMISSIONS["review_fraud"],
             "manage_settings": role in PERMISSIONS["manage_settings"]}
            for role in ROLES]
