# USVI Hurricane Exposure

Portfolio project 05 · [Crucian Data Works](https://cruciandataworks.com) · Roger Simon

Which hurricanes and tropical storms have passed the U.S. Virgin Islands since 1851, which estates did their winds reach, and how many of today's residents live there? This pipeline measures every Atlantic storm track against all 416 Census estates. It watches the National Hurricane Center's live forecasts every 3 hours and opens a GitHub alert when a storm is forecast to pass close.

Live dashboard: [cruciandataworks.com/projects/hurricane-exposure](https://cruciandataworks.com/projects/hurricane-exposure/)

## What it does

1. **HURDAT2.** It reads NOAA's [HURDAT2 folder](https://www.nhc.noaa.gov/data/hurdat/) and downloads the newest Atlantic best-track file (now `hurdat2-1851-2025-092326.txt`). That file holds 1,988 storms and 55,524 track points. The file format is described in [NHC's format notes](https://www.nhc.noaa.gov/data/hurdat/hurdat2-format-atl-1851-2021.pdf).
2. **Census.** It downloads the [2020 Census of the U.S. Virgin Islands](https://www.census.gov/data/tables/2020/dec/2020-us-virgin-islands.html) population and housing-unit tables by estate, plus the TIGER/Line 2023 estate boundaries. All 416 estates join, and their counts add up exactly to the published totals: 87,146 people and 57,257 housing units.
3. **Active storms.** It reads NHC's `CurrentStorms.json` and, for each Atlantic storm, the 5-day forecast-track shapefile from [NHC GIS](https://www.nhc.noaa.gov/gis/). Every advisory is kept.
4. **Load.** It loads the Parquet lake into DuckDB.
5. **Model and test.** dbt fills each track in hour by hour and measures it against every estate. From 2004 it also places each estate in the storm's NE/SE/SW/NW quadrant and compares the distance with the 34-, 50- and 64-knot wind radii. 1 seed, 16 models and 36 data tests run every time. All pass, except one deliberate warning: a single 2004 track point where NHC's own wind radii are out of order.
6. **Export.** It writes two JSON files for the static dashboard.
7. **Alert.** It opens a GitHub issue when a forecast brings a storm's centre within 150 nautical miles, when a collector fails 3 runs in a row, or when NHC publishes a new HURDAT2 release. It closes the issue when the condition clears.

## Results (first build, 20 November 2026)

"Near" means the storm's centre came within 60 nautical miles of an estate. Strength is the storm's maximum sustained wind at its closest approach.

| Measure | Result |
|---|---|
| Storms of tropical-storm strength or more passing near, 1851–2025 | 83 |
| Hurricanes passing near | 39, about one every 4.5 years; 21% of years had one |
| Major hurricanes (Category 3+) passing near | 16, about one every 10.9 years |
| Since 1950 | 14 hurricanes, about one every 5.4 years |
| Residents inside hurricane-force winds, Maria 2017 | 86,989 of 87,146 (99.8%) |
| Irma 2017 / Dorian 2019 | 46,142 / 43,954 residents in hurricane-force winds |
| Storms since 2004 whose 34-knot winds reached homes | 21 |
| Busiest decade | the 2010s: 9 storms, 3 of them major hurricanes |

Known storms are checked by a test. Hugo's centre passed 0.1 nmi from Negro Bay, St. Croix, at 120 knots (1989). Marilyn passed 1.9 nmi from St. Thomas at 93 knots (1995). Irma passed 13.6 nmi from St. John at 152 knots, and Maria passed 11.7 nmi from St. Croix at 143 knots (2017).

The test of a saved NHC advisory, 11 AM AST on 12 August 2024, for the storm that became Ernesto, raises a "direct" alert. That forecast put the centre within 8 nmi of St. Croix 35 hours ahead.

## Read with care

- Counts before aircraft reconnaissance (1944) and satellites (1960s) are a minimum.
- Wind radii exist only from 2004. Older storms are measured by distance only.
- "Strength" is the storm's peak sustained wind near its centre, not the wind at a given estate.
- 2020 population is applied to every storm, as a measure of exposure today.
- Rain, flooding and storm surge are not in this data.

## Run it yourself

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python tests/test_pipeline.py       # parser checks, no network
python run_pipeline.py              # about 30 seconds the first time (10 MB download)
python -m http.server 8805 -d dashboard
```

The full beginner walkthrough is in [docs/STEP_BY_STEP.md](docs/STEP_BY_STEP.md).

## Layout

```
pipeline/   step1_hurdat.py  step2_census.py  step3_active.py  step4_load.py  step5_export.py  step6_alerts.py  common.py
dbt/        staging -> intermediate -> marts, macros (distance, bearing, forecast threats), tests
dashboard/  index.html  app.js  hurricane.css  styles.css  data/summary.json  data/estates.geojson
tests/      test_pipeline.py, fixtures/al052024_5day_004.zip (a real NHC advisory)
.github/workflows/refresh.yml   every 3 hours
```

## Credits

The storm tracks and forecasts come from the NOAA National Hurricane Center. Population, housing and estate boundaries come from the U.S. Census Bureau. Map tiles are from OpenStreetMap contributors. This is an independent analysis, not a forecast. For watches and warnings, follow the [National Hurricane Center](https://www.nhc.noaa.gov/) and [VITEMA](https://vitema.vi.gov/).
