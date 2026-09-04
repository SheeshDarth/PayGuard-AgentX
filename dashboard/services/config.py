"""Small, dependency-light configuration boundary for the product shell."""

import os
import warnings
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    audit_key: str
    llm_backend: str
    llm_model: str
    database_url: str
    sqlite_path: str
    demo_mode: bool
    oidc_client_id: str
    oidc_client_secret: str
    oidc_discovery_url: str
    oidc_redirect_uri: str

    @property
    def oidc_configured(self):
        return all((self.oidc_client_id, self.oidc_client_secret,
                    self.oidc_discovery_url, self.oidc_redirect_uri))


def load_settings() -> Settings:
    """Load .env without overriding explicit process environment variables."""
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
    except ImportError:
        # Offline installs do not require python-dotenv; process variables still work.
        pass
    key = os.getenv("PAYGUARD_AUDIT_KEY", "change-me-to-a-long-random-secret")
    if key.startswith("change-me") or key in {"demo-key", "payguard-demo-key"}:
        warnings.warn("PAYGUARD_AUDIT_KEY is a public/demo value; use a private key for trusted evidence.",
                      RuntimeWarning, stacklevel=2)
    backend = os.getenv("PAYGUARD_LLM_BACKEND", "offline").lower()
    if backend not in {"offline", "ollama", "vllm"}:
        raise ValueError("PAYGUARD_LLM_BACKEND must be offline, ollama, or vllm")
    return Settings(key, backend, os.getenv("PAYGUARD_LLM_MODEL", ""),
                    os.getenv("PAYGUARD_DATABASE_URL", ""),
                    os.getenv("PAYGUARD_SQLITE_PATH", ".payguard/workspace.sqlite"),
                    os.getenv("PAYGUARD_DEMO_MODE", "true").lower() == "true",
                    os.getenv("PAYGUARD_OIDC_CLIENT_ID", ""),
                    os.getenv("PAYGUARD_OIDC_CLIENT_SECRET", ""),
                    os.getenv("PAYGUARD_OIDC_DISCOVERY_URL", ""),
                    os.getenv("PAYGUARD_OIDC_REDIRECT_URI", ""))
