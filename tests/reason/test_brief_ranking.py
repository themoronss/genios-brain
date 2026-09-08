"""Wave Z6 · E3 — the book-level daily re-rank, the arithmetic (doc 06 OUT-2, gate K6).

Doc 06's three acceptance rows, one test each: *a stable, explainable top-3*, *a thrice-ignored card
decays*, *three same-account cards yield one carrier*. Everything else here defends the property
that makes those three worth having — that the ranking is a total order a second run reproduces
exactly, and that every step of it is visible in `rank_components` rather than in a sentence.

Pure: no database, no clock, no model. `open_decisions` and the persistence half are driven against
real Postgres, through the request path, in `tests/test_l4_seams_out.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.reason import brief_ranking as B

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 5, 6, 30, tzinfo=timezone.utc)


def decision(decision_id: str, *, base: int, account: str = "acct_a", surfaced: int = 0,
             absences: int = 0) -> B.OpenDecision:
    return B.OpenDecision(decision_id=decision_id, account_ref=account, base_utility_bp=base,
                          surfaced_count=surfaced, absence_count=absences,
                          card_id=f"card_{decision_id}")


def ranked(*decisions: B.OpenDecision, cap: int = B.BRIEF_ENTRY_CAP) -> B.BookRanking:
    return B.book_rank(org_id="org_1", eval_time=NOW, decisions=decisions, entry_cap=cap)


def order(ranking: B.BookRanking) -> list[str]:
    return [entry.decision_id for entry in ranking.ranking.entries]


# =================================================================================================
# doc 06's three rows
# =================================================================================================

def test_a_stable_explainable_top_three():
    """Stable: the same inputs in a different order produce the identical ranking. Explainable:
    every entry carries the terms that put it where it is, and they reconcile with its score."""
    inputs = [decision("d_a", base=8_000, account="acct_a"),
              decision("d_b", base=6_000, account="acct_b"),
              decision("d_c", base=4_000, account="acct_c")]

    first = ranked(*inputs)
    shuffled = ranked(*reversed(inputs))

    assert order(first) == ["d_a", "d_b", "d_c"] == order(shuffled)
    assert first.ranking_hash == shuffled.ranking_hash
    for entry in first.ranking.entries:
        components = dict(entry.rank_components)
        assert set(components) == {B.BASE_COMPONENT, B.CONCENTRATION_COMPONENT,
                                   B.STALENESS_COMPONENT, B.COVERAGE_COMPONENT,
                                   B.BOOK_SCORE_COMPONENT}
        assert (components[B.BASE_COMPONENT]
                - components[B.CONCENTRATION_COMPONENT]
                - components[B.STALENESS_COMPONENT]
                - components[B.COVERAGE_COMPONENT]) == components[B.BOOK_SCORE_COMPONENT]
        assert components[B.BOOK_SCORE_COMPONENT] == entry.book_score_bp


def test_a_thrice_ignored_card_decays_below_one_nobody_has_seen():
    """doc 06's staleness row. The higher-utility card has been surfaced three times and not acted
    on; the brief stops leading with it. Nothing about the DECISION changed — only the day."""
    stale = decision("d_stale", base=7_000, account="acct_a", surfaced=3)
    fresh = decision("d_fresh", base=6_200, account="acct_b")

    ranking = ranked(stale, fresh)

    assert order(ranking) == ["d_fresh", "d_stale"]
    assert dict(ranking.ranking.entries[1].rank_components)[B.STALENESS_COMPONENT] == (
        2 * B.STALENESS_STEP_BP)


def test_the_first_surfacing_is_free_because_a_card_seen_once_is_not_stale():
    once = ranked(decision("d", base=7_000, surfaced=1))
    assert dict(once.ranking.entries[0].rank_components)[B.STALENESS_COMPONENT] == 0


def test_staleness_is_capped_so_an_old_card_never_disappears_entirely():
    forever = ranked(decision("d", base=9_000, surfaced=99))
    assert dict(forever.ranking.entries[0].rank_components)[B.STALENESS_COMPONENT] == (
        B.STALENESS_CAP_BP)


def test_three_cards_on_one_account_yield_one_carrier():
    """doc 06's concentration row. Three cards about one account are one thing to say about that
    account; the best carries it and the others step down, so the brief spends its second and third
    slot on the rest of the book."""
    ranking = ranked(decision("d_1", base=8_000, account="acct_a"),
                     decision("d_2", base=7_800, account="acct_a"),
                     decision("d_3", base=7_600, account="acct_a"),
                     decision("d_other", base=7_000, account="acct_b"))

    penalties = {entry.decision_id: dict(entry.rank_components)[B.CONCENTRATION_COMPONENT]
                 for entry in ranking.ranking.entries}
    assert penalties == {"d_1": 0, "d_2": B.CONCENTRATION_STEP_BP,
                         "d_3": 2 * B.CONCENTRATION_STEP_BP, "d_other": 0}
    # The carrier still leads, and the account's second card now sits behind another account's.
    assert order(ranking)[:2] == ["d_1", "d_other"]


def test_the_account_carrier_is_the_accounts_best_card_and_ties_break_by_id():
    ranking = ranked(decision("d_z", base=5_000, account="acct_a"),
                     decision("d_a", base=5_000, account="acct_a"))
    penalties = {entry.decision_id: dict(entry.rank_components)[B.CONCENTRATION_COMPONENT]
                 for entry in ranking.ranking.entries}
    assert penalties["d_a"] == 0 and penalties["d_z"] == B.CONCENTRATION_STEP_BP


def test_an_unknowable_heavy_decision_ranks_below_an_evidenced_one():
    """doc 06's coverage row. Both decisions scored the same; one of them recorded four absences on
    its own way to that score, and the brief prefers the one that did not."""
    thin = decision("d_thin", base=7_000, account="acct_a", absences=4)
    evidenced = decision("d_evidenced", base=7_000, account="acct_b")

    ranking = ranked(thin, evidenced)

    assert order(ranking) == ["d_evidenced", "d_thin"]
    assert dict(ranking.ranking.entries[1].rank_components)[B.COVERAGE_COMPONENT] == (
        4 * B.COVERAGE_STEP_BP)


def test_the_coverage_penalty_is_capped_so_recording_an_absence_never_becomes_a_cost():
    """A decision that names what it does not know is more honest than one that names nothing. If
    the penalty were unbounded, the cheapest way to rank first would be to record fewer absences."""
    ranking = ranked(decision("d", base=9_000, absences=50))
    assert dict(ranking.ranking.entries[0].rank_components)[B.COVERAGE_COMPONENT] == (
        B.COVERAGE_CAP_BP)


# =================================================================================================
# the laws the three terms are built on
# =================================================================================================

def test_no_portfolio_term_can_raise_a_decision_above_what_layer_4_concluded():
    """All three terms are subtractions. A bonus would be this pass scoring a decision higher than
    the Decision Maker did — a second scorer with opinions the one decider never had."""
    for surfaced in (0, 1, 5):
        for absences in (0, 3):
            for account in ("acct_a", "acct_b"):
                ranking = ranked(decision("d", base=6_000, account=account,
                                          surfaced=surfaced, absences=absences))
                entry = ranking.ranking.entries[0]
                assert entry.book_score_bp <= 6_000


def test_a_book_score_never_goes_below_zero():
    ranking = ranked(decision("d_1", base=200, account="acct_a", surfaced=9, absences=9),
                     decision("d_2", base=9_999, account="acct_a"))
    assert all(entry.book_score_bp >= 0 for entry in ranking.ranking.entries)


def test_every_number_in_a_ranking_is_an_integer():
    """Integer basis points end to end — a float here would make the brief machine-dependent and
    `ranking_hash` would stop being a content address."""
    ranking = ranked(decision("d_1", base=6_001, surfaced=2, absences=3),
                     decision("d_2", base=5_999, account="acct_b"))
    for entry in ranking.ranking.entries:
        assert isinstance(entry.book_score_bp, int) and not isinstance(entry.book_score_bp, bool)
        assert all(isinstance(value, int) and not isinstance(value, bool)
                   for value in entry.rank_components.values())


def test_ranks_are_contiguous_from_one_and_each_decision_appears_once():
    ranking = ranked(*[decision(f"d_{index}", base=5_000 + index) for index in range(6)])
    assert [entry.rank for entry in ranking.ranking.entries] == [1, 2, 3, 4, 5, 6]
    assert len({entry.decision_id for entry in ranking.ranking.entries}) == 6


def test_a_duplicate_decision_is_dropped_with_a_receipt_rather_than_double_counted():
    """Two cards claiming one decision would count that situation twice against every other account
    in the book. The better one carries; the drop is on the record, because a brief that silently
    omits something is indistinguishable from one that never saw it."""
    ranking = ranked(decision("d_same", base=7_000, account="acct_a"),
                     decision("d_same", base=3_000, account="acct_b"))

    assert order(ranking) == ["d_same"]
    assert ranking.ranking.entries[0].book_score_bp == 7_000
    assert [row["reason"] for row in ranking.dropped] == [B.DROPPED_DUPLICATE]


def test_everything_below_the_entry_cap_is_receipted_not_silently_lost():
    decisions = [decision(f"d_{index:02d}", base=1_000 + index * 100, account=f"acct_{index}")
                 for index in range(8)]
    ranking = ranked(*decisions, cap=3)

    assert len(ranking.ranking.entries) == 3
    assert {row["reason"] for row in ranking.dropped} == {B.DROPPED_BELOW_CAP}
    assert len(ranking.dropped) == 5
    # The cut is by rank, so what the surface shows is the top of the same order.
    assert order(ranking) == ["d_07", "d_06", "d_05"]


def test_an_empty_book_is_an_empty_ranking_and_not_an_error():
    """A tenant with nothing open has no brief, and that is a state rather than a failure."""
    ranking = ranked()
    assert ranking.ranking.entries == ()
    assert ranking.ranking.brief_date_key == "2026-09-05"


def test_the_day_key_is_the_evaluation_instants_date():
    assert B.brief_date_key(datetime(2026, 1, 2, 23, 59, tzinfo=timezone.utc)) == "2026-01-02"


def test_the_ranking_hash_moves_when_the_ranking_does_and_not_otherwise():
    """`ranking_hash` is what makes "did today's brief change" a string compare — and what stops
    the stored row being rewritten on every read."""
    base = ranked(decision("d_1", base=7_000), decision("d_2", base=6_000, account="acct_b"))
    same = ranked(decision("d_1", base=7_000), decision("d_2", base=6_000, account="acct_b"))
    moved = ranked(decision("d_1", base=7_000, surfaced=4),
                   decision("d_2", base=6_000, account="acct_b"))

    assert base.ranking_hash == same.ranking_hash
    assert base.ranking_hash != moved.ranking_hash


def test_a_negative_count_is_refused_rather_than_clamped():
    """A negative surfacing count is a broken query, not a card nobody has seen; clamping it would
    turn a bug in the read into a plausible-looking brief."""
    with pytest.raises(ValueError):
        B.OpenDecision(decision_id="d", account_ref="a", base_utility_bp=5_000, surfaced_count=-1)
    with pytest.raises(ValueError):
        B.OpenDecision(decision_id="d", account_ref="a", base_utility_bp=20_000)
