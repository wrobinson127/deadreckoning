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

Significant hexes (bad_ratio >= FLIGHTS_MIN_BAD_RATIO and meeting the aircraft
floor) also carry a ``flights`` list: up to FLIGHTS_TOP_N affected aircraft, each
``{ic, cs, t0, t1, nd}`` = ICAO, public callsign, first/last degraded-report unix
seconds, and #degraded reports. This bounds the added size to hexes that actually
render as interference; quiet and corridor hexes are unchanged.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import h3

from . import config as C
from .parse import Point


def aggregate_points(points: Iterable[Point]) -> list[dict]:
    """Fold a stream of Points into a list of per-hex daily records."""
    # (cell, icao) -> [degraded_reports, total_reports, t_first_deg, t_last_deg, callsign]
    def _slot():
        return [0, 0, None, None, None]
    per_ac: dict[tuple[str, str], list] = defaultdict(_slot)
    # cell -> total reports
    reports_per_hex: dict[str, int] = defaultdict(int)

    for pt in points:
        cell = h3.latlng_to_cell(pt.lat, pt.lon, C.H3_RESOLUTION)
        slot = per_ac[(cell, pt.icao)]
        slot[1] += 1
        if slot[4] is None and pt.callsign:
            slot[4] = pt.callsign
        if pt.nic <= C.NIC_DEGRADED_MAX:
            slot[0] += 1
            t = int(pt.t)
            if slot[2] is None or t < slot[2]:
                slot[2] = t
            if slot[3] is None or t > slot[3]:
                slot[3] = t
        reports_per_hex[cell] += 1

    # Fold aircraft-level tallies up to hex level.
    hex_aircraft: dict[str, int] = defaultdict(int)
    hex_bad: dict[str, int] = defaultdict(int)
    # cell -> list of (n_degraded, icao, callsign, t_first, t_last) for bad aircraft
    hex_bad_flights: dict[str, list] = defaultdict(list)
    for (cell, icao), (deg, tot, t0, t1, cs) in per_ac.items():
        hex_aircraft[cell] += 1
        if deg > tot * C.BAD_AIRCRAFT_MAJORITY:
            hex_bad[cell] += 1
            hex_bad_flights[cell].append((deg, icao, cs, t0, t1))

    records: list[dict] = []
    for cell, n_aircraft in hex_aircraft.items():
        bad = hex_bad.get(cell, 0)
        bad_ratio = round(bad / n_aircraft, 4) if n_aircraft else 0.0
        rec = {
            "hex": cell,
            "n_aircraft": n_aircraft,
            "n_reports": reports_per_hex[cell],
            "bad_aircraft": bad,
            "bad_ratio": bad_ratio,
            "confidence": C.confidence_tier(n_aircraft),
        }
        # Attach affected flights only to significant hexes (bounds size; leaves
        # quiet/corridor hexes unchanged).
        if (n_aircraft >= C.MIN_AIRCRAFT_FLOOR
                and bad_ratio >= C.FLIGHTS_MIN_BAD_RATIO
                and hex_bad_flights.get(cell)):
            # Highest-degraded first, then ICAO for a stable, reproducible order.
            top = sorted(hex_bad_flights[cell], key=lambda f: (-f[0], f[1]))[:C.FLIGHTS_TOP_N]
            rec["flights"] = [
                {"ic": ic, "cs": cs, "t0": t0, "t1": t1, "nd": nd}
                for (nd, ic, cs, t0, t1) in top
            ]
        records.append(rec)
    # Deterministic order (stable diffs, reproducible files).
    records.sort(key=lambda r: r["hex"])
    return records
