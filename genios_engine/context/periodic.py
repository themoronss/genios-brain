"""Tenant-anchored PERIOD situations — the aggregate reads, which no anchor could carry.

Twenty-two authored capabilities across all three domains ask a question about a WINDOW rather
than about a subject: is turnaround slipping, is the backlog concentrated, does pipeline coverage
add up, are the people running it sustainable. Every one of them was unreachable, and the reason
was structural rather than an authoring gap — `context_situations` anchors on a graph node, and
there is no node whose facts are "the whole queue this month".

Three corpus files name the missing mechanism in identical words so it reads as one build:
`admin.sit.admin_service_under_load`, `customer_support.sit.queue_period_review` and
`sales.sit.pipeline_period_review`.

THE DESIGN, and why it is not a new kind of situation. A tenant node is minted per org and the
period aggregates are written onto it as ordinary facts, exactly as `derived.py` writes
engagement and momentum onto people. A period situation then anchors on that node like every
other situation, and `_load_context`, `_neighborhood`, `build_context_slice` and the whole
compile path work unchanged. The alternative — teaching the compiler about anchorless situations —
would have put a second situation shape into a pipeline that currently has one.

WHY THE TENANT NODE IS NOT IN `ANCHOR_PRIORITY`. It must never win a correlation. `choose_anchors`
returns only the strongest tier present, so a tenant node reachable from correspondence would
swallow every conversation in the org into one situation. It is created here, anchored here, and
is deliberately invisible to correlation.

WHAT IS DELIBERATELY ABSENT. No targets, no thresholds and no verdicts. This module counts what
is there; whether 14 open deals is coverage or a drought is a judgement that needs a target
nobody has stated, and inventing one would put a fabricated benchmark under every forecast. The
corpus asks for distribution rather than average for the same reason — the finding is in the tail,
and a mean is how a failing segment stays hidden.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.domain_spec import _SPECS, spec_for
from genios_engine.platform.ids import new_id

#: The window every aggregate is measured over. Four weeks rather than a calendar month so the
#: comparison against the previous window is like-for-like — a 28-day count and a 31-day count are
#: not comparable, and the movement is the only part of an aggregate anyone can act on.
WINDOW_DAYS = 28

def period_domains() -> tuple[str, ...]:
    """The domains that get a period situation: every registered domain that DECLARES a `tenant`
    anchor, asked of the registry rather than listed here.

    Listing them was the first version and `test_domain_names_appear_in_exactly_one_file_in_the_
    context_layer` rejected it, correctly: a domain named in Layer 2 means adding a domain requires
    editing Layer 2, and the registry exists precisely so it does not. Declaring
    `"tenant": "<something>_period_review"` in `domain_spec` is now the whole opt-in.

    Domains without the anchor are skipped rather than defaulted. `type_for` would otherwise return
    its generic `<domain>_tenant`, which no situation file claims and the registry cannot resolve —
    the exact fault that kept `admin_person` and `fundraising_deal` dark, and it fails silently.
    """
    return tuple(sorted(d for d, spec in _SPECS.items()
                        if spec.situation_types.get("tenant")))


def tenant_key(org_id: str) -> str:
    """The canonical key the tenant node is found by. Identity goes through the store's own
    `find_or_create_node` rather than a hand-built id, so the node participates in
    `register_node_identity` like every other node and a second sweep finds it instead of
    minting a rival."""
    return f"tenant:{org_id}"


def tenant_node_id(conn, org_id: str) -> str | None:
    """The tenant node's id, or None before the first sweep has created it."""
    return conn.execute(text(
        "select node_id from graph_nodes where org_id=:o and canonical_key=:k "
        "and valid_to is null limit 1"), {"o": org_id, "k": tenant_key(org_id)}).scalar()


def period_key(now: datetime) -> str:
    """The window's identity. ISO year-week of the window's END, so a re-run inside the same week
    updates one situation instead of minting a new one every sweep."""
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _ensure_tenant_node(store, conn, org_id: str) -> str:
    return store.find_or_create_node(
        conn, org_id=org_id, node_type="tenant", canonical_key=tenant_key(org_id),
        display_name="This organisation", event_id=None)


def _counts(conn, org_id: str, since: datetime, prev_since: datetime) -> dict[str, float]:
    """Everything countable from the substrate that actually exists, and nothing else.

    Each figure is paired with its previous-window twin because a single number is not a finding.
    "Eleven open deals" tells a reader nothing; "eleven, against seven" tells them what changed,
    which is the only thing a period read is for.
    """
    def scalar(sql: str, **kw) -> float:
        return float(conn.execute(text(sql), {"o": org_id, **kw}).scalar() or 0)

    open_deals = ("select count(distinct n.node_id) from graph_nodes n "
                  "join graph_facts f on f.org_id=n.org_id and f.subject_node_id=n.node_id "
                  "  and f.field='deal.status' and f.valid_to is null and f.value #>> '{}'='open' "
                  "where n.org_id=:o and n.node_type='deal' and n.valid_to is null")
    events_in = ("select count(*) from source_events "
                 "where org_id=:o and occurred_at >= :a and occurred_at < :b")
    owed = ("select count(distinct f.subject_node_id) from graph_facts f "
            "where f.org_id=:o and f.field='thread.ball_in_court' and f.valid_to is null "
            "  and f.value #>> '{}' = 'us'")
    commitments_open = ("select count(*) from graph_facts f "
                        "where f.org_id=:o and f.field='commitment.due_at' and f.valid_to is null")
    overdue = ("select count(*) from graph_facts f "
               "where f.org_id=:o and f.field='commitment.due_at' and f.valid_to is null "
               "  and (f.value #>> '{}') < :now_s")
    active_sits = ("select count(*) from context_situations "
                   "where org_id=:o and status='active'")

    now_s = datetime.now(timezone.utc).isoformat()
    return {
        "period.open_deals": scalar(open_deals),
        "period.events_this_window": scalar(events_in, a=since, b=since + timedelta(days=WINDOW_DAYS)),
        "period.events_prev_window": scalar(events_in, a=prev_since, b=since),
        "period.counterparties_awaiting_us": scalar(owed),
        "period.commitments_open": scalar(commitments_open),
        "period.commitments_overdue": scalar(overdue, now_s=now_s),
        "period.active_situations": scalar(active_sits),
    }


def refresh_period_situations(store, org_id: str, *, now: datetime | None = None) -> int:
    """Write the period aggregates and open/refresh one situation per domain. Returns rows written.

    Idempotent within a window: the facts overwrite their own deterministic version ids and the
    situations conflict on `(org_id, correlation_id)`, whose id contains the period key. A sweep
    that runs six times in a week produces one situation per domain, not six.
    """
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)
    prev_since = since - timedelta(days=WINDOW_DAYS)
    key = period_key(now)
    written = 0

    with store.engine.begin() as c:
        node_id = _ensure_tenant_node(store, c, org_id)
        aggregates = _counts(c, org_id, since, prev_since)
        for field, value in aggregates.items():
            c.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, value_type, status, authority_rank, confidence, occurred_at, "
                "valid_from, visibility_scope) values "
                "(:vid, :fid, :o, :n, :f, cast(:v as jsonb), 'number', 'active', 100, 0.95, "
                ":now, :now, 'org') "
                # Same reasoning as `derived.py`: a recompute overwrites its own version id rather
                # than appending a row per sweep, or the table grows by seven rows an org forever.
                "on conflict (fact_version_id) do update set value = excluded.value, "
                "occurred_at = excluded.occurred_at, valid_from = excluded.valid_from"),
                {"vid": f"fv_period_{org_id}_{field}", "fid": f"f_period_{org_id}_{field}",
                 "o": org_id, "n": node_id, "f": field, "v": repr(round(value, 4)), "now": now})
            written += 1

        for domain in period_domains():
            stype = spec_for(domain).type_for("tenant")
            corr_id = f"corr_period_{domain}_{org_id}_{key}"
            held = c.execute(text(
                "select situation_id from context_situations where org_id=:o and correlation_id=:c"),
                {"o": org_id, "c": corr_id}).scalar()
            c.execute(text(
                "insert into context_situations (situation_id, org_id, correlation_id, "
                "  anchor_node_id, situation_type, domain, status, confidence_overall, "
                "  confidence_evidence, confidence_freshness, confidence_consistency, "
                "  confidence_identity, coverage, missing, inputs, first_seen_at, last_seen_at, "
                "  computed_at) "
                "values (:sid, :o, :c, :n, :st, :d, 'active', :conf, :conf, :conf, :conf, "
                "  10000, :cov, cast(:missing as jsonb), cast(:inputs as jsonb), :now, :now, :now) "
                "on conflict (org_id, correlation_id) do update set "
                "  confidence_overall = excluded.confidence_overall, "
                "  confidence_freshness = excluded.confidence_freshness, "
                "  coverage = excluded.coverage, inputs = excluded.inputs, "
                "  missing = excluded.missing, last_seen_at = excluded.last_seen_at, "
                "  situation_type = excluded.situation_type, computed_at = excluded.computed_at"),
                {"sid": held or new_id("sit"), "o": org_id, "c": corr_id, "n": node_id,
                 "st": stype, "d": domain, "now": now,
                 # Identity is certain — the subject is the tenant, and there is no merge question.
                 # Everything else is bounded by how much of the window the substrate saw, which is
                 # honestly partial on a mail-and-calendar tenant.
                 "conf": 7000,
                 "cov": 5000,
                 "missing": json.dumps(["targets", "per-owner load", "cost per contact"]),
                 "inputs": json.dumps({"window_days": WINDOW_DAYS, "period": key, **aggregates})})
            written += 1
    return written


__all__ = ["WINDOW_DAYS", "period_domains", "period_key", "refresh_period_situations",
           "tenant_key", "tenant_node_id"]
