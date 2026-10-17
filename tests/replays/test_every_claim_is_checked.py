"""STEP-13 · M35's acceptance — nothing the expert says reaches you unchecked, proven by mutation on the golden set.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_every_claim_is_checked.py -q

Tree `yc2_w27_s13` M35.C4.L-integration.V1.U03 (M35's `ships`, and the STEP-13 crosscheck's "Acceptance by
mutation" row, X37). Every case runs through the REAL chain (`engine_runner.run_case`), its model answered from
its cassette (`harness.RecordedLLM`, no spend), and three things are measured:

  1 · EVERY AUTHORED REVIEW STANDS ITS CHECK WHOLE. For every case that authors the expert's answers, every
      `expert_reviews` row the sweep door wrote — one per dossier it served — is valid, checked under the
      current check version, its move SHOWN (a find-out review asking its own question, a wait or nothing
      moving nothing), and no line of it DROPPED — but the one drop `DECLARED_DROPS` names, with why.

  2 · EACH MUTATION OF A SERVED ANSWER IS CAUGHT ON ITS OWN CASE, WITH ITS REASON, AND THE CARD IT WOULD HAVE
      MADE DOES NOT APPEAR. The recorded model is wrapped: at the expert site, on the named serving of one
      file's review, the recorded answer gets ONE mutation (`MUTATIONS`) and is returned. The serving is the
      LAST, so no later prompt reads a card the mutation changed — but F28's first of two: a later serving
      whose headline is unchanged leaves the card with the first serving's words (measured, 13 Oct: F28's
      second-serving quote and F03's third-serving draft reached no card even unchecked), and F28's mutation
      moves neither its headline nor its review's mode, so its second prompt is the recorded one. The
      stored check of that review must record the expected verdict on the expected line, with its
      `claim_check` reason (and drop nothing else), and the expected fate; and no decision card — every text a card carries: headline, situation, why (its
      `expert_check` sources among them), actions, artifact, do_nothing_consequence, success_signal,
      abstained_because — may say what the mutation would have made the founder read (`reads`). A
      correction must keep what is right beside it (`keeps`: X08, a time in the draft is never rewritten).
      Then the same with QUESTION cards included, and the words the mutation wrote into a fact (`echo`): a
      held question never repeats them (M36.C2.L-logic.V2.U10 fix, the second crosscheck G2 — until it, three
      of them were xfail-strict on X10).

  3 · THE NEGATIVE CONTROL. The same mutation with the check switched off — every line passed as written
      (`tests/reason/expert/checks.as_written`) — must put what it `reads` on a card. A mutation that reaches no
      card unchecked tests nothing about the check, and is redrawn until it does.

Each mutation is chosen by measurement (the authored answers, `specs/founder/F*.json` `model.expert`, and the
dossiers the sweep door serves them): must-detect cases that pass today where one exercises it (F11, F26,
F04, F28, F49, F51), else the case whose dossier holds the shape (F19's three people, F45's answered ask and
its older touches, F05's "Altavia"). What the golden set cannot express is declared, not mutated: a lakh
figure (F18's mail, the only one, is reviewed by no expert — `a_value_in_another_unit` holds the same rule on
"20 minutes"), a person who introduced a file (every golden introducer is Introly, a company), an answered ask
beside another still owed, and a fact citing the founder's answer (no golden question is answered).
"""
from __future__ import annotations

import copy
import dataclasses
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from genios_engine.contracts.claim_check import (ANSWERED, BY_ALTERNATIVE, BY_CALCULATOR, CHECK_VERSION, CORRECTED,
                                                 DROPPED, HELD, KEPT, MISQUOTED, RECIPIENT_IS_CONNECTOR,
                                                 RECIPIENT_IS_US, SHOWN, SUPPRESSED, UNGROUNDED, UNQUOTED,
                                                 UNSUPPORTED, WRONG_NUMBER, CheckedReview)
from tests.replays.founder_case import load_cases
from tests.replays.harness import CassetteMiss, RecordedLLM, identify_site
from tests.replays.ideal_reader import IdealReader, without_company_brief

pytestmark = [pytest.mark.pg, pytest.mark.golden]

CASES = {case.case_id: case for case in load_cases()}
#: Every case that authors the expert's answers — every case whose sweeps review a file.
AUTHORED = tuple(sorted(c for c, case in CASES.items() if (case.model or {}).get("expert")))

#: The one line of the authored set the check drops, measured on the golden lane (12-13 Oct): F15's Lattice
#: Capital file, its general (wait) answer's fact 6 — "This is the first time the founder's history holds
#: Lattice Capital." It cites history readings alone, which print no name, and the file's counterparty is
#: known only as `latticecap.test`: "Lattice" begins that label, "Capital" is no part of it, so the name is
#: on no line of its own (M35.C2.L-logic.V1.U12) — "Cobalt Peak" stands the same sentence on `cobaltpeak`.
#: The fact is no ground of the move (`rests_on` fact 1, 2): the fate stays shown and no card changes. The
#: authored text is not this unit's to edit; the drop is pinned exactly, so any other is seen.
DECLARED_DROPS: dict[tuple[str, str], frozenset[tuple[str, str, str]]] = {
    ("F15", "latticecap.test"): frozenset({("fact:6", UNSUPPORTED, "name:Capital")}),
}



# ── the mutations ──────────────────────────────────────────────────────────────────────────────────────────

Answer = dict[str, Any]


@dataclass(frozen=True)
class Mutation:
    """One mutation of one served answer, and what the check must make of it."""
    id: str
    case: str
    key: str                                      # the file, as its dossier names it: `<key>`
    serving: int                                  # which serving of that file's review it mutates
    mutate: Callable[[Answer, str], Answer]       # (the served answer, the prompt) → the mutated answer
    line: str                                     # the line the check must record it on
    verdict: str
    reason: str
    detail: str                                   # in the verdict's detail ("" = anything)
    fate: str
    reads: tuple[str, ...]                        # what the founder reads, unchecked, because of it
    also: tuple[tuple[str, str, str], ...] = ()   # other verdicts the same mutation must record
    keeps: tuple[str, ...] = ()                   # what the checked card must still say
    echo: tuple[str, ...] = ()                    # words it wrote into a fact — never a card text
    finding: str = ""                             # why a question card still carries them (xfail-strict)


def _fact(answer: Answer, n: int) -> dict[str, Any]:
    return answer["facts"][n - 1]


def _replaced(text: str | None, old: str, new: str) -> str:
    assert text and old in text, f"the served answer does not say {old!r}: {text!r}"
    return text.replace(old, new)


def _drop_quote(n: int) -> Callable[[Answer, str], Answer]:
    def mutate(answer: Answer, _prompt: str) -> Answer:
        assert _fact(answer, n).get("quote"), f"fact {n} carries no quote to remove"
        _fact(answer, n)["quote"] = None
        return answer
    return mutate


def _set_quote(n: int, quote: str, *, rest_on: bool = False) -> Callable[[Answer, str], Answer]:
    def mutate(answer: Answer, _prompt: str) -> Answer:
        _fact(answer, n)["quote"] = quote
        if rest_on:
            assert f"fact:{n}" not in answer["next_move"]["rests_on"]
            answer["next_move"]["rests_on"] = [*answer["next_move"]["rests_on"], f"fact:{n}"]
        return answer
    return mutate


def _quote_says(n: int, old: str, new: str) -> Callable[[Answer, str], Answer]:
    def mutate(answer: Answer, _prompt: str) -> Answer:
        _fact(answer, n)["quote"] = _replaced(_fact(answer, n).get("quote"), old, new)
        return answer
    return mutate


def _claim_says(n: int, old: str, new: str) -> Callable[[Answer, str], Answer]:
    def mutate(answer: Answer, _prompt: str) -> Answer:
        _fact(answer, n)["claim"] = _replaced(_fact(answer, n)["claim"], old, new)
        return answer
    return mutate


def _move_says(old: str, new: str) -> Callable[[Answer, str], Answer]:
    def mutate(answer: Answer, _prompt: str) -> Answer:
        answer["next_move"]["what"] = _replaced(answer["next_move"]["what"], old, new)
        return answer
    return mutate


def _draft_says(old: str, new: str) -> Callable[[Answer, str], Answer]:
    def mutate(answer: Answer, _prompt: str) -> Answer:
        answer["draft"] = _replaced(answer.get("draft"), old, new)
        return answer
    return mutate


def _do_nothing_says(before: str = "", after: str = "") -> Callable[[Answer, str], Answer]:
    def mutate(answer: Answer, _prompt: str) -> Answer:
        said = answer["scenarios"]["do_nothing"]
        answer["scenarios"]["do_nothing"] = f"{before}{said}{after}"
        return answer
    return mutate


def _to(to: str) -> Callable[[Answer, str], Answer]:
    def mutate(answer: Answer, _prompt: str) -> Answer:
        assert answer.get("draft"), "a draft to mutate the recipient of"
        answer["next_move"]["to"] = to
        return answer
    return mutate


def _both(*steps: Callable[[Answer, str], Answer]) -> Callable[[Answer, str], Answer]:
    """One mutation written in several places of the answer — a misreading and what follows from it."""
    def mutate(answer: Answer, prompt: str) -> Answer:
        for step in steps:
            answer = step(answer, prompt)
        return answer
    return mutate


def _misattributed(answer: Answer, prompt: str) -> Answer:
    """F19: Naveen asked for the agreement; the answer says Ritika did — Ritika is on the file (her own mail
    asks for the report), never on Naveen's — and sends her the draft."""
    answer = _claim_says(1, "Naveen Gupta of the Incubation Cell asked",
                         "Ritika Sharma of the Incubation Cell asked")(answer, prompt)
    answer["draft"] = _replaced(answer.get("draft"), "Naveen", "Ritika")
    answer["next_move"]["what"] = _replaced(answer["next_move"]["what"], "send Naveen", "send Ritika")
    answer["next_move"]["to"] = "Ritika"
    return answer


def _sibling(answer: Answer, _prompt: str) -> Answer:
    """F49: a fact citing only the quiet calculator writes the longest gap's value, printed on the same line
    (crosscheck X02) — and the cost of ignoring restates it."""
    fact = _fact(answer, 3)
    assert "num:days_quiet" in fact["evidence"]
    fact["evidence"] = ["num:days_quiet"]
    fact["claim"] = "Nothing from Arjun has followed: the file has been quiet for 0.06 days."
    return _do_nothing_says(before="The file has been quiet for 0.06 days. ")(answer, _prompt)


def _beside_a_time(answer: Answer, _prompt: str) -> Answer:
    """F51: a fact's quiet written as "3 days" (its calculator says 3.25), restated in the cost of ignoring —
    while the draft names "Tuesday 4 Aug at 3pm": the correction rewrites the restated figure, never the time
    (crosscheck X08)."""
    fact = _fact(answer, 4)
    assert "num:days_quiet" in fact["evidence"]
    fact["claim"] = ("Her mail is the file's only touch, and the file has been quiet for 3 days; the dossier "
                     "says we have not written in the file and marks the move as ours.")
    return _do_nothing_says(before="The file has been quiet for 3 days. ")(answer, _prompt)


def _to_the_connector_without_a_draft(answer: Answer, _prompt: str) -> Answer:
    """F04: no draft, no `to` — the move itself names the connector, Introly, first (crosscheck X20)."""
    answer["draft"] = None
    answer["next_move"]["to"] = None
    answer["next_move"]["what"] = "Ask Introly to pass a short note to Sofia Brandt offering a demo"
    return answer


def _the_asked_fact(answer: Answer) -> dict[str, Any]:
    asks = [f for f in answer["facts"] if any(str(e).startswith("loop:") for e in f["evidence"])]
    assert len(asks) == 1, f"one fact cites the file's ask: {asks}"
    return asks[0]


def _answers_the_answered_ask(answer: Answer, _prompt: str) -> Answer:
    """F45: the move names, as the ask it answers, the hiring question our reply of 20 Aug answered."""
    answer["next_move"]["answers"] = next(e for e in _the_asked_fact(answer)["evidence"]
                                          if str(e).startswith("loop:"))
    return answer


def _rests_on_the_answered_ask(answer: Answer, _prompt: str) -> Answer:
    """F45: the move names no `answers`, and its ground cites the answered hiring question as still owed —
    the ask alone, not the reply that answered it (crosscheck X21)."""
    fact = _the_asked_fact(answer)
    fact["evidence"] = [e for e in fact["evidence"] if str(e).startswith("loop:")]
    fact["claim"] = "The file lists her hiring question as an open ask that waits on us."
    fact["quote"] = None
    assert not answer["next_move"].get("answers")
    return answer


_OLDER = re.compile(r"\[(evt_[0-9a-f]+)\] [^\n]*· they wrote · [^\n]*\(older — its words not shown\)")


def _on_an_older_touch(answer: Answer, prompt: str) -> Answer:
    """F45: the decisive fact that Meera asked for reference calls, re-pointed at her oldest mail — one the
    dossier prints without its words (crosscheck X01, X22)."""
    older = _OLDER.findall(prompt)
    assert older, "the dossier prints no older touch without its words"
    _fact(answer, 1)["evidence"] = [older[-1]]
    return answer


#: What a fall takes with it, measured: F11's second inference rests on fact 1 alone; F26's "11 am" is on fact 2's
#: mail only, so with fact 2 down the move and its draft no longer stand on their lines either.
_FELL_F11 = (("inference:2", DROPPED, UNGROUNDED),)
_FELL_F26 = (("move", DROPPED, WRONG_NUMBER), ("draft", DROPPED, WRONG_NUMBER))

MUTATIONS: tuple[Mutation, ...] = (
    # ── a decisive fact's quote ──
    Mutation("a_decisive_quote_removed", "F11", "northfieldvc.test", 1, _drop_quote(1),
             "fact:1", DROPPED, UNQUOTED, "", HELD,
             reads=("Reply to Tom that you are raising your seed round now",), also=_FELL_F11),
    Mutation("a_decisive_quote_misquoted", "F11", "northfieldvc.test", 1,
             _quote_says(1, "in a founder community", "at a demo day"),
             "fact:1", DROPPED, MISQUOTED, "at a demo day", HELD,
             reads=("came across Nimbus Labs at a demo day",), also=_FELL_F11),
    Mutation("a_wrong_number_inside_a_quote", "F26", "orbitly.test", 1, _quote_says(2, "11 am", "10 am"),
             "fact:2", DROPPED, MISQUOTED, "10 am", HELD,
             reads=("Would Tuesday 30 Sep, 10 am IST work for you",), also=_FELL_F26),
    Mutation("a_quote_on_a_calculator", "F26", "orbitly.test", 1,
             _set_quote(4, "Neha has waited nine days for our answer", rest_on=True),
             "quote:4", DROPPED, MISQUOTED, "Neha has waited", SHOWN,
             reads=("Neha has waited nine days for our answer",)),
    # ⛔ RESTATED by `yc2_w27_s14` (M42, the living card): served to the file's SECOND review. F28's second review
    # versions the one card its first made, so what the first review's card said is a version the card no longer
    # shows — the negative control reads the card's current words, and the second review is the one they are.
    Mutation("a_quote_on_an_unworded_meeting", "F28", "novacore.test", 2,
             _set_quote(2, "Ishita confirmed the call for the eighth"),
             "quote:2", DROPPED, MISQUOTED, "Ishita confirmed", SHOWN,
             reads=("Ishita confirmed the call for the eighth",)),
    Mutation("two_generic_words_as_a_quote", "F26", "orbitly.test", 1, _set_quote(2, "a call"),
             "fact:2", DROPPED, MISQUOTED, "a call", HELD,
             reads=("Reply to Neha to confirm Tuesday 30 Sep at 11 am IST",), also=_FELL_F26),
    # ── names ──
    Mutation("a_misattributed_speaker", "F19", "ditincubator.test", 2, _misattributed,
             "fact:1", DROPPED, UNSUPPORTED, "name:Ritika", HELD,
             reads=("Hi Ritika and Ekta",), echo=("Ritika Sharma of the Incubation Cell asked",)),
    Mutation("a_name_inside_a_company", "F05", "altavia.test", 2, _draft_says("Hi Marco,", "Hi Avi,"),
             "draft", DROPPED, UNSUPPORTED, "name:Avi", SHOWN, reads=("Hi Avi",)),
    # ── numbers ──
    Mutation("a_wrong_number_in_the_headline", "F26", "orbitly.test", 1, _move_says("11 am IST", "10 am IST"),
             "move", DROPPED, WRONG_NUMBER, "number:10:00", HELD,
             reads=("confirm Tuesday 30 Sep at 10 am IST",)),
    Mutation("a_wrong_number_in_a_fact", "F26", "orbitly.test", 1,
             _claim_says(2, "Tuesday the thirtieth of September at eleven in the morning IST",
                         "Tuesday 30 Sep at 10 am IST"),
             "fact:2", DROPPED, WRONG_NUMBER, "number:10:00", HELD,
             reads=("Reply to Neha to confirm Tuesday 30 Sep at 11 am IST",), also=_FELL_F26,
             echo=("Tuesday 30 Sep at 10 am IST",)),
    Mutation("a_sibling_calculators_number", "F49", "sparkreach.test", 1, _sibling,
             "fact:3", CORRECTED, BY_CALCULATOR, "number:0.06 -> 14.06 (num:days_quiet)", SHOWN,
             reads=("quiet for 0.06 days",), also=(("do_nothing", CORRECTED, BY_CALCULATOR),),
             keeps=("The file has been quiet for 14.06 days.",)),
    Mutation("a_timestamps_digits_as_a_count", "F26", "orbitly.test", 1,
             _do_nothing_says(before="Neha asked 22 days ago. "),
             "do_nothing", DROPPED, WRONG_NUMBER, "number:22", SHOWN, reads=("Neha asked 22 days ago",)),
    Mutation("a_value_in_another_unit", "F11", "northfieldvc.test", 1,
             _draft_says("work for a short call?", "work for the 20 hours you offered?"),
             "draft", DROPPED, WRONG_NUMBER, "number:20", SHOWN, reads=("the 20 hours you offered",)),
    Mutation("a_correction_beside_a_time_in_the_draft", "F51", "brightloop.test", 1, _beside_a_time,
             "fact:4", CORRECTED, BY_CALCULATOR, "number:3 -> 3.25 (num:days_quiet)", SHOWN,
             reads=("quiet for 3 days",),
             also=(("do_nothing", CORRECTED, BY_CALCULATOR), ("draft", KEPT, "")),
             keeps=("Tuesday 4 Aug at 3pm works for me", "The file has been quiet for 3.25 days.")),
    # ── whom the move goes to ──
    Mutation("a_draft_to_us", "F11", "northfieldvc.test", 1, _to("arjun@nimbuslabs.test"),
             "to", DROPPED, RECIPIENT_IS_US, "arjun@nimbuslabs.test", HELD, reads=("arjun@nimbuslabs.test",)),
    Mutation("a_draft_to_the_connector", "F04", "brandtlabs.test", 1,
             _both(_to("Introly"), _draft_says("Hi Sofia,", "Hi Introly,")),
             "to", DROPPED, RECIPIENT_IS_CONNECTOR, "Introly", SHOWN, reads=("Hi Introly",),
             also=(("move", CORRECTED, BY_ALTERNATIVE),)),
    Mutation("a_move_to_the_connector_without_a_draft", "F04", "brandtlabs.test", 1,
             _to_the_connector_without_a_draft,
             "to", DROPPED, RECIPIENT_IS_CONNECTOR, "Introly", SHOWN, reads=("Ask Introly to pass a short note",),
             also=(("move", CORRECTED, BY_ALTERNATIVE),)),
    # ── an ask already answered ──
    Mutation("answers_an_ask_our_reply_answered", "F45", "bluepeak.test", 2, _answers_the_answered_ask,
             "answers", DROPPED, ANSWERED, " by evt_", SUPPRESSED,
             reads=("Introduce Meera Shah to the two pilot leads",)),
    Mutation("an_answered_ask_its_move_does_not_name", "F45", "bluepeak.test", 2, _rests_on_the_answered_ask,
             "answers", DROPPED, ANSWERED, " by evt_", SUPPRESSED,
             reads=("Introduce Meera Shah to the two pilot leads",)),
    # ── what the card says beside the move ──
    Mutation("a_do_nothing_naming_an_absent_party", "F11", "northfieldvc.test", 1,
             _do_nothing_says(after=" Sequoia Capital leads the round without you."),
             "do_nothing", DROPPED, UNSUPPORTED, "Sequoia", SHOWN, reads=("Sequoia Capital leads the round",)),
    Mutation("a_decisive_fact_on_an_older_touch", "F45", "bluepeak.test", 2, _on_an_older_touch,
             "fact:1", DROPPED, UNQUOTED, "evt_", HELD, reads=("Introduce Meera Shah to the two pilot leads",),
             also=(("quote:1", DROPPED, MISQUOTED),)),
)


# ── the runs ──────────────────────────────────────────────────────────────────────────────────────────────

def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL — the golden set never skips")
    pytest.skip("GENIOS_TEST_DATABASE_URL not set — the golden set runs only on a scratch database")


def _serves(prompt: str, key: str) -> bool:
    """Is this an expert prompt about the file `key` — its dossier naming it `<key>`, the brief aside?"""
    return identify_site(prompt) == "expert" and f"<{key}>" in without_company_brief(prompt)


#: The one site a mutated run may ask what its recording never heard: the bundle narrator (L4.5) narrates the
#: decision AFTER the check, and its prompt carries the decision's label, steps and do-nothing — which the
#: mutation, or the check's verdict on it, changes. It is answered as its recording was written: by the ideal
#: reader, from the prompt alone (`ideal_reader.narrate_decision` — the play's own id and number placeholders,
#: never a word of the review), so it can neither carry a mutated word to a card nor hide one. Every other site
#: still refuses what was never recorded, and an unmutated run (test 1) answers only from its cassette.
DOWNSTREAM = "bundle_narrator"


class _Mutating(RecordedLLM):
    """The case's recorded model — but at the expert site, on the named serving of one file's review, the
    recorded answer with ONE mutation. `servings` counts that file's reviews; `mutated` is what was served;
    `narrated` counts the narrations the ideal reader answered (`DOWNSTREAM`)."""

    def __init__(self, cassette: dict, mutation: Mutation | None) -> None:
        super().__init__(cassette)
        self.mutation = mutation
        self.expert_calls = 0
        self.servings = 0
        self.narrated = 0
        self.mutated: Answer | None = None
        #: STEP-13b (M38.C4.L-integration.V14.U01): what the ladder asks AFTER the mutated serving — the same ask again on
        #: its rung with the check's verdicts (a repair), and the stronger rung's fresh ask — is answered with the same
        #: mutated answer: a model that keeps making the one error. `_ask` is the mutated prompt up to its last word.
        self._ask: str | None = None
        self._again: Any = None
        self._reader = IdealReader(CASES[mutation.case]) if mutation is not None else None

    def call(self, prompt: str, **kw: Any):
        if self._ask is not None and identify_site(prompt) == "expert" and prompt.startswith(self._ask):
            with self._lock:
                self.calls.append(("expert", "again"))
            return self._again
        try:
            result = super().call(prompt, **kw)
        except CassetteMiss:
            if self._reader is None or identify_site(prompt) != DOWNSTREAM:
                raise
            with self._lock:
                self.narrated += 1
            return self._reader.call(prompt, **kw)
        if identify_site(prompt) == "expert":
            with self._lock:
                self.expert_calls += 1
        m = self.mutation
        if m is None or not _serves(prompt, m.key):
            return result
        with self._lock:
            self.servings += 1
            serving = self.servings
        if serving != m.serving:
            return result
        answer = m.mutate(copy.deepcopy(result.parsed), prompt)
        self.mutated = answer
        from genios_engine.reason.expert.prompt import LAST_WORD
        self._ask = prompt[:prompt.rindex(LAST_WORD)]
        self._again = dataclasses.replace(result, parsed=answer, raw=json.dumps(answer))
        return self._again


def _as_written(review, _dossier_text, _people, *, evidence_ids=None) -> CheckedReview:
    """The check switched off: every line passes as written (`tests/reason/expert/checks.as_written`)."""
    from tests.reason.expert.checks import as_written
    return as_written(review)


#: The texts a card carries — everything the founder may read on it.
CARD_TEXTS = ("headline", "situation", "why", "actions", "artifact", "business_subject", "unresolved_item",
              "why_now", "do_nothing_consequence", "success_signal", "abstained_because")


def _words(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_words(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return "\n".join(_words(v) for v in value)
    return str(value)


@dataclass
class Ran:
    """What one run left: the file's reviews, as stored, and every card, as the founder could read it."""
    llm: _Mutating
    reviews: list[dict[str, Any]]                 # {key, status, review, checked}, in the order written
    cards: list[tuple[str, bool]]                 # (every text it carries, whether it is a question card)


def _ran(case_id: str, mutation: Mutation | None, *, checked: bool = True) -> Ran:
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.reason.expert import review as expert_review
    from tests.replays import cassettes
    from tests.replays.engine_runner import remove_tenant, run_case

    case = CASES[case_id]
    llm = _Mutating(cassettes.load(case), mutation)
    with pytest.MonkeyPatch.context() as mp:
        if not checked:
            # One seam: the review run and the sweep's re-check both call `review.check`, which calls this.
            mp.setattr(expert_review, "check_review", _as_written)
            # ⛔ RESTATED by `yc2_w27_s14` M43.C4.L-integration.V1.U02: since STEP-14 the card contract stands behind
            # the check at both card writers (`contracts/card_contract`) — a draft to us is refused there too. The
            # negative control asks what the CHECK alone stops, so with the check off the contract is off as well.
            from genios_engine.deliver import pipeline
            mp.setattr(pipeline, "_contract_refusals", lambda *_a, **_k: ())
        run = run_case(case, llm, keep=True)
    engine = routes._graph.engine
    try:
        with engine.connect() as c:
            reviews = [dict(r._mapping) for r in c.execute(text(
                "select n.canonical_key as key, r.status, r.review, r.checked from expert_reviews r "
                "  left join graph_nodes n on n.org_id = r.org_id and n.node_id = r.file_id "
                "       and n.valid_to is null "
                " where r.org_id = :o order by r.reviewed_at, r.fingerprint"), {"o": run.org_id})]
            cards = [("\n".join(_words(getattr(r, col)) for col in CARD_TEXTS), r.rule_id == "founder_question")
                     for r in c.execute(text(
                         f"select {', '.join('c.' + col for col in CARD_TEXTS)}, s.rule_id from cards c "
                         "  left join signals s on s.org_id = c.org_id and s.signal_id = c.signal_id "
                         " where c.org_id = :o order by c.card_id"), {"o": run.org_id})]
    finally:
        remove_tenant(engine, run.org_id)
    return Ran(llm=llm, reviews=reviews, cards=cards)


_RUNS: dict[tuple[str, bool], Ran | BaseException] = {}


def _mutated_run(m: Mutation, *, checked: bool) -> Ran:
    """One run per mutation and switch, shared by the tests that read it."""
    key = (m.id, checked)
    if key not in _RUNS:
        try:
            _RUNS[key] = _ran(m.case, m, checked=checked)
        except BaseException as exc:          # a cassette miss is a BaseException: keep it, report it
            _RUNS[key] = exc
    ran = _RUNS[key]
    if isinstance(ran, BaseException):
        raise AssertionError(f"{m.id}: the run did not finish — {ran!r}") from ran
    assert ran.llm.mutated is not None, \
        f"{m.id}: <{m.key}> was reviewed {ran.llm.servings} time(s); serving {m.serving} was never mutated"
    return ran


def _the_mutated_review(m: Mutation, ran: Ran) -> dict[str, Any]:
    """The stored row of the review the mutation was served to — the file's `serving`-th, as written."""
    from genios_engine.contracts.expert_review import ExpertReview
    rows = [r for r in ran.reviews if r["key"] == m.key]
    assert len(rows) >= m.serving, f"{m.id}: {len(rows)} stored review(s) of <{m.key}>"
    row = rows[m.serving - 1]
    assert row["status"] == "valid", f"{m.id}: the mutated review was stored {row['status']}"
    assert ExpertReview.from_mapping(row["review"]) == ExpertReview.from_mapping(ran.llm.mutated), \
        f"{m.id}: the stored review is not the one the mutation served"
    return row


def _carrying(cards: list[tuple[str, bool]], words: tuple[str, ...], *, questions: bool) -> list[str]:
    return [w for w in words for text, question in cards if w in text and (questions or not question)]


# ── 1 · every authored review stands its check whole ────────────────────────────────────────────────────────

@pytest.mark.parametrize("case_id", AUTHORED)
def test_every_authored_review_stands_its_check_whole(case_id):
    _scratch_db()
    ran = _ran(case_id, None)
    assert ran.reviews, f"{case_id}: its sweeps reviewed no file"
    assert len(ran.reviews) == ran.llm.expert_calls, \
        f"{case_id}: {ran.llm.expert_calls} review(s) served, {len(ran.reviews)} stored"
    for row in ran.reviews:
        where = f"{case_id} <{row['key']}>"
        assert row["status"] == "valid", f"{where}: stored {row['status']}"
        assert row["checked"] is not None, f"{where}: stored with no check"
        checked = CheckedReview.from_mapping(row["checked"])
        assert checked.version == CHECK_VERSION, f"{where}: checked under {checked.version}"
        assert checked.fate == SHOWN, f"{where}: {checked.fate} — {checked.because}"
        dropped = {(v.line, v.reason, v.detail) for v in checked.dropped}
        assert dropped == DECLARED_DROPS.get((case_id, row["key"]), frozenset()), f"{where}: dropped {dropped}"
        mode = row["review"]["mode"]
        if mode in ("act", "find_out"):
            assert checked.words.headline, f"{where}: its move did not stand"
        if mode == "find_out":
            assert checked.question, f"{where}: a find-out review asks its question"


# ── 2 · each mutation is caught on its case, with its reason; the card it would have made does not appear ──────

@pytest.mark.parametrize("m", MUTATIONS, ids=lambda m: m.id)
def test_each_mutation_is_caught_with_its_reason(m):
    _scratch_db()
    ran = _mutated_run(m, checked=True)
    checked = CheckedReview.from_mapping(_the_mutated_review(m, ran)["checked"])
    found = [v for v in checked.verdicts if v.line == m.line and v.verdict == m.verdict]
    assert any(v.reason == m.reason and m.detail in v.detail for v in found), \
        f"{m.id}: no {m.verdict} {m.reason} ({m.detail!r}) on {m.line}: {checked.as_mapping()['verdicts']}"
    for line, verdict, reason in m.also:
        assert any(v.line == line and v.verdict == verdict and (v.reason or "") == reason
                   for v in checked.verdicts), f"{m.id}: no {verdict} {reason} on {line}"
    expected = {(m.line, m.reason)} if m.verdict == DROPPED else set()
    expected |= {(line, reason) for line, verdict, reason in m.also if verdict == DROPPED}
    assert {(v.line, v.reason) for v in checked.dropped} == expected, \
        f"{m.id}: dropped {[(v.line, v.reason, v.detail) for v in checked.dropped]}"
    assert checked.fate == m.fate, f"{m.id}: {checked.fate} — {checked.because}"
    assert not _carrying(ran.cards, m.reads, questions=False), \
        f"{m.id}: a decision card says {_carrying(ran.cards, m.reads, questions=False)}"
    for words in m.keeps:
        assert any(words in text for text, _question in ran.cards), f"{m.id}: no card still says {words!r}"


@pytest.mark.parametrize("m", [pytest.param(m, marks=pytest.mark.xfail(strict=True, reason=m.finding))
                               if m.finding else m for m in MUTATIONS], ids=lambda m: m.id)
def test_a_caught_mutation_reaches_no_card(m):
    _scratch_db()
    ran = _mutated_run(m, checked=True)
    carried = _carrying(ran.cards, m.reads + m.echo, questions=True)
    assert not carried, f"{m.id}: a card — a question card included — says {carried}"


# ── 3 · the negative control: unchecked, each mutation reaches a card ────────────────────────────────────────

@pytest.mark.parametrize("m", MUTATIONS, ids=lambda m: m.id)
def test_unchecked_each_mutation_reaches_a_card(m):
    _scratch_db()
    ran = _mutated_run(m, checked=False)
    for words in m.reads:
        assert any(words in text for text, _question in ran.cards), \
            f"{m.id}: unchecked, no card says {words!r} — the mutation tests nothing about the check"
