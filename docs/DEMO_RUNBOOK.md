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
python -m web.server
```

Then open **http://127.0.0.1:8000**. The dashboard is plain HTML/CSS/JS served by
the Python standard library: nothing to install, nothing to build, no network.

## Walkthrough

1. Open the dashboard. The header states what PayGuard-AgentX does; the sidebar
   **System status** shows every subsystem and that the LLM is the offline stub.
2. Scenario **2 · Suspicious Invoice** → **Run demo**.
3. **Action Inbox**: a HIGH invoice dispute (supplier, amount, confidence) and a
   MEDIUM restock purchase order. Expand **Why this was flagged** — the 487% PO
   deviation, the duplicate billing, and the cited clause `REG_PO_MATCH`.
4. **Agent System**: open this page and explain the ten visible roles. The
   supervisor selects the route, specialist agents call deterministic tools,
   critics review drafts, and the HITL controller stops consequential actions.
   Emphasize that approval records a signed human decision only.
5. **Operations**: low stock, the drafted order and its rationale, the invoice
   checks, and the records quarantined at the gate.
6. Back in **Action Inbox**, **Approve** one item. The decision is signed and the
   item leaves the queue.
7. Scenario **3 · Fraud Ring** → **Run demo**. The timeline now shows six agents
   **skipped** — the supervisor took route `ring_only`. This is the clearest
   demonstration of dynamic routing.
8. **Analyst Workspace**: the closed loop `SUP_A → SUP_B → SUP_C → back to SUP_A`,
   risk 70/100, the per-account signals, and the payroll false-positive control.
9. **Cases**: the investigation records. **Evidence**: signed dossiers; use
   **Demo: tamper with payload** to show verification flip to INVALID.
10. **Settings**: switch the demo role to `VIEWER` and show the decision buttons
    disable — the server rejects the call too, not just the browser.

11. **Persistence check**: decide one item, refresh the page, and reopen the
    Action Inbox. The decision and audit event remain because the workspace is
    stored in SQLite rather than only in browser/session memory.

Select **Reset** to return any scenario to a clean queue.

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
- Capture screenshots of Action Inbox, Operations, Analyst Workspace, Cases, and
  Evidence (save the Action Inbox one as `docs/screenshot.png` and uncomment the
  image line at the top of the README).
- Record Python and package versions.
- Use a private `PAYGUARD_AUDIT_KEY`.
- Keep synthetic-data and no-payment limitations in the presentation.
- Do not claim production, PCI, or regulatory certification.
