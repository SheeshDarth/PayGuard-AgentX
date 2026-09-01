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

1. Open **Action Inbox**; keep **Procurement mismatch** selected and click **Run analysis**.
2. Show the four completion steps, then open **Operations** to explain low stock, the suggested order, and the invoice mismatch.
3. Return to **Action Inbox** and show the PO/dispute cards. Approve or reject one item; confirm the state persists after navigation or rerun.
4. Select **Fraud-ring investigation**, run it, then open **Analyst Workspace** to show the plain-language alert before the technical network details.
5. Open **Cases** to show the investigation record and **Evidence** to show signed dossiers and verification status.
6. Under **Demo tools**, enable tampering and show verification changing from valid to invalid.
7. Open **Settings** to explain demo mode, SQLite fallback, and the no-external-execution guarantee.

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
- Capture screenshots of Action Inbox, Operations, Analyst Workspace, Cases, and Evidence.
- Record Python and package versions.
- Use a private `PAYGUARD_AUDIT_KEY`.
- Keep synthetic-data and no-payment limitations in the presentation.
- Do not claim production, PCI, or regulatory certification.
