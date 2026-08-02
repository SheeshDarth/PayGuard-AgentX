"""
Unit Tests for PayGuardDQ Engine Middleware
"""

from src.core.dq_engine import PayGuardDQEngine
from src.utils.stream_simulator import StreamSimulator

def test_clean_payload():
    raw_payload = StreamSimulator.generate_sample_transaction("CLEAN")
    is_valid, diagnosis, payload = PayGuardDQEngine.validate_payload(raw_payload)
    assert is_valid is True
    assert diagnosis.anomaly_type == "CLEAN"
    assert payload is not None

def test_corrupted_json_payload():
    raw_payload = StreamSimulator.generate_sample_transaction("CORRUPTED_JSON")
    is_valid, diagnosis, payload = PayGuardDQEngine.validate_payload(raw_payload)
    assert is_valid is False
    assert diagnosis.anomaly_type == "DATA_CORRUPTION"
    assert "JSON Decode Failure" in diagnosis.description

def test_invalid_amount_payload():
    raw_payload = StreamSimulator.generate_sample_transaction("INVALID_AMOUNT")
    is_valid, diagnosis, payload = PayGuardDQEngine.validate_payload(raw_payload)
    assert is_valid is False
    assert diagnosis.anomaly_type == "DATA_CORRUPTION"
    assert "Non-positive" in diagnosis.description

def test_checksum_tampered_payload():
    raw_payload = StreamSimulator.generate_sample_transaction("CHECKSUM_TAMPERED")
    is_valid, diagnosis, payload = PayGuardDQEngine.validate_payload(raw_payload)
    assert is_valid is False
    assert diagnosis.anomaly_type == "DATA_CORRUPTION"
    assert "Checksum mismatch" in diagnosis.description
