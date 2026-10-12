"""One file, its real dossier and a faithful review of it — the world STEP-13's check is tested on.

Not a test module: `tests/reason/expert/test_verify*.py` read it. Marco Ruiz backs AI tooling at Altavia
Partners; Introly introduced him on 4 Aug; we wrote on 5 Aug; on 11 Aug he asked for a short deck before a
call. The dossier is built by `reason/expert/dossier.build_dossier` itself, so every line the check reads
is a line the expert is really shown. `answer(**over)` is the faithful review — every fact on its lines,
the move resting on the facts it names, its draft to Marco — with any part replaced.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone

from genios_engine.context.file_judgments import FileJudgments
from genios_engine.context.workstream_numbers import FileNumbers, PersonNumbers
from genios_engine.context.workstream_timeline import FileTimeline, Touch
from genios_engine.context.workstreams import Ask, Lifecycle, SituationLife, WorkFile
from genios_engine.contracts.company_brief import CompanyBriefLine, compose
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.contracts.measured import PLAYBOOK_PRIOR, Measured, median_of
from genios_engine.packs.compiler.playbook_reader import KindPlaybook, PlaybookAnswer, StopRule
from genios_engine.packs.compiler.stage_priors import StagePrior
from genios_engine.platform.self_identity import SelfIdentity
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.simulation import what_if_nothing

NOW = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
FILE = "node_marco"
MARCO = "marco@altavia.test"
INTROLY = "hello@introly.test"
US = SelfIdentity.of(addresses=("arjun@nimbuslabs.test",), domains=("nimbuslabs.test",))
OUR_NAMES = ("Nimbus Labs", "Arjun Rao")

INTRO, OURS, ASK = "evt_intro_0804", "evt_arjun_0805", "evt_marco_0811"
ASK_DECK, ASK_CALL, ASK_MEET = "loop:ask_deck", "loop:ask_call", "loop:ask_meet"
REPLY_TIME = f"num:their_reply_time:{MARCO}"


def _touches(*, ask_words: str) -> tuple[Touch, ...]:
    return (
        Touch(at=datetime(2026, 8, 4, 10, 0, tzinfo=timezone.utc), kind="mail", direction="in",
              who=INTROLY, who_name="Introly", event_id=INTRO, thread="t_intro",
              words="Arjun, meet Marco Ruiz, who backs AI tooling at Altavia Partners."),
        Touch(at=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc), kind="mail", direction="out",
              who="arjun@nimbuslabs.test", who_name="Arjun Rao", event_id=OURS, thread="t_intro",
              words="Hi Marco, Introly suggested we talk. Would a call next week work?"),
        Touch(at=datetime(2026, 8, 11, 9, 20, tzinfo=timezone.utc), kind="mail", direction="in",
              who=MARCO, who_name="Marco Ruiz", event_id=ASK, thread="t_intro", words=ask_words))


MEETING = "evt_meeting"


def parts(*, ask_words: str = ("Thanks Arjun — could you send a short deck before we set up a call? "
                               "I read everything within a week."),
          kind: str = "intro", introduced_by: str | None = INTROLY, asks_a_call: bool = False,
          meeting_at: datetime | None = None) -> D.DossierParts:
    """The file's parts. `asks_a_call`: Marco's mail also asks for a call (`loop:ask_meet`, a
    `meeting_request` that waits on us). `meeting_at`: a meeting on the file — held, before `NOW`, or
    booked ahead, after it."""
    touches = _touches(ask_words=ask_words)
    upcoming: tuple[Touch, ...] = ()
    if meeting_at is not None:
        meeting = Touch(at=meeting_at, kind="meeting", direction="meeting", who=MARCO,
                        who_name="Marco Ruiz", event_id=MEETING, thread=None)
        if meeting_at > NOW:
            upcoming = (meeting,)
        else:
            touches = tuple(sorted((*touches, meeting), key=lambda t: t.at))
    gaps = tuple(round((touches[i + 1].at - touches[i].at).total_seconds() / 86400, 2)
                 for i in range(len(touches) - 1))
    timeline = FileTimeline(file_id=FILE, as_of=NOW, touches=touches, upcoming=upcoming, gaps_days=gaps,
                            usual_gap=median_of(gaps, basis="file", unit="days"),
                            longest_gap_days=max(gaps),
                            days_quiet=round((NOW - touches[-1].at).total_seconds() / 86400, 2),
                            silence_exceeds_prior_gaps=True)
    asked, we_asked = datetime(2026, 8, 11, 9, 20, tzinfo=timezone.utc), datetime(2026, 8, 5, 12, 0,
                                                                                  tzinfo=timezone.utc)
    asks = (Ask(loop_id="ask_deck", kind="question", asked_by=FILE, owed_by="us",
                thread_id="t_intro", opened_at=asked),
            Ask(loop_id="ask_call", kind="meeting_request", asked_by="node_tenant", owed_by="them",
                thread_id="t_intro", opened_at=we_asked))
    if asks_a_call:
        asks += (Ask(loop_id="ask_meet", kind="meeting_request", asked_by=FILE, owed_by="us",
                     thread_id="t_intro", opened_at=asked),)
    work = WorkFile(file_id=FILE, kind=kind, line=None, introduced_by=introduced_by,
                    counterparty="Marco Ruiz", counterparty_key=MARCO, counterparty_type="person",
                    domains=("founder_office",), correlations=("c_marco",),
                    events=tuple(t.event_id for t in touches), first_touch=touches[0].at,
                    last_touch=touches[-1].at, days_quiet=timeline.days_quiet, whose_move="ours",
                    open_asks=asks, people=(FILE,), work_kind="investor")
    numbers = FileNumbers(
        file_id=FILE, as_of=NOW,
        people=(PersonNumbers(node_id=FILE, key=MARCO, name="Marco Ruiz",
                              their_reply_time=Measured(value=6, n=1, basis="person", unit="days"),
                              their_normal=None,
                              your_reply_time=Measured(value=None, n=0, basis="person", unit="days"),
                              your_normal=None, bounced_at=None),),
        your_normal_overall=None, mailboxes=(), no_reply_since=touches[1].at, no_reply_can_be_said=False)
    prior = Measured(value=21, n=0, basis="playbook pb.spine", source=PLAYBOOK_PRIOR, unit="days")
    playbook = PlaybookAnswer(kind="investor", playbook=KindPlaybook(
        kind="investor", capability_id="founder_office.fundraising.investor_relations",
        playbook_id="founder_office.pb.investor.run_the_round", name="Run the round",
        stages=(StagePrior(name="first_call", label="First call", typical=prior,
                           cited="practitioner judgement", quiet_means="they are busy",
                           leaves_when="a partner meeting is booked"),),
        do_nothing_consequence="The fund moves on to the next deal.", success_signal="a partner meeting",
        outcome_window_days=14,
        stop=StopRule(dormant_after=Measured(value=90, n=0, basis="playbook pb.spine",
                                             source=PLAYBOOK_PRIOR, unit="days"),
                      cited="practitioner judgement", then="close the file"),
        moves=(), claims=(), reviewed=False, review_label="playbook not yet reviewed"))
    life = Lifecycle(file_id=FILE, situations=(SituationLife(
        situation_id="sit_marco", situation_type="investor_relationship", domain="founder_office",
        status="active", first_seen_at=touches[0].at, last_seen_at=touches[-1].at, days_seen=7.0,
        days_since_seen=9.0, quiet_window_days=90, window_from="kind", past_window=False),))
    return D.DossierParts(
        org_id="org_x", file_id=FILE, as_of=NOW,
        brief=compose(org_id="org_x", company="Nimbus Labs", founder="Arjun Rao",
                      lines=[CompanyBriefLine(line_id="cbl_1", section="in_motion",
                                              text="Investor · Altavia Partners — introduced by Introly",
                                              kind="investor", domain="altavia.test")]),
        file=work, timeline=timeline, numbers=numbers, playbook=playbook,
        judgments=FileJudgments(file_id=FILE), lifecycle=life,
        what_if=what_if_nothing(now=NOW, quiet_days=timeline.days_quiet, stop_after_days=90,
                                stop_cited="practitioner judgement",
                                do_nothing="The fund moves on to the next deal.", lifecycle=life,
                                next_date=None))


def world(**kw) -> tuple[D.Dossier, D.FilePeople]:
    """The dossier and the file's people, as the expert's check is handed them."""
    p = parts(**kw)
    return D.build_dossier(p), D.people_of(p, us=US, our_names=OUR_NAMES)


ANSWER = {
    "facts": [
        {"claim": "Marco asked for a short deck before setting up a call", "evidence": [ASK],
         "quote": "could you send a short deck before we set up a call"},
        {"claim": "His ask for the deck waits on us", "evidence": [ASK_DECK]},
        {"claim": "Marco answered our first mail in 6 days", "evidence": [REPLY_TIME]},
        {"claim": "Introly introduced Marco on 4 Aug", "evidence": [INTRO]}],
    "inferences": [{"claim": "Marco is screening before he spends a call", "based_on": ["fact:1"]}],
    "patterns": [{"kind": "pattern", "claim": "He answers within a week", "based_on": ["fact:3"]}],
    "hypotheses": [{"proposition": "Altavia is raising a new fund", "needs": "its own news"}],
    "unknowns": [{"question": "Does Altavia lead seed rounds?", "relevance": "decides the ask"}],
    "frames": {"primary": "An introduced investor has asked for a deck before a call; the deck is ours to send",
               "rivals": ["a polite brush-off"]},
    "expected_vs_actual": {"stage": "first_call", "expected": "a call is set", "actual": "a deck is asked first"},
    "scenarios": {"do_nothing": "the introduction goes cold", "act": "the call follows the deck",
                  "best": "a partner meeting", "worst": "a polite pass",
                  "signals_to_watch": ["his reply to the deck"]},
    "appraisal": {"stakes": "high", "urgency": "medium", "reversibility": "reversible",
                  "reasons": ["a warm introduction to a fund that backs AI tooling"]},
    "mode": "act",
    "next_move": {"who": "you", "what": "Send Marco the short deck and offer two times for a call",
                  "for_whom": "Marco Ruiz", "by_when": "2026-08-21", "rests_on": ["fact:1", "fact:2"],
                  "to": "Marco", "answers": ASK_DECK},
    "alternative": "Write to Marco directly with the deck",
    "wait_or_stop": "if he has not answered the deck in a week, ask once",
    "done_when": "Marco has the deck and a call is booked, or he has said it is not a fit",
    "draft": "Hi Marco, thanks for the note — the short deck is attached. Would a call this week or next suit? Arjun"}


def answer(**over) -> dict:
    """The faithful review, any top-level part replaced; `move=` and `fact<n>=` replace inside them."""
    raw = copy.deepcopy(ANSWER)
    move = over.pop("move", None)
    if move is not None:
        raw["next_move"] = None if move is False else {**raw["next_move"], **move}
    for key in [k for k in over if k.startswith("fact") and k[4:].isdigit()]:
        n = int(key[4:])
        raw["facts"][n - 1] = {**raw["facts"][n - 1], **over.pop(key)}
    raw.update(over)
    return raw


def review(**over) -> ExpertReview:
    return ExpertReview.from_mapping(answer(**over))


__all__ = ["ANSWER", "ASK", "ASK_CALL", "ASK_DECK", "ASK_MEET", "MEETING", "FILE", "INTRO", "INTROLY", "MARCO", "NOW", "OURS",
           "OUR_NAMES", "REPLY_TIME", "US", "answer", "parts", "review", "world"]
