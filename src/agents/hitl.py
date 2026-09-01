"""
Human-in-the-loop routing for PayGuard-AgentX.

Confidence remains visible for triage, but every consequential procurement
artifact is human-gated. The system never auto-executes a PO or dispute.
"""

CONF_THRESHOLD = 0.8
VALUE_THRESHOLD = 5000.0


def route_decision(confidence, value):
    return "HUMAN"


def escalate(state):
    queue = {"auto": [], "human": []}
    po = state.get("po_draft")
    if po is not None:
        dest = route_decision(po.get("confidence"), po.get("total_estimated_cost", 0.0))
        queue["human"].append({"kind": "PO", "id": po.get("po_id"), "dest": dest,
                              "confidence": po.get("confidence")})
    for disp in state.get("dispute_drafts", []):
        dest = route_decision(disp.get("confidence"), disp.get("claimed_amount", 0.0))
        queue["human"].append({"kind": "DISPUTE", "id": disp.get("dispute_id"), "dest": dest,
                              "confidence": disp.get("confidence")})
    state["hitl_queue"] = queue
    state.setdefault("logs", []).append(
        "HITL: " + str(len(queue["human"])) + " human approval(s); no auto-execution.")
    return state
