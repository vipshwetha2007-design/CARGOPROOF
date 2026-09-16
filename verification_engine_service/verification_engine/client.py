from __future__ import annotations
from typing import Any, Optional

import httpx

from .config import settings


class EvidenceUnavailable(Exception):
    """
    Raised when a single evidence source could not be retrieved. This is
    caught by the verifier and converted into a structured warning rather
    than crashing the whole verification run — a missing GPS feed
    shouldn't take down the entire pipeline.
    """

    def __init__(self, source: str, detail: str):
        self.source = source
        self.detail = detail
        super().__init__(f"{source}: {detail}")


class EvidenceClient:
    """Talks to the simulated evidence API (default http://127.0.0.1:8000)."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self.base_url = (base_url or settings.evidence_api_url).rstrip("/")
        self.timeout = timeout or settings.request_timeout_seconds

    async def _get(self, path: str, source: str) -> Optional[Any]:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
        except httpx.ConnectError as e:
            raise EvidenceUnavailable(source, f"Connection failed: {e}") from e
        except httpx.TimeoutException as e:
            raise EvidenceUnavailable(source, f"Request timed out: {e}") from e
        except httpx.HTTPError as e:
            raise EvidenceUnavailable(source, f"Request failed: {e}") from e

        if resp.status_code == 404:
            return None
        if resp.status_code >= 500:
            raise EvidenceUnavailable(source, f"Server error {resp.status_code}")
        if resp.status_code >= 400:
            raise EvidenceUnavailable(source, f"Client error {resp.status_code}")

        try:
            return resp.json()
        except ValueError as e:
            raise EvidenceUnavailable(source, f"Invalid JSON response: {e}") from e

    async def get_shipment(self, shipment_id: str):
        return await self._get(f"/api/v1/shipments/{shipment_id}", "shipment")

    async def get_vessel(self, imo_number: str):
        vessel = await self._get(f"/api/v1/vessels/{imo_number}", "vessel")
        if isinstance(vessel, dict) and "name" not in vessel and "vessel_name" in vessel:
            vessel = {**vessel, "name": vessel["vessel_name"]}
        return vessel

    async def get_container(self, container_number: str):
        return await self._get(f"/api/v1/containers/{container_number}", "container")

    async def get_container_events(self, container_number: str):
        events = await self._get(f"/api/v1/containers/{container_number}/events", "port_events")
        if isinstance(events, dict) and isinstance(events.get("value"), list):
            events = events["value"]
        if isinstance(events, list):
            return [
                {
                    **event,
                    "port": event.get("port", event.get("port_name")),
                    "timestamp": event.get("timestamp", event.get("event_time")),
                }
                for event in events
            ]
        return events

    async def get_gps(self, imo_number: str):
        observations = await self._get(f"/api/v1/vessels/{imo_number}/gps", "gps")
        if isinstance(observations, dict) and isinstance(observations.get("value"), list):
            observations = observations["value"]
        if isinstance(observations, list):
            return [
                {
                    **observation,
                    "lat": observation.get("lat", observation.get("latitude")),
                    "lon": observation.get("lon", observation.get("longitude")),
                }
                for observation in observations
            ]
        return observations

    async def get_documents(self, shipment_id: str):
        documents = await self._get(f"/api/v1/shipments/{shipment_id}/documents", "documents")
        if isinstance(documents, dict) and isinstance(documents.get("value"), list):
            documents = documents["value"]
        if isinstance(documents, list):
            return [
                {
                    **document,
                    "vessel_name": document.get("vessel_name", document.get("declared_vessel")),
                    "container_number": document.get("container_number", document.get("declared_container")),
                    "origin_port": document.get("origin_port", document.get("declared_origin")),
                    "destination_port": document.get("destination_port", document.get("declared_destination")),
                    "declared_cargo": document.get("declared_cargo"),
                    "issued_at": document.get("issued_at", document.get("issue_date")),
                }
                for document in documents
            ]
        return documents

    async def get_inspection(self, shipment_id: str):
        inspections = await self._get(
            f"/api/v1/shipments/{shipment_id}/inspections",
            "inspection",
        )
        if isinstance(inspections, list):
            inspection = inspections[0] if inspections else None
            if inspection is not None:
                inspection = {
                    **inspection,
                    "inspector": inspection.get("inspector", inspection.get("inspector_name")),
                    "timestamp": inspection.get("timestamp", inspection.get("inspection_date")),
                }
            return inspection
        return inspections
