# CargoProof Verification Engine

## 1. What this module does

Sits between the simulated evidence API and everything downstream (future AI
agent, escrow orchestrator). Given a `shipment_id`, it collects evidence
from every available source, runs a fixed set of deterministic rules over
it, and returns a structured `VerificationReport`: a status
(`VERIFIED` / `HOLD` / `REJECTED`), a `decision` (`RELEASE` /
`DO_NOT_RELEASE`), a confidence score, the specific rules that failed and
why, and a SHA-256 hash of the evidence used.

## 2. Why verification is deterministic, not LLM-based

For an escrow release decision, an auditor (or a judge) needs to be able to
ask "why did this release?" and get an answer that is exactly reproducible
from the underlying data — not a probabilistic explanation. Every rule
here is a plain Python function with fixed logic. Given the same evidence,
this engine always returns the same status, the same score, and the same
hash. An LLM can *explain* the result afterwards (see section 7) but never
*decides* it.

## 3. How evidence is collected

`client.py` (`EvidenceClient`) calls the simulated evidence API's REST
endpoints for one shipment: shipment record, vessel, container, port
events, GPS, inspection, and documents. Vessel/GPS lookups use the
shipment's `vessel_imo`; container/port-event lookups use its
`container_number`. If a source is unreachable, times out, or 5xxs, that
single source is recorded as a warning (`{SOURCE}_UNAVAILABLE`) rather than
crashing the whole run — a dead GPS feed shouldn't block verification of
everything else. A 404 is treated as "this record doesn't exist," which
several rules use directly (e.g. `CONTAINER_NOT_FOUND`).

### Assumed evidence API schema

The simulated evidence API didn't exist yet at the time this module was
written, so the client and rules assume the following shape. If the real
API differs, only `client.py`'s parsing needs to change — rules and hashing
are unaffected as long as the same field names come through.

- **Shipment**: `shipment_id, vessel_imo, container_number, origin_port, destination_port, claimed_status, cargo_description, declared_value`
- **Vessel**: `imo_number, name, status, last_updated`
- **Container**: `container_number, vessel_imo, origin_port, destination_port, cargo_description`
- **Port event**: `event_type (ARRIVAL/DEPARTURE/LOADED/DISCHARGED), port, timestamp, vessel_imo`
- **GPS observation**: `lat, lon, timestamp, vessel_imo`
- **Inspection**: `shipment_id, result (PASS/FAILED), inspector, timestamp` (or no record at all)
- **Document**: `document_type, container_number, vessel_name, origin_port, destination_port, declared_cargo, declared_value, issued_at`

## 4. How each rule works

All 13 rules live in `rules.py`, each returning a `RuleResult(rule, passed,
severity, message)`.

| Rule | Severity | Checks |
|---|---|---|
| `SHIPMENT_EXISTS` | CRITICAL | Shipment record found |
| `VESSEL_EXISTS` | CRITICAL | Vessel record found |
| `CONTAINER_EXISTS` | CRITICAL | Container record found |
| `VESSEL_CONTAINER_MATCH` | CRITICAL | Shipment's `vessel_imo` == container's `vessel_imo` |
| `ORIGIN_MATCH` | HIGH | Origin agrees across shipment / container / documents |
| `DESTINATION_MATCH` | CRITICAL | Destination agrees across shipment / container / documents |
| `VESSEL_STATUS` | CRITICAL | Vessel's actual status isn't incompatible with the claimed status (e.g. claims IN_TRANSIT but registry says DOCKED) |
| `PORT_EVENT_CONSISTENCY` | HIGH | Events are chronologically sane; no unexplained "departed then arrived back at the same port"; a claimed in-transit shipment has a real DEPARTURE event from its origin |
| `GPS_CONSISTENCY` | HIGH | Latest GPS fix is within `GPS_MAX_DISTANCE_KM` of the great-circle route (see below) |
| `INSPECTION` | MEDIUM/HIGH | PASS passes; FAILED fails (HIGH); no record at all is `INSPECTION_UNAVAILABLE` and does **not** fail the shipment |
| `DOCUMENT_CONSISTENCY` | HIGH | Bill-of-lading fields (container, vessel, origin, destination, cargo) agree with other evidence |
| `CARGO_CONSISTENCY` | MEDIUM | Cargo description agrees across shipment / container / documents |
| `DATA_FRESHNESS` | LOW | Newest timestamped evidence isn't older than `MAX_EVIDENCE_AGE_HOURS` |

**GPS check, specifically**: this is a coarse "is the vessel roughly on its
declared route" check using a spherical cross-track-distance formula
(Haversine-based), against a small hardcoded table of port coordinates in
`rules.py` (`PORT_COORDINATES`). It is *not* real maritime routing — no
coastlines, shipping lanes, or land avoidance. If origin/destination aren't
in the table, the check is skipped (not counted as a failure) and flagged
`GPS_ROUTE_UNVERIFIABLE`. Extend `PORT_COORDINATES` as needed.

## 5. How confidence is calculated

Starts at 100. For every failed rule, subtract by severity:
`CRITICAL -40, HIGH -25, MEDIUM -10, LOW -5`. Clamped to `[0, 100]`.
Multiple failures stack (e.g. two HIGH failures = -50).

## 6. Decision logic

```
shipment not found          -> REJECTED
any CRITICAL rule fails     -> REJECTED
any HIGH or MEDIUM fails    -> HOLD
everything passes           -> VERIFIED

VERIFIED -> decision = RELEASE
HOLD, REJECTED -> decision = DO_NOT_RELEASE
```

**Deliberate deviation from the spec's wording**: the spec's suggested
logic says HOLD on "multiple HIGH/MEDIUM conflicts." This implementation
holds on a **single** HIGH/MEDIUM conflict too, not just multiple. For an
escrow release, we'd rather flag one unresolved conflict for a human/agent
to look at than average it away because it's the only one. This threshold
lives entirely in `determine_status()` in `verifier.py` — change it there
if you want the literal "multiple" behavior instead.

## 7. Evidence hashing (`hashing.py`)

Before hashing, the evidence actually used (shipment, vessel, container,
port events, GPS, inspection, documents) is arranged into a canonical
form: dict keys sorted, and list fields (port events, GPS points,
documents) sorted by a stable key so that *the same underlying evidence*
always serializes identically regardless of what order the API happened to
return it in. That canonical JSON (`sort_keys=True`,
`separators=(",", ":")`) is SHA-256'd. Crucially, nothing the verification
engine itself generates — `verified_at`, `confidence_score`, `decision` —
is part of the hash input, so re-running verification on unchanged
evidence always reproduces the same `evidence_hash`, even hours later.

## 8. How the future AI agent will consume this

The AI agent should treat this engine's output as ground truth and never
override it. A typical integration:

```python
report = await verify_shipment("CP001")
# report.verification_status, report.decision, report.confidence_score,
# report.evidence_hash, report.failed_rules, report.warnings
```

The agent's job is narration, not decision-making — e.g. turning
`report.failed_rules` into "the container registry conflicts with the
declared vessel" for a human reader. If `report.decision == "RELEASE"`,
the agent (or the escrow orchestrator module after it) submits
`report.evidence_hash` on-chain and triggers release; otherwise it holds.

## 9. Why this module never touches the blockchain

Separation of concerns for auditability and security: this module has no
private keys, no mnemonics, no Algorand SDK import, and no escrow contract
calls. It only ever produces a `VerificationReport`. A separate escrow
orchestrator module (not part of this deliverable) is responsible for
reading `report.decision` and `report.evidence_hash` and calling the
already-deployed contract accordingly. If this module is ever compromised
or buggy, it can lie about evidence — but it physically cannot move funds.

## 10. Running it

```bash
# from D:\cargoproof, with .venv active
.venv\Scripts\activate
pip install -r requirements.txt

# Start the simulated evidence API (separate module, not this one)
uvicorn simulated_evidence.main:app --reload --port 8000

# Start the verification engine
uvicorn verification_engine.main:app --reload --port 8001

# Verify a shipment from the command line
python -m verification_engine.demo CP001

# Run the test suite (48 tests, offline — no evidence API needed)
pytest tests/verification -v
```

### Example: `python -m verification_engine.demo CP001` (good shipment)

```
========================================
CargoProof Verification Engine
========================================

Shipment: CP001

Collecting evidence...

✓ Shipment
✓ Vessel
✓ Container
✓ Port Records
✓ GPS
✓ Inspection
✓ Documents

Running verification...

----------------------------------------
RESULT
----------------------------------------
Status     : VERIFIED
Confidence : 100%
Decision   : RELEASE

Evidence Hash:
b949e61ba84ae1661be1c4ade9ec4522344fdab4ba9302f5b428fb14dd7548e0
----------------------------------------
========================================
```

### Example: `python -m verification_engine.demo CP002` (vessel mismatch)

```
Status     : REJECTED
Confidence : 60%
Decision   : DO_NOT_RELEASE

Reasons:
  - VESSEL_MISMATCH: shipment claims vessel IMO 'IMO0001' but container is
    registered to vessel IMO 'IMO9999'
```

## 11. API reference

- `GET /api/v1/health` — liveness check
- `GET /api/v1/rules` — lists the 13 active rules and current config
- `POST /api/v1/verify` `{"shipment_id": "CP001"}` — runs verification, returns full report
- `GET /api/v1/verification/{shipment_id}` — same as above, GET form

## 12. Configuration (environment variables)

```
EVIDENCE_API_URL=http://127.0.0.1:8000
MAX_EVIDENCE_AGE_HOURS=24
GPS_MAX_DISTANCE_KM=500
EVIDENCE_API_TIMEOUT_SECONDS=10
```

## What was actually tested before delivery

All 48 automated tests pass (`pytest tests/verification -v`), covering
every rule individually plus end-to-end pipeline runs for all ten CP001–
CP010 scenarios via an in-memory fake client. Beyond that, this module was
also run as a real, separate FastAPI process on port 8001 against a real
(throwaway, fixture-backed) evidence API on port 8000 — i.e. an actual
HTTP round trip, not just Python function calls — confirming CP001
resolves to `VERIFIED/RELEASE` and CP002 resolves to
`REJECTED/DO_NOT_RELEASE` with the correct failed rule, and that
`evidence_hash` is identical across two separate verify calls on the same
data.
