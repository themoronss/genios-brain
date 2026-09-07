"""THE UPLOAD DOOR REACHES L1's PUBLISHER — driven through the HTTP route, not around it.

    pytest tests/capture/test_upload_door_publishes.py -q      (needs GENIOS_TEST_DATABASE_URL)

**The defect this file closes.** `POST /api/org/{org}/upload` captures a file the tenant chose by
hand — a signed contract, a price list, an audit checklist — chunks it and lands every chunk
through `intake.ingest_manual`, the same one door a connector sync uses. It then stopped. The four
things Layer 1 does after capture (file the conflicts, run the tenant's floor, age the lifecycle,
publish what survived) lived inside `api/routes._run_ledger`, which is a `run_sync` hook, and the
upload door does not call `run_sync`. So an uploaded document was captured, its text prepared, and
— with an activated tenant — extracted and SCORED, and then `qualified_signals` held no row for
it. Nothing raised. The most deliberate source a tenant has produced the least evidence.

Two arguments were missing on top of the missing publish, and both are the same mistake one step
earlier: `ingest_manual` was called with no `semantic` lane and no `esqe` bundle, and S4 returns
before detection when `extraction is None` — so there were no signals to publish even if something
had been there to publish them.

**Why the assertions are what they are.** Each one can only be satisfied by one of the three
repairs, so deleting any of them turns this red:

* a row in `qualified_signals` at all  -> the `semantic` lane reached `ingest_manual` (prose
  carries no typed fields; with no S2 there is no extraction, nothing to detect, no signal);
* that row exists rather than a drop   -> `finalize_l1` ran from the upload door;
* `importance_components.baseline_basis` is ORG_HISTORY -> the `esqe` bundle reached it. Without
  it `capture_event` falls through to `OrgBaseline.cold_start`, which prices nothing and reports
  ESTIMATED.

The transport is the only thing standing in. The repository, the payload and prepared stores, the
coverage declaration, the floor, the drop ledger, the lifecycle store and the signal store are all
the production objects `upload_routes` built at import.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import upload_routes
from genios_engine.contracts.signal import SIGNAL_STATES
from genios_engine.platform.auth import AuthCtx, get_auth_ctx
from genios_engine.platform.db import get_engine

pytestmark = pytest.mark.pg

ORG = "org_upload_door"
UPLOADER = "founder@uploaddoor.test"

#: The document's text. One clause, one amount, one date — enough for ALG-15 to detect and for
#: ALG-17 to have a money term to scale against the org's own history.
#: A heading plus one clause. ALL-CAPS because that is what a contract heading looks like and what
#: `documents/chunking.py` detects as one — a bare title-case first line is not a declaration of
#: structure. It is what every span from this chunk must then cite.
SECTION = "PAYMENT TERMS"
DOC = (f"{SECTION}\n"
       "Northwind Ltd master services agreement. The annual fee of $84,000 is payable on "
       "28 March 2026 and the cancellation window closes on 14 March 2026.")

#: The org's priced history, so L1.6.7's baseline is ORG_HISTORY and not a cold start. Nine rows,
#: so the p50 is the fifth.
PRICED: tuple[int, ...] = (1_000_000, 1_500_000, 2_500_000, 3_800_000, 4_500_000,
                           5_500_000, 7_000_000, 9_000_000, 20_000_000)

#: When the priced history happened. Inside L1.6.7-U2's window relative to the upload, and stated
#: as a constant rather than read off a clock so two runs of this file see the same baseline.
HISTORY_AT = datetime.now(timezone.utc) - timedelta(days=30)

_TABLES = ("qualified_signals", "qualification_drops", "signal_lifecycle",
           "publication_rejections", "l1_extraction_results", "prepared_content",
           "raw_payloads", "parked_events", "source_events", "resource_uploads",
           "l1_semantic_activation", "source_coverage", "connections")


def _cite(quote: str) -> list[dict]:
    start = DOC.index(quote)
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


#: What the model says about the chunk. Every claim carries a span into the REAL text, because
#: ALG-08 resolves them against the prepared content and an unverified span degrades the
#: confidence this test then reads.
EXTRACTION = {
    "intent": "inform", "stance": "neutral", "topics": ["contract_renewal"],
    "entity_mentions": [{"surface_form": "Northwind Ltd", "entity_type": "organization",
                         "evidence": _cite("Northwind Ltd master services agreement"),
                         "confidence_bp": 9000}],
    "amounts": [{"minor_units": 8_400_000, "currency": "USD", "as_written": "$84,000"}],
    "dates_mentioned": [{"as_written": "28 March 2026", "evidence": _cite("28 March 2026")}],
}


class _Result:
    def __init__(self, payload: dict) -> None:
        self.parsed = payload
        self.raw = json.dumps(payload, sort_keys=True)
        self.input_tokens, self.output_tokens = 700, 150
        self.model = "fake-model-upload-door"
        self.cached, self.ok, self.error = False, True, None


class _LLM:
    """One canned extraction for every chunk. The corpus is one short document."""

    model = "fake-model-upload-door"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def call(self, prompt: str, *, max_tokens: int = 4096):
        self.calls.append(prompt)
        return _Result(EXTRACTION)


@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the upload-door probe needs real Postgres")
    return live_db_url


def _wipe(conn) -> None:
    for table in _TABLES:
        conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
    conn.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def seeded(pg_url):
    """An ACTIVATED tenant with a priced history — the state a pilot org is in, and the only
    state in which an upload can produce a signal at all."""
    engine = get_engine(pg_url)
    with engine.begin() as conn:
        _wipe(conn)
        # Every NOT NULL column without a default, read off the live schema — an org row seeded
        # by a hardcoded column list breaks the day the table gains a required column, which is a
        # failure about this fixture and not about the door it is probing.
        names = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'"))]
        cols = ["id"] + names
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                          f"({', '.join(':' + c for c in cols)})"),
                     {"id": ORG, **{n: "scratch" for n in names}})
        conn.execute(text("update orgs set email = :e where id = :o"), {"e": UPLOADER, "o": ORG})
        conn.execute(text(
            "insert into l1_semantic_activation (org_id, enabled_at, enabled_by, notes) "
            "values (:o, now(), 'test', 'upload door probe') on conflict (org_id) do nothing"),
            {"o": ORG})
        # The history is a JOIN — `baseline_reader._HISTORY_SQL` reads amounts out of
        # `l1_extraction_results` and its instant off `source_events` — so an extraction with no
        # landed event contributes nothing. Seeding only half of it is how a fixture reports a
        # cold start and blames the code under test.
        for index, minor in enumerate(PRICED):
            event_id = f"evt_seed_{ORG}_{index}"
            conn.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, "
                "object_type, source_object_id, dedup_key, actor, occurred_at) values "
                "(:e, :o, 'con_seed', 'gmail', 'email_message', :e, :e, cast('{}' as jsonb), "
                ":at)"), {"e": event_id, "o": ORG, "at": HISTORY_AT})
            conn.execute(text(
                "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
                "input_tokens, output_tokens, model_snapshot) "
                "values (:k, :o, :e, cast(:out as jsonb), 10, 10, 'seed')"),
                {"k": f"seed_{ORG}_{index}", "o": ORG, "e": event_id,
                 "out": json.dumps({"amounts": [{"minor_units": minor, "currency": "USD",
                                                 "as_written": f"${minor // 100:,}"}]})})
    yield engine
    with engine.begin() as conn:
        _wipe(conn)


@pytest.fixture
def client(seeded, monkeypatch):
    llm = _LLM()
    real_lane = upload_routes.make_semantic_lane
    monkeypatch.setattr(upload_routes, "make_semantic_lane",
                        lambda org_id, **kw: real_lane(org_id, llm=llm, **kw))
    app = FastAPI()
    app.include_router(upload_routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id=UPLOADER)
    test_client = TestClient(app)
    test_client.llm = llm
    return test_client


def _upload(client) -> dict:
    response = client.post(f"/api/org/{ORG}/upload",
                           files={"file": ("msa.txt", DOC.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()


def _signals(engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select signal_type, importance_bp, importance_components, evidence_refs, state, "
            "coverage_ready from qualified_signals where org_id = :o"), {"o": ORG}).fetchall()
    return [dict(r._mapping) for r in rows]


def test_an_uploaded_document_reaches_qualified_signals(client, seeded):
    """The whole point: the most deliberate source a tenant has must leave a row behind."""
    body = _upload(client)
    assert body["chunks"] >= 1
    assert client.llm.calls, "the semantic lane never reached the upload door — S2 was not called"
    rows = _signals(seeded)
    assert rows, ("the upload door captured, extracted and scored and published nothing: "
                  "finalize_l1 is not wired into upload_resource")
    # Not "every row is active": ALG-19 runs BEFORE publication and a signal whose stated clock
    # has already run out is stored `expired`, which is the lifecycle working rather than a
    # failure. What must hold is that every state is one ALG-19 can produce — a publisher's
    # guess would show up here as a value outside the set.
    assert all(row["state"] in SIGNAL_STATES for row in rows)


def test_the_published_signal_carries_its_receipt_and_the_orgs_own_baseline(client, seeded):
    """Two facts, each reachable through exactly one of the two threaded arguments."""
    _upload(client)
    rows = _signals(seeded)
    assert rows
    row = rows[0]
    assert row["evidence_refs"], "V-4 published a signal with no receipt"
    components = row["importance_components"] or {}
    assert components.get("baseline_basis") == "org_history", (
        "the esqe bundle did not reach the upload door — ALG-17 priced this against a cold start")


def test_an_uploaded_chunk_cites_the_section_it_came_from(client, seeded):
    """L1.3.4-U5 · the upload door is the one door whose events are CHUNKS of a document, so it is
    the door that must state which part of it each chunk was. `chunk_text` dropped the offsets and
    the heading because the door "has no use for offsets yet" — which stopped being true the
    moment a receipt had to be checkable by a person."""
    _upload(client)
    with seeded.connect() as conn:
        refs = conn.execute(text("select evidence_refs from qualified_signals where org_id = :o"),
                            {"o": ORG}).fetchall()
    spans = [span for (row,) in refs for span in (row or [])]
    assert spans, "no receipt to inspect"
    # A plain-text upload has no PAGES — and says so, rather than claiming page 1 — while the
    # section is whatever the chunker detected, which for this one-heading document is its title.
    assert all(span.get("page") is None for span in spans)
    assert {span.get("section") for span in spans} == {SECTION}


def test_a_second_upload_of_the_same_bytes_publishes_no_second_copy(client, seeded):
    """Idempotence at the seam, not only at the door: the dedup ledger refuses the re-land and
    the publisher is content-addressed, so a re-upload cannot double a tenant's signal count."""
    _upload(client)
    first = len(_signals(seeded))
    _upload(client)
    assert len(_signals(seeded)) == first
