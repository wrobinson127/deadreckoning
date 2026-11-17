# EASA warnings against the archive: Stage 1, official lists

Slate project #10, Stage 1 ("Official lists") from the research file's stage
table. Walker's go came through the hub on 2026-11-17. $0, no model calls.
Stage 0 is in `docs/EASA_STAGE0.md`.

**Stage 1 check (research file):** each list re-read against its source by a
second pass; snapshot timestamps recorded. **Met** for every list below.

No agreement, rank or overlap figure was computed. The Stage 3 bar stays
blind until it is registered.

## 1. Files

| File | What it holds |
|---|---|
| `analysis/easa_lists/named_lists.tsv` | 9 dated named lists, 194 rows: one row per FIR, with the "part of" wording kept and the source URL |
| `analysis/easa_lists/ranked_tables.tsv` | 40 EASA ranked tables (20 dates by 7 and 30 days), FIR codes in rank order, with the spoofing and reported flags |

Both hold codes, dates and flags only, not the sources' prose. All sources
were read in the in-app browser on 2026-11-17. PDFs were read as text with
pdf.js, loaded from jsDelivr into a page on the source's own site.

## 2. Named lists

| List | Dated | FIRs | Source |
|---|---|---|---|
| EASA SIB 2022-02R1 | 2023-02-17 (issued) | 21 | EASA PDF |
| EASA SIB 2022-02R2 | 2023-11-06 (issued) | 21 | EASA PDF |
| EASA static web list | 2024-07-05 (SIB R3 issue date; R3 points to the page) | 29 | Wayback capture 2024-07-09 03:47 UTC |
| IATA Safety Risk Assessment V4, copy of EASA list | 2024-09 | 29 | IATA PDF |
| IATA V4, FDX additions | 2024-09 | 12 | same |
| IATA V5 (both parts) | 2025-07 | 29 + 12 | IATA PDF |
| IATA V6 (both parts) | 2026-02 | 29 + 12 | IATA PDF |

**Second pass and what it found:**
- **R1 and R2:** R2's FIR codes, matched by regular expression over the
  whole PDF text, equal its 21 coded rows. R1's list section was read in
  full from the extracted text and gives the same 21 codes. R1 mentions Kaliningrad (UMKK)
  only as a reference point ("FIRs surrounding FIR Kaliningrad UMKK"), so it
  is not coded. R2 differs from R1 in one place: "Northern part of FIR
  Baghdad" becomes "FIR Baghdad".
- **R3 (2024-07-05) and R4 (2026-07-03)** carry no FIR list. Both point to
  the web page. The issue dates and the "revises" chain were re-read in each
  PDF (R4 revises R3 of 2024-07-05).
- **EASA static web list:** the six captures from 2024-07-09 to 2025-02-17
  give the same 29 codes and the same nine "part of" phrases. Compared with
  R2: EYVL and EVRR lose their "part of" wording; EPWW goes from
  north-eastern to eastern; EFIN is named whole, with its northern part also
  listed under the Arctic; ORBB stays whole.
- **IATA V4, V5 and V6** print identical FIR lists. Line by line, the lists
  differ only in spelling ("Capetown" against "Cape town").
- **IATA's copy disagrees with EASA's page in two places.** IATA has
  "Western part of FIR Helsinki EFIN" and "Northern part of FIR Baghdad
  ORBB"; EASA's captured page has EFIN whole and ORBB whole. Stage 2 uses
  EASA's page as the record and treats IATA as a copy.
- **IATA FDX additions** (outside EASA's list): BIRD, "NUUK" (printed as
  given; not an ICAO FIR code), SAEF, SARR, SBBS, SBRE, VIDF, VABF, VYYF,
  ZPKM, FACA, DNKK. These are IATA's FDX observations, not EASA naming.

## 3. Ranked tables

The Wayback index (CDX, collapsed by content) lists 29 captures of the EASA
page, plus the live page on 2026-11-17.

| Captures | Content |
|---|---|
| 20240709034711, 20240709125535, 20240714215733, 20241104022023, 20241114213604, 20250217112045 | Static named list (section 2) |
| 20240901105923 | Redirect, no content |
| 20250520103645 to 20261116103712 (22 captures) | Ranked tables, 19 distinct stamps |
| Live page, read 2026-11-17 | Ranked tables stamped 12/11/2026 |

Three captures repeat an earlier stamp and are not separate rows:
20260310170736 (04/03/2026), 20261108121718 and 20261116103712
(14/10/2026). Their stamps and row counts match the rows kept. Their codes
were not compared separately.

Table stamps: 14/05/2025, 26/06/2025, 30/07/2025, 03/09/2025, 17/09/2025,
24/09/2025, 05/11/2025, 12/11/2025, 10/12/2025, 11/02/2026, 27/02/2026,
04/03/2026, 25/03/2026, 01/04/2026, 15/04/2026, 22/04/2026, 03/06/2026,
07/10/2026, 14/10/2026, 12/11/2026. The gaps run from 5 days to 18 weeks, so the
tables are a sample of EASA's weekly series, not the whole series.

**Second pass:** every row of `ranked_tables.tsv` was rebuilt from the source
HTML by a fresh parse of the page's table elements, and compared by SHA-256
with the stored line. **38 of 38 match** (36 archived plus 2 live). This
closes the Stage 0 caveat that the codes were typed by hand.

**Quirks kept as published:** ULMM appears twice in some 30-day tables
(26/06/2025, 30/07/2025, 03/09/2025, 17/09/2025, 24/09/2025, 11/02/2026,
27/02/2026). The 7-day table of 15/04/2026 lists 19 FIRs. In the captures,
the 2026-11-16 copy still shows 14/10/2026, while the live page read a day
later shows 12/11/2026.

## 4. When the method changed

- Static named list: last seen in the capture of 2025-02-17.
- First ranked table seen: stamp 14/05/2025 (capture 2025-05-20).
- The switch falls between those dates. No capture inside the gap exists,
  and no EASA text found so far dates it.

## 5. Owed to later stages

- A FIR code crosswalk for ULAA, ULKK, ULMM, ULWW and UUYY, which VATSIM
  folds into ULLL sub-sectors (Stage 0, section 2.3), before Stage 3 counts
  them.
- The Stage 3 agreement bar (recall on EASA's top 20, from the research
  file) must be registered in a commit before any agreement figure is run.
- `analysis/easa_stage0.py` still hard-codes the R1 and web-list codes; they
  equal `named_lists.tsv`, and the six static captures parse by machine to
  the same 29 codes. Stage 2 should read the TSV instead.
