"""
Compute per-hex baselines from the committed daily aggregates.

For each hex we take up to the most recent BASELINE_WINDOW_DAYS days on which the
hex met the minimum-aircraft floor (days below the floor are noise and excluded),
and record the mean/std of ``bad_ratio`` plus the day count. The frontend derives
an anomaly z-score client-side as (bad_ratio - mean) / max(std, STD_FLOOR); this
keeps daily files pure aggregates and lets the raw/anomaly toggle be a formula,
not a second data copy.

Causality note: the baseline uses the window of available days around each date
(not strictly trailing), which is appropriate for a retrospective archive. This
is documented in docs/METHODOLOGY.md.

Output: data/baselines.json
    {
      "generated_from_days": N, "window_days": 28, "min_days": 7,
      "std_floor": 0.02,
      "hexes": { "<h3>": {"mean": .., "std": .., "n": ..} }   # n >= min_days only
    }
"""
from __future__ import annotations

import math

import orjson

from . import config as C, dailyio
from .paths import atomic_write_bytes, repo_path


def compute_baselines(dailies: "list[tuple[str, list[dict]]] | None" = None) -> dict:
    if dailies is None:
        dailies = dailyio.load_dailies()
    # hex -> list of (day, bad_ratio) for days meeting the floor
    series: dict[str, list[tuple[str, float]]] = {}
    for day, records in dailies:
        for r in records:
            if r["n_aircraft"] < C.MIN_AIRCRAFT_FLOOR:
                continue
            series.setdefault(r["hex"], []).append((day, r["bad_ratio"]))

    hexes: dict[str, dict] = {}
    for h, pairs in series.items():
        pairs.sort()                      # by day
        window = pairs[-C.BASELINE_WINDOW_DAYS:]
        n = len(window)
        if n < C.BASELINE_MIN_DAYS:
            continue
        vals = [v for _d, v in window]
        mean = sum(vals) / n
        var = sum((v - mean) ** 2 for v in vals) / n
        hexes[h] = {"mean": round(mean, 4), "std": round(math.sqrt(var), 4), "n": n}

    return {
        "generated_from_days": len(dailies),
        "window_days": C.BASELINE_WINDOW_DAYS,
        "min_days": C.BASELINE_MIN_DAYS,
        "std_floor": C.BASELINE_STD_FLOOR,
        "hexes": hexes,
    }


def write_baselines() -> str:
    data = compute_baselines()
    out = repo_path(C.BASELINES_JSON)
    atomic_write_bytes(out, orjson.dumps(data, option=orjson.OPT_INDENT_2))
    return out


if __name__ == "__main__":
    p = write_baselines()
    print(f"wrote {p}")
