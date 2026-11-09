import type { ReactNode } from "react";
import { useAtlas } from "../context";
import { ASSET_COLORS, ASSET_LABELS, LEVEL_COLORS } from "../theme";

export function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="section">
      <header>
        <h3>{title}</h3>
        {aside}
      </header>
      {children}
    </section>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function TypeDot({ type }: { type: string }) {
  return <span className="dot" style={{ background: ASSET_COLORS[type] ?? ASSET_COLORS.other }} title={ASSET_LABELS[type] ?? type} />;
}

export function Badge({ level }: { level: string }) {
  return (
    <span className="badge" style={{ borderColor: LEVEL_COLORS[level] ?? "#888", color: LEVEL_COLORS[level] ?? "#ccc" }}>
      {level.replace("_", " ")}
    </span>
  );
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

export function AssetRow({
  asset, detail, level, action,
}: { asset: { id: string; name: string; type: string; lon: number; lat: number; criticality: number }; detail?: ReactNode; level?: string; action?: ReactNode }) {
  const { fly } = useAtlas();
  return (
    <li className="asset-row" onClick={() => fly(asset.lon, asset.lat, 10)} title="Zoom to asset">
      <TypeDot type={asset.type} />
      <div className="asset-main">
        <div className="asset-name">{asset.name}</div>
        <div className="asset-meta">{ASSET_LABELS[asset.type] ?? asset.type} · C{asset.criticality}{detail ? <> · {detail}</> : null}</div>
      </div>
      {level && <Badge level={level} />}
      {action && <span onClick={(e) => e.stopPropagation()}>{action}</span>}
    </li>
  );
}

export function TypeSelect({ value, onChange, allowAll = true }: { value: string; onChange: (v: string) => void; allowAll?: boolean }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {allowAll && <option value="">All types</option>}
      {Object.entries(ASSET_LABELS).map(([k, v]) => (
        <option key={k} value={k}>{v}</option>
      ))}
    </select>
  );
}

export function useAsync() {
  const { notify } = useAtlas();
  return async function run<T>(label: string, fn: () => Promise<T>): Promise<T | undefined> {
    try {
      return await fn();
    } catch (e) {
      notify(`${label}: ${(e as Error).message}`, "error");
      return undefined;
    }
  };
}
