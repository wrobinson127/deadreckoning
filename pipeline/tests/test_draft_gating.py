"""Regression guard for the region DRAFT-banner leak.

The bug (caught by the pre-launch gauntlet): the region drawer rendered
``<span class="draft-tag">DRAFT — pending author review</span>`` UNCONDITIONALLY
for every region, so all Walker-approved (draft:false) regions were labelled
"DRAFT — pending author review" on the public site. Events gated correctly;
regions did not.

Two invariants, both cheap and build-time:
1. Content: regions.json is approved (file draft:false, no per-region draft:true).
2. Gating: app.js only shows the region draft badge for genuinely-draft content
   in preview builds — the DRAFT literal must be inside a PREVIEW-gated
   conditional, never assigned unconditionally.
"""
from __future__ import annotations

import json
import os
import re

from pipeline.paths import repo_path

_REGIONS_JSON = repo_path("content", "regions.json")
_APP_JS = repo_path("site", "js", "app.js")
_DRAFT_LITERAL = "DRAFT — pending author review"


def test_regions_content_is_approved():
    """Current content is approved, so no region should ever show the badge."""
    with open(_REGIONS_JSON, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data.get("draft") is False, "regions.json file-level draft must be False (approved)"
    drafts = [r.get("id") for r in data.get("regions", []) if r.get("draft")]
    assert not drafts, f"unexpected draft:true regions: {drafts}"


def test_region_draft_badge_is_gated_not_hardcoded():
    """The exact regression: the DRAFT badge must be conditional, not unconditional."""
    with open(_APP_JS, encoding="utf-8") as fh:
        src = fh.read()

    # The file-level draft flag must be read into state (the gate exists).
    assert "state.regionsDraft" in src, "app.js must read regions.json's draft flag into state.regionsDraft"

    # The DRAFT literal must appear, and every statement that assigns it to
    # innerHTML must be PREVIEW-gated. Guard against the old unconditional form
    # `body.innerHTML = `<span class="draft-tag">DRAFT ...`.
    assert _DRAFT_LITERAL in src, "expected the region draft badge literal to still exist"
    unconditional = re.search(
        r"innerHTML\s*=\s*`<span class=\"draft-tag\">DRAFT", src
    )
    assert unconditional is None, (
        "region draft badge is assigned unconditionally — it must be gated on "
        "(regionsDraft/prof.draft) && PREVIEW so approved regions show no badge"
    )

    # The badge-producing expression must reference PREVIEW (preview-only) and a
    # region draft flag. Check the neighbourhood of the literal.
    idx = src.index(_DRAFT_LITERAL)
    window = src[max(0, idx - 400): idx + 200]
    assert "PREVIEW" in window, "region draft badge must be gated on PREVIEW (preview builds only)"
    assert re.search(r"regionDraft|regionsDraft|prof\.draft", window), (
        "region draft badge must be gated on the region draft flag"
    )
