/* Method-illustrating charts for the Methodology essay (Observable Plot, client-side).
   Reads assets/analysis/stats.json so every value stays live with the archive and the
   dated captions quarantine window-specificity. Mechanical only: no interpretation,
   no causal or significance language. (Sensor scatter + distribution render code is
   shared in spirit with js/writeup.js; kept self-contained here on purpose.) */
(function () {
  "use strict";
  var P = window.Plot;
  // Theme-aware palette: the charts follow the page theme (dark by default, light
  // on toggle). Text/leader colors come from the site's CSS tokens so they track
  // the theme; the warm mark color is set per theme for contrast on each ground.
  function palette() {
    var cs = getComputedStyle(document.documentElement);
    var v = function (n, d) { var x = cs.getPropertyValue(n).trim(); return x || d; };
    var dark = document.documentElement.getAttribute("data-theme") !== "light";
    return {
      INK_DIM: v("--ink-dim", "#8b96a3"),
      INK_FAINT: v("--ink-faint", "#5a6473"),
      PANEL: v("--bg-panel", dark ? "#10141a" : "#ffffff"),
      WARM: dark ? "#e0673a" : "#c2531c"      // burnt orange, readable on the light panel
    };
  }
  function chartStyle(pal) { return { background: "transparent", color: pal.INK_DIM, fontSize: "11px", overflow: "visible" }; }
  var W = function (el) { return Math.max(240, Math.min(820, el.clientWidth || 760)); };

  // Short labels for on-chart text (the full name always stays in the hover tip).
  var SHORT = {
    "Baltic Sea": "Baltic", "Eastern Mediterranean": "E. Med", "Black Sea": "Black Sea",
    "US Southwest Test Ranges": "US SW", "Kaliningrad Approaches": "Kaliningrad",
    "Persian Gulf / Strait of Hormuz": "Persian Gulf", "Levant (Israel / Lebanon)": "Levant",
    "Western Ukraine / Border Airspace": "W. Ukraine", "Korean Peninsula": "Korea", "Red Sea": "Red Sea"
  };
  var shortName = function (n) { return SHORT[n] || n; };
  function fill(el, node) { el.innerHTML = ""; el.append(node); }

  // Per-point scatter labels with a greedy vertical declutter in approximate pixel
  // space; labels pulled clear of their dot get a faint leader line back to it.
  function labelMarks(items, xf, yf, plotW, plotH, ymaxDom, pal) {
    var placed = [], texts = [], links = [];
    items
      .map(function (it) { return { it: it, px: it.nx * plotW, py: (1 - it.ny) * plotH }; })
      .sort(function (a, b) { return a.py - b.py; })
      .forEach(function (o) {
        var right = o.it.nx > 0.62;
        var ly = o.py - 6, guard = 0;
        while (guard++ < 14 && placed.some(function (p) { return Math.abs(p.px - o.px) < 74 && Math.abs(p.ly - ly) < 12; })) ly -= 12;
        placed.push({ px: o.px, ly: ly });
        texts.push(P.text([o.it.d], {
          x: xf, y: yf, text: function () { return o.it.label; },
          dx: right ? -9 : 9, dy: ly - o.py, fill: pal.INK_DIM, fontSize: 9,
          textAnchor: right ? "end" : "start"
        }));
        if (o.py - ly > 13) {
          var ldy = (1 - ly / plotH) * ymaxDom;
          links.push(P.link([o.it.d], { x1: xf, y1: yf, x2: xf, y2: function () { return ldy; },
            stroke: pal.INK_FAINT, strokeWidth: 0.6, strokeOpacity: 0.6 }));
        }
      });
    return links.concat(texts);
  }

  var stats;

  // §The sensor-desert paradox — coverage (aircraft/day) vs mean interference.
  function renderSensor() {
    var el = document.querySelector('.plot[data-chart="sensor"]'); if (!el) return;
    var rows = Object.keys(stats.regions).map(function (id) { var r = stats.regions[id]; return { name: r.name, label: shortName(r.name), x: r.mean_aircraft_per_day, y: r.mean_interference }; })
      .filter(function (d) { return d.x; });
    var ymax = Math.max.apply(null, rows.map(function (d) { return d.y; }));
    var lg = function (v) { return Math.log(v) / Math.LN10; };
    var lo = Math.min.apply(null, rows.map(function (d) { return lg(d.x); }));
    var hi = Math.max.apply(null, rows.map(function (d) { return lg(d.x); }));
    var w = W(el), mL = 52, mR = 20, mT = 12, mB = 34, yd = ymax * 1.18;
    var pal = palette();
    fill(el, P.plot({
      width: w, height: 380, marginLeft: mL, marginRight: mR, marginTop: mT, marginBottom: mB, style: chartStyle(pal),
      x: { type: "log", grid: true, label: "coverage (aircraft/day, log)" },
      y: { grid: true, domain: [0, yd], label: "mean interference" },
      marks: [
        P.dot(rows, { x: "x", y: "y", fill: pal.WARM, r: 6, stroke: pal.PANEL,
          title: function (d) { return d.name + "\n" + Math.round(d.x).toLocaleString() + " aircraft/day\nmean interference " + d.y; }, tip: true })
      ].concat(labelMarks(rows.map(function (d) { return { d: d, label: d.label, nx: (lg(d.x) - lo) / (hi - lo), ny: d.y / yd }; }), "x", "y", w - mL - mR, 380 - mT - mB, yd, pal))
    }));
  }

  // §The method — per-hex degraded-ratio distribution (pre-binned counts, log y).
  function renderDistribution() {
    var el = document.querySelector('.plot[data-chart="distribution"]'); if (!el) return;
    var bins = stats.distribution.bins.filter(function (b) { return b.c > 0; });
    var maxc = Math.max.apply(null, bins.map(function (b) { return b.c; }));
    var pal = palette();
    fill(el, P.plot({
      width: W(el), height: 300, marginLeft: 60, marginRight: 16, style: chartStyle(pal),
      x: { label: "per-hex degraded ratio" },   // full detail is in the figcaption; a longer axis label clips on narrow widths
      y: { type: "log", domain: [0.9, maxc * 1.4], grid: true, label: "hex-days (log)" },
      marks: [
        P.rectY(bins, { x1: "x0", x2: "x1", y1: 0.9, y2: "c", fill: pal.WARM, fillOpacity: 0.85, inset: 0.5,
          title: function (d) { return d.x0 + "–" + d.x1 + "\n" + d.c.toLocaleString() + " hex-days"; }, tip: true }),
        P.ruleY([0.9])
      ]
    }));
  }

  // §Why memory matters — every tracked region at a glance (compact table, degrades
  // gracefully on thin data). Classification is the current read for this window.
  function renderGlance() {
    var el = document.getElementById("glanceTable"); if (!el) return;
    var rows = Object.keys(stats.regions).map(function (id) { return stats.regions[id]; })
      .sort(function (a, b) { return b.mean_interference - a.mean_interference; });
    var head = "<thead><tr><th>Region</th><th class=\"num\">mean</th><th class=\"num\">peak</th><th>class (current)</th><th class=\"num\">events</th></tr></thead>";
    var body = "<tbody>" + rows.map(function (r) {
      return "<tr><td>" + r.name + "</td><td class=\"num\">" + r.mean_interference + "</td><td class=\"num\">" + r.peak_ratio +
        "</td><td>" + r.classification + "</td><td class=\"num\">" + r.n_events_total + "</td></tr>";
    }).join("") + "</tbody>";
    el.innerHTML = head + body;
  }

  // Dated captions: one live sentence that quarantines window-specificity.
  function fillDated() {
    var a = stats.archive;
    var txt = "Archive " + a.start + "–" + a.end + "; values reflect this window and update as the archive grows.";
    Array.prototype.forEach.call(document.querySelectorAll("[data-dated]"), function (n) { n.textContent = txt; });
  }

  function renderPlots() { renderSensor(); renderDistribution(); }

  (async function () {
    try {
      stats = await (await fetch("assets/analysis/stats.json")).json();
      fillDated();
      renderGlance();
      if (window.Plot) {
        renderPlots();
        var t; window.addEventListener("resize", function () { clearTimeout(t); t = setTimeout(renderPlots, 200); });
        // re-render the charts when the theme toggles (the glance table follows CSS)
        new MutationObserver(function () { renderPlots(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
      } else {
        Array.prototype.forEach.call(document.querySelectorAll(".plot"), function (e) { e.textContent = "(charts need Observable Plot; check your connection)"; });
      }
    } catch (e) { console.error("methodology charts failed", e); }
  })();
})();
