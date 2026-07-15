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

**`nic = 0` is folded into "degraded" — by design.** On the reference day the
degraded signal is **dominated by `nic = 0`** (~85% of all degraded points),
which makes the physical rationale the load-bearing one: NIC 0 ("integrity
unknown") is the *expected signature of a receiver under interference that cannot
compute an integrity bound at all*. Excluding it would discard the strongest,
most characteristic evidence of GPS denial and leave only the milder "degraded
but still reporting" cases. The spatial evidence supports inclusion — with
`nic = 0` in, the surface concentrates in known interference zones
(Baltic/Kaliningrad `bad_ratio` up to 1.0) and stays near-absent over a quiet
control (central US ~0.10 max), which is the behavior we would demand of a real
interference signal, not of an artifact.

**Documented sensitivity band (reference day 2026-07-13).** Because the choice is
consequential, the with/without figures are kept on the record: the degraded-point
fraction is **5.98% including `nic = 0`** vs **0.87% excluding it**. These are
sample-day figures, not recomputed per render; treat them as the calibrated order
of magnitude. A per-hex *strict* view (`bad_ratio` excluding `nic = 0`) is a
planned UI toggle so a reader can see the band directly — deferred, not dropped.
ADS-B v0 aircraft (~3.8% of reports, different NIC derivation) are treated with
the same coarse `≤ 6` rule; their small share is noted rather than special-cased.

## Confidence & the honesty rule (invariant)
Every hex carries its unique-aircraft count and a tier: **high** (≥10),
**medium** (5–9), **insufficient** (<5). Insufficient hexes are never rendered as
a ratio or confident color — on the map they appear as a dim diagonal hatch (the
"Low-sample cells" toggle). This makes *no interference* visually distinct from
*no coverage*.

**Showing coverage matters** because absence of signal is only meaningful where
presence of monitoring is shown: a dark cell could mean "watched and calm" or
"nobody was looking," and those are opposite claims. So measured-but-quiet hexes
(tier ≥ medium, low degraded ratio) render as a faint "watched airspace" carpet
(the "Quiet coverage" toggle, on by default) — distinct from the near-black of
genuine no-data. The carpet is deliberately a whisper: it must never compete with
a real bloom.

## Affected flights (per degraded hex)
Significant hexes (`bad_ratio ≥ FLIGHTS_MIN_BAD_RATIO`, meeting the aircraft
floor) carry up to `FLIGHTS_TOP_N` of the aircraft counted degraded there:
`{ic, cs, t0, t1, nd}` = ICAO address, callsign, first/last degraded-report time
(UTC seconds), and number of degraded reports, highest first. **Privacy:**
callsigns and ICAO addresses are **public ADS-B broadcast data**, transmitted in
the clear by every aircraft and already redistributed by adsb.lol under ODbL;
DeadReckoning surfaces a bounded top-N per interference hex (click a degraded
cell on the map to see its affected-aircraft list), not tracking. The
list is attached only to hexes that already render as interference, which keeps
the added artifact size small (~15% per day) and leaves quiet/corridor hexes
unchanged.

## Baselines & anomaly
Per hex, baseline = mean/std of `bad_ratio` over up to `BASELINE_WINDOW_DAYS`
days on which the hex met the aircraft floor; a hex needs ≥ `BASELINE_MIN_DAYS`
qualifying days before it earns one. Anomaly z = `(bad_ratio − mean) /
max(std, std_floor)`, computed client-side and clamped to the color scale
(±`anomaly_clip`). The baseline uses the window of days *around* each date, which
suits a **retrospective archive** rather than a real-time alarm — documented so
readers don't mistake it for a causal early-warning signal.

## The sensor-desert paradox
The instrument measures interference **where civil aircraft fly**, which is
systematically **not** the airspace that is closed or avoided. When airspace is
closed or widely avoided the sky empties and the sensors leave with the traffic —
so the worst jamming can sit inside a **dark zone that means "nobody was looking,"
not "all clear."** We measure the *edges* of such airspace, not its interior. The
overlay describes the instrument's blindness (an airspace-status fact), not the
reasons behind it.

The **Airspace context** overlay (on by default) exists to keep that honest: it
outlines airspace that is `closed` (e.g., Ukraine, closed to civil traffic since
Feb 2022) or of `reduced_coverage` (e.g., Russia, widely avoided by Western
carriers and thin on volunteer receivers), plus `known_test_area` ranges where
GPS testing is recurring and announced. It renders as a violet dashed outline
with a faint wash — a hue never used for the signal ramp — so a reader can never
mistake *absence of data* for *absence of jamming*. Each zone card leads with the
regulatory fact ("closed to civil aviation since …") and its source. Zone polygons
are drawn from Natural Earth boundaries and are context, not precise FIR geometry
(see `content/airspace.yaml`).

**Not every dark cell is a zone.** Oceanic and remote-region darkness reflects
**terrestrial ADS-B receiver range** (roughly 250 nm offshore before line-of-sight
runs out) and volunteer-receiver sparsity — *not* airspace status. The
traffic-density **Coverage** view is the honest instrument for reading where the
sensors are; the zone layer is reserved for regulatory / conflict causes only. So
a dark ocean or an empty stretch of central Asia is a coverage fact, not a closed
zone — do not zone the Atlantic.

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
