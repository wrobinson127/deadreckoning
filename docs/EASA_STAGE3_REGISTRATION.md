# EASA Stage 3: agreement bar (REGISTERED)

**Status: REGISTERED 2026-11-18.** Walker approved the bar and chose scope
B (global) as primary, via the hub, on 2026-11-18 ("yes go all of this" to
the three #10 defaults). The registering commit is the one that adds this
line (`git log --diff-filter=M -S "REGISTERED 2026-11-18" -- docs/EASA_STAGE3_REGISTRATION.md`).
No agreement, rank or overlap figure was computed on any data before that
commit. If anything below changes after results are seen, the change gets its
own commit, and both versions' results are reported.

Source of the bar: the hub research file, section 5 (Part b): "recall of at
least 0.7 on EASA's top 20 in FIRs where DeadReckoning has high-confidence
coverage". This draft fixes every term that sentence leaves open.

## 1. Inputs (pinned before registration)

- EASA tables: `analysis/easa_lists/ranked_tables.tsv`, 20 dates, each with
  a 7-day and a 30-day table (Stage 1, hash-checked).
- FIR polygons: VATSIM vatspy-data-project `Boundaries.geojson` at commit
  `bb3440861eeaadb0ae6d6f0a98e96d000f01af3c` (last change to the file,
  2026-11-02; read 2026-11-17), whole-FIR features, rounded to 0.01 degree.
  The derived file is not committed (CC BY-SA 4.0). It is kept in the
  project's session notes as `easa-warnings_vatspy_firs.txt`, SHA-256
  `21e04822b98d6df07e038c13e1567c1d37a3ce8edb5a9baeefccd5ac056d2095`.
  `analysis/easa_lists/fir_crosswalk.tsv` maps the 8 codes with no
  whole-FIR polygon, plus ULLL, to VATSIM sectors. A hex belongs to every
  polygon containing its centre (Stage 0 rule).
- Archive: `data/daily/*.json.gz`, read through `pipeline/dailyio.py`, with
  `MIN_AIRCRAFT_FLOOR` (5), `CONFIDENCE_HIGH_MIN` (10) and the degraded rule
  NIC <= `NIC_DEGRADED_MAX` (6) taken from `pipeline/config.py` unchanged.

## 2. DeadReckoning's FIR score (fixed before any run)

For a FIR F and a table with window W (7 or 30) ending on the table's stamp
date D (days D-W+1 to D, as in Stage 0):

1. **Daily value** on day d: sum of `bad_aircraft` over F's hexes with
   `n_aircraft >= 5`, divided by the sum of their `n_aircraft`. This mirrors
   EASA's stated "ratio of aircraft having a bad NIC to all the aircraft of
   the day". An aircraft seen in two hexes counts twice; the archive has no
   per-FIR unique-aircraft count.
2. **Window score:** mean of the daily values over the window's covered days
   (EASA: "daily analysis ... averaged across" 7 or 30 days).
3. **Eligible:** F has at least one hex with `n_aircraft >= 10` on at least
   half the window's days (4 of 7, 15 of 30). This is the "high-confidence
   coverage" in the bar. Ineligible FIRs are reported as "no data", never as
   disagreement.
4. **Candidates (dedupe).** VATSIM polygons overlap (for example ESOS inside
   ESAA, LTAA inside LTXX, ZBAA inside the crosswalked ZBPE, the three UK
   polygons). Every code in any EASA list or table is kept first. Every
   other polygon with covered hexes is then taken, largest first, and kept
   only if at most half its covered hexes already lie in kept polygons.
   Script: `analysis/easa_stage3_candidates.py` (coverage only).
5. **DeadReckoning's list for the table:** eligible candidates ranked by
   window score, highest first; ties broken by FIR code. Its length N is the
   number of unique codes in that EASA table (ULMM is listed twice in some
   30-day tables).
6. **Scope: B (global) is primary; A is reported as secondary** (Walker,
   2026-11-18).
   - *Option A, EASA's apparent scope (secondary):* drop candidates whose 4-letter code
     starts with C, K, M, P, S or T, or (for non-ICAO VATSIM ids) whose
     bounding-box centre lies west of 30 W. No EASA table has listed an FIR
     in the Americas.
   - *Option B, global (primary):* keep every candidate.
   - Disclosure: Option A was written after the Stage 0 output had shown
     US FIRs (KZMP, KZLA, KZLC, PAZA, KZDV, KZHU) with measurable onsets
     that no EASA list carries. Under Option B those FIRs compete for
     DeadReckoning's N slots, which lowers recall on EASA's top 20 if they
     score high. The other option is reported either way.

Chance level: if DeadReckoning's list were drawn at random from the
eligible candidates, expected recall would be N divided by the number of
candidates. Section 6 gives those counts per table (coverage only), so the
0.70 bar can be read against chance.

## 3. The bar

- **Recall for one table:** take EASA's top 20 for that table, keep those
  that are eligible (denominator); the share of them that appear in
  DeadReckoning's list of length N (numerator).
- **Primary statistic:** the median recall over the 20 thirty-day tables, in scope B (global).
- **PASS** if the primary statistic is **at least 0.70**. Otherwise FAIL, and
  the disagreements are the finding (research file sec. 5).
- **Minimum denominator:** a table counts only if at least 15 of its top 20
  are eligible. Tables that fall short are listed and left out of the median.
  (Stage 0 found 16 to 20 eligible-at-floor in every table but one; the
  high-confidence count may be lower, and is reported.)

## 4. Reported alongside, not part of the bar

- The same recall for the 20 seven-day tables, and for scope A.
- Precision: the share of DeadReckoning's list that appears anywhere in
  EASA's table.
- Spearman rank correlation between EASA rank and DeadReckoning score over
  FIRs that are both eligible and in EASA's table.
- Per-table lists of disagreements, each sorted into one of:
  - **coverage**: in one list, eligible but with fewer than 10 aircraft on
    most covered days;
  - **cutoff**: EASA calls NIC 7 the frontier between good and bad, while
    the archive counts NIC <= 6 as degraded. The archive cannot be re-run at
    NIC <= 7 without the raw dumps, so this category is assigned by rule:
    FIRs whose archive score is within 0.05 of the list cut;
  - **other**: everything else, including EASA's report cross-checks and its
    requirement that an aircraft first broadcast a good signal, which the
    archive does not apply.
- Positive controls: US FIRs with known test areas, in the global run only.

## 5. Already seen before this draft (disclosure)

Stage 0 and its reruns showed, per FIR: covered days, hit days at the
strong threshold (`bad_ratio >= 0.5`), persistent onsets, and which EASA
codes are not covered in each table. They did not compute any window score,
ranking or overlap with EASA's tables. Hit days are related to the window
score, so a reader of Stage 0 could guess at parts of the result; the bar
above was not tuned to any such guess.

## 6. Candidate counts and chance recall (coverage only)

Run 2026-11-18 with `analysis/easa_stage3_candidates.py`. 375 polygons have covered hexes; the dedupe keeps 225 and drops 150. The dropped ones include VATSIM aggregates (BAIRES, UKR), sub-FIR duplicates (ESOS, ESMM, LTXX, LLPT, LLSC), and some real FIR codes that sit mostly inside a larger kept polygon (for example EDGG, EDMM, LDZO, LYBA, EGTT, EGTM). No code from an EASA list or table is ever dropped.

"Eligible top 20" counts EASA top-20 codes with high-confidence coverage (the recall denominator).

| 30-day table | N (unique codes) | Candidates A | Candidates B | Chance A | Chance B | Eligible top 20 |
|---|---|---|---|---|---|---|
| 14/05/2025 | 43 | 114 | 166 | 0.38 | 0.26 | 16 |
| 26/06/2025 | 54 | 117 | 168 | 0.46 | 0.32 | 18 |
| 30/07/2025 | 52 | 123 | 174 | 0.42 | 0.30 | 17 |
| 03/09/2025 | 48 | 121 | 174 | 0.40 | 0.28 | 16 |
| 17/09/2025 | 50 | 120 | 173 | 0.42 | 0.29 | 17 |
| 24/09/2025 | 48 | 120 | 172 | 0.40 | 0.28 | 17 |
| 05/11/2025 | 50 | 121 | 173 | 0.41 | 0.29 | 19 |
| 12/11/2025 | 54 | 121 | 175 | 0.45 | 0.31 | 19 |
| 10/12/2025 | 55 | 123 | 176 | 0.45 | 0.31 | 17 |
| 11/02/2026 | 54 | 119 | 169 | 0.45 | 0.32 | 15 |
| 27/02/2026 | 51 | 119 | 171 | 0.43 | 0.30 | 18 |
| 04/03/2026 | 49 | 119 | 172 | 0.41 | 0.28 | 18 |
| 25/03/2026 | 58 | 115 | 167 | 0.50 | 0.35 | 18 |
| 01/04/2026 | 58 | 114 | 167 | 0.51 | 0.35 | 18 |
| 15/04/2026 | 52 | 118 | 172 | 0.44 | 0.30 | 19 |
| 22/04/2026 | 49 | 118 | 171 | 0.42 | 0.29 | 18 |
| 03/06/2026 | 54 | 120 | 170 | 0.45 | 0.32 | 19 |
| 07/10/2026 | 52 | 133 | 186 | 0.39 | 0.28 | 17 |
| 14/10/2026 | 50 | 131 | 184 | 0.38 | 0.27 | 17 |
| 12/11/2026 | 48 | 133 | 188 | 0.36 | 0.26 | 17 |

Median chance recall over the 30-day tables: 0.42 (A), 0.29 (B), against the 0.70 bar. Every 30-day table has at least 15 eligible top-20 codes, so all 20 count toward the median.

Seven-day tables: chance 0.15 to 0.45 (A), 0.11 to 0.31 (B); eligible top 20 from 12 to 19. The 15/04/2026 table (12 eligible) falls below the minimum of 15 and would be left out.

## 7. What a result will and will not mean

- PASS means the archive's FIR ranking recovers most of EASA's top 20 where
  the archive can see. It does not validate hex-level detail.
- EASA's method is only partly published (thresholds such as "representative
  number of aircraft movements" are not given). Agreement is between two
  related instruments, not against ground truth.
- No FIR result says who caused any interference.
