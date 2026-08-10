"""Money-muling network-fraud detection for PayGuard-AgentX.

Pure-stdlib, deterministic graph detectors ported from the FinForensics core idea
and reframed for procurement collusion (see docs/MULE_DETECTION.md):
  - cycle_detector      circular billing rings
  - smurfing_detector   invoice structuring / fan-in-out
  - shell_detector      pass-through shell suppliers
  - suppressor          payroll / merchant / exchange false-positive filter
  - scorer              multi-signal suspicion score + Union-Find ring grouping
Everything runs offline with no heavy dependencies, matching the project's
deterministic-tool + tested-fallback discipline.
"""
