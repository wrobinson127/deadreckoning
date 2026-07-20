"""download._download_file: a failed/interrupted transfer leaves no orphan.

The final artifact is written via a .part temp + os.replace (atomic). If the
stream dies mid-download the .part must be cleaned up, not left to waste scratch
(the size-match skip keys off the final name, not .part, so an orphan would never
be resumed).
"""
from __future__ import annotations

import os

import pytest

import pipeline.download as dl


class _DyingResp:
    """A urlopen() result whose read() fails after the .part is already open."""
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, _n):
        raise OSError("stream died mid-download")


def test_failed_download_removes_part(tmp_path, monkeypatch):
    out = str(tmp_path / "fixture.tar.aa")
    monkeypatch.setattr(dl.urllib.request, "urlopen", lambda *a, **k: _DyingResp())
    with pytest.raises(OSError):
        dl._download_file("https://example.invalid/x", out)
    assert not os.path.exists(out + ".part")   # no orphaned partial
    assert not os.path.exists(out)              # and no half-written final
