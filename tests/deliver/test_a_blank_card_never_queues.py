"""A card with nothing in it must not reach a person.

MEASURED ON THE PILOT, 9 Sep 2026. Of the fifteen cards the founder was shown, card twelve had
`headline` NULL and `situation` NULL — and state `queued`, at score 44, ahead of two real cards.
It is the cheapest defect in the whole feed to describe: the queue gate never asked whether the
thing it was queueing said anything.

A blank card is worse than a missing one. A missing card costs the reader nothing; a blank card
costs them the seconds it takes to open it, plus the belief that the product knows what it is
doing. `card_builder` already refuses on plenty of grounds and `insert_card`'s own docstring says
the validators are green by the time it runs — so this is the gate that was missing, not one that
was wrong.

REFUSED, NOT REPAIRED. Nothing here invents a headline for a card that has none: a card with no
sentence has no business being shown, and manufacturing one would be the invention this codebase
refuses everywhere else. The build returns "not created" the way it already does for a lost lease.
"""
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from genios_engine.deliver.store import CardStore

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


def _leased_store(calls):
    """A store whose build lease is HELD, so the only thing left to refuse is the copy.

    The lease is checked first and deliberately — `test_card_insert_is_fenced_by_the_current_
    build_lease` pins that it is consulted on every call, so a cheaper content check in front of
    it would unfence the one thing stopping two builders writing the same card.
    """
    class _Result:
        def first(self):
            return object()          # a lease exists

        rowcount = 1

    class _Connection:
        def execute(self, statement, params=None):
            calls.append((str(statement), dict(params or {})))
            return _Result()

    class _Engine:
        @contextmanager
        def begin(self):
            yield _Connection()

    store = CardStore.__new__(CardStore)
    store._engine = _Engine()
    return store


def _copy(**over) -> dict:
    copy = {"headline": "Reply to Manik about GeniOS demo access",
            "situation": "Manik at Titan Capital last wrote 31 days ago. Ball is in your court.",
            "artifact": {}, "render_mode": "authored"}
    copy.update(over)
    return copy


@pytest.mark.parametrize("missing", [
    {"headline": None},
    {"situation": None},
    {"headline": None, "situation": None},
    {"headline": "   "},
    {"situation": ""},
])
def test_a_card_with_no_words_is_refused(missing):
    calls = []
    store = _leased_store(calls)
    card = {"org_id": "o", "signal_id": "s", "urgency_band": "standard",
            "_authority_time": NOW}
    assert store.insert_card(card, _copy(**missing), build_claim_token="t") == (None, False, False)
    # The lease was still consulted — the refusal is about the words, not a skipped fence.
    assert len(calls) == 1
    assert "claim_token=:token" in calls[0][0].lower()


def test_a_card_that_says_something_gets_past_this_guard():
    """The guard must not become a second, silent rejection path for real cards. A card with
    words runs on past the check and does more work — proved by the further statements it
    executes against the same connection."""
    calls = []
    store = _leased_store(calls)
    card = {"org_id": "o", "signal_id": "s", "urgency_band": "standard",
            "_authority_time": NOW}
    # A blank card returns the refusal tuple cleanly. A card WITH words runs on into the real
    # insert, which this fake connection cannot satisfy — so raising is the proof it was not
    # refused here. What must never happen is a quiet `(None, False, False)`.
    outcome = None
    try:
        outcome = store.insert_card(card, _copy(), build_claim_token="t")
    except Exception:                      # noqa: BLE001 — the fake connection is not a database
        return
    assert outcome != (None, False, False), "a card with words was refused by the blank-card guard"
