"""
Structured trace logging for PayGuard-AgentX observability.

Records every agent turn (agent, action, detail, confidence) to a SQLite trace
table so the dashboard can show a timeline and answer "why did the agent decide
that?" in a viva. Stdlib sqlite3 -- no external dependency.
"""

import sqlite3
import time


class Tracer:
    def __init__(self, conn=None):
        self.conn = conn or sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS trace "
            "(run_id TEXT, step INTEGER, agent TEXT, action TEXT, detail TEXT, confidence REAL, ts REAL)")
        self.conn.commit()
        self._step = {}

    def log(self, run_id, agent, action, detail, confidence=None):
        step = self._step.get(run_id, 0) + 1
        self._step[run_id] = step
        self.conn.execute("INSERT INTO trace VALUES (?,?,?,?,?,?,?)",
                          (run_id, step, agent, action, detail, confidence, time.time()))
        self.conn.commit()
        return step

    def events(self, run_id):
        cur = self.conn.execute(
            "SELECT run_id, step, agent, action, detail, confidence FROM trace "
            "WHERE run_id=? ORDER BY step", (run_id,))
        cols = ["run_id", "step", "agent", "action", "detail", "confidence"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
