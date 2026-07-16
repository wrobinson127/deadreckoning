"""
Reproducible analysis scaffold for the DeadReckoning write-up.

    python -m analysis.analyze          # regenerate all figures + stats.json

Reads ONLY committed aggregates (region series, events, daily .gz) via the
pipeline's own readers, computes descriptive statistics, and emits:
  - analysis/figures/*.svg   (dark instrument aesthetic, CVD-aware)
  - analysis/stats.json      (every number the write-up references)

This module builds charts and numbers ONLY. It contains no interpretation and
authors no claims; the write-up page carries mechanical captions plus marked
`WALKER:` prose placeholders. Idempotent, and reads whatever archive coverage
exists (no hardcoded day count) so figures stay current as the backfill grows.
"""
from __future__ import annotations

import json
import os
import statistics as stats
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from pipeline import config as C, dailyio  # noqa: E402
from pipeline.paths import repo_path  # noqa: E402

# ---- output locations -------------------------------------------------------
# Emitted UNDER site/ so the figures + stats deploy with the site and the
# write-up page can load them (the deploy copies site/*, not analysis/). The
# script itself stays in analysis/.
FIG_DIR = repo_path("site", "assets", "analysis")
STATS_OUT = repo_path("site", "assets", "analysis", "stats.json")
REGION_DIR = repo_path("data", "regions")
EVENTS_JSON = repo_path("content", "events.json")

# Featured regions get a full time-series panel; the rest a summary row.
FEATURED = ["baltic", "eastern-med", "black-sea", "us-southwest"]

# ---- dark instrument palette (mirrors DESIGN.md; CVD-aware) ------------------
BG = "#0a0c0f"
PANEL = "#10141a"
INK = "#e6ebf0"
INK_DIM = "#8b96a3"
INK_FAINT = "#5a6473"
LINE = "#2a323c"
SIGNAL = "#35e0d0"     # phosphor teal — the degraded-ratio line
BAND = "#3a6690"       # steel blue — baseline band (distinct hue from signal)
EVENT = "#ffcf5c"      # amber — event markers (matches the map's event ticks)
WARM = "#e0673a"       # warm — histogram / emphasis
QUAD = "#6d4fb0"       # violet — quadrant guides

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": PANEL, "savefig.facecolor": BG,
    "text.color": INK, "axes.labelcolor": INK_DIM, "axes.edgecolor": LINE,
    "xtick.color": INK_DIM, "ytick.color": INK_DIM, "grid.color": LINE,
    "font.family": "DejaVu Sans", "font.size": 12, "svg.fonttype": "none",
    "axes.grid": True, "grid.alpha": 0.35, "axes.axisbelow": True,
})


def _save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, name), format="svg", bbox_inches="tight")
    plt.close(fig)


def _d(s):
    return date.fromisoformat(s)


# ---- data loading (reuses committed aggregates) -----------------------------
def load_regions():
    out = {}
    for fn in sorted(os.listdir(REGION_DIR)):
        if not fn.endswith(".json"):
            continue
        d = json.load(open(os.path.join(REGION_DIR, fn), encoding="utf-8"))
        s = d["series"]
        out[d["id"]] = {
            "name": d.get("display_name", d["id"]),
            "dates": [r["date"] for r in s],
            "ratio": [r["mean_bad_ratio"] for r in s],
            "aircraft": [r["total_aircraft"] for r in s],
        }
    return out


def load_events():
    d = json.load(open(EVENTS_JSON, encoding="utf-8"))
    return d.get("events", [])


def rolling_baseline(ratio, window):
    """Trailing per-day baseline mean/std over the prior `window` days; None
    until BASELINE_MIN_DAYS of history exist (mirrors the map's anomaly rule).
    Null (no-coverage) days are skipped inside the window."""
    mean, sd = [], []
    for i in range(len(ratio)):
        w = [x for x in ratio[max(0, i - window + 1): i + 1] if x is not None]
        if len(w) >= C.BASELINE_MIN_DAYS:
            m = stats.fmean(w)
            mean.append(m)
            sd.append(stats.pstdev(w) if len(w) > 1 else 0.0)
        else:
            mean.append(None)
            sd.append(None)
    return mean, sd


# ---- per-region statistics --------------------------------------------------
def region_stats(regions, events):
    ev_by_region = {}
    for e in events:
        ev_by_region.setdefault(e["region_id"], []).append(e)

    rows = {}
    for rid, r in regions.items():
        ratio, dates = r["ratio"], r["dates"]
        base_m, base_s = rolling_baseline(ratio, C.BASELINE_WINDOW_DAYS)
        valid = [(i, ratio[i]) for i in range(len(ratio)) if ratio[i] is not None]
        if not valid:
            continue
        peak_i, peak_v = max(valid, key=lambda iv: iv[1])
        vals = [v for _, v in valid]
        aircraft = [a for a in r["aircraft"] if a is not None]
        # anomaly breaches: days where ratio exceeds baseline mean + 1 std
        breaches, judged, peak_z = 0, 0, None
        for i in range(len(ratio)):
            if base_m[i] is None or ratio[i] is None:
                continue
            judged += 1
            sd = max(base_s[i], C.BASELINE_STD_FLOOR)
            z = (ratio[i] - base_m[i]) / sd
            peak_z = z if peak_z is None else max(peak_z, z)
            if ratio[i] > base_m[i] + base_s[i]:
                breaches += 1
        win = (dates[0], dates[-1])
        evs = ev_by_region.get(rid, [])
        evs_in = [e for e in evs if win[0] <= e["date"] <= win[1]]
        rows[rid] = {
            "name": r["name"],
            "n_days": len(vals),
            "mean_interference": round(stats.fmean(vals), 4),
            "spikiness_std": round(stats.pstdev(vals), 4),
            "peak_ratio": round(peak_v, 4),
            "peak_day": dates[peak_i],
            "peak_anomaly_z": round(peak_z, 2) if peak_z is not None else None,
            "pct_days_above_band": round(100 * breaches / judged, 1) if judged else None,
            "mean_aircraft_per_day": round(stats.fmean(aircraft), 0) if aircraft else None,
            "n_events_total": len(evs),
            "n_events_in_window": len(evs_in),
        }
    return rows, ev_by_region


def classify(rows):
    """Chronic / episodic / quiet / volatile by median split of mean vs spikiness."""
    means = sorted(v["mean_interference"] for v in rows.values())
    spks = sorted(v["spikiness_std"] for v in rows.values())
    mm, ms = stats.median(means), stats.median(spks)
    for v in rows.values():
        hi_mean = v["mean_interference"] >= mm
        hi_spk = v["spikiness_std"] >= ms
        v["classification"] = (
            "chronic" if hi_mean and not hi_spk else
            "volatile" if hi_mean and hi_spk else
            "episodic" if hi_spk else "quiet"
        )
    return mm, ms


# ---- charts -----------------------------------------------------------------
def chart_region_panel(rid, regions, stats_rows, ev_by_region):
    r, srow = regions[rid], stats_rows[rid]
    xs = [_d(x) for x in r["dates"]]
    base_m, base_s = rolling_baseline(r["ratio"], C.BASELINE_WINDOW_DAYS)
    fig, ax = plt.subplots(figsize=(8.5, 3.1))
    # baseline band (only where defined)
    bx = [xs[i] for i in range(len(xs)) if base_m[i] is not None]
    lo = [base_m[i] - base_s[i] for i in range(len(xs)) if base_m[i] is not None]
    hi = [base_m[i] + base_s[i] for i in range(len(xs)) if base_m[i] is not None]
    bm = [base_m[i] for i in range(len(xs)) if base_m[i] is not None]
    if bx:
        ax.fill_between(bx, lo, hi, color=BAND, alpha=0.28, linewidth=0, label="28-day baseline ±1σ")
        ax.plot(bx, bm, color=BAND, lw=1.0, alpha=0.8)
    ratio_plot = [x if x is not None else float("nan") for x in r["ratio"]]
    ax.plot(xs, ratio_plot, color=SIGNAL, lw=1.7, label="degraded ratio (daily mean)")
    # in-window event markers on the region's own series
    win = (r["dates"][0], r["dates"][-1])
    for e in ev_by_region.get(rid, []):
        if win[0] <= e["date"] <= win[1]:
            ex = _d(e["date"])
            yi = r["ratio"][r["dates"].index(e["date"])]
            ax.axvline(ex, color=EVENT, lw=0.8, alpha=0.5)
            if yi is not None:
                ax.plot([ex], [yi], "o", color=EVENT, ms=6, mec=BG, mew=1)
    ax.set_ylim(0, max(0.05, max(v for v in r["ratio"] if v is not None) * 1.15))
    ax.set_ylabel("degraded ratio")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_title(f"{srow['name']}: daily degraded ratio with 28-day baseline",
                 color=INK, fontsize=12.5, loc="left")
    leg = ax.legend(loc="upper right", fontsize=9, framealpha=0.0, labelcolor=INK_DIM)
    for t in leg.get_texts():
        t.set_color(INK_DIM)
    _save(fig, f"region_{rid}.svg")


def chart_ranking(stats_rows):
    items = sorted(stats_rows.items(), key=lambda kv: (kv[1]["peak_anomaly_z"] or -9))
    names = [v["name"] for _, v in items]
    zs = [v["peak_anomaly_z"] or 0 for _, v in items]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.barh(names, zs, color=SIGNAL, alpha=0.85, height=0.62)
    ax.set_xlabel("peak anomaly (σ above the region's own 28-day baseline)")
    ax.set_title("Regions ranked by peak anomaly over the archive window",
                 color=INK, fontsize=12.5, loc="left")
    ax.grid(axis="y", alpha=0)
    _save(fig, "ranking.svg")


def chart_quadrant(stats_rows, mm, ms):
    fig, ax = plt.subplots(figsize=(7.4, 6.0))
    ax.axvline(mm, color=QUAD, lw=1, ls="--", alpha=0.5)
    ax.axhline(ms, color=QUAD, lw=1, ls="--", alpha=0.5)
    for v in stats_rows.values():
        ax.plot([v["mean_interference"]], [v["spikiness_std"]], "o",
                color=SIGNAL, ms=8, mec=BG, mew=1)
        ax.annotate(v["name"], (v["mean_interference"], v["spikiness_std"]),
                    xytext=(6, 4), textcoords="offset points", color=INK_DIM, fontsize=9)
    # quadrant labels pinned to the axes corners (not data), so they never
    # collide with the title or the plotted points.
    for (fx, fy, ha, va, lab) in [
        (0.98, 0.96, "right", "top", "volatile"),
        (0.02, 0.96, "left", "top", "episodic"),
        (0.98, 0.03, "right", "bottom", "chronic"),
        (0.02, 0.03, "left", "bottom", "quiet"),
    ]:
        ax.text(fx, fy, lab, transform=ax.transAxes, color=INK_FAINT, fontsize=10,
                ha=ha, va=va, style="italic", alpha=0.8)
    ax.set_xlabel("mean interference (archive mean of daily degraded ratio)")
    ax.set_ylabel("spikiness (std of daily degraded ratio)")
    ax.set_title("Chronic vs. flare: regions by mean interference and variability",
                 color=INK, fontsize=12.5, loc="left")
    _save(fig, "quadrant.svg")


def chart_sensor_desert(stats_rows):
    fig, ax = plt.subplots(figsize=(8.0, 5.4))
    for v in stats_rows.values():
        ax.plot([v["mean_aircraft_per_day"]], [v["mean_interference"]], "o",
                color=WARM, ms=8, mec=BG, mew=1)
        ax.annotate(v["name"], (v["mean_aircraft_per_day"], v["mean_interference"]),
                    xytext=(6, 4), textcoords="offset points", color=INK_DIM, fontsize=9)
    ax.set_xscale("log")
    ax.set_xlabel("coverage (mean aircraft observed per day, log scale)")
    ax.set_ylabel("mean interference (degraded ratio)")
    ax.set_title("Coverage vs. signal: least-observed is not least-degraded",
                 color=INK, fontsize=12.5, loc="left")
    _save(fig, "sensor_desert.svg")


def chart_distribution():
    """Per-hex degraded-ratio histogram across the whole archive (reads daily .gz)."""
    ratios = []
    for _day, recs in dailyio.load_dailies():
        for r in recs:
            if r.get("n_aircraft", 0) >= C.MIN_AIRCRAFT_FLOOR:
                ratios.append(r["bad_ratio"])
    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    ax.hist(ratios, bins=40, color=WARM, alpha=0.85)
    ax.set_yscale("log")
    ax.set_xlabel("per-hex degraded ratio (hexes meeting the 5-aircraft floor)")
    ax.set_ylabel("hex-days (log scale)")
    ax.set_title("Distribution of interference intensity across all hex-days",
                 color=INK, fontsize=12.5, loc="left")
    _save(fig, "distribution.svg")
    return {"n_hexdays": len(ratios),
            "median_ratio": round(stats.median(ratios), 4) if ratios else None,
            "frac_zero": round(sum(1 for x in ratios if x == 0) / len(ratios), 4) if ratios else None}


# ---- driver -----------------------------------------------------------------
def run():
    manifest = json.load(open(repo_path("data", "manifest.json"), encoding="utf-8"))
    days = manifest["days"]
    regions = load_regions()
    events = load_events()
    rows, ev_by_region = region_stats(regions, events)
    mm, ms = classify(rows)

    for rid in FEATURED:
        if rid in regions:
            chart_region_panel(rid, regions, rows, ev_by_region)
    chart_ranking(rows)
    chart_quadrant(rows, mm, ms)
    chart_sensor_desert(rows)
    dist = chart_distribution()

    out = {
        "archive": {"n_days": len(days), "start": days[0], "end": days[-1]},
        "featured": FEATURED,
        "quadrant_medians": {"mean_interference": round(mm, 4), "spikiness_std": round(ms, 4)},
        "regions": rows,
        "distribution": dist,
        "events": {"n_total": len(events),
                   "n_in_window": sum(1 for e in events
                                      if days[0] <= e["date"] <= days[-1]),
                   "window": [days[0], days[-1]]},
        "small_sample_note": (f"{len(days)} days, {len(events)} annotated events "
                              f"({sum(1 for e in events if days[0] <= e['date'] <= days[-1])} in window) "
                              "— illustrative, not established; no significance is claimed."),
    }
    with open(STATS_OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"analysis: {len(days)} days ({days[0]}..{days[-1]}), "
          f"{len(regions)} regions, {dist['n_hexdays']} hex-days; "
          f"figures -> {os.path.relpath(FIG_DIR, repo_path())}, stats -> "
          f"{os.path.relpath(STATS_OUT, repo_path())}")
    return out


if __name__ == "__main__":
    run()
