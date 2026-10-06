"""Runs a founder case through the REAL chain, on the scratch database, the way production does.

`speedrun008/YC-II W27/` STEP-01 §3.4. The Atlas
harness never called the engine; this does. For each sweep instant of a case:

  1. the case's mail and calendar are handed to the production sync door — `run_sync`, with the
     connectors' OWN mappings (`ComposioGmailConnector._to_batch`, the calendar's `_to_raw`), the
     production floor, the production stores and `routes._run_ledger`, which runs `finalize_l1`.
     Without `finalize_l1` nothing is published and `_pull` drains nothing (`context/runner.py`);
  2. `routes._run_l2_chain(org, eval_time=at)` runs provision → L2 → L3/L4 → cards → post-passes,
     every stage at the case's instant (M19.C2);
  3. what each stage left is read back: what Layer 1 did with every object, what reached memory,
     the situations, the funnel, the cards a founder could see.

**The model is recorded.** Every model site the chain can reach is handed the caller's model
through the production seam that hands it the real one (`model_sites.DOORS`), and the real
transport is REFUSED for the duration: a site that built its own client fails the case with
`UnrecordedModelCall` instead of skipping itself, which is what a site with no key does.

**Production's switches.** The code's defaults, plus the one production override that changes
this chain: the LLM decider is on for every org (`GENIOS_L4_LLM_DECISION_MAKER=true`,
`speedrun008/YCW27/STATUS.md`). A placeholder key is set so every factory behaves as it does with
a key; the transport refusal guarantees it reaches nothing.

**The world, pinned — like the clock.** Two things the engine draws at random would otherwise make
one case run two ways: the ids it mints (`platform/ids.new_id`), which it then ORDERS by in places
— which person a statement anchors on, which situation an anchor shows — and the interleaving of
its thread pools (capture, the L2 drain), on which a situation's evidence depended. A golden run
mints ids from a per-case sequence and runs those pools with one worker, so a case replays
exactly. Both are findings about the engine in `03-FINDINGS.md`, not features of the runner.

**The scratch database, pinned first.** `api.routes` binds its stores at import, so the database
is pinned BEFORE it is imported, and the runner refuses to start without a scratch URL or with a
production host — a golden set that skipped would be "a pass over an empty table" again.
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from tests.replays.founder_case import (CardView, CaseObject, CaseRun, FounderCase, Landed,
                                        SituationView)

SCRATCH_ENV = "GENIOS_TEST_DATABASE_URL"
#: Set as the model key for a golden run so every factory takes its production branch. It never
#: reaches a network: the transport is refused while a case runs.
PLACEHOLDER_KEY = "golden-replay-no-network"
ORG_PREFIX = "org_golden_"
#: Production's overrides of the code's defaults that change this chain. Nothing else is set.
PRODUCTION_SWITCHES: dict[str, Any] = {"anthropic_api_key": PLACEHOLDER_KEY,
                                       "l4_llm_decision_maker": True,
                                       "l4_llm_decision_maker_orgs": ""}
_REPO = Path(__file__).resolve().parents[2]


#: The engine's in-process model caches, as (module, attribute). A golden run starts COLD, the way
#: a fresh process does: these are keyed by content, so a second run of one case in one process
#: was served answers the first run cached and took a different path — and its replay missed.
#: `test_engine_runner` holds this list to every module-level model cache under `reason/`.
COLD_CACHES: tuple[tuple[str, str], ...] = (
    ("genios_engine.reason.llm_decision_maker", "_cache"),
    ("genios_engine.reason.llm_decision_maker", "_calls_by_org_day"),
    ("genios_engine.reason.llm_interpretation", "_cache"),
)


def cold_start() -> None:
    """Empty every in-process model cache (`COLD_CACHES`) before a case runs."""
    import importlib
    for module, attribute in COLD_CACHES:
        getattr(importlib.import_module(module), attribute).clear()


class RunnerRefused(RuntimeError):
    """The runner will not start: no scratch database, a production host, or a mis-bound process."""


class UnrecordedModelCall(BaseException):
    """A model site reached the real transport during a golden run — it was not handed the
    recorded model. A `BaseException` so the chain's `except Exception` cannot swallow it."""


# =================================================================================================
# the database
# =================================================================================================
def pin_scratch_database() -> str:
    """Point this process at the scratch database, or refuse. Call BEFORE importing `api.routes`.

    Inside pytest `tests/conftest.py` has already done the pinning; this then only checks it.
    Outside (the scripts), it does the pinning itself: the same three variables, in the same order.
    """
    url = os.environ.get(SCRATCH_ENV, "").strip()
    if not url:
        raise RunnerRefused(f"{SCRATCH_ENV} is not set — the golden set runs only on a scratch "
                            "database, and refuses rather than skips")
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from scripts._db import is_production_url
    if is_production_url(url):
        raise RunnerRefused("refusing a production database host for a golden run")
    if os.environ.get("GENIOS_DATABASE_URL") != url:
        if "genios_engine.api.routes" in sys.modules:
            raise RunnerRefused("api.routes was imported before the scratch database was pinned; "
                                "its stores are bound elsewhere")
        os.environ["GENIOS_DATABASE_URL"] = url
        os.environ["GENIOS_ANTHROPIC_API_KEY"] = ""
        os.environ["GENIOS_L4_LLM_DECISION_MAKER"] = "false"
        os.environ.setdefault("GENIOS_CRYPTO_KEY", "sxpepd0Y2jFCXW0Vjbb-EK_dQ9Yv9keeVdOOoNTk0eE=")
        from genios_engine.platform.config import get_settings
        get_settings.cache_clear()
        from genios_engine.platform.migrate import apply_migrations
        apply_migrations(database_url=url)
    from genios_engine.platform.config import get_settings
    if get_settings().database_url != url:
        raise RunnerRefused("the configured database is not the scratch database")
    routes = sys.modules.get("genios_engine.api.routes")
    if routes is not None:
        bound = getattr(getattr(routes, "_graph", None), "engine", None)
        if bound is None or _where(bound.url) != _where(url):
            raise RunnerRefused("api.routes is bound to a different database than the scratch one")
    return url


def _where(url: Any) -> tuple[Any, ...]:
    """Host, port and database — `platform/db.get_engine` rewrites the driver, never these."""
    from sqlalchemy.engine import make_url
    u = make_url(url) if isinstance(url, str) else url
    return u.host, u.port, u.database


# =================================================================================================
# the model doors, and the transport refusal
# =================================================================================================
@contextmanager
def production_switches(llm: Any) -> Iterator[None]:
    """Hand `llm` to every door in `model_sites.DOORS`, refuse the real transport, and set
    production's switches — all restored on exit, whatever happens inside."""
    try:
        import anthropic
    except ImportError:            # not installed: nothing can build a raw client to refuse
        anthropic = None

    from genios_engine.api import routes
    from genios_engine.context.llm import client as llm_client
    from genios_engine.platform import wiring
    from genios_engine.platform.config import get_settings
    from genios_engine.reason import llm_decision_maker, llm_sites
    from tests.replays.harness import identify_site

    def relevance_classifier(org_id: str | None = None, *, seat_id: str | None = None):
        from genios_engine.capture.gate.relevance import LLMRelevanceClassifier
        gate = LLMRelevanceClassifier(llm)
        if org_id and routes._graph is not None:
            gate.bind_costs(routes._graph.record_cost, org_id, seat_id)
        return gate

    def refuse_call(_self, prompt: str, *_a: Any, **_kw: Any):
        raise UnrecordedModelCall(f"the real transport was called by the "
                                  f"{identify_site(prompt)} site — it was not handed the "
                                  "recorded model (tests/replays/model_sites.py)")

    class _RefusedAnthropic:
        def __init__(self, *_a: Any, **_kw: Any) -> None:
            raise UnrecordedModelCall("a raw Anthropic client was built during a golden run")

    settings = get_settings()
    patches: list[tuple[Any, str, Any]] = [
        (routes, "_llm", llm),
        (wiring, "make_llm_client", lambda: llm),
        (routes, "make_llm_client", lambda: llm),
        (wiring, "make_relevance_classifier", relevance_classifier),
        (routes, "make_relevance_classifier", relevance_classifier),
        (llm_decision_maker, "client", lambda: llm),
        (llm_sites, "make_site_client", lambda tier: llm),
        (llm_client.LLMClient, "call", refuse_call),
        (llm_decision_maker.DecisionClient, "call", refuse_call),
        *(((anthropic, "Anthropic", _RefusedAnthropic),) if anthropic is not None else ()),
        *((settings, name, value) for name, value in PRODUCTION_SWITCHES.items()),
    ]
    saved = [(target, name, getattr(target, name)) for target, name, _ in patches]
    try:
        for target, name, value in patches:
            setattr(target, name, value)
        yield
    finally:
        for target, name, value in reversed(saved):
            setattr(target, name, value)


class _PinnedUuid:
    """Stands in for the `uuid` module inside `platform/ids` for one run: the n-th id a case mints
    is the same every run, and no two cases mint the same one."""

    def __init__(self, seed: str) -> None:
        import threading
        self._seed, self._n, self._lock = seed, 0, threading.Lock()

    def uuid4(self):
        import hashlib
        import uuid
        with self._lock:
            self._n += 1
            n = self._n
        return uuid.UUID(hashlib.sha256(f"{self._seed}:{n}".encode()).hexdigest()[:32])


@contextmanager
def pinned_world(seed: str) -> Iterator[None]:
    """Mint ids from a per-case sequence and run the chain's thread pools with one worker, for the
    duration of one run — restored on exit."""
    from genios_engine.capture.acquire import sync_runner
    from genios_engine.context import runner as l2_runner
    from genios_engine.platform import ids

    patches = [(ids, "uuid", _PinnedUuid(seed)), (sync_runner, "_CAPTURE_WORKERS", 1),
               (l2_runner, "_MAX_WORKERS", 1)]
    saved = [(target, name, getattr(target, name)) for target, name, _ in patches]
    try:
        for target, name, value in patches:
            setattr(target, name, value)
        yield
    finally:
        for target, name, value in reversed(saved):
            setattr(target, name, value)


# =================================================================================================
# the providers — the connectors' own mappings, fed the case's objects
# =================================================================================================
def _connectors():
    from genios_engine.capture.connectors.calendar import ComposioCalendarConnector
    from genios_engine.capture.connectors.composio import ComposioGmailConnector

    class CaseMailbox(ComposioGmailConnector):
        """The production Gmail connector with Composio replaced by the case: every message goes
        through `_to_batch` → `_to_objects`, the mapping production runs."""

        def __init__(self, objects: list[CaseObject]) -> None:
            super().__init__(api_key="golden", user_id="golden", ocr=None, relevance=None)
            self._by_id = {o.provider_id: o for o in objects}

        def validate_connection(self) -> bool:
            return True

        def _execute(self, slug: str, arguments: dict[str, Any]) -> Any:
            if slug == "GMAIL_FETCH_EMAILS":                 # Gmail lists newest first
                ordered = sorted(self._by_id.values(), key=lambda o: o.occurred_at, reverse=True)
                messages = [o.provider_message() for o in ordered]
                return {"data": {"messages": messages, "resultSizeEstimate": len(messages)}}
            if slug == "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID":
                return {"data": self._by_id[arguments["message_id"]].provider_message()}
            if slug == "GMAIL_GET_ATTACHMENT":
                return self._by_id[arguments["message_id"]].attachment_response(
                    arguments["attachment_id"])
            raise RunnerRefused(f"the case mailbox does not answer {slug}")

    class CaseCalendar(ComposioCalendarConnector):
        """The production calendar connector with Composio replaced by the case's events."""

        def __init__(self, objects: list[CaseObject], internal: frozenset[str] | None) -> None:
            super().__init__(api_key="golden", user_id="golden", internal_emails=internal)
            self._events = [o.provider_event() for o in objects]

        def validate_connection(self) -> bool:
            return True

        def _fetch(self, *, max_results: int, since: datetime | None, page_token: str | None):
            return {"items": list(self._events)}

    return CaseMailbox, CaseCalendar


# =================================================================================================
# the run
# =================================================================================================
def run_case(case: FounderCase, llm: Any, *, org_id: str | None = None,
             keep: bool = False) -> CaseRun:
    """Run every sweep of `case` through the real chain with `llm` as the model; report it.

    The tenant is REMOVED once the report is read, unless `keep`: the scratch database is shared
    by the whole suite, and a golden tenant left switched on turned up in another test's list of
    every activated org (QA, 2026-10-06). `keep=True` is for a reader who wants to look at the
    rows a run left — and then calls `remove_tenant`."""
    pin_scratch_database()
    from genios_engine.api import routes
    from genios_engine.platform.intelligence_onboarding import provision_intelligence

    if routes._graph is None or routes._card_store is None:
        raise RunnerRefused("api.routes has no database-backed stores")
    org = org_id or f"{ORG_PREFIX}{case.case_id.lower()}"
    engine = routes._graph.engine
    _fresh_tenant(engine, org, case)
    # Process-local memory of a previous run of this org: the tenant switch-on cache and the
    # funnel's pending count. A wiped tenant that this process still believes live would never
    # be switched on again.
    routes._LIVE_ORGS.discard(org)
    routes._take_signals_published(org)
    cold_start()
    mailbox_cls, calendar_cls = _connectors()

    landed: list[Landed] = []
    chain_ok: list[bool] = []
    funnel: list[dict[str, int]] = []
    open_after: list[set[str]] = []
    try:
        with production_switches(llm), pinned_world(f"golden:{case.case_id}"):
            provision_intelligence(engine, org)
            routes._ensure_tenant_live(org)
            for sweep, at in enumerate(case.sweeps):
                objects = case.objects_in(sweep)
                mail = [o for o in objects if o.source == "gmail"]
                events = [o for o in objects if o.source == "gcal"]
                if mail:
                    landed += _land(routes, case, org, sweep, at, mailbox_cls(mail), "gmail")
                if events:
                    landed += _land(routes, case, org, sweep, at,
                                    calendar_cls(events, _internal(routes, org)), "gcal")
                chain_ok.append(bool(routes._run_l2_chain(org, eval_time=at)))
                funnel.append(_funnel(engine, org, at))
                open_after.append(_open_cards(engine, org))
        calls = tuple(getattr(llm, "calls", ()) or ())
        misses = tuple(getattr(llm, "misses", ()) or ())
        report = CaseRun(case_id=case.case_id, org_id=org, landed=tuple(landed),
                         memory=_memory(engine, org, case, landed),
                         situations=_situations(engine, org),
                         cards=_cards(engine, org, open_after), funnel=tuple(funnel),
                         chain_ok=tuple(chain_ok), model_calls=calls, misses=misses)
    finally:
        # On EVERY exit — a cassette miss included — or the tenant stays switched on.
        if not keep:
            remove_tenant(engine, org)
    return report


def remove_tenant(engine: Any, org: str) -> None:
    """Erase a golden tenant the way account deletion does — the `/reset` list, then the org row,
    whose foreign keys cascade the rest (activation rows among them) — and forget it in-process."""
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.api.account_routes import _wipe
    if not str(org).startswith(ORG_PREFIX):
        raise RunnerRefused(f"refusing to remove {org}: not a golden tenant")
    with engine.begin() as conn:
        _wipe(conn, org)
        for table in ("context_correlation_members", "context_situations",
                      "context_correlations"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        conn.execute(text("delete from orgs where id = :o"), {"o": org})
    routes._LIVE_ORGS.discard(org)
    routes._take_signals_published(org)


def _land(routes: Any, case: FounderCase, org: str, sweep: int, at: datetime, connector: Any,
          source: str) -> list[Landed]:
    """One provider's objects for one sweep, through the production sync door."""
    from genios_engine.capture.acquire.sync_runner import run_sync
    from genios_engine.platform.wiring import make_esqe_stage, make_semantic_lane

    engine = routes._graph.engine
    summary = run_sync(
        connector, org_id=org, connection_id=f"conn_golden_{source}", repo=routes._repo,
        mode="incremental", limit=100, parked_store=routes._parked,
        relevance=routes.make_relevance_classifier(org),
        trace_repo=routes._trace_repo, payload_store=routes._payload_store,
        prepared_store=routes._prepared_store, mailbox_owner=case.founder.email,
        sender_resolver=routes._sender_resolver_for(org), cursor_store=None,
        document_job_store=routes._documents, source=source, max_pages=1,
        run_ledger=routes._run_ledger, coverage_fn=routes._coverage_fn_for(org),
        esqe=make_esqe_stage(org, engine=engine, now=at),
        # The production factory, at the case's instant. Its model comes through the
        # `make_llm_client` door; `activated` names the tenant `_ensure_tenant_live` switched on.
        semantic=make_semantic_lane(org, now=at, engine=engine, activated=frozenset({org})),
        structured=routes._structured_lane_for(org), respect_cadence=False, _now=lambda: at)
    by_provider = {o.provider_id: o.object_id for o in case.objects}
    out = []
    for result in summary.results or ():
        event = result.event
        provider_id = str(event.source_object_id or "")
        object_id = by_provider.get(provider_id.split("::", 1)[0], provider_id)
        out.append(Landed(object_id=object_id, source_object_id=provider_id,
                          event_id=getattr(event, "event_id", None), outcome=result.outcome,
                          reason=_reason(result), sweep=sweep))
    return out


def _reason(result: Any) -> str | None:
    if result.outcome == "emitted":
        return None
    records = getattr(getattr(result, "trace", None), "records", None) or ()
    return next((r.reason_code for r in reversed(records) if r.reason_code), None)


def _internal(routes: Any, org: str) -> frozenset[str] | None:
    """The calendar's identity set, read the way `make_connector_for` reads it."""
    from genios_engine.context.runner import _internal_emails
    try:
        return _internal_emails(routes._graph, org)
    except Exception:      # noqa: BLE001 — production keeps the legacy path on a failed read
        return None


def _fresh_tenant(engine: Any, org: str, case: FounderCase) -> None:
    """The tenant, created as a signup creates it, and erased through the production `/reset`
    list — a golden case starts from nothing every time, or a second run lands on `duplicate`."""
    from sqlalchemy import text

    from genios_engine.api.account_routes import _wipe
    with engine.begin() as conn:
        # Every case is the same founder, and `orgs.email` is unique: the address moves to the
        # tenant being run. Only ever from another golden tenant — never from a tenant this
        # runner did not create.
        holder = conn.execute(text("select id from orgs where lower(email) = :e and id <> :o"),
                              {"e": case.founder.email, "o": org}).scalar()
        if holder is not None and not str(holder).startswith(ORG_PREFIX):
            raise RunnerRefused(f"the founder address belongs to {holder}, which is not a golden "
                                "tenant")
        conn.execute(text("update orgs set email = null where lower(email) = :e and id <> :o "
                          "and id like :p"),
                     {"e": case.founder.email, "o": org, "p": ORG_PREFIX + "%"})
        # AS SIGNUP STORES IT (`api/auth_routes`): `orgs.name` is the PERSON's full name and
        # `orgs.company` the workspace. This runner put the company in `name` and no person
        # anywhere, so nothing in a golden tenant knew what the founder is called — and "a card
        # whose subject is the founder" could not be asked by name (STEP-04, U10's control).
        conn.execute(text(
            "insert into orgs (id, name, company, email, timezone) values (:o, :n, :co, :e, :tz) "
            "on conflict (id) do update set name = excluded.name, company = excluded.company, "
            "email = excluded.email, timezone = excluded.timezone"),
            {"o": org, "n": case.founder.name, "co": case.founder.company,
             "e": case.founder.email, "tz": case.founder.timezone})
        _wipe(conn, org)
        # Not on the `/reset` list (migration 0037 erases them on account deletion only).
        for table in ("context_correlation_members", "context_situations",
                      "context_correlations"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        # STEP-04 (F54) — AS SIGNUP DOES: the owner's seat, from `orgs.email`. Without it the
        # sent-folder half of the W-01 whitelist never fired here while it does in production,
        # so the golden set measured a gate harsher than the one the founder has.
        from genios_engine.platform.seats import ensure_owner_seat
        ensure_owner_seat(conn, org)
        # And what the tenant declared as its own, the way `scripts/declare_self_identity.py`
        # does for the design partner: the founder's other addresses, the company's domains.
        conn.execute(text("delete from org_self_identities where org_id = :o"), {"o": org})
        for kind, values in (("address", case.founder.also), ("domain", case.founder.domains)):
            for value in values:
                conn.execute(text(
                    "insert into org_self_identities (org_id, kind, value, declared_by) "
                    "values (:o, :k, :v, 'golden case') on conflict do nothing"),
                    {"o": org, "k": kind, "v": value})


def _funnel(engine: Any, org: str, at: datetime) -> dict[str, int]:
    """This sweep's funnel row, by the sweep id `_run_l2_chain` derives from org and instant."""
    from sqlalchemy import text

    from genios_engine.platform.canonical import stable_id
    sweep_id = stable_id("fsweep", {"org": org, "at": at.isoformat()})
    with engine.connect() as conn:
        rows = conn.execute(text("select stage, n from pipeline_counters "
                                 "where org_id = :o and sweep_id = :s"),
                            {"o": org, "s": sweep_id}).fetchall()
    return {r.stage: int(r.n) for r in rows}


def _open_cards(engine: Any, org: str) -> set[str]:
    from sqlalchemy import text

    from genios_engine.deliver.store import CardStore
    with engine.connect() as conn:
        return set(conn.execute(text("select card_id from cards where org_id = :o "
                                     "and state = any(:s)"),
                                {"o": org, "s": list(CardStore.OPEN_STATES)}).scalars())


def _cards(engine: Any, org: str, open_after: list[set[str]]) -> tuple[CardView, ...]:
    """Every card the founder could see after at least one sweep, with what it says."""
    from sqlalchemy import text
    seen = set().union(*open_after) if open_after else set()
    if not seen:
        return ()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select card_id, state, level, headline, situation, why, actions, artifact, "
            "business_subject, unresolved_item, why_now, output_lane from cards "
            "where org_id = :o and card_id = any(:ids) order by card_id"),
            {"o": org, "ids": sorted(seen)}).fetchall()
    out = []
    for r in rows:
        # One line per thing the founder reads — each WHY item and each action on its own, so a
        # reader can compare two cards line by line.
        artifact = r.artifact if isinstance(r.artifact, dict) else {}
        parts = [r.headline, r.situation, *(_flat(w) for w in (r.why or ())),
                 *(_flat(a) for a in (r.actions or ())), artifact.get("body"), r.business_subject,
                 r.unresolved_item, r.why_now]
        out.append(CardView(card_id=r.card_id, state=r.state, level=r.level,
                            text="\n".join(str(p) for p in parts if p),
                            subject=r.business_subject,
                            output_lane=r.output_lane,
                            sweeps=tuple(i for i, ids in enumerate(open_after) if r.card_id in ids)))
    return tuple(out)


def _flat(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flat(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flat(v) for v in value)
    return json.dumps(value, default=str) if not isinstance(value, (int, float)) else str(value)


def _memory(engine: Any, org: str, case: FounderCase, landed: list[Landed]) -> dict[str, int]:
    """Per object: the rows of memory its events created — nodes, facts, edges, observations."""
    from sqlalchemy import text
    out: dict[str, int] = {}
    with engine.connect() as conn:
        for obj in case.objects:
            events = sorted({x.event_id for x in landed if x.object_id == obj.object_id
                             and x.event_id})
            total = 0
            if events:
                for table in ("graph_nodes", "graph_facts", "graph_edges", "graph_observations"):
                    total += int(conn.execute(text(
                        f"select count(*) from {table} where org_id = :o "
                        "and created_by_event_id = any(:e)"), {"o": org, "e": events}).scalar())
            out[obj.object_id] = total
    return out


def _situations(engine: Any, org: str) -> tuple[SituationView, ...]:
    from sqlalchemy import text
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select s.situation_id, s.situation_type, s.domain, s.status, "
            "coalesce(n.display_name, '') as anchor from context_situations s "
            "left join graph_nodes n on n.node_id = s.anchor_node_id and n.org_id = s.org_id "
            "where s.org_id = :o order by s.situation_type, s.situation_id"), {"o": org}).fetchall()
    return tuple(SituationView(situation_id=r.situation_id, situation_type=r.situation_type,
                               domain=r.domain, status=r.status, anchor=r.anchor) for r in rows)
