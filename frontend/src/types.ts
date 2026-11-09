import type { FeatureCollection, Geometry, LineString } from "geojson";

export type FC = FeatureCollection<Geometry, Record<string, any>>;

export interface Asset {
  id: string;
  name: string;
  type: string;
  province?: string;
  lon: number;
  lat: number;
  criticality: number;
  capacity?: string;
  status: string;
}

export interface ImpactResult {
  hazard: "earthquake" | "wildfire" | "flood";
  summary: {
    assets_affected: number;
    critical_assets_affected: number;
    by_type: Record<string, number>;
    [k: string]: unknown;
  };
  assets: (Asset & Record<string, any>)[];
  intensity_rings?: FC;
  model?: string;
  source?: string;
}

export interface Route {
  distance_km: number;
  duration_min: number;
  geometry: LineString;
  source: "osrm" | "estimate";
}

export interface NearestResult {
  origin: { lon: number; lat: number };
  results: (Asset & { distance_km: number; route?: Route })[];
}

export interface CoverageResult {
  radius_km: number;
  facilities: number;
  demand_points: number;
  covered: number;
  coverage_ratio: number;
  uncovered: (Asset & { nearest_facility_km: number | null })[];
}

export interface ImagerySource {
  id: string;
  name: string;
  kind: "basemap" | "satellite";
  tiles: string[];
  attribution: string;
  max_zoom: number;
  year?: number;
}

export interface Health {
  status: string;
  version: string;
  offline: boolean;
  connectors: Record<string, string>;
}

export interface TimelinePoint {
  period: string;
  count: number;
  max_mag: number;
}
