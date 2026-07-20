"""atomic_write_bytes: writes land whole or not at all.

Guards the crash-safety invariant — a committed aggregate (manifest.json,
baselines.json, a daily .gz) is never left truncated by a crash/Ctrl-C mid-write,
and a failed write never clobbers the previous good file or leaks a temp file.
"""
from __future__ import annotations

import os

import pytest

from pipeline.paths import atomic_write_bytes


def _temps(d) -> list:
    return [n for n in os.listdir(d) if n.startswith(".tmp-")]


def test_writes_and_overwrites(tmp_path):
    p = str(tmp_path / "sub" / "x.json")   # nested dir is auto-created
    atomic_write_bytes(p, b"hello")
    assert open(p, "rb").read() == b"hello"
    atomic_write_bytes(p, b"world")        # overwrite in place
    assert open(p, "rb").read() == b"world"


def test_leaves_no_temp_file_on_success(tmp_path):
    atomic_write_bytes(str(tmp_path / "x.bin"), b"data")
    assert _temps(tmp_path) == []


def test_target_untouched_and_no_temp_when_write_fails(tmp_path):
    p = str(tmp_path / "x.bin")
    atomic_write_bytes(p, b"original")
    # A str payload raises TypeError inside the binary write, AFTER the temp file
    # is opened — exercises the cleanup path. The good target must survive.
    with pytest.raises(TypeError):
        atomic_write_bytes(p, "not-bytes")   # type: ignore[arg-type]
    assert open(p, "rb").read() == b"original"
    assert _temps(tmp_path) == []
