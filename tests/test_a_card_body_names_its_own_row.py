"""A per-subject card whose body cannot mention its own subject is not a card.

Measured on the design partner's production org on 2026-08-31, after the fresh re-sync that
followed the abstention fix. 56 cards, and the level and score work — `{prescriptive: 41,
review: 15}`, nine distinct scores. What the founder saw in the Mac app was the body:

    43 of 56 headlines distinct; 46 of 56 BODIES distinct
    ELEVEN cards shared one byte-identical sentence, and it stopped mid-clause on "and":

      "They wrote several days ago and no reply has gone back. The deadline is from your
       stated first-response policy, not from a contract, and"

    under eleven headlines that were correct and all different —
      "Thread with nikhil@addis.im is owed a reply"
      "willow@myzyner.com: 99 hours past first response"
      "maria@alystventures.com: 577 hours overdue"

Four separate faults stacked into that one sentence, and each has a test below.

  1. THE GUARD ATE THE WRITTEN LINE. `reject_detail` says `V-02:name:Ball` on 28 of the 56 cards —
     half the queue. `_prompt` dumps the fact record WITH ITS KEYS, so the model is handed
     `"thread.ball_in_court": "us"` and writes the only English sentence that says; the corpus was
     built from the fact VALUES alone, so "Ball" was judged an invented company and the whole line
     was thrown away. The module's law already covered it — "a word the system itself put in the
     prompt cannot be evidence of invention" — and it had never been applied to the keys.

  2. THE TEMPLATE NAMED NOBODY. Every other situation in the corpus interpolates its subject into
     its fallback. `first_response_overdue` opened on the pronoun "They", so all eleven fallbacks
     were the same string before a single character was cut.

  3. THE DAY COUNT WAS THE SENTINEL. The compiled lane has no pack rule, so `clock_path` arrives
     None and `slots._CLOCK` was the only clock available — and it had one entry, for
     `deal_health`. `{days}` collapsed to the word "several" for waits of 4, 24 and 43 days.

  4. THE CAP CUT MID-SENTENCE. The interpolated template is 165 characters against a 140 cap, and
     `_fallback` capped it with `_trim_to_word` — the last space before 140, which is a word
     boundary and nothing more. The sentence-and-clause ladder `_fit` that the MODEL's output
     already walks was never applied to the deterministic line.

Replayed over the same live rows (the harness first reproduced all 34 stored fallback lines byte
for byte, so these are the code's output on real data and not an estimate):

                                    before   after
      distinct bodies / 55            45       55
      cards sharing the top body      11        1
      truncated mid-sentence          11        0
      V-02 name rejections re-judged  43       0 (all accepted)
"""
from __future__ import annotations

import glob
import re
from datetime import datetime, timedelta, timezone

import yaml

from genios_engine.context.domain_spec import registered_domains, spec_for
from genios_engine.context.support_situations import (
    Desk,
    Loop,
    Message,
    ResponsePolicy,
    read_backlog_items,
    read_first_response,
)
from genios_engine.deliver.render import (
    SITUATION_CAP,
    _corpus,
    _fallback,
    invention_ok,
)
from genios_engine.deliver.slots import SENTINELS, compute_slots

EVAL = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)

#: The live render block for `customer_support.sit.first_response_overdue`, read off the
#: authored file rather than restated, so the test cannot pass against a copy of the template
#: that production does not use.
FIRST_RESPONSE = yaml.safe_load(open(
    "Domain Expertise/Customer Support Expertise/capabilities/04-entitlement-and-sla/"
    "breach-prevention/situations/first-response-overdue.yaml"))["render"]


def _facts(**kw) -> dict:
    return {k: {"value": v, "confidence": 1.0, "authority_rank": 3} for k, v in kw.items()}


def _card_body(display_name: str, opened_at: str) -> str:
    """The deterministic body for one first-response row, end to end."""
    facts = _facts(**{"response.opened_at": opened_at, "response.overdue_hours": 99.03,
                      "response.target_source": "engine_default", "thread.ball_in_court": "us"})
    slots = compute_slots("first_response_overdue", display_name, facts, EVAL)
    return _fallback(FIRST_RESPONSE, slots)["situation"]


# ── 1 · the body has to distinguish this row from the next one ────────────────────────────────

def test_two_subjects_of_one_situation_do_not_share_a_single_body():
    """The founder's complaint, reduced to two rows.

    These are two of the eleven real live subjects. Before the fix both rendered the identical
    165-character template, cut to the identical 136 characters, under two correct and different
    headlines — so the app showed the same broken sentence twice with different titles over it.
    """
    a = _card_body("Thread with willow@myzyner.com", "2026-07-28T16:00:38+00:00")
    b = _card_body("Thread with maria@alystventures.com", "2026-08-06T09:00:00+00:00")
    assert a != b
    # It is not enough that they differ. Each has to carry the three things a reader acts on:
    # WHO, HOW LONG, and WHOSE TURN.
    assert "willow@myzyner.com" in a and "maria@alystventures.com" in b
    assert "32 days" in a and "24 days" in b
    assert "our move" in a and "our move" in b


def test_the_same_person_on_two_threads_gets_two_distinguishable_cards():
    """willow@myzyner.com really does hold two unanswered conversations, opened a month apart —
    2026-07-28 and 2026-08-25 — and the situation file defends that on purpose: "one requester
    routinely holds several conversations with separate clocks".

    So the second card is NOT suppressed; it is a different thread with a different arrival and a
    different deadline. What was wrong is that a reader could not tell them apart. The day count
    is what separates them, and it only exists because `{days}` now grounds.
    """
    older = _card_body("Thread with willow@myzyner.com", "2026-07-28T16:00:38+00:00")
    newer = _card_body("Thread with willow@myzyner.com", "2026-08-25T16:12:56+00:00")
    assert older != newer
    assert "32 days" in older and "4 days" in newer


def test_the_day_count_comes_from_the_arrival_fact_and_not_from_a_sentinel():
    """`{days}` collapsed to the word "several" on all eleven live cards. The compiled lane
    carries no pack rule, so nothing passed a clock and `_CLOCK` had no entry for this type."""
    slots = compute_slots("first_response_overdue", "Thread with x@y.com",
                          _facts(**{"response.opened_at": "2026-08-25T16:12:56+00:00"}), EVAL)
    assert slots["days"] == 4 and slots["days"] != SENTINELS["days"]


def test_a_body_that_cannot_date_the_wait_still_names_who_and_whose_turn():
    """`_interpolate` cuts the clause holding a slot it cannot substantiate, so the template is
    written in three em-dash clauses rather than two: losing the day count must not take the
    subject with it."""
    body = _card_body("Thread with willow@myzyner.com", "not-a-timestamp")
    assert "willow@myzyner.com" in body
    assert "our move" in body
    assert SENTINELS["days"] not in body


# ── 2 · a body is never cut mid-sentence ──────────────────────────────────────────────────────

#: A line that ends on one of these is a sentence that stopped, not a sentence that ended. The
#: live cards all ended on "and".
_MID_SENTENCE = re.compile(
    r"\s(?:and|but|or|not|from|to|of|with|the|a|an|in|on|for|is|are|was|were)$")


def test_the_fallback_body_of_every_live_first_response_row_is_a_finished_sentence():
    """The eleven real subjects, at their real arrival dates."""
    live = [("Thread with maria@alystventures.com", "2026-08-06T09:00:00+00:00"),
            ("Thread with nitesh.pant@devdashlabs.com", "2026-08-01T09:00:00+00:00"),
            ("Thread with nikhil@addis.im", "2026-07-18T09:00:00+00:00"),
            ("Thread with hi@zeropearl.vc", "2026-07-31T09:00:00+00:00"),
            ("Thread with sal@nexlayer.com", "2026-07-30T09:00:00+00:00"),
            ("Thread with willow@myzyner.com", "2026-07-28T16:00:38+00:00"),
            ("Thread with hv@errorcore.dev", "2026-07-20T09:00:00+00:00"),
            ("Thread with boardy@boardy.ai", "2026-08-14T09:00:00+00:00"),
            ("Thread with willow@myzyner.com", "2026-08-25T16:12:56+00:00"),
            ("Thread with shan@rizvi.nu", "2026-07-19T09:00:00+00:00"),
            ("Thread with boardy@boardy.ai", "2026-07-30T09:00:00+00:00")]
    bodies = [_card_body(n, at) for n, at in live]
    assert len(set(bodies)) == len(bodies), "eleven rows, eleven bodies"
    for b in bodies:
        assert len(b) <= SITUATION_CAP, (len(b), b)
        assert not _MID_SENTENCE.search(b), b


def test_an_overlong_body_loses_a_whole_clause_rather_than_half_a_word():
    """The general guarantee, not just this template's. A 62-character subject — the real
    `invoice+statements+acct_1ika5ja3kz32dpo1@stripe.com` address that has broken this renderer
    before — pushes the line 25 characters over the cap.

    `_trim_to_word` alone returned "... — your", which reads as a card that broke. The ladder
    drops the trailing clause instead, and what remains is whole.
    """
    body = _card_body("Thread with invoice+statements+acct_1ika5ja3kz32dpo1@stripe.com",
                      "2020-01-01T09:00:00+00:00")
    assert len(body) <= SITUATION_CAP
    assert not _MID_SENTENCE.search(body), body
    assert "stripe.com" in body and "our move" in body


def test_a_clause_boundary_inside_a_sentence_never_beats_the_whole_sentence():
    """Found by applying the ladder to the fallback, and it was wrong in `_fit` all along.

    `_CLAUSE_SPLIT` breaks on ", owner" exactly as it breaks on an em-dash, so with clauses tried
    FIRST the 157-character `queue_overloaded` body came back as "…has stopped moving. No queue" —
    stopping two words into its second sentence — while a whole 93-character first sentence was
    sitting there. Clause-splitting exists for a headline, which has no terminal punctuation and
    therefore no sentence run to find; asking it second costs that case nothing.
    """
    body = _fallback(yaml.safe_load(open(
        "Domain Expertise/Customer Support Expertise/capabilities/08-support-operations/"
        "queue-management/situations/queue-overloaded.yaml"))["render"],
        compute_slots("ticket_aging", "meeting request \u00b7 a counterparty", {}, EVAL))["situation"]
    assert body.endswith("stopped moving.")
    assert "No queue" not in body, "a sentence that begins must not be the last thing on the card"


# ── 3 · the guard must not eat a word the prompt supplied ─────────────────────────────────────

def test_a_fact_field_name_is_not_an_invented_company():
    """`V-02:name:Ball` on 28 of 56 live cards — the single biggest cause of a template body.

    `_prompt` serialises the fact dict with its keys, so the model is TOLD `thread.ball_in_court`
    and writes the idiom back. Judging that as an invented entity means the layer pays for a
    render, gets correct copy, and throws it away.
    """
    facts = _facts(**{"thread.ball_in_court": "us", "response.overdue_hours": 99.03})
    slots = compute_slots("first_response_overdue", "Thread with willow@myzyner.com", facts, EVAL)
    text, nums = _corpus(facts, slots, (), None)
    ok, why = invention_ok("Ball is in our court and has been for four days.", text, nums)
    assert ok, why


def test_a_company_nobody_mentioned_is_still_rejected():
    """The guard has to keep doing its job: widening the corpus to the field names must not turn
    it off. `Initech` appears in no fact, no key and no quote."""
    facts = _facts(**{"thread.ball_in_court": "us"})
    slots = compute_slots("first_response_overdue", "Thread with willow@myzyner.com", facts, EVAL)
    text, nums = _corpus(facts, slots, (), None)
    ok, why = invention_ok("Initech will vouch for us.", text, nums)
    assert not ok and why == "name:Initech"


def test_utc_is_grounded_by_a_utc_fact_and_by_nothing_else():
    """`V-02:name:UTC` discarded a live body for restating a timestamp the facts carry.

    A timezone word is a CLAIM, so it is derived from the fact — the same treatment the month
    name and the weekday already get — rather than being exempted as grammar. A tenant whose
    evidence is stamped +05:30 does not thereby ground the word "UTC".
    """
    utc_facts = _facts(**{"response.opened_at": "2026-08-25T16:12:56+00:00"})
    ist_facts = _facts(**{"response.opened_at": "2026-08-25T16:12:56+05:30"})
    slots = compute_slots("first_response_overdue", "Thread with x@y.com", utc_facts, EVAL)
    ok, _ = invention_ok("They wrote at 16:12 UTC.", *_corpus(utc_facts, slots, (), None))
    assert ok
    ok, why = invention_ok("They wrote at 16:12 UTC.", *_corpus(ist_facts, slots, (), None))
    assert not ok and why == "name:UTC"


# ── 4 · one open loop, reported once ──────────────────────────────────────────────────────────

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
US = "founder@acme.io"


def _msg(thread: str, at: datetime, sender: str, *, internal: bool = False) -> Message:
    return Message(event_id=f"ev_{thread}_{at.isoformat()}", thread_id=thread, at=at,
                   sender=sender, internal=internal, recipients=(), head="")


def _desk(messages, loops, *, thread_first=None) -> Desk:
    msgs = tuple(messages)
    first = thread_first or {m.thread_id: min(x.at for x in msgs if x.thread_id == m.thread_id)
                             for m in msgs}
    return Desk(org_id="o", now=NOW, internal=frozenset({US}),
                internal_domains=frozenset({"acme.io"}), messages=msgs, loops=tuple(loops),
                thread_node={m.thread_id: f"n_{m.thread_id}" for m in msgs},
                thread_first=first,
                thread_facts={f"n_{m.thread_id}": {"thread.ball_in_court": "us",
                                                   "thread.last_inbound": m.at.isoformat()}
                              for m in msgs},
                policy=ResponsePolicy(hours=24.0, source="engine_default"))


def _loop(loop_id, thread, days_open, kind="question") -> Loop:
    return Loop(loop_id=loop_id, subject_node_id="n_person", kind=kind, thread_id=thread,
                status="open", opened_at=NOW - timedelta(days=days_open), closed_at=None,
                ask_count=1)


def test_the_aging_reading_yields_a_thread_the_first_response_clock_already_owns():
    """Measured on the live org on 2026-08-31: 10 of the 11 threads carrying a first-response
    clock ALSO carried backlog items — 23 of the 41 aging items in total, up to 7 on one thread,
    one per ask kind the lexicon found in the same unanswered mail.

    It is structural rather than unlucky. A thread the clock fires on has had no internal message
    at all, so `ball` is trivially "us" and every ask extracted from it qualifies as aging too.

    `ticket_aging` is the one that yields. It is up to seven cards per thread against one; it
    restates the same clock more weakly ("this waited longer than comparable work" versus "nobody
    replied", and on a thread with no reply those are the same number); and its own docstring
    scopes it to items nobody committed to inside a worked relationship, which a thread we have
    never written on is not.
    """
    inbound = _msg("t1", NOW - timedelta(days=30), "them@customer.io")
    desk = _desk([inbound], [_loop("l1", "t1", 30), _loop("l2", "t1", 29, "meeting_request")])
    assert [f.canonical_key for f in read_first_response(desk)] == ["thread:t1"]
    assert read_backlog_items(desk) == []


def test_a_never_answered_thread_the_clock_skips_is_still_reported_as_aging():
    """The yield is keyed on the other reading actually FIRING, not on the thread merely looking
    unanswered — otherwise it is a silent suppression rather than a handover.

    A thread that began before the snapshot gets no first-response clock at all: its arrival time
    is unknown, and dating a deadline from the earliest message we happen to hold would put a
    fabricated deadline under a real card. Nothing reports it next door, so it stays here.
    """
    inbound = _msg("t1", NOW - timedelta(days=30), "them@customer.io")
    desk = _desk([inbound], [_loop("l1", "t1", 30)],
                 thread_first={"t1": NOW - timedelta(days=200)})
    assert read_first_response(desk) == []
    assert [f.canonical_key for f in read_backlog_items(desk)] == ["backlog:o:l1"]


def test_a_thread_we_replied_on_is_aging_and_not_a_first_response_miss():
    """The ordinary case, pinned so the yield cannot swallow it: a conversation we joined and
    then let go quiet is exactly what the aging reading is for."""
    them = _msg("t1", NOW - timedelta(days=30), "them@customer.io")
    us = _msg("t1", NOW - timedelta(days=29), US, internal=True)
    desk = _desk([them, us], [_loop("l1", "t1", 30)])
    assert read_first_response(desk) == []
    assert [f.canonical_key for f in read_backlog_items(desk)] == ["backlog:o:l1"]


# ── 5 · the corpus-wide law ───────────────────────────────────────────────────────────────────

#: The situation types whose anchor is one node for the WHOLE ORG. There is exactly one card of
#: each per tenant, so a body with no subject slot cannot collide with a sibling. Derived from
#: `domain_spec` rather than listed, so a new org-wide reading does not need this test edited.
#: `cohort` joins them: one node per stated OBJECTIVE per tenant, describing everyone contacted
#: about it. `{entity}` on a group card would name one person and then say something about
#: eighteen, which is worse than the gap the rule exists to close — so the requirement it does
#: have to meet is the same one in different words, and `campaign-going-quiet.yaml` meets it by
#: stating the split (`{contacted}`, `{awaiting}`, `{past_normal}`, `{never_chased}`) rather than
#: describing the category.
_ORG_WIDE_ANCHORS = {"tenant", "mailbox", "cohort"}

#: `customer_support.sit.queue_overloaded` declares TWO l2 types — `queue_overloaded` (one
#: mailbox, org-wide) and `ticket_aging` (one backlog_item per unmet ask, 41 of them on the live
#: org before the yield above, 18 after). One `render` block serves both, and it is written for
#: the mailbox: "arrivals are outrunning closures". Adding `{entity}` would make the sentence
#: name an item and then say something about the mailbox, which is worse than the gap.
#:
#: FLAGGED, NOT FIXED. The real repair is a `ticket-aging.yaml` of its own with its own copy —
#: authoring work, not a slot. It is latent today: `ticket_aging` minted 41 situations on the
#: live org and ZERO signals, so no card has ever carried this body. Recorded here so it is not
#: discovered later as a surprise.
_SUBJECTLESS_BY_DESIGN = {"customer_support.sit.queue_overloaded"}


def test_every_per_subject_situation_fallback_names_its_subject():
    """The law the eleven identical cards broke, held for the whole corpus rather than for the
    one file that broke it.

    A fallback is what ships when the model's line is refused, and on the live org that was 35 of
    56 cards — the majority. If it cannot name the row it is describing, the card is a category
    label with a headline on top.
    """
    anchor_of = {stype: anchor for d in registered_domains()
                 for anchor, stype in (spec_for(d).situation_types or {}).items()}
    offenders = []
    for path in glob.glob("Domain Expertise/**/situations/*.yaml", recursive=True):
        doc = yaml.safe_load(open(path)) or {}
        body = str((((doc.get("render") or {}).get("fallback")) or {}).get("situation") or "")
        sid = (doc.get("identity") or {}).get("id")
        if not body or sid in _SUBJECTLESS_BY_DESIGN:
            continue
        anchors = {anchor_of[t] for t in (doc.get("matches") or {}).get("l2_situation_types") or []
                   if t in anchor_of}
        if not anchors or anchors <= _ORG_WIDE_ANCHORS:
            continue            # nothing routes it yet, or there is one per tenant
        if not re.search(r"\{(entity|who)\}", body):
            offenders.append(sid)
    assert offenders == [], offenders
