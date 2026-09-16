"""
CargoProof Simulated Evidence API
-----------------------------------
FastAPI application exposing the SIMULATED maritime/trade evidence sources
and the verification engine.

Run with:
    uvicorn simulated_evidence.main:app --reload --port 8000

Swagger UI: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db, init_db
from .verification import VerificationEngine

app = FastAPI(
    title="CargoProof Simulated Evidence API",
    description=(
        "**SIMULATED EVIDENCE SOURCE** - Synthetic maritime and trade-finance "
        "evidence used exclusively for the CargoProof hackathon demonstration. "
        "None of this data represents real vessels, containers, or shipments."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


# ---------------------------------------------------------------------------
# Meta endpoints
# ---------------------------------------------------------------------------
@app.get("/api/v1/about", response_model=schemas.AboutOut, tags=["meta"])
def about() -> schemas.AboutOut:
    return schemas.AboutOut(
        name="CargoProof Simulated Evidence API",
        environment="DEMO",
        data_source="SIMULATED",
        description=(
            "Synthetic maritime evidence used for CargoProof hackathon demonstration"
        ),
    )


@app.get("/api/v1/health", response_model=schemas.HealthOut, tags=["meta"])
def health() -> schemas.HealthOut:
    return schemas.HealthOut(
        status="ok", service="cargoproof-simulated-evidence-api", data_source="SIMULATED"
    )


# ---------------------------------------------------------------------------
# Shipments
# ---------------------------------------------------------------------------
@app.get("/api/v1/shipments", response_model=List[schemas.ShipmentOut], tags=["shipments"])
def list_shipments(db: Session = Depends(get_db)):
    return db.query(models.Shipment).order_by(models.Shipment.shipment_id).all()


@app.get(
    "/api/v1/shipments/{shipment_id}",
    response_model=schemas.ShipmentOut,
    tags=["shipments"],
)
def get_shipment(shipment_id: str, db: Session = Depends(get_db)):
    shipment = (
        db.query(models.Shipment)
        .filter(models.Shipment.shipment_id == shipment_id)
        .first()
    )
    if shipment is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")
    return shipment


# ---------------------------------------------------------------------------
# Vessels
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/vessels/{imo_number}", response_model=schemas.VesselOut, tags=["vessels"]
)
def get_vessel(imo_number: str, db: Session = Depends(get_db)):
    vessel = db.query(models.Vessel).filter(models.Vessel.imo_number == imo_number).first()
    if vessel is None:
        raise HTTPException(status_code=404, detail=f"Vessel '{imo_number}' not found")
    return vessel


@app.get(
    "/api/v1/vessels/{imo_number}/gps",
    response_model=List[schemas.GpsObservationOut],
    tags=["vessels"],
)
def get_vessel_gps(imo_number: str, db: Session = Depends(get_db)):
    observations = (
        db.query(models.GpsObservation)
        .filter(models.GpsObservation.vessel_imo == imo_number)
        .order_by(models.GpsObservation.timestamp.desc())
        .all()
    )
    if not observations:
        raise HTTPException(
            status_code=404, detail=f"No GPS observations found for vessel '{imo_number}'"
        )
    return observations


# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/containers/{container_number}",
    response_model=schemas.ContainerOut,
    tags=["containers"],
)
def get_container(container_number: str, db: Session = Depends(get_db)):
    container = (
        db.query(models.Container)
        .filter(models.Container.container_number == container_number)
        .first()
    )
    if container is None:
        raise HTTPException(
            status_code=404, detail=f"Container '{container_number}' not found"
        )
    return container


@app.get(
    "/api/v1/containers/{container_number}/events",
    response_model=List[schemas.PortEventOut],
    tags=["containers"],
)
def get_container_events(container_number: str, db: Session = Depends(get_db)):
    events = (
        db.query(models.PortEvent)
        .filter(models.PortEvent.container_number == container_number)
        .order_by(models.PortEvent.event_time.asc())
        .all()
    )
    if not events:
        raise HTTPException(
            status_code=404,
            detail=f"No port events found for container '{container_number}'",
        )
    return events


# ---------------------------------------------------------------------------
# Shipment documents & inspections
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/shipments/{shipment_id}/documents",
    response_model=List[schemas.ShipmentDocumentOut],
    tags=["shipments"],
)
def get_shipment_documents(shipment_id: str, db: Session = Depends(get_db)):
    documents = (
        db.query(models.ShipmentDocument)
        .filter(models.ShipmentDocument.shipment_id == shipment_id)
        .all()
    )
    if not documents:
        raise HTTPException(
            status_code=404, detail=f"No documents found for shipment '{shipment_id}'"
        )
    return documents


@app.get(
    "/api/v1/shipments/{shipment_id}/inspections",
    response_model=List[schemas.InspectionOut],
    tags=["shipments"],
)
def get_shipment_inspections(shipment_id: str, db: Session = Depends(get_db)):
    shipment = (
        db.query(models.Shipment)
        .filter(models.Shipment.shipment_id == shipment_id)
        .first()
    )
    if shipment is None:
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")

    inspections = (
        db.query(models.Inspection)
        .filter(models.Inspection.container_number == shipment.container_number)
        .all()
    )
    if not inspections:
        raise HTTPException(
            status_code=404,
            detail=f"No inspections found for shipment '{shipment_id}'",
        )
    return inspections


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
# In-memory cache of the most recent verification report per shipment, so
# GET /api/v1/verification/{shipment_id} can return the last result without
# re-running the engine. (A hackathon-appropriate substitute for a
# verifications table.)
_LAST_VERIFICATION_CACHE: dict[str, schemas.VerificationReport] = {}


@app.post(
    "/api/v1/verify", response_model=schemas.VerificationReport, tags=["verification"]
)
def verify_shipment(request: schemas.VerifyRequest, db: Session = Depends(get_db)):
    engine = VerificationEngine(db)
    result = engine.verify(request.shipment_id)

    if result.get("not_found"):
        raise HTTPException(
            status_code=404, detail=f"Shipment '{request.shipment_id}' not found"
        )

    report = schemas.VerificationReport(
        shipment_id=result["shipment_id"],
        verification_status=result["verification_status"],
        confidence=result["confidence"],
        checks=schemas.VerificationChecks(**result["checks"]),
        reasons=result["reasons"],
        reason_details=result["reason_details"],
        evidence_sources=result["evidence_sources"],
        evidence_hash=result["evidence_hash"],
        generated_at=result["generated_at"],
    )
    _LAST_VERIFICATION_CACHE[report.shipment_id] = report
    return report


@app.get(
    "/api/v1/verification/{shipment_id}",
    response_model=schemas.VerificationReport,
    tags=["verification"],
)
def get_last_verification(shipment_id: str, db: Session = Depends(get_db)):
    cached = _LAST_VERIFICATION_CACHE.get(shipment_id)
    if cached is not None:
        return cached

    # Nothing cached yet - run verification on demand so this endpoint is
    # always demoable even right after a fresh seed/restart.
    engine = VerificationEngine(db)
    result = engine.verify(shipment_id)
    if result.get("not_found"):
        raise HTTPException(status_code=404, detail=f"Shipment '{shipment_id}' not found")

    report = schemas.VerificationReport(
        shipment_id=result["shipment_id"],
        verification_status=result["verification_status"],
        confidence=result["confidence"],
        checks=schemas.VerificationChecks(**result["checks"]),
        reasons=result["reasons"],
        reason_details=result["reason_details"],
        evidence_sources=result["evidence_sources"],
        evidence_hash=result["evidence_hash"],
        generated_at=result["generated_at"],
    )
    _LAST_VERIFICATION_CACHE[shipment_id] = report
    return report


# ---------------------------------------------------------------------------
# Demo helper endpoint
# ---------------------------------------------------------------------------
DEMO_GROUPS = {
    "verified": ["CP001", "CP010"],
    "vessel_mismatch": ["CP002"],
    "container_missing": ["CP003"],
    "destination_mismatch": ["CP004"],
    "vessel_not_in_transit": ["CP005"],
    "port_event_conflict": ["CP006"],
    "gps_conflict": ["CP007"],
    "inspection_failure": ["CP008"],
    "document_mismatch": ["CP009"],
}


@app.get("/api/v1/demo/shipments", tags=["demo"])
def demo_shipments(db: Session = Depends(get_db)):
    """
    Best shipments to use for a live demo, grouped by scenario. A judge can
    call this first, then POST /api/v1/verify with any of the returned IDs.
    """
    grouped = {}
    for group_name, ids in DEMO_GROUPS.items():
        grouped[group_name] = []
        for shipment_id in ids:
            shipment = (
                db.query(models.Shipment)
                .filter(models.Shipment.shipment_id == shipment_id)
                .first()
            )
            if shipment is not None:
                grouped[group_name].append(
                    {
                        "shipment_id": shipment.shipment_id,
                        "seller": shipment.seller,
                        "buyer": shipment.buyer,
                        "cargo_description": shipment.cargo_description,
                        "declared_value": shipment.declared_value,
                        "currency": shipment.currency,
                    }
                )
    return {
        "data_source": "SIMULATED",
        "note": "Call POST /api/v1/verify with any shipment_id below to see the full report.",
        "groups": grouped,
    }
