"""X7 · the AUTHORITY VIEW — *who can decide what, in this org, at a stated instant.*

Doc 01 marks L2.1.4 **MISSING ENTIRELY** and is specific about the cost: Layer 4's Policy unit
(*"which organisational rules bind"*) has no rules to read, its Constraint unit (*"what cannot
happen"*) has no thresholds to check, and the Founder Bottleneck surface — the one Globe rates
highest for *"I can't unsee this"* value — is an Authority query and nothing else.

THE FOUR ROWS OF DOC 01's ACCEPTANCE, and where each is proved here:

* an `admin_declared` rule beats a `discovered` one for the same class  ->  the ranking table;
* an inferred rule comes back as a SUGGESTION and never as an enforceable rule  ->  the
  suggestion tests, plus `AuthorityAnswer` refusing to be constructed around one at all;
* a rule with `valid_until` in the past is not returned for now, but IS returned for an `as_of`
  query inside its validity window  ->  the history tests;
* an unmatched class returns `no_authority_rule`, not an empty permissive answer  ->  the
  absence tests, which assert on `reason` and on `approver_node_id is None` together, because an
  empty result set is exactly what renders as "anyone may approve".

AND TWO THINGS THE DOC DOES NOT SAY, which this file treats as part of the same law. A threshold
in one currency does not cover an amount in another — applying it needs an exchange rate we do
not hold, and the failure is a confidently named WRONG approver. And an authority that held last
quarter is not the authority today: a card that escalates to last quarter's approver is worse
than one that escalates to nobody, so every read here states its instant and none of them reads
a clock.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.authority_view import (SOURCE_AUTHORITY_BP, ApproverLoad,
                                                  AuthorityAnswer, AuthorityOutcome,
                                                  AuthorityView, BottleneckReport,
                                                  InMemoryAuthorityRules, PostgresAuthorityRules,
                                                  bottleneck, covers_amount, resolve,
                                                  rules_in_force)
from genios_engine.contracts.authority import NO_AUTHORITY_RULE, AuthorityRule, AuthoritySource

#: This file's own tenant, for the same reason `test_point_in_time.py` has one: the route tests
#: COMMIT, and a committed governance rule under the shared scratch org would be visible to every
#: other real-Postgres test in the session.
ORG_AUTH = "org_x7_authority"

#: A quarter boundary, and the instants either side of it. Authority is historical, so every test
#: below names an instant; these are the three the fixtures move a rule across.
Q1 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
Q2 = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
Q3 = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
TICK = timedelta(microseconds=1)

#: 50 lakh and 10 lakh in paise. Integer minor units, as `contracts/units.Money` stores money and
#: as the threshold column holds it — a float here rounds, and this rounding decides who signs.
FIFTY_LAKH = 5_000_000_00
TEN_LAKH = 1_000_000_00


def rule(rule_id: str, *, subject_type: str = "contract",
         source: AuthoritySource | str = AuthoritySource.ADMIN_DECLARED,
         approver: str = "node_arjun", threshold: int | None = None,
         currency: str | None = None, delegate: str | None = None,
         valid_from: datetime = Q1, valid_until: datetime | None = None,
         evidence_ref: str | None = None) -> AuthorityRule:
    """The real contract object, never a stand-in. A local dataclass would drift from
    `contracts/authority` the first time a validator moves, and this suite would then be green
    against a rule the rest of the system cannot build."""
    if source in (AuthoritySource.DISCOVERED, "discovered") and evidence_ref is None:
        evidence_ref = "doc:signing_policy_v3"
    return AuthorityRule(
        rule_id=rule_id, subject_type=subject_type, threshold_minor_units=threshold,
        currency=currency or ("INR" if threshold is not None else None),
        approver_node_id=approver, delegate_node_id=delegate, source=source,
        evidence_ref=evidence_ref, valid_from=valid_from, valid_until=valid_until)


# =================================================================================================
# THE RANKING — which of two matching rules decides
# =================================================================================================

ADMIN_50L = rule("authr_admin", threshold=FIFTY_LAKH, approver="node_arjun")
DISCOVERED_50L = rule("authr_doc", source=AuthoritySource.DISCOVERED, threshold=FIFTY_LAKH,
                      approver="node_policy_doc")
ANY_VALUE = rule("authr_any", approver="node_ops")
ADMIN_10L = rule("authr_admin_small", threshold=TEN_LAKH, approver="node_priya")
LATER_ADMIN = rule("authr_admin", threshold=FIFTY_LAKH, approver="node_nikhil", valid_from=Q2)
TIE_A = rule("authr_aaa", threshold=FIFTY_LAKH, approver="node_a")
TIE_B = rule("authr_bbb", threshold=FIFTY_LAKH, approver="node_b")

RANKING_CASES = [
    # (why, rules, amount, expected approver)
    ("admin_declared beats discovered for the same class and threshold",
     (DISCOVERED_50L, ADMIN_50L), FIFTY_LAKH, "node_arjun"),
    ("the tightest matching threshold beats a rule that applies at any value",
     (ANY_VALUE, ADMIN_50L), FIFTY_LAKH, "node_arjun"),
    ("a 60-lakh contract is the 50-lakh approver's, not the 10-lakh one's",
     (ADMIN_10L, ADMIN_50L), FIFTY_LAKH + TEN_LAKH, "node_arjun"),
    ("a 20-lakh contract falls to the 10-lakh rule; the 50-lakh rule does not bite",
     (ADMIN_10L, ADMIN_50L), TEN_LAKH * 2, "node_priya"),
    ("a later version of the same rule supersedes the earlier one at Q3",
     (ADMIN_50L, LATER_ADMIN), FIFTY_LAKH, "node_nikhil"),
    ("a full tie is broken by rule_id, so two runs never disagree",
     (TIE_B, TIE_A), FIFTY_LAKH, "node_a"),
]


@pytest.mark.parametrize("why,rules,amount,expected", RANKING_CASES,
                         ids=[c[0][:48] for c in RANKING_CASES])
def test_the_binding_rule_is_the_one_doc_01_ranks_highest(why, rules, amount, expected):
    answer = resolve(rules, subject_type="contract", evaluated_at=Q3,
                     amount_minor_units=amount, currency="INR")
    assert answer.outcome is AuthorityOutcome.ENFORCEABLE, why
    assert answer.approver_node_id == expected, why
    assert answer.authority_bp == SOURCE_AUTHORITY_BP[answer.rule.source]


def test_the_ranking_does_not_depend_on_the_order_the_rules_arrived_in():
    """A resolver whose answer depends on row order gives a different approver after a VACUUM.
    Every permutation of three matching rules must name the same person."""
    rules = (ANY_VALUE, DISCOVERED_50L, ADMIN_50L)
    answers = {resolve(order, subject_type="contract", evaluated_at=Q3,
                       amount_minor_units=FIFTY_LAKH, currency="INR").approver_node_id
               for order in itertools.permutations(rules)}
    assert answers == {"node_arjun"}


# =================================================================================================
# THE INFERRED RULE — it proposes, and it may never bind
# =================================================================================================

INFERRED = rule("authr_observed", source=AuthoritySource.INFERRED, approver="node_founder",
                threshold=TEN_LAKH)


def test_an_inferred_rule_comes_back_as_a_suggestion_and_never_as_an_approver():
    answer = resolve((INFERRED,), subject_type="contract", evaluated_at=Q3,
                     amount_minor_units=FIFTY_LAKH, currency="INR")
    assert answer.outcome is AuthorityOutcome.SUGGESTED
    assert answer.rule is None and answer.approver_node_id is None
    assert answer.reason == NO_AUTHORITY_RULE
    assert not answer.enforced
    assert [s.rule_id for s in answer.suggestions] == ["authr_observed"]
    assert answer.considered == 1, "the rule was READ; it simply may not bind"


def test_an_enforceable_answer_still_surfaces_the_behaviour_that_disagrees_with_it():
    """Both halves matter: somebody signs, and the observed behaviour that suggests somebody else
    usually does is worth a human's attention rather than being dropped."""
    answer = resolve((ADMIN_10L, INFERRED), subject_type="contract", evaluated_at=Q3,
                     amount_minor_units=FIFTY_LAKH, currency="INR")
    assert answer.approver_node_id == "node_priya"
    assert [s.rule_id for s in answer.suggestions] == ["authr_observed"]


def test_an_answer_cannot_be_built_around_an_inferred_rule_at_all():
    """The law lives in the TYPE, not in the resolver: a future caller assembling an answer by
    hand cannot make an inferred rule enforceable either."""
    with pytest.raises(ValueError, match="may never bind"):
        AuthorityAnswer(subject_type="contract", evaluated_at=Q3,
                        outcome=AuthorityOutcome.ENFORCEABLE, rule=INFERRED,
                        authority_bp=SOURCE_AUTHORITY_BP[AuthoritySource.INFERRED],
                        suggestions=(), considered=1)


def test_an_enforceable_rule_is_never_filed_as_a_suggestion():
    with pytest.raises(ValueError, match="only an inferred rule is a suggestion"):
        AuthorityAnswer(subject_type="contract", evaluated_at=Q3,
                        outcome=AuthorityOutcome.SUGGESTED, rule=None, authority_bp=None,
                        suggestions=(ADMIN_50L,), considered=1)


# =================================================================================================
# ABSENCE IS NOT PERMISSION
# =================================================================================================

ABSENCE_CASES = [
    ("no rule of this class exists at all", (), "contract", FIFTY_LAKH, 0),
    ("rules exist for another class only", (rule("authr_hr", subject_type="hiring"),),
     "contract", FIFTY_LAKH, 0),
    ("the amount is below every threshold in force", (ADMIN_50L,), "contract", TEN_LAKH, 1),
    ("the subject carries no amount and every rule has a threshold", (ADMIN_50L,), "contract",
     None, 1),
]


@pytest.mark.parametrize("why,rules,subject,amount,considered", ABSENCE_CASES,
                         ids=[c[0][:48] for c in ABSENCE_CASES])
def test_an_unmatched_class_says_no_authority_rule_rather_than_going_quiet(
        why, rules, subject, amount, considered):
    """*"We hold no rule for a contract this size"* and *"anyone may approve a contract this
    size"* are opposite facts, and an empty list renders as the second one on every card."""
    answer = resolve(rules, subject_type=subject, evaluated_at=Q3,
                     amount_minor_units=amount, currency=None if amount is None else "INR")
    assert answer.outcome is AuthorityOutcome.NO_AUTHORITY_RULE, why
    assert answer.reason == NO_AUTHORITY_RULE
    assert answer.approver_node_id is None and answer.delegate_node_id is None
    assert not answer.enforced
    assert answer.considered == considered, (
        "'no rule for this class' and 'a rule that did not bite' need different fixes")


# =================================================================================================
# MONEY — a threshold only bites in its own currency, and only on an integer
# =================================================================================================

COVERAGE_CASES = [
    ("an amount at the threshold is covered", ADMIN_50L, FIFTY_LAKH, "INR", True),
    ("an amount below it is not", ADMIN_50L, FIFTY_LAKH - 1, "INR", False),
    ("the same number in another currency is not", ADMIN_50L, FIFTY_LAKH, "USD", False),
    ("an amountless subject does not reach a threshold rule", ADMIN_50L, None, None, False),
    ("an any-value rule covers an amountless subject", ANY_VALUE, None, None, True),
    ("an any-value rule covers any amount too", ANY_VALUE, FIFTY_LAKH, "USD", True),
]


@pytest.mark.parametrize("why,candidate,amount,currency,expected", COVERAGE_CASES,
                         ids=[c[0][:48] for c in COVERAGE_CASES])
def test_a_threshold_bites_only_in_its_own_currency(why, candidate, amount, currency, expected):
    assert covers_amount(candidate, amount, currency) is expected, why


def test_a_cross_currency_amount_gets_no_authority_rule_rather_than_a_converted_guess():
    answer = resolve((ADMIN_50L,), subject_type="contract", evaluated_at=Q3,
                     amount_minor_units=FIFTY_LAKH, currency="USD")
    assert answer.outcome is AuthorityOutcome.NO_AUTHORITY_RULE
    assert answer.considered == 1


def test_an_amount_must_name_its_currency():
    with pytest.raises(ValueError, match="must name its currency"):
        resolve((ADMIN_50L,), subject_type="contract", evaluated_at=Q3,
                amount_minor_units=FIFTY_LAKH)


@pytest.mark.parametrize("bad", [50.0, True, "5000000"])
def test_an_amount_is_integer_minor_units_or_it_is_refused(bad):
    with pytest.raises(TypeError):
        resolve((ADMIN_50L,), subject_type="contract", evaluated_at=Q3,
                amount_minor_units=bad, currency="INR")


# =================================================================================================
# HISTORY — the authority that held last quarter is not necessarily today's
# =================================================================================================

RETIRED = rule("authr_retired", threshold=FIFTY_LAKH, approver="node_priya",
               valid_from=Q1, valid_until=Q2)
CURRENT = rule("authr_current", threshold=FIFTY_LAKH, approver="node_arjun", valid_from=Q2)

WINDOW_CASES = [
    ("inside the retired rule's window it is the answer", Q1, "node_priya"),
    ("one tick before the handover it is still the answer", Q2 - TICK, "node_priya"),
    ("at the handover instant the successor answers, and only the successor", Q2, "node_arjun"),
    ("a quarter later the successor still answers", Q3, "node_arjun"),
]


@pytest.mark.parametrize("why,instant,expected", WINDOW_CASES,
                         ids=[c[0][:48] for c in WINDOW_CASES])
def test_the_window_is_half_open_so_one_instant_has_exactly_one_approver(why, instant, expected):
    """`[valid_from, valid_until)`. A rule superseded at noon and its successor effective at noon
    must not both match noon, or "who approved this" has two answers for one instant and the
    audit trail is a pair of contradictory claims."""
    answer = resolve((RETIRED, CURRENT), subject_type="contract", evaluated_at=instant,
                     amount_minor_units=FIFTY_LAKH, currency="INR")
    assert answer.approver_node_id == expected, why
    assert answer.considered == 1, "exactly one rule is in force at any instant here"


def test_a_retired_rule_is_invisible_now_and_visible_in_its_own_window():
    """Doc 01's third acceptance row, through the STORE — which is where the window is a SQL
    predicate rather than a Python comparison, and therefore where the two can disagree."""
    view = AuthorityView(InMemoryAuthorityRules())
    view.declare(ORG_AUTH, [RETIRED, CURRENT])

    assert [r.rule_id for r in view.rules(ORG_AUTH, as_of=Q3)] == ["authr_current"]
    assert [r.rule_id for r in view.rules(ORG_AUTH, as_of=Q1)] == ["authr_retired"]
    assert len(view.rules(ORG_AUTH)) == 2, "history is kept; it is only filtered on read"


def test_rules_in_force_narrows_by_class_and_instant_together():
    rules = (RETIRED, CURRENT, rule("authr_hire", subject_type="hiring", valid_from=Q1))
    assert {r.rule_id for r in rules_in_force(rules, evaluated_at=Q3)} == {"authr_current",
                                                                          "authr_hire"}
    assert {r.rule_id for r in rules_in_force(rules, evaluated_at=Q3, subject_type="hiring")} == \
           {"authr_hire"}
    assert rules_in_force(rules, evaluated_at=Q1 - TICK) == ()


# =================================================================================================
# THE FOUNDER BOTTLENECK
# =================================================================================================

SOLE = rule("authr_sole", subject_type="contract", approver="node_founder")
SHARED_A = rule("authr_shared_a", subject_type="expense", approver="node_founder")
SHARED_B = rule("authr_shared_b", subject_type="expense", approver="node_cfo")
DELEGATED = rule("authr_delegated", subject_type="legal", approver="node_founder",
                 delegate="node_counsel")


def test_the_bottleneck_is_the_sole_undelegated_approver_of_a_class():
    report = bottleneck((SOLE, SHARED_A, SHARED_B, DELEGATED), evaluated_at=Q3)
    founder = next(load for load in report.loads if load.approver_node_id == "node_founder")

    assert founder.subject_types == ("contract", "expense", "legal")
    assert founder.sole_subject_types == ("contract", "legal")
    assert founder.undelegated_subject_types == ("contract",), (
        "a delegate on the legal rule is an escape hatch; the contract class has none")
    assert founder.is_bottleneck
    assert founder.rule_count == 3
    assert [load.approver_node_id for load in report.bottlenecks] == ["node_founder"]


def test_a_shared_class_makes_nobody_a_bottleneck():
    report = bottleneck((SHARED_A, SHARED_B), evaluated_at=Q3)
    assert report.answered
    assert report.bottlenecks == ()
    assert all(load.sole_subject_types == () for load in report.loads)


def test_a_bottleneck_is_never_manufactured_out_of_observed_behaviour():
    """An inferred rule saying the founder approves everything would otherwise turn "answers
    their email" into a governance finding."""
    report = bottleneck((INFERRED,), evaluated_at=Q3)
    assert not report.answered
    assert report.refusal == NO_AUTHORITY_RULE
    assert report.loads == ()


def test_an_org_with_no_rules_refuses_rather_than_reporting_a_clean_bill_of_health():
    """The refusal doc 01 demands, one level up: "we cannot answer this" and "your authority is
    well spread" are opposite findings that both produce an empty list."""
    empty = bottleneck((), evaluated_at=Q3)
    spread = bottleneck((SHARED_A, SHARED_B), evaluated_at=Q3)
    assert empty.refusal == NO_AUTHORITY_RULE and not empty.answered
    assert spread.refusal is None and spread.answered
    assert empty.bottlenecks == spread.bottlenecks == ()


def test_a_bottleneck_last_quarter_is_not_a_bottleneck_today():
    rules = (rule("authr_old_sole", subject_type="contract", approver="node_founder",
                  valid_from=Q1, valid_until=Q2),
             rule("authr_new_a", subject_type="contract", approver="node_founder", valid_from=Q2),
             rule("authr_new_b", subject_type="contract", approver="node_cfo", valid_from=Q2))
    assert [load.approver_node_id for load in bottleneck(rules, evaluated_at=Q1).bottlenecks] == \
           ["node_founder"]
    assert bottleneck(rules, evaluated_at=Q3).bottlenecks == ()


def test_a_report_cannot_both_refuse_and_carry_findings():
    with pytest.raises(ValueError, match="a refusal carries no loads"):
        BottleneckReport(evaluated_at=Q3, refusal=NO_AUTHORITY_RULE,
                         loads=(ApproverLoad("node_founder", ("contract",), ("contract",),
                                             ("contract",), 1),))


# =================================================================================================
# THE STORE — real Postgres, and the same answers as the hermetic lane
# =================================================================================================

@pytest.fixture(scope="module")
def auth_org(pg_store):
    """This file's own tenant, cloned in SQL from the scratch org and dropped at the end — which
    cascades every authority rule written below out with it."""
    engine = pg_store.engine
    with engine.begin() as conn:
        if not conn.execute(text("select 1 from orgs where id='org_scratch_tests'")).scalar():
            pytest.skip("no scratch org seeded — nothing to clone a tenant from")
        columns = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_generated='NEVER' order by ordinal_position"))]
        projected = ", ".join(":new_id" if c == "id" else c for c in columns)
        conn.execute(text(f"insert into orgs ({', '.join(columns)}) select {projected} "
                          "from orgs where id='org_scratch_tests' on conflict (id) do nothing"),
                     {"new_id": ORG_AUTH})
    yield ORG_AUTH
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": ORG_AUTH})


@pytest.fixture()
def pg_rules(pg_store, auth_org):
    """A clean `authority_rules` table for this tenant on every test."""
    store = PostgresAuthorityRules(pg_store.engine)
    store.erase(ORG_AUTH)
    yield store
    store.erase(ORG_AUTH)


@pytest.mark.pg
def test_a_rule_survives_the_round_trip_through_postgres_unchanged(pg_rules):
    """Through the real constructor on the way back, so a row that violates a coherence law
    raises HERE, naming the rule, rather than reaching a card as a plausible approver."""
    declared = (ADMIN_50L, DISCOVERED_50L, INFERRED, DELEGATED)
    assert pg_rules.put(ORG_AUTH, declared) == 4
    read_back = {r.rule_id: r for r in pg_rules.rules(ORG_AUTH)}
    assert read_back == {r.rule_id: r for r in declared}
    assert read_back["authr_doc"].evidence_ref == "doc:signing_policy_v3"
    assert read_back["authr_admin"].threshold_minor_units == FIFTY_LAKH
    assert isinstance(read_back["authr_admin"].threshold_minor_units, int)


@pytest.mark.pg
def test_declaring_the_same_rule_twice_changes_nothing(pg_rules):
    assert pg_rules.put(ORG_AUTH, [ADMIN_50L]) == 1
    assert pg_rules.put(ORG_AUTH, [ADMIN_50L]) == 0, (
        "an idempotent re-declaration must be visible as one")
    assert len(pg_rules.rules(ORG_AUTH)) == 1


@pytest.mark.pg
def test_the_sql_window_and_the_python_window_agree(pg_rules):
    """The one place the two lanes can silently diverge: `rules(as_of=...)` filters in SQL and
    `rules_in_force` filters in Python, and every historical answer depends on them agreeing."""
    pg_rules.put(ORG_AUTH, [RETIRED, CURRENT, INFERRED])
    everything = pg_rules.rules(ORG_AUTH)
    for instant in (Q1 - TICK, Q1, Q2 - TICK, Q2, Q3):
        from_sql = {r.rule_id for r in pg_rules.rules(ORG_AUTH, as_of=instant)}
        from_python = {r.rule_id for r in rules_in_force(everything, evaluated_at=instant)}
        assert from_sql == from_python, instant.isoformat()


@pytest.mark.pg
def test_superseding_a_rule_keeps_marchs_answer_answerable(pg_rules):
    """A rule is CLOSED, never edited: *"who could approve this in March"* has to survive the
    September edit, which is the whole reason `valid_from` is part of the primary key."""
    view = AuthorityView(pg_rules)
    view.declare(ORG_AUTH, [rule("authr_march", threshold=FIFTY_LAKH, approver="node_priya",
                                 valid_from=Q1)])
    assert view.resolve(ORG_AUTH, subject_type="contract", evaluated_at=Q1,
                        amount_minor_units=FIFTY_LAKH,
                        currency="INR").approver_node_id == "node_priya"

    assert view.supersede(ORG_AUTH, "authr_march", valid_from=Q1, valid_until=Q2)
    view.declare(ORG_AUTH, [rule("authr_april", threshold=FIFTY_LAKH, approver="node_arjun",
                                 valid_from=Q2)])

    march = view.resolve(ORG_AUTH, subject_type="contract", evaluated_at=Q1,
                         amount_minor_units=FIFTY_LAKH, currency="INR")
    today = view.resolve(ORG_AUTH, subject_type="contract", evaluated_at=Q3,
                         amount_minor_units=FIFTY_LAKH, currency="INR")
    assert march.approver_node_id == "node_priya"
    assert today.approver_node_id == "node_arjun"
    assert not view.supersede(ORG_AUTH, "authr_march", valid_from=Q3, valid_until=Q3 + TICK), (
        "superseding is keyed on the version's own valid_from; a wrong one must not match")


@pytest.mark.pg
def test_the_database_refuses_a_threshold_with_no_currency(pg_rules, pg_store):
    """Defence in depth. The contract refuses it first; this is the check constraint that catches
    a hand-written INSERT or a future writer that bypasses the contract."""
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        with pg_store.engine.begin() as conn:
            conn.execute(text(
                "insert into authority_rules (org_id, rule_id, subject_type, "
                "threshold_minor_units, approver_node_id, source, valid_from) "
                "values (:o, 'authr_bad', 'contract', 5000000, 'node_x', 'admin_declared', :t)"),
                {"o": ORG_AUTH, "t": Q1})


@pytest.mark.pg
def test_the_database_refuses_a_window_that_ends_before_it_starts(pg_rules, pg_store):
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        with pg_store.engine.begin() as conn:
            conn.execute(text(
                "insert into authority_rules (org_id, rule_id, subject_type, approver_node_id, "
                "source, valid_from, valid_until) values (:o, 'authr_bad', 'contract', 'node_x', "
                "'admin_declared', :from, :until)"), {"o": ORG_AUTH, "from": Q2, "until": Q1})


@pytest.mark.pg
def test_one_tenants_authority_is_invisible_to_another(pg_rules):
    pg_rules.put(ORG_AUTH, [ADMIN_50L])
    assert pg_rules.rules("org_scratch_tests") == ()
    assert AuthorityView(pg_rules).resolve(
        "org_scratch_tests", subject_type="contract", evaluated_at=Q3,
        amount_minor_units=FIFTY_LAKH, currency="INR").reason == NO_AUTHORITY_RULE


@pytest.mark.pg
def test_the_two_store_lanes_return_the_same_rules(pg_rules):
    """The in-memory store is a real implementation, not a mock: a test that passed against a
    mock and failed against Postgres would be testing the mock."""
    declared = [RETIRED, CURRENT, INFERRED, DELEGATED]
    memory = InMemoryAuthorityRules()
    memory.put(ORG_AUTH, declared)
    pg_rules.put(ORG_AUTH, declared)
    for instant in (None, Q1, Q2, Q3):
        assert memory.rules(ORG_AUTH, as_of=instant) == pg_rules.rules(ORG_AUTH, as_of=instant)


# =================================================================================================
# THE WIRING — the five routes, driven through the router
# =================================================================================================

@pytest.fixture()
def client(pg_rules):
    """The REAL router with only the tenant identity overridden. Layer 1 lost six units to being
    green and unreachable, so every assertion below goes over HTTP: if the router were never
    registered in `main.py`, or reached the wrong store, this is what fails."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api import authority_routes
    from genios_engine.platform.auth import get_current_org
    if authority_routes._graph is None:
        pytest.skip("graph store not configured for the API module")
    app = FastAPI()
    app.include_router(authority_routes.router)
    app.dependency_overrides[get_current_org] = lambda: ORG_AUTH
    return TestClient(app)


@pytest.mark.pg
def test_the_router_is_registered_on_the_application():
    """The wiring itself: `main.py` must include this router, or every route below is reachable
    only from a test."""
    from fastapi.testclient import TestClient

    from genios_engine.main import app
    # Asked of the SERVED application, not of a list of router objects: `app.openapi()` is what
    # the process actually answers on, so an `include_router` line deleted in a later refactor
    # fails here. And one real request each, to prove the path resolves rather than 404s — an
    # unauthenticated call is refused (401/403), which is itself proof the route exists.
    served = app.openapi()["paths"]
    assert "/api/org/{org_id}/authority/resolve" in served
    assert "/api/org/{org_id}/authority/bottleneck" in served
    assert "/api/org/{org_id}/authority/rules" in served
    assert "/graph/as-of" in served

    client = TestClient(app)
    for path in (f"/api/org/{ORG_AUTH}/authority/bottleneck", "/graph/as-of"):
        assert client.get(path).status_code != 404, path


@pytest.mark.pg
def test_a_declared_rule_answers_who_approves_over_http(client):
    declared = client.post(f"/api/org/{ORG_AUTH}/authority/rules", json={
        "subject_type": "contract", "approver_node_id": "node_arjun",
        "threshold_minor_units": FIFTY_LAKH, "currency": "INR",
        "valid_from": Q1.isoformat()})
    assert declared.status_code == 200, declared.text
    assert declared.json()["rule"]["source"] == "admin_declared", "a console POST is a human"

    answer = client.get(f"/api/org/{ORG_AUTH}/authority/resolve", params={
        "subject_type": "contract", "amount_minor_units": FIFTY_LAKH, "currency": "INR",
        "as_of": Q3.isoformat()}).json()
    assert answer["outcome"] == "enforceable"
    assert answer["approver_node_id"] == "node_arjun"
    assert answer["reason"] is None
    assert answer["authority_bp"] == 10000


@pytest.mark.pg
def test_an_unmatched_class_is_not_a_permissive_answer_over_http(client):
    body = client.get(f"/api/org/{ORG_AUTH}/authority/resolve",
                      params={"subject_type": "contract"}).json()
    assert body["outcome"] == NO_AUTHORITY_RULE
    assert body["reason"] == NO_AUTHORITY_RULE
    assert body["approver_node_id"] is None
    assert body["considered"] == 0


@pytest.mark.pg
def test_an_inferred_rule_reaches_the_surface_as_something_to_confirm(client):
    client.post(f"/api/org/{ORG_AUTH}/authority/rules", json={
        "subject_type": "expense", "approver_node_id": "node_founder", "source": "inferred",
        "valid_from": Q1.isoformat()})
    body = client.get(f"/api/org/{ORG_AUTH}/authority/resolve",
                      params={"subject_type": "expense", "as_of": Q3.isoformat()}).json()
    assert body["outcome"] == "suggested"
    assert body["approver_node_id"] is None
    assert body["reason"] == NO_AUTHORITY_RULE
    assert body["suggestions"][0]["enforceable"] is False
    assert body["suggestions"][0]["authority_bp"] == 5000


@pytest.mark.pg
def test_a_discovered_rule_that_cannot_name_its_document_is_refused_with_the_reason(client):
    bad = client.post(f"/api/org/{ORG_AUTH}/authority/rules", json={
        "subject_type": "contract", "approver_node_id": "node_arjun", "source": "discovered"})
    assert bad.status_code == 400
    assert "evidence" in bad.text or "document" in bad.text


@pytest.mark.pg
def test_the_founder_bottleneck_surface_answers_and_refuses_over_http(client):
    empty = client.get(f"/api/org/{ORG_AUTH}/authority/bottleneck",
                       params={"as_of": Q3.isoformat()}).json()
    assert empty["answered"] is False and empty["reason"] == NO_AUTHORITY_RULE

    for subject in ("contract", "legal"):
        client.post(f"/api/org/{ORG_AUTH}/authority/rules", json={
            "subject_type": subject, "approver_node_id": "node_founder",
            "valid_from": Q1.isoformat()})
    body = client.get(f"/api/org/{ORG_AUTH}/authority/bottleneck",
                      params={"as_of": Q3.isoformat()}).json()
    assert body["answered"] is True
    assert [b["approver_node_id"] for b in body["bottlenecks"]] == ["node_founder"]
    assert body["bottlenecks"][0]["undelegated_subject_types"] == ["contract", "legal"]


@pytest.mark.pg
def test_the_rules_listing_shows_history_only_when_asked(client):
    client.post(f"/api/org/{ORG_AUTH}/authority/rules", json={
        "rule_id": "authr_http_march", "subject_type": "contract",
        "approver_node_id": "node_priya", "valid_from": Q1.isoformat()})
    superseded = client.post(
        f"/api/org/{ORG_AUTH}/authority/rules/authr_http_march/supersede",
        params={"valid_from": Q1.isoformat(), "valid_until": Q2.isoformat()})
    assert superseded.status_code == 200

    now = client.get(f"/api/org/{ORG_AUTH}/authority/rules",
                     params={"as_of": Q3.isoformat()}).json()
    ever = client.get(f"/api/org/{ORG_AUTH}/authority/rules", params={"all_time": True}).json()
    back_then = client.get(f"/api/org/{ORG_AUTH}/authority/rules",
                           params={"as_of": Q1.isoformat()}).json()
    assert now["count"] == 0, "a retired rule is not in force"
    assert ever["count"] == 1, "and it is never deleted"
    assert back_then["rules"][0]["rule_id"] == "authr_http_march"


@pytest.mark.pg
def test_superseding_a_rule_that_was_never_in_force_is_a_404(client):
    missing = client.post(f"/api/org/{ORG_AUTH}/authority/rules/authr_ghost/supersede",
                          params={"valid_from": Q1.isoformat(), "valid_until": Q2.isoformat()})
    assert missing.status_code == 404


@pytest.mark.pg
def test_another_tenants_authority_cannot_be_read_through_the_path(client):
    assert client.get("/api/org/org_someone_else/authority/bottleneck").status_code == 403
