# ✅ Rubric Traceability — PayGuard-AgentX (Agentic AI 23AML171)

> Every graded capability mapped to the concrete artifact that implements it, so a
> reviewer can jump straight from the rubric to the code. Offline-tested items run
> today with no GPU/network; live-backend items light up on the RTX 4050 laptop.

| # | Rubric capability | How PayGuard-AgentX satisfies it | Primary artifact | Status |
|---|---|---|---|---|
| 1 | **User–agent interaction** | Streamlit operator dashboard: build a batch, run the supervisor, read the pipeline trace, work the HITL approval queue, one-click HMAC verify with a tamper demo | [`dashboard/app.py`](../dashboard/app.py) | Runs on laptop (`streamlit run`) |
| 2 | **LLM integration** | Ollama-first LLM layer (`phi4-mini` primary, `qwen3:4b` fallback) called at each `LLM-HOOK`; deterministic offline stub keeps the run honest when no model is present | [`src/core/llm.py`](../src/core/llm.py), hooks in [`src/agents/pipeline.py`](../src/agents/pipeline.py) | Live on laptop; offline-tested |
| 3 | **Tools (MCP + custom)** | 8 real tools with schemas covering DQ, SQL, graph, document, case, audit sign/verify, and mule-ring scan, exposed as a `ToolKit` and over MCP | [`src/agents/tools.py`](../src/agents/tools.py), [`mcp_server/server.py`](../mcp_server/server.py) | Offline-tested; MCP smoke-tested when installed |
| 4 | **Memory & knowledge** | Short-term = LangGraph `SqliteSaver`; long-term = Chroma `case_history`; knowledge graph = Kùzu (fraud-ring Cypher); regulatory RAG = Chroma `regulatory_docs`; all with offline fallbacks | [`checkpoint.py`](../src/core/checkpoint.py), [`memory.py`](../src/core/memory.py), [`graph_store.py`](../src/core/graph_store.py), [`relational.py`](../src/core/relational.py) | Offline-tested; live on laptop |
| 5 | **Orchestration** | Dynamic-routing supervisor picks the agents each batch needs (`restock_only` / `audit_only` / `full` / `noop`) — not a fixed pipeline | [`src/agents/orchestrator.py`](../src/agents/orchestrator.py) | Tested |
| 6 | **Multi-agent system** | 7 agents: DQ-Sentinel, Demand-Forecaster, Stock-Watcher, Ops-Planner, Payment-Auditor, Regulatory-Auditor, plus PO-Critic / Dispute-Critic reflectors | [`pipeline.py`](../src/agents/pipeline.py), [`regulatory_auditor.py`](../src/agents/regulatory_auditor.py), [`critics.py`](../src/agents/critics.py) | Tested |
| 7 | **Feedback loops** | (a) Reflection — critics revise oversized POs / weak disputes; (b) Negotiation — Demand↔Stock 2-round exchange on disagreement; (c) confidence-informed mandatory HITL review | [`critics.py`](../src/agents/critics.py), [`negotiation.py`](../src/agents/negotiation.py), [`hitl.py`](../src/agents/hitl.py) | Tested |
| 8 | **Safety / integrity** | HMAC-SHA256 signed evidence dossiers (keyed, not a spoofable self-checksum); every money-spending action `requires_human_approval = True` | [`src/core/audit.py`](../src/core/audit.py) | Tested |
| 9 | **Evaluation** | Labeled eval: restock precision/recall/F1 + invoice-flag accuracy, plus agentic metrics (plan-revision rate, critic recall, escalation miss rate) | [`evaluation/run_eval.py`](../evaluation/run_eval.py) | Tested |
| 10 | **Observability** | Structured SQLite trace log of every agent action with confidence | [`src/core/trace.py`](../src/core/trace.py) | Tested |
| 11 | **Network-level fraud (knowledge graph)** | Money-muling detection — circular billing (cycles), invoice structuring (smurfing), shell suppliers — with multi-signal scoring + false-positive suppression; surfaced by the **Ring-Auditor** agent as HMAC-signed, HITL-routed fraud rings; Cypher artifact for the graph | [`src/core/mule/`](../src/core/mule/), [`ring_auditor.py`](../src/agents/ring_auditor.py), [`queries.cypher`](../src/core/mule/queries.cypher) | Tested |

## Test coverage

`pytest` — **72 passing** across `test_dq_engine`, `test_pipeline` (incl. the end-to-end
`main.py` demo), `test_foundation` (Week 1), `test_week2`, `test_week3`, `test_mule`
(money-muling detectors) and `test_ring_auditor` (Ring-Auditor agent). The Phase-1
deterministic core and the HMAC algorithm are extend-only and were not rewritten.

## Honest-status note

Ollama/vLLM, Kùzu, and Chroma each have a **tested pure-Python fallback**, and it is those
fallbacks the 72-test suite exercises — the suite runs with no GPU, no network and no keys.
The **live** backends have not yet been validated on the demo laptop; that remains an open
step. No production/compliance certification is claimed — the compliance framing is a
design target, kept deliberately honest.
