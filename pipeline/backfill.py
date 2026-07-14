"""
Backfill a range of UTC days, then recompute baselines and region series once.

    python -m pipeline.backfill 2026-06-30 2026-07-13    # inclusive range
    python -m pipeline.backfill 2026-07-13               # single day
    python -m pipeline.backfill --last 14                # most recent 14 days ending yesterday

Idempotent: days whose daily JSON already exists are skipped unless --force.
Designed to run both in Actions (one day at a time) and locally for bulk.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date as date_cls, timedelta

from . import baselines, build_site_data, dailyio, download, regions
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
    ap.add_argument("--no-derived", action="store_true",
                    help="skip baselines/region recompute (do it once at the end of a larger job)")
    args = ap.parse_args(argv)

    if args.last is None and not args.start:
        ap.error("provide a start day, a range, or --last N")

    start, end = _resolve_range(args)
    scratch = args.scratch or default_scratch()

    done, skipped, notready, failed = [], [], [], []
    for d in _daterange(start, end):
        day = d.isoformat()
        out = dailyio.daily_path(day)
        if os.path.exists(out) and not args.force:
            skipped.append(day)
            print(f"[skip] {day} (exists)")
            continue
        try:
            summary = process_day(day, scratch, keep_raw=args.keep_raw)
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
          f"not_ready={len(notready)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
