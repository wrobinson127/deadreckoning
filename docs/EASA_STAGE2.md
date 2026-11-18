# EASA warnings against the archive: Stage 2, lag and omission

Slate project #10, Stage 2 ("Part (a)") from the research file's stage table:
a lag and never-named table and one strip chart, with every row traced to a
hex series and a dated list. Run 2026-11-18. $0, no model calls.

- Table: `docs/easa/stage2_table.tsv` (one row per FIR, with onset hexes)
- Chart: `docs/easa/stage2_strip.svg`
- Script: `analysis/easa_stage2.py`, over the cache from `analysis/easa_cache.py`
  (archive 2023-02-16 to 2026-11-16, FIR polygons and crosswalk as pinned in
  `docs/EASA_STAGE3_REGISTRATION.md` section 1)

## 1. Rules

The onset rule, hit threshold and floor are Stage 0's (`docs/EASA_STAGE0.md`
section 1). The categories below were coded in the script before it was run.

- **First named:** the earliest date in `analysis/easa_lists/named_lists.tsv`
  (R1 2023-02-17, R2 2023-11-06, web list 2024-07-05).
- **Named FIRs:**
  - *censored*: first named 2023-02-17, day 2 of the archive, so no onset
    before naming can be seen;
  - *positive lag*: measurable onset before first naming;
  - *reverse*: no persistent onset before naming, and covered on at least
    half the archive's days before naming;
  - *no data*: covered on fewer than half those days.
- **Omission candidates:** FIRs never on a named list, with a measurable
  onset before 2025-02-17 (the last capture of the static list). Overlapping
  polygons are deduplicated with the Stage 3 rule, so the UK appears once
  (as VATSIM's EGVV, which is not an ICAO FIR code). FIRs outside EASA's
  apparent scope (the Americas) are kept as positive controls, not
  omissions. The research file's narrower group, "never named by
  2024-07-05", is the subset with onsets before 2024-06-01.
- **Partial-FIR sensitivity:** where the list names only part of a FIR
  ("eastern part of"), the FIR's hexes are split at the mean of their
  centres, and only the hexes on the named side are kept (north, south,
  east, west, or a diagonal for "north-eastern" and similar).
- **Trace:** each row lists the hexes that hit on its onset day, and the
  list it was first named in.

## 2. Results

**Positive lag: 1 FIR, Tallinn (EETT).** Onset 2023-06-13 (centroid rule) or
2023-06-26 (interior rule), both measurable. First named on 2024-07-05: a lag
of **388 days** (375 under the interior rule). The trace starts at the Voru
county hex (Stage 0, section 2.2).

**Reverse cases: 4.** ESAA, LGGG, LHCC and LZBB were each named on
2024-07-05 while covered on most days before, with no persistent onset.
- **ESAA (southern part named):** the southern half alone gives the same
  picture: 503 covered days and 11 hit days before naming, with a persistent
  onset only on 2024-10-25, about 3.5 months after naming.
- **LGGG (eastern part named):** the eastern half has 462 covered days and 6
  hit days before naming, and no onset at any time. The reverse case holds
  under the partial rule.
- **LHCC and LZBB:** 0 hit days before naming; persistent onsets only on
  2026-09-24.

**Insufficient coverage ("no data" rule): 3.** LUUU, OBBB and OKAC were
named on 2024-07-05 with coverage on fewer than half the days before it.
OBBB (32 covered days) and OKAC (46) are no data. LUUU is a partial case: 237
covered days and 26 hit days before naming, short of both the coverage rule
and persistence. It is not a reverse case and not a lag case.

**Censored: 21** (all R1 FIRs). The research file did not plan a lead/lag
reading for these. Their later onsets are in the table for reference only.
In 4 of the 10 that name only a part (EFIN, EVRR, HLLL, OIIX), the named
half gives a different onset from the whole FIR, or none at all. That is one
more reason not to read them as findings.

**Omission candidates in EASA's apparent scope: 11.**

| FIR | Measurable onset (centroid) | Interior rule | First in an EASA ranked table |
|---|---|---|---|
| ULLL (Peterburg sector) | 2023-06-02 | same | 14/05/2025 |
| EGVV (VATSIM UK polygon) | 2023-07-20 | same | never |
| UMMV | 2023-09-30 | same | 14/05/2025 |
| OEJD | 2023-12-08 | 2024-06-09 | 14/05/2025 |
| VIDF | 2023-12-12 | no onset | 14/05/2025 |
| VYYF | 2024-01-07 | 2024-01-25 | 14/05/2025 |
| USSV | 2024-08-18 | 2024-08-19 | 14/05/2025 |
| UMKK (named as a reference point in R1 and R2) | 2024-09-23 | same | 14/05/2025 |
| UWWW | 2024-10-17 | same | 14/05/2025 |
| RKRR | 2024-12-08 | no onset | never |
| VTBB | 2025-02-14 | no onset | 14/05/2025 |

- Six of them (ULLL, EGVV, UMMV, OEJD, VIDF, VYYF) are in the research
  file's "never named by 2024-07-05" group.
- Nine first appear in the first ranked table seen. That date is bounded by
  the capture schedule and by the change of method, so it is not a decision
  date and gives no lag.
- UMKK is not a clean omission. R1 and R2 name the "FIRs surrounding FIR
  Kaliningrad UMKK", so the lists point at it without naming it as affected.
- EGVV and RKRR appear in no EASA list or table. RKRR rests on few hit days
  (21 in the whole archive); EGVV is a VATSIM polygon, not an official FIR.

**Positive controls outside EASA's apparent scope: 6** (KZMP, KZLA, KZLC,
PAZA, KZDV, KZHU), with onsets from 2023-06-11 to 2024-08-08. The method
picks up interference where EASA does not look.

## 3. Not done (open)

- The research plan's comparison group for part (a) (FIRs with similar
  traffic and no persistent interference, as a base rate of naming) was not
  built.

## 4. What this does not show

- The named lists do not state their intended scope. Five of the eleven
  omission candidates are Russian or Belarusian FIRs (ULLL, UMKK, UMMV,
  USSV, UWWW). Their absence from the lists is not shown to be a lag or an oversight.
- A lag is a fact about dates, not a grade on EASA. EASA's naming rests on
  occurrence reports and judgement the archive cannot see.
- The reverse cases may mean EASA's 2024 list drew on reports from before
  ADS-B integrity showed persistent loss. Or the interference was too
  intermittent for the persistence rule. The archive cannot tell these apart.
- No FIR is linked to any actor. FIRs are airspace only.
- The VATSIM polygons for EETT, ESAA, LHCC, LZBB and LGGG still need a
  spot-check against official AIP charts before claim text rests on them.
