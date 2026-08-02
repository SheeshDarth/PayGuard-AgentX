"""
Tests for the scale-up Week-1 foundation: extended schemas, Ollama-first LLM
(offline fallback), SQLite relational store, Kuzu graph fallback, Chroma memory
fallback, and audit coverage of new artifact types. All run offline.
"""

import pytest

from src.models.schemas import (
    AgentDecision, NegotiationTurn, NegotiationTranscript, TraceEvent,
)
from src.core import llm, audit, relational
from src.core.graph_store import GraphStore
from src.core.memory import Memory


# --- extended schemas ---
def test_agent_decision_confidence_bounds():
    d = AgentDecision(agent="Ops-Planner", subject_id="PO_1", summary="restock milk", confidence=0.9)
    assert d.requires_human_approval is True
    with pytest.raises(Exception):
        AgentDecision(agent="a", subject_id="s", summary="x", confidence=1.5)


def test_negotiation_transcript_model():
    t = NegotiationTranscript(
        topic="restock",
        turns=[NegotiationTurn(agent="Demand-Forecaster", round=1, position="low", rationale="soft demand")],
        rounds=1, resolution="stock-watcher wins")
    assert t.turns[0].round == 1


def test_trace_event_model():
    e = TraceEvent(run_id="R1", step=1, agent="DQ-Sentinel", action="decision",
                   detail="clean", timestamp="2026-08-02T00:00:00Z")
    assert e.action == "decision"


# --- Ollama-first LLM, offline ---
def test_llm_offline_not_live_and_stub():
    assert llm.is_live() is False
    out = llm.complete("hello world example prompt")
    assert out.startswith("[offline-stub]")


# --- relational (SQLite stdlib) ---
def test_relational_query_and_readonly_guard():
    conn = relational.connect()
    relational.seed_demo(conn)
    rows = relational.sql_query(conn, "SELECT supplier_id, lead_time_days FROM suppliers ORDER BY supplier_id")
    assert rows[0]["supplier_id"] == "SUP_A"
    assert rows[0]["lead_time_days"] == 3
    with pytest.raises(ValueError):
        relational.sql_query(conn, "DELETE FROM suppliers")


# --- graph store (memory fallback) ---
def test_graph_store_fraud_ring_detection():
    g = GraphStore()
    assert g.backend == "memory"
    g.add_supplies("SUP_A", "SKU_MILK")
    g.add_dispute("SUP_A", "DIS_1", "IV_1")
    g.add_dispute("SUP_A", "DIS_2", "IV_2")
    g.add_dispute("SUP_B", "DIS_3", "IV_3")
    assert g.suppliers_with_multiple_disputes(2) == ["SUP_A"]
    assert g.skus_for_supplier("SUP_A") == ["SKU_MILK"]


# --- memory (keyword fallback) ---
def test_memory_case_recall():
    m = Memory()
    assert m.backend == "fallback"
    m.add_case("c1", "supplier SUP_A duplicate invoice milk", {"supplier": "SUP_A"})
    m.add_case("c2", "clean invoice rice", {})
    hits = m.recall_cases("SUP_A duplicate", k=1)
    assert hits and hits[0]["id"] == "c1"


def test_memory_regulatory_retrieval():
    m = Memory()
    m.add_reg("r1", "Invoices must match the purchase order amount within tolerance", {})
    m.add_reg("r2", "Suppliers must be onboarded with valid tax identifiers", {})
    hits = m.retrieve_reg("purchase order amount mismatch", k=1)
    assert hits and hits[0]["id"] == "r1"


# --- audit covers new artifact types ---
def test_audit_signs_negotiation_transcript_and_detects_tamper():
    transcript = {"topic": "restock", "rounds": 2, "resolution": "stock-watcher wins"}
    d = audit.build_dossier("DOS_NEG_1", "NEG_1", "Negotiation transcript", transcript)
    dd = d.model_dump()
    assert audit.verify_dossier_dict(dd) is True
    dd["payload"]["resolution"] = "forecast wins"
    assert audit.verify_dossier_dict(dd) is False
