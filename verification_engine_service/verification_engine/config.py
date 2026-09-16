import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    evidence_api_url: str = os.getenv("EVIDENCE_API_URL", "http://127.0.0.1:8000")
    max_evidence_age_hours: float = float(os.getenv("MAX_EVIDENCE_AGE_HOURS", "24"))
    gps_max_distance_km: float = float(os.getenv("GPS_MAX_DISTANCE_KM", "500"))
    request_timeout_seconds: float = float(os.getenv("EVIDENCE_API_TIMEOUT_SECONDS", "10"))


settings = Settings()
