# DEAD RECKONING — Final pre-launch review (three lenses)

**Date:** 2026-07-17
**Reviewed:** live localhost build of `main` (index / methodology / about / writeup, dark + light, desktop + mobile), against the current 88-day archive (2026-04-17 → 2026-07-16).
**Method:** comprehensive screenshot capture + live interaction + source/data inspection, then three independent critical reviewers (recruiter, technical, policy/GNSS). Screenshots in `docs/review/2026-07-17/shots/`.

| Lens | Score | One-line |
|---|---|---|
| Recruiter / hiring | **7/10** | Distinctive and well-crafted, but the default map undersells the signal and never *shows* the acceleration it claims. |
| Technical / data-viz | **7/10** | A genuinely rigorous instrument undercut by three fixable communication failures (default zoom, anomaly tuning, no trend view). |
| Policy / GNSS-security | **7.5/10** | Methodology and sourcing are expert-grade; the marketing layer overclaims scope/trend the 88-day archive can't support. |

**Through-line:** the foundation is excellent (honesty machinery, sourcing, restraint, sub-40ms scrubbing, strong writing). Three gaps — the same three, seen from all three angles — hold it back from "great." None is architectural. All are shippable before launch.

---

## The three convergent must-fixes (all three reviewers, independently)

### ★ P0-A — Nothing shows the ACCELERATION. The thesis is invisible.
The project is *named for memory and change over time*, yet the map has **no global trend view**. Scrubbing shows *a* day, never *the arc*. The only trend anywhere is the per-region sparkline hidden inside a drawer you have to open. Meanwhile the copy asserts interference "has grown sharply."

The data *does* support the story — Baltic mean bad_ratio rose ~+0.18 (roughly doubled) over the 88-day window, Ukraine-West +0.14 — but a first-time visitor cannot see it.

**Fix:** add an always-visible global trend strip above/beside the scrubber — a single sparkline of daily strong-cell count (or per-region bands) across the whole archive, with the scrubbed day marked. ~40 lines of d3 reusing the existing `drawSpark`; all data already lives in `regions/*.json`. This is the single highest-leverage change in the whole review — it simultaneously (1) answers Walker's crux question, (2) gives the landing page a reason to exist beyond one snapshot, and (3) converts the oversold "grown sharply" copy into an on-screen fact scoped honestly to the window you actually have.

### ★ P0-B — The default map view buries the signal.
On landing (after the intro scrim) the map sits zoomed out over Europe/Russia at ~zoom 3.1. Measured: only **1,251 of 23,274 valued cells** reach opacity ≥0.2 at that zoom — the bloom is a faint smudge. It only becomes visceral when the user manually zooms to the Baltic (compare `02_index_raw_dark.png` → `17_baltic_zoom_dark.png`). A recruiter who clicks past the scrim in 5 seconds sees the *weak* version.

**Fix:** open the default camera on the Baltic/Eastern-Europe hotspot (~zoom 4.3–5, center ~57°N/22°E), or `fitBounds` to the strong-cell envelope of the newest day. Let "zoom out to all of Europe" be the user's choice, not the first impression.

### ★ P0-C — Copy overclaims scope and trend the 88-day archive can't support.
- About: *"no scrubbable, **multi-year** archive"* — positions the site as multi-year; it's 88 days.
- Methodology essay: interference *"has grown sharply as electronic warfare has spread"* — a temporal claim in the project's own voice that 88 days cannot substantiate.
- Essay close: promises the archive answers *"which regions are quietly getting worse"* — needs history it lacks.

This is the most exposed flank: a skeptic who scrubs to a hard April-2026 floor after reading "multi-year" will discount the (genuinely solid) methodology. It's also the exact opposite of the honest-uncertainty ethos the project otherwise nails — the honesty rule you enforce on hexes must also apply to the prose.

**Fix (one afternoon of copy, no code/data):**
1. Reframe About to *capability*, not achieved scope: "no scrubbable *historical* archive… today spanning N days and extending backward toward 2023," and surface a live **coverage-span readout** ("coverage: 2026-04-17 → 2026-07-16, 88 days") near the scrubber.
2. Attribute growth to external reporting: "Independent reporting describes GPS interference as growing sharply…; this archive is being built to measure that trajectory as it deepens."
3. Move "which regions are getting worse" into explicit roadmap voice.

---

## Full findings by priority (merged, deduped)

### P0 (fix before public launch)
- **P0-A** Global trend/acceleration view missing. *(all three)*
- **P0-B** Default zoom buries the signal. *(recruiter, technical)*
- **P0-C** "Multi-year" + "grown sharply" overclaim vs 88 days. *(all three)*
- **P0-D** **Anomaly view is mis-tuned to near-invisible.** Statistically correct, visually reads as broken. Two causes, both measured: (1) opacity is tied to `z/clip` with clip=6, so mean opacity in anomaly mode is **0.093 vs 0.53 for raw**, only 14 cells cross the glow threshold vs 138; (2) chronic zones (Baltic bad_ratio 0.8–0.92) have baselines that caught up → **negative z** → the most visceral raw-mode interference goes *dark* in anomaly mode. **Fix:** decouple opacity from z (fixed floor, e.g. `0.35 + 0.4*clamp(z/clip)`); drop clip 6→~4 (real p99 z ≈ 2.5); add a legend caption distinguishing "anomaly = new/worsening" from "chronic = bad but expected." *(technical)*

### P1
- **P1-A** **Hatch (the honesty layer) defaults OFF.** 21.8% of cells (6,497 on 07-16) fall below the floor but render as blank quiet ground on load — the exact "no-data looks like no-interference" failure the project forbids. Intro card explains hatch, but the default map contradicts it. **Fix:** default hatch ON, or a faint always-on version. *(technical)*
- **P1-B** **Region drawer omits the "analyst interpretation, not measurement" caption at point of use.** About *promises* this label; the drawer renders confident sourced prose ("Widely attributed… EU Council sanctioned…") with the disclaimer living two clicks away on About. **Fix:** one-line caption under the region name in the drawer. *(policy)*
- **P1-C** **Terminology: "jamming" vs "interference."** The essay front door leans on "jamming" ("someone on the ground is jamming the signal," "map GPS jamming worldwide") while the method can't distinguish jamming from spoofing and much content (Levant, E. Med, Baltic) is spoofing. An EW specialist catches this immediately. **Fix:** use "GPS/GNSS interference" as the primary noun; reserve "jamming" for actual loss-of-signal cases. *(policy)*
- **P1-D** **Low-zoom contrast:** raw/anomaly/coverage modes look nearly identical and dim at default zoom; a scanning viewer can't tell modes apart. Compounds P0-B. **Fix:** boost hex opacity/glow at low zoom. *(recruiter)*

### P2
- **P2-A** **Responsible-use statement absent.** Maps interference footprints near military emitters (all from public sources; H3 res-4 ≈ 1,770 km²/cell is far too coarse to be targeting-useful — real risk is low), but a policy audience looks for evidence you considered it. **Fix:** one "Responsible use" paragraph in About (all inputs public; ~40 mi/cell resolution, not tactical; shows effects on civil navigation, re-derives no non-public locations). *(policy)*
- **P2-B** **Light theme flattens the drama** — the bloom nearly disappears against the pale basemap (`08_index_raw_light.png`); reads like a generic atlas. **Fix:** stronger degraded ramp in light mode, or keep dark as the primary and treat light as secondary. *(recruiter)*
- **P2-C** **Region hit-testing** is O(regions × vertices) point-in-polygon on every empty click, no bbox pre-filter. Fine at 10 regions; add per-region bbox short-circuit before it grows. *(technical)*
- **P2-D** **Validation phrasing** "agreement on every major hot zone" is true for the single dated cross-check; tighten to "on that date." *(policy)*

### Decision for Walker (not a defect — a tension)
- **Timeline defaults collapsed for everyone** (you asked for this explicitly). The technical lens flags it as hiding the product's signature feature on load. **Proposed synthesis:** the P0-A trend strip can be the always-visible slim band at the bottom, so the *time dimension has permanent presence* even while the full scrubber stays folded by default. Best of both — your call.

---

## The four questions, synthesized

**Does it convey the info clearly?** Yes at depth, fragile at the surface. The methodology essay, About positioning, and region drawers are clear and honest. But clarity on the *map itself* leans entirely on the dismissable intro scrim; once dismissed, the faint default view carries no standing value-prop, and the entry-level copy speaks with more certainty ("someone is jamming the signal") than the careful deep copy ("inference from agreement"). Fix the default frame + the jamming/interference terminology and clarity becomes robust.

**Does it have the wow / impact we want?** The ceiling is clearly high — the wow lives in the scrim, the "How airliners accidentally became jamming sensors" headline, and the region drawer, and each is strong. But the *map*, where most attention lands, is currently the weakest surface: dim, zoomed-out, modes indistinguishable. The craft (sub-40ms scrubbing on 8k live hexes, native DecompressionStream inflate, per-theme CVD-checked ramps, glow halos, sourced drawers) is real but *latent* because the default frame undersells it. P0-A + P0-B unlock the wow that's already built.

**Does it convey the acceleration?** No — and this is the biggest miss relative to the project's own thesis, flagged by all three lenses. The map has no trend visualization; the acceleration story is simultaneously *unproven on screen* and *slightly oversold in text*. P0-A fixes both at once. The honest, still-compelling framing: make acceleration a thesis the archive is being built to test (attributed to external reporting for the present tense), and lean on what the window *can* show — within-window anomaly-vs-baseline and event alignment (e.g. the June-2025 Hormuz surge).

**Is it interactive enough?** Yes in breadth — three modes, scrub + keyboard + play, jump-to-date calendar showing real gaps, region drawers with fly-to, hover/click readout with affected-aircraft lists, airspace cards, collapsible chrome, working mobile. No dead ends or lag found. The gap is not *quantity* of interaction but that the interactions are conventional-dashboard-shaped and the signature ones are hidden on load (trend behind a drawer, scrubber behind a tab). Surfacing the trend strip is what turns "play" from a slideshow into a story building to a point.

---

## Recommended action plan (in order)

1. **P0-A — global trend strip** (biggest single lever; ~40 lines d3, data ready).
2. **P0-B — default camera on the Baltic hotspot** (one config/one call).
3. **P0-C — copy reframe + coverage-span readout** (one afternoon, no code risk).
4. **P0-D — anomaly retune** (opacity floor + clip 6→4 + legend caption).
5. **P1-A hatch default on**, **P1-C jamming→interference**, **P1-B drawer disclaimer** (all small, high credibility payoff).
6. **P1-D low-zoom contrast**, then **P2** items (responsible-use paragraph, light-mode ramp, bbox pre-filter, validation phrasing).

Items 1–3 are the ones that move all three scores. Everything else is polish on an already-strong base.

---

# Remediation + re-review (same day)

The full slate was implemented on branch `prelaunch-review-remediation-2026-07-17`, then re-reviewed by the same three lenses plus an adversarial code-diff pass.

## New scores

| Lens | Before | After | Δ |
|---|---|---|---|
| Recruiter | 7/10 | **8.5/10** | +1.5 |
| Technical | 7/10 | **8.5/10** | +1.5 |
| Policy/GNSS | 7.5/10 | **9/10** | +1.5 |
| Adversarial diff | — | **SHIP-WITH-FIXES** (fixes applied) | — |

## What shipped (all P0/P1/P2, verified RESOLVED)

- **P0-A trend strip** — always-visible bottom band; `data/trend.json` (per-day strong/degraded/measured, built nightly); d3 sparkline of strong-cell count with current-day cursor; live coverage-span readout; click-to-jump; now also prints magnitude ("N this day · peak M"). Technical lens recomputed 4 days from the raw dailies — exact match.
- **P0-B hero framing** — lands on the Baltic hotspot (center [26,55] z4.3). Verified the bloom is the first impression.
- **P0-C honest copy** — "multi-year" removed (About); growth attributed to "Independent reporting" (essay); future-voice close; live "Coverage: 2026-04-17 → 2026-07-16 · 88 days" readout. Policy lens grep-confirmed no residual overclaim in the project's own voice.
- **P0-D anomaly retune** — opacity decoupled from z (0.05 ghost at/below baseline, 0.35–0.75 above), clip 6→4 (measured p99 z ≈ 2.5); legend caption distinguishes new/worsening from chronic. Legible now (was near-empty); 76% of baselined cells still recede, so no flooding.
- **P1** — hatch defaults ON (sensor-desert visible); "jamming"→"interference" as primary noun + clarifying sentence (title + spoofing-vs-jamming contrasts kept); region-drawer disclaimer at point of use.
- **P2** — Responsible-use paragraph (About); stronger light-theme raw ramp; region bbox short-circuit; new + hardened trend-integrity test. Full suite **115 passing**.

## Re-review fixes applied (from the adversarial + lens passes)

1. Trend strip now shows a **number** (current day's strong count + archive peak) — was shape-only.
2. **Collapsed-band padding** restored (`!important` collision with the generic collapse rule had it flush to the screen edge).
3. **Drawer disclaimer** moved to sit above the interpretive prose it governs, not above the region's own *measured* sparkline.
4. Anomaly caption softened to match the math on high-noise days; stale hatch comment fixed.
5. Trend test hardened with a recompute-one-day exact-match assertion.

## Remaining (flagged, not blocking launch)

- **[P2] Light theme still trails dark** — bloom ramp is stronger but the pale basemap flattens drama vs dark; dark remains the clear hero. One more saturation notch if light is meant to be co-primary.
- **[P2] Default map is near its layer ceiling** — hatch + carpet + airspace + cities all on reads rich, not cluttered, but don't add more default-on layers.
- **[note] `writeup.html`** still carries the old "jamming sensors" framing — it is DRAFT / noindex / not in nav, so out of the public surface; apply the interference-first pass if/when it's published.
- **[note] methodology.html essay** retains a few "jamming" uses in the technical/mechanism sections (e.g. "not for detecting jamming", "jammed or spoofed", "spoofing vs jamming") — the policy lens judged all remaining uses legitimate (loss-of-signal or explicit spoofing-contrast). One borderline case ("When GPS is jammed, the receiver loses its ability…", methodology "The accidental sensor" §) left as loss-of-signal; worth a glance.
- **[decision, per handoff] About "multi-year" replacement** — kept the question list per the handoff's "preserve the surrounding question list" note and changed only "multi-year"→"historical"; the handoff's shorter replacement sentence would have dropped the questions. Flagged for Walker's confirmation.
