"""Empty-day handling is uniform across entrypoints.

A day that aggregates to ZERO hexes is a bad/placeholder release, not a real
"covered, no interference" day. process_day must NOT write it (so we never blur
the no-data vs no-interference line), and run_daily.main must report it as
not-ready (exit 3) so the nightly Action retries instead of recording a fake day.
"""
from __future__ import annotations

import pipeline.run_daily as rd


def _stub_pipeline(monkeypatch, records):
    monkeypatch.setattr(rd.download, "download_day", lambda day, scratch: ["part"])
    monkeypatch.setattr(rd.download, "cleanup", lambda parts: None)
    monkeypatch.setattr(rd.parse, "stream_points", lambda parts: iter(()))
    monkeypatch.setattr(rd.aggregate, "aggregate_points", lambda pts: records)


def test_process_day_zero_hexes_is_not_written(tmp_path, monkeypatch):
    _stub_pipeline(monkeypatch, records=[])
    wrote = {"called": False}
    monkeypatch.setattr(rd.dailyio, "write_daily",
                        lambda day, records: wrote.__setitem__("called", True))
    s = rd.process_day("2026-07-01", str(tmp_path))
    assert s["written"] is False and s["hexes"] == 0
    assert wrote["called"] is False   # nothing committed for a placeholder release


def test_process_day_nonempty_is_written(tmp_path, monkeypatch):
    recs = [{"hex": "8428309ffffffff", "n_aircraft": 9, "confidence": "high", "bad_ratio": 0.1}]
    _stub_pipeline(monkeypatch, records=recs)
    seen = {}
    monkeypatch.setattr(rd.dailyio, "write_daily",
                        lambda day, records: seen.setdefault("out", "path") or "path")
    monkeypatch.setattr(rd.os.path, "getsize", lambda p: 123)
    s = rd.process_day("2026-07-01", str(tmp_path))
    assert s["written"] is True and s["hexes"] == 1 and s["hexes_high_conf"] == 1


def test_main_returns_3_on_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "process_day",
                        lambda *a, **k: {"day": "2026-07-01", "hexes": 0, "written": False})
    assert rd.main(["2026-07-01", "--scratch", str(tmp_path)]) == 3


def test_main_returns_0_on_written(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "process_day",
                        lambda *a, **k: {"day": "2026-07-01", "hexes": 3,
                                         "hexes_high_conf": 2, "output": "data/daily/x",
                                         "bytes": 9, "written": True})
    assert rd.main(["2026-07-01", "--scratch", str(tmp_path)]) == 0
