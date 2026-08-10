"""Phase-1 tests for the money-muling detectors (src/core/mule).

A single synthetic transaction set seeds exactly one of each fraud pattern plus a
payroll "trap" that must NOT be flagged. All deterministic, no heavy deps.
"""

from datetime import datetime, timedelta

from src.core.mule.graph_model import build_graph
from src.core.mule.cycle_detector import detect_cycles
from src.core.mule.smurfing_detector import detect_smurfing
from src.core.mule.shell_detector import detect_shell_networks
from src.core.mule.suppressor import is_merchant_or_payroll
from src.core.mule.scorer import compute_scores

BASE = datetime(2024, 1, 1, 9, 0, 0)


def _tx(tid, s, r, amt, minutes):
    return {"tx_id": tid, "sender": s, "receiver": r, "amount": amt,
            "timestamp": BASE + timedelta(minutes=minutes)}


def _dataset():
    txns = []
    # 1) Cycle A -> B -> C -> A (fast: rapid re-transmit)
    txns += [_tx("CY1", "A", "B", 5000, 0),
             _tx("CY2", "B", "C", 5000, 10),
             _tx("CY3", "C", "A", 5000, 20)]
    # 2) Smurfing fan-in: 12 unique senders -> HUB inside a 72h window
    for i in range(12):
        txns.append(_tx("SM%d" % i, "S%d" % i, "HUB", 1000 + i * 100, i))
    # 3) Shell chain SRC -> SH1 -> SH2 -> DST (pass-through, ~95% retention)
    txns += [_tx("SL1", "SRC", "SH1", 1000, 0),
             _tx("SL2", "SH1", "SH2", 950, 30),
             _tx("SL3", "SH2", "DST", 900, 50)]
    # 4) Payroll trap: identical 3000 to 12 receivers at the same hour (must NOT flag)
    for i in range(12):
        txns.append(_tx("PR%d" % i, "PAY", "P%d" % i, 3000, i))
    return txns


def test_build_graph_basic_stats():
    g = build_graph(_dataset())
    assert "HUB" in g.nodes and "A" in g.nodes
    assert g.stats["HUB"]["in_degree"] == 12
    assert g.stats["PAY"]["out_degree"] == 12


def test_cycle_detected():
    g = build_graph(_dataset())
    cycles = detect_cycles(g)
    assert len(cycles) == 1
    assert set(cycles[0]["cycle_members"]) == {"A", "B", "C"}
    assert cycles[0]["cycle_length"] == 3
    assert cycles[0]["pattern_label"] == "cycle_length_3"


def test_smurfing_fan_in_detected_and_payroll_suppressed():
    g = build_graph(_dataset())
    smurf = detect_smurfing(g)
    hubs = {r["hub_account"]: r for r in smurf}
    assert "HUB" in hubs
    assert hubs["HUB"]["pattern_subtype"] == "fan_in"
    assert len(hubs["HUB"]["connected_accounts"]) >= 10
    # The payroll account is a 12-way fan-out but must be suppressed, not returned.
    assert "PAY" not in hubs


def test_shell_chain_detected():
    g = build_graph(_dataset())
    shells = detect_shell_networks(g)
    assert len(shells) == 1
    assert shells[0]["chain_members"] == ["SRC", "SH1", "SH2", "DST"]
    assert set(shells[0]["shell_accounts"]) == {"SH1", "SH2"}
    assert shells[0]["avg_amount_retention"] > 0.85


def test_payroll_is_recognised_as_legitimate():
    g = build_graph(_dataset())
    verdict = is_merchant_or_payroll("PAY", g.stats)
    assert verdict["is_legitimate"] is True
    assert verdict["reason"] == "payroll_pattern"


def test_scorer_flags_rings_and_spares_payroll():
    g = build_graph(_dataset())
    cycles = detect_cycles(g)
    smurf = detect_smurfing(g)
    shells = detect_shell_networks(g)
    accounts, rings = compute_scores(cycles, smurf, shells, g)
    flagged = {a["account_id"] for a in accounts}
    # Cycle and shell accomplices are flagged; payroll is not.
    assert flagged, "expected at least one flagged account"
    assert "PAY" not in flagged
    assert len(rings) >= 1
    for a in accounts:
        assert 0.0 <= a["suspicion_score"] <= 100.0
        assert a["ring_id"] != "" and a["ring_id"] is not None
    # Every ring has a valid pattern type and a member list.
    for r in rings:
        assert r["pattern_type"] in {"cycle", "smurfing", "shell_network", "mixed"}
        assert r["member_accounts"]
