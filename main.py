"""
PayGuard-AgentX -- demo entry point.

Runs the full multi-agent pipeline end-to-end on a synthetic retail + procurement
stream. Fully deterministic: no LLM key or network required. Demonstrates the closed
loop -- sales/inventory in, a human-approval-gated purchase order out, and a returning
supplier invoice audited against that PO with an HMAC-signed audit trail.
"""

from src.utils.retail_simulator import RetailSimulator
from src.agents.pipeline import run_pipeline
from src.core import audit


def main():
    print("=" * 74)
    print("PayGuard-AgentX -- Retail Ops + Procurement-Integrity Copilot")
    print("=" * 74)

    # --- Build a synthetic inbound stream ---------------------------------
    sales = [RetailSimulator.sales_record("CLEAN") for _ in range(8)]
    sales.append(RetailSimulator.sales_record("NEGATIVE_UNITS"))  # rejected by DQ-Sentinel

    inventory = [
        RetailSimulator.inventory_snapshot(sku="SKU_MILK", store="STORE_01", on_hand=3, reorder_point=20),
        RetailSimulator.inventory_snapshot(sku="SKU_RICE", store="STORE_01", on_hand=55, reorder_point=20),
    ]

    # A supplier over-bills against the PO the planner will draft, plus a tampered invoice
    invoices = [
        RetailSimulator.supplier_invoice(po_id="PO_STORE_01_1", sku="SKU_MILK", amount=999.0, scenario="CLEAN"),
        RetailSimulator.supplier_invoice(scenario="CHECKSUM_TAMPERED"),
    ]

    state = run_pipeline({
        "sales_raw": sales,
        "inventory_raw": inventory,
        "invoices_raw": invoices,
    })

    # --- Report -----------------------------------------------------------
    print("\n--- Agent log ---")
    for line in state.get("logs", []):
        print("  -", line)

    print("\n--- Rejected by DQ-Sentinel ---")
    for r in state.get("rejected", []):
        print(f"  - [{r['kind']}] {r['note']}")

    print("\n--- Purchase order draft (HUMAN APPROVAL REQUIRED) ---")
    po = state.get("po_draft")
    if po:
        print(f"  {po['po_id']} | {len(po['lines'])} line(s) | est {po['total_estimated_cost']} {po['currency']} "
              f"| status={po['status']} | approval_required={po['requires_human_approval']}")
        for line in po["lines"]:
            print(f"    * {line['sku']} @ {line['store_id']}: order {line['recommend_order_qty']} "
                  f"({line['rationale']})")
    else:
        print("  (no restock needed)")

    print("\n--- Payment audit ---")
    for f in state.get("payment_flags", []):
        print(f"  - [{f['flag_type']}] {f['description']}")
    for d in state.get("dispute_drafts", []):
        print(f"  ! Dispute {d['dispute_id']}: claimed {d['claimed_amount']} vs expected {d['expected_amount']} "
              f"-> {d['proposed_verdict']} (human review required)")

    print("\n--- Signed audit dossiers (HMAC-SHA256) ---")
    for d in state.get("dossiers", []):
        ok = audit.verify_dossier_dict(d)
        print(f"  - {d['dossier_id']} | sig={d['signature'][:12]}... | verify={ok}")

    print("\nDone. (This is a deterministic Phase-1 scaffold; see docs/ROADMAP.md for the LLM/agentic phases.)")


if __name__ == "__main__":
    main()
