# 🌍 SDG Alignment — PayGuard-AgentX

> PayGuard-AgentX is a guarded multi-agent copilot for small retail / dark-store
> operations. Its strongest, most defensible contribution is to **institutional
> integrity** — a tamper-evident money trail — so we lead with SDG 16.

## SDG 16 — Peace, Justice & Strong Institutions (primary)

**Target 16.5 (substantially reduce corruption and bribery) and 16.6 (develop
effective, accountable, transparent institutions).**

Procurement is where small retailers quietly lose money to duplicate invoices,
PO-amount mismatches, and price creep. PayGuard-AgentX makes that trail *accountable*:

- **Tamper-evident evidence.** Every consequential action (PO draft, dispute) is
  sealed in an HMAC-SHA256 signed dossier ([`src/core/audit.py`](../src/core/audit.py)).
  A payload cannot be altered after the fact without invalidating the signature — the
  dashboard's tamper demo shows verification flipping to INVALID on a single injected field.
- **Reconciliation, not trust.** The Payment-Auditor reconciles each supplier invoice
  against the very PO the system generated, flagging duplicates and mismatches
  ([`src/agents/pipeline.py`](../src/agents/pipeline.py)).
- **Cited compliance.** The Regulatory-Auditor attaches the specific clause an invoice
  violates ([`src/agents/regulatory_auditor.py`](../src/agents/regulatory_auditor.py)).
- **Humans decide, on the record.** No autonomous financial liability decision —
  disputes default to `NEEDS_REVIEW`, `requires_human_approval = True`.

## SDG 12 — Responsible Consumption & Production (secondary)

**Target 12.3 (reduce food/retail loss) and 12.6 (encourage sustainable practices).**

- **Right-sized restocking.** Demand-Forecaster + Stock-Watcher size reorders to
  projected demand, reducing both stockouts and the overstock that becomes spoilage/waste
  — especially relevant for the perishable SKUs (milk, bread, eggs) in the demo stream.
- **Data quality first.** The DQ-Sentinel quarantines malformed records before any agent
  acts, so waste-driving decisions are not made on dirty data.

## SDG 9 — Industry, Innovation & Infrastructure (secondary)

**Target 9.3 (increase small enterprises' access to financial services and integration
into value chains).**

- **Enterprise-grade controls for small operators.** A 3-person build puts audit trails,
  reconciliation, and calibrated autonomy — normally the preserve of large ERP suites —
  within reach of a single dark store, on a 6 GB-VRAM laptop with offline fallbacks.

## Scope honesty

All data is synthetic; no real payments are executed; no regulatory certification is
claimed. The SDG framing describes the problem the system is built to address, evidenced
by the code above — not an audited social-impact outcome.
