"""Repo-root-relative path helper, so entrypoints work from any cwd."""
from __future__ import annotations

import os
import tempfile

# pipeline/ lives directly under the repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_path(*parts: str) -> str:
    """Join path parts onto the repo root.

    Accepts either a single pre-joined relative path ("data/baselines.json") or
    individual components ("data", "daily", "x.json").
    """
    if len(parts) == 1:
        return os.path.join(REPO_ROOT, parts[0].replace("/", os.sep))
    return os.path.join(REPO_ROOT, *parts)


def atomic_write_bytes(path: str, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically.

    Write to a sibling temp file, flush + fsync, then ``os.replace`` it into
    place (an atomic rename on the same filesystem). A crash or Ctrl-C mid-write
    leaves the temp file behind, never a truncated target — so a committed
    aggregate (manifest.json, baselines.json, a daily .gz) is never half-written
    and read back as corrupt. The temp file is removed if the write fails.
    """
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
