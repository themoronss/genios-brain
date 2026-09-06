"""THE SWEEP'S THREE LANES, PROVED ON THE ONE PATH A REAL TENANT'S MAIL TRAVELS.

    pytest tests/capture/test_sweep_lanes_wired.py -q

`api/routes.run_maintenance_sweep` is what `platform/scheduler._tick` calls every tick, and it is
therefore the only function that ingests a live tenant's mail without a human pressing anything.
Through `run_sync_sweep` it hands `run_sync` three per-org bundles — `esqe`, `semantic` and
`structured` — and until this file existed a reviewer could DELETE ALL THREE ARGUMENTS and the
whole suite stayed green. That is the shape of defect this build has now shipped six times: a
unit written, unit-tested, proved correct, and never actually reached from production.

Two neighbouring files look like they close it and do not:

* `tests/capture/test_g7_g8_g10_gates.py` drives `api/routes._sync_connection` — a DIFFERENT call
  site with its own copy of the three arguments. Deleting them from the sweep leaves every gate in
  that file green.
* `tests/capture/acquire/test_scheduler_wired.py` drives `run_sync_sweep` for real, but with
  `_graph`, `_semantic_lane_for` and every optional store patched to `None`: it asks which
  connections were polled, never what the lanes produced.

So this file drives `run_maintenance_sweep()` itself, against real Postgres, with the PROVIDER and
the MODEL as the only things standing in, and asserts on rows read back out of `qualified_signals`.

TWO TENANTS, BECAUSE THAT IS THE STATE THE PRODUCT IS ACTUALLY IN.
`l1_semantic_activation` ships empty, so `_semantic_lane_for` answers `None` for almost every org
— and `structured_context` falls back to the SEMANTIC lane's zone and discovery store whenever one
is wired. A single activated org would therefore hide the deletion of `structured=` behind the
semantic bundle. The sweep is a cross-org loop, so this uses the two tenants the loop really has:

* an ACTIVATED org with a mailbox — prose, the S2 lane, the org's own priced history;
* an UNACTIVATED org with a CRM — a typed deal, no model, and nothing but the `structured`
  argument standing between its close date and UTC.

Each assertion is anchored to a value that can only arrive through one of the three arguments:

* **semantic** — the EMAIL becomes a qualified signal at all. Prose carries no typed fields, so
  with no S2 lane there is no extraction, nothing to detect, and no row.
* **esqe** — that signal's `entity_standing` is `mission_critical`, a fact about the ORG's
  baseline (`org_mission_critical_entities`, ALG-17 term 4 rung 1). Without the bundle
  `capture_event` falls through to `OrgBaseline.cold_start`, which knows nobody and prices
  nothing, and the same counterparty ranks `first_seen` against an ESTIMATED baseline.
* **structured** — the DEAL's `closedate` is resolved in the ORG's IANA zone, and ALG-19 computes
  `expires_at` from that stated date. The CRM tenant is on `Pacific/Kiritimati` (UTC+14), so its
  end-of-day lands at 09:59:59Z. With no bundle and no semantic lane to borrow from, the lane
  defaults to UTC and every stated date lands 14 hours later, at 23:59:59Z.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.platform.db import get_engine

pytestmark = pytest.mark.pg

# =============================================================================================
# The frozen world. No clock anywhere: every instant below is a constant or derived from one.
# =============================================================================================
ORG_MAIL = "org_sweep_lanes_mail"
ORG_CRM = "org_sweep_lanes_crm"
CONN_MAIL = "con_sweep_lanes_gmail"
CONN_CRM = "con_sweep_lanes_hubspot"
OWNER_MAIL = "founder@sweeplanes.test"
OWNER_CRM = "ops@sweeplanes-crm.test"

#: UTC+14 — the offset furthest from UTC, so "which zone resolved this date" is legible in the
#: stored instant rather than a rounding argument.
ORG_ZONE = "Pacific/Kiritimati"

SWEEP_NOW = datetime(2026, 3, 16, 0, 0, tzinfo=timezone.utc)

#: The counterparty the mail tenant DECLARED mission-critical (migration 0091). A judgement, not
#: an observation, so it is reachable only through the org baseline the `esqe` bundle carries.
VENDOR = "Northwind Ltd"

#: The deal's stated close date, as HubSpot states it — a bare calendar day, which is exactly the
#: shape whose meaning depends on a zone.
CLOSE_DATE = "2026-03-31"

#: The mail org's priced history: nine contracts, so the p50 is the fifth ($45,000). Seeded so the
#: baseline the production factory reads is visibly ORG_HISTORY and not a cold start.
PRICED_HISTORY: tuple[tuple[int, str], ...] = (
    (1_000_000, "Aperture Labs"), (1_500_000, "Blackwood"), (2_500_000, "Cyberdyne"),
    (3_800_000, "Dunder Mifflin"), (4_500_000, "Encom"), (5_500_000, "Frobozz"),
    (7_000_000, "Gringotts"), (9_000_000, "Hyperion"), (20_000_000, VENDOR))

_PROSE = (f"{VENDOR} annual contract renewal: the $84,000 fee is due and the cancellation "
          f"window closes on 28 March 2026.")

#: Every org-scoped table this probe writes to, wiped either side of the run so two consecutive
#: runs of this file see the same database.
_TABLES = ("qualified_signals", "qualification_drops", "signal_lifecycle",
           "publication_rejections", "l1_extraction_results", "prepared_content",
           "raw_payloads", "parked_events", "unclassified_observations", "source_events",
           "l2_processing_runs", "graph_facts", "graph_nodes", "cards", "llm_costs",
           "l1_sync_runs", "source_coverage", "l1_semantic_activation", "sync_cursors",
           "org_qualification_floors", "qualification_floor_changes",
           "org_mission_critical_entities", "connections")


def _cite(quote: str) -> list[dict]:
    start = _PROSE.index(quote)
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


#: What the model says about the email. The entity is cited with the whole CLAUSE rather than the
#: bare name: `Money` is the one claim type C-02 gives no evidence list of its own, so a
#: money-anchored signal's receipt is the literal appearing inside another claim's quote.
EMAIL_EXTRACTION = {
    "intent": "inform", "stance": "neutral", "topics": ["contract_renewal"],
    "entity_mentions": [{"surface_form": VENDOR, "entity_type": "organization",
                         "evidence": _cite(f"{VENDOR} annual contract renewal: the $84,000 fee"),
                         "confidence_bp": 9000}],
    "amounts": [{"minor_units": 8_400_000, "currency": "USD", "as_written": "$84,000"}],
    "dates_mentioned": [{"as_written": "28 March 2026", "evidence": _cite("28 March 2026")}],
}

EMAIL = RawObject(source="gmail", object_type="email_message",
                  source_object_id="m_sweep_lanes_renewal", occurred_at=SWEEP_NOW,
                  actor_email="cfo@northwind.test", recipients=(OWNER_MAIL,),
                  raw={"subject": f"{VENDOR} renewal", "body": _PROSE})

DEAL = RawObject(source="hubspot", object_type="deal",
                 source_object_id="deal_sweep_lanes", occurred_at=SWEEP_NOW,
                 actor_email=OWNER_CRM, content_version="v1",
                 raw={"dealname": f"{VENDOR} renewal", "dealstage": "contractsent",
                      "amount": "84000", "deal_currency_code": "USD",
                      "closedate": CLOSE_DATE, "contact_email": ["ops@northwind.test"]})


class _Connector:
    """The provider, and one of the two things standing in on this sweep. The repository, the
    coverage declaration, the org baseline, the structured lane, the floor, the drop ledger, the
    lifecycle store and the signal store are all the production objects `routes` built at import."""

    def __init__(self, objects, source: str) -> None:
        self._objects = list(objects)
        #: `run_sync` treats the CONNECTOR as authoritative about its own source.
        self.source = source
        self.fetches = 0

    def incremental_changes(self, cursor=None, limit=50, since=None):
        self.fetches += 1
        return SourceBatch(objects=self._objects, next_cursor=None)

    def initial_snapshot(self, cursor=None, limit=50):
        return self.incremental_changes(cursor, limit)

    def validate_connection(self) -> bool:
        return True


class _Result:
    """The transport's answer, field-for-field the shape the extractor reads."""

    def __init__(self, payload: dict) -> None:
        self.parsed = payload
        self.raw = json.dumps(payload, sort_keys=True)
        self.input_tokens, self.output_tokens = 900, 180
        self.model = "fake-model-sweep-lanes"
        self.cached, self.ok, self.error = False, True, None


class _LLM:
    """One canned extraction. The corpus is a single email, so there is nothing to address by
    content; a typed deal never reaches this at all, which is the structured bypass's promise."""

    model = "fake-model-sweep-lanes"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def call(self, prompt: str, *, max_tokens: int = 4096):
        self.calls.append(prompt)
        return _Result(EMAIL_EXTRACTION)


class _Connections:
    """The narrowest `ConnectionStore` the sweep needs: one mailbox and one CRM, two tenants."""

    def __init__(self, *connections) -> None:
        self._connections = list(connections)

    def list_active(self, source_type: str | None = None):
        return [c for c in self._connections
                if source_type is None or c.source_type == source_type]

    def get(self, connection_id: str):
        return next((c for c in self._connections if c.connection_id == connection_id), None)

    def set_status(self, connection_id: str, status: str) -> None:      # pragma: no cover
        raise AssertionError(f"the sweep marked {connection_id} {status}: the connector is fine")


@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the sweep-lane probe needs real Postgres")
    return live_db_url


def _priced_extraction(minor_units: int, counterparty: str) -> dict:
    """One stored extraction, built through the REAL contract and dumped the way the cache writes
    it, so `baseline_reader` parses the bytes production files rather than a fixture shaped like
    them."""
    from genios_engine.contracts.evidence import EvidenceSpan
    from genios_engine.contracts.extraction import EntityMention, ExtractionResult
    from genios_engine.contracts.units import Money

    span = EvidenceSpan(source_ref="prepared_content:pc_hist", quote=counterparty,
                        start_offset=0, end_offset=len(counterparty))
    return ExtractionResult(
        intent="inform", stance="neutral",
        amounts=[Money(minor_units=minor_units, currency="USD",
                       as_written=f"${minor_units // 100}")],
        entity_mentions=[EntityMention(surface_form=counterparty, entity_type="organization",
                                       evidence=[span], confidence_bp=9000)],
        all_evidence=[span], model_snapshot="fake-model-hist", prompt_version="p1",
        schema_version="1", extraction_profile="email", input_tokens=10, output_tokens=5,
    ).model_dump(mode="json")


@pytest.fixture
def two_tenants(pg_url):
    """The two tenants the cross-org sweep really has: one activated mailbox with a priced
    history and a declared mission-critical vendor, and one UNACTIVATED CRM on a UTC+14 zone."""
    engine = get_engine(pg_url)

    def _wipe(conn):
        for org in (ORG_MAIL, ORG_CRM):
            for table in _TABLES:
                conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
            conn.execute(text("delete from orgs where id = :o"), {"o": org})

    with engine.begin() as conn:
        _wipe(conn)
        names = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'"))]
        cols = ["id"] + names
        for org, owner in ((ORG_MAIL, OWNER_MAIL), (ORG_CRM, OWNER_CRM)):
            conn.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                              f"({', '.join(':' + c for c in cols)})"),
                         {"id": org, **{n: "scratch" for n in names}})
            # `email` is what `_mailbox_owner_for` reads and `timezone` is what
            # `make_structured_lane` reads. Both are set as DATA on the org row rather than
            # patched, so what the assertions below exercise is the production reader.
            conn.execute(text("update orgs set email = :e, timezone = :z where id = :o"),
                         {"e": owner, "z": ORG_ZONE, "o": org})
        # ONE tenant on the S2 lane, through the real table `_semantic_activated_orgs` reads.
        conn.execute(text(
            "insert into l1_semantic_activation (org_id, enabled_at, enabled_by, notes) "
            "values (:o, :at, :by, :n) on conflict (org_id) do nothing"),
            {"o": ORG_MAIL, "at": SWEEP_NOW, "by": OWNER_MAIL, "n": "sweep-lane probe"})
        conn.execute(text(
            "insert into org_mission_critical_entities "
            "(org_id, entity_key, display_name, owner, note) values (:o,:k,:d,:w,:n) "
            "on conflict (org_id, entity_key) do nothing"),
            {"o": ORG_MAIL, "k": VENDOR.casefold(), "d": VENDOR, "w": OWNER_MAIL,
             "n": "single-source billing platform"})
        occurred = SWEEP_NOW - timedelta(days=60)
        for index, (minor_units, party) in enumerate(PRICED_HISTORY):
            event_id = f"evt_sweep_lanes_hist_{index}"
            conn.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, "
                "object_type, source_object_id, dedup_key, actor, occurred_at) values "
                "(:e, :o, :c, 'gmail', 'email_message', :e, :e, cast('{}' as jsonb), :at)"),
                {"e": event_id, "o": ORG_MAIL, "c": CONN_MAIL, "at": occurred})
            conn.execute(text(
                "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
                "model_snapshot, profile_id, tier) values (:k, :o, :e, cast(:out as jsonb), "
                "'fake-model-hist', 'email', 'T1')"),
                {"k": f"pk_sweep_lanes_hist_{index}", "o": ORG_MAIL, "e": event_id,
                 "out": json.dumps(_priced_extraction(minor_units, party))})
    yield pg_url
    with engine.begin() as conn:
        _wipe(conn)


@pytest.fixture
def swept(two_tenants, monkeypatch):
    """THE HEARTBEAT ITSELF — `run_maintenance_sweep()`, driven exactly as the scheduler drives it.

    Five monkeypatches, and only three kinds of thing are replaced:

    * the PROVIDER (`make_connector_for`) and the MODEL (injected into the production semantic
      factory) — the two things a test may not have;
    * `_run_l2`, because L2/L3/L5 are another layer's wiring and this probe is about L1;
    * `_connections` and `_cursors`, so the sweep's connection set and watermark are this test's
      own and a second run is not a no-op.

    `_esqe_stage_for`, `_structured_lane_for`, `_coverage_fn_for` and `_mailbox_owner_for` are NOT
    patched. They are the production factories reading the org rows the fixture seeded, which is
    what makes the assertions below evidence about the sweep rather than about a fake. Nor is the
    ACTIVATION gate patched: `_semantic_lane_for` delegates to the production factory with the
    activation set the sweep itself read, so the CRM tenant gets `None` for exactly the reason a
    real unactivated tenant does.
    """
    from genios_engine.api import routes
    from genios_engine.capture.acquire.cursor_store import InMemoryCursorStore
    from genios_engine.contracts.connection import Connection
    from genios_engine.platform.wiring import make_semantic_lane

    if routes._graph is None:
        pytest.skip("routes has no graph store — the sweep cannot reach a database")

    mailbox = Connection(org_id=ORG_MAIL, connection_id=CONN_MAIL, source_type="gmail",
                         composio_user_id=ORG_MAIL)
    crm = Connection(org_id=ORG_CRM, connection_id=CONN_CRM, source_type="hubspot",
                     composio_user_id=ORG_CRM)
    connectors = {CONN_MAIL: _Connector([EMAIL], "gmail"),
                  CONN_CRM: _Connector([DEAL], "hubspot")}
    llm = _LLM()

    def _lane(org, activated=None):
        # The PRODUCTION bundle from the production factory, with only the transport injected.
        # Built by hand it would arrive with no extraction cache and no discovery store, and then
        # `qualified_signals.extraction_ref` would point at a row nothing ever wrote — a property
        # of the test rather than of the build. `activated` is whatever the sweep itself read.
        built = make_semantic_lane(org, engine=routes._graph.engine, llm=llm,
                                   activated=activated)
        return None if built is None else replace(built, eval_time=SWEEP_NOW)

    monkeypatch.setattr(routes, "_connections", _Connections(mailbox, crm))
    monkeypatch.setattr(routes, "_cursors", InMemoryCursorStore())
    monkeypatch.setattr(routes, "make_connector_for",
                        lambda conn, **kw: connectors[conn.connection_id])
    monkeypatch.setattr(routes, "_semantic_lane_for", _lane)
    monkeypatch.setattr(routes, "_run_l2", lambda org: None)

    result = routes.run_maintenance_sweep(mode="incremental", limit=25)
    assert result["sync"]["l1_err"] == 0, f"the sweep errored: {result}"
    assert [c.fetches for c in connectors.values()] == [1, 1], (
        "the sweep did not poll both connections: "
        f"{ {k: c.fetches for k, c in connectors.items()} }")
    return _Swept(two_tenants, llm, result)


class _Swept:
    def __init__(self, url: str, llm: _LLM, result: dict) -> None:
        self.url, self.llm, self.result = url, llm, result

    def signals(self, org_id: str, source_object_id: str) -> list:
        """Every `qualified_signals` row the sweep stored for one provider object."""
        with get_engine(self.url).connect() as conn:
            return list(conn.execute(text(
                "select q.signal_id, q.signal_type, q.importance_bp, q.expires_at, "
                "       q.extraction_ref, q.importance_components as c "
                "from qualified_signals q "
                "join source_events e on e.event_id = q.event_id and e.org_id = q.org_id "
                "where q.org_id = :o and e.source_object_id = :s "
                "order by q.importance_bp desc, q.signal_id"),
                {"o": org_id, "s": source_object_id}))


def _components(row) -> dict:
    return row.c if isinstance(row.c, dict) else json.loads(row.c)


# =============================================================================================
# THE PROBE — one sweep, three lanes, read back out of Postgres
# =============================================================================================

def test_the_maintenance_sweep_runs_the_esqe_semantic_and_structured_lanes(swept):
    """**THE GATE.** One `run_maintenance_sweep()`, and all three bundles arrived where they are
    used: a `qualified_signals` row exists for the email (semantic), it carries the ORG's own
    baseline and its declared mission-critical vendor (esqe), and the CRM tenant's typed deal
    published a structured extraction whose close date was resolved in that tenant's own zone
    (structured).

    Asserted in ONE test because the defect is that the three arguments travel together on one
    call, and a reviewer deleting any of them saw nothing anywhere go red.
    """
    from genios_engine.capture.esqe.importance import BaselineBasis, EntityStanding
    from genios_engine.capture.esqe.lifecycle import DATED_TYPES

    # ── `semantic=` · prose becomes a signal at all ──────────────────────────────────────────
    mail = swept.signals(ORG_MAIL, "m_sweep_lanes_renewal")
    assert mail, (
        "the sweep stored NO qualified signal for the email. Prose carries no typed fields, so "
        "this row exists only if the S2 lane reached `run_sync` — i.e. only if `run_sync_sweep` "
        "still passes `semantic=`")
    assert swept.llm.calls, "a signal was published for prose that no model was ever shown"

    # ── `esqe=` · the ORG's baseline, not a cold start ───────────────────────────────────────
    components = _components(mail[0])
    assert components["baseline_basis"] == BaselineBasis.ORG_HISTORY.value, (
        f"the score was taken against a {components['baseline_basis']!r} baseline. This tenant "
        "has nine priced contracts behind it; `estimated` is `OrgBaseline.cold_start`, which is "
        "what `capture_event` falls back to when `esqe=` never reaches it")
    assert components["baseline_used"] == 4_500_000, (
        f"the sweep scored against a p50 of {components['baseline_used']}, not this org's own "
        "$45,000 — half of ALG-17's formula is pinned to a constant")
    assert components["entity_standing"] == EntityStanding.MISSION_CRITICAL.value, (
        f"{VENDOR} ranked {components['entity_standing']!r}. The tenant DECLARED it "
        "mission-critical in `org_mission_critical_entities`, and that judgement reaches capture "
        "on the `esqe` bundle alone — without it every counterparty is `first_seen`")

    # ── `structured=` · a typed extraction, resolved in the CRM tenant's own zone ─────────────
    deal = swept.signals(ORG_CRM, "deal_sweep_lanes")
    assert deal, "the sweep stored no qualified signal for the HubSpot deal at all"
    struct = [row for row in deal if str(row.extraction_ref).startswith("struct:")]
    assert struct, (
        f"no stored signal points at a structured extraction; refs were "
        f"{[row.extraction_ref for row in deal]}. The typed lane produced nothing the sweep kept")

    # ALG-19 measures a DATED type's expiry from the signal's own stated date, and that date is a
    # bare calendar day whose instant is decided by the ZONE. This tenant is unactivated, so there
    # is no semantic bundle for `structured_context` to borrow a zone from: either the `structured`
    # argument carries Pacific/Kiritimati (end-of-day 09:59:59Z) or the lane defaults to UTC
    # (23:59:59Z), 14 hours later.
    dated = [row for row in struct
             if row.signal_type in DATED_TYPES and row.expires_at is not None]
    assert dated, (
        f"the deal's stated close date never became an expiry; stored types were "
        f"{[row.signal_type for row in struct]}")
    for row in dated:
        stamp = row.expires_at.astimezone(timezone.utc)
        assert (stamp.hour, stamp.minute, stamp.second) == (9, 59, 59), (
            f"{row.signal_type} expires at {stamp.isoformat()}. This tenant is on {ORG_ZONE} "
            f"(UTC+14), where {CLOSE_DATE} ends at 09:59:59Z; 23:59:59Z is UTC, which is what "
            "the lane falls back to when `structured=` does not reach `run_sync`")
