"""Layer 4 · R-1 — the ambiguity interpreter. A reading, never a verdict.

    *"Considering moving some workloads"* is ambiguous. The model returns
    `{classification: EVALUATING_ALTERNATIVES, confidence_bp: 7000}` **as evidence**; a unit reads
    it like any other input; the formula decides. The model never says "this is urgent."

That paragraph is the Theory chat's law and it is the whole of this module's contract. Three
properties make it hold structurally rather than by intention:

**1 · IT RUNS BEFORE THE UNITS, NOT INSIDE THEM.** The interpreter takes a built
:class:`ReasoningRequest`, and returns a request whose snapshot carries one extra fact and one extra
evidence ref per reading. The orchestrator that runs afterwards is unchanged, still pure, still
clockless, still replayable — the model's output is an *input* to a deterministic computation, which
is the only shape in which a model may participate in a decision at all.

**2 · IT CANNOT RAISE CONFIDENCE.** Every interpretation ref is minted into the UNSTATED pool
(`independence_group="unattributed"`), which `decision_maker._stated_groups` deliberately excludes:
unstated origins may LOWER a confidence and can never raise one. Doc 09 case 11 asks that an
interpretation "never be the sole basis for a Rule 11 raise"; making it no basis at all is the
stronger reading and the only one enforceable from outside `decision_maker.py`. The reading is still
named on the record — `source_ref_id` carries `llm_interpretation:<model>` — so an auditor can see
exactly what it is; it simply cannot buy certainty.

**3 · ONE HOP, STRUCTURALLY.** An `interpretation.*` fact is never itself eligible for R-1
(doc 09 loop L-6). The namespace check is in :func:`find_ambiguities`, so the loop cannot be re-entered
by any caller, including a caller that hands back its own output.

WHAT "GENUINE AMBIGUITY" IS, IN CODE
------------------------------------
A site that fires on everything is a cost line; a site that fires on nothing is dead code. Layer 2's
precedent is exact and expensive: fifteen of twenty-one deep sales rules were dead because they gated
on a field only 9% of records carried, and the suite was green throughout. So the precondition here is
a conjunction of checks that are all READS OF THE REQUEST, and its fire rate is measured
(`scripts/ambiguity_fire_rate.py`) rather than assumed:

    1. the field is one the PLAN ACTUALLY READS — the declared inputs of the units this run
       scheduled, not the union of everything the capability could ever want;
    2. the field is not in the `interpretation.` namespace (the one-hop law);
    3. the field is not typed ABSENT — an absence is R-5's case and doc 09 case 13 refuses it here:
       a missing fact defers to a human, it is not interpreted;
    4. the value is free TEXT within a length band — too short to carry a stance, or long enough to
       be a document, and there is nothing to read;
    5. the text carries a HEDGE MARKER from a closed vocabulary — "considering", "might", "exploring".
       A settled sentence is not ambiguous, and paying a model to confirm that is the cost line;
    6. or the field is one Layer 1 recorded an UNRESOLVED CONFLICT about (`situation.conflict.<field>`
       with `resolution = unresolved_surface_both`) AND the contested field's own text is on this
       snapshot, so there is something to read rather than a disagreement to guess at;
    7. and at most :data:`MAX_FLAGS_PER_SITUATION` flags per situation, in a deterministic order.

WHAT THE MODEL MAY SAY
----------------------
One member of a CLOSED enum (:data:`CLASSIFICATIONS`) and one integer, capped at
:data:`MAX_INTERPRETATION_BP`. It may also say :data:`NOT_INTERPRETABLE`, and that answer is kept
rather than discarded — a model that cannot refuse will invent, and the refusal is the honest reading
of a sentence that carries no stance. Anything else is a :class:`SiteRejection`, one retry, then no
interpretation at all — never a default.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from genios_engine.contracts.reasoning import ContextSnapshot, EvidenceRef, ReasoningRequest
from genios_engine.platform.canonical import semantic_hash
from genios_engine.reason.adapters.situation_projection import CONFLICT_PREFIX
from genios_engine.reason.evidence import build_evidence_ref, observed_at_key
from genios_engine.reason.llm_sites import (
    SITE_R1,
    SiteRejection,
    run_site,
    with_correction,
)

# =================================================================================================
# THE VOCABULARY
# =================================================================================================

#: Everything R-1 writes lives under one prefix — so the snapshot can tell an interpretation from a
#: measurement without a list to keep in sync, and so the one-hop law is a string check.
INTERPRETATION_NAMESPACE = "interpretation."

#: The closed set of readings. A stance about a claim, never a judgement about a situation: there is
#: deliberately no `URGENT`, no `AT_RISK` and no `HIGH_PRIORITY` in this list, because those are
#: things the formula decides and a model that could say one of them would be scoring.
EVALUATING_ALTERNATIVES = "EVALUATING_ALTERNATIVES"
INTENT_STATED = "INTENT_STATED"
COMMITMENT_MADE = "COMMITMENT_MADE"
DECISION_MADE = "DECISION_MADE"
SPECULATION_ONLY = "SPECULATION_ONLY"
NOT_INTERPRETABLE = "NOT_INTERPRETABLE"

CLASSIFICATIONS = (EVALUATING_ALTERNATIVES, INTENT_STATED, COMMITMENT_MADE, DECISION_MADE,
                   SPECULATION_ONLY, NOT_INTERPRETABLE)

#: What each member means, in the words the prompt uses. Kept beside the enum rather than inside the
#: prompt string so the definition an auditor reads and the definition the model reads are one text.
CLASSIFICATION_MEANINGS: Mapping[str, str] = {
    EVALUATING_ALTERNATIVES: "the writer is weighing options and has not chosen",
    INTENT_STATED: "the writer says they intend to act, without committing to when or how",
    COMMITMENT_MADE: "the writer commits to a specific action",
    DECISION_MADE: "the writer reports a decision that has already been taken",
    SPECULATION_ONLY: "the writer raises a possibility without owning it",
    NOT_INTERPRETABLE: "the text carries no stance at all — say this rather than guessing",
}

#: An interpretation is never more certain than a measurement. 8000 bp is the same ceiling Layer 2
#: puts on a composed trend, and it is here for the same reason: a reading of somebody's words is
#: derived twice over, and a number that can reach 10000 will eventually be read as a fact.
MAX_INTERPRETATION_BP = 8_000

#: Doc 09 case 11's floor. Below this the model is telling us it could not read the text, and a
#: reading nobody believes is noise on the evidence layer rather than evidence.
MIN_INTERPRETATION_BP = 2_000

#: The hedge vocabulary. CLOSED and word-boundary matched: a marker list that grows by feel becomes a
#: site that fires on everything, and the fire rate is the measured property this module is judged on.
HEDGE_MARKERS = (
    "considering", "consider", "exploring", "explore", "evaluating", "evaluate",
    "might", "maybe", "perhaps", "possibly", "probably", "thinking about", "looking into",
    "leaning towards", "leaning toward", "open to", "not sure", "unsure", "tentative",
    "hoping to", "may need", "could be", "we'll see", "tbd", "to be confirmed",
    "soch rahe", "dekhte hain", "shayad",       # the corpus is Hinglish-bearing (doc 09 case 9)
)

_HEDGE = re.compile(
    r"(?<![\w])(" + "|".join(re.escape(marker) for marker in HEDGE_MARKERS) + r")(?![\w])",
    re.IGNORECASE)

#: A span shorter than this cannot carry a stance ("ok", "soon"); one longer than this is a document,
#: and a document handed to an interpreter is a summarisation task wearing an interpretation's name.
MIN_SPAN_CHARS = 24
MAX_SPAN_CHARS = 400

#: Doc 11 guard 7: R-1 fires "only on a genuine UNRESOLVED ambiguity the plan reads — never just in
#: case". Three per situation is the cost ceiling that makes the forecast (~12 interpretations/day on
#: a 40-decision tenant) hold even when a situation is unusually noisy.
MAX_FLAGS_PER_SITUATION = 3

#: `signal_conflicts.resolution` for a disagreement nobody settled — the closed vocabulary Layer 1
#: writes and Layer 2 projects. The other two members HAVE an answer, and interpreting a
#: disagreement we already resolved would be paying to re-open our own resolution.
UNRESOLVED_CONFLICT = "unresolved_surface_both"

AMBIGUITY_HEDGED = "hedged_statement"
AMBIGUITY_CONFLICT = "unresolved_conflict"
AMBIGUITY_KINDS = (AMBIGUITY_HEDGED, AMBIGUITY_CONFLICT)


# =================================================================================================
# THE PRECONDITION
# =================================================================================================

@dataclass(frozen=True, slots=True)
class AmbiguityFlag:
    """One genuinely ambiguous claim the plan reads: what it is, and the text that makes it so."""

    field: str
    kind: str
    span: str
    #: The content address of THIS CLAIM VERSION — doc 09 case 12's cache key. It covers the value,
    #: so a claim that changed is a different flag and gets its own interpretation; and it covers the
    #: observed-at key, so a superseded reading cannot be answered with the old one (case 14).
    digest: str
    observed_at: str
    fact_version_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in AMBIGUITY_KINDS:
            raise ValueError(f"unknown ambiguity kind {self.kind!r}")
        if not str(self.field).strip():
            raise ValueError("an ambiguity flag names a field")
        if not str(self.span).strip():
            raise ValueError("an ambiguity flag carries the text that is ambiguous")

    @property
    def interpretation_field(self) -> str:
        return f"{INTERPRETATION_NAMESPACE}{self.field}"


def plan_read_fields(request: ReasoningRequest, plan: Any = None) -> frozenset[str]:
    """The fields THIS RUN actually reads — the declared inputs of the units it scheduled.

    Given a plan, the answer is exactly the units that survived selection (doc 01 C1 drops an optional
    unit whose every declared input is absent, receipted). Without one it degrades to the capability's
    full declaration, which is a SUPERSET: a wider precondition can only make R-1 consider more text,
    never less, and every other check still applies. Being explicit about which of the two is in play
    is the difference between "the plan reads this" and "some manifest mentions it".
    """
    names: set[str] = set(request.capability.required_fields)
    names.update(request.capability.selection_fields)
    scheduled = None
    if plan is not None:
        scheduled = {str(step.reasoner_id) for step in getattr(plan, "steps", ())}
    for reasoner in request.capability.reasoners:
        if scheduled is not None and reasoner.reasoner_id not in scheduled:
            continue
        for field in reasoner.required_fields:
            names.add(field.split(":", 1)[1] if field.startswith("neighbor:") else field)
    for play in request.capability.plays:
        for condition in play.preconditions:
            field = str(condition.get("field") or "")
            if field:
                names.add(field)
    return frozenset(names)


def _fact_text(record: Any) -> str | None:
    """The free text of a fact, or None when the fact is not text.

    A number, a boolean and a structured reading are all UNAMBIGUOUS by construction — they were
    already resolved by the layer that wrote them — so only a string is a candidate, and only after
    the `value` unwrapping every reader in `reason/` performs.
    """
    value = record
    if isinstance(record, Mapping):
        if "value" not in record:
            return None
        value = record["value"]
    if isinstance(value, bool) or not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _conflicted_fields(facts: Mapping[str, Any]) -> frozenset[str]:
    """Fields Layer 1 recorded an UNRESOLVED disagreement about, off Layer 2's projection."""
    names: set[str] = set()
    for name, record in facts.items():
        if not name.startswith(CONFLICT_PREFIX):
            continue
        value = record.get("value") if isinstance(record, Mapping) else record
        if not isinstance(value, Mapping):
            continue
        if str(value.get("resolution") or "") != UNRESOLVED_CONFLICT:
            continue
        contested = str(value.get("field") or "").strip() or name[len(CONFLICT_PREFIX):]
        if contested:
            names.add(contested)
    return frozenset(names)


def fact_digest(*, org_id: str, entity_ref: str, field: str, value: Any, observed: str) -> str:
    """The content address of one claim version — R-1's cache key (doc 09 case 12)."""
    return semantic_hash({"org_id": str(org_id), "entity_ref": str(entity_ref), "field": str(field),
                          "value": value, "observed_at": str(observed)})


def find_ambiguities(request: ReasoningRequest, *, plan: Any = None) -> tuple[AmbiguityFlag, ...]:
    """The precondition, in full. Pure: no clock, no I/O, no model.

    Returns flags in a deterministic order (conflicted fields first — Layer 1 already told us those
    are contested — then by field name), capped at :data:`MAX_FLAGS_PER_SITUATION`. The cap is applied
    AFTER sorting so it is the same three flags on every run of the same snapshot, which is what makes
    the fire rate a property of the data rather than of dict ordering.
    """
    snapshot = request.context
    readable = plan_read_fields(request, plan)
    absent = set(snapshot.missing_fields)
    conflicted = _conflicted_fields(snapshot.facts)
    observed_by_field = {ref.field: observed_at_key(ref.occurred_at)
                         for ref in snapshot.evidence if ref.context_scope == "root"}
    version_by_field = {ref.field: ref.fact_version_id for ref in snapshot.evidence
                        if ref.context_scope == "root"}

    flags: list[AmbiguityFlag] = []
    for field, record in snapshot.facts.items():
        if field.startswith(INTERPRETATION_NAMESPACE):
            continue                        # doc 09 L-6 · one hop, structurally
        if field not in readable or field in absent:
            continue                        # not read by this plan, or typed absent (R-5's case)
        if f"{INTERPRETATION_NAMESPACE}{field}" in snapshot.facts:
            continue                        # already read once; one interpretation per claim version
        text = _fact_text(record)
        if text is None or not MIN_SPAN_CHARS <= len(text) <= MAX_SPAN_CHARS:
            continue
        contested = field in conflicted
        if not contested and not _HEDGE.search(text):
            continue                        # a settled sentence is not ambiguous
        observed = observed_by_field.get(field, observed_at_key(None))
        flags.append(AmbiguityFlag(
            field=field,
            kind=AMBIGUITY_CONFLICT if contested else AMBIGUITY_HEDGED,
            span=text,
            digest=fact_digest(org_id=request.org_id, entity_ref=snapshot.root_entity_id,
                               field=field, value=text, observed=observed),
            observed_at=observed,
            fact_version_id=version_by_field.get(field)))

    flags.sort(key=lambda flag: (flag.kind != AMBIGUITY_CONFLICT, flag.field))
    return tuple(flags[:MAX_FLAGS_PER_SITUATION])


# =================================================================================================
# THE READING
# =================================================================================================

@dataclass(frozen=True, slots=True)
class Interpretation:
    """One typed reading of one ambiguous claim, and the receipt for how it was obtained."""

    flag: AmbiguityFlag
    classification: str
    confidence_bp: int
    generation: str
    receipt: SiteReceipt

    def __post_init__(self) -> None:
        if self.classification not in CLASSIFICATIONS:
            raise ValueError(f"unknown interpretation classification {self.classification!r}")
        if isinstance(self.confidence_bp, bool) or not isinstance(self.confidence_bp, int):
            raise TypeError("interpretation confidence_bp must be an integer")
        if not MIN_INTERPRETATION_BP <= self.confidence_bp <= MAX_INTERPRETATION_BP:
            raise ValueError(
                f"interpretation confidence_bp must be between {MIN_INTERPRETATION_BP} and "
                f"{MAX_INTERPRETATION_BP} — a reading of somebody's words is derived twice over")

    @property
    def is_reading(self) -> bool:
        """Whether this says anything at all. `NOT_INTERPRETABLE` is an honest answer and a kept
        receipt, but it is not a fact and never reaches the snapshot."""
        return self.classification != NOT_INTERPRETABLE

    def as_fact(self) -> dict[str, Any]:
        """The snapshot record. `reading` states what the presence of this fact MEANS, in the shape
        Layer 2's projection uses, so a unit reading it cannot invent a direction nobody projected."""
        return {"value": {"classification": self.classification,
                          "confidence_bp": self.confidence_bp,
                          "span": self.flag.span,
                          "kind": self.flag.kind,
                          "field": self.flag.field},
                "source": "l4.llm_interpretation",
                "generation": self.generation,
                "kind": "interpretation",
                "reading": ("a model's typed reading of an ambiguous claim, offered as evidence; "
                            "it cannot raise confidence and it decides nothing")}


def _prompt(flag: AmbiguityFlag) -> str:
    """The whole prompt. Closed enum in, one JSON object out, and no room to volunteer a verdict.

    Note what is absent: the situation, the candidate plays, the score, the decision. The model is
    shown ONE sentence and asked what stance it takes — it cannot recommend, rank or prioritise
    because it is not told there is anything to recommend, rank or prioritise about.
    """
    options = "\n".join(f"  {name} — {CLASSIFICATION_MEANINGS[name]}" for name in CLASSIFICATIONS)
    return (
        "You are reading ONE sentence written by a business counterparty and classifying the "
        "stance it takes. You are not advising anyone and you are not assessing importance, "
        "urgency or risk.\n\n"
        f"FIELD: {flag.field}\n"
        f"TEXT: {flag.span}\n\n"
        "Choose exactly one classification:\n"
        f"{options}\n\n"
        "Answer with JSON and nothing else:\n"
        '{\"classification\": \"<one of the names above>\", \"confidence_bp\": <integer '
        f"{MIN_INTERPRETATION_BP}-{MAX_INTERPRETATION_BP}, how sure you are of the stance>}}\n"
        "If the text does not carry a stance, answer NOT_INTERPRETABLE. Do not guess.")


def _parse(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Step 6. Refuses; never repairs.

    A classification outside the enum is not coerced to the nearest member and a confidence outside
    the band is not clamped: both are the model doing something other than what it was asked, and a
    repaired answer is an answer nobody can audit. The site retries once and then produces no
    interpretation at all, which is the correct outcome — the ambiguity stays ambiguous and the
    deterministic half decides without it.
    """
    classification = str(payload.get("classification") or "").strip().upper()
    if classification not in CLASSIFICATIONS:
        raise SiteRejection("classification_outside_enum", classification[:60])
    raw = payload.get("confidence_bp")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise SiteRejection("confidence_not_numeric", str(raw)[:60])
    confidence = int(raw)
    if not MIN_INTERPRETATION_BP <= confidence <= MAX_INTERPRETATION_BP:
        raise SiteRejection("confidence_outside_band", str(confidence))
    return {"classification": classification, "confidence_bp": confidence}


def interpret(flag: AmbiguityFlag, *, org_id: str, gate: Any = None, cache: Any = None,
              subject_ref: str | None = None) -> Interpretation | None:
    """One flag through the gate. `None` when no reading was obtained, for ANY reason.

    None rather than a neutral classification, deliberately: a default reading would be a fact the
    model never stated, injected into the evidence layer where the formula would weigh it. The
    fallback for an interpretation is silence — the run proceeds exactly as it would have without
    R-1, which is also why the doctrine test passes with this site force-failed.
    """
    result = run_site(
        site=SITE_R1, org_id=org_id, seed={"digest": flag.digest, "kind": flag.kind},
        precondition=True,
        build_prompt=lambda feedback: with_correction(_prompt(flag), feedback), parse=_parse,
        fallback=dict,                    # silence: no reading, no fact, no evidence
        gate=gate, cache=cache, subject_ref=subject_ref)
    if result.fell_back or not result.payload:
        return None
    return Interpretation(flag=flag, classification=str(result.payload["classification"]),
                          confidence_bp=int(result.payload["confidence_bp"]),
                          generation=result.generation, receipt=result.receipt)


# =================================================================================================
# THE AUGMENTATION — how a reading enters the evidence layer
# =================================================================================================

#: Rule 11's unstated pool, spelled here rather than imported so this module does not depend on the
#: decision maker. A test pins the two strings equal; if `decision_maker.UNATTRIBUTED_GROUP` ever
#: changes, that test fails rather than this module silently becoming able to raise a confidence.
UNATTRIBUTED_GROUP = "unattributed"


def interpretation_evidence(*, org_id: str, root_entity_id: str,
                            interpretation: Interpretation) -> EvidenceRef:
    """The evidence ref for one reading, minted by the ONE builder.

    `independence_group` is the unstated pool ON PURPOSE — see the module docstring. `source_ref`
    names the model, which puts the reading's origin on the record AND separates its evidence id from
    the measured fact it was derived from, so the two can never be mistaken for two witnesses to one
    thing.
    """
    return build_evidence_ref(
        org_id=org_id,
        entity_ref=root_entity_id,
        field=interpretation.flag.interpretation_field,
        value=interpretation.as_fact()["value"],
        source_ref=f"llm_interpretation:{interpretation.generation}",
        observed_at=None,
        context_scope="root",
        fact_version_id=interpretation.flag.fact_version_id,
        confidence_bp=interpretation.confidence_bp,
        authority_rank=1,
        independence_group=UNATTRIBUTED_GROUP)


def augment(request: ReasoningRequest,
            interpretations: Sequence[Interpretation]) -> ReasoningRequest:
    """Fold readings into the request the orchestrator will execute.

    Returns the request UNCHANGED — the same object — when there is nothing to add. That identity is
    the doctrine test's whole mechanism: with R-1 failing, no interpretation exists, no fact is added,
    the `context_snapshot_id` does not move and the decision hashes to exactly what it hashed to on a
    no-LLM run.

    An interpretation that would overwrite an existing fact is DROPPED rather than merged. Two
    readings of one field cannot both be true and there is no rule that says which wins, so the one
    already on the snapshot — which a real measurement may have put there — stands.
    """
    readings = [item for item in interpretations if item is not None and item.is_reading]
    if not readings:
        return request
    snapshot = request.context
    facts = dict(snapshot.facts)
    evidence = list(snapshot.evidence)
    added = False
    for reading in readings:
        name = reading.flag.interpretation_field
        if name in facts:
            continue
        facts[name] = reading.as_fact()
        evidence.append(interpretation_evidence(
            org_id=request.org_id, root_entity_id=snapshot.root_entity_id,
            interpretation=reading))
        added = True
    if not added:
        return request
    receipt = tuple(sorted(
        f"{reading.flag.interpretation_field}:{reading.classification}:{reading.confidence_bp}"
        for reading in readings))
    metadata = {**dict(snapshot.metadata), "llm_interpretations": receipt}
    # `request_id` is DERIVED from request content (it names the context snapshot id), so it is
    # cleared and re-derived rather than carried: `dataclasses.replace` alone would hand the new
    # snapshot the old request's id and `ReasoningRequest.__post_init__` refuses that — correctly.
    # Obstacle 7 in the compiled-lane notes is the same rule seen from the other side: a request
    # may not be edited after the fact, so what happens here is that a NEW request is built, before
    # any unit has observed anything.
    return replace(request, request_id=None, context=ContextSnapshot(
        org_id=snapshot.org_id, graph_version=snapshot.graph_version,
        root_entity_id=snapshot.root_entity_id, root_entity_type=snapshot.root_entity_type,
        evaluation_time=snapshot.evaluation_time, selector_version=snapshot.selector_version,
        facts=facts, observations=snapshot.observations, neighbor_facts=snapshot.neighbor_facts,
        neighbor_observations=snapshot.neighbor_observations, edge_count=snapshot.edge_count,
        evidence=tuple(evidence), missing_fields=snapshot.missing_fields, metadata=metadata))


@dataclass(frozen=True, slots=True)
class AmbiguityInterpreter:
    """R-1 as one callable the reasoning lane can be handed — `interpreter(request) -> request`.

    Everything it needs is bound at construction (the policy, the client, the cache, the engine) so
    the lane that calls it neither knows nor decides anything about models. A lane that was given no
    interpreter behaves exactly as it does today, which is what makes this switch-on-able per tenant
    without a second code path.
    """

    org_id: str
    #: `reason/bundle/gate.RSiteGate` — the one C5 gate. `None` means no gate was wired, which is
    #: answered as "no model": the run proceeds uninterpreted rather than unpermitted.
    gate: Any = None
    cache: Any = None

    def readings(self, request: ReasoningRequest, *,
                 plan: Any = None) -> tuple[Interpretation, ...]:
        flags = find_ambiguities(request, plan=plan)
        out: list[Interpretation] = []
        for flag in flags:
            reading = interpret(
                flag, org_id=self.org_id, gate=self.gate, cache=self.cache,
                subject_ref=f"node:{request.context.root_entity_id}")
            if reading is not None:
                out.append(reading)
        return tuple(out)

    def __call__(self, request: ReasoningRequest, *, plan: Any = None) -> ReasoningRequest:
        return augment(request, self.readings(request, plan=(plan or _plan_for(request))))


def _plan_for(request: ReasoningRequest) -> Any:
    """This run's schedule, so the precondition means "the plan reads it" and not "a manifest
    mentions it".

    `ReasoningPlanner.plan` is pure — no clock, no I/O — so building one here costs nothing and
    changes nothing; the orchestrator builds its own from the same inputs and gets the same plan.
    A plan that REFUSES (the latency ceiling, doc 01 C2) leaves the precondition on the capability's
    declared superset, which can only widen what R-1 considers and never narrows it. It is not
    silently swallowed — the run about to happen will raise the same refusal from the orchestrator,
    which is where a refusal belongs.
    """
    try:
        from genios_engine.reason.plan import ReasoningPlanner
        return ReasoningPlanner().plan(request.capability, request)
    except Exception:      # noqa: BLE001 — see the docstring: the orchestrator re-raises this
        return None


def make_interpreter(*, org_id: str, engine: Any, record_cost: Any = None,
                     client: Any = None) -> AmbiguityInterpreter:
    """R-1 assembled for one tenant on a live lane: the real gate, the real cache, the T2 client.

    `client=None` builds one from settings, and settings without a key build nothing — in which case
    every flag falls back to silence and the lane reasons exactly as it does today. That is the same
    honest degradation the rest of the R-sites have: plainer output, never missing output.
    """
    from genios_engine.reason.llm_sites import (
        PostgresSiteCache,
        make_gate,
        make_site_client,
        tier_for,
    )
    return AmbiguityInterpreter(
        org_id=org_id,
        gate=make_gate(org_id=org_id, engine=engine, record_cost=record_cost,
                       client=(client if client is not None
                               else make_site_client(tier_for(SITE_R1)))),
        cache=PostgresSiteCache(engine=engine))


__all__ = ["AMBIGUITY_CONFLICT", "AMBIGUITY_HEDGED", "AMBIGUITY_KINDS", "AmbiguityFlag",
           "AmbiguityInterpreter", "CLASSIFICATIONS", "CLASSIFICATION_MEANINGS",
           "COMMITMENT_MADE", "DECISION_MADE", "EVALUATING_ALTERNATIVES", "HEDGE_MARKERS",
           "INTENT_STATED", "INTERPRETATION_NAMESPACE", "Interpretation",
           "MAX_FLAGS_PER_SITUATION", "MAX_INTERPRETATION_BP", "MAX_SPAN_CHARS",
           "MIN_INTERPRETATION_BP", "MIN_SPAN_CHARS", "NOT_INTERPRETABLE", "SPECULATION_ONLY",
           "UNATTRIBUTED_GROUP", "UNRESOLVED_CONFLICT", "augment", "fact_digest",
           "find_ambiguities", "interpret", "interpretation_evidence", "make_interpreter",
           "plan_read_fields"]
