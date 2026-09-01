# PayGuard-AgentX Demo Runbook

## Setup

```powershell
cd C:\Users\Siddharth\Desktop\AgenticAIproject
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:PAYGUARD_AUDIT_KEY = "replace-with-a-long-private-demo-secret"
```

Optional live backends:

```powershell
pip install -r requirements-live.txt
python scripts\smoke_live.py
```

## Run order

```powershell
pytest -q
python main.py
python evaluation\run_eval.py
python -m streamlit run dashboard\app.py
```

## Walkthrough

1. Keep the default scenario toggles enabled and click **Run pipeline**.
2. In **Overview**, show the full route, suspicious accounts, fraud rings, and dossier count.
3. In **Pipeline**, show rejected negative-unit and checksum-tampered records.
4. Show the PO and dispute in the mandatory human approval queue.
5. Approve or reject one item. Confirm that its status, trace entry, and signed disposition dossier appear.
6. In **Fraud Network**, show the cycle and shell ring and the payroll false-positive control.
7. In **Evidence**, enable **Tamper with payload** and show verification changing from valid to invalid.

Approval records a human disposition only. The demo never sends a PO, transfers money, or calls an external supplier.

## Expected CLI evidence

- route: `full`
- negative sales and checksum-tampered invoice quarantined
- PO estimate around `170 USD`
- invoice/PO mismatch detected (`999` versus `170`)
- regulatory clause `REG_PO_MATCH` cited
- cycle risk around `70`; shell-network risk around `45`
- payroll account not flagged
- all original and disposition dossiers verify before tampering

## Submission checklist

- Run the complete command sequence on the demo laptop.
- Capture screenshots of all four dashboard tabs.
- Record Python and package versions.
- Use a private `PAYGUARD_AUDIT_KEY`.
- Keep synthetic-data and no-payment limitations in the presentation.
- Do not claim production, PCI, or regulatory certification.
