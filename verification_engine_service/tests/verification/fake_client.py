from verification_engine.models import EvidenceBundle


class FakeEvidenceClient:
    """
    Drop-in replacement for EvidenceClient that serves data from an
    in-memory EvidenceBundle instead of making HTTP calls. Used to test
    the full verify_shipment() pipeline deterministically and offline.
    """

    def __init__(self, bundle: EvidenceBundle):
        self.bundle = bundle

    async def get_shipment(self, shipment_id: str):
        return self.bundle.shipment

    async def get_vessel(self, imo_number: str):
        return self.bundle.vessel

    async def get_container(self, container_number: str):
        return self.bundle.container

    async def get_container_events(self, container_number: str):
        return self.bundle.port_events

    async def get_gps(self, imo_number: str):
        return self.bundle.gps

    async def get_inspection(self, shipment_id: str):
        return self.bundle.inspection

    async def get_documents(self, shipment_id: str):
        return self.bundle.documents
