"""STEP-14 · a held file's question card in the gold shape too — who and what the file is, why now, what remains.

    .venv/bin/python -m pytest -q tests/deliver/test_a_question_card_is_in_the_gold_shape.py

Tree `yc2_w27_s14` M43.C3.L-interface.V3.U03 (`deliver/pipeline.question_card`; STEP-14 §8.4 item 5). STEP-13's
question card keeps what it is — the question as its headline, why it is asked as its situation, its actions
(answer, snooze, and since STEP-16 wrong) and surfaces (app, api) — and beside them, from its review's card lines (0221,
`reason/expert/card_lines`): the file's PERSON as its subject (never a bare domain, `03` F64), the brief's role, why
now, and what remains on the file. A review stored before 0221 keeps none: the card is built as before.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.deliver import card_builder as B
from genios_engine.deliver import pipeline
from genios_engine.deliver import router
from genios_engine.reason.expert import store as reviews
from genios_engine.reason.expert.card_lines import CardLines, DEFAULT

pytestmark = pytest.mark.unit

AT = datetime(2026, 8, 12, tzinfo=timezone.utc)
QUESTION = "Ishaan Mehra's address at Corvane, so you can write to him as the introduction asks: it gives none"
LINES = CardLines(why_now="Introly wrote on 12 Aug", what_remains=("Introly asked you to write to Ishaan, since 12 Aug",),
                  subject="Ishaan Mehra", company="corvane.test", kind_of_work=None, role="intro",
                  window_days=7, window_from=DEFAULT)
ROW = {"signal_id": "sig_q", "subject_node_id": "node_introly", "question": QUESTION, "question_id": "fq_1",
       "why": "find_out", "fingerprint": "ffp-1", "asking_review": None, "score": 55, "pack_id": "founder_office",
       "output_lane": "investigation", "lane_reason": "a question first", "capability_id": "expert.file_review",
       "reasoning_run_id": "rrun_1", "reasoning_decision_hash": "d" * 64, "config_snapshot_id": "cfg_1"}


class _Engine:
    @contextmanager
    def connect(self):
        yield object()


def _card(monkeypatch, lines):
    checked = C.CheckedReview(verdicts=(), fate=C.SHOWN, cited=("evt_1",), question=QUESTION,
                              words=C.CardWords(headline=QUESTION, situation="An introduction with no address",
                                                done_when=None, draft=None, to=None))
    monkeypatch.setattr(B, "load_node", lambda *_a, **_k: ("introly.test", "company", {}, {}))
    monkeypatch.setattr(B, "_group_memberships", lambda *_a, **_k: {})
    monkeypatch.setattr(router, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))
    monkeypatch.setattr(reviews, "read_review", lambda *_a, **_k: SimpleNamespace(checked=checked, card_lines=lines))
    return pipeline.question_card(SimpleNamespace(engine=_Engine()), "org_1", dict(ROW), AT)


def test_the_question_card_names_the_files_person_role_why_now_and_what_remains(monkeypatch):
    card, copy = _card(monkeypatch, LINES)
    assert card["business_subject"] == "Ishaan Mehra", "the file's person, never the connector's domain"
    assert card["relationship_role"] == "intro" and card["why_now"] == "Introly wrote on 12 Aug"
    assert card["unresolved_item"] == "Introly asked you to write to Ishaan, since 12 Aug"
    assert (copy["headline"], copy["situation"]) == (QUESTION, "An introduction with no address"), "as built"
    # ⛔ RESTATED by `yc2_w27_s16` M46.C3.L-interface.V5.U07 (S16-D10): the question card offers "don't ask me this".
    assert [a["type"] for a in card["actions"]] == ["answer", "snooze", "wrong"] and card["surfaces"] == ["app", "api"]


def test_a_question_whose_review_kept_no_lines_is_built_as_before(monkeypatch):
    card, _copy = _card(monkeypatch, None)
    assert card["business_subject"] == "introly.test" and card["relationship_role"] is None
    assert card["why_now"] is None and card["unresolved_item"] == QUESTION
