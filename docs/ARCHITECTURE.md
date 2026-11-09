# Augury Atlas — Architecture

```
            ┌──────────────────────────── frontend (React + MapLibre GL) ───────────────────────────┐
            │  Layers · Hazards · Risk · Temporal (swipe) · Logistics · Inventory                    │
            └───────────────────────────────────────┬────────────────────────────────────────────────┘
                                                    │ /api (JSON / GeoJSON)
┌───────────────────────────────────────── backend (FastAPI) ─────────────────────────────────────────┐
│ AuditMiddleware (AUGURY AUDIT) → identity.require(role) (AUGURY IDENTITY) → routers                 │
│                                                                                                     │
│ routers/      platform · infrastructure · hazards · analysis · logistics                            │
│ services/     hazards (MMI, exposure) · risk (grid) · logistics · imagery (catalogue)               │
│ connectors/   usgs · firms · osrm   (AUGURY CONNECT — TTL cache, graceful fallback)                 │
│ geo.py        haversine, geodesic circles, point-in-polygon, bbox                                   │
│ db.py         SQLite: assets, audit_log                                                             │
│ data/         reference datasets (infrastructure, earthquakes, fires, flood zones)                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Design principles

1. **Provenance is always visible.** Every hazard response carries `source`
   (`usgs`, `firms`, `osrm`, `reference`, `estimate`); the UI shows connector mode in the header.
2. **Degrade, don't fail.** Connectors fall back to bundled reference data or
   estimates when offline, unkeyed, or the upstream errors. `ATLAS_OFFLINE=1` forces this.
3. **Transparent models.** Impact and risk models are simple, documented, and return
   their parameters (model name, weights, formula) with the result.
4. **Least privilege.** Read endpoints need `viewer`, analysis needs `analyst`,
   writes and audit need `admin`. Every call — including denied ones — is audited.
5. **Standards first.** All spatial payloads are GeoJSON (RFC 7946, WGS84 lon/lat).

## Analytical models

### Earthquake impact
`MMI = c1 + c2(M−6) + c3(M−6)² + c4·log10 R + c5·R + c6·B + c7·M·log10 R`
(Atkinson & Wald 2007), `R = sqrt(D² + 14²)`, `B = max(0, log10(R/50))`.
`D` is the epicentral distance reduced by half the Wells & Coppersmith (1994)
surface rupture length, so great earthquakes are not treated as point sources.
Damage states: MMI ≥ 9 severe, ≥ 8 heavy, ≥ 7 moderate, ≥ 6 light.

### Regional risk grid
Per cell: seismic (max modelled MMI mapped 5→10 onto 0→1), wildfire (log detection
density within 25 km), flood (weighted share of a 3×3 sample lattice inside zones),
exposure (log of summed asset criticality).
`score = 100 × Σ(wᵢ·hazardᵢ)/Σwᵢ × (0.25 + 0.75 × exposure)`.

## Roadmap

- PostGIS + vector tiles for large inventories; H3 hex grids.
- Sentinel-1/2 scene search (STAC) and automated change detection (NDVI / NDBI deltas, SAR coherence).
- AFAD / Kandilli catalogue connectors; USGS ShakeMap ingestion for real events.
- Population exposure layer (WorldPop / GHSL).
- Road-network isochrones and evacuation routing on a self-hosted OSRM / Valhalla.
- Integration with AUGURY CORE data graph, NEXUS (natural-language queries over Atlas layers)
  and SENTINEL (physical ↔ cyber asset correlation).
- OIDC/SSO via AUGURY IDENTITY; append-only audit sink.
