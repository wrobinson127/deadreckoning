"""
Process ONE UTC day end-to-end: download -> stream-parse -> aggregate -> write
data/daily/YYYY-MM-DD.json, then delete the raw dump. Used by both the nightly
Action and local runs.

    python -m pipeline.run_daily 2026-07-13 [--keep-raw] [--scratch DIR]

Exits 0 on success, 3 if the day's release is not published yet (so the nightly
Action can treat "not ready" as a clean retry, not a failure).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date as date_cls

import orjson

from . import aggregate, config as C, download, parse
from .paths import repo_path


def default_scratch() -> str:
    return os.environ.get("DR_SCRATCH", repo_path(".scratch"))


def process_day(day: str, scratch: str, keep_raw: bool = False) -> dict:
    """Download, parse, aggregate, and write one day. Returns a summary dict."""
    date_cls.fromisoformat(day)  # validate format early
    parts = download.download_day(day, scratch)
    try:
        records = aggregate.aggregate_points(parse.stream_points(parts))
    finally:
        if not keep_raw:
            download.cleanup(parts)

    out = repo_path(C.DAILY_JSON_TEMPLATE.format(date=day))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(orjson.dumps(records))  # compact; small (<~1MB/day)

    n_hi = sum(1 for r in records if r["confidence"] == "high")
    summary = {
        "day": day,
        "hexes": len(records),
        "hexes_high_conf": n_hi,
        "output": os.path.relpath(out, repo_path()),
        "bytes": os.path.getsize(out),
    }
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Process one UTC day of adsb.lol data.")
    ap.add_argument("day", help="UTC day, YYYY-MM-DD")
    ap.add_argument("--keep-raw", action="store_true", help="do not delete the raw dump")
    ap.add_argument("--scratch", default=None, help="scratch dir for raw parts")
    args = ap.parse_args(argv)
    scratch = args.scratch or default_scratch()
    try:
        summary = process_day(args.day, scratch, keep_raw=args.keep_raw)
    except download.ReleaseNotAvailable as e:
        print(f"[not-ready] {e}", file=sys.stderr)
        return 3
    print(orjson.dumps(summary, option=orjson.OPT_INDENT_2).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
