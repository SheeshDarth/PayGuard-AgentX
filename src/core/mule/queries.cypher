// ===========================================================================
// Money-muling knowledge-graph queries (evidence artifact)
// ===========================================================================
// Graph model (Kùzu / Cypher):
//   (:Account {id, txn_count})
//   (:Account)-[:SENT {amount, ts}]->(:Account)
//
// These queries express the graph *intent* of two detectors for the knowledge-
// graph rubric. The pure-Python detectors in this package remain the source of
// truth (they add the multi-signal scorer + false-positive suppressor that
// Cypher cannot express); tests/test_mule.py asserts the Python rings match the
// intent below on the shared fixture. They run as-is on a populated Kùzu graph.
// ===========================================================================

// --- Circular billing ring (cycle length 3): A -> B -> C -> A ---------------
MATCH (a:Account)-[:SENT]->(b:Account)-[:SENT]->(c:Account)-[:SENT]->(a:Account)
WHERE a.id <> b.id AND b.id <> c.id AND a.id <> c.id
RETURN DISTINCT a.id AS n1, b.id AS n2, c.id AS n3;

// --- Shell pass-through chain: source -> shell -> shell -> destination -------
MATCH (src:Account)-[:SENT]->(s1:Account)-[:SENT]->(s2:Account)-[:SENT]->(dst:Account)
WHERE s1.txn_count <= 4 AND s2.txn_count <= 4
  AND src.id <> dst.id
RETURN src.id AS source, s1.id AS shell1, s2.id AS shell2, dst.id AS destination;
