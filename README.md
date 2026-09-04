# 🛡️🛒 PayGuard-AgentX

> **Agentic Retail Operations + Procurement-Integrity Copilot**
> A multi-agent system that decides *what a store should restock* — and *guards the data and money* around every purchase order it creates.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Orchestration: LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![LLM: self-hosted (Ollama/vLLM)](https://img.shields.io/badge/LLM-self--hosted%20Ollama%2FvLLM-green.svg)](src/core/llm.py)
[![Tests: 107 passing](https://img.shields.io/badge/tests-107%20passing-brightgreen.svg)](tests/)
[![UI: zero dependencies](https://img.shields.io/badge/UI-HTML%2FCSS%2FJS%20%C2%B7%20no%20framework-blueviolet.svg)](web/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<!-- Screenshot: run `python -m web.server`, open http://127.0.0.1:8000, run the
     "2 · Suspicious Invoice" scenario, save the page as docs/screenshot.png,
     then uncomment the line below.
![PayGuard-AgentX dashboard](docs/screenshot.png)
-->

---

## What this is

`PayGuard-AgentX` fuses two ideas into one project:

- **ShelfSense** — a retail copilot that reads sales + inventory and proposes restock quantities and purchase orders.
- **PayGuard-AgentX** — a multi-agent financial *data-quality + fraud + dispute* engine.

They meet at one natural loop: the **purchase order → supplier invoice → payment** cycle. ShelfSense decides *what to buy*; PayGuard *guards the data going in and audits the money coming back*. The deterministic PayGuardDQ engine is a **tool the agents call** — not a passive validator — which is what makes the loop genuinely *agentic*.

> **Honest status:** the guarded multi-agent loop runs end-to-end offline with **no GPU, no network, and no API key**. The operator dashboard is hand-written HTML/CSS/JS served by Python's standard-library `http.server` — no web framework, no build step, no CDN, no `npm install` — and separates Action Inbox, Operations, Analyst Workspace, Cases, Evidence, Agent System, and Settings. PostgreSQL/OIDC/live backends are installable paths; SQLite and deterministic fallbacks remain the guaranteed demo path. Nothing here is production-audited and all data is synthetic.

---

## Architecture

```
                        User (browser)
                              │
                    HTML / CSS / JS dashboard          web/static/
                              │  fetch() JSON
                    http.server JSON API               web/server.py
                              │
                  Supervisor / LangGraph               src/agents/orchestrator.py
                              │  dynamic route
        ┌─────────────┬───────┴───────┬─────────────┬──────────────┐
   DQ-Sentinel   Demand +Stock    Ops-Planner   Payment-Auditor  Ring-Auditor
        │        (+negotiation)        │        (+Regulatory)         │
        └─────────────┴───────┬───────┴─────────────┴──────────────┘
                              │  tools
        ┌──────────┬──────────┼──────────┬────────────────┐
    DQ Engine   Relational  Knowledge   RAG / Memory   Fraud Detection
   (0 tokens)    SQLite    Graph (Kùzu)   (Chroma)      (src/core/mule/)
        └──────────┴──────────┼──────────┴────────────────┘
                              │
                 PO/Dispute Critics → HITL queue
                              │
              Evidence dossier (HMAC-SHA256, signed)
                              │
                      ▶ Human decision
              (approve / reject / escalate / dismiss)
```

Every box below the supervisor has a tested offline fallback, so the whole path
runs with no model, no GPU, and no network. **No branch executes a payment** —
the pipeline terminates in a human decision, and approving records a signed
decision only.

---

## Capabilities (mapped to the Agentic AI rubric)

| Capability | Implementation | Artifact |
|---|---|---|
| **User–agent interaction** | Zero-dependency web dashboard: run a demo scenario, work the Action Inbox, read *why* each item was flagged, review cases, and verify signed evidence | [`web/`](web/server.py) |
| **Language model** | Self-hosted only — **Ollama** (`phi4-mini`) or **vLLM**, called at each `LLM-HOOK`; deterministic offline stub otherwise | [`src/core/llm.py`](src/core/llm.py) |
| **Tools (MCP + custom)** | 8 schema'd tools (DQ / relational / graph / doc / case / sign / verify / mule-ring scan) as a ToolKit and over an MCP server | [`tools.py`](src/agents/tools.py), [`mcp_server/`](mcp_server/server.py) |
| **Memory & knowledge** | SQLite checkpoint · Chroma `case_history` + `regulatory_docs` RAG · Kùzu (Cypher) graph | [`core/`](src/core/) |
| **Orchestration** | Dynamic-routing supervisor (`restock_only` / `audit_only` / `full` / `noop`) | [`orchestrator.py`](src/agents/orchestrator.py) |
| **Multi-agent** | 7 agents + PO/Dispute critics | [`agents/`](src/agents/) |
| **Feedback loops** | Reflection critics · Demand↔Stock negotiation · human-only HITL | [`critics.py`](src/agents/critics.py), [`negotiation.py`](src/agents/negotiation.py), [`hitl.py`](src/agents/hitl.py) |
| **Network-level fraud** | Money-muling graph scan — circular billing (cycles), invoice structuring (smurfing), shell suppliers — with multi-signal 0–100 scoring, false-positive suppression, and a Cypher knowledge-graph artifact | [`src/core/mule/`](src/core/mule/) |

The **Agent System** screen makes the agentic design visible without requiring a
reader to inspect source code. It shows the supervisor, specialist agents,
reflection critics, and HITL controller, including each agent's purpose and
authority boundary. Agents choose a route, call tools, produce evidence-backed
recommendations, critique drafts, and stop for a human decision; they do not
authorize payment or supplier submission.

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

## Getting started

### Prerequisites

| Need | Version | Notes |
|---|---|---|
| Python | 3.11 or newer | `python --version` |
| A browser | any modern one | Chrome, Edge, Firefox, Safari |
| Network | **not required** | nothing is downloaded at runtime |

There is no Node.js, npm, bundler, or JavaScript toolchain requirement. The
dashboard is four static files served by Python's standard library.

### Install

```bash
git clone https://github.com/SheeshDarth/PayGuard-AgentX.git
cd PayGuard-AgentX
python -m venv venv
```

Activate the environment:

```bash
source venv/bin/activate
```

On Windows PowerShell instead:

```powershell
venv\Scripts\Activate.ps1
```

Then install — the entire dependency list is `pydantic`, `pytest`, `rich`:

```bash
pip install -r requirements.txt
```

### Run the dashboard

```bash
python -m web.server
```

Open **http://127.0.0.1:8000**. Pick a scenario, select **Run demo**.

To use a different port:

```bash
python -m web.server 8080
```

### Other entry points

Terminal demo — the whole supervised pipeline, no browser:

```bash
python main.py
```

Full test suite (107 tests, ~5 seconds):

```bash
pytest -q
```

Evaluation harness — labelled accuracy plus agentic metrics:

```bash
python evaluation/run_eval.py
```

### Verify the install

A healthy setup prints `107 passed` from `pytest -q`, and `python main.py` ends
with `Done. Deterministic run -- no LLM, GPU or network required.` In the
dashboard, the sidebar **System status** should show seven ticks with
`LLM: offline stub` and `Mode: Demo`.

### Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `No module named web` | Run from the repository root, not from inside `web/`. |
| `Address already in use` | Another process holds 8000. Use `python -m web.server 8080`. |
| Dashboard loads but says it cannot reach the server | The server exited. Check the terminal running `python -m web.server`. |
| Hero background is flat dark, no motion | WebGL is unavailable or reduced-motion is on. Cosmetic only — every feature still works. |
| An action shows no Approve/Reject | Your role cannot decide that item. Change the demo role in **Settings**. |
| Scenario re-runs open with an already-decided queue | Select **Reset** to clear the workspace. |
| `PAYGUARD_AUDIT_KEY is a public/demo value` warning | Expected in demo mode. Set a private key for trusted evidence. |

### Configuration (all optional)

| Variable | Default | Effect |
|---|---|---|
| `PAYGUARD_AUDIT_KEY` | demo value | HMAC signing key for evidence dossiers |
| `PAYGUARD_SQLITE_PATH` | `.payguard/workspace.sqlite` | where decisions persist |
| `PAYGUARD_DEMO_MODE` | on | enables the demo role selector |
| `PAYGUARD_DEFAULT_ROLE` | `OPERATIONS` | role when demo mode is off |
| `PAYGUARD_LLM_BACKEND` | unset (offline stub) | `ollama` or `vllm` — self-hosted only |

State lives in `.payguard/workspace.sqlite`. Delete that directory, or use the
in-app **Reset**, to start clean. Approval records a signed decision only — it
never executes a payment or sends a purchase order. Optional local-backend checks:
`pip install -r requirements-live.txt` then `python scripts/smoke_live.py`.

**Optional live LLM (self-hosted only):** set `PAYGUARD_LLM_BACKEND=ollama` + `PAYGUARD_LLM_MODEL=phi4-mini` (after `ollama pull phi4-mini`), or `PAYGUARD_LLM_BACKEND=vllm` with a running vLLM server. No cloud provider is ever called. See [.env.example](.env.example).

---

## The interface

Six screens, one page, no client-side framework.

| Screen | What it is for |
|---|---|
| **Action Inbox** | Everything waiting on a person, highest severity first, each with a *Why this was flagged* panel and the agent execution timeline. |
| **Operations** | The retail side of a run: low stock, the drafted purchase order and its rationale, invoice checks, and records quarantined at the DQ gate. |
| **Analyst Workspace** | Network-level fraud: the relationship map, per-account signals, ring transactions, and the payroll false-positive control. |
| **Cases** | One case per alert, searchable, status following the decision you record. |
| **Evidence** | Signed dossiers, with server-side verification and a tamper demonstration. |
| **Settings** | Demo role, the role/capability matrix, and live runtime status. |

**Design notes.** A serif display face carries the wordmark and section titles
against a neutral sans for operational text — the pairing financial-audit tooling
has always used. The violet signature colour sits deliberately outside the
severity scale, so red, amber, green and blue are reserved for data and the
chrome can never imply an alert state. Both fonts resolve to faces already on the
machine; requesting a webfont would break the offline guarantee.

The background is **Auralis**, a WebGL ambient shader ([`web/static/auralis.js`](web/static/auralis.js))
— layered simplex noise, glow, and film grain. One fixed canvas covers the whole
content column (the sidebar stays opaque), with panels and cards rendered as
translucent glass so the field reads through the gutters without costing
legibility. A theme-aware veil sits between the two: a light wash in the light
theme, a dark one in dark, so the same violet field works in both. It honours
`prefers-reduced-motion`, pauses when the tab is hidden, and falls back to the
flat theme background if WebGL is unavailable.

Contrast was bounded against the shader's own extremes — its maximum output
`rgb(164,121,255)` derived from the GLSL, composited under each veil — so text
sitting directly on the field stays **WCAG AA in both themes on every frame**
(worst case 4.54:1).

---

## Demo scenarios

Open the dashboard, pick a scenario, and select **Run demo**. Each one runs the
*same* agents over a different synthetic input, so the supervisor's dynamic
routing is visible in the agent timeline — agents the route did not need are
shown as **skipped**, never as executed.

| Scenario | What it shows | Route taken |
|---|---|---|
| **1 · Normal Restock** | Low inventory → demand projection → restock recommendation → purchase-order draft held for approval | `restock_only` |
| **2 · Suspicious Invoice** | Invoice validation → PO mismatch **and** duplicate billing → regulatory clause citation → dispute recommendation → human approval | `full` |
| **3 · Fraud Ring** | Supplier relationships → circular billing + shell-supplier chain → 0–100 fraud score with evidence → human review (and a payroll run that is correctly *not* flagged) | `ring_only` |
| **4 · Data-Quality Quarantine** | Malformed and checksum-failed records stopped at the gate before any agent reasons over them | `full` |
| **5 · Walmart Historical Sales** | Public Walmart store/department weekly sales drive demand and a clearly labeled derived stock baseline; real inventory and procurement feeds are not public | `restock_only` |

Every card carries a **Why this was flagged** panel built from the engine's own
output — deviation percentages, the cited compliance clause, which fraud signals
fired on which account. Nothing in that panel is generated for display.

### Walmart data demo

The Walmart mode uses the public Walmart Store Sales Forecasting files. Download
them once with:

```powershell
python scripts\download_walmart_data.py
```

Then select **5 · Walmart Historical Sales**. The pipeline reads real weekly
sales from multiple Walmart stores and departments, converts revenue into a
transparent sales-equivalent demand measure, derives a demo inventory baseline,
and produces restock recommendations. Walmart does not publish the internal
inventory, supplier, invoice, or payment-network data required for the other
PayGuard controls, so those fraud scenarios remain labeled seeded demonstrations.

---

## Demo in 60 seconds

The shortest reliable sequence for a walkthrough:

```bash
python -m web.server
```

1. Open **http://127.0.0.1:8000** — the header states what the system does.
2. Scenario **2 · Suspicious Invoice** → **Run demo**.
3. **Action Inbox** — a HIGH invoice dispute (supplier, amount, confidence) and a
   MEDIUM purchase order.
4. Expand **Why this was flagged** — the 487% PO deviation, the duplicate, and
   the cited clause `REG_PO_MATCH`.
5. Scroll to **Agent execution** — all ten agents ran; route `full`.
6. Select **Approve**. The decision is signed; the item leaves the queue.
7. Scenario **3 · Fraud Ring** → **Run demo** → **Analyst Workspace** — the
   closed billing loop `SUP_A → SUP_B → SUP_C → back to SUP_A`, risk 70/100, and
   the payroll false-positive control. Note the timeline now shows six agents
   **skipped** — the route changed.
8. **Evidence** → **Demo: tamper with payload** — the HMAC signature fails.
9. **Settings** → switch the demo role to `VIEWER`; the decision buttons disable
   (the server rejects the call too, not just the browser).

Select **Reset** to run any scenario again from a clean queue.

---

## Project layout

```
web/server.py               # stdlib http.server: static files + JSON API
web/static/index.html       #   dashboard shell (6 views, one page)
web/static/app.css          #   design tokens + components, light + dark
web/static/app.js           #   rendering + decisions (vanilla, no framework)
web/static/auralis.js       #   Auralis WebGL ambient hero shader
dashboard/services/         # UI-independent service layer
  workflows.py              #   scenarios, agent timeline, why-flagged, status
  session.py                #   run + persist + record decisions
  storage.py                #   SQLite (default) / PostgreSQL repository
  auth.py                   #   roles and server-enforced capabilities
  config.py                 #   environment boundary
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
tests/                      # 103 pytest cases
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
| Dashboard | Hand-written HTML/CSS/JS on `http.server` | zero dependencies, zero build step; a grader with no network can clone and run it |

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
