"""
DeadReckoning — central configuration.

ALL tunable constants live here. Nothing downstream (parse/aggregate/baselines/
regions/frontend-data) should hard-code a threshold. This is a hard convention:
if you find yourself typing a magic number elsewhere, it belongs in this file.

Values chosen in Phase 0 are documented in docs/verification_report.md and
docs/METHODOLOGY.md, including their sensitivity. Every choice here that lacks a
strong empirical basis is a FLAG_FOR_REVIEW item in the self-audit.
"""

from __future__ import annotations

# --- Spatial aggregation -----------------------------------------------------
# H3 resolution for daily aggregation. res 4 ~ 1770 km^2 average hex area
# (edge ~22 km). Handoff default; res 5 (~252 km^2) considered only if the
# sample day shows it fits the per-day size budget — decision gate, not silent.
H3_RESOLUTION = 4

# --- NIC / integrity thresholds ----------------------------------------------
# Navigation Integrity Category scale is 0..11 (DO-260B). Lower NIC => larger
# containment radius (rc) => worse position integrity. GNSS interference drives
# NIC down. A report is "degraded" when nic <= NIC_DEGRADED_MAX.
# Default nic <= 6 corresponds to rc > ~1 km (NIC 7 => rc < 370 m; NIC 6 =>
# rc < 1111 m). Calibrated against the Phase 0 sample day so chronic zones read
# and quiet zones stay quiet. See METHODOLOGY.md for sensitivity.
NIC_DEGRADED_MAX = 6

# NIC is only meaningful when present. Reports with nic == None are ignored for
# the degraded/clean tally (they still may count toward coverage elsewhere).
# ADS-B version handling: NIC semantics are effectively consistent for our
# coarse "<=6 is degraded" rule across versions 0/1/2, but we record the version
# distribution in Phase 0 and note any anomalies. Version 0 nic is derived from
# the "type code" and is treated identically for this coarse threshold.

# --- Per-aircraft classification within a hex --------------------------------
# An aircraft is counted "bad" in a hex if the MAJORITY of its degraded-eligible
# reports in that hex are degraded (nic <= NIC_DEGRADED_MAX). This is the
# aircraft-level, not report-level, unit — one jet lingering does not dominate.
BAD_AIRCRAFT_MAJORITY = 0.5  # strictly greater-than this fraction => bad

# --- Affected-flights schema (per degraded hex) ------------------------------
# A degraded hex carries up to FLIGHTS_TOP_N of the aircraft that were counted
# "bad" there (majority-degraded), each as {ic, cs, t0, t1, nd}: ICAO, public
# callsign, first/last degraded-report unix-seconds, and #degraded reports.
# Attached ONLY to hexes at/above FLIGHTS_MIN_BAD_RATIO that also meet the
# aircraft floor — this bounds the size to the visually significant hexes and
# keeps quiet/corridor hexes byte-for-byte unchanged. Callsigns are public ADS-B
# broadcast data (see docs/METHODOLOGY.md).
FLIGHTS_TOP_N = 10
FLIGHTS_MIN_BAD_RATIO = 0.5

# --- Minimum-sample guard ----------------------------------------------------
# Hexes with fewer than this many unique aircraft render as "insufficient data"
# and NEVER as a ratio/color. This structurally encodes the FR24 inference rule:
# interference is inferred from MULTIPLE proximate aircraft, not single reports.
MIN_AIRCRAFT_FLOOR = 5

# --- Confidence tiers (by unique aircraft count in hex) -----------------------
# Calibrated on the sample day; documented in METHODOLOGY.md.
CONFIDENCE_HIGH_MIN = 10   # >= 10 unique aircraft
CONFIDENCE_MEDIUM_MIN = 5  # 5..9 ; below MIN_AIRCRAFT_FLOOR => "insufficient"


def confidence_tier(n_aircraft: int) -> str:
    """Map unique-aircraft count to a confidence tier string."""
    if n_aircraft >= CONFIDENCE_HIGH_MIN:
        return "high"
    if n_aircraft >= CONFIDENCE_MEDIUM_MIN:
        return "medium"
    return "insufficient"


# --- Baselines & anomaly -----------------------------------------------------
# Rolling window (days) for per-hex baseline mean/std of bad_ratio.
BASELINE_WINDOW_DAYS = 28
# Minimum days of history required before a baseline (and thus anomaly score) is
# emitted for a hex; below this the hex has no anomaly, only raw bad_ratio.
BASELINE_MIN_DAYS = 7
# Floor on std when computing z-scores, to avoid divide-by-tiny on very stable
# hexes (in bad_ratio units, i.e. 0..1).
BASELINE_STD_FLOOR = 0.02

# --- Parsing / filtering -----------------------------------------------------
# Valid latitude/longitude bounds; anything outside is dropped as corrupt.
LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0

# Ground positions are excluded: readsb encodes them as the string "ground" at
# point index 3. Airborne positions carry a numeric altitude.
GROUND_ALT_SENTINEL = "ground"

# Point array indices (readsb trace format; see wiedehopf README-json.md).
IDX_SECONDS = 0
IDX_LAT = 1
IDX_LON = 2
IDX_ALT = 3
IDX_GS = 4
IDX_TRACK = 5
IDX_FLAGS = 6
IDX_VRATE = 7
IDX_DETAIL = 8  # aircraft detail object or null; carries nic/rc/version/...

# --- Time --------------------------------------------------------------------
# Everything is UTC. adsb.lol dumps are UTC days. State this everywhere.
TIMEZONE = "UTC"

# --- Data source -------------------------------------------------------------
# adsb.lol daily dumps published as split-tar GitHub releases (ODbL 1.0).
GHIST_REPO_TEMPLATE = "adsblol/globe_history_{year}"
RELEASE_TAG_TEMPLATE = "v{date}-planes-readsb-prod-0"   # date as YYYY.MM.DD
RELEASE_STAGING_TEMPLATE = "v{date}-planes-readsb-staging-0"
# Reassembly: concatenate .tar.aa + .tar.ab (+...) then untar. The 2023 archive
# ships a single .tar (no split) — download._select_parts handles both eras.

# Bulk-backfill disk guard: a single day's raw dump peaks at ~4 GB (2026) and is
# deleted immediately after that day aggregates, so scratch never holds more than
# one day. The backfill loop pauses (and flags) before starting a day if free
# space on the scratch volume drops below this floor, rather than filling the disk.
MIN_FREE_DISK_GB = 15

# --- Output ------------------------------------------------------------------
# Daily aggregates are stored gzip-compressed (~13x smaller). This is a hard
# size gate for bulk backfill: 3 years uncompressed ~ 3.7 GB vs ~260 MB gzipped,
# against GitHub Pages' ~1 GB guidance. The browser decompresses client-side via
# native DecompressionStream (no library). All pipeline I/O goes through
# pipeline/dailyio.py so the storage format lives in exactly one place.
DAILY_TEMPLATE = "data/daily/{date}.json.gz"  # date as YYYY-MM-DD
GZIP_LEVEL = 9                                 # max ratio; artifacts are write-once
BASELINES_JSON = "data/baselines.json"         # small, singular — left uncompressed
REGION_SERIES_TEMPLATE = "data/regions/{region_id}.json"
