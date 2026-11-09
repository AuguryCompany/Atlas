import { useEffect, useMemo, useRef, useState } from "react";
import { api, post } from "../api";
import { useAtlas } from "../context";
import type { FC } from "../types";
import { AssetRow, Field, Section, TypeSelect, useAsync } from "./common";

async function readGeoJSON(file: File): Promise<unknown> {
  return JSON.parse(await file.text());
}

export default function InventoryPanel({ canWrite }: { canWrite: boolean }) {
  const { assets, reloadAssets, notify, setMapData, showGroup } = useAtlas();
  const run = useAsync();
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [minC, setMinC] = useState(1);
  const [osmCats, setOsmCats] = useState<Record<string, string>>({});
  const [picked, setPicked] = useState<Set<string>>(new Set(["airport", "port", "hospital"]));
  const [busy, setBusy] = useState(false);
  const assetFile = useRef<HTMLInputElement>(null);
  const floodFile = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (canWrite) api<Record<string, string>>("/infrastructure/osm/categories").then(setOsmCats).catch(() => undefined);
  }, [canWrite]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLocaleLowerCase("tr");
    return assets.filter((a) =>
      (!type || a.type === type) && a.criticality >= minC &&
      (!needle || `${a.name} ${a.province ?? ""} ${a.id}`.toLocaleLowerCase("tr").includes(needle)));
  }, [assets, q, type, minC]);

  const importFile = async (file: File, path: string, label: string, after: () => void) => {
    let payload: unknown;
    try {
      payload = await readGeoJSON(file);
    } catch {
      return notify("File is not valid JSON", "error");
    }
    const r = await run(label, () => post<{ imported: number }>(path, payload));
    if (r) {
      notify(`${label}: imported ${r.imported} feature(s)`);
      after();
    }
  };

  const importOsm = async () => {
    if (!picked.size) return notify("Choose at least one category", "error");
    setBusy(true);
    const r = await run("OpenStreetMap import", () =>
      post<{ imported: number; by_type: Record<string, number> }>("/infrastructure/import/osm", { categories: [...picked], country: "TR" }));
    setBusy(false);
    if (r) {
      notify(`Imported ${r.imported} assets from OpenStreetMap`);
      reloadAssets();
    }
  };

  const reloadFloods = async () => {
    const fc = await run("Flood zones", () => api<FC>("/hazards/floods"));
    if (fc) { setMapData({ floods: fc }); showGroup("floods"); }
  };

  const remove = async (id: string) => {
    if (!window.confirm(`Delete asset ${id}?`)) return;
    const r = await run("Delete", () => api(`/infrastructure/${encodeURIComponent(id)}`, undefined, { method: "DELETE" }));
    if (r) reloadAssets();
  };

  return (
    <>
      <Section title={`Critical infrastructure · ${filtered.length}/${assets.length}`}>
        {assets.length === 0 ? (
          <p className="muted">The inventory is empty. {canWrite
            ? "Import real assets from OpenStreetMap or your organisation's GeoJSON below."
            : "Ask an administrator to import your organisation's inventory."}</p>
        ) : (
          <>
            <Field label="Search"><input value={q} placeholder="Name, province or ID" onChange={(e) => setQ(e.target.value)} /></Field>
            <div className="grid2">
              <Field label="Type"><TypeSelect value={type} onChange={setType} /></Field>
              <Field label="Min. criticality">
                <select value={minC} onChange={(e) => setMinC(Number(e.target.value))}>
                  {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>C{n}+</option>)}
                </select>
              </Field>
            </div>
            <ul className="asset-list tall">
              {filtered.map((a) => (
                <AssetRow key={a.id} asset={a} detail={a.province}
                  action={canWrite && <button className="icon" title="Delete" aria-label={`Delete ${a.name}`} onClick={() => remove(a.id)}>✕</button>} />
              ))}
            </ul>
          </>
        )}
      </Section>
      {canWrite && (
        <>
          <Section title="Import from OpenStreetMap (Türkiye)">
            <p className="muted">Discovers named facilities via the Overpass API. Criticality is derived from tags (international status, beds, MW, kV) and can be corrected by re-importing your own data. Data © OpenStreetMap contributors, ODbL.</p>
            <ul className="toggles">
              {Object.entries(osmCats).map(([k, label]) => (
                <li key={k}>
                  <label>
                    <input type="checkbox" checked={picked.has(k)} onChange={(e) => setPicked((s) => {
                      const n = new Set(s);
                      if (e.target.checked) n.add(k); else n.delete(k);
                      return n;
                    })} />
                    {label}
                  </label>
                </li>
              ))}
            </ul>
            <button className="primary" disabled={busy} onClick={importOsm}>{busy ? "Importing… (can take a minute)" : "Import selected"}</button>
          </Section>
          <Section title="Import your data (AUGURY CORE)">
            <p className="muted">Assets: GeoJSON Point features with <code>id</code>, <code>name</code>, <code>type</code>, <code>criticality</code> (1–5). Flood zones: Polygon features with <code>id</code>, <code>name</code>, <code>level</code> (high/medium/low), e.g. from DSİ / AFAD hazard maps. Existing IDs are updated.</p>
            <input ref={assetFile} type="file" accept=".json,.geojson,application/geo+json,application/json" hidden
              onChange={(e) => { const f = e.target.files?.[0]; if (f) importFile(f, "/infrastructure/import", "Assets", reloadAssets); e.target.value = ""; }} />
            <input ref={floodFile} type="file" accept=".json,.geojson,application/geo+json,application/json" hidden
              onChange={(e) => { const f = e.target.files?.[0]; if (f) importFile(f, "/hazards/floods/import", "Flood zones", reloadFloods); e.target.value = ""; }} />
            <div className="row">
              <button onClick={() => assetFile.current?.click()}>Assets GeoJSON…</button>
              <button onClick={() => floodFile.current?.click()}>Flood zones GeoJSON…</button>
            </div>
          </Section>
        </>
      )}
    </>
  );
}
