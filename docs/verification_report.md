# Phase 0 — Verification Report

**Sample day:** 2026-07-13 (UTC) · **Source:** `adsblol/globe_history_2026`,
prod release `v2026.07.13-planes-readsb-prod-0` (ODbL 1.0).
**Measured on:** the target dev machine (Windows, Python 3.12), single-threaded,
streaming the split-tar directly (no disk extraction).

## Verdict: GATE PASSED ✅
Both gate criteria are met with large margins:
- **(a) NIC is present and dense enough** for hex-level daily aggregation —
  96.2% of aircraft traces carry NIC; 24.1M airborne NIC-bearing points/day.
- **(b) One day processes within runner limits** — 382 s wall-clock, 785 MB peak
  RSS on this machine; a GitHub Actions runner (~14 GB RAM/disk, 6-hour cap) has
  ample headroom.

Proceeding to Phase 1. Threshold, resolution, and nic=0 handling notes below;
open items are carried as FLAG_FOR_REVIEW in the self-audit.

---

## 1. NIC density
| Metric | Value |
|---|---|
| Traces in day | 78,102 |
| Traces with ≥1 NIC detail | 75,117 (**96.2%**) |
| Airborne points total | 96,311,727 |
| Airborne points carrying NIC | **24,090,772** |
| Ground points (excluded) | 12,514,556 |
| Detail-record interval (median) | **18.5 s** (p10 3.9 s, p90 78.5 s) |

NIC detail records recur along a trace roughly every ~18 s (median). Because we
aggregate per-aircraft-per-hex (not per-second), this periodic cadence is more
than sufficient — an aircraft crossing a ~1,770 km² res-4 hex contributes many
NIC samples. **Conclusion: density is not a constraint.**

## 2. Volume & timing
| Metric | Value |
|---|---|
| Download (2 split-tar parts, prod) | 3.96 GB |
| Processing wall-clock (1 day, 1 core) | 382 s (~6.4 min) |
| Peak RSS | 785 MB |
| Active res-4 hexes / day | 29,686 |
| (hex, aircraft) pairs held in memory | 2,751,011 |

Streaming member-by-member means memory is bounded by the aggregation state
(the per-(hex,aircraft) tally), not the day size. 785 MB peak leaves a >17×
margin under a 14 GB runner. A single day is comfortable; no chunking needed.
**14-day backfill** ≈ 14 × (download + ~6.4 min) — hours, not a concern; bulk
multi-year backfill is deferred (see `backfill_strategy.md`).

## 3. Field semantics
**NIC scale 0–11 confirmed present** (all values observed). The `rc` (radius of
containment, metres) median-by-NIC ladder is clean and monotonic, and it
validates the degraded threshold directly:

| NIC | 11 | 10 | 9 | 8 | 7 | **6** | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| median rc (m) | 8 | 25 | 75 | 186 | 371 | **926** | 1852 | 3704 | 7408 | 18520 | 37040 | 0* |

\* NIC 0 reports carry `rc = 0` — a "containment unknown" sentinel, not a 0-metre
radius. NIC 0 means navigation integrity is unknown/unavailable — the state an
aircraft falls into when GNSS is denied.

**Threshold check:** `nic ≤ 6` ⇒ rc ≳ 926 m (~1 km). This matches the intended
"rc > ~1 km = degraded" rule exactly. NIC 7 (rc < 371 m) and above are healthy.

**ADS-B version distribution:** v2 = 22.09M (91.7%), v0 = 0.905M (3.8%),
v1 = 0.116M (0.5%); a handful of corrupt version values (count 1 each) are
ignored. For the coarse `nic ≤ 6` rule, version differences do not change the
classification; noted for completeness.

**NIC value distribution (airborne):**
`8`→16.09M, `9`→5.63M, `0`→1.23M, `7`→0.55M, `10`→0.37M, `6`→0.13M,
`3`→0.063M, `5,4,2`→~5–6k each, `1`→1k, `11`→14k.
Overall degraded (`nic ≤ 6`) fraction of NIC points: **5.98%**.

## 4. Sanity replication vs known chronic zones
Per-hex `bad_ratio` among hexes with ≥5 unique aircraft:

| Zone | hexes ≥5 ac | max bad_ratio | top-5 |
|---|---|---|---|
| Kaliningrad / Baltic | 121 | **1.00** | 1.0, 1.0, 1.0, 1.0, 1.0 |
| Eastern Med / Cyprus | 181 | 0.67 | 0.67, 0.40, 0.26, 0.25, 0.24 |
| Black Sea | 1 | 1.00 | 1.0 (low coverage — airspace largely avoided) |
| **Central US (quiet control)** | 212 | **0.098** | 0.098, 0.085, 0.083, 0.073, 0.071 |

Chronic zones light up; the quiet control stays dark. The spatial signal is
real and separable from background. **Sanity check passes.** (A visual
cross-check against gpsjam.org for a near date is a Review-column task.)

---

## Decisions & flags carried forward
- **H3 resolution 4 (kept).** 29,686 active hexes/day ⇒ a raw daily JSON of
  ~3 MB uncompressed (measured at build; GitHub Pages serves it gzip-compressed
  in transit, and git packs it small). Res-5 would multiply hex count ~7× and
  blow the size budget with thinner per-hex samples — **rejected for v1.**
  FLAG: confirm the ~3 MB/day (≈1 GB/year) trajectory is acceptable, or adopt a
  coverage floor / array encoding later.
- **`nic ≤ 6` degraded threshold (kept), rc-validated** (~1 km). FLAG: the
  degraded signal is **dominated by nic = 0** (~85% of degraded points). nic = 0
  is the correct "GPS-denied" state and its geography is right (concentrates in
  jamming zones, absent in the quiet control), but the choice to fold
  "integrity unknown" into "degraded" is a methodology decision worth a
  conscious sign-off. `METHODOLOGY.md` documents a sensitivity note (bad_ratio
  with vs without nic = 0).
- **v0 aircraft (3.8%).** NIC on ADS-B v0 is derived differently; at the coarse
  threshold this is immaterial, but flagged in case a later, finer analysis
  wants per-version handling.
- **Confidence tiers** (high ≥10 ac, medium 5–9, insufficient <5) are set from
  the min-aircraft inference rule, not yet empirically tuned — FLAG for
  calibration once multi-day baselines exist.
