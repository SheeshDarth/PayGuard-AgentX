import csv

from src.utils.walmart_dataset import load_records


def test_walmart_adapter_converts_public_sales_to_restock_inputs(tmp_path):
    root = tmp_path / "walmart"
    root.mkdir()
    with (root / "stores.csv").open("w", newline="") as handle:
        handle.write("Store,Type,Size\n1,A,1000\n")
    with (root / "train.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Store", "Dept", "Date", "Weekly_Sales"])
        writer.writeheader()
        for week, amount in enumerate((1000, 1200, 1100), start=1):
            writer.writerow({"Store": "1", "Dept": "92", "Date": f"2012-01-0{week}", "Weekly_Sales": amount})
    result = load_records(root, pair_limit=1, weeks=12)
    assert result["dataset_label"] == "Public Walmart Store Sales Forecasting"
    assert len(result["sales_raw"]) == 3
    assert len(result["inventory_raw"]) == 1
