import { useMemo, useState } from "react";
import { api, post } from "../api";
import { assetsToFC, pointFC, useAtlas } from "../context";
import type { ImpactResult } from "../types";
import { AssetRow, Field, Section, Stat, useAsync } from "./common";

const state = {
  lon: 37.014, lat: 37.226, magnitude: 7.8, minMmi: 6, buffer: 10, days: 2,
  result: null as ImpactResult | null,
};

function levelOf(a: Record<string, any>): string {
  return a.damage_state ?? a.exposure ?? "none";
}

function detailOf(a: Record<string, any>): string {
  if (a.mmi != null) return `MMI ${a.mmi} · ${a.distance_km} km`;
  if (a.nearest_fire_km != null) return `${a.nearest_fire_km} km to fire · ${a.detections_in_buffer} det.`;
  if (a.zone_name) return a.zone_name;
  return "";
}

export default function AnalysisPanel() {
  const { setMapData, showGroup, startPick, pickMode, quakes, fly } = useAtlas();
  const run = useAsync();
  const [s, setS] = useState(state);
  const [busy, setBusy] = useState(false);
  const update = (patch: Partial<typeof state>) => setS((cur) => Object.assign(state, { ...cur, ...patch }));

  const events = useMemo(
    () => (quakes?.features ?? [])
      .filter((f) => f.properties.mag != null)
      .sort((a, b) => b.properties.mag - a.properties.mag)
      .slice(0, 25),
    [quakes],
  );

  const show = (result: ImpactResult, extras: Parameters<typeof setMapData>[0] = {}) => {
    update({ result });
    setMapData({ highlight: assetsToFC(result.assets, levelOf), rings: null, marker: null, ...extras });
    showGroup("impact");
  };

  const runQuake = async (lon = s.lon, lat = s.lat) => {
    setBusy(true);
    const r = await run("Earthquake impact", () =>
      post<ImpactResult>("/analysis/earthquake", { lon, lat, magnitude: s.magnitude, min_mmi: s.minMmi }));
    setBusy(false);
    if (!r) return;
    show(r, { rings: r.intensity_rings ?? null, marker: pointFC(lon, lat) });
    fly(lon, lat, 6);
  };

  const runFire = async () => {
    setBusy(true);
    const r = await run("Wildfire exposure", () => api<ImpactResult>("/analysis/wildfire", { buffer_km: s.buffer, days: s.days }));
    setBusy(false);
    if (r) { show(r); showGroup("fires"); }
  };

  const runFlood = async () => {
    setBusy(true);
    const r = await run("Flood exposure", () => api<ImpactResult>("/analysis/flood"));
    setBusy(false);
    if (r) { show(r); showGroup("floods"); }
  };

  const clear = () => {
    update({ result: null });
    setMapData({ highlight: null, rings: null, marker: null });
  };

  const r = s.result;
  return (
    <>
      <Section title="Earthquake impact">
        <Field label="Historical / live event">
          <select value="" onChange={(e) => {
            const f = events[Number(e.target.value)];
            if (!f) return;
            const [lon, lat] = (f.geometry as GeoJSON.Point).coordinates;
            update({ lon, lat, magnitude: f.properties.mag });
          }}>
            <option value="">Choose an event to model…</option>
            {events.map((f, i) => <option key={String(f.id)} value={i}>{f.properties.title} ({String(f.properties.time).slice(0, 10)})</option>)}
          </select>
        </Field>
        <div className="grid2">
          <Field label="Longitude"><input type="number" step="0.001" value={s.lon} onChange={(e) => update({ lon: Number(e.target.value) })} /></Field>
          <Field label="Latitude"><input type="number" step="0.001" value={s.lat} onChange={(e) => update({ lat: Number(e.target.value) })} /></Field>
        </div>
        <Field label={`Magnitude: M${s.magnitude.toFixed(1)}`}>
          <input type="range" min={4} max={8.5} step={0.1} value={s.magnitude} onChange={(e) => update({ magnitude: Number(e.target.value) })} />
        </Field>
        <Field label={`Report assets at MMI ≥ ${s.minMmi}`}>
          <input type="range" min={4} max={9} step={0.5} value={s.minMmi} onChange={(e) => update({ minMmi: Number(e.target.value) })} />
        </Field>
        <div className="row">
          <button className="primary" disabled={busy} onClick={() => runQuake()}>Run scenario</button>
          <button className={pickMode === "epicenter" ? "active" : ""} onClick={() => startPick("epicenter", (lon, lat) => {
            update({ lon: +lon.toFixed(4), lat: +lat.toFixed(4) });
            runQuake(lon, lat);
          })}>Pick epicenter</button>
        </div>
      </Section>

      <Section title="Wildfire & flood exposure">
        <div className="grid2">
          <Field label={`Buffer: ${s.buffer} km`}>
            <input type="range" min={1} max={50} value={s.buffer} onChange={(e) => update({ buffer: Number(e.target.value) })} />
          </Field>
          <Field label={`Fires: last ${s.days} d`}>
            <input type="range" min={1} max={10} value={s.days} onChange={(e) => update({ days: Number(e.target.value) })} />
          </Field>
        </div>
        <div className="row">
          <button disabled={busy} onClick={runFire}>Wildfire exposure</button>
          <button disabled={busy} onClick={runFlood}>Flood exposure</button>
        </div>
      </Section>

      {r && (
        <Section title={`Result · ${r.hazard}`} aside={<button className="link" onClick={clear}>Clear</button>}>
          <div className="stats">
            <Stat label="Assets affected" value={r.summary.assets_affected} />
            <Stat label="Critical (C4–5)" value={r.summary.critical_assets_affected} />
          </div>
          {r.model && <p className="muted">{r.model}</p>}
          {r.source && <p className="muted">Data source: {r.source}</p>}
          {r.hazard === "flood" && r.zones === 0 && <p className="muted">No flood zones loaded — import official zones in Inventory.</p>}
          {r.assets.length === 0 ? <p className="muted">No assets in the affected area.</p> : (
            <ul className="asset-list">
              {r.assets.map((a) => <AssetRow key={a.id} asset={a} level={levelOf(a)} detail={detailOf(a)} />)}
            </ul>
          )}
        </Section>
      )}
    </>
  );
}
