"""
PayGuard-AgentX — Main Entry Point
"""

import sys
from src.core.dq_engine import PayGuardDQEngine
from src.utils.stream_simulator import StreamSimulator

def main():
    print("=" * 70)
    print("PayGuard-AgentX -- Financial Data Quality & Agentic Engine")
    print("=" * 70)
    
    scenarios = ["CLEAN", "CORRUPTED_JSON", "INVALID_AMOUNT", "CHECKSUM_TAMPERED"]
    
    print("\nRunning Ingestion Stream Simulator Test...\n")
    for scenario in scenarios:
        print(f"--- Scenario: {scenario} ---")
        raw = StreamSimulator.generate_sample_transaction(scenario)
        print(f"Raw Input: {raw[:90]}...")
        
        is_valid, diagnosis, payload = PayGuardDQEngine.validate_payload(raw)
        print(f"Passed DQ: {is_valid}")
        print(f"Diagnosis: [{diagnosis.anomaly_type}] Severity: {diagnosis.severity}")
        print(f"Details:   {diagnosis.description}")
        if diagnosis.recommended_agent:
            print(f"Routing to Agent: {diagnosis.recommended_agent}")
        print("-" * 70 + "\n")

if __name__ == "__main__":
    main()
