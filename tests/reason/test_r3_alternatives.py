"""R-3 · narrating why the options that lost, lost — and never a reason the chain did not record.

The elimination chain is already correct and already receipted: `decision_maker` writes eliminated
candidates with their checks, Layer 3's weld carries the rule id and the authored statement, and the
card stores `rejected_candidates`. R-3 adds a sentence and MUST add nothing else. So the tests below
are mostly refusals — an invented reason, an invented quotation, a narration of a comparison that
never happened — because that is where this site can do damage.
"""

from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.contracts.reasoning import (
    CandidateCheck,
    CandidateDisposition,
    CheckOutcome,
    DecisionCandidate,
    DecisionOutcome,
    ReasoningBundle,
    ReasoningDecision,
    bare_numbers,
)
from genios_engine.reason import narration as N
from genios_engine.reason.bundle.gate import force_failed
from genios_engine.reason.llm_sites import (
    OUTCOME_CACHED,
    OUTCOME_PRECONDITION,
    OUTCOME_RAN,
    InMemorySiteCache,
    make_gate,
)

STATEMENT = "no unapproved discount without written approval"
CARD_ROWS = [
    {"play_id": "discount_play", "disposition": "eliminated", "utility_bp": 4200,
     "reason_code": "blocking_rule", "rule_id": "ADM-014", "statement": STATEMENT},
    {"play_id": "wait", "disposition": "eligible", "utility_bp": 5100},
]


class Client:
    model = "claude-haiku-4-5"

    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls = 0
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=600):
        from genios_engine.context.llm.client import LLMResult
        self.calls += 1
        self.prompts.append(prompt)
        body = self.texts[min(self.calls - 1, len(self.texts) - 1)]
        return LLMResult(parsed={"alternatives_narrative": body}, raw="", ok=True,
                         model=self.model, input_tokens=800, output_tokens=200)


def gate(client=None, *, activated=frozenset({"bundle"})):
    """The ONE C5 gate, wired for a test — never a stand-in for it."""
    return make_gate(org_id="org_1", client=client, activated=activated)


def narrate(client=None, options=None, site_gate=None, **kwargs):
    return N.narrate_alternatives(
        org_id="org_1", decision_hash="dh_1",
        options=N.rejected_options_from_card(CARD_ROWS) if options is None else options,
        selected_utility_bp=7000, gate=(site_gate or gate(client)), **kwargs)


# ── reading the chain ────────────────────────────────────────────────────────────────────────

def test_the_elimination_chain_of_a_real_decision_becomes_the_options_r3_narrates():
    """`rejected_options` reads a `ReasoningDecision`, joined to the corpus rules that eliminated."""
    check = CandidateCheck(play_id="discount_play", stage="constraint",
                           outcome=CheckOutcome.ELIMINATE, reason_code="blocking_rule",
                           evaluator_id="core.constraint", evaluator_version="1.0.0")
    loser = DecisionCandidate(play_id="discount_play", play_version="1.0.0",
                              disposition=CandidateDisposition.ELIMINATED, utility_bp=4200,
                              confidence_bp=6000, score_components={"formula_utility": 4200},
                              checks=(check,))
    winner = DecisionCandidate(play_id="outreach", play_version="1.0.0",
                               disposition=CandidateDisposition.ELIGIBLE, utility_bp=7000,
                               confidence_bp=6000, score_components={"formula_utility": 7000},
                               rank_position=1)
    decision = ReasoningDecision(
        outcome=DecisionOutcome.DECISION, capability_id="cap", capability_version="1.0.0",
        context_snapshot_id="ctx_1", candidates=(winner, loser),
        selected_candidate_id=winner.candidate_id, confidence_bp=6000, uncertainty=(),
        do_nothing_consequence="something happens",
        expires_at=datetime(2026, 9, 6, tzinfo=timezone.utc))
    options = N.rejected_options(decision, constraints=[
        # The REAL shape: `eliminated_candidate_ids` holds CANDIDATE ids, because that is what
        # `rule_compiler` writes and what the contract re-checks against this decision.
        {"rule_id": "ADM-014", "statement": STATEMENT, "severity": "blocking",
         "outcome": "fired", "eliminated_candidate_ids": [loser.candidate_id]}])
    assert [option.play_id for option in options] == ["discount_play"]
    assert options[0].reason_code == "blocking_rule"
    assert options[0].rule_id == "ADM-014" and options[0].statement == STATEMENT


def test_only_an_eliminating_check_says_why_an_option_lost():
    """`CheckOutcome` has four members and only ELIMINATE removes a candidate. A WARN annotates and
    an ADJUST rescores — reporting either as the reason an option "lost" would put a sentence on a
    card that the chain does not support."""
    warned = CandidateCheck(play_id="discount_play", stage="policy", outcome=CheckOutcome.WARN,
                            reason_code="stale_pricing_sheet", evaluator_id="core.policy",
                            evaluator_version="1.0.0")
    blocked = CandidateCheck(play_id="discount_play", stage="constraint",
                             outcome=CheckOutcome.ELIMINATE, reason_code="blocking_rule",
                             evaluator_id="core.constraint", evaluator_version="1.0.0")
    loser = DecisionCandidate(play_id="discount_play", play_version="1.0.0",
                              disposition=CandidateDisposition.ELIMINATED, utility_bp=4200,
                              confidence_bp=6000, score_components={"formula_utility": 4200},
                              checks=(warned, blocked))
    winner = DecisionCandidate(play_id="outreach", play_version="1.0.0",
                               disposition=CandidateDisposition.ELIGIBLE, utility_bp=7000,
                               confidence_bp=6000, score_components={"formula_utility": 7000},
                               rank_position=1)
    decision = ReasoningDecision(
        outcome=DecisionOutcome.DECISION, capability_id="cap", capability_version="1.0.0",
        context_snapshot_id="ctx_1", candidates=(winner, loser),
        selected_candidate_id=winner.candidate_id, confidence_bp=6000, uncertainty=(),
        do_nothing_consequence="something happens",
        expires_at=datetime(2026, 9, 6, tzinfo=timezone.utc))
    assert N.rejected_options(decision)[0].reason_code == "blocking_rule"


def test_a_rule_that_names_a_play_id_instead_of_a_candidate_id_joins_nothing():
    """The join is on the id space the compiler actually writes. A play id here would silently match
    nothing — a rule that quietly stops reaching a card while every test still passes."""
    check = CandidateCheck(play_id="discount_play", stage="constraint",
                           outcome=CheckOutcome.ELIMINATE, reason_code="blocking_rule",
                           evaluator_id="core.constraint", evaluator_version="1.0.0")
    loser = DecisionCandidate(play_id="discount_play", play_version="1.0.0",
                              disposition=CandidateDisposition.ELIMINATED, utility_bp=4200,
                              confidence_bp=6000, score_components={"formula_utility": 4200},
                              checks=(check,))
    winner = DecisionCandidate(play_id="outreach", play_version="1.0.0",
                               disposition=CandidateDisposition.ELIGIBLE, utility_bp=7000,
                               confidence_bp=6000, score_components={"formula_utility": 7000},
                               rank_position=1)
    decision = ReasoningDecision(
        outcome=DecisionOutcome.DECISION, capability_id="cap", capability_version="1.0.0",
        context_snapshot_id="ctx_1", candidates=(winner, loser),
        selected_candidate_id=winner.candidate_id, confidence_bp=6000, uncertainty=(),
        do_nothing_consequence="something happens",
        expires_at=datetime(2026, 9, 6, tzinfo=timezone.utc))
    joined = N.rejected_options(decision, constraints=[
        {"rule_id": "ADM-014", "statement": STATEMENT, "severity": "blocking",
         "outcome": "fired", "eliminated_candidate_ids": [loser.candidate_id]}])
    assert joined[0].rule_id == "ADM-014"
    unjoined = N.rejected_options(decision, constraints=[
        {"rule_id": "ADM-014", "statement": STATEMENT, "severity": "blocking",
         "outcome": "fired", "eliminated_candidate_ids": ["discount_play"]}])
    assert unjoined[0].rule_id == ""      # named the wrong id space; nothing is invented


def test_the_compiled_lane_card_row_carries_its_rule_and_r3_reads_it():
    """`domain_shadow._rejected_candidates` writes `eliminated_by` onto the signal row — rule id and
    byte-identical statement — so "why not X?" is answerable at expand time without a re-run."""
    options = N.rejected_options_from_card([
        {"play_id": "discount_play", "disposition": "eliminated", "utility_bp": 4200,
         "eliminated_by": [{"rule_id": "ADM-014", "severity": "blocking",
                            "statement": STATEMENT}]}])
    assert options[0].rule_id == "ADM-014"
    assert options[0].statement == STATEMENT
    assert options[0].reason_code == "blocking_rule"


def test_with_nothing_eliminated_the_site_does_not_run_at_all():
    client = Client("anything")
    result = narrate(client=client, options=())
    assert result.receipt.outcome == OUTCOME_PRECONDITION
    assert result.text == "" and client.calls == 0


# ── what the model may say ───────────────────────────────────────────────────────────────────

def test_a_narration_that_quotes_the_recorded_rule_verbatim_is_accepted():
    client = Client(f'The discount play was eliminated: the rule says "{STATEMENT}". '
                    "Waiting scored lower by {utility_gap_bp} basis points.")
    result = narrate(client=client)
    assert result.receipt.outcome == OUTCOME_RAN
    assert result.numbers_used == {"utility_gap_bp": 1900}
    assert "1900" in result.rendered and "{utility_gap_bp}" not in result.rendered


def test_an_invented_quotation_is_refused():
    """V-2, byte-identity — the model may not improve the corpus's wording."""
    client = Client('The discount play lost because the rule says "discounts are banned".')
    result = narrate(client=client)
    assert result.fell_back
    assert result.receipt.reason_codes == ("unverifiable_quotation",)


def test_a_narration_that_names_none_of_the_recorded_options_is_refused():
    """"Nothing else was suitable" is a reason the chain did not record."""
    client = Client("Nothing else was suitable in the circumstances.")
    assert narrate(client=client).fell_back


def test_a_bare_number_is_refused_even_when_it_is_true():
    client = Client("The discount play scored 4200 and lost.")
    result = narrate(client=client)
    assert result.fell_back and "bare_number" in result.receipt.reason_codes


def test_a_placeholder_nobody_computed_is_refused():
    client = Client("The discount play lost by {invented_gap_bp} basis points.")
    result = narrate(client=client)
    assert result.fell_back
    assert "unresolved_placeholder" in result.receipt.reason_codes


def test_an_over_long_narration_is_refused_at_the_bundles_own_cap():
    client = Client("discount play " + "x" * N.ALTERNATIVES_CAP)
    result = narrate(client=client)
    assert result.fell_back and "over_length" in result.receipt.reason_codes


def test_one_retry_then_the_template_and_never_a_third_call():
    client = Client("bad 1", "bad 2", "discount play was eliminated by the recorded rule.")
    result = narrate(client=client)
    assert client.calls == 2
    assert result.fell_back


# ── the deterministic fallback ───────────────────────────────────────────────────────────────

def test_the_template_says_what_was_eliminated_without_a_digit_anywhere():
    result = narrate(client=None)
    assert result.generation == "template_fallback"
    assert "discount play" in result.text
    assert bare_numbers(result.text) == ()


def test_the_template_never_implies_a_citation_the_chain_did_not_record():
    options = N.rejected_options_from_card([
        {"play_id": "discount_play", "disposition": "eliminated", "utility_bp": 4200}])
    text = N.template_alternatives(options, {})
    assert "rule" not in text and "discount play" in text


def test_a_play_id_carrying_a_digit_falls_back_to_the_generic_sentence():
    """Otherwise the template itself would carry a bare number and no bundle could hold it."""
    options = N.rejected_options_from_card([
        {"play_id": "plan_b2", "disposition": "eliminated", "utility_bp": 1000}])
    text = N.template_alternatives(options, {})
    assert text == N.GENERIC_ALTERNATIVES
    assert bare_numbers(text) == ()


def test_both_the_generation_and_the_template_fit_inside_a_real_bundle():
    """The narration exists to fill `alternatives_narrative`; a field the constructor refuses is a
    card with no narrative at all, so the constructor is the test."""
    for client in (None, Client('The discount play was eliminated: the rule says "%s". '
                                "Waiting cost {utility_gap_bp} basis points." % STATEMENT)):
        result = narrate(client=client)
        bundle = ReasoningBundle(
            decision_id="decision_1", action_id="outreach", headline="Renewal at risk",
            situation_summary="s", why_it_matters="w", root_cause="r",
            recommendation_rationale="rr", expected_effect="e",
            alternatives_narrative=result.text, numbers_used=dict(result.numbers_used),
            evidence_refs=("ev_1",))
        assert bundle.render()["alternatives_narrative"]


# ── the standing guards ──────────────────────────────────────────────────────────────────────

def test_a_re_expanded_card_never_regenerates():
    """Doc 09 loop L-2 and case 10 — the cache is what makes a re-render free AND stable."""
    cache = InMemorySiteCache()
    client = Client('The discount play was eliminated: the rule says "%s".' % STATEMENT)
    site_gate = gate(client)
    first = narrate(site_gate=site_gate, cache=cache)
    second = narrate(site_gate=site_gate, cache=cache)
    assert client.calls == 1
    assert second.receipt.outcome == OUTCOME_CACHED
    assert second.text == first.text and second.generation == first.generation


def test_the_site_is_failable_and_the_card_still_renders():
    """Through the SHIPPED switch — the one K4's doctrine replay flips for every R-site at once."""
    client = Client("anything")
    with force_failed():
        result = narrate(client=client)
    assert result.fell_back and result.text
    assert result.receipt.outcome == "force_failed" and client.calls == 0


def test_the_prompt_offers_no_wording_that_could_not_be_quoted_into_a_bundle():
    """A statement carrying a digit is not offered for quotation, because a quoted digit is a digit
    the bundle constructor refuses — so offering it would be inviting a rejection."""
    options = N.rejected_options_from_card([
        {"play_id": "discount_play", "disposition": "eliminated", "utility_bp": 4200,
         "rule_id": "ADM-014", "statement": "no unapproved discount above 10%"}])
    client = Client("discount play was eliminated by a recorded rule.")
    N.narrate_alternatives(org_id="org_1", decision_hash="dh_1", options=options,
                           selected_utility_bp=7000, gate=gate(client))
    assert "10%" not in client.prompts[0]
    assert "ADM-014" in client.prompts[0]        # the id is context, not quotable prose
