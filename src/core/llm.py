"""
LLM access layer for PayGuard-AgentX.

Self-hosted only, per the Agentic AI course constraint ("self-hosted medium or
small language models over a provider, such as Ollama or vLLM"). No cloud provider
is ever called. Backends, selected by environment, in priority order:
  1. Ollama  (local runtime, default demo path)  -- PAYGUARD_LLM_BACKEND=ollama
  2. vLLM    (self-hosted OpenAI-compatible server) -- PAYGUARD_LLM_BACKEND=vllm
  3. Offline deterministic stub                    -- default when nothing configured

Both live backends are plain in-process HTTP calls (urllib) to a locally hosted
server -- no external SDK, no API key, nothing leaves the machine. The offline stub
keeps the pipeline, tests, and demo fully runnable with no model, no GPU, and no
network: if the model is unreachable, agents receive a clearly-marked stub, never a crash.

Environment (see .env.example):
  PAYGUARD_LLM_BACKEND   ollama | vllm | offline
  PAYGUARD_LLM_MODEL     e.g. phi4-mini (ollama) or the model name served by vLLM
  OLLAMA_HOST            default http://localhost:11434
  VLLM_HOST             default http://localhost:8000  (vLLM OpenAI-compatible server)
"""

import json
import os
import urllib.request

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "phi4-mini"
DEFAULT_VLLM_HOST = "http://localhost:8000"


def _backend() -> str:
    b = os.getenv("PAYGUARD_LLM_BACKEND", "").strip().lower()
    if b in ("ollama", "vllm", "offline"):
        return b
    # Inference: a configured model implies a live backend; default local-first.
    if os.getenv("PAYGUARD_LLM_MODEL"):
        return "ollama"
    return "offline"


def _reachable(url, timeout=0.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _ollama_reachable(timeout=0.5) -> bool:
    host = os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
    return _reachable(host + "/api/tags", timeout)


def _vllm_reachable(timeout=0.5) -> bool:
    host = os.getenv("VLLM_HOST", DEFAULT_VLLM_HOST)
    return _reachable(host + "/v1/models", timeout)


def is_live() -> bool:
    """True only when a self-hosted backend is configured AND reachable."""
    b = _backend()
    if b == "ollama":
        return _ollama_reachable()
    if b == "vllm":
        return _vllm_reachable()
    return False


def complete(prompt, system=None, max_tokens=256, temperature=0.2):
    """Return model text for the prompt, or a deterministic offline stub when not live."""
    b = _backend()
    if b == "ollama" and _ollama_reachable():
        try:
            return _ollama_complete(prompt, system, max_tokens, temperature)
        except Exception:
            return _offline_stub(prompt, system)
    if b == "vllm" and _vllm_reachable():
        try:
            return _vllm_complete(prompt, system, max_tokens, temperature)
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


def _vllm_complete(prompt, system, max_tokens, temperature):
    """Call a self-hosted vLLM OpenAI-compatible /v1/chat/completions endpoint."""
    host = os.getenv("VLLM_HOST", DEFAULT_VLLM_HOST)
    model = os.getenv("PAYGUARD_LLM_MODEL", "")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": temperature}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(host + "/v1/chat/completions", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = json.loads(r.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


def _offline_stub(prompt, system=None):
    """Deterministic stand-in used when no LLM is reachable (keeps output clean and testable)."""
    return "[offline-stub] " + " ".join(str(prompt).split()[:20])
