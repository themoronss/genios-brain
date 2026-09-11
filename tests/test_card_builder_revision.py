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


@pytest.mark.parametrize("old_version", [None, PREVIOUS])
@pytest.mark.parametrize("state", ["built", "queued", "surfaced", "claimed", "snoozed",
                                  "acted", "resolved", "expired"])
def test_only_untouched_older_cards_can_be_claimed_for_the_new_builder(store, old_version, state):
    with store.engine.begin() as c:
        c.execute(text("insert into cards values ('sig', :v, :s, null)"),
                  {"v": old_version, "s": state})
    token = store.claim_build("org", "sig", eval_time=NOW, builder_version=BUILDER_VERSION)
    assert bool(token) is (state in {"built", "queued", "surfaced"})


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
