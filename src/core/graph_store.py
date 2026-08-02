"""
Graph store for PayGuard-AgentX supplier / dispute knowledge.

Uses Kuzu (embedded, real Cypher) when installed; otherwise a pure-Python
in-memory adjacency fallback so graph questions -- e.g. suppliers tied to more
than one disputed invoice (a fraud-ring signal) -- still work offline and in tests.

Any Kuzu error is caught and the store falls back to memory, so a bad driver or
missing DB never takes the pipeline down.
"""

from collections import Counter


class GraphStore:
    """Supplier -[:SUPPLIES]-> SKU  and  Supplier -[:INVOICED]-> Dispute."""

    def __init__(self, db_path=None):
        self._supplies = set()          # (supplier_id, sku)
        self._disputes = []             # (supplier_id, dispute_id, invoice_id)
        self.backend = "memory"
        self._kuzu = None
        if db_path:
            self._try_kuzu(db_path)

    def _try_kuzu(self, db_path):
        try:
            import kuzu
            self._db = kuzu.Database(db_path)
            self._kuzu = kuzu.Connection(self._db)
            self._kuzu.execute("CREATE NODE TABLE IF NOT EXISTS Supplier(id STRING, PRIMARY KEY(id))")
            self._kuzu.execute("CREATE NODE TABLE IF NOT EXISTS Sku(id STRING, PRIMARY KEY(id))")
            self._kuzu.execute("CREATE NODE TABLE IF NOT EXISTS Dispute(id STRING, invoice_id STRING, PRIMARY KEY(id))")
            self._kuzu.execute("CREATE REL TABLE IF NOT EXISTS SUPPLIES(FROM Supplier TO Sku)")
            self._kuzu.execute("CREATE REL TABLE IF NOT EXISTS INVOICED(FROM Supplier TO Dispute)")
            self.backend = "kuzu"
        except Exception:
            self._kuzu = None
            self.backend = "memory"

    def add_supplies(self, supplier_id, sku):
        self._supplies.add((supplier_id, sku))
        if self._kuzu:
            try:
                self._kuzu.execute("MERGE (:Supplier {id: $s})", {"s": supplier_id})
                self._kuzu.execute("MERGE (:Sku {id: $k})", {"k": sku})
                self._kuzu.execute(
                    "MATCH (s:Supplier {id:$s}),(k:Sku {id:$k}) MERGE (s)-[:SUPPLIES]->(k)",
                    {"s": supplier_id, "k": sku})
            except Exception:
                pass

    def add_dispute(self, supplier_id, dispute_id, invoice_id):
        self._disputes.append((supplier_id, dispute_id, invoice_id))
        if self._kuzu:
            try:
                self._kuzu.execute("MERGE (:Supplier {id:$s})", {"s": supplier_id})
                self._kuzu.execute("MERGE (:Dispute {id:$d, invoice_id:$i})",
                                   {"d": dispute_id, "i": invoice_id})
                self._kuzu.execute(
                    "MATCH (s:Supplier {id:$s}),(d:Dispute {id:$d}) MERGE (s)-[:INVOICED]->(d)",
                    {"s": supplier_id, "d": dispute_id})
            except Exception:
                pass

    def suppliers_with_multiple_disputes(self, min_count=2):
        """Fraud-ring signal: suppliers linked to >= min_count disputes."""
        counts = Counter(s for (s, _, _) in self._disputes)
        return sorted(s for s, n in counts.items() if n >= min_count)

    def skus_for_supplier(self, supplier_id):
        return sorted(sku for (s, sku) in self._supplies if s == supplier_id)
