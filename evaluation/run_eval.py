"""
Evaluation harness for PayGuard-AgentX.

Two labeled tasks, run against the deterministic agents to establish a baseline
to beat once the LLM hooks are enabled:

  * restock decision -- does the store need to reorder a SKU? Ground truth is the
    NEXT period's actual demand (hidden from the agent), so the agent's reorder
    heuristic can genuinely disagree with the label. We report precision/recall.
  * invoice audit -- given a batch of supplier invoices against a PO, does the
    Payment-Auditor assign the correct flag (CLEAN / DUPLICATE / PO_MISMATCH)?

Run:  python evaluation/run_eval.py
"""

import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.pipeline import demand_forecaster, stock_watcher, payment_auditor


def _restock_cases(n=30, seed=42):
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        on_hand = rng.randint(0, 60)
        reorder_point = rng.choice([10, 20, 30])
        past_sales = [rng.randint(0, 15) for _ in range(3)]
        next_actual_demand = rng.randint(0, 80)          # hidden ground truth
        cases.append({
            "on_hand": on_hand,
            "reorder_point": reorder_point,
            "past_sales": past_sales,
            "label_should_reorder": next_actual_demand > on_hand,
        })
    return cases


def _invoice_cases(seed=7):
    rng = random.Random(seed)
    po = {"po_id": "PO_EVAL", "total_estimated_cost": 100.0}
    invoices, labels, seen = [], [], set()
    for i in range(20):
        kind = rng.choice(["CLEAN", "CLEAN", "MISMATCH", "DUP"])
        sku = rng.choice(["A", "B", "C"])
        amount = 500.0 if kind == "MISMATCH" else 100.0
        inv = {"invoice_id": "IV_" + str(i), "supplier_id": "SUP_A",
               "sku": sku, "amount": amount, "po_id": "PO_EVAL"}
        if kind == "DUP" and seen:
            s = next(iter(seen))
            inv["supplier_id"], inv["sku"], inv["amount"] = s[0], s[1], s[2]
        sig = (inv["supplier_id"], inv["sku"], round(inv["amount"], 2))
        if sig in seen:
            labels.append("DUPLICATE")
        elif abs(inv["amount"] - po["total_estimated_cost"]) > 0.02 * po["total_estimated_cost"]:
            labels.append("PO_MISMATCH")
        else:
            labels.append("CLEAN")
        seen.add(sig)
        invoices.append(inv)
    return po, invoices, labels


def evaluate():
    tp = fp = tn = fn = 0
    for c in _restock_cases():
        st = demand_forecaster({"valid_sales": [
            {"store_id": "S", "sku": "K", "units_sold": u} for u in c["past_sales"]]})
        st["valid_inventory"] = [{"store_id": "S", "sku": "K",
                                  "on_hand": c["on_hand"], "reorder_point": c["reorder_point"]}]
        st = stock_watcher(st)
        pred = len(st["stock_alerts"]) > 0
        label = c["label_should_reorder"]
        if pred and label:
            tp += 1
        elif pred and not label:
            fp += 1
        elif (not pred) and (not label):
            tn += 1
        else:
            fn += 1
    n = tp + fp + tn + fn
    acc = (tp + tn) / n if n else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0

    po, invoices, labels = _invoice_cases()
    st = payment_auditor({"valid_invoices": invoices, "po_draft": po})
    preds = [f["flag_type"] for f in st["payment_flags"]]
    correct = sum(1 for p, l in zip(preds, labels) if p == l)
    inv_acc = correct / len(labels) if labels else 0.0

    return {
        "restock": {"n": n, "accuracy": round(acc, 3), "precision": round(prec, 3),
                    "recall": round(rec, 3), "f1": round(f1, 3)},
        "invoice": {"n": len(labels), "accuracy": round(inv_acc, 3)},
    }


def main():
    r = full_eval()
    print("=" * 60)
    print("PayGuard-AgentX -- Evaluation (deterministic baseline)")
    print("=" * 60)
    rs = r["restock"]
    print("Restock decision  (n=%d): acc=%.3f  precision=%.3f  recall=%.3f  f1=%.3f"
          % (rs["n"], rs["accuracy"], rs["precision"], rs["recall"], rs["f1"]))
    iv = r["invoice"]
    print("Invoice audit     (n=%d): acc=%.3f" % (iv["n"], iv["accuracy"]))
    ag = r["agentic"]
    print("Plan-revision rate       : %.3f (critic recall %.3f)" % (ag["plan_revision_rate"], ag["critic_recall"]))
    print("Escalation miss rate     : %.3f (auto-approved %d)" % (ag["escalation_miss_rate"], ag["auto_approved"]))
    mu = r["mule"]
    print("Mule ring recall         : %.3f (%d/%d planted rings; payroll FP=%s)"
          % (mu["ring_recall"], mu["detected_rings"], mu["planted_rings"], mu["payroll_false_positive"]))
    print("\nBaseline captured. Re-run after enabling the LLM hooks to compare.")




def agentic_metrics(seed=11):
    import random
    from src.agents.critics import po_critic
    from src.agents.hitl import route_decision
    rng = random.Random(seed)
    n = 20; planted = 0; caught = 0; revisions = 0
    for i in range(n):
        bad = (i % 2 == 0)
        qty = 900 if bad else rng.randint(10, 100)
        po = {"po_id": "PO_" + str(i),
              "lines": [{"sku": "K", "recommend_order_qty": qty, "rationale": "x"}],
              "total_estimated_cost": qty * 10.0}
        review, _, _ = po_critic(po)
        if bad:
            planted += 1
        if review["verdict"] == "REVISE":
            revisions += 1
            if bad:
                caught += 1
    plan_revision_rate = round(revisions / n, 3)
    critic_recall = round(caught / planted, 3) if planted else 0.0
    auto = 0; auto_wrong = 0
    for i in range(20):
        conf = rng.choice([0.6, 0.85, 0.9, 0.7])
        val = rng.choice([100.0, 6000.0, 500.0])
        gt_should_escalate = (val >= 5000.0) or (conf < 0.8)
        if route_decision(conf, val) == "AUTO":
            auto += 1
            if gt_should_escalate:
                auto_wrong += 1
    escalation_miss_rate = round(auto_wrong / auto, 3) if auto else 0.0
    return {"plan_revision_rate": plan_revision_rate, "critic_recall": critic_recall,
            "auto_approved": auto, "escalation_miss_rate": escalation_miss_rate}


def full_eval():
    r = evaluate()
    r["agentic"] = agentic_metrics()
    r["mule"] = mule_metrics()
    return r


def mule_metrics():
    """Ring-detection quality on a labelled synthetic graph: two planted circular
    rings + a payroll trap. Reports ring recall and whether the payroll account is
    wrongly flagged (false-positive control)."""
    from datetime import datetime, timedelta
    from src.core.mule.graph_model import build_graph
    from src.core.mule.cycle_detector import detect_cycles
    from src.core.mule.smurfing_detector import detect_smurfing
    from src.core.mule.shell_detector import detect_shell_networks
    from src.core.mule.scorer import compute_scores
    base = datetime(2024, 1, 1, 9, 0, 0)

    def tx(tid, s, r, a, m):
        return {"tx_id": tid, "sender": s, "receiver": r, "amount": a,
                "timestamp": base + timedelta(minutes=m)}

    txns, planted = [], []
    for k, (x, y, z) in enumerate([("A1", "B1", "C1"), ("A2", "B2", "C2")]):
        off = k * 100
        txns += [tx("c%d1" % k, x, y, 5000, off), tx("c%d2" % k, y, z, 5000, off + 10),
                 tx("c%d3" % k, z, x, 5000, off + 20)]
        planted.append({x, y, z})
    for i in range(12):                       # payroll trap (must not flag)
        txns.append(tx("p%d" % i, "PAY", "P%d" % i, 3000, i))

    g = build_graph(txns)
    accounts, rings = compute_scores(detect_cycles(g), detect_smurfing(g),
                                     detect_shell_networks(g), g)
    ring_sets = [set(r["member_accounts"]) for r in rings]
    detected = sum(1 for p in planted if any(p & rs for rs in ring_sets))
    return {"planted_rings": len(planted), "detected_rings": detected,
            "ring_recall": round(detected / len(planted), 3) if planted else 0.0,
            "payroll_false_positive": any(a["account_id"] == "PAY" for a in accounts)}


if __name__ == "__main__":
    main()
