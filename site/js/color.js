/* Color scales for DEAD RECKONING — PER THEME.
   On a light ground the pale high-ends of the dark ramps disappear, so light
   gets its own ramps whose HIGH (signal) end is dark/saturated. Each family is
   monotonic in lightness on its own ground (CVD-safe, re-verified per theme).
   Saturated alarm colour is RESERVED for extreme anomaly only (invariant 3),
   and is itself per-theme (bright red on dark, darker red on light). */
(function () {
  const clamp = (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x);

  const RAMPS = {
    dark: {
      extreme: "#ff5a48",
      // inferno-style WARM ramp: dark (low) -> pale (high) reads as heat on black
      raw: d3.interpolateRgbBasis([
        "#150c0a", "#4a1710", "#8f2214", "#cc3d18", "#ef6f1c", "#f9a838", "#fbd66b", "#fdf1b8",
      ]),
      // muted steel-blue traffic density: dark (low) -> pale (high)
      cov: d3.interpolateRgbBasis(["#111c28", "#25415c", "#3a6690", "#6098c0", "#a6cbe4"]),
      anomaly: (t) => d3.interpolateMagma(t),   // dark (near-baseline) -> pale (high z)
    },
    light: {
      extreme: "#cf3323",
      // warm inferno for LIGHT: pale cream (low) -> deep maroon (high signal),
      // so a real bloom is dark and legible on the paper ground.
      raw: d3.interpolateRgbBasis([
        "#f5ead3", "#f3c877", "#ec8a2f", "#d8531c", "#a82814", "#6e1108",
      ]),
      // steel for LIGHT: pale blue (low) -> dark navy (high traffic)
      cov: d3.interpolateRgbBasis(["#dbe6f0", "#9fbdd8", "#5f8fbe", "#356199", "#183a63"]),
      // anomaly for LIGHT: near-ground (low) -> deep plum/magenta (high z)
      anomaly: (t) => d3.interpolateRgbBasis([
        "#efe6ee", "#c99fca", "#9c4a9c", "#6a1f6b", "#37103c",
      ])(t),
    },
  };

  const EXTREME_Z = 5.0; // z at/above this reads as an alarm (reserved colour)
  let R = RAMPS.dark;

  window.DR_COLOR = {
    EXTREME_Z,
    get EXTREME() { return R.extreme; },
    setTheme(theme) { R = RAMPS[theme] || RAMPS.dark; },
    // Anomaly z-score -> color. Negative/zero deviation is near-baseline.
    anomaly(z, clip) {
      if (z >= EXTREME_Z) return R.extreme;
      return R.anomaly(clamp(z / clip, 0, 1));
    },
    // Raw degraded-aircraft ratio in [0,1].
    raw(ratio) { return R.raw(clamp(ratio, 0, 1)); },
    // Traffic density, already log-normalized to [0,1] by the caller.
    coverage(t) { return R.cov(clamp(t, 0, 1)); },
  };
})();
