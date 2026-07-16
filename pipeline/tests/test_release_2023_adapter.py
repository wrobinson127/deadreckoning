"""2023 archive adapter.

The 2023 adsb.lol history ships each day as a single `.tar`; 2024+ split the
day into `.tar.aa`/`.tar.ab` byte-parts. `download._select_parts` must pick the
right asset for either era, and — the property that matters — the two packagings
must normalize to byte-identical aggregate records for the same underlying data.
"""
from pipeline import download, parse
from pipeline.aggregate import aggregate_points
from pipeline.tests.helpers import detail, make_trace, write_split_tar


def _sample_traces():
    # a couple of aircraft across a few hexes, with degraded + healthy NIC
    return {
        "a00001": make_trace("a00001", [
            (0, 54.7, 20.5, 32000, detail(0)),      # Kaliningrad-ish, degraded
            (30, 54.8, 20.6, 32000, detail(0)),
        ]),
        "a00002": make_trace("a00002", [
            (0, 54.7, 20.5, 33000, detail(6)),      # same area, degraded (nic<=6)
        ]),
        "b00003": make_trace("b00003", [
            (0, 39.0, -98.0, 36000, detail(9)),     # central US, healthy
        ]),
    }


def test_single_tar_and_split_tar_yield_identical_aggregates(tmp_path):
    """A 2023 single-tar and a 2024 split-tar of the SAME data aggregate identically."""
    traces = _sample_traces()
    split_paths = write_split_tar(str(tmp_path / "split"), traces, parts=2)    # 2024+ layout
    single_paths = write_split_tar(str(tmp_path / "single"), traces, parts=1)  # 2023 layout

    recs_split = sorted(aggregate_points(parse.stream_points(split_paths)), key=lambda r: r["hex"])
    recs_single = sorted(aggregate_points(parse.stream_points(single_paths)), key=lambda r: r["hex"])

    assert recs_single, "adapter produced no records from the single-tar layout"
    assert recs_single == recs_split, "2023 single-tar normalized differently from 2024 split-tar"


def test_select_parts_prefers_split_else_single():
    a2023 = [{"name": "v2023.07.13-planes-readsb-prod-0.tar", "size": 1}]
    a2024 = [
        {"name": "v2024.07.13-planes-readsb-prod-0.tar.ab", "size": 2},
        {"name": "v2024.07.13-planes-readsb-prod-0.tar.aa", "size": 1},
    ]
    # 2023: the lone .tar is selected
    assert [a["name"] for a in download._select_parts(a2023)] == \
        ["v2023.07.13-planes-readsb-prod-0.tar"]
    # 2024: split parts selected and sorted (.aa before .ab)
    assert [a["name"] for a in download._select_parts(a2024)] == [
        "v2024.07.13-planes-readsb-prod-0.tar.aa",
        "v2024.07.13-planes-readsb-prod-0.tar.ab",
    ]
    # if both somehow present, split wins over the single .tar
    assert all(".tar.a" in a["name"] for a in download._select_parts(a2023 + a2024))
    # unrelated assets (checksums etc.) are ignored
    assert download._select_parts([{"name": "SHA256SUMS", "size": 1}]) == []
