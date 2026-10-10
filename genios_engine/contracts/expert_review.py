"""The expert's review of one file — what a 30-year chief of staff writes down before deciding (STEP-12).

`speedrun008/YC-II W27/` STEP-12 §3.4, tree `yc2_w27_s12` M32.C1.L-contract.V0.U01. Plane R's Groups 1-4
had no result contract at all (STEP-12 §8.3 N5: 0 hits for any shape), so a strong model's judgment of
a file had nowhere to land that code could check. This is that shape — the Atlas's `reasoning_result` —
frozen, with its own validation against the dossier the model was shown:

  * what is TRUE — facts, each citing at least one evidence id the dossier holds;
  * what FOLLOWS — inferences with what they rest on (evidence ids, or the review's facts by number);
  * what USUALLY HAPPENS — patterns, counter-patterns and base rates, each with its provenance;
  * what MIGHT be — hypotheses with what would settle them; unknowns with why they matter;
  * how to READ it — a frame and its rivals; expected vs actual against the playbook's stage;
  * what COULD happen — doing nothing, acting, the best and the worst case, the signals to watch;
  * what it is WORTH — stakes, urgency and reversibility as levels, the appraisal with its reasons;
  * what to DO — a mode (act · find out · wait · nothing · blocked), the next move, an alternative,
    when to wait or stop, what done looks like, and a draft.

PATTERNS ARE THE CHECKLIST'S. §3.4's field list leaves them out, while §3.2's checklist asks for
"patterns and counter-patterns, with their provenance" in its fourth section; a section the prompt asks
for and the contract cannot hold would be read by nobody, so the review carries them — each resting on
what the dossier holds (its history, its numbers, its playbook), or refused.

A NUMBER IS CODE'S. The model writes judgment; numbers come from STEP-10's calculators. So `validate`
refuses a review that states any number its dossier does not hold — read off every text the review
writes, the draft included — as it refuses an uncited fact, a citation the dossier never showed, and a
stage the file's playbook does not have. Digits are read; a number spelled in words is not. `validate`
never repairs: a refusal is a record with its reasons (STEP-12 §8.4 item 4). `from_mapping` raises
ValueError naming the field for an answer that is malformed — the one thing a caller may repair, once.

LEVELS, NOT SCORES. Under `06` D1 the appraisal decides what matters — code maps its levels to
importance and urgency; the model never writes the number (the Atlas's RULE 02, as amended).

Pure and frozen: no I/O, no clock, no model.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

#: How the expert intervenes — STEP-12 §8.4 item 2. Code maps each to a decision outcome.
MODES: tuple[str, ...] = ("act", "find_out", "wait", "nothing", "blocked")
#: The modes that move work forward, and so need a next move someone can make.
MOVING: frozenset[str] = frozenset({"act", "find_out"})
#: Stakes and urgency, as a reader of the file would say them — never a number.
LEVELS: tuple[str, ...] = ("low", "medium", "high")
REVERSIBILITY: tuple[str, ...] = ("reversible", "costly_to_reverse", "irreversible")
#: What a pattern line is (Plane R: pattern match, counter-pattern, base rate).
PATTERN_KINDS: tuple[str, ...] = ("pattern", "counter_pattern", "base_rate")

#: Why a review is refused — closed, so a refusal can be counted by kind.
UNCITED_FACT = "uncited_fact"
UNKNOWN_EVIDENCE = "unknown_evidence"
UNGROUNDED_INFERENCE = "ungrounded_inference"
UNGROUNDED_PATTERN = "ungrounded_pattern"
UNKNOWN_STAGE = "unknown_stage"
NO_NEXT_MOVE = "no_next_move"
NUMBER_NOT_IN_DOSSIER = "number_not_in_dossier"
REFUSALS: tuple[str, ...] = (UNCITED_FACT, UNKNOWN_EVIDENCE, UNGROUNDED_INFERENCE, UNGROUNDED_PATTERN,
                             UNKNOWN_STAGE, NO_NEXT_MOVE, NUMBER_NOT_IN_DOSSIER)

_FACT_REF = re.compile(r"^fact:(\d+)$")
# A comma groups thousands only before exactly three digits: "1,400" is one number, "7,8" is two.
_NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)*")


def number_tokens(text: str | None) -> frozenset[str]:
    """Every number written in `text`, normalised — `1,400` and `1400` alike, `2.50` as `2.5`, `07`
    as `7` — so the review's numbers and the dossier's compare by value, not by spelling."""
    out = set()
    for raw in _NUMBER.findall(str(text or "")):
        token = raw.replace(",", "")
        if token.count(".") > 1:                       # a date or a version: each part on its own
            out.update(_norm(part) for part in token.split("."))
            continue
        out.add(_norm(token))
    return frozenset(out)


def _norm(token: str) -> str:
    if "." in token:
        whole, frac = token.split(".", 1)
        frac = frac.rstrip("0")
        return f"{int(whole)}.{frac}" if frac else str(int(whole))
    return str(int(token))


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object, not {type(value).__name__}")
    return value


def _list(values: Any, name: str) -> tuple[Any, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{name} must be a list, not {type(values).__name__}")
    return tuple(values)


def _items(values: Any, name: str, one: str) -> tuple[Mapping[str, Any], ...]:
    items = _list(values, name)
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError(f"{one} must be an object, not {type(item).__name__}")
    return items


def _text(value: Any, name: str, *, required: bool = True) -> str:
    if isinstance(value, (Mapping, list, tuple)):
        raise ValueError(f"{name} must be words, not {type(value).__name__}")
    text = " ".join(str(value or "").split())
    if required and not text:
        raise ValueError(f"an expert review says {name}")
    return text


def _texts(values: Any, name: str, *, at_least: int = 0) -> tuple[str, ...]:
    out = tuple(_text(v, name) for v in _list(values, name))
    if len(out) < at_least:
        raise ValueError(f"an expert review names at least {at_least} of {name}")
    return out


def _one_of(value: Any, allowed: tuple[str, ...], name: str) -> str:
    word = "_".join(str(value or "").strip().lower().replace("-", " ").split())
    if word not in allowed:
        raise ValueError(f"{name} is one of {allowed}, not {value!r}")
    return word


def _day(value: Any) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"the next move's by_when is a date (YYYY-MM-DD), not {value!r}") from None


@dataclass(frozen=True, slots=True)
class Fact:
    claim: str
    evidence: tuple[str, ...]                    # dossier evidence ids — at least one, or refused


@dataclass(frozen=True, slots=True)
class Inference:
    claim: str
    based_on: tuple[str, ...]                    # dossier evidence ids, or `fact:<n>` (1-based)


@dataclass(frozen=True, slots=True)
class Pattern:
    kind: str                                    # one of PATTERN_KINDS
    claim: str
    based_on: tuple[str, ...]                    # its provenance: as an inference's


@dataclass(frozen=True, slots=True)
class Hypothesis:
    proposition: str
    needs: str                                   # what would settle it


@dataclass(frozen=True, slots=True)
class Unknown:
    question: str
    relevance: str                               # why the answer would change the judgment


@dataclass(frozen=True, slots=True)
class Frames:
    primary: str
    rivals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExpectedVsActual:
    stage: str | None                            # one of the playbook's stages, or None without one
    expected: str
    actual: str


@dataclass(frozen=True, slots=True)
class Scenarios:
    do_nothing: str
    act: str
    best: str
    worst: str
    signals_to_watch: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Appraisal:
    stakes: str
    urgency: str
    reversibility: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NextMove:
    who: str
    what: str
    for_whom: str
    by_when: date | None


@dataclass(frozen=True, slots=True)
class ExpertReview:
    facts: tuple[Fact, ...]
    inferences: tuple[Inference, ...]
    patterns: tuple[Pattern, ...]
    hypotheses: tuple[Hypothesis, ...]
    unknowns: tuple[Unknown, ...]
    frames: Frames
    expected_vs_actual: ExpectedVsActual
    scenarios: Scenarios
    appraisal: Appraisal
    mode: str
    next_move: NextMove | None
    alternative: str
    wait_or_stop: str
    done_when: str
    draft: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ExpertReview":
        """The model's answer as a review, or ValueError naming what is malformed — the one error a
        caller may repair once (syntax), never what `validate` refuses (substance)."""
        if not isinstance(raw, Mapping):
            raise ValueError("an expert review is an object")
        facts = tuple(Fact(claim=_text(f.get("claim"), "a fact's claim"),
                           evidence=_texts(f.get("evidence"), "a fact's evidence"))
                      for f in _items(raw.get("facts"), "facts", "a fact"))
        if not facts:
            raise ValueError("an expert review states at least one fact")
        nm = raw.get("next_move")
        next_move = None
        if nm:
            nm = _mapping(nm, "the next move")
            next_move = NextMove(who=_text(nm.get("who"), "who makes the next move"),
                                 what=_text(nm.get("what"), "what the next move is"),
                                 for_whom=_text(nm.get("for_whom"), "for whom the next move is"),
                                 by_when=_day(nm.get("by_when")))
        frames = _mapping(raw.get("frames"), "frames")
        eva = _mapping(raw.get("expected_vs_actual"), "expected_vs_actual")
        sc = _mapping(raw.get("scenarios"), "scenarios")
        ap = _mapping(raw.get("appraisal"), "appraisal")
        return cls(
            facts=facts,
            inferences=tuple(Inference(claim=_text(i.get("claim"), "an inference's claim"),
                                       based_on=_texts(i.get("based_on"), "what an inference rests on"))
                             for i in _items(raw.get("inferences"), "inferences", "an inference")),
            patterns=tuple(Pattern(kind=_one_of(p.get("kind"), PATTERN_KINDS, "a pattern's kind"),
                                   claim=_text(p.get("claim"), "a pattern's claim"),
                                   based_on=_texts(p.get("based_on"), "what a pattern rests on"))
                           for p in _items(raw.get("patterns"), "patterns", "a pattern")),
            hypotheses=tuple(Hypothesis(proposition=_text(h.get("proposition"), "a hypothesis"),
                                        needs=_text(h.get("needs"), "what a hypothesis needs"))
                             for h in _items(raw.get("hypotheses"), "hypotheses", "a hypothesis")),
            unknowns=tuple(Unknown(question=_text(u.get("question"), "an unknown"),
                                   relevance=_text(u.get("relevance"), "why an unknown matters"))
                           for u in _items(raw.get("unknowns"), "unknowns", "an unknown")),
            frames=Frames(primary=_text(frames.get("primary"), "its frame"),
                          rivals=_texts(frames.get("rivals"), "rival frames", at_least=1)),
            expected_vs_actual=ExpectedVsActual(
                stage=_text(eva.get("stage"), "the stage", required=False) or None,
                expected=_text(eva.get("expected"), "what was expected"),
                actual=_text(eva.get("actual"), "what is actual")),
            scenarios=Scenarios(do_nothing=_text(sc.get("do_nothing"), "what doing nothing does"),
                                act=_text(sc.get("act"), "what acting does"),
                                best=_text(sc.get("best"), "the best case"),
                                worst=_text(sc.get("worst"), "the worst case"),
                                signals_to_watch=_texts(sc.get("signals_to_watch"),
                                                        "signals to watch", at_least=1)),
            appraisal=Appraisal(stakes=_one_of(ap.get("stakes"), LEVELS, "stakes"),
                                urgency=_one_of(ap.get("urgency"), LEVELS, "urgency"),
                                reversibility=_one_of(ap.get("reversibility"), REVERSIBILITY,
                                                      "reversibility"),
                                reasons=_texts(ap.get("reasons"), "the appraisal's reasons", at_least=1)),
            mode=_one_of(raw.get("mode"), MODES, "mode"),
            next_move=next_move,
            alternative=_text(raw.get("alternative"), "an alternative", required=False),
            wait_or_stop=_text(raw.get("wait_or_stop"), "when to wait or stop"),
            done_when=_text(raw.get("done_when"), "what done looks like"),
            draft=_text(raw.get("draft"), "a draft", required=False) or None)

    def as_mapping(self) -> dict[str, Any]:
        """The review as `from_mapping` reads it — what is stored, and what a replay reads back."""
        nm = self.next_move
        return {
            "facts": [{"claim": f.claim, "evidence": list(f.evidence)} for f in self.facts],
            "inferences": [{"claim": i.claim, "based_on": list(i.based_on)} for i in self.inferences],
            "patterns": [{"kind": p.kind, "claim": p.claim, "based_on": list(p.based_on)}
                         for p in self.patterns],
            "hypotheses": [{"proposition": h.proposition, "needs": h.needs} for h in self.hypotheses],
            "unknowns": [{"question": u.question, "relevance": u.relevance} for u in self.unknowns],
            "frames": {"primary": self.frames.primary, "rivals": list(self.frames.rivals)},
            "expected_vs_actual": {"stage": self.expected_vs_actual.stage,
                                   "expected": self.expected_vs_actual.expected,
                                   "actual": self.expected_vs_actual.actual},
            "scenarios": {"do_nothing": self.scenarios.do_nothing, "act": self.scenarios.act,
                          "best": self.scenarios.best, "worst": self.scenarios.worst,
                          "signals_to_watch": list(self.scenarios.signals_to_watch)},
            "appraisal": {"stakes": self.appraisal.stakes, "urgency": self.appraisal.urgency,
                          "reversibility": self.appraisal.reversibility,
                          "reasons": list(self.appraisal.reasons)},
            "mode": self.mode,
            "next_move": None if nm is None else {
                "who": nm.who, "what": nm.what, "for_whom": nm.for_whom,
                "by_when": nm.by_when.isoformat() if nm.by_when else None},
            "alternative": self.alternative,
            "wait_or_stop": self.wait_or_stop,
            "done_when": self.done_when,
            "draft": self.draft,
        }

    def texts(self) -> tuple[str, ...]:
        """Every text the review writes — what its numbers are read off."""
        out: list[str] = [f.claim for f in self.facts]
        out += [i.claim for i in self.inferences]
        out += [p.claim for p in self.patterns]
        out += [t for h in self.hypotheses for t in (h.proposition, h.needs)]
        out += [t for u in self.unknowns for t in (u.question, u.relevance)]
        out += [self.frames.primary, *self.frames.rivals]
        out += [self.expected_vs_actual.expected, self.expected_vs_actual.actual]
        out += [self.scenarios.do_nothing, self.scenarios.act, self.scenarios.best,
                self.scenarios.worst, *self.scenarios.signals_to_watch]
        out += list(self.appraisal.reasons)
        if self.next_move is not None:
            out += [self.next_move.who, self.next_move.what, self.next_move.for_whom]
        out += [self.alternative, self.wait_or_stop, self.done_when, self.draft or ""]
        return tuple(t for t in out if t)


@dataclass(frozen=True, slots=True)
class DossierCatalogue:
    """What the dossier showed the model, as `validate` needs it: every evidence id it may cite (its
    events, its numbers, its playbook's lines), every number written anywhere in it (normalised by
    `number_tokens`), and the playbook's stages."""
    evidence_ids: frozenset[str]
    numbers: frozenset[str]
    stages: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Validation:
    problems: tuple[tuple[str, str], ...] = field(default_factory=tuple)    # (refusal, detail)

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(sorted({kind for kind, _ in self.problems}))


def _grounds(refs: tuple[str, ...], facts: int, catalogue: DossierCatalogue, what: str,
             ungrounded: str) -> list[tuple[str, str]]:
    """Each way a line's `based_on` rests on nothing the review or its dossier holds."""
    if not refs:
        return [(ungrounded, f"{what} rests on nothing")]
    problems: list[tuple[str, str]] = []
    for ref in refs:
        m = _FACT_REF.match(ref)
        if m is not None:
            if not 1 <= int(m.group(1)) <= facts:
                problems.append((ungrounded, f"{what} rests on {ref}"))
        elif ref not in catalogue.evidence_ids:
            problems.append((UNKNOWN_EVIDENCE, f"{what} rests on {ref}"))
    return problems


def validate(review: ExpertReview, catalogue: DossierCatalogue) -> Validation:
    """Every way `review` says more than its dossier holds, or `ok`."""
    problems: list[tuple[str, str]] = []
    for n, fact in enumerate(review.facts, start=1):
        if not fact.evidence:
            problems.append((UNCITED_FACT, f"fact {n}"))
        for ref in fact.evidence:
            if ref not in catalogue.evidence_ids:
                problems.append((UNKNOWN_EVIDENCE, f"fact {n} cites {ref}"))
    for n, inference in enumerate(review.inferences, start=1):
        problems += _grounds(inference.based_on, len(review.facts), catalogue, f"inference {n}",
                             UNGROUNDED_INFERENCE)
    for n, pattern in enumerate(review.patterns, start=1):
        problems += _grounds(pattern.based_on, len(review.facts), catalogue, f"pattern {n}",
                             UNGROUNDED_PATTERN)
    stage = review.expected_vs_actual.stage
    if stage is not None and stage not in catalogue.stages:
        problems.append((UNKNOWN_STAGE, stage))
    if review.mode in MOVING and review.next_move is None:
        problems.append((NO_NEXT_MOVE, review.mode))
    stated = frozenset().union(*(number_tokens(t) for t in review.texts()))
    for number in sorted(stated - catalogue.numbers):
        problems.append((NUMBER_NOT_IN_DOSSIER, number))
    return Validation(problems=tuple(problems))


__all__ = ["Appraisal", "DossierCatalogue", "ExpectedVsActual", "ExpertReview", "Fact", "Frames",
           "Hypothesis", "Inference", "LEVELS", "MODES", "MOVING", "NO_NEXT_MOVE",
           "NUMBER_NOT_IN_DOSSIER", "NextMove", "PATTERN_KINDS", "Pattern", "REFUSALS", "REVERSIBILITY",
           "Scenarios", "UNCITED_FACT", "UNGROUNDED_INFERENCE", "UNGROUNDED_PATTERN", "UNKNOWN_EVIDENCE",
           "UNKNOWN_STAGE", "Unknown", "Validation", "number_tokens", "validate"]
