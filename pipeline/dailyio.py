"""
Read/write daily aggregate artifacts — the single place the on-disk storage
format is defined.

Daily aggregates are committed gzip-compressed (``data/daily/YYYY-MM-DD.json.gz``)
so the tracked archive and the deployed Pages site stay small: ~3.3 MB/day of
JSON compresses to ~0.24 MB, which is what keeps a multi-year backfill under
GitHub Pages' ~1 GB guidance. The browser decompresses each day client-side with
the native ``DecompressionStream`` API — no runtime library, no build step.

Writes are deterministic: we set the gzip header ``mtime`` to 0 and omit the
embedded filename, so re-running the pipeline on unchanged input reproduces
byte-identical artifacts (no spurious git diffs, and the adversarial "did the
data actually change?" check stays meaningful).
"""
from __future__ import annotations

import glob
import gzip
import os

import orjson

from . import config as C
from .paths import repo_path

_SUFFIX = ".json.gz"


def daily_path(day: str) -> str:
    """Absolute path to one day's gzipped daily aggregate."""
    return repo_path(C.DAILY_TEMPLATE.format(date=day))


def daily_paths() -> list[str]:
    """Sorted absolute paths of every committed daily aggregate."""
    return sorted(glob.glob(repo_path("data", "daily", "*" + _SUFFIX)))


def day_of(path: str) -> str:
    """The ``YYYY-MM-DD`` day for a daily artifact path (strips ``.json.gz``)."""
    return os.path.basename(path).removesuffix(_SUFFIX)


def write_daily(day: str, records) -> str:
    """Serialize ``records`` to the day's ``.json.gz`` artifact, deterministically."""
    out = daily_path(day)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    raw = orjson.dumps(records)
    with open(out, "wb") as fh:
        # GzipFile (not gzip.open) so we can pin mtime=0 and drop the filename
        # field, making the compressed bytes a pure function of the input.
        with gzip.GzipFile(fileobj=fh, mode="wb",
                           compresslevel=C.GZIP_LEVEL, mtime=0) as gz:
            gz.write(raw)
    return out


def read_daily(path: str):
    """Load and JSON-decode a gzipped daily artifact."""
    with gzip.open(path, "rb") as fh:
        return orjson.loads(fh.read())


def load_dailies() -> list[tuple[str, list]]:
    """[(day, records), ...] for every committed daily artifact, day-sorted."""
    return [(day_of(p), read_daily(p)) for p in daily_paths()]
