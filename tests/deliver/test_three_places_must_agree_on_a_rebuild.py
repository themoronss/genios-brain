"""The selection, the claim and the write agree on which card may be rebuilt.

    pytest tests/deliver/test_three_places_must_agree_on_a_rebuild.py -q

⛔ WHY THIS FILE EXISTS. Measured on the design partner's org, 2026-10-04: NINE `dependency_stated`
signals, every one `status='open'`, every one carrying an expired card. `pipeline.build_cards_for_org`
selected all nine for rebuild — I ran its own query and got nine rows. `CardStore.claim_build` then
refused all nine: `claim_allowed = False`, 0 of 9. Those cards could never have come back, on any
sweep, ever. The tenant's queue showed FOUR cards where thirteen existed, and no log line anywhere
said a claim had been refused.

⛔ THE DISAGREEMENT. `pipeline`'s join has excluded expired cards since the no-auto-expiry fix, in
its own words: *"an expired card used to permanently block a still-open signal from ever getting a
fresh one … only 'expired' reopens the door for a rebuild."* `claim_build` and the upsert were
never told. They asked a different question — `_STALE`, "did a DIFFERENT builder write this card" —
which is FALSE for a card the current builder wrote, so an expired card counted as a live one and
blocked its own replacement.

⛔ WHY ADDING `expired` TO `REFRESHABLE_STATES` WOULD NOT HAVE FIXED IT, and `test_a_live_card_from
_the_same_builder_still_blocks` is the half that proves the other direction. `_STALE` would still
require a different builder_version, which these nine did not have. And it would have let a live
refresh overwrite an expired card mid-window. Expiry is its own question: the card's window has
closed, so there is nothing left to protect.

`_STALE`'s own comment already said it — "shared by the claim and the upsert so the two can never
disagree". There were THREE places, not two.
"""

from __future__ import annotations

import inspect

import pytest

from genios_engine.deliver import pipeline
from genios_engine.deliver.store import CardStore

pytestmark = pytest.mark.unit


def test_the_claim_lets_an_expired_card_be_rebuilt():
    """⛔ THE MUTATION THIS FILE REJECTS: dropping expiry from the claim's predicate. Nine live
    signals go permanently uncardable again, silently."""
    assert "expired" in CardStore._REPLACEABLE, (
        "claim_build blocks on an expired card again — the pipeline selects such a signal and the "
        "claim then refuses it, so the card can never be rebuilt and nothing says so")


def test_a_live_card_from_the_same_builder_still_blocks():
    """The other direction, and the reason this is not just "allow everything". A queued or
    surfaced card the CURRENT builder wrote is the tenant's live queue: rebuilding it would churn
    the LLM and rewrite a card the reader may be mid-way through."""
    assert ":builder" in CardStore._STALE
    assert ":refreshable" in CardStore._STALE
    assert CardStore._STALE in CardStore._REPLACEABLE, (
        "the staleness branch was dropped from the replaceable predicate — either live cards now "
        "rebuild on every sweep, or a genuinely stale card can no longer be refreshed")


def test_a_resolved_card_is_never_rebuilt_even_once_expired():
    """A card the user ACTED on is their answer. It expires like any other, and re-deriving it
    would resurrect work they already closed.

    ⛔ ASSERTED ON THE EXPIRY BRANCH ITSELF, not on the predicate as a whole — `_STALE` carries
    its own `resolved_at is null`, so a substring check over the whole string passes even with the
    expiry branch's guard deleted. It did: removing it left 6 of 6 green until this was tightened.
    """
    expiry_branch = CardStore._REPLACEABLE.split(" or (")[0]
    assert "expired" in expiry_branch, "the expiry branch moved — re-point this test at it"
    assert "resolved_at is null" in expiry_branch, (
        "the expiry branch no longer excludes a card the user acted on; an expired RESOLVED card "
        "would be rebuilt, resurrecting work the reader already closed")


def test_the_claim_and_the_write_use_one_rule():
    """⛔ A claim that succeeds and a write that silently does nothing is the worst of the three
    failures: the signal is marked claimed, the lease is held, and no card appears. Both must
    spell the same rule."""
    source = inspect.getsource(CardStore.insert_card)
    assert "cards.state = 'expired'" in source and "cards.resolved_at is null" in source, (
        "insert_card's upsert no longer replaces an expired card; claim_build would claim the signal and "
        "the write would match no row")
    assert "cards.state in :refreshable" in source, "the upsert lost its staleness branch"


def test_the_pipeline_still_reopens_the_door_on_expiry():
    """The third place — the one that was right all along. If its join stops excluding expired
    cards, the signal is never selected and the two fixes above become unreachable."""
    source = inspect.getsource(pipeline._open_signals_without_cards)
    assert "k.state != 'expired'" in source, (
        "the pipeline's join no longer excludes expired cards; a still-open signal whose card "
        "lapsed is never offered for rebuild again")


def test_the_three_rules_name_the_same_two_conditions():
    """The invariant, stated once: expired-and-unresolved, OR stale-and-untouched. If a fourth
    reader is added it has to answer this question the same way."""
    for predicate in (CardStore._REPLACEABLE, inspect.getsource(CardStore.insert_card)):
        assert "expired" in predicate
        assert "resolved_at is null" in predicate
        assert "refreshable" in predicate
