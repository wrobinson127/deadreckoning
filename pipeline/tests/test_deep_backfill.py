"""The deep-backfill planner orders days by analytic priority (recent gaps ->
event windows -> backward), stays inside [floor, yesterday], excludes days already
present, and never repeats a day."""
from datetime import date

import pipeline.deep_backfill as db
from pipeline.deep_backfill import build_plan, _parse_window, _within_window


def _present(a, b):
    from datetime import date as d, timedelta
    out, cur = set(), d.fromisoformat(a)
    end = d.fromisoformat(b)
    while cur <= end:
        out.add(cur.isoformat()); cur += timedelta(days=1)
    return out


def test_plan_order_and_bounds():
    present = _present("2026-04-17", "2026-07-15")   # the current window ...
    present.discard("2026-06-10")                     # ... with an intra-span hole
    yesterday = date(2026, 7, 16)
    events = ["2024-04-29", "2025-07-15"]            # both far outside the present window
    plan = build_plan(present, "2023-01-01", yesterday, events, pad=7)

    # nothing already present, no duplicates, all inside [floor, yesterday]
    assert not (set(plan) & present)
    assert len(plan) == len(set(plan))
    assert all("2023-01-01" <= d <= "2026-07-16" for d in plan)

    # 1a) the extension day (2026-07-16) is first
    assert plan[0] == "2026-07-16"
    # 1b) the intra-span hole is filled, and before the deep backward tail
    assert "2026-06-10" in plan
    assert plan.index("2026-06-10") < plan.index("2024-04-16")

    # 2) event windows land before the deep backward tail, newest event first
    i_2025 = plan.index("2025-07-15")   # newest event center
    i_2024 = plan.index("2024-04-29")   # older event center
    i_backtail = plan.index("2024-04-16")  # a generic backward-fill day (earliest present - 1)
    assert i_2025 < i_2024 < i_backtail
    # the +/-7 window is present around an event center
    assert "2025-07-08" in plan and "2025-07-22" in plan

    # 3) backward fill reaches toward the floor and is strictly descending at the tail
    assert plan[-1] == "2023-01-01"


def test_empty_archive_starts_at_floor():
    plan = build_plan(set(), "2023-06-10", date(2023, 6, 15), [], pad=7)
    assert plan[0] == "2023-06-10" and plan[-1] == "2023-06-15"


def test_run_window_parse_and_membership():
    assert _parse_window("3-10") == (3, 10)
    assert _parse_window("") is None and _parse_window(None) is None
    # normal window [start, end): start inclusive, end exclusive
    w = _parse_window("3-10")
    assert all(_within_window(w, h) for h in (3, 4, 7, 9))
    assert not any(_within_window(w, h) for h in (0, 2, 10, 11, 23))
    # window that wraps past midnight
    ww = _parse_window("23-8")
    assert all(_within_window(ww, h) for h in (23, 0, 3, 7))
    assert not any(_within_window(ww, h) for h in (8, 9, 12, 22))
    # no window / degenerate window == always on
    assert _within_window(None, 15) and _within_window((5, 5), 15)


def test_startup_reconcile_derives_when_manifest_stale(monkeypatch):
    # A prior crash left more dailies on disk than the manifest lists -> rebuild.
    monkeypatch.setattr(db, "_present_days", lambda: {"a", "b", "c"})
    monkeypatch.setattr(db, "_manifest_day_count", lambda: 2)
    calls = []
    monkeypatch.setattr(db, "_derive", lambda reason: calls.append(reason))
    db._reconcile_derived_if_stale()
    assert len(calls) == 1


def test_startup_reconcile_noop_when_in_sync(monkeypatch):
    monkeypatch.setattr(db, "_present_days", lambda: {"a", "b"})
    monkeypatch.setattr(db, "_manifest_day_count", lambda: 2)
    calls = []
    monkeypatch.setattr(db, "_derive", lambda reason: calls.append(reason))
    db._reconcile_derived_if_stale()
    assert calls == []


def test_startup_reconcile_noop_on_empty_archive(monkeypatch):
    # Fresh checkout, nothing on disk yet -> nothing to reconcile.
    monkeypatch.setattr(db, "_present_days", lambda: set())
    monkeypatch.setattr(db, "_manifest_day_count", lambda: -1)
    calls = []
    monkeypatch.setattr(db, "_derive", lambda reason: calls.append(reason))
    db._reconcile_derived_if_stale()
    assert calls == []
