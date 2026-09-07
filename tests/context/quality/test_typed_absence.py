"""H6 · TYPED ABSENCE (L2.5.5 · BLG-15) — and the negative-inference licence.

**Gate H6** — invoked by `02-Layer-2-Plan/09-Build-Order-and-Acceptance.md` as::

    pytest tests/context/patterns tests/context/quality -q

This file used to be a PLACEHOLDER that skipped. X6 has landed
(`genios_engine/context/quality/missing.py`), so the placeholder is retired and this is the real
gate. The downstream half — the places that until now read a missing fact as a licence to say
"there isn't one" — is `test_negative_inference.py` beside it.

**The gate row this file is measured on: `0` negative inferences drawn from `UNKNOWABLE` facts.**

Three different things looked identical downstream and every one of them was the empty list:

    no support tickets, the desk connected      genuinely healthy    -> a finding
    no support tickets, no desk connected       UNKNOWABLE           -> nothing at all
    no owner recorded on a work item            a real finding       -> the product

Conflating the first two is how a false churn signal is born, and it is born with a confident
receipt attached. The third is why this component exists at all: *"there is a renewal and no owner
is recorded"* is not missing data, it IS the intelligence.

**What is proven here.** The cascade and its ORDER; that `coverage_ready=None` lands with `False`
and never with absent; that `licenses_negative_inference` is computed and unsettable; that `STALE`
and `NOT_EXPECTED` are told apart from both — three absences a boolean `is_missing` collapses into
one wrong answer; and, on real Postgres, that the DRAIN produces these rows and the database
itself refuses a row that claims an absence it cannot back.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from genios_engine.context.quality.lens import CoverageLens, read_coverage_lens
from genios_engine.context.quality.missing import (ABSENCE_TABLE, AbsenceSubject, Expectation,
                                                   absence_counts, absent_fields, classify_absence,
                                                   classify_all, detect_missing,
                                                   expectations_from_spec, findings, missing_fact,
                                                   read_absences, refresh_typed_absences,
                                                   unknowable_fields)
from genios_engine.contracts.quality import AbsenceType, MissingFact

#: The two facts the doc's own table is written about. `support.ticket_count` is the churn signal;
#: `contract.owner` is the Ownership surface.
TICKETS = Expectation(field="support.ticket_count", label="support tickets", domain="support")
OWNER = Expectation(field="contract.owner", label="owner", domain="admin")


def _lens(**ready: bool) -> CoverageLens:
    """A lens where every NAMED domain has that readiness and a real basis, and every domain not
    named is UNDECLARED — which is the tri-state's middle and the thing most of this file is
    about. `basis` is non-empty for the ready ones because a `GENUINELY_ABSENT` with no receipt is
    unconstructible by design."""
    return CoverageLens(
        org_id="org_x6",
        ready=dict(ready),
        basis={domain: ("communication", "support_desk") for domain in ready},
        epochs={domain: 3 for domain in ready})


def _subject(*, present: tuple[str, ...] = (), domain: str = "support",
             situation_type: str = "support_case", **kw) -> AbsenceSubject:
    return AbsenceSubject(situation_id="sit_x6", subject_node_id="nd_acme", domain=domain,
                          situation_type=situation_type, present_fields=frozenset(present), **kw)


# =================================================================================================
# 1 · THE THREE ROWS OF DOC 05'S OWN TABLE
# =================================================================================================

def test_no_tickets_with_the_desk_connected_is_genuinely_absent(eval_time):
    """Row 1. A source could have carried it, everything we can see was checked, and none did.
    This is the ONLY branch that licenses a negative inference."""
    kind = classify_absence(_subject(), TICKETS, _lens(support=True), eval_time=eval_time)
    assert kind is AbsenceType.GENUINELY_ABSENT


def test_no_tickets_with_no_support_connector_is_unknowable(eval_time):
    """Row 2 — *"conflating this with row 1 is how a false churn signal is born."* The account may
    be perfectly healthy or on fire; this is a statement about our own plumbing."""
    kind = classify_absence(_subject(), TICKETS, _lens(support=False), eval_time=eval_time)
    assert kind is AbsenceType.UNKNOWABLE


def test_coverage_ready_none_is_unknowable_and_never_absent(eval_time):
    """The hard rule, and doc 05 names breaking it *"the worst output in this group"*.

    `None` is not `False` and it is emphatically not `True`: "we never assessed this domain" is
    not evidence that the domain is covered, and reading it as absence is a false negative
    inference about a customer.
    """
    empty = CoverageLens(org_id="org_x6")
    assert empty.ready_for("support") is None
    assert classify_absence(_subject(), TICKETS, empty,
                            eval_time=eval_time) is AbsenceType.UNKNOWABLE


def test_no_owner_on_a_work_item_is_genuinely_absent_and_is_a_finding(eval_time):
    """Row 3, the one that is the product. *"There is a renewal, and no owner is recorded"* is not
    a data-quality complaint — Globe's Ownership surface is built entirely out of it."""
    fact = missing_fact(_subject(domain="admin", situation_type="account_admin"), OWNER,
                        _lens(admin=True), eval_time=eval_time)
    assert fact.absence_type is AbsenceType.GENUINELY_ABSENT
    assert fact.is_finding is True
    assert fact.licenses_negative_inference is True
    assert findings((fact,), {OWNER.field: OWNER}) == (fact,)


def test_a_finding_if_absent_false_expectation_lowers_coverage_without_emitting_a_finding(
        eval_time):
    """Not every gap is interesting. A field that is genuinely absent and not worth saying is
    still an absence — it just is not a card."""
    quiet = Expectation(field="contract.version", label="version", domain="admin",
                        finding_if_absent=False)
    fact = missing_fact(_subject(domain="admin"), quiet, _lens(admin=True), eval_time=eval_time)
    assert fact.absence_type is AbsenceType.GENUINELY_ABSENT
    assert findings((fact,), {quiet.field: quiet}) == ()


# =================================================================================================
# 2 · THE CASCADE'S ORDER — the safety rule, not a style choice
# =================================================================================================

def test_a_present_fact_is_present_and_a_stale_one_is_stale_not_absent(eval_time):
    """`STALE` and `GENUINELY_ABSENT` are different facts with different remedies: a stale fact is
    re-fetched, an absent one is asked about. Collapsing them sends somebody to chase a customer
    for a number we already have."""
    subject = _subject(present=("support.ticket_count",),
                       observed_at={"support.ticket_count": eval_time - timedelta(days=400)})
    assert classify_absence(subject, TICKETS, _lens(support=True), eval_time=eval_time,
                            stale_after=timedelta(days=90)) is AbsenceType.STALE
    #: and with no staleness policy, a present fact is simply PRESENT
    assert classify_absence(subject, TICKETS, _lens(support=True),
                            eval_time=eval_time) is AbsenceType.PRESENT


def test_an_undated_present_fact_is_present_not_stale(eval_time):
    """Evidence with no timestamp tells us nothing about currency — it does not tell us the fact
    is old. The same rule `situations.freshness_score` keeps one file over: a dimension with no
    basis is excluded, never scored as bad news."""
    subject = _subject(present=("support.ticket_count",))
    assert classify_absence(subject, TICKETS, _lens(support=True), eval_time=eval_time,
                            stale_after=timedelta(days=1)) is AbsenceType.PRESENT


def test_an_expectation_that_does_not_apply_is_not_expected_not_a_gap(eval_time):
    """`NOT_EXPECTED` is the fourth answer a boolean `is_missing` cannot give. Scoring it as
    missing makes every situation in a new domain look broken on the day it is added."""
    guarded = Expectation(field="deal.close_date", label="close date", domain="support",
                          expected_when=lambda subject: "deal.stage" in subject.present_fields)
    assert classify_absence(_subject(), guarded, _lens(support=True),
                            eval_time=eval_time) is AbsenceType.NOT_EXPECTED
    assert classify_absence(_subject(present=("deal.stage",)), guarded, _lens(support=True),
                            eval_time=eval_time) is AbsenceType.GENUINELY_ABSENT


def test_coverage_is_consulted_before_absence_is_ever_concluded(eval_time):
    """The ordering rule stated as the property it protects, across the whole cross-product.

    Whatever else is true — expectation applies, fact not held, staleness policy or none — a
    domain whose coverage is not `True` NEVER produces `GENUINELY_ABSENT`. This is the row the
    H6 gate counts: `0` negative inferences drawn from `UNKNOWABLE` facts.
    """
    for ready in (False, None):
        lens = CoverageLens(org_id="org_x6",
                            ready={} if ready is None else {"support": False},
                            basis={"support": ("communication",)})
        for present in ((), ("other.field",)):
            for stale in (None, timedelta(days=1)):
                kind = classify_absence(_subject(present=present), TICKETS, lens,
                                        eval_time=eval_time, stale_after=stale)
                assert kind is AbsenceType.UNKNOWABLE, (ready, present, stale)


def test_coverage_ready_true_with_nothing_to_name_as_consulted_fails_closed(eval_time):
    """*"We looked and it was not there"* with no list of what was looked at is a claim with no
    receipt, and a claim with no receipt is a guess. The honest spelling of a guess is
    `UNKNOWABLE` — refused HERE rather than left for the contract to raise on, so the reason lives
    in one place."""
    thin = CoverageLens(org_id="org_x6", ready={"support": True}, basis={"support": ()})
    assert classify_absence(_subject(), TICKETS, thin,
                            eval_time=eval_time) is AbsenceType.UNKNOWABLE


# =================================================================================================
# 3 · THE LICENCE IS COMPUTED, AND NO CALLER CAN SET IT
# =================================================================================================

def test_the_licence_is_true_for_exactly_one_absence_type(eval_time):
    """Five members, one licence. Stated as a total over the enum rather than as four separate
    assertions, so a sixth member added later cannot quietly arrive licensed."""
    licensed = {AbsenceType.GENUINELY_ABSENT}
    for kind in AbsenceType:
        fact = MissingFact(subject_node_id="nd", expected_fact="a.b", absence_type=kind,
                           coverage_ready=True if kind is AbsenceType.GENUINELY_ABSENT else None,
                           coverage_basis=("crm",) if kind is AbsenceType.GENUINELY_ABSENT else ())
        assert fact.licenses_negative_inference is (kind in licensed), kind


def test_a_caller_cannot_talk_the_licence_onto_an_unknowable_fact():
    """The argument for an exception is always persuasive at the call site and always wrong: the
    same exception is how `UNKNOWABLE` becomes "genuinely absent" and a coverage gap becomes a
    finding about a customer. A disagreeing value is REFUSED, never repaired."""
    with pytest.raises(ValueError, match="computed from absence_type"):
        MissingFact(subject_node_id="nd", expected_fact="a.b",
                    absence_type=AbsenceType.UNKNOWABLE, licenses_negative_inference=True)


def test_the_classifier_cannot_construct_an_absence_it_cannot_back():
    """The classifier is not the only thing that will ever build one of these, so the contract
    re-checks what the cascade already checked. Both rules, from the outside."""
    with pytest.raises(ValueError, match="coverage_ready=True"):
        MissingFact(subject_node_id="nd", expected_fact="a.b",
                    absence_type=AbsenceType.GENUINELY_ABSENT, coverage_ready=None,
                    coverage_basis=("crm",))
    with pytest.raises(ValueError, match="coverage_basis"):
        MissingFact(subject_node_id="nd", expected_fact="a.b",
                    absence_type=AbsenceType.GENUINELY_ABSENT, coverage_ready=True)


def test_the_basis_travels_only_with_the_claim_it_is_a_receipt_for(eval_time):
    """A connected-capability list on an `UNKNOWABLE` would read as "we looked at these and found
    nothing" — the exact sentence this type exists to keep unsayable."""
    unknowable = missing_fact(_subject(), TICKETS, _lens(support=False), eval_time=eval_time)
    assert unknowable.coverage_basis == ()
    assert unknowable.coverage_ready is False        # still REPORTED — the reason is not hidden
    absent = missing_fact(_subject(), TICKETS, _lens(support=True), eval_time=eval_time)
    assert absent.coverage_basis == ("communication", "support_desk")


# =================================================================================================
# 4 · THE TOTAL ANSWER, AND WHAT IS WORTH STORING
# =================================================================================================

def test_classify_all_answers_every_expectation_including_the_present_ones(eval_time):
    """A caller must never have to read "no row" as "present". That absence-of-a-row ambiguity is
    the thing this module removes, and returning only the gaps would reintroduce it one layer up.
    """
    subject = _subject(present=("support.ticket_count",))
    expectations = (TICKETS, OWNER)
    total = classify_all(subject, expectations, _lens(support=True, admin=True),
                         eval_time=eval_time)
    assert {f.expected_fact: f.absence_type for f in total} == {
        "support.ticket_count": AbsenceType.PRESENT,
        "contract.owner": AbsenceType.GENUINELY_ABSENT}
    assert {f.expected_fact for f in detect_missing(subject, expectations,
                                                    _lens(support=True, admin=True),
                                                    eval_time=eval_time)} == {"contract.owner"}


def test_the_expectation_map_is_the_one_the_coverage_number_already_scores_against():
    """Not a second declaration. `situations.coverage_score` and `situation_bso._missing_paths`
    both read `domain_spec.expected_fields`, and a third list here would be a third opinion about
    what a situation type should know — whose failure mode is a permanent false finding."""
    from genios_engine.context.domain_spec import spec_for

    expectations = expectations_from_spec("sales", "deal")
    assert {e.field for e in expectations} == set(spec_for("sales").fields_for("deal"))
    assert all(e.label for e in expectations), "the human label is dropped on the floor"


def test_an_unregistered_domain_expects_nothing_and_that_is_not_full_coverage():
    """*"We never said what complete means here"* is a third state, and it must not be read as
    "nothing is missing" — the `situations.py:196-203` failure, where 34 of one org's 73
    situations reported `missing=[]` and full coverage earned by ignorance."""
    assert expectations_from_spec("astrology", "astrology_company") == ()


# =================================================================================================
# 5 · ON A REAL DATABASE — the drain writes these rows, and the schema refuses a bad one
# =================================================================================================

@pytest.mark.pg
def test_the_drain_writes_typed_absences_for_a_real_situation(pg_store, eval_time):
    """**THE WIRING ROW.** *"Green and called by nothing"* is the defect Layer 1 shipped six
    times; a classifier reached only from its own test is exactly that.

    This drives the PRODUCTION path — `commit_structured` then `situations.refresh_situations`,
    which is what `context/runner.py` calls at the end of every drain — and asserts the rows came
    out of it. It runs TWICE over the same org with the coverage row flipped, because the whole
    subject is that the same graph produces different absence TYPES depending on what could have
    been seen.
    """
    from sqlalchemy import text as sql

    from genios_engine.context import situations
    from genios_engine.context.structured import commit_structured

    org = "org_x6_drain"
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'x6') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        commit_structured(
            pg_store, org_id=org, event_id="x6_d1", source="hubspot",
            source_object_id="deal_x6",
            # `deal.stage` only. `deal.amount`, `deal.close_date` and `commitment.due_at` are the
            # sales/deal expectation map's other three, and they are the absences under test.
            structured_fields={"deal.title": "Acme expansion", "deal.stage": "proposal"},
            node_type="deal", occurred_at=eval_time, display_name="Acme expansion",
            domain_hints=[{"domain": "sales"}])

        # PASS 1 — no coverage row at all. Every absence is UNKNOWABLE, and nothing is licensed.
        assert situations.refresh_situations(pg_store, org, eval_time=eval_time) >= 1
        with pg_store.engine.connect() as conn:
            counts = absence_counts(conn, org)
            stored = read_absences(conn, org)
        assert counts.get("genuinely_absent", 0) == 0, \
            "an undeclared domain produced a licensed negative inference: " + str(counts)
        assert counts.get("unknowable", 0) >= 3, counts
        assert absent_fields(stored) == ()
        assert "deal.amount" in unknowable_fields(stored)

        # PASS 2 — the sweep has filed coverage and the CRM is connected and fresh.
        with pg_store.engine.begin() as conn:
            conn.execute(sql(
                "insert into source_coverage (org_id, domain, required, connected, freshness, "
                " coverage_ready, computed_at) values (:o, 'sales', :req, :con, "
                " cast(:fr as jsonb), true, :at) on conflict (org_id, domain) do update set "
                " freshness = excluded.freshness, coverage_ready = excluded.coverage_ready"),
                {"o": org, "req": ["communication", "crm"], "con": ["communication", "crm"],
                 "fr": '{"communication": "fresh", "crm": "fresh"}', "at": eval_time})
        assert situations.refresh_situations(pg_store, org, eval_time=eval_time) >= 1
        with pg_store.engine.connect() as conn:
            counts = absence_counts(conn, org)
            stored = read_absences(conn, org)
            lens = read_coverage_lens(conn, org)
        assert counts.get("unknowable", 0) == 0, \
            "coverage arrived and the absences did not re-type: " + str(counts)
        assert counts.get("genuinely_absent", 0) >= 3, counts
        assert "deal.amount" in absent_fields(stored)
        assert lens.ready_for("sales") is True
        assert all(a.fact.coverage_basis for a in stored), \
            "a stored finding with no receipt for what was searched"

        # PASS 3 — the gap CLOSES. A recomputation must shrink, or the system keeps asserting a
        # missing amount after the amount was recorded.
        commit_structured(
            pg_store, org_id=org, event_id="x6_d2", source="hubspot",
            source_object_id="deal_x6",
            structured_fields={"deal.stage": "proposal", "deal.amount": "84000"},
            node_type="deal", occurred_at=eval_time, display_name="Acme expansion",
            domain_hints=[{"domain": "sales"}])
        situations.refresh_situations(pg_store, org, eval_time=eval_time)
        with pg_store.engine.connect() as conn:
            assert "deal.amount" not in {a.fact.expected_fact for a in read_absences(conn, org)}
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


@pytest.mark.pg
def test_the_table_itself_refuses_an_absence_that_cannot_be_backed(pg_store, eval_time):
    """The three doctrine constraints, from SQL. `MissingFact` enforces them in Python, and a
    table reachable by six writers needs them enforced where the rows land — a rule that lives in
    one writer is a convention, not a rule."""
    import sqlalchemy.exc
    from sqlalchemy import text as sql

    org = "org_x6_constraints"
    base = ("insert into situation_absences (org_id, situation_id, expected_fact, "
            " subject_node_id, absence_type, coverage_ready, coverage_basis, coverage_domain, "
            " licenses_negative_inference, computed_at) "
            "values (:o, 'sit', :f, 'nd', :kind, :ready, :basis, 'sales', :lic, :at)")
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'x6') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        for label, params in (
            ("licence forged onto an unknowable",
             {"f": "a.b", "kind": "unknowable", "ready": None, "basis": [], "lic": True}),
            ("absent with no coverage",
             {"f": "a.c", "kind": "genuinely_absent", "ready": None, "basis": ["crm"],
              "lic": True}),
            ("absent with no receipt",
             {"f": "a.d", "kind": "genuinely_absent", "ready": True, "basis": [], "lic": True}),
        ):
            with pytest.raises(sqlalchemy.exc.IntegrityError), pg_store.engine.begin() as conn:
                conn.execute(sql(base), {"o": org, "at": eval_time, **params})
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


@pytest.mark.pg
def test_an_absence_from_a_superseded_epoch_licenses_nothing_until_it_is_re_evaluated(
        pg_store, eval_time):
    """L-5's read side, welded to L2.5.5's licence — the two units' seam, and the only place it
    is visible.

    A `GENUINELY_ABSENT` drawn under epoch 1 is not WRONG when the sources change; it is
    UNVERIFIED. It stays on the row (deleting it would lose what the system believed and why) and
    it stops licensing anything until the next drain re-types it.
    """
    from sqlalchemy import text as sql

    org = "org_x6_stale"
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'x6') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        with pg_store.engine.begin() as conn:
            conn.execute(sql(
                "insert into situation_absences (org_id, situation_id, expected_fact, "
                " subject_node_id, absence_type, coverage_ready, coverage_basis, coverage_domain, "
                " coverage_epoch, licenses_negative_inference, computed_at) "
                "values (:o, 'sit', 'contract.owner', 'nd', 'genuinely_absent', true, "
                " :basis, 'sales', 1, true, :at)"),
                {"o": org, "basis": ["crm"], "at": eval_time})
        with pg_store.engine.connect() as conn:
            standing = read_absences(conn, org, current={"sales": 1})
            superseded = read_absences(conn, org, current={"sales": 2})
            other_domain_moved = read_absences(conn, org, current={"sales": 1, "admin": 9})
        assert standing[0].licenses_negative_inference is True
        assert superseded[0].stale_coverage is True
        assert superseded[0].licenses_negative_inference is False
        assert superseded[0].fact.licenses_negative_inference is True, \
            "the stored fact must keep saying what it said — staleness is the READER's finding"
        assert other_domain_moved[0].licenses_negative_inference is True, \
            "a connector in another domain revoked a sales inference"
        assert absent_fields(superseded) == ()
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql(f"delete from {ABSENCE_TABLE} where org_id = :o"), {"o": org})
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


@pytest.mark.pg
def test_recomputing_one_situation_never_touches_another_ones_absences(pg_store, eval_time):
    """The scoping of the shrink. A sweep that saw ten situations must not delete the absences of
    the tenant's other two hundred — the failure a bare `delete where org_id` would produce, and
    which nothing downstream would report as anything but "the findings went away"."""
    from sqlalchemy import text as sql

    org = "org_x6_scope"
    with pg_store.engine.begin() as conn:
        conn.execute(sql("insert into orgs (id, name) values (:o, 'x6') "
                         "on conflict (id) do nothing"), {"o": org})
    try:
        lens = CoverageLens(org_id=org, ready={"sales": True},
                            basis={"sales": ("crm",)}, epochs={"sales": 1})
        with pg_store.engine.begin() as conn:
            for situation in ("sit_a", "sit_b"):
                refresh_typed_absences(conn, org, [AbsenceSubject(
                    situation_id=situation, subject_node_id="nd", domain="sales",
                    situation_type="deal", present_fields=frozenset())],
                    lens=lens, eval_time=eval_time)
        with pg_store.engine.connect() as conn:
            before = {a.situation_id for a in read_absences(conn, org)}
        assert before == {"sit_a", "sit_b"}

        with pg_store.engine.begin() as conn:
            refresh_typed_absences(conn, org, [AbsenceSubject(
                situation_id="sit_a", subject_node_id="nd", domain="sales",
                situation_type="deal",
                present_fields=frozenset({"deal.stage", "deal.amount", "deal.close_date",
                                          "commitment.due_at"}))],
                lens=lens, eval_time=eval_time)
        with pg_store.engine.connect() as conn:
            after = {a.situation_id for a in read_absences(conn, org)}
        assert after == {"sit_b"}, \
            "recomputing sit_a either kept its closed gaps or deleted sit_b's"
    finally:
        with pg_store.engine.begin() as conn:
            conn.execute(sql(f"delete from {ABSENCE_TABLE} where org_id = :o"), {"o": org})
            conn.execute(sql("delete from orgs where id = :o"), {"o": org})


# =================================================================================================
# 6 · THE READ SURFACE — the H6 count is queryable, and it is one tenant's
# =================================================================================================

@pytest.mark.pg
def test_the_absence_route_reports_the_h6_count_for_one_tenant_only(pg_store, eval_time):
    """`GET /api/org/{org}/context/absences` through the app, on real rows.

    Doc 05's gate is a MEASUREMENT — *"negative inferences drawn from `UNKNOWABLE` facts: 0"* —
    and a gate stated as a count needs somewhere to read the count from.
    `context_situations.missing` cannot answer it: it is a jsonb array of human phrases.

    Driven through the ROUTER rather than the reader, because every other assertion in this file
    constructs the reader directly and would pass in a build where `main.py` never included the
    route — which is the same "green and called by nothing" shape one layer up.
    """
    import os

    from fastapi.testclient import TestClient
    from sqlalchemy import text as sql

    from genios_engine.api import quality_routes as R
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.main import app
    from genios_engine.platform.auth import get_current_org

    org, other = "org_x6_route", "org_x6_route_other"
    previous = R._graph
    R._graph = GraphStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    app.dependency_overrides[get_current_org] = lambda: org
    insert = ("insert into situation_absences (org_id, situation_id, expected_fact, "
              " subject_node_id, absence_type, coverage_ready, coverage_basis, coverage_domain, "
              " coverage_epoch, licenses_negative_inference, computed_at) "
              "values (:o, :sid, :f, 'nd', :kind, :ready, :basis, 'sales', :ep, :lic, :at)")
    try:
        with pg_store.engine.begin() as conn:
            for tenant in (org, other):
                conn.execute(sql("insert into orgs (id, name) values (:o, :o) "
                                 "on conflict (id) do nothing"), {"o": tenant})
                conn.execute(sql(
                    "insert into coverage_epochs (org_id, domain, epoch, coverage_ready, "
                    " fingerprint, capabilities, opened_at) "
                    "values (:o, 'sales', 2, true, 'fp', :caps, :at)"),
                    {"o": tenant, "caps": ["crm=fresh"], "at": eval_time})
            conn.execute(sql(insert), {
                "o": org, "sid": "sit_1", "f": "deal.amount", "kind": "unknowable",
                "ready": False, "basis": [], "ep": 2, "lic": False, "at": eval_time})
            conn.execute(sql(insert), {
                "o": org, "sid": "sit_1", "f": "commitment.due_at", "kind": "genuinely_absent",
                "ready": True, "basis": ["crm"], "ep": 2, "lic": True, "at": eval_time})
            # Drawn under epoch 1; the tenant is now on 2. Reported, marked, not licensed.
            conn.execute(sql(insert), {
                "o": org, "sid": "sit_1", "f": "deal.close_date", "kind": "genuinely_absent",
                "ready": True, "basis": ["crm"], "ep": 1, "lic": True, "at": eval_time})
            conn.execute(sql(insert), {
                "o": other, "sid": "sit_secret", "f": "deal.amount", "kind": "genuinely_absent",
                "ready": True, "basis": ["crm"], "ep": 2, "lic": True, "at": eval_time})

        client = TestClient(app)
        response = client.get(f"/api/org/{org}/context/absences")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["counts"] == {"unknowable": 1, "genuinely_absent": 2}
        assert body["licensed"] == 1, \
            "a finding from a superseded coverage epoch was reported as still licensed"
        assert body["stale_coverage"] == 1
        by_fact = {a["expected_fact"]: a for a in body["absences"]}
        assert by_fact["deal.amount"]["licenses_negative_inference"] is False
        assert by_fact["deal.amount"]["coverage_basis"] == []
        assert by_fact["commitment.due_at"]["is_finding"] is True
        assert by_fact["deal.close_date"]["is_finding"] is False

        # ONE TENANT. The other org's finding is the same shape and must not appear.
        assert "sit_secret" not in response.text

        epochs = client.get(f"/api/org/{org}/context/coverage-epochs").json()
        assert [e["domain"] for e in epochs["epochs"]] == ["sales"]
        assert epochs["epochs"][0]["epoch"] == 2

        window = client.get(f"/api/org/{org}/context/coverage-window",
                            params={"domain": "sales", "since_days": 1}).json()
        assert window["ready"] is True and window["crossed"] is False
        assert window["licenses_negative_inference"] is True
        assert client.get(f"/api/org/{other}/context/absences").status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        R._graph = previous
        with pg_store.engine.begin() as conn:
            conn.execute(sql("delete from orgs where id in (:a, :b)"), {"a": org, "b": other})
