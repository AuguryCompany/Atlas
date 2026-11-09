"""SQLite persistence for the infrastructure inventory and the audit trail."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import datasets

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL,
    province    TEXT,
    lon         REAL NOT NULL,
    lat         REAL NOT NULL,
    criticality INTEGER NOT NULL DEFAULT 3,
    capacity    TEXT,
    status      TEXT NOT NULL DEFAULT 'operational',
    extra       TEXT NOT NULL DEFAULT '{}',
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(type);
CREATE INDEX IF NOT EXISTS idx_assets_lonlat ON assets(lon, lat);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    principal   TEXT NOT NULL,
    role        TEXT NOT NULL,
    method      TEXT NOT NULL,
    path        TEXT NOT NULL,
    query       TEXT,
    status      INTEGER NOT NULL,
    duration_ms REAL NOT NULL
);
"""

ASSET_COLUMNS = (
    "id", "name", "type", "province", "lon", "lat",
    "criticality", "capacity", "status", "extra", "updated_at",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.Lock()
        # check_same_thread=False + a lock keeps this safe under FastAPI's threadpool.
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    def close(self) -> None:
        self._conn.close()

    # ---- assets -------------------------------------------------------
    def seed_if_empty(self) -> int:
        with self.cursor() as cur:
            count = cur.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        if count:
            return 0
        fc = datasets.load("infrastructure.geojson")
        return self.upsert_features(fc["features"])

    def upsert_features(self, features: list[dict]) -> int:
        rows = [feature_to_row(f) for f in features]
        with self.cursor() as cur:
            cur.executemany(
                f"INSERT OR REPLACE INTO assets ({','.join(ASSET_COLUMNS)}) "
                f"VALUES ({','.join('?' * len(ASSET_COLUMNS))})",
                rows,
            )
        return len(rows)

    def list_assets(self, types: list[str] | None = None) -> list[dict]:
        sql = "SELECT * FROM assets"
        params: list = []
        if types:
            sql += f" WHERE type IN ({','.join('?' * len(types))})"
            params = list(types)
        sql += " ORDER BY criticality DESC, name"
        with self.cursor() as cur:
            return [row_to_asset(r) for r in cur.execute(sql, params).fetchall()]

    def get_asset(self, asset_id: str) -> dict | None:
        with self.cursor() as cur:
            row = cur.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        return row_to_asset(row) if row else None

    def delete_asset(self, asset_id: str) -> bool:
        with self.cursor() as cur:
            cur.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            return cur.rowcount > 0

    # ---- audit --------------------------------------------------------
    def write_audit(self, **entry) -> None:
        with self.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (ts, principal, role, method, path, query, status, duration_ms)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.get("ts") or now_iso(), entry["principal"], entry["role"],
                    entry["method"], entry["path"], entry.get("query"),
                    entry["status"], entry["duration_ms"],
                ),
            )

    def list_audit(self, limit: int = 100) -> list[dict]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def feature_to_row(f: dict) -> tuple:
    props = dict(f.get("properties") or {})
    geom = f.get("geometry") or {}
    if geom.get("type") != "Point":
        raise ValueError("infrastructure features must be Point geometries")
    lon, lat = float(geom["coordinates"][0]), float(geom["coordinates"][1])
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError(f"coordinates out of range: {lon},{lat}")
    asset_id = str(props.pop("id", None) or f.get("id") or "").strip()
    name = str(props.pop("name", "") or "").strip()
    if not asset_id or not name:
        raise ValueError("each feature needs an id and a name")
    criticality = int(props.pop("criticality", 3))
    if not 1 <= criticality <= 5:
        raise ValueError("criticality must be between 1 and 5")
    known = {
        "type": str(props.pop("type", "other")),
        "province": props.pop("province", None),
        "capacity": props.pop("capacity", None),
        "status": str(props.pop("status", "operational")),
    }
    return (
        asset_id, name, known["type"], known["province"], lon, lat, criticality,
        known["capacity"], known["status"], json.dumps(props, ensure_ascii=False), now_iso(),
    )


def row_to_asset(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["extra"] = json.loads(d.get("extra") or "{}")
    return d


def asset_to_feature(a: dict, **extra_props) -> dict:
    props = {k: v for k, v in a.items() if k not in {"lon", "lat"}}
    props.update(extra_props)
    return {
        "type": "Feature",
        "id": a["id"],
        "geometry": {"type": "Point", "coordinates": [a["lon"], a["lat"]]},
        "properties": props,
    }
