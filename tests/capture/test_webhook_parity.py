"""G9 · L1.2.5-U1 — webhook and poll must produce IDENTICAL rows for the same object.

THE DEFECT. `capture/connectors/dispatch.py` parsed gmail, gcal, notion and gdrive and nothing
else, so a HubSpot push — a buildable source, `buildable=True` in the registry, advertising the
`crm` capability the sales pack requires — returned None and the route answered
`{"ingested": false, "reason": "unmapped payload"}` for every trigger it ever received. A whole
source dropped its entire real-time lane silently: the poll path had the deals, the webhook path
had nothing, and no test compared them.

WHAT PARITY MEANS HERE, EXACTLY. The same logical object fed through the poll path and through
the webhook path must yield equal `RawObject`s and equal `SourceEvent`s, field for field.

EXCLUDED FROM THE COMPARISON, AND WHY — only these three:
  * `event_id`   — a fresh id minted at ingest (`new_id("evt")`); it is per-ROW, not per-object,
                   and normalize's own docstring names it non-deterministic.
  * `captured_at`— WHEN WE LEARNED IT is precisely the thing the two doors are supposed to
                   differ on: a webhook learns it now, a poll learns it at the next sweep.
                   `occurred_at` is NOT excluded and is compared.
  * `sync_mode`  — chosen by the CALLER (a drain says `backfill`, a live push says
                   `incremental`), not by the parser under test. Both paths are handed the same
                   value here so the field is still compared, just not left free.
`dedup_key` is compared, and it is the field that matters most: two doors that disagree on it
double-land every message that arrives through both — which is every message, on every recovery
sync, by design.

    pytest tests/capture/connectors/test_webhook_parity.py -q
"""

from __future__ import annotations

import base64

import pytest

from genios_engine.capture.connectors.calendar import ComposioCalendarConnector
from genios_engine.capture.connectors.composio import ComposioGmailConnector
from genios_engine.capture.connectors.dispatch import webhook_to_raw, webhook_to_raw_objects
from genios_engine.capture.connectors.hubspot import ComposioHubspotConnector
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.contracts.source_event import SyncMode

WAVE = "W9"
GATE = "G9"

ORG, CONNECTION = "org_w9", "con_w9"

#: Non-deterministic per row, or deliberately caller-chosen. Everything else is compared.
PATH_SPECIFIC_FIELDS = {"event_id", "captured_at"}


def _events_equal(poll_obj, hook_obj) -> tuple[dict, dict]:
    """Both objects normalized through the SAME seam, with the path-specific fields removed."""
    def one(raw):
        event = to_source_event(raw, org_id=ORG, connection_id=CONNECTION,
                                sync_mode=SyncMode.incremental, payload_ref=None,
                                mailbox_owner="founder@acme.com")
        return {k: v for k, v in event.model_dump().items() if k not in PATH_SPECIFIC_FIELDS}
    return one(poll_obj), one(hook_obj)


class _Exec:
    """A Composio client stub returning a canned page — no network, both paths."""

    def __init__(self, page: dict) -> None:
        self.page = page
        self.calls: list[tuple[str, dict]] = []

    def execute(self, slug: str, arguments: dict):
        self.calls.append((slug, dict(arguments)))
        return self.page


# ── HubSpot: the source that was dropping its whole webhook lane ──────────────────────────────

DEAL = {
    "id": "12345678901",
    "properties": {"dealname": "Acme — platform licence", "dealstage": "contractsent",
                   "amount": "480000", "closedate": "2026-10-31",
                   "hs_lastmodifieddate": "2026-09-04T11:22:33Z"},
    "contacts": ["priya@acme.com"],
    "contact_email": "priya@acme.com",
    "updatedAt": "2026-09-04T11:22:33Z",
}


def _hubspot(page: dict) -> ComposioHubspotConnector:
    connector = ComposioHubspotConnector(api_key="", user_id="")
    connector._x = _Exec(page)
    return connector


@pytest.mark.parametrize("envelope, why", [
    ({"deal": DEAL}, "Composio nests the record under its object name"),
    ({"object": DEAL}, "…or under a generic `object`"),
    ({"record": DEAL}, "…or `record`"),
    (DEAL, "…or delivers the record itself as the payload"),
])
def test_hubspot_webhook_and_poll_emit_identical_rows(envelope, why):
    poll = _hubspot({"results": [DEAL]}).incremental_changes(limit=10).objects
    hook = webhook_to_raw_objects("hubspot", envelope,
                                  connector_factory=lambda: _hubspot({"results": [DEAL]}))
    assert len(poll) == len(hook) == 1, why
    assert poll[0] == hook[0], "RawObject field for field"
    polled, hooked = _events_equal(poll[0], hook[0])
    assert polled == hooked
    assert polled["dedup_key"] == "hubspot:deal:12345678901:2026-09-04T11:22:33Z"


def test_hubspot_property_change_push_fetches_the_deal_the_poll_would_have_seen():
    """HubSpot's own webhook shape carries an objectId and a changed property, not the record.
    Parsing that envelope alone would land a deal with no name, stage or amount — so the
    dispatcher fetches the object, which is exactly what the poll path already reads."""
    push = {"subscriptionType": "deal.propertyChange", "objectId": 12345678901,
            "propertyName": "dealstage", "propertyValue": "contractsent"}
    poll = _hubspot({"results": [DEAL]}).incremental_changes(limit=10).objects
    fetcher = _hubspot(DEAL)
    hook = webhook_to_raw_objects("hubspot", push, connector_factory=lambda: fetcher)
    assert [c[0] for c in fetcher._x.calls] == ["HUBSPOT_GET_DEAL"], "it asked for the deal"
    assert poll[0] == hook[0]


def test_hubspot_id_only_push_without_a_connector_reports_nothing_rather_than_fabricating():
    push = {"subscriptionType": "deal.propertyChange", "objectId": 12345678901}
    assert webhook_to_raw_objects("hubspot", push) == ()


def test_hubspot_push_whose_fetch_comes_back_empty_reports_nothing():
    push = {"subscriptionType": "deal.propertyChange", "objectId": 12345678901}
    assert webhook_to_raw_objects("hubspot", push,
                                  connector_factory=lambda: _hubspot({})) == ()


# ── Gmail ────────────────────────────────────────────────────────────────────────────────────

def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


MESSAGE = {
    "id": "msg_18c4a9e2f7",
    "threadId": "thread_18c4a",
    "internalDate": "1756900000000",
    "labelIds": ["INBOX"],
    "payload": {
        "headers": [{"name": "From", "value": '"Priya Rao" <priya@acme.com>'},
                    {"name": "To", "value": "founder@acme.com"},
                    {"name": "Cc", "value": "cfo@acme.com"},
                    {"name": "Subject", "value": "Revised contract"}],
        "parts": [{"mimeType": "text/plain", "filename": "",
                   "body": {"data": _b64("Budget approved. Send the revised contract by Friday.")}}],
    },
}


def _gmail() -> ComposioGmailConnector:
    connector = ComposioGmailConnector(api_key="", user_id="")
    connector._execute = lambda slug, args: {}      # a full-fetch would be a network call
    return connector


@pytest.mark.parametrize("envelope", [{"message": MESSAGE}, {"email": MESSAGE}, MESSAGE])
def test_gmail_webhook_and_poll_emit_identical_rows(envelope):
    poll = _gmail()._to_batch({"data": {"messages": [MESSAGE]}}).objects
    hook = webhook_to_raw_objects("gmail", envelope, connector_factory=_gmail)
    assert tuple(poll) == hook
    polled, hooked = _events_equal(poll[0], hook[0])
    assert polled == hooked
    assert polled["recipients"] == ("founder@acme.com", "cfo@acme.com")
    assert polled["visibility"] is not None, "the ACL is stamped on both doors, or the gate parks"


def test_gmail_webhook_emits_the_attachment_events_the_poll_path_emits():
    """The webhook lane returned ONE object per push. A message with a PDF produces two on the
    poll path (the mail and the document), and the document is the half that carries the
    contract — so a single-object webhook lane loses it."""
    message = {**MESSAGE, "payload": {
        "headers": MESSAGE["payload"]["headers"],
        "parts": [*MESSAGE["payload"]["parts"],
                  {"mimeType": "text/plain", "filename": "terms.txt",
                   "body": {"attachmentId": "att_1", "data": _b64("Net 30. Governing law: KA.")}}]}}
    poll = _gmail()._to_batch({"data": {"messages": [message]}}).objects
    hook = webhook_to_raw_objects("gmail", {"message": message}, connector_factory=_gmail)
    assert [o.object_type for o in poll] == ["email_message", "email_attachment"]
    assert tuple(poll) == hook


# ── Calendar ─────────────────────────────────────────────────────────────────────────────────

EVENT = {
    "id": "evt_9f2",
    "summary": "Acme — pricing review",
    "start": {"dateTime": "2026-09-10T09:00:00+00:00"},
    "end": {"dateTime": "2026-09-10T10:00:00+00:00"},
    "status": "confirmed",
    "updated": "2026-09-04T08:00:00Z",
    "organizer": {"email": "founder@acme.com"},
    "attendees": [{"email": "priya@acme.com"}, {"email": "founder@acme.com"}],
}


@pytest.mark.parametrize("envelope", [{"event": EVENT}, {"calendar_event": EVENT}, EVENT])
def test_calendar_webhook_and_poll_emit_identical_rows(envelope):
    connector = ComposioCalendarConnector(api_key="", user_id="")
    connector._x = _Exec({"items": [EVENT]})
    poll = connector.incremental_changes(limit=10).objects
    hook = webhook_to_raw_objects("gcal", envelope, connector_factory=lambda: connector)
    assert tuple(poll) == hook
    polled, hooked = _events_equal(poll[0], hook[0])
    assert polled == hooked


# ── the dispatcher's own contract ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("source_type, expected, why", [
    ("gmail", True, "canonical id"),
    ("calendar", True, "gcal alias, from the source registry rather than a hand-listed set"),
    ("google_drive", True, "gdrive alias"),
    ("hubspot", True, "THE fix — a buildable source may not be silently unmapped"),
    ("slack", False, "described in the registry but not buildable: nothing can parse it"),
    ("wat", False, "unknown source"),
    ("", False, "missing source"),
])
def test_dispatch_covers_every_buildable_source(source_type, expected, why):
    from genios_engine.capture.connectors.dispatch import can_dispatch
    assert can_dispatch(source_type) is expected, why


def test_every_buildable_composio_source_is_dispatchable():
    """The gap this unit closes was structural: `buildable` said yes and the dispatcher said no,
    with nothing comparing the two. This is that comparison."""
    from genios_engine.capture.connectors.dispatch import can_dispatch
    from genios_engine.platform.wiring import COMPOSIO_SOURCE_TYPES
    unmapped = sorted(st for st in COMPOSIO_SOURCE_TYPES if not can_dispatch(st))
    assert unmapped == [], f"buildable but no webhook parser: {unmapped}"


@pytest.mark.parametrize("payload", [None, [], "text", 42])
def test_a_payload_that_is_not_an_object_is_reported_not_fabricated(payload):
    assert webhook_to_raw_objects("gmail", payload) == ()
    assert webhook_to_raw("gmail", payload) is None


def test_webhook_to_raw_returns_the_primary_object():
    """The singular helper the live route still calls returns the FIRST object — the message
    itself — so its behaviour is unchanged while the plural form carries the attachments."""
    hook = webhook_to_raw("gmail", {"message": MESSAGE}, connector_factory=_gmail)
    assert hook is not None and hook.object_type == "email_message"
    assert hook == webhook_to_raw_objects("gmail", {"message": MESSAGE},
                                          connector_factory=_gmail)[0]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# ROUTE-LEVEL PARITY · L1.2.5-U1 · "webhook and poll produce IDENTICAL ROWS for the same message"
#
# Everything above compares PARSERS. That is half the gate, and it is the half that was already
# closed: `webhook_objects` funnels into `_to_objects`, so both doors build the same RawObjects.
#
# The rows are still not the same, because the ROUTE decides what the pipeline is given:
#
#   DEFECT #1 — `api/routes.py` called the SINGULAR `webhook_to_raw`, which returns objects[0].
#               A message with a PDF is two objects on the poll path; the webhook lane landed the
#               mail and dropped the document — the half carrying the contract.
#   DEFECT #2 — the webhook call passed no `mailbox_owner` (so `visibility_principals` lost the
#               owner and the ACL was derived from a different rule), no `prepared_store` (so
#               `prepared_content` — the clean text S2 extracts from and every evidence span
#               aligns against — was never written), no `relevance`, no `parked_store` and no
#               `sender_resolver`.
#
# So these tests drive the two REAL doors — `routes._sync_source` (the sweep) and an HTTP POST to
# `/webhooks/composio` — against a REAL Postgres, with the same logical message, and compare the
# rows both wrote.
#
# EXCLUDED FROM THE ROW COMPARISON, AND WHY — only these, each named:
#   * `event_id`, `id`      — freshly minted per row (`new_id`), non-deterministic by construction.
#   * `org_id`              — the two doors are pointed at two tenants ON PURPOSE, because one
#                             tenant would make the second landing a `duplicate` and there would be
#                             no second row to compare.
#   * `connection_id`       — one connection row per door, same reason.
#   * `captured_at`         — WHEN WE LEARNED IT is the one thing the doors are supposed to differ
#                             on. `occurred_at` is NOT excluded and is compared.
#   * `payload_ref` / `prepared_content_id` — content ids minted per row.
#   * `created_at`, `expires_at` — retention clocks stamped from wall time at write.
# `dedup_key`, `visibility_*`, `route`, `triage_lane`, `domain_hints`, `linkage_hints`,
# `recipients`, `outcome`, `clean_text`, `offset_map`, `masked_spans` and the document rows are
# all COMPARED. A parity test that excluded those would prove nothing.
# ══════════════════════════════════════════════════════════════════════════════════════════════

import os

from sqlalchemy import text as _sql

from genios_engine.contracts.connection import Connection

#: Per-row identity and wall-clock stamps. Everything else in every table is compared.
_ROW_EXCLUSIONS: dict[str, str] = {
    "event_id": "minted per row (new_id('evt'))",
    "id": "minted per row (document_jobs.id / raw_payloads.id)",
    "org_id": "one tenant per door — a single tenant would dedup the second landing away",
    "connection_id": "one connection row per door, same reason",
    "captured_at": "when WE learned it; the doors differ here by design (occurred_at is compared)",
    "payload_ref": "content id minted per row",
    "prepared_content_id": "content id minted per row",
    "created_at": "wall-clock stamp at write",
    "expires_at": "retention clock derived from the wall-clock stamp",
}

ATTACHED = {**MESSAGE, "id": "msg_parity_1", "threadId": "thread_parity",
            "payload": {"headers": MESSAGE["payload"]["headers"],
                        "parts": [*MESSAGE["payload"]["parts"],
                                  {"mimeType": "text/plain", "filename": "terms.txt",
                                   "body": {"attachmentId": "att_p1",
                                            "data": _b64("Net 30. Governing law: KA.")}}]}}

MAILBOX_OWNER = "founder@acme.com"


class _RecordingRelevance:
    """A temp-0 stand-in for the S2 gate: one verdict, and a ledger of who asked.

    `keep` at 0.90 rather than a drop, so the gate's decision does not hide the pipeline stages
    that follow it — the parity we care about is over emitted rows too.
    """

    name = "relevance-parity-recorder"

    def __init__(self) -> None:
        self.asked: list[tuple[str, str]] = []      # (org_id, source_object_id)

    def classify(self, ctx, prepared):
        from genios_engine.capture.gate.relevance import RelevanceVerdict
        self.asked.append((ctx.event.org_id, ctx.event.source_object_id))
        return RelevanceVerdict(True, 0.90, disposition="keep", reason="parity_fixture")


class _ParityGmail(ComposioGmailConnector):
    """The SAME connector both doors use, serving one canned page and never touching a network."""

    def __init__(self, message: dict) -> None:
        super().__init__(api_key="", user_id="")
        self._page = {"data": {"messages": [message]}}

    def _execute(self, slug, args):        # a full-message fetch would be a network call
        return {}

    def initial_snapshot(self, cursor=None, limit=50):
        return self._to_batch(self._page)

    def incremental_changes(self, cursor=None, limit=50, since=None):
        return self._to_batch(self._page)


#: Rows are ordered by the SOURCE object they describe, never by `event_id` — the id is minted
#: per row, so ordering by it compares the mail of one door against the attachment of the other
#: and reports a difference that is really just a sort.
_ORDER_BY: dict[str, str] = {
    "source_events": "t.source_object_id",
    "prepared_content": "(select se.source_object_id from source_events se "
                        "where se.event_id = t.event_id)",
    "document_jobs": "(select se.source_object_id from source_events se "
                     "where se.event_id = t.event_id)",
}


def _rows(engine, table: str, org_id: str) -> list[dict]:
    with engine.connect() as c:
        return [dict(r._mapping) for r in
                c.execute(_sql(f"select t.* from {table} t where t.org_id=:o "
                               f"order by {_ORDER_BY[table]}"), {"o": org_id})]


def _comparable(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if k not in _ROW_EXCLUSIONS} for r in rows]


def _field_diff(polled: list[dict], hooked: list[dict]) -> list[str]:
    """Per-FIELD differences, because `assert rows == rows` on a 25-column table prints a
    truncated blob and the reader still does not know which column drifted."""
    out: list[str] = []
    if len(polled) != len(hooked):
        out.append(f"row count: poll={len(polled)} webhook={len(hooked)}")
    for i, (a, b) in enumerate(zip(polled, hooked)):
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                out.append(f"row {i} · {key}: poll={a.get(key)!r} webhook={b.get(key)!r}")
    return out


def _purge(engine, orgs: tuple[str, ...]) -> None:
    """Leave the scratch database exactly as found — the `orgs` rows INCLUDED.

    `tests/conftest.py::_seed_scratch_org` seeds its own tenant only when `orgs` is empty, so a
    parity tenant left behind makes every later run skip that seed and a dozen unrelated files
    fail on a foreign key. A fixture that dirties the database for the next process is a fixture
    that breaks tests it never mentions.
    """
    with engine.begin() as c:
        for org in orgs:
            c.execute(_sql("delete from prepared_content where org_id=:o"), {"o": org})
            c.execute(_sql("delete from document_jobs where org_id=:o"), {"o": org})
            c.execute(_sql("delete from raw_payloads where org_id=:o"), {"o": org})
            c.execute(_sql("delete from event_trace where event_id in "
                           "(select event_id from source_events where org_id=:o)"), {"o": org})
            c.execute(_sql("delete from source_events where org_id=:o"), {"o": org})
            c.execute(_sql("delete from connections where org_id=:o"), {"o": org})
            c.execute(_sql("delete from source_coverage where org_id=:o"), {"o": org})
            c.execute(_sql("delete from parked_events where org_id=:o"), {"o": org})
            c.execute(_sql("delete from l1_sync_runs where org_id=:o"), {"o": org})
            c.execute(_sql("delete from orgs where id=:o"), {"o": org})


@pytest.fixture
def parity_env(monkeypatch):
    """Two tenants, one connection each, the same connector behind both doors."""
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — route parity needs a real Postgres")
    from genios_engine.api import routes as R
    if R._graph is None:
        pytest.skip("graph store not configured")
    engine = R._graph.engine
    poll_org, hook_org = "org_parity_poll", "org_parity_hook"
    _purge(engine, (poll_org, hook_org))
    with engine.begin() as c:
        for org in (poll_org, hook_org):
            c.execute(_sql("insert into orgs (id, name, email) values (:o, :n, :e) "
                           "on conflict (id) do nothing"),
                      {"o": org, "n": "parity", "e": f"{org}@acme.com"})
    hook_conn = Connection(org_id=hook_org, composio_user_id="composio_parity_hook",
                           source_type="gmail")
    R._connections.add(hook_conn)
    monkeypatch.setattr(R, "make_connector_for",
                        lambda conn, **kw: _ParityGmail(ATTACHED))
    # `orgs.email` is UNIQUE, so the two tenants cannot literally share the owner address, and a
    # different owner per tenant would make `visibility_principals` differ for a reason that has
    # nothing to do with the doors. `_mailbox_owner_for` is the ONE helper both doors resolve the
    # owner through, so pinning it keeps the comparison on the question under test: does the
    # webhook door PASS a mailbox owner to the pipeline at all?
    monkeypatch.setattr(R, "_mailbox_owner_for", lambda org_id: MAILBOX_OWNER)
    # The S2 relevance gate is an LLM in any environment that has an Anthropic key, and an LLM
    # asked the same question twice answers differently — this run had it PARK the attachment for
    # one door and DROP it for the other, on the same bytes. A parity test whose expected value is
    # a model's mood measures the model, not the doors. Both doors resolve the gate through this
    # one factory, so pinning it to a deterministic recorder makes the comparison about the
    # wiring and, because the recorder counts calls, also proves the webhook door consults the
    # gate AT ALL — which is defect #2's "no relevance classifier".
    gate = _RecordingRelevance()
    monkeypatch.setattr(R, "make_relevance_classifier", lambda org_id=None: gate)
    yield R, engine, poll_org, hook_org, hook_conn, gate
    _purge(engine, (poll_org, hook_org))


@pytest.mark.pg
@pytest.mark.gate
def test_the_same_message_through_both_doors_lands_identical_rows(parity_env):
    """THE gate criterion, run against real Postgres: poll the message, push the same message,
    compare every row both doors wrote, field for field."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    R, engine, poll_org, hook_org, hook_conn, gate = parity_env

    R._sync_source(poll_org, "gmail", 10)                     # ── door 1: the sweep

    app = FastAPI()                                            # ── door 2: the live push
    app.include_router(R.router)
    body = {"user_id": hook_conn.composio_user_id, "data": {"message": ATTACHED}}
    resp = TestClient(app).post("/webhooks/composio", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("ingested") is True, resp.json()

    for table in ("source_events", "prepared_content", "document_jobs"):
        polled = _comparable(_rows(engine, table, poll_org))
        hooked = _comparable(_rows(engine, table, hook_org))
        assert polled, f"the poll door wrote no {table} rows — the fixture is not exercising it"
        diff = _field_diff(polled, hooked)
        assert not diff, f"{table}: webhook door differs from poll door\n" + "\n".join(diff)


@pytest.mark.pg
@pytest.mark.gate
def test_the_webhook_door_lands_the_attachment_and_the_prepared_text(parity_env):
    """The two named defects, asserted directly so a regression says WHICH one broke."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    R, engine, poll_org, hook_org, hook_conn, gate = parity_env
    app = FastAPI()
    app.include_router(R.router)
    body = {"user_id": hook_conn.composio_user_id, "data": {"message": ATTACHED}}
    assert TestClient(app).post("/webhooks/composio", json=body).status_code == 200

    events = _rows(engine, "source_events", hook_org)
    assert [e["object_type"] for e in events] == ["email_message", "email_attachment"], \
        "DEFECT #1 — the pushed message's attachment must land as its own event"
    prepared = _rows(engine, "prepared_content", hook_org)
    assert prepared, "DEFECT #2 — no prepared_content: S2 has no clean text to extract from"
    mail = next(e for e in events if e["object_type"] == "email_message")
    assert MAILBOX_OWNER in (mail["visibility_principals"] or ()), \
        "DEFECT #2 — no mailbox_owner: the ACL is missing the account that owns the mailbox"


@pytest.mark.pg
@pytest.mark.gate
def test_both_doors_consult_the_relevance_gate_for_every_object(parity_env):
    """"No relevance classifier" was half of defect #2: the always-on lane was the least-guarded
    one. The gate records who asked, so this is the direct question — did the push consult it,
    for the attachment as well as the mail?"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    R, engine, poll_org, hook_org, hook_conn, gate = parity_env
    R._sync_source(poll_org, "gmail", 10)
    app = FastAPI()
    app.include_router(R.router)
    body = {"user_id": hook_conn.composio_user_id, "data": {"message": ATTACHED}}
    assert TestClient(app).post("/webhooks/composio", json=body).status_code == 200

    asked_by = {org: sorted(oid for o, oid in gate.asked if o == org)
                for org in (poll_org, hook_org)}
    assert asked_by[hook_org] == asked_by[poll_org] == ["msg_parity_1", "msg_parity_1::att_p1"]


# ── the wiring itself, so the two doors cannot drift apart again ─────────────────────────────

def _kwargs_capture_event_is_given(module, run) -> set[str]:
    """The keyword names `module` passes to `capture_event`, observed by replacing it."""
    seen: list[set[str]] = []

    def _spy(raw, **kw):
        seen.append(set(kw))
        raise AssertionError("spy — the pipeline is not run here")

    original = module.capture_event
    module.capture_event = _spy
    try:
        run()
    finally:
        module.capture_event = original
    assert seen, "capture_event was never called"
    return seen[0]


def test_the_push_door_hands_the_pipeline_exactly_what_the_sweep_hands_it():
    """THE anti-drift gate. The sweep called `capture_event` with thirteen keywords and the
    webhook route with four; nothing compared the two, so the difference lived in production
    unnoticed. This compares them by OBSERVATION rather than by reading either call site, so a
    keyword added to one door and not the other fails here.

    `sender_known` is passed by both and is a VALUE, not a store: each door resolves it from its
    own resolver, which is why the sets are compared and not the values.
    """
    from genios_engine.capture.acquire import sync_runner
    from genios_engine.capture.connectors import push_ingest
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    obj = _gmail()._to_batch({"data": {"messages": [MESSAGE]}}).objects[0]

    class _OnePage:
        source = "gmail"

        def incremental_changes(self, cursor=None, limit=50, since=None):
            from genios_engine.capture.connectors.base import SourceBatch
            return SourceBatch(objects=[obj], next_cursor=None)

    swept = _kwargs_capture_event_is_given(
        sync_runner,
        lambda: sync_runner.run_sync(_OnePage(), org_id=ORG, connection_id=CONNECTION,
                                     repo=InMemorySourceEventRepository()))
    pushed = _kwargs_capture_event_is_given(
        push_ingest,
        lambda: push_ingest.ingest_pushed_objects(
            (obj,), org_id=ORG, connection_id=CONNECTION,
            wiring=push_ingest.PushIngestWiring(repo=InMemorySourceEventRepository())))
    assert pushed == swept, ("the push door and the sweep must hand the pipeline the same "
                            f"keywords; only-sweep={swept - pushed} only-push={pushed - swept}")


@pytest.mark.parametrize("call, why", [
    ("run_sync", "the sweep"),
    ("backfill_drain", "the full-history drain"),
    ("ingest_pushed_objects", "the real-time webhook"),
])
def test_every_connector_ingest_door_in_the_api_supplies_the_owner_and_the_prepared_store(call, why):
    """A source-level gate over `api/routes.py`, because these two arguments are the ones a new
    call site forgets: without `mailbox_owner` the ACL on the row is built from a smaller
    principal set, and without `prepared_store` there is no clean text for S2 and no offset map
    for an evidence span. Both are invisible at the call site — the row still lands.

    Scoped to the CONNECTOR ingest doors. `/dev/ingest-sample` also calls `capture_event` and is
    deliberately not in this list: it writes to `_demo_repo`, an in-memory store, and is gated
    behind the internal token — it is not a tenant's data.
    """
    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "genios_engine" / "api" / "routes.py"
    tree = ast.parse(src.read_text())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", None) == call]
    assert calls, f"{call} is not called in routes.py — {why} moved and this gate went blind"
    for node in calls:
        keywords = {k.arg for k in node.keywords}
        if call == "ingest_pushed_objects":         # its wiring is one typed argument
            wiring = next(k.value for k in node.keywords if k.arg == "wiring")
            keywords = {k.arg for k in wiring.keywords}
        missing = {"mailbox_owner", "prepared_store"} - keywords
        assert not missing, (f"{call} at routes.py:{node.lineno} ({why}) omits {sorted(missing)}")
