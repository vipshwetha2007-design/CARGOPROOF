# CargoProof — Simulated Evidence API

> **SIMULATED EVIDENCE SOURCE.** Every vessel, container, shipment, GPS ping,
> inspection, and document in this project is synthetic data created for a
> hackathon demo. Nothing here is real maritime or trade data, and this
> service never talks to the Algorand blockchain directly.

This project implements the **evidence layer** of CargoProof:

```
simulated_database
        |
    evidence_api            <-- this project (FastAPI)
        |
  verification_engine       <-- this project (simulated_evidence/verification.py)
        |
   evidence_hash             <-- this project (SHA-256 over canonical evidence JSON)
        |
   CargoProof agent          <-- your existing scripts/*.py (unchanged)
        |
   Algorand escrow           <-- your existing, already-deployed smart contract
```

It does **not** modify, redeploy, or otherwise touch your existing Algorand
TestNet escrow app (`769579669`). It only produces a verification report and
an evidence hash that your existing `scripts/submit_evidence.py` /
`scripts/release.py` can consume.

---

## 1. Project structure

```
cargoproof/
│
├── contracts/                     (your existing Algorand contract — untouched)
├── scripts/                       (your existing submit_evidence.py / release.py — untouched)
│
├── simulated_evidence/
│   ├── __init__.py
│   ├── database.py                SQLAlchemy engine/session setup
│   ├── models.py                  ORM models for the 7 evidence tables
│   ├── schemas.py                 Pydantic request/response models
│   ├── seed.py                    Seed script (10 demo shipments)
│   ├── verification.py            Verification engine + evidence hash
│   └── main.py                    FastAPI app / all endpoints
│
├── data/
│   └── cargoproof.db              SQLite DB (created on first run)
│
├── requirements.txt
├── .env.example                   Documents existing + new env vars (does NOT overwrite your .env)
└── README.md
```

---

## 2. Installation (Windows PowerShell, `D:\cargoproof`)

```powershell
cd D:\cargoproof

# (Recommended) create/activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

> Your existing `.env` with `ESCROW_APP_ID`, `ESCROW_ADDRESS`, `USDC_ASSET_ID`,
> `VERIFIER_ADDRESS`, `BENEFICIARY_ADDRESS` is left untouched. `.env.example`
> in this project is just documentation — do not overwrite your real `.env`
> with it.

---

## 3. Initialize the database

```powershell
python -m simulated_evidence.seed
```

This creates `data\cargoproof.db`, (re)creates all tables, clears any
existing demo rows, and inserts:

- 6 vessels
- 9 containers
- 11 port events
- 6 GPS observations
- 9 inspections
- 10 shipment documents
- **10 shipments** (`CP001`–`CP010`), covering every required scenario

You'll see a summary printed to the console, e.g.:

```
CargoProof SIMULATED evidence database seeded successfully
  Vessels:             6
  Containers:          9
  ...
  CP001  VERIFIED  (clean shipment)
  CP002  REJECTED  (vessel mismatch)
  ...
```

Safe to re-run any time — it wipes and reinserts demo data only.

---

## 4. Start the API

```powershell
uvicorn simulated_evidence.main:app --reload --port 8000
```

Swagger UI: **http://127.0.0.1:8000/docs**
Health check: **http://127.0.0.1:8000/api/v1/health**

---

## 5. API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/about` | Confirms this is a SIMULATED data source |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/shipments` | List all shipments |
| GET | `/api/v1/shipments/{shipment_id}` | Get one shipment |
| GET | `/api/v1/vessels/{imo_number}` | Get a vessel record |
| GET | `/api/v1/vessels/{imo_number}/gps` | Latest→oldest GPS pings for a vessel |
| GET | `/api/v1/containers/{container_number}` | Get a container record |
| GET | `/api/v1/containers/{container_number}/events` | Port event history for a container |
| GET | `/api/v1/shipments/{shipment_id}/documents` | Trade documents (Bill of Lading etc.) |
| GET | `/api/v1/shipments/{shipment_id}/inspections` | Inspection records |
| POST | `/api/v1/verify` | **Run the verification engine** on a shipment |
| GET | `/api/v1/verification/{shipment_id}` | Get the last verification result |
| GET | `/api/v1/demo/shipments` | Judge-friendly grouped list of demo shipments |

---

## 6. Demo shipments (seeded)

| Shipment | Scenario | Expected result | Primary reason |
|---|---|---|---|
| `CP001` | Everything agrees | **VERIFIED** | — |
| `CP002` | Vessel mismatch | REJECTED | `VESSEL_MISMATCH` |
| `CP003` | Container not in registry | REJECTED | `CONTAINER_NOT_FOUND` |
| `CP004` | Destination doesn't match records | REJECTED | `DESTINATION_MISMATCH` |
| `CP005` | Claims in-transit, vessel is docked | REJECTED | `VESSEL_STATUS_CONFLICT` |
| `CP006` | No departure event on record | REJECTED | `PORT_EVENT_CONFLICT` |
| `CP007` | GPS position off the declared route | REJECTED | `GPS_ROUTE_CONFLICT` |
| `CP008` | Cargo inspection failed | REJECTED | `INSPECTION_FAILED` |
| `CP009` | Trade document disagrees with manifest | REJECTED | `DOCUMENT_DATA_MISMATCH` |
| `CP010` | High-value shipment, all sources agree | **VERIFIED** | — |

Note: a few rejected shipments (e.g. `CP004`, `CP005`) trip more than one
check at once. That's intentional and realistic — genuine fraud or data
inconsistency in one place often shows up in multiple independent evidence
sources, which is exactly the kind of cross-source corroboration a real
trade-finance verifier relies on.

---

## 7. Example: verifying CP001 (PASS) and CP002 (FAIL)

### PowerShell

```powershell
# CP001 - should VERIFY
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/verify `
  -ContentType "application/json" `
  -Body (@{ shipment_id = "CP001" } | ConvertTo-Json)

# CP002 - should REJECT (VESSEL_MISMATCH)
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/verify `
  -ContentType "application/json" `
  -Body (@{ shipment_id = "CP002" } | ConvertTo-Json)
```

### curl

```bash
curl -X POST http://127.0.0.1:8000/api/v1/verify \
  -H "Content-Type: application/json" \
  -d '{"shipment_id": "CP001"}'

curl -X POST http://127.0.0.1:8000/api/v1/verify \
  -H "Content-Type: application/json" \
  -d '{"shipment_id": "CP002"}'
```

### CP001 response (abridged)

```json
{
  "shipment_id": "CP001",
  "verification_status": "VERIFIED",
  "confidence": 1.0,
  "checks": {
    "vessel_exists": true,
    "container_exists": true,
    "vessel_container_match": true,
    "origin_match": true,
    "destination_match": true,
    "vessel_status_valid": true,
    "port_events_consistent": true,
    "gps_consistent": true,
    "inspection_passed": true,
    "documents_consistent": true
  },
  "reasons": [],
  "evidence_sources": [
    "vessel_tracking", "container_registry", "port_records",
    "gps", "inspection", "shipment_documents"
  ],
  "evidence_hash": "7208ee8b644963ea5dfad88458f16edd0630320eb1a103da3f025d869a398f94"
}
```

### CP002 response (abridged)

```json
{
  "shipment_id": "CP002",
  "verification_status": "REJECTED",
  "confidence": 0.9,
  "checks": {
    "vessel_exists": true,
    "container_exists": true,
    "vessel_container_match": false,
    "origin_match": true,
    "destination_match": true,
    "vessel_status_valid": true,
    "port_events_consistent": true,
    "gps_consistent": true,
    "inspection_passed": true,
    "documents_consistent": true
  },
  "reasons": ["VESSEL_MISMATCH"],
  "reason_details": {
    "VESSEL_MISMATCH": "Declared vessel IMO = IMO1234567, but container DEF456 is registered against vessel IMO IMO2233445."
  },
  "evidence_hash": "<sha256>"
}
```

The demo narrative: *"CP002 claims Vessel XYZ, but the independent
container registry says this container is actually on Vessel ABC. Escrow
remains locked."*

---

## 8. How the evidence hash works

`compute_evidence_hash()` in `simulated_evidence/verification.py`:

1. Builds a **canonical evidence bundle** — only the fields that actually
   matter to the verdict (vessel status/route, container status/route, port
   events, latest GPS ping, inspection results, and document declarations).
   Non-deterministic bookkeeping fields (auto-increment IDs, "last updated"
   wall-clock times unrelated to the verdict) are excluded.
2. Sorts all dict keys and list entries deterministically.
3. Serializes with `json.dumps(..., sort_keys=True, separators=(",", ":"))`.
4. Hashes the resulting canonical JSON string with SHA-256.

Calling `/api/v1/verify` twice for the same shipment with unchanged
underlying data returns the **same** `evidence_hash` both times (verified
above during testing). This is the hash your CargoProof agent should submit
on-chain — it's a compact, tamper-evident fingerprint of exactly which
evidence justified the release decision.

---

## 9. How this connects to the existing Algorand escrow

This project deliberately stops at producing a `VerificationReport` with an
`evidence_hash`. It never imports `algosdk`, never signs a transaction, and
never talks to TestNet. The separation is intentional so the blockchain
layer (which already works and is already demoed end-to-end) stays
untouched.

Conceptually, the full flow is:

1. Seller submits a shipment claim → stored/represented as a `Shipment` row
   here (in a real system, this would be the trigger for verification).
2. CargoProof agent calls `POST /api/v1/verify` with the `shipment_id`.
3. This API returns `verification_status` (`VERIFIED` / `REJECTED`) and a
   deterministic `evidence_hash`.
4. **If `VERIFIED`:** the CargoProof agent calls the existing
   `scripts/submit_evidence.py` to write `evidence_hash` on-chain, then
   `scripts/release.py` to release the 0.5 (or however much) USDC from
   escrow to `BENEFICIARY_ADDRESS`.
5. **If `REJECTED`:** the agent does not call `release.py` at all — the
   contract stays in status `1 = VERIFIED` never reached, or stays
   `3 = HELD`, and escrow funds remain locked.

---

## 10. Recommended next step: wiring this into `submit_evidence.py` / `release.py`

**Without changing the escrow smart contract**, the smallest integration
is to have your existing scripts call this API first and gate on the
result:

```python
# Pseudocode sketch for scripts/submit_evidence.py (add near the top of main())
import os
import requests

EVIDENCE_API_BASE_URL = os.environ.get("EVIDENCE_API_BASE_URL", "http://127.0.0.1:8000")

def get_verification(shipment_id: str) -> dict:
    resp = requests.post(
        f"{EVIDENCE_API_BASE_URL}/api/v1/verify",
        json={"shipment_id": shipment_id},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()

def main():
    shipment_id = "CP001"  # or from CLI args / config
    report = get_verification(shipment_id)

    if report["verification_status"] != "VERIFIED":
        print(f"Shipment {shipment_id} REJECTED: {report['reasons']}")
        print("ESCROW REMAINS LOCKED. Not submitting evidence on-chain.")
        return

    evidence_hash_hex = report["evidence_hash"]
    evidence_hash_bytes = bytes.fromhex(evidence_hash_hex)

    # ... existing algosdk code that currently builds/submits the
    #     "submit evidence" application-call transaction, using
    #     evidence_hash_bytes as the evidence_hash argument, unchanged.
```

And in `scripts/release.py`, add the same guard before constructing the
release transaction: only proceed if a prior call to `/api/v1/verify` (or
`GET /api/v1/verification/{shipment_id}`) returned `"VERIFIED"`.

This keeps the smart contract's existing evidence-hash storage mechanism
exactly as-is — this API is just the thing that decides *what hash* gets
submitted and *whether* `release.py` should run at all. A natural follow-up
after the hackathon would be to persist verification reports in a small
`verifications` table (instead of the current in-memory cache in
`main.py`) so the on-chain hash can always be traced back to the exact
evidence snapshot that produced it.

---

## 11. Notes on data integrity / demo safety

- No real API keys, no real private keys, and no blockchain credentials
  appear anywhere in this project.
- The existing `.env` (`ESCROW_APP_ID`, `ESCROW_ADDRESS`, `USDC_ASSET_ID`,
  `VERIFIER_ADDRESS`, `BENEFICIARY_ADDRESS`) is never read, written, or
  referenced by this code.
- `/api/v1/about` and the FastAPI description both explicitly label this as
  a `SIMULATED` data source, for the benefit of judges reading the Swagger
  docs.
