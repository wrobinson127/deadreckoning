"""Release-tag resolution across upstream's shifting tag suffixes.

adsb.lol has not used one stable suffix for the archive's whole life. Six appear
across 2023-2026; config.RELEASE_TAG_SUFFIXES pins which we accept, in which
order, and two are excluded on purpose. Getting this wrong is silent and
expensive in both directions: too narrow and real days are written off as
permanent no-data holes (that bug cost 29 recoverable days); too wide and
mlatonly traces, which carry no aircraft-reported NIC, contaminate the measure.
"""
from __future__ import annotations

import pipeline.config as C
import pipeline.download as dl


def test_prod_is_tried_first():
    """An ordinary day must still resolve to prod-0 exactly as it always did."""
    assert dl._tag_variants("2026-07-13")[0] == "v2026.07.13-planes-readsb-prod-0"


def test_preference_order_is_stable():
    """Alternates only ever fill holes, so prod/staging must precede them."""
    got = dl._tag_variants("2025-06-01")
    assert got == [
        "v2025.06.01-planes-readsb-prod-0",
        "v2025.06.01-planes-readsb-staging-0",
        "v2025.06.01-planes-readsb-prod-0tmp",
        "v2025.06.01-planes-readsb-staging-0tmp",
        "v2025.06.01-planes-readsb-test-0",
    ]


def test_dashes_become_dots_in_every_variant():
    """Tags are YYYY.MM.DD; a stray dash silently 404s every candidate."""
    assert all("2023.02.16" in t for t in dl._tag_variants("2023-02-16"))
    assert not any("2023-02-16" in t for t in dl._tag_variants("2023-02-16"))


def test_mlatonly_is_never_accepted():
    """MLAT positions are ground-multilaterated, not aircraft-reported, so they
    carry no meaningful NIC. Accepting them would corrupt the measure."""
    assert not any("mlatonly" in t for t in dl._tag_variants("2026-05-06"))
    assert not any("mlatonly" in s for s in C.RELEASE_TAG_SUFFIXES)


def test_prod_1_is_never_accepted():
    """prod-1 is never a day's sole release (always alongside prod-0), so
    accepting it could only double-count a day already ingested."""
    assert not any(t.endswith("prod-1") for t in dl._tag_variants("2023-06-01"))
    assert "prod-1" not in C.RELEASE_TAG_SUFFIXES


def test_legacy_templates_still_agree_with_the_suffix_list():
    """The two original template constants are still exported; keep them
    consistent with the list so nothing drifts if either is edited alone."""
    dotted = "2024.03.05"
    variants = dl._tag_variants("2024-03-05")
    assert C.RELEASE_TAG_TEMPLATE.format(date=dotted) in variants
    assert C.RELEASE_STAGING_TEMPLATE.format(date=dotted) in variants
