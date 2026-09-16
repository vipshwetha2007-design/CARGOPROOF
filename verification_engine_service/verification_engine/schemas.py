from __future__ import annotations
from typing import List, Literal
from pydantic import BaseModel, Field

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
VerificationStatus = Literal["VERIFIED", "HOLD", "REJECTED"]
Decision = Literal["RELEASE", "DO_NOT_RELEASE"]


class RuleResult(BaseModel):
    rule: str
    passed: bool
    severity: Severity
    message: str


class VerifyRequest(BaseModel):
    shipment_id: str


class VerificationReport(BaseModel):
    shipment_id: str
    verification_status: VerificationStatus
    confidence_score: int
    decision: Decision
    evidence_hash: str
    verified_at: str
    rules: List[RuleResult]
    failed_rules: List[RuleResult]
    warnings: List[str] = Field(default_factory=list)
    evidence_sources: List[str] = Field(default_factory=list)
