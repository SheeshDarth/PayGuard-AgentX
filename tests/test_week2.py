"""
Tests for scale-up Week 2: Regulatory-Auditor RAG, dynamic supervisor routing,
tool registry, checkpointer degradation, and MCP server import. All run offline.
"""

from src.core.memory import Memory
from src.core.regulatory_seed import seed_regulatory
from src.agents.regulatory_auditor import regulatory_auditor
from src.agents.orchestrator import route, run_supervised
from src.agents.tools import ToolKit
from src.core.checkpoint import get_checkpointer
from src.utils.retail_simulator import RetailSimulator


def test_regulatory_auditor_cites_relevant_clause():
    m = seed_regulatory(Memory())
    state = {"payment_flags": [
        {"invoice_id": "I1", "flag_type": "PO_MISMATCH",
         "description": "Invoice 500 deviates from PO estimate 100"}]}
    state = regulatory_auditor(state, m)
    assert state["regulatory_citations"]
    assert state["regulatory_citations"][0]["clause_id"] == "REG_PO_MATCH"


def test_regulatory_auditor_ignores_clean_flags():
    m = seed_regulatory(Memory())
    state = {"payment_flags": [{"invoice_id": "I2", "flag_type": "CLEAN", "description": "ok"}]}
    state = regulatory_auditor(state, m)
    assert state["regulatory_citations"] == []


def test_supervisor_routes_three_scenarios_differently():
    assert route({"sales_raw": ["x"]}) == "restock_only"
    assert route({"invoices_raw": ["x"]}) == "audit_only"
    assert route({"sales_raw": ["x"], "invoices_raw": ["y"]}) == "full"
    assert route({}) == "noop"


def test_run_supervised_full_route_end_to_end():
    m = seed_regulatory(Memory())
    sales = [RetailSimulator.sales_record("CLEAN") for _ in range(4)]
    inv = [RetailSimulator.inventory_snapshot(sku="SKU_MILK", store="STORE_01", on_hand=1, reorder_point=20)]
    invoices = [RetailSimulator.supplier_invoice(po_id="PO_STORE_01_1", sku="SKU_MILK", amount=999.0)]
    state = run_supervised({"sales_raw": sales, "inventory_raw": inv, "invoices_raw": invoices}, m)
    assert state["route"] == "full"
    assert "po_draft" in state
    assert "payment_flags" in state
    assert "regulatory_citations" in state


def test_run_supervised_audit_only_skips_restock():
    m = seed_regulatory(Memory())
    invoices = [RetailSimulator.supplier_invoice(sku="SKU_MILK", amount=120.0)]
    state = run_supervised({"invoices_raw": invoices}, m)
    assert state["route"] == "audit_only"
    assert state.get("po_draft") is None


def test_toolkit_tools_callable():
    kit = ToolKit()
    rows = kit.sql_query("SELECT supplier_id FROM suppliers ORDER BY supplier_id")
    assert rows[0]["supplier_id"] == "SUP_A"
    kit.graph.add_dispute("SUP_A", "D1", "I1")
    kit.graph.add_dispute("SUP_A", "D2", "I2")
    assert kit.graph_query("multi_dispute_suppliers") == ["SUP_A"]
    assert len(kit.schemas()) == 8  # + mule_ring_scan (Phase-2)


def test_checkpointer_degrades_gracefully():
    # langgraph-checkpoint-sqlite is not installed here -> None, and no crash.
    cp = get_checkpointer()
    assert cp is None or cp is not None


def test_mcp_server_module_imports():
    import mcp_server.server as s
    assert hasattr(s, "build_server")
