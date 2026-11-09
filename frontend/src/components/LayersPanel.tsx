import { useEffect, useState } from "react";
import { api, getApiKey, setApiKey } from "../api";
import { useAtlas } from "../context";
import type { LayerGroup } from "../mapLayers";
import { ASSET_COLORS, ASSET_LABELS, RISK_COLORS } from "../theme";
import type { FC } from "../types";
import { Field, Section, useAsync } from "./common";

const GROUPS: { id: LayerGroup; label: string; swatch: string }[] = [
  { id: "infrastructure", label: "Critical infrastructure", swatch: "#4cc9f0" },
  { id: "earthquakes", label: "Earthquakes", swatch: "#ff9e00" },
  { id: "fires", label: "Active fires", swatch: "#dc2626" },
  { id: "floods", label: "Flood-prone zones", swatch: "#3b82f6" },
  { id: "risk", label: "Regional risk grid", swatch: "#f46d43" },
  { id: "impact", label: "Impact analysis", swatch: "#ffd166" },
  { id: "routes", label: "Routes", swatch: "#4ade80" },
];

// Filters survive tab switches.
const filters = {
  start: new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10),
  end: new Date().toISOString().slice(0, 10),
  minMag: 4.5,
  withReference: true,
  fireDays: 2,
};

export default function LayersPanel({ basemapId, setBasemapId, onKeyChange }: { basemapId: string; setBasemapId: (id: string) => void; onKeyChange: () => void }) {
  const { imagery, visible, showGroup, setMapData, quakes, notify } = useAtlas();
  const run = useAsync();
  const [f, setF] = useState(filters);
  const [meta, setMeta] = useState<{ quakes?: string; fires?: string }>({});
  const [key, setKey] = useState(getApiKey());
  const update = (patch: Partial<typeof filters>) => setF((cur) => Object.assign(filters, { ...cur, ...patch }));

  const loadQuakes = () =>
    run("Earthquakes", async () => {
      const live = await api<FC & { metadata: { source: string; count: number } }>("/hazards/earthquakes", { start: f.start, end: f.end, min_mag: f.minMag });
      let features = live.features;
      if (f.withReference) {
        const ref = await api<FC>("/hazards/earthquakes/reference");
        const seen = new Set(features.map((x) => x.id));
        features = features.concat(ref.features.filter((x) => !seen.has(x.id)));
      }
      setMapData({ quakes: { type: "FeatureCollection", features } });
      setMeta((m) => ({ ...m, quakes: `${live.metadata.count} from ${live.metadata.source}${f.withReference ? " + historical reference" : ""}` }));
    });

  const loadFires = () =>
    run("Fires", async () => {
      const fc = await api<FC & { metadata: { source: string; count: number } }>("/hazards/fires", { days: f.fireDays });
      setMapData({ fires: fc });
      setMeta((m) => ({ ...m, fires: `${fc.metadata.count} detections from ${fc.metadata.source}` }));
    });

  const loadFloods = () => run("Floods", async () => setMapData({ floods: await api<FC>("/hazards/floods") }));

  useEffect(() => {
    if (!quakes) loadQuakes();
    loadFloods();
    loadFires();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <Section title="Base imagery">
        <select value={basemapId} onChange={(e) => setBasemapId(e.target.value)} aria-label="Base imagery">
          <optgroup label="Basemaps">
            {imagery?.basemaps.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </optgroup>
          <optgroup label="Sentinel-2 annual mosaics">
            {imagery?.temporal.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </optgroup>
        </select>
      </Section>

      <Section title="Layers">
        <ul className="toggles">
          {GROUPS.map((g) => (
            <li key={g.id}>
              <label>
                <input type="checkbox" checked={visible[g.id]} onChange={(e) => showGroup(g.id, e.target.checked)} />
                <span className="swatch" style={{ background: g.swatch }} />
                {g.label}
              </label>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Earthquake feed" aside={<button className="link" onClick={loadQuakes}>Reload</button>}>
        <div className="grid2">
          <Field label="From"><input type="date" value={f.start} onChange={(e) => update({ start: e.target.value })} /></Field>
          <Field label="To"><input type="date" value={f.end} onChange={(e) => update({ end: e.target.value })} /></Field>
        </div>
        <Field label={`Minimum magnitude: M${f.minMag.toFixed(1)}`}>
          <input type="range" min={2.5} max={7} step={0.1} value={f.minMag} onChange={(e) => update({ minMag: Number(e.target.value) })} />
        </Field>
        <label className="check">
          <input type="checkbox" checked={f.withReference} onChange={(e) => update({ withReference: e.target.checked })} />
          Include historical reference events
        </label>
        {meta.quakes && <p className="muted">{meta.quakes}</p>}
      </Section>

      <Section title="Active fires" aside={<button className="link" onClick={loadFires}>Reload</button>}>
        <Field label={`Window: last ${f.fireDays} day(s)`}>
          <input type="range" min={1} max={10} value={f.fireDays} onChange={(e) => update({ fireDays: Number(e.target.value) })} />
        </Field>
        {meta.fires && <p className="muted">{meta.fires}</p>}
      </Section>

      <Section title="Legend">
        <div className="legend">
          {Object.entries(ASSET_LABELS).filter(([k]) => k !== "other").map(([k, v]) => (
            <span key={k}><i style={{ background: ASSET_COLORS[k] }} />{v}</span>
          ))}
        </div>
        <div className="legend">
          {Object.entries(RISK_COLORS).filter(([k]) => k !== "minimal").map(([k, v]) => (
            <span key={k}><i style={{ background: v }} />Risk: {k.replace("_", " ")}</span>
          ))}
          <span><i style={{ background: "#ff9e00" }} />Live quake</span>
          <span><i style={{ background: "#f72585" }} />Reference quake</span>
        </div>
      </Section>

      <Section title="Access (AUGURY IDENTITY)">
        <Field label="API key">
          <input type="password" value={key} placeholder="Not required in dev mode" onChange={(e) => setKey(e.target.value)} />
        </Field>
        <button onClick={() => { setApiKey(key); onKeyChange(); notify("API key updated"); }}>Apply</button>
      </Section>
    </>
  );
}
