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

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text

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


def _org_filter(org: str | None, alias: str = "") -> str:
    p = f"{alias}." if alias else ""
    return f" and {p}org_id = :org" if org else ""


def receipts(org: str | None) -> list[Receipt]:
    # THE DORMANCY WINDOW IS THE THRESHOLD, and it is imported rather than restated. L2 decides a
    # situation has ended after `DORMANT_AFTER_DAYS` of silence, so a tenant that has been fed
    # nothing for that long has, provably, no working set left — whatever the other receipts say.
    # Picking any other number here would invent a second opinion about when quiet becomes empty.
    # Imported inside the function, the way `platform/wiring.py` already reaches into `context`.
    from genios_engine.capture.pipeline import (JUDGED_DROP_CODES,
                                                JUDGED_DROP_PAYLOAD_TTL_DAYS)
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

        # ── L3 domain expertise ───────────────────────────────────────────────────────
        Receipt("L3", "compiled expertise packages exist",
                f"select count(*) from expertise_packages where 1=1{o}",
                lambda n: n > 0,
                "zero packages ⇒ the compiler is dark or every situation abstains"),
        Receipt("L3", "the tenant is bound to a pack",
                f"select count(*) from tenant_packs where state='active'{o}",
                lambda n: n > 0),

        # ── L4 reasoning ──────────────────────────────────────────────────────────────
        Receipt("L4", "more than one candidate is ever considered",
                "select coalesce(max(c), 0) from (select count(*) as c from reasoning_candidates"
                + (" where org_id = :org" if org else "") +
                " group by run_id) t",
                lambda n: n > 1,
                "exactly one candidate per run means no alternative, no do-nothing, no ranking"),
        Receipt("L4", "the score components are measured, not placeholders",
                "select count(*) from reasoning_candidates where "
                "score_components->>'impact' = '5000' and score_components->>'risk' = '5000' "
                "and score_components->>'effort' = '5000'" + _org_filter(org),
                lambda n: n == 0,
                "four of five components frozen at 5000 means every L4 unit adjustment is a no-op"),
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
        Receipt("L6", "cards carry a written draft, not a template stub",
                "select count(*) from cards where render_mode <> 'llm'" + _org_filter(org),
                lambda n: n == 0,
                "raw_slot with an empty artifact body is a card with no content"),
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
    """Run every receipt; an unrunnable one is a finding (ERROR), never a skip."""
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
    return rows


__all__ = ["Receipt", "evaluate", "receipts"]
