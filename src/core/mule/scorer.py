"""Multi-signal weighted suspicion scorer + Union-Find ring grouping.

Combines the cycle / smurfing / shell signals with velocity, structuring and
network-isolation into a 0-100 score, applies a merchant/payroll penalty, requires
a multi-signal minimum to flag (single strong cycle excepted), and groups flagged
accounts into rings. Returns (scored_accounts, rings).
"""

from src.core.mule.suppressor import is_merchant_or_payroll

_CATS = ["cycle", "smurf", "shell", "velocity", "structuring", "isolation"]


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def _raw(s):
    return sum(s[c] for c in _CATS) + s["fp"]


def compute_scores(cycles, smurfing, shells, g):
    sig = {a: {c: 0 for c in _CATS} for a in g.nodes}
    for a in sig:
        sig[a]["fp"] = 0
    pats = {a: set() for a in g.nodes}

    for c in cycles:
        for a in c["cycle_members"]:
            sig[a]["cycle"] = min(sig[a]["cycle"] + 25, 50)
            pats[a].add(c["pattern_label"])
        if c["time_span_hours"] < 24:
            for a in c["cycle_members"]:
                sig[a]["cycle"] += 10

    for sr in smurfing:
        h, sub = sr["hub_account"], sr["pattern_subtype"]
        # Additive (an account is a hub in at most one result) so a participant
        # bonus already accrued for this account is not clobbered.
        sig[h]["smurf"] += 30 if sub == "scatter_gather" else 15
        pats[h].add(sub)
        for a in sr["connected_accounts"]:
            if a in sig:
                sig[a]["smurf"] += 8; pats[a].add("smurfing_participant")

    for sn in shells:
        for a in sn["shell_accounts"]:
            sig[a]["shell"] = 20; pats[a].add("shell_account")
        for a in (sn["chain_members"][0], sn["chain_members"][-1]):
            sig[a]["shell"] += 10; pats[a].add("shell_network_endpoint")

    for a in g.nodes:
        st = g.stats[a]
        v = st["avg_retransmit_minutes"]
        if v < 60:
            sig[a]["velocity"] += 10; pats[a].add("high_velocity")
        if v < 15:
            sig[a]["velocity"] += 10
        sent = st["amounts_sent"]
        if any(9000 <= x <= 9999 or 4500 <= x <= 4999 or 2250 <= x <= 2499 for x in sent):
            sig[a]["structuring"] = 10; pats[a].add("structuring_detected")
        if any(sent.count(x) >= 3 for x in set(sent)):
            sig[a]["structuring"] += 5; pats[a].add("identical_amounts")

    raw0 = {a: _raw(sig[a]) for a in g.nodes}
    for a in g.nodes:
        if raw0[a] <= 0:
            continue
        neigh = g.stats[a]["unique_senders"] | g.stats[a]["unique_receivers"]
        if not neigh:
            continue
        ratio = sum(1 for n in neigh if raw0.get(n, 0) > 0) / len(neigh)
        if ratio > 0.95:
            sig[a]["isolation"] = 15
        elif ratio > 0.8:
            sig[a]["isolation"] = 8

    for a in g.nodes:
        if is_merchant_or_payroll(a, g.stats)["is_legitimate"]:
            sig[a]["fp"] = -20

    uf = _UF()
    for c in cycles:
        for x in c["cycle_members"]:
            uf.union(c["cycle_members"][0], x)
    for sr in smurfing:
        grp = [sr["hub_account"]] + sr["connected_accounts"]
        for x in grp:
            uf.union(grp[0], x)
    for sn in shells:
        for x in sn["chain_members"]:
            uf.union(sn["chain_members"][0], x)

    scores = {a: round(min(100, max(0, _raw(sig[a]))), 1) for a in g.nodes}
    accounts = []
    for a in g.nodes:
        s = sig[a]
        active = [c for c in _CATS if s[c] > 0]
        if scores[a] <= 0:
            continue
        if len(active) < 2 and s["cycle"] < 40:
            continue
        accounts.append({"account_id": a, "suspicion_score": scores[a],
                         "detected_patterns": sorted(pats[a]), "ring_id": None,
                         "signal_breakdown": dict(s)})

    flagged = {x["account_id"] for x in accounts}
    groups = {}
    for a in flagged:
        groups.setdefault(uf.find(a), []).append(a)
    ranked = sorted(groups.values(), key=lambda mem: max(scores[m] for m in mem), reverse=True)
    ring_of, rings = {}, []
    for i, mem in enumerate(ranked, 1):
        rid = "RING_%03d" % i
        for m in mem:
            ring_of[m] = rid
        rings.append({"ring_id": rid, "member_accounts": sorted(mem),
                      "pattern_type": _ring_type(mem, cycles, smurfing, shells),
                      "risk_score": round(max(scores[m] for m in mem), 1)})
    for x in accounts:
        x["ring_id"] = ring_of.get(x["account_id"], "NONE")
    accounts.sort(key=lambda x: x["suspicion_score"], reverse=True)
    return accounts, rings


def _ring_type(mem, cycles, smurfing, shells):
    ms, types = set(mem), set()
    if any(ms & set(c["cycle_members"]) for c in cycles):
        types.add("cycle")
    if any(ms & ({s["hub_account"]} | set(s["connected_accounts"])) for s in smurfing):
        types.add("smurfing")
    if any(ms & set(s["chain_members"]) for s in shells):
        types.add("shell_network")
    if len(types) == 1:
        return types.pop()
    return "mixed"   # multiple types, or (defensively) none -> never mislabel as a specific type
