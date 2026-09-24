"""L2-0 · which DOMAINS no corpus claims — declared, with a reason and a mover.

    pytest tests/context/test_no_domain_is_silently_dark.py -q

⛔ **THE THIRD PLACE THIS IDIOM IS NEEDED, AND THE ONLY ONE THAT HAD NO FILE.**

This layer already declares its silences twice, and both files carry the same rule:

* `patterns/routing.UNROUTED_PATTERN_TYPES` — *"which pattern situation types no domain claims —
  declared, with a reason and a mover"*
* `context/lane_health` — *"which readings are producing nothing, declared — with a reason and a
  mover"*, whose opening is this step's whole premise: *"A READING THAT RETURNS NOTHING IS
  INDISTINGUISHABLE FROM ONE THAT IS BROKEN... five lanes in this layer were dead for months while
  looking wired, and **every one was found by accident rather than by a check**."*

**Nothing covers DOMAINS.** `domain_spec` registers five; `Domain Expertise/` authors three. So
`fundraising` and `general` mint situations that no corpus can ever read, `l3_domain_for` answers
`None`, `live_lane()` refuses — and **on every tenant configuration, silently**.

The pilot tenant is a fundraising founder.

⛔ **DORMANT IS NOT BROKEN, AND THE DIFFERENCE IS THE WHOLE POINT** — `lane_health`'s sentence, and
it is why an unclaimed domain must be *declared* rather than merely counted. A domain nobody
authored is a decision. A domain nobody noticed is a defect.

**Checked in both directions**, exactly as the two existing files are: a registered domain that no
corpus claims and is not declared here fails; an entry here whose corpus has since been authored
fails just as loudly, so the table cannot rot into a list of things that used to be true.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_every_unclaimed_domain_is_declared_with_a_reason():
    """A domain L2 registers, that no authored corpus claims, must say so here — and say what
    would end it. *"A permanent exception list is a way to never fix anything, so every entry
    names the condition under which it stops being one."*"""
    from genios_engine.context.domain_silence import DARK_DOMAINS
    from genios_engine.context.domain_spec import registered_domains
    from genios_engine.reason.domain_shadow import l3_domain_for

    unclaimed = {d for d in registered_domains() if l3_domain_for(d) is None}

    assert unclaimed <= set(DARK_DOMAINS), (
        f"these domains mint situations no corpus can read, and nothing declares it: "
        f"{sorted(unclaimed - set(DARK_DOMAINS))}")


def test_a_domain_that_gained_a_corpus_is_removed_from_the_table():
    """The other direction, and the reason both existing files check it: a table that only ever
    grows becomes a list of things that used to be true."""
    from genios_engine.context.domain_silence import DARK_DOMAINS
    from genios_engine.reason.domain_shadow import l3_domain_for

    for domain in DARK_DOMAINS:
        assert l3_domain_for(domain) is None, (
            f"{domain!r} now resolves to a corpus — delete its row, the silence ended")


def test_every_entry_names_what_would_end_it():
    """A reason, not a label. Both sibling files require this and say why."""
    from genios_engine.context.domain_silence import DARK_DOMAINS

    for domain, reason in DARK_DOMAINS.items():
        assert len(reason) > 80, f"{domain}: a one-line reason is a label, not a mover"


def test_the_pilots_own_domain_is_named():
    """⛔ Not a generic guard. `fundraising` is the domain the pilot tenant lives in, it mints
    `investor_relationship` and `investor_contact` today, and every one of them dies unread."""
    from genios_engine.context.domain_silence import DARK_DOMAINS

    assert "fundraising" in DARK_DOMAINS
    assert "investor" in DARK_DOMAINS["fundraising"].lower()


def test_layer_two_really_does_mint_situations_for_a_dark_domain():
    """The claim this whole table rests on, asserted against `domain_spec` rather than believed:
    a dark domain is not one L2 ignores — it is one L2 serves and L3 cannot read."""
    from genios_engine.context.domain_silence import DARK_DOMAINS
    from genios_engine.context.domain_spec import spec_for

    for domain in DARK_DOMAINS:
        types = spec_for(domain).situation_types
        assert types, f"{domain} declares no situation types — it is not dark, it is absent"
