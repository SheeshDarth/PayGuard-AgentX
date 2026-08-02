"""
LLM access layer for PayGuard-AgentX.

Backends, selected by environment, in priority order:
  1. Ollama  (local, default demo path)   -- PAYGUARD_LLM_BACKEND=ollama
  2. LiteLLM (cloud / other providers)     -- PAYGUARD_LLM_BACKEND=litellm
  3. Offline deterministic stub            -- default when nothing is configured

The offline stub keeps the pipeline, tests, and demo fully runnable with no model,
no GPU, and no network. This matches the project degrade-gracefully rule: if the
model is unreachable, agents receive a clearly-marked stub, never a crash.

Environment (see .env.example):
  PAYGUARD_LLM_BACKEND   ollama | litellm | offline
  PAYGUARD_LLM_MODEL     e.g. phi4-mini (ollama) or gemini/gemini-1.5-flash (litellm)
  OLLAMA_HOST            default http://localhost:11434
  provider keys for litellm (GEMINI_API_KEY, OPENAI_API_KEY, ...)
"""

import json
import os
import urllib.request

_PROVIDER_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
                  "ANTHROPIC_API_KEY", "LITELLM_API_KEY")
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "phi4-mini"


def _backend() -> str:
    b = os.getenv("PAYGUARD_LLM_BACKEND", "").strip().lower()
    if b in ("ollama", "litellm", "offline"):
        return b
    # Inference: a configured model implies a live backend; default local-first.
    if os.getenv("PAYGUARD_LLM_MODEL"):
        return "ollama"
    return "offline"


def _ollama_reachable(timeout=0.5) -> bool:
    host = os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
    try:
        with urllib.request.urlopen(host + "/api/tags", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def is_live() -> bool:
    """True only when a real backend is configured AND reachable."""
    b = _backend()
    if b == "offline":
        return False
    if b == "litellm":
        if not any(os.getenv(k) for k in _PROVIDER_KEYS):
            return False
        try:
            import litellm  # noqa: F401
            return True
        except Exception:
            return False
    if b == "ollama":
        return _ollama_reachable()
    return False


def complete(prompt, system=None, max_tokens=256, temperature=0.2):
    """Return model text for the prompt, or a deterministic offline stub when not live."""
    b = _backend()
    if b == "ollama" and _ollama_reachable():
        try:
            return _ollama_complete(prompt, system, max_tokens, temperature)
        except Exception:
            return _offline_stub(prompt, system)
    if b == "litellm" and is_live():
        try:
            return _litellm_complete(prompt, system, max_tokens, temperature)
        except Exception:
            return _offline_stub(prompt, system)
    return _offline_stub(prompt, system)


def _ollama_complete(prompt, system, max_tokens, temperature):
    host = os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
    model = os.getenv("PAYGUARD_LLM_MODEL", DEFAULT_OLLAMA_MODEL)
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system or "",
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(host + "/api/generate", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = json.loads(r.read().decode("utf-8"))
    return (body.get("response") or "").strip()


def _litellm_complete(prompt, system, max_tokens, temperature):
    import litellm
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = litellm.completion(model=os.getenv("PAYGUARD_LLM_MODEL"), messages=messages,
                              max_tokens=max_tokens, temperature=temperature)
    return resp["choices"][0]["message"]["content"].strip()


def _offline_stub(prompt, system=None):
    """Deterministic stand-in used when no LLM is reachable (keeps output clean and testable)."""
    return "[offline-stub] " + " ".join(str(prompt).split()[:20])
