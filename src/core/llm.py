"""
LLM access layer for PayGuard-AgentX.

Wraps a chat model (via LiteLLM) behind a single complete() call. When no model
or API key is configured -- or litellm is not installed -- it returns a
deterministic offline stub so the pipeline, tests, and demo run with no network
and no credentials. This is what lets every agent keep an LLM-HOOK while staying
fully runnable offline.

Configure a live model with environment variables (see .env.example):
    PAYGUARD_LLM_MODEL   e.g. gemini/gemini-1.5-flash
    plus the provider key LiteLLM expects, e.g. GEMINI_API_KEY
"""

import os

_PROVIDER_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
                  "ANTHROPIC_API_KEY", "LITELLM_API_KEY")


def is_live() -> bool:
    """True only when a model AND a provider key are configured and litellm imports."""
    if not os.getenv("PAYGUARD_LLM_MODEL"):
        return False
    if not any(os.getenv(k) for k in _PROVIDER_KEYS):
        return False
    try:
        import litellm  # noqa: F401
    except Exception:
        return False
    return True


def complete(prompt, system=None, max_tokens=256, temperature=0.2):
    """Return model text for the prompt, or a deterministic offline stub when not live."""
    if not is_live():
        return _offline_stub(prompt, system)
    import litellm
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = litellm.completion(
        model=os.getenv("PAYGUARD_LLM_MODEL"),
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp["choices"][0]["message"]["content"].strip()


def _offline_stub(prompt, system=None):
    """Deterministic stand-in used when no LLM is configured (keeps output clean and testable)."""
    return "[offline-stub] " + " ".join(str(prompt).split()[:20])
