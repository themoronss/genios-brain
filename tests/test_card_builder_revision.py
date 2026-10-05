"""A renderer change must reach old untouched cards without overriding a human decision."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.deliver.card_builder import BUILDER_VERSION
from genios_engine.deliver.store import CardStore

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)
PREVIOUS = "card-builder.v4-names-the-thing"


@pytest.fixture
def store():
    result = CardStore.__new__(CardStore)
    result._engine = create_engine("sqlite://")
    with result.engine.begin() as c:
        c.execute(text("create table signals (signal_id text primary key, org_id text)"))
        c.execute(text("create table cards (signal_id text unique, builder_version text, "
                       "state text, resolved_at timestamp)"))
        c.execute(text("create table card_build_claims (signal_id text primary key, org_id text, "
                       "claim_token text, claimed_at timestamp, expires_at timestamp)"))
        c.execute(text("insert into signals values ('sig', 'org')"))
    yield result
    result.engine.dispose()


def test_changed_quote_and_count_copy_has_a_new_composition_identity():
    assert BUILDER_VERSION != PREVIOUS


#: States a claim may rebuild over. `built`/`queued`/`surfaced` because a newer builder has
#: something better to say and nobody has touched the card.
#:
#: ⛔ `expired` JOINED THIS SET ON 2026-10-04, and it is a correction rather than a loosening.
#: This file's own purpose is "without overriding a human decision" — and expiry is NOT a human
#: decision, it is the clock. `deliver/pipeline._open_signals_without_cards` has excluded expired
#: cards from its blocking join since the no-auto-expiry fix, in its own words: *"only 'expired'
#: reopens the door for a rebuild"* — and `claim_build` had never been told, so the selection said
#: rebuild and the claim said no.
#:
#: MEASURED on the design partner's org that day: NINE open `dependency_stated` signals whose
#: cards had lapsed, all nine selected by the pipeline, all nine refused by the claim —
#: `claim_allowed = False`, 0 of 9, with no log line. Those cards could never have come back on
#: any sweep, and the owner's queue showed four cards where the tenant had thirteen.
CLAIMABLE_STATES = {"built", "queued", "surfaced", "expired"}

#: ⛔ The states that stay blocked, and the reason this change is not a general loosening: every
#: one of them is somebody's ANSWER. A card that was claimed, snoozed, acted on or resolved was
#: decided by a person or an agent, and re-deriving it would overwrite that decision — which is
#: the exact failure this file was written to prevent.
HUMAN_DECIDED_STATES = {"claimed", "snoozed", "acted", "resolved"}


@pytest.mark.parametrize("old_version", [None, PREVIOUS])
@pytest.mark.parametrize("state", sorted(CLAIMABLE_STATES | HUMAN_DECIDED_STATES))
def test_only_untouched_older_cards_can_be_claimed_for_the_new_builder(store, old_version, state):
    with store.engine.begin() as c:
        c.execute(text("insert into cards values ('sig', :v, :s, null)"),
                  {"v": old_version, "s": state})
    token = store.claim_build("org", "sig", eval_time=NOW, builder_version=BUILDER_VERSION)
    assert bool(token) is (state in CLAIMABLE_STATES)


@pytest.mark.parametrize("state", sorted(HUMAN_DECIDED_STATES))
def test_a_lapsed_card_is_rebuilt_but_a_decided_one_is_never(store, state):
    """⛔ The two directions asserted together, because the 2026-10-04 change moves one and must
    not move the other. An expired card whose window closed is rebuilt whatever wrote it; a card
    somebody ANSWERED is not, even once it expires."""
    with store.engine.begin() as c:
        c.execute(text("insert into cards values ('sig', :v, :s, null)"),
                  {"v": BUILDER_VERSION, "s": state})
    assert store.claim_build("org", "sig", eval_time=NOW,
                             builder_version=BUILDER_VERSION) is None, (
        f"a card in state {state!r} was rebuilt — that is somebody's decision being overwritten")


def test_an_expired_card_is_rebuilt_even_by_the_same_builder(store):
    """⛔ THE MUTATION THIS REJECTS: folding expiry into the staleness test. `_STALE` asks whether
    a DIFFERENT builder wrote the card, which was FALSE for all nine production cards — the same
    builder wrote them. Adding 'expired' to REFRESHABLE_STATES would not have fixed it."""
    with store.engine.begin() as c:
        c.execute(text("insert into cards values ('sig', :v, 'expired', null)"),
                  {"v": BUILDER_VERSION})
    assert store.claim_build("org", "sig", eval_time=NOW, builder_version=BUILDER_VERSION), (
        "an expired card written by the CURRENT builder is still not claimable; the nine stuck "
        "cards had exactly this shape")


def test_an_expired_card_the_user_resolved_is_still_never_rebuilt(store):
    """Expiry opens the door; a resolution closes it again. Resurrecting work somebody closed is
    worse than leaving a lapsed card lapsed."""
    with store.engine.begin() as c:
        c.execute(text("insert into cards values ('sig', :v, 'expired', :r)"),
                  {"v": PREVIOUS, "r": NOW})
    assert store.claim_build("org", "sig", eval_time=NOW,
                             builder_version=BUILDER_VERSION) is None


@pytest.mark.parametrize("same_revision,resolved", [(True, False), (False, True)])
def test_same_revision_or_resolved_timestamp_prevents_rewriting_a_queued_card(store, same_revision, resolved):
    with store.engine.begin() as c:
        c.execute(text("insert into cards values ('sig', :v, 'queued', :r)"),
                  {"v": BUILDER_VERSION if same_revision else PREVIOUS,
                   "r": NOW if resolved else None})
    assert store.claim_build("org", "sig", eval_time=NOW, builder_version=BUILDER_VERSION) is None


def test_fresh_card_claims_are_tenant_scoped_and_successor_leases_cannot_be_released(store):
    assert store.claim_build("foreign", "sig", eval_time=NOW, builder_version=BUILDER_VERSION) is None
    first = store.claim_build("org", "sig", eval_time=NOW, builder_version=BUILDER_VERSION)
    assert first
    assert store.claim_build("org", "sig", eval_time=NOW, builder_version=BUILDER_VERSION) is None
    second = store.claim_build("org", "sig", eval_time=NOW + timedelta(minutes=16),
                               builder_version=BUILDER_VERSION)
    assert second and second != first
    assert not store.release_build("org", "sig", first)
    assert not store.release_build("foreign", "sig", second)
    assert store.release_build("org", "sig", second)
