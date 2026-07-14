"""Test helpers: build a tiny split-tar of gzipped synthetic traces.

Mirrors the real adsb.lol layout (traces/XX/trace_full_<icao>.json, gzipped,
inside a tar that is split into parts) so the parser is exercised against the
real format and the ChainedReader reassembly path.
"""
from __future__ import annotations

import gzip
import io
import os
import tarfile

import orjson


def make_trace(icao: str, points: list, timestamp: int = 1_700_000_000) -> dict:
    """Build a trace dict. Each `points` entry is a partial point spec:
    (sec, lat, lon, alt, detail_or_None). We pad to the readsb point layout.
    """
    trace = []
    for sec, lat, lon, alt, detail in points:
        # [sec, lat, lon, alt, gs, track, flags, vrate, detail, postype, ...]
        trace.append([sec, lat, lon, alt, 400.0, 90.0, 0, 0, detail,
                      "adsb_icao", None, None, None])
    return {"icao": icao, "r": "TEST", "t": "TEST",
            "timestamp": timestamp, "trace": trace}


def detail(nic, rc=None, version=2):
    d = {"type": "adsb_icao", "nic": nic, "version": version}
    if rc is not None:
        d["rc"] = rc
    return d


def write_split_tar(dest_dir: str, traces: dict[str, dict], parts: int = 2) -> list[str]:
    """Write {icao: trace_dict} as gzipped members into a split tar; return part paths.

    Splits the tar bytes into `parts` roughly equal chunks named *.tar.aa/.ab/...
    """
    os.makedirs(dest_dir, exist_ok=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for icao, tr in traces.items():
            payload = gzip.compress(orjson.dumps(tr))
            info = tarfile.TarInfo(name=f"./traces/{icao[-2:]}/trace_full_{icao}.json")
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    data = buf.getvalue()

    paths = []
    step = max(1, len(data) // parts)
    suffixes = ["aa", "ab", "ac", "ad", "ae"]
    for i in range(parts):
        chunk = data[i * step: (i + 1) * step] if i < parts - 1 else data[i * step:]
        p = os.path.join(dest_dir, f"fixture.tar.{suffixes[i]}")
        with open(p, "wb") as fh:
            fh.write(chunk)
        paths.append(p)
    return paths
