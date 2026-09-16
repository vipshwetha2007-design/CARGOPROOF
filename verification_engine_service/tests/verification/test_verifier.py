import pytest

from verification_engine.verifier import (
    compute_confidence,
    determine_status,
    decision_for_status,
    evaluate_rules,
    verify_shipment,
)

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
    bundle_cp010_high_value_verified,
)
from .fake_client import FakeEvidenceClient


def test_confidence_score_perfect():
    results = evaluate_rules(bundle_cp001_good())
    assert compute_confidence(results) == 100


def test_confidence_score_critical_penalty():
    results = evaluate_rules(bundle_cp002_vessel_mismatch())
    score = compute_confidence(results)
    assert score <= 60  # at least one CRITICAL (-40) failure


def test_confidence_score_clamped_at_zero():
    from verification_engine.schemas import RuleResult
    all_critical = [RuleResult(rule="X", passed=False, severity="CRITICAL", message="x") for _ in range(5)]
    assert compute_confidence(all_critical) == 0


def test_verified_decision():
    results = evaluate_rules(bundle_cp001_good())
    status = determine_status(results)
    assert status == "VERIFIED"
    assert decision_for_status(status) == "RELEASE"


def test_rejected_decision_on_critical():
    results = evaluate_rules(bundle_cp002_vessel_mismatch())
    status = determine_status(results)
    assert status == "REJECTED"
    assert decision_for_status(status) == "DO_NOT_RELEASE"


def test_hold_decision_on_high_only():
    results = evaluate_rules(bundle_cp009_document_conflict())
    status = determine_status(results)
    assert status == "HOLD"
    assert decision_for_status(status) == "DO_NOT_RELEASE"


# ---------------------------------------------------------------------
# End-to-end pipeline tests via the fake client, covering CP001-CP010
# ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cp001_good_shipment_is_verified():
    report = await verify_shipment("CP001", client=FakeEvidenceClient(bundle_cp001_good()))
    assert report.verification_status == "VERIFIED"
    assert report.decision == "RELEASE"
    assert report.confidence_score == 100


@pytest.mark.asyncio
async def test_cp002_vessel_mismatch_is_rejected():
    report = await verify_shipment("CP002", client=FakeEvidenceClient(bundle_cp002_vessel_mismatch()))
    assert report.verification_status == "REJECTED"
    assert report.decision == "DO_NOT_RELEASE"
    assert any(r.rule == "VESSEL_CONTAINER_MATCH" for r in report.failed_rules)


@pytest.mark.asyncio
async def test_cp003_container_not_found_is_rejected():
    report = await verify_shipment("CP003", client=FakeEvidenceClient(bundle_cp003_container_not_found()))
    assert report.verification_status == "REJECTED"
    assert any(r.rule == "CONTAINER_EXISTS" for r in report.failed_rules)


@pytest.mark.asyncio
async def test_cp004_wrong_destination_is_rejected():
    report = await verify_shipment("CP004", client=FakeEvidenceClient(bundle_cp004_wrong_destination()))
    assert report.verification_status == "REJECTED"
    assert any(r.rule == "DESTINATION_MATCH" for r in report.failed_rules)


@pytest.mark.asyncio
async def test_cp005_vessel_not_in_transit_is_rejected():
    report = await verify_shipment("CP005", client=FakeEvidenceClient(bundle_cp005_vessel_not_in_transit()))
    assert report.verification_status == "REJECTED"
    assert any(r.rule == "VESSEL_STATUS" for r in report.failed_rules)


@pytest.mark.asyncio
async def test_cp006_port_event_conflict_holds_or_rejects():
    report = await verify_shipment("CP006", client=FakeEvidenceClient(bundle_cp006_port_event_conflict()))
    assert report.verification_status in ("HOLD", "REJECTED")
    assert report.decision == "DO_NOT_RELEASE"


@pytest.mark.asyncio
async def test_cp007_gps_conflict_holds_or_rejects():
    report = await verify_shipment("CP007", client=FakeEvidenceClient(bundle_cp007_gps_conflict()))
    assert report.verification_status in ("HOLD", "REJECTED")
    assert report.decision == "DO_NOT_RELEASE"


@pytest.mark.asyncio
async def test_cp008_inspection_failure_holds_or_rejects():
    report = await verify_shipment("CP008", client=FakeEvidenceClient(bundle_cp008_inspection_failure()))
    assert report.verification_status in ("HOLD", "REJECTED")
    assert report.decision == "DO_NOT_RELEASE"


@pytest.mark.asyncio
async def test_cp009_document_conflict_holds_or_rejects():
    report = await verify_shipment("CP009", client=FakeEvidenceClient(bundle_cp009_document_conflict()))
    assert report.verification_status in ("HOLD", "REJECTED")
    assert report.decision == "DO_NOT_RELEASE"


@pytest.mark.asyncio
async def test_cp010_high_value_verified():
    report = await verify_shipment("CP010", client=FakeEvidenceClient(bundle_cp010_high_value_verified()))
    assert report.verification_status == "VERIFIED"
    assert report.decision == "RELEASE"


@pytest.mark.asyncio
async def test_missing_shipment_end_to_end():
    from verification_engine.models import EvidenceBundle
    report = await verify_shipment("CP999", client=FakeEvidenceClient(EvidenceBundle(shipment=None)))
    assert report.verification_status == "REJECTED"
    assert report.decision == "DO_NOT_RELEASE"
    assert any(r.rule == "SHIPMENT_EXISTS" for r in report.failed_rules)
