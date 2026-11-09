import { useState } from "react";
import { api } from "../api";
import { useAtlas } from "../context";
import type { FC } from "../types";
import { RISK_COLORS } from "../theme";
import { Field, Section, useAsync } from "./common";

type Grid = FC & { metadata: { weights: Record<string, number>; formula: string; sources: Record<string, string>; top_cells: Record<string, any>[] } };

const state = { seismic: 0.5, wildfire: 0.2, flood: 0.3, cell: 0.5, grid: null as Grid | null };

export default function RiskPanel() {
  const { setMapData, showGroup, fly } = useAtlas();
  const run = useAsync();
  const [s, setS] = useState(state);
  const [busy, setBusy] = useState(false);
  const update = (patch: Partial<typeof state>) => setS((cur) => Object.assign(state, { ...cur, ...patch }));

  const compute = async () => {
    setBusy(true);
    const grid = await run("Risk grid", () => api<Grid>("/analysis/risk-grid", {
      cell_deg: s.cell, w_seismic: s.seismic, w_wildfire: s.wildfire, w_flood: s.flood, start: "2000-01-01",
    }));
    setBusy(false);
    if (!grid) return;
    update({ grid });
    setMapData({ risk: grid });
    showGroup("risk");
  };

  const focus = (cellId: string) => {
    const f = s.grid?.features.find((x) => x.properties.cell === cellId);
    if (!f) return;
    const ring = (f.geometry as GeoJSON.Polygon).coordinates[0];
    fly((ring[0][0] + ring[2][0]) / 2, (ring[0][1] + ring[2][1]) / 2, 8);
  };

  return (
    <>
      <Section title="Regional risk model">
        <p className="muted">Multi-hazard screening index: hazard (seismic, wildfire, flood) × exposure of critical assets. Weights are normalised.</p>
        {(["seismic", "wildfire", "flood"] as const).map((k) => (
          <Field key={k} label={`${k[0].toUpperCase()}${k.slice(1)} weight: ${s[k].toFixed(2)}`}>
            <input type="range" min={0} max={1} step={0.05} value={s[k]} onChange={(e) => update({ [k]: Number(e.target.value) })} />
          </Field>
        ))}
        <Field label="Cell size">
          <select value={s.cell} onChange={(e) => update({ cell: Number(e.target.value) })}>
            <option value={1}>1.0° (~100 km)</option>
            <option value={0.5}>0.5° (~50 km)</option>
            <option value={0.25}>0.25° (~25 km)</option>
          </select>
        </Field>
        <div className="row">
          <button className="primary" disabled={busy} onClick={compute}>{busy ? "Computing…" : "Compute risk map"}</button>
          {s.grid && <button onClick={() => { update({ grid: null }); setMapData({ risk: null }); }}>Clear</button>}
        </div>
      </Section>
      {s.grid && (
        <Section title="Highest-risk cells">
          <p className="muted">{s.grid.metadata.formula} · sources: {Object.entries(s.grid.metadata.sources).map(([k, v]) => `${k}=${v}`).join(", ")}</p>
          <table className="table">
            <thead><tr><th>Cell</th><th>Score</th><th>Class</th><th>Assets</th></tr></thead>
            <tbody>
              {s.grid.metadata.top_cells.filter((c) => c.score > 0).map((c) => (
                <tr key={c.cell} onClick={() => focus(c.cell)} className="clickable">
                  <td>{c.cell}</td><td>{c.score}</td><td><span className="badge" style={{ borderColor: RISK_COLORS[c.class], color: RISK_COLORS[c.class] }}>{String(c.class).replace("_", " ")}</span></td><td>{c.assets}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
    </>
  );
}
