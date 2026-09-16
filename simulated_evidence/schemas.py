"""
Pydantic schemas (request/response models) for the CargoProof simulated
evidence API. Kept separate from the ORM models so the API contract is
explicit and independent of the storage layer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Base config so ORM objects can be returned directly from route handlers
# ---------------------------------------------------------------------------
class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Vessel
# ---------------------------------------------------------------------------
class VesselOut(ORMBase):
    imo_number: str
    vessel_name: str
    mmsi: str
    flag: str
    vessel_type: str
    current_latitude: float
    current_longitude: float
    current_port: str
    destination_port: str
    status: str
    last_updated: datetime


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------
class ContainerOut(ORMBase):
    container_number: str
    vessel_imo: str
    cargo_description: str
    origin_port: str
    destination_port: str
    status: str
    seal_number: str
    last_scan_port: str
    last_scan_time: datetime
    created_at: datetime


# ---------------------------------------------------------------------------
# Port event
# ---------------------------------------------------------------------------
class PortEventOut(ORMBase):
    container_number: str
    vessel_imo: str
    port_name: str
    event_type: str
    event_time: datetime
    terminal: str
    status: str
    source: str


# ---------------------------------------------------------------------------
# Shipment
# ---------------------------------------------------------------------------
class ShipmentOut(ORMBase):
    shipment_id: str
    seller: str
    buyer: str
    invoice_number: str
    container_number: str
    vessel_imo: str
    origin_port: str
    destination_port: str
    cargo_description: str
    declared_value: float
    currency: str
    expected_departure: datetime
    expected_arrival: datetime
    claimed_status: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------
class InspectionOut(ORMBase):
    inspection_id: str
    container_number: str
    inspector_name: str
    inspection_type: str
    inspection_date: datetime
    location: str
    result: str
    notes: Optional[str] = None
    document_hash: str


# ---------------------------------------------------------------------------
# GPS observation
# ---------------------------------------------------------------------------
class GpsObservationOut(ORMBase):
    vessel_imo: str
    latitude: float
    longitude: float
    speed: float
    heading: float
    timestamp: datetime
    source: str


# ---------------------------------------------------------------------------
# Shipment document
# ---------------------------------------------------------------------------
class ShipmentDocumentOut(ORMBase):
    shipment_id: str
    document_type: str
    document_number: str
    issued_by: str
    issue_date: datetime
    document_hash: str
    declared_vessel: str
    declared_container: str
    declared_origin: str
    declared_destination: str
    declared_cargo: str
    declared_value: float


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
class VerifyRequest(BaseModel):
    shipment_id: str = Field(..., examples=["CP001"])


class VerificationChecks(BaseModel):
    vessel_exists: bool
    container_exists: bool
    vessel_container_match: bool
    origin_match: bool
    destination_match: bool
    vessel_status_valid: bool
    port_events_consistent: bool
    gps_consistent: bool
    inspection_passed: bool
    documents_consistent: bool


class VerificationReport(BaseModel):
    shipment_id: str
    verification_status: str  # VERIFIED | REJECTED | HELD
    confidence: float
    checks: VerificationChecks
    reasons: List[str]
    reason_details: Dict[str, str] = Field(default_factory=dict)
    evidence_sources: List[str]
    evidence_hash: str
    generated_at: datetime


class AboutOut(BaseModel):
    name: str
    environment: str
    data_source: str
    description: str


class HealthOut(BaseModel):
    status: str
    service: str
    data_source: str
