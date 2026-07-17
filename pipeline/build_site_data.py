"""
Generate the browser-facing JSON the static site consumes:

  data/manifest.json     — list of available days + render hints (color clips)
  content/regions.json   — regions.yaml converted to JSON (profiles + centroids)
  content/events.json    — events.yaml converted to JSON

The frontend fetches only JSON (no YAML parser in the browser). regions.geojson
is already JSON and is consumed directly. Run after dailies/baselines exist.
"""
from __future__ import annotations

import os

import orjson
import yaml

from . import config as C, dailyio
from .paths import repo_path


def build_manifest() -> dict:
    days = sorted(dailyio.day_of(p) for p in dailyio.daily_paths())
    # Global render hints: a robust upper clip for the raw bad_ratio color scale.
    # (Anomaly z-scores are computed client-side from baselines.json.)
    return {
        "days": days,
        "n_days": len(days),
        "h3_resolution": C.H3_RESOLUTION,
        "nic_degraded_max": C.NIC_DEGRADED_MAX,
        "min_aircraft_floor": C.MIN_AIRCRAFT_FLOOR,
        "confidence_high_min": C.CONFIDENCE_HIGH_MIN,
        "bad_ratio_clip": 1.0,
        # z-scores clamped to +/-4 for the color scale: real per-day p99 anomaly
        # z sits near ~2.5, so a 4-sigma clip spends the ramp where the data is
        # (6 wasted the top half and made the anomaly view read as near-empty).
        "anomaly_clip": 4.0,
        "attribution": "adsb.lol (ODbL 1.0)",
    }


def build_trend() -> dict:
    """Per-day aggregate counts for the site's always-visible trend strip.

    One point per UTC day: measured cells (>= aircraft floor), degraded cells
    (bad_ratio > 0 among measured), and STRONG cells (bad_ratio >= the strong
    threshold — a clear bloom). The strip plots the strong count so a reader can
    see the arc of interference over the whole archive, honestly scoped to the
    days that actually exist. Cheap to recompute nightly (reads each daily once).
    """
    series = []
    for path in dailyio.daily_paths():
        day = dailyio.day_of(path)
        measured = degraded = strong = 0
        for rec in dailyio.read_daily(path):
            if rec.get("n_aircraft", 0) < C.MIN_AIRCRAFT_FLOOR:
                continue
            measured += 1
            br = rec.get("bad_ratio", 0) or 0
            if br > 0:
                degraded += 1
            if br >= C.TREND_STRONG_RATIO:
                strong += 1
        series.append({"date": day, "measured": measured,
                       "degraded": degraded, "strong": strong})
    return {"strong_ratio": C.TREND_STRONG_RATIO, "series": series}


def _yaml_to_json(yaml_rel: str, key: str, json_rel: str) -> int:
    src = repo_path("content", yaml_rel)
    if not os.path.exists(src):
        return 0
    with open(src, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    items = data.get(key, data) if isinstance(data, dict) else data
    payload = {"draft": bool(isinstance(data, dict) and data.get("draft")), key: items}
    with open(repo_path("content", json_rel), "wb") as fh:
        fh.write(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
    return len(items) if items else 0


def build_all() -> dict:
    os.makedirs(repo_path("data"), exist_ok=True)
    manifest = build_manifest()
    with open(repo_path("data", "manifest.json"), "wb") as fh:
        fh.write(orjson.dumps(manifest, option=orjson.OPT_INDENT_2))
    trend = build_trend()
    with open(repo_path("data", "trend.json"), "wb") as fh:
        fh.write(orjson.dumps(trend, option=orjson.OPT_INDENT_2))
    n_regions = _yaml_to_json("regions.yaml", "regions", "regions.json")
    n_events = _yaml_to_json("events.yaml", "events", "events.json")
    n_zones = _yaml_to_json("airspace.yaml", "zones", "airspace.json")
    return {"days": manifest["n_days"], "regions": n_regions,
            "events": n_events, "airspace": n_zones,
            "trend_days": len(trend["series"])}


if __name__ == "__main__":
    print(build_all())
