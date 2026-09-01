"""Non-failing smoke checks for optional local backends."""

import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def check_package(name):
    if importlib.util.find_spec(name) is None:
        print(f"SKIP {name}: package not installed")
        return False
    print(f"PASS {name}: package installed")
    return True


def main():
    failures = 0
    if check_package("langgraph"):
        try:
            from src.agents.pipeline import build_graph
            build_graph()
            print("PASS langgraph: graph compiled")
        except Exception as exc:
            print(f"FAIL langgraph: {exc}")
            failures += 1
    if check_package("mcp"):
        try:
            from mcp_server.server import build_server
            build_server()
            print("PASS mcp: server constructed")
        except Exception as exc:
            print(f"FAIL mcp: {exc}")
            failures += 1
    if check_package("kuzu"):
        try:
            from tempfile import TemporaryDirectory
            from src.core.graph_store import GraphStore
            with TemporaryDirectory() as path:
                store = GraphStore(path)
                print(f"PASS kuzu: backend={store.backend}")
        except Exception as exc:
            print(f"FAIL kuzu: {exc}")
            failures += 1
    if check_package("chromadb"):
        try:
            from src.core.memory import Memory
            # Keep this ignored local path; Chroma retains a SQLite handle on
            # Windows and can prevent temporary-directory cleanup.
            memory = Memory(".payguard/smoke-chroma")
            memory.add_reg("SMOKE", "smoke regulatory clause")
            assert memory.retrieve_reg("smoke")
            print(f"PASS chromadb: backend={memory.backend}")
        except Exception as exc:
            print(f"FAIL chromadb: {exc}")
            failures += 1
    backend = os.getenv("PAYGUARD_LLM_BACKEND", "offline")
    if backend in {"ollama", "vllm"}:
        from src.core import llm
        if llm.is_live():
            print(f"PASS {backend}: local service reachable")
            print("LLM response:", llm.complete("Reply with the word ready.", max_tokens=8))
        else:
            print(f"SKIP {backend}: local service not reachable")
    else:
        print("SKIP LLM: PAYGUARD_LLM_BACKEND is offline")
    return failures


if __name__ == "__main__":
    sys.exit(main())
