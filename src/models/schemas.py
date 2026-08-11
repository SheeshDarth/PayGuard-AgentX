"""
PayGuard-AgentX Core Data Schemas (Pydantic v2)

Two families of models:
  1. Retail operations  — SalesRecord, InventorySnapshot, RestockRecommendation, PurchaseOrderDraft
  2. Procurement integrity (PayGuard lineage) — SupplierInvoice, PaymentFlag, DisputeDraft, EvidenceDossier

The original financial TransactionPayload / AnomalyDiagnosis are retained so the
existing PayGuardDQ engine and its tests keep working unchanged.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


# ---------------------------------------------------------------------------
# Legacy financial models (retained for backward compatibility)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Retail operations models (ShelfSense lineage)
# ---------------------------------------------------------------------------

class SalesRecord(BaseModel):
    """A single point-of-sale line item."""
    record_id: str
    sku: str
    store_id: str
    units_sold: int = Field(..., description="Units sold (must be > 0)")
    unit_price: float = Field(..., description="Price per unit at time of sale")
    currency: str
    timestamp: str


class InventorySnapshot(BaseModel):
    """On-hand stock for a SKU at a store at a point in time."""
    record_id: str
    sku: str
    store_id: str
    on_hand: int = Field(..., description="Units currently on hand (>= 0)")
    reorder_point: int = Field(..., description="Threshold below which restock is triggered")
    timestamp: str


class RestockRecommendation(BaseModel):
    sku: str
    store_id: str
    current_on_hand: int
    projected_demand: int
    recommend_order_qty: int = Field(..., ge=0)
    rationale: str


class PurchaseOrderDraft(BaseModel):
    po_id: str
    store_id: str
    lines: List[RestockRecommendation] = Field(default_factory=list)
    total_estimated_cost: float = Field(..., ge=0.0)
    currency: str
    requires_human_approval: bool = True
    status: Literal['DRAFT', 'APPROVED', 'REJECTED'] = 'DRAFT'


# ---------------------------------------------------------------------------
# Procurement integrity models (PayGuard lineage)
# ---------------------------------------------------------------------------

class SupplierInvoice(BaseModel):
    """A supplier's bill for a fulfilled (or claimed) purchase order."""
    invoice_id: str
    supplier_id: str
    po_id: Optional[str] = Field(None, description="Purchase order this invoice bills against")
    sku: str
    amount: float
    currency: str
    timestamp: str
    payload_raw: str = Field(..., description="Raw invoice text used for checksum verification")
    checksum: Optional[str] = Field(None, description="SHA-256 of payload_raw supplied by sender")


class PaymentFlag(BaseModel):
    invoice_id: str
    flag_type: Literal['DUPLICATE', 'PO_MISMATCH', 'AMOUNT_ANOMALY', 'CHECKSUM_FAIL', 'CLEAN']
    severity: Literal['NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    description: str


class DisputeDraft(BaseModel):
    dispute_id: str
    invoice_id: str
    po_id: Optional[str] = None
    reason: str
    claimed_amount: float
    expected_amount: float
    proposed_verdict: Literal['SUPPLIER_LIABLE', 'BUYER_LIABLE', 'SPLIT', 'NEEDS_REVIEW'] = 'NEEDS_REVIEW'
    requires_human_approval: bool = True


class EvidenceDossier(BaseModel):
    """
    Tamper-evident audit record for a consequential action (PO approval, payment,
    or dispute). The signature is an HMAC-SHA256 over the canonical dossier body
    using a server-held secret — NOT a bare self-supplied hash. (See src/core/audit.py.)
    """
    dossier_id: str
    subject_id: str = Field(..., description="ID of the PO / invoice / dispute this attests to")
    timestamp: str
    summary: str
    payload: dict = Field(default_factory=dict, description="Canonical body that was signed")
    signature: str = Field(..., description="HMAC-SHA256 hex digest over payload")
    signature_algo: Literal['HMAC-SHA256'] = 'HMAC-SHA256'


# ---------------------------------------------------------------------------
# Agentic layer (scale-up) -- confidence, negotiation, critics, trace
# ---------------------------------------------------------------------------

class AgentDecision(BaseModel):
    """A consequential agent output carrying a calibrated confidence."""
    agent: str
    subject_id: str
    summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_human_approval: bool = True


class NegotiationTurn(BaseModel):
    agent: str
    round: int = Field(..., ge=1)
    position: str
    rationale: str


class NegotiationTranscript(BaseModel):
    topic: str
    turns: List[NegotiationTurn] = Field(default_factory=list)
    rounds: int = 0
    resolution: str = ""


class CriticReview(BaseModel):
    critic: str
    target_id: str
    verdict: Literal['APPROVE', 'REVISE']
    issues: List[str] = Field(default_factory=list)
    revised: bool = False


class TraceEvent(BaseModel):
    run_id: str
    step: int
    agent: str
    action: str          # 'tool_call' | 'decision' | 'memory_read' | 'negotiation'
    detail: str
    confidence: Optional[float] = None
    timestamp: str


# ---------------------------------------------------------------------------
# Network-fraud layer (money-muling integration)
# ---------------------------------------------------------------------------

class MuleRing(BaseModel):
    """A detected money-muling fraud ring (procurement-collusion reframing)."""
    ring_id: str
    member_accounts: List[str] = Field(default_factory=list)
    pattern_type: Literal['cycle', 'smurfing', 'shell_network', 'mixed']
    risk_score: float = Field(..., ge=0.0, le=100.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class RingFinding(BaseModel):
    """A per-account suspicion finding produced by the money-muling scorer."""
    account_id: str
    suspicion_score: float = Field(..., ge=0.0, le=100.0)
    detected_patterns: List[str] = Field(default_factory=list)
    ring_id: str = "NONE"
