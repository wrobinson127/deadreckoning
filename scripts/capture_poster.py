#!/usr/bin/env python3
"""Render the DeadReckoning hero / OG poster: the Degraded% Baltic-bloom frame.

This is the *reproducible* generator for ``site/assets/og-image.jpg`` — the
signature frame shown behind the loader (the "acquiring signal" sweep runs over
it) and used as the Open Graph / social card. Re-run it whenever the map's look
changes (e.g. after the light-mode batch) so the poster never drifts from the
live instrument.

Frame: the default **Degraded %** view, centred on the Baltic / Kaliningrad
bloom over the quiet-coverage carpet, UI chrome hidden, at the 1200x630 Open
Graph spec. The source date is whatever the served build shows (the latest day
in the committed archive).

Prereqs:
    pip install playwright && python -m playwright install chromium
    # serve the assembled site first (see CLAUDE.md), e.g.:
    #   rm -rf _site && mkdir _site && cp -r site/* _site/ && cp -r data _site/ \
    #     && cp -r content _site/ && python -m http.server -d _site 8777

Usage:
    python scripts/capture_poster.py [--url http://localhost:8777] \
        [--out site/assets/og-image.jpg] [--width 1200] [--height 630]

Notes:
    * Needs the localhost debug handle ``window.__drMap`` (set only on
      localhost/127.0.0.1), so point --url at a localhost server.
    * Headless WebGL uses SwiftShader; if the OpenFreeMap CDN is slow the app
      falls back to its minimal basemap — the blooms + carpet still render, but
      re-run for the full basemap if the frame looks bare.
"""
from __future__ import annotations

import argparse
import sys

# Baltic / Kaliningrad bloom over calm Europe — the signature frame.
BALTIC_CENTER = [21.0, 57.5]
BALTIC_ZOOM = 4.2

HIDE_CHROME = """
  .topbar, .map-overlay, .scrubber, .loader, .intro-scrim, .nav-help,
  .maplibregl-ctrl, .maplibregl-control-container, .region-chips,
  .zone-card, .event-card, .toast { display: none !important; }
  #map { position: fixed !important; inset: 0 !important; }
  html, body { background: #0a0c0f !important; }
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Render the hero/OG poster frame.")
    ap.add_argument("--url", default="http://localhost:8777")
    ap.add_argument("--theme", choices=["dark", "light"], default="dark")
    ap.add_argument("--out", default=None,
                    help="default: og-image.jpg (dark) / og-image-light.jpg (light)")
    ap.add_argument("--width", type=int, default=1200)
    ap.add_argument("--height", type=int, default=630)
    args = ap.parse_args()
    if not args.out:
        args.out = ("site/assets/og-image-light.jpg" if args.theme == "light"
                    else "site/assets/og-image.jpg")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed: pip install playwright && "
              "python -m playwright install chromium", file=sys.stderr)
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--use-gl=angle", "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
            "--enable-webgl", "--hide-scrollbars",
        ])
        page = browser.new_page(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=1,
        )
        # pick the theme before the page's inline theme script runs
        page.add_init_script(
            "try{localStorage.setItem('dr_theme','%s')}catch(e){}" % args.theme)
        page.goto(args.url, wait_until="networkidle", timeout=60000)
        # Wait for the localhost debug handle + a fully-loaded style.
        page.wait_for_function("window.__drMap && window.__drMap.loaded()", timeout=60000)
        # Wait for the ARCHIVE to load + first render (loader gets .hide when the
        # app is ready) so the poster actually shows the blooms, not a bare map.
        page.wait_for_function(
            "(() => { const l = document.querySelector('.loader');"
            " return l && l.classList.contains('hide'); })()", timeout=90000)
        # Frame the Baltic bloom (default mode is already Degraded%).
        page.evaluate(
            "([c, z]) => window.__drMap.jumpTo({ center: c, zoom: z })",
            [BALTIC_CENTER, BALTIC_ZOOM],
        )
        # Let tiles + hex fills settle, then confirm the map is idle.
        page.wait_for_timeout(3500)
        page.wait_for_function(
            "new Promise(r => { const m = window.__drMap;"
            " m.once('idle', () => r(true)); if (!m.isMoving()) r(true); })",
            timeout=15000,
        )
        page.add_style_tag(content=HIDE_CHROME)
        page.wait_for_timeout(1200)
        page.screenshot(path=args.out, clip={
            "x": 0, "y": 0, "width": args.width, "height": args.height,
        })
        browser.close()
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
