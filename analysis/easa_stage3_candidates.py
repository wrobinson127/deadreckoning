"""
EASA Stage 3 candidate set and chance recall (coverage only; reads no
bad_ratio, so the Stage 3 agreement bar stays blind).

    python -m analysis.easa_stage3_candidates FIRS_TXT CROSSWALK_TSV OUT_JSON

Rules are in docs/EASA_STAGE3_REGISTRATION.md section 2.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import sys

from pipeline import config as C, dailyio

from analysis.easa_stage0 import Assigner, load_crosswalk, load_firs

LISTS = "analysis/easa_lists/"
AMERICAS = tuple("CKMPST")
OVERLAP_MAX = 0.5


def easa_codes():
    codes = set()
    for line in open(LISTS + "ranked_tables.tsv", encoding="utf-8"):
        if line.startswith(("#", "capture")):
            continue
        codes |= {c[:4] for c in line.rstrip("\n").split("\t")[3].split(",")}
    for line in open(LISTS + "named_lists.tsv", encoding="utf-8"):
        if not line.startswith(("#", "list_id")):
            codes.add(line.split("\t")[2])
    return codes


def tables():
    out = []
    for line in open(LISTS + "ranked_tables.tsv", encoding="utf-8"):
        if line.startswith(("#", "capture")):
            continue
        cap, win, stamp, codes = line.rstrip("\n").split("\t")
        out.append((win, stamp, [c[:4] for c in codes.split(",")]))
    return out


def in_scope(f):
    if len(f["id"]) == 4:
        return not f["id"].startswith(AMERICAS)
    cx = (f["bbox"][0] + f["bbox"][2]) / 2
    return cx >= -30


def main(firs_txt, crosswalk_tsv, out_json):
    feats = load_firs(firs_txt, load_crosswalk(crosswalk_tsv))
    byid = {f["id"]: f for f in feats}
    A = Assigner(feats)
    E = easa_codes()
    paths = dailyio.daily_paths()
    d0 = dt.date.fromisoformat(dailyio.day_of(paths[0]))
    hexfir, hexes = {}, collections.defaultdict(set)
    hicov = collections.defaultdict(set)
    for p in paths:
        c = (dt.date.fromisoformat(dailyio.day_of(p)) - d0).days
        for r in dailyio.read_daily(p):
            if r["n_aircraft"] < C.MIN_AIRCRAFT_FLOOR:
                continue
            hx = r["hex"]
            if hx not in hexfir:
                hexfir[hx] = A.hex(hx)[0]
            for fir in hexfir[hx]:
                hexes[fir].add(hx)
                if r["n_aircraft"] >= C.CONFIDENCE_HIGH_MIN:
                    hicov[fir].add(c)

    # Dedupe: EASA codes are kept first; other polygons, largest first, are
    # kept only if at most half their covered hexes lie in polygons kept so far.
    kept, taken, dropped = [], set(), []
    order = sorted(hexes, key=lambda f: (f not in E, -len(hexes[f]), f))
    for f in order:
        share = len(hexes[f] & taken) / len(hexes[f])
        if f in E or share <= OVERLAP_MAX:
            kept.append(f)
            taken |= hexes[f]
        else:
            dropped.append(f)

    res = []
    for win, stamp, codes in tables():
        dd, mm, yy = stamp.split("/")
        end = (dt.date(int(yy), int(mm), int(dd)) - d0).days
        w = int(win.rstrip("d"))
        span = set(range(end - w + 1, end + 1))
        elig = [f for f in kept if len(span & hicov[f]) >= w / 2]
        prim = [f for f in elig if in_scope(byid[f])]
        n = len(set(codes))
        top20 = list(dict.fromkeys(codes))[:20]
        res.append(dict(window=win, stamp=stamp, N_unique=n,
                        candidates_primary=len(prim), candidates_global=len(elig),
                        chance_primary=round(min(1, n / len(prim)), 2) if prim else None,
                        chance_global=round(min(1, n / len(elig)), 2) if elig else None,
                        top20_eligible=sum(1 for c in top20 if c in elig)))
    json.dump(dict(polygons_with_coverage=len(hexes), kept=len(kept), dropped=sorted(dropped),
                   tables=res), open(out_json, "w"), indent=1)
    print(len(hexes), len(kept), len(dropped))


if __name__ == "__main__":
    main(*sys.argv[1:4])
