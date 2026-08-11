"""Phase-3 tests for the Ring-Auditor agent.

A fast circular-billing ring must be detected, signed into a verifiable dossier,
and routed to the human-review queue by risk. Deterministic, offline.
"""

from datetime import datetime, timedelta

from src.core import audit
from src.agents.ring_auditor import ring_auditor
from src.agents.orchestrator import run_supervised
from src.utils.retail_simulator import RetailSimulator

BASE = datetime(2024, 1, 1, 9, 0, 0)


def _cycle_txns():
    # A -> B -> C -> A, rapid (velocity signal) => a high-risk cycle ring.
    return [
        {"tx_id": "R1", "sender": "A", "receiver": "B", "amount": 5000, "timestamp": BASE},
        {"tx_id": "R2", "sender": "B", "receiver": "C", "amount": 5000, "timestamp": BASE + timedelta(minutes=10)},
        {"tx_id": "R3", "sender": "C", "receiver": "A", "amount": 5000, "timestamp": BASE + timedelta(minutes=20)},
    ]


def test_ring_auditor_flags_and_signs_ring():
    state = ring_auditor({"mule_transactions": _cycle_txns()})
    assert state["mule_rings"], "expected at least one fraud ring"
    ring = state["mule_rings"][0]
    assert ring["pattern_type"] == "cycle"
    assert "confidence" in ring
    # The ring dossier is HMAC-signed and verifies.
    dossiers = [d for d in state["dossiers"] if d["dossier_id"] == "DOS_RING_" + ring["ring_id"]]
    assert len(dossiers) == 1
    assert audit.verify_dossier_dict(dossiers[0]) is True
    assert dossiers[0]["payload"] == ring


def test_high_risk_ring_routed_to_review():
    state = ring_auditor({"mule_transactions": _cycle_txns()})
    review_ids = {q["ring_id"] for q in state["ring_hitl"]["review"]}
    assert review_ids, "high-risk ring should land in the human-review queue"
    for q in state["ring_hitl"]["review"]:
        assert q["risk_score"] >= 60.0


def test_ring_auditor_no_transactions_is_safe():
    state = ring_auditor({})
    assert state["mule_rings"] == []


def test_run_supervised_audit_route_invokes_ring_auditor():
    # Audit route must run the Ring-Auditor; with the mule graph supplied it flags a ring.
    invoices = [RetailSimulator.supplier_invoice(sku="SKU_MILK", amount=120.0)]
    state = run_supervised({"invoices_raw": invoices, "mule_transactions": _cycle_txns()})
    assert state["route"] == "audit_only"
    assert "mule_rings" in state and state["mule_rings"]
    assert "ring_hitl" in state
