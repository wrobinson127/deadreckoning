"""Aggregation math: majority-degraded aircraft rule, bad_ratio, confidence, floor."""
from __future__ import annotations

import h3

from pipeline import config as C
from pipeline.aggregate import aggregate_points
from pipeline.parse import Point


def _pt(icao, lat, lon, nic):
    return Point(icao=icao, lat=lat, lon=lon, nic=nic, rc=None, version=2, t=0.0)


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
