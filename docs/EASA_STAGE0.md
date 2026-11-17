# EASA warnings against the archive: Stage 0 gate

Slate project #10, Stage 0 only. Source plan: the hub research file
`ideas/inbox/2026-11-16_easa-warnings_research.md` (section 4 gate, section 8
stage table). No model calls, $0. This file stops at the gate; Walker rules on
whether to continue.

## 1. Threshold (written and committed before any FIR-level count)

The research file sets no numeric Stage 0 bar. Its Stage 0 check is "Tallinn and
Chisinau confirmed or dropped; N stated per part". Its 0.7 recall bar belongs to
Stage 3 and is not computed here, so that criterion stays blind. Proposed bar:

**Part (a), lag and omission in the named-list phases.** PASS if at least
**1** FIR has a *measurable* persistent onset (definitions below) that falls
before the first date EASA named that FIR, with the FIR assignment done on
polygons, and the case holds under both the centroid rule and the stricter
interior rule. Reverse cases (named while covered and quiet) and "no data" FIRs
are counted and reported but do not count toward the bar.

**Part (b), EASA's region ranking as an outside check.** PASS if
(1) at least **one** EASA ranked table is readable from a dated primary capture
(the live page or a Wayback capture), and
(2) at least **20** of the FIRs in that table resolve to a polygon and have
DeadReckoning coverage at or above the aircraft floor on at least half the days
of the table's window, with at least **15** of EASA's top 20 among them, so that
the Stage 3 recall bar on EASA's top 20 is computable.
Only coverage is counted. No overlap, rank or agreement figure is computed at
Stage 0.

**Overall.** PASS if (b) passes. Part (a) is expected to be 1 or 2 cases and is
reported as PASS or FAIL on its own; a FAIL on (a) alone shrinks the project to
(b) and does not fail the gate.

### Definitions (carried over from the research file, section 4)

- Floor and strong threshold come from `pipeline/config.py`:
  `MIN_AIRCRAFT_FLOOR` (5) and `TREND_STRONG_RATIO` (0.5).
- **Covered day** for a FIR: at least one assigned res-4 hex with
  `n_aircraft >= MIN_AIRCRAFT_FLOOR`.
- **Hit day:** at least one assigned covered hex with `bad_ratio >= 0.5`.
- **Persistent onset:** the first hit day followed by at least 10 hit days in
  the 30 days starting on it.
- **Measurable onset:** the 60 days before onset fall inside the archive and
  include at least 20 covered, non-hit days. Otherwise the onset is
  **censored**: its date is unknown, not early.
- **Centroid rule:** a hex belongs to the FIR containing its centre.
  **Interior rule:** a hex belongs only if all six vertices are inside the FIR.
- **Partial-FIR wording** ("part of FIR X") counts as naming FIR X.

One change after the threshold commit, made before any count was read: the
first run assigned each hex to a single polygon (smallest wins). That dropped
Sweden (ESAA), because VATSIM's ESOS polygon sits inside it. The counts below
use multi-membership instead: a hex counts toward every whole-FIR polygon that
contains its centre (11,754 of 42,668 hexes sit in more than one). The bar
itself did not change.

## 2. Result: **PASS** (part a PASS, part b PASS)

Run 2026-11-17 on the archive 2023-02-16 to 2026-11-16 (1,364 daily files).
Script: `analysis/easa_stage0.py`. 42,668 res-4 hexes have at least one
covered day; 47 fall in no FIR polygon.

### 2.1 Sources

| Record | Source, how read | What it holds |
|---|---|---|
| SIB 2022-02R1, 2023-02-17 | EASA PDF, read by the research agent (research file sec. 2) | 21 FIRs, several as parts |
| SIB 2022-02R2, 2023-11-06 | EASA PDF, same | Same FIRs as R1 (Baghdad widened) |
| Static web list dated 2024-07-05 | **Wayback capture 2024-07-09 03:47 UTC, read here** (primary; the research file had only secondary copies) | R1 plus LGGG (east), OKAC, OBBB, LZBB, LHCC, LUUU, EETT, ESAA (south). EFIN whole plus its north; ORBB whole |
| Same static list, unchanged | Wayback captures 2024-07-09 (two), 2024-07-14, 2024-11-04, 2024-11-14, 2025-02-17 | Identical FIR list in all six |
| Ranked tables (7 and 30 days) | Wayback captures 2025-05-20 to 2026-11-16 (22 captures), plus the live page read 2026-11-17 | 20 distinct table dates, 14/05/2025 to 12/11/2026, so 40 tables |
| FIR polygons | VATSIM vatspy-data-project `Boundaries.geojson` (CC BY-SA 4.0), read in the in-app browser 2026-11-17, rounded to 0.01 deg | Whole-FIR features only (ids without a sector suffix). Processing only: not committed, not redistributed |

All outside pages were read with the in-app browser. The Wayback index for
the page (CDX, collapsed by content) lists 29 captures from 2024-07-09 to
2026-11-16; one is a redirect.

**Correction to the brief.** The ranked table did not start in October 2026.
The last capture with the static list is 2025-02-17; the first with a ranked
table is 2025-05-20, stamped 14/05/2025. The switch falls in that window. The
exact date is not known.

### 2.2 Part (a): lag and omission in the named-list phase. **PASS, N = 1**

The named-list phase runs from R1 (2023-02-17) to the switch (after
2025-02-17, by 2025-05-14).

**Positive lag (onset measurable, before first naming): 1 FIR.**

| FIR | Rule | Archive onset | Clean covered days in the 60 before | First named | Lag |
|---|---|---|---|---|---|
| EETT Tallinn | centroid | 2023-06-13 | 60 | 2024-07-05 | 388 days |
| EETT Tallinn | interior | 2023-06-26 | 56 | 2024-07-05 | 375 days |

- Before 2024-07-05 the FIR had 502 covered days, 263 of them hit days (245
  under the interior rule).
- The first hex with its own measurable onset is at 57.89 N, 26.83 E (Voru
  county), 2023-06-26, wholly inside EETT. The centroid-rule date is earlier
  because border hexes near Lake Peipus have centres inside the polygon.
- R2 (2023-11-06) came 133 to 146 days after onset and did not add EETT.
- The case holds under both rules. The research file's range of 8 to 12
  months becomes about 12.5 months at FIR level.

**Chisinau (LUUU): dropped.** Its only persistent onset is 2026-01-19 and is
not measurable (2 clean covered days before it). No hex lies wholly inside the
LUUU polygon, so the interior rule has nothing to test. Before 2024-07-05 it
had 237 covered days and 26 hit days, short of persistence.

**R1 and R2 FIRs (21): censored.** R1 was issued one day after the archive
starts, so none can show an onset before naming.

**Reverse cases (named 2024-07-05 while covered, no persistent onset before):
4.** These do not count toward the bar.

| FIR | Covered days before 2024-07-05 | Hit days | Later persistent onset (centroid / interior) |
|---|---|---|---|
| ESAA Sweden (southern part named) | 503 | 14 | 2024-10-25 / 2024-11-15 |
| LHCC Budapest | 497 | 0 | 2026-09-24 / none |
| LZBB Bratislava | 482 | 0 | 2026-09-24 / 2026-09-24 |
| LGGG Athinai (eastern part named) | 497 | 6 | none / none |

LGGG is scored on the whole FIR, but only its eastern part was named, so the
partial-FIR sensitivity run (Stage 2) decides whether it stays.

**No data, not reverse cases:** OKAC Kuwait (46 covered days before naming)
and OBBB Bahrain (32). These stay "no data".

**Omission candidates** (measurable onset before 2025-02-17, never on the
static list), among the FIRs EASA's tables later carry: ULLL, UMMV, OEJD,
VYYF, USSV, UMKK and UWWW hold under both rules (onsets 2023-06-02 to
2024-10-17); VIDF and VTBB hold under the centroid rule only. Each first
appears in the first ranked table seen (14/05/2025), so its "naming" date is
bounded by the capture schedule and by the change of method, not by a
decision to warn. Three UK polygons (EGTT, EGVV, EGTM; onset 2023-07-20) show
a measurable onset and appear in no EASA list or table. These are candidates
for Stage 2, not findings: ULLL's VATSIM polygon absorbs five neighbouring
FIRs (see 2.3), and the UK polygons overlap.

### 2.3 Part (b): EASA's ranked tables as an outside check. **PASS**

Usable means the FIR resolves to a polygon and DeadReckoning has at least one
hex at or above the floor on at least half the window's days. High means the
same with at least `CONFIDENCE_HIGH_MIN` (10) aircraft in a hex. Windows are
the 7 or 30 days ending on the table's stamp; the archive covers every window
in full. No agreement figure was computed.

Funnel for the current table (live page, stamped 12/11/2026):

| Window | Listed | Polygon | Usable | High | Top 20 usable (high) |
|---|---|---|---|---|---|
| 7 days | 40 | 38 | 28 | 28 | 19 (19) |
| 30 days | 48 | 44 | 30 | 30 | 17 (17) |

Across all 40 tables, usable FIRs range from 23 to 35 and top-20 usable from
16 to 20, in every table but one. The exception is the 7-day table of
15/04/2026, which lists only 19 FIRs (11 usable). **39 of 40 tables meet the
bar** (at least 20 usable, at least 15 of the top 20).

Not covered in the current 30-day table (no data, not disagreement): USSV,
UWWW, URRV, UATT, HSSS, UIII, UHHH, OAKX, HHAA, UACN, USTV, UNKL, HCSM, HAAA.
These are interior Russia, Central Asia and the Horn of Africa, where the
adsb.lol feeder network is thin.

**Codes with no whole-FIR polygon (8 across all tables):** ULAA, ULKK, ULMM,
ULWW, UUYY (VATSIM folds these into ULLL sub-sectors) and ZBPE, ZSHA, ZYSH
(China, rare in the tables). Stage 1 needs a crosswalk for the five Russian
codes, or ULLL and its neighbours leave the agreement count.

## 3. What this does not show

- No agreement or rank figure was computed; Stage 3's recall bar on EASA's
  top 20 stays blind.
- A lag is a fact about dates, not a grade on EASA. EASA's naming also rests
  on occurrence reports and judgement the archive cannot see.
- Nothing here says who caused any interference. FIRs are airspace only.
- VATSIM polygons are simulator data. The FIRs that carry a finding (EETT,
  ESAA, LHCC, LZBB, LGGG) need a spot-check against official AIP charts.
- "Covered" at FIR level means at least one hex at the floor. For large FIRs
  this is lenient; Stage 3 should also report the share of hexes covered.

## 4. Proposed next step (Walker's ruling)

Continue to Stage 1 on the narrowed scope, with (b) as the main body and (a)
as one dated case (Tallinn) plus four reverse cases and the omission
candidates. The Wayback series is richer than the research file assumed (40
dated tables, not 8 captures of unknown content), so much of Stage 1 is done:
the tables are parsed and kept outside the repo, in the session notes folder.
