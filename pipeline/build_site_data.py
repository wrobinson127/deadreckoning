"""
Generate the browser-facing JSON the static site consumes:

  data/manifest.json     — list of available days + render hints (color clips)
  content/regions.json   — regions.yaml converted to JSON (profiles + centroids)
  content/events.json    — events.yaml converted to JSON

The frontend fetches only JSON (no YAML parser in the browser). regions.geojson
is already JSON and is consumed directly. Run after dailies/baselines exist.
"""
from __future__ import annotations

import glob
import os

import orjson
import yaml

from . import config as C
from .paths import repo_path


def build_manifest() -> dict:
    days = sorted(
        os.path.basename(p).removesuffix(".json")
        for p in glob.glob(repo_path("data", "daily", "*.json"))
    )
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
        "anomaly_clip": 6.0,      # z-scores clamped to +/-6 for the color scale
        "attribution": "adsb.lol (ODbL 1.0)",
    }


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
    n_regions = _yaml_to_json("regions.yaml", "regions", "regions.json")
    n_events = _yaml_to_json("events.yaml", "events", "events.json")
    return {"days": manifest["n_days"], "regions": n_regions, "events": n_events}


if __name__ == "__main__":
    print(build_all())
