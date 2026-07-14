"""
Streaming parser for adsb.lol daily dumps.

A day is published as a split tar (``*.tar.aa`` + ``*.tar.ab`` ...) whose members
are per-aircraft ``traces/XX/trace_full_<icao>.json`` files, each gzip-compressed.
We stream the tar member-by-member so the whole day never sits in memory and no
extraction to disk is required.

Each trace point is (readsb format, see wiedehopf README-json.md):
    [sec, lat, lon, alt, gs, track, flags, vrate, detail|null, postype, ...]
We keep AIRBORNE points (``alt != "ground"``) with valid lat/lon that carry a
detail object with a numeric ``nic``.

Public API:
    stream_points(part_paths) -> yields Point(icao, lat, lon, nic, rc, version, t)
"""
from __future__ import annotations

import gzip
import io
import tarfile
from dataclasses import dataclass
from typing import Iterator, Sequence

import orjson

from . import config as C


@dataclass(slots=True)
class Point:
    icao: str
    lat: float
    lon: float
    nic: int
    rc: "int | None"
    version: "int | None"
    t: float  # unix seconds (trace timestamp + point offset)


class ChainedReader(io.RawIOBase):
    """Present multiple files as one continuous byte stream (split-tar reassembly).

    adsb.lol splits the tar at a fixed byte boundary; concatenating the parts in
    order reproduces the original archive. We read them sequentially without ever
    holding more than one buffer in memory.
    """

    def __init__(self, paths: Sequence[str]):
        self._files = [open(p, "rb") for p in paths]
        self._i = 0

    def readable(self) -> bool:  # noqa: D401
        return True

    def readinto(self, b) -> int:  # type: ignore[override]
        while self._i < len(self._files):
            n = self._files[self._i].readinto(b)
            if n:
                return n
            self._i += 1
        return 0

    def close(self) -> None:
        for f in self._files:
            try:
                f.close()
            except Exception:
                pass
        super().close()


def _is_trace_member(name: str) -> bool:
    return (
        name.endswith(".json")
        and ("/traces/" in name or name.startswith("./traces/") or name.startswith("traces/"))
    )


def stream_points(part_paths: Sequence[str]) -> Iterator[Point]:
    """Yield airborne, NIC-bearing points from the given split-tar parts."""
    stream = ChainedReader(part_paths)
    tf = tarfile.open(fileobj=stream, mode="r|")
    try:
        for member in tf:
            if not member.isfile() or not _is_trace_member(member.name):
                continue
            f = tf.extractfile(member)
            if f is None:
                continue
            raw = f.read()
            try:
                data = orjson.loads(gzip.decompress(raw))
            except Exception:
                # Corrupt/unexpected member: skip rather than abort the whole day.
                continue
            yield from _points_from_trace(data, member.name)
    finally:
        tf.close()
        stream.close()


def _points_from_trace(data: dict, member_name: str) -> Iterator[Point]:
    icao = data.get("icao")
    if not icao:
        # Fall back to the filename (trace_full_<icao>.json).
        icao = member_name.rsplit("_", 1)[-1].removesuffix(".json")
    ts0 = data.get("timestamp", 0) or 0
    trace = data.get("trace") or []
    for p in trace:
        if len(p) <= C.IDX_DETAIL:
            continue
        alt = p[C.IDX_ALT]
        if alt == C.GROUND_ALT_SENTINEL:  # ground position -> exclude
            continue
        lat = p[C.IDX_LAT]
        lon = p[C.IDX_LON]
        if lat is None or lon is None:
            continue
        if not (C.LAT_MIN <= lat <= C.LAT_MAX and C.LON_MIN <= lon <= C.LON_MAX):
            continue
        detail = p[C.IDX_DETAIL]
        if not detail:
            continue
        nic = detail.get("nic")
        if nic is None:
            continue
        yield Point(
            icao=icao,
            lat=lat,
            lon=lon,
            nic=nic,
            rc=detail.get("rc"),
            version=detail.get("version"),
            t=ts0 + (p[C.IDX_SECONDS] or 0),
        )
