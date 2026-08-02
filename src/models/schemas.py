"""
PayGuard-AgentX Core Data Schemas (Pydantic v2)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class TransactionPayload(BaseModel):
    transaction_id: str = Field(..., description="Unique transaction identifier")
    sender_account: str = Field(..., description="Sender account number / ID")
    receiver_account: str = Field(..., description="Receiver account number / ID")
    amount: float = Field(..., description="Transaction monetary amount")
    currency: str = Field(..., description="ISO 4217 Currency code (e.g. USD, EUR, INR)")
    timestamp: str = Field(..., description="ISO 8601 timestamp string")
    payload_raw: str = Field(..., description="Raw JSON/XML payload text")
    checksum: Optional[str] = Field(None, description="SHA-256 payload checksum")

class AnomalyDiagnosis(BaseModel):
    transaction_id: str
    anomaly_type: Literal['DATA_CORRUPTION', 'FRAUD_VELOCITY', 'REGULATORY_VIOLATION', 'CLEAN']
    severity: Literal['NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    description: str
    recommended_agent: Optional[str] = None

class EvidenceDossier(BaseModel):
    dossier_id: str
    transaction_id: str
    timestamp: str
    anomaly_summary: str
    forensic_score: float = Field(..., ge=0.0, le=100.0)
    regulatory_clauses: List[str] = Field(default_factory=list)
    applied_patch: Optional[str] = None
    dispute_verdict: Literal['MERCHANT_LIABLE', 'BANK_LIABLE', 'SPLIT_SETTLEMENT', 'NO_DISPUTE']
    sha256_signature: str
