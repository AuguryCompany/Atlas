"""Catalogue of satellite / basemap imagery sources exposed to the client.

Atlas does not proxy tiles; it publishes a vetted catalogue (URL templates,
attribution, temporal coverage) so every client renders the same sources.
"""

from __future__ import annotations

# EOX Sentinel-2 cloudless annual mosaics (CC BY 4.0 / CC BY-NC-SA 4.0 for 2016).
S2_YEARS = {
    2016: "s2cloudless_3857",
    2018: "s2cloudless-2018_3857",
    2019: "s2cloudless-2019_3857",
    2020: "s2cloudless-2020_3857",
    2021: "s2cloudless-2021_3857",
    2022: "s2cloudless-2022_3857",
    2023: "s2cloudless-2023_3857",
}
EOX_TEMPLATE = "https://tiles.maps.eox.at/wmts/1.0.0/{layer}/default/g/{{z}}/{{y}}/{{x}}.jpg"
EOX_ATTRIBUTION = (
    "Sentinel-2 cloudless {year} by EOX IT Services GmbH "
    "(contains modified Copernicus Sentinel data)"
)


def catalogue() -> dict:
    basemaps = [
        {
            "id": "dark",
            "name": "Dark (CARTO)",
            "kind": "basemap",
            "tiles": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"],
            "attribution": "© OpenStreetMap contributors © CARTO",
            "max_zoom": 19,
        },
        {
            "id": "osm",
            "name": "OpenStreetMap",
            "kind": "basemap",
            "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            "attribution": "© OpenStreetMap contributors",
            "max_zoom": 19,
        },
        {
            "id": "esri-imagery",
            "name": "Satellite (Esri World Imagery)",
            "kind": "satellite",
            "tiles": [
                "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            ],
            "attribution": "Imagery © Esri, Maxar, Earthstar Geographics",
            "max_zoom": 19,
        },
    ]
    temporal = [
        {
            "id": f"s2-{year}",
            "name": f"Sentinel-2 cloudless {year}",
            "kind": "satellite",
            "year": year,
            "tiles": [EOX_TEMPLATE.format(layer=layer)],
            "attribution": EOX_ATTRIBUTION.format(year=year),
            "max_zoom": 15,
        }
        for year, layer in sorted(S2_YEARS.items())
    ]
    return {"basemaps": basemaps, "temporal": temporal}
