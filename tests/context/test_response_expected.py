"""M2.C2 · `response_expected` means WE asked THEM.

    pytest tests/context/test_response_expected.py -q

THE FLAG'S WHOLE PURPOSE is to separate "we are waiting on an answer we asked for" from "we just
have not written lately", because those two need opposite advice. On the pilot it was wrong in
both directions at once, and 40 of 41 waiting rows said `false`.

THE MISSES. An observation extracted from a message is attributed to its SENDER. So outbound mail
produced 425 observations across exactly TWO subject nodes — when Rohit pitched eleven VCs, every
ask landed on Rohit's own node and never on theirs. Peak XV, Afore, Neon, Together, 3one4, Surge,
Z Fellows and Hub71 all read as "we just have not written lately", about a fundraise. Exactly one
waiting person in the whole tenant had the flag set.

THE FALSE POSITIVES, WHICH ARE WORSE. The old read matched any ask-kind observation on the node
regardless of direction. A `question` extracted from THEIR inbound mail marked us as awaiting
THEIR answer when they were awaiting ours — Evokoa Team, Lalitha A R, Sehan Sanjula, Pablo Llanos,
Prema Roman. It also matched `mrrohitswerashi@gmail.com`, the founder's own node.

Measured against the live tenant before this was written: the corrected read resolves 19 nodes
where the old one resolved 12, and the 11 it drops are all inbound questions or the founder.
"""

from __future__ import annotations

import pytest
from sqlalchemy import bindparam, create_engine, text

from genios_engine.context.waiting import _ASK_KINDS, _ASKS

ORG = "org_pilot"
OTHER = "org_other"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "create table graph_facts (fact_version_id text, org_id text, subject_node_id text, "
            "field text, status text)"))
        c.execute(text(
            "create table graph_source_refs (org_id text, event_id text, fact_version_id text)"))
        c.execute(text(
            "create table graph_observations (org_id text, subject_node_id text, kind text, "
            "status text, created_by_event_id text)"))
    with engine.begin() as c:
        yield c


def we_wrote_to(c, node: str, event: str, *, org: str = ORG, status: str = "active") -> None:
    """The outbound leg: `thread.last_outbound` on the recipient's node, and the source ref that
    maps that fact version back to the message it came from."""
    fv = f"fv_{node}_{event}"
    c.execute(text("insert into graph_facts values (:f, :o, :n, 'thread.last_outbound', :s)"),
              {"f": fv, "o": org, "n": node, "s": status})
    c.execute(text("insert into graph_source_refs values (:o, :e, :f)"),
              {"o": org, "e": event, "f": fv})


def they_wrote_to_us(c, node: str, event: str, *, org: str = ORG) -> None:
    fv = f"fvin_{node}_{event}"
    c.execute(text("insert into graph_facts values (:f, :o, :n, 'thread.last_inbound', 'active')"),
              {"f": fv, "o": org, "n": node})
    c.execute(text("insert into graph_source_refs values (:o, :e, :f)"),
              {"o": org, "e": event, "f": fv})


def observation(c, event: str, kind: str, *, on_node: str = "n_us", org: str = ORG,
                status: str = "active") -> None:
    """An observation, attributed the way the extractor attributes it — to the message's sender,
    which for our own outbound mail is US and never the recipient."""
    c.execute(text("insert into graph_observations values (:o, :n, :k, :s, :e)"),
              {"o": org, "n": on_node, "k": kind, "s": status, "e": event})


def asked(c, org: str = ORG) -> set[str]:
    rows = c.execute(text(_ASKS).bindparams(bindparam("kinds", expanding=True)),
                     {"o": org, "kinds": sorted(_ASK_KINDS)}).all()
    return {r[0] for r in rows}


# =============================================================================================
# The misses — the eleven VCs.
# =============================================================================================
def test_a_pitch_we_sent_makes_the_recipient_asked(db):
    """THE DEFECT, stated directly. The observation sits on the founder's node; the only thing
    that makes it about Peak XV is that the message carrying it was one we sent Peak XV."""
    we_wrote_to(db, "n_peakxv", "evt_pitch")
    observation(db, "evt_pitch", "approval_requested", on_node="n_us")

    assert asked(db) == {"n_peakxv"}


def test_every_recipient_of_one_outbound_ask_is_asked(db):
    """One pitch, eleven VCs, eleven waiting situations. Each carries its own
    `thread.last_outbound`, so each resolves from the same observation."""
    for vc in ("n_peakxv", "n_afore", "n_neon", "n_together"):
        we_wrote_to(db, vc, f"evt_{vc}")
        observation(db, f"evt_{vc}", "approval_requested", on_node="n_us")

    assert asked(db) == {"n_peakxv", "n_afore", "n_neon", "n_together"}


def test_the_admin_and_fundraising_ask_kinds_all_count(db):
    """`_ASK_KINDS` carries the administrative and fundraising asks deliberately — without them
    the set was sales-shaped and the flag was false on every row of an admin inbox."""
    for i, kind in enumerate(sorted(_ASK_KINDS)):
        we_wrote_to(db, f"n_{i}", f"evt_{i}")
        observation(db, f"evt_{i}", kind, on_node="n_us")

    assert len(asked(db)) == len(_ASK_KINDS)


# =============================================================================================
# The false positives — and these are the half that was doing damage.
# =============================================================================================
def test_a_question_THEY_asked_us_does_not_make_us_the_one_waiting(db):
    """Evokoa, Lalitha, Sehan, Pablo, Prema. Their inbound question was recorded on their node,
    and the old read called that "we are awaiting their answer". The ball was with us."""
    they_wrote_to_us(db, "n_lalitha", "evt_their_question")
    observation(db, "evt_their_question", "question", on_node="n_lalitha")

    assert asked(db) == set()


def test_an_ask_observation_on_a_node_we_never_wrote_to_resolves_nothing(db):
    """The old read matched the node. This one matches the message, so an observation with no
    outbound leg behind it grounds nothing at all."""
    observation(db, "evt_orphan", "approval_requested", on_node="n_stranger")

    assert asked(db) == set()


def test_a_non_ask_observation_on_our_own_message_does_not_count(db):
    """`_ASK_KINDS` is a short list on purpose: only kinds that mean we put a question to them.
    Announcing something is not asking for anything."""
    we_wrote_to(db, "n_them", "evt_update")
    observation(db, "evt_update", "relationship_change", on_node="n_us")

    assert asked(db) == set()


# =============================================================================================
# Staleness and tenancy.
# =============================================================================================
def test_a_superseded_outbound_fact_does_not_ground_an_ask(db):
    we_wrote_to(db, "n_them", "evt_old", status="superseded")
    observation(db, "evt_old", "question", on_node="n_us")

    assert asked(db) == set()


def test_a_retired_observation_does_not_ground_an_ask(db):
    we_wrote_to(db, "n_them", "evt_1")
    observation(db, "evt_1", "question", on_node="n_us", status="retired")

    assert asked(db) == set()


def test_another_orgs_outbound_never_marks_this_orgs_node(db):
    """Tenancy. Three joins, three org filters; dropping any one would let one tenant's pitch set
    the flag on another tenant's counterparty."""
    we_wrote_to(db, "n_shared", "evt_x", org=OTHER)
    observation(db, "evt_x", "approval_requested", on_node="n_us", org=OTHER)

    assert asked(db, ORG) == set()


def test_the_ask_and_the_outbound_must_be_the_SAME_message(db):
    """The join is on the event, not merely on the node. An ask we made to someone else, plus an
    unrelated message to this node, is not an ask to this node."""
    we_wrote_to(db, "n_them", "evt_hello")
    observation(db, "evt_other_thread", "question", on_node="n_us")

    assert asked(db) == set()
