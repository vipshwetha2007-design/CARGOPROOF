"""
CargoProof Deterministic Evidence Verification Engine.

This package consumes evidence from the simulated evidence API and produces
an auditable, rule-based verification report. It never calls an LLM and
never touches the Algorand blockchain directly — see README.md for the
full architecture and rationale.
"""

from .verifier import verify_shipment
from .schemas import VerificationReport, RuleResult

__all__ = ["verify_shipment", "VerificationReport", "RuleResult"]
