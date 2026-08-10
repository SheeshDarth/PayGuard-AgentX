"""Directed weighted transaction-graph model for money-muling detection.

build_graph(transactions) -> Graph with adjacency lists + per-account stats.
A transaction is a dict: {tx_id, sender, receiver, amount, timestamp}.
timestamp may be a datetime, an ISO-8601 string, or epoch seconds.
"""

from datetime import datetime, timezone


def _parse_ts(v):
    if isinstance(v, datetime):
        return v
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v, tz=timezone.utc)
    s = str(v).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


class Graph:
    def __init__(self):
        self.nodes = set()
        self.out_edges = {}   # account -> [edge]
        self.in_edges = {}    # account -> [edge]
        self.stats = {}       # account -> stats dict

    def neighbors(self, account):
        return [e["to"] for e in self.out_edges.get(account, [])]


def _blank_stats(acc):
    return {"account_id": acc, "unique_senders": set(), "unique_receivers": set(),
            "amounts_sent": [], "amounts_received": [], "transaction_count": 0,
            "total_out_amount": 0.0, "total_in_amount": 0.0,
            "first_seen": None, "last_seen": None, "tx_by_hour": {},
            "_recv_ts": [], "_send_ts": []}


def build_graph(transactions):
    g = Graph()
    for t in transactions:
        s, r = t["sender"], t["receiver"]
        if s == r:
            continue
        amt = float(t["amount"])
        ts = _parse_ts(t["timestamp"])
        g.nodes.add(s); g.nodes.add(r)
        edge = {"from": s, "to": r, "amount": amt, "timestamp": ts, "tx_id": t.get("tx_id")}
        g.out_edges.setdefault(s, []).append(edge)
        g.in_edges.setdefault(r, []).append(edge)
        for acc in (s, r):
            st = g.stats.get(acc) or _blank_stats(acc)
            g.stats[acc] = st
            st["transaction_count"] += 1
            if st["first_seen"] is None or ts < st["first_seen"]:
                st["first_seen"] = ts
            if st["last_seen"] is None or ts > st["last_seen"]:
                st["last_seen"] = ts
            st["tx_by_hour"][ts.hour] = st["tx_by_hour"].get(ts.hour, 0) + 1
        ss, rr = g.stats[s], g.stats[r]
        ss["unique_receivers"].add(r); ss["amounts_sent"].append(amt)
        ss["total_out_amount"] += amt; ss["_send_ts"].append(ts)
        rr["unique_senders"].add(s); rr["amounts_received"].append(amt)
        rr["total_in_amount"] += amt; rr["_recv_ts"].append(ts)
    for st in g.stats.values():
        st["out_degree"] = len(st["unique_receivers"])
        st["in_degree"] = len(st["unique_senders"])
        if st["first_seen"] and st["last_seen"]:
            st["active_duration_hours"] = (st["last_seen"] - st["first_seen"]).total_seconds() / 3600.0
        else:
            st["active_duration_hours"] = 0.0
        st["avg_retransmit_minutes"] = _avg_retransmit(st)
    return g


def _avg_retransmit(st):
    """Average minutes between receiving funds and the next outgoing send (velocity)."""
    recv, send = sorted(st["_recv_ts"]), sorted(st["_send_ts"])
    if not recv or not send:
        return float("inf")
    diffs = []
    for rt in recv:
        nxt = next((s for s in send if s >= rt), None)
        if nxt is not None:
            diffs.append((nxt - rt).total_seconds() / 60.0)
    return sum(diffs) / len(diffs) if diffs else float("inf")
