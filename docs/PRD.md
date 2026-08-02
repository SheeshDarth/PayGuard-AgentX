# 📑 Product Requirements Document (PRD) — PayGuard-AgentX

> **Project:** `PayGuard-AgentX` (repo: `PayGuard-AgentX`)
> **Version:** 2.0 — retail + procurement-integrity pivot
> **Team:** Siddharth ([@SheeshDarth](https://github.com/SheeshDarth)), Revanth ([@Revanthm2027](https://github.com/Revanthm2027)), Vishnu ([@vishnu-k-dev](https://github.com/vishnu-k-dev))

---

## 1. Vision

`PayGuard-AgentX` is a multi-agent copilot for small retail / dark-store operations. It reads point-of-sale and inventory data, decides what to restock, drafts purchase orders for human approval, and then **guards the procurement money trail** — validating supplier invoices against the very purchase orders it generated, catching duplicate or inflated billing, and drafting disputes. Every consequential action is recorded in a tamper-evident, signed audit dossier.

It fuses two prior concepts: **ShelfSense** (retail restock/pricing copilot) and **PayGuard-AgentX** (financial data-quality + fraud + dispute engine). The bridge between them is the purchase-order → invoice → payment loop.

---

## 2. Problem

Small retailers and dark stores lose margin to three everyday failures:

1. **Stockouts and overstock** — manual reorder decisions lag demand; popular SKUs sell out while slow ones tie up cash.
2. **Dirty operational data** — POS exports and supplier feeds contain malformed records, wrong currencies, and corrupted fields that quietly break naive automation.
3. **Supplier billing leakage** — duplicate invoices, quantities that do not match the purchase order, and price creep slip through because no one reconciles every invoice against its PO.

A single small team cannot watch all three continuously. PayGuard-AgentX puts a guarded, semi-autonomous agent loop on the job, with humans approving the decisions that spend money.

---

## 3. Target personas

- **Store Operations Manager** — wants timely, explainable restock suggestions, not a black box; approves purchase orders.
- **Procurement / Finance Officer** — wants every supplier invoice reconciled against its PO, with duplicates and mismatches flagged and a signed audit trail for each.
- **Data / Ops Engineer** — wants dirty inbound records caught and quarantined before any agent acts on them.

---

## 4. Product epics & features

### EPIC 1 — Guarded ingestion (DQ-Sentinel) ✅ Phase 1
- **FEAT-1.1** Validate POS sales, inventory snapshots, and supplier invoices via the deterministic PayGuardDQ tool (required fields, positive quantities/amounts, supported currency, invoice checksum).
- **FEAT-1.2** Quarantine rejected records with a human-readable reason; only clean records reach downstream agents.

### EPIC 2 — Demand & stock intelligence (Demand-Forecaster, Stock-Watcher) ✅ Phase 1
- **FEAT-2.1** Project near-term demand per store/SKU from validated sales.
- **FEAT-2.2** Flag SKUs below their reorder point or projected demand, with the shortfall quantified.

### EPIC 3 — Restock planning with human approval (Ops-Planner) ✅ Phase 1
- **FEAT-3.1** Assemble stock alerts into a purchase-order draft with per-line rationale and an estimated cost.
- **FEAT-3.2** Mark every PO `requires_human_approval = True`; nothing is "sent" autonomously.

### EPIC 4 — Procurement integrity (Payment-Auditor) ✅ Phase 1
- **FEAT-4.1** Reconcile each returning supplier invoice against the originating PO.
- **FEAT-4.2** Detect duplicate billing and PO-amount mismatches; draft a dispute (human review required) when a mismatch exceeds tolerance.

### EPIC 5 — Tamper-evident audit trail ✅ Phase 1
- **FEAT-5.1** Emit an HMAC-SHA256 signed evidence dossier for each PO draft and dispute draft, verifiable with the server key.

### EPIC 6 — LLM reasoning upgrade 🔜 Phase 2
- **FEAT-6.1** Replace heuristic forecasting/routing with an LLM (Gemini/LiteLLM) at the marked `LLM-HOOK` points, keeping the same agent interfaces.

### EPIC 7 — Regulatory & self-healing 🔜 Phase 3
- **FEAT-7.1** RAG check of invoices against supplier-contract / tax rules (Regulatory-Auditor).
- **FEAT-7.2** Suggest (never auto-apply) a parser patch when a supplier changes invoice format (Self-Healing-Repair).

### EPIC 8 — War-Room dashboard 🔜 Phase 4
- **FEAT-8.1** Streamlit dashboard: live record stream, agent log, pending PO/dispute approvals, and one-click approve/reject.

---

## 5. Out of scope (this project)

- Real payment execution or fund transfer — the system drafts and audits, humans approve and pay.
- Any claim of PCI-DSS / regulatory certification — the compliance framing is a design target, not an audited guarantee.
- Real customer or cardholder data — all streams are synthetic.

---

## 6. Success metrics

- **Data quality:** ≥ 99% of malformed synthetic records correctly quarantined.
- **Restock quality:** on a labeled test set, agent restock suggestions vs. actual next-period sales (precision/recall on "should reorder").
- **Integrity:** 100% of duplicate / mismatched invoices flagged on the test set; 0 forged dossiers pass verification.
- **Human-in-the-loop:** 100% of money-spending actions gated by human approval.
