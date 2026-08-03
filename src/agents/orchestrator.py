"""
Supervisor / orchestrator for PayGuard-AgentX.

Dynamic routing: the agents run depends on what is actually in the inbound state,
not a fixed sequence. This is the difference between agentic orchestration and a
pipeline. On the demo laptop this rule-based router can be swapped for
langgraph-supervisor's create_supervisor() with an Ollama model making the same
routing decision; the deterministic router here keeps it testable offline.

Routes:
  restock_only -- sales/inventory, no invoices -> demand -> stock -> ops_planner
  audit_only   -- invoices only                -> payment_auditor -> regulatory_auditor
  full         -- both                         -> full pipeline + regulatory
  noop         -- nothing actionable
"""

from src.agents.pipeline import (
    dq_sentinel, demand_forecaster, stock_watcher, ops_planner, payment_auditor,
)
from src.agents.regulatory_auditor import regulatory_auditor


def route(state):
    has_retail = bool(state.get("sales_raw") or state.get("inventory_raw"))
    has_invoices = bool(state.get("invoices_raw"))
    if has_retail and has_invoices:
        return "full"
    if has_invoices:
        return "audit_only"
    if has_retail:
        return "restock_only"
    return "noop"


def run_supervised(state, memory=None):
    """Execute only the agents the chosen route needs. Returns the updated state."""
    r = route(state)
    state.setdefault("logs", []).append("Supervisor: route=" + r)
    state = dq_sentinel(state)
    if r in ("restock_only", "full"):
        state = demand_forecaster(state)
        state = stock_watcher(state)
        state = ops_planner(state)
    if r in ("audit_only", "full"):
        state = payment_auditor(state)
        if memory is not None:
            state = regulatory_auditor(state, memory)
    state["route"] = r
    return state
