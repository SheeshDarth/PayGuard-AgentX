"""
Tests for scale-up Week 3: reflection critics, negotiation protocol, confidence-based
HITL, trace logging, supervisor integration, and agentic eval metrics. All offline.
"""

from src.agents.critics import po_critic, dispute_critic
from src.agents.negotiation import needs_negotiation, run_negotiation
from src.agents.hitl import route_decision, escalate
from src.core.trace import Tracer
from src.agents.orchestrator import run_supervised
from src.core.memory import Memory
from src.core.regulatory_seed import seed_regulatory
from src.utils.retail_simulator import RetailSimulator
from evaluation.run_eval import full_eval


def test_po_critic_revises_oversized_line():
    po = {"po_id": "PO_1", "lines": [{"sku": "K", "recommend_order_qty": 900, "rationale": "x"}],
          "total_estimated_cost": 9000.0}
    review, po2, conf = po_critic(po)
    assert review["verdict"] == "REVISE" and review["revised"] is True
    assert po2["lines"][0]["recommend_order_qty"] == 500
    assert conf < 0.8


def test_po_critic_approves_normal():
    po = {"po_id": "PO_2", "lines": [{"sku": "K", "recommend_order_qty": 30, "rationale": "x"}],
          "total_estimated_cost": 300.0}
    review, _, conf = po_critic(po)
    assert review["verdict"] == "APPROVE" and conf >= 0.8


def test_dispute_critic_flags_inconsistent():
    disp = {"dispute_id": "D1", "claimed_amount": 50.0, "expected_amount": 100.0}
    review, _, _ = dispute_critic(disp)
    assert review["verdict"] == "REVISE"


def test_negotiation_triggers_and_records():
    assert needs_negotiation(1, 20, 2) is True
    assert needs_negotiation(100, 20, 2) is False
    state = {"valid_inventory": [{"store_id": "S1", "sku": "K", "on_hand": 1, "reorder_point": 20}],
             "demand_forecast": {"S1|K": 2}}
    state = run_negotiation(state)
    assert len(state["negotiations"]) == 1
    assert state["negotiations"][0]["rounds"] == 2


def test_hitl_routes_all_consequential_actions_to_human():
    assert route_decision(0.95, 100.0) == "HUMAN"
    assert route_decision(0.6, 100.0) == "HUMAN"
    assert route_decision(0.95, 9000.0) == "HUMAN"
    state = {"po_draft": {"po_id": "PO_1", "total_estimated_cost": 100.0, "confidence": 0.95},
             "dispute_drafts": [{"dispute_id": "D1", "claimed_amount": 9000.0, "confidence": 0.9}]}
    state = escalate(state)
    assert len(state["hitl_queue"]["auto"]) == 0
    assert len(state["hitl_queue"]["human"]) == 2


def test_tracer_records_events():
    t = Tracer()
    t.log("R1", "DQ-Sentinel", "decision", "clean", 0.9)
    t.log("R1", "Ops-Planner", "decision", "po drafted", 0.8)
    ev = t.events("R1")
    assert len(ev) == 2 and ev[0]["step"] == 1


def test_supervised_full_runs_critics_negotiation_hitl():
    m = seed_regulatory(Memory())
    sales = [RetailSimulator.sales_record("CLEAN") for _ in range(3)]
    inv = [RetailSimulator.inventory_snapshot(sku="SKU_MILK", store="STORE_01", on_hand=1, reorder_point=20)]
    invoices = [RetailSimulator.supplier_invoice(po_id="PO_STORE_01_1", sku="SKU_MILK", amount=999.0)]
    state = run_supervised({"sales_raw": sales, "inventory_raw": inv, "invoices_raw": invoices}, m)
    assert "critic_reviews" in state
    assert "hitl_queue" in state
    assert "negotiations" in state


def test_agentic_eval_metrics():
    r = full_eval()
    assert 0.0 <= r["agentic"]["plan_revision_rate"] <= 1.0
    assert r["agentic"]["critic_recall"] == 1.0
