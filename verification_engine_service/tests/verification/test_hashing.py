from verification_engine.hashing import evidence_hash

from .fixtures import bundle_cp001_good


def test_evidence_hash_deterministic():
    assert evidence_hash(bundle_cp001_good()) == evidence_hash(bundle_cp001_good())


def test_evidence_hash_is_sha256_hex():
    h = evidence_hash(bundle_cp001_good())
    assert len(h) == 64
    int(h, 16)  # raises if not valid hex


def test_evidence_hash_order_independent_for_events():
    b1 = bundle_cp001_good()
    b2 = bundle_cp001_good()
    b2.port_events = list(reversed(b2.port_events))
    assert evidence_hash(b1) == evidence_hash(b2)


def test_evidence_hash_order_independent_for_documents():
    b1 = bundle_cp001_good()
    b2 = bundle_cp001_good()
    b2.documents = list(reversed(b2.documents))
    assert evidence_hash(b1) == evidence_hash(b2)


def test_evidence_hash_changes_with_data():
    b1 = bundle_cp001_good()
    b2 = bundle_cp001_good()
    b2.vessel["status"] = "DOCKED"
    assert evidence_hash(b1) != evidence_hash(b2)


def test_evidence_hash_changes_when_shipment_missing():
    b1 = bundle_cp001_good()
    b2 = bundle_cp001_good()
    b2.shipment = None
    assert evidence_hash(b1) != evidence_hash(b2)
