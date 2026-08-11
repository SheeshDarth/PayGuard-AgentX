"""Ring-Auditor agent -- network-level fraud detection over the payment graph.

Builds a directed payment graph from the run's transactions, runs the money-muling
detectors (cycle / smurfing / shell) + suspicion scorer, applies a lightweight
Ring-Critic sanity check, signs each confirmed fraud ring into an HMAC dossier, and
routes rings to a human-review or monitor queue by risk. Deterministic, offline --
same state -> state contract as the other agents.

Transaction source (priority order):
  1. state["mule_transactions"]  -- explicit [{tx_id,sender,receiver,amount,timestamp}]
  2. derived from state["valid_invoices"]  -- payer(po_id|STORE) -> supplier edges
"""

from src.core import audit
from src.core.mule.graph_model import build_graph
from src.core.mule.cycle_detector import detect_cycles
from src.core.mule.smurfing_detector import detect_smurfing
from src.core.mule.shell_detector import detect_shell_networks
from src.core.mule.scorer import compute_scores

RING_REVIEW_THRESHOLD = 60.0   # risk_score at/above this -> human review


def _transactions_from_state(state):
    txns = state.get("mule_transactions")
    if txns:
        return txns
    derived = []
    for inv in state.get("valid_invoices", []):
        derived.append({"tx_id": inv.get("invoice_id"),
                        "sender": inv.get("po_id") or "STORE",
                        "receiver": inv.get("supplier_id"),
                        "amount": inv.get("amount", 0.0),
                        "timestamp": inv.get("timestamp")})
    return derived


def _ring_critic(ring):
    """Confirm a ring is worth surfacing (mirrors the false-positive discipline)."""
    if len(ring.get("member_accounts", [])) < 2:
        return False, "single-member ring suppressed"
    if ring.get("pattern_type") not in {"cycle", "smurfing", "shell_network", "mixed"}:
        return False, "unknown pattern type"
    return True, "confirmed"


def ring_auditor(state):
    txns = _transactions_from_state(state)
    if not txns:
        state["mule_rings"] = []
        state.setdefault("logs", []).append("Ring-Auditor: no transactions to scan.")
        return state

    g = build_graph(txns)
    cycles = detect_cycles(g)
    smurf = detect_smurfing(g)
    shells = detect_shell_networks(g)
    accounts, rings = compute_scores(cycles, smurf, shells, g)

    confirmed, queue = [], {"review": [], "monitor": []}
    for ring in rings:
        ok, _reason = _ring_critic(ring)
        if not ok:
            continue
        ring["confidence"] = round(ring["risk_score"] / 100.0, 3)
        dest = "review" if ring["risk_score"] >= RING_REVIEW_THRESHOLD else "monitor"
        queue[dest].append({"ring_id": ring["ring_id"], "risk_score": ring["risk_score"],
                            "pattern_type": ring["pattern_type"], "dest": dest})
        dossier = audit.build_dossier(
            "DOS_RING_" + ring["ring_id"], ring["ring_id"],
            "Money-muling fraud ring (" + ring["pattern_type"] + ")", ring)
        state.setdefault("dossiers", []).append(dossier.model_dump())
        confirmed.append(ring)

    state["mule_rings"] = confirmed
    state["mule_suspicious_accounts"] = accounts
    state["ring_hitl"] = queue
    state.setdefault("logs", []).append(
        "Ring-Auditor: " + str(len(confirmed)) + " ring(s); "
        + str(len(queue["review"])) + " to human review, "
        + str(len(queue["monitor"])) + " monitored.")
    return state
