"""Merchant / payroll / exchange false-positive suppressor.

An account is legitimate if it matches ANY one of three behavioural heuristics.
Runs before an account is reported as a smurfing hub or shell, and applies a
penalty in the scorer.
"""

import math


def is_merchant_or_payroll(account_id, node_stats):
    st = node_stats.get(account_id)
    if not st:
        return {"is_legitimate": False, "reason": None}
    if _payroll(st):
        return {"is_legitimate": True, "reason": "payroll_pattern"}
    if _merchant(st):
        return {"is_legitimate": True, "reason": "merchant_pattern"}
    if _exchange(st):
        return {"is_legitimate": True, "reason": "exchange_pattern"}
    return {"is_legitimate": False, "reason": None}


def _cov(amounts):
    if not amounts:
        return 0.0
    m = sum(amounts) / len(amounts)
    if m == 0:
        return 0.0
    var = sum((a - m) ** 2 for a in amounts) / len(amounts)
    return math.sqrt(var) / m


def _payroll(st):
    # Near-identical amounts sent to many receivers at a consistent hour-of-day.
    if st["out_degree"] < 10:
        return False
    hours = list(st["tx_by_hour"].values())
    if not hours or st["transaction_count"] == 0:
        return False
    concentration = max(hours) / st["transaction_count"]
    return _cov(st["amounts_sent"]) < 0.05 and concentration > 0.3


def _merchant(st):
    # Long-lived account, many diverse senders, high amount variation.
    if st["in_degree"] < 10:
        return False
    age_days = st["active_duration_hours"] / 24
    if age_days < 30:
        return False
    diversity = len(st["unique_senders"]) / max(st["transaction_count"], 1)
    return _cov(st["amounts_received"]) > 0.3 and diversity > 0.7


def _exchange(st):
    # Very old, very high-volume account with a large counterparty pool.
    age_days = st["active_duration_hours"] / 24
    txns_per_day = st["transaction_count"] / max(age_days, 1)
    return (age_days > 60 and txns_per_day > 20
            and len(st["unique_senders"]) > 50 and len(st["unique_receivers"]) > 50)
