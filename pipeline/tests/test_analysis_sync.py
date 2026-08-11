"""The methodology page's day count must match the map's.

site/assets/analysis/stats.json is derived from data/ but lives under site/, so
nothing in the data pipeline touches it. For four consecutive days the nightly
job committed a new daily and deployed while stats.json stayed put, and the live
site showed 1258 days on the map and 1254 on the methodology page. Nothing
failed; the numbers just quietly disagreed.

For an instrument whose whole claim is that it does not misrepresent what it
knows, two different answers to "how many days do you have" is the wrong kind of
wrong. nightly.yml now rebuilds the assets every run; this is the guard that
fails loudly if that ever stops happening.
"""
from __future__ import annotations

import json
import os

import pytest

from pipeline.paths import repo_path

_MANIFEST = repo_path("data", "manifest.json")
_STATS = repo_path("site", "assets", "analysis", "stats.json")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(_MANIFEST) and os.path.exists(_STATS)),
    reason="needs both committed manifest and committed analysis stats",
)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _manifest_days():
    return _load(_MANIFEST).get("days", [])


def test_stats_day_count_matches_manifest():
    days = _manifest_days()
    archive = _load(_STATS)["archive"]
    assert archive["n_days"] == len(days), (
        f"stats.json reports {archive['n_days']} days but manifest has "
        f"{len(days)}. The methodology page and the map will show different "
        f"numbers. Run: PYTHONPATH=. python -m analysis.analyze"
    )


def test_stats_span_matches_manifest():
    """A matching count is not enough; the endpoints must line up too."""
    days = _manifest_days()
    archive = _load(_STATS)["archive"]
    assert archive["start"] == days[0], (
        f"stats.json starts {archive['start']}, manifest starts {days[0]}"
    )
    assert archive["end"] == days[-1], (
        f"stats.json ends {archive['end']}, manifest ends {days[-1]}"
    )
