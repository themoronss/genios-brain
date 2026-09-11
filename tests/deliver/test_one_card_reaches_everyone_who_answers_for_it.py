"""F1 — one situation, one card, and everyone whose job it is.

    pytest tests/deliver/test_one_card_reaches_everyone_who_answers_for_it.py -q

THE CARD STAYS ONE ROW, AND THAT IS THE DESIGN, not a limitation worked around. `cards` carries
`cards_one_per_signal` (migration 0008:31), three writers upsert on that key
(`card_build_claims`, `cards`, `agent_claims`), refresh-in-place rewrites the WORDS of the same
row while keeping its `card_id`, queue state, snooze and feedback history, and four separate
reads join `cards k join signals s`. Widening that key would make one situation two lines in the
morning count and two entries in the per-recipient budget, and would break the refresh outright.

So the people a card reaches ride BESIDE it, in `card_recipients` (migration 0135), written from
the seats whose DECLARED responsibility (`seat_responsibilities`, 0131) covers a slice the
situation names.

WHAT "A SLICE THE SITUATION NAMES" MEANS. A tenant declares `client = Peak XV`. The situation
carries `organization.name`, or the person it anchors on `works_at` a company node called that.
`scope_pairs` turns the situation's facts and attributes into every `(kind, key)` pair it could
be answered for — the RAW PATH is always one of them, so a tenant that declares in the engine's
own words needs no bridge at all, and each alias word (`client`, `account`, `firm`, …) is a
second kind for the same value. The bridges are shipped DEFAULTS; a corpus adds its own under
`responsibility_scopes:`.

EMPTY ON DAY ONE. A tenant that declared nothing has no responsibilities, so `scope_pairs` finds
nobody, `co_recipients` is `()`, no row is written, the queue is byte-identical and the outbox
sends exactly one delivery. Every test below that asserts a co-recipient first has to declare
one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.execution import AudienceClass
from genios_engine.executive.assignment import (
    Responsibility,
    StaticSeatDirectory,
    _answering,
    _others,
    resolve_owner,
    scope_aliases,
    scope_pairs,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def facts(**kw):
    return {k: {"value": v, "confidence": 1.0, "authority_rank": 3} for k, v in kw.items()}


def resp(seat, kind, key, **kw):
    return Responsibility(seat_id=seat, scope_kind=kind, scope_key=key, **kw)


def directory(**seats):
    return StaticSeatDirectory(seats=seats)


# =============================================================================================
# What a situation is ABOUT, in the words a business uses for it.
# =============================================================================================
def test_the_raw_fact_path_is_always_a_scope_kind():
    """A tenant that declares `scope_kind = 'organization.name'` needs no bridge, no alias and
    no corpus entry. This is what stops the alias table from being a gate."""
    pairs = scope_pairs(facts(**{"organization.name": "Peak XV"}), None)

    assert ("organization.name", "peak xv") in pairs


def test_a_business_word_reaches_the_fact_that_carries_it():
    pairs = scope_pairs(facts(**{"organization.name": "Peak XV"}), None)

    assert ("client", "peak xv") in pairs
    assert ("account", "peak xv") in pairs
    assert ("firm", "peak xv") in pairs


def test_the_firm_a_person_belongs_to_counts():
    """`card_builder._group_memberships` puts the `works_at` company on the attrs, because a
    responsibility over a fund must match a card anchored on a partner there — and the partner's
    own node carries no `organization.name` fact at all."""
    pairs = scope_pairs({}, {"works_at": "Peak XV"})

    assert ("client", "peak xv") in pairs


def test_a_quoted_sentence_is_not_a_territory():
    """Facts hold prose too. Matching a declared scope against a 600-character quote is how a
    responsibility silently starts covering everything."""
    pairs = scope_pairs(facts(**{"organization.name": "x" * 400}), None)

    assert pairs == ()


def test_nothing_named_is_no_pairs():
    assert scope_pairs({}, {}) == ()
    assert scope_pairs(None, None) == ()


def test_a_corpus_may_add_a_word_the_engine_never_shipped(monkeypatch):
    """`ward: [patient.ward]` in a `domain.yaml` — the whole point of the alias table being a
    DEFAULT rather than the vocabulary. An authored word ADDS and never removes."""
    import genios_engine.platform.corpus as corpus
    monkeypatch.setattr(corpus, "authored_domains", lambda: iter([
        ("health", {"responsibility_scopes": {"ward": ["patient.ward"]}})]))

    aliases = scope_aliases()

    assert aliases["ward"] == ("patient.ward",)
    assert "organization.name" in aliases["client"], "a shipped word is not lost"


def test_an_unreadable_corpus_leaves_the_shipped_words_alone(monkeypatch):
    import genios_engine.platform.corpus as corpus
    monkeypatch.setattr(corpus, "authored_domains",
                        lambda: (_ for _ in ()).throw(OSError("gone")))

    assert "organization.name" in scope_aliases()["client"]


# =============================================================================================
# Who is told, and who owns it — two different questions.
# =============================================================================================
def test_a_declared_responsibility_does_not_displace_the_entity_owner():
    """Rule 1 still wins. The regional manager is TOLD; the deal's owner still owns it."""
    d = directory(
        **{"seat-deb": {"email": "deb@acme.test", "active": True},
           "seat-reg": {"email": "reg@acme.test", "active": True,
                        "responsibilities": [resp("seat-reg", "client", "Peak XV")]}})

    a = resolve_owner(facts=facts(**{"deal.owner": "deb@acme.test",
                                     "organization.name": "Peak XV"}), attrs=None, directory=d)

    assert (a.seat_id, a.reason_code) == ("seat-deb", "rule1_owner")
    assert [r.seat_id for r in a.co_recipients] == ["seat-reg"]


def test_a_declared_owner_takes_a_card_nobody_else_owns():
    """Rule 2b. Before this the card fell to rule 3 and sat in the admin queue while the person
    whose territory it is was never named."""
    d = directory(**{"seat-reg": {"email": "reg@acme.test", "active": True,
                                  "responsibilities": [resp("seat-reg", "client", "Peak XV")]},
                     "seat-adm": {"email": "adm@acme.test", "active": True, "role": "admin"}})

    a = resolve_owner(facts=facts(**{"organization.name": "Peak XV"}), attrs=None, directory=d)

    assert (a.seat_id, a.reason_code) == ("seat-reg", "rule2b_responsibility")
    assert a.audience is AudienceClass.OWNER


def test_an_inferred_responsibility_may_be_told_and_may_never_own():
    """THE ONE FAILURE THIS CONCEPT COULD INTRODUCE. `Responsibility.narrows` is False for an
    inferred row — "she probably handles the West's mail" — and hiding a real situation from the
    admin on the strength of a guess is a silent false negative."""
    d = directory(**{"seat-guess": {"email": "g@acme.test", "active": True,
                                    "responsibilities": [resp("seat-guess", "client", "Peak XV",
                                                              source="inferred")]},
                     "seat-adm": {"email": "adm@acme.test", "active": True, "role": "admin"}})

    a = resolve_owner(facts=facts(**{"organization.name": "Peak XV"}), attrs=None, directory=d)

    assert a.reason_code == "rule3_admin_queue"
    assert a.queue_seat == "seat-adm"
    assert [r.seat_id for r in a.co_recipients] == ["seat-guess"], "told, not made the owner"


def test_only_an_owns_accountability_can_take_the_card():
    """`covers`, `reviews` and `informed` are all real declarations and none of them says "this
    is mine to do"."""
    d = directory(**{"seat-r": {"email": "r@acme.test", "active": True,
                                "responsibilities": [resp("seat-r", "client", "Peak XV",
                                                          accountability="reviews")]},
                     "seat-adm": {"email": "adm@acme.test", "active": True, "role": "admin"}})

    a = resolve_owner(facts=facts(**{"organization.name": "Peak XV"}), attrs=None, directory=d)

    assert a.reason_code == "rule3_admin_queue"
    assert [r.seat_id for r in a.co_recipients] == ["seat-r"]


def test_several_declared_owners_resolve_the_same_way_every_day():
    """A load-balanced choice would land one situation on different people on different days —
    the failure `resolve_owner`'s docstring already refuses for its other rules."""
    d = directory(**{"seat-b": {"email": "b@acme.test", "active": True,
                                "responsibilities": [resp("seat-b", "client", "Peak XV")]},
                     "seat-a": {"email": "a@acme.test", "active": True,
                                "responsibilities": [resp("seat-a", "client", "Peak XV")]}})

    first = resolve_owner(facts=facts(**{"organization.name": "Peak XV"}), attrs=None, directory=d)
    again = resolve_owner(facts=facts(**{"organization.name": "Peak XV"}), attrs=None, directory=d)

    assert first.seat_id == again.seat_id == "seat-a"
    assert [r.seat_id for r in first.co_recipients] == ["seat-b"], "the other is still told"


def test_the_owner_is_never_their_own_co_recipient():
    d = directory(**{"seat-a": {"email": "a@acme.test", "active": True,
                                "responsibilities": [resp("seat-a", "client", "Peak XV")]}})

    a = resolve_owner(facts=facts(**{"organization.name": "Peak XV"}), attrs=None, directory=d)

    assert a.seat_id == "seat-a"
    assert a.co_recipients == ()


def test_one_seat_appears_once_at_its_tightest_accountability():
    answering = (resp("seat-x", "client", "Peak XV", accountability="informed"),
                 resp("seat-x", "account", "Peak XV", accountability="owns"))

    out = _others(answering, "seat-owner")

    assert [(r.seat_id, r.accountability) for r in out] == [("seat-x", "owns")]


# =============================================================================================
# A term that ended, and a tenant that declared nothing.
# =============================================================================================
def test_a_responsibility_that_ended_stops_applying_by_itself():
    d = directory(**{"seat-old": {"email": "o@acme.test", "active": True,
                                  "responsibilities": [
                                      resp("seat-old", "client", "Peak XV",
                                           valid_from=NOW - timedelta(days=60),
                                           valid_until=NOW - timedelta(days=1))]},
                     "seat-adm": {"email": "adm@acme.test", "active": True, "role": "admin"}})

    assert d.answerable_for([("client", "peak xv")], NOW) == ()


def test_a_tenant_that_declared_nothing_is_unchanged():
    """THE DAY-ONE PROPERTY. No declarations means the same recipient, the same rule and no
    extra rows — which is every tenant on the day this ships."""
    d = directory(**{"seat-adm": {"email": "adm@acme.test", "active": True, "role": "admin"}})

    a = resolve_owner(facts=facts(**{"organization.name": "Peak XV"}), attrs=None, directory=d)

    assert (a.reason_code, a.queue_seat, a.co_recipients) == ("rule3_admin_queue", "seat-adm", ())


def test_a_directory_that_predates_the_question_answers_nothing():
    """`_answering` is called with whatever directory the caller has. One that has never heard
    of `answerable_for` must not raise into a card build."""
    class Old:
        def active_seat(self, ref):
            return None

    assert _answering(Old(), facts(**{"organization.name": "Peak XV"}), None) == ()


def test_a_directory_that_raises_has_said_nothing():
    class Angry:
        def answerable_for(self, pairs, at=None):
            raise OSError("down")

    assert _answering(Angry(), facts(**{"organization.name": "Peak XV"}), None) == ()


# =============================================================================================
# The card, the queue and the outbox.
# =============================================================================================
def test_the_builder_reads_the_owner_first_and_the_others_after():
    """`resolve_assignee` stays THE answer to "who gets this" — one question, one two-tuple, the
    name every caller and test in the engine binds to. Being TOLD is a second question and a
    second read, so a fake store that knows nothing about responsibilities still builds a card."""
    import inspect

    from genios_engine.deliver import card_builder

    src = inspect.getsource(card_builder.build_draft)

    assert "assignee, rule = resolve_assignee(store, org_id, facts, scoped_attrs)" in src
    assert src.index("resolve_assignee(") < src.index("co_recipients_for(")


def test_the_co_recipient_read_never_raises_into_a_build():
    """A card that cannot compute who ELSE to tell is still a correct card for its owner."""
    import inspect

    from genios_engine.deliver import router

    src = inspect.getsource(router.co_recipients_for)

    assert "except Exception" in src
    assert "return ()" in src


def test_nothing_declared_writes_no_row():
    """`_stamp_recipients` must not open a statement for the ordinary card. A hermetic card test
    builds three tables and a DELETE against one it never created would make every such test
    depend on a feature it does not use."""
    from genios_engine.deliver.store import CardStore

    calls = []

    class Conn:
        def execute(self, *a, **k):
            calls.append(a)
            raise AssertionError("no statement may run")

    assert CardStore._stamp_recipients(Conn(), "org", "card", (), owner="seat-a") == 0
    assert calls == []


def test_the_owner_is_dropped_from_the_stamped_rows():
    from genios_engine.deliver.store import CardStore

    seen = []

    class Conn:
        def execute(self, stmt, params=None):
            seen.append((str(stmt), params))
            return type("R", (), {"rowcount": 1})()

    CardStore._stamp_recipients(
        Conn(), "org", "card",
        [{"seat_id": "seat-a", "accountability": "owns", "scope_kind": "client",
          "scope_key": "Peak XV", "source": "admin_declared"},
         {"seat_id": "seat-b", "accountability": "covers", "scope_kind": "client",
          "scope_key": "Peak XV", "source": "admin_declared"}],
        owner="seat-a")

    inserts = [p for s, p in seen if "insert into card_recipients" in s]
    assert [p["s"] for p in inserts] == ["seat-b"]


def test_the_queue_shows_a_seat_what_it_answers_for():
    import inspect

    from genios_engine.deliver.store import CardStore

    src = inspect.getsource(CardStore.queue)

    assert "from card_recipients cr where cr.org_id=k.org_id" in src
    assert "rows = self._your_part(c, org_id, seat, rows)" in src


def test_a_co_recipients_delivery_never_interrupts():
    """Being told about a card that is somebody else's to act on is not a reason to break
    anyone's quiet hours. Only the owner's row carries the interrupt the band earned."""
    import inspect

    from genios_engine.deliver import outbox

    src = inspect.getsource(outbox.enqueue_pending)
    extra = src[src.index("for extra in _co_recipients("):]

    assert ":cclass,false,:i)" in extra
    assert "on conflict (org_id, card_id, channel, coalesce(recipient, '')) do nothing" in extra


def test_the_message_says_what_is_theirs_and_what_is_not():
    from genios_engine.deliver.channels.slack import your_part_line

    line = your_part_line({"accountability": "covers", "scope_kind": "client",
                           "scope_key": "Peak XV", "owner_email": "deb@acme.test"})

    assert "cover Peak XV" in line
    assert "owner: deb@acme.test" in line


def test_the_owners_own_message_is_unchanged():
    from genios_engine.deliver.channels.slack import format_card_message, your_part_line

    card = {"headline": "Peak XV has gone quiet", "situation": "Two partners, no reply.",
            "urgency_band": "high", "card_id": "c1", "level": "review"}

    assert your_part_line(None) == ""
    assert format_card_message(card) == format_card_message(card, your_part=None)


def test_a_word_the_engine_does_not_know_is_stated_not_dropped():
    from genios_engine.deliver.channels.slack import your_part_line

    line = your_part_line({"accountability": "escalates", "scope_kind": "ward",
                           "scope_key": "B4"})

    assert "escalates" in line
    assert "B4" in line
