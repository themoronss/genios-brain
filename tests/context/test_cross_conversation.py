"""CC-25…CC-30 · Cross Conversation — one authored message, many counterparties, one campaign.

    pytest tests/context/test_cross_conversation.py -q

THE MISSING CORRELATOR. The architecture names eight. Four exist: `correlation.py` carries the
anchor/tool/user joins, and resource, timeline and dependency are their own modules. Cross
Conversation, Cross Domain and Cross Organization had no code at all.

WHY THIS ONE FIRST, measured. On 11 August between 03:02 and 08:39 the pilot sent seventeen
messages to eighteen recipients — Peak XV, Afore, Titan, Neon, Together, 3one4, Surge, Z Fellows,
Antler, IIM-B — every one carrying the same sentence. That is one campaign; the system saw
eighteen unrelated threads. `read_outreach_cohorts` exists to answer *"of everyone I contacted
about the raise, who has gone quiet?"* and returned ZERO findings, because it groups by EMPLOYER
and eleven investors at nine firms never reach its floor. **A fundraise is not a company, it is a
message.**

RUN AGAINST LIVE DATA BEFORE THESE TESTS WERE WRITTEN, and it caught two defects the fixtures
below now pin by name — a campaign reported at twice its size, and the founder inside his own
campaign.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.correlation_conversation import (
    MIN_RECIPIENTS,
    MIN_SENTENCE_CHARS,
    WINDOW_HOURS,
    campaign_id_for,
    find_campaigns,
    normalise_sentence,
)

ORG = "org_pilot"
OTHER = "org_other"
OWNER = "mrrohitswerashi@gmail.com"
NOW = datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=90)

PITCH = "As we can see the need of the product, we can expect the numbers to hit nearly ~$2-3k MRR."
INVESTORS = ("vidushi@peakxv.com", "harshita@peakxv.com", "manik@titancapital.vc",
             "shivam@together.fund", "piyush@3one4capital.com", "team@zfellows.com",
             "adityad@iima.ac.in")


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        for ddl in (
            "create table graph_facts (fact_version_id text, org_id text, subject_node_id text, "
            "field text, status text)",
            "create table graph_source_refs (org_id text, event_id text, fact_version_id text)",
            "create table graph_nodes (node_id text, org_id text, node_type text, "
            "canonical_key text, display_name text, valid_to timestamp)",
            "create table graph_edges (org_id text, edge_type text, from_node_id text, "
            "to_node_id text, valid_to timestamp)",
            "create table source_events (event_id text, org_id text, occurred_at timestamp, "
            "actor text)",
            "create table qualified_signals (event_id text, org_id text, evidence_refs text)",
        ):
            c.execute(text(ddl))
    with engine.begin() as c:
        yield c


def node(c, node_id: str, key: str, node_type: str = "person", *, org: str = ORG) -> None:
    c.execute(text("insert into graph_nodes values (:n, :o, :t, :k, :k, null)"),
              {"n": node_id, "o": org, "t": node_type, "k": key})


def we_sent(c, *, to_node: str, event: str, quote: str, at: datetime = NOW,
            org: str = ORG, sender: str = OWNER) -> None:
    """One outbound message: `thread.last_outbound` on the recipient, the source ref, the event
    and the sentence L1 extracted from it."""
    fv = f"fv_{to_node}_{event}"
    c.execute(text("insert into graph_facts values (:f, :o, :n, 'thread.last_outbound', 'active')"),
              {"f": fv, "o": org, "n": to_node})
    c.execute(text("insert into graph_source_refs values (:o, :e, :f)"),
              {"o": org, "e": event, "f": fv})
    c.execute(text("insert into source_events values (:e, :o, :t, :a)"),
              {"e": event, "o": org, "t": at,
               "a": '{"email": "%s"}' % sender})
    c.execute(text("insert into qualified_signals values (:e, :o, :r)"),
              {"e": event, "o": org,
               "r": '[{"quote": %s}]' % _json(quote)})


def _json(value: str) -> str:
    import json

    return json.dumps(value)


def campaign_of(c, org: str = ORG):
    return find_campaigns(c, org, since=SINCE)


def send_the_raise(c, *, recipients=INVESTORS, quote: str = PITCH, at: datetime = NOW) -> None:
    for i, who in enumerate(recipients):
        node(c, f"n_{i}", who)
        we_sent(c, to_node=f"n_{i}", event=f"evt_{i}", quote=quote,
                at=at + timedelta(minutes=i))


# =============================================================================================
# The campaign the system could not see.
# =============================================================================================
def test_one_sentence_to_seven_investors_is_one_campaign(db):
    send_the_raise(db)

    [campaign] = campaign_of(db)

    assert campaign.size == len(INVESTORS)
    assert campaign.sentence == PITCH


def test_every_recipient_is_named(db):
    """The card has to say who. A count alone cannot be acted on."""
    send_the_raise(db)

    [campaign] = campaign_of(db)

    assert len(campaign.recipients) == len(INVESTORS)
    assert len(set(campaign.recipients)) == len(INVESTORS)


def test_the_messages_are_kept_so_a_card_can_cite_them(db):
    send_the_raise(db)

    [campaign] = campaign_of(db)

    assert len(campaign.event_ids) == len(INVESTORS)


def test_two_different_sentences_are_two_campaigns(db):
    """The pilot sent two on the same morning — the MRR line and the materials line. They are
    different messages to overlapping people and must not merge."""
    send_the_raise(db)
    for i, who in enumerate(INVESTORS[:4]):
        we_sent(db, to_node=f"n_{i}", event=f"evt_b_{i}",
                quote="I am sharing a few details here as well for your reference with the deck.")

    assert len(campaign_of(db)) == 2


# =============================================================================================
# The two defects the live run caught, before these tests existed.
# =============================================================================================
def test_a_thread_and_its_person_are_one_recipient(db):
    """DEFECT ONE. `waiting.py` writes `thread.last_outbound` onto BOTH the thread node and the
    party who corresponded on it, so the 11 August raise reported FOURTEEN recipients for seven
    real people — a campaign at twice its true size, which is worse than not finding it, because
    the number is what the card would say."""
    for i, who in enumerate(INVESTORS):
        node(db, f"n_{i}", who)
        node(db, f"t_{i}", f"Thread with {who}", "thread")
        db.execute(text("insert into graph_edges values (:o,'corresponded_with',:f,:t,null)"),
                   {"o": ORG, "f": f"n_{i}", "t": f"t_{i}"})
        we_sent(db, to_node=f"n_{i}", event=f"evt_{i}", quote=PITCH)
        we_sent(db, to_node=f"t_{i}", event=f"evt_{i}_t", quote=PITCH)

    [campaign] = campaign_of(db)

    assert campaign.size == len(INVESTORS)


def test_the_sender_is_not_a_recipient_of_their_own_campaign(db):
    """DEFECT TWO. `thread.last_outbound` is written on every participant including ours, so the
    founder appeared inside his own campaign and inflated it by one."""
    send_the_raise(db)
    node(db, "n_us", OWNER)
    we_sent(db, to_node="n_us", event="evt_self", quote=PITCH)

    [campaign] = campaign_of(db)

    assert "n_us" not in campaign.recipients
    assert campaign.size == len(INVESTORS)


# =============================================================================================
# The three conditions, each of which is wrong alone.
# =============================================================================================
def test_too_few_recipients_is_a_conversation_not_a_campaign(db):
    send_the_raise(db, recipients=INVESTORS[:MIN_RECIPIENTS - 1])

    assert campaign_of(db) == ()


def test_exactly_the_floor_is_a_campaign(db):
    send_the_raise(db, recipients=INVESTORS[:MIN_RECIPIENTS])

    assert len(campaign_of(db)) == 1


def test_the_same_sentence_a_quarter_later_is_a_different_campaign(db):
    """A template reused next quarter is a different attempt with different traction behind it."""
    send_the_raise(db)
    later = NOW + timedelta(hours=WINDOW_HOURS + 24)
    for i, who in enumerate(INVESTORS):
        we_sent(db, to_node=f"n_{i}", event=f"evt_late_{i}", quote=PITCH, at=later)

    campaigns = campaign_of(db)

    assert len(campaigns) == 2
    assert campaigns[0].campaign_id != campaigns[1].campaign_id


def test_a_send_that_crosses_midnight_stays_one_campaign(db):
    """The window is measured from the run's first send, not bucketed by calendar day — a raise
    that starts at 23:40 and finishes at 00:20 is one morning's work."""
    late = datetime(2026, 8, 11, 23, 40, tzinfo=timezone.utc)
    for i, who in enumerate(INVESTORS):
        node(db, f"n_{i}", who)
        we_sent(db, to_node=f"n_{i}", event=f"evt_{i}", quote=PITCH,
                at=late + timedelta(minutes=i * 10))

    assert len(campaign_of(db)) == 1


def test_a_short_fragment_never_groups_anything(db):
    """Below the floor a "shared sentence" is a greeting or a signature, and grouping on it would
    merge everything the founder has ever written."""
    send_the_raise(db, quote="Hi there, thanks!")

    assert campaign_of(db) == ()
    assert len("hi there, thanks!") < MIN_SENTENCE_CHARS


# =============================================================================================
# Identity and tenancy.
# =============================================================================================
def test_the_campaign_id_is_stable_across_runs(db):
    send_the_raise(db)

    first = campaign_of(db)[0].campaign_id
    second = campaign_of(db)[0].campaign_id

    assert first == second


def test_whitespace_and_case_do_not_split_a_campaign():
    assert normalise_sentence("  We  Can\nExpect  ") == normalise_sentence("we can expect")


def test_the_id_depends_on_the_org(db):
    a = campaign_id_for(org_id="org_a", sentence=PITCH, opened_at=NOW)
    b = campaign_id_for(org_id="org_b", sentence=PITCH, opened_at=NOW)

    assert a != b


def test_another_orgs_sends_are_never_grouped_into_this_ones(db):
    """Tenancy on five joins. One tenant's raise must not appear in another's."""
    for i, who in enumerate(INVESTORS):
        node(db, f"n_{i}", who, org=OTHER)
        we_sent(db, to_node=f"n_{i}", event=f"evt_{i}", quote=PITCH, org=OTHER)

    assert campaign_of(db, ORG) == ()
    assert len(campaign_of(db, OTHER)) == 1


def test_a_superseded_outbound_fact_does_not_join_a_campaign(db):
    send_the_raise(db, recipients=INVESTORS[:MIN_RECIPIENTS])
    db.execute(text("update graph_facts set status='superseded' where subject_node_id='n_0'"))

    assert campaign_of(db) == ()


def test_nothing_sent_yields_nothing(db):
    assert campaign_of(db) == ()
