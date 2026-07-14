"""Region assignment: ray-cast point-in-polygon, Polygon & MultiPolygon rings."""
from __future__ import annotations

from pipeline import regions


def _square(lon0, lat0, lon1, lat1):
    return [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]


def test_point_in_ring_basic():
    ring = _square(20.0, 54.0, 24.0, 57.0)  # Baltic-ish box
    assert regions._point_in_ring(22.0, 55.5, ring) is True
    assert regions._point_in_ring(10.0, 55.5, ring) is False   # west, outside
    assert regions._point_in_ring(22.0, 60.0, ring) is False   # north, outside


def test_region_of_first_match_and_none():
    regs = [
        {"id": "a", "rings": [_square(20.0, 54.0, 24.0, 57.0)]},
        {"id": "b", "rings": [_square(30.0, 40.0, 40.0, 47.0)]},
    ]
    assert regions._region_of(55.5, 22.0, regs) == "a"
    assert regions._region_of(43.0, 35.0, regs) == "b"
    assert regions._region_of(0.0, 0.0, regs) is None


def test_rings_of_polygon_and_multipolygon():
    poly = {"type": "Polygon", "coordinates": [_square(0, 0, 1, 1)]}
    multi = {"type": "MultiPolygon",
             "coordinates": [[_square(0, 0, 1, 1)], [_square(5, 5, 6, 6)]]}
    assert len(regions._rings_of(poly)) == 1
    assert len(regions._rings_of(multi)) == 2
    assert regions._rings_of({"type": "Point", "coordinates": [0, 0]}) == []
