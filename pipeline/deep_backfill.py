"""
Deep historical backfill driver — a resumable, long-running LOCAL job that fills
the archive in analytic-priority order:

  1. recent gaps    bring the archive current toward yesterday (UTC)
  2. event windows  +/- EVENT_PAD_DAYS around each content/events.yaml date, so
                    annotated events have data beneath them soonest (this feeds
                    the future Findings piece)
  3. backward fill  day-by-day back from the earliest committed day to --floor,
                    through 2024 and into 2023 (download._select_parts handles the
                    single-.tar 2023 era transparently)

Reuses run_daily.process_day (download -> stream-parse -> aggregate -> write, with
the raw dump deleted immediately in a finally, and no on-disk extraction), and the
same disk-space guard as backfill.py: before each day it checks free space on the
scratch volume and PAUSES cleanly if it drops below --min-free-gb, rather than
filling the disk. Peak scratch is one day's raw parts (~4 GB in 2026, less in
older years).

IDEMPOTENT + RESUMABLE: days whose daily .gz already exists are skipped, so it is
safe to Ctrl-C (or lose the process) and re-run the SAME command to resume;
completed days are never re-downloaded. Derived aggregates (baselines, region
series, site data + manifest) are recomputed every --derive-every landed days and
once at the end, so the manifest-matches-daily-set invariant and the site's
coverage copy stay accurate with the committed data.

Scratch MUST live off any cloud-synced path (OneDrive/Dropbox) for bulk runs, or
the sync client will thrash on multi-GB temp files. Set DR_SCRATCH or --scratch.

    python -m pipeline.deep_backfill --dry-run              # print the plan, download nothing
    set DR_SCRATCH=C:\\dr_scratch                            # scratch off OneDrive (Windows)
    python -m pipeline.deep_backfill --floor 2023-01-01     # real run, resumable
    python -m pipeline.deep_backfill --max-days 30          # bound one sitting

Only aggregates are ever written to the repo; raw parts live in scratch and are
deleted after each day. Committing the landed data/ files is a separate step.
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import sys
import time
from datetime import date as date_cls, datetime, timedelta, timezone

from . import baselines, build_site_data, config as C, dailyio, download, regions
from .paths import repo_path
from .run_daily import default_scratch, process_day

EVENT_PAD_DAYS = 7            # +/- window backfilled around each annotated event
DEFAULT_FLOOR = "2023-01-01"  # earliest day to attempt; unavailable days skip cleanly


def _present_days() -> set[str]:
    return {os.path.basename(p)[:10] for p in glob.glob(repo_path("data", "daily", "*.json.gz"))}


def _utc_yesterday() -> date_cls:
    return (datetime.now(timezone.utc) - timedelta(days=1)).date()


def _event_dates() -> list[str]:
    """Dates from content/events.yaml (a 'date' per event)."""
    import yaml
    raw = yaml.safe_load(open(repo_path("content", "events.yaml"), encoding="utf-8"))
    evs = raw if isinstance(raw, list) else (raw or {}).get("events", [])
    out = []
    for e in evs:
        d = e.get("date") or e.get("start")
        if d:
            out.append(str(d)[:10])
    return out


def _span(a: date_cls, b: date_cls):
    """Inclusive date range a..b as ISO strings (a<=b)."""
    d = a
    while d <= b:
        yield d.isoformat()
        d += timedelta(days=1)


def build_plan(present: set[str], floor: str, yesterday: date_cls,
               event_dates: list[str], pad: int = EVENT_PAD_DAYS) -> list[str]:
    """Ordered, de-duplicated list of days to fetch: recent gaps, then event
    windows (newest event first), then backward to the floor. Present days and
    days outside [floor, yesterday] are excluded."""
    lo = date_cls.fromisoformat(floor)
    seen = set(present)
    plan: list[str] = []

    def add(day: str):
        if day in seen:
            return
        if not (floor <= day <= yesterday.isoformat()):
            return
        seen.add(day)
        plan.append(day)

    # 1a) extension: bring the archive current from the latest present to yesterday
    start = (date_cls.fromisoformat(max(present)) + timedelta(days=1)) if present else lo
    if start <= yesterday:
        for day in _span(start, yesterday):
            add(day)
    # 1b) intra-span gaps: any missing day inside the present span (add() skips
    # present days, so only the holes remain) — an archive with holes is worse
    # than one without, and baselines want a contiguous window.
    if present:
        for day in _span(date_cls.fromisoformat(min(present)), date_cls.fromisoformat(max(present))):
            add(day)

    # 2) event windows, newest event first so recent context lands soonest
    for ed in sorted(set(event_dates), reverse=True):
        c = date_cls.fromisoformat(ed)
        for day in _span(c - timedelta(days=pad), c + timedelta(days=pad)):
            add(day)

    # 3) backward progressive fill from the earliest committed day to the floor
    earliest = date_cls.fromisoformat(min(present)) if present else yesterday
    d = earliest - timedelta(days=1)
    while d >= lo:
        add(d.isoformat())
        d -= timedelta(days=1)

    return plan


def _parse_window(spec: str):
    """'3-10' -> (3, 10). Local wall-clock hours, [start, end). Returns None for
    an empty/None spec (run 24/7)."""
    if not spec:
        return None
    try:
        a, b = spec.split("-")
        start, end = int(a), int(b)
        if not (0 <= start <= 24 and 0 <= end <= 24):
            raise ValueError
    except Exception:
        raise SystemExit(f"bad --run-window {spec!r}; expected 'START-END' hours, e.g. 3-10")
    return (start, end)


def _within_window(window, hour: int) -> bool:
    if window is None:
        return True
    start, end = window
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end   # wraps past midnight (e.g. 23-8)


def _wait_for_window(window):
    """Block until the local clock is inside the run window; announce once."""
    announced = False
    while not _within_window(window, datetime.now().hour):
        if not announced:
            print(f"[sleep] outside run window {window[0]:02d}:00-{window[1]:02d}:00 local "
                  f"(now {datetime.now():%H:%M}); pausing until the window opens…", flush=True)
            announced = True
        time.sleep(300)   # re-check every 5 min
    if announced:
        print(f"[wake] inside run window {window[0]:02d}:00-{window[1]:02d}:00; resuming.", flush=True)


def _derive(reason: str):
    print(f"  [derive] recomputing baselines + regions + site data ({reason}) ...", flush=True)
    baselines.write_baselines()
    regions.build_region_series()
    build_site_data.build_all()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ordered, resumable deep backfill (local).")
    ap.add_argument("--floor", default=DEFAULT_FLOOR, help="earliest day to attempt (YYYY-MM-DD)")
    ap.add_argument("--pad", type=int, default=EVENT_PAD_DAYS, help="+/- days around each event")
    ap.add_argument("--derive-every", type=int, default=10, help="recompute derived every N landed days")
    ap.add_argument("--max-days", type=int, default=None, help="stop after N newly-processed days")
    ap.add_argument("--scratch", default=None, help="raw-parts dir; MUST be off OneDrive for bulk")
    ap.add_argument("--min-free-gb", type=float, default=C.MIN_FREE_DISK_GB,
                    help="pause before a day if free disk on the scratch volume is below this")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit; no downloads")
    ap.add_argument("--run-window", default=None,
                    help="only fetch inside this LOCAL-time window, e.g. 3-10 (3am-10am); "
                         "one persistent process sleeps outside it. Omit to run 24/7.")
    args = ap.parse_args(argv)
    window = _parse_window(args.run_window)

    present = _present_days()
    yesterday = _utc_yesterday()
    plan = build_plan(present, args.floor, yesterday, _event_dates(), args.pad)

    print(f"present={len(present)} days; plan={len(plan)} days to fetch "
          f"(floor {args.floor} .. {yesterday.isoformat()})")
    if plan:
        print(f"  first 8: {plan[:8]}")
        print(f"  last 4:  {plan[-4:]}")
    if args.dry_run:
        return 0
    if not plan:
        print("nothing to do — archive already covers the plan.")
        return 0

    scratch = args.scratch or default_scratch()
    os.makedirs(scratch, exist_ok=True)
    if "onedrive" in os.path.abspath(scratch).lower():
        print(f"[WARN] scratch {scratch} looks OneDrive-synced; set DR_SCRATCH off OneDrive "
              f"for bulk runs to avoid sync thrash.", file=sys.stderr)

    if window:
        print(f"run window: {window[0]:02d}:00-{window[1]:02d}:00 local "
              f"(fetching pauses outside it)")

    done = notready = failed = 0
    for day in plan:
        if args.max_days is not None and done >= args.max_days:
            print(f"[stop] reached --max-days {args.max_days}")
            break
        # Time-of-day gate: pause between days until we're back inside the window.
        # (A day already downloading when the window closes finishes; the gate is
        # checked between days, so overshoot is a few minutes, not a hard cut.)
        _wait_for_window(window)
        free_gb = shutil.disk_usage(scratch).free / 1e9
        if free_gb < args.min_free_gb:
            print(f"[PAUSE] free disk {free_gb:.1f} GB < {args.min_free_gb} GB floor on {scratch}; "
                  f"stopping before {day}. Free space and re-run to resume (done days skip).",
                  file=sys.stderr)
            break
        try:
            s = process_day(day, scratch)
            if s["hexes"] == 0:
                # An empty/placeholder release aggregates to zero hexes. Writing it
                # would add a fake "covered, no interference" day and blur the
                # no-data vs no-interference line, so drop it and leave the gap.
                try:
                    os.remove(dailyio.daily_path(day))
                except FileNotFoundError:
                    pass
                notready += 1
                print(f"[empty] {day} (0 hexes — bad/placeholder release; left as a gap)")
                continue
            done += 1
            print(f"[ok]   {day}  hexes={s['hexes']} bytes={s['bytes']}  ({done} this run)", flush=True)
            if args.derive_every and done % args.derive_every == 0:
                _derive(f"every {args.derive_every}")
        except download.ReleaseNotAvailable:
            notready += 1
            print(f"[wait] {day} (no release published)")
        except Exception as e:
            failed += 1
            print(f"[FAIL] {day}: {e}", file=sys.stderr)

    if done:
        _derive("end of run")
    print(f"\nrun complete: processed={done} not_ready={notready} failed={failed} "
          f"(archive now {len(_present_days())} days)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
