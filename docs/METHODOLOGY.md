# METHODOLOGY — engineering notes

**The canonical methodology is the live site page: `site/methodology.html`** (the
reader-facing essay plus its "Full specifications" section). That page is now the
source of truth for how the signal is computed, the thresholds and their
sensitivity, the honesty rules, the sensor-desert paradox, validation, and what
the instrument can and cannot see. Do not re-narrate any of that here — edit the
page.

This file is a thin engineering companion. It keeps only the internal,
config-level detail that is intentionally **not** surfaced on the public page.

## Tunable constants
Authoritative source is `pipeline/config.py` (all tunables live there, by
convention — nothing downstream hard-codes a threshold). Current values, for
quick reference:

| Constant | Value | Meaning |
|---|---|---|
| `H3_RESOLUTION` | 4 | ~1,770 km²/hex |
| `NIC_DEGRADED_MAX` | 6 | `nic ≤ 6` ⇒ rc ≳ 1 km ⇒ degraded |
| `BAD_AIRCRAFT_MAJORITY` | 0.5 | strictly > half of an aircraft's reports degraded ⇒ bad |
| `MIN_AIRCRAFT_FLOOR` | 5 | below this ⇒ "insufficient", never a value/color |
| `CONFIDENCE_HIGH_MIN` / `CONFIDENCE_MEDIUM_MIN` | 10 / 5 | ≥10 ⇒ high; 5–9 ⇒ medium; <5 ⇒ insufficient |
| `BASELINE_WINDOW_DAYS` | 28 | rolling baseline window |
| `BASELINE_MIN_DAYS` | 7 | min qualifying days before a hex earns a baseline |
| `BASELINE_STD_FLOOR` | 0.02 | floor on std for z-scores (in `bad_ratio` units) |
| `FLIGHTS_TOP_N` / `FLIGHTS_MIN_BAD_RATIO` | 10 / 0.5 | affected-flights cap and the hex ratio that earns the list |

## rc-by-NIC ladder (full; reference day 2026-07-13)
The public page shows this down to NIC 3; the full measured ladder:

| NIC | 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| median rc (m) | 8 | 25 | 75 | 186 | 371 | **926** | 1852 | 3704 | 7408 | 18520 | 37040 |

## Affected-flights artifact schema (per degraded hex)
A hex at/above `FLIGHTS_MIN_BAD_RATIO` that also meets the aircraft floor carries
up to `FLIGHTS_TOP_N` of the aircraft counted degraded there, highest first, each
as `{ic, cs, t0, t1, nd}`: ICAO address, public callsign, first/last
degraded-report time (UTC seconds), and number of degraded reports. Attached only
to hexes that already render as interference, so the added artifact size stays
small (~15%/day) and quiet/corridor hexes are byte-for-byte unchanged. Callsigns
and ICAO addresses are public ADS-B broadcast data (see the live page).

## Anomaly z-score (computed client-side)
`z = (bad_ratio − mean) / max(std, BASELINE_STD_FLOOR)`, clamped to the color
scale (`±anomaly_clip`). Baseline uses the window of days around each date — a
retrospective-archive baseline, not a real-time alarm.

## ADS-B version note
v0 aircraft (~3.8% of reports on the reference day, with a different NIC
derivation) are treated with the same coarse `≤ 6` rule; their small share is
noted rather than special-cased.

---
*History: this file previously held the full methodology narrative. That content
now lives on `site/methodology.html` (canonical) and was not dropped — it was
relocated to the page. Only the engineering-internal notes above remain here.*
