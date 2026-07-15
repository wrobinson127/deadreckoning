# CLAUDE.md — DeadReckoning

A longitudinal **GPS/GNSS interference archive** built from open ADS-B data:
stream each UTC day's adsb.lol dump, aggregate aircraft Navigation Integrity
(NIC) per H3 hex, baseline it, and render a scrubbable static map. It is an
instrument, not an accusation — it shows *where navigation integrity degrades*,
with uncertainty shown as a feature.

## Architecture (data flows one way)
```
adsb.lol dump ─► pipeline/ ─► data/ ─► site/ (static MapLibre) ◄─ content/
 (ODbL, raw,     stream+       committed   reads data/ + content/    (regions,
  deleted)       aggregate     aggregates  as static fetches          events)
                                  │
                                  └► baselines.json + regions/*.json + manifest.json
board/  = self-contained kanban (project state, rides git history)
```
- **pipeline/** (Python 3.11+): `config.py` (ALL tunables) · `download.py`
  (resolve+fetch split-tar release, delete after) · `parse.py` (stream tar,
  airborne NIC points + callsign) · `aggregate.py` (per-hex daily + top-N
  affected flights on degraded hexes) · `baselines.py` ·
  `regions.py` (per-region series) · `build_site_data.py` (manifest + yaml→json)
  · `dailyio.py` (the one place the daily storage format lives)
  · `run_daily.py` / `backfill.py` (entrypoints) · `tests/`.
- **data/** — committed **aggregates only**: `daily/YYYY-MM-DD.json.gz`
  (gzipped ~14×; the browser inflates each day via native `DecompressionStream`),
  `baselines.json`, `regions/{id}.json`, `manifest.json`.
- **content/** — `regions.yaml`+`regions.geojson`+`events.yaml`+`airspace.yaml`
  +`airspace.geojson` (authored, draft-flagged); `regions.json`/`events.json`/
  `airspace.json` are generated for the browser. Airspace zones use
  airspace-status language (closed / reduced_coverage / known_test_area), never
  "conflict zone".
- **site/** — buildless: `index.html` (map), `methodology.html`, `about.html`,
  `js/app.js` (+`color.js`), `css/style.css`. Libs via pinned CDN.
- **.github/workflows/** — `ci.yml` (tests, active) · `nightly.yml`
  (fetch→process→commit→deploy, **DORMANT**; see "Going live").

## Conventions that bite
- **All tunables live in `pipeline/config.py`.** No magic numbers elsewhere.
  Changing the NIC threshold, H3 resolution, floors, or baseline window = edit
  that one file.
- **UTC everywhere.** The dumps are UTC days; dates are UTC.
- **Only aggregates are committed.** Raw dumps + extracted traces + anything
  >50 MB are gitignored and deleted after processing. Never commit raw data.
- **Daily files are gzipped; go through `pipeline/dailyio.py`.** Never read/write
  `data/daily/*` directly — the storage format (deterministic gzip, `.json.gz`)
  lives in that one module. `.gitattributes` marks `*.gz binary` (do not remove;
  eol-normalizing a gzip stream corrupts it). **Size gate:** no *bulk* backfill
  until gzip storage is verified live (3 yrs ≈ 3.7 GB raw vs ≈ 260 MB gzipped
  against Pages' ~1 GB guidance).
- **ODbL attribution is required** wherever data is shown: README, site footer,
  methodology page. Code is MIT; published `data/` is ODbL (see `DATA_LICENSE.md`).
- **Honest uncertainty is not optional.** Hexes below `MIN_AIRCRAFT_FLOOR` render
  as hatch, never a value. Keep the no-data vs no-interference distinction.
- **No invented facts.** Region/event content is DRAFT with sources; unsourced
  claims are marked `[NEEDS SOURCE]`, never asserted.
- **Branch workflow:** Walker merges branches to `main` via the GitHub UI. The
  nightly bot commits data to `main` directly (data only).

## Working commands
```bash
pip install -r requirements.txt

python -m pipeline.run_daily 2026-07-13            # one UTC day -> data/daily/
python -m pipeline.backfill 2026-06-30 2026-07-13  # inclusive range (+ derived)
python -m pipeline.backfill --last 14              # most recent 14 days (UTC)
python -m pipeline.baselines                       # recompute data/baselines.json
python -m pipeline.regions                         # recompute region series
python -m pipeline.build_site_data                 # manifest + content json
python -m pytest pipeline/tests -q                 # run the test suite

# serve the site locally (assemble site + data + content into one root):
rm -rf _site && mkdir _site && cp -r site/* _site/ && cp -r data _site/ && cp -r content _site/
python -m http.server -d _site 8777                # http://localhost:8777

python board/apply_delta.py --list                 # board summary
python board/apply_delta.py delta.json             # apply a structured delta
python -m http.server -d board 8001                # view board.html
```
Raw dumps download to a scratch dir (`.scratch/`, or `$DR_SCRATCH`) and are
deleted after each day — keep this off OneDrive-synced paths for big runs.

## Going live (currently private + dormant, by design)
1. Make the repo public. 2. Enable Pages → Source: **GitHub Actions**.
3. Set repo variable **`NIGHTLY_ENABLED=true`** (Settings → Variables → Actions).
The nightly workflow then processes yesterday and deploys. Manual test any time:
Actions → *Nightly build & deploy* → *Run workflow*.

## Depth / pointers
- `DESIGN.md` — the project's visual design truth (tokens, semantic color rules,
  states). Design truth lives here; it wins conflicts with any design skill
  (anti-slop-design law, Taste Skill).
- `docs/verification_report.md` — Phase 0 gate (real measurements, the numbers).
- `docs/METHODOLOGY.md` — NIC, thresholds + sensitivity, limits, the honesty rule.
- `docs/backfill_strategy.md` — expansion plan + size/time budgets.
- `board/kanban_state.json` — project state; open `board/board.html` to view.

## Session discipline
**Before ending any working session, update the board's `last_session` block**
(date · one-paragraph summary · next-step pointer) via `board/apply_delta.py`
with a `last_session` op. It is the "where was I" answer for the next session.
