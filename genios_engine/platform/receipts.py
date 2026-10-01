"""Semantic-readiness receipts — the runtime half of every structural claim.

Health metrics used to prove that jobs ran and schemas existed: an empty sweep looked healthy,
a skip read as a pass, and "Present / Wired / Tested" was communicated as active intelligence.
These receipts ask the other question — is the DEPLOYED tenant in the state the code implies? —
one read-only SELECT per structural claim, safe to run against production.

`scripts/runtime_receipts.py` is the CLI over this module; `/health/readiness` is the API over
it. One list of claims, two surfaces, so the release gate and the operator dashboard cannot
drift apart about what "ready" means.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text

# ⛔ The organisation-readiness counts, from the FLOOR — not from `executive/`. Both this module and
# `executive/readiness.py` need the same three queries, and duplicating them would let one drift from
# the other. Importing them from `executive/` would have made the floor import a layer, which the
# topology test does not catch because `platform` is cross-cutting and exempt — and an import nothing
# fails the build on is not a safe one, it is an unchecked one.
from genios_engine.platform.org_readiness_sql import COUNT_SQL as _RD_SQL
from genios_engine.platform.org_readiness_sql import COUNT_SQL_FLEET as _RD_SQL_FLEET
from genios_engine.platform import org_readiness_sql as _RD

@dataclass(frozen=True)
class Receipt:
    """One structural claim, its query, and the predicate that decides pass/fail.

    `expect` receives the single scalar the query returns and answers "is the deployed system in
    the state the code implies?". Keeping the predicate next to the claim is what stops a receipt
    from quietly becoming a number nobody reads.
    """
    layer: str
    claim: str
    sql: str
    expect: Callable[[object], bool]
    detail: str = ""
    #: This claim is about the DEPLOYMENT, not the tenant, and its query is therefore not
    #: org-filtered. Declared rather than inferred: a receipt that simply forgot `:org` answers
    #: about every tenant at once while appearing on one tenant's readiness page — their parked
    #: queue reported as this one's — so "no filter" has to be a statement somebody made. The
    #: only members are questions whose answer cannot differ per tenant because the thing asked
    #: about is shared: the schema itself.
    fleet_wide: bool = False


def _org_filter(org: str | None, alias: str = "") -> str:
    p = f"{alias}." if alias else ""
    return f" and {p}org_id = :org" if org else ""


def _UNDECLARED_UNWRITTEN_FACTS_SQL(org: str | None) -> str:
    r"""How many fact paths a reasoning unit BINDS have no rows and no declaration.

    ⛔ THE BOUND LIST IS DERIVED FROM `expertise._ROSTER`, never copied. A seventh role added to a unit
    enters this query without an edit — the rule `S5.U02` established for `AXIS_SOURCES`.

    ⛔ THE QUESTION IS NOT "IS ANY BOUND PATH EMPTY". Measured 2026-10-01: 14 of 22 are, for one root
    (no CRM connector) this layer cannot clear. `api/routes.py:161` computes `ready = not failed` from
    this list, so that claim would be permanently red, and a gate that is always red is a gate nobody
    reads. The claim is the one that is true today and false when it gets worse.

    ⛔ IT COUNTS ROWS PER PATH, NOT DISTINCT NODES. A path with one row has a writer; that is the whole
    question. How WELL it is covered is `deal.status`'s 3-of-293 problem, a different measurement with
    a different mover.

    The paths are inlined as literals for the reason the sibling builder states: `evaluate()` binds
    exactly one parameter. A test asserts every one matches `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$`.
    """
    from genios_engine.reason.unit_health import DECLARED_UNWRITTEN_PATHS, roster_fact_paths

    candidates = sorted(set(roster_fact_paths()) - set(DECLARED_UNWRITTEN_PATHS))
    if not candidates:
        return "select 0"
    wanted = ", ".join(f"'{path}'" for path in candidates)
    return (
        f"select {len(candidates)} - count(distinct field) from graph_facts "
        f"where field in ({wanted})" + _org_filter(org)
    )


def _PLACEHOLDER_COMPONENTS_SQL(org: str | None) -> str:
    r"""Candidates the CURRENT scorer wrote carrying the neutral-default ranking formula.

    ⛔ THE PREDICATE IS UNCHANGED FROM THE ORIGINAL RECEIPT. The three equalities below are
    byte-for-byte what this receipt has always asked. The ONLY thing added is a lower bound, and
    that is the entire fix — see `speedrun008/YCW27/layer-2-reasoning/12-AUDIT-D-the-frozen-formula-receipt.md`.

    ⛔ WHY A LOWER BOUND IS NOT A WEAKENING. `reasoning_candidates` is append-only and this codebase
    soft-deletes only, so the 59 rows the defect wrote on one org between 2026-08-17 and
    2026-09-07 are permanent. Without a bound the receipt returns 59 forever, for a defect closed
    on 2026-09-08, and `api/routes.py:161` computes `ready = not failed` over it — one unfixable
    receipt holding the release gate shut. **A receipt over append-only history needs a lower
    bound, or it is not a gate but a monument.**

    ⛔ THE BOUND IS IMPORTED, NEVER RESTATED HERE. `reason/unit_health.neutral_default_boundary()`
    owns the date together with the commit that establishes it, so the receipt cannot drift from
    the declaration by carrying its own copy. Measured 2026-10-01: 34,167 candidates written at or
    after the boundary, across all three orgs, **zero** frozen.

    The date is inlined as a literal because `evaluate()` binds exactly one parameter; a test
    asserts it matches `^\d{4}-\d{2}-\d{2}$` before it is interpolated.
    """
    from genios_engine.reason.unit_health import neutral_default_boundary

    boundary = neutral_default_boundary()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", boundary):
        raise ValueError(f"boundary must be an ISO date, got {boundary!r}")
    return (
        "select count(*) from reasoning_candidates where "
        "score_components->>'impact' = '5000' and score_components->>'risk' = '5000' "
        f"and score_components->>'effort' = '5000' and created_at >= '{boundary}'"
        + _org_filter(org)
    )


def _UNDECLARED_NEVER_COMPLETED_SQL(org: str | None) -> str:
    r"""Units that have RUN and never once completed, and that nobody declared.

    ⛔ THIS QUESTION IS NOT THE SILENCE QUESTION, AND THE DIFFERENCE IS ONE CLAUSE.
    `_UNDECLARED_SILENT_UNITS_SQL` filters `status = 'completed'` and asks whether the completions
    said anything. A unit with **zero** completed rows is therefore not a row with a low share —
    **it is not a row** — so it cannot appear in that GROUP BY at all. Measured 2026-10-01,
    `core.relationship` has **929 runs and 0 completions** and the silence receipt PASSES.

    > A unit that never completes is not a quiet unit; it is an absent one, and a question asked
    > only of completions cannot see it.

    ⛔ SO THIS ONE DELIBERATELY DOES NOT FILTER BY STATUS. That filter is the whole defect. It
    groups every result row per unit and keeps the units whose completed count is zero.

    ⛔ `having count(*) > 0` IS NOT REDUNDANT, IT IS THE POINT. A unit with no rows at all is a
    different fact — nobody scheduled it — and belongs to ALARM A2, not here.
    `core.signal_composition` is exactly that: 0 runs, because `DEAL_HEALTH_V1` has never been
    swept. A ratio would make 0/0 and 0/929 the same number.

    ⛔ THE EXCUSED SET IS IMPORTED AND PARTLY DERIVED. `core.policy` also has zero completions (165
    runs) and is legitimately accounted for by the sibling grain: all four fact paths it binds are
    in `DECLARED_UNWRITTEN`. `unit_health.starved_by_declared_paths()` computes that from the
    roster, so this receipt never carries a second copy of the fact and cannot go stale when a path
    gains a writer. Inlined as literals because `evaluate()` binds exactly one parameter; a test
    asserts every id matches `^[a-z][a-z0-9_.]+$`.
    """
    from genios_engine.reason.unit_health import (DECLARED_NEVER_COMPLETED_IDS,
                                                  starved_by_declared_paths)

    excused = sorted(DECLARED_NEVER_COMPLETED_IDS | starved_by_declared_paths())
    for unit in excused:
        if not re.fullmatch(r"[a-z][a-z0-9_.]+", unit):
            raise ValueError(f"not a unit id: {unit!r}")
    declared = ", ".join(f"'{unit}'" for unit in excused) or "''"
    return (
        "select count(*) from ("
        "  select reasoner_id"
        "    from reasoning_reasoner_results"
        "   where 1=1" + _org_filter(org) +
        "   group by reasoner_id"
        "  having count(*) > 0"
        "     and sum(case when status = 'completed' then 1 else 0 end) = 0"
        f"     and reasoner_id not in ({declared})"
        ") as undeclared_never_completed"
    )


def _UNDECLARED_SILENT_UNITS_SQL(org: str | None) -> str:
    """How many units are silent above the threshold and NOT declared in `reason/unit_health`.

    ⛔ THE PREDICATE COMES FROM `reason/unit_health.SILENT_SQL`, NEVER RESTATED HERE. It is the same
    rule `is_silent` applies in Python, and `tests/reason/test_a_unit_that_says_nothing_is_not_working.py`
    runs both over the same production rows under the `pg` gate. Two expressions of one rule that are
    never compared eventually disagree — this programme has found that shape five times.

    ⛔ A SHARE, NOT A COUNT. One silent completion out of a thousand is noise; ninety per cent is a
    unit that does not work. The threshold is `SILENT_THRESHOLD_PCT` and lives with the declaration.

    ⛔ THE DECLARED SET IS INLINED AS LITERALS RATHER THAN BOUND. `evaluate()` passes exactly one
    parameter (`:org`), so a second bound list would need a signature change across every receipt.
    The ids are module constants matching `^[a-z][a-z0-9_.]+$`, asserted by a test, so there is
    nothing here a caller can influence.
    """
    from genios_engine.reason.unit_health import (DECLARED_SILENT_IDS, SILENT_SQL,
                                                  SILENT_THRESHOLD_PCT)

    declared = ", ".join(f"'{unit}'" for unit in sorted(DECLARED_SILENT_IDS)) or "''"
    return (
        "select count(*) from ("
        "  select reasoner_id,"
        f"         100 * sum(case when {SILENT_SQL.strip()} then 1 else 0 end) / count(*) as pct"
        "    from reasoning_reasoner_results"
        "   where status = 'completed'" + _org_filter(org) +
        "   group by reasoner_id"
        f"  having 100 * sum(case when {SILENT_SQL.strip()} then 1 else 0 end) / count(*) "
        f"         >= {int(SILENT_THRESHOLD_PCT)}"
        f"     and reasoner_id not in ({declared})"
        ") as undeclared_silent"
    )


def receipts(org: str | None) -> list[Receipt]:
    # THE DORMANCY WINDOW IS THE THRESHOLD, and it is imported rather than restated. L2 decides a
    # situation has ended after `DORMANT_AFTER_DAYS` of silence, so a tenant that has been fed
    # nothing for that long has, provably, no working set left — whatever the other receipts say.
    # Picking any other number here would invent a second opinion about when quiet becomes empty.
    # Imported inside the function, the way `platform/wiring.py` already reaches into `context`.
    from genios_engine.capture.pipeline import (JUDGED_DROP_CODES,
                                                JUDGED_DROP_PAYLOAD_TTL_DAYS)
    from genios_engine.api.account_routes import RETAINED_AFTER_ERASURE
    from genios_engine.context.runner import MAX_PASSES
    from genios_engine.context.situations import DORMANT_AFTER_DAYS
    from genios_engine.deliver.routing import AGENT_TRANSPORTS
    from genios_engine.deliver.units import _implemented_channels

    # The same intersection `deliver.outbox.deliverable_channels` computes in Python:
    # registered AND implemented AND not an agent transport. Inlined as a literal list so
    # one SQL scalar can answer it, derived from the two sources so it cannot drift from
    # what the drain will actually accept.
    pushable = sorted(_implemented_channels() - set(AGENT_TRANSPORTS))

    o = _org_filter(org)
    return [
        # ── L1 capture ────────────────────────────────────────────────────────────────
        Receipt("L1", "no sync cursor is ahead of the clock",
                f"select count(*) from sync_cursors where watermark > now(){o}",
                lambda n: n == 0,
                "a future watermark asks the provider for changes since a date that has not "
                "happened; the connector goes silent while still reporting success"),
        Receipt("L1", "the parked queue is not a black hole",
                f"select count(*) from parked_events where status='pending'{o}",
                lambda n: n == 0,
                "pending forever means a park is a slower delete"),
        Receipt("L1", "every drop we might be wrong about can still be reviewed",
                # SCOPED TO THE JUDGED DROPS, and that is a correction rather than a narrowing.
                # Asked of EVERY drop this counted 2,818 deterministic refusals that by documented
                # policy retain nothing — "L1 stays a filter, not a warehouse" — so it could never
                # pass, on any tenant, in any state. A receipt that cannot pass is exactly the
                # "a skip read as a pass" failure this module exists to end, wearing the other
                # colour: permanent red teaches an operator to stop reading the page.
                #
                # The window is the retention policy's own, so a judged drop past its TTL is
                # EXPECTED to have no payload and does not count against the tenant. That also
                # means the receipt self-clears: 26 events judged in August, before this retention
                # landed, fail it today and stop counting when they age past 90 days.
                "select count(*) from source_events se where se.outcome='dropped' "
                f"and se.captured_at > now() - interval '{JUDGED_DROP_PAYLOAD_TTL_DAYS} days' "
                "and exists (select 1 from event_trace t where t.org_id=se.org_id "
                "            and t.event_id=se.event_id and t.action='drop' "
                f"            and t.reason_code in ({', '.join(repr(c) for c in sorted(JUDGED_DROP_CODES))})) "
                "and not exists (select 1 from raw_payloads rp where rp.event_id=se.event_id "
                "                and rp.org_id=se.org_id)"
                + _org_filter(org, "se"),
                lambda n: n == 0,
                "a provider's SPAM label is a fact and needs no second look; a model saying "
                "\"this looks like junk\" is a JUDGMENT, and judgments improve. Without the body "
                "\"we improved the filter\" is an assertion about mail that no longer exists"),
        Receipt("L1", "the tenant is still being fed",
                # `captured_at`, not `occurred_at`: this asks whether OUR pipeline is receiving,
                # and a backfill of last quarter's mail is healthy ingestion of old messages.
                # `coalesce` makes an org with no events at all FAIL rather than return NULL —
                # a tenant nothing has ever arrived for is the loudest version of this failure,
                # and a NULL that slipped through `expect` as falsey would report it as a pass.
                "select coalesce(extract(day from (now() - max(captured_at)))::int, "
                f"{DORMANT_AFTER_DAYS}) from source_events where true{o}",
                lambda days: int(days) < DORMANT_AFTER_DAYS,
                "every other receipt can pass while a tenant's feed is dead: the graph, the packs "
                "and the cards are all still there. What empties is the WORKING SET — L2 marks a "
                f"situation dormant after {DORMANT_AFTER_DAYS} days of silence, so a feed quiet "
                "that long leaves nothing active to reason about, and nothing else says so"),
        Receipt("L1", "attachments carry readable text",
                "select count(*) from document_jobs where status in ('unsupported','fetch_failed')"
                + _org_filter(org),
                lambda n: n == 0,
                "in a fundraising inbox the deck and the rubric ARE the content"),

        Receipt("L1", "a deleted tenant leaves nothing behind",
                # ASKED OF THE DEPLOYED SCHEMA, because that is where the answer lives. Erasure
                # deletes the `orgs` row and migration 0033's foreign keys take everything that
                # hangs off it — directly, or through a parent that does, which is how the four
                # `reasoning_*` children go without any of them being named. So the question is
                # not "is this table in a list" but "is it reachable from `orgs` by CASCADE", and
                # a recursive walk of the constraint graph is the only honest way to ask it.
                #
                # `_ORG_SCOPED_TABLES`'s own comment names the failure this catches: "a name
                # missing here leaks silently". A table added next month with an `org_id` and no
                # foreign key is a deletion request that quietly stops being complete, and
                # nothing anywhere would have said so. Measured 2026-09-17: 178 org-scoped
                # tables, 0 unreachable.
                "with recursive fk(child, parent) as ("
                "  select tc.table_name, ccu.table_name"
                "    from information_schema.table_constraints tc"
                "    join information_schema.referential_constraints rc"
                "      on rc.constraint_name = tc.constraint_name"
                "    join information_schema.constraint_column_usage ccu"
                "      on ccu.constraint_name = tc.constraint_name"
                "   where tc.constraint_type = 'FOREIGN KEY' and rc.delete_rule = 'CASCADE'), "
                "reachable(tbl) as ("
                "  select child from fk where parent = 'orgs' "
                "  union select f.child from fk f join reachable r on r.tbl = f.parent) "
                "select count(*) from information_schema.columns c "
                "  join information_schema.tables t"
                "    on t.table_name = c.table_name and t.table_schema = c.table_schema "
                " where c.table_schema = 'public' and c.column_name = 'org_id' "
                "   and t.table_type = 'BASE TABLE' "
                f"   and c.table_name not in ({', '.join(repr(x) for x in sorted(RETAINED_AFTER_ERASURE))}) "
                "   and c.table_name not in (select tbl from reachable)",
                lambda n: n == 0,
                "every table left over holds a deleted customer's data under an org_id that "
                "resolves to nobody — the three retained financial ledgers are named in "
                "`RETAINED_AFTER_ERASURE` and are the only rows permitted to outlive a tenant",
                # THE SCHEMA IS SHARED, so this answer cannot differ per tenant. Declared, not
                # inferred from the absent filter — see `Receipt.fleet_wide`.
                fleet_wide=True),

        # ── L2 context ────────────────────────────────────────────────────────────────
        Receipt("L2", "the tenant's own identities are known",
                f"select count(*) from org_seats where active{o}",
                lambda n: n > 0,
                "org_seats empty ⇒ internal_emails is empty ⇒ every self-filter is a no-op and "
                "the org models its own founder as a counterparty"),
        Receipt("L2", "no person node holds thread state fed by several threads",
                "select count(*) from (select f.subject_node_id from graph_facts f "
                "where f.field='thread.ball_in_court' and f.valid_to is null"
                + _org_filter(org, "f") +
                " group by f.subject_node_id having count(*) > 1) t",
                lambda n: n == 0,
                "one last-write-wins row per person collapses every conversation into the newest"),

        Receipt("L2", "the sweep settles instead of chasing itself",
                # `_record_convergence` re-hashes the graph after a pass and counts how many it
                # took to stop moving; at `MAX_PASSES` it stamps `exceeded_at` and raises
                # `l2_convergence_exceeded` with the situation ids still changing. That alert is
                # a LOG LINE — greppable by an operator already looking, invisible to one who is
                # not. The stamp is in a table, so it can be asked instead.
                #
                # Measured 2026-09-17: three orgs, `exceeded_at` null on all three and `passes`
                # zero — the hash settles on the first pass every time. Two clean sweeps were
                # called evidence rather than proof, which was right; this is what turns "we
                # watched it twice" into something that stays watched.
                f"select count(*) from l2_convergence where exceeded_at is not null{o}",
                lambda n: n == 0,
                f"a sweep that never settles re-derives the same situations up to {MAX_PASSES} "
                "times and then gives up mid-pass, so the tenant's picture is whatever the last "
                "partial pass left — and `detail` names the situations that were still moving"),

        # ── L3 domain expertise ───────────────────────────────────────────────────────
        Receipt("L3", "compiled expertise packages exist",
                f"select count(*) from expertise_packages where 1=1{o}",
                lambda n: n > 0,
                "zero packages ⇒ the compiler is dark or every situation abstains"),
        Receipt("L3", "the tenant is bound to a pack",
                f"select count(*) from tenant_packs where state='active'{o}",
                lambda n: n > 0),

        # ── L4 executive · ORGANISATION DATA ──────────────────────────────────────────
        #
        # ⛔ WHY THESE THREE ARE NEW. Twenty-three receipts existed and NOT ONE was about organisation
        # data. So a tenant with a compiled pack, a live activation row, a full graph and every receipt
        # green could still be completely unroutable — which is the state the pilot is in, and the whole
        # reason `executive/` "examines nothing every tick".
        #
        # `test_a_tenant_nobody_feeds_is_not_ready` made the identical argument one layer down: *"Every
        # other receipt can pass while a tenant's feed is dead. ... seventeen receipts still say PASS.
        # Nothing said the feed had stopped."* This is that failure one layer up.
        #
        # The SQL is imported from `executive/readiness.COUNT_SQL` rather than retyped, so the receipt
        # and the readiness page cannot drift about what "ready" means — the same rule this module's own
        # docstring states: *"One list of claims, two surfaces."*
        #
        # ⛔ ORG-FILTERED, ALWAYS. Every one of these is a question about a TENANT, so none may be
        # `fleet_wide`: answering it unfiltered would report one tenant's seats on another's page.
        Receipt("L4", "the tenant has at least one active seat",
                _RD_SQL[_RD.SEATS] if org else _RD_SQL_FLEET[_RD.SEATS],
                lambda n: n > 0,
                "no active seat means nobody to assign an owner to, so every execution plan is "
                "refused before it is written"),
        Receipt("L4", "at least one seat has a manager",
                _RD_SQL[_RD.REPORTING_LINE] if org else _RD_SQL_FLEET[_RD.REPORTING_LINE],
                lambda n: n > 0,
                "with no reporting line, rung 7 of the ladder (escalate -> manager) climbs into "
                "nothing and a stalled item is never escalated"),
        # ⛔ ACTIVATED IS NOT THE SAME AS RAN. `platform/l3_activation` shipped once with a reader, a
        # fail-closed gate, an erasure row, an admin API and a report -- AND NO CALLER. The lesson
        # Plane R recorded from it: *"a switch that reports itself on and changes nothing is worse than
        # no switch."*
        #
        # `reasoning_runs.mode` already answers this exactly: `domain_shadow` writes
        # `ExecutionMode.LIVE if live_row else ExecutionMode.SHADOW`, and only the live lane reaches
        # `_persist_live`. So a tenant with an activation row and zero live runs has a switch that is on
        # and doing nothing -- which is precisely the state this receipt exists to make visible.
        Receipt("L4", "the live pass has actually run, not only the shadow pass",
                "select count(*) from reasoning_runs where mode = 'live'" + _org_filter(org),
                lambda n: n > 0,
                "an activation row with no live run means the switch reports itself on and changes "
                "nothing -- the exact defect l3_activation shipped with once"),

        # ⛔ L2 · EVERY REASONING UNIT THAT SAYS NOTHING IS ONE WE DECLARED.
        #
        # Measured 2026-10-01: `core.impact` completes 1,973 times with 100% silent output
        # (`{"impact_signal_count": 0}`) and `core.opportunity` 94%. Both succeed. Both compute
        # nothing. Every reader downstream treats the absence as "no signal here" rather than "this
        # unit had nothing to read" — and `core.tradeoff`'s `cost_vs_benefit` axis has fired 0 times
        # in 1,200 rows as a direct result, while a unit test proves the axis works on a prior the
        # test supplies itself.
        #
        # ⛔ THE CLAIM IS NOT "NO UNIT IS SILENT", AND THAT CHOICE IS THE WHOLE DESIGN.
        # `api/routes.py:161` computes `ready = not failed` from this list, and it is what the
        # release gate runs. Asserting "no unit is silent" would be PERMANENTLY RED for an upstream
        # reason this layer cannot clear — `deal.status` has no writer — and a gate that is always
        # red is a gate nobody reads. So the claim is the one that is true today and false the moment
        # it gets worse: every silent unit is a DECLARED one, with a reason and a mover.
        #
        # ⛔ AND THE SILENCE TEST IS IMPORTED, NOT RESTATED HERE. `reason/unit_health.SILENT_SQL` is
        # the same rule the probe applies in Python, and a test runs both over the same production
        # rows — because two expressions of one rule that are never compared eventually disagree.
        Receipt("L2", "every reasoning unit that says nothing is one we declared",
                _UNDECLARED_SILENT_UNITS_SQL(org),
                lambda n: n == 0,
                "a unit that completes and computes nothing is read downstream as 'no signal here' "
                "rather than 'nothing to read' -- declare it in reason/unit_health with a reason and "
                "a mover, or find out why it went quiet"),

        # ⛔ L2 · A UNIT THAT RUNS AND NEVER COMPLETES IS DECLARED, OR IT IS INVISIBLE.
        #
        # The silence receipt above asks whether COMPLETIONS said anything, so it cannot see a unit
        # with no completions -- that unit is not a low row, it is no row. Measured 2026-10-01:
        # `core.relationship`, 929 runs, 0 completions, and the silence receipt green. The fact had
        # been written in prose twice (once below, once inside DECLARED_SILENT["core.impact"]'s own
        # reason) and declared nowhere a receipt could read.
        Receipt("L2", "every unit that runs and never completes is a declared one",
                _UNDECLARED_NEVER_COMPLETED_SQL(org),
                lambda n: n == 0,
                "a unit with runs and zero completions is absent, not quiet, and the silence "
                "receipt cannot see it -- declare it in reason/unit_health.DECLARED_NEVER_COMPLETED "
                "with a reason, a mover and the run count, or find out what stopped it answering. "
                "A unit with no runs at all is a different fact (nobody scheduled it) and belongs "
                "to the roster, not here"),

        # ⛔ L2 · EVERY FACT PATH A UNIT BINDS IS EITHER WRITTEN OR DECLARED UNWRITTEN.
        #
        # Measured 2026-10-01: `expertise._ROSTER` binds 22 fact paths and **14 have zero rows**. One
        # root — there is no CRM connector, so `deal.*` is empty beyond `status` (3 rows) and
        # `last_inbound` (34). `core.policy` has skipped all 165 of its rows because ALL FOUR of its
        # essential fields are in that list: it is not failing, it is correctly refusing to run on
        # nothing, forever.
        #
        # ⛔ AND THIS IS WHAT `no_declared_input_available` CANNOT SAY. That skip reason conflates
        # "this situation did not carry the field" with "nothing has ever written the field anywhere".
        # Different movers; the second is not fixable by looking at the situation at all.
        #
        # ⛔ THE CLAIM IS NOT "no bound path is empty", for the reason the sibling receipt states:
        # `ready = not failed`, and 14 of 22 are empty for a reason this layer cannot clear. This one
        # passes today and fails when a FIFTEENTH goes quiet — which produces no error anywhere else.
        Receipt("L2", "every fact path a reasoning unit binds is written or declared unwritten",
                _UNDECLARED_UNWRITTEN_FACTS_SQL(org),
                lambda n: n == 0,
                "a bound fact path with no writer means a unit role that can never bind -- declare "
                "it in reason/unit_health with a reason and a mover, or find out what stopped "
                "writing it"),

        # ⛔ L5 · EVERY DELIVERED CARD SAYS WHICH KIND OF OUTPUT IT IS, OR SAYS IT WAS NEVER ROUTED.
        #
        # `0190` made `cards.output_lane` nullable so the migration could land on a live table, and
        # a nullable column with no reader is how "built, tested, green, called by nothing" happens
        # — which is the defect this whole lane vocabulary was added to end, and which the lane
        # vocabulary then reproduced for one step. A NULL here means a card written by a path that
        # does not carry a lane at all; `unrouted` means the delivery layer looked and found nothing
        # it could honour, which is an answer and passes.
        Receipt("L5", "every delivered card carries a lane, or is labelled unrouted",
                "select count(*) from cards where output_lane is null" + _org_filter(org),
                lambda n: n == 0,
                "a card with no lane at all was written by a path that never read the signal's "
                "routing -- the founder cannot tell a decision from a thing to watch"),

        # ⛔ NO CHANNEL RECEIPT HERE, DELIBERATELY. One already exists further down — *"there is a
        # channel this tenant can be reached on"*, over the same `org_channels` table. Adding a second
        # would be two receipts answering one question, and the first time somebody tuned one they
        # would disagree. `executive/readiness.py` still reports channels, because the readiness page
        # needs all three requirements in ONE verdict with a named fix — that is the other surface this
        # module's docstring names, not a duplicate claim.

        # ── L4 reasoning ──────────────────────────────────────────────────────────────
        Receipt("L4", "more than one candidate is ever considered",
                "select coalesce(max(c), 0) from (select count(*) as c from reasoning_candidates"
                + (" where org_id = :org" if org else "") +
                " group by run_id) t",
                lambda n: n > 1,
                "exactly one candidate per run means no alternative, no do-nothing, no ranking"),
        Receipt("L4", "the score components the scorer writes NOW are measured, not placeholders",
                _PLACEHOLDER_COMPONENTS_SQL(org),
                lambda n: n == 0,
                "a candidate whose impact, risk and effort are all the 5000 neutral default was "
                "ranked by nothing -- every reasoning unit that adjusts those components was a "
                "no-op on it. This happened: 59 rows on one org, and 53 of them carried ALL FIVE "
                "of guards.CANDIDATE_COMPONENTS at 5000. It was closed on 2026-09-08 by 75096bab "
                "and 34,167 candidates have been clean since, so the question is dated at that "
                "boundary -- declared in reason/unit_health.CLOSED_DEFECTS, which also records "
                "why the history cannot be repaired. A hit here means the defect returned"),
        Receipt("L4", "the system has abstained at least once",
                "select count(*) from reasoning_run_outputs where outcome_kind <> 'decision'"
                + _org_filter(org),
                lambda n: n > 0,
                "a reasoner that has never once said 'I don't know' is not exercising a "
                "confidence floor — DEFER is unreachable when confidence_floor_bp defaults to 0"),

        # ── L5 executive ──────────────────────────────────────────────────────────────
        Receipt("L5", "decisions become tracked commitments",
                f"select count(*) from executions where 1=1{o}",
                lambda n: n > 0,
                "zero executions ⇒ every recommendation stops at a card; nothing is ever owed, "
                "chased, escalated or closed"),

        # ── L6 delivery ───────────────────────────────────────────────────────────────
        Receipt("L6", "cards distinguish a warning from an order",
                f"select count(distinct level) from cards where 1=1{o}",
                lambda n: n > 1,
                "one distinct level across every card means the pack's predictive rules are "
                "rendered as direct commands"),
        # ⛔ REWRITTEN 2026-10-01. It asked `render_mode <> 'llm'` and expected zero, which was wrong
        # in BOTH directions. Measured on production:
        #
        #     llm        105 cards,  13 with an empty artifact body
        #     raw_slot    59 cards,  24 with an empty artifact body
        #     template     1 card,    1
        #
        #   (1) it COUNTED 35 `raw_slot` cards that do have a body. A deterministic fallback carrying
        #       real content is the designed behaviour when the model refuses or the validator rejects
        #       — not a stub — so `expect n == 0` made that fallback a permanent failure.
        #   (2) it MISSED 13 `llm` cards with an empty body, which by this receipt's own detail ARE
        #       "a card with no content".
        #
        # ⛔ AND THE HONEST QUESTION IS NARROWER STILL. Of the 38 empty-body cards, 19 ABSTAINED — 13
        # `review` and 6 `observation` — and an abstained card is SUPPOSED to carry no draft:
        # `card_builder` strips `run_play` and `render.py` sets `art = ""` when the artifact is
        # rejected. Demanding a body from those 19 would demand a draft the engine deliberately
        # refused to write.
        #
        # What is left is the thing the claim always meant: a card with no content that is
        # nonetheless giving an order. Measured: 18, so this receipt still FAILS. ⛔ A receipt is not
        # fixed by making it green.
        #
        # `level in ('prescriptive','predictive')` is `abstention.ACTIONABLE`, and a NULL level is
        # EXCLUDED rather than assumed — the rule `calibrate._PRECISION_SQL` already states: *"a card
        # whose level nobody recorded is ungradeable, and defaulting it to 'instruction' is how the
        # old behaviour comes back."*
        #
        # Both conditions, not either: a card can be downgraded by level with no abstention reason
        # (one such card exists), and a reason without a downgrade is a contradiction the card layer
        # does not produce.
        Receipt("L6", "no card gives an order with an empty draft",
                "select count(*) from cards "
                "where coalesce(artifact->>'body', '') = '' "
                "  and abstained_because is null "
                "  and level in ('prescriptive', 'predictive')" + _org_filter(org),
                lambda n: n == 0,
                "a card at an instructing level with no artifact body tells the reader to act and "
                "gives them nothing to act with -- an ABSTAINED card correctly carries no draft and "
                "is excluded"),
        Receipt("L6", "there is a channel this tenant can be reached on",
                # THE PRECONDITION, ASKED FIRST. Measured 2026-09-17: all three orgs register
                # `in_app` and nothing else, and `in_app` is the PULL surface — the card is
                # already sitting on it, there is nothing to send. So the intersection is empty,
                # `deliverable_channels` correctly returns [], and every push receipt below it
                # fails for a reason that has nothing to do with the pipeline.
                "select count(*) from org_channels where active "
                f"and channel in ({', '.join(repr(c) for c in pushable)})" + o,
                lambda n: n > 0,
                "a tenant with no push channel is not a broken pipeline and must not read as "
                "one: nothing is wrong upstream, there is simply nowhere to send"),
        Receipt("L6", "the delivery control plane has run",
                f"select count(*) from delivery_outbox where 1=1{o}",
                lambda n: n > 0,
                # The old detail here read "push is gated on a band the scoring formula cannot
                # reach". That was true when it was written and is now false, and a receipt whose
                # detail names the wrong cause sends an operator to rewrite a scoring formula
                # when the answer is "connect a channel". Measured 2026-09-17: 71 of 133 cards
                # sit at high or critical, and 21 pass PUSHABLE_CARDS_SQL — the authority
                # predicate included — at this instant.
                "cards clear the push band and pass the authority predicate; check the channel "
                "receipt above first, because an empty outbox on a tenant with no channel is "
                "the expected state and not a failure of this layer"),

        # ── L7 learning ───────────────────────────────────────────────────────────────
        Receipt("L7", "the learning engine has executed",
                f"select count(*) from learning_runs where 1=1{o}",
                lambda n: n > 0),
        Receipt("L7", "calibration has executed",
                f"select count(*) from calibration_runs where 1=1{o}",
                lambda n: n > 0,
                "precision → auto-mute → bounded nudges has never fired; the outcome data L5 "
                "starts producing would go unconsumed"),
        Receipt("L7", "the counterfactual ledger joins end to end",
                f"select count(*) from counterfactual_ledger where card_id is not null{o}",
                lambda n: (n or 0) > 0,
                "one row per recommendation: cost, exposure, action, outcome — the denominator "
                "of every ROI claim; zero joined rows means a stage's key is broken"),
        Receipt("L7", "a human verdict has reached the loop",
                f"select count(*) from card_feedback_verdicts where 1=1{o}",
                lambda n: n > 0,
                "no verdicts ⇒ nothing to learn from, whatever the engine is capable of"),
    ]




def evaluate(engine, org: str | None) -> list[dict]:
    """Run every receipt; an unrunnable one is a finding (ERROR), never a skip.

    ⛔ AND ONE UNRUNNABLE RECEIPT MUST NOT TAKE EVERY RECEIPT AFTER IT. Measured against production
    2026-10-01: migration `0190` is unapplied, so the L5 lane receipt raised `UndefinedColumn` —
    correctly, once. Then **twelve** further receipts reported `InFailedSqlTransaction`, because
    SQLAlchemy opens an implicit transaction on first use and a statement that raises leaves it
    invalid. The page said `13 ERROR` where the truth was `1 ERROR` and twelve untried, and an
    operator reading it could not tell which receipt had actually failed.

    ⛔ THIS IS THE SAME DEFECT `domain_shadow` ALREADY FIXED FOR ITS OWN LOOP, and its comment is the
    diagnosis: *"ONE connection serves the whole loop … a single bad situation silently takes every
    situation after it. Measured on the design partner's org: one persist_error was followed by five
    cascade failures … The six missing situations were not unroutable; they were never attempted."*
    The cure there was an unconditional `rollback()` per iteration, for the same reason it is used
    here: `rollback()` on a healthy connection is a no-op, so it needs no flag anybody must keep
    correct.

    ⛔ AND THE ROLLBACK GOES IN `finally`, NOT IN `except`. A receipt whose query SUCCEEDS still leaves
    an open implicit transaction; putting the reset only on the failure path would leave a successful
    receipt holding one, and the next failure would then be attributed to whichever receipt happened
    to be running. The reset belongs after every receipt, not after the broken ones.
    """
    rows: list[dict] = []
    with engine.connect() as c:
        for r in receipts(org):
            params = {"org": org} if org and ":org" in r.sql else {}
            try:
                value = c.execute(text(r.sql), params).scalar()
                ok = bool(r.expect(value))
                rows.append({"layer": r.layer, "claim": r.claim, "value": value,
                             "status": "PASS" if ok else "FAIL", "detail": r.detail})
            except Exception as exc:                       # noqa: BLE001 — evidence, not control flow
                rows.append({"layer": r.layer, "claim": r.claim, "value": None,
                             "status": "ERROR", "detail": f"{type(exc).__name__}: {exc}"[:160]})
            finally:
                c.rollback()
    return rows


__all__ = ["Receipt", "evaluate", "receipts"]
