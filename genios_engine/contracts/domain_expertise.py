"""Typed Layer 2 -> Layer 3 -> Layer 4 contracts.

The Domain Expertise compiler is deliberately a packaging boundary, not a reasoning surface.
It receives one already-qualified business situation, binds the smallest relevant authored and
runtime knowledge slice, and emits one immutable expertise package. The common Atlas envelope is
present under the same four names on both Layer 2 inputs and the Layer 3 output.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from genios_engine.contracts.validators import (
    freeze_mapping,
    freeze,
    require_bp,
    require_hash64,
    require_identifier,
    require_non_negative,
    require_aware,
    require_sorted_unique,
)
from genios_engine.contracts.visibility import Visibility
from genios_engine.platform.canonical import semantic_hash, stable_id

BUSINESS_SITUATION_VERSION = "business-situation.v1"
SITUATION_CONTEXT_VERSION = "situation-context.v1"

#: Schema v1 — every package written before the typed consumers existed.  STILL ACCEPTED, and it
#: has to be: `packs/compiler/expertise_builder.py` stamps this string literally and every row
#: already in `expertise_packages` carries it, so refusing it would take the live compiler down in
#: the name of a contract bump.  A v1 package may not carry any of the v2 additions — a reader
#: pinned to v1 does not know to read them, and knowledge nobody reads is inventory, not
#: intelligence (Law 4).
EXPERTISE_PACKAGE_VERSION_V1 = "expertise-package.v1"

#: Schema v2 — THE TYPED-CONSUMER SCHEMA, and the current version.  Carrying `compiled_constraints`,
#: `citations`, `framing_blocks`, `weld_receipt`, `pattern_id` or `matched_conditions` requires it;
#: and at v2 a package with expert rules must account for them in a weld receipt (V-3).  That pairing
#: is deliberate: the moment Y1 flips the builder to v2 is the moment consumption stops being
#: optional, which is the only forcing function Law 4 has.
EXPERTISE_PACKAGE_VERSION = "expertise-package.v2"

#: Both, and the reason the version check below is a membership test rather than an equality one.
SUPPORTED_EXPERTISE_PACKAGE_VERSIONS = (EXPERTISE_PACKAGE_VERSION_V1, EXPERTISE_PACKAGE_VERSION)


def _records(values: Any, label: str) -> tuple[Mapping[str, Any], ...]:
    records: list[Mapping[str, Any]] = []
    for value in values or ():
        if not isinstance(value, Mapping):
            raise TypeError(f"{label} entries must be mappings")
        records.append(freeze_mapping(value))
    return tuple(records)


def _visibility(value: Visibility | Mapping[str, Any]) -> Mapping[str, Any]:
    parsed = value if isinstance(value, Visibility) else Visibility.model_validate(dict(value))
    return freeze_mapping(parsed.model_dump())




# =================================================================================================
# E-01 · THE TYPED-CONSUMER VOCABULARY — what Layer 3's weld hands Layer 4, and how it is checked
# =================================================================================================
#
# Everything below is ADDITIVE. `ExpertisePackage` predates it, is good, and keeps every field it
# had; the five new fields all default to empty and an old-shaped package still constructs (V-4).
# What is new is that four of the corpus's five artifact classes finally have a SHAPE to travel in.
# Until now `reason/adapters/expertise.py` consumed `organization_rules` and nothing else, so 446
# of 712 authored artifacts — every rule, heuristic, mental model and decision framework — were
# retrieved, hashed and dropped. Law 4: knowledge is not shipped until L4 can consume it, typed.


def _verbatim(value: Any, label: str) -> str:
    """A quoted statement, kept EXACTLY as authored. Not stripped, not coerced.

    `require_text` strips, and a strip is the smallest possible paraphrase: the hash the catalog
    holds is over the authored bytes, so a trailing newline quietly removed here is a citation that
    fails V-1 for a reason nobody reading the two strings can see. A statement is therefore taken
    as authored and refused only when it is not text at all, or carries no visible character.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be the artifact's authored text")
    return value


def citation_statement_hash(statement: str) -> str:
    """The fingerprint V-1 compares — SHA-256 over the statement's exact UTF-8 bytes.

    This is how a contract with no access to the corpus still enforces byte-identity against it.
    Y1's citation binder computes this over the ARTIFACT's authored text and copies the digest onto
    the citation; this module computes it over the statement the citation actually carries. A
    paraphrase moves one and not the other, the two disagree, and the citation is refused at
    construction rather than reaching a card as an expert claim nobody made.

    BOTH SIDES MUST CALL THIS FUNCTION. A binder that hashes the whole YAML file, or a stripped
    statement, or a normalised one, is comparing two different things and proves nothing — so the
    function is exported, and the catalog-side digest is defined as its output rather than as "a
    hash of the artifact".
    """
    if not isinstance(statement, str):
        raise TypeError("a citation statement must be text")
    return hashlib.sha256(statement.encode("utf-8")).hexdigest()


#: Which artifact classes may be cited. The corpus's five, spelled the way `Domain Expertise/`
#: spells its directories, singularised. A class outside this tuple is an authoring mistake, and it
#: must surface here rather than as an empty render slot on a card.
CITATION_CLASSES = ("decision_framework", "heuristic", "mental_model", "playbook", "rule")

#: Which classes may become framing blocks. Mental models and decision frameworks are *ways of
#: reading* a situation; a heuristic is a claim, and a claim belongs in `citations`, quoted.
FRAMING_CLASSES = ("decision_framework", "mental_model")

#: CLG-06's two severities, and there is no third. `blocking` eliminates a candidate and is named
#: in `alternatives_rejected`; `warning` annotates and eliminates nothing.
CONSTRAINT_SEVERITIES = ("blocking", "warning")

#: What happened to one compiled rule on one decision. THREE outcomes, because predicate evaluation
#: is three-state and always has been (`context_adapter.py`): a rule whose `when` is UNKNOWN is
#: `unevaluable` — it does not fire and it does not block, and it must name what was missing.
#: Collapsing this to two outcomes is the coercion this codebase has spent months avoiding; with a
#: two-valued vocabulary, being honest is unrepresentable.
CONSTRAINT_OUTCOMES = ("fired", "satisfied", "unevaluable")

#: CLG-08's cap. Five citations per decision, ranked deterministically, truncation receipted.
MAX_CITATIONS = 5

#: THE ONE PREDICATE GRAMMAR, named on every compiled constraint.
#:
#: `compiled_constraints[*]["predicate_tree"]` is exactly the JSON that
#: ``genios_engine.context.analytic.cohort.predicate_json(parse_predicate(raw, registry=...))``
#: emits. That call is the grammar's ONLY entry point and the only place the operator whitelist
#: lives; Y1's rule compiler imports it rather than writing a parser.
#:
#: This module cannot import it, and the split that follows is deliberate rather than a second
#: grammar. `tests/test_layer_topology.py::test_contracts_import_nothing_above_platform` holds
#: `contracts/` to platform and stdlib, and `cohort` is Layer 2 — a contract importing upward would
#: invert the DAG the whole engine is built on. So:
#:
#:   * `cohort.parse_predicate` owns the VOCABULARY — which facts exist, which operators each fact
#:     kind can answer, how a value is normalised — and it raises at DEFINITION time.
#:   * `require_predicate_tree` below owns the SHAPE — a combinator node carries exactly one key, a
#:     condition carries exactly fact/op/value, `op` is a bare token and never an expression or a
#:     fragment of SQL, depth and width are bounded, and no float survives anywhere inside.
#:
#: `predicate_grammar` is required on every compiled constraint so the producer is named in the
#: data: a second grammar cannot appear without changing a string this contract refuses.
PREDICATE_GRAMMAR = "cohort.predicate.v1"

#: Mirrors of `cohort.MAX_PREDICATE_DEPTH` / `MAX_PREDICATE_TERMS`, for the reason above — the
#: shape check cannot import them. They are bounds, not vocabulary: a tree this check accepts and
#: the parser would reject is still refused by the parser, which is the strict side.
MAX_PREDICATE_DEPTH = 6
MAX_PREDICATE_TERMS = 24
_COMBINATORS = ("all", "any", "none")

#: Every counter a weld receipt must carry. ALL EIGHT, always, zero included — an absent counter is
#: an unaccounted one, and "every refusal named and counted" is invariant #6. Extra keys are
#: allowed (`by_class` and `refusals` are validated below); missing ones are not.
WELD_RECEIPT_COUNTERS = ("citations_attached", "citations_truncated", "plays_over_cap",
                         "plays_selected", "rules_compiled", "rules_fired", "rules_skipped",
                         "rules_unevaluable")


def require_predicate_tree(raw: Any, label: str, *, _depth: int = 0) -> Mapping[str, Any]:
    """The SHAPE half of the predicate contract — see `PREDICATE_GRAMMAR` for the split.

    Refuses anything that is not the JSON `cohort.predicate_json` emits. In particular it refuses a
    string: doc 03's hard rule is *"no eval(), no free expressions"*, and the way a free expression
    gets in is as text somebody means to evaluate later. `op` must be a bare identifier for the
    same reason — an operator carrying a space, a quote or a parenthesis is not an operator.
    """
    if _depth > MAX_PREDICATE_DEPTH:
        raise ValueError(f"{label} nests deeper than {MAX_PREDICATE_DEPTH} — a constraint nobody "
                         "can read is a constraint nobody can correct")
    if not isinstance(raw, Mapping):
        raise TypeError(f"{label} must be a predicate object, got {type(raw).__name__} "
                        "(a predicate is never a string — that is how a free expression gets in)")
    keys = set(raw)
    combinators = keys & set(_COMBINATORS)
    if combinators:
        if len(keys) != 1:
            raise ValueError(f"{label}: a combinator node carries exactly one key, "
                             f"got {sorted(keys)}")
        name = combinators.pop()
        terms = raw[name]
        if not isinstance(terms, (list, tuple)) or not terms:
            raise ValueError(f"{label}: {name!r} needs at least one term — an empty group matches "
                             "either everything or nothing, and which is not visible")
        if len(terms) > MAX_PREDICATE_TERMS:
            raise ValueError(f"{label}: {name!r} carries {len(terms)} terms "
                             f"(max {MAX_PREDICATE_TERMS})")
        for term in terms:
            require_predicate_tree(term, label, _depth=_depth + 1)
        return freeze(raw)
    if "fact" not in raw or "op" not in raw:
        raise ValueError(f"{label}: a condition needs 'fact' and 'op', got {sorted(keys)}")
    unknown = keys - {"fact", "op", "value"}
    if unknown:
        raise ValueError(f"{label}: unsupported keys on a condition: {sorted(unknown)}")
    require_identifier(raw["fact"], f"{label} fact")
    require_identifier(raw["op"], f"{label} operator")
    return freeze(raw)                     # `freeze` canonicalises, so V-5 covers the value too


def _quoted(record: Mapping[str, Any], label: str) -> None:
    """V-1, wherever a quote appears. A statement and its hash travel together or not at all.

    A statement without a hash is an unverifiable quote — the exact thing V-1 exists to make
    impossible — and a hash without a statement verifies nothing.
    """
    has_statement = "statement" in record
    has_hash = "statement_hash" in record
    if has_statement and not has_hash:
        raise ValueError(f"{label} carries a statement with no statement_hash — an unverifiable "
                         "quote is what V-1 exists to make impossible")
    if has_hash and not has_statement:
        raise ValueError(f"{label} carries a statement_hash with no statement — a fingerprint "
                         "with nothing to fingerprint verifies nothing")
    if not has_statement:
        return
    statement = _verbatim(record["statement"], f"{label} statement")
    declared = require_hash64(record["statement_hash"], f"{label} statement hash")
    if declared != citation_statement_hash(statement):
        raise ValueError(
            f"{label} statement does not match the authored artifact it claims to quote — a "
            "citation is QUOTED, never paraphrased (V-1). If the artifact itself changed, re-read "
            "it and re-hash it; do not restate it.")


def require_citation(value: Any, label: str = "citation") -> Mapping[str, Any]:
    """CLG-08's output: one authored claim, quoted, with the receipt that proves it was quoted.

    E5 is why this type exists. A card today bottoms out at play steps, so the expert claim that
    turns a fact into advice — *"warmth is close to uncorrelated with intent"* — is retrieved,
    hashed and discarded, and the card reads as a fact with a verb. A citation is that claim
    carried whole, with `statement_hash` making the carrying checkable.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    for key in ("artifact_id", "artifact_class", "statement", "statement_hash", "source_ref"):
        if key not in value:
            raise ValueError(f"{label} is missing {key!r}")
    require_identifier(value["artifact_id"], f"{label} artifact id")
    if value["artifact_class"] not in CITATION_CLASSES:
        raise ValueError(f"{label} artifact_class must be one of {CITATION_CLASSES}, "
                         f"got {value['artifact_class']!r}")
    require_identifier(value["source_ref"], f"{label} source ref")
    _quoted(value, label)
    return freeze_mapping(value)


def require_compiled_constraint(value: Any, label: str = "compiled constraint"
                                ) -> Mapping[str, Any]:
    """CLG-06's output: one authored rule compiled into something `core.constraint` can run.

    The corpus carries 46 rules with typed when/then and `severity: blocking`, and no parser has
    ever existed for them — so "blocking" rules block nothing, and a prescription can violate the
    corpus's own doctrine. This is the shape that ends that, and `severity` is the field that makes
    the ending real: `blocking` eliminates, `warning` annotates.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    for key in ("rule_id", "severity", "predicate_tree", "source_ref", "predicate_grammar"):
        if key not in value:
            raise ValueError(f"{label} is missing {key!r}")
    require_identifier(value["rule_id"], f"{label} rule id")
    if value["severity"] not in CONSTRAINT_SEVERITIES:
        raise ValueError(f"{label} severity must be one of {CONSTRAINT_SEVERITIES}, "
                         f"got {value['severity']!r}")
    if value["predicate_grammar"] != PREDICATE_GRAMMAR:
        raise ValueError(
            f"{label} declares grammar {value['predicate_grammar']!r}; the only predicate grammar "
            f"is {PREDICATE_GRAMMAR!r} (cohort.parse_predicate). A second grammar is not a new "
            "feature, it is a second place eval() can be reinvented.")
    require_predicate_tree(value["predicate_tree"], f"{label} predicate tree")
    require_identifier(value["source_ref"], f"{label} source ref")
    _quoted(value, label)
    return freeze_mapping(value)


def require_framing_block(value: Any, label: str = "framing block") -> Mapping[str, Any]:
    """A mental model or decision framework, carried as render/explanation INPUT MATERIAL.

    Never a new claim: a framing block says *how to read* a situation, and if it carries prose it
    carries it quoted, under the same V-1 check as a citation.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    for key in ("artifact_id", "artifact_class", "source_ref"):
        if key not in value:
            raise ValueError(f"{label} is missing {key!r}")
    require_identifier(value["artifact_id"], f"{label} artifact id")
    if value["artifact_class"] not in FRAMING_CLASSES:
        raise ValueError(f"{label} artifact_class must be one of {FRAMING_CLASSES}, "
                         f"got {value['artifact_class']!r} — a heuristic is a claim and belongs in "
                         "citations, where it is quoted")
    require_identifier(value["source_ref"], f"{label} source ref")
    _quoted(value, label)
    return freeze_mapping(value)


def require_constraint_application(value: Any, label: str = "constraint application"
                                   ) -> Mapping[str, Any]:
    """E-02's half: what one compiled rule DID on one decision.

    `unevaluable` is required to name what was missing, and that requirement is the point of the
    type. An unevaluable blocking rule must never silently pass OR silently block (doc 03, CLG-06
    step 4); a receipt that says "unevaluable" without saying which predicate was UNKNOWN is
    indistinguishable from one that guessed, so the contract refuses it.
    """
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    for key in ("rule_id", "severity", "outcome"):
        if key not in value:
            raise ValueError(f"{label} is missing {key!r}")
    require_identifier(value["rule_id"], f"{label} rule id")
    if value["severity"] not in CONSTRAINT_SEVERITIES:
        raise ValueError(f"{label} severity must be one of {CONSTRAINT_SEVERITIES}, "
                         f"got {value['severity']!r}")
    if value["outcome"] not in CONSTRAINT_OUTCOMES:
        raise ValueError(f"{label} outcome must be one of {CONSTRAINT_OUTCOMES}, "
                         f"got {value['outcome']!r}")
    if value["outcome"] == "unevaluable" and not require_sorted_unique(
            value.get("missing"), f"{label} missing predicate"):
        raise ValueError(
            f"{label} is unevaluable and names no missing predicate — an UNKNOWN rule that cannot "
            "say what it did not know is indistinguishable from one that guessed")
    eliminated = require_sorted_unique(value.get("eliminated_candidate_ids"),
                                       f"{label} eliminated candidate id")
    if eliminated and not (value["severity"] == "blocking" and value["outcome"] == "fired"):
        raise ValueError(f"{label} eliminates candidates but is {value['severity']}/"
                         f"{value['outcome']} — only a blocking rule that FIRED eliminates "
                         "anything")
    _quoted(value, label)
    return freeze_mapping(value)


def require_weld_receipt(value: Any, label: str = "weld receipt") -> Mapping[str, Any]:
    """Invariant #6: every refusal named and counted, per class.

    All eight counters, always, zero included. An absent counter is an unaccounted one, and the
    receipt is the only artifact that answers "what did the corpus contribute HERE" — the question
    this whole layer is an unlock plan for. The arithmetic is checked too: a rule cannot both fire
    and be unevaluable, so `fired + unevaluable` may not exceed `compiled`.
    """
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{label} must be a non-empty mapping")
    counts = {}
    for key in WELD_RECEIPT_COUNTERS:
        if key not in value:
            raise ValueError(f"{label} is missing the counter {key!r} — an absent counter is an "
                             "unaccounted one")
        counts[key] = require_non_negative(value[key], f"{label}.{key}")
    if counts["rules_fired"] + counts["rules_unevaluable"] > counts["rules_compiled"]:
        raise ValueError(f"{label} does not add up: {counts['rules_fired']} fired + "
                         f"{counts['rules_unevaluable']} unevaluable exceeds "
                         f"{counts['rules_compiled']} compiled")
    by_class = value.get("by_class")
    if by_class is not None:
        if not isinstance(by_class, Mapping):
            raise TypeError(f"{label}.by_class must be a mapping of artifact class to counters")
        for klass, per_class in by_class.items():
            if klass not in CITATION_CLASSES:
                raise ValueError(f"{label}.by_class names {klass!r}, which is not one of "
                                 f"{CITATION_CLASSES}")
            if not isinstance(per_class, Mapping):
                raise TypeError(f"{label}.by_class[{klass!r}] must be a mapping of counters")
            for key, count in per_class.items():
                require_non_negative(count, f"{label}.by_class[{klass!r}].{key}")
    refusals = value.get("refusals")
    if refusals is not None:
        if not isinstance(refusals, (list, tuple)):
            raise TypeError(f"{label}.refusals must be a sequence")
        for refusal in refusals:
            if not isinstance(refusal, Mapping):
                raise TypeError(f"{label}.refusals entries must be mappings")
            require_identifier(refusal.get("reason"), f"{label} refusal reason")
            require_non_negative(refusal.get("count"), f"{label} refusal count")
    return freeze_mapping(value)


def _typed_records(values: Any, label: str, validator) -> tuple[Mapping[str, Any], ...]:
    return tuple(validator(value, label) for value in (values or ()))




class BrainKind(str, Enum):
    EXPERT = "expert"
    ORGANIZATION = "organization"
    BEHAVIOR = "behavior"
    ADAPTIVE = "adaptive"


@dataclass(frozen=True, slots=True)
class BusinessSituationObject:
    """Layer 2's complete, immutable output to the Domain Expertise compiler."""

    org_id: str
    trace_id: str
    visibility: Visibility | Mapping[str, Any]
    id: str
    signal_ids: tuple[str, ...]
    type: str
    confidence_bp: int
    importance_bp: int
    evidence: tuple[Mapping[str, Any], ...]
    entities: tuple[Mapping[str, Any], ...] = ()
    relationships: tuple[Mapping[str, Any], ...] = ()
    timeline: tuple[Mapping[str, Any], ...] = ()
    dependencies: tuple[Mapping[str, Any], ...] = ()
    state: str = "active"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = BUSINESS_SITUATION_VERSION

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "org_id", require_identifier(self.org_id, "org id"))
        setter(self, "trace_id", require_identifier(self.trace_id, "trace id"))
        setter(self, "schema_version", require_identifier(
            self.schema_version, "business situation schema version"))
        if self.schema_version != BUSINESS_SITUATION_VERSION:
            raise ValueError(f"unsupported business situation schema {self.schema_version!r}")
        setter(self, "visibility", _visibility(self.visibility))
        setter(self, "id", require_identifier(self.id, "situation id"))
        setter(self, "signal_ids", require_sorted_unique(self.signal_ids, "signal id"))
        if not self.signal_ids:
            raise ValueError("a business situation requires at least one qualified signal")
        setter(self, "type", require_identifier(self.type, "situation type"))
        setter(self, "confidence_bp", require_bp(self.confidence_bp, "confidence_bp"))
        setter(self, "importance_bp", require_bp(self.importance_bp, "importance_bp"))
        setter(self, "evidence", _records(self.evidence, "situation evidence"))
        if not self.evidence:
            raise ValueError("a business situation requires evidence")
        setter(self, "entities", _records(self.entities, "situation entity"))
        setter(self, "relationships", _records(
            self.relationships, "situation relationship"))
        setter(self, "timeline", _records(self.timeline, "situation timeline"))
        setter(self, "dependencies", _records(self.dependencies, "situation dependency"))
        setter(self, "state", require_identifier(self.state, "situation state"))
        setter(self, "metadata", freeze_mapping(self.metadata))

    def to_semantic_dict(self) -> dict[str, Any]:
        """The package's CONTENT — what `expertise_id` and `semantic_hash` address.

        `trace_id` is deliberately absent, and its absence is the whole point of the method.
        A trace id identifies one OBSERVATION of a package, not the package: `domain_shadow`
        mints a fresh `new_id("trace")` per situation per sweep, so including it made every
        compile content-address to a brand-new id even when the situation, the knowledge, the
        graph version and every capability were byte-identical. The publisher's
        `on conflict (org_id, expertise_id) do nothing` then never fired, and each sweep wrote a
        fresh ~238 kB row per situation. On the design partner's database that reached 4,086 rows
        and 995 MB — 67% of the entire database, on a table holding 127 distinct situations — and
        the project crossed its disk quota into read-only, which stops every write the product
        makes, not just this one.

        The determinism test that should have caught this passes a CONSTANT `trace_id` from its
        fixture, so it proved the compiler deterministic in everything except the one field that
        is never constant in production. `test_a_repeat_compile_does_not_mint_a_new_package` drives
        it the way `domain_shadow` does, with a different trace id each time.

        The trace id is still stored — it has its own column, and it is what ties a package back to
        the sweep that observed it. It just does not participate in the content address, which is
        what "content-addressed" means.
        """
        return {
            "org_id": self.org_id,
            "schema_version": self.schema_version,
            "visibility": self.visibility,
            "id": self.id,
            "signal_ids": self.signal_ids,
            "type": self.type,
            "entities": self.entities,
            "relationships": self.relationships,
            "timeline": self.timeline,
            "dependencies": self.dependencies,
            "confidence_bp": self.confidence_bp,
            "importance_bp": self.importance_bp,
            "evidence": self.evidence,
            "state": self.state,
            "metadata": self.metadata,
        }

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())

    @property
    def domain_hints(self) -> tuple[str, ...]:
        raw = (self.metadata.get("domain_ids") or self.metadata.get("domains")
               or self.metadata.get("domain_id") or self.metadata.get("domain") or ())
        if isinstance(raw, str):
            raw = (raw,)
        return require_sorted_unique(raw, "domain hint")

    @property
    def brain_subject_keys(self) -> tuple[str, ...]:
        raw = self.metadata.get("brain_subject_keys") or ()
        return require_sorted_unique(raw, "brain subject key")


@dataclass(frozen=True, slots=True)
class SituationContextSlice:
    """The relevant Layer 2 graph slice supplied to Layer 3; never fetched by Layer 3."""

    org_id: str
    trace_id: str
    visibility: Visibility | Mapping[str, Any]
    id: str
    graph_version: int
    selector_version: str
    evaluation_time: datetime
    root_entity_ids: tuple[str, ...]
    facts: Mapping[str, Any] = field(default_factory=dict)
    observations: tuple[Mapping[str, Any], ...] = ()
    neighbor_facts: Mapping[str, Any] = field(default_factory=dict)
    neighbor_observations: tuple[str, ...] = ()
    edge_count: int = 0
    evidence: tuple[Mapping[str, Any], ...] = ()
    missing_fields: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = SITUATION_CONTEXT_VERSION

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "org_id", require_identifier(self.org_id, "context org id"))
        setter(self, "trace_id", require_identifier(self.trace_id, "context trace id"))
        setter(self, "schema_version", require_identifier(
            self.schema_version, "situation context schema version"))
        if self.schema_version != SITUATION_CONTEXT_VERSION:
            raise ValueError(f"unsupported situation context schema {self.schema_version!r}")
        setter(self, "visibility", _visibility(self.visibility))
        setter(self, "id", require_identifier(self.id, "context slice id"))
        if isinstance(self.graph_version, bool) or not isinstance(self.graph_version, int) \
                or self.graph_version < 0:
            raise ValueError("context graph_version must be a non-negative integer")
        setter(self, "selector_version", require_identifier(
            self.selector_version, "context selector version"))
        setter(self, "evaluation_time", require_aware(
            self.evaluation_time, "context evaluation_time"))
        setter(self, "root_entity_ids", require_sorted_unique(
            self.root_entity_ids, "context root entity id"))
        if not self.root_entity_ids:
            raise ValueError("a context slice requires at least one root entity")
        setter(self, "facts", freeze_mapping(self.facts))
        setter(self, "observations", _records(self.observations, "context observation"))
        setter(self, "neighbor_facts", freeze_mapping(self.neighbor_facts))
        setter(self, "neighbor_observations", require_sorted_unique(
            self.neighbor_observations, "context neighbor observation"))
        if isinstance(self.edge_count, bool) or not isinstance(self.edge_count, int) \
                or self.edge_count < 0:
            raise ValueError("context edge_count must be a non-negative integer")
        setter(self, "evidence", _records(self.evidence, "context evidence"))
        setter(self, "missing_fields", require_sorted_unique(
            self.missing_fields, "context missing field"))
        setter(self, "metadata", freeze_mapping(self.metadata))

    def to_semantic_dict(self) -> dict[str, Any]:
        """The slice's CONTENT — what `semantic_hash` addresses.

        Two fields the dataclass carries are deliberately absent, and both are observation
        metadata rather than content: `trace_id` (which sweep looked) and `evaluation_time`
        (when it looked). What the slice IS — the facts, observations, neighbours and edges of one
        anchor — is pinned exactly by `graph_version` and `selector_version`, which are here. Two
        sweeps over an unchanged graph see the same slice, and should hash to the same slice.

        This is not a cosmetic distinction. `context_slice_hash` is carried in the expertise
        package's metadata, so it feeds the PACKAGE's content address: while these two fields were
        hashed in, every sweep minted a new package id for unchanged knowledge, the publisher's
        `on conflict do nothing` never fired, and each sweep wrote a fresh ~238 kB row per
        situation. On the design partner's database that reached 4,086 rows and 995 MB — 67% of the
        whole database for 127 distinct situations — and the project crossed its disk quota into
        read-only, which stops every write the product makes, not only this one.

        Removing the clock from the slice's identity does NOT make reasoning time-blind: the
        evaluation time is passed to the reasoner in its own right, decisions and audit bundles are
        written per run, and the field remains on the dataclass for anyone reading a slice. It just
        does not decide whether this is the same slice.
        """
        return {
            "org_id": self.org_id,
            "schema_version": self.schema_version,
            "visibility": self.visibility,
            "id": self.id,
            "graph_version": self.graph_version,
            "selector_version": self.selector_version,
            "root_entity_ids": self.root_entity_ids,
            "facts": self.facts,
            "observations": self.observations,
            "neighbor_facts": self.neighbor_facts,
            "neighbor_observations": self.neighbor_observations,
            "edge_count": self.edge_count,
            "evidence": self.evidence,
            "missing_fields": self.missing_fields,
            "metadata": self.metadata,
        }

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())


@dataclass(frozen=True, slots=True)
class ExpertiseEvidence:
    """One receipt proving where a compiled knowledge item came from."""

    brain: BrainKind
    source_ref: str
    source_version: str
    content_hash: str
    confidence_bp: int
    visibility: Visibility | Mapping[str, Any]
    trace_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        setter = object.__setattr__
        if not isinstance(self.brain, BrainKind):
            setter(self, "brain", BrainKind(self.brain))
        setter(self, "source_ref", require_identifier(self.source_ref, "evidence source ref"))
        setter(self, "source_version", require_identifier(
            self.source_version, "evidence source version"))
        setter(self, "content_hash", require_hash64(self.content_hash, "evidence content hash"))
        setter(self, "confidence_bp", require_bp(self.confidence_bp, "evidence confidence_bp"))
        setter(self, "visibility", _visibility(self.visibility))
        setter(self, "trace_ids", require_sorted_unique(self.trace_ids, "source trace id"))
        setter(self, "metadata", freeze_mapping(self.metadata))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {
            "brain": self.brain,
            "source_ref": self.source_ref,
            "source_version": self.source_version,
            "content_hash": self.content_hash,
            "confidence_bp": self.confidence_bp,
            "visibility": self.visibility,
            "trace_ids": self.trace_ids,
            "metadata": self.metadata,
        }


#: The E-01 additions, in one place, because three separate checks read the same roster: the v1
#: guard, the semantic-dict inclusion, and the tests.  Adding a sixth field and forgetting one of
#: the three is exactly the kind of half-landed addition this tuple makes impossible.
_V2_ONLY_FIELDS = ("compiled_constraints", "citations", "framing_blocks", "weld_receipt",
                   "pattern_id", "matched_conditions")


@dataclass(frozen=True, slots=True)
class ExpertisePackage:
    """Layer 3's entire output.  Structured expertise only; no recommendation or decision."""

    org_id: str
    trace_id: str
    visibility: Visibility | Mapping[str, Any]
    id: str
    situation_id: str
    brain_snapshot_id: str
    capabilities: tuple[Mapping[str, Any], ...]
    objects: tuple[Mapping[str, Any], ...]
    expert_rules: tuple[Mapping[str, Any], ...]
    organization_rules: tuple[Mapping[str, Any], ...]
    behavior_patterns: tuple[Mapping[str, Any], ...]
    adaptive_preferences: tuple[Mapping[str, Any], ...]
    confidence_bp: int
    evidence: tuple[ExpertiseEvidence, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    # ── E-01 · typed-consumer outputs (doc 03) ──────────────────────────────────────────────
    #: CLG-06.  Authored `rules/` compiled into checks `core.constraint` can run.
    compiled_constraints: tuple[Mapping[str, Any], ...] = ()
    #: CLG-08.  Heuristics, models, frameworks and playbooks QUOTED — never paraphrased (V-1).
    citations: tuple[Mapping[str, Any], ...] = ()
    #: Mental models and decision frameworks as render/explanation input material.
    framing_blocks: tuple[Mapping[str, Any], ...] = ()

    # ── E-01 · consumption receipts ─────────────────────────────────────────────────────────
    #: "What did the corpus contribute HERE."  Required once this package is v2 and carries
    #: expert rules (V-3): consumption is accounted for, or it did not happen.
    weld_receipt: Mapping[str, Any] = field(default_factory=dict)

    # ── E-01 · Layer 2 v2 passthrough ───────────────────────────────────────────────────────
    #: The richer routing key L2 v2 hands L3 — a fired pattern rather than an anchor type — and
    #: the conditions that made it fire, which the Context Adapter conditions predicates on.
    pattern_id: str | None = None
    matched_conditions: tuple[Mapping[str, Any], ...] = ()

    schema_version: str = EXPERTISE_PACKAGE_VERSION

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "org_id", require_identifier(self.org_id, "org id"))
        setter(self, "trace_id", require_identifier(self.trace_id, "trace id"))
        setter(self, "schema_version", require_identifier(
            self.schema_version, "expertise package schema version"))
        if self.schema_version not in SUPPORTED_EXPERTISE_PACKAGE_VERSIONS:
            raise ValueError(f"unsupported expertise package schema {self.schema_version!r}")
        setter(self, "visibility", _visibility(self.visibility))
        setter(self, "id", require_identifier(self.id, "expertise id"))
        setter(self, "situation_id", require_identifier(self.situation_id, "situation id"))
        setter(self, "brain_snapshot_id", require_identifier(
            self.brain_snapshot_id, "brain snapshot id"))
        for name in ("capabilities", "objects", "expert_rules", "organization_rules",
                     "behavior_patterns", "adaptive_preferences"):
            setter(self, name, _records(getattr(self, name), name.replace("_", " ")))
        if not self.capabilities:
            raise ValueError("an expertise package requires at least one capability")
        if not self.objects:
            raise ValueError("an expertise package requires at least one knowledge object")
        setter(self, "confidence_bp", require_bp(self.confidence_bp, "confidence_bp"))
        setter(self, "evidence", tuple(sorted(self.evidence, key=lambda item: (
            item.brain.value, item.source_ref, item.content_hash))))
        if not self.evidence:
            raise ValueError("an expertise package requires evidence")
        setter(self, "metadata", freeze_mapping(self.metadata))
        setter(self, "compiled_constraints", _typed_records(
            self.compiled_constraints, "compiled constraint", require_compiled_constraint))
        setter(self, "citations", _typed_records(self.citations, "citation", require_citation))
        setter(self, "framing_blocks", _typed_records(
            self.framing_blocks, "framing block", require_framing_block))
        setter(self, "weld_receipt",
               require_weld_receipt(self.weld_receipt) if self.weld_receipt else freeze_mapping({}))
        if self.pattern_id is not None:
            setter(self, "pattern_id", require_identifier(self.pattern_id, "pattern id"))
        setter(self, "matched_conditions", _records(
            self.matched_conditions, "matched condition"))
        rule_ids = [c["rule_id"] for c in self.compiled_constraints]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("a rule is compiled once per package; a duplicate rule_id means two "
                             "constraints disagree about the same authored rule")
        # V-4 — the additive migration, enforced in the direction that can actually lie.  Old-shaped
        # packages construct freely; a v1 package CARRYING v2 content does not, because a consumer
        # pinned to v1 reads none of it and the package would claim a weld that never reached L4.
        if self.schema_version == EXPERTISE_PACKAGE_VERSION_V1:
            carried = [name for name in _V2_ONLY_FIELDS if getattr(self, name)]
            if carried:
                raise ValueError(
                    f"schema {EXPERTISE_PACKAGE_VERSION_V1} cannot carry {sorted(carried)} — the "
                    f"typed-consumer fields require {EXPERTISE_PACKAGE_VERSION}, and stamping them "
                    "onto v1 would ship knowledge no v1 reader looks at")
        # V-3 — consumption is always accounted for.  Scoped to v2 because v1 PREDATES the weld:
        # every package the live compiler writes today carries expert rules and no receipt, and a
        # contract that failed them would take the compiler down rather than fix the weld.
        elif self.expert_rules and not self.weld_receipt:
            raise ValueError(
                "an expertise package with expert rules and no weld_receipt is inventory, not "
                "intelligence — say what the corpus contributed here, zeros included (V-3)")
        if self.weld_receipt:
            # The receipt counts what actually shipped in THIS package, or it is decoration.
            if self.weld_receipt["rules_compiled"] != len(self.compiled_constraints):
                raise ValueError(
                    f"weld_receipt claims {self.weld_receipt['rules_compiled']} rules compiled but "
                    f"the package carries {len(self.compiled_constraints)} compiled constraints")
            if self.weld_receipt["citations_attached"] != len(self.citations):
                raise ValueError(
                    f"weld_receipt claims {self.weld_receipt['citations_attached']} citations "
                    f"attached but the package carries {len(self.citations)}")

    def to_semantic_dict(self) -> dict[str, Any]:
        """The package's CONTENT — what `expertise_id` and `semantic_hash` address.

        `trace_id` is deliberately absent, and its absence is the whole point of the method.
        A trace id identifies one OBSERVATION of a package, not the package: `domain_shadow`
        mints a fresh `new_id("trace")` per situation per sweep, so including it made every
        compile content-address to a brand-new id even when the situation, the knowledge, the
        graph version and every capability were byte-identical. The publisher's
        `on conflict (org_id, expertise_id) do nothing` then never fired, and each sweep wrote a
        fresh ~238 kB row per situation. On the design partner's database that reached 4,086 rows
        and 995 MB — 67% of the entire database, on a table holding 127 distinct situations — and
        the project crossed its disk quota into read-only, which stops every write the product
        makes, not just this one.

        The determinism test that should have caught this passes a CONSTANT `trace_id` from its
        fixture, so it proved the compiler deterministic in everything except the one field that
        is never constant in production. `test_a_repeat_compile_does_not_mint_a_new_package` drives
        it the way `domain_shadow` does, with a different trace id each time.

        The trace id is still stored — it has its own column, and it is what ties a package back to
        the sweep that observed it. It just does not participate in the content address, which is
        what "content-addressed" means.
        """
        body: dict[str, Any] = {
            "org_id": self.org_id,
            "schema_version": self.schema_version,
            "visibility": self.visibility,
            "id": self.id,
            "situation_id": self.situation_id,
            "brain_snapshot_id": self.brain_snapshot_id,
            "capabilities": self.capabilities,
            "objects": self.objects,
            "expert_rules": self.expert_rules,
            "organization_rules": self.organization_rules,
            "behavior_patterns": self.behavior_patterns,
            "adaptive_preferences": self.adaptive_preferences,
            "confidence_bp": self.confidence_bp,
            "evidence": self.evidence,
            "metadata": self.metadata,
        }
        # PRESENT-WHEN-CARRIED, not always.  Invariant #10 is package-churn suppression, and a
        # schema addition that unconditionally widened this dict would re-address every package in
        # `expertise_packages` for knowledge that did not change — the exact failure `e1a0c47`
        # stopped, at ~238 kB a situation.  A package carrying no v2 content therefore hashes
        # exactly as it did before this wave, and the one re-address the bump does cost is the
        # deliberate one Y1 spends when it flips the builder to v2.
        for name in _V2_ONLY_FIELDS:
            value = getattr(self, name)
            if value:
                body[name] = value
        return body

    @property
    def semantic_hash(self) -> str:
        return semantic_hash(self.to_semantic_dict())


def expertise_id(body: Mapping[str, Any]) -> str:
    """Content-address a package body before the id field itself exists.

    `trace_id` is dropped here rather than by the caller, because this is the ONE place every
    caller passes through and the builder's `body` is a hand-written dict that will be edited
    again. `ExpertisePackage.to_semantic_dict` makes the same exclusion for the same reason; the
    two must agree, or the id and the hash disagree about what the package is and the publisher's
    immutability check rejects a package identical to the one it already holds.

    See `to_semantic_dict` for what this cost: a fresh trace id per sweep meant a fresh id per
    sweep, `on conflict (org_id, expertise_id) do nothing` never fired, and unchanged knowledge
    was rewritten at ~238 kB a situation until the database went read-only.
    """
    return stable_id("expertise", {k: v for k, v in body.items() if k != "trace_id"})


__all__ = [
    "BUSINESS_SITUATION_VERSION",
    "SITUATION_CONTEXT_VERSION",
    "EXPERTISE_PACKAGE_VERSION",
    "EXPERTISE_PACKAGE_VERSION_V1",
    "SUPPORTED_EXPERTISE_PACKAGE_VERSIONS",
    "CITATION_CLASSES",
    "CONSTRAINT_OUTCOMES",
    "CONSTRAINT_SEVERITIES",
    "FRAMING_CLASSES",
    "MAX_CITATIONS",
    "MAX_PREDICATE_DEPTH",
    "MAX_PREDICATE_TERMS",
    "PREDICATE_GRAMMAR",
    "WELD_RECEIPT_COUNTERS",
    "BrainKind",
    "BusinessSituationObject",
    "ExpertiseEvidence",
    "ExpertisePackage",
    "SituationContextSlice",
    "citation_statement_hash",
    "expertise_id",
    "require_citation",
    "require_compiled_constraint",
    "require_constraint_application",
    "require_framing_block",
    "require_predicate_tree",
    "require_weld_receipt",
]
