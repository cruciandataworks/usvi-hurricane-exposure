"""Shared helpers: HTTP with retries, the Parquet "lake", distances, and the source-health log.

The lake (all Parquet, never edited by hand):

    lake/hurdat/    NOAA's Atlantic hurricane database (HURDAT2): storms and track points
    lake/census/    2020 Census population and housing units by estate, plus estate shapes
    lake/active/    every NHC forecast we have seen for an active Atlantic storm
    lake/_download/ the raw files exactly as downloaded (so a rebuild never re-downloads)
    lake/_state/    which file versions we already have, and collector health
"""
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
LAKE = Path(os.environ.get("LAKE_DIR", ROOT / "lake"))
DOWNLOAD = LAKE / "_download"
STATE = LAKE / "_state"
HEADERS = {"User-Agent": "CrucianDataWorks-portfolio/1.0 (hello@cruciandataworks.com)"}

# The middle of the territory, used only to decide which storm points are worth a closer look
USVI_LAT, USVI_LON = 18.05, -64.83


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get(url, tries=3, timeout=60):
    """GET with retries after a failure (waits 5 then 15 seconds)."""
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code >= 500 or r.status_code == 429:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            if r.status_code >= 400:
                raise LookupError(f"HTTP {r.status_code} for {url}")
            return r
        except (requests.RequestException, requests.HTTPError) as e:
            last = e
            if attempt < tries - 1:
                time.sleep(5 * 3 ** attempt)
    raise RuntimeError(f"failed after {tries} attempts: {last}")


def nmi(lat1, lon1, lat2, lon2):
    """Great-circle distance in nautical miles (the unit NHC uses for wind radii)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 3440.065 * math.asin(math.sqrt(a))


def write_parquet(df: pd.DataFrame, path: Path):
    """Write a whole table, beside the old file first so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for c in df.columns:  # an all-empty text column must still be text
        if df[c].dtype == object and df[c].isna().all():
            df[c] = df[c].astype("string")
    con = duckdb.connect()
    con.register("df", df)
    tmp = path.with_suffix(".tmp")
    con.execute(f"copy df to '{tmp}' (format parquet, compression zstd)")
    os.replace(tmp, path)


def upsert(path: Path, df: pd.DataFrame, keys: list) -> int:
    """Merge new rows into one Parquet file. A row whose keys already exist is replaced
    by the newer copy, so repeating a run never creates duplicates. Returns new rows."""
    if df.empty:
        return 0
    df = df.drop_duplicates(subset=keys, keep="last").copy()
    for c in df.columns:
        if df[c].dtype == object and df[c].isna().all():
            df[c] = df[c].astype("string")
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.register("new_rows", df)
    if path.exists():
        before = con.execute(f"select count(*) from read_parquet('{path}')").fetchall()[0][0]
        query = f"""
            select * exclude (src, rn) from (
                select *, row_number() over (partition by {', '.join(keys)} order by src desc) rn
                from (select *, 1 as src from new_rows
                      union all by name select *, 0 as src from read_parquet('{path}'))
            ) where rn = 1 order by {', '.join(keys)}"""
    else:
        before = 0
        query = f"select * from new_rows order by {', '.join(keys)}"
    tmp = path.with_suffix(".tmp")
    con.execute(f"copy ({query}) to '{tmp}' (format parquet, compression zstd)")
    after = con.execute(f"select count(*) from read_parquet('{tmp}')").fetchall()[0][0]
    os.replace(tmp, path)
    return after - before


def load_state(name):
    f = STATE / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def save_state(name, data):
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / f"{name}.json").write_text(json.dumps(data, indent=2, sort_keys=True))


def record_health(source: str, ok: bool, rows: int = 0, error: str = "", detail: str = ""):
    """One line per source: when it last worked, how many tries in a row failed, and the
    last error. The dashboard and the alerts read this file."""
    health = load_state("health")
    h = health.get(source, {"consecutive_failures": 0})
    h["last_attempt"] = now_utc().replace(microsecond=0).isoformat()
    if ok:
        h.update(last_success=h["last_attempt"], consecutive_failures=0, last_rows=rows,
                 last_error="", detail=detail)
    else:
        h["consecutive_failures"] = h.get("consecutive_failures", 0) + 1
        h["last_error"] = error[:300]
    health[source] = h
    save_state("health", health)
