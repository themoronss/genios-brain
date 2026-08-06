"""L2 · Situation Engine — the object reasoning consumes instead of the graph.

Two things here are easy to get subtly, invisibly wrong:

  * CONFIDENCE that hides its weakest dimension. Perfect evidence about an entity we
    cannot identify is not "pretty confident" — it is unusable, and an average would
    report it as fine.
  * LIFECYCLE that cannot reopen. A situation marked handled, that never comes back when
    the customer writes again, is worse than no situation at all: it actively hides work.

Most of these tests are about those two.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.context.situations import (ARCHIVE_AFTER_DAYS, DORMANT_AFTER_DAYS,
                                              RESOLVED_BY_FACT, RESOLVED_BY_HUMAN,
                                              STATUS_ACTIVE, STATUS_ARCHIVED,
                                              STATUS_DORMANT, STATUS_RESOLVED,
                                              consistency_score, coverage_score,
                                              decide_lifecycle, evidence_score,
                                              freshness_score, identity_score,
                                              normalize_stage, score_situation,
                                              situation_type)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def _ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def _score(**overrides):
    args = dict(event_count=5, source_count=2, last_seen_at=_ago(1),
                open_discrepancies=0, open_merge_proposals=0,
                present_fields=set(), expected_fields={}, now=NOW)
    args.update(overrides)
    return score_situation(**args)


# ── classification ───────────────────────────────────────────────────────────────

def test_the_type_decides_what_we_expect_to_know() -> None:
    assert situation_type("deal", "sales") == "deal"
    assert situation_type("company", "sales") == "opportunity"
    assert situation_type("company", "support") == "support_case"


def test_an_unmapped_combination_stays_visibly_unmapped() -> None:
    """Falling back to a generic bucket would file a situation as something it is not,
    and the missing-information report would then check the wrong fields."""
    assert situation_type("company", "engineering") == "engineering_company"


# ── evidence ─────────────────────────────────────────────────────────────────────

def test_corroboration_across_tools_beats_volume_in_one() -> None:
    """Twenty emails in one thread are one person's account. An email plus a CRM record
    plus a calendar invite are three systems independently agreeing."""
    one_noisy_source = evidence_score(event_count=20, source_count=1)
    three_quiet_sources = evidence_score(event_count=3, source_count=3)
    assert three_quiet_sources > one_noisy_source


def test_a_single_email_is_weak_evidence() -> None:
    assert evidence_score(event_count=1, source_count=1) < 50


def test_evidence_is_bounded() -> None:
    assert evidence_score(event_count=10_000, source_count=50) == 100
    assert evidence_score(event_count=0, source_count=0) == 0
    assert evidence_score(event_count=-5, source_count=-2) == 0


# ── freshness ────────────────────────────────────────────────────────────────────

def test_freshness_decays_with_age() -> None:
    scores = [freshness_score(last_seen_at=_ago(d), now=NOW)[0]
              for d in (1, 5, 10, 20, 40, 200)]
    assert scores == sorted(scores, reverse=True)
    assert all(known for _, known in
               (freshness_score(last_seen_at=_ago(d), now=NOW) for d in (1, 200)))


def test_undated_evidence_is_unknown_not_stale() -> None:
    """The distinction that keeps absence from reading as bad news. Nothing dated tells
    us nothing about currency — it does not tell us the situation is old."""
    score, known = freshness_score(last_seen_at=None, now=NOW)
    assert known is False
    assert score == 0


# ── consistency and identity ─────────────────────────────────────────────────────

def test_contradicting_sources_cost_confidence() -> None:
    """The CRM says closed, Slack says the customer is unhappy. That is a real dent."""
    assert consistency_score(open_discrepancies=0) == 100
    assert consistency_score(open_discrepancies=1) < 70
    assert consistency_score(open_discrepancies=5) == 0


def test_an_unresolved_duplicate_is_a_large_doubt() -> None:
    """An open merge proposal means the evidence may be split across two nodes — or this
    situation is about the wrong entity. Neither is a small problem."""
    assert identity_score(open_merge_proposals=0) == 100
    assert identity_score(open_merge_proposals=1) <= 40
    assert identity_score(open_merge_proposals=3) < identity_score(open_merge_proposals=1)


# ── the vector ───────────────────────────────────────────────────────────────────

def test_overall_is_the_minimum_not_the_average() -> None:
    """THE central rule. Perfect evidence about an entity we cannot identify is not 60%
    confidence — it is unusable. An average would report it as fine."""
    c = _score(event_count=50, source_count=5, open_merge_proposals=1)
    assert c.evidence == 100
    assert c.identity <= 40
    assert c.overall == c.identity


def test_an_unknown_dimension_is_excluded_not_zeroed() -> None:
    """Scoring undated evidence as zero would turn missing data into bad news and drag
    every otherwise-solid situation to nothing."""
    c = _score(last_seen_at=None)
    assert c.freshness == 0
    assert c.overall > 0
    assert c.inputs["freshness_known"] is False


def test_a_stale_but_known_date_does_lower_confidence() -> None:
    """The opposite case — here we DO know, and the news is genuinely bad."""
    c = _score(last_seen_at=_ago(300))
    assert c.inputs["freshness_known"] is True
    assert c.overall == c.freshness


def test_missing_information_never_lowers_confidence() -> None:
    """Completeness is not correctness. Not knowing a deal's close date does not make
    the stage we DO know less true — and folding it in would make absence read as doubt,
    which this codebase refuses everywhere else."""
    complete = _score(present_fields={"deal.stage", "deal.amount"},
                      expected_fields={"deal.stage": "stage", "deal.amount": "value"})
    sparse = _score(present_fields=set(),
                    expected_fields={"deal.stage": "stage", "deal.amount": "value"})
    assert sparse.coverage < complete.coverage
    assert sparse.overall == complete.overall


def test_the_gaps_are_named_in_plain_language() -> None:
    """A reasoner should be able to ask for what is missing without knowing field names."""
    _, missing = coverage_score(present_fields={"deal.stage"},
                                expected={"deal.stage": "pipeline stage",
                                          "deal.close_date": "expected close date"})
    assert missing == ["expected close date"]


def test_a_type_with_no_expectations_is_fully_covered() -> None:
    """Not "0% known" — we expect nothing, so nothing is missing. Reporting zero would
    invent a gap that does not exist."""
    score, missing = coverage_score(present_fields=set(), expected={})
    assert (score, missing) == (100, [])


def test_the_score_explains_itself() -> None:
    """A confidence number nobody can account for is a number nobody should act on."""
    c = _score(open_discrepancies=2)
    assert c.inputs["open_discrepancies"] == 2
    assert c.inputs["weakest"] == "consistency"


def test_scoring_is_pure_and_repeatable() -> None:
    assert _score() == _score()


# ── lifecycle ────────────────────────────────────────────────────────────────────

def test_a_new_situation_is_active() -> None:
    d = decide_lifecycle(current_status=None, resolved_by=None, last_seen_at=_ago(1),
                         resolved_at=None, terminal_by_fact=False, now=NOW)
    assert d.status == STATUS_ACTIVE


def test_a_quiet_situation_goes_dormant_not_deleted() -> None:
    d = decide_lifecycle(current_status=STATUS_ACTIVE, resolved_by=None,
                         last_seen_at=_ago(DORMANT_AFTER_DAYS + 5), resolved_at=None,
                         terminal_by_fact=False, now=NOW)
    assert d.status == STATUS_DORMANT


def test_a_closed_deal_resolves_itself() -> None:
    d = decide_lifecycle(current_status=STATUS_ACTIVE, resolved_by=None,
                         last_seen_at=_ago(1), resolved_at=None,
                         terminal_by_fact=True, now=NOW)
    assert (d.status, d.resolved_by) == (STATUS_RESOLVED, RESOLVED_BY_FACT)


def test_a_deal_reopening_in_the_crm_un_resolves_the_situation() -> None:
    """A conclusion drawn from data must be withdrawn when that data changes. Needing a
    human to undo it would leave the system asserting something it no longer believes."""
    d = decide_lifecycle(current_status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_FACT,
                         last_seen_at=_ago(1), resolved_at=_ago(10),
                         terminal_by_fact=False, now=NOW)
    assert d.status == STATUS_ACTIVE
    assert d.reopened is True


def test_a_human_resolution_survives_a_refresh() -> None:
    """Recomputing must not quietly undo somebody's decision."""
    d = decide_lifecycle(current_status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_HUMAN,
                         last_seen_at=_ago(10), resolved_at=_ago(5),
                         terminal_by_fact=False, now=NOW)
    assert d.status == STATUS_RESOLVED
    assert d.reopened is False


def test_new_evidence_reopens_a_human_resolution() -> None:
    """Marking something handled is a statement about the past, not a promise about the
    future. When the customer writes again, it is open again — otherwise the situation
    actively hides work."""
    d = decide_lifecycle(current_status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_HUMAN,
                         last_seen_at=_ago(1), resolved_at=_ago(5),
                         terminal_by_fact=False, now=NOW)
    assert d.status == STATUS_ACTIVE
    assert d.reopened is True


def test_evidence_older_than_the_resolution_does_not_reopen() -> None:
    """Backfill delivering old emails must not resurrect everything a team has closed."""
    d = decide_lifecycle(current_status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_HUMAN,
                         last_seen_at=_ago(30), resolved_at=_ago(5),
                         terminal_by_fact=False, now=NOW)
    assert d.status == STATUS_RESOLVED


def test_a_long_resolved_situation_is_archived() -> None:
    d = decide_lifecycle(current_status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_HUMAN,
                         last_seen_at=_ago(ARCHIVE_AFTER_DAYS + 50),
                         resolved_at=_ago(ARCHIVE_AFTER_DAYS + 10),
                         terminal_by_fact=False, now=NOW)
    assert d.status == STATUS_ARCHIVED


def test_an_archived_situation_still_reopens_on_new_evidence() -> None:
    """Archiving is tidying, not deletion. A customer coming back after a year is exactly
    the moment you most want the history to surface."""
    d = decide_lifecycle(current_status=STATUS_ARCHIVED, resolved_by=RESOLVED_BY_HUMAN,
                         last_seen_at=_ago(1), resolved_at=_ago(ARCHIVE_AFTER_DAYS + 10),
                         terminal_by_fact=False, now=NOW)
    assert d.status == STATUS_ACTIVE


def test_lifecycle_is_pure_and_repeatable() -> None:
    args = dict(current_status=STATUS_ACTIVE, resolved_by=None, last_seen_at=_ago(2),
                resolved_at=None, terminal_by_fact=False, now=NOW)
    assert decide_lifecycle(**args) == decide_lifecycle(**args)


# ── CRM stage spellings ──────────────────────────────────────────────────────────

def test_every_spelling_of_a_closed_deal_counts() -> None:
    """A CRM writes all of these, and the value arrives JSON-encoded with quotes. Missing
    one leaves closed deals sitting in the active list forever."""
    assert {normalize_stage(v) for v in
            ('"closedwon"', "CLOSED_WON", "Closed Won", "closedwon")} == {"closedwon"}


def test_an_open_stage_is_not_mistaken_for_a_closed_one() -> None:
    from genios_engine.context.situations import _TERMINAL_DEAL_STAGES
    for stage in ("contractsent", "negotiation", "qualifiedtobuy", ""):
        assert normalize_stage(stage) not in _TERMINAL_DEAL_STAGES


# ── the boundaries this layer keeps ──────────────────────────────────────────────

def test_situations_never_carry_priority_or_risk() -> None:
    """Those are decisions, and this layer does not decide. The packs already detect
    risk; building it here too would give two layers an opinion about the same thing and
    no way to tell which one was wrong."""
    import inspect

    from genios_engine.context import situations
    source = inspect.getsource(situations).lower()
    for forbidden in ("def priority", "def risk_score", "def recommend", "def urgency"):
        assert forbidden not in source


def test_no_llm_builds_a_situation() -> None:
    import inspect

    from genios_engine.context import situations
    assert "llm" not in inspect.getsource(situations).lower()


def test_a_correlation_with_no_evidence_produces_no_situation() -> None:
    import inspect

    from genios_engine.context.situations import refresh_situations
    assert "if not corr.event_count" in inspect.getsource(refresh_situations)


def test_an_archived_situation_keeps_the_timestamp_it_needs_to_reopen() -> None:
    """The pure rule above says an archived situation reopens on new evidence — but that
    check needs `resolved_at`, and nulling it on archive would strand the row forever.
    A bug living entirely in the seam between the logic and the SQL."""
    import inspect

    from genios_engine.context.situations import refresh_situations
    source = inspect.getsource(refresh_situations)
    assert "in ('resolved', 'archived')" in source


def test_coverage_looks_at_the_whole_situation_not_just_the_anchor() -> None:
    """`thread.ball_in_court` is written to PEOPLE. Checking only the anchor would make
    every company-anchored opportunity report "whose turn it is" missing forever — a
    detector that is always right and never informative."""
    import inspect

    from genios_engine.context.situations import refresh_situations
    source = inspect.getsource(refresh_situations)
    assert "fields_by_correlation" in source
    assert "set(node_facts) | fields_by_correlation" in source


def test_a_reopened_situation_drops_its_resolution_note() -> None:
    """A note explaining why something was closed reads as the current state of something
    that is now open."""
    import inspect

    from genios_engine.context.situations import refresh_situations
    assert "resolution_note = case when excluded.status in" in inspect.getsource(
        refresh_situations)


def test_a_folded_correlation_takes_its_situation_with_it() -> None:
    """Situations are 1:1 with correlations. When an entity merge folds two groups, an
    orphaned situation would sit in the active list describing nothing."""
    import inspect

    from genios_engine.context.merge import _merge_correlations
    assert "delete from context_situations" in inspect.getsource(_merge_correlations)


def test_folding_never_loses_a_human_resolution() -> None:
    """Everything about a situation is rebuilt on the next refresh EXCEPT somebody having
    marked it handled. Confirming two customers are one must not silently reopen work
    that was already closed."""
    import inspect

    from genios_engine.context.merge import _merge_correlations
    source = inspect.getsource(_merge_correlations)
    assert "s.resolved_by = 'human'" in source
    assert "t.resolved_by is distinct from 'human'" in source


def test_a_repointed_situation_follows_the_surviving_entity() -> None:
    from genios_engine.context.merge import _NODE_REFERENCES
    assert ("context_situations", "anchor_node_id") in _NODE_REFERENCES


def test_a_failed_refresh_never_blocks_ingestion() -> None:
    """Every value is derived, so a broken refresh costs one cycle, not data. A stale
    situation view must never stop events from landing."""
    import inspect

    from genios_engine.context.runner import process_pending
    source = inspect.getsource(process_pending)
    refresh_at = source.index("refresh_situations")
    assert "except Exception" in source[refresh_at:refresh_at + 400]


def test_ordering_is_by_confidence_and_says_it_is_not_priority() -> None:
    """Sorting by how sure we are is honest. Calling that a priority would be this layer
    making a decision it is not allowed to make."""
    import inspect

    from genios_engine.context.situations import active_situations
    source = inspect.getsource(active_situations)
    assert "order by s.confidence_overall desc" in source
    assert "not prioritisation" in source.lower() or "NOT prioritisation" in source
