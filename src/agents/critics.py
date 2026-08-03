"""
Reflection critics for PayGuard-AgentX.

PO-Critic reviews an Ops-Planner PO draft; Dispute-Critic reviews a Payment-Auditor
dispute draft. Each returns a CriticReview (APPROVE or REVISE); on REVISE the draft
is revised once. Critics attach a confidence score used by the HITL router.
Deterministic rules run offline; an LLM-HOOK adds narrative when a model is live.
Same local model, different critic system prompt -- see ARCHITECTURE.md.
"""

from src.core import audit, llm

PO_MAX_LINE_QTY = 500          # sanity ceiling for a single restock line
PO_BUDGET = 10000.0           # per-PO soft budget


def po_critic(po_draft):
    if po_draft is None:
        return ({"critic": "PO-Critic", "target_id": None, "verdict": "APPROVE",
                 "issues": [], "revised": False}, po_draft, 1.0)
    issues = []
    for line in po_draft.get("lines", []):
        if line.get("recommend_order_qty", 0) > PO_MAX_LINE_QTY:
            issues.append("line " + line["sku"] + " qty " + str(line["recommend_order_qty"])
                          + " exceeds ceiling " + str(PO_MAX_LINE_QTY))
    if po_draft.get("total_estimated_cost", 0) > PO_BUDGET:
        issues.append("total " + str(po_draft["total_estimated_cost"])
                      + " exceeds budget " + str(PO_BUDGET))
    verdict = "REVISE" if issues else "APPROVE"
    revised = False
    if verdict == "REVISE":
        for line in po_draft.get("lines", []):
            if line.get("recommend_order_qty", 0) > PO_MAX_LINE_QTY:
                line["recommend_order_qty"] = PO_MAX_LINE_QTY
                line["rationale"] = line.get("rationale", "") + " [capped by PO-Critic]"
        po_draft["total_estimated_cost"] = round(
            sum(l["recommend_order_qty"] * 10.0 for l in po_draft.get("lines", [])), 2)
        revised = True
    confidence = 0.6 if issues else 0.95
    po_draft["confidence"] = confidence
    review = {"critic": "PO-Critic", "target_id": po_draft.get("po_id"),
              "verdict": verdict, "issues": issues, "revised": revised}
    if verdict == "REVISE" and llm.is_live():
        review["note"] = llm.complete(
            "Summarise in one sentence why this purchase order needs revision: " + str(issues),
            system="You are a concise procurement PO critic.")
    return review, po_draft, confidence


def dispute_critic(dispute):
    if dispute is None:
        return ({"critic": "Dispute-Critic", "target_id": None, "verdict": "APPROVE",
                 "issues": [], "revised": False}, dispute, 1.0)
    issues = []
    if dispute.get("claimed_amount", 0) <= dispute.get("expected_amount", 0):
        issues.append("claimed " + str(dispute.get("claimed_amount"))
                      + " not greater than expected " + str(dispute.get("expected_amount"))
                      + "; mismatch may be spurious")
    verdict = "REVISE" if issues else "APPROVE"
    revised = False
    if verdict == "REVISE":
        dispute["proposed_verdict"] = "NEEDS_REVIEW"
        dispute["reason"] = dispute.get("reason", "") + " [flagged inconsistent by Dispute-Critic]"
        revised = True
    confidence = 0.55 if issues else 0.9
    dispute["confidence"] = confidence
    review = {"critic": "Dispute-Critic", "target_id": dispute.get("dispute_id"),
              "verdict": verdict, "issues": issues, "revised": revised}
    return review, dispute, confidence


def run_critics(state):
    reviews = []
    po = state.get("po_draft")
    if po is not None:
        review, po, _ = po_critic(po)
        state["po_draft"] = po
        reviews.append(review)
        if review["revised"]:
            d = audit.build_dossier("DOS_CRIT_" + str(po.get("po_id")), po.get("po_id"),
                                    "PO-Critic revision", review)
            state.setdefault("dossiers", []).append(d.model_dump())
    revised = []
    for disp in state.get("dispute_drafts", []):
        review, disp, _ = dispute_critic(disp)
        reviews.append(review)
        revised.append(disp)
    if revised:
        state["dispute_drafts"] = revised
    state["critic_reviews"] = reviews
    state.setdefault("logs", []).append(
        "Critics: " + str(sum(1 for r in reviews if r["revised"])) + " revision(s).")
    return state
