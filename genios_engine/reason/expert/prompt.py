"""The expert's checklist, as its prompt — the thinking a 30-year chief of staff does, in order (STEP-12).

`speedrun008/YC-II W27/` STEP-12 §3.2 and `05` §4, tree `yc2_w27_s12` M32.C3.L-logic.V0.U01. Plane R's
Groups 1-4 compiled into the prompt's sections, in the order the checklist thinks:

  what is true → the frame and the rival frames → expected against actual, from the playbook's stage →
  patterns and counter-patterns, with their provenance → what is not known that would change the
  answer → the scenarios: doing nothing, acting now, the best, the worst, the signals to watch → the
  appraisal: stakes, urgency and reversibility, each with its reasons → the mode → the next move, an
  alternative, when to wait or stop, what done looks like → the draft

— over ONE file's dossier (`reason/expert/dossier`), which rides whole and FIRST (a long document
before the questions about it), then the rules, the checklist, and the answer's schema. The schema is
the review contract's own shape (`contracts/expert_review.ExpertReview.as_mapping`) and vocabularies:
together the steps ask for exactly the fields the contract reads, each once.

NO NUMBER OF ITS OWN. `validate` refuses a review that states a number its dossier does not hold, and a
number in the prompt is a number the model may repeat — so the instructions write none: no step is
numbered and no example carries a digit. Every number the model reads is the dossier's.

WHAT THE CHECK READS (STEP-13, `yc2_w27_s13` M35.C3.L-interface.V0.U04). Since STEP-13 every claim is
checked before anything reaches the founder (`reason/expert/verify`), and the checklist asks for what the
check reads: a fact the move rests on QUOTES the mail it cites; the move names the facts it rests on, whom
its draft goes to, and the ask it answers. And the card speaks to the founder as "you" — STEP-12's answers
named the company and "the founder" as parties (`03` F178): the rule says so now.

`PROMPT_VERSION` is one of a file's fingerprint inputs (`reason/expert/fingerprint`, `06` D48): change
the wording, change the version. Pure — the same dossier is the same prompt, byte for byte.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from genios_engine.contracts.company_brief import WORK_KINDS
from genios_engine.contracts.expert_review import (LEVELS, MODES, MOVING, NO_NEXT_MOVE, OWN_KINDS,
                                                   NUMBER_NOT_IN_DOSSIER, PATTERN_KINDS,
                                                   REVERSIBILITY, UNCITED_FACT,
                                                   UNGROUNDED_INFERENCE, UNGROUNDED_MOVE,
                                                   UNGROUNDED_PATTERN, UNKNOWN_EVIDENCE, UNKNOWN_STAGE)

from .dossier import Dossier

#: ⛔ v2 since M32.C1.L-contract.V0.U09 (2026-10-11): the frame step asks for a proposed kind of work.
#: No review was ever written under v1 — the pass was not yet wired. ⛔ v3 since STEP-13 (2026-10-12): the
#: quote, `rests_on`, `to`, `answers`, and "you". ⛔ CORRECTED 12 Oct (`06` D48, crosscheck X11): a version
#: change alone reviews no file again. The fingerprint names the prompt, so every fingerprint moves — and each
#: standing review is checked again on the dossier it was reviewed on, its file reviewed again only when the
#: file itself moved (`reason/expert/sweep`). ⛔ v4 since STEP-16 (`yc2_w27_s16` M46.C4.L-interface.V0.U02, 16 Oct): the
#: rules say what a correction is — the founder's word on the file, followed or outweighed in an inference citing it;
#: for a kind of work, over the playbook's prior; and a card called wrong is not advised again in its words uncited.
#: ⛔ v5 since STEP-13b (`yc2_w27_s13b` M37.C3.L-interface.V2.U04, 17 Oct): `_ONLY` is two rules — a fact is about the file;
#: reason from the file, the Engine and your own thirty years — the schema gains `own`, `guided_by` and
#: `rests_on: inference:N`, and one worked example of the format rides after it.
PROMPT_VERSION = "expert-review.v5"


def _or(words) -> str:
    words = list(words)
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} or {words[-1]}"


ROLE = (
    "You are the founder's chief of staff, thirty years in the work. You keep a file on every piece "
    "of work in motion — each investor, each application, each intro, each hire. Below is ONE file, "
    "as its dossier: the company brief, the file, what happened in it, the promises in its mail, its "
    "numbers, what was checked, what a professional knows about this kind of work, what the "
    "Engine knows about its situations, what its reasoning units measured, its situations, what was "
    "judged before, and what doing nothing does. Read all of it. Then think it through in "
    "the order of the checklist after it, and answer with one JSON object in the schema at the end.")

RULES_HEADING = "## THE RULES"
_FACT = ("A fact is about this file: it cites what the dossier shows of it — the file, its mail, its numbers. "
         "The Engine's lines and your own expertise are never facts about this file.")
_THREE = ("Reason from all three: the file's data, the Engine's lines and your own thirty years. Write "
          "your own knowledge as own lines — a practice, a base rate, a counter-pattern or a benchmark — in "
          "words, with no number and no name of this file. A line of the engine is a prior about the work; a "
          "line learned from your company's people is the company's own history. Where you disagree with the "
          "engine, say so in an inference that cites both.")
_CITE = ("Every fact, and a proposed kind of work, cites at least one id the dossier prints in square "
         "brackets — the id alone, without the brackets.")
_QUOTE = ("A fact your next move rests on, that cites a mail whose words the dossier shows, carries those "
          "words in its quote — a whole phrase, copied exactly as the dossier prints it, never reworded.")
_GROUND = ("An inference or a pattern rests on ids the dossier prints, or on your own facts as fact:N, "
           "N being the fact's place in your list, counting from one, or on an own line as own:N — which "
           "grounds it only beside a line of the file's data.")
_NUMBERS = ("In every sentence you write, the draft included, use no number the dossier does not hold: "
            "no count of days, sum, share or date you worked out yourself. Copy a number from the "
            "dossier, or say it without one (over a week, most of them). The next move's by_when is "
            "the one date you set yourself.")
_STAGE = ("The stage is the name of one of the playbook's stages exactly as the dossier lists it — the "
          "name before its label in parentheses — or null when the dossier lists none.")
_LEVELS = (f"Stakes and urgency are {_or(LEVELS)}; reversibility is {_or(REVERSIBILITY)}. A level, "
           "never a score.")
_MODE = (f"The mode is {_or(MODES)}; {_or(sorted(MOVING))} always name a next move. Otherwise the next "
         "move may be null.")
_MOVE = ("The next move lists the facts it rests on in rests_on, as fact:N, or an inference of yours that "
         "rests on facts, as inference:N; guided_by lists the lines of the engine or your own, as own:N, that "
         "it follows. A move that sends something "
         "says in to whom it goes: someone the file's mail shows — never the founder or the company, and "
         "never the connector who introduced the person this file is about. A move that answers an ask "
         "the founder owes gives that ask's loop id in answers.")
_PRIOR = ("The playbook is a prior about this kind of work, not a fact about this file; where it is not "
          "yet reviewed, weigh it as such.")
_SOON = "A promise to answer soon is no deadline: judge from the dates whether soon has passed."
_NO_REPLY = "Say that nobody replied only where WHAT WAS CHECKED says it may be said."
_UNKNOWN = "What would change your answer and is not in the dossier is an unknown — named, never guessed."
_YOU = ("Speak to the founder as you, and of the company as yours: never write the founder, and never their "
        "name or the company's as a party.")
# STEP-16 · your correction changes the next judgment, and never silently (`reason/expert/verify` holds a move made
# over a correction the review does not cite, and a move in the words of a card called wrong, as ONE question).
_CORRECTION = ("A correction under WHAT YOU CORRECTED is the founder's word on this file: follow it, or say why "
               "the file now outweighs it, in an inference that cites its corr: id. A correction for the kind of "
               "work outweighs the playbook's prior for this company. A card the founder called wrong is not "
               "advised again in its words unless you cite it and their verdict.")
RULES: tuple[str, ...] = (_FACT, _THREE, _CITE, _QUOTE, _GROUND, _NUMBERS, _STAGE, _LEVELS, _MODE, _MOVE, _PRIOR,
                          _SOON, _NO_REPLY, _UNKNOWN, _YOU, _CORRECTION)

#: For every refusal `validate` can make, the rule that tells the model how not to earn it — a
#: refusal the prompt never warned of would be the model's fault on paper and the prompt's in fact.
RULE_FOR_REFUSAL: dict[str, str] = {
    UNCITED_FACT: _CITE, UNKNOWN_EVIDENCE: _CITE, UNGROUNDED_INFERENCE: _GROUND,
    UNGROUNDED_PATTERN: _GROUND, UNKNOWN_STAGE: _STAGE, NO_NEXT_MOVE: _MODE,
    NUMBER_NOT_IN_DOSSIER: _NUMBERS,
    UNGROUNDED_MOVE: _MOVE,
}

#: What each mode means — the contract's modes, in its order. Code maps a mode to the decision.
MODE_MEANINGS: dict[str, str] = {
    "act": "there is a move to make now",
    "find_out": "a question must be answered before anyone moves",
    "wait": "nothing is to be done until a date or a signal",
    "nothing": "the file needs nothing from the founder",
    "blocked": "someone else must move first",
}


@dataclass(frozen=True, slots=True)
class Step:
    """One step of the checklist: its heading, what it asks, and the review fields it fills."""
    name: str
    title: str
    asks: str
    fields: tuple[str, ...]


CHECKLIST_HEADING = "## THE CHECKLIST — think in this order"
CHECKLIST: tuple[Step, ...] = (
    Step("true", "WHAT IS TRUE",
         "Establish what is true in this file before judging it: each fact in one sentence, with the "
         "ids of the dossier items that show it — and where your next move will rest on it and it cites a "
         "mail, the mail's own words. Then what follows from those facts that the dossier does not say "
         "outright — each inference with what it rests on.",
         ("facts", "inferences")),
    Step("frame", "THE FRAME, AND THE RIVAL FRAMES",
         "Say what situation this is — the frame you would brief the founder with — and at least one "
         "rival: what else it could be, that the same facts would also fit. And if the file's kind of "
         "work — what THE FILE says the brief names it, or that it names none — is missing or wrong, "
         f"the kind you would give it: {_or(WORK_KINDS)}, why, and the ids that show it — proposed to "
         "the founder, never applied. Otherwise null.",
         ("frames", "proposed_kind")),
    Step("expected", "EXPECTED AGAINST ACTUAL",
         "Name the stage the file is in, from its playbook's stages; say what the playbook expects at "
         "that stage, and what has actually happened. Without a playbook the stage is null, and what "
         "is expected comes from the brief and the file's own history.",
         ("expected_vs_actual",)),
    Step("patterns", "PATTERNS AND COUNTER-PATTERNS",
         f"What usually happens in cases like this, and when it does not — each line a {_or(PATTERN_KINDS)}, "
         "with what it rests on, so its provenance can be checked: the founder's own patterns from the "
         "file's numbers and history, the profession's from the playbook and the engine. A pattern the "
         "dossier does not hold is not written. Then, from your own thirty years, what you know of this kind "
         f"of work that the dossier does not — each a {_or(OWN_KINDS)}, in words, with why it holds.",
         ("patterns", "own")),
    Step("unknowns", "WHAT IS NOT KNOWN",
         "The facts that would change your answer and that the dossier does not hold, each with why it "
         "matters; and the hypotheses still open, each with what would settle it. Name them; never fill "
         "them in.",
         ("unknowns", "hypotheses")),
    Step("scenarios", "THE SCENARIOS",
         "What happens if nothing is done; what happens if you act now; the best case and the "
         "worst case; and the signals to watch — what would tell you which way it is going.",
         ("scenarios",)),
    Step("appraisal", "THE APPRAISAL",
         "How much is at stake, how urgent it is, and how reversible a wrong move would be — each a "
         "level, never a score — with the reasons, from the dossier.",
         ("appraisal",)),
    Step("mode", "THE MODE",
         "How to intervene: " + "; ".join(f"{mode} — {meaning}"
                                          for mode, meaning in MODE_MEANINGS.items()) + ".",
         ("mode",)),
    Step("next_move", "THE NEXT MOVE",
         "The best next move — who makes it, what it is, for whom, and by when; the facts it rests on; "
         "whom its draft goes to; the ask it answers, if it answers one; an alternative, if the best one "
         "is refused; when to wait, and when to stop; and what done looks like. Where the founder "
         "corrected the file, the move follows the correction — or an inference citing it says why not.",
         ("next_move", "alternative", "wait_or_stop", "done_when")),
    Step("draft", "THE DRAFT",
         "When the move is a message, the draft: the words the founder could send as they are — short, "
         "in their voice, saying nothing the dossier does not hold. Otherwise null.",
         ("draft",)),
)

SCHEMA_HEADING = "## THE ANSWER — one JSON object, in this shape"
_CITED = "an id the dossier prints in square brackets, without them"
_RESTS_ON = "fact:N, own:N, or an id the dossier prints"
SCHEMA: dict[str, Any] = {
    "facts": [{"claim": "what is true, in one sentence", "evidence": [_CITED],
               "quote": "the cited mail's own words this fact rests on, copied — or null"}],
    "inferences": [{"claim": "what follows, that the dossier does not say outright",
                    "based_on": [_RESTS_ON]}],
    "patterns": [{"kind": " | ".join(PATTERN_KINDS), "claim": "what usually happens, or when it does not",
                  "based_on": [_RESTS_ON]}],
    "own": [{"kind": " | ".join(OWN_KINDS), "claim": "what you know of this kind of work, in words, with no number",
             "why": "why it holds"}],
    "hypotheses": [{"proposition": "what might be true", "needs": "what would settle it"}],
    "unknowns": [{"question": "what is not known", "relevance": "why the answer would change the judgment"}],
    "frames": {"primary": "the situation this is", "rivals": ["what else it could be"]},
    "proposed_kind": {"kind": " | ".join(WORK_KINDS), "why": "why this kind, from the dossier",
                      "evidence": [_CITED]},
    "expected_vs_actual": {"stage": "a stage name from the playbook, or null",
                           "expected": "what is expected at this stage", "actual": "what has happened"},
    "scenarios": {"do_nothing": "if nothing is done", "act": "if you act now",
                  "best": "the best case", "worst": "the worst case",
                  "signals_to_watch": ["what would tell you which way it is going"]},
    "appraisal": {"stakes": " | ".join(LEVELS), "urgency": " | ".join(LEVELS),
                  "reversibility": " | ".join(REVERSIBILITY), "reasons": ["a reason, from the dossier"]},
    "mode": " | ".join(MODES),
    "next_move": {"who": "who makes it", "what": "what it is", "for_whom": "for whom",
                  "by_when": "a date as YYYY-MM-DD, or null", "rests_on": ["fact:N | inference:N"],
                  "guided_by": ["an engine line's id, or own:N"],
                  "to": "whom its draft goes to, as the dossier names them — or null",
                  "answers": "the loop id of the ask it answers, as the dossier prints it — or null"},
    "alternative": "the next best move",
    "wait_or_stop": "when to wait, and when to stop",
    "done_when": "what done looks like",
    "draft": "the words to send, or null",
}

EXAMPLE_HEADING = "## THE FORMAT, ONCE — an example of the shape, not of any file"
#: One worked example of the shape the check reads. Its ids are ones no dossier prints and it holds no digit (this
#: module's own rule), so a model copies the shape and never a value.
_EXAMPLE: dict[str, Any] = {
    "facts": [{"claim": "the person asked for a document", "evidence": ["evt_example"],
               "quote": "could you send the document"}],
    "inferences": [{"claim": "the next move is ours", "based_on": ["fact:N"]}],
    "own": [{"kind": "practice", "claim": "a request answered the same day keeps the thread warm",
             "why": "a reply that waits loses the person's attention"}],
    "patterns": [{"kind": PATTERN_KINDS[0], "claim": "a written ask is usually followed up once",
                  "based_on": ["rule:example", "own:N"]}],
    "next_move": {"who": "you", "what": "send the document", "for_whom": "the person",
                  "rests_on": ["fact:N", "inference:N"], "guided_by": ["rule:example", "own:N"]}}
EXAMPLE_TEXT = json.dumps(_EXAMPLE, indent=2, ensure_ascii=False)
REPAIR_HEADING = "## YOUR LAST ANSWER"
LAST_WORD = "Answer with the JSON object only — nothing before it, nothing after it."


def schema_text() -> str:
    return json.dumps(SCHEMA, indent=2, ensure_ascii=False)


def build_prompt(dossier: Dossier, feedback: str | None = None) -> str:
    """The prompt for one file's review — the role, its dossier whole, the rules, the checklist in
    order, the schema, the gate's complaint when this is the one repair, and the last word."""
    parts = [ROLE, f"<dossier>\n{dossier.text}\n</dossier>",
             RULES_HEADING + "\n" + "\n".join(f"- {rule}" for rule in RULES),
             CHECKLIST_HEADING + "\n\n" + "\n\n".join(f"### {step.title}\n{step.asks}"
                                                    for step in CHECKLIST),
             f"{SCHEMA_HEADING}\n{schema_text()}", f"{EXAMPLE_HEADING}\n{EXAMPLE_TEXT}"]
    complaint = " ".join(str(feedback or "").split())
    if complaint:
        parts.append(f"{REPAIR_HEADING}\n{complaint}")
    parts.append(LAST_WORD)
    return "\n\n".join(parts)


__all__ = ["CHECKLIST", "CHECKLIST_HEADING", "EXAMPLE_HEADING", "EXAMPLE_TEXT", "LAST_WORD", "MODE_MEANINGS", "PROMPT_VERSION",
           "REPAIR_HEADING", "ROLE", "RULES", "RULES_HEADING", "RULE_FOR_REFUSAL", "SCHEMA",
           "SCHEMA_HEADING", "Step", "build_prompt", "schema_text"]
