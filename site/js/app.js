/* DEAD RECKONING — instrument logic.
   Loads per-day aggregates on demand and colors H3 hexes via feature-state so
   scrubbing only mutates state (geometry stays put) and stays well under 100ms.
   Anomaly z-scores are derived client-side from data/baselines.json. */
(function () {
  "use strict";

  const MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/dark";
  // Minimal offline fallback if the hosted basemap CDN is slow/unreachable —
  // the instrument still works (hexes on a plain charcoal ground); coastlines
  // are simply absent. Loads instantly, no network.
  const FALLBACK_STYLE = {
    version: 8,
    sources: {},
    layers: [{ id: "bg", type: "background", paint: { "background-color": "#0a0c0f" } }],
    glyphs: "https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
  };

  // ---- Render tuning (all in one place; see docs/METHODOLOGY.md "Showing
  // coverage"). Absence of signal is only meaningful where monitoring is shown,
  // so measured-but-quiet hexes get a faint "watched airspace" carpet — a
  // whisper that must never compete with a real bloom. Tune against the
  // 2026-07-13 frame with the GPSJam green carpet as the *semantic* benchmark.
  const QUIET_FILL = "#6aa79c";  // desaturated teal; luminance-separated from bg so
                                 // it stays legible under color-vision deficiency
  const QUIET_OP = 0.14;         // faint "watched" floor for conf>=medium, low-degraded
  const FILL_OP_MIN = 0.0;       // 0 at bad_ratio=0 so quiet hexes show pure carpet
  const FILL_OP_MAX = 0.72;      // cap so the basemap/geography ghosts through at peak
  const RAW_GAMMA = 0.6;         // <1: nonlinear boost so mid-range degraded % carries more energy
  const EXTREME_RATIO = 0.85;    // degraded hexes at/above this get a subtle glow (raw view)

  // Airspace-context outlines: violet, chosen over warm/orange because warm hues
  // collapse toward the anomaly ramp / reserved extreme-red under red-green CVD,
  // and toward the ramp under blue-yellow CVD for plain blue. Violet carries both
  // red and blue, so it separates on all three axes (see docs/METHODOLOGY.md).
  // Outline only, NEVER filled. The three status types differ by DASH, not hue.
  const AIRSPACE_COLOR = "#b39ddb";
  const AIRSPACE_DASH = {
    closed:          [3, 1.8],   // long dash — airspace formally closed
    reduced_coverage:[1, 2.5],   // fine dash — avoidance / sparse coverage
    known_test_area: [1, 1.5],   // dotted — recurring announced testing
  };
  const el = (id) => document.getElementById(id);
  const fmtDate = (s) => s; // ISO already human-legible; kept for future locale work

  const state = {
    manifest: null,
    baselines: {},
    stdFloor: 0.02,
    anomalyClip: 6,
    floor: 5,
    regionsGeo: null,
    regions: {},        // id -> profile
    events: [],
    dayCache: new Map(),// day -> {byHex:Map, records:[]}
    dayData: null,      // current day's byHex map
    mode: "raw",
    quiet: true,    // quiet-coverage carpet on by default
    hatch: false,   // low-sample hatch off by default
    cities: true,   // major-city dots + names on by default
    regional: false,// admin-1 (regional) borders off by default
    airspaceOn: true,   // airspace-context overlay on by default
    airspaceGeo: null,  // FeatureCollection of zone outlines
    airspace: {},       // id -> zone metadata (label/type/since/note/sources)
    idx: 0,
    playing: false,
    playTimer: null,
    geomIndex: new Set(),
    geomFC: { type: "FeatureCollection", features: [] },
    prevActive: new Set(),
    activeRegion: null,
    eventsDraft: false,   // file-level draft flag from events.json
    regionsDraft: false,  // file-level draft flag from regions.json
    eventMarkers: [],     // live maplibregl.Marker pins for the current day
    regionCentroids: {},  // rid -> [lon,lat] cache
    pinnedHex: null,      // hex id pinned in the readout (affected-aircraft view)
  };

  // Preview builds (localhost) show draft content; the public origin never does.
  const PREVIEW = /^(localhost|127\.|0\.0\.0\.0|\[?::1\]?)$/.test(location.hostname);

  // ---------- data ----------
  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
  }

  // Daily aggregates are stored gzip-compressed (data/daily/*.json.gz) to keep
  // the archive small. Decompress client-side with the native DecompressionStream
  // API — no library. Static hosts (GitHub Pages, python http.server) serve .gz
  // as an opaque body without a Content-Encoding header, so the browser does NOT
  // auto-inflate it and we must do it here.
  async function getGzJSON(url) {
    if (typeof DecompressionStream === "undefined") {
      throw new Error("This browser lacks DecompressionStream (gzip); please update it.");
    }
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    const stream = r.body.pipeThrough(new DecompressionStream("gzip"));
    const text = await new Response(stream).text();
    return JSON.parse(text);
  }

  async function loadDay(day) {
    if (state.dayCache.has(day)) return state.dayCache.get(day);
    const records = await getGzJSON(`data/daily/${day}.json.gz`);
    const byHex = new Map();
    for (const r of records) byHex.set(r.hex, r);
    const entry = { records, byHex };
    state.dayCache.set(day, entry);
    return entry;
  }

  // ---------- styling ----------
  // Opacity scales with signal strength so faint hexes recede and real blooms
  // dominate — declutters the flight-corridor "haze" of near-zero hexes. Capped
  // at FILL_OP_MAX so the basemap/geography stays legible even under peak signal.
  function opFor(strength) {
    const s = Math.max(0, Math.min(1, strength));
    return FILL_OP_MIN + (FILL_OP_MAX - FILL_OP_MIN) * s;
  }

  // Traffic density is heavily skewed (corridors are orders of magnitude denser
  // than peripheries: floor 5, median ~50, max ~2300), so map it on a log scale.
  const COV_LO = Math.log(5), COV_HI = Math.log(1500);
  function covNorm(n) {
    return Math.max(0, Math.min(1, (Math.log(Math.max(n, 5)) - COV_LO) / (COV_HI - COV_LO)));
  }

  function styleFor(rec) {
    if (rec.n_aircraft < state.floor) return { k: "insuf", c: null, op: null };
    if (state.mode === "coverage") {
      const t = covNorm(rec.n_aircraft);
      return { k: "val", c: DR_COLOR.coverage(t), op: 0.32 + 0.45 * t };
    }
    if (state.mode === "raw") {
      const t = Math.pow(rec.bad_ratio, RAW_GAMMA);   // nonlinear: mid-range pops
      return { k: "val", c: DR_COLOR.raw(t), op: opFor(t),
               ex: rec.bad_ratio >= EXTREME_RATIO ? 1 : 0 };
    }
    // anomaly
    const bl = state.baselines[rec.hex];
    if (!bl) return { k: "val", c: "#1c2430", op: 0.18 }; // measured, no baseline yet
    const z = (rec.bad_ratio - bl.mean) / Math.max(bl.std, state.stdFloor);
    return { k: "val", c: DR_COLOR.anomaly(z, state.anomalyClip),
             op: opFor(z / state.anomalyClip), z };
  }

  function anomalyZ(rec) {
    const bl = state.baselines[rec.hex];
    if (!bl) return null;
    return (rec.bad_ratio - bl.mean) / Math.max(bl.std, state.stdFloor);
  }

  // ---------- map ----------
  let map;

  // Basemap "surgery": OpenFreeMap dark is OpenMapTiles-schema. De-clutter it so
  // an analyst orients instantly and the map never competes with signal:
  //  - English-only labels (kills the stacked latin\nnonlatin dual-script names),
  //  - drop admin-1/oblast labels ("MURMANSK OBLAST" class of noise),
  //  - push minor place labels to zoom-in only; mute + shrink country labels.
  // Coastlines, borders, seas, and major cities on zoom-in are retained.
  function curateStyle(style) {
    const EN = ["coalesce", ["get", "name:en"], ["get", "name_en"],
                ["get", "name:latin"], ["get", "name"]];
    const DROP = new Set(["place_state"]);           // oblast / admin-1 clutter
    const MIN_ZOOM = {                                // continental view stays clean
      place_country_other: 3.2, place_country_minor: 2.6,
      place_other: 6, place_suburb: 7, place_village: 6, place_town: 4.5, place_city: 3,
    };
    style.layers = (style.layers || []).filter((l) => !DROP.has(l.id));
    for (const l of style.layers) {
      // Regional (admin-1) boundary lines start hidden — toggled by "Regional
      // borders". Country borders (boundary_country_*) stay on.
      if (l.id === "boundary_state") {
        l.layout = l.layout || {};
        l.layout.visibility = "none";
        continue;
      }
      if (l.type !== "symbol") continue;
      l.layout = l.layout || {};
      if (l.layout["text-field"]) l.layout["text-field"] = EN;
      if (MIN_ZOOM[l.id] != null) l.minzoom = Math.max(l.minzoom || 0, MIN_ZOOM[l.id]);
      if (l.id.startsWith("place_country")) {        // muted, smaller country names
        l.paint = l.paint || {};
        l.paint["text-color"] = "#6c7a86";
        l.paint["text-halo-color"] = "#0a0c0f";
        l.paint["text-halo-width"] = 1;
        l.layout["text-size"] = ["interpolate", ["linear"], ["zoom"], 2, 9, 5, 12];
      }
    }
    return style;
  }

  async function initMap() {
    // Fetch + curate the style ourselves so the label surgery applies from the
    // first paint. If the CDN is unreachable, fall back to the minimal dark bg.
    let style = FALLBACK_STYLE;
    try {
      const r = await fetch(MAP_STYLE_URL);
      if (r.ok) style = curateStyle(await r.json());
    } catch (e) { /* offline: keep FALLBACK_STYLE */ }

    map = new maplibregl.Map({
      container: "map",
      style,
      center: [22, 48],
      zoom: 3.1,
      minZoom: 1.5,
      maxZoom: 8,
      attributionControl: false,
      dragRotate: false,
    });
    // Localhost-only debug handle (no-op on the deployed origin) for scripted
    // verification / screenshotting.
    if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
      window.__drMap = map;
    }
    // The basemap's city layers reference a "circle-11" dot sprite that isn't in
    // the CDN sprite sheet; provide a small muted dot so major cities show a
    // marker, not just a name.
    map.on("styleimagemissing", (e) => {
      if (e.id === "circle-11" && !map.hasImage("circle-11")) {
        map.addImage("circle-11", makeDotImage(3, "#9aa6b2"), { pixelRatio: 2 });
      }
    });
    map.addControl(new maplibregl.AttributionControl({
      compact: true,
      customAttribution:
        "NIC data © adsb.lol (ODbL) · basemap © OpenStreetMap contributors",
    }), "bottom-right");
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

    // Fire onMapReady exactly once, whether the hosted style loads or we fall back.
    let mapReady = false;
    const ready = () => { if (mapReady) return; mapReady = true; onMapReady(); };
    map.on("load", ready);
    // Watchdog: reassure at 8s; fall back to a keyless minimal basemap at 11s so
    // the app never hangs on a slow/unreachable tile CDN.
    setTimeout(() => {
      const l = el("loader");
      if (l && !l.classList.contains("hide")) {
        l.querySelector(".msg").textContent = "acquiring signal — loading the archive…";
      }
    }, 8000);
    setTimeout(() => {
      if (mapReady) return;
      try {
        map.setStyle(FALLBACK_STYLE);
        map.once("styledata", ready);
        toast("basemap slow — using a minimal map");
      } catch (e) { ready(); }
    }, 11000);
  }

  function makeDotImage(r, color) {
    const d = r * 2 + 2, cv = document.createElement("canvas");
    cv.width = cv.height = d;
    const ctx = cv.getContext("2d");
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(d / 2, d / 2, r, 0, 2 * Math.PI);
    ctx.fill();
    return ctx.getImageData(0, 0, d, d);
  }

  function makeHatchImage() {
    const s = 8, cv = document.createElement("canvas");
    cv.width = cv.height = s;
    const ctx = cv.getContext("2d");
    ctx.clearRect(0, 0, s, s);
    ctx.strokeStyle = "rgba(150,165,180,0.9)";
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, s); ctx.lineTo(s, 0); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-2, 2); ctx.lineTo(2, -2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(s - 2, s + 2); ctx.lineTo(s + 2, s - 2); ctx.stroke();
    return ctx.getImageData(0, 0, s, s);
  }

  // Insert our hex layers BENEATH the basemap's first label layer so place names
  // and geography stay readable through the blooms. On the fallback style (no
  // symbols) this returns undefined and layers go on top, which is fine.
  function firstSymbolId() {
    for (const l of (map.getStyle().layers || [])) {
      if (l.type === "symbol") return l.id;
    }
    return undefined;
  }

  function onMapReady() {
    map.addImage("hatch", makeHatchImage(), { pixelRatio: 2 });
    map.addSource("hexes", {
      type: "geojson", data: state.geomFC, promoteId: "h",
    });
    const before = firstSymbolId();

    // Quiet-coverage carpet (bottom): a faint "watched airspace" floor under every
    // measured hex. Default on. Reads as coverage at continental zoom; never
    // competes with a bloom (QUIET_OP is a whisper vs the signal ramp above it).
    map.addLayer({
      id: "hex-quiet", type: "fill", source: "hexes",
      paint: {
        "fill-color": QUIET_FILL,
        "fill-opacity": ["case", ["==", ["feature-state", "k"], "val"], QUIET_OP, 0],
      },
    }, before);
    // Signal (the blooms) — color + capped opacity ramp, on top of the carpet.
    map.addLayer({
      id: "hex-fill", type: "fill", source: "hexes",
      paint: {
        "fill-color": ["coalesce", ["feature-state", "c"], "rgba(0,0,0,0)"],
        "fill-opacity": ["case", ["==", ["feature-state", "k"], "val"],
          ["coalesce", ["feature-state", "op"], 0.5], 0],
      },
    }, before);
    map.addLayer({
      id: "hex-line", type: "line", source: "hexes",
      paint: {
        "line-color": "rgba(10,12,15,0.55)",
        "line-width": 0.4,
        "line-opacity": ["case", ["==", ["feature-state", "k"], "val"], 0.6, 0],
      },
    }, before);
    // Subtle glow around the most-degraded (extreme) hexes — a blurred warm halo,
    // driven by the "ex" feature-state (raw view only). Adds heat without a fill.
    map.addLayer({
      id: "hex-glow", type: "line", source: "hexes",
      paint: {
        "line-color": "#ffdf8f",
        "line-blur": 6,
        "line-width": ["case", ["==", ["feature-state", "ex"], 1], 2.4, 0],
        "line-opacity": ["case", ["==", ["feature-state", "ex"], 1], 0.65, 0],
      },
    }, before);
    // Low-sample hatch — distinct "too few aircraft to judge" state. Default off.
    map.addLayer({
      id: "hex-insuf", type: "fill", source: "hexes",
      paint: {
        "fill-pattern": "hatch",
        "fill-opacity": ["case", ["==", ["feature-state", "k"], "insuf"], 0.55, 0],
      },
      layout: { visibility: "none" },
    }, before);

    wireHexInteraction();
    boot().catch((e) => fail(e));
  }

  // ---------- airspace-context overlay ----------
  function airspaceLayerIds() {
    return Object.keys(AIRSPACE_DASH).map((t) => "airspace-" + t);
  }
  function addAirspace() {
    if (!state.airspaceGeo || !map) return;
    const before = firstSymbolId();
    if (map.getSource("airspace")) map.getSource("airspace").setData(state.airspaceGeo);
    else map.addSource("airspace", { type: "geojson", data: state.airspaceGeo });
    // Faint violet wash BENEATH the hex layers: it clarifies the zone's extent in
    // the empty (sensor-desert) interior, while any coverage/signal hexes render on
    // top of it. Violet is off the signal palette, and it sits under the data, so
    // it can't be read as jamming. Toggles with the outline.
    if (!map.getLayer("airspace-fill")) {
      map.addLayer({
        id: "airspace-fill", type: "fill", source: "airspace",
        paint: { "fill-color": AIRSPACE_COLOR, "fill-opacity": 0.06 },
        layout: { visibility: state.airspaceOn ? "visible" : "none" },
      }, map.getLayer("hex-quiet") ? "hex-quiet" : before);
    }
    // One line layer per status type — same violet hue, distinct dash. Outline
    // only: a filled zone would read as jamming signal, the exact confusion this
    // layer exists to cure. Sits above the hex fills but below the basemap labels.
    for (const [type, dash] of Object.entries(AIRSPACE_DASH)) {
      const id = "airspace-" + type;
      if (map.getLayer(id)) continue;
      map.addLayer({
        id, type: "line", source: "airspace",
        filter: ["==", ["get", "type"], type],
        paint: {
          "line-color": AIRSPACE_COLOR,
          "line-width": type === "closed" ? 1.7 : 1.3,
          "line-dasharray": dash,
          "line-opacity": 0.9,
        },
        layout: { visibility: state.airspaceOn ? "visible" : "none" },
      }, before);
      map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "help"; });
      map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });
    }
  }
  function setAirspace(on) {
    state.airspaceOn = on;
    for (const id of airspaceLayerIds().concat(["airspace-fill"]))
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
  }

  // Cards LEAD with the regulatory fact (airspace status), not the reasons — this
  // layer describes the instrument's blindness, never "conflict zones".
  const ZONE_LEAD = {
    closed: (z) => `Closed to civil aviation since ${z.since}.`,
    reduced_coverage: (z) => `Reduced coverage — widely avoided, sparsely received`
      + (z.since && z.since !== "recurring" ? ` since ${z.since}` : "") + ".",
    known_test_area: (z) => `Known GPS-testing range — recurring, announced tests.`,
  };
  function showZoneCard(id, point) {
    const z = state.airspace[id];
    if (!z) return;
    const card = el("zoneCard");
    const lead = (ZONE_LEAD[z.type] || (() => ""))(z);
    const srcs = (z.sources || []).map((s) =>
      `<a href="${s.url}" target="_blank" rel="noopener">${escapeHtml(s.title)}</a>`).join("");
    const reg = (z.region_id && state.regions[z.region_id])
      ? `<button class="zc-region" data-rid="${z.region_id}">See the ${escapeHtml(state.regions[z.region_id].display_name || z.region_id)} region →</button>`
      : "";
    card.innerHTML =
      `<button class="zc-close" aria-label="close">×</button>
       <div class="zc-title">${escapeHtml(z.label)}</div>
       <div class="zc-lead">${escapeHtml(lead)}</div>
       <div class="zc-note">${escapeHtml(z.note || "")}</div>
       ${reg}
       <div class="zc-src">${srcs}</div>`;
    card.querySelector(".zc-close").addEventListener("click", hideZoneCard);
    const rb = card.querySelector(".zc-region");
    if (rb) rb.addEventListener("click", () => { hideZoneCard(); openRegion(rb.dataset.rid); });
    card.style.left = Math.min(window.innerWidth - 330, point.x + 14) + "px";
    card.style.top = Math.min(window.innerHeight - 220, point.y + 14) + "px";
    card.classList.add("show");
  }
  function hideZoneCard() { el("zoneCard").classList.remove("show"); }

  function ensureGeometry(records) {
    let added = false;
    for (const r of records) {
      if (state.geomIndex.has(r.hex)) continue;
      state.geomIndex.add(r.hex);
      // h3-js v4: cellToBoundary(h, true) -> [lng,lat] pairs (GeoJSON order)
      const ring = h3.cellToBoundary(r.hex, true);
      ring.push(ring[0]);
      state.geomFC.features.push({
        type: "Feature", id: r.hex, properties: { h: r.hex },
        geometry: { type: "Polygon", coordinates: [ring] },
      });
      added = true;
    }
    if (added) map.getSource("hexes").setData(state.geomFC);
  }

  function renderDay() {
    const day = state.manifest.days[state.idx];
    const entry = state.dayCache.get(day);
    if (!entry) return;
    ensureGeometry(entry.records);
    const nextActive = new Set();
    let nHigh = 0, nInsuf = 0;
    for (const r of entry.records) {
      const st = styleFor(r);
      map.setFeatureState({ source: "hexes", id: r.hex },
        { c: st.c, k: st.k, op: st.op, ex: st.ex || 0 });
      nextActive.add(r.hex);
      if (r.confidence === "high") nHigh++;
      if (st.k === "insuf") nInsuf++;
    }
    // clear hexes that were shown yesterday but not today
    for (const h of state.prevActive) {
      if (!nextActive.has(h)) map.setFeatureState({ source: "hexes", id: h }, { c: null, k: "none", op: 0, ex: 0 });
    }
    state.prevActive = nextActive;
    state.dayData = entry.byHex;
    el("scrubMeta").textContent =
      `${entry.records.length.toLocaleString()} cells · ${nHigh.toLocaleString()} high-confidence`;
  }

  async function goTo(idx) {
    idx = Math.max(0, Math.min(state.manifest.days.length - 1, idx));
    state.idx = idx;
    clearPin();   // a pinned cell's affected-aircraft list is day-specific
    const day = state.manifest.days[idx];
    el("scrubDate").textContent = fmtDate(day);
    el("slider").value = idx;
    updateTrackFill();
    try {
      await loadDay(day);
      renderDay();
    } catch (e) {
      // A listed day that won't load/parse is a real gap, not "awaiting nightly"
      // (the manifest only ever lists already-processed days). Make it legible and
      // persistent — which day failed — instead of a fleeting toast.
      console.error(`day ${day} failed to load:`, e);
      el("scrubMeta").textContent = `no data for ${day} — see console`;
      toast(`no data for ${day}`);
    }
    updateEventPins(day);   // spatial markers for events within ±1 day of this date
  }

  // ---------- hover readout + pinned affected-aircraft ----------
  function wireHexInteraction() {
    map.on("mousemove", "hex-fill", (e) => {
      if (state.pinnedHex) return;   // a pinned readout is not disturbed by hover
      const f = e.features && e.features[0];
      if (!f) return;
      map.getCanvas().style.cursor = "crosshair";
      const rec = state.dayData && state.dayData.get(f.id);
      if (rec) showReadout(rec);
    });
    map.on("mouseleave", "hex-fill", () => {
      map.getCanvas().style.cursor = "";
    });
    map.on("click", (e) => {
      // Airspace zone takes precedence — clicking a zone outline opens its card.
      // Query a small box (not the exact pixel) so the thin dashed line is an
      // easy target.
      if (state.airspaceOn) {
        const live = airspaceLayerIds().filter((id) => map.getLayer(id));
        const pad = 7, p = e.point;
        const box = [[p.x - pad, p.y - pad], [p.x + pad, p.y + pad]];
        const zf = live.length ? map.queryRenderedFeatures(box, { layers: live }) : [];
        if (zf.length) { clearPin(); showZoneCard(zf[0].properties.id, e.point); return; }
      }
      // A degraded hex carries its top affected-aircraft list — pin it in the
      // readout (regions stay reachable via the chips).
      const hf = map.getLayer("hex-fill")
        ? map.queryRenderedFeatures(e.point, { layers: ["hex-fill"] }) : [];
      if (hf.length) {
        const rec = state.dayData && state.dayData.get(hf[0].id);
        if (rec && Array.isArray(rec.flights)) { pinFlights(rec); return; }
      }
      // otherwise region hit-test on click (point in region polygon)
      const rid = regionAt(e.lngLat.lng, e.lngLat.lat);
      if (rid) { clearPin(); openRegion(rid); return; }
      clearPin();   // clicking empty airspace/water unpins
    });
    el("roClose").addEventListener("click", clearPin);
  }

  function pinFlights(rec) {
    state.pinnedHex = rec.hex;
    showReadout(rec, true);
  }
  function clearPin() {
    if (!state.pinnedHex) return;
    state.pinnedHex = null;
    el("roClose").hidden = true;
    el("roFlights").hidden = true;
    el("roFlights").innerHTML = "";
    el("readout").classList.add("empty");
    el("roHex").textContent = "hover a cell";
    el("roVal").textContent = "—";
    el("roAircraft").textContent = "aircraft —";
    el("roConf").textContent = "—";
    el("roConf").className = "conf";
  }

  // unix-seconds -> UTC HH:MM (aggregates and dates are UTC everywhere)
  function utcHM(ts) {
    const d = new Date(ts * 1000);
    const p = (n) => String(n).padStart(2, "0");
    return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
  }

  function showReadout(rec, pinned) {
    const ro = el("readout");
    ro.classList.remove("empty");
    el("roHex").textContent = rec.hex;
    const z = anomalyZ(rec);
    if (state.mode === "anomaly") {
      el("roVal").textContent = z == null ? "—" : (z >= 0 ? "+" : "") + z.toFixed(1) + "σ";
    } else {
      el("roVal").textContent = (rec.bad_ratio * 100).toFixed(0) + "%";
    }
    el("roAircraft").textContent = `${rec.n_aircraft} aircraft · ${(rec.bad_ratio * 100).toFixed(0)}% degraded`;
    const c = el("roConf");
    c.textContent = rec.confidence;
    c.className = "conf " + rec.confidence;

    // pinned view: the aircraft that drove this cell's degraded reading, from the
    // daily artifact (public ADS-B callsigns). Graceful empty state otherwise.
    const fl = el("roFlights"), close = el("roClose");
    if (pinned) {
      close.hidden = false;
      const flights = rec.flights || [];
      if (flights.length) {
        const rows = flights.map((f) =>
          `<div class="fl"><span class="fl-cs">${escapeHtml(f.cs || f.ic || "—")}</span>` +
          `<span class="fl-win">${utcHM(f.t0)}–${utcHM(f.t1)}Z</span>` +
          `<span class="fl-nd">${f.nd}</span></div>`).join("");
        fl.innerHTML =
          `<div class="fl-head">affected aircraft · top ${flights.length}` +
          `<span class="fl-key">callsign · window · degraded reports</span></div>` + rows;
      } else {
        fl.innerHTML = `<div class="fl-empty">no affected-aircraft detail for this cell</div>`;
      }
      fl.hidden = false;
    } else {
      close.hidden = true;
      fl.hidden = true;
    }
  }

  // ---------- regions ----------
  function pointInRing(lng, lat, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
      if ((yi > lat) !== (yj > lat) &&
          lng < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-15) + xi) inside = !inside;
    }
    return inside;
  }
  function ringsOf(geom) {
    if (geom.type === "Polygon") return [geom.coordinates[0]];
    if (geom.type === "MultiPolygon") return geom.coordinates.map((p) => p[0]);
    return [];
  }
  function regionAt(lng, lat) {
    for (const f of state.regionsGeo.features) {
      for (const ring of ringsOf(f.geometry)) {
        if (pointInRing(lng, lat, ring)) return f.properties.id;
      }
    }
    return null;
  }

  async function openRegion(rid) {
    const prof = state.regions[rid];
    if (!prof) return;
    state.activeRegion = rid;
    document.querySelectorAll(".chip").forEach((c) =>
      c.classList.toggle("active", c.dataset.rid === rid));
    el("drRid").textContent = rid;
    el("drName").textContent = prof.display_name || rid;
    const body = el("drBody");
    // Draft badge gates like events do: approved content (draft:false) never
    // shows it; genuinely-draft regions show it in preview builds only, never
    // on the public origin. (Previously hardcoded, which mislabeled every
    // approved region as DRAFT on the live site.)
    const regionDraft = state.regionsDraft || !!prof.draft;
    body.innerHTML = (regionDraft && PREVIEW)
      ? `<span class="draft-tag">DRAFT — pending author review</span>`
      : "";

    // trend sparkline
    let series = [];
    try { series = (await getJSON(`data/regions/${rid}.json`)).series || []; } catch (e) {}
    body.insertAdjacentHTML("beforeend",
      `<div class="section-label">${series.length ? series.length + "-day " : ""}trend · mean degraded ratio</div>
       <svg class="spark" id="sparkSvg"></svg>
       <div class="spark-axis"><span>${series[0]?.date || ""}</span><span>${series.at(-1)?.date || ""}</span></div>`);
    drawSpark(series);

    const ctx = prof.context || {};
    const sec = (label, txt) => txt
      ? `<div class="section-label">${label}</div><p>${escapeHtml(txt)}</p>` : "";
    body.insertAdjacentHTML("beforeend",
      sec("Typical causes", ctx.typical_causes) +
      sec("Known actors (reported)", ctx.known_actors) +
      sec("Interpretation", ctx.interpretation_notes));

    // sources
    if (ctx.sources && ctx.sources.length) {
      const items = ctx.sources.map((s) => {
        if (typeof s === "string")
          return `<li class="needs-source">${escapeHtml(s)}</li>`;
        return `<li><a href="${encodeURI(s.url || "#")}" target="_blank" rel="noopener">${escapeHtml(s.title || s.url)}</a>${s.note ? " — " + escapeHtml(s.note) : ""}</li>`;
      }).join("");
      body.insertAdjacentHTML("beforeend",
        `<div class="section-label">Sources</div><ul class="src-list">${items}</ul>`);
    }

    // events for this region
    const evs = state.events.filter((e) => e.region_id === rid)
      .sort((a, b) => (a.date < b.date ? 1 : -1));
    if (evs.length) {
      const lis = evs.map((e) => `<li>
        <span class="e-date">${e.date}</span><span class="e-type">${e.type || ""}</span>
        <span class="e-title">${escapeHtml(e.title)}</span>
        <span class="e-one">${escapeHtml(e.one_line || "")}</span></li>`).join("");
      body.insertAdjacentHTML("beforeend",
        `<div class="section-label">Events</div><ul class="events-list">${lis}</ul>`);
    }
    el("drawer").classList.add("open");
    el("drawer").setAttribute("aria-hidden", "false");
  }

  function closeRegion() {
    el("drawer").classList.remove("open");
    el("drawer").setAttribute("aria-hidden", "true");
    state.activeRegion = null;
    document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
  }

  function drawSpark(series) {
    const svg = d3.select("#sparkSvg");
    svg.selectAll("*").remove();
    const node = svg.node();
    const w = node.clientWidth || 320, h = 68, pad = 4;
    const pts = series.filter((d) => d.mean_bad_ratio != null);
    if (pts.length < 2) {
      svg.append("text").attr("x", w / 2).attr("y", h / 2)
        .attr("fill", "#5a6473").attr("font-size", 11).attr("text-anchor", "middle")
        .attr("font-family", "IBM Plex Mono").text("insufficient history");
      return;
    }
    const x = d3.scaleLinear().domain([0, pts.length - 1]).range([pad, w - pad]);
    const maxY = d3.max(pts, (d) => d.max_bad_ratio) || 1;
    const y = d3.scaleLinear().domain([0, maxY]).range([h - pad, pad]);
    const area = d3.area().x((d, i) => x(i)).y0(h - pad).y1((d) => y(d.mean_bad_ratio)).curve(d3.curveMonotoneX);
    const line = d3.line().x((d, i) => x(i)).y((d) => y(d.mean_bad_ratio)).curve(d3.curveMonotoneX);
    svg.append("path").datum(pts).attr("d", area).attr("fill", "rgba(53,224,208,0.12)");
    svg.append("path").datum(pts).attr("d", line).attr("fill", "none")
      .attr("stroke", "#35e0d0").attr("stroke-width", 1.5);
    const last = pts.at(-1);
    svg.append("circle").attr("cx", x(pts.length - 1)).attr("cy", y(last.mean_bad_ratio))
      .attr("r", 2.5).attr("fill", "#35e0d0");
  }

  // ---------- scrubber / ticks / events ----------
  function buildTicks() {
    const days = state.manifest.days;
    const ticks = el("ticks");
    ticks.innerHTML = "";
    const n = days.length;
    const eventByDay = new Map();
    for (const e of state.events) eventByDay.set(e.date, (eventByDay.get(e.date) || []).concat(e));
    days.forEach((d, i) => {
      const left = n === 1 ? 50 : (i / (n - 1)) * 100;
      const t = document.createElement("div");
      t.className = "tick";
      t.style.left = left + "%";
      ticks.appendChild(t);
    });
    // event pins positioned by date within [firstDay,lastDay] if in range,
    // else clamped to nearest edge (still discoverable).
    const first = days[0], last = days.at(-1);
    for (const e of state.events) {
      if (!eventVisible(e)) continue;   // draft events: preview builds only
      let i = days.indexOf(e.date);
      let left;
      if (i >= 0) left = n === 1 ? 50 : (i / (n - 1)) * 100;
      else if (e.date < first) left = 0;
      else if (e.date > last) left = 100;
      else continue;
      const pin = document.createElement("div");
      pin.className = "tick event" + (e.date_precision === "approximate" ? " approx" : "");
      pin.style.left = left + "%";
      pin.addEventListener("mouseenter", (ev) => showEventCard(e, ev.target));
      pin.addEventListener("mouseleave", hideEventCard);
      pin.addEventListener("click", () => { if (e.region_id) openRegion(e.region_id); });
      ticks.appendChild(pin);
    }
  }

  function showEventCard(e, target) {
    const card = el("eventCard");
    const disputed = e.disputed ? `<span class="e-tag">disputed</span>` : "";
    const draftTag = (state.eventsDraft || e.draft) ? `<span class="e-tag draft">draft</span>` : "";
    const approx = e.date_precision === "approximate"
      ? `<span class="e-tag approx">date approximate</span>` : "";
    const note = e.editorial_note
      ? `<div class="e-note">${escapeHtml(e.editorial_note)}</div>` : "";
    card.innerHTML = `<div class="e-date">${e.date} · ${e.type || ""}${disputed}${draftTag}${approx}</div>
      <div class="e-title">${escapeHtml(e.title)}</div>
      <div class="e-one">${escapeHtml(e.one_line || "")}</div>${note}`;
    const tr = target.getBoundingClientRect();
    card.style.left = Math.max(8, Math.min(window.innerWidth - 300, tr.left)) + "px";
    if (target.closest(".track-wrap")) {           // timeline tick: anchored above the strip
      card.style.top = "auto"; card.style.bottom = "";
    } else {                                        // map pin: float near the marker
      card.style.bottom = "auto";
      card.classList.add("show");
      const ch = card.offsetHeight || 120;
      let top = tr.top - ch - 10;
      if (top < 8) top = tr.bottom + 10;
      card.style.top = Math.max(8, Math.min(window.innerHeight - ch - 8, top)) + "px";
      return;
    }
    card.classList.add("show");
  }
  function hideEventCard() { el("eventCard").classList.remove("show"); }

  // ---------- event pins (spatial markers) ----------
  function eventVisible(e) {
    const draft = state.eventsDraft || !!e.draft;
    return !draft || PREVIEW;   // draft events only render in local/preview builds
  }
  function regionCentroid(rid) {
    if (rid in state.regionCentroids) return state.regionCentroids[rid];
    let c = null;
    const f = (state.regionsGeo.features || []).find((x) => x.properties.id === rid);
    if (f) {
      let sx = 0, sy = 0, n = 0;
      for (const ring of ringsOf(f.geometry)) for (const p of ring) { sx += p[0]; sy += p[1]; n++; }
      if (n) c = [sx / n, sy / n];
    }
    state.regionCentroids[rid] = c;
    return c;
  }
  function updateEventPins(day) {
    for (const m of state.eventMarkers) m.remove();
    state.eventMarkers = [];
    if (!day) return;
    const t0 = Date.parse(day);
    for (const e of state.events) {
      if (!eventVisible(e)) continue;
      if (Math.abs((Date.parse(e.date) - t0) / 86400000) > 1) continue;   // within ±1 day
      const c = (e.lon != null && e.lat != null) ? [e.lon, e.lat] : regionCentroid(e.region_id);
      if (!c) continue;
      const pin = document.createElement("div");
      pin.className = "event-pin"
        + ((state.eventsDraft || e.draft) ? " draft" : "")
        + (e.date_precision === "approximate" ? " approx" : "");
      pin.setAttribute("aria-label", e.title);
      pin.addEventListener("mouseenter", () => showEventCard(e, pin));
      pin.addEventListener("mouseleave", hideEventCard);
      pin.addEventListener("click", (ev) => { ev.stopPropagation(); showEventCard(e, pin); });
      state.eventMarkers.push(new maplibregl.Marker({ element: pin }).setLngLat(c).addTo(map));
    }
  }

  function updateTrackFill() {
    const n = state.manifest.days.length;
    const pct = n <= 1 ? 100 : (state.idx / (n - 1)) * 100;
    el("trackFill").style.width = pct + "%";
  }

  function togglePlay() {
    state.playing = !state.playing;
    el("playBtn").textContent = state.playing ? "❚❚" : "▶";
    if (state.playing) {
      state.playTimer = setInterval(() => {
        if (state.idx >= state.manifest.days.length - 1) { goTo(0); }
        else goTo(state.idx + 1);
      }, 650);
    } else clearInterval(state.playTimer);
  }

  // ---------- mode / coverage ----------
  function setMode(mode) {
    state.mode = mode;
    document.querySelectorAll("#modeToggle button").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
    const L = ({
      raw:      { title: "Aircraft with degraded GPS", ramp: "raw",  lo: "0%",     hi: "100%" },
      anomaly:  { title: "Anomaly vs baseline (σ)",    ramp: "anom", lo: "normal", hi: state.anomalyClip + "σ+" },
      coverage: { title: "Aircraft per cell (log)",    ramp: "cov",  lo: "few",    hi: "dense" },
    })[mode] || {};
    el("legendTitle").textContent = L.title || "";
    el("legendRamp").className = "ramp " + (L.ramp || "raw");
    el("legLo").textContent = L.lo || "";
    el("legHi").textContent = L.hi || "";
    // The quiet carpet is context for the signal views; in Coverage mode the
    // density ramp already shows "how heavily watched", so hide it to avoid tinting.
    const showCarpet = state.quiet && mode !== "coverage";
    if (map.getLayer("hex-quiet"))
      map.setLayoutProperty("hex-quiet", "visibility", showCarpet ? "visible" : "none");
    renderDay();
  }
  function setQuiet(on) {
    state.quiet = on;
    map.setLayoutProperty("hex-quiet", "visibility", on ? "visible" : "none");
  }
  function setHatch(on) {
    state.hatch = on;
    map.setLayoutProperty("hex-insuf", "visibility", on ? "visible" : "none");
  }
  // Basemap layer toggles (city labels/dots; admin-1 "regional" boundary lines).
  const CITY_LAYERS = ["place_city_large", "place_city", "place_town"];
  function setBasemapLayers(ids, on) {
    for (const id of ids)
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
  }
  function setCities(on) { state.cities = on; setBasemapLayers(CITY_LAYERS, on); }
  function setRegional(on) { state.regional = on; setBasemapLayers(["boundary_state"], on); }

  // ---------- chrome ----------
  function buildChips() {
    const box = el("regionChips");
    box.innerHTML = "";
    const ids = state.regionsGeo.features.map((f) => f.properties.id);
    for (const rid of ids) {
      const prof = state.regions[rid] || {};
      const chip = document.createElement("div");
      chip.className = "chip"; chip.dataset.rid = rid;
      chip.textContent = prof.display_name || rid;
      chip.addEventListener("click", () => {
        if (state.activeRegion === rid) { closeRegion(); return; }
        flyToRegion(rid); openRegion(rid);
      });
      box.appendChild(chip);
    }
  }
  function flyToRegion(rid) {
    const f = state.regionsGeo.features.find((x) => x.properties.id === rid);
    if (!f) return;
    const rings = ringsOf(f.geometry);
    let minX = 180, minY = 90, maxX = -180, maxY = -90;
    for (const ring of rings) for (const [x, y] of ring) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    }
    map.fitBounds([[minX, minY], [maxX, maxY]], { padding: 90, maxZoom: 6, duration: 700 });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (m) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  }
  function toast(msg) {
    const t = el("toast"); t.textContent = msg; t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 2200);
  }
  function fail(e) {
    console.error(e);
    el("loader").querySelector(".msg").textContent = "signal lost — see console";
  }

  // ---------- intro / orientation ----------
  const INTRO_KEY = "dr_intro_v1";
  function showIntro() { el("intro").hidden = false; }
  function hideIntro() {
    el("intro").hidden = true;
    try { localStorage.setItem(INTRO_KEY, "1"); } catch (e) {}
  }
  function maybeShowIntro() {
    let seen = false;
    try { seen = localStorage.getItem(INTRO_KEY); } catch (e) {}
    if (!seen) showIntro();
  }

  // ---------- boot ----------
  async function boot() {
    const [manifest, baselines, regionsGeo, regions, events, airspaceGeo, airspace] =
      await Promise.all([
        getJSON("data/manifest.json"),
        getJSON("data/baselines.json").catch(() => ({ hexes: {}, std_floor: 0.02 })),
        getJSON("content/regions.geojson").catch(() => ({ type: "FeatureCollection", features: [] })),
        getJSON("content/regions.json").catch(() => ({ regions: [] })),
        getJSON("content/events.json").catch(() => ({ events: [] })),
        getJSON("content/airspace.geojson").catch(() => ({ type: "FeatureCollection", features: [] })),
        getJSON("content/airspace.json").catch(() => ({ zones: [] })),
      ]);
    state.manifest = manifest;
    state.baselines = baselines.hexes || {};
    state.stdFloor = baselines.std_floor || 0.02;
    state.anomalyClip = manifest.anomaly_clip || 6;
    state.floor = manifest.min_aircraft_floor || 5;
    state.regionsGeo = regionsGeo;
    state.regions = Object.fromEntries((regions.regions || []).map((r) => [r.id, r]));
    state.events = events.events || [];
    state.eventsDraft = !!events.draft;
    state.regionsDraft = !!regions.draft;   // file-level draft flag from regions.json
    state.airspaceGeo = airspaceGeo;
    state.airspace = Object.fromEntries((airspace.zones || []).map((z) => [z.id, z]));
    addAirspace();

    // (legend text is set by setMode below, called after controls are wired)

    // scrubber bounds
    const n = manifest.days.length;
    el("slider").max = Math.max(0, n - 1);
    el("slider").value = n - 1;
    buildTicks();
    buildChips();

    // wire controls
    document.querySelectorAll("#modeToggle button").forEach((b) =>
      b.addEventListener("click", () => setMode(b.dataset.mode)));
    const quietEl = el("quietToggle"), hatchEl = el("hatchToggle"),
          airspaceEl = el("airspaceToggle"),
          citiesEl = el("citiesToggle"), regionalEl = el("regionalToggle");
    quietEl.checked = state.quiet;      // default on
    hatchEl.checked = state.hatch;      // default off
    airspaceEl.checked = state.airspaceOn;  // default on
    citiesEl.checked = state.cities;    // default on
    regionalEl.checked = state.regional;// default off
    quietEl.addEventListener("change", (e) => setQuiet(e.target.checked));
    hatchEl.addEventListener("change", (e) => setHatch(e.target.checked));
    airspaceEl.addEventListener("change", (e) => setAirspace(e.target.checked));
    citiesEl.addEventListener("change", (e) => setCities(e.target.checked));
    regionalEl.addEventListener("change", (e) => setRegional(e.target.checked));
    setQuiet(state.quiet);           // apply initial visibility to the carpet layer
    setCities(state.cities);
    setRegional(state.regional);
    el("slider").addEventListener("input", (e) => {
      if (state.playing) togglePlay();
      goTo(+e.target.value);
    });
    el("playBtn").addEventListener("click", togglePlay);
    el("drClose").addEventListener("click", closeRegion);
    el("introGo").addEventListener("click", hideIntro);
    el("helpBtn").addEventListener("click", showIntro);
    // Legend is tap-collapsible; on phones it starts collapsed so it never
    // covers the map (collapse styling is mobile-only, so this is a no-op on
    // desktop). The map's color key stays reachable — the mobile contract.
    el("legendTitle").addEventListener("click", () => el("legend").classList.toggle("collapsed"));
    if (window.matchMedia && window.matchMedia("(max-width: 760px)").matches)
      el("legend").classList.add("collapsed");
    document.addEventListener("keydown", (e) => {
      if (!el("intro").hidden) { if (e.key === "Escape") hideIntro(); return; }
      if (e.key === "ArrowLeft") goTo(state.idx - 1);
      else if (e.key === "ArrowRight") goTo(state.idx + 1);
      else if (e.key === " ") { e.preventDefault(); togglePlay(); }
      else if (e.key === "Escape") closeRegion();
    });

    setMode(state.mode);      // sync legend/buttons to the default view
    await goTo(n - 1);        // newest day
    el("loader").classList.add("hide");
    maybeShowIntro();
  }

  // kick off
  if (document.readyState !== "loading") initMap();
  else document.addEventListener("DOMContentLoaded", initMap);
})();
