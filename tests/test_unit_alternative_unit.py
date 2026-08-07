"""Executable contract for the Alternative Unit (`core.alternative`).

The unit exists so that a human is handed an option *set* rather than an instruction. These tests
pin the properties that make that set honest:

* **An unscreened roster is not a clean roster.** Nobody having looked is reported, never assumed.
* **A duplicate is not an option.** Two plays that are the same move must not read as a choice.
* **The null option is always on the table** — and its price is never invented, only read.
* **An unpriced silence stays unpriced.** Zero must never stand in for "we did not measure".
* **It counts options; it never orders them.** No adjustment, no check, no candidate leaves it.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CandidateCheck,
    CapabilityManifest,
    CheckOutcome,
    ContextSnapshot,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.alternative_unit import (
    AlternativeUnit,
    DoNothingBaselinePlugin,
    MoveDistinctnessPlugin,
    PlayViabilityPlugin,
)
from genios_engine.reason.unit import UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------------------------
# Fixtures: a real capability, a real snapshot, real prior results
# ---------------------------------------------------------------------------------------------

def _play(play_id: str, *, steps=("Draft a grounded reply",), impact=6_000, success=7_000,
          read_only=True, metadata=None) -> PlayDefinition:
    return PlayDefinition(
        play_id=play_id,
        version="1",
        label=play_id.replace("_", " ").title(),
        steps=tuple(steps),
        impact_bp=impact,
        success_probability_bp=success,
        read_only=read_only,
        metadata=metadata or {},
    )


def _request(*, plays=None, config=None) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.alternative", "1.0.0", config=config or {}),),
        plays=tuple(plays or (_play("restore_momentum"),)),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=17,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts={"deal.status": "open"},
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
        config_snapshot_id="cfg_1",
    )


def _completed(reasoner_id: str, *, checks=(), **metrics) -> ReasonerResult:
    return ReasonerResult(reasoner_id=reasoner_id, reasoner_version="1",
                          status=ResultStatus.COMPLETED, matched=True, metrics=metrics,
                          checks=tuple(checks))


def _check(play_id: str, outcome: CheckOutcome, reason_code: str) -> CandidateCheck:
    return CandidateCheck(play_id=play_id, stage="policy", outcome=outcome,
                          reason_code=reason_code, evaluator_id="core.constraint",
                          evaluator_version="1")


def _view(prior=None, *, plays=None, config=None) -> UnitView:
    request = _request(plays=plays, config=config)
    return UnitView(request=request, spec=request.capability.reasoners[0],
                    prior={item.reasoner_id: item for item in (prior or ())})


def _by_play(observations) -> dict[str, object]:
    return {item.kind.split(":", 1)[1]: item for item in observations}


def _codes(observation) -> set[str]:
    return set(observation.reason_codes)


# ---------------------------------------------------------------------------------------------
# Viability: which plays are genuinely still on the table
# ---------------------------------------------------------------------------------------------

def test_an_unscreened_roster_is_reported_as_unchecked_not_as_clean():
    """Scheduled before any constraint unit, silence about policy is a blind spot, not a pass."""
    view = _view(plays=(_play("reply_to_buyer"), _play("escalate_to_sponsor")))

    observations = PlayViabilityPlugin().contribute(view)

    assert all(int(item.metrics["viable"]) == 1 for item in observations)
    assert all("viability_unscreened" in _codes(item) for item in observations)


def test_an_upstream_elimination_removes_a_play_from_the_option_set():
    """A play blocked on policy is not an alternative, however good its numbers look."""
    view = _view(
        [_completed("core.constraint",
                    checks=(_check("auto_send_reminder", CheckOutcome.ELIMINATE, "read_only_policy"),
                            _check("reply_to_buyer", CheckOutcome.PASS, "read_only_policy_pass")))],
        plays=(_play("auto_send_reminder", read_only=False), _play("reply_to_buyer")))

    observed = _by_play(PlayViabilityPlugin().contribute(view))

    assert int(observed["auto_send_reminder"].metrics["viable"]) == 0
    assert "option_eliminated_upstream" in _codes(observed["auto_send_reminder"])
    # The reason it left the field travels with it, so the option set can be argued with.
    assert "read_only_policy" in _codes(observed["auto_send_reminder"])
    assert int(observed["reply_to_buyer"].metrics["viable"]) == 1
    assert "viability_unscreened" not in _codes(observed["reply_to_buyer"])


def test_a_warning_is_not_an_elimination():
    """Cost and resource units WARN routinely; treating a caution as a block would erase options."""
    view = _view([_completed("core.cost",
                             checks=(_check("reply_to_buyer", CheckOutcome.WARN,
                                            "cost_exceeds_expected_benefit"),))],
                 plays=(_play("reply_to_buyer"),))

    observed = _by_play(PlayViabilityPlugin().contribute(view))

    assert int(observed["reply_to_buyer"].metrics["viable"]) == 1


def test_a_unit_that_did_not_complete_cannot_eliminate_an_option():
    """A crashed screen has no opinion; reading its absence as a block would silently starve
    the option set."""
    view = _view([ReasonerResult("core.constraint", "1", ResultStatus.FAILED,
                                 reason_codes=("reasoner_failure",))],
                 plays=(_play("reply_to_buyer"),))

    observed = _by_play(PlayViabilityPlugin().contribute(view))

    assert int(observed["reply_to_buyer"].metrics["viable"]) == 1
    assert "viability_unscreened" in _codes(observed["reply_to_buyer"])


def test_a_play_worth_almost_nothing_is_not_presented_as_an_option():
    """2000bp impact landing one time in five is a manifest leftover, not something anyone
    would take."""
    view = _view(plays=(_play("long_shot", impact=2_000, success=2_000),))

    observed = _by_play(PlayViabilityPlugin().contribute(view))

    assert observed["long_shot"].metrics["expected_value_bp"] == 400   # 2000 * 2000 / 10000
    assert int(observed["long_shot"].metrics["viable"]) == 0
    assert "option_below_value_floor" in _codes(observed["long_shot"])


def test_a_capability_can_set_its_own_bar_for_what_counts_as_an_option():
    """A capability whose plays are all low-probability should still be able to present them."""
    plays = (_play("long_shot", impact=2_000, success=2_000),)

    permissive = _by_play(PlayViabilityPlugin().contribute(
        _view(plays=plays, config={"viable_value_floor_bp": 100})))

    assert int(permissive["long_shot"].metrics["viable"]) == 1


def test_a_malformed_value_floor_is_a_manifest_fault():
    with pytest.raises(ValueError, match="basis points"):
        PlayViabilityPlugin().contribute(_view(config={"viable_value_floor_bp": 25_000}))


# ---------------------------------------------------------------------------------------------
# Distinctness: two options, or one option twice?
# ---------------------------------------------------------------------------------------------

def test_two_plays_with_the_same_steps_are_one_move():
    """A roster grows duplicates over time; counting entries would report a choice nobody has."""
    view = _view(plays=(_play("reply_now", steps=("Draft a grounded reply",)),
                        _play("send_response", steps=("Draft a grounded reply",))))

    observed = _by_play(MoveDistinctnessPlugin().contribute(view))

    assert observed["reply_now"].metrics["group"] == observed["send_response"].metrics["group"]
    assert observed["reply_now"].metrics["group_size"] == 2
    assert "plays_share_one_move" in _codes(observed["reply_now"])


def test_wording_and_step_order_do_not_make_a_different_move():
    """Rewriting a play's steps is an edit, not a new alternative."""
    view = _view(plays=(
        _play("alpha", steps=("Draft a reply", "Check the contract")),
        _play("beta", steps=("check   THE contract", "  Draft A Reply "))))

    observed = _by_play(MoveDistinctnessPlugin().contribute(view))

    assert observed["alpha"].metrics["group"] == observed["beta"].metrics["group"]


def test_an_irreversible_variant_is_a_genuinely_different_move():
    """Drafting a reply and auto-sending it read the same on paper and differ entirely in
    consequence — the only choice that matters between them must survive."""
    view = _view(plays=(_play("draft_reply", steps=("Send the reply",), read_only=True),
                        _play("auto_send", steps=("Send the reply",), read_only=False)))

    observed = _by_play(MoveDistinctnessPlugin().contribute(view))

    assert observed["draft_reply"].metrics["group"] != observed["auto_send"].metrics["group"]
    assert "play_is_a_distinct_move" in _codes(observed["auto_send"])


def test_a_play_that_reaches_outside_the_org_is_its_own_move():
    view = _view(plays=(
        _play("internal_note", steps=("Share the summary",),
              metadata={"external_recipient_required": False}),
        _play("customer_note", steps=("Share the summary",),
              metadata={"external_recipient_required": True})))

    observed = _by_play(MoveDistinctnessPlugin().contribute(view))

    assert observed["internal_note"].metrics["group"] != observed["customer_note"].metrics["group"]


# ---------------------------------------------------------------------------------------------
# The do-nothing baseline: the option that is always available
# ---------------------------------------------------------------------------------------------

def test_an_unpriced_silence_stays_unpriced():
    """Reporting an unmeasured wait as costing zero would tell a human that delay is free."""
    assert DoNothingBaselinePlugin().contribute(_view()) == ()


def test_a_deployed_cost_unit_owns_the_price_of_inaction():
    """Two numbers for the same silence on one card is a contradiction; defer to the authority."""
    view = _view([_completed("core.cost", do_nothing_cost_bp=6_400),
                  _completed("core.opportunity", opportunity_bp=9_000)])

    observation, = DoNothingBaselinePlugin().contribute(view)

    assert observation.metrics["do_nothing_baseline_bp"] == 6_400
    assert "inaction_priced_upstream" in _codes(observation)


def test_the_strongest_lapsing_signal_leads_and_the_rest_corroborate():
    """Headroom, momentum and exposure are three views of one silence, not three silences."""
    view = _view([_completed("core.opportunity", opportunity_bp=6_000),
                  _completed("core.temporal", drop_bp=4_000),
                  _completed("core.risk", risk_bp=2_000)])

    observation, = DoNothingBaselinePlugin().contribute(view)

    # 6000 leads; (4000 + 2000) / 4 = 1500 of bounded lift
    assert observation.metrics["do_nothing_baseline_bp"] == 7_500
    assert observation.metrics["signal_count"] == 3
    assert _codes(observation) >= {"headroom_lapses", "momentum_decays", "exposure_compounds",
                                   "inaction_has_a_price"}


def test_a_measured_zero_is_not_the_same_as_an_unmeasured_one():
    """'We looked and waiting costs nothing' is a finding; 'nobody looked' is a blind spot."""
    view = _view([_completed("core.opportunity", opportunity_bp=0)])

    observation, = DoNothingBaselinePlugin().contribute(view)

    assert observation.metrics["do_nothing_baseline_bp"] == 0
    assert observation.metrics["signal_count"] == 1
    assert "inaction_appears_costless" in _codes(observation)
    assert "headroom_lapses" not in _codes(observation)


def test_a_capability_may_appoint_its_own_inaction_authority():
    """Substituting a source is configuration, not a code change."""
    view = _view([_completed("sales.pipeline_decay", opportunity_bp=8_000)],
                 config={"headroom_source": "sales.pipeline_decay"})

    observation, = DoNothingBaselinePlugin().contribute(view)

    assert observation.metrics["do_nothing_baseline_bp"] == 8_000


# ---------------------------------------------------------------------------------------------
# The assembled unit
# ---------------------------------------------------------------------------------------------

def test_the_unit_satisfies_the_reasoner_protocol():
    assert isinstance(AlternativeUnit(), Reasoner)


def test_a_single_play_capability_is_reported_as_a_forced_move():
    """One option is not a choice, and a human deserves to be told that before agreeing to it."""
    result = AlternativeUnit().evaluate(_request(), {})

    assert result.status == ResultStatus.COMPLETED
    assert result.matched is False
    assert result.metrics["declared_count"] == 1
    assert result.metrics["viable_count"] == 1
    assert result.metrics["option_count"] == 2          # the one move, plus doing nothing
    assert result.metrics["has_alternative"] == 0
    assert "single_course_of_action" in result.reason_codes
    assert "do_nothing_cost_unknown" in result.reason_codes


def test_duplicated_plays_do_not_manufacture_a_choice():
    """Three entries that are one move must never be delivered as three alternatives."""
    plays = (_play("reply_a", steps=("Draft a grounded reply",)),
             _play("reply_b", steps=("draft a grounded reply",)),
             _play("reply_c", steps=("Draft  a  grounded  reply",)))

    result = AlternativeUnit().evaluate(_request(plays=plays), {})

    assert result.metrics["declared_count"] == 3
    assert result.metrics["viable_count"] == 3
    assert result.metrics["distinct_count"] == 1
    assert result.metrics["duplicate_count"] == 2
    assert result.metrics["has_alternative"] == 0
    assert "false_choice_in_roster" in result.reason_codes


def test_an_option_set_with_nothing_viable_still_reports_the_null_option():
    """Everything blocked is not an empty result — doing nothing remains, and it has a price."""
    plays = (_play("auto_send", read_only=False),)
    prior = {"core.constraint": _completed(
        "core.constraint", checks=(_check("auto_send", CheckOutcome.ELIMINATE, "read_only_policy"),))}

    result = AlternativeUnit().evaluate(_request(plays=plays), prior)

    assert result.metrics["viable_count"] == 0
    assert result.metrics["distinct_count"] == 0
    assert result.metrics["option_count"] == 1          # only the null option survives
    assert result.matched is False
    assert "no_viable_option" in result.reason_codes


def test_the_quiet_renewal_presents_three_real_options_and_the_price_of_silence():
    """A real scenario, end to end.

    A renewal has gone quiet three weeks out. Layer 3 declared five plays. `core.constraint` has
    already eliminated the auto-send on the read-only policy. Two of the survivors — `reply_to_buyer`
    and `reply_to_buyer_v2` — turn out to be the same drafted reply written up twice. `core.opportunity`
    priced the untaken headroom at 6000bp, `core.temporal` the lost momentum at 4000bp, and
    `core.risk` the compounding exposure at 2000bp.

    The honest answer is three genuinely different moves plus the null option, a false choice named
    rather than hidden, and 7500bp on the cost of standing still. Nothing here says which to take.
    """
    plays = (
        _play("accept_partial_scope", steps=("Offer a reduced first phase",),
              impact=5_000, success=6_000),
        _play("auto_send_reminder", steps=("Send the reminder automatically",), read_only=False),
        _play("escalate_to_sponsor", steps=("Draft a note to the economic sponsor",),
              impact=7_000, success=5_000),
        _play("reply_to_buyer", steps=("Draft a grounded reply to the buyer",)),
        _play("reply_to_buyer_v2", steps=("Draft a  Grounded reply TO the buyer",)),
    )
    prior = {item.reasoner_id: item for item in (
        _completed("core.constraint",
                   checks=(_check("auto_send_reminder", CheckOutcome.ELIMINATE, "read_only_policy"),
                           _check("reply_to_buyer", CheckOutcome.PASS, "read_only_policy_pass"))),
        _completed("core.opportunity", opportunity_bp=6_000),
        _completed("core.temporal", drop_bp=4_000),
        _completed("core.risk", risk_bp=2_000),
    )}

    result = AlternativeUnit().evaluate(_request(plays=plays), prior)

    assert result.metrics["declared_count"] == 5
    assert result.metrics["viable_count"] == 4          # the auto-send left on policy
    assert result.metrics["distinct_count"] == 3        # the two replies are one move
    assert result.metrics["duplicate_count"] == 1
    assert result.metrics["option_count"] == 4          # three moves plus doing nothing
    assert result.metrics["has_alternative"] == 1
    assert result.metrics["do_nothing_baseline_bp"] == 7_500
    assert result.matched is True
    assert "genuine_choice_available" in result.reason_codes
    assert "false_choice_in_roster" in result.reason_codes
    # Every option's screening is on the record, including the one that lost.
    assert "alternative.viability:auto_send_reminder" in {
        finding.finding_id for finding in result.findings}
    assert "alternative.option_set" in {finding.finding_id for finding in result.findings}


def test_the_same_situation_reasons_identically_twice():
    """Replayability is the whole promise: no clock, no randomness, no iteration order."""
    plays = (_play("zeta_play", steps=("Draft a grounded reply",)),
             _play("alpha_play", steps=("Draft a grounded reply",)),
             _play("escalate", steps=("Call the sponsor",)))
    prior = {item.reasoner_id: item for item in (
        _completed("core.opportunity", opportunity_bp=5_500),
        _completed("core.temporal", drop_bp=3_300),
    )}
    unit = AlternativeUnit()

    first = unit.evaluate(_request(plays=plays), prior)
    second = unit.evaluate(_request(plays=plays), prior)

    assert dict(first.metrics) == dict(second.metrics)
    assert first.reason_codes == second.reason_codes
    assert first.semantic_hash == second.semantic_hash


def test_the_option_count_does_not_depend_on_the_order_plays_were_authored():
    """Two manifests with the same plays in a different order describe the same choice."""
    forward = (_play("alpha", steps=("Call the sponsor",)),
               _play("zeta", steps=("call THE sponsor",)))
    reversed_order = (forward[1], forward[0])
    unit = AlternativeUnit()

    assert dict(unit.evaluate(_request(plays=forward), {}).metrics) \
        == dict(unit.evaluate(_request(plays=reversed_order), {}).metrics)


# ---------------------------------------------------------------------------------------------
# Boundaries: this unit analyses, it never decides
# ---------------------------------------------------------------------------------------------

def test_the_unit_never_touches_a_candidate():
    """Emitting an adjustment or a check would make it a second decision authority."""
    result = AlternativeUnit().evaluate(
        _request(plays=(_play("reply", steps=("Reply",)), _play("escalate", steps=("Escalate",)))),
        {"core.opportunity": _completed("core.opportunity", opportunity_bp=7_000)})

    assert result.adjustments == ()
    assert result.checks == ()


def test_the_unit_never_publishes_a_reserved_shared_metric():
    """Publishing confidence or urgency from here would silently re-score every decision."""
    published = set(AlternativeUnit().publishes)

    assert published.isdisjoint({"confidence_bp", "urgency_bp", "priority_override_bp"})

    result = AlternativeUnit().evaluate(_request(), {
        "core.confidence": _completed("core.confidence", confidence_bp=9_000),
        "core.temporal": _completed("core.temporal", urgency_bp=8_000, drop_bp=3_000)})

    assert set(result.metrics) <= published


def test_a_choice_being_available_is_not_a_recommendation():
    """`matched` says options exist — it must never be read as 'take one of them'."""
    result = AlternativeUnit().evaluate(
        _request(plays=(_play("reply", steps=("Reply",)), _play("escalate", steps=("Escalate",)))),
        {})

    assert result.matched is True
    assert all(not code.startswith("recommend") for code in result.reason_codes)
    assert all(not code.startswith("select") for code in result.reason_codes)
