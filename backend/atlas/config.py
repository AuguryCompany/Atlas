"""Runtime configuration, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _api_keys(raw: str | None) -> dict[str, str]:
    """Parse ``key1:role,key2:role`` into a mapping of API key -> role."""
    keys: dict[str, str] = {}
    if not raw:
        return keys
    for pair in raw.split(","):
        if ":" not in pair:
            continue
        key, role = pair.split(":", 1)
        if key.strip() and role.strip():
            keys[key.strip()] = role.strip()
    return keys


@dataclass(frozen=True)
class Settings:
    db_path: Path = field(
        default_factory=lambda: Path(os.getenv("ATLAS_DB_PATH", "atlas.db"))
    )
    # When auth is disabled every request runs as an anonymous analyst (dev mode).
    auth_enabled: bool = field(default_factory=lambda: _bool("ATLAS_AUTH_ENABLED", False))
    api_keys: dict[str, str] = field(
        default_factory=lambda: _api_keys(os.getenv("ATLAS_API_KEYS"))
    )
    # Offline mode: never call external connectors (live layers come back empty).
    offline: bool = field(default_factory=lambda: _bool("ATLAS_OFFLINE", False))
    firms_map_key: str | None = field(default_factory=lambda: os.getenv("FIRMS_MAP_KEY"))
    osrm_url: str = field(
        default_factory=lambda: os.getenv("OSRM_URL", "https://router.project-osrm.org")
    )
    overpass_url: str = field(
        default_factory=lambda: os.getenv(
            "OVERPASS_URL", "https://overpass-api.de/api/interpreter"
        )
    )
    usgs_url: str = field(
        default_factory=lambda: os.getenv(
            "USGS_URL", "https://earthquake.usgs.gov/fdsnws/event/1/query"
        )
    )
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv(
            "ATLAS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
    )
    http_timeout: float = field(
        default_factory=lambda: float(os.getenv("ATLAS_HTTP_TIMEOUT", "8"))
    )


def get_settings() -> Settings:
    return Settings()
