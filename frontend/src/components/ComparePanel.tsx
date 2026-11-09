import { useEffect, useState } from "react";
import { api } from "../api";
import { useAtlas } from "../context";
import type { ImagerySource, TimelinePoint } from "../types";
import { Field, Section, useAsync } from "./common";

interface Props {
  compare: { left: ImagerySource; right: ImagerySource } | null;
  setCompare: (c: { left: ImagerySource; right: ImagerySource } | null) => void;
}

function Timeline({ series }: { series: TimelinePoint[] }) {
  if (!series.length) return <p className="muted">No events in range.</p>;
  const max = Math.max(...series.map((p) => p.count));
  const w = 300, h = 120, bw = w / series.length;
  return (
    <svg viewBox={`0 0 ${w} ${h + 18}`} className="timeline" role="img" aria-label="Earthquake counts per year">
      {series.map((p, i) => {
        const bh = Math.max(2, (p.count / max) * h);
        const color = p.max_mag >= 7 ? "#d00000" : p.max_mag >= 6 ? "#f3722c" : "#ffd166";
        return (
          <g key={p.period}>
            <rect x={i * bw + 1} y={h - bh} width={Math.max(1, bw - 2)} height={bh} fill={color}>
              <title>{`${p.period}: ${p.count} events, max M${p.max_mag}`}</title>
            </rect>
            {(i === 0 || i === series.length - 1 || series.length <= 12) && (
              <text x={i * bw + bw / 2} y={h + 13} textAnchor="middle">{p.period}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export default function ComparePanel({ compare, setCompare }: Props) {
  const { imagery, notify } = useAtlas();
  const run = useAsync();
  const temporal = imagery?.temporal ?? [];
  const [leftId, setLeftId] = useState(compare?.left.id ?? temporal[0]?.id ?? "");
  const [rightId, setRightId] = useState(compare?.right.id ?? temporal[temporal.length - 1]?.id ?? "");
  const [series, setSeries] = useState<TimelinePoint[]>([]);
  const [source, setSource] = useState("");
  const [minMag, setMinMag] = useState(5);

  useEffect(() => {
    if (!leftId && temporal.length) setLeftId(temporal[0].id);
    if (!rightId && temporal.length) setRightId(temporal[temporal.length - 1].id);
  }, [temporal, leftId, rightId]);

  useEffect(() => {
    run("Timeline", () => api<{ source: string; series: TimelinePoint[] }>("/hazards/earthquakes/timeline", {
      start: "2000-01-01", min_mag: minMag, bucket: "year",
    })).then((r) => { if (r) { setSeries(r.series); setSource(r.source); } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minMag]);

  const all = (imagery?.basemaps ?? []).concat(temporal);
  const enable = () => {
    const left = all.find((t) => t.id === leftId);
    const right = all.find((t) => t.id === rightId);
    if (!left || !right) return notify("Choose two imagery layers", "error");
    setCompare({ left, right });
  };

  return (
    <>
      <Section title="Imagery change detection">
        <p className="muted">Swipe between two dates to inspect urban growth, infrastructure change or post-event damage. Drag the handle on the map.</p>
        <div className="grid2">
          <Field label="Before (left)">
            <select value={leftId} onChange={(e) => setLeftId(e.target.value)}>
              {all.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </Field>
          <Field label="After (right)">
            <select value={rightId} onChange={(e) => setRightId(e.target.value)}>
              {all.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </Field>
        </div>
        <div className="row">
          <button className="primary" onClick={enable}>{compare ? "Update comparison" : "Start comparison"}</button>
          {compare && <button onClick={() => setCompare(null)}>Exit</button>}
        </div>
      </Section>
      <Section title="Seismic activity over time">
        <Field label={`Minimum magnitude: M${minMag.toFixed(1)}`}>
          <input type="range" min={4} max={7} step={0.5} value={minMag} onChange={(e) => setMinMag(Number(e.target.value))} />
        </Field>
        <Timeline series={series} />
        <p className="muted">Events per year since 2000 · source: {source || "—"}</p>
      </Section>
    </>
  );
}
