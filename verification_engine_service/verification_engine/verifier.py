from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from .client import EvidenceClient, EvidenceUnavailable
from .models import EvidenceBundle
from .rules import ALL_RULES
from .hashing import evidence_hash
from .schemas import RuleResult, VerificationReport

# Points subtracted from the confidence score (starts at 100) per failed
# rule, by severity. Documented in README.md.
SEVERITY_PENALTY = {
    "CRITICAL": 40,
    "HIGH": 25,
    "MEDIUM": 10,
    "LOW": 5,
}


async def _safe_fetch(coro, warnings: List[str], source: str):
    try:
        return await coro
    except EvidenceUnavailable as e:
        warnings.append(f"{source.upper()}_UNAVAILABLE: {e.detail}")
        return None


async def collect_evidence(shipment_id: str, client: EvidenceClient) -> EvidenceBundle:
    warnings: List[str] = []
    bundle = EvidenceBundle(warnings=warnings)

    bundle.shipment = await _safe_fetch(client.get_shipment(shipment_id), warnings, "shipment")
    if bundle.shipment is None:
        # Nothing else can be meaningfully fetched without the shipment
        # record (it's what tells us the vessel IMO / container number).
        return bundle

    vessel_imo = bundle.shipment.get("vessel_imo")
    container_number = bundle.shipment.get("container_number")

    named_fetches = []
    if vessel_imo:
        named_fetches.append(("vessel", client.get_vessel(vessel_imo)))
        named_fetches.append(("gps", client.get_gps(vessel_imo)))
    if container_number:
        named_fetches.append(("container", client.get_container(container_number)))
        named_fetches.append(("port_events", client.get_container_events(container_number)))
    named_fetches.append(("inspection", client.get_inspection(shipment_id)))
    named_fetches.append(("documents", client.get_documents(shipment_id)))

    results = await asyncio.gather(
        *[_safe_fetch(coro, warnings, name) for name, coro in named_fetches]
    )

    for (name, _), result in zip(named_fetches, results):
        if name == "vessel":
            bundle.vessel = result
        elif name == "container":
            bundle.container = result
        elif name == "port_events":
            bundle.port_events = result or []
        elif name == "gps":
            bundle.gps = result or []
        elif name == "inspection":
            bundle.inspection = result
        elif name == "documents":
            bundle.documents = result or []

    return bundle


def evaluate_rules(evidence: EvidenceBundle) -> List[RuleResult]:
    return [rule(evidence) for rule in ALL_RULES]


def compute_confidence(rule_results: List[RuleResult]) -> int:
    """Start at 100, subtract per-severity penalties for each failed rule, clamp to [0, 100]."""
    score = 100
    for r in rule_results:
        if not r.passed:
            score -= SEVERITY_PENALTY.get(r.severity, 0)
    return max(0, min(100, score))


def determine_status(rule_results: List[RuleResult]) -> str:
    """
    Deterministic decision logic:
      - Any CRITICAL failure (including a missing shipment)  -> REJECTED
      - Any HIGH or MEDIUM failure, with no CRITICAL failure  -> HOLD
      - Everything passes                                     -> VERIFIED

    NOTE ON THE "MULTIPLE HIGH/MEDIUM" WORDING: the spec's suggested logic
    says "if multiple HIGH/MEDIUM conflicts exist -> HOLD". We deliberately
    hold on a SINGLE HIGH/MEDIUM conflict too, rather than requiring two.
    This is a conservative choice for money movement: escrow funds should
    not release on a single unresolved conflict just because it's the only
    one. See README.md "Decision Logic" section.
    """
    failed = [r for r in rule_results if not r.passed]

    critical_failures = [r for r in failed if r.severity == "CRITICAL"]
    if critical_failures:
        return "REJECTED"

    high_medium_failures = [r for r in failed if r.severity in ("HIGH", "MEDIUM")]
    if high_medium_failures:
        return "HOLD"

    return "VERIFIED"


def decision_for_status(status: str) -> str:
    return "RELEASE" if status == "VERIFIED" else "DO_NOT_RELEASE"


async def verify_shipment(shipment_id: str, client: Optional[EvidenceClient] = None) -> VerificationReport:
    """
    Run the full verification pipeline for one shipment ID and return a
    structured, auditable report. Pass a custom `client` (e.g. a fake one)
    for testing without a live evidence API.
    """
    client = client or EvidenceClient()

    evidence = await collect_evidence(shipment_id, client)
    rule_results = evaluate_rules(evidence)
    confidence = compute_confidence(rule_results)
    status = determine_status(rule_results)
    decision = decision_for_status(status)
    h = evidence_hash(evidence)

    failed_rules = [r for r in rule_results if not r.passed]

    sources = []
    if evidence.shipment:
        sources.append("shipment")
    if evidence.vessel:
        sources.append("vessel_tracking")
    if evidence.container:
        sources.append("container_registry")
    if evidence.port_events:
        sources.append("port_records")
    if evidence.gps:
        sources.append("gps")
    if evidence.inspection:
        sources.append("inspection")
    if evidence.documents:
        sources.append("shipment_documents")

    return VerificationReport(
        shipment_id=shipment_id,
        verification_status=status,
        confidence_score=confidence,
        decision=decision,
        evidence_hash=h,
        verified_at=datetime.now(timezone.utc).isoformat(),
        rules=rule_results,
        failed_rules=failed_rules,
        warnings=evidence.warnings,
        evidence_sources=sources,
    )
