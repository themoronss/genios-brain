"""Derived facts — the numbers every rule reads and nothing has ever written.

`derived.engagement`, `derived.sentiment` and `derived.momentum` are consulted across the sales
pack (`derived.engagement <= 0.5`, `derived.sentiment <= -0.34`) and by the compiled L3
capabilities, which declare them as required context. The extraction vocabulary deliberately
excludes them — vocab.py says so plainly: *"computed by the reasoner from other facts, never
extracted"*, because offering them to the model invites a plausible invented number.

Nothing computed them. They were absent from every node in the graph, which means every rule and
every capability gated on them was dead on arrival: the deep sales rules never fired once, and all
18 compiled capabilities returned INSUFFICIENT_CONTEXT against a graph that held everything else
they needed. The shallow output the product shows — nine `unanswered_email` cards out of thirteen —
is exactly what is left when only the fields nobody derives are missing.

Deterministic and LLM-free by construction. These are counts over observations the extractor has
already committed, so the same graph yields the same numbers on every run, and a value can always
be traced back to the rows that produced it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

#: Observation kinds that carry direction. Weighted by how strongly each commits the counterparty:
#: a booked next step is worth more than a warm reply, an explicit loss more than a single
#: objection. Grounded in the kinds the extractor actually emits, not an invented taxonomy.
_SENTIMENT_WEIGHTS: dict[str, float] = {
    "next_step_agreed": 1.0, "demo_requested": 1.0, "proposal_sent": 0.6,
    "positive_reply": 0.6, "meeting_request": 0.5, "introduction": 0.3,
    "question": 0.1,
    "objection": -0.6, "negative_reply": -0.8, "timeline_slip": -0.7,
    "closed_lost_mention": -1.0,
}

#: Kinds that mean the relationship MOVED, as opposed to merely made noise. Momentum asks whether
#: anything advanced recently, which is a different question from whether the tone was warm.
_PROGRESS_KINDS = frozenset({
    "next_step_agreed", "demo_requested", "proposal_sent", "meeting_request", "followup_sent",
})

_RECENT_DAYS = 14          # "lately"
_BASELINE_DAYS = 56        # four times the recent window → a stable denominator, not last week's noise


def _rate(count: int, days: int) -> float:
    return count / days if days > 0 else 0.0


def compute(store, org_id: str, *, now: datetime | None = None) -> int:
    """Write derived.* for every node this org has observations on. Returns rows written.

    One pass, three bulk queries, no per-node round-trips — the same reason attention refreshes
    for the whole org rather than per touched node.
    """
    now = now or datetime.now(timezone.utc)
    recent_from = now - timedelta(days=_RECENT_DAYS)
    baseline_from = now - timedelta(days=_BASELINE_DAYS)

    with store.engine.begin() as c:
        rows = c.execute(text(
            "select subject_node_id, kind, "
            "count(*) filter (where occurred_at >= :recent) as recent_n, "
            "count(*) filter (where occurred_at >= :baseline) as baseline_n "
            "from graph_observations "
            "where org_id = :o and status = 'active' and occurred_at >= :baseline "
            "group by subject_node_id, kind"),
            {"o": org_id, "recent": recent_from, "baseline": baseline_from}).all()

        per_node: dict[str, dict] = {}
        for node_id, kind, recent_n, baseline_n in rows:
            acc = per_node.setdefault(node_id, {
                "recent": 0, "baseline": 0, "pos": 0.0, "neg": 0.0, "progress_recent": 0})
            acc["recent"] += recent_n
            acc["baseline"] += baseline_n
            weight = _SENTIMENT_WEIGHTS.get(kind)
            if weight is not None:
                # Sentiment reads the WHOLE baseline window, not just the recent one: a single
                # sour reply this fortnight should not outweigh a quarter of warm ones.
                if weight > 0:
                    acc["pos"] += weight * baseline_n
                else:
                    acc["neg"] += -weight * baseline_n
            if kind in _PROGRESS_KINDS:
                acc["progress_recent"] += recent_n

        written = 0
        for node_id, acc in per_node.items():
            recent_rate = _rate(acc["recent"], _RECENT_DAYS)
            baseline_rate = _rate(acc["baseline"], _BASELINE_DAYS)
            # Engagement is a RATIO against this relationship's own history, never an absolute
            # count — "halved" has to mean halved for THIS account, whether it ran at forty
            # emails a week or four. A node with no history reads 1.0 (neutral), not 0.0, or
            # every brand-new contact would look like it had gone cold.
            engagement = 1.0 if baseline_rate <= 0 else min(recent_rate / baseline_rate, 3.0)
            total = acc["pos"] + acc["neg"]
            sentiment = 0.0 if total <= 0 else (acc["pos"] - acc["neg"]) / total
            momentum = _rate(acc["progress_recent"], _RECENT_DAYS) * 7.0   # progress events/week

            for field, value in (("derived.engagement", engagement),
                                 ("derived.sentiment", sentiment),
                                 ("derived.momentum", momentum)):
                c.execute(text(
                    "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                    "field, value, value_type, status, authority_rank, confidence, occurred_at, "
                    "valid_from, visibility_scope) values "
                    "(:vid, :fid, :o, :n, :f, cast(:v as jsonb), 'number', 'active', 100, 0.9, "
                    ":now, :now, 'org') "
                    # graph_facts is version-keyed: its only unique index is fact_version_id.
                    # A derived value is a RECOMPUTE, not a new observation of history, so it
                    # overwrites its own deterministic version id rather than appending a row per
                    # drain — otherwise every sync would grow the table by three rows per node
                    # forever, and a reader picking "latest" would be sifting duplicates.
                    "on conflict (fact_version_id) do update set value = excluded.value, "
                    "occurred_at = excluded.occurred_at, valid_from = excluded.valid_from"),
                    {"vid": f"fv_derived_{node_id}_{field}", "fid": f"f_derived_{node_id}_{field}",
                     "o": org_id, "n": node_id, "f": field,
                     "v": repr(round(value, 4)), "now": now})
                written += 1
    return written


#: Observation kinds that place a relationship at a stage. Ordered by how far along they put it,
#: so the furthest-reached stage wins rather than the most recent noise.
_STAGE_BY_KIND: tuple[tuple[str, str], ...] = (
    ("closed_lost_mention", "lost"),
    ("proposal_sent", "proposing"),
    ("demo_requested", "evaluating"),
    ("next_step_agreed", "engaged"),
    ("meeting_request", "engaged"),
    ("introduction", "new"),
)
_STAGE_RANK = {"new": 0, "engaged": 1, "evaluating": 2, "proposing": 3, "lost": 4}


def compute_deal_view(store, org_id: str, *, now: datetime | None = None) -> int:
    """Roll thread-level truth up to the deal fields the rules ask for. Returns rows written.

    `deal.status` and `deal.last_inbound` were missing on 16 of 18 companies not because the
    information is absent but because nobody ever wrote it at the deal's own level: the extractor
    records `thread.last_inbound` per thread and stage observations per person, and the deal — the
    relationship as a whole — is precisely the roll-up of those. Asking a language model to restate
    it per email would be inviting a guess at something already known exactly.

    `deal.value` is deliberately NOT derived. There is no honest way to infer a number nobody
    stated, and a wrong one would flow straight into prioritisation. A capability that needs it
    should keep reporting insufficient context until an email actually says so.
    """
    now = now or datetime.now(timezone.utc)
    with store.engine.begin() as c:
        # Latest inbound anywhere under each company, through its edges.
        rows = c.execute(text(
            "select e.from_node_id as company, max(f.value #>> '{}') as last_inbound "
            "from graph_edges e "
            "join graph_facts f on f.subject_node_id = e.to_node_id and f.org_id = e.org_id "
            "where e.org_id = :o and f.field = 'thread.last_inbound' and f.status = 'active' "
            "group by e.from_node_id"), {"o": org_id}).all()
        stages = c.execute(text(
            "select e.from_node_id as company, o2.kind "
            "from graph_edges e "
            "join graph_observations o2 on o2.subject_node_id = e.to_node_id "
            "and o2.org_id = e.org_id "
            "where e.org_id = :o and o2.status = 'active'"), {"o": org_id}).all()

        best_stage: dict[str, str] = {}
        kind_to_stage = dict(_STAGE_BY_KIND)
        for company, kind in stages:
            stage = kind_to_stage.get(kind)
            if stage is None:
                continue
            held = best_stage.get(company)
            if held is None or _STAGE_RANK[stage] > _STAGE_RANK[held]:
                best_stage[company] = stage

        # Commitments sit TWO hops out: company -> person -> commitment. A 1-hop neighbourhood
        # can never see them, which is why `commitment.action` and `commitment.due_at` were missing
        # on all 18 companies while the promises themselves were extracted correctly and stored on
        # their own nodes. The company's open obligation is the soonest-due one among its people —
        # a roll-up of fact, not a new claim.
        #
        # `commitment.action` is also a NAME gap: the pipeline writes the normalised obligation as
        # `commitment.text`, and both the sales pack and the compiled capabilities ask for
        # `commitment.action`. Reading the former and publishing the latter closes it here rather
        # than renaming a field other readers already depend on.
        commitments = c.execute(text(
            "select e1.from_node_id as company, "
            "min(due.value #>> '{}') as due_at, "
            "min(act.value #>> '{}') as action "
            "from graph_edges e1 "
            "join graph_edges e2 on e2.from_node_id = e1.to_node_id and e2.org_id = e1.org_id "
            "join graph_facts due on due.subject_node_id = e2.to_node_id "
            "and due.org_id = e1.org_id and due.field = 'commitment.due_at' "
            "and due.status = 'active' "
            "left join graph_facts act on act.subject_node_id = e2.to_node_id "
            "and act.org_id = e1.org_id and act.field = 'commitment.text' "
            "and act.status = 'active' "
            "join graph_facts st on st.subject_node_id = e2.to_node_id "
            "and st.org_id = e1.org_id and st.field = 'commitment.status' "
            "and st.status = 'active' and st.value #>> '{}' = 'open' "
            "where e1.org_id = :o group by e1.from_node_id"), {"o": org_id}).all()

        written = 0
        pairs: list[tuple[str, str, str]] = []
        for company, due_at, action in commitments:
            if due_at:
                pairs.append((company, "commitment.due_at", due_at))
            if action:
                pairs.append((company, "commitment.action", action))
        for company, last_inbound in rows:
            if last_inbound:
                pairs.append((company, "deal.last_inbound", last_inbound))
        for company, stage in best_stage.items():
            pairs.append((company, "deal.status", stage))
        for node_id, field, value in pairs:
            c.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, value_type, status, authority_rank, confidence, occurred_at, "
                "valid_from, visibility_scope) values "
                "(:vid, :fid, :o, :n, :f, cast(:v as jsonb), 'string', 'active', 100, 0.9, "
                ":now, :now, 'org') "
                "on conflict (fact_version_id) do update set value = excluded.value, "
                "occurred_at = excluded.occurred_at, valid_from = excluded.valid_from"),
                {"vid": f"fv_derived_{node_id}_{field}", "fid": f"f_derived_{node_id}_{field}",
                 "o": org_id, "n": node_id, "f": field,
                 "v": f'"{value}"', "now": now})
            written += 1
    return written


__all__ = ["compute", "compute_deal_view"]
