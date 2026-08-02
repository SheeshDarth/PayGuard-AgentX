"""
Synthetic Payment Stream Simulator
Generates clean, corrupted, fraudulent, and non-compliant payment streams for testing.
"""

import json
import time
import random
import hashlib
from datetime import datetime

class StreamSimulator:
    
    SAMPLE_ACCOUNTS = [f"ACC_{1000 + i}" for i in range(10)]
    CURRENCIES = ["USD", "EUR", "INR", "GBP", "BAD_CURR"]

    @staticmethod
    def generate_sample_transaction(scenario: str = "CLEAN") -> str:
        tx_id = f"TXN_{int(time.time() * 1000)}_{random.randint(100, 999)}"
        sender = random.choice(StreamSimulator.SAMPLE_ACCOUNTS)
        receiver = random.choice([acc for acc in StreamSimulator.SAMPLE_ACCOUNTS if acc != sender])
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        if scenario == "CLEAN":
            amount = round(random.uniform(10.0, 5000.0), 2)
            currency = random.choice(["USD", "EUR", "INR"])
            raw = f"TXN::{tx_id}::{amount}::{currency}"
            checksum = hashlib.sha256(raw.encode('utf-8')).hexdigest()
            return json.dumps({
                "transaction_id": tx_id,
                "sender_account": sender,
                "receiver_account": receiver,
                "amount": amount,
                "currency": currency,
                "timestamp": timestamp,
                "payload_raw": raw,
                "checksum": checksum
            })

        elif scenario == "CORRUPTED_JSON":
            # Syntax error in JSON payload
            return f'{{"transaction_id": "{tx_id}", "sender_account": "{sender}", "amount": 150.0, '

        elif scenario == "INVALID_AMOUNT":
            raw = f"TXN::{tx_id}::-500.00::USD"
            return json.dumps({
                "transaction_id": tx_id,
                "sender_account": sender,
                "receiver_account": receiver,
                "amount": -500.00,
                "currency": "USD",
                "timestamp": timestamp,
                "payload_raw": raw,
                "checksum": None
            })

        elif scenario == "CHECKSUM_TAMPERED":
            raw = f"TXN::{tx_id}::10000.00::USD"
            return json.dumps({
                "transaction_id": tx_id,
                "sender_account": sender,
                "receiver_account": receiver,
                "amount": 10000.00,
                "currency": "USD",
                "timestamp": timestamp,
                "payload_raw": raw,
                "checksum": "faked_bad_checksum_hash_value"
            })

        return StreamSimulator.generate_sample_transaction("CLEAN")
