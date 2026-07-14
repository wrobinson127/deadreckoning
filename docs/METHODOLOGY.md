# METHODOLOGY

*Draft — technical reference. The site's `methodology.html` is the reader-facing
version; this is the engineering companion. Walker edits voice before publishing.*

## The signal: ADS-B Navigation Integrity Category (NIC)
Every ADS-B–equipped aircraft broadcasts a **NIC** (integer `0`–`11`, DO-260B)
with each position report, paired with a **radius of containment** `rc` (metres).
NIC states how tightly the aircraft can bound its own position error. Under GNSS
interference (jamming or spoofing) receivers can no longer bound that error and
NIC falls, frequently to `0` ("integrity unknown"). Simultaneous low NIC across
many aircraft in one area is the fingerprint of interference there.

Measured `rc`-by-`nic` ladder on the reference day (2026-07-13) confirms the
mapping used for thresholding:

| NIC | 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| median rc (m) | 8 | 25 | 75 | 186 | 371 | **926** | 1852 | 3704 | 7408 | 18520 | 37040 |

## Pipeline
1. **Fetch** one UTC day's open ADS-B dump from adsb.lol (split-tar GitHub
   release; concatenate parts, stream the tar member-by-member — the full day
   never sits in memory).
2. **Filter** to airborne positions (`alt != "ground"`) with valid lat/lon that
   carry a numeric `nic`. Ground and non-positional records are dropped.
3. **Bin** each position to an **H3 resolution-4** cell (~1,770 km²).
4. **Classify** each aircraft in each hex as *degraded* if the **majority** of
   its NIC reports there are `nic ≤ NIC_DEGRADED_MAX` (default **6**).
5. **Aggregate** per hex per day: `n_aircraft` (unique ICAO), `n_reports`,
   `bad_aircraft`, `bad_ratio = bad_aircraft / n_aircraft`, `confidence`.
6. **Baselines**: rolling mean/std of `bad_ratio` per hex; anomaly z-scores are
   derived client-side.

The **aircraft** (not the report) is the unit of "degraded", so one aircraft
with poor reception cannot make a hex look jammed.

All tunables live in `pipeline/config.py`. The current values:

| Constant | Value | Meaning |
|---|---|---|
| `H3_RESOLUTION` | 4 | ~1,770 km²/hex |
| `NIC_DEGRADED_MAX` | 6 | `nic ≤ 6` ⇒ rc ≳ 1 km ⇒ degraded |
| `BAD_AIRCRAFT_MAJORITY` | 0.5 | strictly > half of an aircraft's reports degraded |
| `MIN_AIRCRAFT_FLOOR` | 5 | below this ⇒ "insufficient", never a value |
| `CONFIDENCE_HIGH_MIN` | 10 | ≥10 aircraft ⇒ high; 5–9 ⇒ medium |
| `BASELINE_WINDOW_DAYS` | 28 | rolling baseline window |
| `BASELINE_MIN_DAYS` | 7 | min qualifying days before a baseline exists |
| `BASELINE_STD_FLOOR` | 0.02 | floor on std for z-scores |

## Threshold rationale & sensitivity
`nic ≤ 6` is chosen because NIC 6 ⇒ rc ≈ 926 m (~1 km) — the point at which a
position is too loose to trust. NIC 7+ (rc < ~370 m) is healthy.

**Open calibration note (FLAG).** On the reference day the degraded signal is
**dominated by `nic = 0`** (~85% of all degraded points). Concretely, the
degraded-point fraction is **5.98% including `nic = 0`** but only **0.87%
excluding it** — so the map is largely a `nic = 0` ("integrity unknown") density
surface. That is the expected behavior of GPS denial, and the spatial
distribution is correct (it concentrates in known interference zones —
Baltic/Kaliningrad `bad_ratio` up to 1.0 — and is near-absent over a quiet
control region, central US ~0.10 max). But folding "integrity unknown" into
"degraded" is a deliberate modeling choice, and a reader should know it. Planned:
report `bad_ratio` with and without `nic = 0` as a selectable strict view, and
treat ADS-B v0 aircraft (~3.8% of reports, different NIC derivation) separately.
**Not yet empirically tuned beyond the sanity check.**

## Confidence & the honesty rule (invariant)
Every hex carries its unique-aircraft count and a tier: **high** (≥10),
**medium** (5–9), **insufficient** (<5). Insufficient hexes are never rendered as
a ratio or confident color — on the map they appear as a dim diagonal hatch under
the "coverage" toggle. This makes *no interference* visually distinct from *no
coverage*.

## Baselines & anomaly
Per hex, baseline = mean/std of `bad_ratio` over up to `BASELINE_WINDOW_DAYS`
days on which the hex met the aircraft floor; a hex needs ≥ `BASELINE_MIN_DAYS`
qualifying days before it earns one. Anomaly z = `(bad_ratio − mean) /
max(std, std_floor)`, computed client-side and clamped to the color scale
(±`anomaly_clip`). The baseline uses the window of days *around* each date, which
suits a **retrospective archive** rather than a real-time alarm — documented so
readers don't mistake it for a causal early-warning signal.

## What the instrument cannot see
- **Coverage bias** — signal exists only where aircraft fly and receivers hear
  them; open ocean, closed airspace, and receiver-sparse regions read as
  *no data*, not *no interference*.
- **Equipment / multipath false positives** — suppressed by the multi-aircraft
  rule but never zero; a single anomalous hex is not proof.
- **Cause & attribution** — NIC shows *that* integrity dropped, not *why* or *by
  whom*. Attribution lives only in region profiles, sourced and flagged as draft.
- **Spoofing vs jamming** — v1 measures integrity degradation broadly; separating
  spoofing (false positions) from jamming (lost positions) is future work.

## Time, data, licensing
Everything is **UTC** (source dumps are UTC days). Source data © adsb.lol
feeders and partners, **ODbL 1.0**; published aggregates are a derivative
database, also **ODbL 1.0**; only aggregates are retained (raw deleted after
processing). Code is **MIT**. Basemap © OpenStreetMap contributors via
OpenFreeMap.
