"""
PayGuard-AgentX -- demo entry point.

Runs the FULL supervised multi-agent system end-to-end on a synthetic retail +
procurement + payment-network stream. Fully deterministic: no LLM key, no GPU and
no network required (every heavy component has a tested offline fallback).

Unlike the bare sequential runner, this goes through the dynamic-routing supervisor,
so one command demonstrates every layer:

  DQ-Sentinel quarantine  ->  Demand/Stock (with negotiation)  ->  Ops-Planner PO
  (PO-Critic + HITL)      ->  Payment-Auditor dispute          ->  Regulatory-Auditor
  clause citation         ->  Ring-Auditor money-muling rings  ->  signed dossiers
"""

from datetime import datetime, timedelta

from src.agents.orchestrator import run_supervised
from src.core import audit
from src.core.memory import Memory
from src.core.regulatory_seed import seed_regulatory
from src.utils.retail_simulator import RetailSimulator

_BASE = datetime(2024, 1, 1, 9, 0, 0)


def _tx(tx_id, sender, receiver, amount, minute):
    return {"tx_id": tx_id, "sender": sender, "receiver": receiver,
            "amount": amount, "timestamp": _BASE + timedelta(minutes=minute)}


def mule_transactions():
    """Payment graph seeded with one circular billing ring, one shell-supplier
    chain, and a payroll run that must NOT be flagged (false-positive control)."""
    txns = [
        # Circular billing ring: SUP_A -> SUP_B -> SUP_C -> SUP_A (fast = high risk)
        _tx("CY1", "SUP_A", "SUP_B", 5000.0, 0),
        _tx("CY2", "SUP_B", "SUP_C", 5000.0, 10),
        _tx("CY3", "SUP_C", "SUP_A", 5000.0, 20),
        # Shell pass-through chain: STORE_HQ -> SHELL_1 -> SHELL_2 -> VENDOR_X
        _tx("SL1", "STORE_HQ", "SHELL_1", 1000.0, 0),
        _tx("SL2", "SHELL_1", "SHELL_2", 950.0, 30),
        _tx("SL3", "SHELL_2", "VENDOR_X", 900.0, 50),
    ]
    # Payroll trap: identical amounts to many payees at a consistent hour.
    for i in range(12):
        txns.append(_tx("PR%d" % i, "PAYROLL", "EMP_%d" % i, 3000.0, i))
    return txns


def build_stream():
    sales = [RetailSimulator.sales_record("CLEAN") for _ in range(8)]
    sales.append(RetailSimulator.sales_record("NEGATIVE_UNITS"))   # DQ quarantines this

    inventory = [
        RetailSimulator.inventory_snapshot(sku="SKU_MILK", store="STORE_01",
                                           on_hand=3, reorder_point=20),
        RetailSimulator.inventory_snapshot(sku="SKU_RICE", store="STORE_01",
                                           on_hand=55, reorder_point=20),
    ]

    invoices = [
        # Supplier over-bills against the PO the planner is about to draft
        RetailSimulator.supplier_invoice(po_id="PO_STORE_01_1", sku="SKU_MILK",
                                         amount=999.0, scenario="CLEAN"),
        RetailSimulator.supplier_invoice(scenario="CHECKSUM_TAMPERED"),
    ]

    return {"sales_raw": sales, "inventory_raw": inventory, "invoices_raw": invoices,
            "mule_transactions": mule_transactions()}


def _section(title):
    print("\n--- " + title + " ---")


def main():
    print("=" * 74)
    print("PayGuard-AgentX -- Retail Ops + Procurement-Integrity Copilot")
    print("=" * 74)

    memory = seed_regulatory(Memory())
    state = run_supervised(build_stream(), memory=memory)

    print("\nSupervisor route: " + str(state.get("route")))

    _section("Agent log")
    for line in state.get("logs", []):
        print("  -", line)

    _section("Rejected by DQ-Sentinel")
    rejected = state.get("rejected", [])
    for r in rejected:
        print("  - [%s] %s" % (r["kind"], r["note"]))
    if not rejected:
        print("  (none)")

    _section("Purchase order draft (HUMAN APPROVAL REQUIRED)")
    po = state.get("po_draft")
    if po:
        print("  %s | %d line(s) | est %s %s | status=%s | approval_required=%s | confidence=%s"
              % (po["po_id"], len(po["lines"]), po["total_estimated_cost"], po["currency"],
                 po["status"], po["requires_human_approval"], po.get("confidence")))
        for line in po["lines"]:
            print("    * %s @ %s: order %s (%s)"
                  % (line["sku"], line["store_id"], line["recommend_order_qty"],
                     line["rationale"]))
    else:
        print("  (no restock needed)")

    _section("Critic reviews (reflection loop)")
    reviews = state.get("critic_reviews", [])
    for review in reviews:
        print("  - %s on %s -> %s%s"
              % (review["critic"], review["target_id"], review["verdict"],
                 " (revised)" if review["revised"] else ""))
        for issue in review.get("issues", []):
            print("      ! " + issue)
    if not reviews:
        print("  (none)")

    _section("Payment audit")
    for f in state.get("payment_flags", []):
        print("  - [%s] %s" % (f["flag_type"], f["description"]))
    for d in state.get("dispute_drafts", []):
        print("  ! Dispute %s: claimed %s vs expected %s -> %s (human review required)"
              % (d["dispute_id"], d["claimed_amount"], d["expected_amount"],
                 d["proposed_verdict"]))

    _section("Regulatory citations (RAG)")
    citations = state.get("regulatory_citations", [])
    for c in citations:
        print("  - %s [%s] -> %s" % (c["invoice_id"], c["flag_type"], c["clause_id"]))
    if not citations:
        print("  (none)")

    _section("Money-muling fraud rings (network layer)")
    rings = state.get("mule_rings", [])
    for ring in rings:
        print("  ! %s | %s | risk %.1f | members: %s"
              % (ring["ring_id"], ring["pattern_type"], ring["risk_score"],
                 ", ".join(ring["member_accounts"])))
    if not rings:
        print("  (no rings detected)")
    flagged = state.get("mule_suspicious_accounts", [])
    payroll_flagged = any(a["account_id"] == "PAYROLL" for a in flagged)
    print("  %d suspicious account(s); payroll false-positive: %s"
          % (len(flagged), "YES" if payroll_flagged else "no"))

    _section("Human-in-the-loop queues")
    hq = state.get("hitl_queue", {"auto": [], "human": []})
    print("  approvals : %d auto / %d human" % (len(hq["auto"]), len(hq["human"])))
    for item in hq["human"]:
        print("    -> HUMAN %s %s (confidence %s)"
              % (item["kind"], item["id"], item.get("confidence")))
    rq = state.get("ring_hitl", {"review": [], "monitor": []})
    print("  rings     : %d review / %d monitor" % (len(rq["review"]), len(rq["monitor"])))
    for item in rq["review"]:
        print("    -> REVIEW %s (risk %.1f)" % (item["ring_id"], item["risk_score"]))

    _section("Signed audit dossiers (HMAC-SHA256)")
    for d in state.get("dossiers", []):
        ok = audit.verify_dossier_dict(d)
        print("  - %s | sig=%s... | verify=%s"
              % (d["dossier_id"], d["signature"][:12], ok))

    print("\nDone. Deterministic run -- no LLM, GPU or network required.")
    print("See docs/ROADMAP.md for the live-backend and dashboard steps.")
    return state


if __name__ == "__main__":
    main()
