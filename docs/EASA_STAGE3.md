# EASA warnings against the archive: Stage 3, agreement with EASA's ranking

Slate project #10, Stage 3 ("Part (b)"). The bar and every rule were
registered in `docs/EASA_STAGE3_REGISTRATION.md` at commit `75e1010`
(2026-11-18), before any agreement figure was computed. Run the same day
with `analysis/easa_stage3.py`, unchanged from the registration. $0, no
model calls.

- Per-table results: `docs/easa/stage3_tables.tsv`

## 1. Result against the registered bar: **PASS**

| Scope | Window | Tables counted | Median recall on EASA's top 20 | Range |
|---|---|---|---|---|
| **B, global (primary)** | **30 days** | **20** | **0.942** | 0.824 to 1.0 |
| B, global | 7 days | 19 | 0.933 | 0.765 to 1.0 |
| A, Americas excluded | 30 days | 20 | 1.0 | 0.875 to 1.0 |
| A, Americas excluded | 7 days | 19 | 0.944 | 0.765 to 1.0 |

- **Bar:** a median of at least 0.70 on the primary row. Chance level for the
  primary row is a median of 0.29 (registration, section 6).
- The 7-day table of 15/04/2026 is left out, as registered, because only 12
  of its top 20 are eligible.
- **Plain reading:** where the archive has high-confidence coverage, its own
  FIR ranking puts about 94% of EASA's top 20 inside a list of the same
  length as EASA's table.

## 2. Reported alongside (not part of the bar)

**Precision is about half.** A median of 0.48 (scope B, 30 days) of
DeadReckoning's list appears anywhere in EASA's table, or 0.51 in scope A.
The archive's list also carries FIRs that EASA does not list:
- **Central Europe:** EDXX, EHAA, LKAA, LZBB, EDWW, LHCC, LOVV, EBBU each
  appear in DeadReckoning's list in 32 to 39 of the 40 tables. LZBB and LHCC
  are the Stage 2 reverse cases. EASA named them in 2024; its ranked tables
  do not list them.
- **The Americas (scope B):** KZOA, KZLA, PAZA, KZSE, PHZH, SLLF and KZAB
  take 3 to 10 places in each 30-day list (0 to 10 across all 40). Most
  are US FIRs, the research file's positive controls (US test areas that
  FAA advisories announce), and they show up as they should. SLLF and SAEF (South America) are not
  controls; nothing here explains them.
- **Elsewhere:** HKNA, UKLV, VNSM, EGVV, LLLL and others, less often.

**Rank agreement within EASA's list is weak.** The Spearman correlation
between EASA's rank and the archive's score, over FIRs in both, has a median
of 0.205 on the 30-day tables. It runs from 0.45 in mid-2025 to below zero in
three 2026 tables (15/04, 22/04 and 03/06/2026). The archive finds the same
set of heavily affected FIRs, but orders them differently.

**Misses.** Across the 40 tables (scope B) the archive's list misses an
eligible EASA top-20 FIR 55 times: LTBB Istanbul 21, VTBB Bangkok 12, OEJD
Jeddah 6, HECC Cairo 6, VIDF Delhi 4, LCCC 3, LBSR 2, ORBB 1. In those
tables they sit at ranks 37 to 87 of the archive's ranking.

**Disagreement types: the registered taxonomy does not separate them.** Of
the disagreements, 804 fall in the "cutoff" class (an archive score within
0.05 of the list's last place), 192 in "other" and none in "coverage".
Scores near the cut are packed more tightly than 0.05, so "cutoff" catches
almost everything. This is reported as registered. A narrower band would be
a new registration.

**Not eligible.** EASA top-20 FIRs without high-confidence coverage, so not
in any denominator: ORBB, UNNT, URRV, UATT, UBBA, USSV, UWWW, OPLR, HHAA and
HAAA, in some tables. This is no data, not disagreement.

## 3. What this does and does not mean

- **Shown:** where the open ADS-B archive can see, its FIR-level measure
  recovers nearly all of the FIRs EASA ranks highest. That is outside
  validation at the level of which FIRs are affected.
- **Not shown:** the archive does not reproduce EASA's order (low Spearman).
  Its list also flags FIRs EASA leaves out, especially in central Europe.
  That may be a baseline effect in the archive's measure (aircraft that
  report low NIC for reasons other than interference), or a real difference
  between the two filters (EASA's NIC 7 frontier, its requirement for an
  earlier good signal, its report cross-checks). Stage 3 cannot tell which.
- Agreement is between two related instruments, not against ground truth.
  EASA's method is only partly published.
- No FIR result says who caused any interference.
