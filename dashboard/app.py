"""
PayGuard-AgentX operator dashboard (Streamlit).

Run on the demo laptop:  streamlit run dashboard/app.py  -> http://localhost:8501

Four panels, all driven by the real supervisor (src/agents/orchestrator.run_supervised):
  1. Stream builder     -- assemble a synthetic retail + procurement batch
  2. Pipeline trace     -- per-agent log of what the supervised run did
  3. HITL queue         -- auto vs human buckets from confidence-based escalation
  4. HMAC verify + tamper demo -- one-click integrity check on each signed dossier

No LLM / GPU / network is required: the offline fallbacks in llm/graph_store/memory
keep every panel functional. When Ollama + Kuzu + Chroma are present the same code
lights up for real.
"""

import json
import sys
from pathlib import Path

import streamlit as st

# Make the project importable when Streamlit is launched from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.orchestrator import run_supervised  # noqa: E402
from src.core import audit  # noqa: E402
from src.core.memory import Memory  # noqa: E402
from src.utils.retail_simulator import RetailSimulator  # noqa: E402

st.set_page_config(page_title="PayGuard-AgentX", layout="wide")
st.title("PayGuard-AgentX -- operator dashboard")
st.caption("Guarded multi-agent retail + procurement copilot. Humans approve money.")


# ------------------------------------------------------------------ stream builder
with st.sidebar:
    st.header("Build a batch")
    n_sales = st.slider("Sales records", 0, 10, 4)
    n_low_stock = st.slider("Low-stock SKUs (force restock)", 0, 5, 2)
    add_clean_invoice = st.checkbox("Clean invoice (matches PO)", value=True)
    add_dup_invoice = st.checkbox("Duplicate invoice (should flag)", value=True)
    add_tampered = st.checkbox("Checksum-tampered invoice (should quarantine)", value=True)
    run = st.button("Run supervised pipeline", type="primary")


def _build_state():
    sales = [RetailSimulator.sales_record("CLEAN") for _ in range(n_sales)]
    inventory = [
        RetailSimulator.inventory_snapshot(on_hand=0, reorder_point=20)
        for _ in range(n_low_stock)
    ]
    invoices = []
    if add_clean_invoice:
        invoices.append(RetailSimulator.supplier_invoice(scenario="CLEAN"))
    if add_dup_invoice:
        dup = RetailSimulator.supplier_invoice(sku="SKU_MILK", amount=123.45)
        invoices.append(dup)
        invoices.append(dup)  # exact repeat -> DUPLICATE flag
    if add_tampered:
        invoices.append(RetailSimulator.supplier_invoice(scenario="CHECKSUM_TAMPERED"))
    return {"sales_raw": sales, "inventory_raw": inventory, "invoices_raw": invoices}


if run:
    st.session_state["state"] = run_supervised(_build_state(), memory=Memory())

state = st.session_state.get("state")
if not state:
    st.info("Configure a batch in the sidebar and click **Run supervised pipeline**.")
    st.stop()

col1, col2 = st.columns(2)

# ------------------------------------------------------------------ pipeline trace
with col1:
    st.subheader("Pipeline trace")
    st.caption("Route: **" + str(state.get("route", "?")) + "**")
    for line in state.get("logs", []):
        st.text("- " + line)
    rejected = state.get("rejected", [])
    if rejected:
        st.markdown("**Quarantined records**")
        for r in rejected:
            st.text("  x " + r.get("kind", "?") + ": " + r.get("note", ""))

# ------------------------------------------------------------------ HITL queue
with col2:
    st.subheader("HITL approval queue")
    queue = state.get("hitl_queue", {"auto": [], "human": []})
    st.markdown("**Needs human approval** (" + str(len(queue["human"])) + ")")
    for item in queue["human"]:
        st.warning(item["kind"] + " " + str(item["id"])
                   + "  (confidence " + str(item.get("confidence")) + ")")
    st.markdown("**Auto-approved** (" + str(len(queue["auto"])) + ")")
    for item in queue["auto"]:
        st.success(item["kind"] + " " + str(item["id"])
                   + "  (confidence " + str(item.get("confidence")) + ")")

# ------------------------------------------------------------------ HMAC verify + tamper
st.subheader("Signed dossiers -- HMAC-SHA256 verification")
st.caption("Each consequential action is signed with a server-held key. "
           "Toggle *Tamper* to flip a field and watch verification fail.")

for i, d in enumerate(state.get("dossiers", [])):
    tamper = st.checkbox("Tamper with payload", key="tamper_" + str(i))
    check = json.loads(json.dumps(d))  # deep copy
    if tamper:
        check["payload"]["_injected"] = "attacker-controlled"
    ok = audit.verify_dossier_dict(check)
    label = d.get("dossier_id", "?") + "  --  " + d.get("summary", "")
    if ok:
        st.success("VALID   " + label)
    else:
        st.error("INVALID " + label + "   (signature does not match payload)")
    with st.expander("payload"):
        st.json(check["payload"])

if not state.get("dossiers"):
    st.info("No signed dossiers in this run (no PO draft or dispute was produced).")
