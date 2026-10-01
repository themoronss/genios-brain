r"""L5 STEP-03 · `M13.C1.U01` — a card's copy becomes tagged claims.

⛔ THE VOCABULARY ALREADY EXISTED. `contracts/claim_state.py` defines
`OBSERVED / INFERRED / HYPOTHESISED / ENVELOPE` with `_MODEL_MAY_WRITE`. It classifies FIELDS; this
classifies SENTENCES, and it REUSES the enum: two spellings of one idea disagree the first time one
is extended, which is what `FEATURE_CARDS_FROM_SITUATIONS` cost this exact package.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from genios_engine.contracts.claim_state import CLAIM_STATES, ClaimState
from genios_engine.deliver import claim_validator, claims as C
from genios_engine.deliver.claim_validator import claims_ok, observed_claims
from genios_engine.deliver.claims import Claim, by_state, classify, extract, split_sentences
from genios_engine.deliver.render import invention_ok

CORPUS = "nikhil@addis.im wrote on tuesday about the series a round. sofía padrón replied."
NUMS = {"4", "12"}


# ── the split ─────────────────────────────────────────────────────────────────────────────────

def test_a_decimal_is_not_two_sentences():
    """⛔ Splitting on every period would cut `4.5x` in half and then report both halves as
    ungrounded inventions — the validator refusing a card for a number it broke itself."""
    assert split_sentences("Revenue is 4.5x last year.") == ("Revenue is 4.5x last year.",)



def test_an_address_survives_the_split():
    assert len(split_sentences("Write to nikhil@addis.im today.")) == 1



def test_empty_copy_yields_no_claims():
    assert split_sentences("") == () and extract("") == ()


# ── the tags ──────────────────────────────────────────────────────────────────────────────────


def test_an_instruction_is_not_a_claim():
    """`ENVELOPE` exists so that "not a claim" never means "nobody classified it"."""
    claim = classify("Send the deck today.", corpus_text=CORPUS)
    assert claim.state is ClaimState.ENVELOPE
    assert claim.asserts_about_the_world is False



def test_a_question_is_not_a_claim_either():
    assert classify("Has the contract been signed?").state is ClaimState.ENVELOPE



@pytest.mark.parametrize("sentence", [
    "This deal will probably slip.",
    "They may have gone quiet for a reason.",
    "The round appears to be oversubscribed.",
])
def test_a_hedged_sentence_is_a_hypothesis(sentence):
    assert classify(sentence, corpus_text=CORPUS).state is ClaimState.HYPOTHESISED



def test_a_hedge_outranks_being_perfectly_grounded():
    """⛔ THE MOST IMPORTANT ORDERING IN THE MODULE. "They will probably churn" invents no number
    and no name, and it is still not an observation. Letting grounding win here is exactly how a
    guess acquires a fact's authority, which `claim_state` forbids: a hypothesis is *"never
    rendered as fact"*."""
    claim = classify("Nikhil probably wrote on tuesday.", corpus_text=CORPUS,
                     corpus_nums=NUMS, quotes_something=True)
    assert claim.state is ClaimState.HYPOTHESISED
    assert claim.ungrounded == (), "the sentence is grounded; that is what makes the case sharp"



def test_a_hedge_is_matched_as_a_whole_word():
    """A substring match makes "may" out of "dismayed" and "about" out of "roundabout"."""
    assert classify("Nikhil was dismayed.", corpus_text=CORPUS).state is not ClaimState.HYPOTHESISED



def test_grounded_and_quoting_is_an_observation():
    claim = classify("Nikhil wrote on tuesday.", corpus_text=CORPUS, quotes_something=True)
    assert claim.state is ClaimState.OBSERVED



def test_grounded_without_a_quote_is_an_inference_not_an_observation():
    """The parts are real; the sentence assembling them is ours."""
    claim = classify("Nikhil wrote on tuesday.", corpus_text=CORPUS, quotes_something=False)
    assert claim.state is ClaimState.INFERRED



def test_an_unhedged_invention_is_inferred_and_not_hypothesised():
    """⛔ An unhedged sentence asserting an invented number is not a modest proposal, it is a false
    claim. Tagging it `HYPOTHESISED` would route it to the rules written to be LENIENT with
    hypotheses — a wrong tag is not a neutral act here, it selects the check."""
    claim = classify("Acme raised 99m last week.", corpus_text=CORPUS, corpus_nums=NUMS)
    assert claim.state is ClaimState.INFERRED
    assert "number:99" in claim.ungrounded



def test_the_ungrounded_list_uses_the_same_vocabulary_the_old_validator_uses():
    claim = classify("Mesco raised 99m.", corpus_text=CORPUS, corpus_nums=NUMS)
    assert any(t.startswith("number:") for t in claim.ungrounded)
    assert any(t.startswith("name:") for t in claim.ungrounded)



def test_every_tag_carries_its_reason():
    """A claim in the wrong state with no record of why is undiagnosable, and the state decides
    what the validator will demand of the sentence."""
    for claim in extract("Nikhil wrote on tuesday. This may slip. Send a reply. Acme raised 99m.",
                         corpus_text=CORPUS, corpus_nums=NUMS, quotes_something=True):
        assert claim.reason.strip()



def test_the_mix_declares_every_state_including_the_ones_that_did_not_occur():
    counts = by_state(extract("Send a reply.", corpus_text=CORPUS))
    assert set(counts) == {s.value for s in ClaimState}
    assert counts["envelope"] == 1 and counts["observed"] == 0



def test_the_classifier_reuses_the_contract_vocabulary_rather_than_inventing_one():
    """⛔ Two spellings of one idea disagree the first time one is extended — `card_source` carries
    that lesson from `FEATURE_CARDS_FROM_SITUATIONS`, one file over."""
    tree = ast.parse(pathlib.Path(C.__file__).read_text())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "genios_engine.contracts.claim_state" in imported
    assert not any(isinstance(n, ast.ClassDef) and "State" in n.name for n in ast.walk(tree))



def test_the_grounding_helpers_are_the_renderers_own():
    """⛔ Reimplementing `_fold` would give the card two answers to "is this name in the corpus".
    The folding rules exist because of measured failures — `V-02:name:Sofa` against a graph holding
    "Sofía Padrón"."""
    src = inspect.getsource(C._ungrounded_tokens)
    assert "_haystack" in src and "_fold" in src and "_proper_nouns" in src



def test_the_accented_name_case_the_folding_exists_for():
    assert classify("Sofia replied.", corpus_text=CORPUS).ungrounded == ()



def test_no_model_classifies_a_claim():
    """§4: "if the output is a number, a route or a permission, no model produces it." A claim tag
    decides what the validator demands of a sentence, which makes it a permission."""
    tree = ast.parse(pathlib.Path(C.__file__).read_text())
    mods = {(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any("llm" in m or "anthropic" in m or "openai" in m for m in mods), mods


# ── the widening ──────────────────────────────────────────────────────────────────────────────

