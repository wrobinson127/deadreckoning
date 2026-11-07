"""A night that lands nothing must not exit 0.

2026-11-01's nightly paused on low runner disk, ingested nothing, and backfill
returned 0, so the run went green and 2026-10-31 was silently missing. Pause now
exits EXIT_PAUSED; with --require-ingest a not-published / 0-hex day exits
EXIT_MISSING; and the nightly workflow actually passes those flags.
"""
from __future__ import annotations

from collections import namedtuple
from pathlib import Path

import pipeline.backfill as bf

_Usage = namedtuple("_Usage", "total used free")


def _stub(monkeypatch, tmp_path, free_gb=100.0, summary=None, present=()):
    """Stub disk, storage, processing, and derived steps; return the days processed."""
    seen = []
    monkeypatch.setattr(bf.shutil, "disk_usage",
                        lambda p: _Usage(0, 0, int(free_gb * 1e9)))
    monkeypatch.setattr(bf.dailyio, "daily_path",
                        lambda day: str(tmp_path / ("present" if day in present else "absent") / day))
    for d in present:
        (tmp_path / "present").mkdir(exist_ok=True)
        (tmp_path / "present" / d).write_text("x")

    def fake_process(day, scratch, keep_raw=False):
        seen.append(day)
        return summary or {"day": day, "hexes": 3, "bytes": 9, "written": True}

    monkeypatch.setattr(bf, "process_day", fake_process)
    for mod, fn in ((bf.baselines, "write_baselines"), (bf.regions, "build_region_series"),
                    (bf.build_site_data, "build_all")):
        monkeypatch.setattr(mod, fn, lambda: None)
    return seen


def _run(tmp_path, *args):
    return bf.main([*args, "--scratch", str(tmp_path / "scratch")])


def test_paused_on_low_disk_fails(tmp_path, monkeypatch):
    seen = _stub(monkeypatch, tmp_path, free_gb=13.3)   # the 2026-11-01 runner
    assert _run(tmp_path, "2026-10-31") == bf.EXIT_PAUSED
    assert seen == []                                   # nothing was attempted


def test_zero_hex_day_fails_with_require_ingest(tmp_path, monkeypatch):
    _stub(monkeypatch, tmp_path, summary={"hexes": 0, "written": False})
    assert _run(tmp_path, "2026-10-31", "--require-ingest") == bf.EXIT_MISSING


def test_unpublished_day_fails_with_require_ingest(tmp_path, monkeypatch):
    _stub(monkeypatch, tmp_path)

    def not_ready(*a, **k):
        raise bf.download.ReleaseNotAvailable("not yet")

    monkeypatch.setattr(bf, "process_day", not_ready)
    assert _run(tmp_path, "2026-10-31", "--require-ingest") == bf.EXIT_MISSING


def test_zero_ingest_without_flag_keeps_local_behavior(tmp_path, monkeypatch):
    # Local bulk runs leave gaps and carry on, as before.
    _stub(monkeypatch, tmp_path, summary={"hexes": 0, "written": False})
    assert _run(tmp_path, "2026-10-31") == 0


def test_present_day_is_not_missing(tmp_path, monkeypatch):
    # A rerun of a night that already landed is fine.
    _stub(monkeypatch, tmp_path, present={"2026-10-31"})
    assert _run(tmp_path, "2026-10-31", "--require-ingest") == 0


def test_catchup_retries_prior_days(tmp_path, monkeypatch):
    seen = _stub(monkeypatch, tmp_path, present={"2026-10-30"})
    assert _run(tmp_path, "2026-11-01", "--catchup", "--require-ingest") == 0
    assert bf.C.NIGHTLY_CATCHUP_DAYS == 2
    assert seen == ["2026-10-31", "2026-11-01"]          # 10-30 present, skipped


def test_nightly_workflow_passes_the_flags():
    wf = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "nightly.yml").read_text()
    assert "--require-ingest" in wf and "--catchup" in wf
    assert "ingest-check" in wf and "needs.ingest-check.result == 'failure'" in wf
