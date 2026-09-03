# 📅 Implementation Roadmap — PayGuard-AgentX

> Repo `PayGuard-AgentX` · concept `PayGuard-AgentX` · team of 3 · one-semester scope
> Deliberately scoped below a research-grade capstone: a working guarded agent loop first, LLM depth and UI second.

---

## ✅ Phase 1 — Guarded loop scaffolding (DONE — runs today)

- [x] Retail + procurement Pydantic schemas (`src/models/schemas.py`)
- [x] PayGuardDQ extended into a reusable validation **tool** for sales / inventory / invoices (`src/core/dq_engine.py`)
- [x] HMAC-SHA256 evidence signing (`src/core/audit.py`)
- [x] 5-agent pipeline + LangGraph wiring (`src/agents/pipeline.py`)
- [x] Synthetic retail/procurement stream generator (`src/utils/retail_simulator.py`)
- [x] End-to-end demo (`main.py`) + 19 passing tests
- **Deliverable:** `python main.py` runs the full **supervised** system — route selection → DQ quarantine → demand → stock alert (with negotiation) → PO draft + PO-Critic (HITL) → invoice audit → dispute draft → regulatory clause citation → money-muling ring detection → signed dossiers.

## ✅ Phase 2 — Real agentic reasoning (Weeks 3–4) — DONE

> Landed: self-hosted LLM access layer with offline fallback, environment configuration, and a labeled evaluation harness. Live backend smoke checks remain optional and local-only.


- [x] Wire a self-hosted LLM (Ollama `phi4-mini` / vLLM) at each `LLM-HOOK`: demand explanation and dispute rationale drafting
- [x] Secrets/config via `python-dotenv` (`.env.example`, `PAYGUARD_AUDIT_KEY`)
- [ ] Statistical demand forecast (moving average / simple seasonality with `pandas`) alongside the LLM
- [ ] Build a ~50-case labeled evaluation set; measure restock precision/recall and invoice-flag accuracy
- **Deliverable:** agents that *reason*, plus a metrics table proving they beat the heuristic baseline.

## ✅ Phase 3 — Regulatory RAG & self-healing (Weeks 5–6) — DONE / SCOPE-BOUNDED

- [x] `Regulatory-Auditor`: ChromaDB/keyword-fallback retrieval over seeded clauses, citing the clause an invoice violates
- [ ] `Self-Healing-Repair`: when a supplier changes invoice format, **suggest** a parser patch as a diff for human approval (never auto-execute)
- [ ] Extend audit dossiers to cover approved/rejected disputes with full causal trace
- **Deliverable:** compliance citations on flagged invoices + a human-approved schema-repair suggestion flow.

## ✅ Phase 4 — War-Room dashboard & benchmark (Weeks 7–8) — DONE / SCOPE-BOUNDED

- [x] Streamlit dashboard: scenario builder, agent log, pending approval queues, signed evidence, and network view
- [ ] Reuse the team's existing retail React work (`retail-horizon-ai`, `swiggy_copilot`) for a polished front end if time allows
- [ ] Final benchmark: accuracy, latency, token cost, self-healing suggestion acceptance rate
- [ ] Demo video + slide deck (manual submission artifacts)
- **Deliverable:** an operator-facing dashboard and a defensible evaluation.

---

## Scope guardrails

- **Ship the loop, then deepen it.** The delivered system demonstrates the guarded loop with deterministic decisions, optional local LLM explanations, and tested fallbacks.
- **Humans approve money.** Every PO and dispute stays `requires_human_approval = True` in all phases.
- **No unearned claims.** No self-assigned grades, no invented competitors, no "production-ready / PCI-certified" language — describe what runs and what is planned.

---

## Division of labour (suggested)

| Area | Lead | Basis |
|---|---|---|
| DQ tool, agents, audit, orchestration | Siddharth | RAG/agents + fintech DQ background |
| Retail data, forecasting, evaluation set | Revanth | Python + fintech DQ + CV/IPCV |
| Dashboard + demo + front-end integration | Vishnu | React/TS retail apps |

---

## Scale-up track (Agentic AI 23AML171) -- local-first, offline fallbacks

- [x] Week 1 -- Ollama-first LLM layer; SQLite/Kuzu/Chroma stores; extended schemas; ARCHITECTURE.md
- [x] Week 2 -- dynamic-routing supervisor (orchestrator.py); Regulatory-Auditor + seeded clauses; ToolKit tool registry + MCP server wrapper; SqliteSaver checkpointer factory
- [x] Week 3 -- PO-Critic / Dispute-Critic reflection loops; Demand/Stock negotiation protocol; human-only HITL routing; SQLite trace logging; agentic eval metrics
- [x] Week 4 -- Streamlit dashboard (`dashboard/app.py`: pipeline trace, HITL queue, one-click HMAC verify + tamper demo); `docs/RUBRIC_TRACEABILITY.md`; `docs/SDG_ALIGNMENT.md`

> Kuzu (Cypher), Chroma, and Ollama code paths are written with offline fallbacks; optional backend smoke tests skip cleanly when services are unavailable. The 79-test suite and Streamlit health check cover the guaranteed offline path. Remaining hands-on step: capture the product-shell demo.
