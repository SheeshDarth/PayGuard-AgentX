import json
from pathlib import Path

from src.agents.orchestrator import run_supervised
from src.agents.tools import ToolKit
from src.core.decisions import DecisionStore
from src.core.memory import Memory
from src.core.regulatory_seed import seed_regulatory
from src.utils.retail_simulator import RetailSimulator


def test_full_route_is_human_gated():
    state = run_supervised({
        "sales_raw": [RetailSimulator.sales_record("CLEAN")],
        "inventory_raw": [RetailSimulator.inventory_snapshot(
            sku="SKU_MILK", store="STORE_01", on_hand=0, reorder_point=20)],
        "invoices_raw": [RetailSimulator.supplier_invoice(po_id="PO_STORE_01_1", amount=999.0)],
    }, seed_regulatory(Memory()))
    assert state["hitl_queue"]["auto"] == []
    assert {item["kind"] for item in state["hitl_queue"]["human"]} == {"PO", "DISPUTE"}


def test_decision_store_persists_and_verifies(tmp_path):
    store = DecisionStore(str(tmp_path / "decisions.sqlite"))
    record = store.record("PO", "PO_1", "APPROVED")
    assert store.latest("PO", "PO_1")[0]["action"] == "APPROVED"
    assert store.verify(record)
    dossier = json.loads(store.latest("PO", "PO_1")[0]["dossier"])
    dossier["payload"]["action"] = "REJECTED"
    assert not store.verify(dossier)
    reopened = DecisionStore(str(tmp_path / "decisions.sqlite"))
    assert reopened.latest("PO", "PO_1")[0]["action"] == "APPROVED"


def test_toolkit_schema_names_are_complete():
    names = {schema["name"] for schema in ToolKit().schemas()}
    assert names == {"dq_validate", "sql_query", "graph_query", "doc_retrieve",
                     "case_recall", "audit_sign", "audit_verify", "mule_ring_scan"}


def test_mcp_source_registers_all_toolkit_tools():
    source = Path("mcp_server/server.py").read_text(encoding="utf-8")
    for name in ToolKit().schemas():
        assert f"def {name['name']}" in source


def test_supervisor_supports_ring_only_and_noop():
    from src.agents.orchestrator import route
    assert route({"mule_transactions": [{"sender": "A", "receiver": "B"}]}) == "ring_only"
    assert route({}) == "noop"


def test_local_llm_clients_use_expected_http_payload(monkeypatch):
    from src.core import llm

    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({"response": "ready", "choices": [{
                "message": {"content": "ready"}}]}).encode()

    calls = []
    def fake_urlopen(request, timeout=0):
        calls.append((request.full_url, json.loads(request.data.decode())))
        return Response()

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm, "_ollama_reachable", lambda timeout=0.5: True)
    monkeypatch.setenv("PAYGUARD_LLM_BACKEND", "ollama")
    monkeypatch.setenv("PAYGUARD_LLM_MODEL", "phi4-mini")
    assert llm.complete("hello", max_tokens=8) == "ready"
    assert calls[-1][0].endswith("/api/generate")

    monkeypatch.setattr(llm, "_vllm_reachable", lambda timeout=0.5: True)
    monkeypatch.setenv("PAYGUARD_LLM_BACKEND", "vllm")
    monkeypatch.setenv("PAYGUARD_LLM_MODEL", "local-model")
    assert llm.complete("hello", max_tokens=8) == "ready"
    assert calls[-1][0].endswith("/v1/chat/completions")
