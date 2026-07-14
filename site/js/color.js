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
  };
})();
