"""
Seed script for the CargoProof SIMULATED evidence database.

Run with:

    python -m simulated_evidence.seed

This will:
  1. Create the SQLite database + tables (idempotent).
  2. Clear any existing demo data (safe - only touches these tables).
  3. Insert 10 realistic demo shipments across the required scenarios:
       CP001 - A. Verified shipment                    -> VERIFIED
       CP002 - B. Vessel mismatch                       -> REJECTED
       CP003 - C. Container not found                   -> REJECTED
       CP004 - D. Wrong destination                      -> REJECTED
       CP005 - E. Vessel not in transit                  -> REJECTED
       CP006 - F. Port event conflict                    -> REJECTED
       CP007 - G. GPS conflict                           -> REJECTED
       CP008 - H. Inspection failure                     -> REJECTED
       CP009 - I. Document / data mismatch               -> REJECTED
       CP010 - J. Fully verified high-value shipment     -> VERIFIED
  4. Print a summary table.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .database import SessionLocal, init_db
from . import models


def _dt(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi)


def _recent(hours_ago: float) -> datetime:
    return datetime.now() - timedelta(hours=hours_ago)


def clear_demo_data(db) -> None:
    """Wipe all rows from every evidence table. Safe for a demo DB only."""
    for model in (
        models.ShipmentDocument,
        models.Inspection,
        models.GpsObservation,
        models.PortEvent,
        models.Shipment,
        models.Container,
        models.Vessel,
    ):
        db.query(model).delete()
    db.commit()


def seed(db) -> None:
    # -----------------------------------------------------------------
    # VESSELS
    # -----------------------------------------------------------------
    vessels = [
        models.Vessel(
            imo_number="IMO1234567", vessel_name="Vessel XYZ", mmsi="MMSI987654321",
            flag="India", vessel_type="Container Ship",
            current_latitude=7.50, current_longitude=92.00,
            current_port="Chennai Port", destination_port="Singapore",
            status="IN_TRANSIT", last_updated=_recent(1),
        ),
        models.Vessel(
            imo_number="IMO2233445", vessel_name="Vessel ABC", mmsi="MMSI112233445",
            flag="Panama", vessel_type="Container Ship",
            current_latitude=20.00, current_longitude=45.00,
            current_port="Colombo", destination_port="Rotterdam",
            status="IN_TRANSIT", last_updated=_dt(2026, 8, 18, 6, 0),
        ),
        models.Vessel(
            imo_number="IMO3344556", vessel_name="Delta Star", mmsi="MMSI334455667",
            flag="Singapore", vessel_type="Container Ship",
            current_latitude=13.0827, current_longitude=80.2707,
            current_port="Chennai Port", destination_port="Singapore",
            status="DOCKED", last_updated=_dt(2026, 8, 18, 6, 0),
        ),
        models.Vessel(
            imo_number="IMO4455667", vessel_name="Pacific Trader", mmsi="MMSI445566778",
            flag="Marshall Islands", vessel_type="Container Ship",
            current_latitude=19.00, current_longitude=68.00,
            current_port="Chennai Port", destination_port="Dubai",
            status="IN_TRANSIT", last_updated=_dt(2026, 8, 18, 6, 0),
        ),
        models.Vessel(
            imo_number="IMO6677889", vessel_name="Nordic Voyager", mmsi="MMSI667788990",
            flag="Norway", vessel_type="Container Ship",
            current_latitude=7.50, current_longitude=92.00,
            current_port="Chennai Port", destination_port="Singapore",
            status="IN_TRANSIT", last_updated=_dt(2026, 8, 18, 6, 0),
        ),
        models.Vessel(
            imo_number="IMO5566778", vessel_name="Global Carrier", mmsi="MMSI556677889",
            flag="Liberia", vessel_type="Container Ship",
            current_latitude=41.59, current_longitude=62.81,
            current_port="Shanghai", destination_port="Rotterdam",
            status="IN_TRANSIT", last_updated=_dt(2026, 8, 18, 6, 0),
        ),
    ]
    db.add_all(vessels)
    db.flush()

    # -----------------------------------------------------------------
    # CONTAINERS
    # -----------------------------------------------------------------
    containers = [
        models.Container(
            container_number="ABC123", vessel_imo="IMO1234567",
            cargo_description="Consumer Electronics", origin_port="Chennai Port",
            destination_port="Singapore", status="IN_TRANSIT", seal_number="SEAL12345",
            last_scan_port="Chennai Port", last_scan_time=_dt(2026, 8, 10, 14, 0),
            created_at=_dt(2026, 8, 9, 9, 0),
        ),
        models.Container(
            # Registered under Vessel ABC, NOT Vessel XYZ -> mismatch vs CP002 claim
            container_number="DEF456", vessel_imo="IMO2233445",
            cargo_description="Textiles", origin_port="Chennai Port",
            destination_port="Singapore", status="IN_TRANSIT", seal_number="SEAL22334",
            last_scan_port="Chennai Port", last_scan_time=_dt(2026, 8, 10, 15, 0),
            created_at=_dt(2026, 8, 9, 9, 0),
        ),
        # NOTE: no container created for "XYZ999" - CP003 references it -> CONTAINER_NOT_FOUND
        models.Container(
            container_number="GHI789", vessel_imo="IMO4455667",
            cargo_description="Auto Parts", origin_port="Chennai Port",
            destination_port="Dubai",  # actual destination differs from CP004's declared Singapore
            status="IN_TRANSIT", seal_number="SEAL44556",
            last_scan_port="Chennai Port", last_scan_time=_dt(2026, 8, 11, 10, 0),
            created_at=_dt(2026, 8, 9, 9, 0),
        ),
        models.Container(
            container_number="JKL012", vessel_imo="IMO3344556",
            cargo_description="Pharmaceuticals", origin_port="Chennai Port",
            destination_port="Singapore", status="DOCKED", seal_number="SEAL33445",
            last_scan_port="Chennai Port", last_scan_time=_dt(2026, 8, 12, 8, 0),
            created_at=_dt(2026, 8, 9, 9, 0),
        ),
        models.Container(
            container_number="MNO345", vessel_imo="IMO1234567",
            cargo_description="Industrial Machinery", origin_port="Chennai Port",
            destination_port="Singapore", status="IN_TRANSIT", seal_number="SEAL55667",
            last_scan_port="Chennai Port", last_scan_time=_dt(2026, 8, 12, 11, 0),
            created_at=_dt(2026, 8, 9, 9, 0),
        ),
        models.Container(
            container_number="STU901", vessel_imo="IMO6677889",
            cargo_description="Furniture", origin_port="Chennai Port",
            destination_port="Singapore", status="IN_TRANSIT", seal_number="SEAL66778",
            last_scan_port="Chennai Port", last_scan_time=_dt(2026, 8, 12, 12, 0),
            created_at=_dt(2026, 8, 9, 9, 0),
        ),
        models.Container(
            container_number="VWX234", vessel_imo="IMO1234567",
            cargo_description="Medical Devices", origin_port="Chennai Port",
            destination_port="Singapore", status="IN_TRANSIT", seal_number="SEAL77889",
            last_scan_port="Chennai Port", last_scan_time=_dt(2026, 8, 13, 9, 0),
            created_at=_dt(2026, 8, 9, 9, 0),
        ),
        models.Container(
            container_number="YZA567", vessel_imo="IMO1234567",
            cargo_description="Coffee Beans", origin_port="Chennai Port",
            destination_port="Singapore", status="IN_TRANSIT", seal_number="SEAL88990",
            last_scan_port="Chennai Port", last_scan_time=_dt(2026, 8, 13, 10, 0),
            created_at=_dt(2026, 8, 9, 9, 0),
        ),
        models.Container(
            container_number="BCD890", vessel_imo="IMO5566778",
            cargo_description="Semiconductor Equipment", origin_port="Shanghai",
            destination_port="Rotterdam", status="IN_TRANSIT", seal_number="SEAL99001",
            last_scan_port="Shanghai", last_scan_time=_dt(2026, 8, 14, 7, 0),
            created_at=_dt(2026, 8, 9, 9, 0),
        ),
    ]
    db.add_all(containers)
    db.flush()

    # -----------------------------------------------------------------
    # PORT EVENTS
    # -----------------------------------------------------------------
    port_events = [
        # CP001 - clean departure record
        models.PortEvent(container_number="ABC123", vessel_imo="IMO1234567",
                          port_name="Chennai Port", event_type="GATE_IN",
                  event_time=_recent(4), terminal="CCT-1",
                          status="CONFIRMED", source="TOS-SIM"),
        models.PortEvent(container_number="ABC123", vessel_imo="IMO1234567",
                          port_name="Chennai Port", event_type="LOADED",
                  event_time=_recent(3), terminal="CCT-1",
                          status="CONFIRMED", source="TOS-SIM"),
        models.PortEvent(container_number="ABC123", vessel_imo="IMO1234567",
                          port_name="Chennai Port", event_type="DEPARTURE",
                  event_time=_recent(2), terminal="CCT-1",
                          status="CONFIRMED", source="TOS-SIM"),

        # CP002 - departure recorded under the container's actual vessel
        models.PortEvent(container_number="DEF456", vessel_imo="IMO2233445",
                          port_name="Chennai Port", event_type="DEPARTURE",
                          event_time=_dt(2026, 8, 10, 16, 0), terminal="CCT-2",
                          status="CONFIRMED", source="TOS-SIM"),

        # CP004 - departed normally, just headed to the wrong (actual) destination
        models.PortEvent(container_number="GHI789", vessel_imo="IMO4455667",
                          port_name="Chennai Port", event_type="DEPARTURE",
                          event_time=_dt(2026, 8, 11, 12, 0), terminal="CCT-1",
                          status="CONFIRMED", source="TOS-SIM"),

        # CP005 - vessel is still DOCKED, so intentionally NO departure event

        # CP006 - GATE_IN / LOADED only, DEPARTURE deliberately missing -> PORT_EVENT_CONFLICT
        models.PortEvent(container_number="MNO345", vessel_imo="IMO1234567",
                          port_name="Chennai Port", event_type="GATE_IN",
                          event_time=_dt(2026, 8, 12, 8, 0), terminal="CCT-1",
                          status="CONFIRMED", source="TOS-SIM"),
        models.PortEvent(container_number="MNO345", vessel_imo="IMO1234567",
                          port_name="Chennai Port", event_type="LOADED",
                          event_time=_dt(2026, 8, 12, 9, 0), terminal="CCT-1",
                          status="CONFIRMED", source="TOS-SIM"),

        # CP007 - normal departure, GPS is the problem here
        models.PortEvent(container_number="STU901", vessel_imo="IMO6677889",
                          port_name="Chennai Port", event_type="DEPARTURE",
                          event_time=_dt(2026, 8, 12, 15, 0), terminal="CCT-1",
                          status="CONFIRMED", source="TOS-SIM"),

        # CP008 - normal departure, inspection is the problem here
        models.PortEvent(container_number="VWX234", vessel_imo="IMO1234567",
                          port_name="Chennai Port", event_type="DEPARTURE",
                          event_time=_dt(2026, 8, 13, 11, 0), terminal="CCT-1",
                          status="CONFIRMED", source="TOS-SIM"),

        # CP009 - normal departure, documents are the problem here
        models.PortEvent(container_number="YZA567", vessel_imo="IMO1234567",
                          port_name="Chennai Port", event_type="DEPARTURE",
                          event_time=_dt(2026, 8, 13, 13, 0), terminal="CCT-1",
                          status="CONFIRMED", source="TOS-SIM"),

        # CP010 - clean high-value shipment
        models.PortEvent(container_number="BCD890", vessel_imo="IMO5566778",
                          port_name="Shanghai", event_type="DEPARTURE",
                          event_time=_dt(2026, 8, 14, 9, 0), terminal="Yangshan-3",
                          status="CONFIRMED", source="TOS-SIM"),
    ]
    db.add_all(port_events)

    # -----------------------------------------------------------------
    # GPS OBSERVATIONS (latest ping per vessel)
    # -----------------------------------------------------------------
    gps_observations = [
        models.GpsObservation(vessel_imo="IMO1234567", latitude=7.50, longitude=92.00,
                       speed=18.2, heading=112.0, timestamp=_recent(1),
                               source="AIS-SIM"),
        models.GpsObservation(vessel_imo="IMO2233445", latitude=20.00, longitude=45.00,
                               speed=16.5, heading=290.0, timestamp=_dt(2026, 8, 18, 6, 0),
                               source="AIS-SIM"),
        models.GpsObservation(vessel_imo="IMO3344556", latitude=13.0827, longitude=80.2707,
                               speed=0.0, heading=0.0, timestamp=_dt(2026, 8, 18, 6, 0),
                               source="AIS-SIM"),
        models.GpsObservation(vessel_imo="IMO4455667", latitude=19.00, longitude=68.00,
                               speed=17.8, heading=280.0, timestamp=_dt(2026, 8, 18, 6, 0),
                               source="AIS-SIM"),
        # Nordic Voyager's independent AIS feed places it near Dubai -
        # nowhere near a Chennai -> Singapore route. This directly
        # contradicts the vessel's own self-reported position/status.
        models.GpsObservation(vessel_imo="IMO6677889", latitude=25.2532, longitude=55.3657,
                               speed=15.0, heading=310.0, timestamp=_dt(2026, 8, 18, 6, 0),
                               source="AIS-SIM"),
        models.GpsObservation(vessel_imo="IMO5566778", latitude=41.59, longitude=62.81,
                               speed=19.4, heading=280.0, timestamp=_dt(2026, 8, 18, 6, 0),
                               source="AIS-SIM"),
    ]
    db.add_all(gps_observations)

    # -----------------------------------------------------------------
    # INSPECTIONS
    # -----------------------------------------------------------------
    inspections = [
        models.Inspection(inspection_id="INSP-CP001-01", container_number="ABC123",
                           inspector_name="SGS Cargo Inspections", inspection_type="Pre-shipment",
                   inspection_date=_recent(5), location="Chennai Port",
                           result="PASS", notes="Seal intact, cargo matches manifest.",
                           document_hash="a1b2c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff0"),
        models.Inspection(inspection_id="INSP-CP002-01", container_number="DEF456",
                           inspector_name="SGS Cargo Inspections", inspection_type="Pre-shipment",
                           inspection_date=_dt(2026, 8, 9, 17, 0), location="Chennai Port",
                           result="PASS", notes="Seal intact.",
                           document_hash="b2c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff011"),
        models.Inspection(inspection_id="INSP-CP004-01", container_number="GHI789",
                           inspector_name="Bureau Veritas", inspection_type="Pre-shipment",
                           inspection_date=_dt(2026, 8, 10, 12, 0), location="Chennai Port",
                           result="PASS", notes="Auto parts count verified.",
                           document_hash="c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff01122"),
        models.Inspection(inspection_id="INSP-CP005-01", container_number="JKL012",
                           inspector_name="Bureau Veritas", inspection_type="Pre-shipment",
                           inspection_date=_dt(2026, 8, 11, 9, 0), location="Chennai Port",
                           result="PASS", notes="Cold-chain pharma checks nominal.",
                           document_hash="d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff0112233"),
        models.Inspection(inspection_id="INSP-CP006-01", container_number="MNO345",
                           inspector_name="SGS Cargo Inspections", inspection_type="Pre-shipment",
                           inspection_date=_dt(2026, 8, 11, 15, 0), location="Chennai Port",
                           result="PASS", notes="Machinery secured, no damage.",
                           document_hash="e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff011223344"),
        models.Inspection(inspection_id="INSP-CP007-01", container_number="STU901",
                           inspector_name="Bureau Veritas", inspection_type="Pre-shipment",
                           inspection_date=_dt(2026, 8, 12, 10, 0), location="Chennai Port",
                           result="PASS", notes="Furniture packaging verified.",
                           document_hash="f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff01122334455"),
        # Inspection FAILED -> drives CP008 rejection
        models.Inspection(inspection_id="INSP-CP008-01", container_number="VWX234",
                           inspector_name="SGS Cargo Inspections", inspection_type="Pre-shipment",
                           inspection_date=_dt(2026, 8, 13, 8, 0), location="Chennai Port",
                           result="FAILED",
                           notes="Medical device packaging compromised; missing sterility certs.",
                           document_hash="0718293a4b5c6d7e8f90112233445566778899aabbccddeeff0112233445566"),
        models.Inspection(inspection_id="INSP-CP009-01", container_number="YZA567",
                           inspector_name="Bureau Veritas", inspection_type="Pre-shipment",
                           inspection_date=_dt(2026, 8, 13, 9, 0), location="Chennai Port",
                           result="PASS", notes="Coffee bean quality/quantity confirmed.",
                           document_hash="18293a4b5c6d7e8f90112233445566778899aabbccddeeff011223344556677"),
        models.Inspection(inspection_id="INSP-CP010-01", container_number="BCD890",
                           inspector_name="Bureau Veritas", inspection_type="Pre-shipment",
                           inspection_date=_dt(2026, 8, 13, 18, 0), location="Shanghai",
                           result="PASS", notes="High-value equipment crated and sealed per spec.",
                           document_hash="293a4b5c6d7e8f90112233445566778899aabbccddeeff01122334455667788"),
    ]
    db.add_all(inspections)

    # -----------------------------------------------------------------
    # SHIPMENTS (the CLAIMS being verified)
    # -----------------------------------------------------------------
    shipments = [
        models.Shipment(
            shipment_id="CP001", seller="Chennai Exports Pvt Ltd", buyer="Singapore Trading Co",
            invoice_number="INV-CP001", container_number="ABC123", vessel_imo="IMO1234567",
            origin_port="Chennai Port", destination_port="Singapore",
            cargo_description="Consumer Electronics", declared_value=45000.00, currency="USD",
            expected_departure=_dt(2026, 8, 10), expected_arrival=_dt(2026, 8, 22),
            claimed_status="IN_TRANSIT", created_at=_dt(2026, 8, 9),
        ),
        models.Shipment(
            # Claims Vessel XYZ (IMO1234567), but container DEF456 is really on Vessel ABC
            shipment_id="CP002", seller="Coastal Textiles Ltd", buyer="Global Textile Imports",
            invoice_number="INV-CP002", container_number="DEF456", vessel_imo="IMO1234567",
            origin_port="Chennai Port", destination_port="Singapore",
            cargo_description="Textiles", declared_value=18000.00, currency="USD",
            expected_departure=_dt(2026, 8, 10), expected_arrival=_dt(2026, 8, 22),
            claimed_status="IN_TRANSIT", created_at=_dt(2026, 8, 9),
        ),
        models.Shipment(
            # References a container that does not exist in the registry
            shipment_id="CP003", seller="Deccan Auto Traders", buyer="Gulf Auto Distributors",
            invoice_number="INV-CP003", container_number="XYZ999", vessel_imo="IMO4455667",
            origin_port="Chennai Port", destination_port="Dubai",
            cargo_description="Auto Parts", declared_value=22000.00, currency="USD",
            expected_departure=_dt(2026, 8, 11), expected_arrival=_dt(2026, 8, 20),
            claimed_status="IN_TRANSIT", created_at=_dt(2026, 8, 9),
        ),
        models.Shipment(
            # Declares Singapore, but the vessel/container are actually bound for Dubai
            shipment_id="CP004", seller="Deccan Auto Traders", buyer="Singapore Auto Parts Co",
            invoice_number="INV-CP004", container_number="GHI789", vessel_imo="IMO4455667",
            origin_port="Chennai Port", destination_port="Singapore",
            cargo_description="Auto Parts", declared_value=27000.00, currency="USD",
            expected_departure=_dt(2026, 8, 11), expected_arrival=_dt(2026, 8, 23),
            claimed_status="IN_TRANSIT", created_at=_dt(2026, 8, 9),
        ),
        models.Shipment(
            # Claims IN_TRANSIT, but the vessel is actually DOCKED
            shipment_id="CP005", seller="Madras Pharma Exports", buyer="SEA Pharma Distributors",
            invoice_number="INV-CP005", container_number="JKL012", vessel_imo="IMO3344556",
            origin_port="Chennai Port", destination_port="Singapore",
            cargo_description="Pharmaceuticals", declared_value=61000.00, currency="USD",
            expected_departure=_dt(2026, 8, 12), expected_arrival=_dt(2026, 8, 24),
            claimed_status="IN_TRANSIT", created_at=_dt(2026, 8, 9),
        ),
        models.Shipment(
            # Claims the vessel departed Chennai, but no DEPARTURE event is on record
            shipment_id="CP006", seller="Chennai Heavy Industries", buyer="Singapore Engineering Co",
            invoice_number="INV-CP006", container_number="MNO345", vessel_imo="IMO1234567",
            origin_port="Chennai Port", destination_port="Singapore",
            cargo_description="Industrial Machinery", declared_value=95000.00, currency="USD",
            expected_departure=_dt(2026, 8, 12), expected_arrival=_dt(2026, 8, 24),
            claimed_status="IN_TRANSIT", created_at=_dt(2026, 8, 9),
        ),
        models.Shipment(
            # Route claims Chennai -> Singapore, but AIS puts the vessel near Dubai
            shipment_id="CP007", seller="Chennai Home Furnishings", buyer="Singapore Living Co",
            invoice_number="INV-CP007", container_number="STU901", vessel_imo="IMO6677889",
            origin_port="Chennai Port", destination_port="Singapore",
            cargo_description="Furniture", declared_value=15000.00, currency="USD",
            expected_departure=_dt(2026, 8, 12), expected_arrival=_dt(2026, 8, 24),
            claimed_status="IN_TRANSIT", created_at=_dt(2026, 8, 9),
        ),
        models.Shipment(
            # Everything lines up except a FAILED cargo inspection
            shipment_id="CP008", seller="Chennai MedTech Exports", buyer="Singapore Health Supplies",
            invoice_number="INV-CP008", container_number="VWX234", vessel_imo="IMO1234567",
            origin_port="Chennai Port", destination_port="Singapore",
            cargo_description="Medical Devices", declared_value=38000.00, currency="USD",
            expected_departure=_dt(2026, 8, 13), expected_arrival=_dt(2026, 8, 25),
            claimed_status="IN_TRANSIT", created_at=_dt(2026, 8, 9),
        ),
        models.Shipment(
            # Everything lines up except the trade document disagrees with the manifest
            shipment_id="CP009", seller="Nilgiris Coffee Exporters", buyer="Singapore Roasters Co",
            invoice_number="INV-CP009", container_number="YZA567", vessel_imo="IMO1234567",
            origin_port="Chennai Port", destination_port="Singapore",
            cargo_description="Coffee Beans", declared_value=9000.00, currency="USD",
            expected_departure=_dt(2026, 8, 13), expected_arrival=_dt(2026, 8, 25),
            claimed_status="IN_TRANSIT", created_at=_dt(2026, 8, 9),
        ),
        models.Shipment(
            # Fully verified high-value shipment, all sources agree
            shipment_id="CP010", seller="Shanghai Semicon Supply Co", buyer="Rotterdam Chip Fabricators BV",
            invoice_number="INV-CP010", container_number="BCD890", vessel_imo="IMO5566778",
            origin_port="Shanghai", destination_port="Rotterdam",
            cargo_description="Semiconductor Equipment", declared_value=1250000.00, currency="USD",
            expected_departure=_dt(2026, 8, 14), expected_arrival=_dt(2026, 8, 29),
            claimed_status="IN_TRANSIT", created_at=_dt(2026, 8, 9),
        ),
    ]
    db.add_all(shipments)
    db.flush()

    # -----------------------------------------------------------------
    # SHIPMENT DOCUMENTS (Bill of Lading, mirrors the seller's claim)
    # -----------------------------------------------------------------
    documents = [
        models.ShipmentDocument(
            shipment_id="CP001", document_type="BILL_OF_LADING", document_number="BOL-CP001",
            issued_by="Chennai Port Authority", issue_date=_recent(6),
            document_hash="dcce88445a0b9657cdf5698f381fa7bf40cd71ef93f3c7eb9fb73f051282b6c8",
            declared_vessel="Vessel XYZ", declared_container="ABC123",
            declared_origin="Chennai Port", declared_destination="Singapore",
            declared_cargo="Consumer Electronics", declared_value=45000.00,
        ),
        models.ShipmentDocument(
            shipment_id="CP002", document_type="BILL_OF_LADING", document_number="BOL-CP002",
            issued_by="Chennai Port Authority", issue_date=_dt(2026, 8, 9),
            document_hash="11223344556677889900aabbccddeeff112233445566778899aabbccddeeff",
            declared_vessel="Vessel XYZ", declared_container="DEF456",
            declared_origin="Chennai Port", declared_destination="Singapore",
            declared_cargo="Textiles", declared_value=18000.00,
        ),
        models.ShipmentDocument(
            shipment_id="CP003", document_type="BILL_OF_LADING", document_number="BOL-CP003",
            issued_by="Chennai Port Authority", issue_date=_dt(2026, 8, 9),
            document_hash="22334455667788990011aabbccddeeff223344556677889900aabbccddeeff",
            declared_vessel="Pacific Trader", declared_container="XYZ999",
            declared_origin="Chennai Port", declared_destination="Dubai",
            declared_cargo="Auto Parts", declared_value=22000.00,
        ),
        models.ShipmentDocument(
            shipment_id="CP004", document_type="BILL_OF_LADING", document_number="BOL-CP004",
            issued_by="Chennai Port Authority", issue_date=_dt(2026, 8, 9),
            document_hash="33445566778899001122aabbccddeeff334455667788990011aabbccddeeff",
            declared_vessel="Pacific Trader", declared_container="GHI789",
            declared_origin="Chennai Port", declared_destination="Singapore",
            declared_cargo="Auto Parts", declared_value=27000.00,
        ),
        models.ShipmentDocument(
            shipment_id="CP005", document_type="BILL_OF_LADING", document_number="BOL-CP005",
            issued_by="Chennai Port Authority", issue_date=_dt(2026, 8, 9),
            document_hash="44556677889900112233aabbccddeeff445566778899001122aabbccddeeff",
            declared_vessel="Delta Star", declared_container="JKL012",
            declared_origin="Chennai Port", declared_destination="Singapore",
            declared_cargo="Pharmaceuticals", declared_value=61000.00,
        ),
        models.ShipmentDocument(
            shipment_id="CP006", document_type="BILL_OF_LADING", document_number="BOL-CP006",
            issued_by="Chennai Port Authority", issue_date=_dt(2026, 8, 9),
            document_hash="55667788990011223344aabbccddeeff556677889900112233aabbccddeeff",
            declared_vessel="Vessel XYZ", declared_container="MNO345",
            declared_origin="Chennai Port", declared_destination="Singapore",
            declared_cargo="Industrial Machinery", declared_value=95000.00,
        ),
        models.ShipmentDocument(
            shipment_id="CP007", document_type="BILL_OF_LADING", document_number="BOL-CP007",
            issued_by="Chennai Port Authority", issue_date=_dt(2026, 8, 9),
            document_hash="66778899001122334455aabbccddeeff667788990011223344aabbccddeeff",
            declared_vessel="Nordic Voyager", declared_container="STU901",
            declared_origin="Chennai Port", declared_destination="Singapore",
            declared_cargo="Furniture", declared_value=15000.00,
        ),
        models.ShipmentDocument(
            shipment_id="CP008", document_type="BILL_OF_LADING", document_number="BOL-CP008",
            issued_by="Chennai Port Authority", issue_date=_dt(2026, 8, 9),
            document_hash="778899001122334455aabbccddeeff778899001122334455aabbccddeeff11",
            declared_vessel="Vessel XYZ", declared_container="VWX234",
            declared_origin="Chennai Port", declared_destination="Singapore",
            declared_cargo="Medical Devices", declared_value=38000.00,
        ),
        models.ShipmentDocument(
            # Deliberately disagrees with the shipment record on cargo + container
            shipment_id="CP009", document_type="BILL_OF_LADING", document_number="BOL-CP009",
            issued_by="Chennai Port Authority", issue_date=_dt(2026, 8, 9),
            document_hash="8899001122334455aabbccddeeff8899001122334455aabbccddeeff112233",
            declared_vessel="Vessel XYZ", declared_container="YZA999",
            declared_origin="Chennai Port", declared_destination="Singapore",
            declared_cargo="Instant Coffee Powder", declared_value=9000.00,
        ),
        models.ShipmentDocument(
            shipment_id="CP010", document_type="BILL_OF_LADING", document_number="BOL-CP010",
            issued_by="Shanghai Port Authority", issue_date=_dt(2026, 8, 13),
            document_hash="99001122334455aabbccddeeff99001122334455aabbccddeeff11223344",
            declared_vessel="Global Carrier", declared_container="BCD890",
            declared_origin="Shanghai", declared_destination="Rotterdam",
            declared_cargo="Semiconductor Equipment", declared_value=1250000.00,
        ),
    ]
    db.add_all(documents)
    db.commit()


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        clear_demo_data(db)
        seed(db)

        shipment_count = db.query(models.Shipment).count()
        vessel_count = db.query(models.Vessel).count()
        container_count = db.query(models.Container).count()
        event_count = db.query(models.PortEvent).count()
        gps_count = db.query(models.GpsObservation).count()
        inspection_count = db.query(models.Inspection).count()
        document_count = db.query(models.ShipmentDocument).count()

        print("=" * 60)
        print("CargoProof SIMULATED evidence database seeded successfully")
        print("=" * 60)
        print(f"  Vessels:             {vessel_count}")
        print(f"  Containers:          {container_count}")
        print(f"  Port events:         {event_count}")
        print(f"  GPS observations:    {gps_count}")
        print(f"  Inspections:         {inspection_count}")
        print(f"  Shipment documents:  {document_count}")
        print(f"  Shipments:           {shipment_count}")
        print("-" * 60)
        print("Demo shipment IDs:")
        print("  CP001  VERIFIED  (clean shipment)")
        print("  CP002  REJECTED  (vessel mismatch)")
        print("  CP003  REJECTED  (container not found)")
        print("  CP004  REJECTED  (destination mismatch)")
        print("  CP005  REJECTED  (vessel not in transit)")
        print("  CP006  REJECTED  (port event / departure conflict)")
        print("  CP007  REJECTED  (GPS route conflict)")
        print("  CP008  REJECTED  (inspection failed)")
        print("  CP009  REJECTED  (document data mismatch)")
        print("  CP010  VERIFIED  (high-value, fully verified)")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    run()
