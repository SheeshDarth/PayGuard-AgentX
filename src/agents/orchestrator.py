"""
Supervisor / orchestrator for PayGuard-AgentX.

Dynamic routing: the agents run depends on what is in the inbound state, not a
fixed sequence. On the demo laptop this rule-based router can be swapped for
langgraph-supervisor's create_supervisor() with an Ollama model making the same
routing decision; the deterministic router here keeps it testable offline.

Full route wires the Week-3 additions: Demand/Stock negotiation, PO/Dispute
critics, and confidence-based HITL escalation.

Routes:
  restock_only -- retail only  -> demand -> stock -> negotiation -> ops_planner
  audit_only   -- invoices only -> payment_auditor -> regulatory_auditor
  full         -- both          -> full pipeline + regulatory
  noop         -- nothing actionable
Every route ends with critics + HITL escalation.
"""

from src.agents.pipeline import (
    dq_sentinel, demand_forecaster, stock_watcher, ops_planner, payment_auditor,
)
from src.agents.regulatory_auditor import regulatory_auditor
from src.agents.ring_auditor import ring_auditor
from src.agents.negotiation import run_negotiation
from src.agents.critics import run_critics
from src.agents.hitl import escalate
from src.agents.teams import team_plan


def route(state):
    has_retail = bool(state.get("sales_raw") or state.get("inventory_raw"))
    has_invoices = bool(state.get("invoices_raw"))
    has_payment_graph = bool(state.get("mule_transactions"))
    if has_retail and has_invoices:
        return "full"
    if has_invoices:
        return "audit_only"
    if has_retail:
        return "restock_only"
    # A payment graph on its own is still actionable -- the network-fraud layer does
    # not depend on procurement invoices being present.
    if has_payment_graph:
        return "ring_only"
    return "noop"


def run_supervised(state, memory=None):
    """Execute only the agents the chosen route needs, then critics + HITL."""
    r = route(state)
    state["team_plan"] = team_plan(r)
    state.setdefault("logs", []).append("Supervisor: route=" + r)
    state = dq_sentinel(state)
    if r in ("restock_only", "full"):
        state = demand_forecaster(state)
        state = stock_watcher(state)
        state = run_negotiation(state)
        state = ops_planner(state)
    if r in ("audit_only", "full"):
        state = payment_auditor(state)
        if memory is not None:
            state = regulatory_auditor(state, memory)
    # Network-fraud layer: runs whenever there is a payment graph to analyse -- either
    # an explicit transaction set, or invoices that were just audited above. Keeping
    # this independent of the route string stops the Ring-Auditor from being silently
    # skipped for a mule-only input.
    if r in ("audit_only", "full", "ring_only") or state.get("mule_transactions"):
        state = ring_auditor(state)
    state = run_critics(state)
    state = escalate(state)
    state["route"] = r
    return state
