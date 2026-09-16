import os

from dotenv import load_dotenv
from algosdk import account, mnemonic
from algosdk.transaction import AssetTransferTxn, wait_for_confirmation
from algosdk.v2client.algod import AlgodClient

load_dotenv()

ALGOD_URL = os.getenv("ALGOD_URL")
MNEMONIC = os.getenv("AVM_MNEMONIC")
ASSET_ID = int(os.getenv("USDC_ASSET_ID"))
ESCROW = os.getenv("ESCROW_ADDRESS")

# 0.50 USDC because USDC has 6 decimals
AMOUNT = 500_000

algod = AlgodClient("", ALGOD_URL)

private_key = mnemonic.to_private_key(MNEMONIC)
sender = account.address_from_private_key(private_key)

print("========================================")
print("CargoProof USDC Escrow Deposit")
print("========================================")
print("Sender :", sender)
print("Escrow :", ESCROW)
print("Asset  :", ASSET_ID)
print("Amount :", AMOUNT, "base units")
print("USDC   :", AMOUNT / 1_000_000)
print()

params = algod.suggested_params()

txn = AssetTransferTxn(
    sender=sender,
    sp=params,
    receiver=ESCROW,
    amt=AMOUNT,
    index=ASSET_ID,
)

signed_txn = txn.sign(private_key)

print("Submitting USDC transfer...")

txid = algod.send_transaction(signed_txn)

print("Transaction ID:", txid)
print("Waiting for confirmation...")

confirmed = wait_for_confirmation(algod, txid, 4)

print("Confirmed round:", confirmed["confirmed-round"])
print()
print("DEPOSIT SUCCESSFUL")