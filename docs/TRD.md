# 🛠️ Technical Requirements Document (TRD) — PayGuard-AgentX

> **System Architecture, Schemas, & Technical Specifications**  
> **Project Name:** `PayGuard-AgentX`  

---

## 1. System Architecture & Tech Stack

- **Language:** Python 3.11+
- **Agent Framework:** `LangGraph` + `LangChain`
- **LLM Provider:** Google Gemini 1.5 Flash / LiteLLM / GPT-4o-mini
- **Validation Engine:** Pydantic v2 + Pandas
- **Vector DB:** ChromaDB
- **Dashboard:** Streamlit
- **Hashing & Security:** SHA-256 (`hashlib`)

---

## 2. Core Pydantic Data Models

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class TransactionPayload(BaseModel):
    transaction_id: str
    sender_account: str
    receiver_account: str
    amount: float
    currency: str
    timestamp: str
    payload_raw: str
    checksum: Optional[str] = None

class AnomalyDiagnosis(BaseModel):
    transaction_id: str
    anomaly_type: str  # 'DATA_CORRUPTION' | 'FRAUD_VELOCITY' | 'REGULATORY_VIOLATION'
    severity: str      # 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
    description: str
    recommended_agent: str

class EvidenceDossier(BaseModel):
    dossier_id: str
    transaction_id: str
    timestamp: str
    anomaly_summary: str
    forensic_score: float
    regulatory_clauses: List[str]
    applied_patch: Optional[str] = None
    dispute_verdict: str  # 'MERCHANT_LIABLE' | 'BANK_LIABLE' | 'SPLIT_SETTLEMENT'
    sha256_signature: str
```

---

## 3. LangGraph State Machine Schema

```python
from typing import TypedDict, List

class AgentState(TypedDict):
    transaction: dict
    anomaly_diagnosis: dict
    forensic_result: dict
    regulatory_citations: List[str]
    patch_code: str
    execution_success: bool
    dispute_verdict: str
    logs: List[str]
    current_step: str
```

---

## 4. Subsystem Execution Flow

1. **Ingestion Layer:** Reads stream payload -> executes deterministic `PayGuardDQ` rules -> passes flagged payloads to `AgentState`.
2. **Sentinel Layer:** `DQ-SentinelAgent` classifies anomaly type -> routes to worker node.
3. **Worker Processing:**
   - Schema errors -> `SelfHealing-RepairAgent` (AST parser + sandboxed patch execution).
   - Velocity anomalies -> `Forensic-InvestigatorAgent` (`OriginX-T Lite` 30/90-day calculation).
   - Compliance errors -> `Regulatory-AuditorAgent` (ChromaDB similarity search).
4. **Arbitration & Evidence:** `Arbitration-DisputeAgent` synthesizes findings -> generates SHA-256 signed dossier -> broadcasts to Streamlit War-Room.
