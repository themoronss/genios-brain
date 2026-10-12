"""The questions a file asks you, kept — one open at a time (STEP-13 §3.6, `06` D60, `03` F184).

`speedrun008/YC-II W27/` STEP-13 §8.4 item 7, tree `yc2_w27_s13` M36.C2.L-data.V1.U02; the table is
`founder_questions` (migration 0201). A file whose review's move lost its ground (HELD by the check), or
whose review must find out first, asks the founder ONE question:

  * `ask` files it — the same words asked again are the question already open, never a second; a new
    question retires the file's old one, saying so (`REPLACED`);
  * `answer` keeps the founder's words, once;
  * `retire` closes a file's open question the review no longer asks (`NO_LONGER_ASKED`);
  * `open_question` and `answers_for` read a file's open question and the answers it holds; `by_id` one.

A question's id is its content's — the tenant, the file, the review that asks it, the words — so asking
mints no id another part of a run would have minted (`03` F170's rule), and the same question is the same
row however many sweeps ask it. Pure SQL over one connection; the caller owns the transaction.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

# One name to a line: `tests/test_no_missing_module_deps` reads what a module defines by its assignments.
OPEN = "open"
ANSWERED = "answered"
RETIRED = "retired"
#: Why a question was retired — closed, so each is counted by kind.
REPLACED = "a newer question of the file replaced it"
NO_LONGER_ASKED = "the file's latest review no longer asks it"



@dataclass(frozen=True, slots=True)
class Question:
    question_id: str
    file_id: str
    fingerprint: str
    run_id: str | None
    question: str
    why: str
    asked_at: datetime
    state: str
    answer: str | None = None
    answered_by: str | None = None
    answered_at: datetime | None = None
    retired_at: datetime | None = None
    retired_why: str | None = None


def question_id_for(org_id: str, file_id: str, fingerprint: str, question: str) -> str:
    """The question's id, from what it is."""
    digest = hashlib.sha256("\x1f".join((org_id, file_id, fingerprint, question)).encode()).hexdigest()
    return f"fq_{digest[:24]}"


def _row(r) -> Question:
    return Question(**{k: getattr(r, k) for k in Question.__slots__})


def by_id(conn, org_id: str, question_id: str) -> Question | None:
    r = conn.execute(text(
        "select question_id, file_id, fingerprint, run_id, question, why, asked_at, state, answer, "
        "answered_by, answered_at, retired_at, retired_why from founder_questions "
        "where org_id = :o and question_id = :q"), {"o": org_id, "q": question_id}).first()
    return _row(r) if r else None


def open_question(conn, org_id: str, file_id: str) -> Question | None:
    """The file's one open question, or None."""
    r = conn.execute(text(
        "select question_id, file_id, fingerprint, run_id, question, why, asked_at, state, answer, "
        "answered_by, answered_at, retired_at, retired_why from founder_questions "
        "where org_id = :o and file_id = :f and state = 'open'"), {"o": org_id, "f": file_id}).first()
    return _row(r) if r else None


def answers_for(conn, org_id: str, file_id: str) -> tuple[Question, ...]:
    """The questions of this file the founder answered, newest answer first."""
    return tuple(_row(r) for r in conn.execute(text(
        "select question_id, file_id, fingerprint, run_id, question, why, asked_at, state, answer, "
        "answered_by, answered_at, retired_at, retired_why from founder_questions "
        "where org_id = :o and file_id = :f and state = 'answered' "
        "order by answered_at desc, question_id"), {"o": org_id, "f": file_id}))


def retire(conn, *, org_id: str, file_id: str, why: str, at: datetime) -> bool:
    """Close the file's open question, saying why. False when the file has none open."""
    return conn.execute(text(
        "update founder_questions set state = 'retired', retired_at = :at, retired_why = :why "
        "where org_id = :o and file_id = :f and state = 'open' returning question_id"),
        {"o": org_id, "f": file_id, "at": at, "why": why}).first() is not None


def ask(conn, *, org_id: str, file_id: str, fingerprint: str, run_id: str | None, question: str, why: str,
        at: datetime) -> Question:
    """File the file's question. The same words already open are that question — re-bound to the run
    asking it now; any other open one is retired first — the file has one open question (0201's own
    index). A question this review asked and the founder already answered is not asked again: the
    answered question is returned."""
    standing = open_question(conn, org_id, file_id)
    if standing is not None and standing.question == question:
        if run_id is not None and run_id != standing.run_id:
            # The same question, asked by the run asking it now: its authority is that run's.
            conn.execute(text("update founder_questions set run_id = :run where org_id = :o "
                              "and question_id = :q and state = 'open'"),
                         {"o": org_id, "q": standing.question_id, "run": run_id})
            return by_id(conn, org_id, standing.question_id)
        return standing
    if standing is not None:
        retire(conn, org_id=org_id, file_id=file_id, why=REPLACED, at=at)
    qid = question_id_for(org_id, file_id, fingerprint, question)
    conn.execute(text(
        "insert into founder_questions (org_id, question_id, file_id, fingerprint, run_id, question, why, "
        "asked_at, state) values (:o, :q, :f, :fp, :run, :question, :why, :at, 'open') "
        "on conflict (org_id, question_id) do update set state = 'open', asked_at = excluded.asked_at, "
        "run_id = excluded.run_id, retired_at = null, retired_why = null "
        "where founder_questions.state = 'retired'"),
        {"o": org_id, "q": qid, "f": file_id, "fp": fingerprint, "run": run_id, "question": question,
         "why": why, "at": at})
    return open_question(conn, org_id, file_id) or by_id(conn, org_id, qid)


def answer(conn, *, org_id: str, question_id: str, words: str, by: str, at: datetime) -> Question:
    """Keep the founder's answer to an open question — once. ValueError for words that say nothing, or a
    question that is not open."""
    if not (words or "").strip():
        raise ValueError("an answer that says nothing is no answer")
    r = conn.execute(text(
        "update founder_questions set state = 'answered', answer = :w, answered_by = :by, answered_at = :at "
        "where org_id = :o and question_id = :q and state = 'open' returning question_id, file_id, "
        "fingerprint, run_id, question, why, asked_at, state, answer, answered_by, answered_at, retired_at, "
        "retired_why"),
        {"o": org_id, "q": question_id, "w": words.strip(), "by": by, "at": at}).first()
    if r is None:
        raise ValueError(f"question {question_id} is not open: it is answered once, and a retired one never")
    return _row(r)


__all__ = ["ANSWERED", "NO_LONGER_ASKED", "OPEN", "Question", "REPLACED", "RETIRED", "answer", "answers_for",
           "ask", "by_id", "open_question", "question_id_for", "retire"]
