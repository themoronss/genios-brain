"""Step 9 · "I heard Acme is leaving" and "Acme is leaving, I spoke to their CFO" score the same.

    pytest tests/capture/validate/test_hearsay_does_not_outrank_a_witness.py -q

THE DEFECT. ALG-14 answers *who typed it*. **Nothing answers whether they witnessed it.** Both
sentences above come from the same CEO, so both take `Authority.HIGH`, and hearsay from a
high-authority actor outranks a first-hand account from a lower-authority one.

That is backwards, and it is exactly how a rumour becomes a card — the failure ALG-13's own module
docstring calls the hardest one in the system to see, *"because it looks exactly like rigour"*.

⛔ **THE COST CHECK CHANGED THE DESIGN, checked 2026-09-24 before any code.** The plan's 9-U2 says
*"the extractor PROPOSES it with a span"*. Asking the model for it means:

    a closed set in `semantic/vocabulary._SETS`  →  moves `vocabulary_fingerprint()`
                                                 →  moves the `l1_extraction_results` key
                                                 →  RE-EXTRACTS THE WHOLE CORPUS

...a third full bill after step 4's. And **not** adding it to `_SETS` while still changing the
prompt is strictly worse: the prompt moves, the key does not, and every cached row goes on
answering for a question it was never asked — the recorded *"260 cached extractions survived a
prompt fix, the numbers did not move, and the conclusion drawn was that the fix had not worked."*

**SO DIRECTNESS IS DERIVED, NOT ASKED FOR**, and that is better on three counts:

  1. **no cost** — no prompt change, no new call, no re-extraction;
  2. **doctrine 1** — hearsay is a property of the WORDS, not a judgement. "I heard" is in the
     text or it is not, and a deterministic recogniser cannot hallucinate one;
  3. **the receipt is free** — the marker is inside the span the claim already carries, so the
     evidence for "this is hearsay" is the quote itself. A model proposing it would need a
     SECOND span to justify the first.

E2 is already true and costs nothing: a forwarded message is structurally reported, and the thread
reconstructor already knows a forward restarts the turn index.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# =============================================================================================
# 9-U1 · the axis — four values, and `unknown` is the default and a real answer
# =============================================================================================
def test_directness_has_its_own_closed_axis():
    """`firsthand` / `reported` / `speculative` / `unknown`.

    `speculative` is separate from `reported` and the difference is not cosmetic: *"I heard Acme
    is leaving"* is somebody's account of something that happened, and *"I think Acme might
    leave"* is a guess about something that has not. Folding them would let a guess corroborate a
    witness.
    """
    from genios_engine.capture.validate.directness import Directness

    assert {d.value for d in Directness} == {"firsthand", "reported", "speculative", "unknown"}


def test_unknown_is_the_default_and_is_never_guessed():
    """E1 and E5. Old extractions have no directness and must compose CONSERVATIVELY rather than
    optimistically — `unknown` is a real answer here exactly as it is everywhere else in this
    layer, and defaulting to `firsthand` would silently promote the entire existing corpus."""
    from genios_engine.capture.validate.directness import Directness, read_directness

    assert read_directness("") is Directness.UNKNOWN
    assert read_directness("the renewal is confirmed for March") is Directness.UNKNOWN


# =============================================================================================
# The recogniser — deterministic, and the marker IS the receipt
# =============================================================================================
@pytest.mark.parametrize("quote", [
    "I heard Acme is leaving",
    "apparently they are switching vendors",
    "someone said the budget was cut",
    "word is they are winding down",
    "I was told the contract is signed",
    "rumour has it they lost the round",
])
def test_a_hearsay_marker_makes_a_claim_reported(quote: str):
    """The words that say somebody is relaying rather than witnessing. Each one is a phrase a
    person actually writes, not a synonym list — a recogniser tuned on invented sentences matches
    invented sentences."""
    from genios_engine.capture.validate.directness import Directness, read_directness

    assert read_directness(quote) is Directness.REPORTED, quote


@pytest.mark.parametrize("quote", [
    "I think they might leave",
    "they could be switching vendors",
    "my guess is the renewal slips",
    "it seems like the budget is gone",
    "probably moving to a competitor",
])
def test_a_speculation_marker_is_not_the_same_as_hearsay(quote: str):
    """A guess about something that has not happened. It must not corroborate a witness, and it
    must not be filed as somebody's account either — nobody reported it, including the writer."""
    from genios_engine.capture.validate.directness import Directness, read_directness

    assert read_directness(quote) is Directness.SPECULATIVE, quote


@pytest.mark.parametrize("quote", [
    "I spoke to their CFO and they are leaving",
    "I saw the signed contract",
    "we agreed the new price on the call",
    "I confirmed it with their procurement lead",
])
def test_a_witness_marker_makes_a_claim_firsthand(quote: str):
    """The other end. A claim that names the writer's own contact with the fact.

    NOTE THE ASYMMETRY, deliberately: an absence of markers is `unknown`, not `firsthand`. Most
    business writing states a fact flatly — *"the renewal is confirmed"* — and reading that as
    witnessed would make the default the strongest value, which is the one direction this axis
    may never fail in.
    """
    from genios_engine.capture.validate.directness import Directness, read_directness

    assert read_directness(quote) is Directness.FIRSTHAND, quote


def test_hearsay_beats_witness_when_a_sentence_carries_both():
    """*"I heard they signed, but I confirmed it with their CFO"* — a real sentence shape, and the
    conservative reading wins. Taking the stronger half would let one hedged clause launder a
    rumour into a witnessed fact, and the whole axis exists to stop precisely that."""
    from genios_engine.capture.validate.directness import Directness, read_directness

    both = "I heard they signed, but I confirmed it with their CFO"
    assert read_directness(both) is Directness.REPORTED


def test_speculation_beats_hearsay_when_a_sentence_carries_both():
    """Same rule, one rung further down. The weakest reading present is the reading."""
    from genios_engine.capture.validate.directness import Directness, read_directness

    assert read_directness("I heard they might be leaving") is Directness.SPECULATIVE


def test_the_recogniser_is_pure_and_reads_no_clock_and_no_model():
    """It is handed words and returns a value. A recogniser that called a model would reintroduce
    the cost this design exists to avoid, and one that read a clock could not be replayed."""
    import inspect

    from genios_engine.capture.validate import directness

    source = inspect.getsource(directness)
    for forbidden in ("datetime.now", "utcnow", "llm", "LLMClient", "requests"):
        assert forbidden not in source, f"`{forbidden}` in a pure recogniser"


# =============================================================================================
# 9-U3 · it reaches the composer, and a rumour stops outranking a witness
# =============================================================================================
def test_a_confidence_source_carries_its_directness():
    """`ConfidenceSource` is the right home and says so itself: *"a composition input gains
    dimensions over time... and each of those must arrive as a FIELD WITH A DEFAULT rather than as
    a key that some call site silently misspells and this module silently ignores."*"""
    from genios_engine.capture.validate.confidence import ConfidenceSource

    assert "directness" in ConfidenceSource.__dataclass_fields__


def test_the_same_ceo_s_hearsay_composes_below_their_first_hand_claim():
    """T2 — THE LOAD-BEARING ROW OF THE STEP.

    Identical author, identical authority, identical everything except whether they witnessed it.
    Before this, the two were the same number.
    """
    from genios_engine.capture.validate.authority import Authority
    from genios_engine.capture.validate.confidence import ConfidenceSource, compose_confidence
    from genios_engine.capture.validate.directness import Directness

    def ceo(directness: Directness) -> int:
        # EMAIL_PROSE for BOTH, and that is the defect in one line: ALG-14 ranks the ARTIFACT
        # (an email is an email), so a CEO's rumour and a CEO's witnessed account are the same
        # rank. The plan said "both score actor_authority = HIGH"; the authority ladder is over
        # artifact type and the members are SIGNED_DOCUMENT..INFERRED — same conclusion, and the
        # premise's wording is corrected in the findings.
        source = ConfidenceSource(name="ceo@acme.com", confidence_bp=8000,
                                  independence_key="thread-1", authority=Authority.EMAIL_PROSE,
                                  directness=directness)
        return compose_confidence([source]).confidence_bp

    assert ceo(Directness.REPORTED) < ceo(Directness.FIRSTHAND), (
        "hearsay from a high-authority actor still composes level with a witnessed account")
    assert ceo(Directness.SPECULATIVE) < ceo(Directness.REPORTED)


def test_unknown_is_NEUTRAL_and_never_a_deduction():
    """E5, AND THE CORRECTION THE EXISTING SUITE FORCED.

    This row first asserted `REPORTED <= UNKNOWN < FIRSTHAND`, i.e. a small discount for an
    unstated directness, on the word "conservatively" in E5. **Eight tests in `test_confidence.py`
    went red** — every caller in the tree passes the default, so that discount silently lowered
    EVERY composition in the system by ten percent on deploy day.

    The distinction those failures forced:

        conservative   does not INFLATE on no evidence      →  neutral
        punitive       DEDUCTS on no evidence               →  a discount

    This axis lowers only on POSITIVE EVIDENCE of hearsay or speculation. `unknown` means no
    marker was found, which is no evidence either way, and deducting for it is punishing silence —
    which this layer refuses everywhere else.

    T2 still holds, and it is the whole point of the step: hearsay composes below first-hand.
    """
    from genios_engine.capture.validate.authority import Authority
    from genios_engine.capture.validate.confidence import ConfidenceSource, compose_confidence
    from genios_engine.capture.validate.directness import Directness

    def score(directness: Directness) -> int:
        return compose_confidence([ConfidenceSource(
            name="s", confidence_bp=8000, independence_key="k",
            authority=Authority.EMAIL_PROSE, directness=directness)]).confidence_bp

    assert score(Directness.UNKNOWN) == score(Directness.FIRSTHAND), (
        "an unstated directness is being DEDUCTED for, which downgrades every stored claim")
    assert score(Directness.REPORTED) < score(Directness.UNKNOWN)
    assert score(Directness.SPECULATIVE) < score(Directness.REPORTED)


def test_a_firsthand_claim_from_a_low_authority_actor_does_not_outrank_everything():
    """E4. Directness is ONE INPUT to the clamp, not a new ranking. A junior's witnessed remark is
    better evidence than the same junior's rumour — and still not better than a signed contract.

    An axis that inverted the authority ladder would replace one wrong ordering with another.
    """
    from genios_engine.capture.validate.authority import Authority
    from genios_engine.capture.validate.confidence import ConfidenceSource, compose_confidence
    from genios_engine.capture.validate.directness import Directness

    junior = compose_confidence([ConfidenceSource(
        name="junior", confidence_bp=5000, independence_key="k",
        authority=Authority.CHAT_ASIDE, directness=Directness.FIRSTHAND)]).confidence_bp
    contract = compose_confidence([ConfidenceSource(
        name="signed", confidence_bp=9000, independence_key="k2",
        authority=Authority.SIGNED_DOCUMENT, directness=Directness.UNKNOWN)]).confidence_bp

    assert junior < contract


# =============================================================================================
# 9-U4 · the guards — what this step may not touch
# =============================================================================================
def test_alg14s_authority_table_is_untouched():
    """T4 and E3. Directness is a SEPARATE AXIS and must never be folded into ALG-14's 0..6 ladder
    over artifact type. Two different questions — *what kind of artifact is this* and *did the
    writer witness it* — and one table answering both is a table answering neither."""
    from genios_engine.capture.validate.authority import Authority, rank_of

    ranks = {a.name: rank_of(a) for a in Authority}
    assert ranks == {"SIGNED_DOCUMENT": 6, "COMPANY_CANON": 5, "STRUCTURED_SOURCE": 4,
                     "ATTACHMENT": 3, "EMAIL_PROSE": 2, "CHAT_ASIDE": 1, "INFERRED": 0}
    assert len(set(ranks.values())) == len(ranks), "two authority classes collapsed to one rank"
    assert max(ranks.values()) <= 6 and min(ranks.values()) >= 0


def test_rule_11s_measured_clamp_is_unchanged():
    """T5, and it is a LITERAL for a reason: `corroborate(100, 9000) = 1882`, not 9002.

    Rule 11 is the rule that stops five sources repeating one weak recollection composing into an
    8900 nothing supports. This step adds an input to the clamp and may not loosen it by one basis
    point.
    """
    from genios_engine.capture.validate.authority import Authority
    from genios_engine.capture.validate.confidence import corroborate

    # INFERRED — the FLOOR of the ladder, which is the case the plan measured. A weak base
    # corroborated by our own inference lands at 1882, not at 9002. The whole ladder, for the
    # record: SIGNED_DOCUMENT 4555 · COMPANY_CANON 4332 · STRUCTURED_SOURCE 4109 ·
    # ATTACHMENT 3886 · EMAIL_PROSE 3664 · CHAT_ASIDE 2995 · INFERRED 1882.
    assert corroborate(100, 9000, evidence="a second signed contract",
                       authority=Authority.INFERRED) == 1882
    assert corroborate(100, 9000, evidence="a second signed contract",
                       authority=Authority.SIGNED_DOCUMENT) == 4555


def test_directness_is_not_a_sixth_importance_weight():
    """§9: *"Do not let it become a sixth weight in ALG-17 — the weights sum to 10000 and that
    check stays."* Directness belongs to CONFIDENCE (how sure are we) and not to IMPORTANCE (how
    much does it matter), and the two are different questions this codebase keeps separate."""
    from genios_engine.capture.esqe.importance import BP_MAX, IMPORTANCE_WEIGHTS_V1 as W

    assert W.total == BP_MAX
    assert (W.money, W.deadline, W.criticality, W.authority, W.signal_type) == (
        3000, 2500, 2000, 1500, 1000)


def test_the_extraction_cache_fingerprint_is_untouched():
    """⛔ THE COST GUARD. Directness is DERIVED from words the model already returned, so nothing
    about the prompt changes and nothing re-extracts.

    If this fails, somebody added a directness vocabulary to `_SETS` and the whole corpus is about
    to be re-extracted for a third time — see this file's header.
    """
    from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint

    assert vocabulary_fingerprint() == "a3d5496aa0d3"


# =============================================================================================
# IT REACHES THE REAL PATH — the check that has caught this defect four steps running
# =============================================================================================
def test_the_publisher_reads_directness_off_the_span_it_already_has():
    """FOUR STEPS RUNNING the same defect: step 5's `claimed_total`, step 6's `domain_tagged`,
    step 7's counters, step 8's ceiling — each a field added with a green test and nothing filling
    it.

    `ConfidenceSource.directness` defaults to `UNKNOWN`, which is NEUTRAL, so a publisher that
    never set it would leave every composition exactly as it is today and every test in this file
    would still pass. That is the most dangerous shape a default can have, so the wiring is
    asserted against the source of the only caller in the tree.
    """
    import inspect

    from genios_engine.capture.esqe import publisher

    source = inspect.getsource(publisher)
    assert source.count("directness=read_directness(") == 2, (
        "both ConfidenceSource call sites must read directness — the claim-lane path and the "
        "evidence_refs fallback, or hearsay is only discounted on one of the two routes")


def test_a_hearsay_span_and_a_witness_span_produce_different_confidences_end_to_end():
    """THE STEP, in one assertion, through the arithmetic the publisher actually runs.

    Same author, same authority, same base confidence, same everything — except that one span's
    words say the writer heard it and the other's say they confirmed it.
    """
    from genios_engine.capture.validate.authority import Authority
    from genios_engine.capture.validate.confidence import ConfidenceSource, compose_confidence
    from genios_engine.capture.validate.directness import read_directness

    def compose(quote: str) -> int:
        return compose_confidence([ConfidenceSource(
            name="prepared_content:evt_1@0-40", confidence_bp=8000,
            independence_key="prepared_content:evt_1", authority=Authority.EMAIL_PROSE,
            directness=read_directness(quote))]).confidence_bp

    rumour = compose("I heard Acme is leaving")
    witness = compose("I spoke to their CFO and they are leaving")

    assert rumour < witness, (
        "a rumour and a witnessed account from the same CEO still compose to the same number")
