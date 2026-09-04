"""Storage boundary for the operator dashboard.

SQLite is the default local/offline implementation. PostgreSQL is selected by
PAYGUARD_DATABASE_URL when psycopg is installed; both implementations expose
the same JSON-oriented repository methods to UI pages.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dashboard.services.config import load_settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (decision_id TEXT PRIMARY KEY, subject_kind TEXT NOT NULL,
  subject_id TEXT NOT NULL, action TEXT NOT NULL, actor_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
  payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cases (case_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alerts (alert_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (evidence_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events (event_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
"""

TABLES = ("runs", "decisions", "cases", "alerts", "evidence", "audit_events")


def _now():
    return datetime.now(timezone.utc).isoformat()


class SQLiteStorage:
    backend = "sqlite"

    def __init__(self, path=None):
        self.path = path or os.getenv("PAYGUARD_SQLITE_PATH", ".payguard/workspace.sqlite")
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def _save(self, table, key, payload):
        data = json.dumps(payload, default=str, sort_keys=True)
        self.conn.execute(f"INSERT OR REPLACE INTO {table} VALUES (?,?,?)", (key, data, _now()))
        self.conn.commit()

    def _list(self, table):
        rows = self.conn.execute(f"SELECT payload FROM {table} ORDER BY created_at DESC").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def save_run(self, run_id, payload): self._save("runs", run_id, payload)
    def save_decision(self, decision):
        data = json.dumps(decision, default=str, sort_keys=True)
        self.conn.execute("INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?,?,?)",
                          (decision["decision_id"], decision["subject_kind"], decision["subject_id"],
                           decision["action"], decision["actor_id"], decision.get("workspace_id", "demo"),
                           data, _now()))
        self.conn.commit()
    def save_case(self, case): self._save("cases", case["case_id"], case)
    def save_alert(self, alert): self._save("alerts", alert["alert_id"], alert)
    def save_evidence(self, evidence): self._save("evidence", evidence["evidence_id"], evidence)
    def save_audit_event(self, event): self._save("audit_events", event["event_id"], event)
    def list_runs(self): return self._list("runs")
    def list_decisions(self):
        rows = self.conn.execute("SELECT payload FROM decisions ORDER BY created_at DESC").fetchall()
        return [json.loads(row["payload"]) for row in rows]
    def list_cases(self): return self._list("cases")
    def list_alerts(self): return self._list("alerts")
    def list_evidence(self): return self._list("evidence")
    def list_audit_events(self): return self._list("audit_events")

    def reset(self):
        """Clear the demo workspace. Operator decisions are keyed by subject, so a
        re-run of the same scenario reuses subject ids and would otherwise look
        already-decided; resetting gives a repeatable demo from a clean queue."""
        for table in TABLES:
            self.conn.execute(f"DELETE FROM {table}")
        self.conn.commit()


def get_storage():
    """Return the configured storage backend; safely fall back to SQLite."""
    settings = load_settings()
    url = settings.database_url
    if url.startswith(("postgres://", "postgresql://")):
        try:
            return PostgresStorage(url)
        except Exception:
            pass
    return SQLiteStorage(settings.sqlite_path)


class PostgresStorage:
    """Small PostgreSQL adapter using psycopg; mirrors SQLiteStorage methods."""
    backend = "postgresql"

    def __init__(self, url):
        import psycopg
        self.conn = psycopg.connect(url)
        with self.conn.cursor() as cur:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    cur.execute(stmt)
        self.conn.commit()

    def _save(self, table, key, payload):
        data = json.dumps(payload, default=str, sort_keys=True)
        with self.conn.cursor() as cur:
            cur.execute(f"INSERT INTO {table} VALUES (%s,%s,%s) "
                        "ON CONFLICT DO UPDATE SET payload=EXCLUDED.payload, created_at=EXCLUDED.created_at",
                        (key, data, _now()))
        self.conn.commit()

    def _list(self, table):
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT payload FROM {table} ORDER BY created_at DESC")
            return [json.loads(row[0]) for row in cur.fetchall()]

    def save_run(self, run_id, payload): self._save("runs", run_id, payload)
    def save_case(self, case): self._save("cases", case["case_id"], case)
    def save_alert(self, alert): self._save("alerts", alert["alert_id"], alert)
    def save_evidence(self, evidence): self._save("evidence", evidence["evidence_id"], evidence)
    def save_audit_event(self, event): self._save("audit_events", event["event_id"], event)
    def save_decision(self, decision):
        data = json.dumps(decision, default=str, sort_keys=True)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO decisions VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (decision_id) DO UPDATE SET payload=EXCLUDED.payload",
                (decision["decision_id"], decision["subject_kind"], decision["subject_id"],
                 decision["action"], decision["actor_id"], decision.get("workspace_id", "demo"), data, _now()))
        self.conn.commit()
    def list_runs(self): return self._list("runs")
    def list_cases(self): return self._list("cases")
    def list_alerts(self): return self._list("alerts")
    def list_evidence(self): return self._list("evidence")
    def list_decisions(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT payload FROM decisions ORDER BY created_at DESC")
            return [json.loads(row[0]) for row in cur.fetchall()]
    def list_audit_events(self): return self._list("audit_events")

    def reset(self):
        with self.conn.cursor() as cur:
            for table in TABLES:
                cur.execute(f"DELETE FROM {table}")
        self.conn.commit()
