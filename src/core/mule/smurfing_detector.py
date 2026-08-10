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
    """Best (count, members, start, end) unique counterparties in any window."""
    if not edges:
        return 0, set(), None, None
    es = sorted(edges, key=lambda e: e["timestamp"])
    w = timedelta(hours=window_h)
    best = (0, set(), None, None)
    for i in range(len(es)):
        t0 = es[i]["timestamp"]
        members = set()
        for j in range(i, len(es)):
            if es[j]["timestamp"] - t0 <= w:
                members.add(es[j][key])
            else:
                break
        if len(members) > best[0]:
            best = (len(members), set(members), t0, t0 + w)
    return best


def detect_smurfing(g, threshold=FAN_THRESHOLD):
    results = []
    for acc in g.nodes:
        if is_merchant_or_payroll(acc, g.stats)["is_legitimate"]:
            continue
        st = g.stats[acc]
        fin = _max_window_unique(g.in_edges.get(acc, []), "from")
        fout = _max_window_unique(g.out_edges.get(acc, []), "to")
        is_in, is_out = fin[0] >= threshold, fout[0] >= threshold
        if not (is_in or is_out):
            continue
        if is_in and is_out:
            subtype, conn, win = "scatter_gather", sorted(fin[1] | fout[1]), fin
            count, amt = fin[0] + fout[0], st["total_in_amount"] + st["total_out_amount"]
        elif is_in:
            subtype, conn, win = "fan_in", sorted(fin[1]), fin
            count, amt = fin[0], st["total_in_amount"]
        else:
            subtype, conn, win = "fan_out", sorted(fout[1]), fout
            count, amt = fout[0], st["total_out_amount"]
        results.append({"hub_account": acc, "pattern_subtype": subtype,
                        "connected_accounts": conn, "transaction_count_72h": count,
                        "total_amount_72h": round(amt, 2),
                        "time_window_start": win[2], "time_window_end": win[3]})
    return results
