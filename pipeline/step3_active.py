"""Step 3 - Active storms: NHC's live forecast for anything spinning in the Atlantic now.

CurrentStorms.json lists every active storm. For each Atlantic one it links a zip of
map files (a "shapefile") holding the official 5-day forecast track: where the centre
is now (TAU 0) and where NHC expects it in 12, 24, ... 120 hours, with the expected
wind. We keep every advisory we see, so the history of each forecast is kept too.

Outside hurricane season the list is usually empty - that is a success with 0 rows.
This step is allowed to fail (NHC can be busy during a storm); the failure is logged
and the rest of the pipeline still runs on the history.

    python pipeline/step3_active.py                       # live
    python pipeline/step3_active.py --fixture some.zip    # read a saved forecast zip
"""
import argparse
import io
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone

import pandas as pd
import shapefile

from common import LAKE, get, now_utc, record_health, upsert

CURRENT = "https://www.nhc.noaa.gov/CurrentStorms.json"
OUT = LAKE / "active" / "forecast_points.parquet"
KEYS = ["storm_id", "advisory", "tau_h"]
TZ = {"AST": -4, "EDT": -4, "EST": -5, "CDT": -5, "CST": -6, "MDT": -6, "MST": -7, "PDT": -7, "PST": -8,
      "HST": -10, "UTC": 0, "GMT": 0}


def issued_utc(advdate):
    """'1100 AM AST Mon Aug 12 2024' -> 2024-08-12 15:00 UTC."""
    m = re.match(r"(\d{3,4}) (AM|PM) (\w+) \w+ (\w+) (\d+) (\d{4})", advdate.strip())
    hhmm, ampm, tz, mon, day, year = m.groups()
    hhmm = hhmm.zfill(4)
    h, mi = int(hhmm[:2]) % 12 + (12 if ampm == "PM" else 0), int(hhmm[2:])
    local = datetime.strptime(f"{year} {mon} {day}", "%Y %b %d").replace(hour=h, minute=mi)
    return (local - timedelta(hours=TZ.get(tz, 0))).replace(tzinfo=timezone.utc)


def valid_utc(validtime, issued):
    """'13/0000' means day 13 at 00:00 UTC, in the month of the advisory (or the next)."""
    day, hhmm = validtime.split("/")
    t = issued.replace(day=1, hour=int(hhmm[:2]), minute=int(hhmm[2:]))
    if int(day) < issued.day - 5:  # the forecast ran past the end of the month
        t = (t + timedelta(days=32)).replace(day=1)
    return t.replace(day=int(day))


def read_forecast_zip(data: bytes, storm_id: str):
    z = zipfile.ZipFile(io.BytesIO(data))
    base = next(n[:-4] for n in z.namelist() if n.endswith("_5day_pts.shp"))
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                         shx=io.BytesIO(z.read(base + ".shx")))
    rows = []
    for sr in r.iterShapeRecords():
        rec = sr.record.as_dict()
        lon, lat = sr.shape.points[0]  # the point itself; the LAT/LON columns are rounded down
        issued = issued_utc(rec["ADVDATE"])
        rows.append({
            "storm_id": storm_id.lower(), "storm_name": rec["STORMNAME"].strip(),
            "advisory": str(rec["ADVISNUM"]).strip(), "issued_utc": issued.replace(tzinfo=None),
            "tau_h": int(rec["TAU"]), "valid_utc": valid_utc(rec["VALIDTIME"], issued).replace(tzinfo=None),
            "lat": round(lat, 2), "lon": round(lon, 2),
            "max_wind_kt": int(rec["MAXWIND"]), "gust_kt": int(rec["GUST"]),
            "storm_type": rec["STORMTYPE"].strip(), "development": rec["TCDVLP"].strip(),
        })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="read one saved forecast zip instead of asking NHC")
    ap.add_argument("--print", action="store_true", help="print the rows, do not save them")
    args = ap.parse_args()
    if args.fixture:
        sid = re.search(r"(al\d{6})", args.fixture.lower()).group(1)
        df = read_forecast_zip(open(args.fixture, "rb").read(), sid)
        df["fetched_utc"] = pd.Timestamp(df.issued_utc.min())
        print(df.to_string(index=False)) if args.print else print(f"  +{upsert(OUT, df, KEYS)} rows")
        return
    try:
        storms = get(CURRENT).json().get("activeStorms", [])
        atlantic = [s for s in storms if str(s.get("id", "")).lower().startswith("al")]
        frames = []
        for s in atlantic:
            track = s.get("forecastTrack") or {}
            if not track.get("zipFile"):
                continue
            df = read_forecast_zip(get(track["zipFile"]).content, s["id"])
            df["storm_name"] = s.get("name") or df.storm_name
            frames.append(df)
        new = 0
        if frames:
            df = pd.concat(frames, ignore_index=True)
            df["fetched_utc"] = pd.Timestamp(now_utc().replace(tzinfo=None, microsecond=0))
            new = upsert(OUT, df, KEYS)
        print(f"  {len(storms)} active storm(s) worldwide, {len(atlantic)} Atlantic; +{new} forecast rows")
        record_health("nhc_active", True, new, detail=", ".join(s.get("name", "?") for s in atlantic))
    except Exception as e:  # noqa: BLE001
        record_health("nhc_active", False, error=str(e))
        print(f"  NHC active-storm check failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
