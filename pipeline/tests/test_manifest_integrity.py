"""Every manifest day must resolve to a present, decodable, well-formed artifact.

This is the permanent guard for the "timeline shows no data for day X" class of
bug: if the site lists a day in data/manifest.json, the browser will request
data/daily/<day>.json.gz and feed the records straight into the renderer. If any
listed day is missing, unreadable, or missing a field the renderer reads, the
scrubber shows "no data" for that day. Cheap build-time check; runs in CI against
the committed data, so a bad commit fails before it ever ships.
"""
from __future__ import annotations

import json
import os

import pytest

from pipeline import dailyio
from pipeline.paths import repo_path

# Fields the frontend's styleFor()/readout read for every record.
_REQUIRED = {"hex", "n_aircraft", "bad_ratio", "confidence"}
_MANIFEST = repo_path("data", "manifest.json")


def _manifest_days():
    if not os.path.exists(_MANIFEST):
        return []
    with open(_MANIFEST, encoding="utf-8") as fh:
        return json.load(fh).get("days", [])


@pytest.mark.skipif(not _manifest_days(), reason="no committed manifest/data")
@pytest.mark.parametrize("day", _manifest_days())
def test_manifest_day_resolves_to_wellformed_artifact(day):
    path = dailyio.daily_path(day)
    assert os.path.exists(path), f"manifest lists {day} but {path} is missing"

    records = dailyio.read_daily(path)  # raises if not valid gzip/JSON
    assert isinstance(records, list) and records, f"{day}: empty/invalid records"

    # Check the whole array, not just the head — a single malformed record mid-array
    # would throw in the renderer's per-record loop and blank the day.
    for i, r in enumerate(records):
        missing = _REQUIRED - r.keys()
        assert not missing, f"{day} record {i} missing {missing}"
        assert isinstance(r["bad_ratio"], (int, float)), f"{day} record {i} bad_ratio not numeric"


def test_manifest_matches_committed_dailies():
    """The manifest and the on-disk .gz set must be exactly the same day set."""
    listed = set(_manifest_days())
    on_disk = {dailyio.day_of(p) for p in dailyio.daily_paths()}
    if not listed and not on_disk:
        pytest.skip("no committed data")
    assert listed == on_disk, (
        f"manifest vs disk mismatch — only in manifest: {listed - on_disk}; "
        f"only on disk: {on_disk - listed}"
    )
