"""
Synthetic retail + procurement stream generator for ShelfGuard-AgentX.

Produces clean and deliberately-broken JSON records for the three inbound streams
the DQ-Sentinel guards: POS sales, inventory snapshots, and supplier invoices.
"""

import json
import time
import random
import hashlib
from datetime import datetime, timezone

SKUS = ["SKU_APPLE", "SKU_MILK", "SKU_BREAD", "SKU_EGGS", "SKU_RICE"]
STORES = ["STORE_01", "STORE_02"]
CURRENCIES_OK = ["USD", "EUR", "INR"]


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rid(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{random.randint(100, 999)}"


class RetailSimulator:

    @staticmethod
    def sales_record(scenario: str = "CLEAN") -> str:
        rec = {
            "record_id": _rid("SALE"),
            "sku": random.choice(SKUS),
            "store_id": random.choice(STORES),
            "units_sold": random.randint(1, 25),
            "unit_price": round(random.uniform(1.0, 50.0), 2),
            "currency": random.choice(CURRENCIES_OK),
            "timestamp": _ts(),
        }
        if scenario == "NEGATIVE_UNITS":
            rec["units_sold"] = -3
        elif scenario == "BAD_CURRENCY":
            rec["currency"] = "BAD"
        elif scenario == "CORRUPTED_JSON":
            return '{"record_id": "SALE_x", "sku": "SKU_MILK", '
        return json.dumps(rec)

    @staticmethod
    def inventory_snapshot(sku=None, store=None, on_hand=None, reorder_point=None) -> str:
        rec = {
            "record_id": _rid("INV"),
            "sku": sku or random.choice(SKUS),
            "store_id": store or random.choice(STORES),
            "on_hand": on_hand if on_hand is not None else random.randint(0, 60),
            "reorder_point": reorder_point if reorder_point is not None else 20,
            "timestamp": _ts(),
        }
        return json.dumps(rec)

    @staticmethod
    def supplier_invoice(po_id=None, sku=None, amount=None, scenario: str = "CLEAN") -> str:
        sku = sku or random.choice(SKUS)
        amount = amount if amount is not None else round(random.uniform(50.0, 500.0), 2)
        raw = f"INV::{sku}::{amount}"
        inv = {
            "invoice_id": _rid("INVOICE"),
            "supplier_id": random.choice(["SUP_A", "SUP_B"]),
            "po_id": po_id,
            "sku": sku,
            "amount": amount,
            "currency": "USD",
            "timestamp": _ts(),
            "payload_raw": raw,
            "checksum": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        }
        if scenario == "CHECKSUM_TAMPERED":
            inv["checksum"] = "deadbeef_bad_checksum_value"
        elif scenario == "NEGATIVE_AMOUNT":
            inv["amount"] = -10.0
        elif scenario == "CORRUPTED_JSON":
            return '{"invoice_id": "INVOICE_x", "amount": 10.0, '
        return json.dumps(inv)
