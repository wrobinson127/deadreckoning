"""Daily storage format: gzip round-trip, deterministic bytes, path helpers.

Guards the size gate (Flag #6): dailies must be real gzip (so the archive stays
small) and byte-deterministic (so re-running the pipeline doesn't churn git or
defeat the "did the data actually change?" review check).
"""
from __future__ import annotations

from pipeline import dailyio

_RECS = [
    {"hex": "8428309ffffffff", "n_aircraft": 12, "n_reports": 40,
     "bad_aircraft": 7, "bad_ratio": 0.5833, "confidence": "high"},
    {"hex": "8409201ffffffff", "n_aircraft": 5, "n_reports": 11,
     "bad_aircraft": 0, "bad_ratio": 0.0, "confidence": "medium"},
]


def test_roundtrip_and_gzip_magic(tmp_path, monkeypatch):
    target = tmp_path / "2026-06-30.json.gz"
    monkeypatch.setattr(dailyio, "daily_path", lambda day: str(target))

    out = dailyio.write_daily("2026-06-30", _RECS)
    with open(out, "rb") as fh:
        assert fh.read(2) == b"\x1f\x8b"          # real gzip stream, not plain json
    assert dailyio.read_daily(out) == _RECS        # exact round-trip


def test_write_is_deterministic(tmp_path, monkeypatch):
    target = tmp_path / "2026-06-30.json.gz"
    monkeypatch.setattr(dailyio, "daily_path", lambda day: str(target))

    dailyio.write_daily("2026-06-30", _RECS)
    first = target.read_bytes()
    dailyio.write_daily("2026-06-30", _RECS)
    second = target.read_bytes()
    assert first == second                         # no embedded mtime/filename drift


def test_path_helpers_roundtrip():
    p = dailyio.daily_path("2026-07-13")
    assert p.endswith("2026-07-13.json.gz")
    assert dailyio.day_of(p) == "2026-07-13"
