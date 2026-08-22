# PayGuard-AgentX — Final Project Report

**Course:** Agentic AI (23AML171)
**Team:** Siddharth ([@SheeshDarth](https://github.com/SheeshDarth)) · Revanth ([@Revanthm2027](https://github.com/Revanthm2027)) · Vishnu ([@vishnu-k-dev](https://github.com/vishnu-k-dev))
**Repository:** https://github.com/SheeshDarth/PayGuard-AgentX

---

## 1. Executive summary

PayGuard-AgentX is a guarded, multi-agent copilot for small retail / dark-store
operations. It reads point-of-sale and inventory data, decides what to restock,
drafts purchase orders for human approval, and then **guards the procurement money
trail** — validating supplier invoices against the very purchase orders it generated,
catching duplicate or inflated billing, and drafting disputes. Every consequential
action is sealed in a tamper-evident, HMAC-signed audit dossier, and no autonomous
decision ever spends money.

The system is built, tested (**63 passing tests**), and runs end-to-end offline with
no GPU, no network, and no API key. Every heavy component — the self-hosted language
model, the graph database, the vector store — is local-first with a tested pure-Python
fallback, so the pipeline is fully demonstrable on any machine and lights up for real
on the demo laptop when the backends are present.

---

## 2. Problem & motivation

Small retailers and dark stores lose margin to three everyday failures:

1. **Stockouts and overstock** — manual reorder decisions lag demand; popular SKUs
   sell out while slow ones tie up cash and (for perishables) become waste.
2. **Dirty operational data** — POS exports and supplier feeds contain malformed
   records, wrong currencies, and corrupted fields that quietly break naive automation.
3. **Supplier billing leakage** — duplicate invoices, quantities that do not match
   the purchase order, and price creep slip through because no one reconciles every
   invoice against its PO.

A single small team cannot watch all three continuously. PayGuard-AgentX puts a
guarded, semi-autonomous agent loop on the job, with humans approving anything that
spends money.

---

## 3. Solution overview

The project fuses two concepts — **ShelfSense** (retail restock copilot) and
**PayGuard-AgentX** (financial data-quality + fraud + dispute engine) — at their
natural meeting point: the **purchase order → supplier invoice → payment** loop.
ShelfSense decides *what to buy*; PayGuard *guards the data going in and audits the
money coming back*.

The design thesis: **the deterministic core decides; the language model explains,
critiques, negotiates, and drafts remediation.** No language model ever holds sole
authority over a consequential financial or procurement action. The deterministic
PayGuardDQ engine is exposed as a **tool the agents call**, which is what makes the
loop genuinely agentic rather than a fixed validation script.

---

## 4. Architecture

### 4.1 Multi-agent topology

A dynamic-routing supervisor executes only the agents a given batch needs
(`restock_only` / `audit_only` / `full` / `noop`), then always runs the reflection
critics and the human-in-the-loop escalation.

| Agent | Responsibility |
|---|---|
| **DQ-Sentinel** | Validates every inbound record via the PayGuardDQ tool; quarantines malformed ones with a human-readable reason |
| **Demand-Forecaster** | Projects near-term demand per store / SKU from validated sales |
| **Stock-Watcher** | Flags SKUs below reorder point or projected demand |
| **Ops-Planner** | Assembles alerts into a purchase-order draft — held for human approval |
| **Payment-Auditor** | Reconciles returning invoices against the PO; detects duplicates and mismatches; drafts disputes |
| **Regulatory-Auditor** | Cites the specific compliance clause a flagged invoice violates (RAG over seeded clauses) |
| **Ring-Auditor** | Network-level fraud: builds the payment graph, detects money-muling rings (circular billing / structuring / shell suppliers), HMAC-signs each ring, routes by risk to human review |
| **PO-Critic / Dispute-Critic** | Reflection loops that revise oversized POs / weak disputes before they reach the approval queue |

### 4.2 Data flow

```
   POS sales ┐
  inventory  ├─►  DQ-Sentinel  ──►  Demand-Forecaster  ◄─negotiate─►  Stock-Watcher  ──►  Ops-Planner ──► [PO DRAFT]
  invoices  ─┘  (PayGuardDQ tool)                                                        (PO-Critic, HITL)     │
                     │                                                                                          │
                 rejected                                                                                       ▼
                 records                                        Supplier invoice ──► Payment-Auditor ──► Regulatory-Auditor
                                                                 (vs PO)             (Dispute-Critic)    (clause citation)
                                                                                            │
                                                                                            ▼
                                                              confidence-scored drafts → HITL queue / auto-execute
                                                                                            │
                                                                                            ▼
                                                                          HMAC-SHA256 signed evidence dossiers
```

### 4.3 Hardware-driven technology choices

Every choice follows from the primary demo machine — a laptop with a 6 GB-VRAM GPU on
mobile data — so the reasoning model must be small, quantized, and local, and every
store must be embedded and in-process.

| Component | Choice | Rationale |
|---|---|---|
| Orchestration | LangGraph (+ supervisor) | dynamic routing, not a fixed pipeline |
| Language model | **Self-hosted** — Ollama (`phi4-mini`) or vLLM | course constraint; strong tool/JSON reliability at 6 GB; no cloud dependency |
| Relational | SQLite (stdlib) | metadata store; also the LangGraph checkpoint backend |
| Graph | Kùzu (embedded, Cypher) | supplier/dispute fraud-ring queries, no server |
| Vector / docs | Chroma (embedded) | regulatory RAG + long-term case memory |
| Embeddings | MiniLM, CPU-only | keeps all VRAM for the reasoning model |
| Tools | MCP + custom | validation / relational / graph / doc sources as real MCP tools |
| Dashboard | Streamlit | interactive operator demo |

**Single-model tradeoff (deliberate):** rather than a stronger supervisor model and a
cheaper worker model (which would thrash a single 6 GB card), one model is loaded and
roles are differentiated by system prompt. The explanation is worth more to a grader
than the two-model setup would have been.

---

## 5. Rubric coverage

| Rubric capability | How it is satisfied | Primary artifact |
|---|---|---|
| User–agent interaction | Streamlit dashboard: build a batch, run the supervisor, work the HITL queue, one-click HMAC verify + tamper demo | `dashboard/app.py` |
| Language-model integration | Self-hosted Ollama/vLLM at each `LLM-HOOK`; deterministic offline stub otherwise | `src/core/llm.py` |
| Tools (MCP + custom) | 7 schema'd tools (DQ, SQL, graph, doc, case, sign, verify) as a ToolKit and over an MCP server | `src/agents/tools.py`, `mcp_server/server.py` |
| Memory & knowledge | SQLite checkpoint · Chroma `case_history` + `regulatory_docs` · Kùzu graph | `src/core/{checkpoint,memory,graph_store,relational}.py` |
| Orchestration | Dynamic-routing supervisor | `src/agents/orchestrator.py` |
| Multi-agent *(expected)* | 7 agents + 2 critics | `src/agents/` |
| Feedback loops *(expected)* | Reflection critics · Demand↔Stock negotiation · confidence-based HITL | `critics.py`, `negotiation.py`, `hitl.py` |

Full mapping: `docs/RUBRIC_TRACEABILITY.md`.

---

## 6. Safety & integrity design

- **Tamper-evident evidence.** Every PO draft, dispute, and negotiation transcript is
  sealed in an **HMAC-SHA256** dossier over a canonical JSON body using a server-held
  key (`src/core/audit.py`). This replaces the spoofable self-supplied SHA-256 checksum
  flagged in the original PayGuard review — an attacker who controls the payload cannot
  forge a valid signature without the key. The dashboard's tamper demo flips verification
  to INVALID on a single injected field.
- **Humans approve money.** Every purchase order and dispute stays
  `requires_human_approval = True`; dispute verdicts default to `NEEDS_REVIEW`. No
  autonomous financial liability decision is made.
- **Calibrated autonomy.** Each consequential draft carries a confidence; low-confidence
  or high-value drafts route to the human queue, high-confidence low-value ones can
  auto-execute.
- **Degrade gracefully.** If the model is unreachable, agents receive a clearly-marked
  offline stub — the deterministic conclusion is never skipped or silently replaced.

---

## 7. Evaluation

A labeled synthetic evaluation set measures both decision quality and agentic behaviour.
Current baseline (deterministic core, offline stub for language reasoning):

| Metric | Value |
|---|---|
| Restock decision accuracy (n=30) | 0.733 |
| Restock precision / recall / F1 | 0.706 / 0.800 / 0.750 |
| Invoice-audit accuracy (n=20) | 1.000 |
| Money-muling ring recall (2 planted rings) | 1.000 (payroll false-positive: none) |
| Plan-revision rate (critic activity) | 0.500 |
| Critic recall | 1.000 |
| Escalation miss rate | 0.000 (6 auto-approved) |

Reproduce with `python evaluation/run_eval.py`. The restock numbers reflect the
heuristic forecaster; the harness is designed so the same metrics can be re-run after
enabling the self-hosted language-model hooks to quantify the uplift. Invoice-audit
accuracy is perfect on the current set because duplicate/mismatch detection is
deterministic. **These figures describe the synthetic test set only** — no claim is
made about real-world performance.

---

## 8. Honest status & limitations

- All data is **synthetic**; no real payments are executed and no cardholder data is used.
- **No compliance certification** is claimed — the fraud/compliance framing is a design
  target, kept deliberately honest.
- The real Ollama / vLLM / Kùzu / Chroma backends each have a tested pure-Python
  fallback, and it is those fallbacks the 63-test suite exercises. The **live** backends
  have **not** yet been run on the demo laptop — that on-laptop validation is the one
  remaining hands-on step.
- The language-model hooks are wired and offline-tested; live-model uplift over the
  heuristic baseline is future measurement work.

---

## 9. Division of labour (suggested)

| Area | Lead |
|---|---|
| DQ tool, agents, audit, orchestration | Siddharth |
| Retail data, forecasting, evaluation set | Revanth |
| Dashboard, demo, front-end integration | Vishnu |

---

## 10. Conclusion

PayGuard-AgentX demonstrates a complete, guarded agentic loop across every mandatory
rubric capability — user interaction, a self-hosted language model, MCP and custom
tools, memory and knowledge integration, and dynamic orchestration — plus the expected
multi-agent and feedback-loop extensions (reflection, negotiation, calibrated HITL). Its
distinguishing contribution is **institutional integrity**: a tamper-evident, signed money
trail where humans approve every consequential decision. The engineering is deliberately
scoped to a 6 GB-VRAM laptop with honest, tested fallbacks — a system that runs anywhere
and is defensible in a viva rather than one that overclaims.
