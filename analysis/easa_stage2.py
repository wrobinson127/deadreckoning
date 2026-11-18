"""
EASA Stage 2, part (a): lag and omission table for the named-list phase,
partial-FIR sensitivity, a trace for every row, and one strip chart.

    python -m analysis.easa_stage2 FIRS_TXT CROSSWALK_TSV CACHE_NPZ OUT_DIR

Writes OUT_DIR/stage2.json, OUT_DIR/stage2_table.tsv and
OUT_DIR/stage2_strip.svg. Rules are in docs/EASA_STAGE2.md section 1; the
onset rule and hit threshold are Stage 0's (docs/EASA_STAGE0.md section 1).
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import sys

import h3
import numpy as np

from pipeline import config as C

from analysis.easa_stage0 import load_crosswalk, load_firs, onset
from analysis.easa_stage3_candidates import OVERLAP_MAX, easa_codes, in_scope, tables

LISTS = "analysis/easa_lists/"
STATIC_END = "2025-02-17"      # last capture with the static list
NEVER_BY = "2024-07-05"        # research file: "never named by 2024-07-05"
NEVER_ONSET_BEFORE = "2024-06-01"
DIRS = {"northern": (0, 1), "southern": (0, -1), "eastern": (1, 0), "western": (-1, 0),
        "northeastern": (1, 1), "north-eastern": (1, 1), "northwestern": (-1, 1),
        "north-western": (-1, 1), "southwestern": (-1, -1), "south-western": (-1, -1),
        "southeastern": (1, -1), "south-eastern": (1, -1)}


def named_lists():
    """fir -> (first named date, list id, part wording at first naming)."""
    first = {}
    for line in open(LISTS + "named_lists.tsv", encoding="utf-8"):
        if line.startswith(("#", "list_id")):
            continue
        lid, dated, fir, part = line.rstrip("\n").split("\t")[:4]
        if fir not in first or dated < first[fir][0]:
            first[fir] = (dated, lid, part)
    return first


def first_table():
    out = {}
    for win, stamp, codes in tables():
        d = "-".join(reversed(stamp.split("/")))
        for c in set(codes):
            out[c] = min(out.get(c, "9"), d)
    return out


def main(firs_txt, crosswalk_tsv, cache_npz, out_dir):
    feats = {f["id"]: f for f in load_firs(firs_txt, load_crosswalk(crosswalk_tsv))}
    z = np.load(cache_npz)
    N, B = z["N"], z["B"]
    hexes = [str(h) for h in z["hexes"]]
    d0 = dt.date.fromisoformat(str(z["d0"]))
    nd = N.shape[1]
    day = lambda s: (dt.date.fromisoformat(s) - d0).days  # noqa: E731
    date = lambda c: str(d0 + dt.timedelta(int(c)))  # noqa: E731
    cov = N >= C.MIN_AIRCRAFT_FLOOR
    hit = cov & (B.astype(np.float32) >= C.TREND_STRONG_RATIO * N.astype(np.float32))
    cen = json.loads(str(z["cen"]))
    inn = json.loads(str(z["inn"]))
    mem = {"centroid": collections.defaultdict(list), "interior": collections.defaultdict(list)}
    for h in range(len(hexes)):
        for f in cen[h]:
            mem["centroid"][f].append(h)
        for f in inn[h]:
            mem["interior"][f].append(h)
    E = easa_codes()
    named = named_lists()
    ftab = first_table()

    # dedupe, as registered for Stage 3, so overlapping polygons are not double-counted
    hs = {f: set(v) for f, v in mem["centroid"].items()}
    kept, taken = [], set()
    for f in sorted(hs, key=lambda f: (f not in E, -len(hs[f]), f)):
        if f in E or len(hs[f] & taken) / len(hs[f]) <= OVERLAP_MAX:
            kept.append(f)
            taken |= hs[f]

    def fir_onset(idx):
        if not idx:
            return None, None, None, set(), set()
        c = set(np.nonzero(cov[idx].any(0))[0].tolist())
        t = set(np.nonzero(hit[idx].any(0))[0].tolist())
        o, m, pre = onset(c, t, nd)
        return o, m, pre, c, t

    def trace(idx, o):
        if o is None:
            return []
        out = []
        for h in idx:
            if hit[h, o]:
                la, lo = h3.cell_to_latlng(hexes[h])
                out.append(f"{hexes[h]}@{la:.2f},{lo:.2f}")
        return out

    def part_idx(f, part):
        idx = mem["centroid"][f]
        word = part.split(",")[0].strip()
        if word not in DIRS or not idx:
            return None
        pts = [h3.cell_to_latlng(hexes[h]) for h in idx]
        cla = sum(p[0] for p in pts) / len(pts)
        clo = sum(p[1] for p in pts) / len(pts)
        dx, dy = DIRS[word]
        k = math.cos(math.radians(cla))
        return [h for h, (la, lo) in zip(idx, pts) if (lo - clo) * k * dx + (la - cla) * dy > 0]

    rows = []
    for f, (nd_s, lid, part) in sorted(named.items(), key=lambda x: (x[1][0], x[0])):
        n_day = day(nd_s)
        rec = dict(fir=f, group="named", first_named=nd_s, list_id=lid, part=part)
        for rule in ("centroid", "interior"):
            o, m, pre, c, t = fir_onset(mem[rule][f])
            rec[rule] = dict(onset=date(o) if o is not None else None, measurable=m, pre_clean=pre,
                             covered_before=sum(1 for x in c if x < n_day),
                             hit_before=sum(1 for x in t if x < n_day))
        cr = rec["centroid"]
        o = cr["onset"]
        if nd_s <= "2023-02-17":
            cat = "censored (named on day 2 of the archive)"
        elif o and o < nd_s and cr["measurable"]:
            cat = "positive lag"
        elif o and o < nd_s:
            cat = "onset before naming, not measurable"
        elif cr["covered_before"] >= 0.5 * n_day:
            cat = "reverse (named while covered, no persistent onset)"
        else:
            cat = "no data"
        rec["category"] = cat
        if o and cr["measurable"] and o < nd_s:
            rec["lag_days"] = (dt.date.fromisoformat(nd_s) - dt.date.fromisoformat(o)).days
        rec["trace_onset_hexes"] = trace(mem["centroid"][f], day(o) if o else None)
        pidx = part_idx(f, part)
        if pidx is not None:
            po, pm, ppre, pc, pt = fir_onset(pidx)
            rec["part_only"] = dict(hexes=len(pidx), onset=date(po) if po is not None else None,
                                    measurable=pm, covered_before=sum(1 for x in pc if x < n_day),
                                    hit_before=sum(1 for x in pt if x < n_day))
        rows.append(rec)

    for f in sorted(kept):
        if f in named:
            continue
        o, m, pre, c, t = fir_onset(mem["centroid"][f])
        if o is None or not m or date(o) >= STATIC_END:
            continue
        io, im, _, _, _ = fir_onset(mem["interior"][f])
        rec = dict(fir=f, group="omission candidate", first_named=None,
                   first_easa_table=ftab.get(f), in_easa_scope=in_scope(feats[f]),
                   never_named_by_2024_07_05=date(o) < NEVER_ONSET_BEFORE,
                   centroid=dict(onset=date(o), measurable=m, pre_clean=pre, hit_days=len(t)),
                   interior=dict(onset=date(io) if io is not None else None, measurable=im),
                   trace_onset_hexes=trace(mem["centroid"][f], o))
        rec["category"] = ("omission candidate" if rec["in_easa_scope"]
                           else "outside EASA's apparent scope (positive control)")
        rows.append(rec)

    os.makedirs(out_dir, exist_ok=True)
    json.dump(rows, open(os.path.join(out_dir, "stage2.json"), "w"), indent=1)
    with open(os.path.join(out_dir, "stage2_table.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("fir\tcategory\tfirst_named\tlist_id\tpart\tonset_centroid\tmeasurable\t"
                 "onset_interior\tinterior_measurable\tlag_days\tfirst_easa_table\t"
                 "part_only_onset\tpart_only_covered_before\tpart_only_hit_before\tonset_hexes\n")
        for r in rows:
            po = r.get("part_only", {})
            fh.write("\t".join(str(x) if x is not None else "" for x in (
                r["fir"], r["category"], r["first_named"], r.get("list_id"), r.get("part"),
                r["centroid"]["onset"], r["centroid"]["measurable"], r["interior"]["onset"],
                r["interior"]["measurable"], r.get("lag_days"), r.get("first_easa_table"),
                po.get("onset"), po.get("covered_before"), po.get("hit_before"),
                ";".join(r["trace_onset_hexes"][:5]))) + "\n")
    strip(rows, os.path.join(out_dir, "stage2_strip.svg"))
    print(collections.Counter(r["category"] for r in rows))


def strip(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    keep = [r for r in rows if r["category"] not in ("censored (named on day 2 of the archive)",)]
    keep.sort(key=lambda r: (r["group"] != "named", r["first_named"] or "9", r["fir"]))
    fig, ax = plt.subplots(figsize=(8, 0.28 * len(keep) + 1.2))
    D = lambda s: dt.date.fromisoformat(s)  # noqa: E731
    for i, r in enumerate(keep):
        y = len(keep) - i
        o = r["centroid"]["onset"]
        if o:
            ax.plot(D(o), y, "o", color="#c0392b", mfc="#c0392b" if r["centroid"]["measurable"] else "none")
        if r["first_named"]:
            ax.plot(D(r["first_named"]), y, "D", color="#1f4e79")
        if r.get("first_easa_table"):
            ax.plot(D(r["first_easa_table"]), y, "s", color="#7f8c8d", mfc="none")
        ax.text(D("2023-01-20"), y, f'{r["fir"]}  {r["category"].split(" (")[0]}', va="center", ha="right", fontsize=7)
    for s, lab in (("2023-02-17", "R1"), ("2023-11-06", "R2"), ("2024-07-05", "web list"),
                   ("2025-02-17", "last static capture"), ("2025-05-14", "first ranked table")):
        ax.axvline(D(s), color="#bbb", lw=0.6)
        ax.text(D(s), len(keep) + 0.8, lab, fontsize=6, rotation=90, va="bottom", ha="center", color="#555")
    ax.set_yticks([])
    ax.set_xlim(D("2023-01-25"), D("2026-11-30"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.tick_params(labelsize=7)
    ax.set_title("Archive onset (red; filled = measurable) vs first EASA naming (blue diamond)\n"
                 "and first ranked-table appearance (grey square). Airspace and dates only.", fontsize=8, pad=48)
    fig.subplots_adjust(left=0.32, right=0.98, top=0.84, bottom=0.08)
    fig.savefig(path)


if __name__ == "__main__":
    main(*sys.argv[1:5])
