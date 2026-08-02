# 🛡️🛒 PayGuard-AgentX → **ShelfGuard-AgentX**

> **Agentic Retail Operations + Procurement-Integrity Copilot**
> A multi-agent system that decides *what a store should restock* — and *guards the data and money* around every purchase order it creates.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Orchestration: LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Status: Phase 1 — scaffolding runs](https://img.shields.io/badge/status-Phase%201%20(runs)-green.svg)](docs/ROADMAP.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What this is

`ShelfGuard-AgentX` fuses two ideas into one project:

- **ShelfSense** — a retail copilot that reads sales + inventory and proposes restock quantities, prices, and purchase orders.
- **PayGuard-AgentX** — a multi-agent financial *data-quality + fraud + dispute* engine.

They meet at one natural loop: the **purchase order → supplier invoice → payment** cycle. ShelfSense decides *what to buy*; PayGuard *guards the data going in and audits the money coming back*. The result is a single agentic system where the deterministic PayGuardDQ engine is a **tool** the agents call — not a passive validator — which is what makes the loop genuinely *agentic*.

> **Honest status:** Phase 1 is built and runs end-to-end (deterministic, no API key needed). The LLM reasoning inside the agents, the RAG/regulatory layer, and the dashboard are planned — see [docs/ROADMAP.md](docs/ROADMAP.md). Nothing here is production-audited; the compliance/fraud language describes the *design target*, not a certified system.

---

## How the two projects map

| PayGuard-AgentX agent (financial origin) | Role in ShelfGuard (retail + procurement) | Built in Phase 1? |
|---|---|---|
| **DQ-Sentinel** | Validates every inbound record — POS sales, inventory snapshots, supplier invoices — via the PayGuardDQ tool | ✅ Yes |
| **Demand-Forecaster** *(ShelfSense)* | Projects near-term demand per store / SKU from validated sales | ✅ Yes (heuristic) |
| **Stock-Watcher** *(ShelfSense)* | Flags SKUs below reorder point or projected demand | ✅ Yes |
| **Ops-Planner** *(ShelfSense)* | Drafts a restock purchase order — **held for human approval** | ✅ Yes |
| **Payment-Auditor** *(PayGuard Forensic + Arbitration)* | Audits returning supplier invoices vs the PO: duplicate billing, PO mismatch → drafts a **dispute** | ✅ Yes |
| **Regulatory-Auditor** *(PayGuard RAG)* | Contract-terms / tax checks on invoices | 🔜 Phase 3 |
| **Self-Healing-Repair** *(PayGuard AST)* | Suggests parser fixes when a supplier changes invoice format (**suggest-only**) | 🔜 Phase 3 |

Every consequential action (PO draft, dispute draft) is recorded in an **HMAC-SHA256 signed evidence dossier** — a real keyed integrity control, not a bare self-supplied hash.

---

## Architecture

```
   POS sales ┐
  inventory  ├─►  DQ-Sentinel  ──►  Demand-Forecaster  ──►  Stock-Watcher  ──►  Ops-Planner ──► [PO DRAFT]
  invoices  ─┘  (PayGuardDQ tool)     (project demand)       (reorder flags)     (HITL approve)      │
                     │                                                                               │
                 rejected                                                                            ▼
                 records                                              Supplier invoice ──► Payment-Auditor
                                                                       (vs PO)             │  duplicate?
                                                                                           │  PO mismatch? ──► [DISPUTE DRAFT]
                                                                                           ▼
                                                                          HMAC-signed evidence dossiers
```

Each box is a pure `state -> state` agent function (`src/agents/pipeline.py`). `run_pipeline()` runs them in sequence; `build_graph()` returns the identical sequence as a compiled **LangGraph** `StateGraph`.

---

## Quick start

```bash
git clone https://github.com/SheeshDarth/PayGuard-AgentX.git
cd PayGuard-AgentX

python -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate

pip install -r requirements.txt    # core scaffolding needs only pydantic

python main.py                     # run the end-to-end demo
pytest -q                          # run the test suite (19 tests)
```

`main.py` prints the full loop: which records DQ-Sentinel rejected, the human-approval-gated purchase order, the supplier over-billing the Payment-Auditor caught, the dispute it drafted, and the verified signed dossiers.

---

## Project layout

```
src/
  models/schemas.py        # Pydantic v2 models (retail + procurement + legacy financial)
  core/dq_engine.py        # PayGuardDQ deterministic validation tool (0 LLM tokens)
  core/audit.py            # HMAC-SHA256 evidence signing / verification
  agents/pipeline.py       # the 5-agent pipeline + LangGraph wiring
  utils/retail_simulator.py# synthetic sales / inventory / invoice generator
main.py                    # end-to-end demo entry point
tests/                     # pytest suite (DQ, audit, each agent, full pipeline)
docs/                      # PRD, TRD, ROADMAP
```

---

## Documentation

- [Product Requirements (PRD)](docs/PRD.md)
- [Technical Requirements (TRD)](docs/TRD.md)
- [Implementation Roadmap](docs/ROADMAP.md)

---

## Team

Siddharth ([@SheeshDarth](https://github.com/SheeshDarth)) · Revanth ([@Revanthm2027](https://github.com/Revanthm2027)) · Vishnu ([@vishnu-k-dev](https://github.com/vishnu-k-dev))

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE).
