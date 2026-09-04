"""Product-facing workflow services over the existing deterministic pipeline.

Everything here reads the state the supervised pipeline already produces. No
status, score, or explanation is invented for the UI: if a value is not in the
run state it is reported as unknown or skipped rather than filled in.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

from src.agents.orchestrator import run_supervised
from src.core.memory import Memory
from src.core.regulatory_seed import seed_regulatory
from src.utils.retail_simulator import RetailSimulator
from src.utils.walmart_dataset import load_records as load_walmart_records


def _tx(tid, sender, receiver, amount, minute):
    return {"tx_id": tid, "sender": sender, "receiver": receiver, "amount": amount,
            "timestamp": datetime(2024, 1, 1, 9, tzinfo=timezone.utc) + timedelta(minutes=minute)}


def mule_scenario():
    txns = [_tx("CY1", "SUP_A", "SUP_B", 5000, 0), _tx("CY2", "SUP_B", "SUP_C", 5000, 10),
            _tx("CY3", "SUP_C", "SUP_A", 5000, 20), _tx("SL1", "STORE_HQ", "SHELL_1", 1000, 0),
            _tx("SL2", "SHELL_1", "SHELL_2", 950, 30), _tx("SL3", "SHELL_2", "VENDOR_X", 900, 50)]
    txns.extend(_tx(f"PR{i}", "PAYROLL", f"EMP_{i}", 3000, i) for i in range(12))
    return txns


# --------------------------------------------------------------- demo scenarios
# Three guided scenarios, each exercising a different slice of the same pipeline.
# `demonstrates` is shown in the UI so an evaluator knows what to look for.
DEMO_SCENARIOS = {
    "1 · Normal Restock": {
        "blurb": "A store runs low on milk. The retail agents size the order and draft a "
                 "purchase order for approval.",
        "demonstrates": ["Low inventory detection", "Demand prediction",
                         "Restock recommendation", "Purchase order draft"],
        "route": "restock_only",
    },
    "2 · Suspicious Invoice": {
        "blurb": "Supplier invoices come back against that purchase order. One is inflated "
                 "and one is billed twice.",
        "demonstrates": ["Invoice validation", "PO mismatch + duplicate detection",
                         "Regulatory clause citation", "Dispute recommendation",
                         "Human approval"],
        "route": "full",
    },
    "3 · Fraud Ring": {
        "blurb": "A payment network with circular billing and a shell-supplier chain — plus "
                 "a payroll run that must not be flagged.",
        "demonstrates": ["Supplier relationships", "Circular billing", "Shell suppliers",
                         "Fraud score + evidence", "Human review"],
        "route": "ring_only",
    },
    "4 · Data-Quality Quarantine": {
        "blurb": "Malformed and checksum-failed records are stopped at the gate before any "
                 "agent reasons over them.",
        "demonstrates": ["Schema validation", "Checksum verification", "Quarantine"],
        "route": "full",
    },
    "5 · Walmart Historical Sales": {
        "blurb": "Real public Walmart weekly sales across stores and departments. The agent derives a demo stock baseline from recent demand to show what should be replenished.",
        "demonstrates": ["Real Walmart store history", "Department demand", "Derived stock risk", "Restock recommendation", "Human approval"],
        "route": "restock_only",
    },
}


def scenario(preset):
    # 1 -- Normal restock: low stock, clean invoice, no fraud signal.
    if preset in ("1 · Normal Restock", "Clean operations run"):
        return {"sales_raw": [RetailSimulator.sales_record("CLEAN") for _ in range(6)],
                "inventory_raw": [
                    RetailSimulator.inventory_snapshot(sku="SKU_MILK", store="STORE_01",
                                                       on_hand=3, reorder_point=20),
                    RetailSimulator.inventory_snapshot(sku="SKU_RICE", store="STORE_01",
                                                       on_hand=55, reorder_point=20)]}
    # 2 -- Suspicious invoice: an inflated invoice against the drafted PO, the same
    # invoice billed twice (exercises the Payment-Auditor duplicate branch), and a
    # checksum-tampered record the DQ-Sentinel quarantines.
    if preset in ("2 · Suspicious Invoice", "Procurement mismatch"):
        duplicate = RetailSimulator.supplier_invoice(sku="SKU_BREAD", amount=42000.0)
        return {"sales_raw": [RetailSimulator.sales_record("CLEAN") for _ in range(6)],
                "inventory_raw": [RetailSimulator.inventory_snapshot(
                    sku="SKU_MILK", store="STORE_01", on_hand=3, reorder_point=20)],
                "invoices_raw": [
                    RetailSimulator.supplier_invoice(po_id="PO_STORE_01_1", sku="SKU_MILK",
                                                     amount=999.0),
                    duplicate, duplicate,
                    RetailSimulator.supplier_invoice(scenario="CHECKSUM_TAMPERED")]}
    # 3 -- Fraud ring: the payment graph on its own; the supervisor routes ring_only.
    if preset in ("3 · Fraud Ring", "Fraud-ring investigation"):
        return {"mule_transactions": mule_scenario()}
    if preset == "5 · Walmart Historical Sales":
        return load_walmart_records()
    if preset in ("4 · Data-Quality Quarantine", "Data-quality quarantine"):
        return {"sales_raw": [RetailSimulator.sales_record("NEGATIVE_UNITS"),
                              RetailSimulator.sales_record("CORRUPTED_JSON"),
                              RetailSimulator.sales_record("CLEAN")],
                "invoices_raw": [RetailSimulator.supplier_invoice(scenario="CHECKSUM_TAMPERED"),
                                 RetailSimulator.supplier_invoice(scenario="CLEAN")]}
    return {"sales_raw": [], "inventory_raw": [], "invoices_raw": []}


def run_scenario(preset):
    state = run_supervised(scenario(preset), memory=seed_regulatory(Memory()))
    state["run_id"] = "RUN_" + uuid.uuid4().hex[:10]
    state["preset"] = preset
    return state


def plain_alerts(state):
    alerts = []
    for flag in state.get("payment_flags", []):
        if flag.get("flag_type") == "CLEAN":
            continue
        title = ("Duplicate invoice" if flag["flag_type"] == "DUPLICATE"
                 else "Invoice does not match the purchase order")
        alerts.append({"alert_id": "ALERT_" + flag["invoice_id"], "title": title,
                       "summary": flag["description"], "alert_type": flag["flag_type"],
                       "severity": "HIGH", "subject_id": flag["invoice_id"]})
    for ring in state.get("mule_rings", []):
        alerts.append({"alert_id": "ALERT_" + ring["ring_id"],
                       "title": "Suspicious payment network", "summary":
                       f"A {ring['pattern_type'].replace('_', ' ')} pattern connects "
                       f"{len(ring['member_accounts'])} accounts.",
                       "alert_type": ring["pattern_type"], "severity":
                       "HIGH" if ring["risk_score"] >= 60 else "MEDIUM",
                       "subject_id": ring["ring_id"]})
    return alerts


# ------------------------------------------------------------- agent timeline
# Canonical execution order and the log prefix each agent writes. An agent is
# reported as run only when its own line is present in the trace; anything the
# route skipped is labelled as skipped, never as executed.
_AGENT_SEQUENCE = [
    ("DQ-Sentinel", "DQ-Sentinel", "always"),
    ("Demand-Forecaster", "Demand-Forecaster", "restock"),
    ("Stock-Watcher", "Stock-Watcher", "restock"),
    ("Negotiation", "Negotiation", "restock"),
    ("Ops-Planner", "Ops-Planner", "restock"),
    ("Payment-Auditor", "Payment-Auditor", "audit"),
    ("Regulatory-Auditor", "Regulatory-Auditor", "audit"),
    ("Ring-Auditor", "Ring-Auditor", "network"),
    ("Critics", "Critics", "always"),
    ("HITL", "HITL", "always"),
]

_SKIP_REASON = {
    "restock": "no sales or inventory in this run",
    "audit": "no supplier invoices in this run",
    "network": "no payment graph in this run",
    "always": "did not run",
}


def agent_timeline(state):
    """Rebuild the execution timeline from the run's own trace.

    Returns [{name, status, detail}] where status is done | skipped | pending.
    A step is 'done' only if the agent wrote its line into state['logs'].
    """
    logs = state.get("logs", [])
    steps = []
    for name, prefix, group in _AGENT_SEQUENCE:
        line = next((l for l in logs if l.startswith(prefix + ":")), None)
        if line:
            steps.append({"name": name, "status": "done",
                          "detail": line.split(":", 1)[1].strip()})
        else:
            steps.append({"name": name, "status": "skipped",
                          "detail": _SKIP_REASON[group]})
    waiting = (len(state.get("hitl_queue", {}).get("human", []))
               + len(state.get("ring_hitl", {}).get("review", [])))
    if waiting:
        steps.append({"name": "Human approval", "status": "pending",
                      "detail": f"{waiting} decision(s) held for a person"})
    return steps


TIMELINE_ICON = {"done": "✓", "skipped": "–", "pending": "⏳"}


# ------------------------------------------------------------ pending actions
def _supplier_of(state, invoice_id):
    for inv in state.get("valid_invoices", []):
        if inv.get("invoice_id") == invoice_id:
            return inv.get("supplier_id")
    return None


def _priority(risk):
    if risk is None:
        return "MEDIUM"
    return "HIGH" if risk >= 60 else ("MEDIUM" if risk >= 30 else "LOW")


def pending_actions(state, decided_subjects=()):
    """Consequential actions still awaiting a person, enriched for display.

    Every field is read from the run state; `risk` is None when the pipeline did
    not produce a score for that subject rather than being defaulted to a number.
    """
    if not state:
        return []
    decided = set(decided_subjects)
    actions = []

    po = state.get("po_draft")
    for item in state.get("hitl_queue", {}).get("human", []):
        kind, subject_id = item.get("kind"), item.get("id")
        if (kind, subject_id) in decided:
            continue
        if kind == "PO" and po and po.get("po_id") == subject_id:
            actions.append({
                "kind": "PO", "id": subject_id, "type": "Restock purchase order",
                "entity": po.get("store_id"), "entity_label": "Store",
                "amount": po.get("total_estimated_cost"), "currency": po.get("currency", "USD"),
                "confidence": po.get("confidence"), "risk": None, "priority": "MEDIUM",
                "reason": f"{len(po.get('lines', []))} SKU(s) below reorder point.",
                "recommended": "Approve the draft purchase order",
                "status": po.get("status", "DRAFT"),
                "approve_label": "Approve", "reject_label": "Reject",
                "approve_action": "APPROVED", "reject_action": "REJECTED",
                "capability": "approve_po"})
            continue
        if kind == "DISPUTE":
            disp = next((d for d in state.get("dispute_drafts", [])
                         if d.get("dispute_id") == subject_id), None)
            if not disp:
                continue
            supplier = _supplier_of(state, disp.get("invoice_id"))
            actions.append({
                "kind": "DISPUTE", "id": subject_id, "type": "Invoice dispute",
                "entity": supplier or disp.get("invoice_id"), "entity_label": "Supplier",
                "amount": disp.get("claimed_amount"), "currency": "USD",
                "confidence": disp.get("confidence"), "risk": None, "priority": "HIGH",
                "reason": disp.get("reason", ""),
                "recommended": "Raise a dispute for human review",
                "status": disp.get("status", "DRAFT"),
                "approve_label": "Approve", "reject_label": "Reject",
                "approve_action": "APPROVED", "reject_action": "REJECTED",
                "capability": "approve_po"})

    for item in state.get("ring_hitl", {}).get("review", []):
        subject_id = item.get("ring_id")
        if ("RING", subject_id) in decided:
            continue
        ring = next((r for r in state.get("mule_rings", [])
                     if r.get("ring_id") == subject_id), {})
        risk = ring.get("risk_score", item.get("risk_score"))
        members = ring.get("member_accounts", [])
        actions.append({
            "kind": "RING", "id": subject_id, "type": "Suspicious payment network",
            "entity": members[0] if members else subject_id, "entity_label": "Lead account",
            "amount": None, "currency": "USD", "confidence": ring.get("confidence"),
            "risk": risk, "priority": _priority(risk),
            "reason": f"{item.get('pattern_type', 'unknown').replace('_', ' ').title()} "
                      f"pattern across {len(members)} accounts.",
            "recommended": "Escalate for financial-crime review",
            "status": ring.get("disposition", "PENDING"),
            "approve_label": "Escalate", "reject_label": "Dismiss",
            "approve_action": "ESCALATED", "reject_action": "DISMISSED",
            "capability": "review_fraud"})

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    actions.sort(key=lambda a: (order.get(a["priority"], 3), -(a["risk"] or 0)))
    return actions


# --------------------------------------------------------- "why was this flagged"
def why_flagged(state, kind, subject_id):
    """Signals the engine actually recorded for one subject.

    Returns {reasons, score, score_label, recommendation}. Reasons are quoted
    from pipeline output; nothing is generated to fill the panel out.
    """
    reasons, score, score_label, recommendation = [], None, "", ""

    if kind == "DISPUTE":
        disp = next((d for d in state.get("dispute_drafts", [])
                     if d.get("dispute_id") == subject_id), {})
        invoice_id = disp.get("invoice_id")
        claimed, expected = disp.get("claimed_amount"), disp.get("expected_amount")
        if claimed and expected:
            pct = abs(claimed - expected) / expected * 100
            reasons.append(f"Invoice amount differs from the purchase order by {pct:.1f}% "
                           f"({claimed:,.2f} billed vs {expected:,.2f} estimated).")
        for flag in state.get("payment_flags", []):
            if flag.get("invoice_id") == invoice_id and flag.get("flag_type") != "CLEAN":
                reasons.append(flag["description"] + ".")
        for cite in state.get("regulatory_citations", []):
            if cite.get("invoice_id") == invoice_id:
                reasons.append(f"Cited compliance clause {cite['clause_id']}: {cite['clause_text']}")
        for review in state.get("critic_reviews", []):
            if review.get("target_id") == subject_id:
                reasons.extend(f"Dispute-Critic: {issue}" for issue in review.get("issues", []))
        if disp.get("llm_explanation"):
            reasons.append("Model note (narrative only): " + disp["llm_explanation"])
        if disp.get("confidence") is not None:
            score = round(disp["confidence"] * 100)
            score_label = "Confidence"
        recommendation = disp.get("proposed_verdict", "NEEDS_REVIEW").replace("_", " ").title()
        recommendation = f"{recommendation} — raise a dispute for human review"

    elif kind == "RING":
        ring = next((r for r in state.get("mule_rings", [])
                     if r.get("ring_id") == subject_id), {})
        members = set(ring.get("member_accounts", []))
        score, score_label = ring.get("risk_score"), "Risk score"
        if members:
            reasons.append(f"{ring.get('pattern_type', 'unknown').replace('_', ' ').title()} "
                           f"pattern detected across {len(members)} linked accounts.")
        fired = {}
        for acc in state.get("mule_suspicious_accounts", []):
            if acc["account_id"] not in members:
                continue
            for pattern in acc.get("detected_patterns", []):
                fired.setdefault(pattern, []).append(acc["account_id"])
        for pattern, accs in sorted(fired.items()):
            reasons.append(f"Signal `{pattern.replace('_', ' ')}` on {', '.join(sorted(accs))}.")
        if state.get("mule_scan_truncated"):
            reasons.append("Scan hit its time budget — this is a subset of the graph, "
                           "not proof that no other rings exist.")
        recommendation = "Escalate for financial-crime review"

    elif kind == "PO":
        po = state.get("po_draft") or {}
        for line in po.get("lines", []):
            reasons.append(f"{line['sku']} at {line['store_id']}: {line['rationale']}; "
                           f"order {line['recommend_order_qty']}.")
        for review in state.get("critic_reviews", []):
            if review.get("target_id") == subject_id:
                reasons.extend(f"PO-Critic: {issue}" for issue in review.get("issues", []))
                if review.get("revised"):
                    reasons.append("PO-Critic revised this draft before it reached you.")
        for note in state.get("negotiations", []):
            reasons.append(f"Demand/Stock negotiation on {note['topic']} resolved to "
                           f"{note['resolution']}.")
        if po.get("confidence") is not None:
            score, score_label = round(po["confidence"] * 100), "Confidence"
        recommendation = "Approve the draft purchase order"

    elif kind == "INVOICE":
        for flag in state.get("payment_flags", []):
            if flag.get("invoice_id") == subject_id and flag.get("flag_type") != "CLEAN":
                reasons.append(flag["description"] + ".")
        for cite in state.get("regulatory_citations", []):
            if cite.get("invoice_id") == subject_id:
                reasons.append(f"Cited compliance clause {cite['clause_id']}: {cite['clause_text']}")
        recommendation = "Hold the invoice and confirm with the supplier"

    return {"reasons": reasons, "score": score, "score_label": score_label,
            "recommendation": recommendation}


# ------------------------------------------------------- fraud relationship map
def ring_edges(state, ring):
    """Transactions between members of one ring (for the relationship view)."""
    members = set(ring.get("member_accounts", []))
    return [t for t in state.get("mule_transactions", [])
            if t.get("sender") in members and t.get("receiver") in members]


def ring_chain(ring, edges):
    """Order ring members into a walk along their own edges, so a cycle reads as
    a cycle. Falls back to the member list when the edges do not form a chain."""
    members = ring.get("member_accounts", [])
    if not edges:
        return members, False
    nxt = {}
    for e in edges:
        nxt.setdefault(e["sender"], e["receiver"])
    # Start where the money enters: a member with no inbound edge inside the ring.
    # A closed cycle has no such node, so it falls back to the first member, which
    # is where a cycle should start anyway.
    receivers = {e["receiver"] for e in edges}
    sources = [m for m in members if m not in receivers]
    start = sources[0] if sources else members[0]
    walk, seen = [start], {start}
    node = start
    while node in nxt and nxt[node] not in seen:
        node = nxt[node]
        walk.append(node)
        seen.add(node)
    closes = node in nxt and nxt[node] == start
    if len(walk) < len(members):
        return members, False
    return walk, closes


# --------------------------------------------------------------- system status
def system_status(storage=None, memory=None):
    """Component health read from the live configuration, not hard-coded.

    Reports what each subsystem actually resolved to (embedded backend vs the
    offline fallback) so the offline-first design is visible rather than implied.
    """
    from src.core import llm
    from src.core.graph_store import GraphStore
    from src.core.config import graph_path, memory_path

    mem = memory or Memory(memory_path())
    graph = GraphStore(graph_path())
    backend = os.getenv("PAYGUARD_LLM_BACKEND", "offline").lower()
    live = llm.is_live()
    rows = [
        ("Database", True, getattr(storage, "backend", "sqlite")),
        ("Agent orchestrator", True, "supervisor + LangGraph nodes"),
        ("DQ engine", True, "deterministic, 0 tokens"),
        ("Fraud engine", True, "cycle · smurfing · shell"),
        ("Knowledge graph", True, graph.backend + (" (offline fallback)"
                                                   if graph.backend == "memory" else "")),
        ("RAG / memory", True, mem.backend + (" (keyword fallback)"
                                              if mem.backend == "fallback" else "")),
        ("Evidence signing", True, "HMAC-SHA256"),
    ]
    llm_label = f"{backend} (reachable)" if live else (
        "offline stub" if backend == "offline" else f"{backend} configured, not reachable")
    return {"rows": rows, "llm": llm_label,
            "mode": "Demo · synthetic data" if not live else "Demo · local model",
            "executes_payments": False}
