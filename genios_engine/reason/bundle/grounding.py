"""What a narrative is ALLOWED to say — the material, and the vocabulary drawn from it.

Three jobs, and they are the three the gauntlet's hardest checks read from:

* **V-1 · grounding.** Every sentence must rest on something. `terms` is the set of words this
  decision's own material contains, so a sentence carrying none of them is a sentence about
  something else.
* **V-2 · citation fidelity.** `quotes` is the exact set of spans that may appear between quotation
  marks. L3 already proved each one byte-identical to the authored artifact twice, and
  `require_citation` proves it a third time inside the bundle constructor; this is where a
  PARAPHRASE — the failure V-2 is actually about — becomes detectable, because a quoted span that
  is not in this set was written by the model.
* **V-6 · scope.** `entities` and `addresses` are the proper names and addresses that exist in this
  situation. A name outside them was invented.

**One decision's material and nothing else.** Every field here is derived from the decision, its
units' results, and the context snapshot that decision was made from — all of which belong to one
tenant and one subject by construction. There is no query in this module, so there is no way for
another tenant's text, or another subject's, to enter a prompt: doc 09 case 7 asks for a structural
guard rather than a prompt-based one, and "the builder cannot reach anything else" is that guard.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from genios_engine.contracts.reasoning import (
    CandidateDisposition,
    ReasonerResult,
    ReasoningDecision,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.contracts.visibility import Visibility, narrowest

#: Reused verbatim from the explanation validator this gauntlet extends. Imported rather than
#: re-declared so that the two can never diverge — doc 08's retirement table says the one-sentence
#: cap's validator machinery is REUSED by the gauntlet, not deleted, and an identity test pins it.
from genios_engine.reason.intelligence import _ADDRESS_RE as ADDRESS_RE  # noqa: PLC2701

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
#: A proper name as a reader sees one: an ALL-CAPS acronym, or a capitalised token that is not the
#: first word of its sentence. Same boundary `intelligence._validated_explanation` draws, for the
#: same reason it gives — sentence casing capitalises the first word by construction.
_NAMEISH = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]*\b")

#: Depth limit when walking fact payloads for text. Facts nest a couple of levels
#: (`{"value": ..., "confidence": ...}`); anything deeper is structure, not vocabulary, and an
#: unbounded walk over an adversarial payload is a prompt builder that can be made to hang.
_MAX_DEPTH = 4


@dataclass(frozen=True, slots=True)
class Grounding:
    """Everything a bundle for this decision may rest on, quote, or name."""

    evidence_refs: tuple[str, ...] = ()
    citations: tuple[Mapping[str, Any], ...] = ()
    #: Every casefolded word the material contains. V-1's test is membership in this set.
    terms: frozenset[str] = frozenset()
    #: Quotable spans: the authored statements, byte-identical.
    quotes: tuple[str, ...] = ()
    #: Proper names present in the situation. V-6's allowlist.
    entities: frozenset[str] = frozenset()
    #: What the decision is ABOUT, in a word a sentence can carry: the context snapshot's root
    #: entity type ("deal", "account"). Read from the snapshot rather than from the capability id,
    #: because a capability is named after the READING ("renewal_risk") and a sentence that says
    #: "on this renewal risk" is naming the conclusion where it should be naming the subject.
    subject_type: str = "situation"
    addresses: frozenset[str] = frozenset()
    #: What the units actually found, in the order the prompt shows them.
    observations: tuple[Mapping[str, Any], ...] = ()
    #: The action the decision committed to, and the ones it did not.
    selected: Mapping[str, Any] = field(default_factory=dict)
    rejected: tuple[Mapping[str, Any], ...] = ()
    #: The narrowest audience of the evidence this narrative rests on. `derived_from` says
    #: "unstated" when nothing in the material carried one, which is honest rather than a
    #: confident "org".
    visibility: Visibility = field(default_factory=Visibility)

    def grounds(self, word: str) -> bool:
        return word.casefold() in self.terms


def _texts(value: Any, out: list[str], depth: int = 0) -> None:
    if depth > _MAX_DEPTH:
        return
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, Mapping):
        for key, item in value.items():
            out.append(str(key))
            _texts(item, out, depth + 1)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _texts(item, out, depth + 1)
    elif value is not None and not isinstance(value, bool):
        out.append(str(value))


def _visibility_of(payload: Any) -> Visibility | None:
    if not isinstance(payload, Mapping):
        return None
    raw = payload.get("visibility")
    if isinstance(raw, Visibility):
        return raw
    if isinstance(raw, Mapping):
        try:
            return Visibility(**dict(raw))
        except Exception:      # noqa: BLE001 — a malformed record is not an audience claim
            return None
    return None


def build_grounding(decision: ReasoningDecision, results: Sequence[ReasonerResult] = (), *,
                    request: ReasoningRequest | None = None) -> Grounding:
    """Assemble the material for ONE decision. Pure; no I/O; no clock."""
    material: list[str] = []
    subject_type = "situation"
    evidence_refs: set[str] = set()
    observations: list[Mapping[str, Any]] = []
    visibilities: list[Visibility] = []

    context = getattr(request, "context", None)
    if context is not None:
        _texts(dict(context.facts), material)
        for observation in context.observations:
            _texts(dict(observation), material)
            found = _visibility_of(observation)
            if found is not None:
                visibilities.append(found)
        _texts(dict(context.neighbor_facts), material)
        material.extend(str(item) for item in context.neighbor_observations)
        material.append(str(context.root_entity_id))
        material.append(str(context.root_entity_type))
        subject_type = str(context.root_entity_type).replace("_", " ").strip().lower() or "situation"

        for ref in context.evidence:
            evidence_refs.add(ref.evidence_id)
            material.append(str(ref.field))
            _texts(ref.value, material)
        found = _visibility_of(dict(context.metadata))
        if found is not None:
            visibilities.append(found)

    capability = getattr(request, "capability", None)
    plays = {play.play_id: play for play in getattr(capability, "plays", ()) or ()}
    if capability is not None:
        material.append(str(capability.goal.statement))
        material.extend(str(item) for item in capability.goal.success_criteria)
        for play in capability.plays:
            material.append(str(play.label))
            material.extend(str(step) for step in play.steps)

    # ── what the UNITS said. The observations block a narrator reads. ────────────────────────
    for result in results:
        if result.status != ResultStatus.COMPLETED:
            continue
        evidence_refs.update(result.evidence_ids)
        material.append(str(result.reasoner_id))
        material.extend(code.replace("_", " ") for code in result.reason_codes)
        for finding in result.findings:
            evidence_refs.update(finding.evidence_ids)
            material.append(finding.kind.replace("_", " "))
            _texts(dict(finding.metrics), material)
            material.extend(code.replace("_", " ") for code in finding.reason_codes)
            observations.append({
                "unit": result.reasoner_id, "finding": finding.kind,
                "matched": finding.matched, "value_bp": finding.value_bp,
                "metrics": dict(finding.metrics),
                "evidence_ids": list(finding.evidence_ids),
                "reason_codes": list(finding.reason_codes)})

    # ── what the DECISION committed to, and what it refused. ────────────────────────────────
    selected: dict[str, Any] = {}
    rejected: list[Mapping[str, Any]] = []
    eliminated_by: dict[str, list[Mapping[str, Any]]] = {}
    for applied in decision.constraints_applied or ():
        material.append(str(applied.get("rule_id")))
        if applied.get("statement"):
            material.append(str(applied["statement"]))
        for candidate_id in applied.get("eliminated_candidate_ids") or ():
            eliminated_by.setdefault(str(candidate_id), []).append({
                "rule_id": applied["rule_id"], "severity": applied.get("severity"),
                "statement": applied.get("statement")})

    for candidate in decision.candidates:
        play = plays.get(candidate.play_id)
        record = {
            "play_id": candidate.play_id,
            "label": str(play.label) if play is not None else candidate.play_id,
            "steps": [str(step) for step in getattr(play, "steps", ()) or ()],
            "disposition": candidate.disposition.value,
            "utility_bp": candidate.utility_bp,
            "rank_position": candidate.rank_position,
            "score_components": dict(candidate.score_components),
            "eliminated_by": eliminated_by.get(candidate.candidate_id, []),
        }
        material.append(record["label"])
        evidence_refs.update(candidate.evidence_ids)
        if candidate.candidate_id == decision.selected_candidate_id:
            selected = record
        else:
            rejected.append(record)
    rejected.sort(key=lambda item: (item["disposition"] != CandidateDisposition.ELIGIBLE.value,
                                    -int(item["utility_bp"]), item["play_id"]))

    material.append(str(decision.do_nothing_consequence))
    do_nothing = dict(decision.do_nothing or {})
    if do_nothing.get("statement"):
        material.append(str(do_nothing["statement"]))
    material.extend(str(item).replace("_", " ") for item in decision.uncertainty)

    quotes: list[str] = []
    for citation in decision.citations:
        statement = str(citation.get("statement") or "")
        if statement:
            quotes.append(statement)
            material.append(statement)
        material.append(str(citation.get("artifact_id")))
    for applied in decision.constraints_applied or ():
        statement = applied.get("statement")
        if statement:
            quotes.append(str(statement))

    blob = "\n".join(material)
    terms = frozenset(word.casefold() for word in _WORD.findall(blob.replace("_", " ")))
    addresses = frozenset(token.casefold() for token in ADDRESS_RE.findall(blob))
    entities = frozenset(
        token.casefold() for token in _NAMEISH.findall(blob)
        if (token.isupper() and len(token) > 1) or token[:1].isupper())

    return Grounding(
        evidence_refs=tuple(sorted(evidence_refs)),
        citations=tuple(decision.citations),
        terms=terms,
        quotes=tuple(dict.fromkeys(quotes)),
        entities=entities,
        addresses=addresses,
        subject_type=subject_type,
        observations=tuple(observations),
        selected=selected,
        rejected=tuple(rejected),
        # `narrowest()` over every audience the material declared. Nothing declared one -> the
        # default, whose `derived_from` says so rather than asserting "org".
        visibility=(narrowest(*visibilities) if visibilities
                    else Visibility(derived_from="unstated")),
    )


__all__ = ["ADDRESS_RE", "Grounding", "build_grounding"]
