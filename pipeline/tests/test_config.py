"""Config invariants: threshold + tier ordering must stay self-consistent."""
from __future__ import annotations

from pipeline import config as C


def test_threshold_and_tiers_are_sane():
    assert 0 <= C.NIC_DEGRADED_MAX <= 11
    assert C.CONFIDENCE_MEDIUM_MIN == C.MIN_AIRCRAFT_FLOOR  # floor == medium entry
    assert C.CONFIDENCE_HIGH_MIN > C.CONFIDENCE_MEDIUM_MIN
    assert 0 < C.BASELINE_MIN_DAYS <= C.BASELINE_WINDOW_DAYS


def test_tier_monotonic():
    tiers = [C.confidence_tier(n) for n in range(0, 15)]
    # once "high", never regress downward as n grows
    order = {"insufficient": 0, "medium": 1, "high": 2}
    nums = [order[t] for t in tiers]
    assert nums == sorted(nums)
