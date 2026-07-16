"""The write-up analysis runs clean on the current archive, and its stat logic
is guarded. Reads committed aggregates; no chart rendering here (fast, no I/O)."""
import json
import os

from analysis import analyze
from pipeline.paths import repo_path


def test_rolling_baseline_none_safe_and_min_days():
    r = [0.1] * 10 + [None, 0.5]        # a null (no-coverage) day inside the window
    m, s = analyze.rolling_baseline(r, 28)
    assert m[:6] == [None] * 6          # below BASELINE_MIN_DAYS -> no baseline
    assert m[6] is not None             # enough history -> baseline exists
    assert m[11] is not None            # the None day does not break the window


def test_classify_quadrants():
    rows = {
        "a": {"mean_interference": 0.80, "spikiness_std": 0.01},  # chronic
        "b": {"mean_interference": 0.80, "spikiness_std": 0.30},  # volatile
        "c": {"mean_interference": 0.02, "spikiness_std": 0.30},  # episodic
        "d": {"mean_interference": 0.02, "spikiness_std": 0.01},  # quiet
    }
    analyze.classify(rows)
    assert rows["a"]["classification"] == "chronic"
    assert rows["b"]["classification"] == "volatile"
    assert rows["c"]["classification"] == "episodic"
    assert rows["d"]["classification"] == "quiet"


def test_region_stats_runs_on_current_archive():
    regions = analyze.load_regions()
    assert regions, "no committed region series to analyze"
    rows, _ = analyze.region_stats(regions, analyze.load_events())
    analyze.classify(rows)
    assert rows, "region_stats produced no rows"
    for r in rows.values():
        assert 0.0 <= r["mean_interference"] <= 1.0
        assert 0.0 <= r["peak_ratio"] <= 1.0
        assert r["classification"] in {"chronic", "episodic", "quiet", "volatile"}
        assert r["n_events_in_window"] <= r["n_events_total"]


def test_committed_stats_json_is_wellformed_and_honest():
    p = repo_path("site", "assets", "analysis", "stats.json")
    if not os.path.exists(p):
        return  # figures not regenerated in this checkout
    d = json.load(open(p, encoding="utf-8"))
    for k in ("archive", "regions", "distribution", "events", "small_sample_note"):
        assert k in d, f"stats.json missing {k}"
    assert d["archive"]["n_days"] >= 1
    # the honesty guardrail must state its own limits, not a significance claim
    note = d["small_sample_note"].lower()
    assert "illustrative" in note and "no significance" in note


def test_committed_stats_json_carries_client_render_contract():
    """The interactive write-up charts render client-side from stats.json, so the
    file must carry the per-region series (with baseline) and the pre-binned
    distribution the browser needs. Guards site/js/writeup.js's data binding."""
    p = repo_path("site", "assets", "analysis", "stats.json")
    if not os.path.exists(p):
        return  # figures not regenerated in this checkout
    d = json.load(open(p, encoding="utf-8"))
    assert d.get("featured"), "no featured regions for the region panels"
    for rid, r in d["regions"].items():
        s = r.get("series")
        assert s, f"region {rid} has no series for the client line chart"
        pt = s[0]
        for k in ("d", "r", "bm", "bs"):        # date, ratio, baseline mean/std
            assert k in pt, f"series point in {rid} missing {k}"
        # ratio and baseline are numbers-or-null (no strings, no interpretation)
        for k in ("r", "bm", "bs"):
            assert pt[k] is None or isinstance(pt[k], (int, float))
    bins = d["distribution"].get("bins")
    assert bins, "distribution has no pre-binned counts for the client histogram"
    b0 = bins[0]
    for k in ("x0", "x1", "c"):
        assert k in b0, f"distribution bin missing {k}"
    assert all(b["c"] >= 0 for b in bins)
