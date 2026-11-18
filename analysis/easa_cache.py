"""
One pass over the archive for EASA Stages 2 and 3: per-hex daily aircraft and
bad-aircraft counts, plus each hex's FIR memberships. Read-only over the
committed aggregates; writes one .npz cache outside the repo.

    python -m analysis.easa_cache FIRS_TXT CROSSWALK_TSV OUT_NPZ

Rows with n_aircraft below MIN_AIRCRAFT_FLOOR are stored as 0 (not covered).
"""
from __future__ import annotations

import datetime as dt
import json
import sys

import numpy as np

from pipeline import config as C, dailyio

from analysis.easa_stage0 import Assigner, load_crosswalk, load_firs


def main(firs_txt, crosswalk_tsv, out_npz):
    feats = load_firs(firs_txt, load_crosswalk(crosswalk_tsv))
    A = Assigner(feats)
    paths = dailyio.daily_paths()
    days = [dailyio.day_of(p) for p in paths]
    d0 = dt.date.fromisoformat(days[0])
    ndays = (dt.date.fromisoformat(days[-1]) - d0).days + 1
    idx, cen, inn, rows = {}, [], [], []
    for p in paths:
        c = (dt.date.fromisoformat(dailyio.day_of(p)) - d0).days
        for r in dailyio.read_daily(p):
            if r["n_aircraft"] < C.MIN_AIRCRAFT_FLOOR:
                continue
            hx = r["hex"]
            if hx not in idx:
                idx[hx] = len(idx)
                a, b = A.hex(hx)
                cen.append(a)
                inn.append(b)
            rows.append((idx[hx], c, r["n_aircraft"], r["bad_aircraft"]))
    arr = np.array(rows, dtype=np.int32)
    N = np.zeros((len(idx), ndays), dtype=np.int16)
    B = np.zeros((len(idx), ndays), dtype=np.int16)
    N[arr[:, 0], arr[:, 1]] = arr[:, 2]
    B[arr[:, 0], arr[:, 1]] = arr[:, 3]
    np.savez_compressed(out_npz, N=N, B=B, hexes=np.array(list(idx)), d0=str(d0),
                        cen=json.dumps(cen), inn=json.dumps(inn))
    print(len(idx), ndays, len(rows))


if __name__ == "__main__":
    main(*sys.argv[1:4])
