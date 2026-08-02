"""
Long-term and knowledge memory for PayGuard-AgentX.

Chroma (persistent, embedded) with CPU MiniLM embeddings when installed; a
pure-Python keyword-overlap retriever as the offline fallback, so case recall and
document retrieval work with no vector DB, no model download, and no GPU.

Collections:
  case_history    -- past disputes / rejections, for pattern-over-time fraud signals
  regulatory_docs -- compliance clause excerpts for the Regulatory-Auditor RAG
"""


class _FallbackCollection:
    """Deterministic keyword-overlap retriever used when Chroma is unavailable."""

    def __init__(self):
        self.docs = []   # list of (id, text, metadata)

    def add(self, doc_id, text, metadata=None):
        self.docs.append((doc_id, text, metadata or {}))

    def query(self, text, k=3):
        terms = set(str(text).lower().split())
        scored = []
        for (doc_id, doc_text, meta) in self.docs:
            overlap = len(terms & set(doc_text.lower().split()))
            scored.append((overlap, doc_id, doc_text, meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"id": i, "text": t, "metadata": m, "score": s}
                for (s, i, t, m) in scored[:k]]


class Memory:
    def __init__(self, path=None):
        self.backend = "fallback"
        self.case_history = _FallbackCollection()
        self.regulatory_docs = _FallbackCollection()
        if path:
            self._try_chroma(path)

    def _try_chroma(self, path):
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=path)
            # Real embeddings would be attached here (CPU MiniLM) on the demo laptop.
            self._case = self._client.get_or_create_collection("case_history")
            self._reg = self._client.get_or_create_collection("regulatory_docs")
            self.backend = "chroma"
        except Exception:
            self.backend = "fallback"

    # --- case history (long-term memory) ---
    def add_case(self, case_id, text, metadata=None):
        if self.backend == "chroma":
            try:
                self._case.add(ids=[case_id], documents=[text], metadatas=[metadata or {}])
                return
            except Exception:
                pass
        self.case_history.add(case_id, text, metadata)

    def recall_cases(self, text, k=3):
        if self.backend == "chroma":
            try:
                res = self._case.query(query_texts=[text], n_results=k)
                return [{"id": i, "text": d} for i, d in
                        zip(res.get("ids", [[]])[0], res.get("documents", [[]])[0])]
            except Exception:
                pass
        return self.case_history.query(text, k)

    # --- regulatory knowledge (RAG) ---
    def add_reg(self, doc_id, text, metadata=None):
        if self.backend == "chroma":
            try:
                self._reg.add(ids=[doc_id], documents=[text], metadatas=[metadata or {}])
                return
            except Exception:
                pass
        self.regulatory_docs.add(doc_id, text, metadata)

    def retrieve_reg(self, text, k=3):
        if self.backend == "chroma":
            try:
                res = self._reg.query(query_texts=[text], n_results=k)
                return [{"id": i, "text": d} for i, d in
                        zip(res.get("ids", [[]])[0], res.get("documents", [[]])[0])]
            except Exception:
                pass
        return self.regulatory_docs.query(text, k)
