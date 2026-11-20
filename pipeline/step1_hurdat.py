"""Step 1 - HURDAT2: NOAA's best-track record of every Atlantic storm since 1851.

NHC republishes the whole database once or twice a year, as one text file whose name
says which seasons it covers and when it was released (hurdat2-1851-2025-092326.txt =
seasons 1851-2025, released 23 Sep 2026). This step reads the folder listing, picks the
newest Atlantic file, and only downloads and parses it if it is new to us.

File format: a header line per storm, then one line per track point (every 6 hours,
plus extra points such as landfalls):

    AL112017,               IRMA,     66,
    20170906, 1200,  , HU, 18.3N,  64.7W, 155,  914,  ...wind radii...

Winds are 1-minute sustained, in knots. From 2004 the line also gives how far out
(nautical miles) winds of 34, 50 and 64 knots reached in each quadrant (NE, SE, SW, NW).
"""
import re
import sys

import pandas as pd

from common import DOWNLOAD, LAKE, get, load_state, record_health, save_state, write_parquet

LISTING = "https://www.nhc.noaa.gov/data/hurdat/"
NAME = re.compile(r'href="(hurdat2-1851-(\d{4})-(\d{6}|\d{8})\.txt)"')
OUT = LAKE / "hurdat"


def release_key(seasons, stamp):
    """Sort key for a file: last season, then release date (MMDDYY or MMDDYYYY)."""
    mm, dd, yy = stamp[:2], stamp[2:4], stamp[4:]
    year = int(yy) + 2000 if len(yy) == 2 else int(yy)
    return (int(seasons), year, int(mm), int(dd))


def newest_file():
    html = get(LISTING).text
    files = [(release_key(s, d), f) for f, s, d in NAME.findall(html)]
    if not files:
        raise RuntimeError("no hurdat2-1851-*.txt file in the NHC listing")
    return max(files)[1]


def num(v):
    v = v.strip()
    return None if v in ("", "-999", "-99") else int(v)


def coord(v):
    v = v.strip()
    x = float(v[:-1])
    return -x if v[-1] in "SW" else x


def parse(text):
    storms, points = [], []
    lines = iter(text.splitlines())
    for line in lines:
        if not line.strip():
            continue
        sid, name, n = [p.strip() for p in line.split(",")[:3]]
        storms.append({"storm_id": sid, "name": name, "season": int(sid[4:8]), "n_points": int(n)})
        for i in range(int(n)):
            p = [x.strip() for x in next(lines).split(",")]
            row = {
                "storm_id": sid, "seq": i,
                "time_utc": pd.Timestamp(f"{p[0]} {p[1][:2]}:{p[1][2:]}"),
                "record_id": p[2] or None, "status": p[3],
                "lat": coord(p[4]), "lon": coord(p[5]),
                "wind_kt": num(p[6]), "pressure_mb": num(p[7]),
            }
            for k, kt in enumerate((34, 50, 64)):
                for q, quad in enumerate(("ne", "se", "sw", "nw")):
                    row[f"r{kt}_{quad}"] = num(p[8 + 4 * k + q])
            row["rmw_nmi"] = num(p[20]) if len(p) > 20 else None
            points.append(row)
    return pd.DataFrame(storms), pd.DataFrame(points)


def main():
    try:
        fname = newest_file()
        state = load_state("hurdat")
        if state.get("file") == fname and (OUT / "points.parquet").exists():
            print(f"  {fname} is already in the lake - nothing to do")
            record_health("nhc_hurdat2", True, 0, detail=fname)
            return
        raw = DOWNLOAD / fname
        if not raw.exists():
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(get(LISTING + fname).content)
        storms, points = parse(raw.read_text())
        storms["source_file"] = fname
        write_parquet(storms, OUT / "storms.parquet")
        write_parquet(points, OUT / "points.parquet")
        save_state("hurdat", {"file": fname, "storms": len(storms), "points": len(points)})
        print(f"  {fname}: {len(storms):,} storms, {len(points):,} track points "
              f"({storms.season.min()}-{storms.season.max()})")
        record_health("nhc_hurdat2", True, len(points), detail=fname)
    except Exception as e:  # noqa: BLE001
        record_health("nhc_hurdat2", False, error=str(e))
        if not (OUT / "points.parquet").exists():
            raise
        print(f"  HURDAT2 check failed ({e}); keeping the copy already in the lake", file=sys.stderr)


if __name__ == "__main__":
    main()
