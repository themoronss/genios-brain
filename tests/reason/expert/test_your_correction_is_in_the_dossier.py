"""STEP-16 · your corrections are in front of the expert — WHAT YOU CORRECTED, and beside the playbook's prior.

    .venv/bin/python -m pytest -q tests/reason/expert/test_your_correction_is_in_the_dossier.py
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… (the read from memory)

Tree `yc2_w27_s16` M46.C4.L-logic.V2.U03 (`reason/expert/dossier`; STEP-16 §8.4 items 3-4, S16-D1). The dossier prints
the file's standing corrections — its own (on its anchor or one of its people) and its kind of work's — after WHAT
YOU TOLD US: a head line (when, what it reaches, the card it was about, the reason you gave) that no id prints on,
then `[corr:<id>]` and your words verbatim. A correction for the kind of work also prints in WHAT A PROFESSIONAL
KNOWS ABOUT THIS WORK, beside the profession's prior, as yours — the corrected playbook prior. The catalogue holds
the `corr:` ids, so a review may cite them. Printed only when there is one: a file with none reads byte for byte
as before. Bounded, the cut counted.
"""
from __future__ import annotations

import dataclasses
import os
from datetime import timedelta

import pytest

from genios_engine.context.founder_corrections import Correction
from genios_engine.contracts.expert_review import validate
from genios_engine.packs.compiler.playbook_reader import PlaybookAnswer
from genios_engine.reason.expert import dossier as D
from tests.reason.expert.test_the_dossier import NOW, _parts, _review

WORDS = "Kunal asked for news only on real milestones — don't push him."
KIND_WORDS = "Investors who asked for news only on milestones get nothing before one lands."


def _correction(n: int, *, scope: str = "file", words: str = WORDS, kind: str | None = None, card: str | None = None,
                reason: str | None = None, hours: int = 0) -> Correction:
    return Correction(correction_id=f"fc_{n:024d}", file_id="node_meridian", card_id=card, feedback_id=None,
                      reason=reason, words=words, scope=scope, kind=kind, brief_line_id=None,
                      corrected_by="user_arjun", corrected_at=NOW - timedelta(days=2) + timedelta(hours=hours),
                      state="standing")


def _with(parts, **over):
    return dataclasses.replace(parts, **over)


def test_a_file_with_no_correction_reads_byte_for_byte_as_before():
    before = D.build_dossier(_parts())
    assert "WHAT YOU CORRECTED" not in before.text and "corr:" not in before.text
    assert D.build_dossier(_with(_parts(), corrections=(), corrections_cut=0)).digest == before.digest


def test_your_correction_prints_after_what_happened_with_its_id_and_your_words():
    d = D.build_dossier(_with(_parts(), corrections=(_correction(1, card="card_1", reason="not_relevant"),)))
    titles = [s.name for s in d.sections]
    assert titles[titles.index("timeline") + 1] == "corrections", titles
    [section] = [s for s in d.sections if s.name == "corrections"]
    assert section.text.splitlines() == [
        "You corrected this file on 2026-10-08 12:00 UTC, on the card “Reply to Kunal” — you called it wrong: "
        "not_relevant:",
        f"- [corr:fc_{1:024d}] “{WORDS}”"]
    assert "## WHAT YOU CORRECTED" in d.text
    assert f"corr:fc_{1:024d}" in d.catalogue.evidence_ids


def test_after_what_you_told_us_when_you_answered_too():
    from genios_engine.context.founder_questions import Question
    answered = Question(question_id="fq_1", file_id="node_meridian", fingerprint="ffp-1", run_id="run_1",
                        question="Which quarter?", why="the file asks", asked_at=NOW - timedelta(days=3),
                        state="answered", answer="This quarter's.", answered_by="user_arjun",
                        answered_at=NOW - timedelta(days=3))
    d = D.build_dossier(_with(_parts(), answers=(answered,), corrections=(_correction(1),)))
    titles = [s.name for s in d.sections]
    assert titles[titles.index("timeline"):titles.index("timeline") + 3] == ["timeline", "answers", "corrections"]


def test_your_words_are_printed_verbatim_and_the_head_line_carries_no_id():
    d = D.build_dossier(_with(_parts(), corrections=(_correction(1, words="  news   only on  milestones "),)))
    places = D.lines_by_id(d.text, d.catalogue.evidence_ids)[f"corr:fc_{1:024d}"]
    assert [p.line for p in places] == [f"- [corr:fc_{1:024d}] “news only on milestones”"]
    head = next(line for line in d.text.splitlines() if line.startswith("You corrected"))
    assert "[" not in head, "no fact can cite the date line"


def test_a_correction_for_the_kind_of_work_prints_beside_the_profession_prior_as_yours():
    kind = _correction(2, scope="kind", kind="investor", words=KIND_WORDS)
    d = D.build_dossier(_with(_parts(), corrections=(kind,)))
    [corrected] = [s for s in d.sections if s.name == "corrections"]
    [playbook] = [s for s in d.sections if s.name == "playbook"]
    assert corrected.text.startswith("You corrected every file of this kind of work (investor) on ")
    assert playbook.text.splitlines()[-2:] == [
        "Yours, for this kind of work — beside the profession's prior, which it outweighs for your company:",
        f"- [corr:fc_{2:024d}] “{KIND_WORDS}”"]
    assert len(D.lines_by_id(d.text)[f"corr:fc_{2:024d}"]) == 2, "in both places, one id"


def test_a_kind_correction_prints_even_where_the_file_has_no_playbook():
    kind = _correction(2, scope="kind", kind="investor", words=KIND_WORDS)
    d = D.build_dossier(_with(_parts(playbook=PlaybookAnswer(kind="investor", playbook=None, reason="no_kind")),
                              corrections=(kind,)))
    [playbook] = [s for s in d.sections if s.name == "playbook"]
    # ⛔ RESTATED by STEP-13b M37.C3.L-interface.V4.U01: the "none" carries its id, `[none:playbook]`.
    assert playbook.text.splitlines()[0] == ("No playbook for this file: the brief names no kind of work for it. "
                                             "[none:playbook]")
    assert playbook.text.splitlines()[-1] == f"- [corr:fc_{2:024d}] “{KIND_WORDS}”"


def test_a_file_correction_is_not_printed_beside_the_prior():
    d = D.build_dossier(_with(_parts(), corrections=(_correction(1),)))
    [playbook] = [s for s in d.sections if s.name == "playbook"]
    assert "Yours, for this kind of work" not in playbook.text


def test_the_corrections_left_out_are_counted():
    d = D.build_dossier(_with(_parts(), corrections=(_correction(1),), corrections_cut=3))
    assert d.cut["corrections"] == 3 and "… and 3 older correction(s), not shown." in d.text


def test_a_review_may_cite_your_correction():
    """The catalogue holds the `corr:` id: an inference grounded on your correction validates, and one grounded on a
    correction the dossier never showed does not."""
    from genios_engine.contracts.expert_review import Inference
    d = D.build_dossier(_with(_parts(), corrections=(_correction(1),)))
    review = _review("evt_005", "Hi Kunal, booking it now.")
    follows = dataclasses.replace(review, inferences=(*review.inferences, Inference(
        claim="Kunal wants news only on real milestones", based_on=(f"corr:fc_{1:024d}",))))
    unseen = dataclasses.replace(review, inferences=(*review.inferences, Inference(
        claim="Kunal wants news only on real milestones", based_on=(f"corr:fc_{9:024d}",))))
    assert validate(follows, d.catalogue).ok
    assert not validate(unseen, d.catalogue).ok


def test_a_maximal_set_of_corrections_keeps_the_dossier_under_its_bound():
    """The dossier test's own maximal dossier, with every correction it may carry — `SHOWN`, each of `MAX_WORDS`,
    half of them for the kind (printed twice) — stays under `DOSSIER_CHARS`."""
    from genios_engine.context.founder_corrections import MAX_WORDS, SHOWN
    from genios_engine.contracts.company_brief import CompanyBriefLine, compose
    from tests.reason.expert import test_the_dossier as T
    shown = tuple(_correction(i, words="w" * MAX_WORDS, scope="kind" if i % 2 else "file",
                              kind="investor" if i % 2 else None, card="card_1", reason="not_relevant", hours=i)
                  for i in range(SHOWN))
    long_words = " ".join(["word"] * 300)[:1200]
    touches = [T._touch(n, words=long_words, cut=4000) for n in range(200)]
    promises = tuple(D.Promise(promise_id=f"node_c{i}", words="x" * 200, quote="y" * 400, due_at=NOW, status="open",
                               owner=T.KUNAL, ours=False, event_id=f"evt_{i:03d}") for i in range(D.PROMISES_LIMIT))
    parts = T._parts(touches=touches, promises=promises,
                     playbook=T._playbook(moves=D.MOVES_LIMIT + 5, claims=D.CLAIMS_LIMIT + 5),
                     numbers=T._numbers(people=D.PEOPLE_LIMIT + 5, mailboxes=4))
    parts = _with(parts, brief=compose(org_id="org_x", company="Nimbus Labs", founder="Arjun Rao",
                                       lines=[CompanyBriefLine(line_id=f"cbl_{i}", section="goals", text="g" * 190)
                                              for i in range(40)]),
                  corrections=shown, corrections_cut=99)
    d = D.build_dossier(parts)
    assert len(d.text) < D.DOSSIER_CHARS, len(d.text)


# =================================================================================================
# read from memory — the file's own, its people's and its kind's, newest first
# =================================================================================================
@pytest.mark.pg
def test_a_files_corrections_are_read_with_its_dossier(pg_store):
    from sqlalchemy import text

    from genios_engine.context import founder_corrections as C
    from tests.reason.test_a_programme_is_not_decided_as_an_investor import FUND, _tenant
    from tests.reason.expert.test_a_covered_file_decides_once import NOW as AT
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the file is read from Postgres")
    org = "org_s16_dossier_reads"
    _tenant(pg_store, org)
    with pg_store.engine.connect() as c:
        anchor = c.execute(text(
            "select s.anchor_node_id from context_situations s join graph_nodes n on n.org_id = s.org_id "
            "and n.node_id = s.anchor_node_id and n.valid_to is null where s.org_id = :o "
            "and n.canonical_key like :k limit 1"), {"o": org, "k": f"%{FUND}"}).scalar()
    assert anchor, "the fund's file"
    with pg_store.engine.begin() as c:
        own = C.correct(c, org_id=org, file_id=anchor, words=WORDS, scope=C.FILE, by="user_arjun",
                        at=AT - timedelta(hours=2))
        kind = C.correct(c, org_id=org, file_id="node_another_fund", words=KIND_WORDS, scope=C.KIND,
                         kind="investor", by="user_arjun", at=AT - timedelta(hours=1))
        C.correct(c, org_id=org, file_id="node_another_fund", words="Not this file's.", scope=C.FILE,
                  by="user_arjun", at=AT)
    with pg_store.engine.connect() as c:
        parts = D.read_parts(c, org, anchor, now=AT + timedelta(hours=1))
    assert [k.correction_id for k in parts.corrections] == [kind.correction_id, own.correction_id]
    assert parts.corrections_cut == 0
    assert f"corr:{own.correction_id}" in D.build_dossier(parts).catalogue.evidence_ids
