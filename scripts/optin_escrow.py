import os
import base64

from dotenv import load_dotenv
from algosdk import account, mnemonic
from algosdk.transaction import ApplicationOptInTxn, wait_for_confirmation
from algosdk.v2client.algod import AlgodClient

load_dotenv()

ALGOD_URL = os.getenv("ALGOD_URL")
MNEMONIC = os.getenv("AVM_MNEMONIC")
APP_ID = int(os.getenv("ESCROW_APP_ID"))
ASSET_ID = int(os.getenv("USDC_ASSET_ID"))

algod = AlgodClient("", ALGOD_URL)

private_key = mnemonic.to_private_key(MNEMONIC)
sender = account.address_from_private_key(private_key)

print("Verifier:", sender)
print("App ID:", APP_ID)
print("USDC:", ASSET_ID)

params = algod.suggested_params()

txn = ApplicationOptInTxn(
    sender=sender,
    sp=params,
    index=APP_ID,
    app_args=[b"optin"],
    foreign_assets=[ASSET_ID],
)
signed = txn.sign(private_key)

print("Submitting escrow opt-in...")
txid = algod.send_transaction(signed)

print("Transaction:", txid)
confirmed = wait_for_confirmation(algod, txid, 4)

print("Confirmed in round:", confirmed["confirmed-round"])
print("Escrow opt-in transaction successful.")