"""
Fixture evidence bundles for CP001-CP010, matching the scenarios and
expected outcomes described in the module spec. Each function returns a
fresh EvidenceBundle so tests can mutate it without affecting others.
"""
from datetime import datetime, timedelta, timezone

from verification_engine.models import EvidenceBundle

NOW = datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _base_shipment(**overrides):
    base = {
        "shipment_id": "CP001",
        "vessel_imo": "IMO0001",
        "container_number": "CONT0001",
        "origin_port": "Chennai",
        "destination_port": "Singapore",
        "claimed_status": "IN_TRANSIT",
        "cargo_description": "Electronics",
        "declared_value": 500000,
    }
    base.update(overrides)
    return base


def _base_vessel(**overrides):
    base = {
        "imo_number": "IMO0001",
        "name": "MV Test Carrier",
        "status": "IN_TRANSIT",
        "last_updated": _iso(NOW - timedelta(hours=1)),
    }
    base.update(overrides)
    return base


def _base_container(**overrides):
    base = {
        "container_number": "CONT0001",
        "vessel_imo": "IMO0001",
        "origin_port": "Chennai",
        "destination_port": "Singapore",
        "cargo_description": "Electronics",
    }
    base.update(overrides)
    return base


def _base_events(port: str = "Chennai"):
    return [
        {"event_type": "ARRIVAL", "port": port, "timestamp": _iso(NOW - timedelta(hours=10)), "vessel_imo": "IMO0001"},
        {"event_type": "LOADED", "port": port, "timestamp": _iso(NOW - timedelta(hours=8)), "vessel_imo": "IMO0001"},
        {"event_type": "DEPARTURE", "port": port, "timestamp": _iso(NOW - timedelta(hours=6)), "vessel_imo": "IMO0001"},
    ]


def _base_gps_good():
    # Roughly along the Chennai -> Singapore corridor.
    return [{"lat": 7.17355, "lon": 92.04535, "timestamp": _iso(NOW - timedelta(hours=1)), "vessel_imo": "IMO0001"}]


def _base_gps_bad():
    # Rotterdam — nowhere near a Chennai -> Singapore route.
    return [{"lat": 51.9244, "lon": 4.4777, "timestamp": _iso(NOW - timedelta(hours=1)), "vessel_imo": "IMO0001"}]


def _base_inspection(**overrides):
    base = {"shipment_id": "CP001", "result": "PASS", "inspector": "QA-1", "timestamp": _iso(NOW - timedelta(hours=2))}
    base.update(overrides)
    return base


def _base_documents(**overrides):
    doc = {
        "document_type": "bill_of_lading",
        "container_number": "CONT0001",
        "vessel_name": "MV Test Carrier",
        "origin_port": "Chennai",
        "destination_port": "Singapore",
        "declared_cargo": "Electronics",
        "declared_value": 500000,
        "issued_at": _iso(NOW - timedelta(hours=12)),
    }
    doc.update(overrides)
    return [doc]


def bundle_cp001_good() -> EvidenceBundle:
    return EvidenceBundle(
        shipment=_base_shipment(),
        vessel=_base_vessel(),
        container=_base_container(),
        port_events=_base_events(),
        gps=_base_gps_good(),
        inspection=_base_inspection(),
        documents=_base_documents(),
    )


def bundle_cp002_vessel_mismatch() -> EvidenceBundle:
    return EvidenceBundle(
        shipment=_base_shipment(shipment_id="CP002"),
        vessel=_base_vessel(),
        container=_base_container(vessel_imo="IMO9999"),
        port_events=_base_events(),
        gps=_base_gps_good(),
        inspection=_base_inspection(shipment_id="CP002"),
        documents=_base_documents(),
    )


def bundle_cp003_container_not_found() -> EvidenceBundle:
    return EvidenceBundle(
        shipment=_base_shipment(shipment_id="CP003"),
        vessel=_base_vessel(),
        container=None,
        port_events=_base_events(),
        gps=_base_gps_good(),
        inspection=_base_inspection(shipment_id="CP003"),
        documents=_base_documents(),
    )


def bundle_cp004_wrong_destination() -> EvidenceBundle:
    return EvidenceBundle(
        shipment=_base_shipment(shipment_id="CP004"),
        vessel=_base_vessel(),
        container=_base_container(destination_port="Dubai"),
        port_events=_base_events(),
        gps=_base_gps_good(),
        inspection=_base_inspection(shipment_id="CP004"),
        documents=_base_documents(),
    )


def bundle_cp005_vessel_not_in_transit() -> EvidenceBundle:
    return EvidenceBundle(
        shipment=_base_shipment(shipment_id="CP005"),
        vessel=_base_vessel(status="DOCKED"),
        container=_base_container(),
        port_events=_base_events(),
        gps=_base_gps_good(),
        inspection=_base_inspection(shipment_id="CP005"),
        documents=_base_documents(),
    )


def bundle_cp006_port_event_conflict() -> EvidenceBundle:
    events = [
        {"event_type": "DEPARTURE", "port": "Chennai", "timestamp": _iso(NOW - timedelta(hours=6)), "vessel_imo": "IMO0001"},
        {"event_type": "ARRIVAL", "port": "Chennai", "timestamp": _iso(NOW - timedelta(hours=2)), "vessel_imo": "IMO0001"},
    ]
    return EvidenceBundle(
        shipment=_base_shipment(shipment_id="CP006"),
        vessel=_base_vessel(),
        container=_base_container(),
        port_events=events,
        gps=_base_gps_good(),
        inspection=_base_inspection(shipment_id="CP006"),
        documents=_base_documents(),
    )


def bundle_cp007_gps_conflict() -> EvidenceBundle:
    return EvidenceBundle(
        shipment=_base_shipment(shipment_id="CP007"),
        vessel=_base_vessel(),
        container=_base_container(),
        port_events=_base_events(),
        gps=_base_gps_bad(),
        inspection=_base_inspection(shipment_id="CP007"),
        documents=_base_documents(),
    )


def bundle_cp008_inspection_failure() -> EvidenceBundle:
    return EvidenceBundle(
        shipment=_base_shipment(shipment_id="CP008"),
        vessel=_base_vessel(),
        container=_base_container(),
        port_events=_base_events(),
        gps=_base_gps_good(),
        inspection=_base_inspection(shipment_id="CP008", result="FAILED"),
        documents=_base_documents(),
    )


def bundle_cp009_document_conflict() -> EvidenceBundle:
    return EvidenceBundle(
        shipment=_base_shipment(shipment_id="CP009"),
        vessel=_base_vessel(),
        container=_base_container(),
        port_events=_base_events(),
        gps=_base_gps_good(),
        inspection=_base_inspection(shipment_id="CP009"),
        documents=_base_documents(vessel_name="MV Wrong Vessel"),
    )


def bundle_cp010_high_value_verified() -> EvidenceBundle:
    return EvidenceBundle(
        shipment=_base_shipment(shipment_id="CP010", declared_value=25_000_000),
        vessel=_base_vessel(),
        container=_base_container(),
        port_events=_base_events(),
        gps=_base_gps_good(),
        inspection=_base_inspection(shipment_id="CP010"),
        documents=_base_documents(declared_value=25_000_000),
    )
