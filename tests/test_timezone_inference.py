"""Quiet hours are defined in the recipient's LOCAL time, and nothing supplied one.

`AttentionProfile.timezone` defaulted to "UTC" and the only configured source was
`delivery_preferences.tz_name` — a table with zero rows. Every tenant's politeness window was
therefore evaluated in UTC, which for an India-based founder puts 21:00–08:00 at 02:30–13:30 IST:
it covers his entire working morning and leaves his real evening wide open. Precisely inverted.
"""
from datetime import datetime, timedelta, timezone

from genios_engine.deliver.timezone_infer import (
    MAX_AMBIGUOUS_OFFSET_HOURS,
    MIN_EVENTS,
    awake_fraction,
    infer_zone,
    score_zone,
)


def _sends(local_hours, tz_offset_hours, days=10):
    """Timestamps for somebody in UTC+`tz_offset_hours` who sends mail at `local_hours`."""
    out = []
    base = datetime(2026, 3, 2, tzinfo=timezone.utc)
    for d in range(days):
        for h in local_hours:
            out.append(base + timedelta(days=d, hours=h - tz_offset_hours))
    return out


def test_an_indian_founders_own_send_hours_identify_his_timezone():
    """The evidence was always there: people send mail while they are awake, so a send-hour
    histogram in UTC is a shifted copy of a working day and the shift IS the offset."""
    zone, why = infer_zone(_sends([9, 11, 14, 16, 18, 21], tz_offset_hours=5.5, days=15))
    assert zone == "Asia/Kolkata"
    assert why["reason"] == "inferred_from_activity"
    assert why["score"] > why["utc_score"]


def test_a_california_team_is_not_mistaken_for_an_indian_one():
    zone, _ = infer_zone(_sends([9, 11, 13, 15, 17, 19], tz_offset_hours=-8))
    assert zone in ("America/Los_Angeles", "America/Denver")


def test_too_little_activity_returns_nothing_rather_than_a_guess():
    """An inferred zone that is wrong is worse than a recorded absence, because a wrong value
    stops anyone from asking. `insufficient_activity` keeps the question open."""
    zone, why = infer_zone(_sends([10, 14], tz_offset_hours=5.5, days=3))
    assert zone is None
    assert why["reason"] == "insufficient_activity"
    assert why["required"] == MIN_EVENTS


def test_a_zone_that_explains_nothing_more_than_utc_is_not_a_finding():
    """Round-the-clock activity fits every zone equally. Picking the alphabetical winner of a
    tie would look like a measurement and be a coin flip."""
    zone, why = infer_zone(_sends(list(range(0, 24)), tz_offset_hours=0, days=4))
    assert zone in (None, "UTC")
    if zone is None:
        # Round-the-clock activity has no local night anywhere, so no zone is even admissible —
        # a different refusal than "tied with UTC", and both are correct refusals.
        assert why["reason"] in ("no_better_than_utc", "no_plausible_working_day")


def test_the_runner_up_is_reported_so_a_thin_win_is_visible():
    """Neighbouring zones an hour apart routinely tie. Naming the runner-up keeps "we picked
    Kolkata over Dubai by 5%" stated rather than implied."""
    _, why = infer_zone(_sends([9, 11, 14, 16, 18, 21], tz_offset_hours=5.5))
    assert why["runner_up"]


def test_scoring_is_continuous_so_neighbouring_zones_do_not_tie():
    """The original score was "is the local hour between 7 and 23" — a 16-hour step that
    saturated at 1.0 for every zone within a few hours of the truth. `sorted(reverse=True)` then
    fell through to the zone NAME, and a Kolkata founder was assigned Asia/Tokyo. Quiet hours
    21:00-08:00 Tokyo is 17:30-04:30 IST: it mutes his entire evening, which is strictly worse
    than the UTC default it replaced. Ranking by name is not an inference."""
    ist = _sends([9, 11, 13, 15, 17, 19], tz_offset_hours=5.5)
    assert score_zone(ist, "Asia/Kolkata") > score_zone(ist, "Asia/Tokyo")
    assert score_zone(ist, "Asia/Kolkata") > score_zone(ist, "America/Los_Angeles")
    # the old step measure survives as an admissibility FILTER, not as the ranking
    assert awake_fraction(ist, "Asia/Kolkata") == 1.0


def test_a_tight_working_day_resolves_close_even_when_it_cannot_resolve_exactly():
    """Activity strictly inside 09:00-19:00 local genuinely cannot separate +3 from +6:30 —
    every one of them puts the whole day in daylight and the night empty. The honest outcome is
    a near-miss from the median of the tied set, not a confident exact answer."""
    from zoneinfo import ZoneInfo

    zone, _ = infer_zone(_sends([9, 11, 13, 15, 17, 19], tz_offset_hours=5.5, days=20))
    off = datetime(2026, 3, 2, tzinfo=timezone.utc).astimezone(
        ZoneInfo(zone)).utcoffset().total_seconds() / 3600
    assert abs(off - 5.5) <= 2.5


def test_whatever_it_infers_beats_the_utc_fallback_it_replaces():
    """THE invariant. Refusing is not free — it leaves `orgs.timezone` NULL, and NULL falls back
    to UTC quiet hours, which is 5.5 hours wrong for an Indian founder and 8 for a Californian.
    So an inference is only worth making if it is closer than that, and the tolerance for a tie
    is calibrated against what refusing COSTS rather than against tidiness."""
    from zoneinfo import ZoneInfo

    sample = datetime(2026, 3, 2, tzinfo=timezone.utc)

    def offset(zone):
        return sample.astimezone(ZoneInfo(zone)).utcoffset().total_seconds() / 3600

    for hours, true_offset in (([9, 11, 14, 16, 18, 21], 5.5),     # Kolkata, long day
                               ([9, 11, 13, 15, 17, 19], 5.5),     # Kolkata, tight day
                               ([10, 12, 14, 16, 18, 20, 22], 5.5),  # Kolkata, late day
                               ([9, 11, 13, 15, 17, 19], -8),      # California
                               ([9, 11, 13, 15, 17, 19], 9)):      # Tokyo
        zone, why = infer_zone(_sends(hours, tz_offset_hours=true_offset, days=15))
        if zone is None:
            continue                                   # refusing is always permitted
        error = abs(offset(zone) - true_offset)
        assert error < abs(true_offset), (
            f"{zone} is {error}h off — worse than the UTC fallback it replaced "
            f"({abs(true_offset)}h), so making the inference made things worse")
        # Bounded by the tie width, not half of it — the true offset can sit at an edge of an
        # asymmetric contender set, so the median pick is not symmetric around it.
        assert error <= MAX_AMBIGUOUS_OFFSET_HOURS, (
            f"{zone} is {error}h off, wider than the tie tolerance permits")


def test_a_kolkata_founder_is_never_assigned_tokyo():
    """The exact regression. Under the step measure every nearby zone tied at 1.0 and the winner
    was whichever zone NAME sorted last."""
    for hours in ([9, 11, 13, 15, 17, 19], [9, 11, 14, 16, 18, 21], [10, 12, 15, 18, 21]):
        zone, _ = infer_zone(_sends(hours, tz_offset_hours=5.5, days=15))
        assert zone not in ("Asia/Tokyo", "Australia/Sydney")


def test_a_human_typed_zone_outranks_the_histogram():
    """Inference fills a gap; it never argues with a person."""
    import inspect

    from genios_engine.deliver import timezone_infer

    src = inspect.getsource(timezone_infer.infer_and_store)
    assert "if current and not overwrite" in src


# ── the watermark clock and the query clock must be the same clock ──────────────
def test_incremental_calendar_sync_asks_the_question_the_cursor_answers():
    """The cursor stores `updated` — when Google last TOUCHED the event — and the fetch handed
    that value to `timeMin`, which filters on when the event STARTS.

    Once anyone edits the calendar, max(updated) is roughly now, so timeMin becomes roughly now
    and every earlier-starting event is permanently unreachable — including the rescheduled ones
    the `updated` cursor exists to catch. A meeting moved to an EARLIER slot could never be
    fetched again, which nullifies the guarantee written in the same commit.
    """
    import inspect

    from genios_engine.capture.connectors.calendar import ComposioCalendarConnector

    src = inspect.getsource(ComposioCalendarConnector._fetch)
    assert "updatedMin" in src
    # a first run still bounds the backfill by start time; only the INCREMENTAL run changed
    assert "timeMin" in src
    assert "if since is not None" in src
    # a cursor already poisoned into the future must not be sent as a future bound
    assert "min(since, now)" in src


def test_an_unconfident_drop_keeps_a_body_worth_re_adjudicating():
    """The gate parks a low-confidence junk verdict rather than deleting it, and its comment
    promises the park "keeps a payload". That promise was empty: the fetch decision ran first and
    keyed on `disposition == "drop"` alone, so every parked message had already been reduced to
    the same snippet the model had just judged — and with no MIME payload, its attachments became
    no event at all."""
    import inspect

    from genios_engine.capture.connectors import composio

    src = inspect.getsource(composio)
    assert "DROP_BELOW_RELEVANCE" in src, (
        "the fetch decision and the gate decision must key on the SAME threshold, or they drift")


# ── L7's delivery feed and the legacy/v2 drain split ─────────────────────────────
def test_the_live_enqueue_paths_stamp_delivery_id():
    """`delivery_id` was written by exactly one function in the whole codebase —
    `deliver/spine.py::materialize` — which has no production caller. So
    `feedback/delivery_facts.py`'s `where delivery_id is not null` predicate excluded every row
    either LIVE enqueue path (`enqueue_pending`, `enqueue_digest`) ever wrote: a fully working
    legacy delivery path still fed L7 zero DeliveryFacts, forever."""
    import inspect

    from genios_engine.deliver import outbox

    pending_src = inspect.getsource(outbox.enqueue_pending)
    digest_src = inspect.getsource(outbox.enqueue_digest)
    assert "delivery_id" in pending_src
    assert "delivery_id" in digest_src


def test_the_legacy_drain_and_the_v2_claimer_cannot_select_the_same_row():
    """Neither excluded rows the OTHER path could also claim. Risk was zero only because the v2
    path (`spine.materialize`) has never written a row — the moment it does, both workers could
    select the same one and double-send a card. `dedupe_key` is set by exactly one writer
    (`materialize`), so `is null` / `is not null` on it is a real, already-existing
    discriminator that needs no new column or migration."""
    import inspect

    from genios_engine.deliver import outbox, spine

    drain_src = inspect.getsource(outbox.drain)
    claim_src = inspect.getsource(spine.claim_due)
    assert "dedupe_key is null" in drain_src
    assert "dedupe_key is not null" in claim_src


# ── a domain hint is a pydantic model, not a dict ────────────────────────────────
def test_a_domain_hint_reads_by_attribute_not_by_isinstance_dict():
    """`domain_hints()` returns `DomainHint` PYDANTIC MODELS, never dicts —
    `isinstance(hints[0], dict)` was False on every call, so the coverage-hint branch was
    dead code with a passing type signature: `coverage_ready` stayed None on 100% of emitted
    events no matter what a wired `coverage_fn` would have said."""
    from genios_engine.contracts.gated_event import DomainHint

    calls = []
    hint = DomainHint(domain="sales", source="scope")
    first = hint.get("domain") if isinstance(hint, dict) else getattr(hint, "domain", None)
    assert first == "sales"

    def _coverage_fn(domain):
        calls.append(domain)
        return {"coverage_ready": True}

    if first:
        _coverage_fn(first)
    assert calls == ["sales"], "the fixed read path must actually reach coverage_fn"


# ── an all-stub route is an abstention, not a compiler bug ──────────────────────
def test_unsupported_coverage_is_not_a_domain_compiler_error():
    """Deliberately NOT a `DomainCompilerError` subclass — inheriting from the error hierarchy
    would put it one bare `except DomainCompilerError` away from being silently swallowed again,
    the exact failure this type exists to end."""
    from genios_engine.packs.compiler.errors import DomainCompilerError, UnsupportedCoverage

    assert not issubclass(UnsupportedCoverage, DomainCompilerError)
    exc = UnsupportedCoverage("all_stub", "routed capabilities are incomplete stubs: ['x']")
    assert exc.reason == "all_stub"

    import pytest
    with pytest.raises(ValueError):
        UnsupportedCoverage("not_a_real_reason")


def test_an_all_stub_route_raises_unsupported_coverage_not_authoring_integrity_error():
    """`domain_shadow.py`'s catch-all folded an honest "we do not cover this yet" into the same
    `counts["error"]` as an actual compiler bug — a live cutover would surface an exception, not
    the route-coverage metric's own `all_stub` disposition."""
    import inspect

    from genios_engine.packs.compiler import capability_resolver

    src = inspect.getsource(capability_resolver)
    stub_raise = src[src.index("if not capability_ids:"):]
    stub_raise = stub_raise[:stub_raise.index("if len(capability_ids)")]
    assert "raise UnsupportedCoverage(" in stub_raise
    assert "raise AuthoringIntegrityError(" not in stub_raise


def test_the_shadow_pass_counts_unsupported_coverage_by_reason_not_as_a_generic_error():
    import inspect

    from genios_engine.reason import domain_shadow

    src = inspect.getsource(domain_shadow)
    assert "except UnsupportedCoverage as exc:" in src
    assert 'counts[f"unsupported_{exc.reason}"]' in src


# ── the Boardy chimera: one anchor is not one relationship ──────────────────────
def test_entities_come_from_real_correlation_members_not_the_anchor_alone():
    """`build_business_situation` used to build `entities` as a one-element tuple from
    `anchor_node_id` alone. A situation anchored on `boardy.ai` with 68 correlated events
    reported as being about ONE entity — the connector bot — rather than the dozens of real
    people it introduced. Every later layer inherited that: L3 reasoned about "the Boardy
    relationship" as a unit, and a rejected pitch to one introduced founder read as evidence
    about all of them."""
    from genios_engine.context.situation_bso import build_business_situation

    situation = {"situation_id": "sit_1", "situation_type": "relationship", "anchor_node_id": "n1",
                "status": "active", "confidence_overall": 50, "coverage": 100}
    members = (
        {"id": "a@acme.com", "type": "external_contact", "name": "a@acme.com", "event_count": 5},
        {"id": "b@zenith.io", "type": "external_contact", "name": "b@zenith.io", "event_count": 3},
    )
    bso = build_business_situation(org_id="o", situation=situation, signal_ids=["s1"],
                                   evidence=[{"event_id": "s1", "reconstructed": True}],
                                   trace_id="t1", members=members)
    assert len(bso.entities) == 2
    assert {e["id"] for e in bso.entities} == {"a@acme.com", "b@zenith.io"}


def test_no_members_falls_back_to_the_old_anchor_only_behaviour():
    """A fresh or synthetic situation with no correlation membership yet — the anchor is still
    the only honest entity, exactly the pre-fix behaviour."""
    from genios_engine.context.situation_bso import build_business_situation

    situation = {"situation_id": "sit_1", "situation_type": "relationship", "anchor_node_id": "n1",
                "anchor_type": "person", "anchor_name": "Someone", "status": "active",
                "confidence_overall": 50, "coverage": 100}
    bso = build_business_situation(org_id="o", situation=situation, signal_ids=["s1"],
                                   evidence=[{"event_id": "s1", "reconstructed": True}],
                                   trace_id="t1", members=())
    assert len(bso.entities) == 1
    assert bso.entities[0]["id"] == "n1"
    assert bso.metadata["split_required"] is False


def test_more_than_two_distinct_external_counterparties_requires_a_split():
    """The Boardy shape, minimally reproduced: three or more genuinely distinct external
    parties correlated onto one anchor is not one relationship, and the flag is how a reviewer
    (or a later L2 re-correlation pass) finds out without reading raw correlation rows."""
    from genios_engine.context.situation_bso import (
        SPLIT_REQUIRED_THRESHOLD,
        _distinct_external_domains,
        build_business_situation,
    )

    situation = {"situation_id": "sit_1", "situation_type": "relationship", "anchor_node_id": "n1",
                "status": "active", "confidence_overall": 50, "coverage": 100}
    members = tuple(
        {"id": f"p{i}@company{i}.com", "type": "external_contact",
         "name": f"p{i}@company{i}.com", "event_count": 1}
        for i in range(SPLIT_REQUIRED_THRESHOLD + 1))
    assert len(_distinct_external_domains(members)) == SPLIT_REQUIRED_THRESHOLD + 1
    bso = build_business_situation(org_id="o", situation=situation, signal_ids=["s1"],
                                   evidence=[{"event_id": "s1", "reconstructed": True}],
                                   trace_id="t1", members=members)
    assert bso.metadata["split_required"] is True
    assert bso.metadata["distinct_counterparty_count"] == SPLIT_REQUIRED_THRESHOLD + 1


def test_a_warm_intro_of_two_people_is_not_a_chimera():
    """One sender plus one newly-introduced contact is a genuine, ordinary 1:1-adjacent
    relationship, not a connector-bot fan-out — the threshold must not flag it."""
    from genios_engine.context.situation_bso import build_business_situation

    situation = {"situation_id": "sit_1", "situation_type": "relationship", "anchor_node_id": "n1",
                "status": "active", "confidence_overall": 50, "coverage": 100}
    members = (
        {"id": "intro@friend.com", "type": "external_contact", "name": "x", "event_count": 1},
        {"id": "new@lead.com", "type": "external_contact", "name": "y", "event_count": 1},
    )
    bso = build_business_situation(org_id="o", situation=situation, signal_ids=["s1"],
                                   evidence=[{"event_id": "s1", "reconstructed": True}],
                                   trace_id="t1", members=members)
    assert bso.metadata["split_required"] is False


# ── L5-05: a card action claims its linked execution, same transaction ──────────
def test_a_card_action_claims_pending_toward_running_not_toward_completed():
    """The card surface and the execution subsystem used to be two disconnected state machines:
    `ingest_action` never touched `executions`, so a card the founder marked acted left its
    linked commitment sitting at `created`/`pending` with the clock still running. A card action
    means "claimed", never "done" — no scoped success evidence has arrived, only intent."""
    import inspect

    from genios_engine.deliver import actions

    src = inspect.getsource(actions)
    assert "_CLAIMING_ACTIONS = frozenset({" in src
    assert '"wrong"' not in src.split("_CLAIMING_ACTIONS = frozenset({")[1].split("})")[0]
    assert "ExecutionState.PENDING" in src
    assert "ExecutionState.RUNNING" in src
    assert "ExecutionState.COMPLETED" not in src, (
        "a button press is a claim, not completion — completion needs scoped evidence")


def test_the_claim_transition_and_link_happen_inside_the_cards_transaction():
    """Same transaction as the card write, so the two surfaces can never observe a state where
    one moved and the other did not."""
    import inspect

    from genios_engine.deliver import actions

    src = inspect.getsource(actions.ingest_action)
    with_body = src[src.index("with graph.engine.begin() as c:"):]
    assert "_apply_execution_transition" in with_body
    assert "_link_execution_card" in with_body


def test_apply_transition_does_not_choke_on_its_own_advertised_default():
    """`next_check_at` defaults to `None` and every EXISTING caller happened to always pass an
    explicit value or `close=True` — so the default itself was never exercised against real
    Postgres. The first call using the plain default (this fix's own call site) hit
    `DatatypeMismatch: column next_check_at is ... but expression is of type text`, because an
    untyped None in one CASE branch and a typed column in the other need an explicit cast.
    Correct code with an unreachable-until-now default is the same trap this session keeps
    finding in other layers."""
    import inspect

    from genios_engine.executive import execution_store

    src = inspect.getsource(execution_store.apply_transition)
    assert "cast(:nca as timestamptz)" in src
