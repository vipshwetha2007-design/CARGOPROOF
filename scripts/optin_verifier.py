import os
from dotenv import load_dotenv
from algosdk import account, mnemonic
from algosdk.transaction import AssetTransferTxn, wait_for_confirmation
from algosdk.v2client.algod import AlgodClient

load_dotenv()

ALGOD_URL = os.getenv("ALGOD_URL")
MNEMONIC = os.getenv("AVM_MNEMONIC")
ASSET_ID = int(os.getenv("USDC_ASSET_ID"))

algod = AlgodClient("", ALGOD_URL)

private_key = mnemonic.to_private_key(MNEMONIC)
address = account.address_from_private_key(private_key)

params = algod.suggested_params()

txn = AssetTransferTxn(
    sender=address,
    sp=params,
    receiver=address,
    amt=0,
    index=ASSET_ID,
)

signed = txn.sign(private_key)

print("Verifier:", address)
print("USDC ASA:", ASSET_ID)
print("Submitting USDC opt-in...")

txid = algod.send_transaction(signed)

print("Transaction:", txid)

confirmed = wait_for_confirmation(algod, txid, 4)

print("Confirmed round:", confirmed["confirmed-round"])
print("Verifier USDC opt-in successful.")