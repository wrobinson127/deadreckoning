"""The deep-backfill planner orders days by analytic priority (recent gaps ->
event windows -> backward), stays inside [floor, yesterday], excludes days already
present, and never repeats a day."""
from datetime import date

from pipeline.deep_backfill import build_plan


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
