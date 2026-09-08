"""K4 · **the voice** — the V-gauntlet, the number mechanism, the fallback, and the 25-bundle review.

    pytest tests/reason/test_bundle_gauntlet.py -q

**What this file is written against.** `intelligence.py`'s explanation validator caps a rendering at
ONE SENTENCE, NO DIRECTIVES, NO NUMBERS. Those three make the founder's card structurally
impossible — WHY THIS MATTERS needs a consequence with a magnitude, ROOT CAUSE needs more than a
clause, RECOMMENDATION needs an instruction, EXPECTED EFFECT needs a quantified projection. The caps
were not relaxed to fix that: the REASON for them was removed (the decision is fixed and typed
before a word exists, every number is substituted by code, every claim is bound to this decision's
own material) and each cap was replaced by something stricter, which is what the first section here
measures one row at a time.

**The golden set is a REPLAY LANE**, the same shape `tests/golden/l2` uses. Every fixture carries the
generation R-2 returned when it was labelled, and more than half are wrong on purpose — so what is
graded is the gauntlet, the substitution and the fallback, never a model's quality on an afternoon.
Each fixture also names WHICH check must catch it, so a fixture that starts failing for a different
reason is a regression rather than a pass.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from genios_engine.contracts.reasoning import (
    BUNDLE_PROSE_FIELDS,
    TEMPLATE_FALLBACK,
    DecisionOutcome,
    ReasoningBundle,
    ReasoningDecision,
    placeholders,
)
from genios_engine.reason import intelligence as INTEL
from genios_engine.reason.bundle import (
    build_catalogue,
    build_grounding,
    build_template,
    run_gauntlet,
    template_bundle,
)
from genios_engine.reason.bundle import gauntlet as G
from genios_engine.reason.bundle.numbers import MAX_CATALOGUE

from .l4_golden import NOW, build, load_golden

GOLDEN = load_golden()
SITUATIONS = GOLDEN["situations"]
FIXTURES = GOLDEN["fixtures"]
GATE = GOLDEN["gate"]


def _material(situation_id: str, eval_time: datetime = NOW):
    decision, results, request = build(SITUATIONS[situation_id], eval_time=eval_time)
    catalogue = build_catalogue(decision, results, eval_time=eval_time)
    grounding = build_grounding(decision, results, request=request)
    return decision, results, request, catalogue, grounding


def _judge(situation_id: str, generation: dict):
    decision, results, request, catalogue, grounding = _material(situation_id)
    return run_gauntlet(generation, decision=decision, catalogue=catalogue, grounding=grounding,
                        citations=decision.citations)


def _clean(situation_id: str) -> dict:
    """The labelled clean generation for a situation, as a fresh mutable copy."""
    for fixture in FIXTURES:
        if fixture["situation"] == situation_id and fixture["expect"]["gauntlet"] == "pass":
            return dict(fixture["model_answer"])
    raise AssertionError(f"no clean fixture for {situation_id}")


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE WALL: the three caps are REUSED where they were doing work and REPLACED where they blocked
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_validator_machinery_is_reused_and_not_forked():
    """Doc 08's retirement table: the one-sentence cap's machinery is REUSED by the gauntlet, not
    deleted. Object identity, so a later copy-paste of the regex turns this red — a fork drifts on
    the first tuning and then two validators disagree about what a directive is."""
    assert G.DIRECTIVE_RE is INTEL._DIRECTIVE_RE
    assert G.ADDRESS_RE is INTEL._ADDRESS_RE
    assert G.EXPLANATION_GLUE is INTEL._EXPLANATION_GLUE


def test_the_no_directives_cap_still_binds_on_every_descriptive_section():
    """It moved; it did not go. A situation summary that instructs is a model choosing an action."""
    for field in G.DESCRIPTIVE_FIELDS:
        generation = _clean("renewal_northwind")
        generation[field] = "The account is exposed, so you should call the economic buyer today."
        report = _judge("renewal_northwind", generation)
        failed = {check.check for check in report.failures}
        assert "V-3" in failed, f"{field} was allowed to instruct"


def test_the_recommendation_is_the_one_section_allowed_to_instruct():
    """The cap is lifted exactly where it made the founder's card impossible, and nowhere else."""
    generation = _clean("renewal_northwind")
    assert G.DIRECTIVE_RE.search(generation[G.DIRECTIVE_FIELD]), (
        "the clean fixture's recommendation does not actually instruct, so this proves nothing")
    assert _judge("renewal_northwind", generation).passed


def test_the_one_sentence_cap_is_replaced_by_grounding_every_sentence():
    """The old check could never look at a second sentence. This one refuses the field if ANY
    sentence rests on nothing — strictly more than the cap could ask."""
    generation = _clean("renewal_northwind")
    generation["situation_summary"] += (
        " Procurement has frozen all discretionary spending until the quarter turns over.")
    report = _judge("renewal_northwind", generation)
    assert not report.passed
    assert "V-1" in {check.check for check in report.failures}


def test_the_no_numbers_cap_is_replaced_by_something_the_old_one_allowed():
    """`intelligence` allowed any number that appeared anywhere in the grounding blob. V-4 allows
    NONE, in digits or in words, and V-5 then refuses a placeholder nobody computed."""
    generation = _clean("renewal_northwind")
    generation["why_it_matters"] = "The renewal is 11 days out and the committee has gone quiet."
    assert "V-4" in {c.check for c in _judge("renewal_northwind", generation).failures}
    generation["why_it_matters"] = (
        "The renewal is eleven days out and the committee has been quiet for fourteen days.")
    assert "V-4" in {c.check for c in _judge("renewal_northwind", generation).failures}


# ═════════════════════════════════════════════════════════════════════════════════════════════
# V-1 … V-7, one row at a time
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_every_check_runs_and_every_outcome_is_recorded_in_order():
    """Doc 05 §4: run in order, record every outcome. A report that only carried failures could
    not tell 'V-2 passed' from 'V-2 never ran', and only one of those means the citations were
    checked."""
    report = _judge("renewal_northwind", _clean("renewal_northwind"))
    assert tuple(check.check for check in report.checks) == G.CHECK_ORDER
    assert all(check.name for check in report.checks)
    assert [row["check"] for row in report.as_records()] == list(G.CHECK_ORDER)


def test_v2_refuses_a_quotation_that_is_not_byte_identical():
    generation = _clean("renewal_northwind")
    generation["recommendation_rationale"] = (
        'Send the renewal-risk outreach to the economic buyer today. The corpus says '
        '"discounts over ten percent need approval", which removed the discount offer.')
    assert "V-2" in {c.check for c in _judge("renewal_northwind", generation).failures}


def test_v2_accepts_the_authored_claim_quoted_exactly():
    decision, _results, _request, catalogue, grounding = _material("renewal_northwind")
    statement = decision.citations[0]["statement"]
    generation = _clean("renewal_northwind")
    generation["alternatives_narrative"] = f'The rule reads: "{statement}"'
    report = run_gauntlet(generation, decision=decision, catalogue=catalogue, grounding=grounding,
                          citations=decision.citations)
    assert "V-2" not in {check.check for check in report.failures}


def test_v2_refuses_a_citation_this_decision_never_carried():
    """The other way to invent a citation: attach one the decision does not hold. The model cannot
    do this — code attaches them — so this is the guard against a CALLER doing it."""
    decision, _results, _request, catalogue, grounding = _material("renewal_northwind")
    foreign = dict(decision.citations[0]) | {"statement_hash": "0" * 64}
    report = run_gauntlet(_clean("renewal_northwind"), decision=decision, catalogue=catalogue,
                          grounding=grounding, citations=(foreign,))
    assert "V-2" in {check.check for check in report.failures}


def test_v3_refuses_a_recommendation_that_opens_on_the_eliminated_option():
    """Doc 09 case 2, the worst output this layer can produce — and the one a whole-field check
    misses, because the eliminated option is contradicted LATER in the paragraph."""
    generation = _clean("renewal_northwind")
    generation["recommendation_rationale"] = (
        "Open with a discount offer to the economic buyer; a renewal-risk outreach can follow if "
        "it does not land.")
    assert "V-3" in {c.check for c in _judge("renewal_northwind", generation).failures}


def test_v3_refuses_a_comparison_on_a_decision_that_weighed_nothing_else():
    generation = _clean("thin_evidence")
    generation["recommendation_rationale"] = (
        "Review the account before acting. It beat a competitive displacement play and a pricing "
        "review on every axis.")
    assert "V-3" in {c.check for c in _judge("thin_evidence", generation).failures}


def test_v5_refuses_a_placeholder_nobody_computed():
    generation = _clean("renewal_northwind")
    generation["why_it_matters"] = "Exposure compounds at {daily_burn_rate} per day to renewal."
    assert "V-5" in {c.check for c in _judge("renewal_northwind", generation).failures}


def test_v5_refuses_a_malformed_placeholder_rather_than_shipping_a_brace():
    generation = _clean("renewal_northwind")
    generation["why_it_matters"] = "Exposure compounds until { do_nothing_cost_bp } is realised."
    assert "V-5" in {c.check for c in _judge("renewal_northwind", generation).failures}


def test_v6_refuses_an_entity_and_an_address_absent_from_the_situation():
    for field, text in (
            ("root_cause", "Engagement fell away after the pricing thread, and Contoso has been "
                           "evaluating the category since."),
            ("recommendation_rationale", "Send the renewal-risk outreach to the economic buyer at "
                                         "buyer@northwind-holdings.example, referencing the "
                                         "pricing thread.")):
        generation = _clean("renewal_northwind")
        generation[field] = text
        assert "V-6" in {c.check for c in _judge("renewal_northwind", generation).failures}, field


def test_v7_refuses_a_hole_a_cap_cannot_see():
    """Every character cap in the contract is satisfied by "N/A". A card with a hole in it is not."""
    generation = _clean("renewal_northwind")
    generation["root_cause"] = "N/A"
    assert "V-7" in {c.check for c in _judge("renewal_northwind", generation).failures}


def test_v7_has_a_floor_and_not_only_a_cap():
    """A section too short to be the section it names, on prose that trips nothing else: it is
    grounded, it carries no number, it invents no entity and it ends in a full stop. Only the floor
    can catch it, which is why the floor is tested away from the residue check."""
    generation = _clean("renewal_northwind")
    generation["root_cause"] = "Engagement fell."
    failures = {c.check for c in _judge("renewal_northwind", generation).failures}
    assert failures == {"V-7"}, failures


def test_v7_sees_a_bullet_list_that_starts_on_the_second_line():
    """The shape a model produces when it starts in prose and reverts to a list. Without MULTILINE
    the residue check anchors to the start of the field and never looks at line two."""
    generation = _clean("renewal_northwind")
    generation["root_cause"] = (
        "Engagement fell away after the pricing thread.\n- the economic buyer stopped replying\n"
        "- only the champion is active.")
    assert "V-7" in {c.check for c in _judge("renewal_northwind", generation).failures}


def test_v7_refuses_a_missing_section_and_an_unknown_one():
    missing = {k: v for k, v in _clean("renewal_northwind").items() if k != "expected_effect"}
    assert "V-7" in {c.check for c in _judge("renewal_northwind", missing).failures}
    extra = _clean("renewal_northwind") | {"next_steps": "Call them."}
    assert "V-7" in {c.check for c in _judge("renewal_northwind", extra).failures}


def test_the_feedback_names_what_to_fix_rather_than_saying_invalid():
    """Doc 05 §4 allows exactly ONE regeneration, so the message it carries is the only chance to
    turn a near miss into a narrative."""
    generation = _clean("renewal_northwind")
    generation["why_it_matters"] = "The renewal is 11 days out and 84000 is exposed."
    feedback = _judge("renewal_northwind", generation).feedback()
    assert "11" in feedback and "84000" in feedback and "V-4" in feedback


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE NUMBER MECHANISM — "numbers_used is the mechanism, not a note"
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_digits_a_customer_reads_are_the_engines_digits():
    decision, _results, _request, catalogue, grounding = _material("renewal_northwind")
    generation = _clean("renewal_northwind")
    used = catalogue.subset([n for text in generation.values() for n in placeholders(text)])
    bundle = ReasoningBundle.for_decision(
        decision, **generation, citations=decision.citations,
        evidence_refs=grounding.evidence_refs, numbers_used=used,
        generation="llm:claude-sonnet-5@20260101")
    rendered = bundle.render()
    assert str(catalogue.by_name["do_nothing_cost_bp"]) in rendered["why_it_matters"]
    for name, value in used.items():
        assert any(str(value) in (text or "") for text in rendered.values()), name
    assert "{" not in "".join(text or "" for text in rendered.values())


def test_the_catalogue_is_integer_only_and_holds_no_clock():
    decision, results, _request, catalogue, _grounding = _material("renewal_northwind")
    for number in catalogue.numbers:
        assert isinstance(number.value, int) and not isinstance(number.value, bool)
        assert number.label and number.origin
    later = build_catalogue(decision, results, eval_time=NOW + timedelta(days=3))
    assert catalogue.by_name["decision_expires_in_days"] == 11
    assert later.by_name["decision_expires_in_days"] == 8, (
        "the catalogue read a clock instead of its eval_time parameter")


def test_the_catalogue_is_deterministic_and_capped():
    decision, results, _request, catalogue, _grounding = _material("renewal_northwind")
    again = build_catalogue(decision, results, eval_time=NOW)
    assert [(n.name, n.value) for n in catalogue.numbers] == [(n.name, n.value) for n in again.numbers]
    assert len(catalogue) <= MAX_CATALOGUE


def test_a_number_the_units_never_published_is_not_in_the_catalogue():
    """The catalogue is EVERY number the deterministic half computed and nothing else. A fact is an
    input; only a metric a unit published is a computed value."""
    _decision, _results, request, catalogue, _grounding = _material("renewal_northwind")
    assert "deal_stage" not in catalogue
    assert "core_risk_engagement_gap_bp" in catalogue
    assert request.context.facts, "the situation carried facts, so the exclusion is meaningful"


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE FALLBACK — under 15% means it ships, so it has to be good
# ═════════════════════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("situation_id", sorted(SITUATIONS))
def test_the_template_survives_its_own_gauntlet_on_every_situation(situation_id):
    decision, _results, _request, catalogue, grounding = _material(situation_id)
    prose = build_template(decision, catalogue=catalogue, grounding=grounding)
    report = run_gauntlet(prose, decision=decision, catalogue=catalogue, grounding=grounding,
                          citations=decision.citations)
    assert report.passed, f"{situation_id}: {[c.as_record() for c in report.failures]}"


@pytest.mark.parametrize("situation_id", sorted(SITUATIONS))
def test_the_template_constructs_labels_itself_and_says_the_five_things(situation_id):
    decision, _results, _request, catalogue, grounding = _material(situation_id)
    bundle = template_bundle(decision, catalogue=catalogue, grounding=grounding,
                             citations=decision.citations,
                             evidence_refs=grounding.evidence_refs)
    assert bundle.generation == TEMPLATE_FALLBACK, "a fallback that is not labelled is a lie"
    rendered = bundle.render()
    for name in BUNDLE_PROSE_FIELDS:
        if name == "alternatives_narrative":
            continue
        assert rendered[name] and len(rendered[name].split()) >= 6, name
    assert bundle.action_id == decision.action_id


def test_the_template_names_the_action_and_the_do_nothing_contrast():
    decision, _results, _request, catalogue, grounding = _material("renewal_northwind")
    rendered = template_bundle(decision, catalogue=catalogue, grounding=grounding,
                               evidence_refs=grounding.evidence_refs).render()
    assert "renewal risk outreach" in rendered["recommendation_rationale"].lower()
    assert "doing nothing" in rendered["expected_effect"].lower()
    assert str(catalogue.by_name["do_nothing_cost_bp"]) in rendered["expected_effect"]


def test_the_template_floor_constructs_even_when_the_plain_version_cannot():
    """K4's first row is 100% of published decisions carry a bundle, so the fallback may not itself
    be able to fail — not even on a play label nobody anticipated."""
    from genios_engine.reason.bundle.template import _minimal
    decision, _results, _request, catalogue, grounding = _material("thin_evidence")
    floor = _minimal(decision, catalogue=catalogue, grounding=grounding)
    report = run_gauntlet(floor, decision=decision, catalogue=catalogue, grounding=grounding)
    assert report.passed, [c.as_record() for c in report.failures]


def test_a_decision_that_chose_nothing_is_never_narrated():
    """Doc 11 guard 3, at the type. Narrating a DEFER would mean minting an action id for an action
    that does not exist, which is exactly what Law 2 forbids."""
    decision, _results, _request, catalogue, grounding = _material("renewal_northwind")
    deferred = ReasoningDecision(
        outcome=DecisionOutcome.NO_ACTION, capability_id=decision.capability_id,
        capability_version=decision.capability_version,
        context_snapshot_id=decision.context_snapshot_id, candidates=(),
        selected_candidate_id=None, confidence_bp=4000, uncertainty=("thin",),
        do_nothing_consequence="Nothing changes.", expires_at=decision.expires_at)
    assert deferred.action_id is None
    with pytest.raises(ValueError):
        template_bundle(deferred, catalogue=catalogue, grounding=grounding)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE 25-BUNDLE GOLDEN REVIEW  (K4's last row)
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_golden_set_is_a_golden_set():
    """A set that only contains easy cases is not a golden set — the L2 README's rule, restated
    here because the temptation is identical."""
    assert len(FIXTURES) >= GATE["min_fixtures"], "the review is smaller than K4 asks for"
    tags = [set(fixture["tags"]) for fixture in FIXTURES]
    assert sum("clean" in t for t in tags) >= GATE["min_clean"]
    assert sum("adversarial" in t for t in tags) >= GATE["min_adversarial"]
    assert sum("hinglish" in t for t in tags) >= GATE["min_hinglish"], (
        "the corpus is Hinglish-bearing (doc 09 case 9) and the review has to be too")
    caught = {check for fixture in FIXTURES for check in fixture["expect"]["checks_failed"]}
    for check in GATE["checks_covered"]:
        assert check in caught, f"no fixture exercises {check}"


@pytest.mark.parametrize("fixture", [f for f in FIXTURES if f["model_answer"] is not None],
                         ids=lambda f: f["fixture_id"])
def test_every_golden_generation_is_judged_the_way_it_was_labelled(fixture):
    report = _judge(fixture["situation"], fixture["model_answer"])
    expected = fixture["expect"]["gauntlet"]
    failed = {check.check for check in report.failures}
    if expected == "pass":
        assert report.passed, f"{fixture['fixture_id']}: {[c.as_record() for c in report.failures]}"
        return
    assert not report.passed, f"{fixture['fixture_id']} was labelled a failure and passed"
    named = set(fixture["expect"]["checks_failed"])
    assert named <= failed, (
        f"{fixture['fixture_id']} failed on {sorted(failed)} rather than {sorted(named)} — a "
        "fixture caught by a different check is a regression wearing a pass")


@pytest.mark.parametrize("fixture", [f for f in FIXTURES if f["expect"].get("rendered")],
                         ids=lambda f: f["fixture_id"])
def test_the_committed_card_is_what_the_code_renders_today(fixture):
    """The rendered card is committed so a human reads exactly what a founder would. It is also a
    regression pin: a change to the substitution shows up here as a diff in prose."""
    decision, _results, _request, catalogue, grounding = _material(fixture["situation"])
    generation = fixture["model_answer"]
    used = catalogue.subset([n for text in generation.values() for n in placeholders(text)])
    bundle = ReasoningBundle.for_decision(
        decision, **generation, citations=decision.citations,
        evidence_refs=grounding.evidence_refs, numbers_used=used,
        generation="llm:claude-sonnet-5@20260101")
    rendered = {k: v for k, v in bundle.render().items() if v is not None}
    assert rendered == fixture["expect"]["rendered"]


@pytest.mark.parametrize("fixture", [f for f in FIXTURES if f["expect"].get("rendered")],
                         ids=lambda f: f["fixture_id"])
def test_the_ten_second_test(fixture):
    """A founder should understand the card in ten seconds. The human standard is the review; what
    is machine-checkable is the shape that makes it possible — a glance card that is short enough
    to read, six sections that each answer their own question, a consequence that carries a
    magnitude, and no unresolved placeholder anywhere."""
    rendered = fixture["expect"]["rendered"]
    glance = GATE["ten_second_glance_fields"]
    words = {name: len(text.split()) for name, text in rendered.items()}
    assert sum(words[n] for n in glance if n in words) <= GATE["ten_second_max_words_per_card"]
    assert max(words.values()) <= GATE["ten_second_max_words_per_section"]
    assert not any("{" in text or "}" in text for text in rendered.values())
    # A consequence with no magnitude is not a consequence, and an expected effect with no
    # do-nothing half is half a card.
    assert any(char.isdigit() for char in rendered["why_it_matters"])
    assert any(marker in rendered["expected_effect"].lower()
               for marker in ("doing nothing", "not acting", "leaving it", "if it is left"))
    assert rendered["root_cause"].lower() != rendered["situation_summary"].lower()
