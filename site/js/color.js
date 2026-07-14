/* Color scales for DEAD RECKONING.
   Both families are colorblind-safe and perceptually ordered. Saturated red is
   RESERVED for extreme anomaly only (invariant 3). Anomaly uses magma; raw
   bad_ratio uses a dark-teal -> pale sequential ramp tuned to the instrument. */
(function () {
  const EXTREME = "#ff5a48";
  const EXTREME_Z = 5.0; // z at/above this reads as an alarm (reserved red)

  // Raw ramp stops (match the CSS legend .ramp.raw), interpolated by D3.
  const rawRamp = d3.interpolateRgbBasis([
    "#0b1a24", "#123b4e", "#1f6f74", "#3fae8f", "#a7d99b", "#f0f6c0",
  ]);
  // Coverage (traffic density) ramp — a muted single-hue STEEL-BLUE, deliberately
  // off the teal signal ramp, the violet airspace overlay, and the magma anomaly
  // ramp. Only ever shown in its own "Coverage" mode, so it never competes with
  // signal in the default view. Match CSS .ramp.cov.
  const covRamp = d3.interpolateRgbBasis([
    "#111c28", "#25415c", "#3a6690", "#6098c0", "#a6cbe4",
  ]);

  function clamp(x, lo, hi) { return x < lo ? lo : x > hi ? hi : x; }

  window.DR_COLOR = {
    EXTREME,
    EXTREME_Z,
    // Anomaly z-score -> color. Negative/zero deviation is near-baseline (dark).
    anomaly(z, clip) {
      if (z >= EXTREME_Z) return EXTREME;
      const t = clamp(z / clip, 0, 1);
      return d3.interpolateMagma(t);
    },
    // Raw degraded-aircraft ratio in [0,1].
    raw(ratio) {
      return rawRamp(clamp(ratio, 0, 1));
    },
    // Traffic density, already log-normalized to [0,1] by the caller.
    coverage(t) {
      return covRamp(clamp(t, 0, 1));
    },
  };
})();
