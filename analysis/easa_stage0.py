"""
EASA Stage 0 gate (slate project #10): assign the archive to FIRs and count
usable cases. Read-only over committed aggregates; writes one JSON of counts.

    python -m analysis.easa_stage0 FIRS_TXT TABLES_TSV OUT_JSON [CROSSWALK_TSV]

FIRS_TXT   FIR polygons, one feature per line: ``id|oceanic|ring;ring...``
           (lon lat pairs, rings split by '#', polygons by '@'). Derived from
           the VATSIM vatspy-data-project Boundaries.geojson (CC BY-SA 4.0).
           Used in processing only: never committed or redistributed.
TABLES_TSV EASA ranked tables: ``capture  7d|30d  dd/mm/yyyy  CODE[s][r],...``
           (analysis/easa_lists/ranked_tables.tsv; '#' and header lines skipped)
CROSSWALK_TSV optional EASA code -> VATSIM boundary ids
           (analysis/easa_lists/fir_crosswalk.tsv, Stage 1 follow-up)

Definitions are in docs/EASA_STAGE0.md section 1 (set before counting).
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import sys

import h3

from pipeline import config as C, dailyio

STRONG = C.TREND_STRONG_RATIO
FLOOR = C.MIN_AIRCRAFT_FLOOR
HIGH = C.CONFIDENCE_HIGH_MIN
# Gate rule constants (Stage 0 study parameters, from the research file sec. 4).
WIN, K, PRE, PRE_COV = 30, 10, 60, 20

# --- EASA named lists (primary sources; see docs/EASA_STAGE0.md section 2) ---
R1 = "LTBB LTAA LRBB LBSR UGGG UDDD UBBA LCCC OLBB OSTT LLLL OJAC HECC ORBB OIIX HLLL EYVL EPWW EVRR EFIN ENOR".split()
WEB_2024_07_05_ADDED = "LGGG OKAC OBBB LZBB LHCC LUUU EETT ESAA".split()
NAMED = {c: "2023-02-17" for c in R1}
NAMED.update({c: "2024-07-05" for c in WEB_2024_07_05_ADDED})
LAST_STATIC_CAPTURE = "2025-02-17"   # last Wayback capture still showing the static list
FIRST_TABLE = "2025-05-14"           # first ranked table seen (capture 2025-05-20)


# --- polygons ---------------------------------------------------------------
def load_crosswalk(path):
    """EASA code -> VATSIM boundary ids, from analysis/easa_lists/fir_crosswalk.tsv."""
    cw = {}
    for line in open(path, encoding="utf-8"):
        if line.startswith(("#", "easa_code")) or not line.strip():
            continue
        code, ids = line.split("\t")[:2]
        cw[code] = ids.split(",")
    return cw


def load_firs(path, crosswalk=None):
    """Whole-FIR features, with EASA codes in ``crosswalk`` built from the
    listed VATSIM boundaries instead (a listed base id is replaced)."""
    raw = collections.defaultdict(list)
    oce = {}
    for line in open(path, encoding="utf-8"):
        fid, oceanic, body = line.rstrip("\n").split("|", 2)
        for p in body.split("@"):
            rings = [[tuple(map(float, v.split())) for v in r.split(";")] for r in p.split("#")]
            raw[fid].append(rings)
        oce[fid] = oceanic == "1"
    units = {fid: [fid] for fid in raw if "-" not in fid}  # sub-sectors are not whole FIRs
    for code, ids in (crosswalk or {}).items():
        units[code] = ids
    feats = []
    for uid, ids in units.items():
        polys = [p for i in ids for p in raw[i]]
        xs = [x for p in polys for x, _ in p[0]]
        ys = [y for p in polys for _, y in p[0]]
        feats.append(dict(id=uid, oceanic=all(oce[i] for i in ids), polys=polys,
                          bbox=(min(xs), min(ys), max(xs), max(ys)),
                          area=(max(xs) - min(xs)) * (max(ys) - min(ys))))
    return feats


def _in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _in_feat(x, y, f):
    b = f["bbox"]
    if not (b[0] <= x <= b[2] and b[1] <= y <= b[3]):
        return False
    for rings in f["polys"]:
        if _in_ring(x, y, rings[0]) and not any(_in_ring(x, y, h) for h in rings[1:]):
            return True
    return False


class Assigner:
    """Hex -> set of whole-FIR polygons containing it (multi-membership).

    VATSIM polygons overlap in places (e.g. ESOS inside ESAA), so a hex counts
    toward every whole-FIR feature that contains it rather than a single pick.
    """

    def __init__(self, feats):
        self.feats = feats
        self.multi = 0

    def hex(self, hx):
        lat, lon = h3.cell_to_latlng(hx)
        cen = [f for f in self.feats if _in_feat(lon, lat, f)]
        if len(cen) > 1:
            self.multi += 1
        verts = h3.cell_to_boundary(hx)
        inn = [f for f in cen if all(_in_feat(b, a, f) for a, b in verts)]
        return tuple(f["id"] for f in cen), tuple(f["id"] for f in inn)


# --- onset rule -------------------------------------------------------------
def onset(cov: set, hit: set, n_days: int):
    """First persistent hit day (>= K hits in WIN days) and measurability."""
    for c in sorted(hit):
        if sum(1 for x in range(c, c + WIN) if x in hit) >= K:
            pre_clean = sum(1 for x in range(c - PRE, c) if x in cov and x not in hit)
            return c, (c - PRE >= 0 and pre_clean >= PRE_COV), pre_clean
    return None, None, None


def main(firs_txt, tables_tsv, out_json, crosswalk_tsv=None):
    feats = load_firs(firs_txt, load_crosswalk(crosswalk_tsv) if crosswalk_tsv else None)
    A = Assigner(feats)
    paths = dailyio.daily_paths()
    days = [dailyio.day_of(p) for p in paths]
    d0 = dt.date.fromisoformat(days[0])
    cal = [(dt.date.fromisoformat(d) - d0).days for d in days]
    n_days = cal[-1] + 1
    date = lambda c: str(d0 + dt.timedelta(c))  # noqa: E731

    hexfir = {}
    # rule -> fir -> {cov, hit, hicov} day sets
    S = {r: collections.defaultdict(lambda: dict(cov=set(), hit=set(), hicov=set()))
         for r in ("centroid", "interior")}
    hexser = collections.defaultdict(lambda: (set(), set()))  # per-hex, EETT/LUUU only
    for p, c in zip(paths, cal):
        for r in dailyio.read_daily(p):
            if r["n_aircraft"] < FLOOR:
                continue
            hx = r["hex"]
            if hx not in hexfir:
                hexfir[hx] = A.hex(hx)
            cen, inn = hexfir[hx]
            for rule, fir in [("centroid", f) for f in cen] + [("interior", f) for f in inn]:
                s = S[rule][fir]
                s["cov"].add(c)
                if r["n_aircraft"] >= HIGH:
                    s["hicov"].add(c)
                if r["bad_ratio"] >= STRONG:
                    s["hit"].add(c)
            if {"EETT", "LUUU"} & set(cen):
                cov, hit = hexser[hx]
                cov.add(c)
                if r["bad_ratio"] >= STRONG:
                    hit.add(c)

    out = dict(archive=dict(first=days[0], last=days[-1], files=len(days), calendar_days=n_days),
               hexes_assigned=len(hexfir),
               hexes_no_fir=sum(1 for v in hexfir.values() if not v[0]),
               hexes_multi_fir=A.multi, firs={}, hex_level={}, tables=[])

    for rule in ("centroid", "interior"):
        for fir, s in S[rule].items():
            o, meas, pre = onset(s["cov"], s["hit"], n_days)
            rec = out["firs"].setdefault(fir, {})
            pre_named = None
            if fir in NAMED:
                nd = (dt.date.fromisoformat(NAMED[fir]) - d0).days
                pre_named = dict(covered=sum(1 for x in s["cov"] if x < nd),
                                 hit=sum(1 for x in s["hit"] if x < nd))
            rec[rule] = dict(onset=date(o) if o is not None else None, measurable=meas,
                             pre_clean=pre, covered_days=len(s["cov"]), hit_days=len(s["hit"]),
                             before_named=pre_named)
        for fir in out["firs"]:
            out["firs"][fir]["named"] = NAMED.get(fir)

    for hx, (cov, hit) in hexser.items():
        o, meas, pre = onset(cov, hit, n_days)
        if o is None:
            continue
        lat, lon = h3.cell_to_latlng(hx)
        out["hex_level"][hx] = dict(fir=hexfir[hx][0], interior=hexfir[hx][1],
                                    lat=round(lat, 2), lon=round(lon, 2), onset=date(o),
                                    measurable=meas, pre_clean=pre)

    # --- part (b) coverage funnel, per dated table ---------------------------
    feat_ids = {f["id"] for f in feats}
    seen = set()
    for line in open(tables_tsv, encoding="utf-8"):
        if line.startswith(("#", "capture")):
            continue
        cap, win, stamp, codes = line.rstrip("\n").split("\t")
        key = (win, stamp)
        if key in seen:
            continue
        seen.add(key)
        dd, mm, yy = stamp.split("/")
        end = dt.date(int(yy), int(mm), int(dd))
        wl = int(win.rstrip("d"))
        span = {(end - d0).days - k for k in range(wl)}  # wl days ending on the stamp
        in_archive = sum(1 for x in span if 0 <= x < n_days)
        ranked = []
        for i, raw in enumerate(codes.split(","), 1):
            code = raw[:4]
            s = S["centroid"].get(code)
            cov = len(span & s["cov"]) if s else 0
            hic = len(span & s["hicov"]) if s else 0
            ranked.append(dict(rank=i, code=code, polygon=code in feat_ids,
                               cov_days=cov, hicov_days=hic))
        half = wl / 2
        usable = [r for r in ranked if r["polygon"] and r["cov_days"] >= half]
        usable_hi = [r for r in usable if r["hicov_days"] >= half]
        top20 = [r for r in ranked[:20] if r["polygon"] and r["cov_days"] >= half]
        top20_hi = [r for r in top20 if r["hicov_days"] >= half]
        out["tables"].append(dict(
            capture=cap, window=win, stamp=stamp, window_days_in_archive=in_archive,
            listed=len(ranked), unique=len({r["code"] for r in ranked}),
            resolved=sum(1 for r in ranked if r["polygon"]),
            usable=len(usable), usable_high=len(usable_hi),
            top20_usable=len(top20), top20_usable_high=len(top20_hi),
            unresolved=sorted({r["code"] for r in ranked if not r["polygon"]}),
            not_covered=[r["code"] for r in ranked if r["polygon"] and r["cov_days"] < half]))

    json.dump(out, open(out_json, "w"), indent=1)
    print("hexes", len(hexfir), "no-fir", out["hexes_no_fir"], "multi", A.multi)


if __name__ == "__main__":
    main(*sys.argv[1:5])
