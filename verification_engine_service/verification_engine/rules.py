from __future__ import annotations
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .config import settings
from .models import EvidenceBundle
from .schemas import RuleResult

# ---------------------------------------------------------------------------
# ASSUMPTION: a small fixed table of port coordinates for the demo's trade
# lanes (Chennai <-> Dubai / Singapore corridor). This is a hackathon MVP —
# extend this table as new ports are needed. Not a real maritime database.
# ---------------------------------------------------------------------------
PORT_COORDINATES: Dict[str, Tuple[float, float]] = {
    "chennai": (13.0827, 80.2707),
    "dubai": (25.2048, 55.2708),
    "singapore": (1.2644, 103.8200),
    "mumbai": (18.9490, 72.9525),
    "colombo": (6.9271, 79.8612),
    "shanghai": (31.2304, 121.4737),
    "rotterdam": (51.9244, 4.4777),
}

EARTH_RADIUS_KM = 6371.0

IN_TRANSIT_STATUSES = {"IN_TRANSIT", "UNDERWAY"}
CONFLICTING_STATUSES = {"DOCKED", "MOORED", "ANCHORED", "IDLE"}


def _norm(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _port_coords(name: Optional[str]) -> Optional[Tuple[float, float]]:
    return PORT_COORDINATES.get(_norm(name))


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))


def _bearing_rad(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.atan2(y, x)


def cross_track_distance_km(point: Tuple[float, float], start: Tuple[float, float], end: Tuple[float, float]) -> float:
    """
    Approximate cross-track distance of `point` from the great-circle path
    between `start` and `end` (standard spherical cross-track formula).
    This is a coarse "is this vessel roughly on its declared route" check —
    not real maritime navigation software.
    """
    R = EARTH_RADIUS_KM
    d13 = haversine_km(start, point) / R
    brng13 = _bearing_rad(start, point)
    brng12 = _bearing_rad(start, end)
    xt = math.asin(max(-1.0, min(1.0, math.sin(d13) * math.sin(brng13 - brng12))))
    return abs(xt * R)


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        v = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def rule_shipment_exists(evidence: EvidenceBundle) -> RuleResult:
    if evidence.shipment is None:
        return RuleResult(rule="SHIPMENT_EXISTS", passed=False, severity="CRITICAL",
                           message="SHIPMENT_NOT_FOUND: shipment does not exist in evidence sources")
    return RuleResult(rule="SHIPMENT_EXISTS", passed=True, severity="CRITICAL",
                       message="Shipment exists in shipment registry")


def rule_vessel_exists(evidence: EvidenceBundle) -> RuleResult:
    if evidence.vessel is None:
        return RuleResult(rule="VESSEL_EXISTS", passed=False, severity="CRITICAL",
                           message="VESSEL_NOT_FOUND: vessel referenced by shipment does not exist")
    return RuleResult(rule="VESSEL_EXISTS", passed=True, severity="CRITICAL",
                       message="Vessel exists in vessel registry")


def rule_container_exists(evidence: EvidenceBundle) -> RuleResult:
    if evidence.container is None:
        return RuleResult(rule="CONTAINER_EXISTS", passed=False, severity="CRITICAL",
                           message="CONTAINER_NOT_FOUND: claimed container does not exist")
    return RuleResult(rule="CONTAINER_EXISTS", passed=True, severity="CRITICAL",
                       message="Container exists in container registry")


def rule_vessel_container_match(evidence: EvidenceBundle) -> RuleResult:
    if evidence.container is None or evidence.shipment is None:
        return RuleResult(rule="VESSEL_CONTAINER_MATCH", passed=False, severity="CRITICAL",
                           message="VESSEL_MISMATCH: cannot compare, container or shipment missing")
    shipment_imo = _norm(evidence.shipment.get("vessel_imo"))
    container_imo = _norm(evidence.container.get("vessel_imo"))
    if shipment_imo and container_imo and shipment_imo != container_imo:
        return RuleResult(rule="VESSEL_CONTAINER_MATCH", passed=False, severity="CRITICAL",
                           message=f"VESSEL_MISMATCH: shipment claims vessel IMO '{shipment_imo}' but "
                                   f"container is registered to vessel IMO '{container_imo}'")
    return RuleResult(rule="VESSEL_CONTAINER_MATCH", passed=True, severity="CRITICAL",
                       message="Shipment vessel matches container's registered vessel")


def rule_origin_match(evidence: EvidenceBundle) -> RuleResult:
    if evidence.shipment is None:
        return RuleResult(rule="ORIGIN_MATCH", passed=False, severity="HIGH",
                           message="ORIGIN_MISMATCH: shipment missing")
    shipment_origin = _norm(evidence.shipment.get("origin_port"))
    candidates = []
    if evidence.container:
        candidates.append(_norm(evidence.container.get("origin_port")))
    for doc in evidence.documents:
        candidates.append(_norm(doc.get("origin_port")))
    conflicting = [c for c in candidates if c and shipment_origin and c != shipment_origin]
    if conflicting:
        return RuleResult(rule="ORIGIN_MATCH", passed=False, severity="HIGH",
                           message=f"ORIGIN_MISMATCH: shipment declares origin '{shipment_origin}' "
                                   f"but other evidence declares '{conflicting[0]}'")
    return RuleResult(rule="ORIGIN_MATCH", passed=True, severity="HIGH",
                       message="Origin port is consistent across evidence sources")


def rule_destination_match(evidence: EvidenceBundle) -> RuleResult:
    if evidence.shipment is None:
        return RuleResult(rule="DESTINATION_MATCH", passed=False, severity="CRITICAL",
                           message="DESTINATION_MISMATCH: shipment missing")
    shipment_dest = _norm(evidence.shipment.get("destination_port"))
    candidates = []
    if evidence.container:
        candidates.append(_norm(evidence.container.get("destination_port")))
    for doc in evidence.documents:
        candidates.append(_norm(doc.get("destination_port")))
    conflicting = [c for c in candidates if c and shipment_dest and c != shipment_dest]
    if conflicting:
        return RuleResult(rule="DESTINATION_MATCH", passed=False, severity="CRITICAL",
                           message=f"DESTINATION_MISMATCH: shipment declares destination '{shipment_dest}' "
                                   f"but other evidence declares '{conflicting[0]}'")
    return RuleResult(rule="DESTINATION_MATCH", passed=True, severity="CRITICAL",
                       message="Destination port is consistent across evidence sources")


def rule_vessel_status(evidence: EvidenceBundle) -> RuleResult:
    if evidence.vessel is None or evidence.shipment is None:
        return RuleResult(rule="VESSEL_STATUS", passed=False, severity="CRITICAL",
                           message="VESSEL_STATUS_CONFLICT: cannot verify, vessel or shipment missing")
    claimed = _norm(evidence.shipment.get("claimed_status")).upper()
    actual = _norm(evidence.vessel.get("status")).upper()
    if claimed in IN_TRANSIT_STATUSES and actual in CONFLICTING_STATUSES:
        return RuleResult(rule="VESSEL_STATUS", passed=False, severity="CRITICAL",
                           message=f"VESSEL_STATUS_CONFLICT: shipment claims '{claimed}' but "
                                   f"vessel registry reports '{actual}'")
    return RuleResult(rule="VESSEL_STATUS", passed=True, severity="CRITICAL",
                       message=f"Vessel status '{actual}' is compatible with claimed status '{claimed}'")


def rule_port_event_consistency(evidence: EvidenceBundle) -> RuleResult:
    events = sorted(
        [e for e in evidence.port_events if _parse_ts(e.get("timestamp"))],
        key=lambda e: _parse_ts(e.get("timestamp")),
    )
    if not events:
        return RuleResult(rule="PORT_EVENT_CONSISTENCY", passed=False, severity="HIGH",
                           message="PORT_EVENT_CONFLICT: no port events available to corroborate movement")

    # A DEPARTURE from a port followed later by an ARRIVAL at the SAME port
    # with no intervening event elsewhere indicates a return with no
    # recorded voyage context.
    last_departure_port = None
    for e in events:
        etype = _norm(e.get("event_type")).upper()
        port = _norm(e.get("port"))
        if etype == "DEPARTURE":
            last_departure_port = port
        elif etype == "ARRIVAL" and last_departure_port == port:
            return RuleResult(rule="PORT_EVENT_CONSISTENCY", passed=False, severity="HIGH",
                               message=f"PORT_EVENT_CONFLICT: vessel departed '{port}' and later arrived "
                                       f"back at '{port}' with no intervening voyage event")

    if evidence.shipment:
        claimed = _norm(evidence.shipment.get("claimed_status")).upper()
        origin = _norm(evidence.shipment.get("origin_port"))
        if claimed in IN_TRANSIT_STATUSES:
            has_departure = any(
                _norm(e.get("event_type")).upper() == "DEPARTURE" and _norm(e.get("port")) == origin
                for e in events
            )
            if not has_departure:
                return RuleResult(rule="PORT_EVENT_CONSISTENCY", passed=False, severity="HIGH",
                                   message=f"PORT_EVENT_CONFLICT: shipment claims departure from '{origin}' "
                                           f"but no DEPARTURE event exists for that port")

    return RuleResult(rule="PORT_EVENT_CONSISTENCY", passed=True, severity="HIGH",
                       message="Port event sequence is chronologically consistent")


def rule_gps_consistency(evidence: EvidenceBundle) -> RuleResult:
    if not evidence.gps:
        return RuleResult(rule="GPS_CONSISTENCY", passed=False, severity="HIGH",
                           message="GPS_ROUTE_CONFLICT: no GPS observations available")
    if evidence.shipment is None:
        return RuleResult(rule="GPS_CONSISTENCY", passed=False, severity="HIGH",
                           message="GPS_ROUTE_CONFLICT: shipment missing, cannot evaluate route")

    origin = _port_coords(evidence.shipment.get("origin_port"))
    destination = _port_coords(evidence.shipment.get("destination_port"))
    if origin is None or destination is None:
        return RuleResult(rule="GPS_CONSISTENCY", passed=True, severity="HIGH",
                           message="GPS_ROUTE_UNVERIFIABLE: origin/destination not in known port table, "
                                   "route check skipped (not counted as a failure)")

    dated = [g for g in evidence.gps if _parse_ts(g.get("timestamp"))]
    latest = sorted(dated, key=lambda g: _parse_ts(g.get("timestamp")))[-1] if dated else evidence.gps[-1]
    point = (float(latest.get("lat", 0.0)), float(latest.get("lon", 0.0)))

    distance = cross_track_distance_km(point, origin, destination)
    if distance > settings.gps_max_distance_km:
        return RuleResult(rule="GPS_CONSISTENCY", passed=False, severity="HIGH",
                           message=f"GPS_ROUTE_CONFLICT: latest GPS position is {distance:.0f} km off the "
                                   f"declared route (limit {settings.gps_max_distance_km:.0f} km)")
    return RuleResult(rule="GPS_CONSISTENCY", passed=True, severity="HIGH",
                       message=f"Latest GPS position is {distance:.0f} km from declared route, within tolerance")


def rule_inspection(evidence: EvidenceBundle) -> RuleResult:
    if evidence.inspection is None:
        return RuleResult(rule="INSPECTION", passed=True, severity="MEDIUM",
                           message="INSPECTION_UNAVAILABLE: no inspection record found; not treated as a failure")
    result = _norm(evidence.inspection.get("result")).upper()
    if result == "PASS":
        return RuleResult(rule="INSPECTION", passed=True, severity="MEDIUM", message="Inspection result: PASS")
    if result == "FAILED":
        return RuleResult(rule="INSPECTION", passed=False, severity="HIGH",
                           message="INSPECTION_FAILED: cargo inspection reported FAILED")
    return RuleResult(rule="INSPECTION", passed=True, severity="MEDIUM",
                       message=f"INSPECTION_UNAVAILABLE: unrecognized inspection result '{result}'")


def rule_document_consistency(evidence: EvidenceBundle) -> RuleResult:
    if not evidence.documents:
        return RuleResult(rule="DOCUMENT_CONSISTENCY", passed=True, severity="HIGH",
                           message="No shipment documents available; not treated as a failure")
    if evidence.shipment is None:
        return RuleResult(rule="DOCUMENT_CONSISTENCY", passed=False, severity="HIGH",
                           message="DOCUMENT_MISMATCH: shipment missing, cannot compare documents")

    shipment = evidence.shipment
    mismatches: List[str] = []
    for doc in evidence.documents:
        if evidence.container:
            doc_container = _norm(doc.get("container_number"))
            if doc_container and doc_container != _norm(evidence.container.get("container_number")):
                mismatches.append("DOCUMENT_CONTAINER_MISMATCH")
        if evidence.vessel:
            doc_vessel = _norm(doc.get("vessel_name"))
            if doc_vessel and doc_vessel != _norm(evidence.vessel.get("name")):
                mismatches.append("DOCUMENT_VESSEL_MISMATCH")
        doc_origin = _norm(doc.get("origin_port"))
        if doc_origin and doc_origin != _norm(shipment.get("origin_port")):
            mismatches.append("DOCUMENT_ORIGIN_MISMATCH")
        doc_dest = _norm(doc.get("destination_port"))
        if doc_dest and doc_dest != _norm(shipment.get("destination_port")):
            mismatches.append("DOCUMENT_DESTINATION_MISMATCH")
        doc_cargo = _norm(doc.get("declared_cargo"))
        if doc_cargo and doc_cargo != _norm(shipment.get("cargo_description")):
            mismatches.append("DOCUMENT_CARGO_MISMATCH")

    if mismatches:
        unique = sorted(set(mismatches))
        return RuleResult(rule="DOCUMENT_CONSISTENCY", passed=False, severity="HIGH",
                           message=f"{unique[0]}: shipment documents conflict with other evidence "
                                   f"({', '.join(unique)})")
    return RuleResult(rule="DOCUMENT_CONSISTENCY", passed=True, severity="HIGH",
                       message="Shipment documents are consistent with other evidence")


def rule_cargo_consistency(evidence: EvidenceBundle) -> RuleResult:
    if evidence.shipment is None:
        return RuleResult(rule="CARGO_CONSISTENCY", passed=False, severity="MEDIUM",
                           message="CARGO_MISMATCH: shipment missing")
    shipment_cargo = _norm(evidence.shipment.get("cargo_description"))
    candidates = []
    if evidence.container:
        candidates.append(_norm(evidence.container.get("cargo_description")))
    for doc in evidence.documents:
        candidates.append(_norm(doc.get("declared_cargo")))
    conflicting = [c for c in candidates if c and shipment_cargo and c != shipment_cargo]
    if conflicting:
        return RuleResult(rule="CARGO_CONSISTENCY", passed=False, severity="MEDIUM",
                           message=f"CARGO_MISMATCH: shipment declares cargo '{shipment_cargo}' but "
                                   f"other evidence declares '{conflicting[0]}'")
    return RuleResult(rule="CARGO_CONSISTENCY", passed=True, severity="MEDIUM",
                       message="Cargo description is consistent across evidence sources")


def rule_data_freshness(evidence: EvidenceBundle) -> RuleResult:
    timestamps: List[datetime] = []
    if evidence.vessel and evidence.vessel.get("last_updated"):
        ts = _parse_ts(evidence.vessel.get("last_updated"))
        if ts:
            timestamps.append(ts)
    for g in evidence.gps:
        ts = _parse_ts(g.get("timestamp"))
        if ts:
            timestamps.append(ts)

    if not timestamps:
        return RuleResult(rule="DATA_FRESHNESS", passed=True, severity="LOW",
                           message="No timestamped evidence available to assess freshness; not treated as a failure")

    newest = max(timestamps)
    age_hours = (datetime.now(timezone.utc) - newest).total_seconds() / 3600.0
    if age_hours > settings.max_evidence_age_hours:
        return RuleResult(rule="DATA_FRESHNESS", passed=False, severity="LOW",
                           message=f"EVIDENCE_STALE: newest evidence is {age_hours:.1f}h old "
                                   f"(limit {settings.max_evidence_age_hours:.0f}h)")
    return RuleResult(rule="DATA_FRESHNESS", passed=True, severity="LOW",
                       message=f"Evidence is fresh ({age_hours:.1f}h old)")


ALL_RULES = [
    rule_shipment_exists,
    rule_vessel_exists,
    rule_container_exists,
    rule_vessel_container_match,
    rule_origin_match,
    rule_destination_match,
    rule_vessel_status,
    rule_port_event_consistency,
    rule_gps_consistency,
    rule_inspection,
    rule_document_consistency,
    rule_cargo_consistency,
    rule_data_freshness,
]
