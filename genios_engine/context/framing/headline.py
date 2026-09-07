"""L2.7.2-U1 · M-6 · situation FRAMING — the model picks the sentence, the system supplies every
word in it that makes a claim.

A pattern match yields *"these five conditions held"*. A card needs *"the AWS renewal decision is
unowned with 12 days left on the cancellation window"*. That is synthesis, and no amount of
assembly produces it — which is why there is a model site here at all.

THE MECHANISM, AND WHY IT MAKES THE TWO HARD-FAIL ROWS UNREACHABLE RATHER THAN UNLIKELY. The model
does not write prose. It returns two things: a TEMPLATE ID from a closed registry, and a mapping
from that template's slots to FACT IDS drawn from the supplied set. Nothing the model emits is
ever echoed into the output — not a noun, not a digit, not a word. The sentence comes from the
template, and every value substituted into it comes from a supplied fact.

  * **0 fabricated facts** (doc 09, hard fail). A noun the model invented has nowhere to go: the
    only strings that reach the headline are the template's own literal text and the values of
    facts the caller supplied. An unknown fact id fails validation and the deterministic template
    headline publishes instead.
  * **0 visibility leaks** (doc 09, hard fail). Input is filtered by `narrowest()`/`can_view`
    BEFORE the prompt is built, so the model never sees a fact the reader may not; and a slot
    naming a fact outside the filtered set is refused, so even a model that guessed an id
    correctly cannot pull one back in. Two independent barriers, because one is a policy and two
    is a property.
  * **numbers never drift** (case 12). Registration refuses a template whose literal text contains
    a digit. Every number on a card is therefore substituted, never generated.
  * **framing cannot overrule the evidence** (case 11). A template declares which matched
    conditions it asserts; if the situation's matched conditions do not include them, the framing
    is rejected. Pattern conditions are authoritative; framing DESCRIBES them.

FALLBACK IS A REAL PATH, NOT A THEORETICAL ONE. No model, no budget, a malformed response, an
unknown slot, a contradiction — all five land on `template_headline`, the deterministic sentence
built from the supplied facts alone, and every one of them is LOGGED with which it was. A plainer
card always beats a wrong one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.visibility import Visibility, narrowest
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.context.framing")

#: Every reason a framing fell back, as constants — the log groups on them and a typo would make a
#: second bucket for the same failure.
FALLBACK_NO_MODEL = "no_model"
FALLBACK_MODEL_ERROR = "model_error"
FALLBACK_MALFORMED = "malformed_response"
FALLBACK_UNKNOWN_TEMPLATE = "unknown_template"
FALLBACK_TEMPLATE_NOT_PERMITTED = "template_not_permitted"
FALLBACK_UNSUPPORTED_SLOT = "unsupported_slot"
FALLBACK_CONTRADICTS_CONDITIONS = "contradicts_conditions"
FALLBACK_UNSUPPORTED_TERM = "unsupported_term"

_DIGIT = re.compile(r"\d")
_SLOT = re.compile(r"\{([a-z_]+)\}")


class FramingError(ValueError):
    """A template that may not be registered. Registration-time, like the pattern registry's."""


@dataclass(frozen=True, slots=True)
class FramingFact:
    """One fact the model is allowed to know about, and the audience it came from.

    `value` is what gets substituted. It is a str or an int and never a structure: a nested value
    is one a card cannot render and a human cannot check, and the moment a renderer has to
    summarise a value to fit it, the summary is a claim nobody validated.
    """

    fact_id: str
    field_path: str
    #: A short human noun for the thing — "AWS renewal", "Northwind". Shown, so it is checked.
    label: str
    value: str | int
    visibility: Visibility | None = None
    spans: tuple[EvidenceSpan, ...] = ()

    def rendered(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class HeadlineTemplate:
    """One sentence the model may choose, and the conditions choosing it ASSERTS.

    `requires_conditions` is the case-11 mechanism: a template that says "unowned" may only be
    chosen for a situation whose matched conditions include the one that established that nobody
    owns it. Without this the model could pick a truthful-sounding sentence the evidence does not
    support, which is a fabrication that no span check would catch because every word in it is
    real.
    """

    template_id: str
    situation_types: tuple[str, ...]
    slots: tuple[str, ...]
    sentence: str
    why_it_matters: str
    requires_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for text_part, label in ((self.sentence, "sentence"),
                                 (self.why_it_matters, "why_it_matters")):
            if _DIGIT.search(text_part):
                raise FramingError(
                    f"template {self.template_id!r} {label} contains a digit. Numbers are "
                    "TEMPLATED IN from supplied facts, never written into a sentence — a literal "
                    "in the template is a number no fact backs")
            for slot in _SLOT.findall(text_part):
                if slot not in self.slots:
                    raise FramingError(
                        f"template {self.template_id!r} uses slot {slot!r} which it does not "
                        "declare")
        if not self.slots:
            raise FramingError(f"template {self.template_id!r} declares no slots; a headline with "
                               "no supplied value is a category label, not a framing")


@dataclass(frozen=True, slots=True)
class FramingInput:
    """What the model may see. Already visibility-filtered — see `for_viewer`."""

    situation_type: str
    #: WHAT THE SITUATION IS ABOUT — the anchor's own name, supplied by the caller.
    #:
    #: Explicit and not derived from the facts, because the facts are sorted by id and "the first
    #: one" is whichever fact happens to sort first: a renewal card would be titled "days left".
    #: The subject of a situation is its ANCHOR, and only the caller knows which node that was.
    subject_label: str
    #: The facts the framing may draw on, filtered. Sorted by `fact_id` so two identical
    #: situations build byte-identical prompts and a cached response stays valid.
    facts: tuple[FramingFact, ...]
    #: The field paths of the conditions that actually held. Authoritative over any framing.
    matched_conditions: tuple[str, ...]
    #: The audience of the situation — the narrowest of the evidence it was derived from.
    visibility: Visibility

    @classmethod
    def for_viewer(cls, situation_type: str, facts: Sequence[FramingFact], *,
                   matched_conditions: Sequence[str], viewer_email: str | None,
                   subject_label: str | None = None,
                   org_member: bool = True) -> FramingInput:
        """Build the input for ONE reader, dropping every fact they may not see.

        This is barrier one of two, and it is the one doc 12 says to build the test for first:
        *"framing input is filtered by narrowest() visibility BEFORE the call — the model never
        sees what the recipient may not"*. A fact dropped here is absent from the prompt, so a
        leak would require the model to invent the fact rather than to repeat it — and barrier two
        (slot validation against this same set) refuses it even then.
        """
        allowed = tuple(sorted(
            (f for f in facts
             if f.visibility is None or f.visibility.can_view(viewer_email, org_member=org_member)),
            key=lambda f: f.fact_id))
        audience = narrowest(*(f.visibility for f in allowed))
        # A READER WHO MAY SEE NOTHING IS TOLD NOTHING, including the subject's name. The caller
        # supplies `subject_label` from the anchor, and the anchor's name is itself a fact about
        # the world: "AWS renewal" on a card for somebody who could see none of the evidence is a
        # smaller leak than a quoted sentence and it is still a leak. When the filter empties the
        # input, the subject degrades to the situation TYPE, which names a category and nobody.
        subject = (subject_label or allowed[0].label) if allowed \
            else situation_type.replace("_", " ")
        return cls(situation_type=situation_type, subject_label=subject, facts=allowed,
                   matched_conditions=tuple(matched_conditions), visibility=audience)

    def fact(self, fact_id: str) -> FramingFact | None:
        for f in self.facts:
            if f.fact_id == fact_id:
                return f
        return None


@dataclass(frozen=True, slots=True)
class Framing:
    """The card's words, and the account of where every one of them came from."""

    headline: str
    subject_label: str
    why_it_matters: str
    template_id: str
    #: The facts substituted in, sorted. This IS the span reference set — every claim in the
    #: headline traces to one of these.
    evidence_fact_ids: tuple[str, ...]
    spans: tuple[EvidenceSpan, ...]
    visibility: Visibility
    #: True when the model was not used or was rejected. Never hidden: a founder reading a plain
    #: card should be able to find out that the richer one failed validation.
    fallback: bool
    fallback_reason: str = ""

    def as_record(self) -> dict[str, Any]:
        return {"headline": self.headline, "subject_label": self.subject_label,
                "why_it_matters": self.why_it_matters, "template_id": self.template_id,
                "evidence_fact_ids": list(self.evidence_fact_ids),
                "visibility": self.visibility.model_dump(mode="json"),
                "fallback": self.fallback, "fallback_reason": self.fallback_reason}


# =================================================================================================
# The template registry — closed, digit-free, and situation-scoped
# =================================================================================================

TEMPLATES: tuple[HeadlineTemplate, ...] = (
    HeadlineTemplate(
        template_id="unowned_decision",
        situation_types=("vendor_renewal_decision",),
        slots=("subject", "days"),
        sentence="{subject} renews with no owner recorded and {days} days left to cancel",
        why_it_matters="Nobody is assigned to decide, and the window closes on its own.",
        # Naming the two conditions the sentence ASSERTS. A situation whose owner edge condition
        # did not hold cannot be framed as unowned, however well the sentence reads.
        requires_conditions=("edge.owns", "subscription.current_period_end")),
    HeadlineTemplate(
        template_id="overdue_promise",
        situation_types=("commitment_unresolved",),
        slots=("subject", "days"),
        sentence="{subject} was due {days} days ago and nothing is recorded as delivered",
        why_it_matters="A promise past its date with no delivery is the cheapest trust to lose.",
        requires_conditions=("commitment.due_at",)),
    HeadlineTemplate(
        template_id="relationship_cooling",
        situation_types=("relationship_going_cold",),
        slots=("subject", "metric"),
        sentence="Contact with {subject} is falling and sits in the bottom quarter of its peers"
                 " on {metric}",
        why_it_matters="Declining contact against its own cohort is the earliest churn signal "
                       "this system can see.",
        requires_conditions=("trend.engagement.touch_count_28d",)),
    HeadlineTemplate(
        template_id="unprepared_meeting",
        situation_types=("meeting_preparation_gap",),
        slots=("subject", "days"),
        sentence="{subject} starts in {days} days with no agenda recorded",
        why_it_matters="An external meeting without an agenda is the one you walk into cold.",
        requires_conditions=("meeting.start_at",)),
    HeadlineTemplate(
        template_id="sole_approver",
        situation_types=("founder_bottleneck",),
        slots=("subject", "count"),
        sentence="{subject} is the only approver for {count} classes of decision, with no "
                 "delegate",
        why_it_matters="Every one of those decisions stops when this person is unavailable.",
        requires_conditions=("authority.sole_approver_subject_count",)),
    HeadlineTemplate(
        template_id="condition_met",
        situation_types=("condition_now_satisfied",),
        slots=("subject",),
        sentence="What {subject} was waiting on has happened, and the next move is ours",
        why_it_matters="The condition somebody set months ago is now true and nobody was told.",
        requires_conditions=("derived.timeline.condition_satisfied",)),
)

_BY_ID: dict[str, HeadlineTemplate] = {t.template_id: t for t in TEMPLATES}


def templates_for(situation_type: str) -> tuple[HeadlineTemplate, ...]:
    """What the model may choose between for this situation type. A CLOSED set — the model picks
    from it and cannot extend it."""
    return tuple(t for t in TEMPLATES if situation_type in t.situation_types)


# =================================================================================================
# Framing
# =================================================================================================

#: What a framing model is: a function from a prompt to a parsed mapping, or None.
#: Injected rather than imported, so this module has no dependency on a client, no API key, no
#: network — and a test drives the real code path with a stub instead of a mock of it.
Asker = Callable[[str], Mapping[str, Any] | None]


def build_prompt(inp: FramingInput) -> str:
    """The prompt. Contains ONLY facts that survived the visibility filter, and asks for ids.

    Deterministic: facts are sorted, templates are listed in registry order, and the same
    situation therefore produces the same prompt — which is what makes a cached response safe to
    reuse and a golden fixture meaningful.
    """
    lines = [
        "Choose how to frame ONE business situation.",
        "",
        "You may not write prose. Return JSON with exactly two keys:",
        '  {"template_id": "<one of the ids below>", "slots": {"<slot>": "<fact_id>"}}',
        "Every slot must name one of the FACT IDS below. You may not introduce a fact, a name or "
        "a number; anything you write other than these two keys is discarded.",
        "",
        f"SITUATION TYPE: {inp.situation_type}",
        "CONDITIONS THAT HELD (authoritative — a framing may describe these and may not "
        "contradict them):"]
    lines.extend(f"  - {c}" for c in inp.matched_conditions)
    lines.append("FACTS:")
    for fact in inp.facts:
        lines.append(f"  - id={fact.fact_id}  {fact.field_path}  {fact.label}: {fact.rendered()}")
    lines.append("TEMPLATES:")
    for template in templates_for(inp.situation_type):
        lines.append(f"  - id={template.template_id}  slots={list(template.slots)}  "
                     f"\"{template.sentence}\"")
    return "\n".join(lines)


def template_headline(inp: FramingInput) -> Framing:
    """The deterministic fallback — no model, no choice, no risk.

    Built from the supplied facts alone: the first fact's label is the subject and the type is
    spelled out. Plain, and unfalsifiable in the only way that matters — every word traces to
    something the caller handed in.
    """
    subject = inp.subject_label
    readable = inp.situation_type.replace("_", " ")
    return Framing(
        headline=f"{subject}: {readable}", subject_label=subject,
        why_it_matters="Framing was not applied; the conditions below are the whole account.",
        template_id="deterministic_template",
        evidence_fact_ids=tuple(f.fact_id for f in inp.facts),
        spans=tuple(s for f in inp.facts for s in f.spans),
        visibility=inp.visibility, fallback=True, fallback_reason=FALLBACK_NO_MODEL)


def frame(inp: FramingInput, *, ask: Asker | None = None,
          eval_time: datetime | None = None) -> Framing:
    """M-6. Returns a framing that is either the model's CHOICE rendered deterministically, or the
    template fallback — never anything in between, and never a word the model wrote.

    `eval_time` is accepted and unused by the arithmetic here (the headline states no interval of
    its own; `timeline.narrate` computes those). It is in the signature because every framing call
    from a route or a drain must be replayable, and a site that does not take the instant is a
    site somebody later adds a clock to.
    """
    if ask is None:
        return _fallback(inp, FALLBACK_NO_MODEL)
    try:
        response = ask(build_prompt(inp))
    except Exception as exc:                              # noqa: BLE001 — a model site never
        _log.warning("framing model failed: %s", exc)     # takes a card down with it
        return _fallback(inp, FALLBACK_MODEL_ERROR)
    if not isinstance(response, Mapping):
        return _fallback(inp, FALLBACK_MALFORMED)

    template = _BY_ID.get(str(response.get("template_id") or ""))
    if template is None:
        return _fallback(inp, FALLBACK_UNKNOWN_TEMPLATE)
    if inp.situation_type not in template.situation_types:
        return _fallback(inp, FALLBACK_TEMPLATE_NOT_PERMITTED)

    # CASE 11 · the conditions are authoritative. A template asserting something the pattern did
    # not establish is rejected outright, however well the sentence reads.
    matched = set(inp.matched_conditions)
    if not set(template.requires_conditions).issubset(matched):
        return _fallback(inp, FALLBACK_CONTRADICTS_CONDITIONS)

    slots = response.get("slots")
    if not isinstance(slots, Mapping):
        return _fallback(inp, FALLBACK_MALFORMED)
    values: dict[str, str] = {}
    used: list[FramingFact] = []
    for slot in template.slots:
        fact = inp.fact(str(slots.get(slot) or ""))
        if fact is None:
            # Barrier two. An id the model invented, and — the case that matters — an id for a
            # fact this reader may not see, which was filtered out of `inp.facts` upstream.
            return _fallback(inp, FALLBACK_UNSUPPORTED_SLOT)
        values[slot] = fact.rendered()
        used.append(fact)

    headline = template.sentence.format(**values)
    unsupported = unsupported_terms(headline, template, used)
    if unsupported:                                        # pragma: no cover — belt and braces
        _log.warning("framing produced unsupported terms %s", sorted(unsupported))
        return _fallback(inp, FALLBACK_UNSUPPORTED_TERM)
    return Framing(
        headline=headline, subject_label=values.get("subject", used[0].label),
        why_it_matters=template.why_it_matters, template_id=template.template_id,
        evidence_fact_ids=tuple(sorted({f.fact_id for f in used})),
        spans=tuple(s for f in used for s in f.spans),
        visibility=inp.visibility, fallback=False)


def _fallback(inp: FramingInput, reason: str) -> Framing:
    _log.info("framing fell back to the deterministic template: %s", reason)
    plain = template_headline(inp)
    return Framing(headline=plain.headline, subject_label=plain.subject_label,
                   why_it_matters=plain.why_it_matters, template_id=plain.template_id,
                   evidence_fact_ids=plain.evidence_fact_ids, spans=plain.spans,
                   visibility=plain.visibility, fallback=True, fallback_reason=reason)


def unsupported_terms(rendered: str, template: HeadlineTemplate,
                      used: Sequence[FramingFact]) -> set[str]:
    """Any word or number in the output that traces to neither the template nor a supplied value.

    Defence in depth, and a directly assertable property for the hard-fail test: the set is empty
    by construction — `str.format` can only substitute what it was given — so a non-empty answer
    means the rendering path changed and the guarantee has to be re-argued. Cheap insurance
    against a future edit that starts concatenating the model's own text.
    """
    allowed: set[str] = set(_words(template.sentence))
    for fact in used:
        allowed |= _words(fact.rendered())
        allowed |= _words(fact.label)
    return {w for w in _words(rendered) if w not in allowed}


def _words(text_part: str) -> set[str]:
    return {w for w in re.split(r"[^\w.@-]+", text_part.lower()) if w and not _SLOT.match(w)}


__all__ = ["FALLBACK_CONTRADICTS_CONDITIONS", "FALLBACK_MALFORMED", "FALLBACK_MODEL_ERROR",
           "FALLBACK_NO_MODEL", "FALLBACK_TEMPLATE_NOT_PERMITTED", "FALLBACK_UNKNOWN_TEMPLATE",
           "FALLBACK_UNSUPPORTED_SLOT", "TEMPLATES", "Asker", "Framing", "FramingError",
           "FramingFact", "FramingInput", "HeadlineTemplate", "build_prompt", "frame",
           "template_headline", "templates_for", "unsupported_terms"]
