"""
Per-region daily time series from the committed daily aggregates.

Reads content/regions.geojson (analyst-defined watch polygons) and every
data/daily/*.json.gz, assigns each active hex to the first region whose polygon
contains the hex centroid, and writes one time series per region to
data/regions/{id}.json for the region panel's trend sparkline.

Point-in-polygon is a plain ray-cast on hex centroids — with a few thousand
active hexes and ~10 regions this is trivially fast and dependency-free.
"""
from __future__ import annotations

import os

import h3
import orjson

from . import config as C, dailyio
from .paths import repo_path

REGIONS_GEOJSON = repo_path("content", "regions.geojson")


def _rings_of(geom: dict) -> list[list[list[float]]]:
    """Return a flat list of exterior rings ([[lon,lat],...]) for Polygon/MultiPolygon."""
    t = geom.get("type")
    if t == "Polygon":
        return [geom["coordinates"][0]]
    if t == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    return []


def load_regions() -> list[dict]:
    """[{id, display_name, rings:[[ [lon,lat],... ], ...]}] from the geojson."""
    if not os.path.exists(REGIONS_GEOJSON):
        return []
    with open(REGIONS_GEOJSON, "rb") as fh:
        gj = orjson.loads(fh.read())
    out = []
    for feat in gj.get("features", []):
        props = feat.get("properties", {})
        rid = props.get("id")
        if not rid:
            continue
        out.append({
            "id": rid,
            "display_name": props.get("display_name", rid),
            "rings": _rings_of(feat.get("geometry", {})),
        })
    return out


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and \
                (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi):
            inside = not inside
        j = i
    return inside


def _region_of(lat: float, lon: float, regions: list[dict]) -> "str | None":
    for reg in regions:
        for ring in reg["rings"]:
            if _point_in_ring(lon, lat, ring):
                return reg["id"]
    return None


def build_region_series() -> list[str]:
    regions = load_regions()
    if not regions:
        return []

    # Cache hex -> region assignment across all days.
    hex_region: dict[str, "str | None"] = {}

    def region_for(hexid: str) -> "str | None":
        if hexid not in hex_region:
            lat, lon = h3.cell_to_latlng(hexid)
            hex_region[hexid] = _region_of(lat, lon, regions)
        return hex_region[hexid]

    # region_id -> list of per-day metric dicts
    series: dict[str, list[dict]] = {r["id"]: [] for r in regions}

    for day, records in dailyio.load_dailies():
        # region_id -> accumulators
        acc: dict[str, dict] = {r["id"]: {"ratios": [], "aircraft": 0} for r in regions}
        for rec in records:
            if rec["n_aircraft"] < C.MIN_AIRCRAFT_FLOOR:
                continue
            rid = region_for(rec["hex"])
            if rid is None:
                continue
            acc[rid]["ratios"].append(rec["bad_ratio"])
            acc[rid]["aircraft"] += rec["n_aircraft"]
        for rid, a in acc.items():
            ratios = a["ratios"]
            series[rid].append({
                "date": day,
                "n_hexes": len(ratios),
                "mean_bad_ratio": round(sum(ratios) / len(ratios), 4) if ratios else None,
                "max_bad_ratio": round(max(ratios), 4) if ratios else None,
                "total_aircraft": a["aircraft"],
            })

    out_paths = []
    outdir = repo_path("data", "regions")
    os.makedirs(outdir, exist_ok=True)
    by_id = {r["id"]: r for r in regions}
    for rid, s in series.items():
        payload = {
            "id": rid,
            "display_name": by_id[rid]["display_name"],
            "series": s,
        }
        out = os.path.join(outdir, f"{rid}.json")
        with open(out, "wb") as fh:
            fh.write(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
        out_paths.append(out)
    return out_paths


if __name__ == "__main__":
    paths = build_region_series()
    print(f"wrote {len(paths)} region series")
