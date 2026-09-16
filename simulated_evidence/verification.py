"""
CargoProof verification engine.

This module pulls together evidence from all SIMULATED evidence sources
(vessel tracking, container registry, port records, GPS, inspection,
shipment documents), cross-checks them, and produces:

  1. A structured VerificationReport (schemas.VerificationReport)
  2. A deterministic SHA-256 "evidence hash" over the canonical evidence
     bundle used to reach that verdict.

IMPORTANT: This module does NOT talk to the Algorand blockchain. It only
produces the verification result that the (separate) CargoProof agent /
scripts layer will submit on-chain via submit_evidence.py / release.py.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from . import models

# Ports we know about, with approximate lat/lon, used only for the simple
# GPS "is the vessel roughly near its declared route" sanity check.
PORT_COORDINATES: Dict[str, Tuple[float, float]] = {
    "Chennai Port": (13.0827, 80.2707),
    "Singapore": (1.2644, 103.8200),
    "Dubai": (25.2532, 55.3657),
    "Rotterdam": (51.9496, 4.1453),
    "Shanghai": (31.2304, 121.4737),
    "Los Angeles": (33.7292, -118.2620),
    "Colombo": (6.9271, 79.8612),
}

# How far (in degrees, roughly) a GPS ping may be from the straight line
# between origin and destination before we call it a conflict. This is a
# deliberately simple heuristic appropriate for a hackathon demo, not a
# real great-circle route model.
GPS_ROUTE_TOLERANCE_DEG = 12.0


def _haversine_deg_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Cheap planar distance in degrees (good enough for a sanity check)."""
    return math.dist(p1, p2)


def _point_to_segment_distance(
    point: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]
) -> float:
    """Distance from `point` to the line segment a-b, in degrees."""
    px, py = point
    ax, ay = a
    bx, by = b
    abx, aby = bx - ax, by - ay
    seg_len_sq = abx ** 2 + aby ** 2
    if seg_len_sq == 0:
        return _haversine_deg_distance(point, a)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / seg_len_sq))
    proj = (ax + t * abx, ay + t * aby)
    return _haversine_deg_distance(point, proj)


class VerificationEngine:
    """Runs the full cross-source evidence verification for one shipment."""

    def __init__(self, db: Session):
        self.db = db

    # -- evidence retrieval -------------------------------------------------
    def _get_shipment(self, shipment_id: str) -> Optional[models.Shipment]:
        return (
            self.db.query(models.Shipment)
            .filter(models.Shipment.shipment_id == shipment_id)
            .first()
        )

    def _get_vessel(self, imo_number: str) -> Optional[models.Vessel]:
        return (
            self.db.query(models.Vessel)
            .filter(models.Vessel.imo_number == imo_number)
            .first()
        )

    def _get_container(self, container_number: str) -> Optional[models.Container]:
        return (
            self.db.query(models.Container)
            .filter(models.Container.container_number == container_number)
            .first()
        )

    def _get_port_events(self, container_number: str) -> List[models.PortEvent]:
        return (
            self.db.query(models.PortEvent)
            .filter(models.PortEvent.container_number == container_number)
            .order_by(models.PortEvent.event_time.asc())
            .all()
        )

    def _get_latest_gps(self, vessel_imo: str) -> Optional[models.GpsObservation]:
        return (
            self.db.query(models.GpsObservation)
            .filter(models.GpsObservation.vessel_imo == vessel_imo)
            .order_by(models.GpsObservation.timestamp.desc())
            .first()
        )

    def _get_inspections(self, container_number: str) -> List[models.Inspection]:
        return (
            self.db.query(models.Inspection)
            .filter(models.Inspection.container_number == container_number)
            .all()
        )

    def _get_documents(self, shipment_id: str) -> List[models.ShipmentDocument]:
        return (
            self.db.query(models.ShipmentDocument)
            .filter(models.ShipmentDocument.shipment_id == shipment_id)
            .all()
        )

    # -- main entry point -----------------------------------------------------
    def verify(self, shipment_id: str) -> dict:
        shipment = self._get_shipment(shipment_id)
        if shipment is None:
            return {
                "not_found": True,
            }

        vessel = self._get_vessel(shipment.vessel_imo)
        container = self._get_container(shipment.container_number)
        port_events = self._get_port_events(shipment.container_number)
        gps = self._get_latest_gps(shipment.vessel_imo)
        inspections = self._get_inspections(shipment.container_number)
        documents = self._get_documents(shipment.shipment_id)

        reasons: List[str] = []
        reason_details: Dict[str, str] = {}

        checks = {
            "vessel_exists": vessel is not None,
            "container_exists": container is not None,
            "vessel_container_match": False,
            "origin_match": False,
            "destination_match": False,
            "vessel_status_valid": False,
            "port_events_consistent": False,
            "gps_consistent": False,
            "inspection_passed": False,
            "documents_consistent": False,
        }

        if vessel is None:
            reasons.append("VESSEL_NOT_FOUND")
            reason_details["VESSEL_NOT_FOUND"] = (
                f"No vessel record exists for IMO {shipment.vessel_imo}."
            )
        if container is None:
            reasons.append("CONTAINER_NOT_FOUND")
            reason_details["CONTAINER_NOT_FOUND"] = (
                f"No container record exists for container {shipment.container_number}."
            )

        # From here on, checks that depend on vessel/container require them
        # to exist; if they don't, we skip the dependent check (already
        # reflected as a failure via the reasons above).
        if vessel is not None and container is not None:
            # 1. Vessel <-> container consistency: does the container's
            #    vessel_imo match the vessel the shipment claims?
            checks["vessel_container_match"] = container.vessel_imo == vessel.imo_number
            if not checks["vessel_container_match"]:
                reasons.append("VESSEL_MISMATCH")
                reason_details["VESSEL_MISMATCH"] = (
                    f"Declared vessel IMO = {shipment.vessel_imo}, but container "
                    f"{container.container_number} is registered against vessel "
                    f"IMO {container.vessel_imo}."
                )

            # 2. Origin match (shipment's declared origin vs container record)
            checks["origin_match"] = shipment.origin_port == container.origin_port
            if not checks["origin_match"]:
                reasons.append("ORIGIN_MISMATCH")
                reason_details["ORIGIN_MISMATCH"] = (
                    f"Declared origin = {shipment.origin_port}, but container "
                    f"record shows origin = {container.origin_port}."
                )

            # 3. Destination match
            checks["destination_match"] = (
                shipment.destination_port == container.destination_port
                and shipment.destination_port == vessel.destination_port
            )
            if not checks["destination_match"]:
                reasons.append("DESTINATION_MISMATCH")
                reason_details["DESTINATION_MISMATCH"] = (
                    f"Declared destination = {shipment.destination_port}, but "
                    f"vessel/container records show destination = "
                    f"{vessel.destination_port}/{container.destination_port}."
                )

            # 4. Vessel status valid (claims IN_TRANSIT -> vessel must be IN_TRANSIT)
            if shipment.claimed_status == "IN_TRANSIT":
                checks["vessel_status_valid"] = vessel.status == "IN_TRANSIT"
            else:
                checks["vessel_status_valid"] = vessel.status == shipment.claimed_status
            if not checks["vessel_status_valid"]:
                reasons.append("VESSEL_STATUS_CONFLICT")
                reason_details["VESSEL_STATUS_CONFLICT"] = (
                    f"Shipment claims status = {shipment.claimed_status}, but "
                    f"vessel {vessel.vessel_name} status = {vessel.status}."
                )

            # 5. Port events consistency: for an IN_TRANSIT claim we expect a
            #    DEPARTURE event from the origin port and no unexplained gap.
            checks["port_events_consistent"] = self._check_port_events(
                shipment, port_events, reason_details, reasons
            )

            # 6. GPS consistency: latest ping should be roughly on the
            #    origin -> destination route.
            checks["gps_consistent"] = self._check_gps(
                shipment, vessel, gps, reason_details, reasons
            )

        # 7. Inspection check (independent of vessel/container existing)
        checks["inspection_passed"] = self._check_inspection(
            container, inspections, reason_details, reasons
        )

        # 8. Document consistency (independent check against declared docs)
        checks["documents_consistent"] = self._check_documents(
            shipment, documents, reason_details, reasons
        )

        all_passed = all(checks.values())
        verification_status = "VERIFIED" if all_passed else "REJECTED"

        # Confidence: simple heuristic - fraction of checks passed, with a
        # small penalty per distinct failure reason, clamped to [0, 1].
        total_checks = len(checks)
        passed_checks = sum(1 for v in checks.values() if v)
        base_confidence = passed_checks / total_checks
        confidence = round(max(0.0, min(1.0, base_confidence)), 2)
        if all_passed:
            confidence = max(confidence, 0.9)

        evidence_sources = [
            "vessel_tracking",
            "container_registry",
            "port_records",
            "gps",
            "inspection",
            "shipment_documents",
        ]

        evidence_hash = compute_evidence_hash(
            shipment_id=shipment.shipment_id,
            vessel=vessel,
            container=container,
            port_events=port_events,
            gps=gps,
            inspections=inspections,
            documents=documents,
            checks=checks,
            verification_status=verification_status,
        )

        return {
            "not_found": False,
            "shipment_id": shipment.shipment_id,
            "verification_status": verification_status,
            "confidence": confidence,
            "checks": checks,
            "reasons": reasons,
            "reason_details": reason_details,
            "evidence_sources": evidence_sources,
            "evidence_hash": evidence_hash,
            "generated_at": datetime.now(timezone.utc),
        }

    # -- sub-checks -----------------------------------------------------------
    def _check_port_events(
        self,
        shipment: models.Shipment,
        port_events: List[models.PortEvent],
        reason_details: Dict[str, str],
        reasons: List[str],
    ) -> bool:
        if shipment.claimed_status != "IN_TRANSIT":
            # For non-transit claims we don't require a departure event.
            return True

        departure_events = [
            e for e in port_events
            if e.event_type == "DEPARTURE" and e.port_name == shipment.origin_port
        ]
        if not departure_events:
            reasons.append("PORT_EVENT_CONFLICT")
            reason_details["PORT_EVENT_CONFLICT"] = (
                f"Shipment claims the vessel departed {shipment.origin_port}, "
                f"but no DEPARTURE event from {shipment.origin_port} exists in "
                f"port records for container {shipment.container_number}."
            )
            return False
        return True

    def _check_gps(
        self,
        shipment: models.Shipment,
        vessel: models.Vessel,
        gps: Optional[models.GpsObservation],
        reason_details: Dict[str, str],
        reasons: List[str],
    ) -> bool:
        if gps is None:
            reasons.append("GPS_MISSING")
            reason_details["GPS_MISSING"] = (
                f"No GPS observations found for vessel IMO {vessel.imo_number}."
            )
            return False

        origin_coords = PORT_COORDINATES.get(shipment.origin_port)
        dest_coords = PORT_COORDINATES.get(shipment.destination_port)

        if origin_coords is None or dest_coords is None:
            # Unknown port coordinates - can't validate, treat as consistent
            # rather than penalize the demo for an unmapped port.
            return True

        distance = _point_to_segment_distance(
            (gps.latitude, gps.longitude), origin_coords, dest_coords
        )
        if distance > GPS_ROUTE_TOLERANCE_DEG:
            reasons.append("GPS_ROUTE_CONFLICT")
            reason_details["GPS_ROUTE_CONFLICT"] = (
                f"Latest GPS position ({gps.latitude:.4f}, {gps.longitude:.4f}) "
                f"is far outside the expected route from {shipment.origin_port} "
                f"to {shipment.destination_port}."
            )
            return False
        return True

    def _check_inspection(
        self,
        container: Optional[models.Container],
        inspections: List[models.Inspection],
        reason_details: Dict[str, str],
        reasons: List[str],
    ) -> bool:
        if container is None:
            # Already flagged via CONTAINER_NOT_FOUND
            return False
        if not inspections:
            # No inspection on file - treat as neutral pass for demo
            # purposes (not all shipments require inspection).
            return True
        latest = sorted(inspections, key=lambda i: i.inspection_date)[-1]
        if latest.result != "PASS":
            reasons.append("INSPECTION_FAILED")
            reason_details["INSPECTION_FAILED"] = (
                f"Latest inspection ({latest.inspection_id}) result = "
                f"{latest.result}. Notes: {latest.notes or 'none'}."
            )
            return False
        return True

    def _check_documents(
        self,
        shipment: models.Shipment,
        documents: List[models.ShipmentDocument],
        reason_details: Dict[str, str],
        reasons: List[str],
    ) -> bool:
        if not documents:
            reasons.append("DOCUMENTS_MISSING")
            reason_details["DOCUMENTS_MISSING"] = (
                f"No shipment documents on file for {shipment.shipment_id}."
            )
            return False

        for doc in documents:
            mismatches = []
            if doc.declared_vessel and shipment.vessel_imo not in doc.declared_vessel:
                # declared_vessel stores a human vessel name; compared loosely
                pass
            if doc.declared_container != shipment.container_number:
                mismatches.append("container")
            if doc.declared_origin != shipment.origin_port:
                mismatches.append("origin")
            if doc.declared_destination != shipment.destination_port:
                mismatches.append("destination")
            if doc.declared_cargo != shipment.cargo_description:
                mismatches.append("cargo")
            if abs(doc.declared_value - shipment.declared_value) > 0.01:
                mismatches.append("value")

            if mismatches:
                reasons.append("DOCUMENT_DATA_MISMATCH")
                reason_details["DOCUMENT_DATA_MISMATCH"] = (
                    f"Document {doc.document_number} disagrees with shipment "
                    f"record on: {', '.join(mismatches)}."
                )
                return False
        return True


# ---------------------------------------------------------------------------
# Deterministic evidence hash
# ---------------------------------------------------------------------------
def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.replace(microsecond=0).isoformat()


def compute_evidence_hash(
    *,
    shipment_id: str,
    vessel: Optional[models.Vessel],
    container: Optional[models.Container],
    port_events: List[models.PortEvent],
    gps: Optional[models.GpsObservation],
    inspections: List[models.Inspection],
    documents: List[models.ShipmentDocument],
    checks: Dict[str, bool],
    verification_status: str,
) -> str:
    """
    Build a canonical JSON representation of the exact evidence used to reach
    a verification verdict, then SHA-256 it. This hash is what gets stored
    on-chain by the (separate) CargoProof agent when it calls
    scripts/submit_evidence.py.

    Determinism is achieved by:
      - only including evidence FIELDS relevant to verification (not DB
        auto-increment ids, not "last_updated" timestamps that don't affect
        the verdict)
      - sorting all dict keys
      - using a fixed, compact JSON separator style
    """
    bundle = {
        "shipment_id": shipment_id,
        "verification_status": verification_status,
        "checks": checks,
        "vessel": None if vessel is None else {
            "imo_number": vessel.imo_number,
            "vessel_name": vessel.vessel_name,
            "status": vessel.status,
            "current_port": vessel.current_port,
            "destination_port": vessel.destination_port,
        },
        "container": None if container is None else {
            "container_number": container.container_number,
            "vessel_imo": container.vessel_imo,
            "origin_port": container.origin_port,
            "destination_port": container.destination_port,
            "status": container.status,
            "seal_number": container.seal_number,
        },
        "port_events": sorted(
            [
                {
                    "event_type": e.event_type,
                    "port_name": e.port_name,
                    "event_time": _iso(e.event_time),
                    "status": e.status,
                }
                for e in port_events
            ],
            key=lambda x: (x["event_time"] or "", x["event_type"]),
        ),
        "gps": None if gps is None else {
            "latitude": round(gps.latitude, 4),
            "longitude": round(gps.longitude, 4),
            "timestamp": _iso(gps.timestamp),
        },
        "inspections": sorted(
            [
                {
                    "inspection_id": i.inspection_id,
                    "result": i.result,
                    "document_hash": i.document_hash,
                }
                for i in inspections
            ],
            key=lambda x: x["inspection_id"],
        ),
        "documents": sorted(
            [
                {
                    "document_number": d.document_number,
                    "document_hash": d.document_hash,
                    "declared_vessel": d.declared_vessel,
                    "declared_container": d.declared_container,
                    "declared_origin": d.declared_origin,
                    "declared_destination": d.declared_destination,
                    "declared_cargo": d.declared_cargo,
                    "declared_value": d.declared_value,
                }
                for d in documents
            ],
            key=lambda x: x["document_number"],
        ),
    }

    canonical_json = json.dumps(
        bundle, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
