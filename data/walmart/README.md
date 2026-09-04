# Public Walmart data

The optional `5 · Walmart Historical Sales` demo uses the public Walmart Store
Sales Forecasting dataset: weekly sales by store and department, plus store and
regional features. The CSV files are downloaded locally and are not committed
to this repository because `train.csv` is large.

From the repository root:

```powershell
python scripts\download_walmart_data.py
```

This is historical public data, not a Walmart production feed. The dataset has
no on-hand inventory, supplier invoices, purchase orders, or payment graph. The
adapter therefore derives a clearly labeled stock baseline from recent sales so
the retail agents can recommend replenishment. Fraud-ring demonstrations remain
seeded test transactions and must not be described as Walmart fraud data.
