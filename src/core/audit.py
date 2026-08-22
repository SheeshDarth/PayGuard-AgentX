"""
Tamper-evident audit signing for PayGuard-AgentX.

Uses HMAC-SHA256 over a canonical JSON body with a server-held secret key.
This is a real keyed integrity control — NOT a bare self-supplied SHA-256 of the
same payload (the weakness flagged in the PayGuard-AgentX council review). An
attacker who controls the payload cannot forge a valid signature without the key.

Key resolution: PAYGUARD_AUDIT_KEY env var, else a clearly-labelled dev demo key.
"""

import hashlib
import hmac
import json
import os
import warnings
from datetime import datetime, timezone
from src.models.schemas import EvidenceDossier

DEFAULT_DEMO_KEY = "payguard-dev-demo-key-change-me"


_warned_default_key = False


def _secret(key: str | None = None) -> bytes:
    """Resolve the signing secret. Falls back to the demo key, but never silently:
    that key is published in this repository, so anyone who can read the source can
    forge a signature. Warning once makes the weakened guarantee visible instead of
    letting a demo run masquerade as tamper-evident. The returned bytes -- and so the
    signing algorithm -- are unchanged."""
    global _warned_default_key
    resolved = key or os.getenv("PAYGUARD_AUDIT_KEY")
    if not resolved:
        if not _warned_default_key:
            _warned_default_key = True
            warnings.warn(
                "PAYGUARD_AUDIT_KEY is not set -- signing with the public dev demo key. "
                "Dossiers are NOT tamper-evident against anyone who can read this repo. "
                "Set PAYGUARD_AUDIT_KEY for any run whose evidence is meant to be trusted.",
                RuntimeWarning, stacklevel=2)
        resolved = DEFAULT_DEMO_KEY
    return resolved.encode("utf-8")


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(payload: dict, key: str | None = None) -> str:
    """Return the HMAC-SHA256 hex digest of a canonicalised payload."""
    return hmac.new(_secret(key), _canonical(payload), hashlib.sha256).hexdigest()


def verify(payload: dict, signature: str, key: str | None = None) -> bool:
    """Constant-time verification of a payload against its signature."""
    return hmac.compare_digest(sign(payload, key), signature)


def _dossier_body(dossier_id: str, subject_id: str, payload: dict) -> dict:
    return {"dossier_id": dossier_id, "subject_id": subject_id, "payload": payload}


def build_dossier(dossier_id: str, subject_id: str, summary: str, payload: dict,
                  key: str | None = None) -> EvidenceDossier:
    """Build a signed EvidenceDossier attesting to a consequential action."""
    body = _dossier_body(dossier_id, subject_id, payload)
    return EvidenceDossier(
        dossier_id=dossier_id,
        subject_id=subject_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        payload=payload,
        signature=sign(body, key),
    )


def verify_dossier_dict(d: dict, key: str | None = None) -> bool:
    """Verify a dossier that has been serialised to a plain dict (e.g. inside pipeline state)."""
    body = _dossier_body(d["dossier_id"], d["subject_id"], d["payload"])
    return verify(body, d["signature"], key)
