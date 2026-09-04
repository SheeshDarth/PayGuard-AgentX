# Enterprise Retail Control Centre Plan

## Product goal

Evolve PayGuard-AgentX into an offline-first prototype for multi-store retailers:
large-format, value, and omnichannel stores. The system is an operating control
centre, not a payment or supplier-execution platform. It helps teams see what
needs attention, why it matters, which agents investigated it, and which human
decision is required next.

## Operating model

```text
Retail data intake
       ↓
Store Operations Team        → demand, stockout, replenishment recommendations
       ↓
Procurement Integrity Team   → PO draft, invoice matching, disputes
       ↓
Risk Intelligence Team       → supplier/payment-network investigations
       ↓
Enterprise Control Team      → route, evidence, mandatory human decision
```

The supervisor activates only the teams required for the current input. Every
purchase order, dispute, or fraud disposition ends in a human decision with an
HMAC-signed dossier. Custom teams assign responsibility and visibility around
existing agents; they cannot enable payment execution or remove the approval
gate.

## Retailer profiles

| Profile | Intended prototype use | Data status |
|---|---|---|
| Multi-store retail group | Generic chain or independent franchise group | Representative local demo data |
| Walmart-style large-format retail | Store/department replenishment | Public Walmart historical sales only when the Walmart scenario is selected; stock is derived for demonstration |
| DMart-style value retail | Value retail, high-turn grocery/household operations | Representative demo profile; no DMart data or connection |
| Target-style omnichannel retail | Store and omnichannel operating workflow | Representative demo profile; no Target data or connection |

No retailer profile claims an integration with a retailer's private POS,
inventory, supplier, invoice, customer, payment, or identity system.

## Release sequence

### Release 1 — Enterprise foundation (implemented)

- Retail operating profile selector and clear data-source disclosures.
- Four governed operating teams: Store Operations, Procurement Integrity, Risk
  Intelligence, and Enterprise Control.
- Route-aware active/standby team plan on every supervised run.
- Administrator-only custom team configuration persisted in SQLite.
- Product shell language updated from a single use case to an enterprise control
  centre while retaining the offline-first dashboard.

### Release 2 — Unified operational work management (in progress)

- [x] Persistent case ownership, handover notes, valid status transitions, signed
  update evidence, and audit events.
- [ ] Workspace-scoped ownership and saved queue filters.
- Supplier, store, department, and SKU drill-down pages.
- Workload/aging KPIs and an exception service-level view.
- Downloadable signed investigation and replenishment reports.

### Release 3 — Data integration boundary

- Schema adapters for POS, inventory, supplier invoice, and transaction feeds.
- Import staging, data lineage, connector health, and replayable runs.
- Read-only connector contracts first; no write connector is added without an
  explicit approval and security design.

### Release 4 — Published enterprise mode

- PostgreSQL deployment, OIDC identity, workspace isolation, and audit export.
- Rate limits, health checks, retention policy, and role/permission review.
- Performance and accessibility validation with representative data volume.

## Acceptance checks for the prototype

- A user can select a retail profile and clearly tell whether data is public or
  representative.
- The run identifies its active agent teams and skipped teams.
- An administrator can create a custom team from existing agents.
- A viewer cannot create teams or approve/reject any consequential item.
- An Operations user can approve/reject a PO; an Analyst can escalate/dismiss a
  risk ring; neither action executes external work.
- Decision evidence verifies before tampering and fails afterward.
- The offline suite runs with no network, GPU, LLM, graph DB, or vector DB.

## Non-goals for this prototype

- No live Walmart, DMart, Target, supplier, banking, payment, or procurement
  connection.
- No autonomous buying, payment, customer action, or supplier submission.
- No claim of production certification, fraud-model accuracy in a real retailer,
  or compliance accreditation.
