"""Base de datos SQLite: esquema y helpers."""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "coach.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    activity_id     INTEGER PRIMARY KEY,
    start_time      TEXT,           -- ISO local
    name            TEXT,
    type_key        TEXT,           -- mountain_biking, road_biking, etc.
    distance_m      REAL,
    duration_s      REAL,
    moving_s        REAL,
    elevation_gain_m REAL,
    avg_hr          REAL,
    max_hr          REAL,
    avg_power       REAL,
    norm_power      REAL,
    has_power       INTEGER DEFAULT 0,
    calories        REAL,
    hr_zone_secs    TEXT,           -- JSON: {"1": secs, ..., "5": secs}
    trimp           REAL,           -- se calcula en fase 2
    tss             REAL,           -- se calcula en fase 2
    raw_json        TEXT,
    synced_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    date              TEXT PRIMARY KEY,  -- YYYY-MM-DD
    resting_hr        REAL,
    hrv_last_night    REAL,
    hrv_weekly_avg    REAL,
    hrv_status        TEXT,
    sleep_seconds     REAL,
    sleep_score       REAL,
    training_readiness REAL,
    readiness_status  TEXT,
    body_battery_max  REAL,
    body_battery_min  REAL,
    raw_json          TEXT,
    synced_at         TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS sync_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    ok         INTEGER,
    detail     TEXT
);
"""


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript(SCHEMA)


def get_setting(key, default=None):
    with get_db() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_db() as db:
        db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def get_all_settings():
    with get_db() as db:
        rows = db.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


def rows_to_dicts(rows, drop_raw=True):
    out = []
    for r in rows:
        d = dict(r)
        if drop_raw:
            d.pop("raw_json", None)
        if d.get("hr_zone_secs"):
            try:
                d["hr_zone_secs"] = json.loads(d["hr_zone_secs"])
            except (json.JSONDecodeError, TypeError):
                pass
        out.append(d)
    return out
