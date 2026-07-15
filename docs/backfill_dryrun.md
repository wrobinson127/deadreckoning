# Backfill format dry-run (2026-07-16)

Converts the bulk backfill from assumption to plan. This run validated the
**release resolution** per historical year (the cheap, high-signal part: does the
release exist, with the expected tag pattern and tar-part structure). The full
**parse validation** (trace format, NIC density, known zones lighting up)
requires actually downloading + processing a day and is documented below as the
ready-to-run remaining step — deliberately not executed tonight because it is
~2-4 GB per day and the backfill gate stands.

## Resolution check (GitHub releases API only, no download)
Ran `pipeline.download.resolve_release(day)` for one sample day per year:

| Year | Sample day | Resolves? | Tag | Tar parts | Total size |
|---|---|---|---|---|---|
| 2023 | 2023-07-13 | **NO** | — | — | — |
| 2024 | 2024-07-13 | yes | `v2024.07.13-planes-readsb-prod-0` | 2 (`.tar.aa/.ab`) | ~2.25 GB |
| 2025 | 2025-07-13 | yes | `v2025.07.13-planes-readsb-prod-0` | 2 (`.tar.aa/.ab`) | ~3.29 GB |
| 2026 (ref) | 2026-07-13 | yes | `v2026.07.13-planes-readsb-prod-0` | 2 (`.tar.aa/.ab`) | ~3.96 GB |

## Findings / format drift
- **2024–2026 are consistent** with the production build's assumptions: the same
  `vYYYY.MM.DD-planes-readsb-prod-0` tag pattern and a 2-part split tar. The
  resolver + downloader should work unchanged for these years.
- **Day size grows over time** (2.25 → 3.29 → 3.96 GB/day). Update the backfill
  budget: older years are cheaper to transfer. A weekly-sampled 2024–2026 pull is
  meaningfully smaller than assuming ~4 GB/day throughout.
- **2023 does NOT resolve** through the current config. adsb.lol publishes history
  in **per-year repositories** (`adsblol/globe_history_2023`, `…2024`, `…2025`,
  `…2026`); the current release-repo config resolves the recent years but not
  2023. **Adaptation needed before any 2023 backfill (describe, do not implement
  tonight):** parameterize the release repo by the day's year so 2023 days query
  `globe_history_2023`, then confirm the 2023 tag pattern (it may predate the
  `-planes-readsb-prod-0` naming; check the actual 2023 release tags before
  assuming). Until verified, treat 2023 as unproven.

## Remaining step (ready to run, NOT run tonight — gate stands)
For one real day per resolvable year (2024, 2025), off OneDrive scratch, no commit:
```bash
DR_SCRATCH=/c/Users/wrobi/.dr_scratch python -m pipeline.run_daily 2024-07-13
DR_SCRATCH=/c/Users/wrobi/.dr_scratch python -m pipeline.run_daily 2025-07-13
# then, do NOT commit; inspect the produced data/daily/<day>.json.gz:
#  - trace format parsed (record count in the tens of thousands of hexes)
#  - NIC-field density comparable to the 2026 reference (~29.7k cells)
#  - known zones light up (Baltic/Kaliningrad bad_ratio high; central US ~quiet)
#  - then delete the outputs (git checkout / rm) — the gate stands until live-verified
```
Per-year parser adaptations, if the parse reveals drift, get described here and
implemented in a later approved batch — never silently.

## Bottom line for the backfill plan
- Recent-90-days + weekly-sampled **2024–2026**: green to plan on (standard format,
  known sizes). Start here after the live-verify gate clears.
- **2023**: blocked on the per-year-repo adaptation + a tag-pattern confirmation.
  Do the 2023 resolution fix as its own small task before including 2023 days.
