"""Seven customer-support readings over a mailbox that has no helpdesk behind it.

`_schema/vocabulary.yaml` recorded the gap in one line: of the shipped Layer 2 situation types
exactly five are domain-neutral and ZERO observation kinds are support-native. Seven authored
situations therefore sat in `pending_l2_situation_types` — routed to nothing, counted by
`backlog.py`, invisible in the product. `context/support_situations.py` mints them from
correspondence.

Every one is an APPROXIMATION, and the failure these tests exist to prevent is not a wrong number.
It is a card that reads like a record: a headline saying "SLA Breach Imminent" on an org with no
SLAs, or a `missing` list that empties out the moment the mechanical facts land, so a downstream
gate reading "no actionable output when required context is unknown" goes green on ignorance. The
honesty properties below are pinned as hard as the arithmetic.

The readings take an in-memory `Desk` rather than a database, which is the whole reason they can
be tested at all: the gather is one bounded snapshot and the seven decisions are pure functions
over it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.context.domain_spec import domains_declaring, spec_for
from genios_engine.context.situations import COVERAGE_UNKNOWN, SCORE_MAX, coverage_score
from genios_engine.context.support_situations import (
    ANCHOR_BACKLOG_ITEM,
    ANCHOR_CONTACT_INTENT,
    ANCHOR_ESCALATION,
    ANCHOR_MAILBOX,
    ANCHOR_THREAD,
    ANCHOR_TOPIC,
    ANCHOR_WORKAROUND,
    QUIET_DAYS,
    READINGS,
    Desk,
    Loop,
    Message,
    ResponsePolicy,
    advance_working_hours,
    answer_reuse_bp,
    classify_intent,
    desk_domains,
    percentile_bp,
    read_backlog_items,
    read_escalations,
    read_first_response,
    read_knowledge_gaps,
    read_mailbox_load,
    read_repeat_contacts,
    read_workarounds,
    workaround_cost,
)

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)      # a Saturday
US = "founder@acme.io"


def _ago(days: float = 0, hours: float = 0) -> datetime:
    return NOW - timedelta(days=days, hours=hours)


def _msg(thread: str, at: datetime, sender: str, *, internal: bool = False,
         head: str = "", to: tuple[str, ...] = ()) -> Message:
    return Message(event_id=f"ev_{thread}_{at.isoformat()}_{sender}", thread_id=thread, at=at,
                   sender=sender, internal=internal, recipients=to, head=head)


def _desk(**kw) -> Desk:
    """A Desk with `us` known, because an org that has synced Gmail has by construction told us
    which address it owns. The empty-set case is pinned separately below."""
    base = dict(org_id="o", now=NOW, internal=frozenset({US}),
                internal_domains=frozenset({"acme.io"}))
    messages = kw.get("messages", ())
    base["thread_first"] = {m.thread_id: min(x.at for x in messages if x.thread_id == m.thread_id)
                            for m in messages}
    base.update(kw)
    return Desk(**base)


# ── the working-window clock ─────────────────────────────────────────────────────────────────

def test_the_first_response_clock_does_not_run_over_the_weekend():
    """A request arriving at 17:55 on a Friday under an eight-hour policy is not late at 01:55 on
    Saturday, and reporting it as late is how a first-response number stops being believed."""
    friday_1755 = datetime(2026, 8, 28, 17, 55, tzinfo=timezone.utc)
    due = advance_working_hours(friday_1755, ResponsePolicy(hours=8.0))
    assert due.weekday() == 0 and due.hour == 16 and due.minute == 55, due
    # five minutes on Friday, seven hours fifty-five on Monday from 09:00


def test_a_request_inside_the_working_day_is_due_the_same_day():
    tuesday_0930 = datetime(2026, 8, 25, 9, 30, tzinfo=timezone.utc)
    assert advance_working_hours(tuesday_0930, ResponsePolicy(hours=2.0)) == \
        datetime(2026, 8, 25, 11, 30, tzinfo=timezone.utc)


def test_a_policy_with_no_working_days_is_rejected_rather_than_looping():
    """An empty working week has no clock to run, and the walk that advances the deadline would
    skip days forever looking for one."""
    import pytest
    with pytest.raises(ValueError, match="no working days"):
        ResponsePolicy(working_days=())


# ── reading 1 · first response ───────────────────────────────────────────────────────────────

def test_an_unanswered_arrival_past_its_deadline_opens_a_situation():
    desk = _desk(messages=(_msg("t1", _ago(6), "customer@big.co", head="the export is broken"),),
                 thread_node={"t1": "n_t1"}, node_name={"n_t1": "Thread with customer@big.co"})
    found = read_first_response(desk)
    assert [f.anchor for f in found] == [ANCHOR_THREAD]
    facts = dict((k, v) for k, v, _ in found[0].facts)
    assert facts["response.channel"] == "email"
    # NEVER 'entitlement'. There is no per-customer target anywhere in this system, and the word
    # is what would turn a stated policy into a contractual claim.
    assert facts["response.target_source"] == "engine_default"


def test_a_thread_we_started_is_not_a_first_response_failure():
    """Nobody is waiting on a first reply to our own outbound message, and counting one would fill
    the reading with every cold email the org ever sent."""
    desk = _desk(messages=(_msg("t1", _ago(6), US, internal=True),
                           _msg("t1", _ago(5), "customer@big.co")),
                 thread_node={"t1": "n_t1"})
    assert read_first_response(desk) == []


def test_a_thread_that_began_before_the_snapshot_is_skipped_not_dated_from_what_we_hold():
    """The earliest message we can SEE is not necessarily the earliest message there was. Dating
    the arrival from it would put a fabricated deadline under a real card — so the thread is
    dropped, and the loss is reported rather than papered over."""
    desk = _desk(messages=(_msg("t1", _ago(6), "customer@big.co"),), thread_node={"t1": "n_t1"})
    desk = Desk(**{**{f: getattr(desk, f) for f in Desk.__slots__},
                   "thread_first": {"t1": _ago(400)}})
    assert read_first_response(desk) == []


def test_a_replied_thread_stops_the_clock():
    desk = _desk(messages=(_msg("t1", _ago(6), "customer@big.co"),
                           _msg("t1", _ago(5), US, internal=True)),
                 thread_node={"t1": "n_t1"})
    assert read_first_response(desk) == []


def test_the_clock_refuses_to_run_when_we_do_not_know_which_addresses_are_ours():
    """`runner._internal_emails` returns an EMPTY set on a tenant that never filled `org_seats`,
    and an empty "us" set does not fail loudly — every `sender not in internal` test passes, so
    every thread reads as never answered. The reading would then mint one overdue situation per
    conversation in the mailbox. It declines instead."""
    blind = Desk(org_id="o", now=NOW, internal=frozenset(), internal_domains=frozenset(),
                 messages=(_msg("t1", _ago(6), "customer@big.co"),),
                 thread_first={"t1": _ago(6)}, thread_node={"t1": "n_t1"})
    assert not blind.we_know_who_we_are
    assert read_first_response(blind) == []
    assert read_escalations(blind) == []


# ── reading 2 · one unmet ask, aging ─────────────────────────────────────────────────────────

def _loop(loop_id: str, thread: str, *, days_open: float, status: str = "open",
          closed: datetime | None = None, kind: str = "question", asks: int = 1) -> Loop:
    return Loop(loop_id=loop_id, subject_node_id="n_person", kind=kind, thread_id=thread,
                status=status, opened_at=_ago(days_open), closed_at=closed, ask_count=asks)


def test_an_old_unmet_ask_opens_an_aging_item_with_no_promise_required():
    """The whole point of the type, and why `commitment_overdue` can never see it: the items that
    age are precisely the ones nobody promised anything about. Nobody committed, so nothing is
    overdue, so the oldest item in the queue is invisible to the only elapsed-time signal the
    pipeline had."""
    desk = _desk(loops=(_loop("l1", "t1", days_open=30),),
                 thread_node={"t1": "n_t1"},
                 thread_facts={"n_t1": {"thread.ball_in_court": "us",
                                        "thread.last_inbound": _ago(30).isoformat()}})
    found = read_backlog_items(desk)
    assert [f.anchor for f in found] == [ANCHOR_BACKLOG_ITEM]
    facts = dict((k, v) for k, v, _ in found[0].facts)
    assert facts["backlog.waiting_on"] == "us"
    # The two clocks are carried SEPARATELY. An old item being actively worked and an old item
    # nobody has touched share an age and are completely different findings.
    assert "backlog.age_days" in facts and "backlog.days_since_customer" in facts


def test_a_self_opened_outbound_ask_never_becomes_backlog():
    """`ASK_KINDS` includes `proposal_sent`, and `pipeline.py` files an outbound ask against OUR
    OWN node while `close_loops_for_reply` closes on the recipient — so a self-opened loop never
    closes. Without the ball_in_court filter it would inflate this backlog's size and age
    forever, and it is the oldest thing in it by construction."""
    desk = _desk(loops=(_loop("l1", "t1", days_open=200, kind="proposal_sent"),),
                 thread_node={"t1": "n_t1"},
                 thread_facts={"n_t1": {"thread.ball_in_court": "them"}})
    assert read_backlog_items(desk) == []


def test_work_legitimately_parked_with_the_customer_does_not_age():
    desk = _desk(loops=(_loop("l1", "t1", days_open=60),),
                 thread_node={"t1": "n_t1"},
                 thread_facts={"n_t1": {"thread.ball_in_court": "them"}})
    assert read_backlog_items(desk) == []


def test_the_aging_band_is_relative_to_this_orgs_own_turnaround():
    """A constant threshold calls a fast team broken and a slow one healthy. The band is twice the
    org's median closed-loop span, floored so a tenant that replies in hours does not open an
    aging item on everything unanswered overnight."""
    fast = _desk(
        loops=tuple([_loop("l1", "t1", days_open=4)]
                    + [_loop(f"c{n}", "tx", days_open=10, status="closed",
                             closed=_ago(9.9)) for n in range(5)]),
        thread_node={"t1": "n_t1"}, thread_facts={"n_t1": {"thread.ball_in_court": "us"}})
    # median closed span ~0.1d -> band falls to the 3-day floor, so a 4-day item qualifies
    assert len(read_backlog_items(fast)) == 1

    slow = _desk(
        loops=tuple([_loop("l1", "t1", days_open=4)]
                    + [_loop(f"c{n}", "tx", days_open=40, status="closed",
                             closed=_ago(30)) for n in range(5)]
                    + [_loop(f"o{n}", f"t{n + 2}", days_open=50) for n in range(9)]),
        thread_node={f"t{n}": f"n_t{n}" for n in range(1, 12)},
        thread_facts={f"n_t{n}": {"thread.ball_in_court": "us"} for n in range(1, 12)})
    # median closed span 10d -> band 20d, and the 4-day item is also nowhere near the 90th
    # percentile of the nine 50-day items, so it stays quiet.
    assert "l1" not in {f.inputs["loop_id"] for f in read_backlog_items(slow)}


def test_the_percentile_is_computed_in_python_because_the_module_must_run_on_sqlite():
    """`percentile_cont` is Postgres-only — the same constraint `open_loops.py` records when it
    uses CASE instead of `greatest()`. Ties count as half so a population of identical ages
    reports the middle rather than putting everybody at the top."""
    assert percentile_bp([1.0, 2.0, 3.0, 4.0], 4.0) == 8750
    assert percentile_bp([5.0, 5.0, 5.0], 5.0) == 5000
    assert percentile_bp([], 5.0) == 0


# ── reading 3 · escalation ───────────────────────────────────────────────────────────────────

def test_an_escalation_stays_open_across_replies():
    """The defining property, and the reason this cannot be `unanswered_email`: an escalation
    request only resembles an unanswered email while it is unanswered, which is the shortest part
    of its life. The moment the current owner replies, the compromise binding falls silent while
    the escalation is still unaccepted and still unowned — and the two prescribe opposite
    handling, because a reply from the current owner is exactly what the customer rejected."""
    desk = _desk(messages=(_msg("t1", _ago(3), "angry@big.co",
                                head="this is going nowhere, put me through to your manager"),
                           _msg("t1", _ago(2), US, internal=True, head="sorry, looking into it")),
                 person_node={"angry@big.co": "n_p", US: "n_us"},
                 node_name={"n_p": "Angry Customer"})
    found = read_escalations(desk)
    assert [f.anchor for f in found] == [ANCHOR_ESCALATION]
    facts = dict((k, v) for k, v, _ in found[0].facts)
    assert facts["escalation.receiver_named"] is False
    assert facts["escalation.status"] == "requested"


def test_an_unaccepted_escalation_goes_stale_and_stays_open_rather_than_quiet():
    """An unaccepted escalation going quiet is the FAILURE, not the resolution. Past the typical
    span it is written `stale` and the situation stays ACTIVE — which is why these rows are
    written directly and never handed to `DORMANT_AFTER_DAYS`."""
    desk = _desk(messages=(_msg("t1", _ago(20), "angry@big.co", head="I want your manager"),),
                 person_node={"angry@big.co": "n_p"})
    facts = dict((k, v) for k, v, _ in read_escalations(desk)[0].facts)
    assert facts["escalation.status"] == "stale"


def test_a_reply_from_the_owner_the_customer_just_rejected_is_not_an_acceptance():
    """The defect this rule was written twice to get right. "An internal sender new to this
    thread" matched the ORIGINAL OWNER's first reply on a thread the customer had started, and
    scored it as a transfer — closing every escalation with the answer that caused it. The
    incumbent is the first internal voice on the thread, whenever they wrote, and they can never
    accept."""
    desk = _desk(messages=(_msg("t1", _ago(3), "angry@big.co", head="escalate this please"),
                           _msg("t1", _ago(2), "owner@acme.io", internal=True)),
                 person_node={"angry@big.co": "n_p", "owner@acme.io": "n_owner"})
    assert len(read_escalations(desk)) == 1


def test_a_new_internal_name_on_the_thread_closes_the_escalation():
    """Acceptance is the customer-visible act the capability names: an unfamiliar name appeared on
    their thread. It is an INFERENCE and wrong in both directions — a receiver who takes over
    internally while the original owner keeps writing scores as never having accepted — which is
    why the situation carries the raw interval and never an acceptance rate."""
    desk = _desk(messages=(_msg("t1", _ago(5), "angry@big.co", head="the sync is broken"),
                           _msg("t1", _ago(4), "owner@acme.io", internal=True),
                           _msg("t1", _ago(3), "angry@big.co", head="escalate this please"),
                           _msg("t1", _ago(2), "head@acme.io", internal=True)),
                 person_node={"angry@big.co": "n_p", "owner@acme.io": "n_owner",
                              "head@acme.io": "n_head"})
    assert read_escalations(desk) == []


def test_anger_alone_is_not_an_escalation():
    """A furious customer is a sentiment and belongs to `derived.sentiment`. The corpus's
    escalation is defined by an unaccepted REQUEST for somebody else, and matching anger would
    fill the type with people nobody was asked to hand over."""
    desk = _desk(messages=(_msg("t1", _ago(3), "angry@big.co",
                                head="this is completely unacceptable and I am furious"),),
                 person_node={"angry@big.co": "n_p"})
    assert read_escalations(desk) == []


def test_the_escalation_rolls_up_to_the_account():
    """The second escalation from a different contact at the same company is the same event
    continuing, and a person-scoped reading loses that entirely."""
    desk = _desk(messages=(_msg("t1", _ago(3), "a@big.co", head="I want your manager"),),
                 person_node={"a@big.co": "n_a"}, company_of={"n_a": "n_bigco"},
                 node_name={"n_bigco": "Big Co"})
    found = read_escalations(desk)
    assert found[0].concerns_node == "n_bigco"
    assert dict((k, v) for k, v, _ in found[0].facts)["escalation.account_node_id"] == "n_bigco"


def test_two_raises_at_one_account_on_one_day_are_two_subjects_and_neither_overwrites_the_other():
    """The roll-up above must not become a COLLISION. Keyed on `{org}:{account}:{date}` alone, two
    people at one company asking for a manager on the same day produced two findings sharing a
    canonical_key AND a correlation_id — so both wrote the same anchor node and the same situation
    row, and whichever the (then unordered) scan yielded last decided which `escalation.ask_text`
    and `escalation.thread_id` survived. A real unaccepted escalation was silently overwritten by
    another one, and nothing errored.

    Two raises are two subjects because acceptance is read per THREAD: a new name appearing on
    one thread cannot be an acceptance of the raise on the other. The account roll-up the corpus
    asks for survives in the places order cannot disturb — the `concerns` edge and
    `escalation.account_node_id`, both asserted here."""
    desk = _desk(messages=(
        _msg("t1", _ago(3), "a@big.co", head="I want your manager, billing is still wrong"),
        _msg("t2", _ago(3, hours=2), "b@big.co", head="escalate this please, the sync is down"),
    ), person_node={"a@big.co": "n_a", "b@big.co": "n_b"},
       company_of={"n_a": "n_bigco", "n_b": "n_bigco"}, node_name={"n_bigco": "Big Co"})
    found = read_escalations(desk)

    assert len(found) == 2
    assert len({f.canonical_key for f in found}) == 2, [f.canonical_key for f in found]
    assert len({f.correlation_id for f in found}) == 2, [f.correlation_id for f in found]
    facts = [dict((k, v) for k, v, _ in f.facts) for f in found]
    assert {f["escalation.thread_id"] for f in facts} == {"t1", "t2"}
    assert len({f["escalation.ask_text"] for f in facts}) == 2, "one raise's words replaced another"
    # The roll-up is untouched: both still belong to the account, which is what `scope: account`
    # in the situation file actually asks for.
    assert {f.concerns_node for f in found} == {"n_bigco"}
    assert {f["escalation.account_node_id"] for f in facts} == {"n_bigco"}


def test_messages_tied_on_a_timestamp_are_read_in_the_same_order_whatever_order_they_arrive_in():
    """`gather` orders its query by `(occurred_at, event_id)` and `by_thread` sorts by the same
    total key. Neither half is cosmetic: a stable sort on `at` alone preserves whatever order the
    scan handed it, and this module's docstring promises that "the same mailbox re-swept tomorrow
    produces the same seven answers".

    A tie is not exotic — a send and its own delivery record share a second — and the escalation
    reading resolves the INCUMBENT as "the first internal voice on this thread", so a tie decided
    by scan order decides who can never accept an escalation."""
    at = _ago(2)
    customer = _msg("t1", at, "a@big.co", head="put me through to your manager")
    owner = _msg("t1", at, US, internal=True, head="looking into it")
    forward = _desk(messages=(customer, owner)).by_thread()["t1"]
    reverse = _desk(messages=(owner, customer)).by_thread()["t1"]
    assert [m.event_id for m in forward] == [m.event_id for m in reverse]
    assert [m.event_id for m in forward] == sorted(m.event_id for m in (customer, owner))


# ── the intent lane ──────────────────────────────────────────────────────────────────────────

def test_two_phrasings_of_one_question_land_on_one_intent():
    """"How do I export this" and "where is the download button" are one gap in two phrasings, and
    counting by ticket splits the evidence exactly where it needs to be joined."""
    assert classify_intent("How do I export this to CSV?") == "export_download"
    assert classify_intent("where do I find the download button") == "export_download"


def test_an_unrecognised_message_is_not_a_bucket():
    """"Unclassified" as a group would join a password reset to an invoice query because neither
    matched — the fragmentation failure running in reverse, and worse: it manufactures a repeat
    contact out of two unrelated messages."""
    assert classify_intent("thanks, speak soon") is None
    assert classify_intent("") is None


def test_a_second_contact_about_the_same_thing_that_we_answered_is_a_repeat():
    desk = _desk(messages=(_msg("t1", _ago(20), "u@big.co", head="how do I export this"),
                           _msg("t2", _ago(3), "u@big.co", head="where is the download button")),
                 person_node={"u@big.co": "n_u"}, node_name={"n_u": "A User"},
                 thread_node={"t1": "n_t1", "t2": "n_t2"},
                 thread_facts={"n_t1": {"thread.ball_in_court": "them"},
                               "n_t2": {"thread.ball_in_court": "us"}})
    found = read_repeat_contacts(desk)
    assert [f.anchor for f in found] == [ANCHOR_CONTACT_INTENT]
    assert found[0].inputs["ordinal"] == 2
    # The ordinal is a FLOOR, never an exact count — an unrecognised phrasing splits the group and
    # the situation quietly does not fire. The payload says so rather than presenting "2nd
    # contact" as a fact.
    assert "floor" in found[0].inputs["ordinal_is"]


def test_a_repeat_whose_earlier_contact_was_never_answered_is_left_to_unanswered_mail():
    """Repeat contact is the exact OPPOSITE of unanswered mail: every one of these contacts was
    answered, that is what makes it interesting, and it is why the situation is invisible on every
    dashboard a support team already owns. A group whose prior contact is still owed a reply is
    not this finding."""
    desk = _desk(messages=(_msg("t1", _ago(20), "u@big.co", head="how do I export this"),
                           _msg("t2", _ago(3), "u@big.co", head="how do I export this")),
                 person_node={"u@big.co": "n_u"},
                 thread_node={"t1": "n_t1", "t2": "n_t2"},
                 thread_facts={"n_t1": {"thread.ball_in_court": "us"},
                               "n_t2": {"thread.ball_in_court": "us"}})
    assert read_repeat_contacts(desk) == []


def test_one_chatty_account_is_a_repeat_contact_and_not_a_content_gap():
    """Three asks from one company says that company is struggling. The content gap needs
    independent accounts, or the ranking of gaps is just a ranking of loud customers."""
    msgs, people, facts, nodes = [], {}, {}, {}
    for n in range(3):
        who = f"p{n}@big.co"
        msgs.append(_msg(f"t{n}", _ago(5 + n), who, head="how do I export this"))
        people[who] = f"n_p{n}"
        nodes[f"t{n}"] = f"n_t{n}"
        facts[f"n_t{n}"] = {"thread.ball_in_court": "them"}
    one_account = _desk(messages=tuple(msgs), person_node=people, thread_node=nodes,
                        thread_facts=facts,
                        company_of={f"n_p{n}": "n_bigco" for n in range(3)})
    assert read_knowledge_gaps(one_account) == []


def test_three_askers_at_two_accounts_all_answered_is_a_content_gap():
    msgs, people, facts, nodes, companies = [], {}, {}, {}, {}
    for n in range(3):
        who = f"p{n}@co{n // 2}.com"
        msgs.append(_msg(f"t{n}", _ago(5 + n), who, head="how do I export this to csv"))
        msgs.append(_msg(f"t{n}", _ago(4 + n), US, internal=True,
                         head="open settings, choose export, then download"))
        people[who] = f"n_p{n}"
        companies[f"n_p{n}"] = f"n_co{n // 2}"
        nodes[f"t{n}"] = f"n_t{n}"
        facts[f"n_t{n}"] = {"thread.ball_in_court": "them"}
    desk = _desk(messages=tuple(msgs), person_node=people, thread_node=nodes,
                 thread_facts=facts, company_of=companies)
    found = read_knowledge_gaps(desk)
    assert [f.anchor for f in found] == [ANCHOR_TOPIC]
    facts_out = dict((k, v) for k, v, _ in found[0].facts)
    assert facts_out["knowledge.distinct_askers"] == 3
    assert facts_out["knowledge.distinct_accounts"] == 2
    # The SURROGATE, and it must never be mistaken for the corpus's real discriminator.
    assert facts_out["knowledge.answer_reuse_bp"] > 0
    assert "knowledge.published_answer_seen" not in facts_out


def test_answer_reuse_is_a_surrogate_and_says_which_way_it_reads():
    """HIGH means a settled answer exists and we retype it — publish it. LOW means every reply is
    improvised, so the answer does not exist yet. It measures OUR answers, not the customer's
    retrieval experience, which is a related question and not the same one."""
    settled = ["open settings then choose export then download the file"] * 3
    improvised = ["open settings then choose export then download the file",
                  "I have asked the platform team to pull this for you manually"]
    assert answer_reuse_bp(settled) == 10000
    assert answer_reuse_bp(improvised) < 3000
    assert answer_reuse_bp(["only one reply"]) == 0     # nothing to compare: not "no reuse"


# ── reading 6 · mailbox load ─────────────────────────────────────────────────────────────────

def _load_desk(loops, *, threads=("t1",)) -> Desk:
    return _desk(loops=tuple(loops), mailboxes={"c1": "founder@acme.io"},
                 thread_conn={t: "c1" for t in threads},
                 thread_node={t: f"n_{t}" for t in threads},
                 thread_facts={f"n_{t}": {"thread.ball_in_court": "us"} for t in threads})


def test_a_pile_that_is_shrinking_while_getting_older_still_fires():
    """The anti-pattern the corpus file is actually about. A shrinking queue of steadily older
    items reads as improvement under any count-based signal and is the precise opposite of it —
    agents take the quick, well-written, easily-closed work, the count falls, and the customers
    who have waited longest keep waiting."""
    old = [_loop(f"l{n}", "t1", days_open=40) for n in range(3)]
    closed = [_loop(f"c{n}", "t1", days_open=60, status="closed", closed=_ago(1))
              for n in range(9)]
    found = read_mailbox_load(_load_desk(old + closed))
    assert [f.anchor for f in found] == [ANCHOR_MAILBOX]
    assert "shrinking_while_getting_older" in found[0].inputs["rules_fired"]


def test_the_load_reading_reports_the_distribution_and_never_the_average():
    """The finding is in the tail and a mean is how the failing segment stays hidden. The oldest
    open item is additionally the one number that cannot be gamed by working the queue badly."""
    found = read_mailbox_load(_load_desk(
        [_loop(f"l{n}", "t1", days_open=40) for n in range(3)]))
    fields = {k for k, _, _ in found[0].facts}
    assert {"mailbox.backlog_oldest_days", "mailbox.backlog_age_p50_days",
            "mailbox.backlog_age_p90_days", "mailbox.backlog_over_14d"} <= fields
    assert not any("mean" in f or "average" in f for f in fields)


def test_the_ratios_are_precomputed_because_layer_4_cannot_divide_two_facts():
    """The predicate grammar compares a path to a LITERAL and has no fact-to-fact form
    (`_eval_condition` in `reason/engine.py`), so a rule cannot express arrivals-over-closures. If
    Layer 2 does not materialise the ratio, no authored rule can ever ask the question."""
    found = read_mailbox_load(_load_desk(
        [_loop(f"l{n}", "t1", days_open=40) for n in range(3)]))
    fields = {k for k, _, _ in found[0].facts}
    assert {"mailbox.flow_ratio", "mailbox.arrival_vs_baseline",
            "mailbox.backlog_delta"} <= fields


def test_a_healthy_mailbox_mints_nothing():
    assert read_mailbox_load(_load_desk([_loop("l1", "t1", days_open=1)])) == []


# ── reading 7 · workaround ───────────────────────────────────────────────────────────────────

def test_a_customer_left_on_a_workaround_in_silence_opens_a_situation():
    desk = _desk(messages=(_msg("t1", _ago(40), "u@big.co", head="the sync keeps failing"),
                           _msg("t1", _ago(39), US, internal=True, to=("u@big.co",),
                                head="as a workaround, re-run it manually every morning "
                                     "until we fix the scheduler"),),
                 person_node={"u@big.co": "n_u"}, node_name={"n_u": "A User"},
                 thread_node={"t1": "n_t1"},
                 thread_facts={"n_t1": {"thread.ball_in_court": "them"}})
    found = read_workarounds(desk)
    assert [f.anchor for f in found] == [ANCHOR_WORKAROUND]
    facts = dict((k, v) for k, v, _ in found[0].facts)
    # The corpus's central demand: a one-time configuration change and a manual step performed
    # every morning are recorded identically today and are not remotely the same debt.
    assert facts["workaround.cost"] == "recurring_manual"
    assert found[0].inputs["fix_evidence"] == "none"


def test_a_finding_carries_the_words_that_caused_it_not_just_the_lexicon_hit():
    """A finding whose evidence is "the lexicon fired" cannot be checked by anybody, and the whole
    message head would put three paragraphs of unrelated mail where a reader is looking for the
    sentence. The text is already PII-masked by `capture/preprocess`, the same material every
    other `evidence.text` in the graph holds."""
    from genios_engine.context.support_situations import clause_around
    head = ("Hi. As a workaround, re-run the export manually every morning. "
            "We will fix it properly soon.")
    assert clause_around(head, "as a workaround") == (
        "As a workaround, re-run the export manually every morning.")

    desk = _desk(messages=(_msg("t1", _ago(3), "a@big.co",
                                head="This is not good enough. I want your manager. Please."),),
                 person_node={"a@big.co": "n_a"})
    facts = dict((k, v) for k, v, _ in read_escalations(desk)[0].facts)
    assert facts["escalation.ask_text"] == "I want your manager."


def test_an_ambiguous_workaround_leaves_the_cost_absent_rather_than_guessing():
    """An absent value must read as "we could not tell", never as "one-off" — which is the exact
    distinction the corpus says is recorded identically today."""
    assert workaround_cost("as a workaround, try the other button") is None
    assert workaround_cost("a one-off change to your config") == "one_time"


def test_a_fix_announced_after_the_workaround_closes_it():
    """The closing edge, wired now so the day a fix email lands the situation closes itself. On an
    email-only tenant it fires only if somebody happens to write — which is precisely the
    behaviour the situation exists to prompt."""
    desk = _desk(messages=(_msg("t1", _ago(40), US, internal=True, to=("u@big.co",),
                                head="in the meantime please re-run it by hand"),
                           _msg("t1", _ago(2), US, internal=True, to=("u@big.co",),
                                head="good news, the scheduler is now fixed")),
                 person_node={"u@big.co": "n_u"}, thread_node={"t1": "n_t1"},
                 thread_facts={"n_t1": {"thread.ball_in_court": "them"}})
    assert read_workarounds(desk) == []


def test_a_workaround_given_this_week_is_still_live_support_not_debt():
    desk = _desk(messages=(_msg("t1", _ago(2), US, internal=True, to=("u@big.co",),
                                head="as a workaround, refresh the page"),),
                 person_node={"u@big.co": "n_u"}, thread_node={"t1": "n_t1"},
                 thread_facts={"n_t1": {"thread.ball_in_court": "them"}})
    assert read_workarounds(desk) == []
    assert QUIET_DAYS == 14


# ── the honesty properties, across all seven ─────────────────────────────────────────────────

def _every_finding() -> list:
    """One firing example of each reading, so the properties below are asserted on all seven
    rather than on whichever one a future edit happens to keep."""
    out = []
    out += read_first_response(_desk(
        messages=(_msg("t1", _ago(6), "c@big.co", head="help"),),
        thread_node={"t1": "n_t1"}))
    out += read_backlog_items(_desk(
        loops=(_loop("l1", "t1", days_open=30),), thread_node={"t1": "n_t1"},
        thread_facts={"n_t1": {"thread.ball_in_court": "us"}}))
    out += read_escalations(_desk(
        messages=(_msg("t1", _ago(3), "a@big.co", head="I want your manager"),),
        person_node={"a@big.co": "n_a"}))
    out += read_repeat_contacts(_desk(
        messages=(_msg("t1", _ago(20), "u@big.co", head="how do I export this"),
                  _msg("t2", _ago(3), "u@big.co", head="where is the download button")),
        person_node={"u@big.co": "n_u"}, thread_node={"t1": "n_t1", "t2": "n_t2"},
        thread_facts={"n_t1": {"thread.ball_in_court": "them"},
                      "n_t2": {"thread.ball_in_court": "us"}}))
    msgs, people, facts, nodes, companies = [], {}, {}, {}, {}
    for n in range(3):
        who = f"p{n}@co{n // 2}.com"
        msgs.append(_msg(f"k{n}", _ago(5 + n), who, head="how do I export this to csv"))
        people[who], companies[f"n_p{n}"] = f"n_p{n}", f"n_co{n // 2}"
        nodes[f"k{n}"], facts[f"n_k{n}"] = f"n_k{n}", {"thread.ball_in_court": "them"}
    out += read_knowledge_gaps(_desk(messages=tuple(msgs), person_node=people,
                                     thread_node=nodes, thread_facts=facts,
                                     company_of=companies))
    out += read_mailbox_load(_load_desk([_loop(f"l{n}", "t1", days_open=40) for n in range(3)]))
    out += read_workarounds(_desk(
        messages=(_msg("t1", _ago(40), US, internal=True, to=("u@big.co",),
                       head="as a workaround, re-run it manually every morning"),),
        person_node={"u@big.co": "n_u"}, thread_node={"t1": "n_t1"},
        thread_facts={"n_t1": {"thread.ball_in_court": "them"}}))
    return out


def test_every_reading_produced_at_least_one_finding_for_the_honesty_checks():
    """Guard the oracle below: these properties mean nothing if a reading silently stopped
    firing and its example vanished from the list."""
    assert {f.anchor for f in _every_finding()} == {a for a, _ in READINGS}


def test_no_reading_asserts_that_a_ticket_a_queue_or_an_sla_object_exists():
    """The rule that governs the whole module. This tenant has no helpdesk, so a fact path named
    `ticket.status` or `sla.target_first_response_at` would be a fabricated record wearing the
    corpus's vocabulary — and the corpus itself says that is worse than a gap, because it looks
    like coverage. The `ticket.*` / `sla.*` / `entitlement.*` families stay in
    `planned_substrate`, unwritten, which is what keeps the difference visible."""
    banned = ("ticket.", "sla.", "entitlement.", "csat.", "incident.")
    for f in _every_finding():
        for name, _, _ in f.facts:
            assert not name.startswith(banned), f"{f.anchor} writes {name}"


def test_every_situation_declares_what_it_cannot_see():
    """A `missing` list that empties out the moment the mechanical facts land is how 34 of one
    org's 73 situations came to report full coverage on the strength of knowing whose turn it
    was — and any acceptance gate reading "no actionable output when required context is unknown"
    then goes green on ignorance."""
    for f in _every_finding():
        assert len(f.missing) >= 3, f.anchor
        assert all(isinstance(m, str) and len(m) > 15 for m in f.missing), f.anchor


def test_coverage_is_capped_because_these_are_inferred_and_not_recorded():
    """Nothing here may report the completeness of a record. The cap is the ceiling on what can be
    inferred from mail at all; the registry's `expected_fields` still decides the number under
    it, so a reading missing its own inputs scores lower still.

    The unit is the int PERCENT `situations.SCORE_MAX` names, not basis points. When these were
    4000/2500 they read as legal percentages to nothing and as a saturating input to
    `situation_bso._bp`, which turned every capped reading into coverage_bp=10000 at Layer 3."""
    for f in _every_finding():
        assert 0 < f.coverage_cap_pct <= 40, f.anchor
        assert f.coverage_cap_pct <= SCORE_MAX, f.anchor


def test_every_situation_type_expects_at_least_one_field_nothing_writes():
    """The mechanism that keeps `missing` honest FOREVER rather than until the writers catch up.
    Each type's `expected_fields` names a receiver, a published answer, an owner or a fix state —
    things a helpdesk would supply and mail cannot — so coverage can never reach 100."""
    for anchor, _ in READINGS:
        for domain in domains_declaring(anchor):
            stype = spec_for(domain).type_for(anchor)
            expected = spec_for(domain).fields_for(stype)
            assert expected, f"{stype} registers no expectations, so coverage says nothing"
            pct, gaps = coverage_score(present_fields=set(expected), expected=expected)
            assert pct != COVERAGE_UNKNOWN
            # every field the module can actually write, per the readings above
            writable = {name for f in _every_finding() for name, _, _ in f.facts}
            assert set(expected) - writable, (
                f"{stype} expects only fields the engine writes — its `missing` will empty out")


# ── registry wiring ──────────────────────────────────────────────────────────────────────────

def test_each_reading_has_its_own_anchor_and_a_named_type():
    """`type_for` maps ONE anchor to ONE type, so two readings sharing an anchor could not both be
    named — and a missing entry falls to the generic `<domain>_<anchor>` default, which no
    situation file claims and the registry cannot resolve. That is the exact fault that kept
    `admin_person` and `fundraising_deal` dark, and it fails silently."""
    anchors = [a for a, _ in READINGS]
    assert len(anchors) == len(set(anchors)) == 7
    for anchor in anchors:
        claiming = domains_declaring(anchor)
        assert claiming, f"nothing declares the {anchor} anchor"
        for domain in claiming:
            stype = spec_for(domain).type_for(anchor)
            assert not stype.endswith(f"_{anchor}"), (
                f"{domain}/{anchor} fell to the generic default: {stype}")


def test_none_of_these_anchors_can_win_a_correlation():
    """`choose_anchors` returns only the strongest tier present, so a synthetic anchor reachable
    from correspondence would swallow every conversation that touched it into ONE situation.
    `thread` matters most: correlation is already thread-first, and a thread tier would re-anchor
    every live sales and general correlation onto its own thread."""
    from genios_engine.context.correlation import ANCHOR_PRIORITY
    tiers = {t for tier in ANCHOR_PRIORITY for t in (tier if isinstance(tier, (list, tuple, set))
                                                     else [tier])}
    for anchor, _ in READINGS:
        assert anchor not in tiers, f"{anchor} is correlatable and would swallow conversations"


def test_the_sync_path_refreshes_them():
    """A reading refreshed only by a separate schedule is a reading that is always stale, and
    seven authored situation types would be reachable in principle and empty in practice."""
    import inspect

    from genios_engine.context import runner
    assert "refresh_support_situations" in inspect.getsource(runner.process_pending)


def test_layer_2_still_names_no_domain_outside_the_registry():
    """The module must discover which domains want these readings by ASKING the registry, or
    adding a domain would mean editing Layer 2 — which is what the registry exists to prevent."""
    assert desk_domains() == tuple(sorted(set(desk_domains())))
    assert desk_domains(), "no domain declares any of the seven anchors"


# ── the corpus census ────────────────────────────────────────────────────────────────────────

def test_the_seven_types_are_substrate_and_no_longer_planned():
    """`vocabulary.yaml`'s own rule: a name moves out of `planned_substrate` in the same commit
    that ships the thing emitting it. Leaving a shipped type in the planned list makes the census
    a wish; validate.py errors on the mirror image, a pending binding for a type Layer 2 already
    emits."""
    from genios_engine.packs.compiler.authoring import default_authoring_root
    import yaml

    vocab = yaml.safe_load((default_authoring_root() / "_schema" / "vocabulary.yaml").read_text())
    shipped = {spec_for(d).type_for(a) for a, _ in READINGS for d in domains_declaring(a)}
    substrate = set(vocab["substrate"]["l2_situation_types"])
    planned = set(vocab["planned_substrate"]["l2_situation_types"])
    assert shipped <= substrate
    assert not (shipped & planned)


def test_every_fact_path_these_readings_write_is_in_the_census():
    """A fact the engine writes and the census does not list is a path an author cannot use: a
    pattern naming it is marked `needs_signal` and becomes dead authoring instead of a live rule.
    The reverse — listing one nothing writes — is what `planned_substrate` is for."""
    from genios_engine.packs.compiler.authoring import default_authoring_root
    import yaml

    vocab = yaml.safe_load((default_authoring_root() / "_schema" / "vocabulary.yaml").read_text())
    declared = set(vocab["substrate"]["fact_paths"])
    written = {name for f in _every_finding() for name, _, _ in f.facts}
    assert written <= declared, sorted(written - declared)
