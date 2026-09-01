"""Product-facing workflow services over the existing deterministic pipeline."""

import json
import uuid
from datetime import datetime, timedelta, timezone

from src.agents.orchestrator import run_supervised
from src.core.memory import Memory
from src.core.regulatory_seed import seed_regulatory
from src.utils.retail_simulator import RetailSimulator


def _tx(tid, sender, receiver, amount, minute):
    return {"tx_id": tid, "sender": sender, "receiver": receiver, "amount": amount,
            "timestamp": datetime(2024, 1, 1, 9, tzinfo=timezone.utc) + timedelta(minutes=minute)}


def mule_scenario():
    txns = [_tx("CY1", "SUP_A", "SUP_B", 5000, 0), _tx("CY2", "SUP_B", "SUP_C", 5000, 10),
            _tx("CY3", "SUP_C", "SUP_A", 5000, 20), _tx("SL1", "STORE_HQ", "SHELL_1", 1000, 0),
            _tx("SL2", "SHELL_1", "SHELL_2", 950, 30), _tx("SL3", "SHELL_2", "VENDOR_X", 900, 50)]
    txns.extend(_tx(f"PR{i}", "PAYROLL", f"EMP_{i}", 3000, i) for i in range(12))
    return txns


def scenario(preset):
    if preset == "Procurement mismatch":
        return {"sales_raw": [RetailSimulator.sales_record("CLEAN") for _ in range(6)],
                "inventory_raw": [RetailSimulator.inventory_snapshot(sku="SKU_MILK", store="STORE_01", on_hand=3, reorder_point=20)],
                "invoices_raw": [RetailSimulator.supplier_invoice(po_id="PO_STORE_01_1", sku="SKU_MILK", amount=999.0),
                                 RetailSimulator.supplier_invoice(scenario="CHECKSUM_TAMPERED")],
                "mule_transactions": mule_scenario()}
    if preset == "Fraud-ring investigation":
        return {"invoices_raw": [RetailSimulator.supplier_invoice(scenario="CLEAN")],
                "mule_transactions": mule_scenario()}
    if preset == "Data-quality quarantine":
        return {"sales_raw": [RetailSimulator.sales_record("NEGATIVE_UNITS")],
                "invoices_raw": [RetailSimulator.supplier_invoice(scenario="CHECKSUM_TAMPERED")]}
    if preset == "Clean operations run":
        return {"sales_raw": [RetailSimulator.sales_record("CLEAN") for _ in range(4)],
                "inventory_raw": [RetailSimulator.inventory_snapshot(sku="SKU_RICE", store="STORE_01", on_hand=55, reorder_point=20)],
                "invoices_raw": [RetailSimulator.supplier_invoice(scenario="CLEAN")]}
    return {"sales_raw": [], "inventory_raw": [], "invoices_raw": []}


def run_scenario(preset):
    state = run_supervised(scenario(preset), memory=seed_regulatory(Memory()))
    state["run_id"] = "RUN_" + uuid.uuid4().hex[:10]
    state["preset"] = preset
    return state


def plain_alerts(state):
    alerts = []
    for flag in state.get("payment_flags", []):
        if flag.get("flag_type") != "CLEAN":
            alerts.append({"alert_id": "ALERT_" + flag["invoice_id"], "title": "Invoice needs review",
                           "summary": flag["description"], "alert_type": flag["flag_type"],
                           "severity": "HIGH", "subject_id": flag["invoice_id"]})
    for ring in state.get("mule_rings", []):
        alerts.append({"alert_id": "ALERT_" + ring["ring_id"],
                       "title": "Suspicious payment network", "summary":
                       f"A {ring['pattern_type']} pattern connects {len(ring['member_accounts'])} accounts.",
                       "alert_type": ring["pattern_type"], "severity":
                       "HIGH" if ring["risk_score"] >= 60 else "MEDIUM", "subject_id": ring["ring_id"]})
    return alerts
