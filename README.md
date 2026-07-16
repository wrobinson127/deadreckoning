# DEAD RECKONING: a GPS interference archive

> *Dead reckoning* is how you navigate when GPS is denied: from last known
> position, heading, and speed. The name is the thesis.

A longitudinal instrument for **GPS/GNSS interference**, built entirely from open
ADS-B data. Aircraft broadcast a Navigation Integrity Category (**NIC**) alongside
each position. When many aircraft in one area simultaneously report degraded
integrity, that indicates GNSS interference in that airspace.

Live tools already show *current* conditions (GPSJam, Flightradar24's jamming
map, SkAI's spoofing tracker). **None has memory.** This project is the memory:
a scrubbable archive (seeded with a rolling recent window and built to grow
toward multi-year) with per-hex baselines, anomaly scoring, named watch regions
with analyst context, and curated event annotations. (Archive depth today is
whatever has been backfilled; see `data/manifest.json`.)

**This is an instrument, not an accusation.** It shows *where navigation
integrity degrades*, with honest uncertainty. It does not assert "jamming by X":
attribution of cause lives only in region context profiles, with sources.

---

## What it shows
- A world map of H3 hexes colored by **anomaly score** (deviation from each
  hex's own rolling baseline), with a toggle to raw degraded-aircraft ratio.
- A **date scrubber** with play, spanning the available archive.
- **Honest uncertainty as a feature**: every hex carries sample counts and a
  confidence tier. Low-sample hexes render visibly distinct: you can always
  tell "no interference" from "no coverage."
- **Named regions** (Baltic, Black Sea, Eastern Mediterranean, Persian Gulf, …)
  with analyst context profiles and 90-day trends.
- A **timeline** of sourced events (strikes, exercises, incidents) as pins.

## Method, in one paragraph
For each UTC day we stream that day's adsb.lol dump, keep airborne positions
carrying a NIC value, and aggregate per H3 hex: an aircraft is "degraded" in a
hex if the majority of its NIC reports there are `nic ≤ 6` (containment radius
> ~1 km). A hex's `bad_ratio` is degraded aircraft ÷ unique aircraft. Hexes below
a minimum-aircraft floor are shown as *insufficient data*, never as a value.
Interference is inferred from **multiple proximate aircraft**, not single
reports. Full detail, thresholds, and their sensitivity: **`docs/METHODOLOGY.md`**.

## Architecture
```
adsb.lol dump ──► pipeline/ ──► data/ ──► site/ (static, MapLibre)
  (ODbL, raw,      stream-parse   committed    reads data/ + content/
   deleted after)  aggregate      aggregates   as static fetches
                   baselines      only
content/ (regions.yaml, events.yaml, geojson) ─┘
```
- `pipeline/`: Python. `config.py` holds **all** tunables. `run_daily.py`
  processes one UTC day → `data/daily/YYYY-MM-DD.json`; `backfill.py` a range;
  `baselines.py` recomputes `data/baselines.json` + per-region series.
- `data/`: committed **aggregates only**. Never raw traces (see `.gitignore`).
- `content/`: named regions + curated events (sourced analyst layer).
- `site/`: buildless static frontend (MapLibre GL JS, h3-js, D3).
- `.github/workflows/`: `ci.yml` (tests) and `nightly.yml` (fetch→process→
  deploy; **dormant until the repo is made public + Pages enabled**).

## Run it
```bash
pip install -r requirements.txt
python -m pipeline.run_daily 2026-07-13          # process one UTC day
python -m pipeline.backfill 2026-06-30 2026-07-13 # process a date range
python -m pipeline.baselines                       # recompute baselines + regions
python -m pytest pipeline/tests -q                 # run tests
python -m http.server -d site 8000                 # serve the site locally
```
See `CLAUDE.md` for the full command reference and conventions.

## Data, licensing & attribution
- **Source:** [adsb.lol](https://www.adsb.lol) daily dumps
  ([globe_history_2026](https://github.com/adsblol/globe_history_2026)), **ODbL 1.0**.
- **Code:** MIT (`LICENSE`). **Published data** under `data/`: **ODbL 1.0**
  (`DATA_LICENSE.md`): a derivative database of adsb.lol.
- **Basemap:** [OpenFreeMap](https://openfreemap.org) / © OpenStreetMap
  contributors, ODbL.
- **$0 to run:** static site + GitHub Actions + flat files. No paid APIs, no
  servers, no databases. v1 makes zero LLM calls.

## Author
Built by **Walker Robinson**. [walker-robinson.com](https://walker-robinson.com) · [github.com/wrobinson127](https://github.com/wrobinson127)

*Region context profiles and event annotations are analyst interpretation:
sourced, and labeled as such, not measurement.*
