"""
Regulatory clause seed data for PayGuard-AgentX.

Realistic (NOT certified -- keep the honest-status framing) compliance clause
excerpts used to seed the Chroma regulatory_docs collection, so the
Regulatory-Auditor can retrieve and cite a relevant clause for a flagged invoice.
"""

REGULATORY_CLAUSES = [
    ("REG_PO_MATCH",
     "Invoices must match the approved purchase order amount within a 2 percent tolerance; "
     "deviations require documented justification and approver sign-off."),
    ("REG_DUP",
     "Duplicate invoices for the same purchase order and supplier must be rejected and "
     "flagged for review before any payment is released."),
    ("REG_TAX_ID",
     "Suppliers must present a valid tax identifier and onboarding record before any "
     "payment is released."),
    ("REG_CURRENCY",
     "Invoice currency must match the purchase order currency; cross-currency billing "
     "requires an approved and recorded FX rate."),
    ("REG_LEAD_TIME",
     "Orders exceeding the supplier agreed lead time by more than 50 percent must be "
     "escalated to procurement before settlement."),
]


def seed_regulatory(memory):
    """Load the clause excerpts into a Memory instance regulatory_docs store."""
    for clause_id, text in REGULATORY_CLAUSES:
        memory.add_reg(clause_id, text, {"clause": clause_id})
    return memory
