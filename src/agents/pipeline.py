"""
PayGuard-AgentX multi-agent pipeline.

Each agent is a pure function: state(dict) -> state(dict). Keeping the agent logic
pure makes it unit-testable with no LLM key and no heavy dependencies. The place to
plug an LLM reasoning call is marked with an LLM-HOOK comment in each agent; swapping
the deterministic heuristic for a model call there does not change the graph wiring.

run_pipeline() executes the agents sequentially. build_graph() returns the identical
node sequence as a compiled LangGraph StateGraph, imported lazily so the package (and
its tests) work without langgraph installed.

Agent lineage:
  dq_sentinel        <- PayGuard  DQ-Sentinel (validates every record via the DQ tool)
  demand_forecaster  <- ShelfSense demand reader
  stock_watcher      <- ShelfSense stock watcher
  ops_planner        <- ShelfSense order drafter (emits HITL purchase order + audit dossier)
  payment_auditor    <- PayGuard  Forensic-Investigator + Arbitration-Dispute
"""

from typing import TypedDict, List, Optional
from src.core.dq_engine import PayGuardDQEngine
from src.core import audit
from src.core import llm


class AgentState(TypedDict, total=False):
    sales_raw: List[str]
    inventory_raw: List[str]
    invoices_raw: List[str]
    valid_sales: List[dict]
    valid_inventory: List[dict]
    valid_invoices: List[dict]
    rejected: List[dict]
    demand_forecast: dict
    forecast_note: str
    stock_alerts: List[dict]
    po_draft: Optional[dict]
    payment_flags: List[dict]
    dispute_drafts: List[dict]
    dossiers: List[dict]
    logs: List[str]


def _log(state: dict, msg: str) -> None:
    state.setdefault("logs", []).append(msg)


# 1. DQ-Sentinel — gate every inbound record through the PayGuardDQ tool
def dq_sentinel(state: dict) -> dict:
    valid_sales, valid_inv, valid_docs, rejected = [], [], [], []
    for raw in state.get("sales_raw", []):
        ok, note, rec = PayGuardDQEngine.validate_sales_record(raw)
        if ok:
            valid_sales.append(rec.model_dump())
        else:
            rejected.append({"kind": "SALES", "note": note})
    for raw in state.get("inventory_raw", []):
        ok, note, rec = PayGuardDQEngine.validate_inventory_snapshot(raw)
        if ok:
            valid_inv.append(rec.model_dump())
        else:
            rejected.append({"kind": "INVENTORY", "note": note})
    for raw in state.get("invoices_raw", []):
        ok, note, rec = PayGuardDQEngine.validate_supplier_invoice(raw)
        if ok:
            valid_docs.append(rec.model_dump())
        else:
            rejected.append({"kind": "INVOICE", "note": note})
    state["valid_sales"] = valid_sales
    state["valid_inventory"] = valid_inv
    state["valid_invoices"] = valid_docs
    state["rejected"] = rejected
    _log(state, f"DQ-Sentinel: {len(valid_sales)} sales / {len(valid_inv)} inventory / "
                f"{len(valid_docs)} invoices valid; {len(rejected)} rejected.")
    return state


# 2. Demand-Forecaster — project near-term demand per store/SKU from validated sales
def demand_forecaster(state: dict) -> dict:
    forecast: dict = {}
    for s in state.get("valid_sales", []):
        key = f"{s['store_id']}|{s['sku']}"
        forecast[key] = forecast.get(key, 0) + int(s["units_sold"])
    # LLM-HOOK: when a live model is configured, attach a natural-language demand note.
    state["demand_forecast"] = forecast
    if llm.is_live():
        state["forecast_note"] = llm.complete(
            "In one sentence, summarise near-term retail demand from these projected "
            "per-SKU units: " + str(forecast) + ".",
            system="You are a concise retail demand analyst.")
    _log(state, f"Demand-Forecaster: projected demand for {len(forecast)} store/SKU pair(s).")
    return state


# 3. Stock-Watcher — flag SKUs below reorder point or below projected demand
def stock_watcher(state: dict) -> dict:
    alerts = []
    for inv in state.get("valid_inventory", []):
        key = f"{inv['store_id']}|{inv['sku']}"
        demand = state.get("demand_forecast", {}).get(key, 0)
        needed = max(inv["reorder_point"], demand)
        if inv["on_hand"] < needed:
            alerts.append({
                "store_id": inv["store_id"],
                "sku": inv["sku"],
                "on_hand": inv["on_hand"],
                "projected_demand": demand,
                "recommend_order_qty": max(needed - inv["on_hand"], 0),
                "rationale": (f"on_hand {inv['on_hand']} < needed {needed} "
                              f"(reorder {inv['reorder_point']}, demand {demand})"),
            })
    state["stock_alerts"] = alerts
    _log(state, f"Stock-Watcher: {len(alerts)} stock alert(s).")
    return state


# 4. Ops-Planner — turn alerts into a restock PO draft (human approval required)
def ops_planner(state: dict, unit_cost: float = 10.0) -> dict:
    alerts = state.get("stock_alerts", [])
    if not alerts:
        state["po_draft"] = None
        _log(state, "Ops-Planner: no restock needed.")
        return state
    lines = [{
        "sku": a["sku"],
        "store_id": a["store_id"],
        "current_on_hand": a["on_hand"],
        "projected_demand": a["projected_demand"],
        "recommend_order_qty": a["recommend_order_qty"],
        "rationale": a["rationale"],
    } for a in alerts]
    total = round(sum(line["recommend_order_qty"] * unit_cost for line in lines), 2)
    po = {
        "po_id": f"PO_{alerts[0]['store_id']}_{len(lines)}",
        "store_id": alerts[0]["store_id"],
        "lines": lines,
        "total_estimated_cost": total,
        "currency": "USD",
        "requires_human_approval": True,
        "status": "DRAFT",
    }
    state["po_draft"] = po
    dossier = audit.build_dossier(f"DOS_{po['po_id']}", po["po_id"],
                                  "PO draft awaiting human approval", po)
    state.setdefault("dossiers", []).append(dossier.model_dump())
    _log(state, f"Ops-Planner: drafted {po['po_id']} ({len(lines)} line(s), "
                f"est {total} {po['currency']}) -- awaiting human approval.")
    return state


# 5. Payment-Auditor — audit returning supplier invoices vs the PO (PayGuard lineage)
def payment_auditor(state: dict, tolerance: float = 0.02) -> dict:
    flags, disputes, seen = [], [], set()
    po = state.get("po_draft")
    expected = po["total_estimated_cost"] if po else None
    for inv in state.get("valid_invoices", []):
        sig = (inv["supplier_id"], inv["sku"], round(inv["amount"], 2))
        if sig in seen:
            flags.append({"invoice_id": inv["invoice_id"], "flag_type": "DUPLICATE", "severity": "HIGH",
                          "description": f"Duplicate billing for {inv['sku']} amount {inv['amount']}"})
            continue
        seen.add(sig)
        if (po and inv.get("po_id") == po["po_id"] and expected is not None
                and abs(inv["amount"] - expected) > tolerance * expected):
            flags.append({"invoice_id": inv["invoice_id"], "flag_type": "PO_MISMATCH", "severity": "HIGH",
                          "description": f"Invoice {inv['amount']} deviates from PO estimate {expected}"})
            disputes.append({"dispute_id": f"DIS_{inv['invoice_id']}", "invoice_id": inv["invoice_id"],
                             "po_id": po["po_id"], "reason": "Invoice amount exceeds PO estimate beyond tolerance",
                             "claimed_amount": inv["amount"], "expected_amount": expected,
                             "proposed_verdict": "NEEDS_REVIEW", "requires_human_approval": True,
                             "status": "DRAFT"})
            if llm.is_live():
                # Narrative only. The deterministic `reason` stays authoritative and
                # signed; model prose goes in a separate, bounded, clearly-labelled
                # field (and is never trusted as the dispute's ground truth).
                note = (llm.complete(
                    "Draft a one-sentence procurement dispute rationale. Invoice bills "
                    + str(inv["amount"]) + " for " + inv["sku"] + " but the PO estimate was "
                    + str(expected) + ".",
                    system="You are a concise, factual procurement dispute assistant.") or "").strip()
                if note:
                    disputes[-1]["llm_explanation"] = note[:280]
            continue
        flags.append({"invoice_id": inv["invoice_id"], "flag_type": "CLEAN", "severity": "NONE",
                      "description": "Invoice passed payment audit."})
    state["payment_flags"] = flags
    state["dispute_drafts"] = disputes
    for d in disputes:
        dossier = audit.build_dossier(f"DOS_{d['dispute_id']}", d["invoice_id"],
                                      "Dispute draft awaiting human review", d)
        state.setdefault("dossiers", []).append(dossier.model_dump())
    _log(state, f"Payment-Auditor: {len(flags)} flag(s), {len(disputes)} dispute draft(s).")
    return state


AGENTS = [dq_sentinel, demand_forecaster, stock_watcher, ops_planner, payment_auditor]


def run_pipeline(state: dict) -> dict:
    """Sequential runner (LangGraph-free). Mirrors build_graph() node order."""
    for agent in AGENTS:
        state = agent(state)
    return state


def build_graph():
    """Return a compiled LangGraph StateGraph with the same node sequence.

    Imported lazily so the package and its tests run without langgraph installed.
    """
    from langgraph.graph import StateGraph, END
    g = StateGraph(AgentState)
    g.add_node("dq_sentinel", dq_sentinel)
    g.add_node("demand_forecaster", demand_forecaster)
    g.add_node("stock_watcher", stock_watcher)
    g.add_node("ops_planner", ops_planner)
    g.add_node("payment_auditor", payment_auditor)
    g.set_entry_point("dq_sentinel")
    g.add_edge("dq_sentinel", "demand_forecaster")
    g.add_edge("demand_forecaster", "stock_watcher")
    g.add_edge("stock_watcher", "ops_planner")
    g.add_edge("ops_planner", "payment_auditor")
    g.add_edge("payment_auditor", END)
    return g.compile()
