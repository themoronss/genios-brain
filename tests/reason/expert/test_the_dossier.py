"""STEP-12 · the dossier — everything the expert is shown for one file, in one fixed order, with what it may cite.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_the_dossier.py -q

`reason/expert/dossier.py` (tree `yc2_w27_s12` M32.C2.L-logic.V1.U04). The brief, the file, its timeline
(the newest touches whole with their words, older ones one line each, the rest counted), the promises in
its mail (a *"soon"* is no deadline, `06` D56), its numbers with their n (your reply time unsplit, D52),
what was checked, its playbook (reviewed or labelled), its situations against their windows, what was
judged before, and what nothing does (D39) — in an order that never moves. Every citable item carries its
id, and the catalogue holds exactly those ids, every number written in it and the playbook's stages, so a
review is held to what this dossier showed. Bounded by construction under `DOSSIER_CHARS`, each cut
counted; the same parts give the same dossier and digest.
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.coverage_receipt import MailboxReceipt
from genios_engine.context.file_judgments import (CardEvent, FileJudgments, PastFact, PriorCard,
                                                  PriorReview, SituationEnd, Verdict)
from genios_engine.context.workstream_numbers import FileNumbers, PersonNumbers
from genios_engine.context.workstream_timeline import FileTimeline, Touch
from genios_engine.context.workstreams import Ask, Lifecycle, SituationLife, WorkFile
from genios_engine.contracts.company_brief import CompanyBriefLine, compose
from genios_engine.contracts.expert_review import (UNKNOWN_EVIDENCE, ExpertReview, number_tokens,
                                                   validate)
from genios_engine.contracts.measured import PLAYBOOK_PRIOR, Measured, median_of
from genios_engine.packs.compiler.playbook_reader import (Claim, KindPlaybook, Move,
                                                          PlaybookAnswer, StopRule)
from genios_engine.packs.compiler.stage_priors import StagePrior
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.simulation import what_if_nothing

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
FILE = "node_meridian"
KUNAL = "kunal@meridianvc.test"


def _touch(n: int, *, direction: str = "in", words: str | None = "a note", outcome="emitted",
           cut: int = 0) -> Touch:
    return Touch(at=NOW - timedelta(days=60) + timedelta(hours=n), kind="mail", direction=direction,
                 who=KUNAL if direction == "in" else "arjun@nimbuslabs.test",
                 who_name="Kunal Shah" if direction == "in" else None, event_id=f"evt_{n:03d}",
                 thread="t_k", outcome=outcome, words=words, words_cut=cut)


def _timeline(touches) -> FileTimeline:
    touches = tuple(touches)
    gaps = tuple(round((touches[i + 1].at - touches[i].at).total_seconds() / 86400, 2)
                 for i in range(len(touches) - 1))
    return FileTimeline(file_id=FILE, as_of=NOW, touches=touches, upcoming=(), gaps_days=gaps,
                        usual_gap=median_of(gaps, basis="file", unit="days"),
                        longest_gap_days=max(gaps) if gaps else None,
                        days_quiet=round((NOW - touches[-1].at).total_seconds() / 86400, 2)
                        if touches else None,
                        silence_exceeds_prior_gaps=True if gaps else None)


def _file(asks=()) -> WorkFile:
    return WorkFile(file_id=FILE, kind=None, line=None, introduced_by=None,
                    counterparty="Meridian Ventures", counterparty_key="meridianvc.test",
                    counterparty_type="company", domains=("founder_office",), correlations=("c1",),
                    events=("evt_000",), first_touch=NOW - timedelta(days=60),
                    last_touch=NOW - timedelta(days=9), days_quiet=9.0, whose_move="ours",
                    open_asks=tuple(asks), people=(FILE, "node_kunal"), work_kind="investor")


def _numbers(people: int = 1, mailboxes: int = 1) -> FileNumbers:
    m = Measured(value=1.92, n=1, basis="person", unit="days")
    return FileNumbers(
        file_id=FILE, as_of=NOW,
        people=tuple(PersonNumbers(node_id=f"node_{i}", key=f"p{i}@meridianvc.test",
                                   name=f"Partner {i}", their_reply_time=m, their_normal=None,
                                   your_reply_time=Measured(value=0.4, n=3, basis="person",
                                                            unit="days"),
                                   your_normal=None, bounced_at=None) for i in range(people)),
        your_normal_overall=Measured(value=0.6, n=12, basis="tenant", unit="days"),
        mailboxes=tuple(MailboxReceipt(connection_id=f"con_{i}", address=f"box{i}@nimbuslabs.test",
                                       window_days=365, window_start=NOW - timedelta(days=365),
                                       last_finished_at=NOW - timedelta(hours=1), last_completed=True)
                        for i in range(mailboxes)),
        no_reply_since=NOW - timedelta(days=9), no_reply_can_be_said=True)


def _playbook(*, reviewed: bool = False, moves: int = 1, claims: int = 1) -> PlaybookAnswer:
    prior = Measured(value=21, n=0, basis="playbook pb.spine", source=PLAYBOOK_PRIOR, unit="days")
    pb = KindPlaybook(
        kind="investor", capability_id="founder_office.fundraising.investor_relations",
        playbook_id="founder_office.pb.investor.run_the_round", name="Run the round",
        stages=(StagePrior(name="first_call", label="First call", typical=prior,
                           cited="practitioner judgement", quiet_means="they are busy",
                           leaves_when="a partner meeting is booked"),
                StagePrior(name="partner_meeting", label="Partner meeting", typical=prior,
                           cited="practitioner judgement", quiet_means=None, leaves_when=None)),
        do_nothing_consequence="The fund moves on to the next deal.",
        success_signal="a partner meeting", outcome_window_days=14,
        stop=StopRule(dormant_after=Measured(value=90, n=0, basis="playbook pb.spine",
                                             source=PLAYBOOK_PRIOR, unit="days"),
                      cited="practitioner judgement — 90 days", then="close the file"),
        moves=tuple(Move(artifact_id=f"founder_office.pb.investor.move_{i}", name=f"Move {i}",
                         steps=("send a pre-read", "ask for the partner meeting"),
                         success_signal="a reply", outcome_window_days=7, reviewed=reviewed)
                    for i in range(moves)),
        claims=tuple(Claim(artifact_id=f"founder_office.heu.investor.claim_{i}",
                           statement="A first call that books itself rarely ghosts.",
                           why="the fund chose the time", reviewed=reviewed) for i in range(claims)),
        reviewed=reviewed, review_label=None if reviewed else "playbook not yet reviewed")
    return PlaybookAnswer(kind="investor", playbook=pb)


def _judgments() -> FileJudgments:
    at = NOW - timedelta(days=20)
    return FileJudgments(
        file_id=FILE,
        reviews=(PriorReview(fingerprint="fp_old", status="valid", reason=None, mode="wait",
                             model="claude-sonnet-5", prompt_version="expert-review.v1",
                             reviewed_at=at),),
        cards=(PriorCard(card_id="card_1", subject_node_id="node_kunal",
                         headline="Reply to Kunal", level="prescriptive", state="resolved",
                         created_at=at, resolved_at=at + timedelta(days=1),
                         events=(CardEvent(kind="surfaced", cause="built", at=at),),
                         verdicts=(Verdict(cause="run_play", reason=None, at=at),)),),
        situations=(SituationEnd(situation_id="sit_old", situation_type="investor_relationship",
                                 domain="founder_office", status="resolved", first_seen_at=at,
                                 last_seen_at=at, resolved_by=None, resolved_at=None,
                                 outcome="decided", reason=None),),
        history=(PastFact(field="derived.history.times_seen@founder_office", value=2,
                          value_type="count", valid_from=at),))


def _lifecycle() -> Lifecycle:
    return Lifecycle(file_id=FILE, situations=(SituationLife(
        situation_id="sit_now", situation_type="investor_relationship", domain="founder_office",
        status="active", first_seen_at=NOW - timedelta(days=60), last_seen_at=NOW - timedelta(days=9),
        days_seen=51.0, days_since_seen=9.0, quiet_window_days=90, window_from="kind",
        past_window=False),))


def _parts(*, touches=None, promises=(), playbook=None, numbers=None, brief=True, asks=(),
           promises_cut: int = 0) -> D.DossierParts:
    tl = _timeline(touches if touches is not None else (
        _touch(0, direction="out", words="Please resend the calendar link."),
        _touch(3, words="Here it is again: any slot this week works."),
        _touch(5, direction="out", words="Thanks Kunal, I will book it again tonight.")))
    life = _lifecycle()
    pb = playbook or _playbook()
    stop = pb.playbook.stop if pb.playbook else None
    return D.DossierParts(
        org_id="org_x", file_id=FILE, as_of=NOW,
        brief=compose(org_id="org_x", company="Nimbus Labs", founder="Arjun Rao",
                      lines=[CompanyBriefLine(line_id="cbl_1", section="in_motion",
                                              text="Investor · Meridian Ventures — first call",
                                              kind="investor", domain="meridianvc.test")])
        if brief else None,
        file=_file(asks), timeline=tl, numbers=numbers or _numbers(), playbook=pb,
        judgments=_judgments(), lifecycle=life,
        what_if=what_if_nothing(now=NOW, quiet_days=tl.days_quiet,
                                stop_after_days=int(stop.dormant_after.value) if stop else None,
                                stop_cited=stop.cited if stop else None,
                                do_nothing=pb.playbook.do_nothing_consequence if pb.playbook else None,
                                lifecycle=life, next_date=None),
        promises=tuple(promises), promises_cut=promises_cut)


def _cited(text: str) -> set[str]:
    return set(re.findall(r"\[([^\[\]\s]+)\]", text))


# ── the order, the determinism, the catalogue ──────────────────────────────────────────────────

def test_the_sections_are_in_the_one_order():
    """The order is part of the dossier's identity — its digest, the cache, the checklist that reads
    it — so it is pinned here as words, not read back from the module."""
    assert D.SECTIONS == ("brief", "file", "timeline", "promises", "numbers", "coverage",
                          "playbook", "situations", "judged_before", "what_if")
    d = D.build_dossier(_parts())
    assert [s.name for s in d.sections] == list(D.SECTIONS)
    heads = [line for line in d.text.splitlines() if line.startswith("## ")]
    assert heads == [f"## {D.TITLES[name]}" for name in D.SECTIONS]
    assert d.text.startswith(f"DOSSIER {D.DOSSIER_VERSION} — file {FILE}, as of 2026-10-10 12:00 UTC")


def test_the_same_parts_are_the_same_dossier_byte_for_byte():
    one, two = D.build_dossier(_parts()), D.build_dossier(_parts())
    assert one.text == two.text and one.digest == two.digest
    assert one.digest == "sha256:" + hashlib.sha256(one.text.encode("utf-8")).hexdigest()
    assert D.build_dossier(_parts(touches=(_touch(0), _touch(1, words="changed")))).digest != one.digest


def test_the_catalogue_is_exactly_what_the_dossier_shows():
    d = D.build_dossier(_parts(asks=(Ask(loop_id="lp_1", kind="request", asked_by="node_kunal",
                                         owed_by="us", thread_id="t_k",
                                         opened_at=NOW - timedelta(days=9)),)))
    assert d.catalogue.evidence_ids == _cited(d.text)
    assert {"evt_000", "evt_003", "evt_005", "loop:lp_1", "num:usual_gap", "num:days_quiet",
            "pb:founder_office.pb.investor.run_the_round", "sit:sit_now", "sit:sit_old",
            "review:fp_old", "card:card_1", "hist:derived.history.times_seen@founder_office",
            "whatif:3", "whatif:7", "whatif:14"} <= d.catalogue.evidence_ids
    assert d.catalogue.numbers == number_tokens(d.text)
    assert d.catalogue.stages == ("first_call", "partner_meeting")


# ── the timeline, bounded ──────────────────────────────────────────────────────────────────────

def test_the_newest_touches_are_whole_the_older_listed_the_rest_counted():
    touches = [_touch(n, words=f"words of touch {n}") for n in range(50)]
    d = D.build_dossier(_parts(touches=touches))
    timeline = next(s for s in d.sections if s.name == "timeline")
    newest = [f"evt_{n:03d}" for n in range(49, 49 - D.TOUCHES_WHOLE, -1)]
    for n in range(49, 49 - D.TOUCHES_WHOLE, -1):
        assert f"words of touch {n}" in timeline.text
    assert "words of touch 41" not in timeline.text                         # listed, not whole
    listed = [f"evt_{n:03d}" for n in range(41, 41 - D.TOUCHES_LISTED, -1)]
    counted = [f"evt_{n:03d}" for n in range(41 - D.TOUCHES_LISTED, -1, -1)]
    assert set(newest + listed) <= d.catalogue.evidence_ids
    assert not set(counted) & d.catalogue.evidence_ids                      # never shown, never citable
    assert timeline.cut == len(counted) == 50 - D.TOUCHES_WHOLE - D.TOUCHES_LISTED
    assert d.cut["timeline"] == timeline.cut and f"… and {timeline.cut} older touch(es)" in timeline.text


def test_an_archived_touch_says_so_and_shows_no_words():
    d = D.build_dossier(_parts(touches=(_touch(0, outcome="archived", words=None), _touch(1))))
    assert "· archived — its words are not read" in d.text


def test_a_kept_touch_with_no_words_in_memory_says_so():
    d = D.build_dossier(_parts(touches=(_touch(0, words=None),)))
    assert "(memory holds no words for it)" in d.text


@pytest.mark.parametrize("words, quote, word", [
    ("get back to Kunal", "I will get back to you soon.", "soon"),
    ("send the deck", "I'll send it shortly, after the call", "shortly"),
    ("book the soonest slot", "the soonest slot works", None),          # a whole word, never a part
    ("send the deck", "by Friday", None),
])
def test_a_relative_time_is_read_as_a_whole_word(words, quote, word):
    assert D.Promise(promise_id="p", words=words, quote=quote, due_at=None, status="open",
                     owner=None, ours=None, event_id=None).relative == word


def test_a_cut_touch_says_how_much_was_cut():
    d = D.build_dossier(_parts(touches=(_touch(0, words="the start of it", cut=812),)))
    assert "“the start of it” … (812 characters cut)" in d.text


# ── promises, numbers, coverage, playbook ──────────────────────────────────────────────────────

def test_a_soon_promise_is_no_deadline_and_a_dated_one_is_due():
    soon = D.Promise(promise_id="node_c1", words="get back to Kunal", quote="I will get back to you soon",
                     due_at=NOW - timedelta(days=9), status="open", owner="arjun@nimbuslabs.test",
                     ours=True, event_id="evt_005")
    dated = D.Promise(promise_id="node_c2", words="send the deck", quote="I'll send the deck by Friday",
                      due_at=NOW + timedelta(days=2), status="open", owner=KUNAL, ours=False,
                      event_id="evt_003")
    d = D.build_dossier(_parts(promises=(soon, dated), promises_cut=2))
    section = next(s for s in d.sections if s.name == "promises")
    assert ("[promise:node_c1] we promised: get back to Kunal · no deadline — its words say “soon”; "
            "judge from this file's own gaps whether soon has passed") in section.text
    assert "[promise:node_c2] they promised: send the deck · due 2026-10-12 12:00 UTC" in section.text
    assert section.cut == 2 and "… and 2 more promise(s)" in section.text


def test_your_reply_time_is_said_unsplit_and_a_screen_is_no_touch():
    d = D.build_dossier(_parts())
    assert "on every answer you sent them, not split by who wrote first, as decided" in d.text
    assert "Screen activity is not part of a file's timeline, as decided." in d.text
    assert "“no reply since then” may be said" in d.text


# ── each line says what was read, and only that (`03` F159–F161, found by the golden authoring) ──

def _section(d, name):
    return next(s.text for s in d.sections if s.name == name)


def test_no_reply_is_said_only_up_to_what_a_mailbox_read():
    coverage = _section(D.build_dossier(_parts()), "coverage")
    assert "“no reply since then” may be said up to 2026-10-10 11:00 UTC" in coverage


def test_no_reply_is_bounded_by_the_mailbox_that_read_least_and_finished():
    from genios_engine.context.coverage_receipt import MailboxReceipt
    boxes = (MailboxReceipt(connection_id="con_a", address="a@nimbuslabs.test", window_days=365,
                            window_start=NOW - timedelta(days=365),
                            last_finished_at=NOW - timedelta(hours=1), last_completed=True),
             MailboxReceipt(connection_id="con_b", address="b@nimbuslabs.test", window_days=365,
                            window_start=NOW - timedelta(days=365),
                            last_finished_at=NOW - timedelta(days=2), last_completed=True),
             MailboxReceipt(connection_id="con_c", address="c@nimbuslabs.test", window_days=365,
                            window_start=NOW - timedelta(days=365),
                            last_finished_at=NOW - timedelta(minutes=5), last_completed=False))
    numbers = dataclasses.replace(_numbers(), mailboxes=boxes)
    coverage = _section(D.build_dossier(_parts(numbers=numbers)), "coverage")
    assert "may be said up to 2026-10-08 12:00 UTC" in coverage          # b's read, never c's unfinished one
    unread = dataclasses.replace(_numbers(), mailboxes=boxes[2:])        # can-be-said with nothing finished
    assert "may NOT be said" in _section(D.build_dossier(_parts(numbers=unread)), "coverage")


def test_a_meeting_after_our_last_mail_is_not_their_reply():
    numbers = dataclasses.replace(_numbers(), no_reply_since=NOW - timedelta(days=60) + timedelta(hours=4))
    meeting = Touch(at=NOW - timedelta(days=60) + timedelta(hours=4, minutes=30), kind="meeting",
                    direction="meeting", who=None, who_name=None, event_id="evt_meet", thread=None)
    tl = _timeline((_touch(0, direction="out"), _touch(3), meeting))
    parts = dataclasses.replace(_parts(numbers=numbers), timeline=tl)
    coverage = _section(D.build_dossier(parts), "coverage")
    assert "they wrote after it" not in coverage and "may be said" in coverage


def test_a_reply_after_our_last_mail_is_said_and_no_reply_never_is():
    numbers = dataclasses.replace(_numbers(), no_reply_since=NOW - timedelta(days=60) + timedelta(hours=1))
    coverage = _section(D.build_dossier(_parts(numbers=numbers)), "coverage")
    assert "they wrote after it [evt_003]" in coverage and "may be said" not in coverage


def test_no_mailbox_and_no_mail_of_ours_is_no_absence():
    numbers = dataclasses.replace(_numbers(mailboxes=0), no_reply_since=None)
    coverage = _section(D.build_dossier(_parts(numbers=numbers)), "coverage")
    assert "Whether we wrote in this file cannot be said" in coverage
    assert "We have not written" not in coverage
    read = dataclasses.replace(_numbers(), no_reply_since=None)
    assert "We have not written in this file." in _section(D.build_dossier(_parts(numbers=read)),
                                                           "coverage")


def test_a_decision_on_a_situation_still_open_is_no_ending():
    parts = _parts()
    j = parts.judgments
    still = dataclasses.replace(j.situations[0], status="active", outcome="decided",
                                reason="emitted")
    judged = dataclasses.replace(parts, judgments=dataclasses.replace(j, situations=(still,)))
    text = _section(D.build_dossier(judged), "judged_before")
    assert "investor_relationship active; last decided: decided — emitted" in text
    assert "ended" not in text
    assert "investor_relationship ended: decided" in _section(D.build_dossier(parts), "judged_before")
    from genios_engine.context.workstreams import OPEN_STATUSES
    assert set(D._OPEN) == OPEN_STATUSES


def test_a_meeting_booked_ahead_is_no_touch_and_no_negative_quiet():
    parts = _parts()
    meeting = NOW + timedelta(days=2)
    booked = dataclasses.replace(parts, file=dataclasses.replace(parts.file, last_touch=meeting))
    life = parts.lifecycle
    ahead = dataclasses.replace(life, situations=(dataclasses.replace(
        life.situations[0], last_seen_at=meeting, days_since_seen=-2.0),))
    d = D.build_dossier(dataclasses.replace(booked, lifecycle=ahead))
    assert f"last touch {D._when(parts.timeline.touches[-1].at)}" in _section(d, "file")
    situations = _section(d, "situations")
    assert "quiet -2" not in situations and "last seen at a booking 2 days ahead" in situations


def test_an_unreviewed_playbook_says_so_and_no_playbook_says_why():
    assert "playbook not yet reviewed" in D.build_dossier(_parts()).text
    assert "reviewed by a named human" in D.build_dossier(_parts(playbook=_playbook(reviewed=True))).text
    none = D.build_dossier(_parts(playbook=PlaybookAnswer(kind="partner", playbook=None,
                                                          reason="no_capability_for_kind")))
    assert "No playbook for this file: no capability is written for its kind of work yet." in none.text
    assert none.catalogue.stages == ()


def test_no_brief_says_so():
    assert "No company brief is accepted for this tenant." in D.build_dossier(_parts(brief=False)).text


# ── a review is held to this dossier ───────────────────────────────────────────────────────────

def _review(evidence: str, draft: str, *, quote: str | None = "I will book it again tonight") -> ExpertReview:
    """A review of the file `_parts` builds. Since STEP-13 (`yc2_w27_s13`) it carries what the check reads:
    its one fact quotes the mail it cites (touch 5's own words by default) and its draft says whom it goes
    to — so a review the check would refuse is never this fixture by accident."""
    return ExpertReview.from_mapping({
        "facts": [{"claim": "Kunal sent the link again", "evidence": [evidence],
                   **({"quote": quote} if quote else {})}],
        "inferences": [{"claim": "the next move is ours", "based_on": ["fact:1"]}],
        "frames": {"primary": "a first call being booked", "rivals": ["a polite brush-off"]},
        "expected_vs_actual": {"stage": "first_call", "expected": "the call booked",
                               "actual": "we have not booked it"},
        "scenarios": {"do_nothing": "the fund moves on", "act": "the call happens",
                      "best": "a partner meeting", "worst": "a pass",
                      "signals_to_watch": ["a calendar invite"]},
        "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                      "reasons": ["our move, nine days quiet"]},
        "mode": "act", "next_move": {"who": "the founder", "what": "book the call",
                                     "for_whom": "Kunal", "by_when": "2026-10-11", "to": "Kunal"},
        "wait_or_stop": "if no slot by Friday, ask for another week",
        "done_when": "the call is on the calendar", "draft": draft})


def test_a_review_that_cites_what_it_was_shown_validates_and_one_that_cites_a_cut_touch_does_not():
    touches = [_touch(n, words=f"words of touch {n}") for n in range(50)]
    d = D.build_dossier(_parts(touches=touches))
    assert validate(_review("evt_049", "Hi Kunal, booking it now."), d.catalogue).ok
    refused = validate(_review("evt_000", "Hi Kunal, booking it now."), d.catalogue)
    assert UNKNOWN_EVIDENCE in refused.reasons, refused.problems


# ── bounded by construction ────────────────────────────────────────────────────────────────────

def test_a_maximal_dossier_stays_under_its_bound():
    long_words = " ".join(["word"] * 300)[:1200]
    touches = [_touch(n, words=long_words, cut=4000) for n in range(200)]
    promises = tuple(D.Promise(promise_id=f"node_c{i}", words="x" * 200, quote="y" * 400,
                               due_at=NOW, status="open", owner=KUNAL, ours=False,
                               event_id=f"evt_{i:03d}") for i in range(D.PROMISES_LIMIT))
    brief_lines = [CompanyBriefLine(line_id=f"cbl_{i}", section="goals", text="g" * 190)
                   for i in range(40)]
    parts = _parts(touches=touches, promises=promises,
                   playbook=_playbook(moves=D.MOVES_LIMIT + 5, claims=D.CLAIMS_LIMIT + 5),
                   numbers=_numbers(people=D.PEOPLE_LIMIT + 5, mailboxes=4))
    parts = D.DossierParts(**{**{f: getattr(parts, f) for f in parts.__dataclass_fields__},
                              "brief": compose(org_id="org_x", company="Nimbus Labs",
                                               founder="Arjun Rao", lines=brief_lines)})
    d = D.build_dossier(parts)
    assert len(d.text) < D.DOSSIER_CHARS, len(d.text)
    assert d.cut["playbook"] == 10 and d.cut["numbers"] == 5


# ── read from memory ───────────────────────────────────────────────────────────────────────────

@pytest.mark.pg
def test_a_files_dossier_is_read_from_memory(pg_store):
    from tests.context.workstream_world import FOUNDER, process, reset, tenant
    org = "org_s12_dossier"
    tenant(pg_store, org)
    try:
        process(pg_store, org, event_id="evt_d_in", sender=KUNAL, thread="t_d",
                at=NOW - timedelta(days=12))
        process(pg_store, org, event_id="evt_d_out", sender=FOUNDER, recipients=(KUNAL,),
                thread="t_d", at=NOW - timedelta(days=10))
        with pg_store.engine.connect() as c:
            from sqlalchemy import text
            file_id = c.execute(text(
                "select distinct k.anchor_node_id from context_correlations k "
                "  join context_correlation_members m on m.org_id = k.org_id "
                "       and m.correlation_id = k.correlation_id "
                " where k.org_id = :o and m.event_id = 'evt_d_in'"), {"o": org}).scalar_one()
            d = D.dossier_for(c, org, file_id, now=NOW)
            assert D.dossier_for(c, org, "node_nobody_holds", now=NOW) is None
        assert {"evt_d_in", "evt_d_out"} <= d.catalogue.evidence_ids
        assert [s.name for s in d.sections] == list(D.SECTIONS)
        assert "No company brief is accepted for this tenant." in d.text
        assert "No playbook for this file: the brief names no kind of work for it." in d.text
    finally:
        reset(pg_store, org)


@pytest.mark.pg
def test_the_promises_in_a_files_own_mail_are_read_and_a_soon_is_no_deadline(pg_store):
    """The promise is a commitment node the drain writes (`context/pipeline`), its words an event of the
    file wrote, its quote on the fact's source reference — read here through the real writer."""
    from tests.context.workstream_world import FOUNDER, process, reset, tenant
    org = "org_s12_dossier_promises"
    tenant(pg_store, org)
    try:
        process(pg_store, org, event_id="evt_p_in", sender=KUNAL, thread="t_p",
                at=NOW - timedelta(days=12))
        process(pg_store, org, event_id="evt_p_out", sender=FOUNDER, recipients=(KUNAL,),
                thread="t_p", at=NOW - timedelta(days=10))
        with pg_store.engine.begin() as c:
            node = pg_store.find_or_create_node(c, org_id=org, node_type="commitment",
                                                canonical_key="commitment:test_soon",
                                                display_name="get back to Kunal", event_id="evt_p_out")
            elsewhere = pg_store.find_or_create_node(c, org_id=org, node_type="commitment",
                                                     canonical_key="commitment:test_other",
                                                     display_name="another file's promise",
                                                     event_id=None)
            for subject, event, fields in (
                    (node, "evt_p_out", (("commitment.text", "get back to Kunal", "string"),
                                         ("commitment.status", "open", "enum"),
                                         ("commitment.owner", FOUNDER, "string"),
                                         ("commitment.due_at", (NOW - timedelta(days=10)).isoformat(),
                                          "timestamp"))),
                    (elsewhere, "evt_not_this_files", (("commitment.text", "not this file's", "string"),))):
                for fld, val, vt in fields:
                    pg_store.write_fact(c, org_id=org, subject_node_id=subject, field=fld, value=val,
                                        value_type=vt, confidence=0.8,
                                        occurred_at=NOW - timedelta(days=10), event_id=event,
                                        evidence={"text": "I will get back to you soon"},
                                        source="gmail", authority_rank=2)
        with pg_store.engine.connect() as c:
            from sqlalchemy import text
            file_id = c.execute(text(
                "select distinct k.anchor_node_id from context_correlations k "
                "  join context_correlation_members m on m.org_id = k.org_id "
                "       and m.correlation_id = k.correlation_id "
                " where k.org_id = :o and m.event_id = 'evt_p_in'"), {"o": org}).scalar_one()
            d = D.dossier_for(c, org, file_id, now=NOW)
        section = next(s for s in d.sections if s.name == "promises")
        assert f"[promise:{node}] we promised: get back to Kunal · no deadline — its words say " \
               "“soon”" in section.text
        assert "not this file's" not in section.text and f"promise:{node}" in d.catalogue.evidence_ids
    finally:
        reset(pg_store, org)


# ── STEP-14 · a file card's versions, and a meeting by its title (`yc2_w27_s14` M42.C2.L-interface.V3.U04) ──────

def _versioned_judgments() -> FileJudgments:
    from genios_engine.context.file_judgments import PriorVersion
    at = NOW - timedelta(days=20)
    j = _judgments()
    card = dataclasses.replace(j.cards[0], headline="Send Kunal the deck by Friday", state="queued", versions=(
        PriorVersion(version=1, headline="Reply to Kunal", change="created", material=True, changed=(), at=at),
        PriorVersion(version=2, headline="Send Kunal the deck by Friday", change="updated", material=True,
                     changed=("headline", "by_when"), at=at + timedelta(days=2))))
    return dataclasses.replace(j, cards=(card,))


def test_a_files_card_is_printed_with_its_versions():
    """The expert still sees the advice it gave before — one card, each version under it, what changed and when."""
    parts = dataclasses.replace(_parts(), judgments=_versioned_judgments())
    judged = _section(D.build_dossier(parts), "judged_before")
    assert "- [card:card_1] a card “Send Kunal the deck by Friday”, queued" in judged
    assert "  version 1: “Reply to Kunal”" in judged
    assert "  version 2, updated (headline, by_when): “Send Kunal the deck by Friday”" in judged
    assert "UTC" not in judged.split("[card:card_1]")[1].split("\n- ")[0], "no instant: a dossier replays exactly"
    assert judged.index("version 1") < judged.index("version 2")


def test_a_card_never_versioned_prints_as_before():
    assert "version 1" not in _section(D.build_dossier(_parts()), "judged_before")


def test_a_meeting_is_named_by_its_title_and_the_check_still_reads_it_as_a_meeting():
    """`03` F164: "a meeting at …" named no meeting — F54's "Fintech founders mixer - Bluebay" read as any meeting.
    The calendar's title is printed beside it; the check's own reading of a meeting (`verify._MET`) is unchanged."""
    from genios_engine.reason.expert.verify import _MET
    held = Touch(at=NOW - timedelta(days=3), kind="meeting", direction="meeting", who=KUNAL, who_name="Kunal Shah",
                 event_id="evt_met", thread=None, outcome="emitted", words=None)
    booked = Touch(at=NOW + timedelta(days=2), kind="meeting", direction="meeting", who=KUNAL, who_name="Kunal Shah",
                   event_id="evt_next", thread=None, outcome="emitted", words=None)
    parts = _parts(touches=(_touch(0, direction="out", words="Shall we meet?"), held))
    parts = dataclasses.replace(parts, timeline=dataclasses.replace(parts.timeline, upcoming=(booked,)),
                                meeting_titles={"evt_met": "Fintech founders mixer - Bluebay",
                                                "evt_next": "Partner meeting — Meridian"})
    timeline = _section(D.build_dossier(parts), "timeline")
    assert "  the calendar calls it “Fintech founders mixer - Bluebay”" in timeline
    # ⛔ RESTATED by `yc2_w27_s14` M42.C2.L-interface.V3.U04 (fix, found by the golden lane 14 Oct): a title is the
    # calendar's, never the meeting's words — memory still holds none, and the dossier still says so (F54's and the
    # second fix wave's "a wordless meeting" read exactly that line).
    assert "  the calendar calls it “Fintech founders mixer - Bluebay”\n  (memory holds no words for it)" in timeline
    assert D.meeting_events(parts.timeline) == ("evt_met", "evt_next"), "its meetings — held and booked — never a mail"
    assert (f"Booked: [evt_next] a meeting at {D._when(booked.at)}, the calendar calls it “Partner meeting — "
            f"Meridian”") in timeline
    assert {m.group("evt") for line in timeline.splitlines() for m in _MET.finditer(line)} == {"evt_met", "evt_next"}
    untitled = _section(D.build_dossier(dataclasses.replace(parts, meeting_titles={})), "timeline")
    assert "the calendar calls it" not in untitled and "(memory holds no words for it)" in untitled


@pytest.mark.pg
def test_a_meetings_title_is_read_from_its_meeting_node(pg_store):
    import json
    from sqlalchemy import text
    org = "org_s14_meeting_title"
    with pg_store.engine.begin() as c:
        for table in ("graph_facts", "graph_nodes", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'mt@example.test')"), {"o": org})
        for event, meeting in (("evt_title_1", "m1"), ("evt_title_2", "m2"), ("evt_title_3", "m3")):
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, source_object_id, "
                " dedup_key, actor, occurred_at, outcome) values (:e, :o, 'con_cal', 'gcal', 'calendar_event', :m, "
                " :k, cast(:a as jsonb), :at, 'emitted')"),
                {"e": event, "o": org, "m": meeting, "k": f"gcal:calendar_event:{event}",
                 "a": json.dumps({"type": "external_contact", "email": KUNAL}), "at": NOW})
        for node, key in (("node_m1", "gcal:m1"), ("node_m2", "gcal:m2")):
            c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key) "
                           "values (:n, :o, 'meeting', :k)"), {"n": node, "o": org, "k": key})
        for fid, node, title, scope, valid_to in (
                ("f1", "node_m1", "Fintech  founders\nmixer - Bluebay", "org", None),
                ("f1old", "node_m1", "An older title", "org", NOW),
                ("f2", "node_m2", "A private calendar's title", "private", None)):
            c.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, value, "
                " visibility_scope, valid_to) values (:v, :f, :o, :n, 'meeting.title', cast(:t as jsonb), :s, :to)"),
                {"v": f"fv_{fid}", "f": fid, "o": org, "n": node, "t": json.dumps(title), "s": scope, "to": valid_to})
        titles = D.read_meeting_titles(c, org, ["evt_title_1", "evt_title_2", "evt_title_3", "evt_none"])
        for table in ("graph_facts", "graph_nodes", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})
    assert titles == {"evt_title_1": "Fintech founders mixer - Bluebay"}
