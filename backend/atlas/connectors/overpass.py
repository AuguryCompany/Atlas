"""OpenStreetMap (Overpass API) connector for critical-infrastructure discovery.

Data © OpenStreetMap contributors, available under the ODbL. Imported assets
keep their OSM id and tags so they can be traced back to the source.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable

import httpx

from ..config import Settings
from ..geo import BBox

log = logging.getLogger("atlas.connect.overpass")


@dataclass(frozen=True)
class OsmCategory:
    asset_type: str
    label: str
    selectors: tuple[str, ...]  # Overpass tag filters, e.g. '["aeroway"="aerodrome"]'
    criticality: Callable[[dict], int | None]  # None => skip element
    require_name: bool = True


def _mw(tags: dict) -> float | None:
    raw = tags.get("plant:output:electricity") or ""
    m = re.match(r"\s*([\d.,]+)\s*(GW|MW|kW)?", raw, re.I)
    if not m:
        return None
    try:
        value = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    unit = (m.group(2) or "MW").upper()
    return value * {"GW": 1000.0, "MW": 1.0, "KW": 0.001}[unit]


def _int(tags: dict, key: str) -> int | None:
    try:
        return int(str(tags.get(key, "")).split(";")[0].strip())
    except ValueError:
        return None


def _airport(tags: dict) -> int:
    intl = tags.get("aerodrome:type") == "international" or tags.get("aerodrome") == "international"
    return 5 if intl else 4


def _hospital(tags: dict) -> int:
    beds = _int(tags, "beds") or 0
    return 5 if beds >= 1000 else 4 if beds >= 300 else 3


def _power_plant(tags: dict) -> int | None:
    mw = _mw(tags)
    if mw is None or mw < 50:  # skip small / unrated generation
        return None
    return 5 if mw >= 1000 else 4 if mw >= 300 else 3


def _substation(tags: dict) -> int | None:
    volts = [_int({"v": v}, "v") or 0 for v in str(tags.get("voltage", "")).split(";")]
    return 4 if max(volts, default=0) >= 380000 else None


CATEGORIES: dict[str, OsmCategory] = {
    "airport": OsmCategory("airport", "Airport", ('["aeroway"="aerodrome"]["iata"]',), _airport),
    "port": OsmCategory("port", "Port", ('["industrial"="port"]', '["landuse"="port"]'), lambda t: 4),
    "hospital": OsmCategory("hospital", "Hospital", ('["amenity"="hospital"]',), _hospital),
    "power_plant": OsmCategory(
        "power_plant", "Power plant", ('["power"="plant"]["plant:output:electricity"]',), _power_plant
    ),
    "dam": OsmCategory("dam", "Dam", ('["waterway"="dam"]',), lambda t: 4),
    "energy": OsmCategory(
        "energy", "Refinery / terminal",
        ('["industrial"="refinery"]', '["industrial"="oil"]["name"]'), lambda t: 5,
    ),
    "substation": OsmCategory(
        "substation", "Substation (≥380 kV)",
        ('["power"="substation"]["voltage"~"(^|;)(380000|400000)(;|$)"]',), _substation,
        require_name=False,
    ),
    "bridge": OsmCategory("bridge", "Bridge", ('["man_made"="bridge"]',), lambda t: 4),
}


def build_query(categories: list[str], bbox: BBox | None, country: str = "TR", timeout: int = 180) -> str:
    """Overpass QL selecting every requested category, returning element centres."""
    if bbox:
        west, south, east, north = bbox
        scope, prelude = f"({south},{west},{north},{east})", ""
    else:
        if not re.fullmatch(r"[A-Z]{2}", country):
            raise ValueError("country must be an ISO 3166-1 alpha-2 code")
        prelude = f'area["ISO3166-1"="{country}"]["admin_level"="2"]->.aoi;\n'
        scope = "(area.aoi)"
    parts = []
    for key in categories:
        for sel in CATEGORIES[key].selectors:
            parts.append(f"  nwr{sel}{scope};")
    return f"[out:json][timeout:{timeout}];\n{prelude}(\n" + "\n".join(parts) + "\n);\nout center tags;"


def _classify(tags: dict, categories: list[str]) -> OsmCategory | None:
    for key in categories:
        cat = CATEGORIES[key]
        for sel in cat.selectors:
            if _matches(tags, sel):
                return cat
    return None


_SEL = re.compile(r'\["([^"]+)"(?:(=|~)"([^"]*)")?\]')


def _matches(tags: dict, selector: str) -> bool:
    for key, op, value in _SEL.findall(selector):
        if key not in tags:
            return False
        if op == "=" and tags[key] != value:
            return False
        if op == "~" and not re.search(value, tags[key]):
            return False
    return True


def to_features(elements: list[dict], categories: list[str]) -> list[dict]:
    """Convert Overpass elements into Atlas asset features (deduplicated)."""
    feats: dict[str, dict] = {}
    for el in elements:
        tags = el.get("tags") or {}
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        if lat is None or lon is None:
            continue
        cat = _classify(tags, categories)
        if cat is None:
            continue
        crit = cat.criticality(tags)
        if crit is None:
            continue
        name = tags.get("name:tr") or tags.get("name") or tags.get("name:en")
        if not name:
            if cat.require_name:
                continue
            name = f"{cat.label} {tags.get('ref') or el['id']}"
        osm_ref = f"{el['type']}/{el['id']}"
        asset_id = f"osm-{el['type'][0]}{el['id']}"
        capacity = (
            tags.get("plant:output:electricity")
            or (f"{tags['beds']} beds" if tags.get("beds") else None)
            or (f"{int(tags['voltage'].split(';')[0]) // 1000} kV" if cat.asset_type == "substation" else None)
            or tags.get("iata")
        )
        props = {
            "id": asset_id,
            "name": name,
            "type": cat.asset_type,
            "province": tags.get("addr:province") or tags.get("addr:city"),
            "criticality": crit,
            "capacity": capacity,
            "status": "operational" if tags.get("disused") != "yes" else "disused",
            "source": "OpenStreetMap",
            "osm": osm_ref,
            "operator": tags.get("operator"),
            "wikidata": tags.get("wikidata"),
        }
        feats[asset_id] = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": {k: v for k, v in props.items() if v is not None},
        }
    return list(feats.values())


class OverpassError(RuntimeError):
    pass


async def fetch_infrastructure(
    settings: Settings, categories: list[str], bbox: BBox | None, country: str = "TR"
) -> list[dict]:
    if settings.offline:
        raise OverpassError("Atlas is running in offline mode (ATLAS_OFFLINE=1)")
    unknown = [c for c in categories if c not in CATEGORIES]
    if unknown:
        raise ValueError(f"unknown categories: {unknown}")
    query = build_query(categories, bbox, country)
    try:
        async with httpx.AsyncClient(timeout=max(settings.http_timeout, 200)) as client:
            resp = await client.post(settings.overpass_url, data={"data": query})
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Overpass request failed: %s", exc)
        raise OverpassError(f"OpenStreetMap Overpass request failed: {exc}") from exc
    return to_features(elements, categories)
