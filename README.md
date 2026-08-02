# 🛡️ PayGuard-AgentX

> **Enterprise Autonomous Multi-Agent Financial Data Quality, Forensic Fraud Auditing & Regulatory Settlement Platform**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Agentic Framework](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Executive Summary

`PayGuard-AgentX` is a next-generation autonomous multi-agent system built to secure, audit, and self-heal modern financial payment data pipelines (ISO 20022, SWIFT, and REST payment gateways). 

By fusing selective core capabilities from past engineering foundations (**`PayGuardDQ`**, **`OriginX-T`**, **`NirmiqResearchOS`**, and **`NirmiqCodeSensei`**), `PayGuard-AgentX` bridges the gap between static data validation rules and dynamic AI-driven reasoning.

---

## 🏗️ Multi-Agent Architecture

```
                    ┌────────────────────────────────────────────────────────┐
                    │            Live Streaming Payment Gateway Ingestion     │
                    └───────────────────────────┬────────────────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ MODULE 1: Streaming Data Quality Ingestion (PayGuardDQ Engine Middleware)                     │
│ • Validates ISO 20022 / SWIFT payload integrity & schema drift in real-time                  │
└───────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ MODULE 2: Multi-Agent Intelligence Core (LangGraph Orchestrator)                             │
│                                                                                              │
│   ┌────────────────────────┐    ┌─────────────────────────┐    ┌─────────────────────────┐   │
│   │ DQ-SentinelAgent       │    │ Forensic-Investigator   │    │ Regulatory-Auditor      │   │
│   │ (Anomaly Filtering)    │    │ (OriginX-T Temporal)    │    │ (NirmiqResearchOS RAG)  │   │
│   └───────────┬────────────┘    └────────────┬────────────┘    └────────────┬────────────┘   │
│               │                              │                              │                │
│               └──────────────────────────────┼──────────────────────────────┘                │
│                                              ▼                                               │
│                                 ┌─────────────────────────┐                                  │
│                                 │ SelfHealing-Repair Agent│                                  │
│                                 │ (NirmiqCodeSensei AST)  │                                  │
│                                 └─────────────────────────┘                                  │
└───────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ MODULE 3: Autonomous Dispute Settlement & Evidence Engine                                    │
│ • Simulates merchant-bank chargeback arbitration                                             │
│ • Generates cryptographically signed Audit Evidence Dossiers (SHA-256)                      │
└───────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ MODULE 4: Real-Time Incident War-Room Dashboard (Streamlit UI)                               │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Key Agent Roles

1. **`DQ-SentinelAgent`** (*PayGuardDQ Engine*): Real-time payload sanitization, format integrity validation, and anomaly classification.
2. **`Forensic-InvestigatorAgent`** (*OriginX-T Lite*): 30/90-day velocity tracking, sleeper account detection, and temporal drift scoring.
3. **`Regulatory-AuditorAgent`** (*NirmiqResearchOS RAG*): Vector search across PCI-DSS 4.0, AML, and ISO 20022 regulatory guidelines for instant clause citations.
4. **`SelfHealing-RepairAgent`** (*NirmiqCodeSensei AST*): Sandboxed AST parser that synthesizes Python patches for breaking payment API schemas.
5. **`Arbitration-DisputeAgent`**: Simulates chargeback arbitration between merchants and banks, producing cryptographically signed evidence dossiers.

---

## 📅 Implementation Roadmap (8 Weeks / 4 Phases)

- [x] **Phase 1: Foundation & Specs** — Repository structure, PRD/TRD documentation, schema definitions.
- [ ] **Phase 2: Core Ingestion & Sentinel Engine** (Weeks 1–2) — Stream simulator, PayGuardDQ middleware, DQ-Sentinel agent.
- [ ] **Phase 3: Forensics, RAG & Self-Healing** (Weeks 3–4) — Temporal risk engine, ChromaDB regulatory store, AST repair sandbox.
- [ ] **Phase 4: Dispute Settlement & War-Room UI** (Weeks 5–8) — Chargeback negotiation engine, SHA-256 evidence signing, Streamlit UI.

---

## 📄 Documentation

- [Product Requirements Document (PRD)](docs/PRD.md)
- [Technical Requirements Document (TRD)](docs/TRD.md)
- [Implementation Roadmap & Milestones](docs/ROADMAP.md)

---

## ⚡ Quick Start

```bash
# Clone repository
git clone https://github.com/SheeshDarth/PayGuard-AgentX.git
cd PayGuard-AgentX

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run main application
python main.py
```

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.
