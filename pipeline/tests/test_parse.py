"""Parser tests: real-format streaming, ground/invalid filtering, split reassembly."""
from __future__ import annotations

from pipeline import parse
from pipeline.tests.helpers import detail, make_trace, write_split_tar


def test_streams_airborne_nic_points_and_reassembles_split(tmp_path):
    traces = {
        "aaaa01": make_trace("aaaa01", [
            (0, 55.0, 21.0, 35000, detail(8, rc=186)),     # airborne, nic present
            (30, 55.01, 21.01, 35000, detail(3, rc=7408)), # airborne, degraded
        ]),
        "bbbb02": make_trace("bbbb02", [
            (0, 55.2, 21.2, "ground", detail(8)),          # GROUND -> excluded
            (10, 55.2, 21.2, 2000, None),                  # no detail -> excluded
            (20, 999.0, 21.2, 2000, detail(8)),            # invalid lat -> excluded
            (30, 55.2, 21.2, 2000, detail(9, rc=75)),      # kept
        ]),
    }
    parts = write_split_tar(str(tmp_path), traces, parts=2)
    assert len(parts) == 2  # reassembly path is exercised

    pts = list(parse.stream_points(parts))
    # aaaa01 -> 2 points, bbbb02 -> 1 point (only the last valid airborne w/ nic)
    assert len(pts) == 3
    by_icao = {}
    for p in pts:
        by_icao.setdefault(p.icao, []).append(p)
    assert sorted(by_icao) == ["aaaa01", "bbbb02"]
    assert len(by_icao["aaaa01"]) == 2
    assert len(by_icao["bbbb02"]) == 1
    # nic/rc carried through
    a0 = by_icao["aaaa01"][0]
    assert a0.nic == 8 and a0.rc == 186 and a0.version == 2
    # timestamps are trace timestamp + point seconds
    assert by_icao["aaaa01"][1].t == 1_700_000_000 + 30


def test_missing_icao_falls_back_to_filename(tmp_path):
    tr = make_trace("cccc03", [(0, 10.0, 10.0, 30000, detail(8))])
    del tr["icao"]
    parts = write_split_tar(str(tmp_path), {"cccc03": tr}, parts=1)
    pts = list(parse.stream_points(parts))
    assert len(pts) == 1
    assert pts[0].icao == "cccc03"


def test_non_numeric_nic_is_dropped(tmp_path):
    # A corrupt trace with a string/bool nic must be dropped at parse (else the
    # aggregate comparison pt.nic <= NIC_DEGRADED_MAX raises and sinks the day).
    # A float nic is legitimate and kept.
    tr = make_trace("dddd04", [
        (0, 55.0, 21.0, 35000, detail("8")),                                  # string -> dropped
        (10, 55.0, 21.0, 35000, {"type": "adsb_icao", "nic": True, "version": 2}),  # bool -> dropped
        (20, 55.0, 21.0, 35000, detail(6.0)),                                 # float -> kept
    ])
    parts = write_split_tar(str(tmp_path), {"dddd04": tr}, parts=1)
    pts = list(parse.stream_points(parts))
    assert len(pts) == 1
    assert pts[0].nic == 6.0
