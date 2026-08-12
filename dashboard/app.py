"""
PayGuard-AgentX operator workbench (Streamlit).

Run:  streamlit run dashboard/app.py  ->  http://localhost:8501

A fraud-analyst workbench over the supervised pipeline. Four tabs:
  Overview       -- KPIs + per-typology fraud-ring scorecards
  Pipeline       -- agent trace + HITL approval / fraud-ring queues (risk-sorted)
  Fraud Network  -- offline node-link graph of the payment graph (read-only)
  Evidence       -- HMAC-signed dossiers with one-click verify + tamper demo

Everything runs offline (llm/graph/memory fallbacks). Enable the Money-muling
scenario toggle to inject a synthetic fraud graph so the Ring-Auditor lights up.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.orchestrator import run_supervised   # noqa: E402
from src.core import audit                            # noqa: E402
from src.core.memory import Memory                    # noqa: E402
from src.utils.retail_simulator import RetailSimulator  # noqa: E402

st.set_page_config(page_title="PayGuard-AgentX", layout="wide",
                   initial_sidebar_state="expanded")


# ----------------------------------------------------------------- helpers
def risk_tier(score):
    if score >= 80:
        return "CRITICAL", "#DC2626"
    if score >= 60:
        return "HIGH", "#EA580C"
    if score >= 40:
        return "MEDIUM", "#D97706"
    if score >= 20:
        return "LOW", "#CA8A04"
    return "NORMAL", "#2563EB"


_BASE = datetime(2024, 1, 1, 9, 0, 0)


def _mtx(tid, s, r, a, m):
    return {"tx_id": tid, "sender": s, "receiver": r, "amount": a,
            "timestamp": _BASE + timedelta(minutes=m)}


def mule_scenario():
    """Synthetic fraud graph: one fast cycle + one shell chain + a payroll trap."""
    txns = [
        _mtx("CY1", "SUP_A", "SUP_B", 5000, 0), _mtx("CY2", "SUP_B", "SUP_C", 5000, 10),
        _mtx("CY3", "SUP_C", "SUP_A", 5000, 20),
        _mtx("SL1", "STORE_HQ", "SHELL_1", 1000, 0), _mtx("SL2", "SHELL_1", "SHELL_2", 950, 30),
        _mtx("SL3", "SHELL_2", "VENDOR_X", 900, 50),
    ]
    for i in range(12):
        txns.append(_mtx("PR%d" % i, "PAYROLL", "EMP_%d" % i, 3000, i))
    return txns


def build_state(n_sales, n_low, clean_inv, dup_inv, tampered, muling):
    sales = [RetailSimulator.sales_record("CLEAN") for _ in range(n_sales)]
    inventory = [RetailSimulator.inventory_snapshot(on_hand=0, reorder_point=20)
                 for _ in range(n_low)]
    invoices = []
    if clean_inv:
        invoices.append(RetailSimulator.supplier_invoice(scenario="CLEAN"))
    if dup_inv:
        dup = RetailSimulator.supplier_invoice(sku="SKU_MILK", amount=123.45)
        invoices += [dup, dup]
    if tampered:
        invoices.append(RetailSimulator.supplier_invoice(scenario="CHECKSUM_TAMPERED"))
    state = {"sales_raw": sales, "inventory_raw": inventory, "invoices_raw": invoices}
    if muling:
        state["mule_transactions"] = mule_scenario()
        if not invoices:
            state["invoices_raw"] = [RetailSimulator.supplier_invoice(scenario="CLEAN")]
    return state


# ----------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Scenario builder")
    n_sales = st.slider("Sales records", 0, 10, 4)
    n_low = st.slider("Low-stock SKUs", 0, 5, 2)
    clean_inv = st.checkbox("Clean invoice", value=True)
    dup_inv = st.checkbox("Duplicate invoice", value=True)
    tampered = st.checkbox("Checksum-tampered invoice", value=True)
    st.divider()
    muling = st.checkbox("Money-muling scenario", value=True,
                         help="Inject a synthetic fraud graph (cycle + shell + payroll trap)")
    run = st.button("Run supervised pipeline", type="primary")

if run:
    st.session_state["state"] = run_supervised(
        build_state(n_sales, n_low, clean_inv, dup_inv, tampered, muling), memory=Memory())

st.title("PayGuard-AgentX -- operator workbench")
st.caption("Guarded multi-agent retail + procurement + network-fraud copilot. Humans approve money.")

state = st.session_state.get("state")
if not state:
    st.info("Configure a scenario in the sidebar and click Run supervised pipeline.")
    st.stop()

accounts = state.get("mule_suspicious_accounts", [])
rings = state.get("mule_rings", [])
dossiers = state.get("dossiers", [])

tab_overview, tab_pipeline, tab_network, tab_evidence = st.tabs(
    ["Overview", "Pipeline", "Fraud Network", "Evidence"])

with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Route", state.get("route", "?"))
    c2.metric("Suspicious accounts", len(accounts))
    c3.metric("Fraud rings", len(rings))
    verified = sum(1 for d in dossiers if audit.verify_dossier_dict(d))
    c4.metric("Signed dossiers", "%d/%d valid" % (verified, len(dossiers)))

    st.subheader("Fraud rings by typology")
    if rings:
        by_type = {}
        for r in rings:
            by_type.setdefault(r["pattern_type"], []).append(r)
        cols = st.columns(max(len(by_type), 1))
        for col, (ptype, rs) in zip(cols, sorted(by_type.items())):
            col.metric(ptype, len(rs), help="max risk %.1f" % max(r["risk_score"] for r in rs))
    else:
        st.caption("No fraud rings in this run. Enable the Money-muling scenario in the sidebar.")

    if accounts:
        st.subheader("Suspicious accounts (risk-ranked)")
        import pandas as pd
        st.dataframe(pd.DataFrame([
            {"account": a["account_id"], "score": a["suspicion_score"], "ring": a["ring_id"],
             "patterns": ", ".join(a["detected_patterns"])} for a in accounts]),
            use_container_width=True, hide_index=True)

with tab_pipeline:
    left, right = st.columns(2)
    with left:
        st.subheader("Agent trace")
        st.caption("Route: **%s**" % state.get("route", "?"))
        for line in state.get("logs", []):
            st.text("- " + line)
        rej = state.get("rejected", [])
        if rej:
            st.markdown("**Quarantined**")
            for r in rej:
                st.text("  x %s: %s" % (r.get("kind", "?"), r.get("note", "")))
    with right:
        st.subheader("HITL approval queue")
        q = state.get("hitl_queue", {"auto": [], "human": []})
        st.markdown("**Needs human approval** (%d)" % len(q["human"]))
        for it in q["human"]:
            st.warning("%s %s (conf %s)" % (it["kind"], it["id"], it.get("confidence")))
        st.markdown("**Auto-approved** (%d)" % len(q["auto"]))
        for it in q["auto"]:
            st.success("%s %s (conf %s)" % (it["kind"], it["id"], it.get("confidence")))

        st.subheader("Fraud-ring queue")
        rq = state.get("ring_hitl", {"review": [], "monitor": []})
        for it in sorted(rq["review"], key=lambda x: x["risk_score"], reverse=True):
            st.error("REVIEW %s  risk %.1f  (%s)" % (it["ring_id"], it["risk_score"], it["pattern_type"]))
        for it in sorted(rq["monitor"], key=lambda x: x["risk_score"], reverse=True):
            st.info("monitor %s  risk %.1f  (%s)" % (it["ring_id"], it["risk_score"], it["pattern_type"]))
        if not rq["review"] and not rq["monitor"]:
            st.caption("No fraud rings queued.")

with tab_network:
    st.subheader("Payment network (read-only)")
    txns = state.get("mule_transactions", [])
    if not txns:
        st.info("No money-muling graph in this run. Enable the Money-muling scenario in the sidebar.")
    else:
        score_of = {a["account_id"]: a["suspicion_score"] for a in accounts}
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import networkx as nx
            gx = nx.DiGraph()
            for t in txns:
                gx.add_edge(t["sender"], t["receiver"])
            colors = [risk_tier(score_of.get(n, 0))[1] for n in gx.nodes()]
            sizes = [300 + 12 * score_of.get(n, 0) for n in gx.nodes()]
            fig, ax = plt.subplots(figsize=(9, 6))
            pos = nx.spring_layout(gx, seed=42, k=0.9)
            nx.draw_networkx_edges(gx, pos, ax=ax, edge_color="#94A3B8",
                                   arrows=True, arrowsize=12, width=1.2)
            nx.draw_networkx_nodes(gx, pos, ax=ax, node_color=colors, node_size=sizes)
            nx.draw_networkx_labels(gx, pos, ax=ax, font_size=8, font_color="#0F172A")
            ax.axis("off")
            st.pyplot(fig)
            st.caption("Node colour = suspicion tier (red critical to blue normal); size = risk.")
        except Exception as exc:
            st.warning("Graph render unavailable (%s). Showing edge list." % exc)
            import pandas as pd
            st.dataframe(pd.DataFrame([
                {"from": t["sender"], "to": t["receiver"], "amount": t["amount"]} for t in txns]),
                use_container_width=True, hide_index=True)

        if accounts:
            st.subheader("Account detail")
            sel = st.selectbox("Flagged account", [a["account_id"] for a in accounts])
            acc = next(a for a in accounts if a["account_id"] == sel)
            tier, _ = risk_tier(acc["suspicion_score"])
            st.markdown("**%s** -- score %.1f (%s) -- ring %s"
                        % (sel, acc["suspicion_score"], tier, acc["ring_id"]))
            st.markdown("Patterns: " + ", ".join(acc["detected_patterns"]))
            st.json(acc.get("signal_breakdown", {}))
            related = [t for t in txns if t["sender"] == sel or t["receiver"] == sel]
            st.caption("%d related transaction(s)" % len(related))

with tab_evidence:
    st.subheader("Signed dossiers -- HMAC-SHA256")
    st.caption("Toggle Tamper to flip a field and watch verification fail.")
    for i, d in enumerate(dossiers):
        tamper = st.checkbox("Tamper with payload", key="t_%d" % i)
        chk = json.loads(json.dumps(d))
        if tamper:
            chk["payload"]["_injected"] = "attacker-controlled"
        ok = audit.verify_dossier_dict(chk)
        label = "%s -- %s" % (d.get("dossier_id", "?"), d.get("summary", ""))
        (st.success if ok else st.error)(("VALID   " if ok else "INVALID ") + label)
        with st.expander("payload"):
            st.json(chk["payload"])
    if not dossiers:
        st.info("No signed dossiers in this run.")
