"""Central environment configuration for PayGuard-AgentX.

Configuration is loaded once, without overriding variables already supplied by
the process.  Keeping this in one module makes the offline demo and live local
backends behave consistently from the CLI, dashboard, and MCP server.
"""

import os
import warnings

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only in minimal installs
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv(override=False)


DEFAULT_AUDIT_KEY = "payguard-dev-demo-key-change-me"
_warned_demo_key = False


def audit_key() -> str:
    """Return the configured audit key, warning when the public demo key is used."""
    global _warned_demo_key
    value = os.getenv("PAYGUARD_AUDIT_KEY", "").strip()
    if not value or value == DEFAULT_AUDIT_KEY:
        if not _warned_demo_key:
            _warned_demo_key = True
            warnings.warn(
                "PAYGUARD_AUDIT_KEY is not set to a private value; evidence is suitable "
                "for demonstration only. Set PAYGUARD_AUDIT_KEY for trusted evidence.",
                RuntimeWarning,
                stacklevel=2,
            )
        return DEFAULT_AUDIT_KEY
    if len(value) < 16:
        warnings.warn("PAYGUARD_AUDIT_KEY is shorter than the recommended 16 characters.",
                      RuntimeWarning, stacklevel=2)
    return value


def memory_path() -> str | None:
    return os.getenv("PAYGUARD_MEMORY_PATH") or None


def graph_path() -> str | None:
    return os.getenv("PAYGUARD_GRAPH_PATH") or None
