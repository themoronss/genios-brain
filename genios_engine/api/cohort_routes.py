"""L2.4.4 · the cohort surface — listing, positioning, and M-9 predicate authoring.

THIS FILE EXISTS BECAUSE M-9 IS ON DEMAND ONLY. Doc 04 L2.4.4-U4 puts predicate authoring at "T3,
on demand only — never in a sweep", and gives the reason: the model DRAFTS a predicate and a HUMAN
approves it. A sweep has no human in it, so the drafting path cannot live on the drain — it needs
a request, with a person on the other end of it, and that request is `POST .../cohorts/propose`.

The three guards doc 04 names are enforced in `context/analytic/cohort.propose_cohort`, not here:
the population preview, the reference-node check, and fact validation at definition time. What
this file adds is the fourth thing that makes the flow safe — `created_by` is taken from the
AUTHENTICATED PRINCIPAL and never from the request body, so a client cannot store a cohort under
somebody else's name, and the model's name can never end up in the field a founder reads when they
ask who decided this.

Everything here is single-tenant. `_org` refuses a mismatch between the path and the credential,
and every function below passes exactly one `org_id` into the cohort module, which is where the
statements that carry it live.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.context.analytic.cohort import (COHORT_MEMBERSHIP_TABLE,
                                                   MAX_COHORTS_PER_ORG,
                                                   CohortProposal, PredicateError,
                                                   ProposalRefused, approve_proposal,
                                                   default_fact_registry, define_cohort,
                                                   llm_predicate_drafter, load_definitions,
                                                   load_node_facts, load_node_names,
                                                   membership_changes,
                                                   propose_cohort, save_definitions)
from genios_engine.context.analytic.comparator import PositionedReading, compare_in_cohort
from genios_engine.platform.auth import AuthCtx, get_auth_ctx, get_current_org
from genios_engine.platform.wiring import make_graph_store, make_llm_client

router = APIRouter()
_graph = make_graph_store()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


def _human(ctx: AuthCtx) -> str:
    """Who is authoring this cohort. A PERSON, or the request is refused.

    `created_by` is the answer to "who decided this?", and an API key minted for an organisation
    carries no person — `AuthCtx.actor_id` is NULL on that path by construction. Storing "the org"
    as the author of a model-drafted predicate would put the one field a founder can appeal to
    beyond anybody's reach.
    """
    actor = (ctx.actor_id or "").strip()
    if not actor:
        raise HTTPException(403, "authoring a cohort needs a signed-in person: this credential "
                                 "names none")
    return actor


def _now() -> datetime:
    """The clock is read HERE, at the process boundary, and nowhere below it — every function in
    the cohort module takes `eval_time` as a parameter so a request is replayable."""
    return datetime.now(timezone.utc)


def _predicate_payload(definition) -> dict[str, Any]:
    return {"cohort_id": definition.cohort_id, "name": definition.name,
            "node_type": definition.node_type, "predicate": definition.predicate.as_json(),
            "created_by": definition.created_by, "created_at": definition.created_at.isoformat(),
            "active": definition.active, "system_owned": definition.system_owned}


class ProposeCohort(BaseModel):
    ask: str
    node_type: str = "company"
    reference_node_id: str | None = None


class AuthorCohort(BaseModel):
    name: str
    node_type: str
    predicate: dict


@router.get("/api/org/{org_id}/cohorts")
def list_cohorts(org_id: str, org: str = Depends(_org)) -> dict:
    """This tenant's cohorts, with the CURRENT population of each.

    The population travels with every cohort for the same reason `CohortPosition` refuses to exist
    without it: a cohort of four is not a small peer group, it is no peer group, and a list that
    showed only names would let one be picked without that being visible.
    """
    definitions = load_definitions(_store().engine, org)
    with _store().engine.connect() as conn:
        counts = {str(r.cohort_id): int(r.n) for r in conn.execute(text(
            f"select cohort_id, count(*) as n from {COHORT_MEMBERSHIP_TABLE} "
            "where org_id = :o and left_at is null group by cohort_id"), {"o": org}).all()}
    return {"cohorts": [{**_predicate_payload(d), "population_size": counts.get(d.cohort_id, 0)}
                        for d in definitions]}


@router.get("/api/org/{org_id}/cohorts/{cohort_id}/position")
def cohort_position(org_id: str, cohort_id: str, metric: str, node_id: str,
                    org: str = Depends(_org)) -> dict:
    """Where one node sits in one cohort on one metric — or the REFUSAL, spelled out.

    A refusal is returned as a 200 with a named reason rather than as an error: "this cohort has
    four members, so there is no percentile" is an ANSWER, and rendering it as a failure is how a
    UI ends up inventing a number to fill the space.

    IT READS `comparator.compare_in_cohort`, NOT `cohort.position_in_cohort`, AND THE DIFFERENCE
    IS TWO DEFECTS THIS ROUTE WAS SERVING. Both were measured against this handler, on real
    Postgres, with a ten-member cohort five of whose members had been dark for 300 days:

      * NO STALENESS HORIZON. `cohort._VALUES_SQL` bounds the per-member read only from above
        (`observed_at <= :at`), so a member whose connector died ten months ago still arrives as a
        reading. The handler answered `population_size: 10`, `percentile_bp: 10000`, no refusal —
        the coverage floor exists in the arithmetic and could not be reached from here.
        `cohort_readings`, which `compare_in_cohort` reads through, bounds the same lateral below
        by `peer_baseline.staleness_floor` at the METRIC's own grain, so those five now count as
        `unknown` and the same request refuses with `insufficient_coverage`.
      * THE RAW LADDER. `CohortPosition.p25_bp/p50_bp/p75_bp` are `_quantile` over the sorted
        population — the literal readings of three named members, from a floor of five — and
        `model_dump()` served all three. The same request returned `p25_bp: 30, p50_bp: 50,
        p75_bp: 70`, which were exactly three of the other members' numbers, beside an exact rank
        that bounds a fourth. `peer_baseline` refuses to publish a ladder on populations under ten
        for precisely that reason, and one wave cannot hold both rules. `PositionedReading`
        carries `publishable_distribution` instead: the smoothed ladder when the population can
        support one, and `None` — withheld, not degraded — when it cannot.

    `compare_in_cohort` was built for this and reached no request path, which is the shape this
    codebase has shipped before: a public callable, fully tested, that nothing calls. It is called
    here now, so its refusals are the ones a customer actually sees.
    """
    outcome = compare_in_cohort(_store(), org_id=org, cohort_id=cohort_id, metric=metric,
                                subject_node_id=node_id, eval_time=_now())
    if isinstance(outcome, PositionedReading):
        # The SUBJECT's own reading, its rank, its band and the population's size are facts about
        # the subject and about the shape of the population. `distribution` is the only field that
        # describes other members, and it is None unless the ladder is publishable.
        return {"position": {"metric": outcome.metric,
                             "cohort_id": outcome.cohort_id,
                             "subject_node_id": outcome.subject_node_id,
                             "value_bp": outcome.value_bp,
                             "unit": outcome.unit.value if outcome.unit else None,
                             "population_size": outcome.population_size,
                             "percentile_bp": outcome.percentile_bp,
                             "band": outcome.band.value,
                             "phrase": outcome.phrase,
                             "distribution": list(outcome.distribution)
                             if outcome.distribution else None,
                             "computed_at": outcome.position.computed_at.isoformat()},
                "refusal": None}
    return {"position": None,
            "refusal": {"reason": outcome.reason.value, "cohort_id": outcome.cohort_id,
                        "metric": outcome.metric, "population_size": outcome.population_size,
                        "detail": outcome.detail,
                        "computed_at": outcome.computed_at.isoformat()}}


#: The widest window this route will answer over. `cohort_membership` is pruned on the drain, so a
#: question about last year reads a table that no longer holds last year and would answer "nothing
#: changed" — which is indistinguishable from the truth and worse than a refusal.
MAX_CHANGE_WINDOW_DAYS = 180


@router.get("/api/org/{org_id}/cohorts/changes")
def cohort_changes(org_id: str, days: int = 30, org: str = Depends(_org)) -> dict:
    """Every join and leave in a window — L2.4.4-U3's reader, on the surface that can show it.

    THIS IS THE PATTERN, not a log. *"Three accounts dropped out of your healthy-engagement cohort
    this month"* is the sentence doc 04 L2.4.4-U3 exists to make sayable, and it is only sayable
    if transitions are readable. Without this route `membership_changes` was a function nothing
    called and the transitions were invisible in the product even though the rows recorded them.

    DERIVED FROM STATE, NOT FROM A LEDGER. The events are computed from each membership row's own
    `joined_at` / `left_at`, so asking twice returns the same answer and a re-run cannot emit a
    transition twice. That is why there is no second table here to fall out of step with the
    first — and why a re-drain is safe.

    Counts travel with the events because a caller that renders "3 left" from `len(events)` would
    be counting joins too. `left` and `joined` are separate numbers on purpose.
    """
    if days < 1 or days > MAX_CHANGE_WINDOW_DAYS:
        raise HTTPException(400, f"days must be between 1 and {MAX_CHANGE_WINDOW_DAYS}")
    until = _now()
    events = membership_changes(_store(), org, since=until - timedelta(days=days), until=until)
    return {
        "window_days": days,
        "since": (until - timedelta(days=days)).isoformat(),
        "until": until.isoformat(),
        "joined": sum(1 for e in events if e.kind.value == "joined_cohort"),
        "left": sum(1 for e in events if e.kind.value == "left_cohort"),
        "events": [{"kind": e.kind.value, "cohort_id": e.cohort_id, "node_id": e.node_id,
                    "at": e.at.isoformat()} for e in events],
    }


def _proposal_payload(proposal: CohortProposal) -> dict[str, Any]:
    return {"ask": proposal.ask, "name": proposal.name, "node_type": proposal.node_type,
            "predicate": proposal.predicate_json, "population_size": proposal.population_size,
            "universe_size": proposal.universe_size, "share_bp": proposal.share_bp,
            "samples": [{"node_id": nid, "name": name} for nid, name in proposal.samples],
            "reference_node_id": proposal.reference_node_id,
            "warnings": list(proposal.warnings)}


@router.post("/api/org/{org_id}/cohorts/propose")
def propose(org_id: str, body: ProposeCohort, org: str = Depends(_org),
            ctx: AuthCtx = Depends(get_auth_ctx)) -> dict:
    """M-9 · a founder's sentence becomes a reviewable predicate, a count, and five named samples.

    NOTHING IS STORED HERE. The response is a preview; `POST /cohorts` is where a human turns it
    into a definition, under their own name. That separation is what keeps Law 3 intact while
    still letting a model do the typing: the artifact is the same reviewable tree a human would
    have written, and a person still decides.
    """
    _human(ctx)                                    # a draft is requested BY somebody, or not at all
    registry = default_fact_registry()
    at = _now()
    facts = load_node_facts(_store().engine, org, node_types=(body.node_type,), eval_time=at,
                            registry=registry).get(body.node_type.lower(), {})
    if not facts:
        raise HTTPException(400, f"this tenant has no {body.node_type} records to draft against")
    try:
        proposal = propose_cohort(
            org_id=org, ask=body.ask, drafter=llm_predicate_drafter(make_llm_client()),
            node_type=body.node_type, node_facts=facts,
            node_names=load_node_names(_store().engine, org, sorted(facts)),
            eval_time=at, reference_node_id=body.reference_node_id, registry=registry)
    except ProposalRefused as refused:
        # 422, not 500: the draft was understood and REFUSED, and the reason is the useful part —
        # "the predicate excludes Acme, which you named" is what tells a founder to rephrase.
        raise HTTPException(422, {"reason": refused.reason.value,
                                  "detail": refused.detail}) from None
    return _proposal_payload(proposal)


@router.post("/api/org/{org_id}/cohorts")
def author_cohort(org_id: str, body: AuthorCohort, org: str = Depends(_org),
                  ctx: AuthCtx = Depends(get_auth_ctx)) -> dict:
    """Store a cohort. `created_by` is the authenticated PERSON — never the body, never the model.

    This is the approval step of the M-9 flow and also the way a human writes one by hand; they
    are the same operation, which is the point of the whole design. The predicate is validated
    here, at definition time, so an unregistered fact name is a 422 on the request that wrote it
    rather than an empty cohort somebody trusts six weeks later.
    """
    author = _human(ctx)
    # The definition-count ceiling, enforced on the one path a client can grow the table from.
    # `cohort_definitions` is otherwise bounded by construction — system families upsert onto
    # stable slot ids and authored cohorts are content-addressed — and this is the hole in that
    # argument: a loop posting distinct predicates would grow the table (and the per-sweep work,
    # which is one membership pass per active cohort) without limit.
    with _store().engine.connect() as conn:
        held = conn.execute(text(
            "select count(*) from cohort_definitions where org_id = :o and active"),
            {"o": org}).scalar() or 0
    if held >= MAX_COHORTS_PER_ORG:
        raise HTTPException(409, f"this tenant already has {held} active cohorts (max "
                                 f"{MAX_COHORTS_PER_ORG}); retire one before adding another")
    try:
        definition = define_cohort(org_id=org, name=body.name, node_type=body.node_type,
                                   predicate=body.predicate, created_by=author,
                                   eval_time=_now())
    except PredicateError as bad:
        raise HTTPException(422, str(bad)) from None
    save_definitions(_store().engine, [definition])
    return _predicate_payload(definition)


__all__ = ["router", "approve_proposal", "list_cohorts", "cohort_position", "propose",
           "author_cohort"]
