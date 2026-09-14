"""Loading an angle is not the point; REFUSING one is.

`patterns/registry.py`'s sentence, and it applies harder here because an angle is the one artefact
in this layer whose cost is paid per tenant per sweep. Every rule below is enforced at
CONSTRUCTION rather than at evaluation, because each alternative fails quietly and expensively:
an angle with no gate does not error, it bills; an enum with no refusal does not error, it
guesses; a band reaching certainty does not error, it outranks a measured fact.

The one that is not a validation at all is the last section. There is no field that makes an angle
required — not a flag defaulting to false, the field does not exist — so nothing downstream can
withhold a situation because a model was unavailable, over budget or unsure. That is this branch's
standing rule expressed as an absence in the schema rather than a sentence in a comment.
"""
import dataclasses

import pytest

from genios_engine.context.angles.contract import (CONFIDENCE_CEILING_BP,
                                                   CONFIDENCE_FLOOR_BP,
                                                   MAX_CALLS_PER_SWEEP, Angle,
                                                   AngleVerdict, CostTier,
                                                   GateSource, UnavailableAngle,
                                                   register, registered, resolve)

VALID = dict(
    angle_id="condition_now_true", version="1.0.0",
    gate=("derived.timeline.condition_review",),
    gate_source=GateSource.FACTS,
    sees=("condition.quote", "condition.stated_at"),
    returns=("met", "not_met", "not_a_condition", "unknowable"),
    refusal="unknowable",
    confidence_band=(2_000, 8_000),
    max_per_sweep=40,
)


def _angle(**over):
    return Angle(**{**VALID, **over})


# ── the gate is the cost control ─────────────────────────────────────────────────────────────

def test_an_angle_with_no_gate_cannot_be_constructed() -> None:
    """Not a cheap angle — an unbounded one. Without a gate the question is asked about every
    subject on every sweep, and that failure arrives as a bill rather than an error."""
    with pytest.raises(UnavailableAngle, match="cost control"):
        _angle(gate=())


def test_a_gate_may_not_contain_a_blank() -> None:
    with pytest.raises(UnavailableAngle, match="blank entry"):
        _angle(gate=("derived.timeline.condition_review", "   "))


# ── what leaves the tenant is named ──────────────────────────────────────────────────────────

def test_an_angle_that_shows_the_model_nothing_cannot_be_constructed() -> None:
    with pytest.raises(UnavailableAngle, match="answer from nothing"):
        _angle(sees=())


def test_the_verdict_records_what_the_model_was_shown() -> None:
    """The audit answer to "on what basis?", and what lets a verdict be re-judged later without
    being re-run."""
    angle = _angle()
    verdict = AngleVerdict.of(angle, subject_ref="n1", verdict="met", confidence_bp=5_000)
    assert verdict.saw == angle.sees


# ── the refusal, which is the rule this system keeps relearning ──────────────────────────────

def test_an_enum_with_no_way_to_say_i_cannot_tell_is_refused() -> None:
    """`met / not_met` forces a guess on every call, because "I cannot tell from this" has nowhere
    to land. `quality/missing.py` spent a module establishing that conflating "no" with
    "unknowable" is how a false finding is born."""
    with pytest.raises(UnavailableAngle, match="forces a guess"):
        _angle(returns=("met", "not_met"), refusal="unknowable")


def test_the_refusal_must_be_one_of_the_answers() -> None:
    with pytest.raises(UnavailableAngle, match="must be one of"):
        _angle(refusal="cannot_say")


def test_a_question_with_one_answer_is_not_a_question() -> None:
    with pytest.raises(UnavailableAngle, match="not a question"):
        _angle(returns=("unknowable",), refusal="unknowable")


def test_refusing_is_recorded_as_a_result_not_a_failure() -> None:
    """An angle whose refusals dominate is asking the wrong question or reading the wrong queue,
    and that is visible only if refusing is recorded. `lifecycle/gate.py` makes the same argument
    for writing down why a call was NOT made."""
    angle = _angle()
    assert AngleVerdict.of(angle, subject_ref="n1", verdict="unknowable",
                           confidence_bp=3_000).refused is True
    assert AngleVerdict.of(angle, subject_ref="n1", verdict="met",
                           confidence_bp=3_000).refused is False


def test_the_refusal_flag_does_not_depend_on_the_registry() -> None:
    """An earlier cut looked this up at read time and fell back to the verdict itself, so every
    verdict of an unregistered angle read as a refusal. `of()` has the angle in hand."""
    unregistered = _angle(angle_id="never_registered")
    verdict = AngleVerdict.of(unregistered, subject_ref="n1", verdict="met", confidence_bp=5_000)
    assert verdict.refused is False


# ── a verdict outside the enum cannot exist ──────────────────────────────────────────────────

def test_free_text_wearing_a_schema_is_refused_at_construction() -> None:
    """The constructor is the enforcement point, not a downstream reader's `if` — the discipline
    `SatisfiedCondition` keeps for its evidence spans. No consumer has to check, and none can
    forget to."""
    with pytest.raises(UnavailableAngle, match="not in its declared returns"):
        AngleVerdict.of(_angle(), subject_ref="n1", verdict="probably met", confidence_bp=5_000)


def test_a_verdict_needs_a_subject_to_be_about() -> None:
    with pytest.raises(UnavailableAngle, match="subject"):
        AngleVerdict.of(_angle(), subject_ref="  ", verdict="met", confidence_bp=5_000)


# ── confidence may never reach certainty ─────────────────────────────────────────────────────

def test_a_band_that_touches_certainty_is_refused() -> None:
    """An angle answers about a queue the deterministic layer could not resolve. A band reaching
    10,000 lets that opinion outrank a measured fact."""
    with pytest.raises(UnavailableAngle, match="must sit inside"):
        _angle(confidence_band=(2_000, 10_000))


def test_a_band_that_starts_at_zero_is_refused() -> None:
    """A model that answered at all has said something."""
    with pytest.raises(UnavailableAngle, match="must sit inside"):
        _angle(confidence_band=(0, 8_000))


def test_an_inverted_band_is_refused() -> None:
    with pytest.raises(UnavailableAngle, match="low < high"):
        _angle(confidence_band=(8_000, 2_000))


@pytest.mark.parametrize("claimed, expected", [(9_999, 8_000), (1, 2_000), (5_000, 5_000)])
def test_an_over_claiming_model_is_bounded_not_discarded(claimed: int, expected: int) -> None:
    """A model returning 9,900 is over-claiming, which is a thing to bound — not a reason to lose
    the verdict it came with."""
    verdict = AngleVerdict.of(_angle(), subject_ref="n1", verdict="met", confidence_bp=claimed)
    assert verdict.confidence_bp == expected


def test_the_engine_bounds_sit_where_the_layer_below_put_them() -> None:
    """`llm_interpretation` bands its own readings 2,000-8,000; these are the outer walls every
    angle must sit inside, not a second opinion about them."""
    assert CONFIDENCE_FLOOR_BP > 0
    assert CONFIDENCE_CEILING_BP < 10_000


# ── every model pass carries a ceiling ───────────────────────────────────────────────────────

@pytest.mark.parametrize("budget", [0, -1, True])
def test_a_pass_with_no_ceiling_is_refused(budget) -> None:
    """Every pass in `runner.py` that grows with a tenant carries one, and the `budgets` ledger
    exists because those ceilings were once computed and thrown away."""
    with pytest.raises(UnavailableAngle, match="positive integer"):
        _angle(max_per_sweep=budget)


def test_an_angle_cannot_raise_the_engine_ceiling_by_declaring_a_bigger_one() -> None:
    with pytest.raises(UnavailableAngle, match="exceeds the engine ceiling"):
        _angle(max_per_sweep=MAX_CALLS_PER_SWEEP + 1)


# ── registration ─────────────────────────────────────────────────────────────────────────────

def test_two_questions_cannot_share_one_id() -> None:
    """Two angles sharing an id is two budgets sharing a ledger and two prompts sharing an audit
    trail — a cost nobody can attribute."""
    register(_angle(angle_id="shared_id"))
    register(_angle(angle_id="shared_id"))          # identical re-registration is a no-op
    with pytest.raises(UnavailableAngle, match="already registered"):
        register(_angle(angle_id="shared_id", max_per_sweep=7))


def test_naming_an_unregistered_angle_fails_loudly() -> None:
    """A caller naming one that does not exist would otherwise ask nothing and report success."""
    with pytest.raises(UnavailableAngle, match="no angle registered"):
        resolve("not_declared_anywhere")


def test_the_report_is_diffable() -> None:
    register(_angle(angle_id="zzz_last"))
    register(_angle(angle_id="aaa_first"))
    ids = [a.angle_id for a in registered()]
    assert ids == sorted(ids)


# ── the absence that is the point ────────────────────────────────────────────────────────────

def test_no_field_can_make_an_angle_required() -> None:
    """THE RULE AS A SHAPE, NOT A SENTENCE. An angle may only ever ADD to what the deterministic
    layer produced. There is no `required`, no `failure_policy`, no `blocking` — so nothing
    downstream can withhold a situation because a model was unavailable, over budget or unsure,
    and adding that power means editing this contract in front of a reviewer.
    """
    fields = {f.name for f in dataclasses.fields(Angle)}
    assert not fields & {"required", "blocking", "failure_policy", "mandatory", "gating"}


def test_an_angle_declares_no_model_and_no_prompt() -> None:
    """An angle says what is asked and what may come back. A model name in a declaration is a
    declaration that must be re-reviewed every time a vendor renames one, and prompt text in a
    schema is a prompt nobody can diff against its own results."""
    fields = {f.name for f in dataclasses.fields(Angle)}
    assert not fields & {"model", "prompt", "temperature", "max_tokens", "system"}
    assert isinstance(_angle().cost_tier, CostTier)


def test_an_angle_must_say_which_queue_its_gate_names() -> None:
    """ADDED WHEN THE STORE WAS WRITTEN, and the schema landing alone is what surfaced it.
    `derived.timeline.condition_review` is a `graph_facts` row and `ball_in_court_unreported` is a
    `context_residue` row; nothing in the declaration said which a gate meant, so the first thing
    that had to EXECUTE one could not. A store inferring it from the string's shape would read the
    wrong table the day somebody names a fact after a residue kind."""
    with pytest.raises(UnavailableAngle, match="not a queue this engine can read"):
        _angle(gate_source="inbox")


def test_the_queue_sources_are_closed_so_the_store_can_match_exhaustively() -> None:
    """A source the store does not implement must be undeclarable, rather than discovered as an
    angle that quietly never fires — the failure `patterns/registry.py` refuses loudly for
    condition kinds."""
    assert {s.value for s in GateSource} == {"facts", "residue"}
