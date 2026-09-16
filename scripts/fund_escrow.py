import os
from dotenv import load_dotenv

from algosdk import mnemonic, account
from algosdk.transaction import PaymentTxn, wait_for_confirmation
from algosdk.v2client.algod import AlgodClient

load_dotenv()

ALGOD_URL = os.getenv("ALGOD_URL")
MNEMONIC = os.getenv("AVM_MNEMONIC")
ESCROW = os.getenv("ESCROW_ADDRESS")

algod = AlgodClient("", ALGOD_URL)

private_key = mnemonic.to_private_key(MNEMONIC)
sender = account.address_from_private_key(private_key)

amount = 1_000_000  # 1 ALGO

params = algod.suggested_params()

txn = PaymentTxn(
    sender=sender,
    sp=params,
    receiver=ESCROW,
    amt=amount,
)

signed = txn.sign(private_key)

print("Sender :", sender)
print("Escrow :", ESCROW)
print("Amount : 1 ALGO")
print()
print("Funding escrow...")

txid = algod.send_transaction(signed)

print("Transaction:", txid)
print("Waiting for confirmation...")

confirmed = wait_for_confirmation(algod, txid, 4)

print("Confirmed round:", confirmed["confirmed-round"])
print()
print("ESCROW FUNDING SUCCESSFUL")