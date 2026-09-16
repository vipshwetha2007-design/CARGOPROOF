# Escrow deployment notes

The contract is designed as a stateful Algorand application whose application
account is the escrow address.

## State

- `asset_id`: USDC ASA ID; TestNet is 10458941.
- `beneficiary`: seller/payment recipient.
- `verifier`: CargoProof verification authority.
- `status`: PENDING / VERIFIED / RELEASED / HELD.
- `evidence_hash`: hash of the evidence bundle.
- `amount`: settlement amount in the configured ASA's atomic units.

## Lifecycle

1. Create the application with asset ID, beneficiary and verifier.
2. The app account opts into the USDC ASA.
3. Buyer transfers settlement USDC to the app account.
4. CargoProof writes the evidence hash.
5. If evidence is sufficient, the verifier marks the state VERIFIED.
6. The verifier calls `release`; the app performs an inner asset transfer.
7. If evidence is insufficient, the verifier calls `hold`.

For a hackathon demo, use TestNet USDC only. Do not represent testnet
balances as real ₹50 lakh.

The exact deployment transaction composition depends on the Algorand SDK /
AlgoKit version installed on the machine. `scripts/deploy.py` is intentionally
a minimal starting point rather than a claim that a production deployment
has been audited.
