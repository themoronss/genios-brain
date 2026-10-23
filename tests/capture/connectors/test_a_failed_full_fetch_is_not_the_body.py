"""GeniOS-011 S06.U2 · a refused Gmail fetch is said, retried once, then parked; promotion re-fetches.

    pytest tests/capture/connectors/test_a_failed_full_fetch_is_not_the_body.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest … -q          # the promotion half

THE DEFECT (audit `l1-gmail-full-fetch-failure-silent`, P1). `fetch_content` handed Composio's
failure envelope (`{"successful": false, …}`) on as data, `_full_message` turned every exception
into `{}`, and `_to_objects` read `src = full or m` — so a refused, timed-out or failed per-message
fetch became the LIST message, and its text or snippet became `raw["body"]` with no marker. A body
we did not get was passed off as the body, extracted, and could publish. The Gmail connector's
`_execute` also had no hard deadline, unlike `ComposioExec`.

THE RULE. A refusal raises (A1). A keeper's failed full fetch is tried once more; failing again,
the mail carries `raw["body_fetch"] = "failed"`, no body, and a `fetch_failed` document status —
which the gate's never-bypassable integrity rule parks as DOC-05, a NEEDS_REFETCH code — and the
sweep counts it (`SyncSummary.body_fetch_failed`).

AND PROMOTION (audit `l1-d23-b27-promoted-archive-reads-only-the-snippet`, B27). A confident junk
drop keeps only its list snippet; `scripts/promote_archived.py --apply` now re-fetches each mail's
whole body through the connector and stores it BEFORE the mail goes back to the ledger as kept. A
mail whose body cannot be fetched stays archived, counted.
"""
from __future__ import annotations

import base64
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

_REFUSAL = {"successful": False, "error": "Connected account is not active", "data": {}}
_FULL_WORDS = "Pankaj, meet Meera — she runs the seed fund at Kite and wants the deck by Friday."


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def _list_message(mid: str = "m1") -> dict:
    """What GMAIL_FETCH_EMAILS lists: list fields and a snippet, no MIME parts."""
    return {"messageId": mid, "sender": "Sehan <hello@boardy.test>", "subject": "An intro",
            "messageText": "the list snippet", "preview": "the list snippet, shown in the inbox",
            "messageTimestamp": "2026-10-20T09:00:00Z", "labelIds": ["INBOX"]}


def _full_message(mid: str = "m1") -> dict:
    """What GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID returns: the whole MIME message."""
    return {"messageId": mid, "sender": "Sehan <hello@boardy.test>", "subject": "An intro",
            "messageTimestamp": "2026-10-20T09:00:00Z", "labelIds": ["INBOX"],
            "payload": {"mimeType": "multipart/alternative", "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64(_FULL_WORDS)}}]}}


class _Provider:
    """Composio's side of the wire: the list call answers, the per-message call answers from
    `full` — a list consumed in order, each entry a response or an exception to raise."""

    def __init__(self, full: list[Any], *, listed: list[dict] | None = None) -> None:
        self.full = list(full)
        self.listed = listed if listed is not None else [_list_message()]
        self.calls: list[str] = []

    def __call__(self, slug: str, arguments: dict[str, Any]) -> Any:
        self.calls.append(slug)
        if slug == "GMAIL_FETCH_EMAILS":
            return {"successful": True, "data": {"messages": list(self.listed)}}
        if slug == "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID":
            answer = self.full.pop(0) if self.full else _REFUSAL
            if isinstance(answer, BaseException):
                raise answer
            return answer
        raise AssertionError(f"unexpected slug {slug}")

    def full_fetches(self) -> int:
        return self.calls.count("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID")


def _gmail(provider: _Provider):
    """The production connector with only the network replaced — `_raw_execute`, UNDER `_execute`,
    so the deadline and the refusal handling are the production ones."""
    from genios_engine.capture.connectors import composio

    connector = composio.ComposioGmailConnector(api_key="k", user_id="u")
    connector._raw_execute = provider          # type: ignore[method-assign]
    return connector


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    from genios_engine.capture.connectors import composio
    monkeypatch.setattr(composio, "_FULL_FETCH_RETRY_PAUSE_S", 0.0)


# ------------------------------------------------------------------------- the refusal is said

@pytest.mark.unit
def test_fetch_content_raises_on_a_refusal_and_names_the_error():
    from genios_engine.capture.connectors.composio_base import ProviderRefused

    with pytest.raises(ProviderRefused, match="Connected account is not active"):
        _gmail(_Provider([_REFUSAL])).fetch_content("m1")


@pytest.mark.unit
def test_fetch_content_passes_a_real_answer_through():
    """The negative control: a successful answer is the answer."""
    answer = {"successful": True, "data": _full_message()}
    assert _gmail(_Provider([answer])).fetch_content("m1") == answer


@pytest.mark.unit
def test_the_gmail_execute_has_a_hard_deadline(monkeypatch):
    """A stalled Composio round-trip must not hold a sync worker past the deadline — the same
    bound `ComposioExec` has always had."""
    from genios_engine.capture.connectors import composio

    monkeypatch.setattr(composio, "_GMAIL_EXEC_TIMEOUT_S", 0.2)
    connector = composio.ComposioGmailConnector(api_key="k", user_id="u")
    connector._raw_execute = lambda slug, arguments: time.sleep(3)   # type: ignore[method-assign]
    began = time.monotonic()
    with pytest.raises(TimeoutError):
        connector._execute("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {"message_id": "m1"})
    assert time.monotonic() - began < 2.0, "the deadline did not bound the call"


# --------------------------------------------------------------------- retried once, then parked

@pytest.mark.unit
def test_a_keepers_failed_full_fetch_is_retried_once_and_then_read_whole():
    provider = _Provider([_REFUSAL, {"successful": True, "data": _full_message()}])
    email = _gmail(provider)._to_objects(_list_message(), fetch_full=True)[0]
    assert provider.full_fetches() == 2, "a failed full fetch is tried exactly once more"
    assert email.raw["body"].startswith("Pankaj, meet Meera")
    assert "body_fetch" not in email.raw, "a fetch that succeeded on retry carries no marker"


@pytest.mark.unit
@pytest.mark.parametrize("failure", [_REFUSAL, TimeoutError("deadline"),
                                     RuntimeError("socket reset"),
                                     {"successful": True, "data": {}}],
                         ids=["refused", "timed-out", "errored", "answered-empty"])
def test_a_keepers_twice_failed_full_fetch_is_marked_and_never_the_list_text(failure):
    provider = _Provider([failure, failure])
    email = _gmail(provider)._to_objects(_list_message(), fetch_full=True)[0]
    assert provider.full_fetches() == 2, "retried once, and only once"
    assert email.raw["body_fetch"] == "failed"
    assert email.raw["body"] == "", (
        "the list message's text was passed off as the body of a mail we never fetched")
    assert email.raw["document"]["status"] == "fetch_failed"
    # The list's own fields are still the list's: who sent it, when, what it is called.
    assert email.actor_email == "hello@boardy.test" and email.raw["subject"] == "An intro"


@pytest.mark.unit
def test_a_light_object_is_not_a_failed_fetch():
    """The fast path's LIGHT object never asked for the body — it is a snippet by design and is
    named as one. No fetch, no marker."""
    provider = _Provider([])
    email = _gmail(provider)._to_objects(_list_message(), fetch_full=False)[0]
    assert provider.full_fetches() == 0 and "body_fetch" not in email.raw


@pytest.mark.unit
def test_the_gate_parks_a_failed_fetch_as_needs_refetch_and_the_sweep_counts_it():
    from genios_engine.capture.acquire.sync_runner import run_sync
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository
    from genios_engine.capture.parked.drain import NEEDS_REFETCH

    provider = _Provider([_REFUSAL, _REFUSAL])
    summary = run_sync(_gmail(provider), org_id="org_s06u2", connection_id="con_s06u2",
                       repo=InMemorySourceEventRepository(), source="gmail",
                       respect_cadence=False)
    assert summary.body_fetch_failed == 1
    assert summary.parked == 1 and summary.emitted == 0, (
        "a mail whose body we never fetched reached extraction")
    (result,) = summary.results
    reason = result.trace.records[-1].reason_code
    assert reason == "DOC-05" and reason in NEEDS_REFETCH


@pytest.mark.unit
def test_a_fetched_body_is_emitted_and_counts_no_failure():
    """The negative control for the sweep: the same mail, fetched, is read and counts nothing."""
    from genios_engine.capture.acquire.sync_runner import run_sync
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    provider = _Provider([{"successful": True, "data": _full_message()}])
    summary = run_sync(_gmail(provider), org_id="org_s06u2", connection_id="con_s06u2",
                       repo=InMemorySourceEventRepository(), source="gmail",
                       respect_cadence=False)
    assert summary.body_fetch_failed == 0 and summary.emitted == 1


@pytest.mark.unit
def test_the_backfill_drain_carries_the_count():
    from genios_engine.capture.acquire.sync_runner import backfill_drain
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    total = backfill_drain(_gmail(_Provider([_REFUSAL, _REFUSAL])), org_id="org_s06u2",
                           connection_id="con_s06u2", repo=InMemorySourceEventRepository(),
                           source="gmail")
    assert total.body_fetch_failed == 1


# ------------------------------------------------------------------- the whole-message reader

class _Row:
    """The columns `unread.to_raw_object` reads off a parked row."""

    def __init__(self, *, source: str = "gmail", object_type: str = "email_message",
                 source_object_id: str = "m1", reason_code: str | None = None) -> None:
        self.event_id = "evt_1"
        self.source = source
        self.object_type = object_type
        self.source_object_id = source_object_id
        self.reason_code = reason_code


@pytest.mark.unit
def test_the_whole_message_reader_reads_the_whole_body():
    from genios_engine.capture.connectors.composio import whole_message_reader

    provider = _Provider([{"successful": True, "data": _full_message()}])
    raw = whole_message_reader(_gmail(provider))(_Row())
    assert raw.source == "gmail" and raw.source_object_id == "m1"
    assert raw.raw["body"].startswith("Pankaj, meet Meera")
    assert provider.calls == ["GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID"], (
        "the reader downloads the message, never its attachments")


@pytest.mark.unit
def test_the_whole_message_reader_says_a_refusal_after_one_retry():
    from genios_engine.capture.connectors.composio import WholeMessageUnavailable
    from genios_engine.capture.connectors.composio import whole_message_reader

    provider = _Provider([_REFUSAL, _REFUSAL])
    with pytest.raises(WholeMessageUnavailable, match="m1"):
        whole_message_reader(_gmail(provider))(_Row())
    assert provider.full_fetches() == 2


@pytest.mark.unit
def test_the_whole_message_reader_answers_nothing_for_what_is_not_a_gmail_message():
    from genios_engine.capture.connectors.composio import whole_message_reader

    provider = _Provider([])
    reader = whole_message_reader(_gmail(provider))
    assert reader(_Row(source="gcal")) is None
    assert reader(_Row(object_type="email_attachment", source_object_id="m1::a1")) is None
    assert provider.calls == []


@pytest.mark.unit
def test_the_rejudgment_path_reads_through_the_reader_and_never_the_snippet():
    """The seam `capture/landing/unread.to_raw_object(whole=…)` waits for (GeniOS-011 S06.U1)."""
    from genios_engine.capture.connectors.composio import whole_message_reader
    from genios_engine.capture.landing import unread

    row = _Row(reason_code=unread.LLM_JUNK_REJUDGE)
    whole = whole_message_reader(_gmail(_Provider([{"successful": True,
                                                    "data": _full_message()}])))
    raw = unread.to_raw_object(row, "unused-key", whole=whole)
    assert raw is not None and raw.raw["body"].startswith("Pankaj, meet Meera")
    assert raw.rereading == unread.LLM_JUNK_REJUDGE
    refused = whole_message_reader(_gmail(_Provider([_REFUSAL, _REFUSAL])))
    assert unread.to_raw_object(row, "unused-key", whole=refused) is None


# ----------------------------------------------------------- promotion re-fetches (B27, PG half)

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "promote_archived.py"
SNIPPET = "the list snippet"


def _script():
    import importlib.util
    spec = importlib.util.spec_from_file_location("promote_archived_s06u2", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def archived_tenant():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from sqlalchemy import create_engine, text

    from genios_engine.contracts.source_event import compute_dedup_key
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import encrypt

    key = get_settings().crypto_key
    org = f"org_s06u2_{uuid.uuid4().hex[:8]}"
    eng = create_engine(url)
    at = datetime.now(timezone.utc) - timedelta(days=2)
    mids = {"fetched": f"m_{uuid.uuid4().hex[:8]}", "refused": f"m_{uuid.uuid4().hex[:8]}"}
    events = {name: f"evt_{uuid.uuid4().hex[:12]}" for name in mids}
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 's06u2 promotion')"), {"o": org})
        for name, event_id in events.items():
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome, "
                " attention, attention_reason) values (:e, :o, 'con_x', 'gmail', 'email_message', "
                " :m, :dk, cast(:a as jsonb), :at, :at, 'archived', 'archive', 'llm_junk')"),
                {"e": event_id, "o": org, "m": mids[name], "at": at,
                 "dk": compute_dedup_key("gmail", "email_message", mids[name], None),
                 "a": json.dumps({"type": "external_contact", "email": "hello@boardy.test"})})
            c.execute(text(
                "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
                " expires_at) values (:id, :o, :e, 'application/json', :enc, :exp)"),
                {"id": f"pay_{event_id}", "o": org, "e": event_id,
                 "enc": encrypt(json.dumps({"subject": "An intro", "body": SNIPPET}), key),
                 "exp": at + timedelta(days=180)})
    yield url, eng, org, mids, events, key
    with eng.begin() as c:
        for table in ("raw_payloads", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _state(eng, org, key) -> dict[str, tuple[str, str]]:
    from sqlalchemy import text

    from genios_engine.platform.crypto import decrypt
    with eng.connect() as c:
        rows = c.execute(text(
            "select se.event_id, se.outcome, rp.enc_content from source_events se "
            "  join raw_payloads rp on rp.event_id = se.event_id and rp.org_id = se.org_id "
            " where se.org_id = :o"), {"o": org}).fetchall()
    return {r.event_id: (r.outcome, json.loads(decrypt(bytes(r.enc_content), key))["body"])
            for r in rows}


@pytest.mark.pg
def test_promotion_refetches_the_body_and_leaves_a_refused_one_archived(archived_tenant, capsys):
    url, eng, org, mids, events, key = archived_tenant
    from genios_engine.capture.connectors.composio import whole_message_reader

    provider = _Provider([])
    full = {mids["fetched"]: {"successful": True, "data": _full_message(mids["fetched"])}}

    def _answer(slug, arguments):
        provider.calls.append(slug)
        return full.get(arguments["message_id"], _REFUSAL)

    connector = _gmail(provider)
    connector._raw_execute = _answer           # type: ignore[method-assign]
    asked: list[tuple[str, str]] = []

    def reader_for(connection_id, source):
        asked.append((connection_id, source))
        return whole_message_reader(connector)

    mod = _script()
    assert mod.main(["--org", org, "--rule", "llm_junk", "--database-url", url,
                     "--crypto-key", key], reader_for=reader_for) == 0
    assert "DRY RUN" in capsys.readouterr().out and provider.calls == [], (
        "a dry run fetched from the provider")
    assert mod.main(["--org", org, "--rule", "llm_junk", "--database-url", url,
                     "--crypto-key", key, "--apply"], reader_for=reader_for) == 0
    out = capsys.readouterr().out
    assert "PROMOTED 1" in out and "NOT FETCHED 1" in out
    assert _FULL_WORDS not in out and SNIPPET not in out, "the report printed a mail's words"
    state = _state(eng, org, key)
    assert state[events["fetched"]] == ("emitted", _FULL_WORDS), (
        "the promoted mail is read from its stored snippet, not its whole body")
    assert state[events["refused"]] == ("archived", SNIPPET), (
        "a mail whose body could not be fetched was promoted on its snippet")
    assert asked and all(src == "gmail" for _, src in asked)


@pytest.mark.pg
def test_promotion_with_no_reader_promotes_nothing(archived_tenant, capsys):
    url, eng, org, mids, events, key = archived_tenant
    assert _script().main(["--org", org, "--rule", "llm_junk", "--database-url", url,
                           "--crypto-key", key, "--apply"],
                          reader_for=lambda connection_id, source: None) == 0
    assert "PROMOTED 0" in capsys.readouterr().out
    assert {o for o, _ in _state(eng, org, key).values()} == {"archived"}
