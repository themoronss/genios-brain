"""The same day's cards, ordered for whoever is reading them.

    pytest tests/reason/test_a_brief_ranks_for_the_person_reading_it.py -q

The book pass compares the day's decisions against each other and subtracts three portfolio
penalties — concentration, staleness, coverage. It had no idea who the brief was FOR, so a
founder's office and a support lead read the same order.

THE MODULE'S OWN LAW DECIDES THE SHAPE, and it is stated in its docstring: every term is a
SUBTRACTION, never an addition, because "a bonus would let the book pass raise a decision above
what Layer 4 concluded about it, which is a second scorer with opinions the Decision Maker never
had". So this is not a fit bonus. A card inside your remit is left exactly where Layer 4 put it;
a card outside it steps down. Subtraction can only ever say "not this one, today".

INERT UNTIL SOMEBODY DECLARES. `read_profile` returns `{}` for a tenant that has declared nothing,
`answerable_domains` returns an empty set for a persona that states no remit, and an empty remit
penalises nothing. Every tenant today ranks byte-identically to the day before.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.reason.brief_ranking import (
    BASE_COMPONENT, BOOK_SCORE_COMPONENT, ROLE_COMPONENT, ROLE_MISMATCH_BP,
    COVERAGE_CAP_BP, CONCENTRATION_CAP_BP, OpenDecision, book_rank)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)


def _rank(decisions, answerable=None):
    out = book_rank(org_id="org_1", eval_time=NOW, decisions=decisions,
                    answerable_for=answerable)
    return {e.decision_id: e for e in out.ranking.entries}


def _d(decision_id, utility, domain=None, account=None, **kw):
    return OpenDecision(decision_id=decision_id, account_ref=account or decision_id,
                        base_utility_bp=utility, domain=domain, **kw)


def test_a_tenant_that_declared_nothing_ranks_exactly_as_before() -> None:
    """The safety property. No remit means no subtraction and no component — `rank_components`
    stays a record of what actually moved the entry, and the stored brief is byte-identical."""
    entries = _rank([_d("d1", 6_000, "admin"), _d("d2", 5_800, "sales")])
    assert entries["d1"].rank == 1
    assert ROLE_COMPONENT not in dict(entries["d1"].rank_components)
    assert entries["d1"].book_score_bp == 6_000


def test_a_card_outside_the_readers_remit_steps_down() -> None:
    """The point of the change: a sales lead's brief leads with the sales card, even though Layer
    4 scored the admin one higher."""
    entries = _rank([_d("admin_card", 6_000, "admin"), _d("sales_card", 5_800, "sales")],
                    answerable=frozenset({"sales"}))
    assert entries["sales_card"].rank == 1
    assert entries["admin_card"].book_score_bp == 6_000 - ROLE_MISMATCH_BP


def test_a_matching_card_is_never_raised() -> None:
    """The module's law. Layer 4's conclusion is the ceiling; the book pass may only lower."""
    entries = _rank([_d("sales_card", 5_800, "sales")], answerable=frozenset({"sales"}))
    assert entries["sales_card"].book_score_bp == 5_800
    assert ROLE_COMPONENT not in dict(entries["sales_card"].rank_components)


def test_the_penalty_is_named_on_the_entry_it_moved() -> None:
    """"Why #1 today" is data, not narrative. A subtraction nobody can see is a reorder nobody
    can argue with."""
    entries = _rank([_d("admin_card", 6_000, "admin")], answerable=frozenset({"sales"}))
    components = dict(entries["admin_card"].rank_components)
    assert components[ROLE_COMPONENT] == ROLE_MISMATCH_BP
    assert components[BASE_COMPONENT] == 6_000
    assert components[BOOK_SCORE_COMPONENT] == 6_000 - ROLE_MISMATCH_BP


def test_a_card_with_no_domain_takes_no_penalty() -> None:
    """The legacy pack lane carries 51 of this tenant's 72 cards and some have no domain.
    Guessing one would push down most of the brief on the strength of a missing column."""
    entries = _rank([_d("no_domain", 6_000, None)], answerable=frozenset({"sales"}))
    assert entries["no_domain"].book_score_bp == 6_000


def test_an_urgent_card_outside_the_remit_still_reaches_the_reader() -> None:
    """DELIBERATELY SURVIVABLE. The alternative is a system that hides an incident from a founder
    because a file said founders do not do incidents. 1,500bp loses a near-tie and nothing more."""
    entries = _rank([_d("urgent_admin", 9_000, "admin"), _d("routine_sales", 5_000, "sales")],
                    answerable=frozenset({"sales"}))
    assert entries["urgent_admin"].rank == 1


def test_it_is_lighter_than_the_objections_about_the_work_itself() -> None:
    """Ordering of the four terms is a judgement and it is stated: a decision built on absences
    (coverage) and the day's portfolio shape (concentration) both outweigh whose desk it lands on.
    Whose desk it is is the weakest of the four objections, and must stay so."""
    assert ROLE_MISMATCH_BP < COVERAGE_CAP_BP + 1
    assert ROLE_MISMATCH_BP < CONCENTRATION_CAP_BP


def test_the_penalties_stack_and_never_go_below_zero() -> None:
    """Four subtractions on one entry must not produce a negative score, which would sort below a
    card with nothing to say."""
    entries = _rank([_d("piled_on", 1_000, "admin", surfaced_count=9, absence_count=9)],
                    answerable=frozenset({"sales"}))
    assert entries["piled_on"].book_score_bp == 0


def test_a_reader_answerable_for_several_domains_is_penalised_on_none_of_them() -> None:
    """A founder's office answers for everything. The remit is a set, not a single domain."""
    entries = _rank([_d("a", 6_000, "admin"), _d("b", 5_000, "sales")],
                    answerable=frozenset({"admin", "sales", "customer_support"}))
    assert all(ROLE_COMPONENT not in dict(e.rank_components) for e in entries.values())
