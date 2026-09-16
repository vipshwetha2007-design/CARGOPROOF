import os
import hashlib

from dotenv import load_dotenv
from algosdk import account, mnemonic
from algosdk.transaction import (
    ApplicationNoOpTxn,
    wait_for_confirmation,
)
from algosdk.v2client.algod import AlgodClient

load_dotenv()

ALGOD_URL = os.getenv("ALGOD_URL")
MNEMONIC = os.getenv("AVM_MNEMONIC")
APP_ID = int(os.getenv("ESCROW_APP_ID"))
ASSET_ID = int(os.getenv("USDC_ASSET_ID"))

algod = AlgodClient("", ALGOD_URL)

private_key = mnemonic.to_private_key(MNEMONIC)
sender = account.address_from_private_key(private_key)

# ------------------------------------------------------------
# Demo shipment evidence
# In the real system this will be generated from verified
# vessel/container/port evidence.
# ------------------------------------------------------------

evidence = """
CargoProof shipment verification

Vessel: Vessel XYZ
Container: ABC123
Origin: Chennai Port
Destination: Singapore
Status: IN_TRANSIT
Verification: PASS
"""

evidence_hash = hashlib.sha256(
    evidence.strip().encode()
).digest()

AMOUNT = 500_000  # 0.50 USDC

print("========================================")
print("CargoProof Evidence Submission")
print("========================================")
print("Sender :", sender)
print("App ID :", APP_ID)
print("USDC   :", ASSET_ID)
print("Amount :", AMOUNT)
print()
print("Evidence:")
print(evidence.strip())
print()
print("SHA-256:", evidence_hash.hex())

params = algod.suggested_params()

txn = ApplicationNoOpTxn(
    sender=sender,
    sp=params,
    index=APP_ID,
    app_args=[
        b"evidence",
        evidence_hash,
        AMOUNT.to_bytes(8, "big"),
    ],
    foreign_assets=[ASSET_ID],
)

signed_txn = txn.sign(private_key)

print()
print("Submitting evidence transaction...")

txid = algod.send_transaction(signed_txn)

print("Transaction ID:", txid)
print("Waiting for confirmation...")

confirmed = wait_for_confirmation(algod, txid, 4)

print("Confirmed round:", confirmed["confirmed-round"])
print()
print("EVIDENCE SUBMISSION SUCCESSFUL")