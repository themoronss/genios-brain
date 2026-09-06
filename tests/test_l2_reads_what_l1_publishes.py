"""THE L1 -> L2 SEAM, driven on a real Postgres: does Layer 2 read what Layer 1 published?

Every wave of Layer 1 ends in two durable artifacts — an extraction filed in
`l1_extraction_results` and a judged signal filed in `qualified_signals` — and until this file
existed nothing on a request path read either of them. The two halves of that failure are
different bugs wearing one name:

  (a) `context/runner._pull` EXCLUDED every event carrying an `l1_extraction_results` row. That
      guard was written when Layer 2 was the ONLY writer of that table (it still writes it, via
      `GraphStore.cache_set`, with a null `profile_id`), so it read as "L2 already extracted
      this". Layer 1 v2 now writes the same table for every event it extracts, with a real
      `profile_id` — so on the day activation is switched on, the guard would silence Layer 2 for
      exactly the events Layer 1 understood best. Turning activation on would have made the
      product WORSE, not incomplete, and nothing would have errored.

  (b) `context/situation_bso.build_business_situation` stamped `importance_bp =
      DEFAULT_IMPORTANCE_BP` — a constant — over the score ALG-17 had just computed and the
      publisher had just stored. That is the exact defect W7 exists to fix (193 of 223 signals
      sharing one score), reappearing one layer up at the seam into Layer 3.

Both are driven here through production entry points only: `run_sync` (the sync door) with
`api/routes._run_ledger` as its ledger hook, `context/runner.process_pending` (the drain) and
`reason/domain_shadow.shadow_compile` (the L2 -> L3 compile the reasoning runner calls). Nothing
in this file constructs a scorer, a publisher, a BSO or a signal row.

Real Postgres: skips without GENIOS_TEST_DATABASE_URL, the same gate every other L2 test has.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import text

from genios_engine.capture import pipeline as P
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
from genios_engine.capture.payload_store import PostgresRawPayloadStore
from genios_engine.capture.prepared_store import PostgresPreparedContentStore
from genios_engine.capture.semantic.cache import PostgresExtractionCache
from genios_engine.context.runner import process_pending
from genios_engine.platform.config import get_settings

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
OWNER = "founder@genios.test"

BODY = ("Hi — legal signed off, so we can move forward with the $84,000 annual contract. "
        "I still need Finance to confirm, but send the paperwork over and we will "
        "counter-sign this week.")


# =============================================================================================
# Doubles for the two things a test may not reach: a mailbox and a model.
# =============================================================================================
@dataclass
class _Result:
    """Field-for-field the shape both LLM clients return. Duck-typed on purpose — L1's extractor
    and L2's extractor take different clients and neither may learn its result type here."""

    parsed: dict[str, Any]
    raw: str = "{}"
    input_tokens: int = 10
    output_tokens: int = 20
    model: str = "fake-model-1"
    cached: bool = False
    ok: bool = True
    error: str | None = None


class _FakeLLM:
    """One canned answer, repeated. Both lanes share the class and neither shares an instance,
    so a call count read off one lane cannot be the other lane's."""

    model = "fake-model-1"

    def __init__(self, parsed: dict[str, Any]) -> None:
        self._parsed = parsed
        self.calls = 0

    @staticmethod
    def content_hash(material: str) -> str:
        import hashlib
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def call(self, prompt: str, *, max_tokens: int = 4096) -> _Result:
        self.calls += 1
        return _Result(parsed=self._parsed, raw=json.dumps(self._parsed, sort_keys=True))


class _Mailbox:
    """A connector that hands `run_sync` one email. The narrowest real `SourceConnector`."""

    source = "gmail"

    def __init__(self, object_id: str, thread_id: str) -> None:
        self._object_id, self._thread_id = object_id, thread_id

    def validate_connection(self) -> bool:
        return True

    def _objects(self) -> list[RawObject]:
        return [RawObject(source="gmail", object_type="email_message",
                          source_object_id=self._object_id, occurred_at=NOW,
                          actor_email="priya@northwind.test", actor_type="external_contact",
                          recipients=(OWNER,), parent_object_id=self._thread_id,
                          raw={"subject": "Annual contract", "body": BODY})]

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)


def _l1_payload() -> dict[str, Any]:
    """What Layer 1's extractor returns for BODY — an amount, an entity, a decision and a
    dependency, each citing a real substring so ALG-08 can verify the span."""
    def cite(quote: str) -> list[dict]:
        start = BODY.index(quote)
        return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]

    return {
        "intent": "commit", "stance": "positive",
        "entity_mentions": [{"surface_form": "Finance", "entity_type": "organization",
                             "evidence": cite("Finance"), "confidence_bp": 8800}],
        "amounts": [{"minor_units": 8_400_000, "currency": "USD", "as_written": "$84,000"}],
        "decision_states": [{"subject": "annual contract", "state": "pending",
                             "blocked_on": "Finance confirmation",
                             "evidence": cite("we can move forward with the $84,000 annual "
                                              "contract"),
                             "confidence_bp": 8000}],
        "dependencies": [{"blocker": "Finance", "blocked": "us",
                          "dependency_type": "approval",
                          "evidence": cite("I still need Finance to confirm"),
                          "confidence_bp": 7900}],
    }


def _l2_payload() -> dict[str, Any]:
    """What Layer 2's own extractor returns for the same mail. The OLD path is still live until
    G10, so the drain must keep working exactly as it did."""
    return {
        "relevance": 0.9, "noise_type": "none", "domains": ["sales"],
        "entity_mentions": [
            {"type": "person", "name": "Priya", "email": "priya@northwind.test",
             "evidence_text": "Priya"},
            {"type": "company", "name": "Northwind", "email": None,
             "evidence_text": "annual contract"}],
        "fact_candidates": [
            {"subject": "Priya", "field": "deal_value", "value": "$84,000",
             "evidence_text": "$84,000 annual contract"}],
        "commitments": [{"text": "send the paperwork over", "owner": "them",
                         "evidence_text": "send the paperwork over"}],
        "questions": [],
        "observations": [{"kind": "budget_approved", "evidence_text": "legal signed off"}],
    }


# =============================================================================================
# Fixtures — one scratch org per test, and the production stores pointed at the scratch DB.
# =============================================================================================
@pytest.fixture
def url() -> str:
    value = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres seam tests skipped")
    return value


def _fresh_org(store, org: str) -> None:
    """A clean tenant for this run, erased through `account_routes._wipe` — the real /reset loop.

    The scratch database outlives one pytest process, and every table on this path is
    content-addressed or dedup-keyed: a second run of the same file would land on `duplicate` at
    the landing stage and prove nothing. Wiping through the production erasure list rather than a
    hand-written DELETE also means a table this seam writes but that list has forgotten shows up
    here as a stale row instead of as a tenant's quotes surviving their own deletion.
    """
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as conn:
        _wipe(conn, org)
        # NOT in `_ORG_SCOPED_TABLES`: migration 0037 says these are erased "by schema, not by
        # an application list", which is true of an account DELETION (the org FK cascades) and
        # not of `/reset`, which runs that list and never deletes the org. Deleted here so this
        # file starts from an empty graph either way. Reported rather than fixed —
        # `api/account_routes.py` is not this seam's file.
        for tbl in ("context_correlation_members", "context_situations", "context_correlations"):
            conn.execute(text(f"delete from {tbl} where org_id=:o"), {"o": org})
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": org}
        for r in reqd:
            cols.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else False if dt == "boolean"
                                   else OWNER if "email" in r.column_name
                                   else "{}" if dt in ("json", "jsonb") else org)
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                          "on conflict (id) do nothing"), vals)


def _capture(url: str, pg_store, org: str, monkeypatch, *, signal_store=None,
             cache=True, object_id="msg_seam_1") -> Any:
    """ONE email through the real sync door, with `api/routes._run_ledger` as the ledger hook.

    That hook is what every `run_sync` caller in the HTTP layer passes, and it is where L1.6.8's
    floor, ALG-19's lifecycle and L1.6.10's publication run. Only the tenant-scoped STORES are
    redirected at the scratch database; every unit on the path is the production one.
    """
    from genios_engine.api import routes
    from genios_engine.capture.esqe import qualification as Q

    _fresh_org(pg_store, org)
    monkeypatch.setattr(routes, "_graph", pg_store, raising=False)
    monkeypatch.setattr(routes, "_floor_store", Q.InMemoryFloorStore({org: 1}), raising=False)
    monkeypatch.setattr(routes, "_drop_ledger", Q.InMemoryDropLedger(), raising=False)
    monkeypatch.setattr(routes, "_lifecycle_store", None, raising=False)
    if signal_store is not None:
        monkeypatch.setattr(routes, "_signal_store", signal_store, raising=False)

    lane = P.SemanticLane(llm=_FakeLLM(_l1_payload()), eval_time=NOW,
                          cache=PostgresExtractionCache(url) if cache else None)
    return run_sync(_Mailbox(object_id, f"thr_{object_id}"), org_id=org,
                    connection_id=f"con_{org}", source="gmail", mode="backfill",
                    repo=PostgresSourceEventRepository(url),
                    payload_store=PostgresRawPayloadStore(url, get_settings().crypto_key),
                    prepared_store=PostgresPreparedContentStore(url),
                    mailbox_owner=OWNER, semantic=lane,
                    esqe=P.EsqeStage(eval_time=NOW, org_domains=("genios.test",)),
                    run_ledger=routes._run_ledger)


def _drain(pg_store, org: str) -> dict:
    return process_pending(org_id=org, store=pg_store, llm=_FakeLLM(_l2_payload()),
                           crypto_key=get_settings().crypto_key)


# =============================================================================================
# (a) THE DRAIN — an event Layer 1 extracted must still reach Layer 2
# =============================================================================================
def test_an_event_layer_1_extracted_still_reaches_the_layer_2_drain(url, pg_store, monkeypatch):
    """**THE ACTIVATION GATE.** `_pull` excluded every event with an `l1_extraction_results`
    row. Layer 1 v2 writes that table for everything it extracts, so activation would have
    SILENCED Layer 2 rather than improved it — no error, no log line, just a drain that finds
    nothing and a graph that stops growing.

    Nothing here inserts a cache row by hand: the row is written by L1's own
    `PostgresExtractionCache` on the sync path, which is the only writer whose behaviour matters.
    """
    org = "seam_pull_l1"
    summary = _capture(url, pg_store, org, monkeypatch)
    assert summary.emitted == 1, f"L1 emitted nothing to drain: {summary}"

    with pg_store.engine.connect() as conn:
        rows = conn.execute(text(
            "select event_id, profile_id from l1_extraction_results where org_id=:o"),
            {"o": org}).all()
    assert rows and all(r.profile_id for r in rows), (
        "Layer 1 filed no extraction with a profile — the premise of this test is gone")

    # The onboarding progress bar reads the same queue through `api/routes._pending_count`. It
    # carried its own copy of this filter, so it reported a finished sync for a tenant whose
    # drain had not started. Asserted BEFORE the drain, which is the only moment the two can
    # disagree.
    from genios_engine.api import routes
    assert routes._pending_count(org) >= 1, (
        "the progress count says nothing is pending while the drain has work")

    out = _drain(pg_store, org)

    assert out["processed"] >= 1, (
        "the drain skipped an event Layer 1 had extracted — activation silences Layer 2")
    with pg_store.engine.connect() as conn:
        nodes = conn.execute(text("select count(*) from graph_nodes where org_id=:o"),
                             {"o": org}).scalar()
    assert nodes >= 1, "the event reached the drain but built no graph"

    # ...and exactly once. Relaxing the extraction-cache guard must not cost the idempotency it
    # was standing in for: `l2_processing_runs` is the ledger that actually owns that job, and a
    # drain that re-read this event would pay the model again on every sweep for ever.
    assert _drain(pg_store, org)["processed"] == 0, (
        "the drain re-processed an event it had already finished")


def test_the_drain_still_skips_what_layer_2_itself_already_extracted(url, pg_store, monkeypatch):
    """The OTHER half of the same guard, and why it cannot simply be deleted: Layer 2 writes
    `l1_extraction_results` too, through `GraphStore.cache_set`, and re-draining an event it has
    already extracted pays the model twice for one message.

    The row here is written by that real writer, not by a hand-rolled insert, so the
    discriminator is proven against both producers rather than against a fixture's idea of them.
    """
    org = "seam_pull_l2"
    summary = _capture(url, pg_store, org, monkeypatch, cache=False, object_id="msg_seam_2")
    assert summary.emitted == 1

    with pg_store.engine.connect() as conn:
        event_id = conn.execute(text(
            "select event_id from source_events where org_id=:o"), {"o": org}).scalar()
    pg_store.cache_set(processing_key=f"l2test:{event_id}", org_id=org, event_id=event_id,
                       output={"already": "extracted"}, input_tokens=1, output_tokens=1,
                       model="fake-model-1")

    out = _drain(pg_store, org)

    assert out["processed"] == 0, (
        "Layer 2 re-extracted a message it had already paid to read — the idempotency half of "
        "the guard was lost")


# =============================================================================================
# (b) THE SEAM INTO LAYER 3 — the situation must carry the score Layer 1 computed
# =============================================================================================
def test_the_situation_carries_layer_1s_importance_not_a_constant(url, pg_store, monkeypatch):
    """**THE TEST THAT COUNTS.** One email is captured through the real sync door, so a real
    `qualified_signals` row is stored with ALG-17's real score. The real drain then builds the
    graph, the correlation and the situation, and the real L2 -> L3 compile
    (`domain_shadow.shadow_compile`, which `reason/runner` calls) produces the BSO.

    The assertion is that the BSO carries the score Layer 1 stored — not `DEFAULT_IMPORTANCE_BP`,
    and not a number this layer re-derived for itself.
    """
    from genios_engine.capture.esqe.signal_store import PostgresSignalStore
    from genios_engine.context.situation_bso import DEFAULT_IMPORTANCE_BP
    from genios_engine.reason import domain_shadow

    org = "seam_importance"
    store = PostgresSignalStore(url)
    _capture(url, pg_store, org, monkeypatch, signal_store=store, object_id="msg_seam_3")

    published = store.list(org)
    assert published, "Layer 1 published no qualified signal — nothing for Layer 2 to read"
    expected = max(r.importance_bp for r in published)

    out = _drain(pg_store, org)
    assert out["situation_rows"] >= 1, f"the drain built no situation to compile: {out}"

    seen: list[Any] = []
    real = domain_shadow.build_business_situation

    def _spy(**kwargs):
        bso = real(**kwargs)
        seen.append(bso)
        return bso

    monkeypatch.setattr(domain_shadow, "build_business_situation", _spy)
    domain_shadow.shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=False)

    assert seen, "the L2 -> L3 compile produced no business situation object"
    assert expected != DEFAULT_IMPORTANCE_BP, (
        "this email happens to score exactly the constant, so the assertion below would pass "
        "against the defect — change the fixture, never the assertion")
    carried = [b for b in seen
               if b.metadata["importance_source"] == "l1_qualified_signals"]
    assert carried, (
        f"every situation carried {sorted({b.importance_bp for b in seen})} from "
        f"{sorted({b.metadata['importance_source'] for b in seen})} while Layer 1 had stored "
        f"{expected} — Layer 2 is not reading qualified_signals")
    assert all(b.importance_bp == expected for b in carried)

    # ... and the rest of the row travels with the score, because a number nobody can explain is
    # a ranking nobody can argue with.
    top = carried[0]
    assert all(sid.startswith("sig_") for sid in top.signal_ids), (
        f"the BSO still names event ids, not the qualified signal ids: {top.signal_ids}")
    assert {r.signal_id for r in published} >= set(top.signal_ids)
    assert any(e.get("source") == "l1_qualified_signal" for e in top.evidence), (
        "the situation carries none of Layer 1's verified receipts")
    assert top.metadata["importance_version"] == "alg17-v1"
    assert top.metadata["importance_components"], "the score arrived with no explanation"
    assert top.metadata["l1_scored_count"] >= 1

    # THE FALLBACK, on the same real run: the period-review situations this drain also builds
    # correlate no captured event, so no qualified signal covers them. They must still compile —
    # on the neutral default, and saying so.
    fallback = [b for b in seen if b.metadata["importance_source"] == "default"]
    assert fallback, "no situation exercised the pre-activation path in this run"
    assert all(b.importance_bp == DEFAULT_IMPORTANCE_BP for b in fallback)


# =============================================================================================
# SELECTION — which of a situation's signals sets its importance, and which may not
# =============================================================================================
def _stored_row(**over: Any):
    """One `qualified_signals` row, written through the real store. Constructed here on purpose:
    the WIRING is proven above, and these cases are about rules a captured email cannot reach —
    a superseded signal, a signal the floor could not score, a tie."""
    from genios_engine.capture.esqe.signal_store import QualifiedSignalRow

    base: dict[str, Any] = dict(
        signal_id="sig_" + "0" * 32, org_id="seam_select", event_id="evt_select",
        trace_id="evt_select", signal_type="decision_pending", importance_bp=5000,
        importance_version="alg17-v1", confidence_bp=7000, extraction_ref="l1x_select",
        state="active", occurred_at=NOW,
        evidence_refs=({"quote": "we can move forward", "source_ref": "prepared_content:x",
                        "start_offset": 0, "end_offset": 19, "verified": True},),
        importance_components={"money_bp": 4000}, conflict_ids=())
    base.update(over)
    return QualifiedSignalRow(**base)


#: (name, rows as (importance_bp, importance_version, state), expected importance, expected count)
_SELECTION_CASES = [
    ("the highest scored signal sets it",
     ((1200, "alg17-v1", "active"), (8800, "alg17-v1", "active")), 8800, 2),
    ("a superseded signal does not — ALG-19 already ruled on it",
     ((1200, "alg17-v1", "active"), (9900, "alg17-v1", "superseded")), 1200, 1),
    ("nor does an expired one",
     ((1200, "alg17-v1", "active"), (9900, "alg17-v1", "expired")), 1200, 1),
    ("an UNSCORED signal is an absence, not a zero",
     ((0, "unscored", "active"), (3300, "alg17-v1", "active")), 3300, 2),
    ("a tie is broken by signal id, never left to row order",
     ((7000, "alg17-v1", "active"), (7000, "alg17-v1", "active")), 7000, 2),
]


@pytest.mark.parametrize("name,rows,expected,count",
                         _SELECTION_CASES, ids=[c[0] for c in _SELECTION_CASES])
def test_which_signal_sets_a_situations_importance(url, pg_store, name, rows, expected, count):
    from genios_engine.capture.esqe.signal_store import PostgresSignalStore
    from genios_engine.context.situation_bso import gather_l1_signals

    org, correlation = "seam_select", f"corr_{abs(hash(name)):x}"
    _fresh_org(pg_store, org)
    store = PostgresSignalStore(url)
    stored = []
    for i, (bp, version, state) in enumerate(rows):
        event_id = f"evt_select_{i}"
        stored.append(_stored_row(signal_id=f"sig_{i}{'a' * 31}", event_id=event_id,
                                  trace_id=event_id, importance_bp=bp,
                                  importance_version=version, state=state))
        with pg_store.engine.begin() as conn:
            conn.execute(text(
                "insert into context_correlation_members (org_id, correlation_id, event_id) "
                "values (:o,:c,:e) on conflict do nothing"),
                {"o": org, "c": correlation, "e": event_id})
    assert store.put(stored) == len(stored), "the store refused the fixture rows"

    with pg_store.engine.connect() as conn:
        l1 = gather_l1_signals(conn, org, correlation)

    assert l1 is not None
    assert l1.importance_bp == expected, name
    assert l1.signal_count == count, "a state filter leaked a signal into the count"
    assert l1.evidence and all(e["source"] == "l1_qualified_signal" for e in l1.evidence)


def test_a_situation_whose_signals_are_all_unscored_reports_no_importance(url, pg_store):
    """`importance_bp = 0` on an unscored row means "nobody measured this", and the floor lets
    it through precisely so an unmeasurable signal is not silently refused. Reading that 0 as a
    score would rank every unmeasured signal below every measured one."""
    from genios_engine.capture.esqe.signal_store import PostgresSignalStore
    from genios_engine.context.situation_bso import gather_l1_signals

    org, correlation = "seam_select", "corr_all_unscored"
    _fresh_org(pg_store, org)
    with pg_store.engine.begin() as conn:
        conn.execute(text(
            "insert into context_correlation_members (org_id, correlation_id, event_id) "
            "values (:o,:c,'evt_u') on conflict do nothing"), {"o": org, "c": correlation})
    PostgresSignalStore(url).put([_stored_row(event_id="evt_u", trace_id="evt_u",
                                              importance_bp=0, importance_version="unscored",
                                              importance_components={})])

    with pg_store.engine.connect() as conn:
        l1 = gather_l1_signals(conn, org, correlation)

    assert l1 is not None and l1.signal_count == 1
    assert l1.importance_bp is None, "an unscored signal was read as a score of zero"
    assert l1.scored_count == 0


def test_a_situation_with_no_qualified_signal_reads_as_the_absence_it_is(url, pg_store):
    """The pre-activation path, and the reason this is a READ that PREFERS `qualified_signals`
    rather than a replacement for the old one: a tenant whose signals were never published must
    compile exactly as before."""
    from genios_engine.context.situation_bso import gather_l1_signals

    _fresh_org(pg_store, "seam_select")
    with pg_store.engine.connect() as conn:
        assert gather_l1_signals(conn, "seam_select", "corr_nothing_here") is None
        assert gather_l1_signals(conn, "seam_select", None) is None


# =============================================================================================
# CONTENT ADDRESSING — the score may re-mint a package; the clock beside it may not
# =============================================================================================
def _bso_with(components: Mapping[str, Any], *, importance_bp: int = 8100):
    from genios_engine.context.domain_spec import spec_for
    from genios_engine.context.situation_bso import L1Signals, build_business_situation

    situation = {"situation_id": "sit_addr_1", "situation_type": spec_for("sales").type_for(
        "company"), "domain": "sales", "status": "active", "correlation_id": "corr_addr",
        "confidence_overall": 82, "coverage": 70, "first_seen_at": NOW, "last_seen_at": NOW,
        "anchor_node_id": "account_1", "anchor_name": "Acme", "anchor_type": "company"}
    return build_business_situation(
        org_id="org_addr", situation=situation, signal_ids=["evt_addr"],
        evidence=[{"event_id": "evt_addr", "source": "gmail"}], trace_id="trace_addr",
        l1=L1Signals(signal_ids=("sig_addr",), importance_bp=importance_bp,
                     importance_version="alg17-v1", components=components,
                     evidence=({"quote": "q", "source_ref": "prepared_content:x",
                                "start_offset": 0, "end_offset": 1, "verified": True,
                                "source": "l1_qualified_signal"},),
                     signal_count=1, scored_count=1))


def test_a_resweep_at_a_new_instant_does_not_mint_a_new_package():
    """`importance_components` carries the sweep's frozen instant, and `to_semantic_dict` hashes
    `metadata`. Re-sweeping an unchanged tenant re-publishes the same signal under the same
    content-addressed id with a NEW `eval_time` — so copying the components in whole would mint
    a fresh ~238 kB `expertise_packages` row per situation per sweep. That is not hypothetical:
    the trace-id version of this bug put 995 MB on one tenant's database and took the project
    read-only.
    """
    august = _bso_with({"weighted_bp": 8100, "baseline_used": 1,
                        "eval_time": "2026-08-08T12:00:00+00:00"})
    september = _bso_with({"weighted_bp": 8100, "baseline_used": 1,
                           "eval_time": "2026-09-08T12:00:00+00:00"})

    assert august.to_semantic_dict() == september.to_semantic_dict()
    assert "eval_time" not in august.metadata["importance_components"]
    assert august.metadata["importance_components"]["weighted_bp"] == 8100, (
        "the explanation was thrown away with the clock")


def test_a_score_that_actually_moved_does_mint_a_new_package():
    """The other direction, and the reason the whole metadata block is not simply dropped: a
    situation whose importance changed IS a different situation to Layer 3, and a content address
    that ignored the score would serve last month's ranking for ever."""
    before = _bso_with({"weighted_bp": 8100}, importance_bp=8100)
    after = _bso_with({"weighted_bp": 2200}, importance_bp=2200)

    assert before.to_semantic_dict() != after.to_semantic_dict()
