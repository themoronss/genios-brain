"""R-2's prompt — what the model is shown, and what it is not.

**It is shown a decision that is already made.** Not a situation to judge: an action id, the score
that won it, the alternatives that lost and why, the units' findings, the authored claims, and the
catalogue of numbers the deterministic half computed. There is nothing in this prompt to choose
between, which is what makes "the model may narrate but never choose" a property of the input rather
than an instruction in it.

**It is shown the VALUES of the numbers, and cannot type them.** A narrator that could not see that
the engagement gap was large would have no way to write "sharply" rather than "slightly", and prose
that is hedged uniformly is prose nobody reads. So the catalogue carries `name = value — meaning`,
and V-4 refuses any digit or spelled-out quantity in the answer. The model reads the magnitude and
writes `{name}`; code substitutes. Seeing is interpretation, which the doctrine allows; typing is
generating a number, which it does not.

**It is shown one decision's material and nothing else.** Everything here comes from `Grounding` and
`Catalogue`, both built from a single decision — no query, no other tenant, no other subject.

**The hedging is bound to the evidence, not to taste.** Doc 09 case 4: a root cause that sounds more
certain than the confidence vector is a failure mode, so the weakest named axis is stated in the
prompt with the qualifier it obliges.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.contracts.reasoning import BUNDLE_FIELD_CAPS, ReasoningDecision

from .gauntlet import DESCRIPTIVE_FIELDS, DIRECTIVE_FIELD, MAX_SENTENCES
from .grounding import Grounding
from .numbers import Catalogue

#: Below this, the narrative must carry an explicit qualifier naming what is thin. 7000 bp is the
#: point at which "the engine is fairly sure" stops being an honest reading of a number, and it sits
#: above the compiled lane's 4500 bp confidence floor so that a decision which cleared the floor can
#: still be one the prose has to hedge.
HEDGE_BELOW_BP = 7_000

#: What each section must ANSWER. Written as a question because a section brief written as a topic
#: ("the root cause") produces a paraphrase of the headline, and a section brief written as a
#: question produces an answer.
SECTION_BRIEFS = {
    "headline": ("the card's title. What is happening and to what. No terminal full stop needed. "
                 "A phrase, not a sentence."),
    "situation_summary": "What is happening right now, in the units' own terms?",
    "why_it_matters": ("What does it cost if this is left alone? Use the priced numbers from the "
                       "catalogue. This section carries the consequence."),
    "root_cause": ("WHY is this happening? Name the chain — which reading drove it and what that "
                   "reading rests on. Not a restatement of the situation."),
    "recommendation_rationale": ("Why THIS action rather than the alternatives that lost? Name the "
                                 "committed action, then say what removed the others."),
    "expected_effect": ("What changes if this is acted on, and what stands if it is not? Both "
                        "halves. Say when the effect should be visible."),
    "alternatives_narrative": ("Optional. Why the strongest rejected option lost, in one or two "
                               "sentences."),
}


def _catalogue_block(catalogue: Catalogue) -> str:
    lines = [f"  {{{item.name}}} = {item.value}   — {item.label}" for item in catalogue.numbers]
    if catalogue.truncated:
        lines.append(f"  (+{catalogue.truncated} lower-ranked numbers omitted; you may not "
                     "reference them)")
    return "\n".join(lines) or "  (no computed numbers — write the sections without any)"


def _observations_block(grounding: Grounding) -> str:
    lines = []
    for observation in grounding.observations[:12]:
        magnitude = observation.get("value_bp")
        parts = [f"  - {observation.get('unit')} found "
                 f"{str(observation.get('finding') or '').replace('_', ' ')}"]
        if magnitude is not None:
            parts.append(f" (magnitude {magnitude} bp)")
        metrics = {key: value for key, value in dict(observation.get("metrics") or {}).items()}
        if metrics:
            parts.append(f" metrics={json.dumps(metrics, sort_keys=True, default=str)[:200]}")
        codes = list(observation.get("reason_codes") or ())
        if codes:
            parts.append(f" reasons={', '.join(codes[:4])}")
        lines.append("".join(parts))
    return "\n".join(lines) or "  (no unit findings were recorded on this decision)"


def _alternatives_block(grounding: Grounding) -> str:
    lines = []
    for rejected in grounding.rejected[:6]:
        eliminated = rejected.get("eliminated_by") or []
        why = (f"eliminated by an authored rule: "
               f"{'; '.join(str(item.get('statement') or item.get('rule_id')) for item in eliminated)}"
               if eliminated else
               f"ranked below the recommendation at {rejected.get('utility_bp')} bp")
        lines.append(f"  - {rejected.get('label')} — {why}")
    return "\n".join(lines) or "  (nothing else was on the table)"


def _citations_block(citations: Sequence[Mapping[str, Any]]) -> str:
    lines = []
    for citation in citations[:8]:
        lines.append(f'  - {citation.get("artifact_class")} {citation.get("artifact_id")}: '
                     f'"{citation.get("statement")}"')
    return "\n".join(lines) or ("  (this decision quotes no authored claim; do not put anything in "
                                "quotation marks)")


def _hedging(decision: ReasoningDecision) -> str:
    """Doc 09 case 4 — the qualifier the weakest named axis obliges."""
    vector = {key: int(value) for key, value in dict(decision.confidence_vector or {}).items()
              if key.endswith("_bp")}
    weakest = min(vector.items(), key=lambda item: (item[1], item[0])) if vector else None
    if weakest is None:
        return ("The confidence vector was not recorded on this decision. Do not claim certainty "
                "about causes: write the root cause as what the evidence shows, not as what is "
                "true.")
    name, value = weakest
    if value >= HEDGE_BELOW_BP:
        return (f"The weakest confidence axis is {name.replace('_', ' ')} at {value} bp, which is "
                "adequate. Write plainly; no extra hedging is required.")
    return (f"The weakest confidence axis is {name.replace('_', ' ')} at {value} bp. The root "
            "cause and expected effect MUST carry a qualifier that names this limit in words "
            "(for example: on the evidence available). Prose that sounds more certain than this "
            "number will be rejected.")


def build_prompt(decision: ReasoningDecision, *, catalogue: Catalogue, grounding: Grounding,
                 citations: Sequence[Mapping[str, Any]] = (), feedback: str | None = None,
                 locale: str = "en") -> str:
    """The R-2 prompt. `feedback` is the gauntlet's complaint on the ONE regeneration."""
    selected = dict(grounding.selected or {})
    caps = "\n".join(
        f"  {name}: at most {BUNDLE_FIELD_CAPS[name]} characters, at most {MAX_SENTENCES} "
        f"sentences — {SECTION_BRIEFS[name]}"
        for name in SECTION_BRIEFS)
    language = ("Write in the same language and register as the material above, including "
                "mixed-script material — do not translate a customer's own words."
                if locale not in {"en", "en-US", "en-GB"} else
                "Write in English, in the register of the material above. Where the material is "
                "mixed-script, keep quoted fragments in their original script.")
    retry = ""
    if feedback:
        retry = (
            "\n\nYOUR PREVIOUS ANSWER WAS REJECTED. Fix exactly these and change nothing else:\n"
            f"{feedback}\n")

    return f"""You are the reasoning narrator for GeniOS. You explain a decision that has ALREADY
been made by a deterministic engine. You may interpret evidence and narrate reasoning. You may
never choose, score, rank, or permit anything.

THE DECISION IS FIXED. It is not a proposal and you cannot change it:
  committed action : {selected.get('play_id')} — {selected.get('label')}
  steps            : {json.dumps(list(selected.get('steps') or []), default=str)[:600]}
  ranked           : position {selected.get('rank_position')} at {selected.get('utility_bp')} bp
  score components : {json.dumps(dict(selected.get('score_components') or {}), sort_keys=True)[:400]}
  outcome          : {decision.outcome.value}
  do-nothing       : {json.dumps(dict(decision.do_nothing or {}), sort_keys=True, default=str)[:300]}
  uncertainty      : {json.dumps(list(decision.uncertainty), default=str)[:300]}

WHAT THE UNITS FOUND (this is your evidence; you may not add to it):
{_observations_block(grounding)}

WHAT ELSE WAS ON THE TABLE, AND WHY IT LOST:
{_alternatives_block(grounding)}

AUTHORED EXPERT CLAIMS you may quote. A quotation must be BYTE-IDENTICAL to one of these; if you
cannot quote one exactly, do not use quotation marks at all:
{_citations_block(citations)}

THE NUMBER CATALOGUE. These are the only numbers that exist. Reference one by writing its
placeholder EXACTLY as shown, braces included. Code substitutes the value after you answer:
{_catalogue_block(catalogue)}

HARD RULES — a violation is rejected, not corrected:
  1. NEVER write a digit. Never write a quantity as a word either (fourteen, twice, half, hundred).
     Write the placeholder. If a number you want is not in the catalogue, it does not exist: leave
     the claim out.
  2. Every sentence must rest on the material above. A sentence about anything else is rejected.
  3. Name only entities that appear above. Do not invent a company, a person, an address or a URL.
  4. Only `{DIRECTIVE_FIELD}` may instruct, and it may only instruct the committed action above.
     These sections must DESCRIBE and never tell anyone to do anything: {', '.join(DESCRIPTIVE_FIELDS)}.
  5. You may name a rejected option only while saying it lost.
  6. Plain prose. No markdown, no bullet lists, no headings, no code fences.

HEDGING: {_hedging(decision)}

{language}

SECTIONS — answer each question, do not restate the others:
{caps}

Return STRICT JSON only, with exactly these keys and nothing else:
{{"headline": "...", "situation_summary": "...", "why_it_matters": "...", "root_cause": "...",
 "recommendation_rationale": "...", "expected_effect": "...", "alternatives_narrative": "..."}}
Omit "alternatives_narrative" entirely if nothing was rejected.{retry}"""


__all__ = ["HEDGE_BELOW_BP", "SECTION_BRIEFS", "build_prompt"]
