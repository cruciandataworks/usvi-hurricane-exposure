"""Step 4 - Load: copy the lake into one DuckDB warehouse, in a "raw" schema dbt reads.

    raw.hurdat_storms, raw.hurdat_points   NOAA's best tracks (step 1)
    raw.census_counts, raw.estate_shapes   2020 Census by estate + estate boundaries (step 2)
    raw.active_forecast                    every live NHC forecast we have saved (step 3)
    raw.source_health                      when each collector last worked

Nothing is changed here; all the logic lives in dbt, where it is tested.
"""
import json

import duckdb
import pandas as pd

from common import LAKE, ROOT, STATE

DB = ROOT / "warehouse" / "hurricanes.duckdb"
EMPTY_FORECAST = """select ''::varchar storm_id, ''::varchar storm_name, ''::varchar advisory,
    null::timestamp issued_utc, 0 tau_h, null::timestamp valid_utc, 0.0 lat, 0.0 lon, 0 max_wind_kt,
    0 gust_kt, ''::varchar storm_type, ''::varchar development, null::timestamp fetched_utc where false"""


def main():
    DB.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("create schema if not exists raw")
    tables = {
        "hurdat_storms": LAKE / "hurdat" / "storms.parquet",
        "hurdat_points": LAKE / "hurdat" / "points.parquet",
        "census_counts": LAKE / "census" / "estate_counts.parquet",
        "estate_shapes": LAKE / "census" / "estate_shapes.parquet",
        "active_forecast": LAKE / "active" / "forecast_points.parquet",
    }
    for table, path in tables.items():
        if path.exists():
            con.execute(f"create or replace table raw.{table} as select * from read_parquet('{path}')")
        elif table == "active_forecast":  # no storm seen yet: an empty table with the right columns
            con.execute(f"create or replace table raw.{table} as {EMPTY_FORECAST}")
        else:
            raise SystemExit(f"missing {path} - run steps 1 and 2 first")
        print(f"  raw.{table:<16} {con.execute(f'select count(*) from raw.{table}').fetchall()[0][0]:>8,} rows")

    hf = STATE / "health.json"
    health = json.loads(hf.read_text()) if hf.exists() else {}
    cols = ["source", "last_attempt", "last_success", "consecutive_failures", "last_error", "detail"]
    hdf = pd.DataFrame([{"source": k, **{c: v.get(c) for c in cols[1:]}} for k, v in health.items()], columns=cols)
    hdf = hdf.astype({c: "string" for c in cols if c != "consecutive_failures"})
    con.register("hdf", hdf)
    con.execute("create or replace table raw.source_health as select * from hdf")
    con.close()


if __name__ == "__main__":
    main()
