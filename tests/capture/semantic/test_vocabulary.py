"""L1.4.4-U1 · the closed vocabularies — Wave W3, gate G3.

    pytest tests/capture/semantic/test_vocabulary.py -q

Doc 04's acceptance for this unit is four assertions — *each set is non-empty, lowercase,
snake_case, and frozen* — plus the import-graph one, which is a property of the source tree and
lives in `test_import_graph.py`. Each is a row below, per set, so a failure names the set rather
than the loop.

Three assertions here are NOT in the doc's list and are here because the sets have three
consumers that the doc names in prose and that nothing else checks:

* `capture/validate/schema.py::ExtractionVocabulary` takes all six sets as a keyword argument
  each. Its field names and `vocabulary_sets()`'s keys are two hand-written lists of the same
  six words, in two files, that no type checker compares — and if they disagree the validator is
  built with a `TypeError` at wiring time or, worse, with a set silently paired to the wrong
  field name. The bridge is asserted here rather than imported in the module, so the prompt side
  stays free of the validating side (that is the point of the whole unit);
* `capture/structured/mapper.py::STRUCTURED_PROFILE` stamps `"structured"` on every
  `ExtractionResult` the model-free bypass lane maps. Doc 04's five profiles do not contain that
  word, and the mapper's own comment says the fix belongs in this module — so the row below is
  what closes that cross-doc gap instead of leaving the one definitionally-correct lane failing
  S-3;
* the extraction cache key contains `vocab_fingerprint`. A digest that is not stable across
  processes silently re-extracts the world on every deploy, and a digest that does not move when
  a word is promoted serves 260 stale rows and hides the promotion completely — the recorded
  failure, in those numbers.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

from genios_engine.capture.semantic import vocabulary as vocab
from genios_engine.capture.semantic.vocabulary import (DECISION_STATE, DEPENDENCY_TYPE,
                                                       ENTITY_TYPE, EXTRACTION_PROFILE, INTENT,
                                                       STANCE, FIELD_TO_SET, vocabulary_block,
                                                       vocabulary_fingerprint, vocabulary_sets)
from genios_engine.capture.structured.mapper import STRUCTURED_PROFILE
from genios_engine.capture.validate.schema import ExtractionVocabulary
from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                EntityMention, ExtractionResult)

WAVE = "W3"
GATE = "G3"

#: `word`, `two_words`, `word2`. No leading digit, no double underscore, no trailing underscore —
#: every one of those is a shape that reads as snake_case to a human and sorts, groups or joins
#: differently to a consumer.
_SNAKE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")

#: The six sets by name, as the module exports them. Every row-per-set test iterates this, so a
#: seventh set added to `vocabulary_sets()` without a constant — or a constant that never reached
#: the accessor — fails immediately instead of being tested by nothing.
SETS = (
    ("intent", INTENT),
    ("entity_type", ENTITY_TYPE),
    ("decision_state", DECISION_STATE),
    ("dependency_type", DEPENDENCY_TYPE),
    ("stance", STANCE),
    ("extraction_profile", EXTRACTION_PROFILE),
)

#: Doc 04, L1.4.4-U1, copied word for word. Pinning the MEMBERS and not only their shape is the
#: difference between "somebody typed a set" and "the set the plan specified": a deleted word is
#: a prompt that stops offering a value the validator still accepts, and a nothing-fails silence
#: is exactly how `deal.status` and `status` drifted apart.
DOC_04_MEMBERS = {
    "intent": {"inform", "request", "commit", "decide", "escalate", "schedule",
               "negotiate", "approve", "reject", "question", "acknowledge", "introduce"},
    "entity_type": {"person", "organization", "vendor", "product", "document", "project"},
    "decision_state": {"pending", "made", "blocked", "deferred", "abandoned"},
    "dependency_type": {"approval", "information", "delivery", "decision"},
    "stance": {"positive", "neutral", "cautious", "negative", "mixed"},
}


@pytest.mark.gate
@pytest.mark.parametrize("name,members", SETS)
def test_every_closed_set_is_non_empty(name, members):
    """An empty closed set rejects every extraction that has the field — which reads as a broken
    extractor for as long as it takes somebody to find the empty frozenset."""
    assert members, f"{name} is empty"


@pytest.mark.gate
@pytest.mark.parametrize("name,members", SETS)
def test_every_member_is_lowercase_snake_case(name, members):
    """Case and separator are part of the value. `Approval` and `approval` are two words to every
    consumer that compares them, and the model copies whatever shape the prompt showed it."""
    bad = sorted(w for w in members if not isinstance(w, str) or not _SNAKE.match(w))
    assert not bad, f"{name} has non-snake_case members: {bad}"


@pytest.mark.gate
@pytest.mark.parametrize("name,members", SETS)
def test_every_set_is_frozen(name, members):
    """`frozenset`, not `set`. A caller who can mutate a shared module constant changes what the
    prompt offers and what S-3 accepts for every tenant in the process, with no version bump and
    no cache-key change."""
    assert isinstance(members, frozenset), f"{name} is {type(members).__name__}, not frozenset"
    with pytest.raises(AttributeError):
        members.add("smuggled")            # type: ignore[attr-defined]


@pytest.mark.gate
@pytest.mark.parametrize("name,expected", sorted(DOC_04_MEMBERS.items()))
def test_sets_hold_exactly_the_words_doc_04_specifies(name, expected):
    """The five sets doc 04 lists verbatim. `extraction_profile` is asserted separately: it is
    the one set the plan does not fully specify (see the `structured` row)."""
    assert set(vocabulary_sets()[name]) == expected


@pytest.mark.gate
def test_extraction_profile_holds_the_five_doc_04_profiles_and_the_bypass_lane():
    """The five registry profiles plus `structured`, which no profile serves.

    `capture/structured/mapper.py` maps a CRM/DB/calendar row into an `ExtractionResult` with no
    model involved and stamps `profile_id="structured"` so a stored row says which lane produced
    it. Without the word here, S-3 rejects the only lane that cannot hallucinate.
    """
    assert set(EXTRACTION_PROFILE) == {"email", "chat", "transcript", "document", "crm_note",
                                       STRUCTURED_PROFILE}


@pytest.mark.gate
def test_vocabulary_sets_keys_match_the_validators_six_arguments():
    """`ExtractionVocabulary(**vocabulary_sets())` must construct, now and after any promotion.

    Two hand-written lists of the same six names in two files. If they drift, wiring the S-3
    validator raises at startup — or pairs a set to the wrong field and rejects correct
    extractions for the field it was mis-paired with.
    """
    assert set(vocabulary_sets()) == set(ExtractionVocabulary.model_fields)
    built = ExtractionVocabulary(**vocabulary_sets())
    for name, members in SETS:
        assert getattr(built, name) == members


@pytest.mark.gate
def test_vocabulary_sets_is_a_read_only_view_over_the_frozen_sets():
    """The accessor may not become a back door around the frozen sets."""
    sets = vocabulary_sets()
    with pytest.raises(TypeError):
        sets["intent"] = frozenset({"anything"})    # type: ignore[index]


@pytest.mark.gate
@pytest.mark.parametrize("field,set_name", sorted(FIELD_TO_SET.items()))
def test_every_governed_field_names_a_real_contract_field_and_a_real_set(field, set_name):
    """`FIELD_TO_SET` is what the schema generator and the validator branch on. A key that is not
    a field of any claim type governs nothing, and a value that is not a set name raises a
    KeyError inside prompt generation."""
    declared = set(ExtractionResult.model_fields)
    for claim in (EntityMention, Commitment, DecisionState, Dependency):
        declared |= set(claim.model_fields)
    assert field in declared, f"{field!r} is not a field of ExtractionResult or of any claim type"
    assert set_name in vocabulary_sets(), f"{set_name!r} is not a closed set"


@pytest.mark.gate
def test_every_closed_set_that_governs_a_field_is_reachable_from_field_to_set():
    """All six sets govern a named field, `extraction_profile` included — the extractor stamps
    the profile onto the result and S-3 checks it there. A set that nothing maps to is a word
    list the prompt never shows and the validator never enforces."""
    assert set(FIELD_TO_SET.values()) == set(vocabulary_sets())


@pytest.mark.gate
def test_fingerprint_is_short_hex_and_identical_on_repeated_calls():
    first = vocabulary_fingerprint()
    assert first == vocabulary_fingerprint()
    assert len(first) == 12 and re.fullmatch(r"[0-9a-f]{12}", first)


@pytest.mark.gate
@pytest.mark.parametrize("label,mutate", [
    ("added word", lambda sets: {**sets, "intent": sets["intent"] | {"promoted_kind"}}),
    ("removed word", lambda sets: {**sets, "stance": sets["stance"] - {"mixed"}}),
    ("renamed set", lambda sets: {k if k != "stance" else "posture": v for k, v in sets.items()}),
])
def test_fingerprint_moves_when_the_vocabulary_moves(monkeypatch, label, mutate):
    """A promotion changes what the model was asked to look for, so it must change the cache key.

    The recorded failure is exact: 260 cached extractions survived a prompt fix, the numbers did
    not move, and the conclusion drawn was that the fix had not worked.
    """
    before = vocabulary_fingerprint()
    monkeypatch.setattr(vocab, "_SETS", mutate(dict(vocabulary_sets())))
    assert vocabulary_fingerprint() != before, f"fingerprint ignored a {label}"


@pytest.mark.gate
def test_fingerprint_does_not_depend_on_the_interpreters_hash_seed():
    """Frozensets iterate in hash order, and string hashing is randomised per process by default.

    A fingerprint derived from iteration order is stable inside one run — which is exactly long
    enough for a test suite to pass — and different in every worker, so the extraction cache
    misses on every deploy and the model is paid for twice.
    """
    env = {**os.environ, "PYTHONHASHSEED": "12345"}
    other = subprocess.run(
        [sys.executable, "-c",
         "from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint;"
         "print(vocabulary_fingerprint())"],
        capture_output=True, text=True, env=env, timeout=180)
    assert other.returncode == 0, other.stderr
    assert other.stdout.strip() == vocabulary_fingerprint()


@pytest.mark.gate
@pytest.mark.parametrize("name,members", SETS)
def test_prompt_vocab_block_shows_every_word_of_every_set(name, members):
    """The block is what fills `{vocab}` in all five templates. A word missing from it is a word
    the validator accepts and the model was never offered."""
    block = vocabulary_block()
    assert f"{name}:" in block
    for word in members:
        assert word in block, f"{name} member {word!r} missing from the VOCAB block"


@pytest.mark.gate
def test_prompt_vocab_block_sends_the_unmatched_value_to_the_open_lane():
    """The block must not merely list words — the instruction that stops the model bending an
    unlisted value to the nearest listed one is the reason the Open Lane gets anything at all."""
    block = vocabulary_block()
    assert "unclassified_observations" in block
    assert vocabulary_block() == block          # deterministic: it is part of the prompt hash
