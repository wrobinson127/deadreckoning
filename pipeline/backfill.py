"""
Backfill a range of UTC days, then recompute baselines and region series once.

    python -m pipeline.backfill 2026-06-30 2026-07-13    # inclusive range
    python -m pipeline.backfill 2026-07-13               # single day
    python -m pipeline.backfill --last 14                # most recent 14 days ending yesterday

RESUMABLE + IDEMPOTENT: days whose daily .gz already exists are skipped (unless
--force), so an interrupted bulk run resumes just by re-invoking the same command
— completed days are never re-downloaded. Safe to Ctrl-C and re-kick, or to
schedule (a cron / Task Scheduler entry re-running the same range until the
archive fills over days, no babysitting).

DISK-SAFE: one day's raw dump is deleted immediately after that day aggregates
(run_daily.process_day's finally), so scratch holds at most ONE day (~4 GB peak,
2026). Before each day the loop checks free space on the scratch volume and
PAUSES cleanly (with a flag) if it falls below --min-free-gb (default
config.MIN_FREE_DISK_GB), rather than filling the disk. Free space and re-run.

Designed to run both in Actions (one day at a time) and locally for bulk.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import date as date_cls, timedelta

from . import baselines, build_site_data, config as C, dailyio, download, regions
from .run_daily import default_scratch, process_day


def _daterange(start: date_cls, end: date_cls):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _resolve_range(args) -> tuple[date_cls, date_cls]:
    if args.last is not None:
        # `--last N` ends yesterday (UTC), since today's dump won't exist yet.
        end = date_cls.fromisoformat(args.end_today) - timedelta(days=1) \
            if args.end_today else _utc_yesterday()
        start = end - timedelta(days=args.last - 1)
        return start, end
    start = date_cls.fromisoformat(args.start)
    end = date_cls.fromisoformat(args.end) if args.end else start
    return start, end


def _utc_yesterday() -> date_cls:
    # Avoid importing datetime.now() semantics beyond date; UTC yesterday.
    from datetime import datetime, timezone
    return (datetime.now(timezone.utc) - timedelta(days=1)).date()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Backfill a date range of adsb.lol days.")
    ap.add_argument("start", nargs="?", help="start day YYYY-MM-DD")
    ap.add_argument("end", nargs="?", help="end day YYYY-MM-DD (inclusive)")
    ap.add_argument("--last", type=int, default=None, help="most recent N days ending yesterday (UTC)")
    ap.add_argument("--end-today", dest="end_today", default=None,
                    help="override 'today' (UTC) for --last, YYYY-MM-DD (testing)")
    ap.add_argument("--force", action="store_true", help="reprocess days already present")
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--scratch", default=None)
    ap.add_argument("--min-free-gb", type=float, default=C.MIN_FREE_DISK_GB,
                    help="pause (don't start a new day) if free disk on the scratch volume "
                         "falls below this many GB")
    ap.add_argument("--no-derived", action="store_true",
                    help="skip baselines/region recompute (do it once at the end of a larger job)")
    args = ap.parse_args(argv)

    if args.last is None and not args.start:
        ap.error("provide a start day, a range, or --last N")

    start, end = _resolve_range(args)
    scratch = args.scratch or default_scratch()
    os.makedirs(scratch, exist_ok=True)   # so the disk-space check has a real path

    done, skipped, notready, failed = [], [], [], []
    paused = False
    for d in _daterange(start, end):
        day = d.isoformat()
        out = dailyio.daily_path(day)
        if os.path.exists(out) and not args.force:
            skipped.append(day)
            print(f"[skip] {day} (exists)")
            continue
        free_gb = shutil.disk_usage(scratch).free / 1e9
        if free_gb < args.min_free_gb:
            paused = True
            print(f"[PAUSE] free disk {free_gb:.1f} GB < {args.min_free_gb} GB floor on "
                  f"{scratch}; stopping before {day} rather than filling the disk. "
                  f"Free space, then re-run the same command to resume (done days skip).",
                  file=sys.stderr)
            break
        try:
            summary = process_day(day, scratch, keep_raw=args.keep_raw)
            if not summary.get("written"):
                # 0-hex placeholder release — left as a gap, like a not-ready day.
                notready.append(day)
                print(f"[empty] {day} (0 hexes — placeholder release; left as a gap)")
                continue
            done.append(day)
            print(f"[ok]   {day}  hexes={summary['hexes']} bytes={summary['bytes']}")
        except download.ReleaseNotAvailable:
            notready.append(day)
            print(f"[wait] {day} (release not published)")
        except Exception as e:  # keep going; one bad day shouldn't sink the range
            failed.append((day, str(e)))
            print(f"[FAIL] {day}: {e}", file=sys.stderr)

    if not args.no_derived and (done or args.force):
        print("recomputing baselines + region series + site data ...")
        baselines.write_baselines()
        regions.build_region_series()
        build_site_data.build_all()

    print(f"\nprocessed={len(done)} skipped={len(skipped)} "
          f"not_ready={len(notready)} failed={len(failed)}"
          + (" PAUSED (low disk — free space and re-run to resume)" if paused else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
