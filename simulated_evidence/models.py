"""
SQLAlchemy ORM models for the CargoProof SIMULATED evidence sources.

Each table represents a distinct, independent "data provider" the way a real
trade-finance verification system would query separate systems (AIS vessel
tracking, terminal operating systems, customs, inspection agencies, etc).
This separation matters for the verification engine, which cross-checks
evidence ACROSS sources rather than trusting a single shipment record.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Vessel(Base):
    """Simulated AIS / vessel registry record."""
    __tablename__ = "vessels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imo_number: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    vessel_name: Mapped[str] = mapped_column(String, nullable=False)
    mmsi: Mapped[str] = mapped_column(String, nullable=False)
    flag: Mapped[str] = mapped_column(String, nullable=False)
    vessel_type: Mapped[str] = mapped_column(String, nullable=False)
    current_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    current_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    current_port: Mapped[str] = mapped_column(String, nullable=False)
    destination_port: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # IN_TRANSIT, DOCKED, ANCHORED
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Container(Base):
    """Simulated container registry record."""
    __tablename__ = "containers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    container_number: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    vessel_imo: Mapped[str] = mapped_column(String, ForeignKey("vessels.imo_number"), nullable=False)
    cargo_description: Mapped[str] = mapped_column(String, nullable=False)
    origin_port: Mapped[str] = mapped_column(String, nullable=False)
    destination_port: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # IN_TRANSIT, DISCHARGED, GATE_OUT...
    seal_number: Mapped[str] = mapped_column(String, nullable=False)
    last_scan_port: Mapped[str] = mapped_column(String, nullable=False)
    last_scan_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PortEvent(Base):
    """Simulated terminal operating system (TOS) event feed."""
    __tablename__ = "port_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    container_number: Mapped[str] = mapped_column(String, index=True, nullable=False)
    vessel_imo: Mapped[str] = mapped_column(String, index=True, nullable=False)
    port_name: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # ARRIVAL / DEPARTURE / LOADED / DISCHARGED / CUSTOMS_CLEARANCE / GATE_IN / GATE_OUT
    event_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    terminal: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # CONFIRMED / PENDING
    source: Mapped[str] = mapped_column(String, nullable=False)


class Shipment(Base):
    """The shipment as CLAIMED by the seller (this is what gets verified)."""
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    seller: Mapped[str] = mapped_column(String, nullable=False)
    buyer: Mapped[str] = mapped_column(String, nullable=False)
    invoice_number: Mapped[str] = mapped_column(String, nullable=False)
    container_number: Mapped[str] = mapped_column(String, nullable=False)
    vessel_imo: Mapped[str] = mapped_column(String, nullable=False)
    origin_port: Mapped[str] = mapped_column(String, nullable=False)
    destination_port: Mapped[str] = mapped_column(String, nullable=False)
    cargo_description: Mapped[str] = mapped_column(String, nullable=False)
    declared_value: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    expected_departure: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expected_arrival: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    claimed_status: Mapped[str] = mapped_column(String, nullable=False)  # e.g. IN_TRANSIT
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Inspection(Base):
    """Simulated 3rd-party cargo inspection agency record."""
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inspection_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    container_number: Mapped[str] = mapped_column(String, index=True, nullable=False)
    inspector_name: Mapped[str] = mapped_column(String, nullable=False)
    inspection_type: Mapped[str] = mapped_column(String, nullable=False)
    inspection_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[str] = mapped_column(String, nullable=False)  # PASS / FAILED
    notes: Mapped[str] = mapped_column(String, nullable=True)
    document_hash: Mapped[str] = mapped_column(String, nullable=False)


class GpsObservation(Base):
    """Simulated raw AIS GPS ping feed (independent of the vessel 'summary' record)."""
    __tablename__ = "gps_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vessel_imo: Mapped[str] = mapped_column(String, index=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed: Mapped[float] = mapped_column(Float, nullable=False)
    heading: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)


class ShipmentDocument(Base):
    """Simulated trade document (Bill of Lading / Commercial Invoice) as DECLARED by seller."""
    __tablename__ = "shipment_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    document_type: Mapped[str] = mapped_column(String, nullable=False)  # BILL_OF_LADING / INVOICE
    document_number: Mapped[str] = mapped_column(String, nullable=False)
    issued_by: Mapped[str] = mapped_column(String, nullable=False)
    issue_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    document_hash: Mapped[str] = mapped_column(String, nullable=False)
    declared_vessel: Mapped[str] = mapped_column(String, nullable=False)
    declared_container: Mapped[str] = mapped_column(String, nullable=False)
    declared_origin: Mapped[str] = mapped_column(String, nullable=False)
    declared_destination: Mapped[str] = mapped_column(String, nullable=False)
    declared_cargo: Mapped[str] = mapped_column(String, nullable=False)
    declared_value: Mapped[float] = mapped_column(Float, nullable=False)
