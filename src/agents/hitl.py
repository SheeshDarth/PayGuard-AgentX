"""
Confidence-based human-in-the-loop routing for PayGuard-AgentX.

Every consequential draft carries a confidence. Route: low confidence OR high
value -> human approval queue; high confidence AND low value -> auto-execute.
This is calibrated autonomy, not a hardcoded gate.
"""

CONF_THRESHOLD = 0.8
VALUE_THRESHOLD = 5000.0


def route_decision(confidence, value):
    if confidence is None:
        return "HUMAN"
    if confidence < CONF_THRESHOLD or value >= VALUE_THRESHOLD:
        return "HUMAN"
    return "AUTO"


def escalate(state):
    queue = {"auto": [], "human": []}
    po = state.get("po_draft")
    if po is not None:
        dest = route_decision(po.get("confidence"), po.get("total_estimated_cost", 0.0))
        bucket = "auto" if dest == "AUTO" else "human"
        queue[bucket].append({"kind": "PO", "id": po.get("po_id"), "dest": dest,
                              "confidence": po.get("confidence")})
    for disp in state.get("dispute_drafts", []):
        dest = route_decision(disp.get("confidence"), disp.get("claimed_amount", 0.0))
        bucket = "auto" if dest == "AUTO" else "human"
        queue[bucket].append({"kind": "DISPUTE", "id": disp.get("dispute_id"), "dest": dest,
                              "confidence": disp.get("confidence")})
    state["hitl_queue"] = queue
    state.setdefault("logs", []).append(
        "HITL: " + str(len(queue["auto"])) + " auto, " + str(len(queue["human"])) + " human.")
    return state
