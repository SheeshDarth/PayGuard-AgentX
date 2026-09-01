"""Product-facing workspace models used by the published UI."""

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


CaseStatus = Literal["OPEN", "INVESTIGATING", "ESCALATED", "RESOLVED", "DISMISSED"]
AlertStatus = Literal["OPEN", "ACKNOWLEDGED", "ESCALATED", "DISMISSED", "RESOLVED"]
DecisionAction = Literal["APPROVED", "REJECTED", "ESCALATED", "DISMISSED"]
UserRole = Literal["ADMIN", "OPERATIONS", "ANALYST", "VIEWER"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Workspace(BaseModel):
    workspace_id: str
    name: str
    environment: Literal["DEMO", "PUBLISHED", "OFFLINE"] = "DEMO"


class User(BaseModel):
    user_id: str
    display_name: str
    email: str = ""
    role: UserRole = "VIEWER"
    workspace_id: str = "demo"


class Alert(BaseModel):
    alert_id: str
    title: str
    summary: str
    alert_type: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "NORMAL"] = "LOW"
    status: AlertStatus = "OPEN"
    owner: Optional[str] = None
    run_id: str = ""
    subject_id: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class Case(BaseModel):
    case_id: str
    title: str
    summary: str
    status: CaseStatus = "OPEN"
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "NORMAL"] = "LOW"
    owner: Optional[str] = None
    workspace_id: str = "demo"
    related_ids: list[str] = Field(default_factory=list)
    notes: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class OperatorDecision(BaseModel):
    decision_id: str
    subject_kind: Literal["PO", "DISPUTE", "RING"]
    subject_id: str
    action: DecisionAction
    actor_id: str
    workspace_id: str = "demo"
    created_at: datetime = Field(default_factory=utc_now)
    dossier_id: str = ""


class EvidenceRecord(BaseModel):
    evidence_id: str
    subject_id: str
    evidence_type: str
    summary: str
    verified: bool = False
    case_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    dossier: dict = Field(default_factory=dict)


class RunSummary(BaseModel):
    run_id: str
    route: str
    preset: str
    rejected_count: int = 0
    alert_count: int = 0
    decision_count: int = 0
    ring_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
