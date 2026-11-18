# EASA Stage 3: agreement bar (DRAFT, not yet registered)

**Status: DRAFT for Walker's OK.** It becomes the registration when Walker
approves it and a commit changes this line to "REGISTERED <date>, commit
<sha>". No agreement, rank or overlap figure has been computed on any data
before that commit. If anything below changes after results are seen, the
change gets its own commit, and both versions' results are reported.

Source of the bar: the hub research file, section 5 (Part b): "recall of at
least 0.7 on EASA's top 20 in FIRs where DeadReckoning has high-confidence
coverage". This draft fixes every term that sentence leaves open.

## 1. Inputs (all committed before registration)

- EASA tables: `analysis/easa_lists/ranked_tables.tsv`, 20 dates, each with
  a 7-day and a 30-day table (Stage 1, hash-checked).
- FIR polygons: VATSIM `Boundaries.geojson` whole-FIR features, with
  `analysis/easa_lists/fir_crosswalk.tsv` for the 9 codes that have no
  whole-FIR polygon. A hex belongs to every FIR polygon containing its centre
  (Stage 0 rule).
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
4. **DeadReckoning's list for the table:** eligible FIRs ranked by window
   score, highest first; ties broken by FIR code. Its length N equals the
   number of rows in that EASA table.
5. **Scope:** primary run excludes FIRs whose code starts with C, K, M, P, S
   or T (the Americas and the US Pacific), because no EASA table has listed
   an FIR there. A secondary run keeps every FIR worldwide.

## 3. The bar

- **Recall for one table:** take EASA's top 20 for that table, keep those
  that are eligible (denominator); the share of them that appear in
  DeadReckoning's list of length N (numerator).
- **Primary statistic:** the median recall over the 20 thirty-day tables.
- **PASS** if the primary statistic is **at least 0.70**. Otherwise FAIL, and
  the disagreements are the finding (research file sec. 5).
- **Minimum denominator:** a table counts only if at least 15 of its top 20
  are eligible. Tables that fall short are listed and left out of the median.
  (Stage 0 found 16 to 20 eligible-at-floor in every table but one; the
  high-confidence count may be lower, and is reported.)

## 4. Reported alongside, not part of the bar

- The same recall for the 20 seven-day tables, and for the global scope.
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

## 5. What a result will and will not mean

- PASS means the archive's FIR ranking recovers most of EASA's top 20 where
  the archive can see. It does not validate hex-level detail.
- EASA's method is only partly published (thresholds such as "representative
  number of aircraft movements" are not given). Agreement is between two
  related instruments, not against ground truth.
- No FIR result says who caused any interference.
