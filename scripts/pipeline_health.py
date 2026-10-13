"""Every invariant that was green in the test suite and false in production, asserted on real data.

    GENIOS_TARGET_DATABASE_URL=... python scripts/pipeline_health.py --org org_... \
        [--json health.json] [--require-data]

⛔ WHY THIS SCRIPT EXISTS. On 2026-10-04 the hermetic suite reported **14,624 passed, 0 failed**
while production was carrying, simultaneously:

    4,076  LLM calls rejected outright (`temperature` deprecated for the model)
       19  calls truncated at max_tokens and reported as "unparseable JSON"
      160  emitted events with no `route` — extraction never ran on one of them
       85  parked attachments whose stored error was 400 characters of identifier and no reason
        9  cards the pipeline selected for rebuild and the claim refused, 0 of 9, silently
      255  messages dropped by a whitelist that could not know anybody on a cold graph

Not one test went red, because every test runs against a FAKE LLM and FAKE data. A fake client
never returns a 400, never hits `max_tokens`, never leaves a row half-written. The suite asserts
that the code does what the code says; it has never asserted that the product works.

This script is the other half. It runs READ-ONLY against a real database and fails on the shapes
that were actually true while the suite was green. Each check names what it measured, what it
expected, and what to do — a check whose failure does not tell you the next move is a check
somebody learns to ignore.

EXIT CODE 1 if any check fails, so it can be a deploy gate rather than a thing someone remembers.

THREE VERDICTS — PASS, FAIL, NO DATA (STEP-17 §3.4). A check whose population was empty judged
nothing, and says so instead of passing; NO DATA is counted apart and is not a failure, unless the run
asks for data (`--require-data`, exit 2 — the run a day after a deploy, when every lane should have
run). `--json PATH` keeps every verdict as a file, the record a deploy keeps.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from genios_engine.platform.self_identity import identity_for, names_us  # noqa: E402
from genios_engine.reason.bundle.budget import OWN_BUDGETS, usd_to_micro  # noqa: E402
from genios_engine.reason.bundle.sites import SITE_EXPERT                # noqa: E402
from scripts._db import add_database_argument, resolve_database_url   # noqa: E402
from scripts._gate import read_only_connection, sql                   # noqa: E402


#: The three verdicts. ⛔ STEP-17 §3.4 (`yc2_w27_s17` M40.C3.L-contract.V0.U01): measured on a tenant
#: with no data at all, 17 of these 19 checks printed PASS — six saying "not exercised" or "skipped"
#: in the same line — and `03` F24's ceiling check passed while its lane made no call. A pass over an
#: empty table is not a pass.
PASS, FAIL, NO_DATA = "PASS", "FAIL", "NO DATA"


@dataclass
class Check:
    """One measured invariant. `detail` rows are printed under a failure, never summarised away.

    ⛔ TWO QUESTIONS, TWO FIELDS. `ok` answers *"did it fail?"* and keeps the meaning every reader of
    it already relies on (the golden replays assert it); `no_data` answers *"did it judge anything?"*
    — a check whose population was empty sets it, and prints NO DATA, never PASS. A failure is never
    hidden as no data (`verdict`)."""

    name: str
    ok: bool
    measured: str
    expected: str
    fix: str
    detail: list[str] = field(default_factory=list)
    no_data: bool = False

    @property
    def verdict(self) -> str:
        if not self.ok:
            return FAIL
        return NO_DATA if self.no_data else PASS


def _scalar(conn, statement: str, **params) -> int:
    return int(conn.execute(sql(statement), params).scalar() or 0)


# ── the checks ──────────────────────────────────────────────────────────────────────────────────

def check_every_emitted_event_is_routed(conn, org: str) -> Check:
    """⛔ 160 of 361 emitted events carried `route IS NULL` and extraction had run on NONE of them.

    A parked row is written with `route` NULL — correct, it has not been admitted. The re-admission
    paths then flipped `outcome` to 'emitted' and touched neither `route` nor `triage_lane`, and
    `route` is exactly what the extraction lane selects on. The mail was in the database, counted
    as emitted, carrying its payload, and contributing nothing.
    """
    n = _scalar(conn, "select count(*) from source_events "
                      "where org_id = :o and outcome = 'emitted' and route is null", o=org)
    emitted = _scalar(conn, "select count(*) from source_events "
                            "where org_id = :o and outcome = 'emitted'", o=org)
    return Check(
        name="every emitted event is routed",
        ok=n == 0, no_data=emitted == 0,
        measured=f"{n} emitted events with route IS NULL",
        expected="0 — an emitted event that is routed nowhere is never read",
        fix="UPDATE them to route='needs_extraction'; the writers are capture/parked/drain.py "
            "and capture/parked/recapture.py",
    )


#: ⛔ `03` F24 (`yc2_w27_s17` M40.C3.L-logic.V0.U02): a lane that called in this many days and not in
#: the window is SILENT, and the two LLM checks cannot vouch for it — NO DATA, named. Longer ago than
#: this, a lane is retired rather than silent.
SILENT_LANE_LOOKBACK_DAYS = 7


def _silent_lanes(conn, org: str, *, hours: int) -> list:
    """Lanes (`llm_costs.purpose`) that called in the lookback and not in the window, with the time
    of each one's last call."""
    return conn.execute(sql(
        "select purpose, max(created_at) as last_call from llm_costs "
        " where org_id = :o and created_at > now() - make_interval(days => :d) "
        " group by 1 having max(created_at) <= now() - make_interval(hours => :h) "
        " order by 1"), {"o": org, "d": SILENT_LANE_LOOKBACK_DAYS, "h": hours}).fetchall()


def _silence(silent, hours: int) -> tuple[str, list[str]]:
    """The measured-line suffix and the detail lines that name each silent lane."""
    if not silent:
        return "", []
    return ("; no call in " + f"{hours}h from: "
            + ", ".join(f"{r.purpose} (last {r.last_call:%Y-%m-%d})" for r in silent),
            [f"{r.purpose}: no call in {hours}h — its last was {r.last_call:%Y-%m-%d %H:%M} UTC; "
             "nothing here says it is healthy" for r in silent])


def check_llm_failure_rate(conn, org: str, *, hours: int, ceiling_bp: int) -> Check:
    """⛔ `l4_bundle` ran at 8 failures in 12 calls and nothing anywhere said so.

    Per PURPOSE, not overall: one lane failing totally is invisible in a global rate, and
    `l4_bundle` — the deep reasoning bundle — was at 67% while the fleet average looked fine.
    """
    rows = conn.execute(sql(
        "select purpose, count(*) n, count(*) filter (where not success) bad "
        "  from llm_costs "
        " where org_id = :o and created_at > now() - make_interval(hours => :h) "
        " group by 1 having count(*) >= 5 order by 2 desc"), {"o": org, "h": hours}).fetchall()
    bad = [(r.purpose, r.bad, r.n) for r in rows if r.n and (r.bad * 10000 // r.n) > ceiling_bp]
    silent = _silent_lanes(conn, org, hours=hours)
    suffix, silent_detail = _silence(silent, hours)
    return Check(
        name="no LLM lane is mostly failing",
        ok=not bad, no_data=not rows or bool(silent),
        measured=(", ".join(f"{p}: {b}/{n}" for p, b, n in bad) if bad
                  else f"{len(rows)} lane(s) under {ceiling_bp / 100:g}% in {hours}h") + suffix,
        expected=f"every purpose under {ceiling_bp / 100:g}% failures",
        fix="read llm_costs.error for that purpose — a 400 means the request shape is wrong for "
            "the model, a truncation means the budget is too small for the question",
        detail=[f"{p}: {b} of {n} failed" for p, b, n in bad] + silent_detail,
    )


def check_no_silent_truncation(conn, org: str, *, hours: int) -> Check:
    """⛔ Every failure of `l1_extract` and `l1_relevance` sat at EXACTLY its ceiling — 8192 and
    1024 — while the stored error said "unparseable JSON" and sent every reader to the prompt.

    A lane whose failures cluster on one output size is not writing bad JSON; it is running out
    of budget, and `LLMResult.truncated` now says so. This asserts the shape stays visible.

    ⛔ WHETHER OR NOT IT PARSED (`yc2_w27_s18` M50.C4.L-interface.V1.U11, s5t-F6). A cut the lenient
    parser closed was a SUCCESS with no error — on every R-site, in the drafter, in `l5_render` — so a
    lane whose every call was cut could pass here. A cut call now names itself in `error`
    (`truncated: …`, `context/llm/client.TRUNCATED`), and it is counted whatever `success` says.
    """
    rows = conn.execute(sql(
        "select purpose, min(output_tokens) lo, max(output_tokens) hi, count(*) n "
        "  from llm_costs "
        " where org_id = :o and (not success or error like 'truncated:%') "
        "   and created_at > now() - make_interval(hours => :h) "
        " group by 1 having count(*) >= 3"), {"o": org, "h": hours}).fetchall()
    pinned = [(r.purpose, r.lo, r.n) for r in rows if r.lo == r.hi and r.lo > 0]
    calls = _scalar(conn, "select count(*) from llm_costs where org_id = :o "
                          "and created_at > now() - make_interval(hours => :h)", o=org, h=hours)
    silent = _silent_lanes(conn, org, hours=hours)
    suffix, silent_detail = _silence(silent, hours)
    return Check(
        name="no lane is failing at a fixed token ceiling",
        ok=not pinned, no_data=calls == 0 or bool(silent),
        measured=(", ".join(f"{p}: {n} failures all at {lo} tokens" for p, lo, n in pinned)
                  if pinned else "no failure cluster pinned to one output size") + suffix,
        expected="failures spread across output sizes — a single size means truncation",
        fix="raise that lane's max_tokens, or ask it a smaller question; the error text will "
            "name the ceiling since LLMClient reads stop_reason",
        detail=[f"{p}: {n} failures, every one at {lo} output tokens" for p, lo, n in pinned]
               + silent_detail,
    )


def check_parked_errors_are_readable(conn, org: str) -> Check:
    """⛔ 48 of 50 stored attachment failures were 400 characters of Gmail attachment id and no
    reason at all. The retry ladder worked perfectly and reported nothing anybody could act on.
    """
    total = _scalar(conn, "select count(*) from parked_events "
                          "where org_id = :o and refetch_last_error is not null", o=org)
    mute = _scalar(conn, "select count(*) from parked_events "
                         "where org_id = :o and refetch_last_error is not null "
                         "and refetch_last_error not like '%: %'", o=org)
    return Check(
        name="a stored failure says why",
        ok=mute == 0, no_data=total == 0,
        measured=f"{mute} of {total} stored refetch errors carry no reason",
        expected="0 — an error nobody can read is an error nobody can fix",
        fix="capture/parked/refetch._readable_failure keeps the reason inside the 400-char cap",
    )


def check_the_known_sender_set_is_not_empty(conn, org: str) -> Check:
    """⛔ On a wiped tenant this set was EMPTY, so `whitelist()` protected nobody and the N-codes
    ran at full strength over the whole history. Twenty senders had some mail kept and some
    dropped — the same person, decided by which page of the backfill they landed on.
    """
    outbound = _scalar(conn, "select count(*) from source_events e "
                             "where e.org_id = :o and e.recipients is not null "
                             "and cardinality(e.recipients) > 0", o=org)
    if not outbound:
        return Check(name="the tenant knows who it has written to", ok=True, no_data=True,
                     measured="no outbound mail captured yet",
                     expected="skipped — nothing has been sent, so nobody can be known",
                     fix="")
    # W-01's own statement shape (`api/routes.KNOWN_FROM_SENT_SQL`), on the same one answer to who
    # "us" is (`platform/self_identity`, STEP-04) — so this check and W-01 cannot disagree. Not
    # imported from `api/routes`: that module builds a graph store from settings at import.
    ours = sorted(identity_for(conn, org).addresses)
    known = _scalar(conn,
                    "select count(distinct lower(r)) from source_events e, unnest(e.recipients) r "
                    " where e.org_id = :o and e.recipients is not null "
                    "   and lower(e.actor ->> 'email') = any(:ours) "
                    "   and nullif(trim(r), '') is not null", o=org, ours=ours)
    return Check(
        name="the tenant knows who it has written to",
        ok=known > 0,
        measured=f"{known} known counterparties from {outbound} outbound events",
        expected=">0 — an empty set turns W-01 off and hands the N-codes the whole mailbox",
        fix=("check `platform/self_identity.identity_for` holds the mailbox owner's address — a "
             "seat, `orgs.email`, a connected account or a declaration "
             "(`scripts/declare_self_identity.py`); the whitelist reads exactly that"),
    )


def check_a_selected_signal_can_be_carded(conn, org: str) -> Check:
    """⛔ Nine signals the pipeline selected for rebuild were refused by `claim_build`, 0 of 9,
    with no log line. The selection excluded expired cards; the claim treated an expired card as
    a live one. Three places answering one question, and two of them disagreed.
    """
    stuck = _scalar(conn,
                    "select count(*) from signals s "
                    "  join cards k on k.signal_id = s.signal_id and k.org_id = s.org_id "
                    " where s.org_id = :o and s.status = 'open' and k.state = 'expired' "
                    "   and k.resolved_at is null "
                    "   and k.created_at < now() - interval '2 hours'", o=org)
    lapsed = _scalar(conn,
                     "select count(*) from signals s "
                     "  join cards k on k.signal_id = s.signal_id and k.org_id = s.org_id "
                     " where s.org_id = :o and s.status = 'open' and k.state = 'expired' "
                     "   and k.resolved_at is null", o=org)
    return Check(
        name="an open signal with a lapsed card gets rebuilt",
        ok=stuck == 0, no_data=lapsed == 0,
        measured=f"{stuck} open signals whose expired card has not been rebuilt in 2h",
        expected="0 — the pipeline selects these, so the claim and the write must accept them",
        fix="CardStore._REPLACEABLE must admit an expired, unresolved card; "
            "deliver/pipeline._open_signals_without_cards already does",
    )


def check_cards_reach_the_app(conn, org: str) -> Check:
    """⛔ The owner saw 3 cards where the system held 16: the rest carried no `app` surface, and
    nothing in the product said they existed.
    """
    live = _scalar(conn, "select count(*) from cards where org_id = :o "
                         "and state in ('queued','surfaced')", o=org)
    on_app = _scalar(conn, "select count(*) from cards where org_id = :o "
                           "and state in ('queued','surfaced') and 'app' = any(surfaces)", o=org)
    return Check(
        name="live cards reach a surface a person reads",
        ok=live == 0 or on_app > 0, no_data=live == 0,
        measured=f"{on_app} of {live} live cards carry the app surface",
        expected=">0 whenever any card is live — a card on no surface was not delivered",
        fix="deliver/card_builder._surfaces decides this; a card with no quotable finding keeps "
            "only ask/api, which in practice means nobody sees it",
    )


def check_the_change_gate_skips_what_did_not_change(conn, org: str) -> Check:
    """⛔ STEP-02 (`yc2_w27_s02/M20.C6`). Every sweep used to re-decide every subject: on the golden
    runner one more sweep with nothing new cost F13 2 model calls and F29 12, and production's decider
    and R-1 ran 760-1,890 calls a day. The change gate skips a subject whose decision inputs did not
    move, and records each subject it looks at in `reasoning_fingerprints`. Its two failure modes:

      * NOT RUNNING — sweeps ran in the window and the gate recorded nothing;
      * SAVING NOTHING — four or more sweeps ran and not one subject was skipped. That is what a
        fingerprint carrying an input that moves every sweep looks like (STEP-02 §7, risk 2).
    """
    sweeps = _scalar(conn, "select count(distinct sweep_id) from pipeline_counters "
                           "where org_id = :o and sweep_at > now() - interval '6 hours'", o=org)
    name = "the change gate skips what did not change"
    if not sweeps:
        return Check(name=name, ok=True, no_data=True, measured="no sweep in the last 6 hours",
                     expected="skipped — nothing to judge", fix="")
    looked = _scalar(conn, "select count(*) from reasoning_fingerprints where org_id = :o "
                           "and last_checked_at > now() - interval '6 hours'", o=org)
    if not looked:
        return Check(name=name, ok=False,
                     measured=f"{sweeps} sweeps in 6 h and the gate recorded nothing",
                     expected="every decided or skipped subject has a reasoning_fingerprints row",
                     fix="the gate fails open — check the sweep log for 'change gate unavailable' "
                         "or 'could not record'; reason/domain_shadow._CompiledGate, "
                         "reason/runner._LaneGate")
    skipping = _scalar(conn, "select count(*) from reasoning_fingerprints where org_id = :o "
                             "and last_checked_at > now() - interval '6 hours' and skips > 0",
                       o=org)
    ok = skipping > 0 or sweeps < 4
    return Check(
        name=name, ok=ok,
        measured=f"{skipping} of {looked} subjects looked at in 6 h were skipped, over {sweeps} "
                 "sweeps",
        expected=">0 once 4 sweeps have run — a steady tenant has subjects nothing happened to",
        fix="an input of reason/fingerprint.material_fingerprint moves every sweep: run the golden "
            "probe (tests/replays/test_an_unchanged_sweep_costs_nothing.py) and diff two "
            "fingerprints of one subject")


def check_nothing_was_deleted_at_the_gate(conn, org: str) -> Check:
    """⛔ STEP-03 (`yc2_w27_s03/M21.C6`). Before it, 258 of the design partner's 395 mails were deleted
    at the first gate with their content gone — every noise rule and the AI filter's confident junk
    was a DROP. The gate now ARCHIVES what it calls noise (kept, read by no model) and the only drop
    left is S0's scope exclusion, `out_of_scope`. So the promise is a number: objects captured in
    the last 24 hours with outcome `dropped` and no scope exclusion in their trace — 0.

    The window starts no earlier than the tenant's first archived mail, so on the deploy day the
    mail the OLD gate dropped that morning is history, not this gate's deletion. A tenant that has
    never archived anything and still drops is running the gate from before STEP-03.
    """
    name = "nothing captured was deleted at the gate"
    archiving_since = conn.execute(sql(
        "select min(captured_at) from source_events where org_id = :o and outcome = 'archived'"),
        {"o": org}).scalar()
    rows = conn.execute(sql(
        "select coalesce(et.reason_code, 'no trace') as code, count(*) as n "
        "  from source_events se "
        "  left join event_trace et on et.org_id = se.org_id and et.event_id = se.event_id "
        "       and et.action = 'drop' "
        " where se.org_id = :o and se.outcome = 'dropped' "
        "   and se.captured_at > now() - interval '24 hours' "
        "   and (cast(:since as timestamptz) is null or se.captured_at >= cast(:since as timestamptz)) "
        "   and not exists (select 1 from event_trace s0 where s0.org_id = se.org_id "
        "                   and s0.event_id = se.event_id and s0.reason_code = 'out_of_scope') "
        " group by 1 order by 2 desc, 1"), {"o": org, "since": archiving_since}).fetchall()
    deleted = sum(int(r.n) for r in rows)
    window = ("the last 24 h" if archiving_since is None
              else "the last 24 h, since this tenant's first archived mail")
    if archiving_since is None:
        fix = ("nothing has ever been archived here, and mail is still dropped: the gate is the one "
               "from before STEP-03 — is STEP-03 deployed, with migration 0192 applied? Then read "
               "the codes below against `capture/gate/gate._never_delete`")
    else:
        fix = ("the archiving gate runs and something still drops: walk one event with "
               "`capture/journey.event_journey` — every drop verdict should reach "
               "`capture/gate/gate._never_delete`, and only S0 `out_of_scope` may stay a drop")
    captured = _scalar(conn, "select count(*) from source_events where org_id = :o "
                             "and captured_at > now() - interval '24 hours'", o=org)
    return Check(
        name=name, ok=deleted == 0, no_data=captured == 0,
        measured=f"{deleted} object(s) captured in {window} were deleted at the gate",
        expected="0 — the gate archives what it calls noise; only S0's scope exclusion drops",
        fix=fix,
        detail=[f"{r.code}: {int(r.n)} deleted" for r in rows])


#: `CardStore.OPEN_STATES` — a card in any of these is still in front of somebody.
_OPEN_CARD_STATES = ("queued", "surfaced", "snoozed", "claimed", "delivered")
#: The separator `context/graph_store.thread_label` writes between who and what.
_DASH = " — "


def check_we_are_never_the_subject(conn, org: str) -> Check:
    """⛔ STEP-04 (`yc2_w27_s04/M22.C6`). Production carried *"Send Mr Rohit Swerashi your traction
    metrics"* and threads frozen as *"Mr Rohit Swerashi — <the pitch>"*: the founder as the subject
    of his own cards and the name of his own threads. STEP-04 stops new ones (one answer to who is
    us, `platform/self_identity`) and `scripts/repair_self_identity.py` removes the old. So the
    promise is two numbers, by the same test the card builder refuses by (`names_us`): open cards
    whose subject is one of us — 0; threads named after one of us — 0.
    """
    name = "we are never a card's subject or a thread's name"
    us = identity_for(conn, org)
    row = conn.execute(sql("select name, first_name, last_name, company from orgs where id = :o"),
                       {"o": org}).first()
    names = () if row is None else (
        row.name, row.company,
        f"{row.first_name} {row.last_name}" if row.first_name and row.last_name else None)
    open_cards = conn.execute(sql(
        "select card_id, business_subject from cards where org_id = :o and state = any(:open) "
        "   and business_subject is not null order by card_id"),
        {"o": org, "open": list(_OPEN_CARD_STATES)}).fetchall()
    named_threads = conn.execute(sql(
        "select node_id, display_name from graph_nodes where org_id = :o and valid_to is null "
        "   and node_type = 'thread' and display_name like '%' || :dash || '%' order by node_id"),
        {"o": org, "dash": _DASH}).fetchall()
    cards = [(r.card_id, r.business_subject) for r in open_cards
             if names_us(r.business_subject, us, names)]
    threads = [(r.node_id, r.display_name) for r in named_threads
               if names_us(str(r.display_name).partition(_DASH)[0], us, names)]
    return Check(
        name=name, ok=not cards and not threads, no_data=not open_cards and not named_threads,
        measured=f"{len(cards)} open card(s) about us, {len(threads)} thread(s) named after us",
        expected="0 and 0 — after STEP-04's repair",
        fix=("before the repair this is the old defect: run `scripts/repair_self_identity.py` dry, "
             "let Rohit read the list (06 D14), then `--apply`. After it, a card here was built by a "
             "path that did not ask `platform/self_identity` — read its signal's subject node"),
        detail=[f"card {c}: {s!r}" for c, s in cards[:5]]
               + [f"thread {t}: {d!r}" for t, d in threads[:5]])


def check_every_kept_event_entered_memory(conn, org: str) -> Check:
    """⛔ STEP-05 (`yc2_w27_s05/M23.C6`). Memory held ~27 of the design partner's 395 mails and 2 of
    its 34 meetings: Layer 2 took only events with a live signal, and nothing said so. STEP-05 gives
    every kept event a road into memory and every recovery a re-read. The promise is the receipt's —
    kept events a day old with no settled L2 run, 0 (`platform/receipts` "every kept event has
    entered memory", the same population, held equal by the test) — split here by what holds each
    one, so a failure names its lever; and every calendar event is a meeting. The re-read ladder's
    backlog is measured either way: mail waiting a pass or two is normal, a number that only grows
    is not.
    """
    from genios_engine.capture.parked.drain import NEEDS_REEXTRACTION
    from genios_engine.context.memory_lanes import KEPT_OUTCOMES, SCREEN_SOURCE

    name = "every kept event entered memory, every calendar event is a meeting"
    reread = sorted(NEEDS_REEXTRACTION)
    rows = conn.execute(sql(
        "select case "
        "  when r.status is not null then 'its L2 run is ' || r.status "
        "  when pe.status = 'pending' and pe.reason_code = any(:reread) "
        "       then 'waiting for its re-read' "
        "  when pe.status = 'dead_letter' and pe.reason_code = any(:reread) "
        "       then 'given up by the re-read ladder' "
        "  when se.outcome = 'emitted' and not exists ("
        "         select 1 from l1_extraction_results x where x.org_id = se.org_id "
        "            and x.event_id = se.event_id) "
        "       and not exists (select 1 from qualified_signals q where q.org_id = se.org_id "
        "            and q.event_id = se.event_id and q.state = 'active') "
        "       then 'never read, and not in the ladder' "
        "  else 'never taken by the drain' end as why, count(*) as n "
        "  from source_events se "
        "  left join l2_processing_runs r on r.org_id = se.org_id and r.event_id = se.event_id "
        "  left join parked_events pe on pe.event_id = se.event_id "
        " where se.org_id = :o and se.outcome = any(:kept) "
        "   and se.captured_at < now() - interval '1 day' "
        "   and not (se.source = :screen and not exists (select 1 from qualified_signals q "
        "            where q.org_id = se.org_id and q.event_id = se.event_id "
        "              and q.state = 'active')) "
        "   and (r.status is null or r.status <> 'done') "
        " group by 1 order by 2 desc, 1"),
        {"o": org, "kept": list(KEPT_OUTCOMES), "screen": SCREEN_SOURCE,
         "reread": reread}).fetchall()
    outside = sum(int(r.n) for r in rows)
    meetings = _scalar(
        conn,
        "select count(distinct se.source_object_id) from source_events se "
        " where se.org_id = :o and se.source = 'gcal' and se.object_type = 'calendar_event' "
        "   and se.outcome = 'emitted' and se.captured_at < now() - interval '1 day' "
        "   and not exists (select 1 from graph_nodes n where n.org_id = se.org_id "
        "                   and n.node_type = 'meeting' and n.valid_to is null "
        "                   and n.canonical_key = 'gcal:' || se.source_object_id)", o=org)
    waiting = _scalar(
        conn,
        "select count(*) from parked_events pe join source_events se "
        "    on se.org_id = pe.org_id and se.event_id = pe.event_id and se.outcome = 'emitted' "
        " where pe.org_id = :o and pe.status = 'pending' and pe.reason_code = any(:reread)",
        o=org, reread=reread)
    kept = _scalar(conn, "select count(*) from source_events where org_id = :o "
                         "and outcome = any(:kept) and captured_at < now() - interval '1 day'",
                   o=org, kept=list(KEPT_OUTCOMES))
    return Check(
        name=name, ok=outside == 0 and meetings == 0, no_data=kept == 0,
        measured=(f"{outside} kept event(s) a day old outside memory, {meetings} calendar "
                  f"event(s) with no meeting; {waiting} kept mail(s) waiting for their re-read"),
        expected="0 and 0 — every kept event enters memory within a day (STEP-05)",
        fix=("read the split: 'never taken by the drain' — the L2 drain is not running for this "
             "tenant, or `context/runner._pull` and `context/memory_lanes.lane_for` disagree; 'its "
             "L2 run is …' — read `l2_processing_runs.last_error`; 'waiting for its re-read' — the "
             "chain's re-read (`api/routes._reread_unread`) has not reached it: is the tenant's "
             "Layer 1 on, is it under the LLM cap?; 'given up' — `parked_events.refetch_last_error`; "
             "'never read, and not in the ladder' — Layer 1 is off, or the payload is gone; a "
             "missing meeting — walk the calendar event with `capture/journey.event_journey`"),
        detail=[f"{r.why}: {int(r.n)}" for r in rows]
               + ([f"calendar events with no meeting node: {meetings}"] if meetings else []))


def check_every_situation_and_card_says_how_it_ended(conn, org: str) -> Check:
    """⛔ STEP-06 (`yc2_w27_s06/M24.C4`). A silent loss looks exactly like "there was nothing there":
    nine of twelve places that expired a card wrote nothing, and 126 of the golden set's 227 active
    situations had no record of how they ended. Every situation now names one end
    (`reason/situation_end`) and every expiry its reason (`platform/card_lifecycle`). This check
    fails on the two things that are wrong whenever they are non-zero — a live situation nothing
    explains, a card created since STEP-06 that expired with no event (the receipt's own SQL) — and
    names, without failing, every live situation type with no open card, with the histogram of its
    ends: a type can be right to stay silent (`06` D25), and the histogram says which kind of silent.
    """
    from collections import Counter

    from genios_engine.platform.receipts import _EXPIRED_WITHOUT_A_REASON_SQL
    from genios_engine.reason.situation_end import CARDED, NO_CORPUS, NOT_LIVE, UNRECORDED
    from genios_engine.reason.situation_end import situation_ends

    name = "every situation and every card says how it ended"
    ends = situation_ends(conn, org)
    unrecorded = [e.situation_id for e in ends if e.end == UNRECORDED]
    silent_cards = _scalar(conn, _EXPIRED_WITHOUT_A_REASON_SQL() + " and c.org_id = :o", o=org)
    by_type: dict[str, Counter] = {}
    for e in ends:
        if e.end not in (NO_CORPUS, NOT_LIVE):
            by_type.setdefault(f"{e.domain}:{e.situation_type}", Counter())[e.end] += 1
    silent_types = {kind: counts for kind, counts in sorted(by_type.items())
                    if counts.get(CARDED, 0) == 0}
    any_card = _scalar(conn, "select count(*) from cards where org_id = :o", o=org)
    return Check(
        name=name, ok=not unrecorded and silent_cards == 0, no_data=not ends and any_card == 0,
        measured=(f"{len(unrecorded)} live situation(s) with no recorded end, {silent_cards} "
                  f"card(s) expired with no reason; {len(silent_types)} live situation type(s) "
                  "with no open card"),
        expected="0 and 0 — every situation and every expired card says how it ended (STEP-06)",
        fix=("an unrecorded situation — `scripts/situation_ends.py --org … --verbose` names it, and "
             "the compiled pass's log line (`outcome_write_failed`, `no_anchor`) says why nothing "
             "was noted; an expiry with no reason — something set a card `expired` outside "
             "`platform/card_lifecycle` (the guard `tests/platform/test_one_way_to_expire_a_card.py` "
             "should have refused it)"),
        detail=([f"unrecorded: {', '.join(unrecorded[:10])}"
                 + (f" (+{len(unrecorded) - 10} more)" if len(unrecorded) > 10 else "")]
                if unrecorded else [])
               + [f"no open card — {kind}: "
                  + ", ".join(f"{end} {n}" for end, n in sorted(counts.items()))
                  for kind, counts in silent_types.items()])


def check_the_company_brief_exists_and_is_current(conn, org: str) -> Check:
    """⛔ STEP-07 (`yc2_w27_s07/M25.C6`). Every judging and reading prompt carries the company brief —
    once the founder has accepted a line of it. Until then no prompt names the company, its goals, its
    people or a watchlist, the portal's and the intro agent's mail stays "unknown sender" at all four
    gate stages, and the engine judges the mailbox as a stranger would. So this fails while no line is
    accepted, and says what waits: the brief's version, the proposals the founder has not decided,
    the lines its budget left out, and when the weekly review last looked for what it is missing.
    """
    from genios_engine.platform.company_brief import brief_for, last_review

    name = "the company brief exists and is current"
    brief = brief_for(conn, org)
    pending = conn.execute(sql(
        "select line_id, section, text from company_brief_lines "
        " where org_id = :o and status = 'proposed' order by proposed_at, line_id"), {"o": org}
    ).mappings().all()
    review = last_review(conn, org)
    reviewed = (f"last weekly review {review['week']} ({review['outcome'] or 'unfinished'}, "
                f"{review['proposed']} proposed)" if review else "no weekly review yet")
    return Check(
        name=name, ok=bool(brief),
        measured=((f"version {brief.version}, {len(brief.lines)} accepted line(s), "
                   f"{len(brief.truncated)} left out by the budget" if brief
                   else "no accepted line — no prompt carries a brief")
                  + f"; {len(pending)} proposal(s) waiting; {reviewed}"),
        expected="at least one accepted line — every judging and reading prompt then carries it",
        fix=("draft it — `scripts/draft_company_brief.py --org … --patterns`, then the dry run, then "
             "`--apply` — and have the founder accept, edit or reject each proposal "
             "(`scripts/company_brief.py --org … show`, then `accept` / `reject`)"),
        detail=[f"waiting: {p['line_id']} [{p['section']}] {p['text']}" for p in pending[:20]]
               + [f"left out by the budget: {line_id}" for line_id in brief.truncated])


def check_every_gmail_message_in_the_window_has_its_content(conn, org: str, *,
                                                            now=None) -> Check:
    """⛔ STEP-08 (`yc2_w27_s08/M26.C4`). Before STEP-03 the gate DELETED what a noise rule or the AI
    filter called noise, and the body went with it: 258 of the design partner's 395 Gmail messages are a
    ledger row, outcome `dropped`, with no content — Boardy's introductions and the portal's notices
    among them. The re-sync frees their keys, the backfill drain lands each again through today's gate,
    and its finish supersedes the old row or says why the mail did not come back
    (`capture/landing/resync`). So the promise is a number: Gmail messages inside the connection's
    window with no content and no stated reason — 0. A stated reason is a scope exclusion
    (`out_of_scope`) or the re-sync's own `resync_not_listed`; a message older than the window is
    counted beside the number, never in it. It fails until STEP-08 has run, by design. `now` is for a
    replay that pins the clock; the deploy gate reads the database's.
    """
    from collections import Counter

    from genios_engine.capture.landing.resync import window_days

    name = "every Gmail message in the window has its content, or a stated reason"
    days = window_days(conn, org)
    rows = conn.execute(sql(
        "select se.event_id, se.occurred_at, position('#resync:' in se.dedup_key) > 0 as freed, "
        "       se.occurred_at >= coalesce(cast(:now as timestamptz), now()) "
        "                         - make_interval(days => :days) as inside, "
        "       coalesce((select x.reason_code from event_trace x where x.org_id = se.org_id "
        "                  and x.event_id = se.event_id and x.action = 'drop' "
        "                  order by x.at desc, x.id desc limit 1), 'no trace') as rule "
        "  from source_events se "
        " where se.org_id = :o and se.source = 'gmail' and se.object_type = 'email_message' "
        "   and se.outcome = 'dropped' "
        "   and not exists (select 1 from raw_payloads rp where rp.org_id = se.org_id "
        "                    and rp.event_id = se.event_id "
        "                    and rp.expires_at > coalesce(cast(:now as timestamptz), now())) "
        "   and not exists (select 1 from event_trace t where t.org_id = se.org_id "
        "                    and t.event_id = se.event_id "
        "                    and t.reason_code in ('out_of_scope', 'resync_not_listed')) "
        " order by se.occurred_at, se.event_id"), {"o": org, "now": now, "days": days}).fetchall()
    inside = [r for r in rows if r.inside]
    older = len(rows) - len(inside)
    never = Counter(r.rule for r in inside if not r.freed)
    freed = sum(1 for r in inside if r.freed)
    measured = (f"{len(inside)} Gmail message(s) inside the {days}-day window have no content and "
                "no stated reason"
                + (f", the oldest {inside[0].occurred_at.date().isoformat()}" if inside else "")
                + (f"; {older} more older than the window" if older else ""))
    detail = []
    if never:
        detail.append(f"never freed: {sum(never.values())} — by the rule that deleted them: "
                      + " · ".join(f"{code} {n}" for code, n in
                                   sorted(never.items(), key=lambda kv: (-kv[1], kv[0]))))
    if freed:
        detail.append(f"freed, not yet back or finished: {freed} — finish the backfill drain (a "
                      "TRUNCATED one again with a larger page, `?limit=100`), then --finish")
    in_window = _scalar(
        conn, "select count(*) from source_events where org_id = :o and source = 'gmail' "
              "and object_type = 'email_message' and occurred_at >= "
              "coalesce(cast(:now as timestamptz), now()) - make_interval(days => :days)",
        o=org, now=now, days=days)
    return Check(
        name=name, ok=not inside, no_data=in_window == 0, measured=measured,
        expected=("0 — each came back with its content and its old row is superseded, or says why "
                  "not: Gmail no longer lists it, it is older than the window, a scope exclusion"),
        fix=("STEP-08 §8.6: `scripts/resync_deleted_mail.py --org …` (the dry run) → Rohit names the "
             "window → `PATCH /connections/{gmail}/backfill-window` → `--apply --days N` → "
             "`POST /connections/{gmail}/backfill` → `--finish`"),
        detail=detail)


#: How close to the window's first day memory's oldest mail must come — a mailbox's first mail inside
#: a window is rarely on the window's first day.
REACH_SLACK_DAYS = 14


def check_memory_reaches_the_window(conn, org: str, *, now=None) -> Check:
    """⛔ STEP-08's reach (`yc2_w27_align` M34.C2.L-interface.V1.U04, `06` D16, `09` G3). The window is
    a recommendation until something measures it: the check beside this one asks that every mail
    INSIDE the connection's window has its content, and it passed at 60 days. This asks how far back
    memory goes — the oldest Gmail mail kept in memory (`context/memory_lanes.KEPT_OUTCOMES`) against
    the first day of the connection's window — and fails while memory stops short of it, with the
    mail per month beside it, so a gap is a month you can see. `now` is for a replay that pins the
    clock; the deploy gate reads the database's.
    """
    from genios_engine.capture.landing.resync import window_days
    from genios_engine.context.memory_lanes import KEPT_OUTCOMES

    name = "memory reaches back as far as the Gmail connection's window"
    days = window_days(conn, org)
    rows = conn.execute(sql(
        "select to_char(date_trunc('month', se.occurred_at), 'YYYY-MM') as month, count(*) as n, "
        "       min(se.occurred_at) as oldest, "
        "       coalesce(cast(:now as timestamptz), now()) - make_interval(days => :days) as starts "
        "  from source_events se "
        " where se.org_id = :o and se.source = 'gmail' and se.object_type = 'email_message' "
        "   and se.outcome = any(:kept) "
        " group by 1 order by 1"),
        {"o": org, "now": now, "days": days, "kept": list(KEPT_OUTCOMES)}).fetchall()
    fix = ("STEP-08 §8.6 / `08` §3.7: `PATCH /connections/{gmail}/backfill-window` to the window Rohit "
           "named, then `POST /connections/{gmail}/backfill` — a TRUNCATED drain again with a larger "
           "page, `?limit=100`: it always starts from the newest page")
    if not rows:
        return Check(name=name, ok=False, measured=f"no Gmail mail in memory; the window is {days} days",
                     expected=f"memory's oldest mail within {REACH_SLACK_DAYS} days of the window's "
                              "first day", fix=fix)
    oldest = min(r.oldest for r in rows)
    starts = rows[0].starts
    short = (oldest - starts).days
    ok = short <= REACH_SLACK_DAYS
    measured = (f"memory's oldest Gmail mail is {oldest.date().isoformat()}; the {days}-day window "
                f"starts {starts.date().isoformat()}"
                + (f" — {short} days short" if short > 0 else " — memory reaches it"))
    return Check(
        name=name, ok=ok, measured=measured,
        expected=f"memory's oldest mail within {REACH_SLACK_DAYS} days of the window's first day",
        fix=fix,
        detail=["mail per month: " + " · ".join(f"{r.month} {int(r.n)}" for r in rows)])


def check_every_named_counterparty_has_a_file(conn, org: str) -> Check:
    """⛔ STEP-09 (`yc2_w27_s09/M27.C4`). Every counterparty the founder's company brief names — a
    connector, a person, a portal or program it watches — whose mail memory read has that mail in a
    file: each person a connector introduced in their own, a portal's notices in the portal's
    (`context/workstreams`, the read model `GET /v1/workstreams` serves — this check reads the same
    answer). A mailing, spam and an auto-reply are never a file and are not counted. It fails while a
    named counterparty has such mail and nothing filed — usually mail read before the founder named
    it, as a machine's noise — and names each. A brief that names no counterparty measures nothing,
    and says so.
    """
    from datetime import datetime, timezone

    from genios_engine.context.workstreams import files_for

    name = "every counterparty the brief names that has mail has a file"
    ws = files_for(conn, org, now=datetime.now(timezone.utc))
    unfiled, misfiled = ws.unfiled, ws.misfiled
    partly = [n for n in ws.named if 0 < n.filed < n.mail]
    if not ws.named:
        measured = "not exercised — no counterparty the brief names has mail memory read"
    else:
        measured = (f"{len(ws.unfiled)} of {len(ws.named)} named counterparties with mail have no "
                    f"file; {sum(n.filed for n in ws.named)} of {sum(n.mail for n in ws.named)} "
                    f"of their mails are filed; {len(ws.files)} file(s) in all"
                    + (f"; {sum(n.misfiled for n in misfiled)} introduction(s) are filed under "
                       "the connector" if misfiled else "")
                    + (f"; some of the mail of {len(partly)} is outside its file" if partly
                       else ""))
    return Check(
        name=name, ok=not unfiled and not misfiled, no_data=not ws.named, measured=measured,
        expected=("every named counterparty whose mail was read has that mail in a file, and every "
                  "introduction a connector made is in the file of the person introduced"),
        fix=("re-read the named counterparty's mail with the brief in force, in this order: "
             "`scripts/rebuild_graph.py --org … --apply` reads every event again (the people a "
             "connector introduced, their turns), then `POST /api/org/{org}/situations/backfill?"
             "rebuild=true` re-derives every file from it — the graph rebuild alone keeps the old "
             "files; mail read after the brief and still unfiled is a filing defect: run "
             "`tests/replays/test_every_piece_of_work_has_a_file.py`"),
        detail=[f"{n.named} — \"{n.line}\": {n.mail} mail read, none filed" for n in unfiled]
               + [f"{n.named} — \"{n.line}\": {n.misfiled} introduction(s) filed under the "
                  "connector, not under the people introduced" for n in misfiled]
               + [f"{n.named}: {n.filed} of {n.mail} filed" for n in partly])


def _names(line, address) -> bool:
    """Whether one in-motion line names this address — itself, or its domain or a parent of it."""
    address = str(address or "").strip().lower()
    if not address:
        return False
    if line.address:
        return address == line.address
    domain = address.rsplit("@", 1)[-1]
    return bool(line.domain) and (domain == line.domain or domain.endswith("." + line.domain))


def check_every_piece_of_work_has_one_file(conn, org: str) -> Check:
    """⛔ STEP-09's two numbers (`yc2_w27_align` M34.C2.L-interface.V1.U08), read on the brief's
    IN-MOTION lines — the work the founder named, each with its kind (`06` D31). The check above reads
    connectors, people and the watchlist only, and a counterparty named only in motion is no named
    sender (`03` F125), so "every investor in the brief has a file" and "one file per subject" were
    promised and never measured. Each line whose counterparty memory holds mail with — from them or to
    them, an archive included (its names are memory, STEP-05), never a mailing, spam, an auto-reply or
    a private mail — has exactly ONE file, by the rule a file takes its kind of work by
    (`context/workstreams._work_kind`: an address line by one of the file's people, a domain line by
    the file's anchor). None is F125's gap — its archived mail stays archived; two or more is one
    subject split across files. A brief with no line in motion measures nothing, and says so.
    """
    from datetime import datetime, timezone

    from genios_engine.context.memory_lanes import KEPT_OUTCOMES
    from genios_engine.context.workstreams import NEVER_A_FILE, _anchor_domain, _work_lines, files_for
    from genios_engine.platform.company_brief import brief_for

    name = "every piece of work the brief names in motion has one file"
    expected = ("each piece of work named in motion whose counterparty memory holds mail with has "
                "exactly one file")
    fix = ("no file: its mail was archived and an in-motion counterparty is no named sender (`03` F125) "
           "— promote it (`scripts/promote_archived.py --rule <code> --sender-domain <domain> "
           "--apply`) or name it on the watchlist or as a person; more than one: read the files "
           "`GET /v1/workstreams` lists for it, and `tests/replays/test_every_piece_of_work_has_a_file.py`")
    brief = brief_for(conn, org)
    work = _work_lines(brief)
    if not work:
        return Check(name=name, ok=True, no_data=True, expected=expected, fix=fix,
                     measured="not exercised — the brief names no piece of work in motion")
    ws = files_for(conn, org, now=datetime.now(timezone.utc), company_brief=brief)
    keys = {r.node_id: r.key for r in conn.execute(sql(
        "select node_id, lower(canonical_key) as key from graph_nodes "
        " where org_id = :o and node_id = any(:ids) and valid_to is null"),
        {"o": org, "ids": sorted({p for f in ws.files for p in f.people})})}
    files = {line.line_id: [f for f in ws.files
                            if (line.address and line.address in {keys.get(p) for p in f.people})
                            or (line.domain and _names(line, f"x@{_anchor_domain(f.counterparty_key)}"))]
             for line in work}
    mail = {line.line_id: 0 for line in work}
    for r in conn.execute(sql(
            "select lower(se.actor->>'email') as sender, se.recipients from source_events se "
            " where se.org_id = :o and se.outcome = any(:kept) "
            "   and se.visibility_scope is distinct from 'private' "
            "   and not exists (select 1 from graph_observations ob where ob.org_id = se.org_id "
            "                     and ob.created_by_event_id = se.event_id and ob.kind = any(:never))"),
            {"o": org, "kept": list(KEPT_OUTCOMES), "never": list(NEVER_A_FILE)}):
        for line in work:
            if any(_names(line, a) for a in (r.sender, *(r.recipients or ()))):
                mail[line.line_id] += 1
    worked = [line for line in work if mail[line.line_id]]
    unfiled = [line for line in worked if not files[line.line_id]]
    split = [line for line in work if len(files[line.line_id]) > 1]
    return Check(
        name=name, ok=not unfiled and not split, no_data=not worked and not split,
        expected=expected, fix=fix,
        measured=(f"{len(worked)} piece(s) of work in motion have mail — no file: {len(unfiled)}, "
                  f"split across files: {len(split)}"),
        detail=[f"{line.kind} · {line.address or line.domain} — \"{line.text}\": "
                f"{mail[line.line_id]} mail, no file" for line in unfiled]
               + [f"{line.kind} · {line.address or line.domain} — \"{line.text}\": "
                  f"{len(files[line.line_id])} files — "
                  + ", ".join(sorted(f.counterparty_key for f in files[line.line_id]))
                  for line in split])


#: STEP-10 · the reply times the waiting pass writes as NORMALS — each `(days, n)` pair.
_NORMALS = (("party.reply_cadence_days", "party.reply_cadence_n"),
            ("party.our_reply_days", "party.our_reply_n"),
            ("derived.our_reply_days", "derived.our_reply_n"))


def check_every_normal_says_its_n(conn, org: str) -> Check:
    """⛔ STEP-10 (`yc2_w27_s10/M29.C6.L-interface.V3.U03`). Every reply time written as a NORMAL —
    their reply time (`party.reply_cadence_*`), your reply time with one counterparty
    (`party.our_reply_*`) and overall (`derived.our_reply_*`) — says its n, and none rests on fewer
    than `NORMAL_AT` (`06` D37). On the golden set the only normals were built from ONE reply counted
    twice, with no n anywhere (golden F17, F25); a file must never show a habit like that again. It
    names the file each failing number is on — the counterparty the founder would read it beside, by
    the same files `GET /v1/workstreams` serves (`context/workstreams.files_for`) — and a tenant with no
    normal written measures nothing, and says so.
    """
    from datetime import datetime, timezone

    from genios_engine.context.workstreams import files_for
    from genios_engine.contracts.measured import NORMAL_AT

    name = "every reply time written as a normal says its n, and none rests on fewer than five"
    rows = conn.execute(sql(
        "select n.node_id, n.canonical_key, n.node_type, f.field, f.value #>> '{}' as value "
        "  from graph_facts f "
        "  join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id "
        "       and n.valid_to is null "
        " where f.org_id = :o and f.valid_to is null and f.status = 'active' "
        "   and f.field in ('party.reply_cadence_days', 'party.reply_cadence_n', "
        "                   'party.our_reply_days', 'party.our_reply_n', "
        "                   'derived.our_reply_days', 'derived.our_reply_n')"),
        {"o": org}).fetchall()
    held: dict[str, dict[str, str]] = {}
    who: dict[str, tuple[str, str]] = {}
    for r in rows:
        held.setdefault(r.node_id, {})[r.field] = r.value
        who[r.node_id] = (r.canonical_key, r.node_type)
    file_of = {person: f.counterparty_key
               for f in files_for(conn, org, now=datetime.now(timezone.utc)).files
               for person in f.people}
    normals, wrong = 0, []
    for node_id, fields in sorted(held.items(), key=lambda kv: who[kv[0]][0]):
        key, node_type = who[node_id]
        where = "the tenant" if node_type == "tenant" else file_of.get(node_id, "no file")
        for days, n in _NORMALS:
            if days not in fields:
                continue
            normals += 1
            try:
                count = int(float(fields.get(n) or ""))
            except ValueError:
                # Worded so no fragment opens with "with": the statement counter reads such prose
                # as a CTE (`03` F100).
                wrong.append(f"{where} — {key}: {days} {fields[days]} has no n beside it")
                continue
            if count < NORMAL_AT:
                wrong.append(f"{where} — {key}: {days} {fields[days]} rests on {count}, "
                             f"fewer than {NORMAL_AT}")
    if not normals:
        measured = "not exercised — no reply time is written as a normal"
    elif not wrong:
        measured = f"{normals} normal(s) written, each with its n and none below {NORMAL_AT}"
    else:
        measured = f"{normals} normal(s) written; {len(wrong)} without its n or below {NORMAL_AT}"
    return Check(
        name=name, ok=not wrong, no_data=not normals, measured=measured,
        expected=(f"every normal says its n, and every n is {NORMAL_AT} or more — below it a number "
                  "is shown as what it is, never written as a habit"),
        fix=("a normal with no n was written before STEP-10 and the waiting pass retires it on its "
             "next sweep — run it (`context/waiting.compute_waiting`, every chain pass) and check "
             "again; a normal below five written since is a defect in `context/waiting`: run "
             "`tests/context/test_a_reply_is_counted_once.py` and "
             "`tests/context/test_your_reply_time.py`"),
        detail=wrong)


#: `06` D7, answered 10 Oct: the expert's own day — $2 a day per org — read from the budget itself
#: (`reason/bundle/budget.OWN_BUDGETS`), so the check and the gate never disagree about the cap. The
#: ledger rows are R-7's (`SITE_EXPERT`), named as a literal in the SQL below.
EXPERT_DAILY_CAP_MICRO_USD = usd_to_micro(OWN_BUDGETS[SITE_EXPERT][0])


def check_the_expert_says_why_and_stays_in_budget(conn, org: str) -> Check:
    """⛔ STEP-12 (`yc2_w27_s12/M32.C3.L-interface.V3.U06`). The expert reviews a file once per
    fingerprint and keeps every consult that reached the model, or was refused one for want of budget,
    as a row of `expert_reviews` — a refusal with its reason (STEP-12 §8.4 item 4). On the last day:

      * the reviews, by status;
      * the refusals, by what they said — the detail rows;
      * today's spend against the expert's own cap (`06` D7: $2), read from the ledger its budget is
        read from — every R-7 consult in `l4_r_site_calls`, a retry included.

    It FAILS while a row that is not valid has no reason — the schema refuses one, so that is the
    schema changed under it — or while today's spend is over the cap, which is a gate that let a call
    through — or while MORE THAN HALF of the day's reviews were cut at the ceiling (`yc2_w27_s18`
    M50.C4.L-interface.V1.U11): the Sonnet live pass of 12 Oct had 203 of 203 cut and this check would
    have passed it. No review in the window is nothing to judge, and passes saying so.
    """
    name = "the expert says why, and stays in its budget"
    rows = conn.execute(sql(
        "select status, count(*) as n from expert_reviews "
        " where org_id = :o and reviewed_at > now() - interval '24 hours' "
        " group by status order by status"), {"o": org}).fetchall()
    if not rows:
        return Check(name=name, ok=True, no_data=True,
                     measured="no expert review in the last 24 hours",
                     expected="skipped — nothing to judge", fix="")
    total = sum(int(r.n) for r in rows)
    silent = _scalar(conn, "select count(*) from expert_reviews where org_id = :o "
                           "and reviewed_at > now() - interval '24 hours' and status <> 'valid' "
                           "and coalesce(btrim(reason), '') = ''", o=org)
    spent = _scalar(conn, "select coalesce(sum(cost_micro_usd), 0) from l4_r_site_calls "
                          "where org_id = :o and site = 'R-7' "
                          "and created_at >= date_trunc('day', now())", o=org)
    reasons = conn.execute(sql(
        "select status, reason, count(*) as n from expert_reviews "
        " where org_id = :o and reviewed_at > now() - interval '24 hours' and status <> 'valid' "
        " group by status, reason order by count(*) desc, status, reason limit 10"),
        {"o": org}).fetchall()
    # `reason/expert/store.TRUNCATED`: a review cut at R-7's token ceiling.
    cut = sum(int(r.n) for r in rows if r.status == "truncated")
    measured = (f"{total} reviews in 24 h — "
                + ", ".join(f"{r.status} {int(r.n)}" for r in rows)
                + f"; spent today ${spent / 1_000_000:.2f} of ${EXPERT_DAILY_CAP_MICRO_USD / 1_000_000:.2f}"
                + (f"; {silent} not valid with no reason" if silent else "")
                + (f"; {cut} of {total} truncated" if cut else ""))
    over = spent > EXPERT_DAILY_CAP_MICRO_USD
    mostly_cut = cut * 2 > total
    return Check(
        name=name, ok=not silent and not over and not mostly_cut, measured=measured,
        expected="every refused, truncated, carried or failed review says why, the day's spend "
                 "stays within the expert's own $2, and no more than half of the reviews are cut",
        fix=("a row that is not valid has no reason: the expert_reviews_reason_check constraint "
             "(migration 0197) was dropped or bypassed — restore it, and find the writer that is not "
             "reason/expert/store.write_review" if silent else
             "more than half of the day's reviews were cut at R-7's token ceiling: the model's answer — "
             "its thinking included, which counts toward max_tokens — does not fit. Read R-7's "
             "SITE_MAX_OUTPUT_TOKENS and SITE_THINKING in reason/bundle/sites.py (06 D71, D72)"
             if mostly_cut and not over else
             "the day's R-7 spend is over its budget: a consult ran that RSiteGate's budget should have "
             "refused — check reason/expert/sweep builds its gate with NarrativeBudget.for_site and "
             "the BundleStore ledger"),
        detail=[f"{r.status} × {int(r.n)}: {r.reason}" for r in reasons])


def check_every_new_signal_has_a_lane(conn, org: str) -> Check:
    """⛔ STEP-13 (`yc2_w27_s13` M36.C1.L-integration.V1.U06, `03` F10 and F186). Five writers of
    `signals` left `output_lane` NULL — the LLM decider's decision, the legacy rule lane (LIVE), the
    native publication, the deal-health composer and the team emitter — so a card could not say
    whether it was a thing to do, to find out, to rule on or to watch, and every one of them passed
    its tests. Each now writes the lane and its reason. On the last day:

      * the signals written, and those of them with no lane, by the rule that wrote them.

    It FAILS while one signal of the last day has no lane — run a day after the deploy (`08`), when
    every signal of the window was written by the routed writers. No signal in the window is nothing
    to judge, and passes saying so.
    """
    name = "every new signal has a lane"
    total = _scalar(conn, "select count(*) from signals where org_id = :o "
                          "and created_at > now() - interval '24 hours'", o=org)
    if not total:
        # NO DATA, never PASS (STEP-17's rule, `03` F24's shape; crosscheck S17X-B3): an empty window
        # judged nothing.
        return Check(name=name, ok=True, measured="no signal written in the last 24 hours",
                     expected="skipped — nothing to judge", fix="", no_data=True)
    rows = conn.execute(sql(
        "select coalesce(pack_id, '-') as pack, rule_id, count(*) as n from signals "
        " where org_id = :o and created_at > now() - interval '24 hours' and output_lane is null "
        " group by 1, 2 order by count(*) desc, 1, 2 limit 10"), {"o": org}).fetchall()
    unrouted = sum(int(r.n) for r in rows)
    return Check(
        name=name, ok=unrouted == 0,
        measured=f"{unrouted} of {total} signals written in 24 h have no lane",
        expected="0 — every writer routes its lane (reason/output_lane), and says why",
        fix="a writer inserts into signals without output_lane and lane_reason: "
            "tests/test_every_signal_has_a_lane.py names every writer there is (the engine's six and the "
            "pilot seed) — find the new one, or the one whose decision was never routed "
            "(reason/decision_maker, reason/llm_decision_maker)",
        detail=[f"{r.pack} {r.rule_id} × {int(r.n)}" for r in rows])


CHECKS = (
    check_every_emitted_event_is_routed,
    check_parked_errors_are_readable,
    check_the_known_sender_set_is_not_empty,
    check_a_selected_signal_can_be_carded,
    check_cards_reach_the_app,
    check_the_change_gate_skips_what_did_not_change,
    check_nothing_was_deleted_at_the_gate,
    check_we_are_never_the_subject,
    check_every_kept_event_entered_memory,
    check_every_situation_and_card_says_how_it_ended,
    check_the_company_brief_exists_and_is_current,
    check_every_gmail_message_in_the_window_has_its_content,
    check_memory_reaches_the_window,
    check_every_named_counterparty_has_a_file,
    check_every_piece_of_work_has_one_file,
    check_every_normal_says_its_n,
    check_the_expert_says_why_and_stays_in_budget,
    check_every_new_signal_has_a_lane,
)


def run(conn, org: str, *, hours: int, ceiling_bp: int) -> list[Check]:
    results = [fn(conn, org) for fn in CHECKS]
    results.append(check_llm_failure_rate(conn, org, hours=hours, ceiling_bp=ceiling_bp))
    results.append(check_no_silent_truncation(conn, org, hours=hours))
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    add_database_argument(ap)
    ap.add_argument("--org", required=True, help="org_id to audit")
    ap.add_argument("--hours", type=int, default=24, help="window for the LLM checks")
    ap.add_argument("--max-failure-bp", type=int, default=2000,
                    help="failures per lane, in basis points (default 2000 = 20%%)")
    # ⛔ STEP-17 §3.4 (`yc2_w27_s17` M40.C3.L-interface.V0.U03): "run after each deploy; its output
    # is kept". A file, not stdout: `scripts/_db` prints its `[db]` lines to stdout first (03 F36).
    ap.add_argument("--json", dest="json_path", default=None,
                    help="also write every verdict to this file as JSON, pass or fail")
    ap.add_argument("--require-data", action="store_true",
                    help="exit 2 when no check failed but one judged nothing (NO DATA) — for the "
                         "run a day after a deploy, when every lane should have run")
    args = ap.parse_args()

    url = resolve_database_url(args, purpose="pipeline health audit (read-only)")

    # The engine the application itself builds — same driver, same pool sizing. 
    # here would reach for psycopg2, which this project does not install.
    from genios_engine.platform.db import get_engine
    conn = read_only_connection(get_engine(url))
    try:
        results = run(conn, args.org, hours=args.hours, ceiling_bp=args.max_failure_bp)
    finally:
        conn.close()

    failed = [c for c in results if c.verdict == FAIL]
    no_data = [c for c in results if c.verdict == NO_DATA]
    for c in results:
        print(f"{c.verdict:<7}  {c.name}")
        print(f"      measured: {c.measured}")
        if not c.ok:
            print(f"      expected: {c.expected}")
            for line in c.detail:
                print(f"        · {line}")
            print(f"      fix:      {c.fix}")
    passed = len(results) - len(failed) - len(no_data)
    print(f"\n{passed}/{len(results)} checks passed, {len(no_data)} with no data, "
          f"{len(failed)} failed")
    if args.json_path:
        _keep(args.json_path, args.org, results, passed=passed, no_data=len(no_data),
              failed=len(failed))
    # ⛔ NO DATA is not a failure and not a pass: nothing was judged. It is printed and counted
    # apart — never folded into "passed" — and exits 2 only when the run asked for data.
    if args.require_data and not failed and no_data:
        return 2
    return 1 if failed else 0


def _keep(path: str, org: str, results: list[Check], *, passed: int, no_data: int,
          failed: int) -> None:
    """Every verdict, as JSON, to `path` — the record a deploy keeps."""
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    Path(path).write_text(json.dumps({
        "org": org,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {"checks": len(results), "passed": passed, "no_data": no_data,
                    "failed": failed},
        "checks": [{"name": c.name, "verdict": c.verdict, "measured": c.measured,
                    "expected": c.expected, "fix": c.fix, "detail": list(c.detail)}
                   for c in results],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":        # pragma: no cover
    raise SystemExit(main())
