"""
EASA Stage 3: agreement between DeadReckoning's FIR ranking and EASA's ranked
tables, exactly as registered in docs/EASA_STAGE3_REGISTRATION.md (commit
75e1010, 2026-11-18). Do not change a rule here without a new registration
commit.

    python -m analysis.easa_stage3 FIRS_TXT CROSSWALK_TSV CACHE_NPZ OUT_JSON
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import statistics
import sys

import numpy as np

from pipeline import config as C

from analysis.easa_stage0 import load_crosswalk, load_firs
from analysis.easa_stage3_candidates import OVERLAP_MAX, easa_codes, in_scope, tables

BAR = 0.70
MIN_ELIG_TOP20 = 15
CUTOFF_BAND = 0.05
TOP = 20


def spearman(x, y):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    if len(x) < 3:
        return None
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(num / den, 3) if den else None


def main(firs_txt, crosswalk_tsv, cache_npz, out_json):
    feats = {f["id"]: f for f in load_firs(firs_txt, load_crosswalk(crosswalk_tsv))}
    z = np.load(cache_npz)
    N, B = z["N"].astype(np.int64), z["B"].astype(np.int64)
    d0 = dt.date.fromisoformat(str(z["d0"]))
    cen = json.loads(str(z["cen"]))
    members = collections.defaultdict(list)
    for h, firs in enumerate(cen):
        for f in firs:
            members[f].append(h)
    E = easa_codes()

    # candidate dedupe (registration sec. 2 item 4; same rule as easa_stage3_candidates)
    hexes = {f: set(hs) for f, hs in members.items()}
    kept, taken = [], set()
    for f in sorted(hexes, key=lambda f: (f not in E, -len(hexes[f]), f)):
        if f in E or len(hexes[f] & taken) / len(hexes[f]) <= OVERLAP_MAX:
            kept.append(f)
            taken |= hexes[f]

    sn = {f: N[members[f]].sum(0) for f in kept}
    sb = {f: B[members[f]].sum(0) for f in kept}
    hic = {f: (N[members[f]] >= C.CONFIDENCE_HIGH_MIN).any(0) for f in kept}

    results = []
    for win, stamp, codes in tables():
        dd, mm, yy = stamp.split("/")
        end = (dt.date(int(yy), int(mm), int(dd)) - d0).days
        w = int(win.rstrip("d"))
        span = slice(end - w + 1, end + 1)
        score, elig, cov_d, hic_d = {}, set(), {}, {}
        for f in kept:
            n, b = sn[f][span], sb[f][span]
            c = n > 0
            cov_d[f], hic_d[f] = int(c.sum()), int(hic[f][span].sum())
            if c.any():
                score[f] = float((b[c] / n[c]).mean())
            if hic_d[f] >= w / 2 and f in score:
                elig.add(f)
        uniq = list(dict.fromkeys(codes))
        n_list = len(uniq)
        top = uniq[:TOP]
        row = dict(window=win, stamp=stamp, N=n_list)
        for scope in ("B", "A"):
            pool = [f for f in elig if scope == "B" or in_scope(feats[f])]
            ranked = sorted(pool, key=lambda f: (-score[f], f))
            dr = ranked[:n_list]
            drs = set(dr)
            cut = score[dr[-1]] if dr else None
            et = [c for c in top if c in elig]
            hit = [c for c in et if c in drs]
            both = [c for c in uniq if c in elig]
            def kind(f):
                if hic_d[f] < 0.5 * cov_d[f]:
                    return "coverage"
                if cut is not None and abs(score[f] - cut) <= CUTOFF_BAND:
                    return "cutoff"
                return "other"
            row[scope] = dict(
                candidates=len(pool), eligible_top20=len(et),
                counts=len(et) >= MIN_ELIG_TOP20,
                recall=round(len(hit) / len(et), 3) if et else None,
                precision=round(len(drs & set(uniq)) / n_list, 3),
                spearman=spearman([uniq.index(c) + 1 for c in both], [-score[c] for c in both]),
                missed=[(c, kind(c), round(score[c], 3), ranked.index(c) + 1) for c in et if c not in drs],
                extra=[(f, kind(f), round(score[f], 3)) for f in dr if f not in set(uniq)],
                americas_in_list=[f for f in dr if not in_scope(feats[f])],
                not_eligible_top20=[c for c in top if c not in elig],
                cut=round(cut, 4) if cut is not None else None)
        results.append(row)

    summ = {}
    for scope in ("B", "A"):
        for win in ("30d", "7d"):
            rs = [r[scope]["recall"] for r in results if r["window"] == win and r[scope]["counts"]]
            summ[f"{scope}_{win}"] = dict(n_tables=len(rs), median_recall=round(statistics.median(rs), 3),
                                         min=min(rs), max=max(rs))
    primary = summ["B_30d"]["median_recall"]
    out = dict(registered_commit="75e1010", bar=BAR, primary_median_recall=primary,
               verdict="PASS" if primary >= BAR else "FAIL", summary=summ,
               candidates_kept=len(kept), tables=results)
    json.dump(out, open(out_json, "w"), indent=1)
    print(out["verdict"], primary, json.dumps(summ))


if __name__ == "__main__":
    main(*sys.argv[1:5])
