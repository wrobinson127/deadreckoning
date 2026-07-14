"""Aggregation math: majority-degraded aircraft rule, bad_ratio, confidence, floor."""
from __future__ import annotations

import h3

from pipeline import config as C
from pipeline.aggregate import aggregate_points
from pipeline.parse import Point


def _pt(icao, lat, lon, nic):
    return Point(icao=icao, lat=lat, lon=lon, nic=nic, rc=None, version=2, t=0.0)


def _ptc(icao, lat, lon, nic, cs, t):
    return Point(icao=icao, lat=lat, lon=lon, nic=nic, rc=None, version=2, t=t, callsign=cs)


def test_majority_rule_ratio_and_confidence():
    # One hex, 6 aircraft: 4 majority-degraded, 2 clean -> bad_ratio 4/6.
    lat, lon = 55.0, 21.0
    cell = h3.latlng_to_cell(lat, lon, C.H3_RESOLUTION)
    pts = []
    # 4 "bad" aircraft: majority of their reports degraded (nic 3 <= 6)
    for i in range(4):
        pts += [_pt(f"bad{i}", lat, lon, 3), _pt(f"bad{i}", lat, lon, 3),
                _pt(f"bad{i}", lat, lon, 8)]  # 2 degraded / 3 -> majority bad
    # 2 "clean" aircraft
    for i in range(2):
        pts += [_pt(f"ok{i}", lat, lon, 8), _pt(f"ok{i}", lat, lon, 9)]

    recs = {r["hex"]: r for r in aggregate_points(pts)}
    assert cell in recs
    r = recs[cell]
    assert r["n_aircraft"] == 6
    assert r["bad_aircraft"] == 4
    assert r["bad_ratio"] == round(4 / 6, 4)
    assert r["n_reports"] == 4 * 3 + 2 * 2
    assert r["confidence"] == "medium"  # 6 aircraft -> 5..9


def test_exactly_half_degraded_is_not_bad():
    # majority is strictly > 0.5; a 1/2 split must NOT count as bad.
    lat, lon = 40.0, -100.0
    pts = [_pt("x", lat, lon, 3), _pt("x", lat, lon, 8)]  # 1 of 2 degraded
    r = aggregate_points(pts)[0]
    assert r["bad_aircraft"] == 0
    assert r["bad_ratio"] == 0.0


def test_confidence_tiers_and_floor():
    assert C.confidence_tier(10) == "high"
    assert C.confidence_tier(9) == "medium"
    assert C.confidence_tier(C.MIN_AIRCRAFT_FLOOR) == "medium"
    assert C.confidence_tier(C.MIN_AIRCRAFT_FLOOR - 1) == "insufficient"
    assert C.confidence_tier(1) == "insufficient"


def test_low_sample_hex_is_insufficient():
    lat, lon = 0.0, 0.0
    pts = [_pt(f"a{i}", lat, lon, 3) for i in range(3)]  # 3 unique aircraft
    r = aggregate_points(pts)[0]
    assert r["n_aircraft"] == 3
    assert r["confidence"] == "insufficient"


def test_flights_attached_to_degraded_hex():
    # 6 aircraft, 5 majority-degraded (ratio 5/6 >= FLIGHTS_MIN_BAD_RATIO) -> flights.
    lat, lon = 55.0, 21.0
    pts = []
    for i in range(5):
        # i+1 degraded reports so nd differs -> deterministic sort by nd desc
        for k in range(i + 1):
            pts.append(_ptc(f"bad{i}", lat, lon, 3, f"CS{i}", 1000 + k))
        pts.append(_ptc(f"bad{i}", lat, lon, 8, f"CS{i}", 2000))  # one clean report
    pts += [_ptc("ok0", lat, lon, 9, "OK0", 500)]  # 1 clean aircraft
    r = aggregate_points(pts)[0]
    assert r["bad_ratio"] >= C.FLIGHTS_MIN_BAD_RATIO
    assert "flights" in r
    fl = r["flights"]
    # bad0 is exactly 1/2 degraded (not a majority) so it is NOT bad -> 4 flights.
    assert len(fl) == 4 <= C.FLIGHTS_TOP_N
    # sorted by n_degraded descending; bad4 has the most degraded reports
    assert [f["nd"] for f in fl] == sorted((f["nd"] for f in fl), reverse=True)
    top = fl[0]
    assert top["ic"] == "bad4" and top["cs"] == "CS4" and top["nd"] == 5
    assert top["t0"] == 1000 and top["t1"] == 1004  # degraded window only
    assert set(fl[0]) == {"ic", "cs", "t0", "t1", "nd"}


def test_no_flights_below_ratio_or_floor():
    # Below floor: insufficient hex, never gets flights.
    lat, lon = 10.0, 10.0
    pts = [_ptc(f"a{i}", lat, lon, 3, f"C{i}", 1) for i in range(3)]
    assert "flights" not in aggregate_points(pts)[0]

    # Meets floor but bad_ratio below FLIGHTS_MIN_BAD_RATIO -> no flights.
    lat, lon = 20.0, 20.0
    pts = [_ptc("b0", lat, lon, 3, "C0", 1)]  # 1 bad
    pts += [_ptc(f"ok{i}", lat, lon, 9, f"K{i}", 1) for i in range(9)]  # 9 clean
    r = aggregate_points(pts)[0]
    assert r["bad_ratio"] < C.FLIGHTS_MIN_BAD_RATIO
    assert "flights" not in r
