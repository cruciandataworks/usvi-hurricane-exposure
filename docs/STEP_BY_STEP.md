# USVI Hurricane Exposure: Step-by-Step Guide

Portfolio project 05 · Crucian Data Works · Roger Simon

This guide walks through the project in the order it was built. Each step covers the goal, why it is done that way, the command to run and what you should see. Work through it top to bottom and you will be able to rebuild the project yourself and explain every decision to a client.

Sources:
- NOAA National Hurricane Center [HURDAT2 files](https://www.nhc.noaa.gov/data/hurdat/) and [format notes](https://www.nhc.noaa.gov/data/hurdat/hurdat2-format-atl-1851-2021.pdf).
- NHC [CurrentStorms.json](https://www.nhc.noaa.gov/CurrentStorms.json) and [GIS forecast tracks](https://www.nhc.noaa.gov/gis/).
- U.S. Census Bureau [2020 Census of the U.S. Virgin Islands](https://www.census.gov/data/tables/2020/dec/2020-us-virgin-islands.html), tables 2 and 4.
- Census [TIGER/Line 2023 estates](https://www2.census.gov/geo/tiger/TIGER2023/ESTATE/).

This project is an independent analysis, not a forecast.

---

## The big picture

Everyone in the territory knows the names: Hugo, Marilyn, Irma, Maria. But "how often", "how close" and "who was in the wind" are questions most people answer from memory. The data to answer them properly is public, in two places that were never joined:

- **NOAA's HURDAT2** records the centre, strength and (since 2004) the size of every Atlantic storm, every 6 hours, since 1851.
- **The 2020 Census** counts people and homes in each of the 416 estates, the old land divisions still used in addresses.

This project joins them. It measures every storm hour against every estate, then keeps watching the live NHC forecasts.

```
NHC HURDAT2 (yearly) ─────► 1 hurdat ─┐
Census tables + TIGER ────► 2 census ─┼─► Parquet lake ─► 4 load DuckDB ─► 5 dbt models + tests
NHC active storms (live) ─► 3 active ─┘                                           │
                                            dashboard ◄─ 6 export JSON ◄──────────┤
                                        GitHub issues ◄─ 7 sync alerts ◄──────────┘
```

### Final results (first full build, 20 November 2026)

| Measure | Result |
|---|---|
| Atlantic storms / track points | 1,988 / 55,524 (1851–2025) |
| Estates joined to boundaries | 416 of 416; population 87,146 and housing 57,257, both exact |
| Storm hours filled in near the territory | 24,733 |
| Storms listed (centre within 150 nmi) | 215 |
| Storms passing near (within 60 nmi, 34 kt+) | 83: 39 hurricanes, 16 of them major |
| dbt | 1 seed, 16 models, 36 data tests; one deliberate warning |

What the data shows:

- **A hurricane passes near about every 4.5 years.** 21% of years since 1851 had at least one.
- **Maria 2017 put 99.8% of today's residents inside hurricane-force winds.** Irma, two weeks earlier, reached 46,142 people, and Dorian in 2019 reached 43,954.
- **St. Thomas took the most direct hits since 2004.** 130 estates, home to 43,954 people, were inside hurricane-force winds three times: Irma, Maria and Dorian.
- **The 2010s were the busiest decade on record**, with 9 storms passing near and 3 major hurricanes.

---

## Step 0: Set up your machine

You need Python 3.12 or newer.

```bash
cd 05-usvi-hurricane-exposure
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # requests, duckdb, pandas, pyshp, dbt-core, dbt-duckdb
```

`pyshp` is a small pure-Python reader for shapefiles, the map-file format the Census and NHC use. It needs nothing else installed, unlike the larger GIS libraries.

### Project layout

```
pipeline/
  common.py          shared helpers: lake paths, HTTP with retries, distance, upsert, health log
  step1_hurdat.py    newest HURDAT2 file -> lake/hurdat
  step2_census.py    Census tables + estate shapes -> lake/census
  step3_active.py    NHC active storms + forecast tracks -> lake/active
  step4_load.py      lake -> DuckDB "raw" schema
  step5_export.py    marts -> dashboard/data/*.json
  step6_alerts.py    open / update / close GitHub issues
dbt/
  macros/            geo.sql (distance, bearing, category), forecast_threats.sql
  models/staging     clean names and types
  models/intermediate  int_track_hourly, int_estate_storm
  models/marts       storms, decades, return periods, estates, population, threats, alerts
  seeds/             fixture_ernesto_forecast.csv (a real advisory, for a test)
  tests/             known storms, totals, interpolation, Ernesto fixture
tests/test_pipeline.py   parser checks (no network)
run_pipeline.py          runs steps 1 to 7
```

---

## Step 1: Download HURDAT2

**Goal:** get the newest copy of NOAA's best-track database.

NHC republishes the whole database once or twice a year as one text file. The name tells you what it covers: `hurdat2-1851-2025-092326.txt` means seasons 1851–2025, released 23 Sep 2026. Older names use an 8-digit date (`02272026`), so `release_key()` reads both styles and sorts by last season, then release date.

```bash
python pipeline/step1_hurdat.py
```

You should see:

```
  hurdat2-1851-2025-092326.txt: 1,988 storms, 55,524 track points (1851-2025)
```

Run it again and it says the file is already in the lake. The file name is saved in `lake/_state/hurdat.json`, so a 7 MB download only happens when NHC publishes something new.

### Key idea: reading a fixed format

Each storm starts with a header line, then one line per track point:

```
AL112017,               IRMA,     66,
20170906, 1200,  , HU, 18.3N,  64.7W, 155,  914,  160, 120, 80, 130, ...
```

The header says how many lines follow (66). The parser reads exactly that many, so a broken file fails loudly instead of silently mixing storms. A dbt test checks it again later. Each point has a date, a time, a record type (`L` = landfall), a status (`HU` hurricane, `TS` tropical storm ...), latitude, longitude, wind in knots and pressure. Then come 12 wind radii: how far 34-, 50- and 64-knot winds reached in each quadrant. `-999` means missing; before 2004 the radii are always missing.

West longitudes are stored as negative numbers (64.7W becomes -64.7), the convention every map library expects.

---

## Step 2: Census population and estate boundaries

**Goal:** know how many people and homes are in each estate, and where each estate is.

```bash
python pipeline/step2_census.py
```

```
  416 estates in the tables (87,146 people, 57,257 housing units); 416 estate shapes
```

Three files are used:

- `us-virgin-islands-phc-table02.csv`: population by estate.
- `us-virgin-islands-phc-table04.csv`: housing units by estate.
- `tl_2023_78_estate.zip`: the TIGER/Line estate boundaries, with an "internal point" inside each estate.

### Key idea: joining on names, carefully

The Census tables have no ID codes, only names listed under each island:

```
St. Croix Island,"41,004"
Estate Allandale,0
...
St. Thomas Island,"42,261"
Estate Water Island,84
```

The first version treated every row ending in "Island" as a new island heading, and 14 estates went missing. The cause was Estate Water Island, Estate Hassel Island and other estates that are islands themselves. The fix is to treat only the three main island names as headings. After that, every one of the 416 table rows matches one of the 416 boundaries on island plus name. dbt proves this on every run (Step 5).

The shapes are simplified with the Douglas-Peucker method: points within about 15 metres of a straight line are dropped. That keeps the map file around 200 KB. Distances are measured from each estate's Census internal point, not its outline.

---

## Step 3: Watch NHC's active storms

**Goal:** save NHC's official 5-day forecast for any Atlantic storm, every 3 hours.

```bash
python pipeline/step3_active.py
```

In November you will usually see:

```
  0 active storm(s) worldwide, 0 Atlantic; +0 forecast rows
```

That counts as a success with 0 rows. When a storm is active, the script downloads its forecast-track zip and reads `*_5day_pts.shp`: one point per forecast time (0, 12, 24 ... 120 hours), with expected position and wind.

To see what a real storm looks like, replay the saved advisory in `tests/fixtures`:

```bash
python pipeline/step3_active.py --fixture tests/fixtures/al052024_5day_004.zip --print
```

This is advisory 4 for "Potential Tropical Cyclone Five", issued at 11 AM AST on 12 August 2024. It became Hurricane Ernesto. Its 36-hour point is 17.3N 64.6W, just off St. Croix.

### Key idea: use the shape, not the label

The shapefile's `LAT` and `LON` columns are cut to whole degrees (17 and -64). The exact position is in the shape itself (`sr.shape.points`), so that is what the script reads. A test checks it.

### Key idea: times without a month

`VALIDTIME` looks like `13/0000`: day 13, 00:00 UTC, with no month or year. `valid_utc()` takes the month from the advisory time. If the day number is much smaller than the advisory's day, the forecast has run into the next month. A test covers 31 Aug to 2 Sep.

This step is allowed to fail. NHC's servers are busiest exactly when a storm is coming. A failure is written to `lake/_state/health.json`, and the rest of the pipeline still runs. Three failures in a row raise an alert.

---

## Step 4: Load into DuckDB

```bash
python pipeline/step4_load.py
```

```
  raw.hurdat_storms       1,988 rows
  raw.hurdat_points      55,524 rows
  raw.census_counts         420 rows
  raw.estate_shapes         416 rows
  raw.active_forecast         0 rows
```

Nothing is changed here. Keeping all logic in dbt means it is all tested. If no storm has ever been saved, an empty `active_forecast` table is created with the right columns, so dbt still builds.

---

## Step 5: Model and test with dbt

```bash
cd dbt
dbt build --profiles-dir .
cd ..
```

```
Done. PASS=52 WARN=1 ERROR=0 SKIP=0 TOTAL=53
```

### The layers

| Layer | Models | What they do |
|---|---|---|
| staging (views) | `stg_storms`, `stg_track_points`, `stg_estates`, `stg_island_totals`, `stg_active_forecast`, `stg_source_health` | names, types, labels; the Census join |
| intermediate (tables) | `int_track_hourly`, `int_estate_storm` | fill tracks hour by hour; measure every estate against every storm hour |
| marts (tables) | `mart_storms_near_usvi`, `mart_decade_counts`, `mart_return_periods`, `mart_estate_exposure`, `mart_storm_population`, `mart_active_threats`, `mart_threat_replay`, `mart_alerts` | what the dashboard and alerts read |

### Key idea 1: fill in the track

Track points are 6 hours apart. A storm moving at 15 knots covers 90 nautical miles in that time, enough to skip right past an island. `int_track_hourly` draws a straight line between each pair of points and adds a point every hour. Wind, pressure and the wind radii are blended the same way. A value 2 hours into a 6-hour leg is 2/6 of the way from one point to the next. Only hours within 400 nmi of the territory are kept: 24,733 rows.

A test (`assert_interpolation_in_bounds`) checks that no filled-in wind is outside the two real values around it.

### Key idea 2: distance and quadrant

Two macros in `macros/geo.sql` do the geometry:

- `nmi()`: the haversine great-circle distance in nautical miles, NHC's unit.
- `bearing()`: the compass direction from the storm's centre to the estate (0 = north, 90 = east).

NHC gives wind radii per quadrant because storms are lopsided: the right-hand side of a northern-hemisphere hurricane is usually stronger. An estate at bearing 200° from the centre is in the SW quadrant, so it is inside hurricane-force winds if its distance is less than `r64_sw`. `int_estate_storm` does this for 416 estates × 24,733 hours (about 10 million pairs) in a few seconds. It keeps the closest approach and the strongest wind field each estate was inside.

### Key idea 3: choose a definition and say it

"Passed near" means the centre came within 60 nautical miles of any estate. That is roughly the reach of hurricane-force winds in a typical hurricane. The number lives in `dbt_project.yml` (`near_nmi: 60`), so it can be changed in one place. "Strength" is the storm's maximum sustained wind at the hour of closest approach. The dashboard says both on the page.

### Key idea 4: return periods

`mart_return_periods` divides years by storms. 175 seasons and 39 hurricanes passing near gives one every 4.5 years. It also counts the years with at least one: 36 of 175, or 21%. They differ because some years had two (2017 had Irma and Maria). Three periods are shown, because the early record misses storms: since 1851, since 1950 (aircraft reconnaissance) and since 2004 (wind radii).

### Key idea 5: tests that encode what everyone knows

| Test | Checks |
|---|---|
| `assert_points_match_headers` | every storm has as many points as its header says |
| `assert_estates_add_up_to_islands` | estate population and housing add up exactly to the Census island and territory totals |
| `not_null` on `stg_estates.geoid` and `population` | every table row found a boundary, and every boundary a row |
| `assert_known_storms_pass_close` | Hugo 1989, Marilyn 1995, Irma 2017 and Maria 2017 are hurricanes within 60 nmi |
| `assert_interpolation_in_bounds` | filled-in hours stay between real values |
| `assert_wind_radii_valid` (warn) | 64-kt radius ≤ 50-kt ≤ 34-kt |
| `assert_ernesto_fixture_alerts` | the saved 2024 advisory produces a "direct" threat to St. Croix 24–48 hours ahead |

The radii test is set to warn, not fail, because one 2004 point in NOAA's own file breaks the rule. The data is reported as it is, not changed.

The known-storms test is the most useful kind for a client. If a change to the distance maths ever moved Hugo away from St. Croix, the build would stop before the dashboard changed.

### Key idea 6: one macro, two uses

`forecast_threats()` takes a table of forecast points and a time. It finds each storm's latest advisory and fills the forecast in hour by hour. Then it measures every hour against every estate and rates the result: `direct` (≤ 60 nmi), `watch` (≤ 150 nmi), `monitor` or `passed`. `mart_active_threats` runs it on live data. The Ernesto test and `mart_threat_replay` run the same code on the saved advisory. So the alert logic is tested even in November, when nothing is spinning.

---

## Step 6: Export for the dashboard

```bash
python pipeline/step5_export.py
```

```
  wrote dashboard/data/summary.json (478 KB)
  wrote dashboard/data/estates.geojson (208 KB)
```

`summary.json` holds every number, table and track on the page. `estates.geojson` holds only the outlines and each estate's ID. The page looks up the numbers by ID, so they are not stored twice. To preview:

```bash
python -m http.server 8805 -d dashboard     # then open http://localhost:8805
```

The page has an alert strip (active storms, or an "Example" replay of Ernesto), four headline figures and an estate map. The map can show history measures, or one storm's track with the estates its winds reached. It also has decade and return-period panels, a "who was in the wind" chart, storm and estate tables, caveats and credits.

---

## Step 7: Alert issues on GitHub

```bash
python pipeline/step6_alerts.py
```

Without a `GH_TOKEN` it only prints what it would do. In GitHub Actions it keeps one issue open per alert key (`storm:al052024`, `collector:nhc_active`, `release:hurdat2`), labelled `hurricane-alert` and assigned to you. GitHub emails you when it opens. The issue closes itself when the condition clears, so a storm that is a threat for three days sends one email, not 24.

The `release:hurdat2` notice is a reminder, not an error. When NHC publishes a new HURDAT2, the pipeline rebuilds on it automatically. The notice asks you to review the README figures and then update `hurdat_reviewed` in `dbt_project.yml`.

---

## Step 8: Run everything with one command

```bash
python tests/test_pipeline.py     # 4 parser checks, no network
python run_pipeline.py            # steps 1-7
python run_pipeline.py --from 4   # rebuild from the lake without downloading
```

Step 3 is "tolerant": if NHC is unreachable the run carries on. Any failure from step 4 on stops the run, so bad data never reaches the dashboard.

---

## Step 9: Schedule it every 3 hours

`.github/workflows/refresh.yml` runs at 41 minutes past every third hour (UTC). NHC issues advisories every 6 hours, and every 3 when watches are up. Each run:

1. Downloads the lake from a GitHub release called `lake` (one `lake.tar.gz`).
2. Runs the unit tests and the pipeline.
3. Uploads the lake again.
4. Once a day (the first automatic run of the day, or any manual run), commits the dashboard data. GitHub pauses schedules in repositories with no commits for 60 days.
5. Uploads the dashboard to Hostinger, if the FTP secrets exist.
6. On any failure, opens or updates a "refresh failed" issue.

**A backup for GitHub's scheduler.** GitHub can take a long time to start firing schedules in a new repository, and it sometimes drops runs. So every run that was not started by the schedule ends with a small second job, `next-run`. That job waits until 3 hours after the run began and then starts the next run itself (`chained=true`). It first checks whether any newer run has started in the meantime (a scheduled run, a manual run or another chain); if one has, it stops. That keeps only one chain going, and once the schedule fires, the chain ends on its own. The wait runs in its own job so it never blocks the refresh. It uses runner time, which is free in a public repository. Set the repository variable `CHAIN_RUNS` to `false` to turn the backup off.

### Setup checklist in GitHub

1. Settings → Secrets and variables → Actions → Secrets: `FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD`.
2. Variables: `FTP_SERVER_DIR` = `/public_html/projects/hurricane-exposure/`. Optionally set `ALERT_ASSIGNEE`.
3. Actions → Hurricane exposure refresh → Run workflow, to test.

---

## Talking about this project

- "I joined NOAA's storm record with the Census at estate level, which nobody publishes, and proved the join is complete: 416 of 416 estates, with totals that match exactly."
- "The distance maths is tested against storms everyone here remembers. If Hugo ever moved away from St. Croix, the build would stop."
- "The live alert is tested year-round by replaying a real 2024 advisory."
- "Definitions are in one config file and stated on the page, so a client can change '60 nautical miles' and see what moves."

For an insurer, a bank or the government, the same pipeline answers "how many of our customers, properties or facilities were inside each storm's winds", given their address list in place of Census estates.

## Publishing to cruciandataworks.com

The workflow uploads `dashboard/` to `/public_html/projects/hurricane-exposure/` on every run once the FTP secrets are set. The homepage card links to [cruciandataworks.com/projects/hurricane-exposure](https://cruciandataworks.com/projects/hurricane-exposure/).
