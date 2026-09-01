"""Durable, signed operator dispositions for the Streamlit workbench."""

import json
import sqlite3
from datetime import datetime, timezone

from src.core import audit


class DecisionStore:
    """Persist the latest operator decision and its evidence dossier in SQLite."""

    def __init__(self, path=".payguard/decisions.sqlite"):
        self.path = path
        if path != ":memory:":
            from pathlib import Path
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS decisions ("
            "subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL, action TEXT NOT NULL, "
            "actor TEXT NOT NULL, created_at TEXT NOT NULL, dossier TEXT NOT NULL, "
            "PRIMARY KEY(subject_kind, subject_id))")
        self.conn.commit()

    def latest(self, subject_kind=None, subject_id=None):
        query = "SELECT * FROM decisions"
        params = []
        clauses = []
        if subject_kind is not None:
            clauses.append("subject_kind=?")
            params.append(subject_kind)
        if subject_id is not None:
            clauses.append("subject_id=?")
            params.append(subject_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def record(self, subject_kind, subject_id, action, actor="operator"):
        created_at = datetime.now(timezone.utc).isoformat()
        payload = {"subject_kind": subject_kind, "subject_id": subject_id,
                   "action": action, "actor": actor, "created_at": created_at}
        dossier = audit.build_dossier(
            f"DOS_DECISION_{subject_kind}_{subject_id}", subject_id,
            f"Operator disposition: {action}", payload).model_dump()
        self.conn.execute(
            "INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?)",
            (subject_kind, subject_id, action, actor, created_at,
             json.dumps(dossier, sort_keys=True, default=str)))
        self.conn.commit()
        return {"subject_kind": subject_kind, "subject_id": subject_id,
                "action": action, "actor": actor, "created_at": created_at,
                "dossier": dossier}

    @staticmethod
    def verify(record):
        dossier = record.get("dossier", record)
        return audit.verify_dossier_dict(dossier)

