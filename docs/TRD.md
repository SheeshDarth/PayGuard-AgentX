# 🛠️ Technical Requirements Document (TRD) — PayGuard-AgentX

> **System architecture, schemas & technical specification**
> Repo: `PayGuard-AgentX` · Concept: `PayGuard-AgentX`

---

## 1. Tech stack

| Component | Choice | Status |
|---|---|---|
| Language | Python 3.11+ | Active |
| Data validation | Pydantic v2 | Active |
| Agent orchestration | LangGraph (`StateGraph`) | Active (optional import; sequential fallback) |
| Audit integrity | `hmac` + `hashlib` (HMAC-SHA256) | Active |
| LLM reasoning | Self-hosted Ollama (`phi4-mini`) / vLLM (at `LLM-HOOK` points) | Implemented with offline fallback |
| Regulatory RAG | ChromaDB | Implemented with keyword fallback |
| Dashboard | Streamlit | Implemented |

The offline installation runs without live-backend packages. `langgraph`, MCP,
Kùzu, Chroma, and embeddings are available through `requirements-live.txt`;
the supervised runner remains dependency-light with tested fallbacks.

---

## 2. Module map

```
src/
  models/schemas.py         # Pydantic models
  core/dq_engine.py         # PayGuardDQEngine — deterministic validation TOOL
  core/audit.py             # sign / verify / build_dossier (HMAC-SHA256)
  agents/pipeline.py        # AgentState + 5 agents + run_pipeline + build_graph
  utils/retail_simulator.py # synthetic record generator
main.py                     # demo entry point
```

---

## 3. Core data schemas (Pydantic v2)

**Retail**
```python
class SalesRecord(BaseModel):
    record_id: str; sku: str; store_id: str
    units_sold: int          # DQ: must be > 0
    unit_price: float        # DQ: must be > 0
    currency: str; timestamp: str

class InventorySnapshot(BaseModel):
    record_id: str; sku: str; store_id: str
    on_hand: int             # DQ: >= 0
    reorder_point: int
    timestamp: str

class PurchaseOrderDraft(BaseModel):
    po_id: str; store_id: str
    lines: list[RestockRecommendation]
    total_estimated_cost: float
    currency: str
    requires_human_approval: bool = True
    status: Literal['DRAFT','APPROVED','REJECTED'] = 'DRAFT'
```

**Procurement integrity (PayGuard lineage)**
```python
class SupplierInvoice(BaseModel):
    invoice_id: str; supplier_id: str
    po_id: str | None        # links invoice back to the PO
    sku: str; amount: float; currency: str; timestamp: str
    payload_raw: str
    checksum: str | None     # SHA-256 of payload_raw

class EvidenceDossier(BaseModel):
    dossier_id: str; subject_id: str; timestamp: str
    summary: str; payload: dict
    signature: str                          # HMAC-SHA256 over canonical payload
    signature_algo: Literal['HMAC-SHA256'] = 'HMAC-SHA256'
```

---

## 4. Agent state machine

```python
class AgentState(TypedDict, total=False):
    sales_raw / inventory_raw / invoices_raw: list[str]   # inbound
    valid_sales / valid_inventory / valid_invoices: list[dict]
    rejected: list[dict]
    demand_forecast: dict            # "store|sku" -> projected units
    stock_alerts: list[dict]
    po_draft: dict | None
    payment_flags: list[dict]
    dispute_drafts: list[dict]
    dossiers: list[dict]             # signed audit records
    logs: list[str]
```

**Node sequence** (`build_graph`):
`dq_sentinel → demand_forecaster → stock_watcher → ops_planner → payment_auditor → END`

Each node is a pure `state -> state` function, so the graph is testable without an LLM and the LLM upgrade is a localized change at each `LLM-HOOK`.

---

## 5. DQ tool interface

`PayGuardDQEngine` exposes deterministic, zero-token validators the DQ-Sentinel calls:

| Method | Validates | Returns |
|---|---|---|
| `validate_sales_record(raw)` | units > 0, price > 0, currency supported | `(ok, note, SalesRecord?)` |
| `validate_inventory_snapshot(raw)` | on_hand ≥ 0, reorder ≥ 0 | `(ok, note, InventorySnapshot?)` |
| `validate_supplier_invoice(raw)` | amount > 0, currency, **checksum** | `(ok, note, SupplierInvoice?)` |
| `validate_payload(raw)` *(legacy)* | financial transaction | `(ok, AnomalyDiagnosis, TransactionPayload?)` |

---

## 6. Audit integrity design

The prior PayGuard design compared a SHA-256 of a payload against a checksum field on the *same* payload — spoofable by anyone who controls the payload. PayGuard-AgentX replaces this for evidence signing with **HMAC-SHA256 over a canonical JSON body using a server-held secret** (`PAYGUARD_AUDIT_KEY`):

```python
sign(payload)   -> hmac.new(secret, canonical_json(payload), sha256).hexdigest()
verify(payload, sig) -> hmac.compare_digest(sign(payload), sig)   # constant-time
```

An attacker cannot forge a valid signature without the key. (The supplier-supplied SHA-256 checksum is retained only as a transport-integrity hint on `SupplierInvoice`, never as proof of authenticity.)

---

## 7. Safety design decisions (from the PayGuard council review)

- **Self-Healing-Repair is suggest-only** — the agent may propose a parser patch but never auto-executes code against live parsing logic.
- **Payment-Auditor drafts, humans decide** — dispute verdicts default to `NEEDS_REVIEW` and `requires_human_approval = True`; no autonomous financial liability decision.
- **Truthful dependencies** — `requirements.txt` installs only what is imported; later-phase deps are commented until used.
