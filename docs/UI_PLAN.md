# 🖥️ UI Plan — PayGuard-AgentX Operator Workbench

> **⚠️ SUPERSEDED — kept as a decision record.**
> The UI was rebuilt as hand-written HTML/CSS/JS served by Python's stdlib
> `http.server` (see [`web/`](../web/server.py) and the Dashboard row in
> [ARCHITECTURE.md](ARCHITECTURE.md)). The *goal* below still holds — one command
> on a cold clone shows the whole system, offline, with no `npm install` — and the
> AML/fraud UI patterns in §2–§4 were carried over: action inbox, why-flagged
> explanations, relationship maps, evidence dossiers. What changed is the delivery
> mechanism: the current dashboard needs **zero** third-party packages, where the
> Streamlit path needed four.
>
> Original direction, for the record:

> Direction set by the LLM council (unanimous): **enhance the existing Streamlit
> dashboard into a fraud-analyst workbench** — do NOT build a separate React app.
> One `streamlit run` on a cold clone must show the whole system. Reliability is the
> demo. This plan maps proven AML/fraud-tool UI patterns onto PayGuard-AgentX's own
> data and features.

---

## 1. Why Streamlit (council verdict, condensed)

- The full supervised pipeline (agent trace, HITL queue, HMAC verify/tamper) is
  **already wired** in `dashboard/app.py`. That is the user–agent interaction the
  rubric rewards.
- A prior React + vis-network money-muling app was **deliberately discarded** to
  consolidate into this Python project; "rebuild React" re-imports the API/CORS/
  two-process plumbing we removed.
- The fraud-network graph is a **component drop-in**, not a platform.
- **Reliability guardrail:** a two-service React+API stack can score zero if the
  grader can't `npm install` offline. One Streamlit process cannot.

## 2. Patterns borrowed from industry AML tools (researched)

| Pattern (source) | What it does | PayGuard mapping |
|---|---|---|
| **Link / network analysis** (Unit21, Linkurious, Neo4j) | Node-link graph; suspicious entities visually distinct; click a node to see related entities + history | Fraud-network graph over `mule_rings` + payment edges; node colour = `suspicion_score`, size = risk |
| **Risk-scored alert triage** (Facctum, Quantexa) | Surface highest-risk alerts first; prioritized queue; typology scorecards | Sort the HITL + `ring_hitl` queues by risk/confidence; KPI cards per pattern type |
| **Single pane of glass** (Unit21) | Click a suspicious node → every related entity + transaction history in one panel | Node-detail panel: `signal_breakdown`, `detected_patterns`, the account's transactions |
| **Typology grouping** (Oracle, Quantexa) | Group alerts by laundering typology | Group rings by `pattern_type` (cycle / smurfing / shell / mixed) |
| **Visual hierarchy / progressive disclosure** (fintech UX) | Concise summaries first, expandable detail on demand | KPI row → panels → `st.expander` for payloads (already partly done) |
| **Case disposition** (Unit21 case mgmt) | Analyst approves / escalates with an audit trail | Approve / escalate buttons on HITL items; every decision already HMAC-signed |

## 3. Information architecture (product pages)

```
┌ Header: PayGuard-AgentX — operator workbench ───────────────────────────┐
│ Sidebar: scenario builder (retail batch, invoices, + Money-muling toggle)│
├─ Action Inbox       prioritized actions + one primary Run analysis CTA    │
├─ Operations         stock health, POs, invoices, approval state           │
├─ Analyst Workspace  alert explanations, rings, accounts, transactions     │
├─ Cases              searchable investigations and decision history        │
├─ Evidence           searchable signed records + progressive disclosure     │
├─ Settings           workspace, user, role, storage, runtime status         │
└──────────────────────────────────────────────────────────────────────────┘
```

## 4. The fraud-network graph (the new, high-value piece)

- **Data:** build nodes/edges from the run's `mule_transactions` + `mule_rings`;
  colour nodes by `suspicion_score` tier, size by risk, badge ring membership.
- **Rendering (offline-first, in priority order):**
  1. **Default — `networkx` + `matplotlib` static PNG** rendered with `st.pyplot`.
     Zero JS, zero CDN, works on any offline laptop. Deterministic layout (seeded).
  2. **Optional enhancement — `streamlit-agraph`** (interactive pan/zoom/click) when
     the package is installed; degrade to the static render otherwise. Mirrors the
     project's tested-fallback discipline.
- **Colour tiers** (risk palette): ≥80 critical (red), ≥60 high (orange),
  ≥40 medium (amber), ≥20 low (yellow), else normal (blue).

## 5. Implementation guardrails (from the Critic)

- Put the graph in its **own tab / `st.fragment`** so a graph rerun cannot reset the
  approval queue held in `st.session_state`.
- Graph interaction is **read-only** — a node click populates a detail panel; it
  **never mutates pipeline state**.
- **Cap the demo graph to 1–2 rings** / flagged nodes only — never render the full
  transaction set. Pre-filter to `suspicion_score > 0`.
- Keep the pipeline result in `session_state` so tab switches don't recompute.

## 6. Current implementation status

The new product shell now uses an Action Inbox, separate Operations and Analyst
Workspace pages, searchable Cases and Evidence pages, seeded scenario presets,
and semantic light/dark theme tokens. The dashboard feeds a seeded fraud graph so
the analyst workflow is demoable end-to-end. The former four-tab layout is no
longer the visible entry point.

The **Fraud-ring investigation** preset injects a synthetic fraud graph (one cycle,
one shell, and a payroll trap) into the supervised run. This keeps the strongest
feature demoable without adding another toggle to the primary workflow.

## 7. Build phases

1. **Product shell** → page navigation, Action Inbox, scenario presets, and accessible tokens.
2. **Operations and Analyst workflows** → business-language summaries, queues, cases, and drill-downs.
3. **Evidence and workspace persistence** → searchable evidence, SQLite fallback, PostgreSQL adapter.
4. **Published team mode** → generic OIDC/SSO, roles, and deployment configuration.

Each phase leaves a working `streamlit run`. No new backend, no API, no second process.

---

## Sources

- [Unit21 — Link Analysis in AML case management](https://www.unit21.ai/blog/what-is-link-analysis-in-aml-case-management)
- [Unit21 — AI-powered case management](https://www.unit21.ai/products/case-management)
- [Neo4j — Combating money laundering: graph data visualizations](https://neo4j.com/blog/fraud-detection/combating-money-laundering-graph-data-visualizations/)
- [Linkurious — AML graph analytics use cases](https://linkurious.com/blog/anti-money-laundering-use-cases-graph-analytics/)
- [Facctum — AML alert triage](https://www.facctum.com/alert-triage-aml)
- [Financial Crime Academy — data visualization techniques for AML](https://financialcrimeacademy.org/data-visualization-techniques-for-aml/)
- [Wildnet Edge — fintech dashboard UX best practices](https://www.wildnetedge.com/blogs/fintech-ux-design-best-practices-for-financial-dashboards)
