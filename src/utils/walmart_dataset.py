"""Adapter for the public Walmart Store Sales Forecasting dataset.

The source contains weekly sales by store and department. It does not contain
on-hand inventory or procurement documents, so this adapter derives a bounded
inventory baseline from recent demand and labels the result accordingly.
"""

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "walmart"

DEPARTMENT_NAMES = {
    "2": "Specialty Foods", "4": "Bakery", "8": "Seasonal",
    "9": "Outdoor Living", "13": "Fabrics & Crafts", "23": "Optical",
    "38": "Jewelry & Accessories", "40": "Pharmacy", "72": "Electronics",
    "90": "Dairy", "91": "Grocery", "92": "Dry Grocery",
    "93": "Frozen Foods", "94": "Produce", "95": "Grocery, Snacks & Beverages",
    "96": "HBA", "97": "Household", "79": "Health & Beauty",
}


def display_name(sku):
    """Return a business-readable label while retaining the source department ID."""
    dept = str(sku).replace("DEPT_", "")
    return f"Department {dept} - {DEPARTMENT_NAMES.get(dept, 'Retail merchandise')}"


def available(data_dir=DEFAULT_DIR):
    root = Path(data_dir)
    return (root / "train.csv").exists() and (root / "stores.csv").exists()


def load_records(data_dir=DEFAULT_DIR, pair_limit=300, weeks=12):
    """Return pipeline-compatible records from the real Walmart sales history.

    Weekly_Sales is converted to a transparent ``sales-equivalent`` unit using
    a $100 reference basket because the public file has revenue, not units.
    The latest 12 weeks for the most active store/department pairs are used to
    keep the offline demo responsive.
    """
    root = Path(data_dir)
    if not available(root):
        raise FileNotFoundError("Walmart data missing: expected train.csv and stores.csv in " + str(root))

    history = defaultdict(list)
    with (root / "train.csv").open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            try:
                when = datetime.strptime(row["Date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                sales = float(row["Weekly_Sales"])
                store, dept = row["Store"].strip(), row["Dept"].strip()
            except (KeyError, TypeError, ValueError):
                continue
            history[(store, dept)].append((when, sales))

    recent = {key: sorted(rows)[-weeks:] for key, rows in history.items()}
    ranked = sorted(recent.items(), key=lambda item: sum(v for _, v in item[1]), reverse=True)
    selected = ranked[:pair_limit]
    sales_raw, inventory_raw = [], []
    for index, ((store, dept), rows) in enumerate(selected, start=1):
        sku = f"DEPT_{dept}"
        item_name = display_name(f"DEPT_{dept}")
        store_id = f"WALMART_STORE_{store}"
        equivalents = [max(1, round(sales / 100.0)) for _, sales in rows]
        avg = max(1, round(sum(equivalents[-4:]) / min(4, len(equivalents))))
        on_hand = max(0, round(avg * 0.35))
        reorder = max(1, math.ceil(avg * 1.05))
        for week, units in zip(rows, equivalents):
            sales_raw.append(json.dumps({
                "record_id": f"WALMART_SALE_{index}_{week[0].strftime('%Y%m%d')}",
                "sku": sku, "store_id": store_id, "units_sold": units,
                "item_name": item_name,
                "unit_price": 100.0, "currency": "USD",
                "timestamp": week[0].isoformat(),
            }))
        inventory_raw.append(json.dumps({
            "record_id": f"WALMART_INV_{index}", "sku": sku, "store_id": store_id,
            "item_name": item_name,
            "on_hand": on_hand, "reorder_point": reorder,
            "timestamp": rows[-1][0].isoformat(),
        }))
    return {
        "sales_raw": sales_raw, "inventory_raw": inventory_raw,
        "dataset_label": "Public Walmart Store Sales Forecasting",
        "data_lineage": ("Real weekly sales by Walmart store/department; inventory is a "
                          "derived demo baseline because public data has no stock ledger."),
        "source_rows": len(sales_raw), "source_pairs": len(selected),
    }
