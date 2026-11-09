import type maplibregl from "maplibre-gl";
import type { ImagerySource } from "./types";
import { ASSET_COLORS, LEVEL_COLORS, MMI_COLORS, RISK_COLORS } from "./theme";

export const EMPTY_FC = { type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection;

/** Toggleable layer groups → MapLibre layer ids. */
export const LAYER_GROUPS = {
  risk: ["risk-fill", "risk-line"],
  floods: ["floods-fill", "floods-line"],
  impact: ["rings-fill", "rings-line", "highlight-circle"],
  routes: ["route-line", "route-estimate"],
  fires: ["fires-circle"],
  earthquakes: ["quakes-circle"],
  infrastructure: ["infra-circle"],
} as const;

export type LayerGroup = keyof typeof LAYER_GROUPS;

const SOURCES = ["risk", "floods", "rings", "routes", "fires", "quakes", "infra", "highlight", "marker"];

function matchColors(prop: string, colors: Record<string, string>, fallback: string): any {
  return ["match", ["get", prop], ...Object.entries(colors).flat(), fallback];
}

const mmiColor: any = ["match", ["get", "mmi"], ...Object.entries(MMI_COLORS).flatMap(([k, v]) => [Number(k), v]), "#ffd166"];

export function installLayers(map: maplibregl.Map): void {
  for (const id of SOURCES) map.addSource(id, { type: "geojson", data: EMPTY_FC });

  map.addLayer({
    id: "risk-fill", type: "fill", source: "risk",
    paint: { "fill-color": matchColors("class", RISK_COLORS, "rgba(0,0,0,0)"), "fill-opacity": 0.55 },
  });
  map.addLayer({
    id: "risk-line", type: "line", source: "risk",
    filter: ["!=", ["get", "class"], "minimal"],
    paint: { "line-color": "#0b0f17", "line-width": 0.4, "line-opacity": 0.6 },
  });
  map.addLayer({
    id: "floods-fill", type: "fill", source: "floods",
    paint: {
      "fill-color": ["match", ["get", "level"], "high", "#1d4ed8", "medium", "#3b82f6", "#93c5fd"],
      "fill-opacity": 0.35,
    },
  });
  map.addLayer({
    id: "floods-line", type: "line", source: "floods",
    paint: { "line-color": "#60a5fa", "line-width": 1.2 },
  });
  map.addLayer({
    id: "rings-fill", type: "fill", source: "rings",
    paint: {
      "fill-color": mmiColor,
      "fill-opacity": 0.12,
    },
  });
  map.addLayer({
    id: "rings-line", type: "line", source: "rings",
    paint: {
      "line-color": mmiColor,
      "line-width": 1.5, "line-dasharray": [2, 1],
    },
  });
  // line-dasharray cannot be data-driven, so road routes and estimates are separate layers.
  for (const [id, source, dash] of [["route-line", "osrm", null], ["route-estimate", "estimate", [2, 2]]] as const) {
    map.addLayer({
      id, type: "line", source: "routes",
      filter: ["==", ["get", "source"], source],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": source === "osrm" ? "#4ade80" : "#a3e635",
        "line-width": ["case", ["get", "best"], 4, 2.5],
        "line-opacity": ["case", ["get", "best"], 0.95, 0.55],
        ...(dash ? { "line-dasharray": [...dash] } : {}),
      },
    });
  }
  map.addLayer({
    id: "fires-circle", type: "circle", source: "fires",
    paint: {
      "circle-color": ["interpolate", ["linear"], ["coalesce", ["get", "frp"], 10], 0, "#fde047", 50, "#fb923c", 150, "#dc2626"],
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 2.5, 10, 6],
      "circle-blur": 0.4,
      "circle-opacity": 0.85,
    },
  });
  map.addLayer({
    id: "quakes-circle", type: "circle", source: "quakes",
    paint: {
      "circle-color": ["case", ["==", ["get", "source"], "reference"], "#f72585", "#ff9e00"],
      "circle-radius": ["interpolate", ["exponential", 1.6], ["coalesce", ["get", "mag"], 4], 3, 2, 5, 5, 6, 9, 7, 15, 8, 24],
      "circle-opacity": 0.45,
      "circle-stroke-color": ["case", ["==", ["get", "source"], "reference"], "#f72585", "#ff9e00"],
      "circle-stroke-width": 1.2,
    },
  });
  map.addLayer({
    id: "highlight-circle", type: "circle", source: "highlight",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 9, 10, 16],
      "circle-color": "rgba(0,0,0,0)",
      "circle-stroke-color": matchColors("level", LEVEL_COLORS, "#ffffff"),
      "circle-stroke-width": 2.5,
    },
  });
  map.addLayer({
    id: "infra-circle", type: "circle", source: "infra",
    paint: {
      "circle-color": matchColors("type", ASSET_COLORS, "#adb5bd"),
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, ["+", 2, ["get", "criticality"]], 10, ["+", 5, ["*", 1.5, ["get", "criticality"]]]],
      "circle-stroke-color": "#0b0f17",
      "circle-stroke-width": 1,
    },
  });
  map.addLayer({
    id: "marker-circle", type: "circle", source: "marker",
    paint: {
      "circle-radius": 7, "circle-color": "#ffffff",
      "circle-stroke-color": "#f72585", "circle-stroke-width": 3,
    },
  });
}

export function setData(map: maplibregl.Map, source: string, data: GeoJSON.FeatureCollection | null): void {
  const src = map.getSource(source) as maplibregl.GeoJSONSource | undefined;
  src?.setData(data ?? EMPTY_FC);
}

export function setGroupVisible(map: maplibregl.Map, group: LayerGroup, visible: boolean): void {
  for (const id of LAYER_GROUPS[group]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
  }
}

/** Replace the raster basemap, keeping it underneath every analytic layer. */
export function setBasemap(map: maplibregl.Map, source: ImagerySource): void {
  if (map.getLayer("base")) map.removeLayer("base");
  if (map.getSource("base")) map.removeSource("base");
  map.addSource("base", {
    type: "raster",
    tiles: source.tiles,
    tileSize: 256,
    maxzoom: source.max_zoom,
    attribution: source.attribution,
  });
  const firstLayer = map.getStyle().layers.find((l) => l.id !== "base")?.id;
  map.addLayer({ id: "base", type: "raster", source: "base" }, firstLayer);
}

export function rasterStyle(source: ImagerySource): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      base: { type: "raster", tiles: source.tiles, tileSize: 256, maxzoom: source.max_zoom, attribution: source.attribution },
    },
    layers: [{ id: "base", type: "raster", source: "base" }],
  };
}
