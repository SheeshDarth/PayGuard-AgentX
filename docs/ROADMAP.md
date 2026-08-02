# 📅 Implementation Roadmap — ShelfGuard-AgentX

> Repo `PayGuard-AgentX` · concept `ShelfGuard-AgentX` · team of 3 · one-semester scope
> Deliberately scoped below a research-grade capstone: a working guarded agent loop first, LLM depth and UI second.

---

## ✅ Phase 1 — Guarded loop scaffolding (DONE — runs today)

- [x] Retail + procurement Pydantic schemas (`src/models/schemas.py`)
- [x] PayGuardDQ extended into a reusable validation **tool** for sales / inventory / invoices (`src/core/dq_engine.py`)
- [x] HMAC-SHA256 evidence signing (`src/core/audit.py`)
- [x] 5-agent pipeline + LangGraph wiring (`src/agents/pipeline.py`)
- [x] Synthetic retail/procurement stream generator (`src/utils/retail_simulator.py`)
- [x] End-to-end demo (`main.py`) + 19 passing tests
- **Deliverable:** `python main.py` runs the full loop — DQ quarantine → demand → stock alert → PO draft (HITL) → invoice audit → dispute draft → signed dossiers.

## 🟡 Phase 2 — Real agentic reasoning (Weeks 3–4)

- [ ] Wire an LLM (Gemini 1.5 Flash / LiteLLM) at each `LLM-HOOK`: demand explanation, ambiguous-record triage, dispute rationale drafting
- [ ] Secrets/config via `python-dotenv` (`.env.example`, `SHELFGUARD_AUDIT_KEY`, LLM keys)
- [ ] Statistical demand forecast (moving average / simple seasonality with `pandas`) alongside the LLM
- [ ] Build a ~50-case labeled evaluation set; measure restock precision/recall and invoice-flag accuracy
- **Deliverable:** agents that *reason*, plus a metrics table proving they beat the heuristic baseline.

## 🔵 Phase 3 — Regulatory RAG & self-healing (Weeks 5–6)

- [ ] `Regulatory-Auditor`: ChromaDB RAG over supplier-contract terms / tax rules, cite the clause an invoice violates
- [ ] `Self-Healing-Repair`: when a supplier changes invoice format, **suggest** a parser patch as a diff for human approval (never auto-execute)
- [ ] Extend audit dossiers to cover approved/rejected disputes with full causal trace
- **Deliverable:** compliance citations on flagged invoices + a human-approved schema-repair suggestion flow.

## 🟣 Phase 4 — War-Room dashboard & benchmark (Weeks 7–8)

- [ ] Streamlit dashboard: live record stream, agent log, pending PO/dispute approval queue, one-click approve/reject
- [ ] Reuse the team's existing retail React work (`retail-horizon-ai`, `swiggy_copilot`) for a polished front end if time allows
- [ ] Final benchmark: accuracy, latency, token cost, self-healing suggestion acceptance rate
- [ ] Demo video + slide deck + honest "built vs. planned" README
- **Deliverable:** an operator-facing dashboard and a defensible evaluation.

---

## Scope guardrails

- **Ship the loop, then deepen it.** Phase 1 already demonstrates the agentic loop; Phases 2–4 add intelligence and polish. If time runs short, a working Phase 2 (one real LLM agent + eval) is a strong stopping point.
- **Humans approve money.** Every PO and dispute stays `requires_human_approval = True` in all phases.
- **No unearned claims.** No self-assigned grades, no invented competitors, no "production-ready / PCI-certified" language — describe what runs and what is planned.

---

## Division of labour (suggested)

| Area | Lead | Basis |
|---|---|---|
| DQ tool, agents, audit, orchestration | Siddharth | RAG/agents + fintech DQ background |
| Retail data, forecasting, evaluation set | Revanth | Python + fintech DQ + CV/IPCV |
| Dashboard + demo + front-end integration | Vishnu | React/TS retail apps |
