"""
PayGuardDQ Data Quality Middleware Engine

Deterministic field validation & payload integrity verification (0 LLM tokens consumed).
In PayGuard-AgentX this engine is used as a TOOL that the DQ-Sentinel agent calls to
gate every inbound record — retail sales, inventory snapshots, and supplier invoices —
before any downstream agent is allowed to reason over it.

Backward compatibility: validate_payload() and the financial TransactionPayload path are
unchanged so the original tests keep passing.
"""

import hashlib
import json
from typing import Tuple, Optional
from src.models.schemas import (
    TransactionPayload,
    AnomalyDiagnosis,
    SalesRecord,
    InventorySnapshot,
    SupplierInvoice,
)

SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "INR", "JPY", "CAD", "AUD"}


class PayGuardDQEngine:
    """Deterministic data quality validation engine."""

    SUPPORTED_CURRENCIES = SUPPORTED_CURRENCIES

    # ---- Legacy financial transaction path (unchanged) ----
    @staticmethod
    def validate_payload(raw_json: str) -> Tuple[bool, AnomalyDiagnosis, TransactionPayload | None]:
        try:
            data = json.loads(raw_json)
            payload = TransactionPayload(**data)
        except json.JSONDecodeError as e:
            return False, AnomalyDiagnosis(
                transaction_id="UNKNOWN", anomaly_type="DATA_CORRUPTION", severity="HIGH",
                description=f"JSON Decode Failure: {str(e)}", recommended_agent="SelfHealing-RepairAgent",
            ), None
        except Exception as e:
            return False, AnomalyDiagnosis(
                transaction_id=data.get("transaction_id", "UNKNOWN") if isinstance(data, dict) else "UNKNOWN",
                anomaly_type="DATA_CORRUPTION", severity="HIGH",
                description=f"Schema Validation Failure: {str(e)}", recommended_agent="SelfHealing-RepairAgent",
            ), None

        if payload.amount <= 0:
            return False, AnomalyDiagnosis(
                transaction_id=payload.transaction_id, anomaly_type="DATA_CORRUPTION", severity="CRITICAL",
                description=f"Non-positive transaction amount: {payload.amount}", recommended_agent="DQ-SentinelAgent",
            ), payload
        if payload.currency.upper() not in SUPPORTED_CURRENCIES:
            return False, AnomalyDiagnosis(
                transaction_id=payload.transaction_id, anomaly_type="DATA_CORRUPTION", severity="MEDIUM",
                description=f"Unsupported currency code: {payload.currency}", recommended_agent="DQ-SentinelAgent",
            ), payload
        if payload.checksum:
            computed_hash = hashlib.sha256(payload.payload_raw.encode('utf-8')).hexdigest()
            if computed_hash != payload.checksum:
                return False, AnomalyDiagnosis(
                    transaction_id=payload.transaction_id, anomaly_type="DATA_CORRUPTION", severity="CRITICAL",
                    description=f"Checksum mismatch! Computed {computed_hash[:8]} vs Provided {payload.checksum[:8]}",
                    recommended_agent="Forensic-InvestigatorAgent",
                ), payload
        return True, AnomalyDiagnosis(
            transaction_id=payload.transaction_id, anomaly_type="CLEAN", severity="NONE",
            description="Payload passed all deterministic data quality checks.", recommended_agent=None,
        ), payload

    # ---- Retail sales record path ----
    @staticmethod
    def validate_sales_record(raw_json: str) -> Tuple[bool, str, Optional[SalesRecord]]:
        try:
            record = SalesRecord(**json.loads(raw_json))
        except json.JSONDecodeError as e:
            return False, f"JSON decode failure: {e}", None
        except Exception as e:
            return False, f"Schema validation failure: {e}", None
        if record.units_sold <= 0:
            return False, f"Non-positive units_sold: {record.units_sold}", record
        if record.unit_price <= 0:
            return False, f"Non-positive unit_price: {record.unit_price}", record
        if record.currency.upper() not in SUPPORTED_CURRENCIES:
            return False, f"Unsupported currency: {record.currency}", record
        return True, "Sales record passed DQ checks.", record

    # ---- Inventory snapshot path ----
    @staticmethod
    def validate_inventory_snapshot(raw_json: str) -> Tuple[bool, str, Optional[InventorySnapshot]]:
        try:
            record = InventorySnapshot(**json.loads(raw_json))
        except json.JSONDecodeError as e:
            return False, f"JSON decode failure: {e}", None
        except Exception as e:
            return False, f"Schema validation failure: {e}", None
        if record.on_hand < 0:
            return False, f"Negative on_hand: {record.on_hand}", record
        if record.reorder_point < 0:
            return False, f"Negative reorder_point: {record.reorder_point}", record
        return True, "Inventory snapshot passed DQ checks.", record

    # ---- Supplier invoice path (PayGuard integrity lineage) ----
    @staticmethod
    def validate_supplier_invoice(raw_json: str) -> Tuple[bool, str, Optional[SupplierInvoice]]:
        try:
            invoice = SupplierInvoice(**json.loads(raw_json))
        except json.JSONDecodeError as e:
            return False, f"JSON decode failure: {e}", None
        except Exception as e:
            return False, f"Schema validation failure: {e}", None
        if invoice.amount <= 0:
            return False, f"Non-positive invoice amount: {invoice.amount}", invoice
        if invoice.currency.upper() not in SUPPORTED_CURRENCIES:
            return False, f"Unsupported currency: {invoice.currency}", invoice
        if invoice.checksum:
            computed = hashlib.sha256(invoice.payload_raw.encode('utf-8')).hexdigest()
            if computed != invoice.checksum:
                return False, f"Checksum mismatch: computed {computed[:8]} vs provided {invoice.checksum[:8]}", invoice
        return True, "Supplier invoice passed DQ checks.", invoice
