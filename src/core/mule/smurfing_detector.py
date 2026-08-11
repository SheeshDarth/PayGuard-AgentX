"""Temporal fan-in / fan-out / scatter-gather (smurfing) detection.

Flags a hub account with >= threshold unique counterparties inside any 72h window.
Maps onto procurement invoice-structuring (many small POs to slip under approval
limits). Merchant/payroll accounts are pre-filtered out.
"""

from datetime import timedelta

from src.core.mule.suppressor import is_merchant_or_payroll

WINDOW_H = 72
FAN_THRESHOLD = 10


def _max_window_unique(edges, key, window_h=WINDOW_H):
    """Best window by unique counterparties. Returns
    (unique_count, members, start, end, txn_count, amount) for that window --
    txn_count and amount are measured over the window, not the account lifetime."""
    if not edges:
        return 0, set(), None, None, 0, 0.0
    es = sorted(edges, key=lambda e: e["timestamp"])
    w = timedelta(hours=window_h)
    best = (0, set(), None, None, 0, 0.0)
    for i in range(len(es)):
        t0 = es[i]["timestamp"]
        members, txn_count, amount = set(), 0, 0.0
        for j in range(i, len(es)):
            if es[j]["timestamp"] - t0 <= w:
                members.add(es[j][key]); txn_count += 1; amount += es[j]["amount"]
            else:
                break
        if len(members) > best[0]:
            best = (len(members), set(members), t0, t0 + w, txn_count, amount)
    return best


def detect_smurfing(g, threshold=FAN_THRESHOLD):
    results = []
    for acc in g.nodes:
        if is_merchant_or_payroll(acc, g.stats)["is_legitimate"]:
            continue
        fin = _max_window_unique(g.in_edges.get(acc, []), "from")
        fout = _max_window_unique(g.out_edges.get(acc, []), "to")
        is_in, is_out = fin[0] >= threshold, fout[0] >= threshold
        if not (is_in or is_out):
            continue
        if is_in and is_out:
            subtype, conn, win = "scatter_gather", sorted(fin[1] | fout[1]), fin
            count, amt = fin[4] + fout[4], round(fin[5] + fout[5], 2)
        elif is_in:
            subtype, conn, win = "fan_in", sorted(fin[1]), fin
            count, amt = fin[4], round(fin[5], 2)
        else:
            subtype, conn, win = "fan_out", sorted(fout[1]), fout
            count, amt = fout[4], round(fout[5], 2)
        results.append({"hub_account": acc, "pattern_subtype": subtype,
                        "connected_accounts": conn, "transaction_count_72h": count,
                        "total_amount_72h": round(amt, 2),
                        "time_window_start": win[2], "time_window_end": win[3]})
    return results
