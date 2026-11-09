import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import MapView, { type FlyTarget, type MapData } from "./components/MapView";
import { Ctx, assetsToFC, type AtlasContext, type PickMode } from "./context";
import type { LayerGroup } from "./mapLayers";
import type { Asset, FC, Health, ImagerySource } from "./types";
import LayersPanel from "./components/LayersPanel";
import AnalysisPanel from "./components/AnalysisPanel";
import RiskPanel from "./components/RiskPanel";
import ComparePanel from "./components/ComparePanel";
import LogisticsPanel from "./components/LogisticsPanel";
import InventoryPanel from "./components/InventoryPanel";

const TABS = [
  { id: "layers", label: "Layers" },
  { id: "analysis", label: "Hazards" },
  { id: "risk", label: "Risk" },
  { id: "compare", label: "Temporal" },
  { id: "logistics", label: "Logistics" },
  { id: "inventory", label: "Inventory" },
] as const;
type TabId = (typeof TABS)[number]["id"];

const INITIAL_VISIBLE: Record<LayerGroup, boolean> = {
  infrastructure: true, earthquakes: true, fires: false, floods: false, risk: false, impact: true, routes: true,
};

export default function App() {
  const [tab, setTab] = useState<TabId>("layers");
  const [health, setHealth] = useState<Health | null>(null);
  const [me, setMe] = useState<{ name: string; role: string } | null>(null);
  const [imagery, setImagery] = useState<AtlasContext["imagery"]>(null);
  const [basemapId, setBasemapId] = useState("dark");
  const [compare, setCompare] = useState<{ left: ImagerySource; right: ImagerySource } | null>(null);
  const [visible, setVisible] = useState(INITIAL_VISIBLE);
  const [mapData, setMapDataState] = useState<MapData>({});
  const [assets, setAssets] = useState<Asset[]>([]);
  const [quakes, setQuakes] = useState<FC | null>(null);
  const [pickMode, setPickMode] = useState<PickMode>(null);
  const pickCb = useRef<((lon: number, lat: number) => void) | null>(null);
  const [flyTo, setFlyTo] = useState<FlyTarget | null>(null);
  const [toast, setToast] = useState<{ msg: string; kind: "error" | "info" } | null>(null);

  const notify = useCallback((msg: string, kind: "error" | "info" = "info") => {
    setToast({ msg, kind });
    window.setTimeout(() => setToast((t) => (t?.msg === msg ? null : t)), 5000);
  }, []);

  const setMapData = useCallback((patch: MapData) => {
    setMapDataState((d) => ({ ...d, ...patch }));
    if ("quakes" in patch) setQuakes((patch.quakes as FC | null | undefined) ?? null);
  }, []);

  const reloadAssets = useCallback(async () => {
    try {
      const fc = await api<FC>("/infrastructure");
      const list = fc.features.map((f) => {
        const [lon, lat] = (f.geometry as GeoJSON.Point).coordinates;
        return { ...(f.properties as Asset), lon, lat };
      });
      setAssets(list);
      setMapData({ infra: assetsToFC(list) });
    } catch (e) {
      notify(`Infrastructure: ${(e as Error).message}`, "error");
    }
  }, [notify, setMapData]);

  const loadPlatform = useCallback(() => {
    api<Health>("/health").then(setHealth).catch(() => setHealth(null));
    api<{ name: string; role: string }>("/me").then(setMe).catch(() => setMe(null));
    api<AtlasContext["imagery"]>("/imagery").then(setImagery).catch((e) => notify(`Imagery: ${e.message}`, "error"));
    reloadAssets();
  }, [notify, reloadAssets]);

  useEffect(loadPlatform, [loadPlatform]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPickMode(null);
        pickCb.current = null;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const basemap = useMemo(
    () => imagery?.basemaps.concat(imagery.temporal).find((b) => b.id === basemapId) ?? imagery?.basemaps[0] ?? null,
    [imagery, basemapId],
  );

  const ctx: AtlasContext = {
    assets,
    reloadAssets,
    imagery,
    setMapData,
    visible,
    showGroup: (group, on = true) => setVisible((v) => ({ ...v, [group]: on })),
    startPick: (mode, cb) => {
      pickCb.current = cb;
      setPickMode(mode);
    },
    pickMode,
    fly: (lon, lat, zoom) => setFlyTo({ lon, lat, zoom, nonce: Date.now() }),
    notify,
    quakes,
  };

  const onPick = useCallback((lon: number, lat: number) => {
    const cb = pickCb.current;
    pickCb.current = null;
    setPickMode(null);
    cb?.(lon, lat);
  }, []);

  return (
    <Ctx.Provider value={ctx}>
      <div className="app">
        <header className="topbar">
          <div className="brand">
            <span className="logo" aria-hidden>◈</span>
            <div>
              <div className="brand-name">AUGURY <b>ATLAS</b></div>
              <div className="brand-sub">Geospatial Intelligence · See the Bigger Picture</div>
            </div>
          </div>
          <div className="status">
            {health ? (
              <>
                {Object.entries(health.connectors).map(([k, v]) => (
                  <span key={k} className={`chip ${v === "live" ? "ok" : "warn"}`} title={`${k.toUpperCase()} connector: ${v}`}>
                    {k.toUpperCase()} · {v}
                  </span>
                ))}
                <span className="chip">v{health.version}</span>
              </>
            ) : (
              <span className="chip err">API offline</span>
            )}
            {me && <span className="chip role" title={me.name}>{me.role}</span>}
          </div>
        </header>
        <aside className="sidebar">
          <nav className="tabs" role="tablist">
            {TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
                {t.label}
              </button>
            ))}
          </nav>
          <div className="panel">
            {tab === "layers" && <LayersPanel basemapId={basemapId} setBasemapId={setBasemapId} onKeyChange={loadPlatform} />}
            {tab === "analysis" && <AnalysisPanel />}
            {tab === "risk" && <RiskPanel />}
            {tab === "compare" && <ComparePanel compare={compare} setCompare={setCompare} />}
            {tab === "logistics" && <LogisticsPanel />}
            {tab === "inventory" && <InventoryPanel canWrite={me?.role === "admin"} />}
          </div>
        </aside>
        <main className="stage">
          <MapView basemap={basemap} compare={compare} visible={visible} data={mapData} picking={pickMode !== null} onPick={onPick} flyTo={flyTo} />
          {toast && <div className={`toast ${toast.kind}`} role="status">{toast.msg}</div>}
        </main>
      </div>
    </Ctx.Provider>
  );
}
