# Backfill Strategy

All estimates below use the **measured** Phase 0 figures for one UTC day
(2026-07-13) on the reference machine — see `verification_report.md`:

| Quantity | Measured |
|---|---|
| Download (2 prod tar parts) | **3.96 GB / day** |
| Stream-parse + aggregate | **~4–6.5 min / day** (1 core) |
| Peak RSS | 785 MB |
| Output aggregate (uncompressed) | **3.36 MB / day** |
| Output aggregate (gzipped) | **0.24 MB / day** |

Processing is CPU/IO-light; **the wall-clock cost of a large backfill is
dominated by download bandwidth**, not compute.

## Tonight's scope (done)
The **14 most recent days** (2026-06-30 … 2026-07-13), processed via
`python -m pipeline.backfill 2026-06-30 2026-07-13`. This seeds enough history
for per-hex baselines to begin forming (the baseline needs ≥7 qualifying days).

## Planned expansion (runs later, on local hardware — NOT tonight)
Ordered by analytic value:

1. **Recent 90 days.** Establishes a full rolling-baseline window for every hex
   with coverage.
   - Storage: 90 × 3.36 MB ≈ **300 MB** uncompressed (≈ 22 MB gzipped).
   - Download: 90 × 3.96 GB ≈ **356 GB** transferred (raw parts deleted after
     each day; peak disk stays ~4–8 GB).
   - Time: download-bound; at ~30 MB/s ≈ 3–4 h transfer + ~7–10 h compute,
     easily chunked/resumable (idempotent: existing days are skipped).

2. **Event windows.** For each entry in `content/events.yaml`, backfill a ±7-day
   window so the timeline has context around documented incidents. ~15 events ×
   ~15 days ≈ 225 days (minus overlaps with the 90-day set).

3. **Weekly-sampled 2023–2026.** One representative day per week across the
   `globe_history_2023/2024/2025/2026` releases (~4 yr × 52 ≈ **208 days**) for
   the long-view trend without the storage cost of every day.
   - Storage: 208 × 3.36 MB ≈ **700 MB** uncompressed (≈ 50 MB gzipped).

## Repo-size guardrail (important)
At **3.36 MB/day uncompressed**, a full *daily* year is ≈ **1.2 GB** — at
GitHub's ~1 GB soft repo guidance and the 100 MB/file hard limit is never
approached (per-file is 3.36 MB). Mitigations, in order of preference:
- **Weekly sampling** for the deep multi-year fill (above) keeps totals modest.
- If dense multi-year daily coverage is later desired, **commit gzipped**
  (`data/daily/*.json.gz`, ~0.24 MB/day → ~90 MB/yr) and have the frontend
  fetch/inflate, or move bulk history to a release asset / separate data branch.
  A `GZIP_DAILY` flag already exists in `pipeline/config.py` for this switch.

## Operational invariants
- **All dates are UTC.** The dumps are UTC days.
- **Idempotent & resumable.** `backfill.py` skips days already present (unless
  `--force`); a failed day is logged and the range continues.
- **Actions does one day at a time** (the nightly job); **bulk runs locally**.
- **Only aggregates are committed.** Raw parts are downloaded to a scratch dir
  and deleted immediately after each day.
- Recompute of `baselines.json` + region series + site data happens once at the
  end of a backfill run (`backfill.py` derived step), not per day.
