"""Shared machinery for the M-4 suite: the golden set, the replay lane, and a scripted model.

THE REPLAY LANE IS THE POINT. Every fixture carries the answer M-4 returned when it was
labelled, so what these tests grade is OUR code — the gate, the speaker-authority table, ALG-08,
the floors and the ledger — and not any model's quality on a given afternoon. It is the same
discipline `tests/golden/l1/test_golden_corpus.py` runs on, for the same reason: a suite whose
result depends on a live model is a suite that reports a different number every week and can
never be a gate.

Nothing here calls a model. `ScriptedModel` is the seam the drain's `llm` parameter takes, and it
records what it was asked so a test can assert that a call was NOT made — which for M-4 is half
the acceptance list.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest

from genios_engine.context.lifecycle.authority import role_for_scope
from genios_engine.context.lifecycle.contract import Message, Obligation
from genios_engine.context.lifecycle.gate import gate_decision
from genios_engine.context.lifecycle.judge import judge
from genios_engine.context.lifecycle.prompt import parse_description

#: One instant for the whole suite. `eval_time` is a parameter everywhere below it, and no test
#: in this tree reads a clock — a resolution suite that did would grade differently at midnight.
AT = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)

_GOLDEN = (pathlib.Path(__file__).resolve().parents[2] / "golden" / "l2"
           / "m4_resolution.json")


@dataclass
class ScriptedModel:
    """The `llm` seam, with a recorded script instead of a network call.

    `answers` is keyed by event id FOR THE READER; the match is on the answer's own quote, which
    is the only part of the fixture that appears in the prompt (the prompt carries the message,
    the subject and the obligations — never an event id). A message with no scripted answer
    returns a FAILED result rather than a plausible one: a model that always answers is not a
    model, and the failure path (nothing stored, the message re-read next sweep) is one this
    suite has to be able to drive.
    """

    answers: dict[str, dict] = field(default_factory=dict)
    model: str = "scripted-m4"
    prompts: list[str] = field(default_factory=list)

    def call(self, prompt: str, *, max_tokens: int = 500) -> Any:
        self.prompts.append(prompt)
        # Matched against the FENCED MESSAGE, not the whole prompt. The instruction spine carries
        # worked examples ("we signed yesterday", "ho gaya"), so a naive substring test over the
        # prompt matches every message ever sent — and the suite would then be scripting answers
        # for messages the model was never given.
        body = prompt.split("<<<CONTENT_", 1)[-1]
        for payload in self.answers.values():
            if str(payload.get("quote") or "\0") in body:
                return _Result(parsed=dict(payload), ok=True)
        return _Result(parsed={}, ok=False, error="no scripted answer")

    @property
    def calls(self) -> int:
        return len(self.prompts)


@dataclass
class _Result:
    parsed: dict
    ok: bool = True
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


def answer_for(text: str, *, verdict: str, certainty: str, scope: list[str], quote: str,
               start_offset: int | None = None) -> dict:
    """A model answer with offsets measured against the real message — what a correct M-4 does.

    Offsets are computed rather than typed so a fixture cannot drift from its own message; the
    tests that need WRONG offsets pass `start_offset` explicitly, which is the only way this
    helper will produce them.
    """
    start = text.find(quote) if start_offset is None else start_offset
    return {"verdict": verdict, "certainty": certainty, "scope": list(scope), "quote": quote,
            "start_offset": max(start, 0), "end_offset": max(start, 0) + len(quote)}


@pytest.fixture(scope="session")
def golden() -> dict:
    """The committed golden set. A later wave extends the JSON; nothing here needs editing."""
    return json.loads(_GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def replay():
    """Run ONE fixture through the real deterministic path: gate → parse → judge.

    The only thing replaced is the model call itself. In particular the SPAN VALIDATOR is the
    real one, the authority table is the real one and the floors are the real ones, so a fixture
    that passes here passes because the shipped code decided it.
    """
    def _replay(fixture: dict):
        obligations = tuple(Obligation(o["id"], o["subject"], o.get("owner"))
                            for o in fixture["obligations"])
        message = Message(event_id=fixture["fixture_id"], text=fixture["message"],
                          sender_email=fixture["sender"], occurred_at=AT)
        internal = fixture["internal_emails"]
        role = role_for_scope(fixture["sender"], obligations, internal_emails=internal)
        decision = gate_decision(
            status="active", resolved_by=None, terminal_by_fact=False, has_new_signal=True,
            already_examined=False, has_text=bool(fixture["message"].strip()),
            speaker_role=role, calls_today_for_situation=0, calls_today_for_org=0)
        if not decision.fires:
            return "gated", None, None
        answer = dict(fixture["model_answer"])
        anchor = answer.pop("quote_anchor", None)
        if "start_offset" not in answer:
            answer["start_offset"] = max(fixture["message"].find(anchor or answer["quote"]), 0)
        answer["end_offset"] = answer["start_offset"] + len(answer["quote"])
        description = parse_description(answer)
        assert description is not None, f"{fixture['fixture_id']} is not a well-formed answer"
        claim = judge(description, situation_id="sit_golden", message=message,
                      obligations=obligations, internal_emails=internal)
        return claim.decision, claim.verdict, claim
    return _replay
