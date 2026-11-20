"""Step 2 - Census: who lives where, estate by estate.

The 2020 Census of the U.S. Virgin Islands publishes population (table 2) and housing
units (table 4) for every estate, the historic land division people still use for
addresses. The Census TIGER/Line files give each estate's boundary and an internal point.

The tables have no ID codes, only names under an island heading, so the two are joined
in dbt by island + name. Nothing is matched by hand; dbt tests prove every estate joins.
These files do not change, so they are downloaded once and kept in lake/_download.
"""
import csv
import io
import json
import zipfile

import pandas as pd
import shapefile  # pyshp: a small pure-Python shapefile reader

from common import DOWNLOAD, LAKE, get, record_health, write_parquet

TABLES = ("https://www2.census.gov/programs-surveys/decennial/2020/data/island-areas/"
          "us-virgin-islands/population-and-housing-unit-counts/us-virgin-islands-phc-table{n}.csv")
TIGER = "https://www2.census.gov/geo/tiger/TIGER2023/ESTATE/tl_2023_78_estate.zip"
ISLAND_FP = {"010": "St. Croix", "020": "St. John", "030": "St. Thomas"}
OUT = LAKE / "census"


def fetch(url):
    f = DOWNLOAD / url.rsplit("/", 1)[1]
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(get(url).content)
    return f.read_bytes()


def read_table(n, value_name):
    """Rows under each island heading become (island, estate, value).
    Careful: some estates are islands too (Estate Water Island), so only the three
    main islands count as headings."""
    text = fetch(TABLES.format(n=n)).decode("utf-8-sig")
    rows, island = [], None
    for r in csv.reader(io.StringIO(text)):
        if not r or not r[0].strip() or len(r) < 2 or not r[1].strip():
            continue
        name, value = r[0].strip(), r[1].replace(",", "").strip()
        if not value.isdigit():
            continue
        if name in ("St. Croix Island", "St. John Island", "St. Thomas Island"):
            island = name[: -len(" Island")]
            rows.append({"island": island, "estate": None, value_name: int(value), "is_island_total": True})
        elif name == "United States Virgin Islands":
            rows.append({"island": None, "estate": None, value_name: int(value), "is_island_total": False})
        elif island:
            rows.append({"island": island, "estate": name, value_name: int(value), "is_island_total": False})
    return pd.DataFrame(rows)


def simplify(points, tol):
    """Douglas-Peucker: drop points that sit within `tol` degrees of a straight line.
    Keeps the map file small; exposure is measured from the Census internal point."""
    if len(points) < 4:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
    best, idx = 0, 0
    for i in range(1, len(points) - 1):
        x, y = points[i]
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm if (dx or dy) else ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [points[0], points[-1]]
    return simplify(points[: idx + 1], tol)[:-1] + simplify(points[idx:], tol)


def read_shapes():
    z = zipfile.ZipFile(io.BytesIO(fetch(TIGER)))
    names = {n.rsplit(".", 1)[1]: n for n in z.namelist() if n.count(".") == 1}
    r = shapefile.Reader(shp=io.BytesIO(z.read(names["shp"])), dbf=io.BytesIO(z.read(names["dbf"])),
                         shx=io.BytesIO(z.read(names["shx"])))
    rows = []
    for sr in r.iterShapeRecords():
        rec = sr.record.as_dict()
        shp = sr.shape
        parts = list(shp.parts) + [len(shp.points)]
        rings = []
        for a, b in zip(parts[:-1], parts[1:]):
            ring = simplify([tuple(p) for p in shp.points[a:b]], 0.00015)
            if len(ring) >= 4:
                rings.append([[round(x, 5), round(y, 5)] for x, y in ring])
        rows.append({
            "geoid": rec["GEOID"], "island": ISLAND_FP[rec["COUNTYFP"]], "estate": rec["NAMELSAD"],
            "lat": float(rec["INTPTLAT"]), "lon": float(rec["INTPTLON"]),
            "land_m2": int(rec["ALAND"]), "water_m2": int(rec["AWATER"]),
            # each ring is stored on its own; the export step builds the GeoJSON
            "rings_json": json.dumps(rings, separators=(",", ":")),
        })
    return pd.DataFrame(rows)


def main():
    try:
        pop = read_table("02", "population")
        hu = read_table("04", "housing_units")
        counts = pop.merge(hu, on=["island", "estate", "is_island_total"], how="outer")
        shapes = read_shapes()
        write_parquet(counts, OUT / "estate_counts.parquet")
        write_parquet(shapes, OUT / "estate_shapes.parquet")
        est = counts[counts.estate.notna()]
        print(f"  {len(est)} estates in the tables ({est.population.sum():,} people, "
              f"{est.housing_units.sum():,} housing units); {len(shapes)} estate shapes")
        record_health("census", True, len(shapes))
    except Exception as e:  # noqa: BLE001
        record_health("census", False, error=str(e))
        raise


if __name__ == "__main__":
    main()
