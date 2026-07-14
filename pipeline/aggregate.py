"""
Aggregate a day's airborne NIC points into per-H3-hex daily records.

Per hex per day we compute:
    n_aircraft   unique ICAO count
    n_reports    total NIC-bearing reports
    bad_aircraft aircraft whose in-hex reports are MAJORITY degraded (nic<=thr)
    bad_ratio    bad_aircraft / n_aircraft
    confidence   tier from n_aircraft ("high"/"medium"/"insufficient")

The aircraft (not the report) is the unit of "bad", so a single jet lingering in
a hex cannot dominate it. Hexes below MIN_AIRCRAFT_FLOOR keep their counts but
are tier "insufficient" and must never be rendered as a value by the frontend.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import h3

from . import config as C
from .parse import Point


def aggregate_points(points: Iterable[Point]) -> list[dict]:
    """Fold a stream of Points into a list of per-hex daily records."""
    # (cell, icao) -> [degraded_reports, total_reports]
    per_ac: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    # cell -> total reports
    reports_per_hex: dict[str, int] = defaultdict(int)

    for pt in points:
        cell = h3.latlng_to_cell(pt.lat, pt.lon, C.H3_RESOLUTION)
        slot = per_ac[(cell, pt.icao)]
        slot[1] += 1
        if pt.nic <= C.NIC_DEGRADED_MAX:
            slot[0] += 1
        reports_per_hex[cell] += 1

    # Fold aircraft-level tallies up to hex level.
    hex_aircraft: dict[str, int] = defaultdict(int)
    hex_bad: dict[str, int] = defaultdict(int)
    for (cell, _icao), (deg, tot) in per_ac.items():
        hex_aircraft[cell] += 1
        if deg > tot * C.BAD_AIRCRAFT_MAJORITY:
            hex_bad[cell] += 1

    records: list[dict] = []
    for cell, n_aircraft in hex_aircraft.items():
        bad = hex_bad.get(cell, 0)
        records.append({
            "hex": cell,
            "n_aircraft": n_aircraft,
            "n_reports": reports_per_hex[cell],
            "bad_aircraft": bad,
            "bad_ratio": round(bad / n_aircraft, 4) if n_aircraft else 0.0,
            "confidence": C.confidence_tier(n_aircraft),
        })
    # Deterministic order (stable diffs, reproducible files).
    records.sort(key=lambda r: r["hex"])
    return records
