import { useMemo, useRef, useState } from "react";
import { api, post } from "../api";
import { useAtlas } from "../context";
import { AssetRow, Field, Section, TypeSelect, useAsync } from "./common";

export default function InventoryPanel({ canWrite }: { canWrite: boolean }) {
  const { assets, reloadAssets, notify } = useAtlas();
  const run = useAsync();
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [minC, setMinC] = useState(1);
  const fileRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    const needle = q.trim().toLocaleLowerCase("tr");
    return assets.filter((a) =>
      (!type || a.type === type) && a.criticality >= minC &&
      (!needle || `${a.name} ${a.province ?? ""} ${a.id}`.toLocaleLowerCase("tr").includes(needle)));
  }, [assets, q, type, minC]);

  const onImport = async (file: File) => {
    const text = await file.text();
    let payload: unknown;
    try {
      payload = JSON.parse(text);
    } catch {
      return notify("File is not valid JSON", "error");
    }
    const r = await run("Import", () => post<{ imported: number }>("/infrastructure/import", payload));
    if (r) {
      notify(`Imported ${r.imported} asset(s)`);
      reloadAssets();
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm(`Delete asset ${id}?`)) return;
    const r = await run("Delete", () => api(`/infrastructure/${encodeURIComponent(id)}`, undefined, { method: "DELETE" }));
    if (r) reloadAssets();
  };

  return (
    <>
      <Section title={`Critical infrastructure · ${filtered.length}/${assets.length}`}>
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
      </Section>
      {canWrite && (
        <Section title="Import (AUGURY CORE)">
          <p className="muted">Upload a GeoJSON FeatureCollection of Point features with <code>id</code>, <code>name</code>, <code>type</code> and <code>criticality</code> (1–5). Existing IDs are updated.</p>
          <input ref={fileRef} type="file" accept=".json,.geojson,application/geo+json,application/json" hidden
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onImport(f); e.target.value = ""; }} />
          <button onClick={() => fileRef.current?.click()}>Choose GeoJSON file…</button>
        </Section>
      )}
    </>
  );
}
