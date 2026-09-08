"""U5's urgency ladder, measured on its SUPPLY rather than on a hand-built fact.

`tests/reason/test_timeline_urgency.py` proves the ladder's arithmetic: hand a unit a date and
the right rung comes back, sixteen parametrised cases green. Every one of them passed on the
sixty-decision pilot population while `urgency_bp` was a CONSTANT 0 on 60 of 60 decisions, which
is the whole lesson of this file — an example-based suite cannot see a constant, because a
constant is correct on every single example.

Measured through the production path on a sixty-situation population (`scripts/l4_pilot_seed.py`
plus the L2 derived passes the sweep runs), before:

    core.timeline   urgency_bp = 0      on 60 of 60
    core.priority   urgency_bp = 0      on 60 of 60      -- one value, the whole org

after the three fixes this file guards:

    core.timeline   urgency_bp in {500, 2000, 4000, 6000, 7500, 9000, 10000}   7 distinct
    core.priority   urgency_bp in 12 distinct values, 500 .. 10000, modal count 9 of 60

THREE THINGS WERE BROKEN, in three different layers, and each alone was enough to flatten the
term. They are guarded here together because a test for any one of them passes while the other
two still kill the ladder:

1.  `context/derived.py`'s commitment roll-up walked `company -> person -> commitment`.
    `pipeline.py` writes `person -> company` (`works_at`) and `person -> commitment` (`owns`), so
    the chain matched no row on any org and `commitment.due_at` -- the one field the ladder is
    configured to read -- was absent from every company-anchored situation in the system.

2.  `pipeline.parse_due` returned a NAIVE datetime for the commonest shape a promise takes, a
    plain ISO date. `reasoners/common.parse_time` refuses a naive timestamp and
    `timeline_unit._moment` swallows the refusal, so a date that HAD been read correctly by the
    extractor was dropped without a trace.

3.  `core.temporal` read `derived.engagement` -- a ratio against the relationship's own history,
    band 0.0 .. 3.0 -- through `ratio_bp`, which passes anything above 1 through as basis points.
    Every warming account read as 1..3bp of engagement, published a ~10,000bp drop, and saturated
    `urgency_bp` at the ceiling. Fixing (1) and (2) alone left `core.priority` a spike at 10,000,
    because priority takes the MAXIMUM across sources and this one was pinned at the top.

And one three-state repair in the ladder itself: a declared date that cannot be read is UNKNOWN,
not zero. Publishing 0 for both "nobody committed to a date" and "a date was there and we could
not read it" is what let defect (2) hide behind defect (1) for a whole wave.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from genios_engine.context.derived import compute_deal_view
from genios_engine.context.pipeline import parse_due
from genios_engine.contracts.reasoning import ResultStatus
from genios_engine.reason.reasoners.temporal import TemporalReasoner
from genios_engine.reason.reasoners.timeline_unit import TimelineUnit, urgency_from_hours

from .conftest import NOW, request, run, spec

DUE = "commitment.due_at"

#: Reused rather than re-copied, for the reason `test_account_rollup_reaches_the_company` states:
#: these seeders discover their columns from `information_schema`, so a migration does not break
#: a test about something else.
from tests.test_deal_status_survives_a_sync import _seed_event, _seed_org  # noqa: E402

PG_NOW = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


# ── 2 · L1 normalises the date, and it must arrive normalised ─────────────────────────────────

@pytest.mark.parametrize("due_text", ["2026-08-27", "2026-08-27T09:00:00",
                                     "tomorrow", "next week", "in 3 days"])
def test_every_shape_of_due_date_l1_reads_arrives_timezone_aware(due_text):
    """The split that made one half of the promises invisible.

    A promise dated in WORDS ("tomorrow", "next week") inherited `base`'s zone and was readable
    downstream. The same promise dated EXPLICITLY came back naive from `fromisoformat` and was
    refused by every Layer 4 date reader. Two spellings of one fact, one of them unreadable.
    """
    base = datetime(2026, 8, 20, 9, tzinfo=timezone.utc)
    due = parse_due(due_text, base)
    assert due is not None, "the extractor read a date and the pipeline lost it"
    assert due.tzinfo is not None and due.utcoffset() is not None, (
        "a naive due date is refused by reasoners/common.parse_time and silently dropped by "
        "timeline_unit._moment, which reports it as no date at all")


def test_a_date_written_the_way_the_pipeline_writes_it_reaches_the_ladder():
    """End of the chain for defect (2): the exact string `pipeline.py` stores must ladder.

    The pipeline writes `due.isoformat()`. This asserts against that spelling rather than against
    a hand-written one, so a change to how the date is stored fails here rather than in
    production.
    """
    base = NOW
    due = parse_due((NOW + timedelta(hours=30)).date().isoformat(), base)
    result = run(TimelineUnit(), facts={DUE: {"value": due.isoformat()}})

    assert result.status is ResultStatus.COMPLETED
    assert result.metrics["urgency_bp"] == urgency_from_hours(
        int((due - NOW).total_seconds()) // 3600)
    assert result.metrics["urgency_bp"] > 0


# ── the three-state repair ────────────────────────────────────────────────────────────────────

def test_a_declared_date_that_cannot_be_read_is_unknown_not_zero():
    """UNKNOWN publishes no reading at all; only a genuinely undated situation publishes 0.

    This is the distinction that hid defect (2). While both states shared the number 0, a whole
    org's worth of unreadable `commitment.due_at` values was indistinguishable from a whole org
    that had promised nothing -- and the second is a legitimate, common state, so nobody looked.
    """
    unreadable = run(TimelineUnit(), facts={DUE: {"value": "2026-08-27T09:00:00"}})

    assert unreadable.status is ResultStatus.COMPLETED
    assert "urgency_bp" not in unreadable.metrics, (
        "a date we could not read must not be published as a measured zero")
    assert "material_date_unreadable" in unreadable.reason_codes
    assert "no_material_date" not in unreadable.reason_codes


def test_a_genuinely_undated_situation_still_reads_a_measured_zero():
    """The other side of the same coin, asserted beside it so the two can never re-merge."""
    undated = run(TimelineUnit(), facts={})

    assert undated.metrics["urgency_bp"] == 0
    assert "no_material_date" in undated.reason_codes
    assert "material_date_unreadable" not in undated.reason_codes


# ── 3 · engagement is a ratio against its own history, not a fraction of one ───────────────────

def _temporal(engagement: str, hours_since: int = 0):
    # `Decimal`, not `float`: `platform/canonical.py` forbids floats in a semantic artifact, and
    # `adapters/native.py` hands the unit exactly what `semantic_legacy_value` produced from the
    # number `context/derived.py` wrote. Testing with a float would test a shape that cannot
    # reach the unit in production.
    facts = {"derived.engagement": Decimal(engagement),
             "thread.last_inbound": (NOW - timedelta(hours=hours_since)).isoformat()}
    return TemporalReasoner().evaluate(
        request(spec("core.temporal"), facts=facts), {})


@pytest.mark.parametrize("engagement, expected_bp", [
    ("0.0", 0),        # nothing lately against a real history: total collapse
    ("0.25", 2_500),
    ("0.5", 5_000),    # "halved" -- the reading `max_engagement_bp` is calibrated against
    ("1.0", 10_000),   # the writer's neutral, and no history reads here too
    ("1.4", 10_000),   # WARMING. Read as 1bp before this fix, i.e. total collapse.
    ("3.0", 10_000),   # the writer's cap; read as 3bp before this fix
])
def test_engagement_is_read_on_the_scale_its_writer_declares(engagement, expected_bp):
    """`context/derived.py::_metrics` caps engagement at 3.0 and calls 1.0 neutral.

    Below 1.0 this is arithmetically identical to the `ratio_bp` reading it replaces, so every
    cooling situation -- the ones the unit exists to catch -- is unchanged to the basis point.
    Above 1.0 it stops inverting the reading.
    """
    assert _temporal(engagement).metrics["engagement_bp"] == expected_bp


def test_a_warming_account_is_not_the_most_urgent_thing_in_the_org():
    """The defect as the ranker saw it. `drop_bp` is `10,000 - engagement_bp` and `urgency_bp` is
    built on the drop, so an account engaging at three times its own baseline published a
    maximal drop and a saturated urgency -- and `core.priority` takes the MAXIMUM across sources,
    so that one reading pinned the whole org's urgency term at the ceiling."""
    hot = _temporal("3.0", hours_since=6)
    cold = _temporal("0.1", hours_since=6)

    assert hot.metrics["drop_bp"] == 0
    assert hot.metrics["urgency_bp"] < cold.metrics["urgency_bp"]
    assert hot.metrics["urgency_bp"] < 10_000
    assert "engagement_healthy" in hot.reason_codes


def test_a_record_that_declares_basis_points_is_still_read_as_basis_points():
    """Two shapes, two readings, and the DECLARATION is what separates them -- never the
    magnitude. A fact carrying `value_bp` means what it says."""
    result = TemporalReasoner().evaluate(request(
        spec("core.temporal"),
        facts={"derived.engagement": {"value_bp": 3_000},
               "thread.last_inbound": NOW.isoformat()}), {})
    assert result.metrics["engagement_bp"] == 3_000


# ── 1 · the roll-up that never matched a row ──────────────────────────────────────────────────

def _promise(store, org: str, ev: str, person: str, *, key: str, due: datetime,
             action: str, status: str = "open") -> str:
    with store.engine.begin() as conn:
        node = store.find_or_create_node(conn, org_id=org, node_type="commitment",
                                         canonical_key=key, display_name=action, event_id=ev)
        store.write_edge(conn, org_id=org, edge_type="owns", from_node_id=person,
                         to_node_id=node, confidence=0.9, occurred_at=PG_NOW, event_id=ev,
                         evidence={}, source=None, authority_rank=2)
        for field, value, vt in ((DUE, due.isoformat(), "timestamp"),
                                 ("commitment.text", action, "string"),
                                 ("commitment.status", status, "enum")):
            store.write_fact(conn, org_id=org, subject_node_id=node, field=field, value=value,
                             value_type=vt, confidence=0.9, relevance=0.9, occurred_at=PG_NOW,
                             event_id=ev, evidence={}, source=None, authority_rank=2)
    return node


def _account_with_a_promise(store, org: str, *, promises, reversed_edge: bool = False) -> str:
    """A company, a person under it, and the person's own commitment nodes.

    Wired THE WAY `pipeline.py` WRITES THEM: `works_at` is person -> company and `owns` is
    person -> commitment. A fixture that seeds the reverse proves a query correct that matches
    zero rows live, which is exactly how this roll-up shipped broken.
    """
    ev = f"evt_{org}"
    with store.engine.begin() as conn:
        conn.execute(text("delete from graph_facts where org_id = :o"), {"o": org})
        _seed_event(conn, org, ev)
        company = store.find_or_create_node(conn, org_id=org, node_type="company",
                                            canonical_key=f"{org}.test", display_name="Acme",
                                            event_id=ev)
        person = store.find_or_create_node(conn, org_id=org, node_type="person",
                                           canonical_key=f"p@{org}.test", display_name="P",
                                           event_id=ev)
        ends = (company, person) if reversed_edge else (person, company)
        store.write_edge(conn, org_id=org, edge_type="works_at", from_node_id=ends[0],
                         to_node_id=ends[1], confidence=0.9, occurred_at=PG_NOW, event_id=ev,
                         evidence={}, source=None, authority_rank=2)
    for i, (hours, action, status) in enumerate(promises):
        _promise(store, org, ev, person, key=f"cm:{org}:{i}",
                 due=PG_NOW + timedelta(hours=hours), action=action, status=status)
    return company


def _facts(store, org: str, node: str) -> dict[str, str]:
    with store.engine.connect() as conn:
        return dict(conn.execute(text(
            "select field, value #>> '{}' from graph_facts where org_id=:o and subject_node_id=:n "
            "and status='active' and valid_to is null"), {"o": org, "n": node}).all())


def test_the_company_carries_the_commitment_its_people_made(pg_store):
    """The headline, and the input the whole ladder was starved of.

    A commitment sits TWO hops from the account -- company - person - commitment -- so the 1-hop
    neighbourhood `adapters/native.py` borrows from can never reach it. The roll-up exists to
    close that, and it walked the one edge direction the pipeline does not write.
    """
    org = "urg_rollup_company"
    _seed_org(pg_store, org)
    company = _account_with_a_promise(
        pg_store, org, promises=[(72, "send the signed authorisation form", "open")])

    assert DUE not in _facts(pg_store, org, company), "precondition: the account starts undated"

    compute_deal_view(pg_store, org, now=PG_NOW)

    facts = _facts(pg_store, org, company)
    assert DUE in facts, (
        "the account still cannot see what its people promised, so core.timeline's ladder has "
        "nothing to read and publishes its measured-absence zero for the whole org")
    assert facts["commitment.action"] == "send the signed authorisation form"


def test_the_roll_up_does_not_care_which_way_the_edge_was_written(pg_store):
    """`_person_neighbours` names this bug class in its own docstring -- accept both directions
    rather than assume, or a whole tenant's roll-up is silently empty. The rule is applied to the
    commitment chain here, at BOTH hops."""
    org = "urg_rollup_reversed"
    _seed_org(pg_store, org)
    company = _account_with_a_promise(
        pg_store, org, promises=[(72, "return the signed form", "open")], reversed_edge=True)

    compute_deal_view(pg_store, org, now=PG_NOW)

    assert DUE in _facts(pg_store, org, company)


def test_the_account_carries_the_soonest_open_promise_and_its_own_text(pg_store):
    """Two judgements in one row.

    SOONEST, because urgency is about the nearest obligation and a later one cannot discharge it.
    OPEN, because a promise already kept is not a deadline. And the action must belong to the
    SAME promise as the date: the old shape took `min()` of each column independently, so an
    account with two open promises could publish one obligation's date beside another's text.
    """
    org = "urg_rollup_soonest"
    _seed_org(pg_store, org)
    company = _account_with_a_promise(pg_store, org, promises=[
        (24, "kept already", "done"),          # sooner, but discharged
        (96, "send the filing", "open"),       # the soonest OPEN promise
        (240, "renew the licence", "open"),
    ])

    compute_deal_view(pg_store, org, now=PG_NOW)

    facts = _facts(pg_store, org, company)
    assert facts[DUE] == (PG_NOW + timedelta(hours=96)).isoformat()
    assert facts["commitment.action"] == "send the filing"


# ── the distributional gate: urgency must not be a spike ──────────────────────────────────────

def test_the_urgency_term_is_a_distribution_and_not_a_spike(pg_store):
    """G-L4.2's own row, measured rather than asserted about one example.

    A population of accounts whose promises fall at genuinely different distances must produce
    genuinely different urgency. Both failures this wave has seen would be caught here: a dead
    ladder collapses every reading to 0, and a saturated one collapses every reading to 10,000.
    The assertion is on the SHAPE -- distinct count and modal share -- because a spike is exactly
    what an example-based test cannot see.
    """
    org = "urg_distribution"
    _seed_org(pg_store, org)
    # Hours out chosen to land across the ladder's rungs, not to game it: overdue, days, a week,
    # a fortnight, a month, a quarter and beyond. A real inbox produces this spread; a fixture
    # that seeds one distance would pass on a constant.
    distances = (-48, -1, 6, 30, 60, 100, 200, 300, 500, 900, 1_500, 3_000)
    readings: list[int] = []
    for i, hours in enumerate(distances):
        sub = f"{org}_{i}"
        _seed_org(pg_store, sub)
        company = _account_with_a_promise(
            pg_store, sub, promises=[(hours, f"promise {i}", "open")])
        compute_deal_view(pg_store, sub, now=PG_NOW)
        facts = _facts(pg_store, sub, company)
        assert DUE in facts
        result = run(TimelineUnit(), facts={DUE: {"value": facts[DUE]}},
                     evaluation_time=PG_NOW)
        readings.append(result.metrics["urgency_bp"])

    distinct = set(readings)
    modal = max(readings.count(value) for value in distinct)
    assert len(distinct) >= 5, (
        f"urgency_bp took {len(distinct)} values over {len(readings)} accounts at seven different "
        f"distances: {sorted(distinct)} -- a constant wearing a score's clothes")
    assert modal <= len(readings) // 2, (
        f"one urgency reading covers {modal} of {len(readings)} accounts: {sorted(readings)}")
    assert min(readings) < max(readings)
