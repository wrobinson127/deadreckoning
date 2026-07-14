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
    idx: 0,
    playing: false,
    playTimer: null,
    geomIndex: new Set(),
    geomFC: { type: "FeatureCollection", features: [] },
    prevActive: new Set(),
    activeRegion: null,
  };

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

  function styleFor(rec) {
    if (rec.n_aircraft < state.floor) return { k: "insuf", c: null, op: null };
    if (state.mode === "raw") {
      return { k: "val", c: DR_COLOR.raw(rec.bad_ratio), op: opFor(rec.bad_ratio) };
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
      map.setFeatureState({ source: "hexes", id: r.hex }, { c: st.c, k: st.k, op: st.op });
      nextActive.add(r.hex);
      if (r.confidence === "high") nHigh++;
      if (st.k === "insuf") nInsuf++;
    }
    // clear hexes that were shown yesterday but not today
    for (const h of state.prevActive) {
      if (!nextActive.has(h)) map.setFeatureState({ source: "hexes", id: h }, { c: null, k: "none", op: 0 });
    }
    state.prevActive = nextActive;
    state.dayData = entry.byHex;
    el("scrubMeta").textContent =
      `${entry.records.length.toLocaleString()} cells · ${nHigh.toLocaleString()} high-confidence`;
  }

  async function goTo(idx) {
    idx = Math.max(0, Math.min(state.manifest.days.length - 1, idx));
    state.idx = idx;
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
  }

  // ---------- hover readout ----------
  function wireHexInteraction() {
    map.on("mousemove", "hex-fill", (e) => {
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
      // region hit-test on click (point in region polygon)
      const rid = regionAt(e.lngLat.lng, e.lngLat.lat);
      if (rid) openRegion(rid);
    });
  }

  function showReadout(rec) {
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
    body.innerHTML = `<span class="draft-tag">DRAFT — pending author review</span>`;

    // trend sparkline
    let series = [];
    try { series = (await getJSON(`data/regions/${rid}.json`)).series || []; } catch (e) {}
    body.insertAdjacentHTML("beforeend",
      `<div class="section-label">90-day trend · mean degraded ratio</div>
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
      let i = days.indexOf(e.date);
      let left;
      if (i >= 0) left = n === 1 ? 50 : (i / (n - 1)) * 100;
      else if (e.date < first) left = 0;
      else if (e.date > last) left = 100;
      else continue;
      const pin = document.createElement("div");
      pin.className = "tick event";
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
    const note = e.editorial_note
      ? `<div class="e-note">${escapeHtml(e.editorial_note)}</div>` : "";
    card.innerHTML = `<div class="e-date">${e.date} · ${e.type || ""}${disputed}</div>
      <div class="e-title">${escapeHtml(e.title)}</div>
      <div class="e-one">${escapeHtml(e.one_line || "")}</div>${note}`;
    const wrap = target.closest(".track-wrap").getBoundingClientRect();
    const tr = target.getBoundingClientRect();
    card.style.left = Math.min(window.innerWidth - 300, tr.left) + "px";
    card.classList.add("show");
  }
  function hideEventCard() { el("eventCard").classList.remove("show"); }

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
    el("legendTitle").textContent = mode === "anomaly"
      ? "Anomaly vs baseline (σ)" : "Aircraft with degraded GPS";
    el("legendRamp").className = "ramp " + (mode === "anomaly" ? "anom" : "raw");
    el("legLo").textContent = mode === "anomaly" ? "normal" : "0%";
    el("legHi").textContent = mode === "anomaly" ? state.anomalyClip + "σ+" : "100%";
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
    const [manifest, baselines, regionsGeo, regions, events] = await Promise.all([
      getJSON("data/manifest.json"),
      getJSON("data/baselines.json").catch(() => ({ hexes: {}, std_floor: 0.02 })),
      getJSON("content/regions.geojson").catch(() => ({ type: "FeatureCollection", features: [] })),
      getJSON("content/regions.json").catch(() => ({ regions: [] })),
      getJSON("content/events.json").catch(() => ({ events: [] })),
    ]);
    state.manifest = manifest;
    state.baselines = baselines.hexes || {};
    state.stdFloor = baselines.std_floor || 0.02;
    state.anomalyClip = manifest.anomaly_clip || 6;
    state.floor = manifest.min_aircraft_floor || 5;
    state.regionsGeo = regionsGeo;
    state.regions = Object.fromEntries((regions.regions || []).map((r) => [r.id, r]));
    state.events = events.events || [];

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
    const quietEl = el("quietToggle"), hatchEl = el("hatchToggle");
    quietEl.checked = state.quiet;   // default on
    hatchEl.checked = state.hatch;   // default off
    quietEl.addEventListener("change", (e) => setQuiet(e.target.checked));
    hatchEl.addEventListener("change", (e) => setHatch(e.target.checked));
    setQuiet(state.quiet);           // apply initial visibility to the carpet layer
    el("slider").addEventListener("input", (e) => {
      if (state.playing) togglePlay();
      goTo(+e.target.value);
    });
    el("playBtn").addEventListener("click", togglePlay);
    el("drClose").addEventListener("click", closeRegion);
    el("introGo").addEventListener("click", hideIntro);
    el("helpBtn").addEventListener("click", showIntro);
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
