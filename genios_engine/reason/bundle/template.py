"""The deterministic fallback — doc 05 §6's "plainer, never less true", and labelled.

**This is not a stub, and K4 is why.** The gate's fallback rate is allowed to reach 15%, so roughly
one card in seven a founder reads on a bad day is this text. A placeholder-shaped apology would fail
that bar on the day the budget runs out, which is exactly the day the product has to still work. So
the template writes the same five sections a narrative writes, from the same computed numbers, in
plainer sentences — and labels itself `template_fallback` so nobody mistakes one for the other.

**It is built to survive its own gauntlet.** Every sentence is assembled from material that is in
the grounding by construction (unit ids, finding kinds, play labels, the decision's own counts) and
every number is a `{placeholder}` drawn from the catalogue — so V-1, V-4 and V-5 pass for structural
reasons rather than by luck. A sentence whose numbers are not in the catalogue is DROPPED rather
than written with a hole in it, which is why every builder below is a list-append guarded by
availability.

**Why no rule ids in prose.** Doc 05 §5's card prints "Admin corpus rule ADM-014", and that string
cannot appear in a prose field: `ADM-014` contains digits, V-4 refuses digits outside a placeholder,
and the constructor refuses them too. That is the right answer rather than an obstacle — a rule id
is a REFERENCE, not a sentence, and it travels in `citations` where a card renders it under
"Sources" and a client can link it. The prose says what the rule did; the citation says which rule.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from genios_engine.contracts.reasoning import (
    TEMPLATE_FALLBACK,
    BUNDLE_FIELD_CAPS,
    ReasoningBundle,
    ReasoningDecision,
    bare_numbers,
    placeholders,
)

from .grounding import Grounding
from .numbers import Catalogue

_UNSAFE = re.compile(r"[^a-z0-9]+")


def _slug(value: object) -> str:
    """The catalogue's naming, reused so a lookup key cannot drift from the key that was minted."""
    return _UNSAFE.sub("_", str(value or "").lower()).strip("_")

_PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]{0,63})\}")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")

#: How many unit findings the plain version names. Two is the number a reader holds; the rest are on
#: the card's evidence list, where they are countable rather than narrated.
MAX_NAMED_FINDINGS = 2
MAX_NAMED_ALTERNATIVES = 2


@dataclass(frozen=True, slots=True)
class _Sentence:
    text: str

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(_PLACEHOLDER.findall(self.text))


def _humanise(value: object) -> str:
    """`core.risk` -> `risk`; `deal_cooling` -> `deal cooling`. Lower case throughout, because a
    capitalised word mid-sentence is a proper name to V-6 and these are not names."""
    text = str(value or "").split(".")[-1]
    return text.replace("_", " ").replace("-", " ").strip().lower()


def _safe(text: str, catalogue: Catalogue) -> bool:
    """Would this sentence survive the constructor and the gauntlet's mechanical checks?

    Checked per sentence rather than per field so one unavailable number costs one clause instead of
    a whole section. `bare_numbers` is the contract's own detector: a play label or a finding kind
    that happens to contain a digit (`tier_2_escalation`) would otherwise put a digit in prose, and
    dropping the clause is better than refusing the bundle.
    """
    if bare_numbers(text):
        return False
    return all(name in catalogue for name in placeholders(text))


def _join(sentences: Sequence[_Sentence], catalogue: Catalogue, cap: int) -> str | None:
    kept: list[str] = []
    for sentence in sentences:
        text = sentence.text.strip()
        if not text or not _safe(text, catalogue):
            continue
        candidate = " ".join([*kept, text])
        if len(candidate) > cap:
            break
        kept.append(text)
    return " ".join(kept) if kept else None


def _reading(observation: Mapping[str, object]) -> str:
    """The shortest true phrase for WHAT a unit found.

    Measured against the shipped capability rather than assumed: `deal_cooling`'s units emit
    findings whose `kind` is the unit's own short name, so the obvious sentence comes out as "the
    relationship unit reported relationship" — a tautology on a customer's card. When the kind says
    nothing the unit's name has not already said, the unit's REASON CODE is what it actually found;
    when there is no reason code either, the finding has no describable content and is left to the
    magnitude sentence.
    """
    unit = _humanise(observation.get("unit"))
    kind = _humanise(observation.get("finding"))
    if kind and kind != unit:
        return kind
    for code in observation.get("reason_codes") or ():
        phrase = _humanise(code)
        if phrase and phrase != unit:
            return phrase
    return ""


def _kinds(grounding: Grounding, limit: int = 3) -> list[str]:
    seen: list[str] = []
    for observation in grounding.observations:
        kind = _reading(observation)
        if kind and kind not in seen:
            seen.append(kind)
        if len(seen) >= limit:
            break
    return seen


def _phrase(items: Sequence[str]) -> str:
    """`a`, `a and b`, `a, b and c`. No Oxford comma and no digits — a list joined with "3 items"
    would put a number in prose that no placeholder covers."""
    items = [item for item in items if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def build_template(decision: ReasoningDecision, *, catalogue: Catalogue,
                   grounding: Grounding) -> dict[str, str]:
    """The five sections (plus alternatives when there are any), as plain prose with placeholders."""
    selected = dict(grounding.selected or {})
    label = str(selected.get("label") or selected.get("play_id") or "the recommended action")
    label_lower = _humanise(label) or "the recommended action"
    kinds = _kinds(grounding)
    # The SUBJECT, not the reading. `capability_id` is named after the conclusion
    # ("expertise.renewal_risk"), so a sentence built from it says "on this renewal risk" where it
    # should say "on this deal". The snapshot's root entity type is the subject; the capability is
    # the fallback only when there is no snapshot.
    subject = grounding.subject_type or _humanise(
        getattr(decision, "capability_id", "")) or "situation"

    out: dict[str, str] = {}

    # ── headline · the card title. A title, not a sentence: no terminal stop is required of it. ──
    headline = label if len(label) <= BUNDLE_FIELD_CAPS["headline"] else label_lower
    if kinds and len(headline) + len(kinds[0]) + 3 <= BUNDLE_FIELD_CAPS["headline"]:
        headline = f"{headline} — {kinds[0]}"
    if len(headline.strip()) < 12:
        headline = f"{headline} — {subject}"[:BUNDLE_FIELD_CAPS["headline"]]
    out["headline"] = headline[:BUNDLE_FIELD_CAPS["headline"]].strip()

    # ── situation_summary · what is happening, in the units' own words. ─────────────────────────
    summary = [_Sentence(f"The reasoning units reported {_phrase(kinds)} on this {subject}.")
               if kinds else
               _Sentence(f"The reasoning units completed on this {subject} with no exception "
                         "reported.")]
    weighed = catalogue.by_name.get("alternatives_considered", 0)
    if weighed:
        # Singular and plural are two sentences, because "1 other actions" is the kind of seam a
        # reader notices immediately and stops trusting the rest of the card over.
        summary.append(_Sentence(
            "{alternatives_considered} other action was weighed against the recommendation."
            if weighed == 1 else
            "{alternatives_considered} other actions were weighed against the recommendation."))
    if "evidence_coverage_pct" in catalogue:
        summary.append(_Sentence(
            "Evidence coverage on the facts this decision needed was "
            "{evidence_coverage_pct} percent."))
    out["situation_summary"] = _join(summary, catalogue,
                                     BUNDLE_FIELD_CAPS["situation_summary"]) or (
        f"The reasoning units completed on this {subject}.")

    # ── why_it_matters · the consequence, priced where E4 priced it. ────────────────────────────
    matters: list[_Sentence] = []
    if "do_nothing_cost_bp" in catalogue:
        matters.append(_Sentence(
            "Not acting carries a priced exposure of {do_nothing_cost_bp} basis points."))
    if "do_nothing_horizon_days" in catalogue:
        matters.append(_Sentence(
            "That exposure is fully realised within {do_nothing_horizon_days} days."))
    consequence = str(decision.do_nothing_consequence or "").strip()
    if not matters and consequence and _safe(consequence, catalogue):
        matters.append(_Sentence(consequence if consequence.endswith((".", "!", "?"))
                                 else consequence + "."))
    if "recommended_score_pct" in catalogue:
        matters.append(_Sentence(
            "This decision ranks at {recommended_score_pct} percent against the other open "
            "decisions on this account."))
    out["why_it_matters"] = _join(matters, catalogue, BUNDLE_FIELD_CAPS["why_it_matters"]) or (
        f"The reasoning found {_phrase(kinds) or 'a condition'} that changes what should happen "
        f"on this {subject}.")

    # ── root_cause · which reading drove it, and how big that reading was. ──────────────────────
    cause: list[_Sentence] = []
    for observation in grounding.observations[:MAX_NAMED_FINDINGS]:
        unit = _humanise(observation.get("unit"))
        if not unit:
            continue
        reading = _reading(observation)
        # The catalogue names a magnitude with the unit's FULL id slugged (`core.risk` ->
        # `core_risk`), while the prose wants the short human form (`risk`). Building the lookup
        # key from the prose form is how a magnitude that exists gets silently dropped.
        magnitude = f"{_slug(observation.get('unit'))}_{_slug(observation.get('finding'))}_bp"
        if magnitude in catalogue and reading:
            cause.append(_Sentence(
                f"The {unit} unit read {reading} at {{{magnitude}}} basis points."))
        elif magnitude in catalogue:
            cause.append(_Sentence(
                f"The {unit} unit measured this {subject} at {{{magnitude}}} basis points."))
        elif reading:
            cause.append(_Sentence(f"The {unit} unit reported {reading}."))
        else:
            cause.append(_Sentence(f"The {unit} unit's reading fired on this {subject}."))
    if "independent_evidence_groups" in catalogue:
        cause.append(_Sentence(
            "{independent_evidence_groups} independent sources of evidence agree on that reading."))
    out["root_cause"] = _join(cause, catalogue, BUNDLE_FIELD_CAPS["root_cause"]) or (
        f"The decision rests on {_phrase(kinds) or 'the evidence recorded against this subject'} "
        f"reported by the reasoning units on this {subject}.")

    # ── recommendation_rationale · the ONE field allowed to instruct. ───────────────────────────
    rationale = [_Sentence(f"Recommended: {label_lower}.")]
    if "score_gap_bp" in catalogue and catalogue.by_name["score_gap_bp"]:
        rationale.append(_Sentence(
            "It ranked {score_gap_bp} basis points ahead of the next best action on the same "
            "axes."))
    if "alternatives_eliminated" in catalogue and catalogue.by_name["alternatives_eliminated"]:
        rationale.append(_Sentence(
            "{alternatives_eliminated} of the alternatives were removed outright by an authored "
            "rule, quoted in the sources on this card."))
    if "confidence_pct" in catalogue:
        rationale.append(_Sentence(
            "The engine holds this at {confidence_pct} percent confidence."))
    out["recommendation_rationale"] = _join(
        rationale, catalogue, BUNDLE_FIELD_CAPS["recommendation_rationale"]) or (
        f"Recommended: {label_lower}, which ranked first on the recorded axes.")

    # ── expected_effect · what changes, and the do-nothing contrast. ────────────────────────────
    effect: list[_Sentence] = []
    if "outcome_window_days" in catalogue:
        effect.append(_Sentence(
            "The effect of acting should be visible within {outcome_window_days} days."))
    if "do_nothing_cost_bp" in catalogue:
        effect.append(_Sentence(
            "Doing nothing leaves the priced exposure of {do_nothing_cost_bp} basis points "
            "standing."))
    if "do_nothing_cost_bp" not in catalogue:
        # E4's computed cost is not on every decision yet, and a card whose EXPECTED EFFECT has no
        # do-nothing half is half a card — doc 05 §5 closes on the contrast and K4's founder-bar row
        # is measured on it. So the contrast is always present; when there is no priced number it
        # says what it can say, which is that the condition stands.
        effect.append(_Sentence(
            f"Doing nothing leaves this {subject} where the units found it."))
    if "decision_expires_in_days" in catalogue:
        effect.append(_Sentence(
            "This reading holds for {decision_expires_in_days} days, after which the situation is "
            "reasoned again from fresh evidence."))
    out["expected_effect"] = _join(effect, catalogue, BUNDLE_FIELD_CAPS["expected_effect"]) or (
        "Acting resolves the condition the units reported; leaving it stands the exposure the "
        "decision recorded.")

    # ── alternatives_narrative · only when something actually lost. ─────────────────────────────
    losers: list[str] = []
    for rejected in grounding.rejected[:MAX_NAMED_ALTERNATIVES]:
        name = _humanise(rejected.get("label") or rejected.get("play_id"))
        if name:
            losers.append(name)
    if losers:
        alternatives = [_Sentence(
            f"{_phrase(losers).capitalize()} was rejected: it ranked lower on the same axes."
            if len(losers) == 1 else
            f"{_phrase(losers).capitalize()} were rejected: they ranked lower on the same axes.")]
        if "alternatives_eliminated" in catalogue and catalogue.by_name["alternatives_eliminated"]:
            alternatives.append(_Sentence(
                "{alternatives_eliminated} of them were removed by an authored rule rather than "
                "by score."))
        narrative = _join(alternatives, catalogue, BUNDLE_FIELD_CAPS["alternatives_narrative"])
        if narrative:
            out["alternatives_narrative"] = narrative
    return out


def template_bundle(decision: ReasoningDecision, *, catalogue: Catalogue, grounding: Grounding,
                    citations: Sequence[Mapping[str, object]] = (),
                    evidence_refs: Sequence[str] = ()) -> ReasoningBundle:
    """The fallback, as a constructed `ReasoningBundle`.

    Two attempts, and the second is the floor: if the full plain version cannot be constructed for
    this decision — an unusual play label, a section that came out too short — the MINIMAL version
    is built from the decision's own guaranteed numbers and generic grounded prose. K4's first row
    is "100% of published decisions carry a bundle", and a fallback that can itself fail leaves that
    row depending on the shape of a play label.
    """
    prose = build_template(decision, catalogue=catalogue, grounding=grounding)
    refs = tuple(evidence_refs) or tuple(grounding.evidence_refs)
    for attempt in (prose, _minimal(decision, catalogue=catalogue, grounding=grounding)):
        used = _used(attempt, catalogue)
        try:
            return ReasoningBundle.for_decision(
                decision, generation=TEMPLATE_FALLBACK, numbers_used=used,
                citations=tuple(citations), evidence_refs=refs, **attempt)
        except Exception:      # noqa: BLE001 — the minimal version is the answer to this
            continue
    raise ValueError("no template narrative could be constructed for this decision")


def _used(prose: Mapping[str, str], catalogue: Catalogue) -> dict[str, int]:
    names: list[str] = []
    for text in prose.values():
        names.extend(placeholders(text))
    return catalogue.subset(names)


def _minimal(decision: ReasoningDecision, *, catalogue: Catalogue,
             grounding: Grounding) -> dict[str, str]:
    """The floor. Generic, honest, and constructible for any decision that committed to an action.

    Every sentence here is free of digits and of catalogue references, so its constructability does
    not depend on which numbers this particular decision produced — which is the whole point of
    having a floor under a fallback.
    """
    label = _humanise(dict(grounding.selected or {}).get("label")
                      or dict(grounding.selected or {}).get("play_id")
                      or "the recommended action")
    subject = _humanise(getattr(decision, "capability_id", "")) or "this situation"
    return {
        "headline": (f"{label} — {subject}")[:BUNDLE_FIELD_CAPS["headline"]],
        "situation_summary": (
            f"The reasoning units completed on this {subject} and the decision was recorded with "
            "its evidence."),
        "why_it_matters": (
            f"The engine found a condition on this {subject} that changes what should happen "
            "next, and recorded the evidence it rests on."),
        "root_cause": (
            f"The recorded evidence for this {subject} is what drove the reading; the units' "
            "findings and the sources are listed on this card."),
        # No comparative claim here: the floor runs on ANY decision, including one that weighed
        # nothing else, and "ranked first against the alternatives" on a single-candidate decision
        # is a comparison that did not happen.
        "recommendation_rationale": (
            f"Recommended: {label}, which the engine ranked first on the axes it recorded for "
            "this decision."),
        "expected_effect": (
            "Acting resolves the condition the units reported; leaving it stands the exposure the "
            "decision recorded."),
    }


__all__ = ["MAX_NAMED_ALTERNATIVES", "MAX_NAMED_FINDINGS", "build_template", "template_bundle"]
