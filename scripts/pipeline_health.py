"""Every invariant that was green in the test suite and false in production, asserted on real data.

    GENIOS_TARGET_DATABASE_URL=... python scripts/pipeline_health.py --org org_...

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
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402
from scripts._gate import read_only_connection, sql                   # noqa: E402


@dataclass
class Check:
    """One measured invariant. `detail` rows are printed under a failure, never summarised away."""

    name: str
    ok: bool
    measured: str
    expected: str
    fix: str
    detail: list[str] = field(default_factory=list)


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
    return Check(
        name="every emitted event is routed",
        ok=n == 0,
        measured=f"{n} emitted events with route IS NULL",
        expected="0 — an emitted event that is routed nowhere is never read",
        fix="UPDATE them to route='needs_extraction'; the writers are capture/parked/drain.py "
            "and capture/parked/recapture.py",
    )


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
    return Check(
        name="no LLM lane is mostly failing",
        ok=not bad,
        measured=(", ".join(f"{p}: {b}/{n}" for p, b, n in bad) if bad
                  else f"{len(rows)} lane(s) under {ceiling_bp / 100:g}% in {hours}h"),
        expected=f"every purpose under {ceiling_bp / 100:g}% failures",
        fix="read llm_costs.error for that purpose — a 400 means the request shape is wrong for "
            "the model, a truncation means the budget is too small for the question",
        detail=[f"{p}: {b} of {n} failed" for p, b, n in bad],
    )


def check_no_silent_truncation(conn, org: str, *, hours: int) -> Check:
    """⛔ Every failure of `l1_extract` and `l1_relevance` sat at EXACTLY its ceiling — 8192 and
    1024 — while the stored error said "unparseable JSON" and sent every reader to the prompt.

    A lane whose failures cluster on one output size is not writing bad JSON; it is running out
    of budget, and `LLMResult.truncated` now says so. This asserts the shape stays visible.
    """
    rows = conn.execute(sql(
        "select purpose, min(output_tokens) lo, max(output_tokens) hi, count(*) n "
        "  from llm_costs "
        " where org_id = :o and not success and created_at > now() - make_interval(hours => :h) "
        " group by 1 having count(*) >= 3"), {"o": org, "h": hours}).fetchall()
    pinned = [(r.purpose, r.lo, r.n) for r in rows if r.lo == r.hi and r.lo > 0]
    return Check(
        name="no lane is failing at a fixed token ceiling",
        ok=not pinned,
        measured=(", ".join(f"{p}: {n} failures all at {lo} tokens" for p, lo, n in pinned)
                  if pinned else "no failure cluster pinned to one output size"),
        expected="failures spread across output sizes — a single size means truncation",
        fix="raise that lane's max_tokens, or ask it a smaller question; the error text will "
            "name the ceiling since LLMClient reads stop_reason",
        detail=[f"{p}: {n} failures, every one at {lo} output tokens" for p, lo, n in pinned],
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
        ok=mute == 0,
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
        return Check(name="the tenant knows who it has written to", ok=True,
                     measured="no outbound mail captured yet",
                     expected="skipped — nothing has been sent, so nobody can be known",
                     fix="")
    known = _scalar(conn,
                    "select count(distinct lower(r)) from source_events e, unnest(e.recipients) r "
                    " where e.org_id = :o and e.recipients is not null "
                    "   and lower(e.actor ->> 'email') in "
                    "       (select lower(s.email) from org_seats s "
                    "         where s.org_id = :o and s.email is not null)", o=org)
    return Check(
        name="the tenant knows who it has written to",
        ok=known > 0,
        measured=f"{known} known counterparties from {outbound} outbound events",
        expected=">0 — an empty set turns W-01 off and hands the N-codes the whole mailbox",
        fix="check org_seats carries the mailbox owner's address; the whitelist reads it",
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
    return Check(
        name="an open signal with a lapsed card gets rebuilt",
        ok=stuck == 0,
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
        ok=live == 0 or on_app > 0,
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
        return Check(name=name, ok=True, measured="no sweep in the last 6 hours",
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
    return Check(
        name=name, ok=deleted == 0,
        measured=f"{deleted} object(s) captured in {window} were deleted at the gate",
        expected="0 — the gate archives what it calls noise; only S0's scope exclusion drops",
        fix=fix,
        detail=[f"{r.code}: {int(r.n)} deleted" for r in rows])


CHECKS = (
    check_every_emitted_event_is_routed,
    check_parked_errors_are_readable,
    check_the_known_sender_set_is_not_empty,
    check_a_selected_signal_can_be_carded,
    check_cards_reach_the_app,
    check_the_change_gate_skips_what_did_not_change,
    check_nothing_was_deleted_at_the_gate,
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

    failed = [c for c in results if not c.ok]
    for c in results:
        print(f"{'PASS' if c.ok else 'FAIL'}  {c.name}")
        print(f"      measured: {c.measured}")
        if not c.ok:
            print(f"      expected: {c.expected}")
            for line in c.detail:
                print(f"        · {line}")
            print(f"      fix:      {c.fix}")
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":        # pragma: no cover
    raise SystemExit(main())
