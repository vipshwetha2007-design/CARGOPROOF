"""
CargoProof escrow contract.

Design:
- The application account is the escrow address.
- The settlement asset is configured at initialization.
- A verifier records an evidence hash and verification state.
- Release creates an inner AssetTransfer from the application account
  to the beneficiary.
- The application cannot release before verification is satisfied.

This is a reference contract for TestNet deployment. Audit before any
production use.
"""

from pyteal import *


STATUS_PENDING = Int(0)
STATUS_VERIFIED = Int(1)
STATUS_RELEASED = Int(2)
STATUS_HELD = Int(3)

ASSET_ID = Bytes("asset_id")
BENEFICIARY = Bytes("beneficiary")
VERIFIER = Bytes("verifier")
STATUS = Bytes("status")
EVIDENCE_HASH = Bytes("evidence_hash")
AMOUNT = Bytes("amount")


def approval():
    on_create = Seq([
        App.globalPut(ASSET_ID, Btoi(Txn.application_args[1])),
        App.globalPut(BENEFICIARY, Txn.application_args[2]),
        App.globalPut(VERIFIER, Txn.application_args[3]),
        App.globalPut(STATUS, STATUS_PENDING),
        App.globalPut(EVIDENCE_HASH, Bytes("")),
        App.globalPut(AMOUNT, Int(0)),
        Approve(),
    ])

    optin_asset = Seq([
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: App.globalGet(ASSET_ID),
            TxnField.asset_amount: Int(0),
            TxnField.asset_receiver: Global.current_application_address(),
        }),
        InnerTxnBuilder.Submit(),
        Approve(),
    ])

    set_evidence = Seq([
        Assert(Txn.sender() == App.globalGet(VERIFIER)),
        App.globalPut(EVIDENCE_HASH, Txn.application_args[1]),
        App.globalPut(STATUS, STATUS_VERIFIED),
        App.globalPut(AMOUNT, Btoi(Txn.application_args[2])),
        Approve(),
    ])

    hold = Seq([
        Assert(Txn.sender() == App.globalGet(VERIFIER)),
        App.globalPut(STATUS, STATUS_HELD),
        Approve(),
    ])

    release = Seq([
        Assert(Txn.sender() == App.globalGet(VERIFIER)),
        Assert(App.globalGet(STATUS) == STATUS_VERIFIED),
        Assert(App.globalGet(AMOUNT) > Int(0)),

        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: App.globalGet(ASSET_ID),
            TxnField.asset_amount: App.globalGet(AMOUNT),
            TxnField.asset_receiver: App.globalGet(BENEFICIARY),
        }),
        InnerTxnBuilder.Submit(),

        # Clear the released amount from global state.
        App.globalPut(AMOUNT, Int(0)),

        # Mark the escrow as released.
        App.globalPut(STATUS, STATUS_RELEASED),

        Approve(),
    ])

    return Cond(
        [Txn.application_id() == Int(0), on_create],
        [Txn.application_args[0] == Bytes("optin"), optin_asset],
        [Txn.application_args[0] == Bytes("evidence"), set_evidence],
        [Txn.application_args[0] == Bytes("hold"), hold],
        [Txn.application_args[0] == Bytes("release"), release],
    )


def clear():
    return Return(Int(1))


if __name__ == "__main__":
    print(compileTeal(approval(), Mode.Application, version=8))
    print("---CLEAR---")
    print(compileTeal(clear(), Mode.Application, version=8))