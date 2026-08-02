"""
PayGuardDQ Data Quality Middleware Engine
Performs deterministic field validation & payload integrity verification (0 LLM tokens consumed).
"""

import hashlib
import json
from typing import Tuple
from src.models.schemas import TransactionPayload, AnomalyDiagnosis

class PayGuardDQEngine:
    """
    Deterministic data quality validation engine.
    Checks required fields, currency bounds, checksums, and syntax errors.
    """
    
    SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "INR", "JPY", "CAD", "AUD"}

    @staticmethod
    def validate_payload(raw_json: str) -> Tuple[bool, AnomalyDiagnosis, TransactionPayload | None]:
        try:
            data = json.loads(raw_json)
            payload = TransactionPayload(**data)
        except json.JSONDecodeError as e:
            return False, AnomalyDiagnosis(
                transaction_id="UNKNOWN",
                anomaly_type="DATA_CORRUPTION",
                severity="HIGH",
                description=f"JSON Decode Failure: {str(e)}",
                recommended_agent="SelfHealing-RepairAgent"
            ), None
        except Exception as e:
            return False, AnomalyDiagnosis(
                transaction_id=data.get("transaction_id", "UNKNOWN") if isinstance(data, dict) else "UNKNOWN",
                anomaly_type="DATA_CORRUPTION",
                severity="HIGH",
                description=f"Schema Validation Failure: {str(e)}",
                recommended_agent="SelfHealing-RepairAgent"
            ), None

        # Check Amount bounds
        if payload.amount <= 0:
            return False, AnomalyDiagnosis(
                transaction_id=payload.transaction_id,
                anomaly_type="DATA_CORRUPTION",
                severity="CRITICAL",
                description=f"Non-positive transaction amount: {payload.amount}",
                recommended_agent="DQ-SentinelAgent"
            ), payload

        # Check Currency validity
        if payload.currency.upper() not in PayGuardDQEngine.SUPPORTED_CURRENCIES:
            return False, AnomalyDiagnosis(
                transaction_id=payload.transaction_id,
                anomaly_type="DATA_CORRUPTION",
                severity="MEDIUM",
                description=f"Unsupported currency code: {payload.currency}",
                recommended_agent="DQ-SentinelAgent"
            ), payload

        # Check Checksum if provided
        if payload.checksum:
            computed_hash = hashlib.sha256(payload.payload_raw.encode('utf-8')).hexdigest()
            if computed_hash != payload.checksum:
                return False, AnomalyDiagnosis(
                    transaction_id=payload.transaction_id,
                    anomaly_type="DATA_CORRUPTION",
                    severity="CRITICAL",
                    description=f"Checksum mismatch! Computed {computed_hash[:8]} vs Provided {payload.checksum[:8]}",
                    recommended_agent="Forensic-InvestigatorAgent"
                ), payload

        # Payload is clean
        return True, AnomalyDiagnosis(
            transaction_id=payload.transaction_id,
            anomaly_type="CLEAN",
            severity="NONE",
            description="Payload passed all deterministic data quality checks.",
            recommended_agent=None
        ), payload
