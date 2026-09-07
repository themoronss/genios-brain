"""H7 · doc 01's ACCEPTANCE block for the Authority view, executed exactly as written.

**Gate H7** — invoked by `02-Layer-2-Plan/09-Build-Order-and-Acceptance.md` as:

    pytest tests/context/test_authority.py tests/context/test_point_in_time.py \\
           tests/context/test_dependency_correlation.py -q

This file was a PLACEHOLDER that skipped, and X7 replaces it with the gate it was holding a
place for. It is deliberately SHORT: four tests, one per line of doc 01's ACCEPTANCE block, over
the in-memory store so the gate runs anywhere with no database. The depth — ranking, currency,
the founder bottleneck, the store lanes, the routes — lives in `test_authority_view.py`, which
this file does not duplicate.

    # an admin_declared rule beats a discovered one for the same class
    # an inferred rule is returned as a SUGGESTION and never as an enforceable rule
    # a rule with valid_until in the past is not returned for now, but IS returned
    #   for an as_of query in its validity window
    # an unmatched class returns no_authority_rule, not an empty permissive answer

And the group gate's own metric — *inferred rules auto-applied: 0* — is the second of those,
because it is the one whose failure would let the system invent its own governance.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.context.authority_view import AuthorityOutcome, AuthorityView, \
    InMemoryAuthorityRules
from genios_engine.contracts.authority import NO_AUTHORITY_RULE, AuthorityRule, AuthoritySource

ORG = "org_h7_gate"
MARCH = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
JUNE = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
SEPTEMBER = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)

#: 50 lakh in paise — integer minor units, as the threshold column stores it.
FIFTY_LAKH = 5_000_000_00


def _rule(rule_id: str, source: AuthoritySource, approver: str, **over) -> AuthorityRule:
    base = dict(rule_id=rule_id, subject_type="contract", threshold_minor_units=FIFTY_LAKH,
                currency="INR", approver_node_id=approver, source=source, valid_from=MARCH,
                evidence_ref=("doc:signing_policy" if source is AuthoritySource.DISCOVERED
                              else None))
    base.update(over)
    return AuthorityRule(**base)


@pytest.fixture()
def view() -> AuthorityView:
    return AuthorityView(InMemoryAuthorityRules())


def _answer(view: AuthorityView, at: datetime = SEPTEMBER):
    return view.resolve(ORG, subject_type="contract", evaluated_at=at,
                        amount_minor_units=FIFTY_LAKH, currency="INR")


@pytest.mark.gate
def test_an_admin_declared_rule_beats_a_discovered_one_for_the_same_class(view):
    view.declare(ORG, [_rule("authr_doc", AuthoritySource.DISCOVERED, "node_from_pdf"),
                       _rule("authr_admin", AuthoritySource.ADMIN_DECLARED, "node_arjun")])
    assert _answer(view).approver_node_id == "node_arjun"


@pytest.mark.gate
def test_an_inferred_rule_is_a_suggestion_and_is_never_auto_applied(view):
    """The group gate's own metric: *inferred rules auto-applied — 0.* Inferring an approval
    threshold from behaviour and then enforcing it is the system inventing governance."""
    view.declare(ORG, [_rule("authr_observed", AuthoritySource.INFERRED, "node_founder")])
    answer = _answer(view)
    assert answer.outcome is AuthorityOutcome.SUGGESTED
    assert answer.rule is None and answer.approver_node_id is None
    assert [s.rule_id for s in answer.suggestions] == ["authr_observed"]


@pytest.mark.gate
def test_a_retired_rule_is_gone_from_now_and_still_answers_inside_its_window(view):
    view.declare(ORG, [_rule("authr_retired", AuthoritySource.ADMIN_DECLARED, "node_priya",
                             valid_until=JUNE)])
    assert _answer(view, SEPTEMBER).reason == NO_AUTHORITY_RULE
    assert _answer(view, MARCH).approver_node_id == "node_priya"


@pytest.mark.gate
def test_an_unmatched_class_is_no_authority_rule_and_not_an_empty_permissive_answer(view):
    answer = view.resolve(ORG, subject_type="discount", evaluated_at=SEPTEMBER)
    assert answer.outcome is AuthorityOutcome.NO_AUTHORITY_RULE
    assert answer.reason == NO_AUTHORITY_RULE
    assert answer.approver_node_id is None
    assert not answer.enforced
