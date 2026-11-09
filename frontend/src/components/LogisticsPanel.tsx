import { useState } from "react";
import { api } from "../api";
import { assetsToFC, pointFC, useAtlas } from "../context";
import type { CoverageResult, FC, NearestResult } from "../types";
import { AssetRow, Field, Section, Stat, TypeSelect, useAsync } from "./common";

const state = {
  type: "hospital", k: 5, nearest: null as NearestResult | null,
  covType: "hospital", radius: 100, coverage: null as CoverageResult | null,
};

export default function LogisticsPanel() {
  const { startPick, pickMode, setMapData, showGroup } = useAtlas();
  const run = useAsync();
  const [s, setS] = useState(state);
  const update = (patch: Partial<typeof state>) => setS((cur) => Object.assign(state, { ...cur, ...patch }));

  const findNearest = (lon: number, lat: number) =>
    run("Nearest facilities", async () => {
      const r = await api<NearestResult>("/logistics/nearest", { lon, lat, types: s.type, k: s.k, with_routes: true });
      update({ nearest: r });
      const routes: FC = {
        type: "FeatureCollection",
        features: r.results.filter((a) => a.route).map((a, i) => ({
          type: "Feature", geometry: a.route!.geometry, properties: { id: a.id, source: a.route!.source, best: i === 0 },
        })),
      };
      setMapData({ routes, marker: pointFC(lon, lat) });
      showGroup("routes");
    });

  const runCoverage = () =>
    run("Coverage", async () => {
      const r = await api<CoverageResult>("/logistics/coverage", { facility_types: s.covType, radius_km: s.radius });
      update({ coverage: r });
      setMapData({ highlight: assetsToFC(r.uncovered, () => "high") });
      showGroup("impact");
    });

  const n = s.nearest;
  const c = s.coverage;
  return (
    <>
      <Section title="Nearest facilities & routing">
        <div className="grid2">
          <Field label="Facility type"><TypeSelect value={s.type} onChange={(v) => update({ type: v })} /></Field>
          <Field label="Results"><input type="number" min={1} max={10} value={s.k} onChange={(e) => update({ k: Number(e.target.value) })} /></Field>
        </div>
        <div className="row">
          <button className={`primary ${pickMode === "origin" ? "active" : ""}`} onClick={() => startPick("origin", findNearest)}>Pick origin on map</button>
          {n && <button onClick={() => { update({ nearest: null }); setMapData({ routes: null, marker: null }); }}>Clear</button>}
        </div>
        {n && (
          <ul className="asset-list">
            {n.results.map((a) => (
              <AssetRow key={a.id} asset={a} detail={a.route ? `${a.route.distance_km} km · ${Math.round(a.route.duration_min)} min (${a.route.source})` : `${a.distance_km} km`} />
            ))}
          </ul>
        )}
        <p className="muted">Road routes via OSRM; dashed lines are straight-line estimates when routing is unavailable.</p>
      </Section>
      <Section title="Service coverage gaps">
        <div className="grid2">
          <Field label="Facility type"><TypeSelect value={s.covType} allowAll={false} onChange={(v) => update({ covType: v })} /></Field>
          <Field label={`Radius: ${s.radius} km`}>
            <input type="range" min={10} max={400} step={10} value={s.radius} onChange={(e) => update({ radius: Number(e.target.value) })} />
          </Field>
        </div>
        <button className="primary" onClick={runCoverage}>Analyse coverage</button>
        {c && (
          <>
            <div className="stats">
              <Stat label="Coverage" value={`${Math.round(c.coverage_ratio * 100)}%`} />
              <Stat label="Uncovered assets" value={c.uncovered.length} />
            </div>
            <ul className="asset-list">
              {c.uncovered.map((a) => <AssetRow key={a.id} asset={a} level="high" detail={a.nearest_facility_km != null ? `${a.nearest_facility_km} km to nearest` : "no facility"} />)}
            </ul>
          </>
        )}
      </Section>
    </>
  );
}
