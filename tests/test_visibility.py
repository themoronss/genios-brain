"""Source ACLs, carried forward. The rule under test: **the audience of anything derived
from an event can never be wider than the audience of the event itself.**

Before `capture/visibility.py` nothing recorded who could see the original, so a fact
extracted from a two-person thread and one extracted from a company-wide page arrived at
Layer 2 identical, and every layer above was free to deliver either to anyone in the org.
"""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event
from genios_engine.capture.visibility import visibility_for
from genios_engine.contracts.visibility import (ORG, PARTICIPANTS, PRIVATE, PUBLIC,
                                                Visibility, narrowest)


def _raw(source="gmail", object_type="email_message", **raw):
    return RawObject(source=source, object_type=object_type, source_object_id="o1",
                     occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                     actor_email="priya@chat360.io", actor_type="external_contact",
                     raw={"body": "hello", "subject": "s", **raw})


# ── derivation, per source shape ────────────────────────────────────────────────────
def test_email_audience_is_sender_plus_to_plus_cc():
    v = visibility_for(_raw(to=["rohit@genios.ai"], cc=["ops@genios.ai"]))
    assert v.scope == PARTICIPANTS
    assert v.principals == ["priya@chat360.io", "rohit@genios.ai", "ops@genios.ai"]
    assert v.derived_from == "mail:sender+to+cc"


def test_email_addresses_are_lowercased_and_deduped():
    v = visibility_for(_raw(to=["Rohit@Genios.ai", "rohit@genios.ai"], cc=None))
    assert v.principals == ["priya@chat360.io", "rohit@genios.ai"]


def test_attachment_inherits_its_parent_messages_audience():
    v = visibility_for(_raw(object_type="email_attachment", to=["rohit@genios.ai"]))
    assert v.scope == PARTICIPANTS and "rohit@genios.ai" in v.principals


def test_calendar_event_audience_is_organizer_plus_attendees():
    v = visibility_for(_raw(source="gcal", object_type="calendar_event",
                            attendees=["lp@314.capital"]))
    assert v.scope == PARTICIPANTS
    assert v.principals == ["priya@chat360.io", "lp@314.capital"]


def test_solo_calendar_block_is_private_not_org_wide():
    """A focus block on one person's calendar is not something the company booked."""
    v = visibility_for(_raw(source="gcal", object_type="calendar_event", attendees=[]))
    assert v.scope == PRIVATE and v.principals == ["priya@chat360.io"]


def test_drive_link_sharing_is_public_and_domain_sharing_is_org():
    anyone = visibility_for(_raw(source="gdrive", object_type="file",
                                 permissions=[{"type": "anyone"}]))
    domain = visibility_for(_raw(source="gdrive", object_type="file",
                                 permissions=[{"type": "domain"}]))
    assert anyone.scope == PUBLIC
    assert domain.scope == ORG


def test_drive_named_permissions_become_participants():
    v = visibility_for(_raw(source="gdrive", object_type="file",
                            permissions=[{"type": "user", "emailAddress": "cfo@genios.ai"}]))
    assert v.scope == PARTICIPANTS and "cfo@genios.ai" in v.principals


def test_unshared_drive_file_belongs_to_its_owner_alone():
    v = visibility_for(_raw(source="gdrive", object_type="file", shared=False))
    assert v.scope == PRIVATE and v.principals == ["priya@chat360.io"]


def test_unknown_source_defaults_to_org_never_to_public():
    """The default must be the tenant boundary that already exists — not a guess in
    either direction. `public` would leak; something narrower would hide evidence from
    the people who own it."""
    v = visibility_for(_raw(source="notion", object_type="page"))
    assert v.scope == ORG and v.derived_from == "default:notion"


def test_a_connector_that_knows_the_real_acl_wins():
    v = visibility_for(_raw(source="slack", object_type="message",
                            acl={"scope": "participants",
                                 "principals": ["a@x.com"], "derived_from": "slack:channel"}))
    assert v.scope == PARTICIPANTS and v.derived_from == "slack:channel"


def test_a_malformed_acl_falls_back_instead_of_raising():
    v = visibility_for(_raw(source="notion", object_type="page", acl={"scope": "everyone"}))
    assert v.scope == ORG


# ── the viewer question ─────────────────────────────────────────────────────────────
def test_participants_scope_excludes_an_org_member_who_was_not_on_the_thread():
    v = Visibility(scope=PARTICIPANTS, principals=["priya@chat360.io"])
    assert v.can_view("priya@chat360.io") is True
    assert v.can_view("PRIYA@chat360.io") is True          # case-insensitive
    assert v.can_view("someone.else@genios.ai") is False   # in the org, not on the thread
    assert v.can_view(None) is False


def test_org_scope_admits_any_member_and_public_admits_everyone():
    assert Visibility(scope=ORG).can_view("anyone@genios.ai") is True
    assert Visibility(scope=ORG).can_view("x@y.com", org_member=False) is False
    assert Visibility(scope=PUBLIC).can_view(None, org_member=False) is True


# ── merging evidence ────────────────────────────────────────────────────────────────
def test_merging_takes_the_narrowest_scope():
    """A situation built from a company page AND a private thread is as sensitive as the
    private thread. Merging must only ever narrow."""
    merged = narrowest(Visibility(scope=ORG),
                       Visibility(scope=PARTICIPANTS, principals=["a@x.com", "b@x.com"]))
    assert merged.scope == PARTICIPANTS and merged.principals == ["a@x.com", "b@x.com"]


def test_merging_two_participant_sets_intersects_them():
    merged = narrowest(Visibility(scope=PARTICIPANTS, principals=["a@x.com", "b@x.com"]),
                       Visibility(scope=PARTICIPANTS, principals=["b@x.com", "c@x.com"]))
    assert merged.principals == ["b@x.com"]
    assert merged.can_view("a@x.com") is False


def test_merging_nothing_is_org_not_public():
    assert narrowest().scope == ORG
    assert narrowest(None, None).scope == ORG


# ── it survives the pipeline ────────────────────────────────────────────────────────
def test_visibility_reaches_the_gated_event_and_the_ledger():
    repo = InMemorySourceEventRepository()
    res = capture_event(_raw(to=["rohit@genios.ai"]), org_id="org_a", connection_id="c1",
                        repo=repo)
    assert res.outcome == "emitted"
    assert res.gated.visibility.scope == PARTICIPANTS
    assert res.gated.visibility.can_view("rohit@genios.ai") is True
    assert res.gated.visibility.can_view("intern@genios.ai") is False
    assert res.event.visibility == res.gated.visibility     # ledger and seam agree
