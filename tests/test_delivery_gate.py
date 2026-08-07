"""Layer 5.2 · the Delivery Engine — may this travel, to this person, right now?

Every test here is hermetic: the units are pure functions and the two stateful pieces
(``PgDeliveryContext``, ``outbox._drain_claimed``) are exercised against fakes that answer SQL by
substring.  No container, no clock of its own, no network.

The suite is organised around the failure modes this layer exists to prevent, because that is
what a reader needs to check when they change it:

  * a correct alert arriving at 03:14, which is how a channel gets muted;
  * a *deferral* spending a retry, which turns politeness into silent delivery loss;
  * an opt-out and a revoked card looking the same in the row, which makes "why did nothing
    arrive?" unanswerable;
  * one tenant's typo stopping every other tenant's mail.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from genios_engine.contracts.delivery import (
    BAND_ORDER,
    DeliveryCandidate,
    DeliveryDecision,
    DeliveryVerdict,
)
from genios_engine.contracts.execution import ChannelClass
from genios_engine.deliver.gate import (
    PgDeliveryContext,
    build_context,
    candidate_from_row,
    channel_class_for,
    defer_until,
    evaluate_delivery,
    resolve_preferences,
)
from genios_engine.deliver.policy import DeliveryPolicy, evaluate_policy
from genios_engine.deliver.timing import (
    AttentionProfile,
    AttentionState,
    evaluate_timing,
    next_open_window,
)

NIGHT = datetime(2026, 8, 7, 2, 0, tzinfo=timezone.utc)          # a Friday, 02:00 UTC
MORNING = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)


def candidate(**over) -> DeliveryCandidate:
    base = dict(org_id="org_1", subject_id="card_1", channel="slack",
                channel_class=ChannelClass.CHAT, band="high", interrupt=False,
                recipient="seat_1")
    base.update(over)
    return DeliveryCandidate(**base)


# ── the contract ──────────────────────────────────────────────────────────────────────
def test_a_deferral_without_a_clock_is_refused_at_construction():
    """A deferral with no ``not_before`` is a message that waits forever. Both halves of the
    invariant are checked, because a SEND that carries a clock is a unit that meant to defer."""
    with pytest.raises(ValueError, match="never wakes up"):
        DeliveryDecision(verdict=DeliveryVerdict.DEFER, unit="timing", reason_code="quiet_hours")
    with pytest.raises(ValueError, match="only a deferral carries a clock"):
        DeliveryDecision(verdict=DeliveryVerdict.SEND, unit="timing", reason_code="ok",
                         not_before=MORNING)


def test_combining_can_only_ever_make_the_system_quieter():
    send = DeliveryDecision.send("a", "fine")
    defer = DeliveryDecision.defer("b", "later", MORNING)
    stop = DeliveryDecision.suppress("c", "never")
    assert DeliveryDecision.combine(send, defer).verdict is DeliveryVerdict.DEFER
    assert DeliveryDecision.combine(send, defer, stop).verdict is DeliveryVerdict.SUPPRESS
    assert DeliveryDecision.combine(stop, defer, send).verdict is DeliveryVerdict.SUPPRESS
    assert DeliveryDecision.combine(send).verdict is DeliveryVerdict.SEND
    with pytest.raises(ValueError):
        DeliveryDecision.combine()


def test_among_deferrals_the_latest_window_binds():
    """Satisfying the earlier window would violate the later one, so the later one is the
    constraint. Equal windows resolve to argument order — the same delivery blocked twice must
    always be explained the same way, or an incident review becomes an argument."""
    early = DeliveryDecision.defer("timing", "quiet_hours", MORNING)
    late = DeliveryDecision.defer("policy", "org_delivery_held", MORNING + timedelta(days=3))
    assert DeliveryDecision.combine(early, late) is late
    assert DeliveryDecision.combine(late, early) is late
    tie = DeliveryDecision.defer("other", "same_moment", MORNING)
    assert DeliveryDecision.combine(early, tie) is early


def test_suppression_is_never_satisfied_by_the_passage_of_time():
    """The one property that separates a suppression from a deferral."""
    later = MORNING + timedelta(days=365)
    assert DeliveryDecision.suppress("policy", "opted_out").is_satisfied_at(later) is False
    assert DeliveryDecision.defer("timing", "quiet_hours", MORNING).is_satisfied_at(later) is True
    assert DeliveryDecision.send("timing", "ok").is_satisfied_at(NIGHT) is True


def test_intrusiveness_is_a_property_of_the_channel_not_of_the_sender():
    """Layer 5's ``interrupt`` means "this deserves attention"; it does not mean "this makes a
    phone buzz". A high card pushed to Slack with interrupt=False still lights a lock screen."""
    assert candidate(channel_class=ChannelClass.CHAT, interrupt=False).intrusive is True
    assert candidate(channel_class=ChannelClass.DIGEST, interrupt=True).intrusive is False
    assert candidate(channel_class=ChannelClass.IN_APP, interrupt=True).intrusive is False
    assert candidate(channel_class=ChannelClass.EMAIL, interrupt=True).intrusive is False


# ── timing: the ⭐ unit ────────────────────────────────────────────────────────────────
def test_quiet_hours_hold_a_message_until_the_window_opens():
    decision = evaluate_timing(candidate(), AttentionProfile(), AttentionState(), now=NIGHT)
    assert decision.verdict is DeliveryVerdict.DEFER
    assert decision.reason_code == "quiet_hours"
    assert decision.not_before == datetime(2026, 8, 7, 8, 0, tzinfo=timezone.utc)


def test_the_timing_unit_can_never_suppress_anything():
    """Whether a person should hear about something at all is not a question about the clock.
    Every reachable branch is swept rather than argued about."""
    profiles = [AttentionProfile(), AttentionProfile(quiet_enabled=False),
                AttentionProfile(quiet_weekends=True), AttentionProfile(timezone="Asia/Kolkata"),
                AttentionProfile(max_interrupts_per_hour=1)]
    states = [AttentionState(), AttentionState(busy_until=MORNING),
              AttentionState(interrupts_last_hour=99, oldest_interrupt_at=NIGHT)]
    hours = [NIGHT + timedelta(hours=h) for h in range(0, 24 * 8, 5)]
    for profile in profiles:
        for state in states:
            for band in BAND_ORDER:
                for interrupt in (True, False):
                    for now in hours:
                        verdict = evaluate_timing(
                            candidate(band=band, interrupt=interrupt),
                            profile, state, now=now).verdict
                        assert verdict is not DeliveryVerdict.SUPPRESS


def test_break_glass_needs_both_the_band_and_layer_fives_confidence_flag():
    """``interrupt`` is only set by ``executive/communication.py`` when the reasoner cleared its
    confidence floor, so a critical-scoring conclusion it is 40% sure of cannot wake anybody —
    and this unit gets that property without knowing what a confidence interval is."""
    profile = AttentionProfile()
    sure = evaluate_timing(candidate(band="critical", interrupt=True), profile,
                           AttentionState(), now=NIGHT)
    assert sure.verdict is DeliveryVerdict.SEND
    assert sure.reason_code == "override_band_critical"

    unsure = evaluate_timing(candidate(band="critical", interrupt=False), profile,
                             AttentionState(), now=NIGHT)
    assert unsure.verdict is DeliveryVerdict.DEFER

    loud_but_not_critical = evaluate_timing(candidate(band="high", interrupt=True), profile,
                                            AttentionState(), now=NIGHT)
    assert loud_but_not_critical.verdict is DeliveryVerdict.DEFER


def test_break_glass_beats_every_other_hold_at_once():
    """Deliberately not a per-check exception: one place decides this is worth waking someone
    for, so raising the bar is a config change rather than an audit of every branch."""
    decision = evaluate_timing(
        candidate(band="critical", interrupt=True), AttentionProfile(),
        AttentionState(busy_until=MORNING, interrupts_last_hour=50, oldest_interrupt_at=NIGHT),
        now=NIGHT)
    assert decision.verdict is DeliveryVerdict.SEND


def test_a_tenant_can_refuse_to_be_woken_by_raising_the_override_band():
    """There is no band above 'critical', so this is how "never interrupt me" is expressed."""
    profile = AttentionProfile(override_band="critical")
    assert evaluate_timing(candidate(band="critical", interrupt=True), profile,
                           AttentionState(), now=NIGHT).verdict is DeliveryVerdict.SEND
    with pytest.raises(ValueError):
        AttentionProfile(override_band="apocalyptic")


def test_a_digest_is_never_held_on_the_clock():
    decision = evaluate_timing(candidate(channel_class=ChannelClass.DIGEST, band="standard"),
                               AttentionProfile(), AttentionState(), now=NIGHT)
    assert decision.verdict is DeliveryVerdict.SEND
    assert decision.reason_code == "channel_not_intrusive"


def test_a_stale_busy_signal_resolves_to_go_not_to_a_closed_window():
    """A ``busy_until`` in the past must not produce a deferral whose window already shut."""
    state = AttentionState(busy_until=MORNING - timedelta(hours=4))
    assert evaluate_timing(candidate(), AttentionProfile(quiet_enabled=False), state,
                           now=MORNING).verdict is DeliveryVerdict.SEND


def test_the_burst_limit_caps_the_minute_not_the_day():
    """Seven cards are a reasonable day and an unreasonable minute. The daily volume is already
    capped by the pack's ``budget_per_user_day`` in deliver/router.py — a second daily dial here
    would be a second answer to one question, and the failure mode is two limits that disagree."""
    profile = AttentionProfile(quiet_enabled=False, max_interrupts_per_hour=3)
    window_started = MORNING - timedelta(minutes=20)
    held = evaluate_timing(candidate(), profile,
                           AttentionState(interrupts_last_hour=3,
                                          oldest_interrupt_at=window_started), now=MORNING)
    assert held.verdict is DeliveryVerdict.DEFER
    assert held.reason_code == "burst_limit"
    assert held.not_before == window_started + timedelta(hours=1)

    ok = evaluate_timing(candidate(), profile,
                         AttentionState(interrupts_last_hour=2), now=MORNING)
    assert ok.verdict is DeliveryVerdict.SEND


def test_a_burst_window_that_already_closed_still_moves_the_clock_forward():
    """Otherwise the row is due immediately and the drain spins against a constraint it just
    failed. One minute is enough to guarantee progress."""
    profile = AttentionProfile(quiet_enabled=False, max_interrupts_per_hour=1)
    stale = MORNING - timedelta(hours=6)
    held = evaluate_timing(candidate(), profile,
                           AttentionState(interrupts_last_hour=9, oldest_interrupt_at=stale),
                           now=MORNING)
    assert held.not_before == MORNING + timedelta(minutes=1)


def test_quiet_hours_are_wall_clock_and_survive_a_daylight_saving_change():
    """Quiet hours are a statement about the wall clock ("not before 8am"), so the search steps
    naive local hours and converts per candidate. Adding absolute hours to an aware datetime
    would drift the boundary by one on the two days a year it matters."""
    profile = AttentionProfile(timezone="America/New_York")
    spring = datetime(2026, 3, 8, 6, 0, tzinfo=timezone.utc)     # 01:00 EST, clocks jump to 03:00
    assert next_open_window(spring, profile) == datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc)
    autumn = datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)    # 01:00 EST, the hour repeats
    assert next_open_window(autumn, profile) == datetime(2026, 11, 1, 13, 0, tzinfo=timezone.utc)
    for opened in (next_open_window(spring, profile), next_open_window(autumn, profile)):
        assert opened.astimezone(ZoneInfo("America/New_York")).hour == 8


def test_a_half_hour_offset_zone_lands_on_the_local_hour_not_the_utc_one():
    profile = AttentionProfile(timezone="Asia/Kolkata")
    opened = next_open_window(NIGHT, profile)
    assert opened == datetime(2026, 8, 7, 2, 30, tzinfo=timezone.utc)
    assert opened.astimezone(ZoneInfo("Asia/Kolkata")).hour == 8


def test_weekend_quiet_finds_monday_rather_than_falling_off_the_search_horizon():
    profile = AttentionProfile(quiet_weekends=True)
    friday_evening = datetime(2026, 8, 7, 22, 0, tzinfo=timezone.utc)
    opened = next_open_window(friday_evening, profile)
    assert opened == datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
    assert opened.weekday() == 0


def test_an_all_day_quiet_window_is_refused_rather_than_silently_muting_a_tenant():
    """Equal bounds mean either zero hours of quiet or twenty-four, and one of those readings
    mutes the product forever. Refusing the config turns a support mystery into a typo."""
    with pytest.raises(ValueError, match="permanently silent"):
        AttentionProfile(quiet_start_hour=9, quiet_end_hour=9)
    AttentionProfile(quiet_enabled=False, quiet_start_hour=9, quiet_end_hour=9)   # explicit off


def test_a_quiet_window_that_cannot_open_sends_rather_than_holding_forever():
    """Unreachable through AttentionProfile, which refuses it. Kept because a message delivered
    slightly rudely beats one that is never delivered at all."""
    profile = AttentionProfile(quiet_enabled=False)
    object.__setattr__(profile, "quiet_enabled", True)
    object.__setattr__(profile, "quiet_start_hour", 0)
    object.__setattr__(profile, "quiet_end_hour", 0)
    decision = evaluate_timing(candidate(), profile, AttentionState(), now=NIGHT)
    assert decision.verdict is DeliveryVerdict.SEND
    assert decision.reason_code == "quiet_window_unsatisfiable"


# ── policy ────────────────────────────────────────────────────────────────────────────
def test_policy_answers_with_the_widest_blast_radius_first():
    """An org on a compliance hold is a stronger fact than one person's preference, so the
    reason code names the real cause rather than whichever rule was evaluated earliest."""
    everything_wrong = DeliveryPolicy(delivery_enabled=False, channel_enabled=False,
                                      recipient_active=False, recipient_opted_out=True)
    decision = evaluate_policy(candidate(), everything_wrong, now=NIGHT)
    assert decision.reason_code == "org_delivery_disabled"


@pytest.mark.parametrize("policy,expected", [
    (DeliveryPolicy(delivery_enabled=False), "org_delivery_disabled"),
    (DeliveryPolicy(channel_enabled=False), "channel_inactive"),
    (DeliveryPolicy(channel_min_band="critical"), "below_channel_min_band"),
    (DeliveryPolicy(recipient_active=False), "recipient_inactive"),
    (DeliveryPolicy(recipient_opted_out=True), "recipient_opted_out"),
])
def test_policy_suppressions_are_terminal_and_named(policy, expected):
    decision = evaluate_policy(candidate(), policy, now=NIGHT)
    assert decision.verdict is DeliveryVerdict.SUPPRESS
    assert decision.reason_code == expected


def test_a_disconnected_channel_is_suppressed_not_retried():
    """A disconnected webhook does not reconnect itself, and retrying it burns the ladder that
    exists for genuinely transient faults."""
    decision = evaluate_policy(candidate(), DeliveryPolicy(channel_enabled=False), now=NIGHT)
    assert decision.verdict is DeliveryVerdict.SUPPRESS
    assert decision.not_before is None


def test_a_hold_with_an_end_is_the_only_deferral_policy_issues():
    monday = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
    held = evaluate_policy(candidate(), DeliveryPolicy(hold_until=monday), now=NIGHT)
    assert held.verdict is DeliveryVerdict.DEFER and held.not_before == monday
    lifted = evaluate_policy(candidate(), DeliveryPolicy(hold_until=NIGHT), now=MORNING)
    assert lifted.verdict is DeliveryVerdict.SEND


def test_a_stop_and_a_pause_cannot_be_held_at_once():
    """Carrying both means neither is legible in the row that explains a blocked delivery."""
    with pytest.raises(ValueError, match="never both"):
        DeliveryPolicy(delivery_enabled=False, hold_until=MORNING)


def test_policy_has_no_daily_cap_because_the_router_already_owns_one():
    """The pack's ``budget_per_user_day`` is enforced in deliver/router.py. A second daily dial
    here would be a second answer to one question — and the failure mode is not double-blocking,
    it is a support engineer finding one limit, changing it, and nothing happening."""
    from genios_engine.deliver import router
    assert hasattr(router, "budget_full")           # the dial lives there, and only there
    fields = set(DeliveryPolicy.__dataclass_fields__) | set(AttentionProfile.__dataclass_fields__)
    assert not any("day" in name or "budget" in name or "quota" in name for name in fields)


# ── the gate: resolution ──────────────────────────────────────────────────────────────
def test_preferences_resolve_field_by_field_not_row_by_row():
    """A person who sets only their timezone must not thereby discard their tenant's quiet
    hours — which is exactly what picking a winning *row* would do."""
    resolved = resolve_preferences([
        {"org_id": "org_1", "seat_id": "*", "channel": "*", "tz_name": "UTC",
         "quiet_start_hour": 22, "max_interrupts_per_hour": 5},
        {"org_id": "org_1", "seat_id": "seat_1", "channel": "*", "tz_name": "Asia/Kolkata",
         "quiet_start_hour": None, "max_interrupts_per_hour": None},
    ], "seat_1", "slack")
    assert resolved["tz_name"] == "Asia/Kolkata"
    assert resolved["quiet_start_hour"] == 22
    assert resolved["max_interrupts_per_hour"] == 5
    assert "org_id" not in resolved and "seat_id" not in resolved


def test_a_persons_own_setting_outranks_an_org_wide_rule_about_a_channel():
    """The seat is a statement about a human, the channel is a statement about a pipe."""
    resolved = resolve_preferences([
        {"seat_id": "*", "channel": "slack", "quiet_enabled": True},
        {"seat_id": "seat_1", "channel": "*", "quiet_enabled": False},
    ], "seat_1", "slack")
    assert resolved["quiet_enabled"] is False


def test_a_false_setting_is_an_opinion_and_only_null_inherits():
    resolved = resolve_preferences([
        {"seat_id": "*", "channel": "*", "opted_out": True},
        {"seat_id": "seat_1", "channel": "slack", "opted_out": False},
    ], "seat_1", "slack")
    assert resolved["opted_out"] is False


def test_one_tenants_typo_cannot_stop_another_tenants_mail():
    """Every fallback is the *protective* default rather than the permissive one: a broken
    timezone falls back to UTC quiet hours, not to no quiet hours."""
    context = build_context(
        {"tz_name": "Amercia/New_York", "quiet_start_hour": 99, "min_band": "urgent",
         "max_interrupts_per_hour": 0, "opted_out": "probably", "quiet_weekends": 7},
        channel_enabled=True, recipient_active=True)
    assert context.profile.timezone == "UTC"
    assert context.profile.quiet_enabled is True
    assert context.policy.channel_min_band == "standard"
    assert context.policy.recipient_opted_out is False
    for field in ("tz_name", "quiet_start_hour", "min_band", "max_interrupts_per_hour",
                  "opted_out", "quiet_weekends"):
        assert field in context.config_error
    assert evaluate_delivery(candidate(), context, now=NIGHT).verdict is DeliveryVerdict.DEFER


def test_an_ambiguous_quiet_window_falls_back_to_the_protective_default_not_to_silence():
    context = build_context({"quiet_start_hour": 9, "quiet_end_hour": 9},
                            channel_enabled=True, recipient_active=True)
    assert (context.profile.quiet_start_hour, context.profile.quiet_end_hour) == (21, 8)
    assert context.profile.quiet_enabled is True
    assert "quiet_start_hour" in context.config_error


def test_a_row_carrying_both_a_stop_and_a_pause_resolves_to_the_stop():
    """Ambiguity in this layer resolves toward silence, never toward noise."""
    context = build_context({"delivery_enabled": False, "hold_until": MORNING},
                            channel_enabled=True, recipient_active=True)
    assert context.policy.delivery_enabled is False
    assert context.policy.hold_until is None
    assert "hold_until" in context.config_error


def test_an_unconfigured_tenant_is_quiet_at_night_and_useful_in_the_morning():
    """The asymmetry that makes the defaults right: protective timing, permissive policy.
    Silence by default would be indistinguishable from the product being broken."""
    context = build_context({}, channel_enabled=True, recipient_active=True)
    assert evaluate_delivery(candidate(), context, now=NIGHT).verdict is DeliveryVerdict.DEFER
    assert evaluate_delivery(candidate(), context, now=MORNING).verdict is DeliveryVerdict.SEND
    assert context.config_error is None


# ── the gate: composition ─────────────────────────────────────────────────────────────
def test_an_opt_out_at_three_am_is_explained_by_the_opt_out_not_by_the_clock():
    """Computing a humane window for a message that will never be sent would put "quiet_hours"
    in the row and send an operator looking at a clock that was never the problem."""
    context = build_context({"opted_out": True}, channel_enabled=True, recipient_active=True)
    decision = evaluate_delivery(candidate(), context, now=NIGHT)
    assert decision.verdict is DeliveryVerdict.SUPPRESS
    assert (decision.unit, decision.reason_code) == ("policy", "recipient_opted_out")


def test_a_successful_send_records_why_it_was_allowed_to_interrupt():
    """``override_band_critical`` in the row is what tells a reviewer that something
    deliberately broke through quiet hours. ``policy:permitted`` would say only that nothing
    objected, which is the less useful half of the answer."""
    context = build_context({}, channel_enabled=True, recipient_active=True)
    decision = evaluate_delivery(candidate(band="critical", interrupt=True), context, now=NIGHT)
    assert decision.verdict is DeliveryVerdict.SEND
    assert (decision.unit, decision.reason_code) == ("timing", "override_band_critical")


def test_an_org_hold_that_outlasts_quiet_hours_is_the_binding_window():
    monday = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
    context = build_context({"hold_until": monday}, channel_enabled=True, recipient_active=True)
    decision = evaluate_delivery(candidate(), context, now=NIGHT)
    assert decision.verdict is DeliveryVerdict.DEFER
    assert decision.not_before == monday


def test_a_window_that_already_opened_can_never_make_a_row_due_immediately():
    stale = DeliveryDecision.defer("timing", "recipient_busy", NIGHT - timedelta(hours=3))
    assert defer_until(stale, NIGHT) == NIGHT + timedelta(minutes=1)
    real = DeliveryDecision.defer("policy", "org_delivery_held", MORNING)
    assert defer_until(real, NIGHT) == MORNING


# ── the gate: the delivery object on the row ──────────────────────────────────────────
def test_an_unreadable_row_fails_safe_rather_than_open_or_loud():
    """A raise would take the whole drain down; a shrug would page somebody at 03:00. So an
    unrecognised channel class becomes CHAT (assumed able to wake someone, and gated), and an
    unreadable band becomes 'standard' (which cannot break glass)."""
    coerced = candidate_from_row({"org_id": "org_1", "card_id": "card_1", "channel": "slack",
                                  "channel_class": "carrier_pigeon", "band": "apocalyptic",
                                  "interrupt": 1, "recipient": "   "})
    assert coerced.channel_class is ChannelClass.CHAT and coerced.intrusive is True
    assert coerced.band == "standard"
    assert coerced.recipient is None
    assert coerced.at_least("critical") is False


def test_the_chat_channel_list_is_layer_fives_so_a_new_adapter_lands_in_both_layers():
    from genios_engine.executive.communication import CHAT_CHANNELS
    for name in CHAT_CHANNELS:
        assert channel_class_for(name) is ChannelClass.CHAT
    assert channel_class_for("carrier_pigeon") is ChannelClass.IN_APP


def test_the_card_path_and_layer_five_share_one_interrupt_dial():
    """The card push never builds a CommunicationPlan but still has to mark whether it may break
    glass. Both paths ask the same predicate, so a tenant who says "too noisy" turns it down
    once and both go quiet."""
    from genios_engine.executive.communication import DEFAULTS, may_interrupt
    floor = int(DEFAULTS["interrupt_min_confidence_bp"])
    assert may_interrupt("critical", floor) is True
    assert may_interrupt("critical", floor - 1) is False
    assert may_interrupt("high", 10_000) is False
    assert may_interrupt("critical", floor, {"interrupt_band": "critical",
                                             "interrupt_min_confidence_bp": 9_900}) is False


def test_a_card_with_no_recorded_confidence_cannot_break_glass():
    """An unmeasured conclusion is not a confident one, and the cost of being wrong is sleep."""
    from genios_engine.deliver.outbox import card_confidence_bp
    assert card_confidence_bp(None) == 0
    assert card_confidence_bp("not json") == 0
    assert card_confidence_bp({}) == 0
    assert card_confidence_bp({"C": "nan-ish"}) == 0
    assert card_confidence_bp({"C": 72}) == 7_200
    assert card_confidence_bp('{"C": 72}') == 7_200


# ── the gate: reading live state ──────────────────────────────────────────────────────
class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Answers the gate's four reads by SQL substring; records what it was asked."""

    def __init__(self, *, preferences=(), channel_active=True, seat_active=True,
                 burst=(0, None)):
        self.preferences = list(preferences)
        self.channel_active = channel_active
        self.seat_active = seat_active
        self.burst = burst
        self.seen: list[str] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.seen.append(sql)
        if "from delivery_preferences" in sql:
            seat, channel = params["seat"], params["ch"]
            return _Result([row for row in self.preferences
                            if row.get("seat_id") in (seat, "*")
                            and row.get("channel") in (channel, "*")])
        if "from org_channels" in sql:
            return _Result([{"one": 1}] if self.channel_active else [])
        if "from org_seats" in sql:
            return _Result([{"one": 1}] if self.seat_active else [])
        if "from delivery_outbox" in sql:
            sent, oldest = self.burst
            return _Result([{"sent": sent, "oldest": oldest}])
        raise AssertionError(f"unexpected query: {sql}")


def test_an_org_surface_is_governed_by_the_tenants_own_quiet_hours():
    """A shared webhook has no single owner, so the wildcard row is the honest answer — and it
    makes the burst limiter count the shared channel as one stream for free."""
    conn = _FakeConn(preferences=[{"seat_id": "*", "channel": "*", "tz_name": "Asia/Kolkata"}])
    resolver = PgDeliveryContext(conn)
    digest = candidate(recipient=None, channel_class=ChannelClass.DIGEST, band="standard")
    context = resolver.resolve(digest, now=NIGHT)
    assert context.profile.timezone == "Asia/Kolkata"
    # No seat means no seat to be deactivated — asking org_seats for '*' would find nothing and
    # suppress every card the tenant has.
    assert context.policy.recipient_active is True
    assert not any("from org_seats" in sql for sql in conn.seen)


def test_a_deactivated_seat_suppresses_the_push_without_reassigning_it():
    """Choosing a different person at delivery time would invent an owner the commitment never
    had. The commitment stays live and visible on the card surface; only this push stops."""
    resolver = PgDeliveryContext(_FakeConn(seat_active=False))
    context = resolver.resolve(candidate(), now=MORNING)
    decision = evaluate_delivery(candidate(), context, now=MORNING)
    assert decision.verdict is DeliveryVerdict.SUPPRESS
    assert decision.reason_code == "recipient_inactive"


def test_an_unregistered_channel_suppresses_rather_than_burning_the_retry_ladder():
    resolver = PgDeliveryContext(_FakeConn(channel_active=False))
    context = resolver.resolve(candidate(), now=MORNING)
    assert evaluate_delivery(candidate(), context,
                             now=MORNING).reason_code == "channel_inactive"


def test_settings_and_burst_are_re_read_so_mid_batch_consent_changes_take_effect():
    """Ten intrusive messages coming due together against a limit of three must send three and
    hold seven. A memoised count would read "0 delivered this hour" ten times and let every one
    of them through — the exact flood the limiter exists to prevent."""
    conn = _FakeConn(preferences=[{"seat_id": "*", "channel": "*", "quiet_enabled": False,
                                   "max_interrupts_per_hour": 3}])
    resolver = PgDeliveryContext(conn)
    subject = candidate()

    sent = 0
    for _ in range(10):
        context = resolver.resolve(subject, now=MORNING)
        decision = evaluate_delivery(subject, context, now=MORNING)
        if decision.verdict is DeliveryVerdict.SEND:
            sent += 1
            # Model the commit `_finish` performs before the next candidate resolves. The
            # resolver must observe this live count rather than maintain a second local count.
            conn.burst = (sent, MORNING)
    assert sent == 3

    settings_reads = [sql for sql in conn.seen if "from delivery_preferences" in sql]
    burst_reads = [sql for sql in conn.seen if "from delivery_outbox" in sql]
    assert len(settings_reads) == 10
    assert len(burst_reads) == 10


def test_a_committed_delivery_is_counted_exactly_once():
    """The fresh database read already includes this pass's committed sends. Keeping a second
    in-memory counter would double-count each one and hold the third message after only two."""
    resolver = PgDeliveryContext(_FakeConn(burst=(1, MORNING)))
    context = resolver.resolve(candidate(), now=MORNING)
    assert context.state.interrupts_last_hour == 1


def test_shared_chat_burst_is_org_wide_while_private_surfaces_remain_recipient_scoped():
    """One Slack/Teams incoming webhook is shared attention, regardless of logical recipient."""
    conn = _FakeConn()
    resolver = PgDeliveryContext(conn)
    resolver.resolve(candidate(recipient=None), now=MORNING)
    burst = next(sql for sql in conn.seen if "from delivery_outbox" in sql)
    assert "channel = any(:shared_channels)" in burst
    conn.seen.clear()
    resolver.resolve(candidate(channel="email", channel_class=ChannelClass.EMAIL,
                               recipient="seat_2"), now=MORNING)
    assert "recipient = :r" in next(sql for sql in conn.seen if "from delivery_outbox" in sql)


# ── the wiring: what the drain does with a verdict ────────────────────────────────────
class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _DrainConn:
    def __init__(self, log: list, burst_conn: _FakeConn | None = None):
        self.log = log
        self.burst_conn = burst_conn
        self.active = False

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.log.append((sql, dict(params or {})))
        if self.burst_conn is not None and (
                "from delivery_preferences" in sql or "select 1 from org_channels" in sql
                or "from org_seats" in sql or "from delivery_presence" in sql
                or "count(*) as sent" in sql):
            return self.burst_conn.execute(statement, params)
        if (self.burst_conn is not None and sql.startswith("update delivery_outbox")
                and "status='delivered'" in sql):
            sent, oldest = self.burst_conn.burst
            delivered_at = (params or {}).get("t")
            self.burst_conn.burst = (sent + 1, oldest or delivered_at)
        if "from org_channels" in sql:
            return _Result([_Row(config={"webhook_url": "https://example.invalid/hook"})])
        if "from feature_flags" in sql:
            return _Result([_Row(enabled=True)])
        if "from orgs" in sql:
            return _Result([_Row(id="org_1")])
        if "from cards k join signals s" in sql:
            return _Result([_Row(one=1)])
        return _Result([])

    def __enter__(self):
        self.active = True
        return self

    def __exit__(self, *exc):
        self.active = False
        return False


class _DrainEngine:
    """Records every statement the drain issues, so the shape of an update is assertable."""

    def __init__(self, burst_conn: _FakeConn | None = None):
        self.log: list = []
        self.burst_conn = burst_conn

    def begin(self):
        return _DrainConn(self.log, self.burst_conn)

    def connect(self):
        return _DrainConn(self.log, self.burst_conn)

    def updates(self) -> list[tuple[str, dict]]:
        return [(sql, p) for sql, p in self.log if sql.startswith("update delivery_outbox")]


class _Sent:
    ok = True
    detail = ""


class _Adapter:
    def __init__(self):
        self.calls = []

    def send(self, payload, cfg):
        self.calls.append((payload, cfg))
        return _Sent()


def outbox_row(**over) -> dict:
    row = {"id": "ob_1", "org_id": "org_1", "card_id": "card_1", "channel": "slack",
           "payload": {"text": "hello"}, "attempts": 0, "signal_id": "sig_1",
           "reasoning_run_id": "run_1", "reasoning_decision_hash": "dec_1",
           "authority_pack_revision": "rev_1", "authority_expires_at": MORNING,
           "recipient": "seat_1", "band": "high", "channel_class": "chat",
           "interrupt": False, "defer_count": 0}
    row.update(over)
    return row


def run_drain(monkeypatch, rows, *, now, preferences=(), burst=(0, None), gate=None):
    from genios_engine.deliver import outbox as outbox_module

    adapter = _Adapter()
    monkeypatch.setattr(outbox_module, "get_channel", lambda name: adapter)
    burst_conn = None
    if gate is None:
        burst_conn = _FakeConn(preferences=preferences, burst=burst)
        gate = PgDeliveryContext(burst_conn)
    else:
        burst_conn = getattr(gate, "_conn", None)
    engine = _DrainEngine(burst_conn)
    out = {"delivered": 0, "retried": 0, "terminal": 0, "cancelled": 0,
           "deferred": 0, "suppressed": 0}
    outbox_module._drain_claimed(engine, list(rows), gate, now, out)
    return out, engine, adapter


def test_a_quiet_hours_hold_moves_the_clock_and_spends_nothing_else(monkeypatch):
    """The single most important statement in this layer. A hold that consumed an `attempts`
    slot would spend the whole backoff ladder overnight and mark the message failed_terminal at
    05:00 — turning the politeness feature into a delivery-loss bug."""
    out, engine, adapter = run_drain(monkeypatch, [outbox_row()], now=NIGHT)

    assert out["deferred"] == 1 and out["delivered"] == 0
    assert adapter.calls == []                       # nothing left the building

    (sql, params), = engine.updates()
    assignments, _, guard = sql.partition(" where ")
    assert "defer_count=defer_count+1" in assignments
    assert "attempts" not in assignments              # a hold is not a failure
    assert "status=" not in assignments               # the row stays queued
    assert "last_error" not in assignments            # nothing went wrong
    assert "status='queued'" in guard                 # …but only a queued row may be held
    assert params["na"] == datetime(2026, 8, 7, 8, 0, tzinfo=timezone.utc)
    assert (params["u"], params["r"]) == ("timing", "quiet_hours")


def test_the_gate_is_asked_before_the_authority_check_that_takes_locks(monkeypatch):
    """The authority query holds `for share` locks across an outbound POST. Discovering the
    recipient is asleep is local and free, so it is asked first."""
    _out, engine, _adapter = run_drain(monkeypatch, [outbox_row()], now=NIGHT)
    assert not any("from cards k join signals s" in sql for sql, _ in engine.log)
    assert not any("graph_version" in sql for sql, _ in engine.log)


def test_a_deferral_is_repeatable_forever_without_ever_becoming_terminal(monkeypatch):
    from genios_engine.deliver.outbox import BACKOFF_MINUTES

    row = outbox_row()
    for tick in range(len(BACKOFF_MINUTES) + 6):
        out, engine, adapter = run_drain(monkeypatch, [row], now=NIGHT)
        assert (out["deferred"], out["terminal"], out["retried"]) == (1, 0, 0), tick
        assert adapter.calls == []
        row = {**row, "defer_count": row["defer_count"] + 1}
    assert row["attempts"] == 0


def test_an_opt_out_is_suppressed_and_that_is_not_the_same_row_as_a_cancellation(monkeypatch):
    """Cancelled means the subject stopped being live; suppressed means this person said no.
    Three fixes, three statuses — an operator seeing `suppressed` should look at preferences,
    not at Slack's status page."""
    out, engine, adapter = run_drain(
        monkeypatch, [outbox_row()], now=MORNING,
        preferences=[{"seat_id": "seat_1", "channel": "slack", "opted_out": True}])

    assert out["suppressed"] == 1 and out["cancelled"] == 0 and out["terminal"] == 0
    assert adapter.calls == []
    (sql, params), = engine.updates()
    assert "status='suppressed'" in sql and "cancelled" not in sql
    assert (params["u"], params["r"]) == ("policy", "recipient_opted_out")
    assert params["e"] == "policy:recipient_opted_out"   # legible to existing last_error queries


def test_a_permitted_message_still_takes_the_authority_path_and_sends(monkeypatch):
    out, engine, adapter = run_drain(monkeypatch, [outbox_row()], now=MORNING)
    assert out["delivered"] == 1 and out["deferred"] == 0
    assert len(adapter.calls) == 1
    assert any("from cards k join signals s" in sql for sql, _ in engine.log)


def test_a_successful_executive_send_confirms_delivery_on_the_commitment(monkeypatch):
    from genios_engine.deliver import outbox as outbox_module

    confirmed = []
    monkeypatch.setattr(outbox_module, "executive_delivery_is_live",
                        lambda *args, **kwargs: True)
    monkeypatch.setattr(outbox_module, "mark_executive_delivered",
                        lambda conn, org_id, card_id, **kwargs:
                        confirmed.append((org_id, card_id, kwargs)) or True)

    row = outbox_row(card_id="exec:exec_1:exev_1")
    out, _engine, adapter = run_drain(monkeypatch, [row], now=MORNING)

    assert out["delivered"] == 1 and len(adapter.calls) == 1
    assert confirmed == [("org_1", "exec:exec_1:exev_1",
                          {"at": MORNING, "channel": "slack"})]


def test_a_stale_execution_hash_is_classified_before_authority_connection_closes(monkeypatch):
    from genios_engine.deliver import outbox as outbox_module

    calls = []

    def live(conn, *_args, **kwargs):
        assert conn.active, "authority query reused a closed transaction connection"
        calls.append(kwargs.get("expected_route") is not None)
        return kwargs.get("expected_route") is None  # exact route stale; commitment still live

    monkeypatch.setattr(outbox_module, "executive_delivery_is_live", live)
    row = outbox_row(card_id="exec:exec_1:exev_1", execution_hash="old_hash")
    _out, engine, adapter = run_drain(monkeypatch, [row], now=MORNING)

    assert calls == [True, False]
    assert adapter.calls == []
    assert any("awaiting route refresh" in str(params.get("e"))
               for _sql, params in engine.log)


def test_opt_out_committed_between_initial_gate_and_send_is_rechecked(monkeypatch):
    class _ConsentFlip(_FakeConn):
        reads = 0

        def execute(self, statement, params=None):
            sql = str(statement)
            if "from delivery_preferences" in sql:
                self.reads += 1
                return _Result([] if self.reads == 1 else [
                    {"seat_id": "seat_1", "channel": "slack", "opted_out": True}])
            return super().execute(statement, params)

    state = _ConsentFlip()
    out, _engine, adapter = run_drain(
        monkeypatch, [outbox_row()], now=MORNING, gate=PgDeliveryContext(state))
    assert state.reads == 2
    assert out["suppressed"] == 1 and out["delivered"] == 0
    assert adapter.calls == []


def test_workspace_pause_after_claim_defers_instead_of_cancelling_valid_work(monkeypatch):
    from genios_engine.deliver import outbox as outbox_module

    monkeypatch.setattr(outbox_module, "executive_delivery_is_live",
                        lambda *_args, **_kwargs: False)
    monkeypatch.setattr(outbox_module, "_tenant_delivery_live",
                        lambda *_args, **_kwargs: False)
    row = outbox_row(card_id="exec:exec_1:exev_1", execution_hash="hash")
    out, engine, adapter = run_drain(monkeypatch, [row], now=MORNING)
    assert adapter.calls == [] and out["cancelled"] == 0
    assert any("awaiting resume" in str(params.get("e")) for _sql, params in engine.log)
    assert not any("status='cancelled'" in sql for sql, _params in engine.log)


def test_a_burst_arriving_at_once_sends_the_limit_and_holds_the_rest(monkeypatch):
    """Five messages come due in the same pass against a limit of three. Without the in-pass
    counter every one of them would read "0 delivered this hour" and go out together."""
    rows = [outbox_row(id=f"ob_{n}", card_id=f"card_{n}") for n in range(5)]
    out, _engine, adapter = run_drain(
        monkeypatch, rows, now=MORNING,
        preferences=[{"seat_id": "*", "channel": "*", "quiet_enabled": False,
                      "max_interrupts_per_hour": 3}])
    assert out["delivered"] == 3
    assert out["deferred"] == 2
    assert len(adapter.calls) == 3


def test_a_digest_goes_out_at_three_am_while_a_card_to_the_same_org_waits(monkeypatch):
    """The whole point of keying on channel physics: nobody was ever going to be woken by a
    digest, and the card that would wake them waits for morning."""
    rows = [outbox_row(id="ob_d", card_id="digest:2026-08-07", channel_class="digest",
                       band="standard", recipient=None),
            outbox_row(id="ob_c", card_id="card_1")]
    out, _engine, _adapter = run_drain(monkeypatch, rows, now=NIGHT)
    assert out["deferred"] == 1
    assert out["delivered"] + out["retried"] + out["terminal"] == 1


# ── schema conformance ────────────────────────────────────────────────────────────────
def _migration_sql() -> str:
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "migrations"
    return "\n".join(path.read_text() for path in sorted(root.glob("*.sql")))


def test_every_preference_the_gate_reads_is_a_column_that_exists():
    """The failure this locks is silent: rename a column and `preferences.get(...)` returns None
    everywhere, the gate falls back to its defaults, and a tenant who set quiet hours watches
    nothing change with no error anywhere. Derived from the source rather than restated, so the
    list cannot drift out of date."""
    import inspect
    import re

    from genios_engine.deliver import gate

    read = set(re.findall(r'preferences\.get\("([a-z_]+)"\)',
                          inspect.getsource(gate.build_context)))
    assert read, "build_context stopped reading preferences by name — update this lock"

    sql = _migration_sql()
    body = sql.split("create table if not exists delivery_preferences (")[1].split("\n);")[0]
    columns = set(re.findall(r"^\s{4}([a-z_]+)\s", body, re.MULTILINE))
    assert read <= columns, f"gate reads columns that do not exist: {sorted(read - columns)}"


def test_every_delivery_object_column_the_outbox_writes_exists():
    sql = _migration_sql()
    for column in ("recipient", "band", "channel_class", "interrupt", "defer_count",
                   "gate_unit", "gate_reason"):
        assert f"alter table delivery_outbox add column if not exists {column} " in sql


def test_the_wildcard_sentinel_is_the_schemas_default_not_just_the_readers_convention():
    """NULLs in a primary key never compare equal, which would let two org-wide default rows
    coexist and make resolution depend on physical row order."""
    from genios_engine.deliver.gate import WILDCARD

    sql = _migration_sql()
    body = sql.split("create table if not exists delivery_preferences (")[1].split("\n);")[0]
    assert f"seat_id                 text not null default '{WILDCARD}'" in body
    assert f"channel                 text not null default '{WILDCARD}'" in body
    assert "primary key (org_id, seat_id, channel)" in body


def test_suppressed_is_a_documented_status_distinct_from_cancelled():
    import inspect

    from genios_engine.deliver import outbox

    assert "SUPPRESSED IS NOT CANCELLED" in _migration_sql()
    assert "status='suppressed'" in inspect.getsource(outbox._suppress)
    assert "status='cancelled'" in inspect.getsource(outbox._cancel)
    assert "status='failed_terminal'" in inspect.getsource(outbox._finish)


def test_the_resolver_does_not_hold_a_snapshot_across_an_outbound_call():
    """A connection left `idle in transaction` while Slack answers holds a snapshot and blocks
    vacuum; it also hides deliveries this pass just committed from the next burst read."""
    class _CountingConn(_FakeConn):
        rollbacks = 0

        def rollback(self):
            type(self).rollbacks += 1

    conn = _CountingConn()
    resolver = PgDeliveryContext(conn)
    resolver.resolve(candidate(), now=MORNING)
    resolver.resolve(candidate(), now=MORNING)
    assert _CountingConn.rollbacks == 2


def test_a_reader_with_no_transaction_still_works():
    """The injected reader is a Protocol, not a SQLAlchemy Connection."""
    resolver = PgDeliveryContext(_FakeConn())
    assert resolver.resolve(candidate(), now=MORNING).policy.delivery_enabled is True


# ── the three fixes ───────────────────────────────────────────────────────────────────
def test_a_tenant_who_tightens_their_pack_quiets_their_cards_too():
    """The card path never builds a CommunicationPlan, so it used to fall back to the engine
    defaults — meaning `interrupt_band` governed a tenant's commitments and not their cards.
    It now reads the same config snapshot the card was authorised under, so the dial is one."""
    from genios_engine.deliver.outbox import communication_config
    from genios_engine.executive.communication import may_interrupt

    default_pack = communication_config(None)
    assert default_pack == {}                                  # untuned = engine defaults
    assert may_interrupt("critical", 9_000, default_pack) is True

    # A tenant who says "only wake me for things you are nearly certain about".
    strict = {"scoring": {"execution": {"communication": {
        "interrupt_min_confidence_bp": 9_500}}}}
    assert communication_config(strict) == {"interrupt_min_confidence_bp": 9_500}
    assert may_interrupt("critical", 9_000, communication_config(strict)) is False
    # …and the same config arriving as a jsonb string rather than a dict.
    import json
    assert communication_config(json.dumps(strict)) == {"interrupt_min_confidence_bp": 9_500}
    assert communication_config("not json at all") == {}


def test_the_card_enqueue_reads_the_snapshot_the_card_was_authorised_under():
    """Not the *current* pack config. A tenant who tightens the dial while a card is queued must
    not have that card re-judged by a rule its band was never cut by."""
    import inspect

    from genios_engine.deliver import outbox

    source = inspect.getsource(outbox.enqueue_pending)
    assert "authority_cfg.effective as effective_config" in source
    assert "communication_config(r.effective_config)" in source


def test_a_message_that_woke_somebody_records_who_authorised_it(monkeypatch):
    """"Who let this through at 2am?" is a question that gets asked, and the row has to answer
    it. Before this, a row deferred overnight kept its stale `quiet_hours` reason after it
    finally sent."""
    row = outbox_row(band="critical", interrupt=True, defer_count=3)
    out, engine, adapter = run_drain(monkeypatch, [row], now=NIGHT)

    assert out["delivered"] == 1 and len(adapter.calls) == 1
    (sql, params), = engine.updates()
    assert "status='delivered'" in sql and "gate_unit=:u" in sql
    assert (params["u"], params["r"]) == ("timing", "override_band_critical")


def test_a_routine_send_records_the_reason_it_was_admitted(monkeypatch):
    _out, engine, _adapter = run_drain(monkeypatch, [outbox_row()], now=MORNING)
    (sql, params), = engine.updates()
    assert params["r"] == "within_attention_window"


class _BrokenGate:
    """A resolver whose reads fail — a missing column, a dead replica, a blipped lookup."""

    def resolve(self, candidate, *, now):
        raise RuntimeError("relation \"delivery_preferences\" does not exist")


def test_a_gate_that_cannot_read_never_decides_by_accident(monkeypatch):
    """Sending anyway would page somebody at 03:00 on the strength of a failed query; dropping
    the row would lose a message because a lookup blipped. So it takes the existing bounded
    ladder: the message survives, nothing goes out un-judged."""
    out, engine, adapter = run_drain(monkeypatch, [outbox_row()], now=NIGHT,
                                     gate=_BrokenGate())

    assert adapter.calls == []                      # nothing sent un-judged
    assert out["retried"] == 1
    assert out["delivered"] == out["suppressed"] == out["deferred"] == 0
    (sql, params), = engine.updates()
    assert "attempts=attempts+1" in sql             # a real fault, so it does spend a retry
    assert "delivery gate unavailable" in params["e"]


def test_a_gate_that_stays_broken_ends_terminal_rather_than_silently(monkeypatch):
    from genios_engine.deliver.outbox import BACKOFF_MINUTES

    exhausted = outbox_row(attempts=len(BACKOFF_MINUTES))
    out, engine, _adapter = run_drain(monkeypatch, [exhausted], now=NIGHT, gate=_BrokenGate())
    assert out["terminal"] == 1
    (sql, _params), = engine.updates()
    assert "status='failed_terminal'" in sql


def test_one_tenants_broken_gate_does_not_stop_the_pass_draining(monkeypatch):
    """Caught per row on purpose. A gate failure that escaped would take every other tenant's
    queued message down with it."""
    class _BrokenForOne(PgDeliveryContext):
        def resolve(self, candidate, *, now):
            if candidate.org_id == "org_bad":
                raise RuntimeError("boom")
            return super().resolve(candidate, now=now)

    rows = [outbox_row(id="ob_bad", org_id="org_bad"),
            outbox_row(id="ob_ok", card_id="card_ok")]
    out, _engine, adapter = run_drain(
        monkeypatch, rows, now=MORNING,
        gate=_BrokenForOne(_FakeConn()))

    assert out["retried"] == 1          # the broken tenant's row waits
    assert out["delivered"] == 1        # …and everyone else's still went
    assert len(adapter.calls) == 1
