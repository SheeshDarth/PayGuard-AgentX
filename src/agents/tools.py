"""
Tool registry for PayGuard-AgentX.

Each tool is a plain typed callable, so the agents can call them today and the
MCP server (mcp_server/server.py) can expose the same set as real MCP tools on
the demo laptop. Deterministic tools consume 0 LLM tokens.
"""

from src.core.dq_engine import PayGuardDQEngine
from src.core import audit, relational
from src.core.graph_store import GraphStore
from src.core.memory import Memory


class ToolKit:
    """Bundles the data-source resources and exposes them as callable tools."""

    def __init__(self, conn=None, graph=None, memory=None):
        if conn is None:
            conn = relational.connect()
            relational.seed_demo(conn)
        self.conn = conn
        self.graph = graph or GraphStore()
        self.memory = memory or Memory()

    # 1. deterministic validation
    def dq_validate(self, kind, raw_json):
        if kind == "sales":
            ok, note, _ = PayGuardDQEngine.validate_sales_record(raw_json)
        elif kind == "inventory":
            ok, note, _ = PayGuardDQEngine.validate_inventory_snapshot(raw_json)
        elif kind == "invoice":
            ok, note, _ = PayGuardDQEngine.validate_supplier_invoice(raw_json)
        else:
            raise ValueError("unknown kind: " + str(kind))
        return {"valid": ok, "note": note}

    # 2. relational
    def sql_query(self, query, params=()):
        return relational.sql_query(self.conn, query, params)

    # 3. graph
    def graph_query(self, kind, supplier_id=""):
        if kind == "multi_dispute_suppliers":
            return self.graph.suppliers_with_multiple_disputes()
        if kind == "skus_for_supplier":
            return self.graph.skus_for_supplier(supplier_id)
        raise ValueError("unknown graph query: " + str(kind))

    # 4. document RAG
    def doc_retrieve(self, text, k=3):
        return self.memory.retrieve_reg(text, k)

    # 5. case memory
    def case_recall(self, text, k=3):
        return self.memory.recall_cases(text, k)

    # 6. audit
    def audit_sign(self, dossier_id, subject_id, summary, payload):
        return audit.build_dossier(dossier_id, subject_id, summary, payload).model_dump()

    def audit_verify(self, dossier):
        return audit.verify_dossier_dict(dossier)

    def schemas(self):
        """Lightweight tool schemas (name/description/inputs) for MCP exposure."""
        return [
            {"name": "dq_validate", "description": "Deterministic PayGuardDQ validation",
             "inputs": {"kind": "sales|inventory|invoice", "raw_json": "str"}},
            {"name": "sql_query", "description": "Read-only SELECT over vendor/store/SKU/PO",
             "inputs": {"query": "str", "params": "tuple"}},
            {"name": "graph_query", "description": "Supplier/dispute graph lookups",
             "inputs": {"kind": "multi_dispute_suppliers|skus_for_supplier", "supplier_id": "str"}},
            {"name": "doc_retrieve", "description": "Regulatory clause RAG retrieval",
             "inputs": {"text": "str", "k": "int"}},
            {"name": "case_recall", "description": "Past-case long-term memory retrieval",
             "inputs": {"text": "str", "k": "int"}},
            {"name": "audit_sign", "description": "HMAC-sign an evidence dossier",
             "inputs": {"dossier_id": "str", "subject_id": "str", "summary": "str", "payload": "dict"}},
            {"name": "audit_verify", "description": "Verify an evidence dossier signature",
             "inputs": {"dossier": "dict"}},
        ]
