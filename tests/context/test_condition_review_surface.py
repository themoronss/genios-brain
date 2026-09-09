"""M5 · the dormant-condition review queue becomes a surface.

    pytest tests/context/test_condition_review_surface.py -q

`correlation_timeline`'s own docstring: *"a review queue is a surface, not a silence."* Until this
reading existed that sentence was false. The correlator finds a conditional statement, names its
actor, extracts what that actor will do, keeps the counterparty's verbatim sentence, and — when
`parse_condition` cannot turn the condition into a checkable predicate — files it under
`derived.timeline.condition_review` instead of guessing. That refusal is correct: doc 03's first
failure mode is a rhetorical condition matched.

Nobody built the other half. On the pilot the queue holds **24 conditions across 5 rows**, every
one with an actor, an action, a date and a real sentence, and not one reached a card:

    Theresa Hoffmann, Antler      "…always happy to take a look and reconsider."
    Hub71                         "We'd encourage you to stay engaged…"
    Boardy                        'Reply with "I want to apply to HF0" and I'll call you…'
    Sehan Sanjula                 'If this isn't relevant, just reply "no" and I'll close the loop'

THE FIRST ONE PROVES THE POINT. Asked what to do about Antler, the feed reasoned from
`follow_up_count = 5` and `days_waiting = 13` and produced *stop chasing them* — the exact opposite
of what Theresa wrote, which had been sitting in this queue since the day she wrote it.
The intelligence was not missing. It was never surfaced.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.condition_situations import (
    MAX_PER_NODE,
    REVIEW_FIELD,
    STALE_AFTER_DAYS,
    gather_conditions_in_review,
    read_conditions_in_review,
)

ORG = "org_pilot"
OTHER = "org_other"
NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
OWNER = "mrrohitswerashi@gmail.com"


def condition(actor: str, action: str, *, text_: str = "if that works",
              quote: str | None = "some sentence they wrote",
              days_ago: int = 30, condition_id: str | None = None) -> dict:
    entry = {
        "actor": actor,
        "action": action,
        "predicate": None,
        "condition_text": text_,
        "condition_id": condition_id or f"cond_{actor}_{action}".replace(" ", "_"),
        "stated_at": (NOW - timedelta(days=days_ago)).isoformat(),
    }
    if quote is not None:
        entry["statement"] = [{"quote": quote, "start_offset": 0, "end_offset": len(quote),
                               "verified": False, "source_ref": "prepared_content:pc_x"}]
    return entry


def rows(*entries, node: str = "n_person") -> dict:
    return {node: {"review": list(entries)}}


def facts_of(finding) -> dict:
    return {name: value for name, value, _kind in finding.facts}


def read(row_map, owner: str | None = OWNER):
    return read_conditions_in_review(row_map, NOW, owner)


# =============================================================================================
# The four conditions from the pilot, each stated as the card it should become.
# =============================================================================================
def test_theresas_invitation_reaches_the_surface():
    """THE ONE THAT MATTERS. The feed said "stop following up"; she had written the opposite, and
    the sentence was in this queue the whole time."""
    quote = ("If there's any changes in the business or updates you can share with us, please "
             "feel free to do so - always happy to take a look and reconsider.")
    [finding] = read(rows(condition(
        "Theresa Hoffmann", "take a look and reconsider if business updates are shared",
        text_="If there's any changes in the business or updates you can share with us",
        quote=quote, days_ago=33)))

    fx = facts_of(finding)
    assert fx["condition.actor"] == "Theresa Hoffmann"
    assert "reconsider" in fx["condition.action"]
    assert fx["condition.quote"] == quote
    assert fx["condition.age_days"] == 33


def test_the_vendors_own_exit_is_the_action():
    """Sehan/myzyner is the card the live feed renders as "deliver $2,000 monthly savings to
    myzyner.com". His own sentence names the correct action, and it is one word."""
    [finding] = read(rows(condition(
        "Sehan Sanjula", "close the loop if Rohit replies 'no'",
        text_="If this isn't relevant, just reply 'no'",
        quote='If this isn\'t relevant, just reply "no" and I\'ll close the loop', days_ago=11)))

    assert "reply" in facts_of(finding)["condition.text"]


def test_a_one_sentence_unlock_is_reported_with_the_sentence():
    [finding] = read(rows(condition(
        "Boardy", "call to kick off application",
        text_='Reply with "I want to apply to HF0"', days_ago=26)))

    fx = facts_of(finding)
    assert fx["condition.text"] == 'Reply with "I want to apply to HF0"'
    assert fx["condition.action"] == "call to kick off application"


def test_our_own_promise_is_surfaced_too_and_marked_as_ours():
    """"You told them you would reply once it was booked" is as much an open loop as anything
    they said. The mailbox owner comparison is a string match and nothing more — whether the
    resulting MOVE is ours is a reading of the condition, and this module does not make it."""
    [finding] = read(rows(condition(
        "Rohit Swerashi", "reply here once it's booked", text_="once it's booked", days_ago=40)))

    assert facts_of(finding)["condition.actor_is_us"] is True


def test_a_counterpartys_condition_is_not_marked_as_ours():
    [finding] = read(rows(condition("Boardy", "line up the invite")))

    assert facts_of(finding)["condition.actor_is_us"] is False


def test_a_bare_first_name_claims_nothing():
    """THE TRAP THIS TENANT ACTUALLY CONTAINS. There are two Rohits here — Rohit Swerashi, the
    mailbox owner, and Rohit Nallapeta of Crescere Labs. `"Rohit"` is inside the owner's address
    by accident, so a substring match would stamp a counterparty's promise as the founder's own.
    An absent flag is the honest answer; the condition still surfaces."""
    [finding] = read(rows(condition("Rohit", "reply here once it's booked")))

    assert "condition.actor_is_us" not in facts_of(finding)


def test_the_other_rohit_is_confidently_not_us():
    """A full name that shares only a first name is not ambiguous — it is a different person, and
    saying so is more useful than staying silent."""
    [finding] = read(rows(condition("Rohit Nallapeta", "chat and explore potential synergies")))

    assert facts_of(finding)["condition.actor_is_us"] is False


def test_the_owners_own_address_as_an_actor_resolves():
    [finding] = read(rows(condition(OWNER, "reply once booked")))

    assert facts_of(finding)["condition.actor_is_us"] is True


def test_without_a_known_mailbox_owner_the_flag_is_not_invented():
    """Absent is honest. A tenant whose owner this pass does not know gets no claim either way
    rather than a default that reads as "not us"."""
    [finding] = read(rows(condition("Rohit Swerashi", "reply")), owner=None)

    assert "condition.actor_is_us" not in facts_of(finding)


# =============================================================================================
# Shape, ordering and the refusals.
# =============================================================================================
def test_several_conditions_on_one_node_become_several_findings():
    """One stored fact per subject carrying N conditions, not N facts. A counterparty who left
    four open loops has four of them, and they close separately."""
    findings = read(rows(condition("Boardy", "line up the invite", condition_id="c1"),
                         condition("Boardy", "coordinate the invite", condition_id="c2"),
                         condition("Boardy", "get it on the calendar", condition_id="c3")))

    assert len(findings) == 3
    assert len({f.canonical_key for f in findings}) == 3


def test_the_newest_survive_the_bound():
    """A long history must not fill a feed, and the cut is by date so it is the live ones that
    remain rather than whichever the correlator serialised first."""
    entries = [condition("X", f"action {i}", condition_id=f"c{i}", days_ago=i)
               for i in range(MAX_PER_NODE + 4)]
    findings = read(rows(*reversed(entries)))

    assert len(findings) == MAX_PER_NODE
    assert max(facts_of(f)["condition.age_days"] for f in findings) < MAX_PER_NODE


def test_an_entry_with_nothing_to_say_yields_nothing():
    """No actor, no action, no quote is not a card. The condition id alone cannot be rendered."""
    assert read({"n": {"review": [{"condition_id": "c1", "predicate": None}]}}) == []


def test_an_entry_without_a_condition_id_is_refused():
    """The id is the correlation key the situation is written under; without it two sweeps would
    mint two situations for one condition."""
    assert read({"n": {"review": [{"actor": "X", "action": "do a thing"}]}}) == []


def test_a_malformed_row_costs_one_condition_not_the_whole_tenant():
    """A row that will not decode yields nothing and does not raise. An exception here would make
    every condition on the tenant invisible, which is the failure this queue exists to end."""
    assert read({"n_bad": "not json at all", "n_ok": {"review": [condition("X", "y")]}})


def test_the_value_is_accepted_as_json_text_too():
    """`jsonb` arrives decoded from Postgres and as a string from a driver that has not decoded
    it. Both must work or a tenant's queue is invisible for a driver reason."""
    payload = json.dumps({"review": [condition("Theresa Hoffmann", "reconsider")]})

    [finding] = read({"n": payload})

    assert facts_of(finding)["condition.actor"] == "Theresa Hoffmann"


def test_a_condition_with_no_date_still_surfaces():
    """The date is the correlator's, not ours to require. A condition whose `stated_at` did not
    survive is still an open loop; it simply carries no age."""
    entry = condition("X", "do a thing")
    entry.pop("stated_at")

    [finding] = read({"n": {"review": [entry]}})

    fx = facts_of(finding)
    assert fx["condition.actor"] == "X"
    assert "condition.age_days" not in fx


def test_age_is_reported_and_never_used_to_drop():
    """An invitation to come back does not expire because the system was slow to show it. The
    staleness flag travels so a reader can tell a fortnight from a season."""
    [finding] = read(rows(condition("X", "y", days_ago=STALE_AFTER_DAYS + 30)))

    assert facts_of(finding)["condition.stale"] is True


def test_the_predicate_is_declared_missing_rather_than_scored_as_complete():
    """Everything in this queue is here BECAUSE its predicate is absent. Declaring it keeps the
    coverage score honest — "not evaluable" rather than a reading that looks complete."""
    [finding] = read(rows(condition("X", "y")))

    assert finding.missing == ["condition.predicate"]


def test_the_finding_points_at_the_node_the_condition_was_stored_on():
    [finding] = read(rows(condition("X", "y"), node="n_theresa"))

    assert finding.concerns_node == "n_theresa"


# =============================================================================================
# The read.
# =============================================================================================
@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "create table graph_facts (org_id text, subject_node_id text, field text, "
            "value text, status text, valid_to timestamp)"))
    with engine.begin() as c:
        yield c


def _store(c, node: str, payload: dict, *, org: str = ORG, status: str = "active") -> None:
    c.execute(text("insert into graph_facts values (:o, :n, :f, :v, :s, null)"),
              {"o": org, "n": node, "f": REVIEW_FIELD, "v": json.dumps(payload), "s": status})


def test_the_read_returns_the_stored_queue(db):
    _store(db, "n_theresa", {"review": [condition("Theresa Hoffmann", "reconsider")]})

    got = gather_conditions_in_review(db, ORG)

    assert set(got) == {"n_theresa"}


def test_a_superseded_review_row_is_not_read(db):
    _store(db, "n_x", {"review": [condition("X", "y")]}, status="superseded")

    assert gather_conditions_in_review(db, ORG) == {}


def test_another_orgs_queue_is_never_visible(db):
    _store(db, "n_shared", {"review": [condition("X", "y")]}, org=OTHER)

    assert gather_conditions_in_review(db, ORG) == {}


def test_the_read_and_the_reading_compose(db):
    """End to end on a real database: what the read returns is what the reading accepts."""
    _store(db, "n_hub71", {"review": [condition(
        "Hub71", "continue to track progress", text_="if you stay engaged",
        quote="We'd encourage you to stay engaged so we can continue to track your progress.")]})

    [finding] = read_conditions_in_review(gather_conditions_in_review(db, ORG), NOW, OWNER)

    assert facts_of(finding)["condition.actor"] == "Hub71"
    assert "stay engaged" in facts_of(finding)["condition.quote"]


# =============================================================================================
# THE WIRING. The reading existed and nothing called it — 16 findings that reached no situation
# and therefore no card. These pin the three seams that had to be joined for that to change.
# =============================================================================================
def test_the_condition_reading_is_on_the_dispatch():
    """`READINGS` is what `refresh_state_situations` iterates. A reading absent from it runs
    nowhere, which is exactly the state this queue was in."""
    from genios_engine.context.outreach_situations import ANCHOR_CONDITION, READINGS

    assert ANCHOR_CONDITION in [anchor for anchor, _reader in READINGS]


def test_the_anchor_is_declared_by_exactly_one_domain():
    """`domains_declaring` returns every domain holding the anchor and the dispatch mints one
    situation PER claiming domain — two claimants would be two situations, two compiles and two
    cards for one condition."""
    from genios_engine.context.domain_spec import domains_declaring

    assert domains_declaring("condition") == ("admin",)


def test_the_expected_fields_do_not_demand_the_predicate():
    """Everything in this queue is here BECAUSE no predicate could be parsed. Listing it as
    expected would score every row incomplete for the one reason they all share — the reading
    declares it `missing` instead."""
    from genios_engine.context.domain_spec import spec_for

    fields = spec_for("admin").expected_fields["condition_in_review"]

    assert "condition.predicate" not in fields
    assert {"condition.actor", "condition.action", "condition.quote"} <= set(fields)


def test_the_dispatch_adapter_unpacks_the_reserved_key():
    """`_gather` stamps the queue under `_conditions` rather than under a node id, because the
    other three readings iterate `rows` BY NODE."""
    from genios_engine.context.outreach_situations import read_conditions_for_dispatch

    rows = {"_conditions": {"n_x": {"review": [condition("Hub71", "track progress")]}},
            "_mailbox_owner": OWNER}

    [finding] = read_conditions_for_dispatch(rows, NOW, {})

    assert facts_of(finding)["condition.actor"] == "Hub71"


def test_an_empty_queue_yields_nothing_rather_than_raising():
    from genios_engine.context.outreach_situations import read_conditions_for_dispatch

    assert read_conditions_for_dispatch({}, NOW, {}) == []


@pytest.mark.parametrize("reader_name", ["read_awaiting_response", "read_overdue_commitments",
                                         "read_outreach_cohorts"])
def test_the_reserved_keys_never_reach_a_node_reading(reader_name):
    """THE REGRESSION THIS CAUSED. `_gather` now puts two non-node entries in `rows`, and the
    three readings that iterate it by node crashed on the first one —
    `'str' object has no attribute 'get'` — taking every commitment and cohort finding with it."""
    import genios_engine.context.outreach_situations as mod

    reader = getattr(mod, reader_name)
    rows = {"_conditions": {"n": {"review": []}}, "_mailbox_owner": OWNER}

    assert reader(rows, NOW, {}) == []
