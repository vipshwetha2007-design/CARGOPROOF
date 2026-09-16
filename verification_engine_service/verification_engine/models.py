from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvidenceBundle:
    """
    Raw evidence collected from the simulated evidence API, before any
    verification rules are applied. Fields are None / empty when that
    evidence source was unavailable or returned nothing.
    """
    shipment: Optional[Dict[str, Any]] = None
    vessel: Optional[Dict[str, Any]] = None
    container: Optional[Dict[str, Any]] = None
    port_events: List[Dict[str, Any]] = field(default_factory=list)
    gps: List[Dict[str, Any]] = field(default_factory=list)
    inspection: Optional[Dict[str, Any]] = None
    documents: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
