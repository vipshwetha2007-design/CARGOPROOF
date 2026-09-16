import base64
import os
from pathlib import Path
from dotenv import load_dotenv
from algosdk import account, mnemonic, encoding, logic
from algosdk.transaction import (
    ApplicationCreateTxn,
    StateSchema,
    OnComplete,
    wait_for_confirmation,
)
from algosdk.v2client.algod import AlgodClient

load_dotenv()

ALGOD_URL = os.getenv("ALGOD_URL")
MNEMONIC = os.getenv("AVM_MNEMONIC")
VERIFIER = os.getenv("VERIFIER_ADDRESS")
BENEFICIARY = os.getenv("BENEFICIARY_ADDRESS")
ASSET_ID = int(os.getenv("USDC_ASSET_ID", "10458941"))

if not MNEMONIC:
    raise SystemExit("ERROR: AVM_MNEMONIC is not configured in .env")

if not VERIFIER:
    raise SystemExit("ERROR: VERIFIER_ADDRESS is not configured")

if not BENEFICIARY:
    raise SystemExit("ERROR: BENEFICIARY_ADDRESS is not configured")

if not encoding.is_valid_address(VERIFIER):
    raise SystemExit("ERROR: Invalid VERIFIER_ADDRESS")

if not encoding.is_valid_address(BENEFICIARY):
    raise SystemExit("ERROR: Invalid BENEFICIARY_ADDRESS")

# ------------------------------------------------------------------
# Client / deployer
# ------------------------------------------------------------------

algod = AlgodClient("", ALGOD_URL)

private_key = mnemonic.to_private_key(MNEMONIC)
deployer = account.address_from_private_key(private_key)

print("========================================")
print("CargoProof Algorand TestNet Deployment")
print("========================================")
print("Deployer   :", deployer)
print("Verifier   :", VERIFIER)
print("Beneficiary:", BENEFICIARY)
print("USDC ASA   :", ASSET_ID)
print()

# Make sure the mnemonic corresponds to the expected verifier.
if deployer != VERIFIER:
    raise SystemExit(
        "ERROR: AVM_MNEMONIC does not belong to VERIFIER_ADDRESS.\n"
        f"Mnemonic address: {deployer}\n"
        f"Verifier address: {VERIFIER}"
    )

account_info = algod.account_info(deployer)

print("Deployer balance:",
      account_info["amount"] / 1_000_000,
      "ALGO")

if account_info["amount"] < 300_000:
    raise SystemExit(
        "ERROR: Deployer needs more ALGO for deployment."
    )

# ------------------------------------------------------------------
# Read compiled TEAL
# ------------------------------------------------------------------

approval_path = Path("contracts/build/approval.teal")
clear_path = Path("contracts/build/clear.teal")

if not approval_path.exists():
    raise SystemExit("ERROR: approval.teal not found. Compile the contract first.")

if not clear_path.exists():
    raise SystemExit("ERROR: clear.teal not found. Compile the contract first.")

approval_teal = approval_path.read_text()
clear_teal = clear_path.read_text()

print("Compiling approval program...")
approval_result = algod.compile(approval_teal)
approval_program = base64.b64decode(approval_result["result"])

print("Compiling clear program...")
clear_result = algod.compile(clear_teal)
clear_program = base64.b64decode(clear_result["result"])


# ------------------------------------------------------------------
# Application arguments
#
# approval():
#   Txn.application_args[1] = asset ID
#   Txn.application_args[2] = beneficiary
#   Txn.application_args[3] = verifier
# ------------------------------------------------------------------

app_args = [
    b"create",
    ASSET_ID.to_bytes(8, "big"),
    encoding.decode_address(BENEFICIARY),
    encoding.decode_address(VERIFIER),
]

# ------------------------------------------------------------------
# Create application
# ------------------------------------------------------------------

params = algod.suggested_params()

txn = ApplicationCreateTxn(
    sender=deployer,
    sp=params,
    on_complete=OnComplete.NoOpOC,
    approval_program=approval_program,
    clear_program=clear_program,
    global_schema=StateSchema(
        num_uints=3,
        num_byte_slices=4,
    ),
    local_schema=StateSchema(
        num_uints=0,
        num_byte_slices=0,
    ),
    app_args=app_args,
)

signed_txn = txn.sign(private_key)

print()
print("Submitting application creation transaction...")

txid = algod.send_transaction(signed_txn)

print("Transaction ID:", txid)
print("Waiting for confirmation...")

confirmed = wait_for_confirmation(algod, txid, 4)

app_id = confirmed["application-index"]

print()
print("========================================")
print("DEPLOYMENT SUCCESSFUL")
print("========================================")
print("ESCROW_APP_ID:", app_id)

app_address = logic.get_application_address(app_id)

print("ESCROW_ADDRESS:", app_address)
print()

print("Add these to .env:")
print()
print(f"ESCROW_APP_ID={app_id}")
print(f"ESCROW_ADDRESS={app_address}")