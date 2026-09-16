from verification_engine import rules
from verification_engine.models import EvidenceBundle

from .fixtures import (
    bundle_cp001_good,
    bundle_cp002_vessel_mismatch,
    bundle_cp003_container_not_found,
    bundle_cp004_wrong_destination,
    bundle_cp005_vessel_not_in_transit,
    bundle_cp006_port_event_conflict,
    bundle_cp007_gps_conflict,
    bundle_cp008_inspection_failure,
    bundle_cp009_document_conflict,
)


def test_shipment_exists():
    assert rules.rule_shipment_exists(bundle_cp001_good()).passed is True


def test_missing_shipment():
    r = rules.rule_shipment_exists(EvidenceBundle(shipment=None))
    assert r.passed is False
    assert r.severity == "CRITICAL"


def test_vessel_exists():
    assert rules.rule_vessel_exists(bundle_cp001_good()).passed is True


def test_missing_vessel():
    b = bundle_cp001_good()
    b.vessel = None
    r = rules.rule_vessel_exists(b)
    assert r.passed is False
    assert r.severity == "CRITICAL"


def test_container_exists():
    assert rules.rule_container_exists(bundle_cp001_good()).passed is True


def test_missing_container():
    r = rules.rule_container_exists(bundle_cp003_container_not_found())
    assert r.passed is False
    assert r.severity == "CRITICAL"


def test_vessel_container_match():
    assert rules.rule_vessel_container_match(bundle_cp001_good()).passed is True


def test_vessel_mismatch():
    r = rules.rule_vessel_container_match(bundle_cp002_vessel_mismatch())
    assert r.passed is False
    assert r.severity == "CRITICAL"
    assert "VESSEL_MISMATCH" in r.message


def test_origin_match():
    assert rules.rule_origin_match(bundle_cp001_good()).passed is True


def test_destination_match():
    assert rules.rule_destination_match(bundle_cp001_good()).passed is True


def test_destination_mismatch():
    r = rules.rule_destination_match(bundle_cp004_wrong_destination())
    assert r.passed is False
    assert r.severity == "CRITICAL"
    assert "DESTINATION_MISMATCH" in r.message


def test_vessel_status():
    assert rules.rule_vessel_status(bundle_cp001_good()).passed is True


def test_vessel_status_conflict():
    r = rules.rule_vessel_status(bundle_cp005_vessel_not_in_transit())
    assert r.passed is False
    assert r.severity == "CRITICAL"
    assert "VESSEL_STATUS_CONFLICT" in r.message


def test_port_event_consistency():
    assert rules.rule_port_event_consistency(bundle_cp001_good()).passed is True


def test_port_event_conflict():
    r = rules.rule_port_event_consistency(bundle_cp006_port_event_conflict())
    assert r.passed is False
    assert "PORT_EVENT_CONFLICT" in r.message


def test_gps_consistency():
    assert rules.rule_gps_consistency(bundle_cp001_good()).passed is True


def test_gps_conflict():
    r = rules.rule_gps_consistency(bundle_cp007_gps_conflict())
    assert r.passed is False
    assert "GPS_ROUTE_CONFLICT" in r.message


def test_inspection_pass():
    assert rules.rule_inspection(bundle_cp001_good()).passed is True


def test_inspection_failure():
    r = rules.rule_inspection(bundle_cp008_inspection_failure())
    assert r.passed is False
    assert "INSPECTION_FAILED" in r.message


def test_inspection_unavailable_not_a_failure():
    b = bundle_cp001_good()
    b.inspection = None
    r = rules.rule_inspection(b)
    assert r.passed is True
    assert "INSPECTION_UNAVAILABLE" in r.message


def test_document_consistency():
    assert rules.rule_document_consistency(bundle_cp001_good()).passed is True


def test_document_conflict():
    r = rules.rule_document_consistency(bundle_cp009_document_conflict())
    assert r.passed is False
    assert "DOCUMENT_VESSEL_MISMATCH" in r.message


def test_cargo_consistency():
    assert rules.rule_cargo_consistency(bundle_cp001_good()).passed is True


def test_data_freshness_fresh():
    assert rules.rule_data_freshness(bundle_cp001_good()).passed is True


def test_data_freshness_stale():
    b = bundle_cp001_good()
    from datetime import timedelta
    stale_ts = (rules._parse_ts(b.vessel["last_updated"]) - timedelta(hours=48)).isoformat()
    b.vessel["last_updated"] = stale_ts
    b.gps = []
    r = rules.rule_data_freshness(b)
    assert r.passed is False
    assert "EVIDENCE_STALE" in r.message
