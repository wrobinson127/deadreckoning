"""Baseline math: window, min-days gate, floor exclusion, mean/std."""
from __future__ import annotations

import math

from pipeline import baselines, config as C


def _daily(day, hexrecs):
    return (day, [{"hex": h, "n_aircraft": na, "n_reports": na * 3,
                   "bad_aircraft": int(round(br * na)), "bad_ratio": br,
                   "confidence": C.confidence_tier(na)} for h, na, br in hexrecs])


def test_min_days_gate_and_mean_std():
    # Hex "A": present with >=floor aircraft on enough days -> baseline emitted.
    # Hex "B": present on too few qualifying days -> no baseline.
    dailies = []
    ratios = [0.1, 0.2, 0.3, 0.1, 0.2, 0.3, 0.2]  # 7 days == BASELINE_MIN_DAYS
    for i, br in enumerate(ratios):
        day = f"2026-06-{10+i:02d}"
        dailies.append(_daily(day, [("A", 12, br), ("B", 2, 0.9)]))  # B below floor

    out = baselines.compute_baselines(dailies)
    assert "A" in out["hexes"]
    assert "B" not in out["hexes"]  # B never met the aircraft floor
    a = out["hexes"]["A"]
    assert a["n"] == 7
    assert a["mean"] == round(sum(ratios) / len(ratios), 4)
    var = sum((x - sum(ratios) / len(ratios)) ** 2 for x in ratios) / len(ratios)
    assert a["std"] == round(math.sqrt(var), 4)


def test_below_min_days_yields_no_baseline():
    dailies = [_daily(f"2026-06-{10+i:02d}", [("A", 12, 0.2)])
               for i in range(C.BASELINE_MIN_DAYS - 1)]
    out = baselines.compute_baselines(dailies)
    assert out["hexes"] == {}


def test_window_caps_days():
    # More than the window of qualifying days -> n capped at window size.
    n_days = C.BASELINE_WINDOW_DAYS + 5
    dailies = [_daily(f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", [("A", 12, 0.2)])
               for i in range(n_days)]
    out = baselines.compute_baselines(dailies)
    assert out["hexes"]["A"]["n"] == C.BASELINE_WINDOW_DAYS
