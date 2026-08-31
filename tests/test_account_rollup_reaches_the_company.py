"""The account level: company and deal nodes must carry the evidence their situations reason over.

THE FAILURE THESE TESTS EXIST FOR is a direction, and it had already shipped twice.
`pipeline.py::_works_at` writes the edge PERSON -> COMPANY. Both account-level roll-ups assumed
the reverse — `derived.compute_deal_view` selects `e.from_node_id as company`, and
`baselines._account_rows` filtered `node_type='company'` on the FROM side — so on the real graph
each of them walked out to `owns` (company -> deal), read facts off a deal that has none, and
wrote nothing to any company at all.

Measured on the design partner's production graph, read-only, the morning this was written:

  * person nodes    129, holding 1,279 facts
  * company nodes    40, holding    18 facts — 33 of the 40 hold NONE
  * deal nodes       33, holding   137 facts, and no `derived.*` whatever
  * every one of the org's 1,123 observations sits on a person node
  * 49 of 103 live situations are anchored on a company or a deal
  * `baselines` held 387 rows — exactly 129 people x 3 person metrics — and zero
    `contact_frequency` rows, from a build that had run ten minutes earlier

The reason nobody caught it is in this repository: `test_deal_status_survives_a_sync.py`
seeds `works_at` as company -> person, the direction production does not use. A hermetic fixture
that encodes the wrong shape proves a query correct that matches zero rows live. So every test
below seeds the edge THE WAY THE PIPELINE WRITES IT, and one of them seeds it backwards on
purpose to prove the roll-up no longer cares.

WHAT THIS DOES NOT FIX, recorded here so the next reader does not infer more from a passing
suite than it earns. An empty company node did NOT mean the reasoner was blind to the account:
`adapters/native.py` already borrows a missing root field from the 1-hop neighbourhood. Compared
read-only against production, the borrow already finds every value this roll-up writes, and the
roll-up changes 5 of 287. Its value is that the number becomes the ACCOUNT's aggregate rather
than the last-written neighbour's, that evidence cites the account, and that a row exists for
every reader that does not go through the reasoner. The one strictly-new signal is
`derived.contact_frequency`, covered in `test_account_contact_metrics.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.derived import compute_account_view

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


#: Reused rather than re-copied. These two seeders already discover their columns from
#: `information_schema` so a migration does not break a test about something else, and a second
#: hand-written copy of an `orgs` insert is how a suite ends up asserting against a shape the
#: schema no longer has.
from tests.test_deal_status_survives_a_sync import _seed_event, _seed_org  # noqa: E402


def _observe(conn, org: str, node: str, kind: str, *, at: datetime, n: int = 1) -> None:
    for i in range(n):
        conn.execute(text(
            "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
            "status, confidence, occurred_at) values (:i,:o,:n,:k,'active',0.9,:t) "
            "on conflict do nothing"),
            {"i": f"obs_{org}_{node}_{kind}_{i}_{at.date()}", "o": org, "n": node, "k": kind,
             "t": at})


def _seed_account(store, org: str, *, reversed_edge: bool = False,
                  people: int = 1) -> tuple[str, list[str], str]:
    """A company with people under it and a deal, wired the way `pipeline.py` writes them.

    `works_at` is PERSON -> COMPANY and `involves` is DEAL -> PERSON. `reversed_edge` flips the
    works_at edge so a test can prove the roll-up is direction-agnostic rather than merely
    right-by-luck about which way round it happens to be today.
    """
    ev = f"evt_{org}"
    person_ids: list[str] = []
    with store.engine.begin() as conn:
        # The scratch database is session-scoped and REUSED across runs, so a test that asserts
        # "the company starts empty" passes once and fails for ever after. Clearing this org's
        # facts makes each run start from the state the test claims, rather than from whatever
        # the last one left behind.
        conn.execute(text("delete from graph_facts where org_id = :o"), {"o": org})
        _seed_event(conn, org, ev)
        company = store.find_or_create_node(conn, org_id=org, node_type="company",
                                            canonical_key="acme.test",
                                            display_name="Acme", event_id=ev)
        deal = store.find_or_create_node(conn, org_id=org, node_type="deal",
                                         canonical_key=f"deal:acme.test:{org}",
                                         display_name="Acme deal", event_id=ev)
        for i in range(people):
            person = store.find_or_create_node(conn, org_id=org, node_type="person",
                                               canonical_key=f"p{i}@acme.test",
                                               display_name=f"P{i}", event_id=ev)
            person_ids.append(person)
            ends = ((company, person) if reversed_edge else (person, company))
            store.write_edge(conn, org_id=org, edge_type="works_at", from_node_id=ends[0],
                             to_node_id=ends[1], confidence=0.9, occurred_at=NOW, event_id=ev,
                             evidence={}, source=None, authority_rank=2)
            store.write_edge(conn, org_id=org, edge_type="involves", from_node_id=deal,
                             to_node_id=person, confidence=0.9, occurred_at=NOW, event_id=ev,
                             evidence={}, source=None, authority_rank=2)
    return company, person_ids, deal


def _facts(store, org: str, node: str) -> dict[str, str]:
    with store.engine.connect() as conn:
        return dict(conn.execute(text(
            "select field, value #>> '{}' from graph_facts where org_id=:o and subject_node_id=:n "
            "and status='active' and valid_to is null"), {"o": org, "n": node}).all())


def test_the_company_inherits_its_people_s_evidence(pg_store):
    """The headline. A company whose only contact has been corresponding must stop being an empty
    node: on production 33 of 40 companies held zero facts while their people held 1,279."""
    org = "acct_rollup_company"
    _seed_org(pg_store, org)
    company, people, _deal = _seed_account(pg_store, org)

    assert _facts(pg_store, org, company) == {}, "precondition: the company starts empty"

    with pg_store.engine.begin() as conn:
        _observe(conn, org, people[0], "meeting_request", at=NOW - timedelta(days=3), n=4)
        _observe(conn, org, people[0], "positive_reply", at=NOW - timedelta(days=30), n=2)

    compute_account_view(pg_store, org, now=NOW)

    facts = _facts(pg_store, org, company)
    assert "derived.engagement" in facts, "the account still cannot be reasoned about"
    assert "derived.sentiment" in facts
    assert "derived.momentum" in facts
    # meeting_request is a stage-bearing kind and ranks as `engaged`; the STATUS must be the
    # canonical `open` every Sales deal situation compares against, with the richer word kept
    # beside it. Writing `engaged` into deal.status is the regression that once cost the deal
    # lane 20 of 20 situations.
    assert facts["deal.status"] == "open"
    assert facts["deal.stage"] == "engaged"


def test_the_roll_up_does_not_care_which_way_the_edge_was_written(pg_store):
    """The actual defect. `works_at` is written person -> company, and both shipped roll-ups
    matched on the company being the FROM side, so they reached a company never."""
    org = "acct_rollup_reversed"
    _seed_org(pg_store, org)
    company, people, _deal = _seed_account(pg_store, org, reversed_edge=True)

    with pg_store.engine.begin() as conn:
        _observe(conn, org, people[0], "meeting_request", at=NOW - timedelta(days=2), n=3)

    compute_account_view(pg_store, org, now=NOW)

    assert "derived.engagement" in _facts(pg_store, org, company), (
        "the roll-up read the edge in one direction only — the bug that left 33 of 40 companies "
        "empty on production while their people held everything")


def test_the_deal_inherits_derived_facts_too(pg_store):
    """Deals reach their people through `involves`, and held no `derived.*` at all on production —
    27 of 33 deals had a person carrying engagement that never rolled up."""
    org = "acct_rollup_deal"
    _seed_org(pg_store, org)
    _company, people, deal = _seed_account(pg_store, org)

    with pg_store.engine.begin() as conn:
        _observe(conn, org, people[0], "demo_requested", at=NOW - timedelta(days=1), n=2)

    compute_account_view(pg_store, org, now=NOW)

    facts = _facts(pg_store, org, deal)
    assert "derived.engagement" in facts and "derived.momentum" in facts
    # Ownership: `compute_deal_view` already writes deal.status/deal.stage on DEAL nodes through
    # the same `involves` edge and works there. Two writers racing over one `fact_version_id` is
    # the ambiguity this split avoids.
    assert "deal.status" not in facts, (
        "compute_account_view must leave deal-node status to compute_deal_view")


def test_an_account_nobody_has_written_to_reports_nothing_rather_than_neutral(pg_store):
    """NEVER INVENT. `_metrics` returns a neutral 1.0 engagement for an empty accumulator, which
    is right for a person we have not heard from lately and wrong for an account with no
    correspondence at all. "Engagement is normal" and "there is nothing to measure" are different
    claims and only the first may reach a rule."""
    org = "acct_rollup_silent"
    _seed_org(pg_store, org)
    company, _people, _deal = _seed_account(pg_store, org)

    compute_account_view(pg_store, org, now=NOW)

    facts = _facts(pg_store, org, company)
    assert "derived.engagement" not in facts, (
        "an account with no observations was given a neutral engagement it has not earned")
    assert facts == {}, f"nothing should have been written, got {facts}"


def test_the_account_is_waiting_on_us_if_any_one_person_is(pg_store):
    """`us` outranks `them` on purpose: taking the majority or the most recent would let one
    answered contact hide an unanswered one, which is the failure the field exists to catch."""
    org = "acct_rollup_ball"
    _seed_org(pg_store, org)
    company, people, _deal = _seed_account(pg_store, org, people=2)

    with pg_store.engine.begin() as conn:
        _observe(conn, org, people[0], "question", at=NOW - timedelta(days=1))
        for person, side in ((people[0], "them"), (people[1], "us")):
            pg_store.write_fact(conn, org_id=org, subject_node_id=person,
                                field="thread.ball_in_court", value=side, value_type="string",
                                confidence=0.8, relevance=0.8, occurred_at=NOW,
                                event_id=f"evt_{org}", evidence={}, source=None, authority_rank=2)

    compute_account_view(pg_store, org, now=NOW)

    assert _facts(pg_store, org, company)["thread.ball_in_court"] == "us"


def test_the_account_s_last_inbound_is_the_latest_across_its_people(pg_store):
    """An account is not quiet because one contact is. On production 25 of 40 companies had a
    person carrying `thread.last_inbound` and no company carried one."""
    org = "acct_rollup_inbound"
    _seed_org(pg_store, org)
    company, people, _deal = _seed_account(pg_store, org, people=2)
    older, newer = "2026-07-01T00:00:00+00:00", "2026-08-20T00:00:00+00:00"

    with pg_store.engine.begin() as conn:
        _observe(conn, org, people[0], "question", at=NOW - timedelta(days=1))
        for person, stamp in ((people[0], older), (people[1], newer)):
            pg_store.write_fact(conn, org_id=org, subject_node_id=person,
                                field="thread.last_inbound", value=stamp, value_type="string",
                                confidence=0.8, relevance=0.8, occurred_at=NOW,
                                event_id=f"evt_{org}", evidence={}, source=None, authority_rank=2)

    compute_account_view(pg_store, org, now=NOW)

    assert _facts(pg_store, org, company)["thread.last_inbound"] == newer


def test_deal_value_is_never_derived_at_the_account_level_either(pg_store):
    """The line `compute_deal_view` holds, held one level out. `sales.deal_cooling` REQUIRES
    `deal.value` and returned INSUFFICIENT_CONTEXT on 501 production runs because of it; the
    field is present on exactly one node in the whole org. Closing three of that capability's
    four required fields and leaving the fourth open is the correct outcome — a guessed deal size
    flows straight into prioritisation."""
    import inspect

    org = "acct_rollup_no_value"
    _seed_org(pg_store, org)
    company, people, _deal = _seed_account(pg_store, org)
    with pg_store.engine.begin() as conn:
        _observe(conn, org, people[0], "proposal_sent", at=NOW - timedelta(days=2), n=3)

    compute_account_view(pg_store, org, now=NOW)

    assert "deal.value" not in _facts(pg_store, org, company)
    # Check the CODE too, not just this graph: a function could derive it from a source this
    # fixture happens not to seed.
    body = inspect.getsource(compute_account_view)
    body = body[body.index('"""', body.index('"""') + 3) + 3:]      # drop the docstring
    assert "deal.value" not in body, "deal.value must never be derived; nobody stated it"


def test_recomputing_overwrites_rather_than_appending(pg_store):
    """`graph_facts` is version-keyed on `fact_version_id`. A derived value is a RECOMPUTE, so a
    second drain must update its own row — otherwise every sync grows the table per node forever
    and a reader picking "latest" sifts duplicates."""
    org = "acct_rollup_idempotent"
    _seed_org(pg_store, org)
    company, people, _deal = _seed_account(pg_store, org)
    with pg_store.engine.begin() as conn:
        _observe(conn, org, people[0], "meeting_request", at=NOW - timedelta(days=2), n=2)

    first = compute_account_view(pg_store, org, now=NOW)
    second = compute_account_view(pg_store, org, now=NOW)

    assert first == second
    with pg_store.engine.connect() as conn:
        rows = conn.execute(text(
            "select count(*) from graph_facts where org_id=:o and subject_node_id=:n "
            "and field='derived.engagement'"), {"o": org, "n": company}).scalar()
    assert rows == 1, f"the roll-up appended instead of overwriting: {rows} rows"


@pytest.mark.parametrize("obs_kind,stage", [
    ("introduction", "new"),
    ("meeting_request", "engaged"),
    ("demo_requested", "evaluating"),
    ("proposal_sent", "proposing"),
])
def test_the_company_stage_ladder_matches_the_deal_one(pg_store, obs_kind, stage):
    """One stage vocabulary, not two. `compute_deal_view` publishes these words for deals and this
    publishes them for companies; a second ladder would put the same account at two stages."""
    org = f"acct_rollup_stage_{stage}"
    _seed_org(pg_store, org)
    company, people, _deal = _seed_account(pg_store, org)
    with pg_store.engine.begin() as conn:
        _observe(conn, org, people[0], obs_kind, at=NOW - timedelta(days=2))

    compute_account_view(pg_store, org, now=NOW)

    facts = _facts(pg_store, org, company)
    assert facts["deal.status"] == "open"
    assert facts["deal.stage"] == stage


def test_a_lost_account_is_still_lost(pg_store):
    """The normaliser must not flatten everything to `open` — a rule that saw a dead relationship
    as open would keep recommending action on it."""
    org = "acct_rollup_lost"
    _seed_org(pg_store, org)
    company, people, _deal = _seed_account(pg_store, org)
    with pg_store.engine.begin() as conn:
        _observe(conn, org, people[0], "closed_lost_mention", at=NOW - timedelta(days=2))

    compute_account_view(pg_store, org, now=NOW)

    facts = _facts(pg_store, org, company)
    assert facts["deal.status"] == "lost"
    assert "deal.stage" not in facts, "`lost` is already canonical; there is no richer word"
