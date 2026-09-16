# CargoProof 4-day build plan

## Day 1 — foundation
- Run the local demo.
- Replace `DEMO_MODE=true` only after the local flow works.
- Create TestNet payer + provider + verifier accounts.
- Opt provider and payer into USDC ASA 10458941.

## Day 2 — real x402
- Configure `PAY_TO`.
- Run the paid provider endpoint.
- Use an Algorand x402 client to trigger 402 → payment → retry.
- Capture settlement transaction IDs.

## Day 3 — escrow
- Compile/deploy `contracts/cargoproof_escrow.py`.
- Fund the application account.
- Opt the app account into USDC.
- Transfer a small TestNet USDC amount to the escrow.
- Add the backend transaction adapter for `evidence`, `hold`, and `release`.

## Day 4 — presentation
- Add three browser role views.
- Add live explorer links.
- Add evidence hash display.
- Rehearse the 5-minute demo.
- Keep all synthetic maritime observations explicitly labeled.

## Demo principle

Do not claim the maritime observations are real unless a real source is
actually connected. The strongest truthful claim is:

"CargoProof's payment, agent decision loop, evidence commitment and settlement
contract are live on Algorand TestNet; domain evidence is simulated for the
MVP."

That is much stronger than pretending synthetic AIS data is real.
