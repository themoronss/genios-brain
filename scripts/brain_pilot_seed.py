"""Seed a pilot tenant and DRIVE the Behaviour and Adaptive brains through their real paths.

    python scripts/brain_pilot_seed.py --org org_j4_pilot --database-url postgresql://…
    python scripts/brain_content_report.py --org org_j4_pilot --database-url postgresql://…

**WHY THIS EXISTS.** J4 asks whether the three runtime brains hold anything and how it got there,
and two of its rows were reported `0` with the note "blocked on a pilot tenant". They were not.
Every feeder has a production path, and the only thing missing was a POPULATION for those paths
to run on — the same shape Layer 2's H5 was measured in: seeded rows, production code, and the
gate reading the result out of the tables afterwards.

**WHAT IS SEEDED AND WHAT IS DRIVEN — the distinction this whole script is built around.**

  SEEDED (population, written straight into the tables a customer's own traffic would fill):
    * the tenant row and its active pack;
    * one founder's correspondence — `source_events` plus the directed `thread.last_outbound` /
      `thread.last_inbound` facts, written through `GraphStore.write_fact`, which is the same
      writer `context/pipeline.py` uses on a real email, so each message lands with its own fact
      version and its own `graph_source_refs` row exactly as L1→L2 leaves it;
    * a handful of audited cards, complete enough to satisfy the LIVE authority predicate in
      `reason/authority.py` — nothing there is relaxed, and if a seeded row were short of it the
      feedback route below would answer 409 and this script would fail.

  DRIVEN (production entry points, called exactly as the running system calls them):
    * `context/runner.process_pending` — the drain. It backfills `metric_history` from the event
      ledger, samples the current period and recomputes `derived.trend.<metric>`. Nothing about
      L2.4's arithmetic is reimplemented here; this script does not compute a single number that
      reaches a brain.
    * `feedback/orchestrator.run_learning` — the weekly pass, which is what
      `run_learning_sweep` calls per tenant. N-4's behaviour proposals are collected by
      `brain_pipeline_proposals` INSIDE that run and go through the same validate → preflight →
      govern → persist → publish loop as every other proposal.
    * `POST /v1/intelligence/feedback` — the founder's card verdict, over HTTP through
      `TestClient`, with only the credential dependency overridden. The route writes the verdict
      and calls `lease_from_card_feedback` in the same transaction; this script never calls that
      function itself.

**THE ONE PLACE A CLOCK IS BENT, and it is named rather than hidden.** A lease needs
`min_observations` bad-timing verdicts across `min_distinct_days` distinct days, and the route
stamps a verdict with the instant that request evaluates at. A script cannot wait two days, so
after each verdict is written BY THE ROUTE its `occurred_at` is moved back a day. The verdict
rows are the route's; only the moment they carry is the population's. Nothing else about the
lease is adjusted: the floors, the governance, the expiry and the publisher all run untouched,
and the last verdict — the one whose cohort the live lease states — is stamped by the route
itself.

**IT WRITES, SO IT NAMES ITS TARGET.** The database is resolved through `scripts/_db.py`, which
has no fallback to the application's configured URL and refuses a Supabase host without a second
deliberate act. There is no `--at`: the clock is read once, here, at the process boundary, and
every stage is handed that one instant — the same discipline `process_pending` keeps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

if __package__ in (None, ""):                       # pragma: no cover - CLI import shim
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url        # noqa: E402

# =================================================================================================
# THE POPULATION'S SHAPE. Every number here is a property of the seeded tenant, never a threshold
# the pipelines are judged against — those live in `learning_policies` and in L2.4's own module
# constants, and this script does not read, copy or lower one of them.
# =================================================================================================

#: Accounts the founder corresponds with. Above `min_distinct_entities` (3) with room to spare:
#: a behaviour pattern is a claim about how the COMPANY acts, and a cohort sitting exactly on the
#: k-anonymity floor would make the run's pass depend on the floor rather than on the data.
ACCOUNTS = 6

#: Weeks of correspondence. The trend computer reads the last twelve periods
#: (`TREND_WINDOW_PERIODS`) and N-4 requires a 60-day observed window, so twenty weeks leaves the
#: window full at both ends rather than starting exactly where the reader starts.
WEEKS = 20

#: The founder's weekly outbound volume, oldest week first: a real, gradual taper rather than a
#: switch. Every reading L2.4 takes off this is a 28-day count, so a step change would show up as
#: one cliff and four flat periods; a fall of one message every second week is what "we have been
#: reaching out less" actually looks like in a mailbox.
def weekly_outbound(week_index: int) -> int:
    return max(2, 14 - week_index // 2)


#: The capability the founder's cards are about, and the subject the lease is keyed on. A real
#: Admin capability id, so `adaptive:card_timing:<capability>` is a key a reader that holds a
#: route plan can match on rather than a string invented for a fixture.
CAPABILITY = "admin.executive_support.commitment_tracking"
CAPABILITY_VERSION = "1.0.0"
PACK_ID = "admin"
PACK_VERSION = "1.0.1"
PLAY_ID = "hold_the_line"
PLAY_VERSION = "1.0.0"

#: The root the seeded reasoning ran on. `reasoning_context_root_type_required` (migration 0034)
#: is a CHECK, not a convention: a context snapshot that does not say what kind of thing it was
#: reasoning about cannot be stored, and the counterparties this population corresponds with are
#: `person` nodes — the same type `seed_correspondence` created them as.
ROOT_NODE_TYPE = "person"

#: How the seeded run was triggered. `reasoning_runs_trigger_kind_check` allows exactly
#: event/query/schedule/manual/replay, and the scheduled sweep that produces a founder's queue is
#: `schedule` — the vocabulary is the table's, not this script's.
TRIGGER_KIND = "schedule"

#: Cards the founder judges. Four verdicts is one above `min_observations` (3) — enough that the
#: lease is earned rather than exactly reached, and few enough that every one of them is a real
#: HTTP call this script makes and prints. The THIRD verdict is the one that first clears the
#: floors, so the route grants a lease inside that request and the fourth supersedes it with the
#: larger cohort; the tenant is left holding exactly one live lease, which is
#: `publisher.publish_runtime`'s one-active-per-subject rule doing its job in the open.
CARDS = 4

#: The founder, as a principal. Two seats, because `LearningEvidence.independent_refs` counts
#: independent judges: three verdicts from one person is one opinion said three times.
ACTORS = ("seat_founder", "seat_chief_of_staff")


def _sha(*parts: Any) -> str:
    """A 64-hex digest of the given parts. The reasoning tables CHECK this shape on every hash."""
    payload = "|".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class SeedReport:
    """What each stage actually did, in numbers the operator can compare against the gate."""

    org_id: str
    at: datetime
    accounts: int = 0
    messages: int = 0
    history_points: int = 0
    trend_facts: int = 0
    learning: dict[str, Any] = field(default_factory=dict)
    behavior_entries: int = 0
    cards: int = 0
    verdicts: int = 0
    lease_rows: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "at": self.at.isoformat(), "accounts": self.accounts,
                "messages": self.messages, "history_points": self.history_points,
                "trend_facts": self.trend_facts, "learning": self.learning,
                "behavior_entries": self.behavior_entries, "cards": self.cards,
                "verdicts": self.verdicts, "lease_rows": self.lease_rows, "notes": self.notes}


# =================================================================================================
# STAGE 1 · THE TENANT
# =================================================================================================

def ensure_org(engine, org_id: str, *, at: datetime) -> None:
    """An `orgs` row, filled from the table's own NOT NULL columns rather than a hard-coded list.

    Reading the columns is what keeps this working when the tenant table grows a required field:
    a seeder that spelled its INSERT out would fail on the next migration, and the failure would
    look like a broken gate rather than a stale script.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        required = conn.execute(text(
            "select column_name, data_type from information_schema.columns where "
            "table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        columns, placeholders, values = ["id"], [":id"], {"id": org_id}
        for row in required:
            columns.append(row.column_name)
            placeholders.append(f":{row.column_name}")
            kind = row.data_type
            values[row.column_name] = (
                at.isoformat() if ("time" in kind or "date" in kind)
                else 0 if ("int" in kind or "numeric" in kind or "double" in kind)
                else "pilot@example.test" if "email" in row.column_name else org_id)
        conn.execute(text(f"insert into orgs ({','.join(columns)}) "
                          f"values ({','.join(placeholders)}) on conflict do nothing"), values)


# =================================================================================================
# STAGE 2 · THE CORRESPONDENCE (population)
# =================================================================================================

def seed_correspondence(store, *, org_id: str, at: datetime, accounts: int = ACCOUNTS,
                        weeks: int = WEEKS) -> tuple[int, int]:
    """One founder's outbound cadence, tapering, with the replies it drew. Returns (nodes, msgs).

    Written through `GraphStore.write_fact`, which is the writer the L2 pipeline uses for exactly
    these two fields on a real email — so every message leaves the same triple behind (a
    `source_events` row, a `graph_facts` version, a `graph_source_refs` row joining them), and
    `context/analytic/sampler.read_org_snapshot` reads the result with the query it already runs
    in production. Seeding `metric_history` directly would have been four lines and would have
    proved nothing: the numbers the brain ends up stating would have been ours.
    """
    from sqlalchemy import text

    from genios_engine.context.analytic.history import MetricGrain, period_start

    last_bucket = period_start(at, MetricGrain.WEEK)
    messages = 0
    with store.engine.begin() as conn:
        for index in range(accounts):
            address = f"counterparty{index}@account{index}.test"
            node = store.find_or_create_node(
                conn, org_id=org_id, node_type="person", canonical_key=address,
                display_name=f"Counterparty {index}", event_id=None)
            for week in range(weeks):
                bucket = last_bucket - timedelta(days=7 * (weeks - 1 - week))
                for slot in range(weekly_outbound(week)):
                    sent = bucket + timedelta(days=slot % 5, hours=9 + slot // 5)
                    # Their reply, five hours later. Both legs are written: a mailbox with only
                    # one direction in it would make `relationship.response_latency_hours` a
                    # series of gaps, and a founder who never gets answered is a different
                    # tenant from the one this population is describing.
                    for field_name, moment in (("thread.last_outbound", sent),
                                               ("thread.last_inbound", sent + timedelta(hours=5))):
                        if moment >= at:
                            continue
                        # The LEG is part of the event id. `field_name[-3:]` spelled both
                        # `thread.last_outbound` and `thread.last_inbound` as "und", so the reply
                        # collided with the message it answered and `on conflict do nothing` threw
                        # half the ledger away — leaving a mailbox whose inbound side existed only
                        # as facts, with no event behind it.
                        leg = field_name.rsplit(".", 1)[-1]
                        event_id = f"ev_{org_id}_{index}_{week}_{slot}_{leg}"
                        conn.execute(text(
                            "insert into source_events (event_id, org_id, connection_id, source, "
                            "object_type, source_object_id, dedup_key, actor, occurred_at) values "
                            "(:e, :o, 'conn_pilot', 'gmail', 'email_message', :e, :e, "
                            "cast(:actor as jsonb), :at) on conflict (event_id) do nothing"),
                            {"e": event_id, "o": org_id, "at": moment,
                             "actor": json.dumps({"email": address})})
                        messages += 1
                        store.write_fact(
                            conn, org_id=org_id, subject_node_id=node, field=field_name,
                            value=moment.isoformat(), value_type="timestamp", confidence=0.95,
                            occurred_at=moment, event_id=event_id,
                            evidence={"derived": "message"}, source="gmail", authority_rank=2)
    return accounts, messages


# =================================================================================================
# STAGE 3 · THE DRAIN, and STAGE 4 · THE WEEKLY PASS (both production entry points)
# =================================================================================================

def drive_the_drain(store, *, org_id: str, at: datetime) -> dict[str, Any]:
    """`context/runner.process_pending` — the sweep both sync routes and the upload route run.

    `llm=None` is safe and deliberate: the seeded `source_events` carry no `raw_payloads` row, so
    the extraction lane's own query does not select them and the drain goes straight to the
    passes this script is here for — the backfill, the sampler and the trend computer.
    """
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings

    return process_pending(org_id=org_id, store=store, llm=None,
                           crypto_key=get_settings().crypto_key, eval_time=at)


def drive_the_weekly_pass(engine, *, org_id: str, at: datetime) -> dict[str, Any]:
    """`feedback/orchestrator.run_learning` — one tenant's claimed weekly pass, in one transaction.

    The per-tenant body of `run_learning_sweep`, called directly so a failure is raised rather
    than counted as a skipped tenant. N-4's proposals are collected inside it.
    """
    from genios_engine.feedback.orchestrator import run_learning

    with engine.begin() as conn:
        return run_learning(conn, org_id=org_id, now=at)


# =================================================================================================
# STAGE 5 · THE CARDS (population, and it must satisfy the LIVE authority predicate)
# =================================================================================================

def seed_audited_card(conn, *, org_id: str, index: int, at: datetime, node_id: str) -> str:
    """One card the feedback route will accept, with the whole audit chain underneath it.

    `reason/authority.py`'s predicate is not relaxed anywhere and is not copied here: this
    function writes the rows a completed live reasoning run leaves behind, and the ROUTE's own
    SELECT is what decides whether they are enough. A missing or inconsistent row does not
    produce a weaker card — it produces a 409 from the route and a failed seed, which is the
    property that makes seeding a card safe to do at all.

    The manifest declares one read-only play, one required reasoner and NO policies, so the
    candidate-check index the predicate demands is empty on both sides — the honest audit trail
    of a decision that had nothing to constrain, rather than a check row invented to satisfy a
    comparison.
    """
    from sqlalchemy import text

    suffix = f"{org_id}_{index}"
    run_id, candidate_id = f"rrun_{suffix}", f"rcand_{suffix}"
    # ONE capability snapshot and ONE config snapshot for the tenant, not one per card:
    # `reasoning_capability_snapshots` is UNIQUE on (org_id, capability_id, capability_version),
    # which is the schema saying what a snapshot is — the manifest a version of a capability was
    # reasoned under, shared by every run of it. A per-card snapshot is not a stricter fixture,
    # it is a row the table refuses. The run and its context are per-card, because those are what
    # actually differ: a different root node at a different instant.
    config_id, capability_snapshot = f"cfg_{org_id}", f"capsnap_{org_id}"
    context_snapshot, signal_id = f"ctxsnap_{suffix}", f"sig_{suffix}"
    card_id = f"card_{suffix}"
    expires_at = at + timedelta(days=14)
    utility_bp, confidence_bp = 6_000, 8_000
    score = (utility_bp + 50) // 100                # the projection law, in this script's copy
    rule_id = CAPABILITY.rsplit(".", 1)[-1]
    manifest = {
        "domain": PACK_ID, "capability_id": CAPABILITY, "live_delivery_enabled": True,
        "plays": [{"play_id": PLAY_ID, "version": PLAY_VERSION, "read_only": True}],
        "reasoners": [{"reasoner_id": "core.constraint", "version": "1.0.0"}],
        "policies": []}
    decision_core = {"expires_at": {"$datetime": expires_at.isoformat()}}
    decision_hash = _sha("decision", suffix, expires_at.isoformat())

    conn.execute(text(
        "insert into tenant_packs (org_id, pack_id, version, state, authority_revision, "
        "updated_at) values (:o, :p, :v, 'active', 1, :t) on conflict (org_id, pack_id) do update "
        "set version=excluded.version, state='active', authority_revision=1, "
        "updated_at=excluded.updated_at"),
        {"o": org_id, "p": PACK_ID, "v": PACK_VERSION, "t": at - timedelta(days=1)})
    conn.execute(text(
        "insert into config_snapshots (snapshot_id, org_id, pack_id, effective, cause) "
        "values (:s, :o, :p, cast(:e as jsonb), 'pilot_seed') on conflict do nothing"),
        {"s": config_id, "o": org_id, "p": PACK_ID,
         "e": json.dumps({"pack_id": PACK_ID, "version": PACK_VERSION, "state": "active"})})
    conn.execute(text(
        "insert into reasoning_capability_snapshots (org_id, capability_snapshot_id, "
        "capability_id, capability_version, manifest, manifest_hash) "
        "values (:o, :cs, :c, :cv, cast(:m as jsonb), :h) on conflict do nothing"),
        {"o": org_id, "cs": capability_snapshot, "c": CAPABILITY, "cv": CAPABILITY_VERSION,
         "m": json.dumps(manifest, sort_keys=True), "h": _sha("manifest", org_id)})
    conn.execute(text(
        "insert into reasoning_context_snapshots (org_id, context_snapshot_id, capability_id, "
        "capability_version, capability_snapshot_id, root_node_id, root_node_type, graph_version, "
        "evaluation_time, selector_version, selector, selector_hash, payload_hash, context_hash) "
        "values (:o, :x, :c, :cv, :cs, :n, :nt, 1, :t, '1', cast('{}' as jsonb), :sh, :ph, :ch) "
        "on conflict do nothing"),
        {"o": org_id, "x": context_snapshot, "c": CAPABILITY, "cv": CAPABILITY_VERSION,
         "cs": capability_snapshot, "n": node_id, "nt": ROOT_NODE_TYPE, "t": at,
         "sh": _sha("selector", suffix), "ph": _sha("payload", suffix),
         "ch": _sha("context", suffix)})
    conn.execute(text(
        "insert into reasoning_runs (org_id, run_id, idempotency_key, capability_id, "
        "capability_version, capability_snapshot_id, context_snapshot_id, config_snapshot_id, "
        "trigger_kind, root_node_id, mode, status, evaluation_time, input_manifest, input_hash, "
        "reasoner_plan, reasoner_plan_hash, orchestrator_version, engine_build, output_hash, "
        "started_at, completed_at) values (:o, :r, :r, :c, :cv, :cs, :x, :cfg, :trigger, :n, "
        "'live', 'completed', :t, cast('{}' as jsonb), :ih, cast('[]' as jsonb), :rh, '1', '1', "
        ":oh, :t, :t) on conflict do nothing"),
        {"o": org_id, "r": run_id, "c": CAPABILITY, "cv": CAPABILITY_VERSION,
         "cs": capability_snapshot, "x": context_snapshot, "cfg": config_id, "n": node_id,
         "trigger": TRIGGER_KIND, "t": at, "ih": _sha("input", suffix),
         "rh": _sha("plan", suffix), "oh": _sha("output", suffix)})
    conn.execute(text(
        "insert into reasoning_candidates (org_id, candidate_id, run_id, play_id, play_version, "
        "parameters, score_components, initial_utility_bp, final_utility_bp, confidence_bp, "
        "disposition, rank_position, candidate_hash) values (:o, :cd, :r, :play, :pv, "
        "cast(:params as jsonb), cast('{}' as jsonb), :u, :u, :cf, 'eligible', 1, :h) "
        "on conflict do nothing"),
        {"o": org_id, "cd": candidate_id, "r": run_id, "play": PLAY_ID, "pv": PLAY_VERSION,
         "params": json.dumps({"read_only": True}), "u": utility_bp, "cf": confidence_bp,
         "h": _sha("candidate", suffix)})
    conn.execute(text(
        "insert into reasoning_run_outputs (org_id, run_id, outcome_kind, selected_candidate_id, "
        "ranked_candidate_ids, decision_core, decision_hash, confidence_bp) values "
        "(:o, :r, 'decision', :cd, cast(:ranked as jsonb), cast(:core as jsonb), :dh, :cf) "
        "on conflict do nothing"),
        {"o": org_id, "r": run_id, "cd": candidate_id, "ranked": json.dumps([candidate_id]),
         "core": json.dumps(decision_core), "dh": decision_hash, "cf": confidence_bp})
    conn.execute(text(
        "insert into reasoning_reasoner_results (org_id, result_id, run_id, ordinal, reasoner_id, "
        "reasoner_version, status, input_hash, output, output_hash) values "
        "(:o, :rid, :r, 1, 'core.constraint', '1.0.0', 'completed', :ih, cast(:out as jsonb), "
        ":oh) on conflict do nothing"),
        {"o": org_id, "rid": f"rres_{suffix}", "r": run_id, "ih": _sha("cinput", suffix),
         "out": json.dumps({"checks": []}), "oh": _sha("coutput", suffix)})
    conn.execute(text(
        "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
        "play, status, eval_time, config_snapshot_id, reasoning_run_id, reasoning_candidate_id, "
        "reasoning_decision_hash, authority_expires_at, authority_pack_revision, "
        "authority_binding_version, pack_id, pack_version, capability_id, capability_version) "
        "values (:s, :o, :rid, :n, :sc, :rid, :play, 'open', :t, :cfg, :r, :cd, :dh, :exp, 1, 1, "
        ":p, :pv, :c, :cv) on conflict (signal_id) do nothing"),
        {"s": signal_id, "o": org_id, "rid": rule_id, "n": node_id, "sc": score, "t": at,
         "cfg": config_id, "r": run_id, "cd": candidate_id, "dh": decision_hash,
         "exp": expires_at, "p": PACK_ID, "pv": PACK_VERSION, "c": CAPABILITY,
         "cv": CAPABILITY_VERSION, "play": PLAY_ID})
    conn.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
        "score, state, expires_at, created_at, capability_key, capability_version) values "
        "(:k, :s, :o, 'prescriptive', 'standard', :head, :sit, :sc, 'queued', :exp, :t, :c, :cv) "
        "on conflict (card_id) do nothing"),
        {"k": card_id, "s": signal_id, "o": org_id, "sc": score, "exp": expires_at, "t": at,
         "head": "Chase the countersignature", "sit": "A commitment is open and the clock is on",
         "c": CAPABILITY, "cv": CAPABILITY_VERSION})
    return card_id


# =================================================================================================
# STAGE 6 · THE FOUNDER'S VERDICTS (driven over HTTP, through the route)
# =================================================================================================

@contextmanager
def feedback_client(engine, *, org_id: str, actor_id: str):
    """A `TestClient` over the real intelligence router, bound to THIS script's target database.

    Everything the route does — the authority SELECT, the verdict write, the revision row and the
    call into `lease_from_card_feedback` — runs untouched against the target. Exactly two seams
    are stood in for, and neither of them is a decision the route makes:

    * `get_auth_ctx` supplies the principal an operator's API key would have supplied;
    * `platform.auth.check_org_kill` reads the APPLICATION's configured database (`_engine()`),
      which is not the database this script named — on a developer machine that is the production
      tenant DB, and a script whose whole contract is "I only touch the target you named" must not
      quietly open a connection to another one for a kill-switch row that a pilot tenant does not
      have. It fails open on any error, so standing it down changes no outcome, only which
      database is contacted.

    A context manager because both seams are MODULE GLOBALS: patching them permanently would
    leave the intelligence router pointed at this script's engine for the rest of the process,
    which matters the moment this function is called from anywhere but a one-shot CLI.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api import intelligence_routes as routes
    from genios_engine.platform import auth
    from genios_engine.platform.auth import AuthCtx, get_auth_ctx

    class _Graph:
        def __init__(self, e):
            self.engine = e

    previous_graph, previous_kill = routes._graph, auth.check_org_kill
    routes._graph = _Graph(engine)
    auth.check_org_kill = lambda _org_id: None
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=org_id, actor_id=actor_id,
                                                             scopes=None)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        routes._graph, auth.check_org_kill = previous_graph, previous_kill


def post_bad_timing(engine, *, org_id: str, card_id: str, actor_id: str) -> dict[str, Any]:
    """`POST /v1/intelligence/feedback` with `never_show` + `bad_timing`. The founder's own words.

    `bad_timing` says the card was RIGHT and the moment was wrong, which is the only card verdict
    that is a statement about now — and therefore the only one that earns a lease.
    """
    with feedback_client(engine, org_id=org_id, actor_id=actor_id) as client:
        response = client.post("/v1/intelligence/feedback",
                               json={"action": "never_show", "insight_id": card_id,
                                     "reason": "bad_timing"})
    if response.status_code != 200:
        raise RuntimeError(f"the feedback route refused the seeded card {card_id}: "
                           f"{response.status_code} {response.text}")
    return response.json()


def _backdate_verdict(engine, *, org_id: str, card_id: str, days: int) -> None:
    """Move ONE route-written verdict back by whole days. The only clock this script bends.

    A lease needs its evidence spread across `min_distinct_days`, which exists precisely so that
    one sitting of clicks is not a preference. A seed script cannot sit for two days, so the
    verdicts the route already wrote are dated as the founder's week rather than as this minute.
    The row, its cause, its reason, its actor and its capability are all the route's.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text(
            "update card_feedback_verdicts set occurred_at = occurred_at - cast(:d as interval) "
            "where org_id = :o and card_id = :c"),
            {"o": org_id, "c": card_id, "d": f"{days} days"})


# =================================================================================================
# THE RUN
# =================================================================================================

def seed(url: str, *, org_id: str, at: datetime, accounts: int = ACCOUNTS,
         weeks: int = WEEKS, cards: int = CARDS) -> SeedReport:
    """Every stage, in order, on one instant. Returns what each of them did."""
    from sqlalchemy import text

    from genios_engine.context.graph_store import GraphStore

    report = SeedReport(org_id=org_id, at=at)
    store = GraphStore(url)
    engine = store.engine

    ensure_org(engine, org_id, at=at)
    report.accounts, report.messages = seed_correspondence(
        store, org_id=org_id, at=at, accounts=accounts, weeks=weeks)

    drain = drive_the_drain(store, org_id=org_id, at=at)
    report.history_points = int(drain.get("history_backfilled") or 0)
    report.trend_facts = int(drain.get("trend_facts") or 0)

    report.learning = drive_the_weekly_pass(engine, org_id=org_id, at=at)
    with engine.connect() as conn:
        report.behavior_entries = int(conn.execute(text(
            "select count(*) from learned_brain_entries where org_id=:o and brain='behavior' "
            "and active"), {"o": org_id}).scalar() or 0)

    # ---- the Adaptive half: audited cards, then the founder's verdicts through the route -------
    with engine.begin() as conn:
        nodes = [row[0] for row in conn.execute(text(
            "select node_id from graph_nodes where org_id=:o and valid_to is null "
            "order by node_id limit :n"), {"o": org_id, "n": cards})]
        card_ids = [seed_audited_card(conn, org_id=org_id, index=i, at=at, node_id=nodes[i])
                    for i in range(min(cards, len(nodes)))]
    report.cards = len(card_ids)

    for position, card_id in enumerate(card_ids):
        post_bad_timing(engine, org_id=org_id, card_id=card_id,
                        actor_id=ACTORS[position % len(ACTORS)])
        report.verdicts += 1
        # Every verdict but the last is dated back a day, so the LAST one — the call that finds a
        # cohort spread over four days and states the tenant's live preference — is the route's
        # own, at the route's own instant. (The third call already earns a lease on three days of
        # complaints; the fourth supersedes it. Both are the route's, and both are real.)
        remaining = len(card_ids) - 1 - position
        if remaining:
            _backdate_verdict(engine, org_id=org_id, card_id=card_id, days=remaining)

    with engine.connect() as conn:
        report.lease_rows = int(conn.execute(text(
            "select count(*) from temporary_memories where org_id=:o and active"),
            {"o": org_id}).scalar() or 0)
    if not report.behavior_entries:
        report.notes.append("no behaviour entry was published — read the run's counts above")
    if not report.lease_rows:
        report.notes.append("no lease is live — the last route call did not clear the floors")
    return report


def render(report: SeedReport) -> str:
    lines = [f"pilot seed — org={report.org_id}",
             f"  at               {report.at:%Y-%m-%d %H:%M} UTC", "",
             f"  population       {report.accounts} accounts, {report.messages} messages",
             f"  drain            {report.history_points} history points, "
             f"{report.trend_facts} trend facts",
             f"  weekly pass      {json.dumps(report.learning, default=str)}",
             f"  behaviour brain  {report.behavior_entries} active entries",
             f"  cards            {report.cards} audited, {report.verdicts} verdicts posted "
             "through the route",
             f"  adaptive leases  {report.lease_rows} live"]
    lines += [f"  NOTE: {note}" for note in report.notes]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="brain_pilot_seed",
        description="seed a pilot tenant and drive the Behaviour and Adaptive brains")
    parser.add_argument("--org", required=True, help="the tenant to seed")
    parser.add_argument("--accounts", type=int, default=ACCOUNTS)
    parser.add_argument("--weeks", type=int, default=WEEKS)
    parser.add_argument("--cards", type=int, default=CARDS)
    parser.add_argument("--json", action="store_true", help="emit the seed report as JSON")
    add_database_argument(parser)
    args = parser.parse_args(argv)

    url = resolve_database_url(args, purpose="J4 pilot seed (WRITES to this database)")
    at = datetime.now(timezone.utc)
    report = seed(url, org_id=args.org, at=at, accounts=args.accounts, weeks=args.weeks,
                  cards=args.cards)
    print(json.dumps(report.as_dict(), indent=2, default=str) if args.json else render(report))
    return 0 if report.behavior_entries and report.lease_rows else 1


if __name__ == "__main__":                              # pragma: no cover - CLI entry
    raise SystemExit(main())
