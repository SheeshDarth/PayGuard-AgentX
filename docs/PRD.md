# 📑 Product Requirements Document (PRD) — PayGuard-AgentX

> **Project Name:** `PayGuard-AgentX`  
> **Version:** 1.0  
> **Author:** Siddharth ([github.com/SheeshDarth](https://github.com/SheeshDarth))  

---

## 1. Vision & Core Value Proposition

`PayGuard-AgentX` is an enterprise multi-agent platform designed to monitor, audit, and self-heal financial payment pipelines in real time. It reduces payment data processing errors, flags temporal fraud velocity, and automates chargeback dispute arbitration.

---

## 2. Target Personas

1. **Financial Fraud Analyst:** Needs real-time anomaly scores and temporal velocity tracking.
2. **Compliance Officer:** Needs instant regulatory clause citations (PCI-DSS, AML, FATF) attached to flagged payloads.
3. **Data/DevOps Engineer:** Requires automated self-healing patches when payment APIs drift or break.

---

## 3. Product Features & Scope

### Feature Group 1: Data Ingestion & Sanitization (`PayGuardDQ`)
- Real-time JSON/XML payment payload validation.
- Deterministic checks for missing keys, malformed timestamps, out-of-bound amounts, and currency mismatches.

### Feature Group 2: Agentic Anomaly Triage (`DQ-SentinelAgent`)
- Autonomous classification of anomalies: `DATA_CORRUPTION`, `FRAUD_VELOCITY`, or `REGULATORY_VIOLATION`.
- State-graph routing to specialized worker agents.

### Feature Group 3: Temporal Velocity Forensics (`OriginX-T Lite`)
- 30-day and 90-day velocity metrics per account.
- Detection of sleeper account activation and volume spikes.

### Feature Group 4: Regulatory Policy RAG (`NirmiqResearchOS RAG`)
- ChromaDB vector store containing banking regulations (PCI-DSS 4.0, AML directives).
- Automatic citation extraction for non-compliant transactions.

### Feature Group 5: Self-Healing Code Repair (`NirmiqCodeSensei AST`)
- AST inspection of broken payload structures.
- Sandboxed Python patch generation and execution test loop.

### Feature Group 6: Autonomous Dispute Settlement & Evidence Engine
- Two-agent chargeback arbitration (Merchant Agent vs Bank Agent).
- SHA-256 cryptographically signed PDF/Markdown evidence dossiers.

### Feature Group 7: Incident War-Room Dashboard
- Real-time Streamlit web interface with live streaming ticker, agent thought logs, and Human-in-the-Loop overrides.
