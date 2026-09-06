"""L1.4.4-U1 · the closed vocabularies — the words the model is allowed to SAY.

Six frozen sets and nothing else runs in this file: no rule is read, no pack is loaded, no
clock is called and no model is asked. That emptiness is the unit.

**Why the sets live here and not next to the rules.** The previous extractor derived its
vocabulary from the rules' own `has_obs` clauses (`context/extract/vocab.py`, still in the
tree and still doing exactly that for the v1 lane). Two failures came out of it, and both are
recorded there in the module's own words:

* *"the model, given three examples and an ellipsis for `field`, invented 268 distinct field
  names in one org, 192 of them used exactly once"* — the sink had no shape, so the model made
  one up per message;
* *"rules read `deal.status` while the extractor, never told the name, wrote `status` — so the
  rule was dead on arrival"* — prompt and consumer disagreed about a name and nothing noticed.

The circularity is the deeper of the two. A vocabulary read off the rules can only ever ask
the model to look for a pattern somebody already wrote a rule for, which makes discovery
impossible by construction: the extractor's ceiling becomes the rule author's imagination.
So in v2 the extraction vocabulary is **independent of the rule vocabulary** — asserted as a
property of the source tree by `tests/capture/semantic/test_import_graph.py`, not as a promise
in a comment — and anything outside BOTH vocabularies goes down the Open Lane (L1.4.5) rather
than being forced into a field where it does not belong.

**Who reads this module.** The prompt's VOCAB block (doc 04, L1.4.2-U2 block 4) and its SCHEMA
block (`schema_gen.py`, which inlines these values as the allowed enums), the schema validator's
S-3 membership check (`capture/validate/schema.py::ExtractionVocabulary`, which takes the sets
as a PARAMETER precisely so this stays the only copy), the extraction cache key by way of
`vocabulary_fingerprint()`, and the promotion path (L1.4.5-U2), which is the only sanctioned way
a word is ever added: a human promotes a discovered `proposed_kind`, this file changes, the
fingerprint changes, and every extraction taken under the older wording stays keyed to the
wording that produced it instead of being reinterpreted by code that did not run.

The sets are `frozenset`, not `set`, and that is load-bearing rather than stylistic. A caller
who can `.add()` to a shared module constant changes what the prompt offers and what the
validator accepts for every tenant in the process, from anywhere, with no version bump and no
cache-key change — which is the same class of invisible drift as the two failures above.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from types import MappingProxyType

#: What the message is DOING. Doc 04, L1.4.4-U1, verbatim.
#:
#: Twelve verbs, and the set is deliberately about the speech act rather than about a domain: a
#: `negotiate` is a negotiate whether the subject is a contract, a hiring package or a delivery
#: date. Domain readings are Layer 3's job (`packs/`); putting `pricing_pushback` here would put
#: a sales word in the one place every tenant's extractor reads.
INTENT: frozenset[str] = frozenset({
    "inform", "request", "commit", "decide", "escalate", "schedule",
    "negotiate", "approve", "reject", "question", "acknowledge", "introduce",
})

#: What a named thing IS. `person` and `organization` carry the graph; `vendor` is kept separate
#: from `organization` because the relationship, not the entity, is what a later rule branches
#: on, and collapsing it loses the distinction at the only point it is legible.
ENTITY_TYPE: frozenset[str] = frozenset({
    "person", "organization", "vendor", "product", "document", "project",
})

#: Where a decision STANDS. `blocked` and `deferred` are separate on purpose: one names an
#: obstacle that can be cleared and the other names a choice to wait, and a reader that cannot
#: tell them apart cannot tell an escalation from a calendar entry.
DECISION_STATE: frozenset[str] = frozenset({
    "pending", "made", "blocked", "deferred", "abandoned",
})

#: What one thing is WAITING ON. Four kinds, matching the four things that actually block work
#: in a message stream: somebody must say yes, somebody must answer, somebody must ship,
#: somebody must choose.
DEPENDENCY_TYPE: frozenset[str] = frozenset({
    "approval", "information", "delivery", "decision",
})

#: The posture the text takes. `mixed` exists so the model has somewhere honest to put a message
#: that is warm about the product and cold about the price; without it the choice is one of the
#: two halves, and the half it drops is the one a human would have wanted.
STANCE: frozenset[str] = frozenset({
    "positive", "neutral", "cautious", "negative", "mixed",
})

#: Which profile ran. Doc 04, L1.4.2-U1 registers five; `structured` is the sixth and it is
#: NOT a profile the registry serves — it is the name the model-free bypass lane stamps on the
#: `ExtractionResult` it maps out of a CRM/DB/calendar row
#: (`capture/structured/mapper.py::STRUCTURED_PROFILE`, doc 03).
#:
#: GAP RESOLVED (cross-doc, flagged by W2 at that constant): doc 04's list has no `structured`
#: member, so a vocabulary built strictly from doc 04 fails S-3 on every row the bypass lane
#: produces — the one lane that is definitionally correct, since no model spoke. The alternative
#: the mapper names, filing a HubSpot deal under `crm_note`, is a lie about a typed column and
#: is not even a plausible one for a calendar event. The word is admitted here, which is where
#: the mapper's own comment says the fix belongs.
EXTRACTION_PROFILE: frozenset[str] = frozenset({
    "email", "chat", "transcript", "document", "crm_note", "structured",
})

#: Set name -> the set. The keys are exactly the field names of
#: `capture/validate/schema.py::ExtractionVocabulary`, so a caller wires the validator with
#: `ExtractionVocabulary(**vocabulary_sets())` and cannot mis-pair two frozensets of strings that
#: no type checker can tell apart. The pairing is asserted in `test_vocabulary.py` rather than by
#: importing the validator here: the prompt side must not depend on the validating side, or the
#: independence this module exists to establish is traded for a different coupling.
_SETS: Mapping[str, frozenset[str]] = MappingProxyType({
    "intent": INTENT,
    "entity_type": ENTITY_TYPE,
    "decision_state": DECISION_STATE,
    "dependency_type": DEPENDENCY_TYPE,
    "stance": STANCE,
    "extraction_profile": EXTRACTION_PROFILE,
})

#: THE THREE UNTYPED LANES, in the contract's own words. `ExtractionResult` declares `roles`,
#: `relationships` and `scheduling_proposals` as `list[dict[str, Any]]` and
#: `contracts/extraction.py::_open_lane_dicts` calls them "the three untyped lanes" verbatim.
#: The order is declaration order on the contract, which is what `UNTYPED_LANE_KEYS` below is
#: keyed by and what the guard iterates.
UNTYPED_LANES: tuple[str, ...] = ("roles", "relationships", "scheduling_proposals")

#: Lane -> the keys an entry in that lane may carry. **This is a closed vocabulary of FIELD
#: NAMES, and it is the missing half of this module.**
#:
#: The six sets above close what the model may SAY. These three close what it may NAME, and
#: without them the closure is decorative: an extraction whose `roles` entry reads
#: `{"deal_stage": "negotiation"}` passed every check in the validated lane — S-2 asked only
#: whether the key was a string, S-3 was never applied to a mapping list at all — and was cached
#: permanently in `l1_extraction_results` under a name no consumer reads. That is
#: `context/extract/vocab.py`'s recorded failure exactly: *268 distinct field names in one org,
#: 192 of them used exactly once*, restored inside the unit built to prevent it.
#:
#: **The members are read off the shipping consumer, never invented.** `context/pipeline.py` is
#: the only code in the tree that consumes these three lanes — it reads them off the v1
#: `Extraction`, which carries the same three lane names and is fed by the same prompt shape
#: (`context/extract/prompt.py` asks for exactly these keys). It reads `party` / `role` /
#: `evidence_text` off `roles` (writing the `party.role` fact), `party` / `nature` / `direction`
#: / `evidence_text` off `relationships` (the `relationship.nature` and `relationship.direction`
#: facts), and `proposer` / `text` / `evidence_text` off `scheduling_proposals`. A key outside
#: these is a key nothing downstream reads, which is why refusing it loses nothing and recording
#: it in the open lane gains the only thing that was ever available: evidence that the model
#: wanted a field we do not have.
#:
#: Closing them NOW, while `ExtractionResult`'s own copies of these lanes still have no consumer
#: at all, is the cheap moment to do it: there is no stored extraction whose keys have to be
#: migrated, and the first rule written against `roles` gets a name it can rely on.
#:
#: `evidence_text` is in all three because it is the receipt convention every one of the lanes
#: carries — the guard prefers it when it has to mint a probe span, so a refused key is cited
#: against the sentence the entry itself pointed at rather than against its own label.
#:
#: The lanes stay `list[dict[str, Any]]` on the contract (W0 is frozen, and the values are
#: genuinely open — a `text` is free text). Only the NAMES are closed, which is the half that
#: decides whether a rule can ever be written.
UNTYPED_LANE_KEYS: Mapping[str, frozenset[str]] = MappingProxyType({
    "roles": frozenset({"party", "role", "evidence_text"}),
    "relationships": frozenset({"party", "nature", "direction", "evidence_text"}),
    "scheduling_proposals": frozenset({"proposer", "text", "evidence_text"}),
})

#: Contract field/attribute name -> set name. `state` on `DecisionState` and `entity_type` on
#: `EntityMention` are nested one level down; the names are unique across every claim type, so
#: one flat table covers the result and its claims without per-type dispatch — the same reason
#: `capture/validate/schema.py` splits its two tables by that key and not by type.
FIELD_TO_SET: Mapping[str, str] = MappingProxyType({
    "intent": "intent",
    "stance": "stance",
    "extraction_profile": "extraction_profile",
    "entity_type": "entity_type",
    "state": "decision_state",
    "dependency_type": "dependency_type",
})

#: Bumped by hand whenever a word is added, removed or renamed — i.e. on every promotion. It is
#: human-readable provenance for a row; `vocabulary_fingerprint()` is the machine's copy and is
#: derived, so a promotion that forgets this constant still changes the cache key.
#:
#: "2" — `UNTYPED_LANE_KEYS` closed the three lanes that had no key vocabulary at all. That is
#: the same class of change as a promotion (what the prompt asks for moved), so the constant
#: moves with it and the fingerprint moves underneath both.
VOCABULARY_VERSION = "2"

#: Length of the hex digest `vocabulary_fingerprint()` returns. Twelve hex characters is 48 bits
#: — collision-free for a set of words a human curates, and short enough that the composite cache
#: key `org : prompt_version : schema_version : model : vocab_fingerprint : content` stays
#: readable in a log line, which is where a stale-cache diagnosis actually starts.
_FINGERPRINT_CHARS = 12


def vocabulary_sets() -> Mapping[str, frozenset[str]]:
    """The six closed sets, keyed by set name. Read-only view; the sets themselves are frozen.

    The one accessor every consumer uses, so that "which sets exist" has a single answer. A
    module that wants the intent set imports `INTENT`; a module that wants to hand ALL of them
    to something — the validator, the VOCAB block, the fingerprint — takes them from here and
    therefore picks up a seventh set on the day one is added instead of on the day somebody
    remembers to extend a list.
    """
    return _SETS


def untyped_lane_sets() -> Mapping[str, frozenset[str]]:
    """Lane name -> the closed key set for that lane. Read-only view; the sets are frozen.

    The counterpart of `vocabulary_sets()`, and deliberately a SEPARATE accessor rather than
    three more entries in `_SETS`. `capture/validate/schema.py::ExtractionVocabulary` is
    `extra="forbid"` over exactly six named fields and callers wire it with
    `ExtractionVocabulary(**vocabulary_sets())`; folding lane keys into that mapping would break
    every one of those call sites for the sake of a tidier-looking constant. The two kinds of
    closure are also not the same kind: those six say which WORD may fill a field, these three
    say which FIELD may exist, and the second is enforced by the sink guard (L1.4.5-U0) because
    W1's validator is frozen and has no rule for a mapping's key names.
    """
    return UNTYPED_LANE_KEYS


def vocabulary_fingerprint() -> str:
    """A stable 12-hex-character digest of every word in every set.

    Part of the `l1_extraction_results` key (doc 07, L1.7.3), and the reason a promotion cannot
    be silent: adding one word changes what the model was asked to look for, so every cached
    extraction taken under the old wording must stop answering for the new one. The recorded
    failure is exact — 260 cached extractions survived a prompt fix, the numbers did not move,
    and the conclusion drawn was that the fix had not worked.

    Deterministic across processes and runs: set names sorted, members sorted inside each set,
    so it depends on the WORDS and never on `PYTHONHASHSEED` or on the order they were typed.
    Renaming a set changes it too — a consumer keyed on set names is as affected by that as by a
    changed word.

    **The lane key sets are folded in as well**, under a `lane:` prefix that keeps them from
    colliding with a set of the same name. They belong here for the same reason the words do:
    they are part of what the prompt asks for and part of what the sink accepts, so an
    extraction taken before a lane key was added must not go on answering for a prompt that now
    offers it. The prefix is what lets a `roles` LANE and a hypothetical future `roles` SET
    coexist in one digest instead of silently overwriting each other.
    """
    material = "\n".join(
        [f"{name}={'|'.join(sorted(members))}" for name, members in sorted(_SETS.items())]
        + [f"lane:{name}={'|'.join(sorted(members))}"
           for name, members in sorted(UNTYPED_LANE_KEYS.items())]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:_FINGERPRINT_CHARS]


def vocabulary_block() -> str:
    """The prompt's VOCAB block (doc 04, L1.4.2-U2, block 4) — one line per closed set.

    Rendered here rather than typed into five prompt templates for the reason the whole module
    exists: five copies of a word list are five things that drift from the validator, and the
    drift shows up as correct extractions being rejected at S-3, which is the failure mode that
    is hardest to read backwards. `profiles.py` fills `{vocab}` with this string.

    Sorted, so the block — and therefore the prompt hash, and therefore the cache key — is the
    same on every machine.
    """
    lines = [
        "CLOSED VOCABULARIES — use these values exactly. Do not invent, abbreviate or "
        "pluralise them.",
    ]
    lines += [
        f"  {name}: {' | '.join(sorted(members))}"
        for name, members in sorted(_SETS.items())
    ]
    lines.append(
        "CLOSED OBJECT KEYS — these three lists hold objects, and an object may carry these "
        "keys and no others. Omit a key you have nothing for; never add one."
    )
    lines += [
        f"  {name}: {' | '.join(sorted(members))}"
        for name, members in sorted(UNTYPED_LANE_KEYS.items())
    ]
    lines.append(
        "If a value or a key you want is not on these lists, do NOT bend it to the nearest "
        "word and do NOT invent a field: record it in unclassified_observations with your own "
        "proposed_kind label."
    )
    return "\n".join(lines)


__all__ = ["DECISION_STATE", "DEPENDENCY_TYPE", "ENTITY_TYPE", "EXTRACTION_PROFILE",
           "FIELD_TO_SET", "INTENT", "STANCE", "UNTYPED_LANES", "UNTYPED_LANE_KEYS",
           "VOCABULARY_VERSION", "untyped_lane_sets", "vocabulary_block",
           "vocabulary_fingerprint", "vocabulary_sets"]
