"""STEP-16 · the dossier says what came of it — how each decision of the file ended, the asks closed since, your numbers.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_dossier_says_what_came_of_it.py
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… (the reads from memory, and the sweep)

Tree `yc2_w27_s16` M47.C2.L-logic.V4.U02 (`reason/expert/dossier`; STEP-16 §8.4 items 4 and 8, Atlas V.3). WHAT WAS
JUDGED BEFORE says under each card how it ended (`context/file_outcomes`) — verified or only replied to BY the event
that closed its ask, that event citable; taken; called wrong, and why; lapsed; dismissed; replaced; cleared — and lists
the asks of the file closed since its last review (answered or only replied to, by which event). WHAT A PROFESSIONAL
KNOWS prints beside a stage's prior YOUR number for it (`context/kind_numbers`) with its n, and the share of your
decisions on the kind that ended verified: "a prior" and "yours" told apart, never merged. Absent, the dossier reads
byte for byte as before; none of it is an input of the file's fingerprint. The sweep measures a kind's numbers once.
"""
from __future__ import annotations

import dataclasses
import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import file_outcomes as O
from genios_engine.context.file_judgments import PriorCard, Verdict
from genios_engine.context.kind_numbers import KindNumbers
from genios_engine.contracts.measured import count_of, median_of, rate_of
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert.fingerprint import file_fingerprint, fingerprint_inputs
from tests.reason.expert.test_the_dossier import FILE, NOW, _parts


def _with(parts, **over):
    return dataclasses.replace(parts, **over)


def _ended(end: str, *, by: str | None = None, reason: str | None = None, card: str = "card_1") -> O.Ended:
    return O.Ended(card_id=card, file_id=FILE, lane="decision", ended=end, by=by, reason=reason, at=NOW)


def _judged(text_: str) -> list[str]:
    head = "## " + D.TITLES["judged_before"]
    after = text_.split(head, 1)[1].split("\n## ", 1)[0]
    return [line for line in after.splitlines() if line]


def _numbers(*, days=(8.0, 10.0), verified=(1, 2)) -> KindNumbers:
    basis = "your files of this kind"
    return KindNumbers(kind="investor", files=3, reached={"first_call": count_of(3, basis=basis, unit="files")},
                       days_in={"first_call": median_of(days, basis=basis, unit="days")},
                       verified=rate_of(*verified, basis="decisions on your files of this kind"))


# =================================================================================================
# absent, byte for byte as before
# =================================================================================================
def test_a_file_with_nothing_come_of_it_reads_byte_for_byte_as_before():
    before = D.build_dossier(_parts())
    assert D.build_dossier(_with(_parts(), outcomes=(), asks_closed=(), kind_numbers=None)).digest == before.digest


@pytest.mark.parametrize("end", [O.OPEN, O.UNRECORDED])
def test_a_card_still_open_or_ended_with_no_cause_written_says_nothing_new(end):
    before = D.build_dossier(_parts())
    assert D.build_dossier(_with(_parts(), outcomes=(_ended(end),))).digest == before.digest


def test_every_end_a_card_can_have_is_said():
    assert set(D._ENDED_SAYS) == set(O.ENDS) - {O.OPEN, O.UNRECORDED}


# =================================================================================================
# how each card ended — under the card, its proof citable
# =================================================================================================
def test_a_verified_end_is_said_under_its_card_and_cites_the_event_that_closed_the_ask():
    d = D.build_dossier(_with(_parts(), outcomes=(_ended(O.VERIFIED, by="evt_signed_nda"),)))
    lines = _judged(d.text)
    card = next(i for i, line in enumerate(lines) if line.startswith("- [card:card_1]"))
    assert lines[card + 1] == "  how it ended: verified — its ask closed answered, by [evt_signed_nda]"
    assert "evt_signed_nda" in d.catalogue.evidence_ids, "its evidence is citable"
    [place] = D.lines_by_id(d.text, d.catalogue.evidence_ids)["evt_signed_nda"]
    assert place.item.startswith("- [card:card_1]"), "the proof belongs to the card it ended"


@pytest.mark.parametrize(("end", "by", "reason", "said"), [
    (O.REPLIED, "evt_thanks", "rule_cleared", "cleared — its ask was only replied to, by [evt_thanks]"),
    (O.TAKEN, None, "run_play", "you took it"),
    (O.CALLED_WRONG, None, "bad_timing", "you called it wrong — bad_timing"),
    (O.LAPSED, None, "expired", "its window passed with nobody acting"),
    (O.DISMISSED, None, "extension", "you dismissed it"),
    (O.REPLACED, None, "replaced", "a newer decision replaced it"),
    (O.CLEARED, None, "rule_cleared", "the decision behind it stopped holding")])
def test_each_end_is_said_in_its_own_words(end, by, reason, said):
    d = D.build_dossier(_with(_parts(), outcomes=(_ended(end, by=by, reason=reason),)))
    assert f"  how it ended: {said}" in _judged(d.text)


def test_a_verified_end_with_no_event_written_names_none():
    d = D.build_dossier(_with(_parts(), outcomes=(_ended(O.VERIFIED),)))
    assert "  how it ended: verified — its ask closed answered" in _judged(d.text)


def test_an_end_is_said_only_under_its_own_card():
    other = _with(_parts().judgments, cards=(*_parts().judgments.cards, PriorCard(
        card_id="card_2", subject_node_id="node_kunal", headline="Send the deck", level="prescriptive",
        state="queued", created_at=NOW, resolved_at=None, events=(), verdicts=())))
    d = D.build_dossier(_with(_parts(), judgments=other, outcomes=(_ended(O.LAPSED, card="card_2"),)))
    lines = _judged(d.text)
    card_2 = next(i for i, line in enumerate(lines) if line.startswith("- [card:card_2]"))
    assert lines[card_2 + 1] == "  how it ended: its window passed with nobody acting"
    assert sum(line.startswith("  how it ended:") for line in lines) == 1


# =================================================================================================
# the asks closed since the last review
# =================================================================================================
def _closed(n: int, basis: str | None = "answered", by: str | None = "evt_reply") -> D.ClosedAsk:
    return D.ClosedAsk(loop_id=f"lp_{n}", kind="meeting_request", basis=basis, by_event=by,
                       closed_at=NOW - timedelta(days=1, hours=n))


def test_an_ask_closed_since_the_last_review_is_listed_with_what_closed_it():
    d = D.build_dossier(_with(_parts(), asks_closed=(_closed(0), _closed(1, basis="replied", by="evt_thanks"))))
    lines = _judged(d.text)
    at = lines.index("Asks of the file closed since its last review:")
    assert lines[at + 1:at + 3] == [
        "- [loop:lp_0] an ask (meeting_request) closed answered by [evt_reply], 2026-10-09 12:00 UTC",
        "- [loop:lp_1] an ask (meeting_request) closed — only replied to by [evt_thanks], 2026-10-09 11:00 UTC"]
    assert {"loop:lp_0", "evt_reply", "evt_thanks"} <= d.catalogue.evidence_ids


def test_a_closure_with_no_basis_or_event_says_only_closed():
    d = D.build_dossier(_with(_parts(), asks_closed=(_closed(0, basis=None, by=None),)))
    assert "- [loop:lp_0] an ask (meeting_request) closed, 2026-10-09 12:00 UTC" in _judged(d.text)


def test_the_asks_closed_past_the_limit_are_counted():
    asks = tuple(_closed(n) for n in range(D.ASKS_CLOSED_LIMIT + 2))
    lines = _judged(D.build_dossier(_with(_parts(), asks_closed=asks)).text)
    assert sum(line.startswith("- [loop:") for line in lines) == D.ASKS_CLOSED_LIMIT
    assert "… and 2 more ask(s) closed, not shown." in lines


# =================================================================================================
# your numbers beside the prior — told apart, never merged
# =================================================================================================
def _stage_line(d, stage: str) -> str:
    return next(line for line in d.text.splitlines() if line.startswith(f"- {stage} ("))


def test_your_number_for_a_stage_prints_beside_its_prior():
    d = D.build_dossier(_with(_parts(), kind_numbers=_numbers()))
    assert _stage_line(d, "first_call") == (
        "- first_call (First call): typically 21 days — a playbook's prior, not measured here, practitioner judgement"
        "; yours: 2 times, median 9 days — too few to call normal; quiet means: they are busy"
        "; it ends when: a partner meeting is booked")
    assert "yours" not in _stage_line(d, "partner_meeting"), "no file of yours moved on from it: nothing measured"
    assert ("Yours for this kind of work: 1 of 2 decisions on your files of it ended verified "
            "(measured here, not a prior)") in d.text.splitlines()


def test_at_five_files_your_number_is_a_habit_and_says_its_n():
    d = D.build_dossier(_with(_parts(), kind_numbers=_numbers(days=(7.0,) * 5)))
    assert "; yours: usually 7 days (n=5, your files of this kind);" in _stage_line(d, "first_call")
    assert "typically 21 days — a playbook's prior" in _stage_line(d, "first_call"), "the prior stays a prior"


def test_a_kind_with_no_decision_ended_prints_no_verified_share():
    d = D.build_dossier(_with(_parts(), kind_numbers=_numbers(verified=(0, 0))))
    assert "Yours for this kind of work" not in d.text


def test_a_file_with_no_playbook_prints_none_of_your_numbers():
    from genios_engine.packs.compiler.playbook_reader import PlaybookAnswer
    parts = _parts(playbook=PlaybookAnswer(kind="investor", playbook=None, reason="no_kind"))
    assert D.build_dossier(_with(parts, kind_numbers=_numbers())).digest == D.build_dossier(parts).digest


# =================================================================================================
# none of it is an input of the fingerprint; and the dossier stays bounded
# =================================================================================================
def test_what_came_of_it_is_no_input_of_the_fingerprint():
    plain = _parts()
    full = _with(plain, outcomes=(_ended(O.VERIFIED, by="evt_signed_nda"),), asks_closed=(_closed(0),),
                 kind_numbers=_numbers())
    assert D.build_dossier(full).digest != D.build_dossier(plain).digest, "the dossier says it"
    assert fingerprint_inputs(full, prompt_version="p") == fingerprint_inputs(plain, prompt_version="p")
    assert file_fingerprint(full, prompt_version="p") == file_fingerprint(plain, prompt_version="p")


def test_a_maximal_dossier_with_everything_that_came_of_it_stays_under_its_bound():
    from genios_engine.context.file_judgments import LIMITS
    from genios_engine.context.founder_corrections import MAX_WORDS, SHOWN, Correction
    from genios_engine.contracts.company_brief import CompanyBriefLine, compose
    from tests.reason.expert import test_the_dossier as T
    long_words = " ".join(["word"] * 300)[:1200]
    parts = T._parts(touches=[T._touch(n, words=long_words, cut=4000) for n in range(200)],
                     promises=tuple(D.Promise(promise_id=f"node_c{i}", words="x" * 200, quote="y" * 400, due_at=NOW,
                                              status="open", owner=T.KUNAL, ours=False, event_id=f"evt_{i:03d}")
                                    for i in range(D.PROMISES_LIMIT)),
                     playbook=T._playbook(moves=D.MOVES_LIMIT + 5, claims=D.CLAIMS_LIMIT + 5),
                     numbers=T._numbers(people=D.PEOPLE_LIMIT + 5, mailboxes=4))
    cards = tuple(PriorCard(card_id=f"card_{i:02d}_{'k' * 30}", subject_node_id="node_kunal", headline="h" * 200,
                            level="prescriptive", state="acted", created_at=NOW, resolved_at=None, events=(),
                            verdicts=(Verdict(cause="wrong", reason="r" * 40, at=NOW),))
                  for i in range(LIMITS["cards"]))
    corrections = tuple(Correction(correction_id=f"fc_{i:024d}", file_id=FILE, card_id="card_1", feedback_id=None,
                                   reason="not_relevant", words="w" * MAX_WORDS, scope="kind" if i % 2 else "file",
                                   kind="investor" if i % 2 else None, brief_line_id=None, corrected_by="user_arjun",
                                   corrected_at=NOW, state="standing") for i in range(SHOWN))
    parts = _with(parts, brief=compose(org_id="org_x", company="Nimbus Labs", founder="Arjun Rao",
                                       lines=[CompanyBriefLine(line_id=f"cbl_{i}", section="goals", text="g" * 190)
                                              for i in range(40)]),
                  judgments=_with(parts.judgments, cards=cards), corrections=corrections, corrections_cut=99,
                  outcomes=tuple(_ended(O.CALLED_WRONG, reason="r" * 40, card=c.card_id) for c in cards),
                  asks_closed=tuple(_closed(n, by="evt_" + "e" * 40) for n in range(D.ASKS_CLOSED_LIMIT + 9)),
                  kind_numbers=KindNumbers(
                      kind="investor", files=99, reached={},
                      days_in={s.name: median_of([1.25] * 99, basis="your files of this kind", unit="days")
                               for s in parts.playbook.playbook.stages},
                      verified=rate_of(49, 99, basis="decisions on your files of this kind")))
    d = D.build_dossier(parts)
    assert len(d.text) < D.DOSSIER_CHARS, len(d.text)


# =================================================================================================
# read from memory — the file's own cards' ends, its asks closed since its review, its kind's numbers
# =================================================================================================
from tests.deliver.test_a_card_verdict_reaches_every_reader import AT, decided  # noqa: E402,F401 — fixture
from tests.reason.expert.test_a_covered_file_decides_once import world  # noqa: E402,F401 — fixture
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: E402,F401 — fixture


def _read(store, org, anchor):
    with store.engine.connect() as c:
        return D.read_parts(c, org, anchor, now=AT + timedelta(hours=1))


@pytest.mark.pg
def test_the_dossier_reads_how_its_card_ended(decided):
    from genios_engine.deliver import actions
    store, org, anchor, card = decided
    assert actions.ingest_action(card_store=None, graph=store, org_id=org, card_id=card.card_id, actor="founder",
                                 action="wrong", reason="wrong_person", eval_time=AT,
                                 allow_any_assignee=True)["ok"] is True
    parts = _read(store, org, anchor)
    assert [(e.card_id, e.ended, e.reason) for e in parts.outcomes] == [(card.card_id, O.CALLED_WRONG, "wrong_person")]
    assert "  how it ended: you called it wrong — wrong_person" in _judged(D.build_dossier(parts).text)


@pytest.mark.pg
def test_a_verified_end_read_from_memory_cites_the_event_that_closed_the_ask(decided):
    from genios_engine.platform import card_lifecycle as L
    store, org, anchor, card = decided
    with store.engine.connect() as c:
        event = c.execute(text("select event_id from source_events where org_id = :o order by occurred_at desc, "
                               "event_id limit 1"), {"o": org}).scalar_one()
    with store.engine.begin() as c:
        L.resolve_cards(c, org_id=org, cause=L.VERIFIED, card_ids=[card.card_id], at=AT,
                        evidence={"event_id": event, "loop_id": "loop_nda", "basis": "answered"})
    d = D.build_dossier(_read(store, org, anchor))
    assert f"  how it ended: verified — its ask closed answered, by [{event}]" in _judged(d.text)
    assert event in d.catalogue.evidence_ids


@pytest.mark.pg
def test_only_the_asks_closed_since_the_last_review_are_listed(decided):
    store, org, anchor, _card = decided
    parts = _read(store, org, anchor)
    [last] = parts.judgments.reviews[:1]
    people = list(parts.file.people or (anchor,))
    with store.engine.begin() as c:
        event = c.execute(text("select event_id from source_events where org_id = :o order by occurred_at desc, "
                               "event_id limit 1"), {"o": org}).scalar_one()
        for loop, closed_at in (("lp_s16_after", last.reviewed_at + timedelta(minutes=1)),
                                ("lp_s16_before", last.reviewed_at - timedelta(minutes=1))):
            c.execute(text(
                "insert into open_loops (org_id, loop_id, kind, status, subject_node_id, opened_at, last_seen_at, "
                "opened_by_event, closed_at, closed_basis, closed_by_event) values (:o, :l, 'meeting_request', "
                "'closed', :s, :opened, :opened, :e, :at, 'answered', :e)"),
                {"o": org, "l": loop, "s": people[0], "opened": last.reviewed_at - timedelta(days=2), "at": closed_at,
                 "e": event})
    parts = _read(store, org, anchor)
    assert [a.loop_id for a in parts.asks_closed] == ["lp_s16_after"]
    assert (parts.asks_closed[0].basis, parts.asks_closed[0].by_event) == ("answered", event)
    assert "loop:lp_s16_after" in D.build_dossier(parts).catalogue.evidence_ids


@pytest.mark.pg
def test_your_numbers_for_its_kind_are_read_with_the_dossier(decided):
    store, org, anchor, _card = decided
    parts = _read(store, org, anchor)
    assert parts.file.work_kind and parts.kind_numbers is not None
    assert (parts.kind_numbers.kind, parts.kind_numbers.files >= 1) == (parts.file.work_kind, True)


@pytest.mark.pg
def test_a_file_never_reviewed_lists_no_closed_ask(pg_store):
    from tests.reason.expert.test_the_dossier import KUNAL
    from tests.context.workstream_world import process, tenant
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the file is read from Postgres")
    org = "org_s16_came_of_it_unreviewed"
    tenant(pg_store, org)
    process(pg_store, org, event_id="evt_u_in", sender=KUNAL, thread="t_u", at=NOW - timedelta(days=3))
    with pg_store.engine.begin() as c:
        anchor = c.execute(text(
            "select distinct k.anchor_node_id from context_correlations k join context_correlation_members m "
            "on m.org_id = k.org_id and m.correlation_id = k.correlation_id where k.org_id = :o "
            "and m.event_id = 'evt_u_in'"), {"o": org}).scalar_one()
        c.execute(text("insert into open_loops (org_id, loop_id, kind, status, subject_node_id, opened_at, "
                       "last_seen_at, opened_by_event, closed_at, closed_basis, closed_by_event) values (:o, 'lp_u', "
                       "'request', 'closed', :s, :at, :at, 'evt_u_in', :at, 'answered', 'evt_u_in')"),
                  {"o": org, "s": anchor, "at": NOW - timedelta(days=2)})
    with pg_store.engine.connect() as c:
        parts = D.read_parts(c, org, anchor, now=NOW)
    assert parts.judgments.reviews == () and parts.asks_closed == (), "no review, no since"


# =================================================================================================
# the sweep measures a kind's numbers once a pass
# =================================================================================================
from tests.reason.expert.test_the_expert_pass import world as pass_world  # noqa: E402,F401 — fixture


@pytest.mark.pg
def test_the_sweep_measures_a_kinds_numbers_once_for_every_file_of_it(pass_world, monkeypatch):
    from genios_engine.context import kind_numbers as K
    from tests.reason.expert import test_the_expert_pass as EP
    from tests.reason.expert.test_a_correction_brings_the_file_back import _brief_names_both_kinds
    store, now = pass_world
    _brief_names_both_kinds(store, now - timedelta(days=1))
    calls: list[tuple[str, tuple[str, ...] | None]] = []
    real = K.numbers_for_kind

    def counted(conn, org_id, kind, *, now, files=None):
        calls.append((kind, None if files is None else tuple(sorted(files))))
        return real(conn, org_id, kind, now=now, files=files)
    monkeypatch.setattr(K, "numbers_for_kind", counted)
    receipt, expert = EP._pass(store, now)
    files = sorted(set(EP._files_of(store).values()))
    assert receipt["files"] == len(files) == 2
    assert calls == [("investor", tuple(files))], "once a pass, over the kind's files the pass read"
    assert all("## WHAT A PROFESSIONAL KNOWS ABOUT THIS WORK" in p for p in expert.prompts)
