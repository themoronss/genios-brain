"""V-1 … V-7 — the structural gauntlet that REPLACES the three caps, and is stricter than they were.

**Why the caps could go.** `intelligence.py`'s explanation validator enforces one sentence, no
directives, no numbers, grounded in retrieved text. Those caps exist because, today, the sentence is
generated *about* a decision the model can see but cannot verify — so the only safe sentence is a
short, unquantified, non-instructing one, and the founder's card (WHY THIS MATTERS · ROOT CAUSE ·
RECOMMENDATION · EXPECTED EFFECT) is structurally impossible. v2 removes the REASON for the caps:
the decision is fixed and typed first (V-3), every number is substituted by code (V-4/V-5), and
every claim is bound to this decision's own material (V-1/V-2/V-6).

**Nothing was relaxed. Three things were made harder.**

| the old cap | what replaces it |
|---|---|
| ONE SENTENCE | V-1 grounds EVERY sentence, and refuses the whole field if one is ungrounded — the old check never looked at a second sentence because there could not be one |
| NO DIRECTIVES | V-3 keeps `_DIRECTIVE_RE` on the four DESCRIPTIVE fields and lifts it only on `recommendation_rationale`, whose instruction is the decision's own action, id-matched at the constructor. The cap moved to where it was doing work; it did not go |
| NO NUMBERS | V-4 refuses digits AND spelled-out quantities, and V-5 refuses a placeholder the deterministic half did not compute. The old check allowed any number that appeared anywhere in the grounding blob |

**Reused, not forked.** `_DIRECTIVE_RE`, `_ADDRESS_RE` and `_EXPLANATION_GLUE` are imported from
`intelligence.py` rather than copied. Doc 08's retirement table says that validator's machinery is
reused by the gauntlet and not deleted, and a copy is a fork that drifts on the first tuning.
`tests/reason/test_bundle_gauntlet.py` pins the identity so a copy cannot be introduced later.

**Run in order; every outcome recorded.** Doc 05 §4. The report carries a row per check whether it
passed or failed, because "V-2 passed" and "V-2 never ran" are different facts about a generation
and only one of them means the citations were checked.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from genios_engine.contracts.reasoning import (
    BUNDLE_FIELD_CAPS,
    BUNDLE_PROSE_FIELDS,
    ReasoningDecision,
    bare_numbers,
    placeholders,
)

# Reused verbatim — see the module docstring. The `noqa`s are deliberate: these are the private
# names of the validator this gauntlet extends, and importing them is the point.
from genios_engine.reason.intelligence import _ADDRESS_RE as ADDRESS_RE  # noqa: PLC2701
from genios_engine.reason.intelligence import _DIRECTIVE_RE as DIRECTIVE_RE  # noqa: PLC2701
from genios_engine.reason.intelligence import _EXPLANATION_GLUE as EXPLANATION_GLUE  # noqa: PLC2701

from .grounding import Grounding
from .numbers import Catalogue

#: The four fields that DESCRIBE. The old no-directives cap stays on exactly these: a situation
#: summary that instructs is a model choosing an action, whatever the decision said.
DESCRIPTIVE_FIELDS = ("situation_summary", "why_it_matters", "root_cause", "expected_effect")
#: The one field that INSTRUCTS. Its instruction is the decision's committed action, and V-3's
#: constructor half has already made it impossible for that action to be a different one.
DIRECTIVE_FIELD = "recommendation_rationale"

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_NAMEISH = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]*\b")
#: Straight and typographic quotation marks. A model asked for JSON emits straight ones; a model
#: that has been near a word processor emits curly ones, and a check that only knew about one shape
#: would pass a paraphrase in the other.
_QUOTED = re.compile(r"\"([^\"]{4,400})\"|“([^”]{4,400})”")
#: Residue that says the model answered with a document rather than a sentence. MULTILINE, because
#: without it `^` anchors to the start of the FIELD and a bullet list that begins on its second line
#: — which is what a model that starts prose and then reverts to a list actually produces — sails
#: straight through.
_RESIDUE = re.compile(r"```|\*\*|^\s*[-*]\s|<[a-zA-Z/]|\{\"|\bnull\b|\bundefined\b|\bN/?A\b",
                      re.MULTILINE)

#: Quantities spelled as words. V-4's second half, and the reason it exists: `bare_numbers` sees
#: digits, and a model told not to type digits types "fourteen". Ordinals are deliberately ABSENT
#: ("the first reply", "second thoughts") and so is "one", which is a pronoun far more often than a
#: quantity — a check that fires on ordinary English is a check somebody turns off.
NUMBER_WORDS = frozenset({
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
    "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand",
    "million", "billion", "dozen", "half", "twice", "double", "triple", "quadruple",
})

#: Words that assert a COMPARISON. A decision with nothing else on the table cannot honestly make
#: one, and "it beat a competitive displacement play" is a sentence that grounds on ordinary
#: vocabulary while inventing the entire comparison — the failure a per-sentence grounding test
#: provably cannot see, measured rather than assumed (the clean fixtures' grounded-word ratios run
#: as low as 0%, so no ratio threshold separates them from this).
COMPARISON_WORDS = frozenset({
    "beat", "beats", "outranked", "outranks", "outscored", "outperformed", "ahead", "above",
    "alternatives", "alternative", "options", "instead", "versus", "compared", "runner",
})

#: Words that make a mention of a rejected option a CONTRAST rather than a second recommendation.
#: A narrative may name the discount play — doc 05's own card does — but only while saying it lost.
CONTRAST_WORDS = frozenset({
    "not", "instead", "rather", "over", "against", "than", "eliminated", "rejected", "ruled",
    "blocked", "refused", "excluded", "removed", "loses", "lost", "why", "unlike", "whereas",
    "but", "however", "despite", "cannot", "would", "no", "nor", "without",
})

#: Minimum characters a prose field must carry to be a sentence rather than a placeholder for one.
#: The headline is exempt (it is a title) and gets its own floor.
MIN_FIELD_CHARS = {"headline": 12, "situation_summary": 40, "why_it_matters": 40,
                   "root_cause": 40, "recommendation_rationale": 40, "expected_effect": 40,
                   "alternatives_narrative": 40}
#: A runaway generation that still fits the character cap. Six sentences of narrative per field is
#: already more than the ten-second test survives.
MAX_SENTENCES = 6

CHECK_ORDER = ("V-1", "V-2", "V-3", "V-4", "V-5", "V-6", "V-7")
CHECK_NAMES = {
    "V-1": "grounding", "V-2": "citation_fidelity", "V-3": "decision_fidelity",
    "V-4": "no_raw_numbers", "V-5": "placeholder_resolution", "V-6": "scope",
    "V-7": "length_and_shape",
}


@dataclass(frozen=True, slots=True)
class CheckResult:
    check: str
    passed: bool
    reason_codes: tuple[str, ...] = ()
    #: What exactly failed, in the model's own words where that helps a regeneration: the digits it
    #: typed, the sentence that grounded in nothing, the name it invented.
    detail: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return CHECK_NAMES[self.check]

    def as_record(self) -> dict[str, Any]:
        return {"check": self.check, "name": self.name, "passed": self.passed,
                "reason_codes": list(self.reason_codes), "detail": list(self.detail)}


@dataclass(frozen=True, slots=True)
class GauntletReport:
    checks: tuple[CheckResult, ...]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.checks)

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        return tuple(item for item in self.checks if not item.passed)

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(code for item in self.failures for code in item.reason_codes)

    def as_records(self) -> list[dict[str, Any]]:
        return [item.as_record() for item in self.checks]

    def feedback(self) -> str:
        """What the ONE regeneration is told. Specific, in the model's own words, and bounded.

        Doc 05 §4 allows exactly one regeneration, so the message it carries is the only chance to
        turn a near miss into a bundle. "Invalid output" wastes it; "you wrote 14, use
        {core_timeline_quiet_days}" does not.
        """
        lines = []
        for item in self.failures:
            detail = "; ".join(item.detail[:6])
            lines.append(f"- {item.check} ({item.name}) FAILED: {detail}" if detail
                         else f"- {item.check} ({item.name}) FAILED")
        return "\n".join(lines)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE.split(str(text or "").strip()) if part.strip()]


def _prose(generation: Mapping[str, Any]) -> list[tuple[str, str]]:
    """(field, text) for every prose field the generation actually supplied, in card order."""
    out = []
    for name in BUNDLE_PROSE_FIELDS:
        value = generation.get(name)
        if value is None:
            continue
        out.append((name, " ".join(str(value).split()) if name == "headline" else str(value)))
    return out


def run_gauntlet(generation: Mapping[str, Any], *, decision: ReasoningDecision,
                 catalogue: Catalogue, grounding: Grounding,
                 citations: Sequence[Mapping[str, Any]] = ()) -> GauntletReport:
    """V-1 through V-7, in order, against a RAW generation — before any object exists.

    Deliberately runs on the mapping and not on a `ReasoningBundle`: doc 05 §4 records every
    outcome, and a constructor that raises on the first structural problem can only ever report
    one. The constructor then refuses the same things, so a bundle that skipped this cannot exist
    either — the split Z0's contract docstring describes.
    """
    fields = _prose(generation)
    checks = [
        _v1_grounding(fields, grounding),
        _v2_citations(fields, decision=decision, grounding=grounding, citations=citations),
        _v3_decision(fields, decision=decision, grounding=grounding),
        _v4_numbers(fields),
        _v5_placeholders(fields, catalogue=catalogue),
        _v6_scope(fields, grounding=grounding),
        _v7_shape(fields, generation=generation),
    ]
    return GauntletReport(checks=tuple(checks))


# ── V-1 · grounding ──────────────────────────────────────────────────────────────────────────

def _v1_grounding(fields: Sequence[tuple[str, str]], grounding: Grounding) -> CheckResult:
    """Every SENTENCE rests on this decision's own material, or on a computed number.

    Doc 09 case 1 says an ungrounded claim is DROPPED and more than 5% of drops falls back to
    template. This refuses the generation instead of editing it, which is stricter in both
    directions: a narrative with a sentence silently removed is a narrative nobody wrote, and a
    field can be left saying less than it appears to. The regeneration is told which sentence, so
    the model gets a real second chance rather than a rejection.
    """
    ungrounded: list[str] = []
    total = 0
    for name, text in fields:
        for sentence in _sentences(text):
            total += 1
            if placeholders(sentence):
                continue
            words = [word.casefold() for word in _WORD.findall(sentence.replace("_", " "))]
            content = [word for word in words
                       if len(word) >= 4 and word not in EXPLANATION_GLUE]
            if any(word in grounding.terms for word in content):
                continue
            ungrounded.append(f"{name}: {sentence[:120]!r} rests on nothing in this situation")
    if not total:
        return CheckResult("V-1", False, ("no_prose",), ("the generation carried no sentences",))
    if ungrounded:
        return CheckResult("V-1", False, ("ungrounded_claim",), tuple(ungrounded[:6]))
    return CheckResult("V-1", True)


# ── V-2 · citation fidelity ──────────────────────────────────────────────────────────────────

def _v2_citations(fields: Sequence[tuple[str, str]], *, decision: ReasoningDecision,
                  grounding: Grounding,
                  citations: Sequence[Mapping[str, Any]]) -> CheckResult:
    """A quoted span is byte-identical to an authored one, and an attached citation is one THIS
    decision carried.

    Two halves, because there are two ways to invent a citation. The model can invent one by
    QUOTING — writing a plausible sentence between quotation marks — which is the paraphrase failure
    doc 05 §7 names, caught by comparing every quoted span against the statements L3 proved
    byte-identical. And a caller can invent one by ATTACHING a citation the decision never carried,
    caught by comparing statement hashes against `decision.citations`.
    """
    problems: list[str] = []
    allowed = {quote for quote in grounding.quotes}
    for name, text in fields:
        for match in _QUOTED.finditer(text):
            span = (match.group(1) or match.group(2) or "").strip()
            if span and span not in allowed:
                problems.append(f"{name}: quoted {span[:100]!r}, which is not an authored claim "
                                "this decision carried")
    decision_hashes = {str(item.get("statement_hash")) for item in decision.citations}
    for citation in citations:
        if str(citation.get("statement_hash")) not in decision_hashes:
            problems.append(f"citation {citation.get('artifact_id')!r} was not carried by this "
                            "decision")
    if problems:
        return CheckResult("V-2", False, ("citation_not_byte_identical",), tuple(problems[:6]))
    return CheckResult("V-2", True)


# ── V-3 · decision fidelity ──────────────────────────────────────────────────────────────────

def _ambient(label: str, grounding: Grounding) -> set[str]:
    """The words this situation already uses for itself — the recommended action's own label and
    every finding kind the units published. A rejected option is NAMED only by the words that are
    not already ambient; see the comment at the call site."""
    words = set(_WORD.findall(label.replace("_", " ").casefold()))
    for observation in grounding.observations:
        words |= set(_WORD.findall(
            str(observation.get("finding") or "").replace("_", " ").casefold()))
    return words


def _v3_decision(fields: Sequence[tuple[str, str]], *, decision: ReasoningDecision,
                 grounding: Grounding) -> CheckResult:
    """The narrative recommends the action the decision committed to, and nothing else.

    The id half of V-3 is STRUCTURAL and lives in `ReasoningBundle.__post_init__` — it cannot be
    checked here because the ids are derived, not generated. What is checked here is the PROSE half,
    which the id match cannot see: a bundle can carry the right `action_id` and a paragraph that
    recommends something else. Three ways that happens, three checks:

    1. the recommendation does not name the committed action at all;
    2. a DESCRIPTIVE field instructs — the old no-directives cap, kept exactly where it was doing
       work;
    3. a rejected option is named without being contradicted, i.e. read as a second recommendation.
    """
    problems: list[str] = []
    by_name = dict(fields)

    selected = dict(grounding.selected or {})
    label = str(selected.get("label") or selected.get("play_id") or "")
    if label:
        anchor = " ".join((by_name.get(DIRECTIVE_FIELD, ""), by_name.get("headline", ""))).casefold()
        tokens = [word for word in _WORD.findall(label.replace("_", " ").casefold())
                  if len(word) >= 4]
        if tokens and not any(token in anchor for token in tokens):
            problems.append(
                f"the recommendation never names the committed action {label!r} — a narrative "
                "about an action a reader cannot identify is a narrative about a different one")

    for name in DESCRIPTIVE_FIELDS:
        text = by_name.get(name)
        if text and DIRECTIVE_RE.search(text):
            problems.append(f"{name} instructs; only {DIRECTIVE_FIELD} may, and only about the "
                            "committed action")

    # THE FIRST SENTENCE OF THE RECOMMENDATION IS THE RECOMMENDATION. Doc 05 §5's card opens
    # "Send the renewal-risk outreach to the economic buyer today" and only then says "Why this and
    # not a discount offer". A generation that opens with the option the corpus eliminated and
    # mentions the committed action afterwards satisfies every whole-field check — it names the
    # action, and the word "not" appears somewhere — and is still the worst output this layer can
    # produce. So the opening sentence is checked on its own.
    rejected_labels = {str(item.get("label") or item.get("play_id") or ""): item
                       for item in grounding.rejected}
    opening = (_sentences(by_name.get(DIRECTIVE_FIELD, "")) or [""])[0].casefold()
    if opening:
        if label:
            tokens = [word for word in _WORD.findall(label.replace("_", " ").casefold())
                      if len(word) >= 4]
            if tokens and not any(token in opening for token in tokens):
                problems.append(
                    f"the recommendation OPENS on something other than the committed action "
                    f"{label!r} — the first sentence is what a reader acts on")
        for other, item in rejected_labels.items():
            tokens = [word for word in _WORD.findall(other.replace("_", " ").casefold())
                      if len(word) >= 5 and word not in _ambient(label, grounding)]
            if tokens and all(token in opening for token in tokens):
                problems.append(
                    f"the recommendation OPENS by naming {other!r}, which this decision did not "
                    f"choose ({item.get('disposition')}) — whatever the rest of the paragraph "
                    "says, that is the sentence a reader acts on")

    # A COMPARISON THE DECISION DID NOT MAKE. With nothing else on the table there is no "it beat
    # X" to narrate, and a sentence that invents one grounds perfectly well on ordinary vocabulary.
    # This is the one invention V-1 structurally cannot catch, so V-3 catches it: the record says
    # how many options existed, and the prose may not claim more.
    if not grounding.rejected:
        for name, text in fields:
            claimed = sorted(set(_WORD.findall(text.casefold())) & COMPARISON_WORDS)
            if claimed:
                problems.append(
                    f"{name} claims a comparison ({', '.join(claimed)}) on a decision that "
                    "weighed no other option — the comparison did not happen")

    selected_id = str(selected.get("play_id") or "")
    # The AMBIENT vocabulary of this situation: the words the recommended action and the units'
    # own findings already use. A rejected option is only NAMED when the words that distinguish it
    # appear — "Move the promised date" shares "promised" with the finding `promised_date_slipping`,
    # so a headline reading "promised date slipping" is describing the situation, not recommending
    # the option that lost. Without this subtraction the check fires on the engine's own template.
    ambient = _ambient(label, grounding)
    for rejected in grounding.rejected:
        other = str(rejected.get("label") or rejected.get("play_id") or "")
        if not other or rejected.get("play_id") == selected_id:
            continue
        tokens = [word for word in _WORD.findall(other.replace("_", " ").casefold())
                  if len(word) >= 5 and word not in ambient]
        if not tokens:
            continue
        for name, text in fields:
            lowered = text.casefold()
            if not all(token in lowered for token in tokens):
                continue
            words = set(_WORD.findall(lowered))
            if not (words & CONTRAST_WORDS):
                problems.append(
                    f"{name} names the rejected option {other!r} without saying it lost — a "
                    "reader takes an uncontradicted option as a second recommendation")
    if problems:
        return CheckResult("V-3", False, ("contradicts_decision",), tuple(problems[:6]))
    return CheckResult("V-3", True)


# ── V-4 · no raw numbers ─────────────────────────────────────────────────────────────────────

def _v4_numbers(fields: Sequence[tuple[str, str]]) -> CheckResult:
    """No digit and no spelled-out quantity outside a placeholder.

    `bare_numbers` is the contract's own detector, imported rather than reimplemented so the
    gauntlet and the constructor cannot disagree about what a bare number is. The spelled-out half
    is this module's addition and it is not optional: a model told "do not type digits" complies by
    typing "fourteen", and the resulting sentence is exactly the drifted number V-4 exists to stop —
    with the added property that no substitution will ever correct it.
    """
    problems: list[str] = []
    for name, text in fields:
        digits = bare_numbers(text)
        if digits:
            problems.append(f"{name}: typed the number(s) {', '.join(digits)} — write a "
                            "{placeholder} instead")
        spelled = sorted({word for word in _WORD.findall(text.casefold())
                          if word in NUMBER_WORDS})
        if spelled:
            problems.append(f"{name}: spelled the quantity/quantities {', '.join(spelled)} — "
                            "write a {placeholder} instead")
    if problems:
        return CheckResult("V-4", False, ("bare_number",), tuple(problems[:6]))
    return CheckResult("V-4", True)


# ── V-5 · placeholder resolution ─────────────────────────────────────────────────────────────

def _v5_placeholders(fields: Sequence[tuple[str, str]], *, catalogue: Catalogue) -> CheckResult:
    """Every placeholder names a number the deterministic half computed.

    A placeholder with no catalogue entry is not a formatting problem: it is the model asking for a
    number nobody computed, and rendering it would put a brace on a card or, worse, invite a later
    substitution from somewhere else.
    """
    problems: list[str] = []
    for name, text in fields:
        for token in placeholders(text):
            if token not in catalogue:
                problems.append(f"{name}: {{{token}}} is not a computed number — the catalogue is "
                                "the complete list")
        residue = re.sub(r"\{[a-z][a-z0-9_]{0,63}\}", "", text)
        if "{" in residue or "}" in residue:
            problems.append(f"{name}: a malformed placeholder — placeholders are "
                            "{lower_snake_case} with no spaces")
    if problems:
        return CheckResult("V-5", False, ("unresolved_placeholder",), tuple(problems[:6]))
    return CheckResult("V-5", True)


# ── V-6 · scope ──────────────────────────────────────────────────────────────────────────────

def _v6_scope(fields: Sequence[tuple[str, str]], *, grounding: Grounding) -> CheckResult:
    """No proper name, acronym, address or URL that is absent from this situation.

    The boundary `intelligence._validated_explanation` draws, applied to a card instead of a
    sentence: the first word of each sentence is exempt because sentence casing capitalises it by
    construction. Ordinary vocabulary is NOT checked here — a five-field narrative needs ordinary
    English, and "is this sentence about the situation" is V-1's question, asked per sentence, which
    is a stronger test than a word allowlist tuned for a single clause.
    """
    problems: list[str] = []
    for name, text in fields:
        for token in ADDRESS_RE.findall(text):
            if token.casefold() not in grounding.addresses:
                problems.append(f"{name}: {token!r} is an address this situation does not contain")
        for sentence in _sentences(text):
            words = _NAMEISH.findall(sentence)
            for index, word in enumerate(words):
                named = (word.isupper() and len(word) > 1) or (index > 0 and word[:1].isupper())
                if named and word.casefold() not in grounding.entities:
                    problems.append(f"{name}: {word!r} names something absent from this situation")
    if problems:
        return CheckResult("V-6", False, ("out_of_scope_entity",), tuple(dict.fromkeys(problems))[:6])
    return CheckResult("V-6", True)


# ── V-7 · length and shape ───────────────────────────────────────────────────────────────────

def _v7_shape(fields: Sequence[tuple[str, str]], *,
              generation: Mapping[str, Any]) -> CheckResult:
    """The five required fields exist, are prose, and fit the card.

    The caps are the contract's, imported rather than restated. What this adds is the FLOOR and the
    residue check: a model that answers `"root_cause": "N/A"` satisfies every cap in the contract
    and produces a card with a hole in it, and one that answers with a markdown bullet list
    satisfies them and produces a card with asterisks in it.
    """
    problems: list[str] = []
    supplied = dict(fields)
    for name in BUNDLE_PROSE_FIELDS:
        if name == "alternatives_narrative":
            continue
        if name not in supplied or not supplied[name].strip():
            problems.append(f"{name} is missing — it is one of the five sections the card renders")
    for name, text in fields:
        cap = BUNDLE_FIELD_CAPS[name]
        if len(text) > cap:
            problems.append(f"{name} is {len(text)} characters; the cap is {cap}")
        if len(text.strip()) < MIN_FIELD_CHARS[name]:
            problems.append(f"{name} is too short to be the section it names")
        if _RESIDUE.search(text):
            problems.append(f"{name} carries markup or a null-ish literal rather than prose")
        if name == "headline":
            if "\n" in text:
                problems.append("headline is a title, not a paragraph")
        else:
            sentences = _sentences(text)
            if len(sentences) > MAX_SENTENCES:
                problems.append(f"{name} runs to {len(sentences)} sentences; "
                                f"{MAX_SENTENCES} is the ceiling the ten-second test survives")
            if text.strip()[-1:] not in ".!?":
                problems.append(f"{name} does not end in a complete sentence")
    unknown = sorted(set(map(str, generation)) - set(BUNDLE_PROSE_FIELDS))
    if unknown:
        problems.append(f"the generation carried unknown field(s) {unknown} — the card renders "
                        f"exactly {list(BUNDLE_PROSE_FIELDS)}")
    if problems:
        return CheckResult("V-7", False, ("shape",), tuple(problems[:6]))
    return CheckResult("V-7", True)


__all__ = ["CHECK_NAMES", "CHECK_ORDER", "COMPARISON_WORDS", "CONTRAST_WORDS", "CheckResult", "DESCRIPTIVE_FIELDS",
           "DIRECTIVE_FIELD", "GauntletReport", "MAX_SENTENCES", "MIN_FIELD_CHARS",
           "NUMBER_WORDS", "run_gauntlet"]
