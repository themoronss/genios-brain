"""STEP-11 · an investor situation is read through the Founder Office corpus, not through Sales.

    .venv/bin/python -m pytest tests/packs/test_founder_aliases.py -q

Tree `yc2_w27_s11 · M30.C1.L-logic.V1.U03`, `06` D2. `capability_resolver.DOMAIN_ALIASES` sent the L2
domains `fundraising` and `investor` to the Sales corpus, for a reason its comment gave as permanent —
that a corpus of its own "can never become a card" — and that `packs/wiring._corpus_packs` had since
made false (`03` F122). Both names now resolve to `founder_office`; the comment says why; and coverage
still knows both names are spoken for by the shipped `fundraising` requirement set, so no new coverage
domain appears for a corpus that capture never asks about.
"""
from __future__ import annotations

import inspect


def test_fundraising_and_investor_resolve_to_the_founder_office():
    from genios_engine.packs.compiler.capability_resolver import DOMAIN_ALIASES
    assert (DOMAIN_ALIASES["fundraising"], DOMAIN_ALIASES["investor"]) == (
        "founder_office", "founder_office")
    assert "sales" not in {DOMAIN_ALIASES["fundraising"], DOMAIN_ALIASES["investor"]}


def test_the_stale_reason_is_gone_and_the_true_one_is_named():
    from genios_engine.packs.compiler import capability_resolver
    source = inspect.getsource(capability_resolver)
    assert "can never become a card." not in source.replace('"can never become a card"', "")
    assert "_corpus_packs" in source


def test_the_corpus_side_resolves_the_l2_name_to_the_founder_corpus():
    """The resolver looks a `fundraising` situation up in the corpus the alias names — and that corpus
    exists in the catalog."""
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
    from genios_engine.packs.compiler.capability_resolver import DOMAIN_ALIASES
    catalog = ExpertBrainCatalog(default_authoring_root())
    assert DOMAIN_ALIASES["fundraising"] in catalog.domains


def test_coverage_still_knows_both_names_are_spoken_for():
    """`speaks_for` must not mistake the Founder Office for a new coverage domain, nor forget that
    `investor` is the shipped `fundraising` set under another name."""
    from genios_engine.capture.coverage.model import PACK_REQUIREMENTS, pack_requirements
    from genios_engine.platform.corpus import speaks_for
    for name in ("fundraising", "investor", "founder_office"):
        assert speaks_for(name, PACK_REQUIREMENTS), name
    assert "founder_office" not in pack_requirements()
    assert not speaks_for("clinic", PACK_REQUIREMENTS)
