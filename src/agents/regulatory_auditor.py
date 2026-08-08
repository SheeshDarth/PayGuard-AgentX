"""
Regulatory-Auditor agent for PayGuard-AgentX.

For each non-clean payment flag, retrieves the most relevant compliance clause
from the regulatory_docs RAG memory and attaches a citation. The set of citations
is signed into an HMAC evidence dossier. Runs offline via the Memory keyword
fallback; upgrades to Chroma + MiniLM retrieval when those are installed.
"""

from src.core import audit

# Map a flag type to clause-aligned query keywords so retrieval is relevant even
# with the offline keyword-overlap retriever. Only the flag types the Payment-Auditor
# actually emits are listed (PO_MISMATCH, DUPLICATE); checksum failures are quarantined
# upstream by the DQ-Sentinel and never reach this agent. Any unmapped type falls back
# to the flag's own description as the query.
_FLAG_QUERY = {
    "PO_MISMATCH": "purchase order amount tolerance deviation approved",
    "DUPLICATE": "duplicate invoices same supplier rejected",
}


def regulatory_auditor(state, memory):
    citations = []
    for flag in state.get("payment_flags", []):
        ftype = flag.get("flag_type")
        if not ftype or ftype == "CLEAN":
            continue
        query = _FLAG_QUERY.get(ftype, flag.get("description", ""))
        hits = memory.retrieve_reg(query, k=1)
        if hits:
            citations.append({
                "invoice_id": flag.get("invoice_id"),
                "flag_type": ftype,
                "clause_id": hits[0]["id"],
                "clause_text": hits[0]["text"],
            })
    state["regulatory_citations"] = citations
    if citations:
        dossier = audit.build_dossier(
            "DOS_REG_" + str(len(citations)), "REGULATORY",
            "Regulatory clause citations for flagged invoices", {"citations": citations})
        state.setdefault("dossiers", []).append(dossier.model_dump())
    state.setdefault("logs", []).append(
        "Regulatory-Auditor: cited " + str(len(citations)) + " clause(s).")
    return state
