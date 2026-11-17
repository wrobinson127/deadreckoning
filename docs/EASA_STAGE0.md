# EASA warnings against the archive: Stage 0 gate

Slate project #10, Stage 0 only. Source plan: the hub research file
`ideas/inbox/2026-11-16_easa-warnings_research.md` (section 4 gate, section 8
stage table). No model calls, $0. This file stops at the gate; Walker rules on
whether to continue.

## 1. Threshold (written and committed before any FIR-level count)

The research file sets no numeric Stage 0 bar. Its Stage 0 check is "Tallinn and
Chisinau confirmed or dropped; N stated per part". Its 0.7 recall bar belongs to
Stage 3 and is not computed here, so that criterion stays blind. Proposed bar:

**Part (a), lag and omission in the named-list phases.** PASS if at least
**1** FIR has a *measurable* persistent onset (definitions below) that falls
before the first date EASA named that FIR, with the FIR assignment done on
polygons, and the case holds under both the centroid rule and the stricter
interior rule. Reverse cases (named while covered and quiet) and "no data" FIRs
are counted and reported but do not count toward the bar.

**Part (b), EASA's region ranking as an outside check.** PASS if
(1) at least **one** EASA ranked table is readable from a dated primary capture
(the live page or a Wayback capture), and
(2) at least **20** of the FIRs in that table resolve to a polygon and have
DeadReckoning coverage at or above the aircraft floor on at least half the days
of the table's window, with at least **15** of EASA's top 20 among them, so that
the Stage 3 recall bar on EASA's top 20 is computable.
Only coverage is counted. No overlap, rank or agreement figure is computed at
Stage 0.

**Overall.** PASS if (b) passes. Part (a) is expected to be 1 or 2 cases and is
reported as PASS or FAIL on its own; a FAIL on (a) alone shrinks the project to
(b) and does not fail the gate.

### Definitions (carried over from the research file, section 4)

- Floor and strong threshold come from `pipeline/config.py`:
  `MIN_AIRCRAFT_FLOOR` (5) and `TREND_STRONG_RATIO` (0.5).
- **Covered day** for a FIR: at least one assigned res-4 hex with
  `n_aircraft >= MIN_AIRCRAFT_FLOOR`.
- **Hit day:** at least one assigned covered hex with `bad_ratio >= 0.5`.
- **Persistent onset:** the first hit day followed by at least 10 hit days in
  the 30 days starting on it.
- **Measurable onset:** the 60 days before onset fall inside the archive and
  include at least 20 covered, non-hit days. Otherwise the onset is
  **censored**: its date is unknown, not early.
- **Centroid rule:** a hex belongs to the FIR containing its centre.
  **Interior rule:** a hex belongs only if all six vertices are inside the FIR.
- **Partial-FIR wording** ("part of FIR X") counts as naming FIR X.
