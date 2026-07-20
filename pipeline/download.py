"""
Resolve and download one UTC day's adsb.lol dump (split-tar parts).

Uses the public GitHub Releases API via stdlib urllib — no third-party HTTP
dependency, and no auth required for public repos (a GH_TOKEN/GITHUB_TOKEN in the
environment is used if present, only to raise rate limits). Raw parts are written
to a scratch dir and are meant to be DELETED after processing (see cleanup()).

A day may not be published yet; resolve_release() raises ReleaseNotAvailable so
the nightly Action can exit cleanly and retry next schedule instead of failing.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date as date_cls
from typing import Sequence

from . import config as C


class ReleaseNotAvailable(Exception):
    """Raised when neither a prod nor staging release exists for the date yet."""


def _api_get(url: str) -> "dict | list | None":
    req = urllib.request.Request(url, headers={
        "User-Agent": "deadreckoning-pipeline",
        "Accept": "application/vnd.github+json",
    })
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _tag_variants(day: str) -> list[str]:
    dotted = day.replace("-", ".")  # YYYY-MM-DD -> YYYY.MM.DD
    return [
        C.RELEASE_TAG_TEMPLATE.format(date=dotted),
        C.RELEASE_STAGING_TEMPLATE.format(date=dotted),
    ]


def _select_parts(assets: list[dict]) -> list[dict]:
    """Pick a day's tar payload asset(s), across archive-format eras.

    2024+ split each day into byte-parts (``.tar.aa``, ``.tar.ab``, ...); the
    2023 archive ships a single ``.tar``. Prefer split parts (sorted so ``.aa``
    precedes ``.ab``); otherwise fall back to a lone ``.tar``. Either way the
    parser concatenates the returned parts in order and reassembles an identical
    tar stream, so downstream normalization is byte-for-byte format-agnostic.
    """
    split = sorted((a for a in assets if ".tar.a" in a["name"]), key=lambda a: a["name"])
    if split:
        return split
    return [a for a in assets if a["name"].endswith(".tar")]


def resolve_release(day: str) -> tuple[str, list[dict]]:
    """Return (tag, assets) for the given YYYY-MM-DD day, preferring prod.

    ``assets`` is the GitHub API asset list (each has ``name``, ``size``,
    ``browser_download_url``). Raises ReleaseNotAvailable if nothing is published.
    """
    year = date_cls.fromisoformat(day).year
    repo = C.GHIST_REPO_TEMPLATE.format(year=year)
    for tag in _tag_variants(day):
        data = _api_get(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
        if data and data.get("assets"):
            parts = _select_parts(data["assets"])
            if parts:
                return tag, parts
    raise ReleaseNotAvailable(f"No prod/staging release with tar parts for {day}")


def download_day(day: str, dest_dir: str) -> list[str]:
    """Download the split-tar parts for ``day`` into ``dest_dir``; return paths."""
    os.makedirs(dest_dir, exist_ok=True)
    _tag, parts = resolve_release(day)
    paths: list[str] = []
    for a in parts:
        out = os.path.join(dest_dir, a["name"])
        if os.path.exists(out) and os.path.getsize(out) == a["size"]:
            paths.append(out)  # already present, correct size
            continue
        _download_file(a["browser_download_url"], out)
        paths.append(out)
    return paths


def _download_file(url: str, out: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "deadreckoning-pipeline"})
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    tmp = out + ".part"
    try:
        with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as fh:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
        os.replace(tmp, out)
    except BaseException:
        # A failed/interrupted download must not leave a partial .part orphaned
        # (it would waste scratch and never be resumed — the size-match skip keys
        # off the final name, not .part). Clean it up; re-run to retry.
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def cleanup(paths: Sequence[str]) -> None:
    """Delete raw dump parts after processing — we keep only aggregates."""
    for p in paths:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
