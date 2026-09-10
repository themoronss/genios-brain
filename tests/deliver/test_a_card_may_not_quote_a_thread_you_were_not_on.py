"""P0 — an admin who was never on the thread received sentences quoted out of it.

    pytest tests/deliver/test_a_card_may_not_quote_a_thread_you_were_not_on.py -q

Four links, each verified against the checkout before this file was written:

  1. `source_events.visibility_scope` and `.visibility_principals` EXIST
     (`migrations/0067_source_event_visibility.sql:11-12`).
  2. `capture/visibility_rules.py:78` fills them with `scope=PARTICIPANTS` and the real
     addresses for EVERY communication source — mail, chat, meetings, calendar.
  3. `card_builder._QUOTES_SQL` lifted `sr.evidence` — the verbatim sentence, 300 characters —
     with NO filter on either column.
  4. `enqueue_pending` writes `seat = r.assignee`, and `assignment.resolve_owner` rule 3 routes
     every unowned card to `admins[0]`, which is currently almost every card.

So on a multi-seat tenant with more than one connected mailbox, an admin who was not a
participant received, in the card body, sentences quoted from a participants-scoped thread.

`deliver/audience.resolve_recipient` was written for exactly this and has NO production caller:
its only caller is `outbox.shadow_resolve_v2`, which sends nothing and passes
`can_view=lambda _seat: True` with the comment *"Org-scope default until card rows carry the
evidence ACL."* This is the card row carrying it.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.deliver.card_builder import _visible_quotes

pytestmark = pytest.mark.unit

ORG = "org1"


class _Store:
    def __init__(self, engine=None):
        self.engine = engine


@pytest.fixture
def seats():
    """A real `org_seats` table, because the filter reads one."""
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table org_seats (org_id text, seat_id text, email text)"))
        for seat, email in (("seat-rohit", "rohit@genios.ai"),
                            ("seat-ops", "ops@genios.ai")):
            c.execute(text("insert into org_seats values (:o, :s, :e)"),
                      {"o": ORG, "s": seat, "e": email})
    return _Store(engine)


def participants(*people):
    return {"kind": "question", "quote": "our runway is four months",
            "visibility_scope": "participants",
            "visibility_principals": tuple(people)}


ORG_WIDE = {"kind": "question", "quote": "the uploaded policy says X",
            "visibility_scope": "org", "visibility_principals": ()}

PRE_0067 = {"kind": "question", "quote": "captured before the column existed",
            "visibility_scope": None, "visibility_principals": ()}


def kept(quotes, seat, store):
    return [q["quote"] for q in _visible_quotes(quotes, seat, store=store, org_id=ORG)]


# =============================================================================================
# The leak.
# =============================================================================================
def test_an_admin_who_was_not_on_the_thread_does_not_get_its_words(seats):
    """THE WHOLE POINT. Ops was never a participant; the sentence is not theirs to read."""
    quote = participants("joseph@afore.vc", "rohit@genios.ai")

    assert kept([quote], "seat-ops", seats) == []


def test_a_participant_still_gets_their_own_thread(seats):
    """The guard may not become "drop every quote" — that would gut every card."""
    quote = participants("joseph@afore.vc", "rohit@genios.ai")

    assert kept([quote], "seat-rohit", seats) == ["our runway is four months"]


def test_the_match_is_case_and_space_insensitive(seats):
    """An address stored with different casing is the same person, and a leak that depends on
    capitalisation is still a leak — in whichever direction it lands."""
    quote = participants("  ROHIT@Genios.AI  ")

    assert kept([quote], "seat-rohit", seats) == ["our runway is four months"]


def test_only_the_forbidden_quote_is_dropped(seats):
    """A card built over three sources keeps the two the recipient may see."""
    got = kept([participants("joseph@afore.vc"), ORG_WIDE, PRE_0067], "seat-ops", seats)

    assert got == ["the uploaded policy says X", "captured before the column existed"]


# =============================================================================================
# What org scope still means.
# =============================================================================================
def test_a_deliberate_source_stays_visible_to_everybody(seats):
    """A source the tenant handed its own system on purpose — an upload, a CRM row — is ORG,
    and every seat may see it. Only PARTICIPANTS narrows."""
    assert kept([ORG_WIDE], "seat-ops", seats) == ["the uploaded policy says X"]


def test_a_row_captured_before_the_column_existed_reads_as_org_visible(seats):
    """Deliberate. Those events predate `0067`, the tenant has been seeing them all along, and
    retroactively hiding them would be a behaviour change dressed as a fix."""
    assert kept([PRE_0067], "seat-ops", seats) == ["captured before the column existed"]


# =============================================================================================
# The two fail-open paths, each narrow and each argued.
# =============================================================================================
def test_an_unrouted_card_keeps_its_quotes(seats):
    """`seat_id` is None when the card goes to the admin QUEUE rather than to a named person.
    Dropping every participants-scoped quote there would silently gut the admin view; the
    honest boundary for a queue is the tenant, which `org_id` already enforces. What this stops
    is the narrower, worse case: a card ADDRESSED to a named seat who was not a participant."""
    assert kept([participants("joseph@afore.vc")], None, seats) == ["our runway is four months"]


def test_a_directory_failure_keeps_the_quotes_rather_than_blanking_the_card():
    """A card that silently loses its evidence looks identical to a situation with none. This
    function must not be able to blank a card because a directory query timed out."""
    broken = _Store(engine=None)

    assert kept([participants("joseph@afore.vc")], "seat-ops", broken) \
        == ["our runway is four months"]


def test_a_seat_with_no_address_on_file_sees_no_participants_quote(seats):
    """The other direction of the same question, and it must NOT fail open: a seat we cannot
    name cannot be shown to have been on the thread."""
    with seats.engine.begin() as c:
        c.execute(text("insert into org_seats values (:o, 'seat-ghost', null)"), {"o": ORG})

    assert kept([participants("joseph@afore.vc")], "seat-ghost", seats) == []


def test_nothing_in_no_quotes_out(seats):
    assert kept([], "seat-ops", seats) == []
    assert _visible_quotes(None, "seat-ops", store=seats, org_id=ORG) == []


# =============================================================================================
# The query carries what the filter needs.
# =============================================================================================
def test_the_quote_read_selects_the_visibility_columns():
    from genios_engine.deliver.card_builder import _QUOTES_SQL

    assert "se.visibility_scope" in _QUOTES_SQL
    assert "se.visibility_principals" in _QUOTES_SQL


def test_the_filter_runs_after_the_recipient_is_known():
    """The structural reason this check never existed: quotes are read at
    `load_evidence_quotes` BEFORE `resolve_assignee` runs, so the recipient is not known at the
    point the SQL executes. Filtering in the query is not possible; filtering here is."""
    import inspect

    from genios_engine.deliver import card_builder

    source = inspect.getsource(card_builder.build_card_payload) \
        if hasattr(card_builder, "build_card_payload") else inspect.getsource(card_builder)
    resolve_at = source.index("resolve_assignee(")
    filter_at = source.index("_visible_quotes(quotes, assignee")

    assert resolve_at < filter_at
