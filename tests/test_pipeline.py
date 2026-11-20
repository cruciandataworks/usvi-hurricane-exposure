"""Small checks of the parsers that need no network. Run: python tests/test_pipeline.py"""
import sys

import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from step1_hurdat import parse, release_key  # noqa: E402
from step3_active import issued_utc, read_forecast_zip, valid_utc  # noqa: E402

SAMPLE = """AL112017,               IRMA,      2,
20170906, 0545, L, HU, 18.2N,  63.1W, 155,  914,  160,  110,   80,  130,   80,   60,   50,   60,   50,   45,   30,   45,   -999
20170906, 1200,  , HU, 18.3N,  64.7W, 155,  914,  160,  120,   80,  130,   80,   60,   50,   60,   50,   45,   30,   45,   -999
"""


def test_hurdat_parse():
    storms, points = parse(SAMPLE)
    assert storms.iloc[0].to_dict()["name"] == "IRMA" and storms.iloc[0].n_points == 2
    p = points.iloc[1]
    assert (p.lat, p.lon, p.wind_kt, p.pressure_mb) == (18.3, -64.7, 155, 914)
    assert p.r34_ne == 160 and p.r64_nw == 45 and pd.isna(p.rmw_nmi)
    assert points.iloc[0].record_id == "L" and pd.isna(points.iloc[1].record_id)


def test_release_order():
    # newest seasons first, then release date; two date styles exist (MMDDYY and MMDDYYYY)
    assert release_key("2025", "092326") > release_key("2025", "02272026")
    assert release_key("2025", "02272026") > release_key("2024", "040425")


def test_advisory_times():
    t = issued_utc("1100 AM AST Mon Aug 12 2024")
    assert t == datetime(2024, 8, 12, 15, 0, tzinfo=timezone.utc)
    assert valid_utc("13/0000", t) == datetime(2024, 8, 13, 0, 0, tzinfo=timezone.utc)
    end = issued_utc("1100 PM AST Sat Aug 31 2024")
    assert valid_utc("02/1200", end) == datetime(2024, 9, 2, 12, 0, tzinfo=timezone.utc)


def test_fixture_zip():
    df = read_forecast_zip((ROOT / "tests/fixtures/al052024_5day_004.zip").read_bytes(), "AL052024")
    assert len(df) == 9 and df.tau_h.max() == 120 and df.storm_id.iloc[0] == "al052024"
    row = df[df.tau_h == 36].iloc[0]
    assert (row.lat, row.lon) == (17.3, -64.6)  # from the point itself, not the rounded columns


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok  {name}")
