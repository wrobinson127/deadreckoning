"""Repo-root-relative path helper, so entrypoints work from any cwd."""
from __future__ import annotations

import os

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
