"""CLG-08 · the citation binder — the expert's own words reach the decision, quoted.

THE DEFECT THIS CLOSES. 280 heuristics, 61 mental models and 59 decision frameworks are compiled
into every package and then dropped: `reason/adapters/expertise.py` consumed `organization_rules`
and nothing else, so the claim that turns a fact into advice — *"warmth is close to uncorrelated
with intent"* — was retrieved, content-hashed and discarded. What reached a card was a fact with a
verb. E5 asks every prescription to carry auditable reasoning; without this module the "why"
bottoms out at play steps, which are the WHAT.

WHAT TRAVELS, AND WHAT IS REFUSED TO TRAVEL:

  heuristic          -> a CITATION. A heuristic is a claim, so it is quoted, byte for byte, and
                        the contract's V-1 re-checks the quote against its own hash at the
                        package and again at the decision.
  mental_model       -> a FRAMING BLOCK. A way of READING the situation, handed to the explanation
  decision_framework    renderer as input material. Never a new claim — the contract refuses a
                        heuristic here for exactly that reason.
  rule               -> neither. A rule that fired already reaches the decision TYPED, as a
                        `constraints_applied` record carrying its statement and that statement's
                        hash (CLG-06). Citing it here as well would put one artifact on the card
                        twice under two names and would spend the five-citation budget on doctrine
                        that is already there with its outcome attached.
  playbook           -> neither. It is already consumed, as a play (CLG-07).

SELECTION IS TAG INTERSECTION, NOT SIMILARITY. MAP B of the Layer 3 doctrine: *"embeddings:
none"*. Everything refused is refused BY NAME and counted. The bar differs by what the artifact
will DO on the card, and the difference is the point:

  * A CITATION is quoted as a reason, so it must prove it is about THIS situation: the capability
    that owns it was routed AND its declared tags — the objects it reads, the situations it names,
    the patterns it operationalises — intersect this situation's.
  * A FRAMING BLOCK is a lens the renderer reads, never a claim, so a routed capability is enough.
    Mental models and decision frameworks in the shipped corpus declare no `objects_used` at all —
    "fit is a joint property" is a way of thinking, not a reader of facts — so requiring object
    overlap of them would refuse all 61 models and all 59 frameworks forever while the receipt
    reported a consumer that consumes nothing. Overlap still RANKS them; it just does not gate.

THE CAP IS A CAP, NOT A CUT. Five citations, ranked deterministically, truncation receipted. A
card with a bibliography is not more auditable than a card with five sources; it is less readable
and equally unfalsifiable.

CONTRADICTIONS ARE SURFACED, NEVER RESOLVED SILENTLY. The corpus authors 147 `contradicts` links
because, in the schema's own words, *"real expertise contains genuine tensions and hiding them
makes the brain read more confident than the profession is"*. Two rules that both fired and
contradict each other make Layer 4 ABSTAIN. A heuristic that contradicts a rule which fired is
DROPPED with a named refusal rather than quoted beside the doctrine it denies — the rule is
binding and the heuristic is a claim, and putting both on one card is how a card argues with
itself. A mental model in the same tension is KEPT: a lens denies nothing, so the disagreement is
surfaced rather than resolved by deleting one side of it.

ZERO LLM. Selection, ranking, truncation and conflict detection are all set arithmetic over
authored fields.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from genios_engine.contracts.domain_expertise import (
    MAX_CITATIONS,
    citation_statement_hash,
    require_citation,
    require_framing_block,
)

from .rule_compiler import RuleVerdict, artifact_class

#: How many framing blocks reach the explanation renderer. Three, and the number is this module's
#: own rather than the contract's: `MAX_CITATIONS` caps CLAIMS, which a card quotes, while a
#: framing block is a lens the renderer reads. Both are capped for the same reason — an unbounded
#: list is a truncation nobody receipted — and both truncations are counted.
MAX_FRAMING_BLOCKS = 3

#: Tag namespaces that count as OVERLAP. `capability:` is deliberately absent: it is the
#: eligibility gate, asked separately, and counting it would give every eligible artifact a free
#: point and flatten the ranking. `domain:` is absent for the same reason — every artifact in a
#: package shares it.
OVERLAP_PREFIXES = ("object:", "pattern:", "situation:")

#: What an artifact with no `last_updated` sorts as. Explicit rather than an empty string so the
#: reason it sorts last is legible at the comparison site.
UNDATED = "0000-00-00"


def _definition(record: Mapping[str, Any]) -> Mapping[str, Any]:
    definition = record.get("definition")
    return definition if isinstance(definition, Mapping) else {}


def _identity(record: Mapping[str, Any]) -> Mapping[str, Any]:
    identity = _definition(record).get("identity")
    return identity if isinstance(identity, Mapping) else {}


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if item)
    return ()


def situation_tags(package) -> frozenset[str]:
    """What THIS situation is about, in the same tag vocabulary artifacts declare themselves in.

    Everything here is a compile output, not a re-derivation: the routed capabilities, the
    situations that matched, the objects the route named plus the ones actually loaded, the
    domains, and — when Layer 2 v2 supplied them — the fired pattern and the conditions that made
    it fire. `matched_conditions` is empty on every package the current builder emits, so the
    `condition:` tags are the forward half of this function; the rest carry the selection today.
    """
    metadata = package.metadata or {}
    tags: set[str] = set()
    for capability in package.capabilities or ():
        if isinstance(capability, Mapping) and capability.get("id"):
            tags.add(f"capability:{capability['id']}")
    for situation_id in _strings(metadata.get("matched_situation_ids")):
        tags.add(f"situation:{situation_id}")
    for key in ("required_object_ids", "optional_object_ids"):
        for object_id in _strings(metadata.get(key)):
            tags.add(f"object:{object_id}")
    for obj in package.objects or ():
        if isinstance(obj, Mapping) and obj.get("id"):
            tags.add(f"object:{obj['id']}")
    for domain_id in _strings(metadata.get("domain_ids")):
        tags.add(f"domain:{domain_id}")
    if getattr(package, "pattern_id", None):
        tags.add(f"pattern:{package.pattern_id}")
    for condition in getattr(package, "matched_conditions", ()) or ():
        if not isinstance(condition, Mapping):
            continue
        for key in ("fact", "path", "has_obs", "no_obs"):
            if condition.get(key):
                tags.add(f"condition:{condition[key]}")
    return frozenset(tags)


def artifact_tags(record: Mapping[str, Any]) -> frozenset[str]:
    """What one authored artifact declares itself to be about.

    Every field read here is an id list the author wrote and `validate.py` already checks for link
    integrity, so a tag can never be a typo that quietly matches nothing: `objects_used`, the
    per-class `reads` lists, a rule's `spans`, a playbook's `when_to_use.situations`, a
    heuristic's `pattern_ref`.
    """
    definition = _definition(record)
    identity = _identity(record)
    tags: set[str] = set()
    if identity.get("owner_capability"):
        tags.add(f"capability:{identity['owner_capability']}")
    if identity.get("domain"):
        tags.add(f"domain:{identity['domain']}")
    for object_id in _strings(definition.get("objects_used")):
        tags.add(f"object:{object_id}")
    heuristic = definition.get("heuristic")
    if isinstance(heuristic, Mapping):
        for object_id in _strings(heuristic.get("reads")):
            tags.add(f"object:{object_id}")
        for pattern_id in _strings(heuristic.get("pattern_ref")):
            tags.add(f"pattern:{pattern_id}")
    rule = definition.get("rule")
    if isinstance(rule, Mapping):
        for object_id in _strings(rule.get("spans")):
            tags.add(f"object:{object_id}")
    for criterion in definition.get("criteria") or ():
        if isinstance(criterion, Mapping):
            for object_id in _strings(criterion.get("reads")):
                tags.add(f"object:{object_id}")
    for dimension in definition.get("dimensions") or ():
        if isinstance(dimension, Mapping):
            for object_id in _strings(dimension.get("objects")):
                tags.add(f"object:{object_id}")
    when_to_use = definition.get("when_to_use")
    if isinstance(when_to_use, Mapping):
        for situation_id in _strings(when_to_use.get("situations")):
            tags.add(f"situation:{situation_id}")
    return frozenset(tags)


def contradicts_of(record: Mapping[str, Any]) -> tuple[str, ...]:
    """The artifact ids this one declares itself in tension with.

    Read from the per-class block AND from the top level. Only `heuristic.contradicts` exists in
    the schema today; looking in both places means the day a rule or a framework is given the same
    field, the conflict detector reads it without a code change — and until then the second lookup
    costs one `.get`.
    """
    definition = _definition(record)
    declared: set[str] = set(_strings(definition.get("contradicts")))
    for block in ("heuristic", "rule", "mental_model", "decision_framework", "playbook"):
        value = definition.get(block)
        if isinstance(value, Mapping):
            declared.update(_strings(value.get("contradicts")))
    return tuple(sorted(declared))


def _last_updated(record: Mapping[str, Any]) -> str:
    metadata = _definition(record).get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("last_updated"):
        return str(metadata["last_updated"])
    return UNDATED


@dataclass(frozen=True, slots=True)
class _Selected:
    """One artifact that passed selection, with the numbers its rank is computed from."""

    artifact_id: str
    artifact_class: str
    statement: str
    source_ref: str
    overlap: int
    last_updated: str
    class_rank: int

    @property
    def sort_key(self) -> tuple[int, int, str, str]:
        """Deterministic and total. Class first (doctrine that fired outranks a rule of thumb),
        then tag overlap, then recency, then the artifact id — which is LAST, as the tie-break it
        is, never as the selector it used to be."""
        return (self.class_rank, -self.overlap, descending_date(self.last_updated),
                self.artifact_id)


def descending_date(value: str) -> str:
    """Sort an ISO date descending inside an ascending tuple, without a reverse pass.

    Dates are ISO, so lexicographic order is chronological; complementing each digit turns newest
    into smallest. Cheaper to read than a multi-pass sort, it keeps the whole rank key one tuple,
    and CLG-07 ranks capability recency with the same function so the two orderings cannot drift.
    """
    return "".join(chr(255 - ord(character)) if character.isdigit() else character
                   for character in value)


@dataclass(frozen=True, slots=True)
class CitationBinding:
    """CLG-08's output for one package: what was quoted, what framed it, what was refused."""

    citations: tuple[Mapping[str, Any], ...] = ()
    framing_blocks: tuple[Mapping[str, Any], ...] = ()
    citations_truncated: int = 0
    framing_truncated: int = 0
    refusals: Mapping[str, int] = field(default_factory=dict)
    by_class: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    #: Pairs of active artifacts that declare each other in tension, sorted and named.
    conflicts: tuple[Mapping[str, Any], ...] = ()
    #: True when two rules that BOTH fired contradict each other. Layer 4 abstains instead of
    #: applying one of them and calling it doctrine.
    abstain: bool = False


def bind_citations(package, verdicts: Sequence[RuleVerdict] = ()) -> CitationBinding:
    """CLG-08 over one package. Pure: no clock, no database, no model."""
    tags = situation_tags(package)
    routed = {tag for tag in tags if tag.startswith("capability:")}
    fired = {verdict.rule_id: verdict for verdict in verdicts if verdict.fired}

    refusals: dict[str, int] = {}
    by_class: dict[str, dict[str, int]] = {}

    def refuse(klass: str, reason: str) -> None:
        refusals[reason] = refusals.get(reason, 0) + 1
        by_class.setdefault(klass, {})
        by_class[klass][reason] = by_class[klass].get(reason, 0) + 1

    def count(klass: str, key: str) -> None:
        by_class.setdefault(klass, {})
        by_class[klass][key] = by_class[klass].get(key, 0) + 1

    citation_pool: list[_Selected] = []
    framing_pool: list[_Selected] = []

    for record in package.expert_rules or ():
        if not isinstance(record, Mapping):
            continue
        klass = artifact_class(record)
        artifact_id = str(record.get("id") or _identity(record).get("id") or "")
        if not artifact_id:
            continue
        if klass == "playbook":
            # Consumed as a play by CLG-07. Named so "5 of 5 classes have a consumer" is provable
            # from the receipt rather than from a reading of the code.
            count(klass, "consumed_as_play")
            continue
        if klass == "rule":
            # Consumed by CLG-06, and carried onto the decision by it. Counted both ways so the
            # receipt can be read as "the corpus's doctrine was compiled, and this much of it
            # applied" without opening the constraint list.
            count(klass, "consumed_as_compiled_constraint")
            if artifact_id in fired:
                count(klass, "fired")
            continue
        if klass not in ("heuristic", "mental_model", "decision_framework"):
            continue

        owner = f"capability:{_identity(record).get('owner_capability')}"
        if owner not in routed:
            refuse(klass, "capability_not_routed")
            continue
        overlap = _overlap(record, tags)
        if overlap < 1 and klass == "heuristic":
            refuse(klass, "no_tag_overlap")
            continue
        if klass == "heuristic" and set(contradicts_of(record)) & set(fired):
            # A CLAIM that denies doctrine which just fired does not travel beside it: the rule
            # binds, the heuristic argues with it, and a card carrying both argues with itself.
            # The tension is not lost — it is counted here and named in `conflicts`.
            #
            # Scoped to claims deliberately. A mental model or a framework in tension with a rule
            # is a LENS, not a counter-claim; it says how to read the situation and denies nothing,
            # so it stays and the disagreement is surfaced rather than resolved by deletion.
            refuse(klass, "contradicts_fired_rule")
            continue
        statement = _statement_of(record, klass)
        if statement is None:
            refuse(klass, "statement_missing")
            continue
        selected = _Selected(
            artifact_id=artifact_id, artifact_class=klass, statement=statement,
            source_ref=f"expert:{record.get('kind') or 'artifact'}:{artifact_id}",
            overlap=overlap, last_updated=_last_updated(record),
            class_rank=0 if klass == "heuristic" else 1)
        (citation_pool if klass == "heuristic" else framing_pool).append(selected)

    citation_pool.sort(key=lambda item: item.sort_key)
    framing_pool.sort(key=lambda item: item.sort_key)
    kept_citations, dropped_citations = citation_pool[:MAX_CITATIONS], citation_pool[MAX_CITATIONS:]
    kept_framing, dropped_framing = (framing_pool[:MAX_FRAMING_BLOCKS],
                                     framing_pool[MAX_FRAMING_BLOCKS:])
    for item in dropped_citations:
        refuse(item.artifact_class, "over_citation_cap")
    for item in dropped_framing:
        refuse(item.artifact_class, "over_framing_cap")

    citations = tuple(require_citation({
        "artifact_id": item.artifact_id,
        "artifact_class": item.artifact_class,
        "statement": item.statement,
        "statement_hash": citation_statement_hash(item.statement),
        "source_ref": item.source_ref,
        "tag_overlap": item.overlap,
    }, f"citation {item.artifact_id}") for item in kept_citations)
    framing_blocks = tuple(require_framing_block({
        "artifact_id": item.artifact_id,
        "artifact_class": item.artifact_class,
        "statement": item.statement,
        "statement_hash": citation_statement_hash(item.statement),
        "source_ref": item.source_ref,
        "tag_overlap": item.overlap,
    }, f"framing block {item.artifact_id}") for item in kept_framing)
    for item in kept_citations:
        count(item.artifact_class, "cited")
    for item in kept_framing:
        count(item.artifact_class, "framing")

    active = {verdict.rule_id: "fired_rule" for verdict in fired.values()}
    active.update({item["artifact_id"]: "citation" for item in citations})
    active.update({item["artifact_id"]: "framing_block" for item in framing_blocks})
    conflicts = named_conflicts(package, active)
    abstain = any(conflict["left_role"] == "fired_rule" and conflict["right_role"] == "fired_rule"
                  for conflict in conflicts)

    return CitationBinding(
        citations=citations,
        framing_blocks=framing_blocks,
        citations_truncated=len(dropped_citations),
        framing_truncated=len(dropped_framing),
        refusals=dict(sorted(refusals.items())),
        by_class={klass: dict(sorted(counts.items()))
                  for klass, counts in sorted(by_class.items())},
        conflicts=conflicts,
        abstain=abstain,
    )


def _overlap(record: Mapping[str, Any], tags: frozenset[str]) -> int:
    return len({tag for tag in artifact_tags(record) & tags
                if tag.startswith(OVERLAP_PREFIXES)})


def _statement_of(record: Mapping[str, Any], klass: str) -> str | None:
    """The verbatim text this class quotes, taken as authored — not stripped, not reflowed.

    A heuristic quotes its own `heuristic.statement`: that is the claim. A mental model or a
    decision framework quotes `purpose.statement`, which is what the model is FOR — its dimensions
    and criteria are structure, and flattening them into prose here would be this module writing
    the sentence instead of the author.
    """
    definition = _definition(record)
    if klass == "heuristic":
        block = definition.get("heuristic")
        value = block.get("statement") if isinstance(block, Mapping) else None
    else:
        purpose = definition.get("purpose")
        value = purpose.get("statement") if isinstance(purpose, Mapping) else None
    return value if isinstance(value, str) and value.strip() else None


def named_conflicts(package, active: Mapping[str, str]) -> tuple[Mapping[str, Any], ...]:
    """Every authored `contradicts` link between two artifacts that are BOTH active here.

    Symmetric and de-duplicated: the pair is named once, ordered by artifact id, so the same
    tension cannot be reported twice because both sides happened to declare it. `declared_by`
    records which side wrote the link, because "who says these disagree" is part of the finding.
    """
    by_id = {str(record.get("id") or ""): record for record in package.expert_rules or ()
             if isinstance(record, Mapping)}
    seen: set[tuple[str, str]] = set()
    conflicts: list[Mapping[str, Any]] = []
    for artifact_id, role in sorted(active.items()):
        record = by_id.get(artifact_id)
        if record is None:
            continue
        for other in contradicts_of(record):
            if other not in active:
                continue
            pair = tuple(sorted((artifact_id, other)))
            if pair in seen:
                continue
            seen.add(pair)
            left, right = pair
            conflicts.append({
                "left": left, "left_role": active[left],
                "right": right, "right_role": active[right],
                "declared_by": artifact_id,
            })
    return tuple(conflicts)


__all__ = [
    "CitationBinding",
    "MAX_FRAMING_BLOCKS",
    "OVERLAP_PREFIXES",
    "UNDATED",
    "artifact_tags",
    "bind_citations",
    "descending_date",
    "contradicts_of",
    "named_conflicts",
    "situation_tags",
]
