from fastapi import FastAPI

from .config import settings
from .rules import ALL_RULES
from .schemas import VerificationReport, VerifyRequest
from .verifier import verify_shipment

app = FastAPI(
    title="CargoProof Verification Engine",
    description="Deterministic, rule-based shipment evidence verification. No LLM, no blockchain access.",
    version="0.1.0",
)


@app.get("/api/v1/health")
async def health():
    return {"service": "CargoProof Verification Engine", "status": "healthy"}


@app.get("/api/v1/rules")
async def rules():
    return {
        "rules": [fn.__name__.replace("rule_", "").upper() for fn in ALL_RULES],
        "config": {
            "max_evidence_age_hours": settings.max_evidence_age_hours,
            "gps_max_distance_km": settings.gps_max_distance_km,
            "evidence_api_url": settings.evidence_api_url,
        },
    }


@app.post("/api/v1/verify", response_model=VerificationReport)
async def verify(request: VerifyRequest):
    return await verify_shipment(request.shipment_id)


@app.get("/api/v1/verification/{shipment_id}", response_model=VerificationReport)
async def get_verification(shipment_id: str):
    return await verify_shipment(shipment_id)
