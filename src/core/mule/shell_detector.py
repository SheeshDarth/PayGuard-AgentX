"""Shell pass-through chain detection.

A shell is a low-activity account with pure 1-in / 1-out topology that forwards
almost all of what it receives. Chains source -> shell(s) -> destination model
shell suppliers used to launder procurement payments. Reverse/forward BFS grows a
chain from each candidate to its non-shell endpoints.
"""

from src.core.mule.suppressor import is_merchant_or_payroll


def _is_candidate(acc, g):
    st = g.stats.get(acc)
    if not st or st["transaction_count"] > 4:
        return False
    if st["in_degree"] != 1 or st["out_degree"] != 1:
        return False
    if st["active_duration_hours"] > 168:
        return False
    if is_merchant_or_payroll(acc, g.stats)["is_legitimate"]:
        return False
    if st["total_in_amount"] <= 0:
        return False
    return st["total_out_amount"] / st["total_in_amount"] > 0.85


def _sole_sender(g, acc):
    senders = {e["from"] for e in g.in_edges.get(acc, [])}
    return next(iter(senders)) if len(senders) == 1 else None


def _sole_receiver(g, acc):
    receivers = {e["to"] for e in g.out_edges.get(acc, [])}
    return next(iter(receivers)) if len(receivers) == 1 else None


def _edge(g, a, b):
    return next((e for e in g.out_edges.get(a, []) if e["to"] == b), None)


def detect_shell_networks(g):
    candidates = {a for a in g.nodes if _is_candidate(a, g)}
    used, chains = set(), []
    for start in candidates:
        if start in used:
            continue
        chain, cur = [start], start
        while True:                                    # walk backwards through shells
            prev = _sole_sender(g, cur)
            if prev in candidates and prev not in chain:
                chain.insert(0, prev); cur = prev
            else:
                source = prev
                break
        cur = start
        while True:                                    # walk forwards through shells
            nxt = _sole_receiver(g, cur)
            if nxt in candidates and nxt not in chain:
                chain.append(nxt); cur = nxt
            else:
                dest = nxt
                break
        if source is None or dest is None or source in candidates or dest in candidates:
            continue
        members = [source] + chain + [dest]
        if len(members) < 3:
            continue
        used.update(chain)
        total, ratios = 0.0, []
        for i in range(len(members) - 1):
            e = _edge(g, members[i], members[i + 1])
            if e:
                total += e["amount"]
        for sh in chain:
            st = g.stats[sh]
            if st["total_in_amount"] > 0:
                ratios.append(st["total_out_amount"] / st["total_in_amount"])
        chains.append({"chain_members": members, "shell_accounts": list(chain),
                       "chain_length": len(members) - 1,
                       "total_amount_transacted": round(total, 2),
                       "avg_amount_retention": round(sum(ratios) / len(ratios), 3) if ratios else 0.0})
    return chains
