# 🛡️🛒 PayGuard-AgentX

> **Agentic Retail Operations + Procurement-Integrity Copilot**
> A multi-agent system that decides *what a store should restock* — and *guards the data and money* around every purchase order it creates.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Orchestration: LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![LLM: self-hosted (Ollama/vLLM)](https://img.shields.io/badge/LLM-self--hosted%20Ollama%2FvLLM-green.svg)](src/core/llm.py)
[![Tests: passing](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What this is

`PayGuard-AgentX` fuses two ideas into one project:

- **ShelfSense** — a retail copilot that reads sales + inventory and proposes restock quantities and purchase orders.
- **PayGuard-AgentX** — a multi-agent financial *data-quality + fraud + dispute* engine.

They meet at one natural loop: the **purchase order → supplier invoice → payment** cycle. ShelfSense decides *what to buy*; PayGuard *guards the data going in and audits the money coming back*. The deterministic PayGuardDQ engine is a **tool the agents call** — not a passive validator — which is what makes the loop genuinely *agentic*.

> **Honest status:** the guarded multi-agent loop runs end-to-end offline with **no GPU, no network, and no API key**. The Streamlit product shell separates Action Inbox, Operations, Analyst Workspace, Cases, Evidence, and Settings. PostgreSQL/OIDC/live backends are installable paths; SQLite and deterministic fallbacks remain the guaranteed demo path. Nothing here is production-audited and all data is synthetic.

---

## Capabilities (mapped to the Agentic AI rubric)

| Capability | Implementation | Artifact |
|---|---|---|
| **User–agent interaction** | Streamlit product shell: run a preset, prioritize the Action Inbox, review cases, and inspect signed evidence | [`dashboard/app.py`](dashboard/app.py) |
| **Language model** | Self-hosted only — **Ollama** (`phi4-mini`) or **vLLM**, called at each `LLM-HOOK`; deterministic offline stub otherwise | [`src/core/llm.py`](src/core/llm.py) |
| **Tools (MCP + custom)** | 8 schema'd tools (DQ / relational / graph / doc / case / sign / verify / mule-ring scan) as a ToolKit and over an MCP server | [`tools.py`](src/agents/tools.py), [`mcp_server/`](mcp_server/server.py) |
| **Memory & knowledge** | SQLite checkpoint · Chroma `case_history` + `regulatory_docs` RAG · Kùzu (Cypher) graph | [`core/`](src/core/) |
| **Orchestration** | Dynamic-routing supervisor (`restock_only` / `audit_only` / `full` / `noop`) | [`orchestrator.py`](src/agents/orchestrator.py) |
| **Multi-agent** | 7 agents + PO/Dispute critics | [`agents/`](src/agents/) |
| **Feedback loops** | Reflection critics · Demand↔Stock negotiation · human-only HITL | [`critics.py`](src/agents/critics.py), [`negotiation.py`](src/agents/negotiation.py), [`hitl.py`](src/agents/hitl.py) |
| **Network-level fraud** | Money-muling graph scan — circular billing (cycles), invoice structuring (smurfing), shell suppliers — with multi-signal 0–100 scoring, false-positive suppression, and a Cypher knowledge-graph artifact | [`src/core/mule/`](src/core/mule/) |

See [docs/RUBRIC_TRACEABILITY.md](docs/RUBRIC_TRACEABILITY.md) for the full mapping and [docs/SDG_ALIGNMENT.md](docs/SDG_ALIGNMENT.md) for SDG 16/12/9.

---

## The agents

| Agent | Role | Lineage |
|---|---|---|
| **DQ-Sentinel** | Validates every inbound record (POS sales, inventory, supplier invoices) via the PayGuardDQ tool; quarantines the rest | PayGuard |
| **Demand-Forecaster** | Projects near-term demand per store / SKU from validated sales | ShelfSense |
| **Stock-Watcher** | Flags SKUs below reorder point or projected demand | ShelfSense |
| **Ops-Planner** | Drafts a restock purchase order — **held for human approval** | ShelfSense |
| **Payment-Auditor** | Audits returning invoices vs the PO: duplicate billing / PO mismatch → drafts a **dispute** | PayGuard |
| **Regulatory-Auditor** | Cites the compliance clause a flagged invoice violates (Chroma RAG) | PayGuard |
| **PO-Critic / Dispute-Critic** | Reflection loops that revise oversized POs / weak disputes before the HITL queue | — |

Every consequential action (PO draft, dispute, negotiation transcript) is sealed in an **HMAC-SHA256 signed evidence dossier** — a real keyed integrity control, not a spoofable self-supplied hash. Every money-spending action stays `requires_human_approval = True`.

---

## Quick start

```bash
git clone https://github.com/SheeshDarth/PayGuard-AgentX.git
cd PayGuard-AgentX

python -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate
pip install -r requirements.txt    # core scaffolding needs only pydantic

python main.py                     # end-to-end demo (offline, no key needed)
pytest -q                          # full test suite
python evaluation/run_eval.py      # evaluation baseline + agentic metrics
streamlit run dashboard/app.py     # operator dashboard -> http://localhost:8501
```

The dashboard persists operator dispositions in `.payguard/workspace.sqlite` and
signs them with HMAC-SHA256. Approval records a decision only; it never executes
a payment or sends a purchase order. Optional local-backend checks are available
with `pip install -r requirements-live.txt` followed by
`python scripts/smoke_live.py`.

**Optional live LLM (self-hosted only):** set `PAYGUARD_LLM_BACKEND=ollama` + `PAYGUARD_LLM_MODEL=phi4-mini` (after `ollama pull phi4-mini`), or `PAYGUARD_LLM_BACKEND=vllm` with a running vLLM server. No cloud provider is ever called. See [.env.example](.env.example).

---

## Project layout

```
dashboard/app.py            # Streamlit operator dashboard (user-agent interaction)
dashboard/pages/             # Operations, Analyst, Cases, Evidence, Settings pages
dashboard/services/          # configuration, auth, workflows, storage, decisions
dashboard/ui/                # semantic theme and reusable product components
mcp_server/server.py        # MCP tool server exposing the ToolKit
src/
  models/schemas.py         # Pydantic v2 models (retail + procurement + legacy)
  core/
    dq_engine.py            # PayGuardDQ deterministic validation tool (0 LLM tokens)
    audit.py                # HMAC-SHA256 evidence signing / verification
    llm.py                  # self-hosted LLM layer (Ollama | vLLM | offline stub)
    relational.py           # SQLite vendor/store/SKU/PO metadata
    graph_store.py          # Kùzu (Cypher) graph, in-memory fallback
    memory.py               # Chroma case_history + regulatory_docs RAG, keyword fallback
    checkpoint.py           # LangGraph SqliteSaver factory
    regulatory_seed.py      # seeded compliance clauses
    trace.py                # structured SQLite trace log
    mule/                   # money-muling graph detection (Phase 1-2)
      graph_model.py        #   directed weighted graph + per-account stats
      cycle_detector.py     #   circular billing rings (Tarjan SCC + bounded DFS)
      smurfing_detector.py  #   fan-in/out structuring (72h window)
      shell_detector.py     #   pass-through shell suppliers
      suppressor.py         #   payroll/merchant/exchange false-positive filter
      scorer.py             #   multi-signal 0-100 score + Union-Find rings
      queries.cypher        #   knowledge-graph evidence (cycle/shell)
  agents/
    pipeline.py             # 5 core agents + LangGraph wiring
    orchestrator.py         # dynamic-routing supervisor
    regulatory_auditor.py   # RAG compliance-clause citation
    critics.py              # PO / Dispute reflection loops
    negotiation.py          # Demand<->Stock negotiation protocol
    hitl.py                 # confidence-based human-in-the-loop routing
    tools.py                # ToolKit: 8 schema'd tools
  utils/retail_simulator.py # synthetic sales / inventory / invoice generator
evaluation/run_eval.py      # labeled eval + agentic metrics
main.py                     # end-to-end demo entry point
tests/                      # 72 pytest cases
docs/                       # PRD, TRD, ARCHITECTURE, ROADMAP, RUBRIC, SDG
```

---

## Technology decisions

Local-first for a 6 GB-VRAM laptop on mobile data; every component degrades to a tested offline fallback.

| Component | Choice | Why |
|---|---|---|
| Orchestration | LangGraph (+ supervisor) | dynamic routing, not a fixed pipeline |
| Local LLM | **Ollama** `phi4-mini` / **vLLM** | self-hosted per course constraint; strong tool/JSON reliability at 6 GB; no cloud dependency |
| Relational | SQLite (stdlib) | zero-setup metadata; also the LangGraph checkpoint backend |
| Graph | Kùzu (embedded, Cypher) | supplier/dispute fraud-ring queries, no server |
| Vector / docs | Chroma (embedded) | `regulatory_docs` RAG + `case_history` long-term memory |
| Embeddings | MiniLM, CPU-only | keeps all VRAM for the reasoning LLM |
| Tools | MCP (custom tools) | validation / relational / graph / doc sources as real MCP tools |
| Dashboard | Streamlit | fast interactive demo (trace, HITL queue, HMAC verify) |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the single-model VRAM tradeoff and degrade-gracefully table.

---

## Documentation

- [Product Requirements (PRD)](docs/PRD.md) · [Technical Requirements (TRD)](docs/TRD.md) · [Architecture](docs/ARCHITECTURE.md)
- [Implementation Roadmap](docs/ROADMAP.md) · [Rubric Traceability](docs/RUBRIC_TRACEABILITY.md) · [SDG Alignment](docs/SDG_ALIGNMENT.md)
- **[Final Project Report](docs/FINAL_REPORT.md)**

---

## Team

Siddharth ([@SheeshDarth](https://github.com/SheeshDarth)) · Revanth ([@Revanthm2027](https://github.com/Revanthm2027)) · Vishnu ([@vishnu-k-dev](https://github.com/vishnu-k-dev))

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE).
