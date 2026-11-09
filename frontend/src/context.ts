import { createContext, useContext } from "react";
import type { MapData } from "./components/MapView";
import type { LayerGroup } from "./mapLayers";
import type { Asset, FC, ImagerySource } from "./types";

export type PickMode = "epicenter" | "origin" | null;

export interface AtlasContext {
  assets: Asset[];
  reloadAssets: () => Promise<void>;
  imagery: { basemaps: ImagerySource[]; temporal: ImagerySource[] } | null;
  setMapData: (patch: MapData) => void;
  showGroup: (group: LayerGroup, on?: boolean) => void;
  visible: Record<LayerGroup, boolean>;
  startPick: (mode: Exclude<PickMode, null>, cb: (lon: number, lat: number) => void) => void;
  pickMode: PickMode;
  fly: (lon: number, lat: number, zoom?: number) => void;
  notify: (msg: string, kind?: "error" | "info") => void;
  quakes: FC | null;
}

export const Ctx = createContext<AtlasContext | null>(null);

export function useAtlas(): AtlasContext {
  const c = useContext(Ctx);
  if (!c) throw new Error("Atlas context missing");
  return c;
}

export function assetsToFC(assets: Asset[], level?: (a: any) => string): FC {
  return {
    type: "FeatureCollection",
    features: assets.map((a) => ({
      type: "Feature",
      id: a.id,
      geometry: { type: "Point", coordinates: [a.lon, a.lat] },
      properties: { ...a, ...(level ? { level: level(a) } : {}) },
    })),
  };
}

export function pointFC(lon: number, lat: number): FC {
  return { type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: {} }] };
}
