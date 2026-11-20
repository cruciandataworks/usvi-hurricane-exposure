"""Step 5 - Export: write the small files the dashboard reads.

The dashboard is a static web page with no database behind it. This step reads the
finished marts and writes:

    dashboard/data/summary.json    every number, table and chart series on the page
    dashboard/data/estates.geojson estate outlines with their exposure numbers (the map)
"""
import json
import math
from datetime import date, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "warehouse" / "hurricanes.duckdb"
OUT = ROOT / "dashboard" / "data"


def clean(v):
    if isinstance(v, datetime):
        return v.isoformat(timespec="minutes")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return int(v) if v.is_integer() else v
    if hasattr(v, "__int__") and type(v).__name__ in ("Decimal", "int128"):
        return int(v)
    return v


def rows(con, sql):
    rel = con.sql(sql)
    return [{k: clean(v) for k, v in zip(rel.columns, r)} for r in rel.fetchall()]


def one(con, sql):
    r = rows(con, sql)
    return r[0] if r else {}


def main():
    con = duckdb.connect(str(DB), read_only=True)
    meta = one(con, """
        select
            (select any_value(source_file) from staging.stg_storms)           as hurdat_file,
            (select min(season) from staging.stg_storms)                      as first_season,
            (select max(season) from staging.stg_storms)                      as last_season,
            (select count(*) from staging.stg_storms)                         as storms_total,
            (select count(*) from staging.stg_track_points)                   as track_points,
            (select count(*) from marts.mart_storms_near_usvi where is_near and is_ts_plus) as storms_near,
            (select count(*) from marts.mart_storms_near_usvi where is_near and is_hurricane) as hurricanes_near,
            (select count(*) from marts.mart_storms_near_usvi where is_near and is_major) as majors_near,
            (select count(*) from staging.stg_estates)                        as estates,
            (select sum(population) from staging.stg_estates)                 as population,
            (select sum(housing_units) from staging.stg_estates)              as housing_units,
            60 as near_nmi,
            cast(now() at time zone 'UTC' as timestamp)                       as built_utc
    """)
    returns = rows(con, "select * from marts.mart_return_periods order by first_season, level_order")
    decades = rows(con, "select * from marts.mart_decade_counts order by decade")
    storms = rows(con, """
        select storm_id, storm_label, season, closest_nmi, closest_date_ast, closest_island, closest_estate,
               stx_nmi, stt_nmi, stj_nmi, wind_at_closest_kt, category_at_closest, is_near, is_ts_plus,
               is_hurricane, is_major, peak_wind_kt, peak_category, min_pressure_mb, has_radii, max_field_kt,
               pop_in_34kt, housing_in_34kt, pop_in_50kt, pop_in_64kt, housing_in_64kt, estates_in_34kt,
               estates_in_64kt, max_hours_in_34kt
        from marts.mart_storms_near_usvi order by closest_utc desc""")
    storm_pop = rows(con, "select * from marts.mart_storm_population order by season desc, storm_id, island")
    # the real track points of every storm that passed near, within 500 nmi, for the map
    tracks = {}
    for r in con.sql("""
        select p.storm_id, round(p.lat, 2), round(p.lon, 2), p.wind_kt, strftime(p.time_utc, '%Y-%m-%d %H:%M')
        from staging.stg_track_points p join marts.mart_storms_near_usvi s using (storm_id)
        where (s.is_near or s.max_field_kt >= 34) and 2 * 3440.065 * asin(sqrt(pow(sin(radians(p.lat - 18.05) / 2), 2)
              + cos(radians(18.05)) * cos(radians(p.lat)) * pow(sin(radians(p.lon + 64.83) / 2), 2))) <= 500
        order by p.storm_id, p.time_utc, p.seq""").fetchall():
        tracks.setdefault(r[0], []).append([clean(r[1]), clean(r[2]), r[3], r[4]])
    # 2004 on: which estates each storm's 34/50/64-knot winds reached, for the map
    fields = {}
    for sid, kt, geoids in con.sql("""
        select storm_id, max_field_kt, list(geoid order by geoid) from intermediate.int_estate_storm
        where has_radii and max_field_kt >= 34 group by all order by all""").fetchall():
        fields.setdefault(sid, {})[str(kt)] = geoids
    active = rows(con, "select * from marts.mart_active_threats order by closest_nmi")
    active_tracks = rows(con, """
        select f.storm_id, f.tau_h, f.valid_utc, f.lat, f.lon, f.max_wind_kt
        from staging.stg_active_forecast f join marts.mart_active_threats t using (storm_id, advisory)
        order by f.storm_id, f.tau_h""")
    replay = one(con, "select * from marts.mart_threat_replay")
    replay_track = rows(con, "select tau_h, valid_utc, lat, lon, max_wind_kt from reference.fixture_ernesto_forecast order by tau_h")
    alerts = rows(con, "select alert_key, category, severity, title, message, observed_at from marts.mart_alerts")
    health = rows(con, "select * from staging.stg_source_health order by source")
    estates = rows(con, "select * from marts.mart_estate_exposure order by island, estate_name")
    island_totals = rows(con, "select * from staging.stg_island_totals order by island")

    OUT.mkdir(parents=True, exist_ok=True)
    data = dict(meta=meta, returns=returns, decades=decades, storms=storms, storm_pop=storm_pop,
                tracks=tracks, fields=fields, active=active, active_tracks=active_tracks, replay=replay, replay_track=replay_track, alerts=alerts, health=health,
                estates=estates, island_totals=island_totals)
    (OUT / "summary.json").write_text(json.dumps(data, separators=(",", ":"), default=str))

    shapes = dict(con.sql("select geoid, rings_json from staging.stg_estates").fetchall())
    feats = []
    for e in estates:
        rings = json.loads(shapes[e["geoid"]])
        feats.append({"type": "Feature",
                      "properties": {"geoid": e["geoid"]},  # the numbers come from summary.json
                      # TIGER rings are listed one by one; holes are rare at this scale, so each
                      # ring is drawn as its own polygon
                      "geometry": {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}})
    (OUT / "estates.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                                    separators=(",", ":")))
    for f in ("summary.json", "estates.geojson"):
        print(f"  wrote dashboard/data/{f} ({(OUT / f).stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
