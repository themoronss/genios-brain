"""STEP-08 · the acceptance: the mail the old gate deleted comes back, with its content, once.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_the_deleted_mail_comes_back.py -q

Tree `yc2_w27_s08 · M26.C5.L-integration.V2.U01`. STEP-08 §8.1 as a test, on the cases it measured:
F01 F02 F03 F09 F16 F32 — thirteen mails the gate deleted before STEP-03 (`test_the_gate_deletes_nothing.
DROPPED_BEFORE`). Each case is replayed from its cassette through the real chain, and then the rows of
those mails are rewritten to exactly the shape production holds for the 258 it deleted: outcome
`dropped`, no tier, no body, no prepared text, nothing read, and the old gate's own trace. Then the
runbook runs — the dry run (`scripts/resync_deleted_mail.census`), `--apply` (`resync.free_deleted`),
the backfill drain (the production sync door, `run_sync`, listing the case's mailbox again), `--finish`
(`resync.finish`) and the health check — and per case:

  * every deleted mail lands again through today's gate WITH its body, and its old row is superseded
    with a trace naming the new event; a mail the company brief names comes back READ (emitted, deep,
    W-07, an extraction), the rest archived under the code that deleted it before;
  * a mail Gmail no longer lists (F03's control) is reported — left `dropped`, with that reason — and
    never superseded;
  * the health check fails before the run and passes after it;
  * a second listing lands nothing and a second finish changes nothing;
  * no model call the cassette does not hold.

And on F10, the one case with attachments, listed again under FRESH attachment ids as Gmail hands them
out: an attachment that survived its deleted message is not landed twice, and attachments deleted with
their message come back with it.

The clock is pinned (`NOW`), so the window and the health check read the same on any day. The rewrite
is Layer 1's: what the first replay put in MEMORY from a mail it read stays, so this is the capture
door's acceptance — whether a deleted mail lands again, with what, and once — not memory's.

F10's re-listing asks the junk filter about a page it never saw — the surviving attachments' copies are
dropped before the page is primed — so its few extra answers sit in their own cassette,
`cassettes/resync/F10.json`, recorded deliberately from the ideal reader. Re-record it, when a prompt
moves, with

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… python -m tests.replays.test_the_deleted_mail_comes_back --record
"""
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import CASSETTE_DIR, load_cases
from tests.replays.test_the_gate_deletes_nothing import (DROPPED_BEFORE, KEPT_AS_A_DELIVERY_REPORT,
                                                         KEPT_BY_THE_BRIEF)

CASES = {c.case_id: c for c in load_cases()}
MEASURED = ("F01", "F02", "F03", "F09", "F16", "F32")
#: After every measured case's last sweep, and inside the default window from each.
NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
#: The window Rohit is recommended to name (D5 / D16).
WINDOW = 365
#: Everything Layer 1 keeps for a mail it read — and nothing the old gate's deletion left.
_L1_ROWS = ("raw_payloads", "prepared_content", "l1_extraction_results", "message_fingerprints",
            "parked_events", "document_jobs")
#: The mail Gmail no longer lists: deleted at the provider after the old gate deleted it here.
GONE = "f03-gone"
#: The answers a re-sync scenario needs beyond its case's own cassette (F10's re-primed page).
RESYNC_CASSETTES = CASSETTE_DIR / "resync"


def _cassette(case) -> dict:
    """The case's own cassette, and what its re-sync scenario adds — never a different answer."""
    own = cassettes.load(case)
    if not cassettes.path_for(case, RESYNC_CASSETTES).is_file():
        return own
    extra = cassettes.load(case, RESYNC_CASSETTES)
    assert not own.keys() & extra.keys(), "the scenario cassette re-answers a recorded prompt"
    return {**own, **extra}


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _delete(engine, org: str, objects: dict[str, str]) -> dict[str, str]:
    """Rewrite these objects' rows (provider id → the code that deleted it) to the shape production
    holds for a mail the old gate deleted. Returns provider id → the old row's event id."""
    from sqlalchemy import text
    with engine.begin() as c:
        rows = c.execute(text(
            "select event_id, source_object_id, dedup_key from source_events "
            " where org_id = :o and source = 'gmail' and source_object_id = any(:ids) "
            "   and outcome <> 'superseded'"), {"o": org, "ids": list(objects)}).fetchall()
        assert sorted(r.source_object_id for r in rows) == sorted(objects), rows
        ids = [r.event_id for r in rows]
        c.execute(text("update source_events set outcome = 'dropped', attention = null, "
                       "attention_reason = null, route = null, triage_lane = null "
                       "where org_id = :o and event_id = any(:ids)"), {"o": org, "ids": ids})
        for table in (*_L1_ROWS, "event_trace"):
            c.execute(text(f"delete from {table} where org_id = :o and event_id = any(:ids)"),
                      {"o": org, "ids": ids})
        for r in rows:
            code = objects[r.source_object_id]
            c.execute(text("insert into event_trace (org_id, event_id, dedup_key, source, stage, "
                           "action, reason_code) values (:o, :e, :k, 'gmail', :s, 'drop', :r)"),
                      {"o": org, "e": r.event_id, "k": r.dedup_key, "r": code,
                       "s": "S2" if code == "llm_junk" else "S1"})
    return {r.source_object_id: r.event_id for r in rows}


def _gone(engine, org: str) -> str:
    """A deleted mail the mailbox no longer lists — the not-listed control."""
    from sqlalchemy import text

    from genios_engine.contracts.source_event import compute_dedup_key
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) values "
            " ('evt_f03_gone', :o, 'conn_golden_gmail', 'gmail', 'email_message', :m, :k, "
            " cast('{\"type\": \"external_contact\", \"email\": \"hello@introly.test\"}' as jsonb), "
            " :at, :at, 'dropped')"),
            {"o": org, "m": GONE, "k": compute_dedup_key("gmail", "email_message", GONE),
             "at": datetime(2026, 9, 5, 9, tzinfo=timezone.utc)})
        c.execute(text("insert into event_trace (org_id, event_id, stage, action, reason_code) "
                       "values (:o, 'evt_f03_gone', 'S1', 'drop', 'N-02')"), {"o": org})
    return "evt_f03_gone"


def _mailbox(fresh_attachment_ids: bool):
    from tests.replays.engine_runner import _connectors
    mailbox, _calendar = _connectors()
    if not fresh_attachment_ids:
        return mailbox

    class ListedAgain(mailbox):
        """Gmail hands out a fresh `attachmentId` on every read of a message."""

        def _execute(self, slug: str, arguments: dict[str, Any]) -> Any:
            if slug == "GMAIL_GET_ATTACHMENT":
                arguments = {**arguments,
                             "attachment_id": arguments["attachment_id"].removesuffix("-again")}
                return super()._execute(slug, arguments)
            answer = super()._execute(slug, arguments)
            messages = (answer["data"].get("messages") if slug == "GMAIL_FETCH_EMAILS"
                        else [answer["data"]])
            for message in messages:
                for part in message["payload"]["parts"]:
                    body = part.get("body") or {}
                    if "attachmentId" in body:
                        body["attachmentId"] = f"{body['attachmentId']}-again"
            return answer

    return ListedAgain


def _relist(case, org: str, llm, tag: str, *, fresh_attachment_ids: bool = False) -> Counter:
    """The backfill drain: the case's mail listed again through the production sync door, sweep by
    sweep as the run listed it — the junk filter is asked about the same page, so it is served."""
    from genios_engine.api import routes
    from tests.replays.engine_runner import _land, pinned_world, production_switches
    mailbox = _mailbox(fresh_attachment_ids)
    outcomes: Counter = Counter()
    with production_switches(llm), pinned_world(f"golden:{case.case_id}:{tag}"):
        for sweep, at in enumerate(case.sweeps):
            mail = [o for o in case.objects_in(sweep) if o.source == "gmail"]
            if mail:
                landed = _land(routes, case, org, sweep, at, mailbox(mail), "gmail")
                outcomes.update((x.source_object_id, x.outcome) for x in landed)
    return outcomes


def _rows(engine, org: str) -> dict[str, Any]:
    from sqlalchemy import text
    with engine.connect() as c:
        return {r.event_id: r for r in c.execute(text(
            "select se.event_id, se.source_object_id, se.object_type, se.parent_object_id, "
            "       se.outcome, se.attention, se.attention_reason, "
            "       exists (select 1 from raw_payloads p where p.org_id = se.org_id "
            "               and p.event_id = se.event_id) as has_body, "
            "       exists (select 1 from l1_extraction_results x where x.org_id = se.org_id "
            "               and x.event_id = se.event_id) as was_read "
            "  from source_events se where se.org_id = :o and se.source = 'gmail'"), {"o": org})}


def _resync_trace(engine, org: str) -> dict[str, list]:
    from sqlalchemy import text
    out: dict[str, list] = {}
    with engine.connect() as c:
        for r in c.execute(text("select event_id, action, reason_code, detail from event_trace "
                                "where org_id = :o and stage = 'resync' order by at, id"),
                           {"o": org}):
            out.setdefault(r.event_id, []).append(r)
    return out


def _health(engine, org: str):
    import importlib
    health = importlib.import_module("scripts.pipeline_health")
    with engine.connect() as c:
        return health.check_every_gmail_message_in_the_window_has_its_content(c, org, now=NOW)


def _census(engine, org: str) -> list[str]:
    import importlib
    script = importlib.import_module("scripts.resync_deleted_mail")
    with engine.connect() as c:
        return script.census(c, org, now=NOW, days=WINDOW)


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case_id", MEASURED)
def test_the_deleted_mail_comes_back_with_its_content(case_id):
    _scratch_db()
    from genios_engine.api import routes
    from genios_engine.capture.landing import resync
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM

    case = CASES[case_id]
    llm = RecordedLLM(cassettes.load(case))
    run = run_case(case, llm, keep=True)
    engine = routes._graph.engine
    org = run.org_id
    try:
        objects = DROPPED_BEFORE[case_id]
        deleted = _delete(engine, org, objects)
        gone = _gone(engine, org) if case_id == "F03" else None
        expected = len(objects) + (gone is not None)

        before = _health(engine, org)
        assert not before.ok and f"{expected} Gmail message(s)" in before.measured, before
        census = _census(engine, org)
        assert census[0].startswith(f"{org}: {expected} Gmail message(s) the old gate deleted")
        assert f"--days {WINDOW} reaches {expected} and leaves out 0" in "\n".join(census)

        assert resync.free_deleted(engine, org, days=WINDOW, now=NOW) == expected
        listed = _relist(case, org, llm, "resync")
        assert all(listed[(oid, "duplicate")] == 0 for oid in objects), listed
        done = resync.finish(engine, org, now=NOW)
        assert (done.superseded, done.not_listed) == (len(objects), int(gone is not None)), done

        rows, traces = _rows(engine, org), _resync_trace(engine, org)
        brief = set(KEPT_BY_THE_BRIEF.get(case_id, ()))
        report = set(KEPT_AS_A_DELIVERY_REPORT.get(case_id, ()))
        for oid, code in objects.items():
            old = rows[deleted[oid]]
            assert old.outcome == "superseded", (oid, old)
            [freed, replaced] = traces[deleted[oid]]
            assert (freed.reason_code, freed.detail["dropped_by"]) == ("resync_freed", code)
            assert replaced.reason_code == "resync_replaced", (oid, replaced)
            new = rows[replaced.detail["replaced_by"]]
            assert new.source_object_id == oid and new.has_body, (oid, new)
            if oid in brief:
                assert (new.outcome, new.attention, new.attention_reason, new.was_read) == (
                    "emitted", "deep", "W-07", True), (oid, new)
            elif oid in report:        # STEP-10 (D38): a delivery report is kept and read
                assert (new.outcome, new.attention, new.was_read) == (
                    "emitted", "deep", True), (oid, new)
            else:
                assert (new.outcome, new.attention, new.attention_reason, new.was_read) == (
                    "archived", "archive", code, False), (oid, new)
        if gone:
            assert rows[gone].outcome == "dropped"
            [_freed, reported] = traces[gone]
            assert (reported.action, reported.reason_code, reported.detail["inside_window"]) == (
                "drop", "resync_not_listed", True)

        after = _health(engine, org)
        assert after.ok, after

        again = _relist(case, org, llm, "again")
        assert all(again[(oid, "duplicate")] == 1 for oid in objects), again
        second = resync.finish(engine, org, now=NOW)
        assert (second.superseded, second.newly_reported) == (0, 0), second
        assert not llm.misses, f"{case_id}: the cassette did not hold {llm.misses[:3]}"
    finally:
        remove_tenant(engine, org)


def _f10(fresh: dict[str, str], model=None):
    """F10, its message deleted (and `fresh` with it), listed again under fresh attachment ids."""
    from genios_engine.api import routes
    from genios_engine.capture.landing import resync
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM

    case = CASES["F10"]
    llm = model or RecordedLLM(_cassette(case))
    run = run_case(case, llm, keep=True)
    engine = routes._graph.engine
    org = run.org_id
    try:
        files_before = {e: r for e, r in _rows(engine, org).items()
                        if r.object_type == "email_attachment"}
        deleted = _delete(engine, org, {"f10-ask": "N-06", **fresh})
        assert resync.free_deleted(engine, org, days=WINDOW, now=NOW) == 1, "the message only"
        _relist(case, org, llm, "resync", fresh_attachment_ids=True)
        done = resync.finish(engine, org, now=NOW)
        rows = _rows(engine, org)
        assert not getattr(llm, "misses", ()), f"F10: the cassette did not hold {llm.misses[:3]}"
        return done, deleted, files_before, rows
    finally:
        remove_tenant(engine, org)


@pytest.mark.pg
@pytest.mark.golden
def test_an_attachment_that_survived_its_deleted_message_is_not_landed_twice():
    _scratch_db()
    done, deleted, files_before, rows = _f10({})
    assert done.superseded == 1 and rows[deleted["f10-ask"]].outcome == "superseded"
    files_after = {e: r for e, r in rows.items() if r.object_type == "email_attachment"}
    assert len(files_before) == 2
    assert files_after.keys() == files_before.keys(), "a surviving attachment came back a second time"


@pytest.mark.pg
@pytest.mark.golden
def test_attachments_deleted_with_their_message_come_back_with_it():
    _scratch_db()
    done, deleted, files_before, rows = _f10({"f10-ask::att1": "N-06", "f10-ask::att2": "N-06"})
    assert done.superseded == 1 and rows[deleted["f10-ask"]].outcome == "superseded"
    again = {r.source_object_id for r in rows.values()
             if r.object_type == "email_attachment" and r.outcome != "dropped"}
    assert again == {"f10-ask::att1-again", "f10-ask::att2-again"}
    assert all(r.has_body for r in rows.values()
               if r.source_object_id in again), "an attachment came back without its file"
    old = [rows[deleted[k]] for k in ("f10-ask::att1", "f10-ask::att2")]
    assert [r.outcome for r in old] == ["dropped", "dropped"], (
        "an attachment's old key is never taken again — its old row stays as it was")


# ── recording F10's scenario cassette — deliberate, never from a test run ───────────────────────

class _ServedThenRead:
    """F10's own cassette first; a prompt it does not hold is answered by the ideal reader, and that
    answer — only that — is written down."""

    def __init__(self, case) -> None:
        from tests.replays.harness import CassetteRecorder, RecordedLLM
        from tests.replays.ideal_reader import IdealReader
        self._recorded = RecordedLLM(cassettes.load(case))
        self.recorder = CassetteRecorder(IdealReader(case))
        self.model = self._recorded.model

    def call(self, prompt: str, **kw: Any):
        from tests.replays.harness import CassetteMiss
        try:
            return self._recorded.call(prompt, **kw)
        except CassetteMiss:
            return self.recorder.call(prompt, **kw)


def record() -> None:
    from tests.replays.engine_runner import pin_scratch_database
    pin_scratch_database()
    case = CASES["F10"]
    model = _ServedThenRead(case)
    _f10({}, model)
    _f10({"f10-ask::att1": "N-06", "f10-ask::att2": "N-06"}, model)
    answers = model.recorder.cassette
    path = cassettes.save(case, answers, source=cassettes.IDEAL_READER, folder=RESYNC_CASSETTES)
    print(f"{path}: {len(answers)} answer(s) — "
          + ", ".join(sorted({a['site'] for a in answers.values()})))


if __name__ == "__main__":       # pragma: no cover - the recording entry point
    import sys
    if sys.argv[1:] != ["--record"]:
        raise SystemExit("usage: python -m tests.replays.test_the_deleted_mail_comes_back --record")
    record()
