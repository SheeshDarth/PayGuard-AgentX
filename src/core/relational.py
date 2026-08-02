"""
Relational store (SQLite, Python stdlib) for PayGuard-AgentX.

Holds vendor / store / SKU / purchase-order metadata. Zero external dependency,
and the natural backend for LangGraph's SqliteSaver checkpointer later on.
Exposes a read-only sql_query() that the MCP sql_query tool wraps.
"""

import sqlite3

SCHEMA = [
    "CREATE TABLE IF NOT EXISTS suppliers (supplier_id TEXT PRIMARY KEY, name TEXT, lead_time_days INTEGER)",
    "CREATE TABLE IF NOT EXISTS stores (store_id TEXT PRIMARY KEY, name TEXT, region TEXT)",
    "CREATE TABLE IF NOT EXISTS skus (sku TEXT PRIMARY KEY, description TEXT, unit_cost REAL)",
    "CREATE TABLE IF NOT EXISTS purchase_orders "
    "(po_id TEXT PRIMARY KEY, store_id TEXT, supplier_id TEXT, total_cost REAL, status TEXT)",
]


def connect(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def seed_demo(conn):
    conn.executemany("INSERT OR REPLACE INTO suppliers VALUES (?,?,?)",
                     [("SUP_A", "Alpha Supply", 3), ("SUP_B", "Beta Distributors", 7)])
    conn.executemany("INSERT OR REPLACE INTO stores VALUES (?,?,?)",
                     [("STORE_01", "Downtown", "North"), ("STORE_02", "Airport", "South")])
    conn.executemany("INSERT OR REPLACE INTO skus VALUES (?,?,?)",
                     [("SKU_MILK", "Milk 1L", 10.0), ("SKU_RICE", "Rice 5kg", 10.0),
                      ("SKU_BREAD", "Bread", 10.0)])
    conn.commit()


def sql_query(conn, query, params=()):
    """Parameterised, read-only SELECT access. Raises on any non-SELECT statement."""
    q = query.strip().lower()
    if not q.startswith("select"):
        raise ValueError("sql_query is read-only; only SELECT statements are allowed")
    if ";" in query.strip().rstrip(";"):
        raise ValueError("sql_query allows a single statement only")
    cur = conn.execute(query, params)
    return [dict(r) for r in cur.fetchall()]
