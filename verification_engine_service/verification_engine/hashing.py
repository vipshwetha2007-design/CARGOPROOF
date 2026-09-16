from __future__ import annotations
import hashlib
import json
from typing import Any, Dict

from .models import EvidenceBundle


def _sort_key_port_event(e: Dict[str, Any]) -> tuple:
    return (str(e.get("timestamp", "")), str(e.get("event_type", "")), str(e.get("port", "")))


def _sort_key_gps(g: Dict[str, Any]) -> tuple:
    return (str(g.get("timestamp", "")), str(g.get("lat", "")), str(g.get("lon", "")))


def _sort_key_document(d: Dict[str, Any]) -> tuple:
    return (str(d.get("document_type", "")), str(d.get("issued_at", "")))


def canonicalize_evidence(evidence: EvidenceBundle) -> Dict[str, Any]:
    """
    Build an order-independent, canonical representation of the evidence
    that was actually used during verification.

    Deliberately excludes anything the verification engine itself
    generates at run time (verified_at, confidence_score, decision, etc.)
    so that the SAME underlying evidence always produces the SAME hash,
    no matter when verification is re-run.
    """
    return {
        "shipment": evidence.shipment,
        "vessel": evidence.vessel,
        "container": evidence.container,
        "port_events": sorted(evidence.port_events, key=_sort_key_port_event),
        "gps": sorted(evidence.gps, key=_sort_key_gps),
        "inspection": evidence.inspection,
        "documents": sorted(evidence.documents, key=_sort_key_document),
    }


def canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def evidence_hash(evidence: EvidenceBundle) -> str:
    canonical = canonicalize_evidence(evidence)
    payload = canonical_json(canonical)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
