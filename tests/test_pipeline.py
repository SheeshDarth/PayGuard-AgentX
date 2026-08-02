"""
Tests for the PayGuard-AgentX retail + procurement pipeline.

Covers the DQ tool (retail + invoice paths), the HMAC audit module, each agent's
logic in isolation, and a full end-to-end pipeline run. No LLM key or heavy deps
required -- everything here runs against the deterministic scaffolding.
"""

from src.core.dq_engine import PayGuardDQEngine
from src.core import audit
from src.utils.retail_simulator import RetailSimulator
from src.agents.pipeline import (
    run_pipeline, demand_forecaster, stock_watcher, ops_planner, payment_auditor,
)


# --- DQ tool: retail + invoice paths ---------------------------------------

def test_sales_record_valid():
    ok, note, rec = PayGuardDQEngine.validate_sales_record(RetailSimulator.sales_record("CLEAN"))
    assert ok is True
    assert rec is not None


def test_sales_record_negative_units_rejected():
    ok, note, rec = PayGuardDQEngine.validate_sales_record(RetailSimulator.sales_record("NEGATIVE_UNITS"))
    assert ok is False
    assert "units" in note.lower()


def test_sales_record_bad_currency_rejected():
    ok, note, rec = PayGuardDQEngine.validate_sales_record(RetailSimulator.sales_record("BAD_CURRENCY"))
    assert ok is False
    assert "currency" in note.lower()


def test_inventory_negative_on_hand_rejected():
    raw = RetailSimulator.inventory_snapshot(on_hand=-5)
    ok, note, rec = PayGuardDQEngine.validate_inventory_snapshot(raw)
    assert ok is False


def test_invoice_clean_passes():
    ok, note, inv = PayGuardDQEngine.validate_supplier_invoice(RetailSimulator.supplier_invoice("CLEAN"))
    assert ok is True


def test_invoice_checksum_tamper_rejected():
    ok, note, inv = PayGuardDQEngine.validate_supplier_invoice(
        RetailSimulator.supplier_invoice(scenario="CHECKSUM_TAMPERED"))
    assert ok is False
    assert "checksum" in note.lower()


# --- HMAC audit -------------------------------------------------------------

def test_audit_sign_verify_roundtrip():
    body = {"a": 1, "b": [1, 2, 3], "c": "x"}
    sig = audit.sign(body)
    assert audit.verify(body, sig) is True


def test_audit_detects_tampering():
    body = {"amount": 100.0}
    sig = audit.sign(body)
    body["amount"] = 999.0
    assert audit.verify(body, sig) is False


def test_audit_dossier_build_and_verify():
    d = audit.build_dossier("DOS_1", "PO_1", "test", {"po_id": "PO_1", "total": 50})
    assert audit.verify_dossier_dict(d.model_dump()) is True


# --- Agent logic ------------------------------------------------------------

def test_stock_watcher_triggers_on_low_stock():
    state = {
        "valid_sales": [{"store_id": "S1", "sku": "K", "units_sold": 10}],
        "valid_inventory": [{"store_id": "S1", "sku": "K", "on_hand": 2, "reorder_point": 20}],
    }
    state = demand_forecaster(state)
    state = stock_watcher(state)
    assert len(state["stock_alerts"]) == 1
    assert state["stock_alerts"][0]["recommend_order_qty"] > 0


def test_stock_watcher_silent_when_stocked():
    state = {
        "valid_sales": [],
        "valid_inventory": [{"store_id": "S1", "sku": "K", "on_hand": 100, "reorder_point": 20}],
    }
    state = demand_forecaster(state)
    state = stock_watcher(state)
    assert state["stock_alerts"] == []


def test_ops_planner_po_requires_human_approval():
    state = {"stock_alerts": [{
        "store_id": "S1", "sku": "K", "on_hand": 2, "projected_demand": 10,
        "recommend_order_qty": 18, "rationale": "low",
    }]}
    state = ops_planner(state)
    assert state["po_draft"]["requires_human_approval"] is True
    assert state["po_draft"]["status"] == "DRAFT"
    assert len(state["dossiers"]) == 1  # audit dossier emitted


def test_payment_auditor_flags_duplicate_invoice():
    inv = {"invoice_id": "I1", "supplier_id": "SUP_A", "sku": "K", "amount": 100.0, "po_id": None}
    inv2 = dict(inv, invoice_id="I2")
    state = {"valid_invoices": [inv, inv2], "po_draft": None}
    state = payment_auditor(state)
    assert "DUPLICATE" in [f["flag_type"] for f in state["payment_flags"]]


def test_payment_auditor_flags_po_mismatch_and_drafts_dispute():
    po = {"po_id": "PO_1", "total_estimated_cost": 100.0}
    inv = {"invoice_id": "I9", "supplier_id": "SUP_A", "sku": "K", "amount": 500.0, "po_id": "PO_1"}
    state = {"valid_invoices": [inv], "po_draft": po}
    state = payment_auditor(state)
    assert "PO_MISMATCH" in [f["flag_type"] for f in state["payment_flags"]]
    assert len(state["dispute_drafts"]) == 1
    assert state["dispute_drafts"][0]["requires_human_approval"] is True


# --- End to end -------------------------------------------------------------

def test_full_pipeline_runs_and_logs():
    sales = [RetailSimulator.sales_record("CLEAN") for _ in range(5)]
    inv = [RetailSimulator.inventory_snapshot(sku="SKU_MILK", store="STORE_01", on_hand=1, reorder_point=20)]
    state = run_pipeline({"sales_raw": sales, "inventory_raw": inv, "invoices_raw": []})
    assert "logs" in state
    assert len(state["logs"]) >= 5  # one log line per agent


# --- Phase 2: LLM hook + evaluation harness --------------------------------

def test_llm_offline_fallback_is_not_live():
    from src.core import llm
    # No PAYGUARD_LLM_MODEL configured in tests -> offline, deterministic path.
    assert llm.is_live() is False


def test_llm_hook_enriches_dispute_when_live(monkeypatch):
    from src.core import llm
    from src.agents.pipeline import payment_auditor
    monkeypatch.setattr(llm, "is_live", lambda: True)
    monkeypatch.setattr(llm, "complete", lambda *a, **k: "LLM rationale: supplier overbilled")
    po = {"po_id": "PO_1", "total_estimated_cost": 100.0}
    inv = {"invoice_id": "I9", "supplier_id": "SUP_A", "sku": "K", "amount": 500.0, "po_id": "PO_1"}
    state = payment_auditor({"valid_invoices": [inv], "po_draft": po})
    assert "LLM rationale" in state["dispute_drafts"][0]["reason"]


def test_eval_harness_produces_metrics():
    from evaluation.run_eval import evaluate
    r = evaluate()
    assert 0.0 <= r["restock"]["accuracy"] <= 1.0
    assert 0.0 <= r["invoice"]["accuracy"] <= 1.0
    assert r["restock"]["n"] >= 20
