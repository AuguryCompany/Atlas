import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { ImagerySource } from "../types";
import { installLayers, LAYER_GROUPS, rasterStyle, setBasemap, setData, setGroupVisible, type LayerGroup } from "../mapLayers";
import { ASSET_LABELS } from "../theme";

export type MapData = Partial<Record<"risk" | "floods" | "rings" | "routes" | "fires" | "quakes" | "infra" | "highlight" | "marker", GeoJSON.FeatureCollection | null>>;

export interface FlyTarget {
  lon: number;
  lat: number;
  zoom?: number;
  nonce: number;
}

interface Props {
  basemap: ImagerySource | null;
  compare: { left: ImagerySource; right: ImagerySource } | null;
  visible: Record<LayerGroup, boolean>;
  data: MapData;
  picking: boolean;
  onPick: (lon: number, lat: number) => void;
  flyTo: FlyTarget | null;
}

const INTERACTIVE = ["infra-circle", "quakes-circle", "fires-circle", "floods-fill", "risk-fill"];

function esc(v: unknown): string {
  return String(v ?? "—").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

function popupHtml(layer: string, p: Record<string, any>): string {
  const row = (k: string, v: unknown) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`;
  switch (layer) {
    case "infra-circle":
      return `<h4>${esc(p.name)}</h4><table>${row("Type", ASSET_LABELS[p.type] ?? p.type)}${row("Province", p.province)}${row("Criticality", `${p.criticality} / 5`)}${row("Capacity", p.capacity)}${row("Status", p.status)}${row("ID", p.id)}</table>`;
    case "quakes-circle":
      return `<h4>${esc(p.title)}</h4><table>${row("Magnitude", p.mag)}${row("Depth", p.depth_km != null ? `${p.depth_km} km` : "—")}${row("Time (UTC)", p.time)}${row("Source", p.source)}</table><p class="hint">Use “Analysis → Earthquake impact” to model this event.</p>`;
    case "fires-circle":
      return `<h4>Thermal anomaly</h4><table>${row("Date", p.acq_date)}${row("FRP", p.frp != null ? `${p.frp} MW` : "—")}${row("Confidence", p.confidence)}${row("Area", p.area)}${row("Source", p.source)}</table>`;
    case "floods-fill":
      return `<h4>${esc(p.name)}</h4><table>${row("Province", p.province)}${row("Level", p.level)}</table><p class="hint">Illustrative zone — not an official hazard map.</p>`;
    case "risk-fill":
      return `<h4>Risk cell ${esc(p.cell)}</h4><table>${row("Score", p.score)}${row("Class", p.class)}${row("Seismic", p.seismic)}${row("Wildfire", p.wildfire)}${row("Flood", p.flood)}${row("Exposure", p.exposure)}${row("Assets", p.assets)}</table>`;
    default:
      return "";
  }
}

export default function MapView({ basemap, compare, visible, data, picking, onPick, flyTo }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const overlayContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<maplibregl.Map | null>(null);
  const pickRef = useRef({ picking, onPick });
  const [ready, setReady] = useState(false);
  const [split, setSplit] = useState(50);

  pickRef.current = { picking, onPick };

  // Create the main map once.
  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: { version: 8, sources: {}, layers: [] },
      center: [35.2, 39.0],
      zoom: 5.2,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    map.on("load", () => {
      installLayers(map);
      setReady(true);
    });
    const popup = new maplibregl.Popup({ closeButton: true, maxWidth: "320px", className: "atlas-popup" });
    map.on("click", (e) => {
      if (pickRef.current.picking) {
        pickRef.current.onPick(e.lngLat.lng, e.lngLat.lat);
        return;
      }
      const layers = INTERACTIVE.filter((id) => map.getLayer(id) && map.getLayoutProperty(id, "visibility") !== "none");
      const hit = map.queryRenderedFeatures(e.point, { layers })[0];
      if (!hit) return;
      popup.setLngLat(e.lngLat).setHTML(popupHtml(hit.layer.id, hit.properties ?? {})).addTo(map);
    });
    for (const id of INTERACTIVE) {
      map.on("mouseenter", id, () => { if (!pickRef.current.picking) map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", id, () => { if (!pickRef.current.picking) map.getCanvas().style.cursor = ""; });
    }
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (map) map.getCanvas().style.cursor = picking ? "crosshair" : "";
  }, [picking]);

  // Basemap (left side when comparing).
  const effectiveBase = compare ? compare.left : basemap;
  useEffect(() => {
    if (ready && effectiveBase && mapRef.current) setBasemap(mapRef.current, effectiveBase);
  }, [ready, effectiveBase]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    for (const [source, fc] of Object.entries(data)) setData(map, source, fc ?? null);
  }, [ready, data]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    for (const group of Object.keys(LAYER_GROUPS) as LayerGroup[]) setGroupVisible(map, group, visible[group]);
  }, [ready, visible]);

  useEffect(() => {
    if (flyTo && mapRef.current) {
      mapRef.current.flyTo({ center: [flyTo.lon, flyTo.lat], zoom: flyTo.zoom ?? 9, speed: 1.4 });
    }
  }, [flyTo]);

  // Swipe-compare overlay: a passive second map that mirrors the main camera.
  useEffect(() => {
    const main = mapRef.current;
    if (!compare || !overlayContainer.current || !main) return;
    const overlay = new maplibregl.Map({
      container: overlayContainer.current,
      style: rasterStyle(compare.right),
      center: main.getCenter(),
      zoom: main.getZoom(),
      bearing: main.getBearing(),
      pitch: main.getPitch(),
      interactive: false,
      attributionControl: false,
    });
    const sync = () => overlay.jumpTo({
      center: main.getCenter(), zoom: main.getZoom(), bearing: main.getBearing(), pitch: main.getPitch(),
    });
    main.on("move", sync);
    overlayRef.current = overlay;
    return () => {
      main.off("move", sync);
      overlay.remove();
      overlayRef.current = null;
    };
  }, [compare]);

  const startDrag = (e: React.PointerEvent) => {
    const host = container.current?.parentElement;
    if (!host) return;
    e.preventDefault();
    const rect = host.getBoundingClientRect();
    const move = (ev: PointerEvent) => {
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setSplit(Math.max(2, Math.min(98, pct)));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return (
    <div className="map-host">
      <div ref={container} className="map" />
      {compare && (
        <>
          <div ref={overlayContainer} className="map overlay" style={{ clipPath: `inset(0 0 0 ${split}%)` }} />
          <div className="swipe" style={{ left: `${split}%` }} onPointerDown={startDrag} role="slider" aria-label="Compare imagery" aria-valuenow={Math.round(split)} tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft") setSplit((s) => Math.max(2, s - 2));
              if (e.key === "ArrowRight") setSplit((s) => Math.min(98, s + 2));
            }}>
            <span>⇆</span>
          </div>
          <div className="compare-tag left">{compare.left.name}</div>
          <div className="compare-tag right">{compare.right.name}</div>
        </>
      )}
      {picking && <div className="pick-hint">Click on the map to select a location · Esc to cancel</div>}
    </div>
  );
}
