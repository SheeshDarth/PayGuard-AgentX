"""Bounded cycle detection: Tarjan SCC prune + DFS for cycles of length 3-5.

Catches circular billing rings (A -> B -> C -> A). SCC pre-filtering keeps this
near O(V+E) on sparse graphs; an 8s wall-clock budget prevents browser/UI hangs on
adversarial inputs.
"""

import sys
import time


def _tarjan_scc(g):
    index, low, on_stack, stack, sccs = {}, {}, {}, [], []
    counter = [0]
    sys.setrecursionlimit(10000)

    def strong(v):
        index[v] = low[v] = counter[0]; counter[0] += 1
        stack.append(v); on_stack[v] = True
        for w in g.neighbors(v):
            if w not in index:
                strong(w); low[v] = min(low[v], low[w])
            elif on_stack.get(w):
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop(); on_stack[w] = False; comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for v in list(g.nodes):
        if v not in index:
            strong(v)
    return sccs


def detect_cycles(g, min_len=3, max_len=5, time_budget_s=8.0):
    """Enumerate simple cycles of length min_len..max_len.

    Convenience wrapper that discards the truncation flag. Callers that record or
    sign the result should use detect_cycles_status() instead, so an incomplete
    search is never presented as an exhaustive one.
    """
    results, _truncated = detect_cycles_status(g, min_len, max_len, time_budget_s)
    return results


def detect_cycles_status(g, min_len=3, max_len=5, time_budget_s=8.0):
    """Same search as detect_cycles, returning (results, truncated).

    truncated is True when the wall-clock budget stopped enumeration early, which
    means the cycle list is a subset -- not proof that no further cycles exist.
    """
    t0 = time.time()
    sccs = [set(c) for c in _tarjan_scc(g) if len(c) >= 3]
    seen, results = set(), []
    for scc in sccs:
        for root in list(scc):
            if time.time() - t0 > time_budget_s:
                return results, True
            _dfs(g, root, root, [root], {root}, 1, min_len, max_len, scc,
                 seen, results, t0, time_budget_s)
    # _dfs also bails out on the budget without signalling, so re-check the clock:
    # an over-budget elapsed time means at least one branch was cut short.
    return results, (time.time() - t0) > time_budget_s


def _dfs(g, start, cur, path, visited, depth, min_len, max_len, scc,
         seen, results, t0, budget):
    if depth > max_len or time.time() - t0 > budget:
        return
    for nb in g.neighbors(cur):
        if nb == start and depth >= min_len:
            _record(g, path, seen, results)
        elif nb in scc and nb not in visited and depth < max_len:
            visited.add(nb)
            _dfs(g, start, nb, path + [nb], visited, depth + 1, min_len, max_len,
                 scc, seen, results, t0, budget)
            visited.discard(nb)


def _record(g, path, seen, results):
    mi = path.index(min(path))                 # normalise: rotate to smallest node
    members = path[mi:] + path[:mi]
    key = tuple(members)
    if key in seen:
        return
    seen.add(key)
    total, times = 0.0, []
    for i in range(len(members)):
        e = _min_edge(g, members[i], members[(i + 1) % len(members)])
        if e is None:
            return
        total += e["amount"]; times.append(e["timestamp"])
    span = (max(times) - min(times)).total_seconds() / 3600.0 if times else 0.0
    results.append({"cycle_members": members, "cycle_length": len(members),
                    "pattern_label": "cycle_length_" + str(len(members)),
                    "total_amount_circulated": round(total, 2),
                    "time_span_hours": round(span, 2)})


def _min_edge(g, a, b):
    cands = [e for e in g.out_edges.get(a, []) if e["to"] == b]
    return min(cands, key=lambda e: e["amount"]) if cands else None
