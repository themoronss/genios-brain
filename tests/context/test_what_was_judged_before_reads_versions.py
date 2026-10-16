"""STEP-14 · what was judged before reads a file card's VERSIONS — the advice the expert gave, each time it changed.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_what_was_judged_before_reads_versions.py -q

`context/file_judgments.judgments_for` (tree `yc2_w27_s14` M42.C2.L-data.V2.U03; STEP-14 §8.4 item 1). Until STEP-14
a file's new decision was a new card and the old one was expired REPLACED, so the expert saw a replaced card beside a
new one. A file's card now lives (`migrations/0220`, `platform/card_lifecycle.version_card`): one card, versioned. So
what was judged before reads each card's versions from its `card.versioned` events — each version's headline, when,
what changed and whether it was material, the first version's words from the event that replaced them — newest kept,
the cut counted; and the version events are no longer listed again among what happened to the card.
"""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import file_judgments as J
from genios_engine.contracts.card_version import VersionWords, version_of
from tests.context.test_a_file_knows_what_was_judged_before import (  # noqa: F401 — the fixture
    FILE, ORG, T0, _card, engine)

pytestmark = pytest.mark.pg


def _words(headline: str, **over) -> VersionWords:
    return VersionWords(**{"headline": headline, "situation": "Kestrel asked for the deck.", "lane": "decision",
                           "mode": "act", "ask": "loop:deck", "by_when": "2026-10-03", **over})


def _versions(c, card: str, heads: list[VersionWords], *, start=T0):
    """Version `card` through `heads` (heads[0] is version 1): one `card.versioned` event per version after it."""
    for n in range(1, len(heads)):
        v = version_of(heads[n - 1], heads[n], version=n + 1, signal_id=f"sig_{card}_v{n + 1}")
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, occurred_at) "
                       "values (:i, :c, :o, 'card.versioned', :cause, 'system', cast(:d as jsonb), :at)"),
                  {"i": f"ev_{card}_v{n + 1}", "c": card, "o": ORG, "cause": v.change,
                   "d": json.dumps({**v.as_mapping(), "from_signal": f"sig_{card}", "reopened": False}),
                   "at": start + timedelta(days=n)})
    c.execute(text("update cards set headline = :h, version = :v where card_id = :c"),
              {"h": heads[-1].headline, "v": len(heads), "c": card})


def test_a_versioned_card_is_one_card_with_its_versions(engine):
    v1, v2, v3 = (_words("Reply to Rahul with the deck"), _words("Send Rahul the deck by Friday", by_when="2026-10-09"),
                  _words("Send Rahul the deck by Friday", by_when="2026-10-09", situation="Rahul asked again on 6 Oct."))
    with engine.begin() as c:
        _card(c, "card_live", FILE, T0, events=(("card.created", None),))
        _versions(c, "card_live", [v1, v2, v3])
        got = J.judgments_for(c, ORG, FILE)
    [card] = got.cards
    assert card.headline == v3.headline
    assert [(v.version, v.headline, v.change, v.material) for v in card.versions] == [
        (1, v1.headline, "created", True), (2, v2.headline, "updated", True), (3, v3.headline, "reworded", False)]
    assert [v.at for v in card.versions] == [T0, T0 + timedelta(days=1), T0 + timedelta(days=2)]
    assert [v.changed for v in card.versions] == [(), ("headline", "by_when"), ("situation",)]
    assert [e.kind for e in card.events] == ["card.created"], "a version is said once — as a version"
    assert card.as_dict()["versions"][1] == {"version": 2, "headline": v2.headline, "change": "updated",
                                             "material": True, "changed": ["headline", "by_when"],
                                             "at": (T0 + timedelta(days=1)).isoformat()}


def test_a_card_never_versioned_has_no_versions(engine):
    with engine.begin() as c:
        _card(c, "card_once", FILE, T0, events=(("card.created", None),))
        got = J.judgments_for(c, ORG, FILE)
    [card] = got.cards
    assert card.versions == () and card.as_dict()["versions"] == []


def test_versions_are_bounded_newest_kept_and_the_cut_counted(engine):
    heads = [_words(f"Advice number {n}", ask=f"loop:{n}") for n in range(J.LIMITS["versions"] + 3)]
    with engine.begin() as c:
        _card(c, "card_long", FILE, T0)
        _versions(c, "card_long", heads)
        got = J.judgments_for(c, ORG, FILE)
    [card] = got.cards
    assert J.LIMITS["versions"] == 5, "the dossier carries a card's newest five versions"
    assert len(card.versions) == J.LIMITS["versions"] and got.cut["versions"] == 3
    assert card.versions[-1].headline == heads[-1].headline and card.versions[0].version == 4


def test_a_version_event_that_is_no_version_is_not_read_as_one(engine):
    """A malformed detail — written by hand, or by an older writer — is counted out, never shown as advice."""
    with engine.begin() as c:
        _card(c, "card_odd", FILE, T0)
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, detail, occurred_at) values "
                       "('ev_odd', 'card_odd', :o, 'card.versioned', 'updated', cast('{\"version\": 2}' as jsonb), "
                       ":at)"), {"o": ORG, "at": T0 + timedelta(days=1)})
        got = J.judgments_for(c, ORG, FILE)
    [card] = got.cards
    assert card.versions == () and got.cut["versions"] == 1
