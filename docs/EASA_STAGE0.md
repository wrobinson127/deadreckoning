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

One change after the threshold commit, made after the first run's counts had
been read: that run assigned each hex to a single polygon (smallest wins),
which dropped Sweden (ESAA), because VATSIM's ESOS polygon sits inside it. The
counts below use multi-membership instead: a hex counts toward every
whole-FIR polygon that contains its centre (11,754 of 42,668 hexes sit in
more than one). The bar did not change, and the verdict is the same under
either assignment: the first run also met (b) in 39 of 40 tables (usable
minimum 21, top-20 minimum 15; live 30-day table 29 usable, 17 of the top
20), and gave identical EETT onsets.

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
- The interference starts in one hex wholly inside EETT, at 57.89 N,
  26.83 E (Voru county): hit days 2023-06-13, 14, 16, 17, 26 and 27. Its own
  hex-level onset is 2023-06-26. The centroid-rule FIR onset is 2023-06-13
  because two border hexes (58.16 N 27.29 E and 57.62 N 26.37 E, centres
  inside EETT) add hit days on 06-28 to 06-30, bringing the 30-day count from
  06-13 to 10. No EETT hex hits before 06-13 that month.
- R2 (2023-11-06) came 133 to 146 days after onset and did not add EETT.
- The case holds under both rules. The research file's range of 8 to 12
  months becomes about 12.5 months at FIR level.

**Chisinau (LUUU): dropped.** Its only persistent onset is 2026-01-19 and is
not measurable (2 clean covered days before it). Hexes wholly inside LUUU
exist (8 in a grid test) but had no covered day before 2024-07-05 (97 covered
days in the whole archive, 1 hit day), so the interior rule has nothing to
test. Under the centroid rule it had 237 covered days and 26 hit days before
2024-07-05, short of persistence.

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
for Stage 2, not findings: the UK polygons overlap, and ULLL was first scored
on VATSIM's whole ULLL (see 2.4 for the Peterburg-sector rerun).

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

### 2.4 Rerun with the FIR crosswalk (added 2026-11-18)

`analysis/easa_lists/fir_crosswalk.tsv` maps the 8 codes that had no
whole-FIR polygon, plus ULLL, to VATSIM sectors by their names in VATSpy.dat. EASA's
ULLL now means VATSIM's Peterburg sector (ULLL-R) only, not the whole
VATSIM ULLL, which also contains the Arkhangelsk, Murmansk, Kotlas, Vologda,
Syktyvkar, Naryan-Mar and oceanic sectors. Command: as above, with the
crosswalk as a fourth argument.

- **Every EASA code now resolves to a polygon.** The verdict is unchanged:
  **39 of 40 tables** meet the (b) bar. Usable FIRs range from 24 to 36 and
  top-20 usable from 16 to 20 (the 15/04/2026 7-day table aside: 12 and 12).
  Current 30-day table: 48 listed, 48 resolve, 30 usable, 17 of the top 20.
- **Part (a) is unchanged.** EETT, ESAA, LHCC, LZBB, LGGG and LUUU give
  identical onsets and counts under both rules.
- **ULLL (Peterburg sector only)** keeps its measurable onset of 2023-06-02,
  so it stays an omission candidate.
- **The five northern Russian codes** are mostly no data: ULKK has no covered
  day at all, ULAA 58, ULWW 148, ULMM 173 (onset 2023-07-30, not measurable)
  and UUYY 281 (no hit days).

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
dated tables, not 8 captures of unknown content). The tables are parsed once
and kept outside the repo, in the session notes folder. Row counts match the
browser's parse for all 40 tables, but the FIR codes were transcribed by hand
and still owe the second-pass re-read that Stage 1 requires.

The onset-rule constants (30-day window, 10 hit days, 60-day lookback, 20
clean days) live in `analysis/easa_stage0.py`, not `pipeline/config.py`: they
are study parameters for this gate, not pipeline tunables.
