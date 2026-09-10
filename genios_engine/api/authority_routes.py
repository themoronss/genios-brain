"""L2.1.4 · the AUTHORITY VIEW's request surface — *who can decide what, in this org*.

Five routes over `context/authority_view`, and the reason they exist at all is that a view
nothing can call is not a view. Doc 01 names two consumers — Layer 4's Policy and Constraint
units — and one surface, the Founder Bottleneck, which is *"this person is the only approver for
N classes"* rendered from `/authority/bottleneck` and nothing else.

THE CLOCK IS READ HERE AND NOWHERE BELOW. Every function in `authority_view` takes
`evaluated_at` as a parameter, so a March decision replays against March's rules. That leaves
exactly one place that has to decide what "now" means, and this is it: `?as_of=` on every read,
defaulting to `datetime.now(timezone.utc)` at the seam. A caller auditing an old decision passes
the instant and gets the rules that bound then.

WHAT A POST MAY WRITE. A console POST is a human declaring a rule, so it is `admin_declared` by
default. `discovered` and `inferred` are accepted because the same table holds all three, but the
contract refuses a discovered rule with no `evidence_ref`, and an inferred rule can never come
back from `/authority/resolve` as an enforceable answer — it lands in `suggestions`, for a human
to confirm by declaring it. A rule is never edited in place: `/supersede` closes its window and a
successor row is inserted, which is what keeps "who could approve this in March" answerable after
a September edit.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ValidationError

from genios_engine.context.authority_view import (AuthorityView, PostgresAuthorityRules,
                                                  rule_record)
from genios_engine.contracts.authority import AuthorityRule
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.ids import new_id
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _view() -> AuthorityView:
    """The view, over the graph store's own pool. A second engine per request would be a
    connection leak on a database whose measured ceiling is 60."""
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return AuthorityView(PostgresAuthorityRules(_graph.engine))


def _instant(as_of: str | None) -> datetime:
    """`?as_of=` as a tz-aware instant, defaulting to now. THE one clock read in this subsystem.

    A naive string is read as UTC rather than rejected: the alternative is a 400 on the most
    common way a human types an instant, and every column this compares against is `timestamptz`.
    """
    if not as_of:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(400, f"as_of must be an ISO-8601 instant: {as_of!r}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class RuleIn(BaseModel):
    """One declared rule. Mirrors `contracts/authority.AuthorityRule` and is deliberately not it:
    the contract requires `rule_id` and `valid_from`, and a console that had to mint both would
    be inventing an id in the browser."""

    subject_type: str
    approver_node_id: str
    threshold_minor_units: int | None = None
    currency: str | None = None
    delegate_node_id: str | None = None
    source: str = "admin_declared"
    evidence_ref: str | None = None
    rule_id: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None


@router.get("/api/org/{org_id}/authority/rules")
def list_rules(org_id: str, subject_type: str | None = None, as_of: str | None = None,
               all_time: bool = Query(False, description="every row ever, ignoring the window"),
               org: str = Depends(_org)) -> dict:
    """The rules in force at `as_of` (or every row ever, with `all_time=true`).

    `all_time` is what an admin console needs to show a rule's HISTORY — the superseded row is
    still there, and hiding it would make the table look like it was edited in place.
    """
    at = _instant(as_of)
    rules = _view().rules(org, subject_type=subject_type,
                          as_of=None if all_time else at)
    return {"org_id": org, "as_of": None if all_time else at.isoformat(),
            "subject_type": subject_type, "count": len(rules),
            "rules": [rule_record(r) for r in rules]}


@router.post("/api/org/{org_id}/authority/rules")
def declare_rule(org_id: str, body: RuleIn, org: str = Depends(_org)) -> dict:
    """Declare a rule. Defaults to `admin_declared` — a human setting it in the console is
    exactly doc 01's first source — and to a window starting now with no end."""
    now = datetime.now(timezone.utc)
    try:
        rule = AuthorityRule(
            rule_id=body.rule_id or new_id("authr"), subject_type=body.subject_type,
            threshold_minor_units=body.threshold_minor_units, currency=body.currency,
            approver_node_id=body.approver_node_id, delegate_node_id=body.delegate_node_id,
            source=body.source, evidence_ref=body.evidence_ref,
            valid_from=_instant(body.valid_from) if body.valid_from else now,
            valid_until=_instant(body.valid_until) if body.valid_until else None)
    except (ValidationError, ValueError, TypeError) as exc:
        # The contract's coherence errors are the useful message here — "a threshold must name
        # its currency", "a discovered rule must name the document it was read from" — so they
        # are surfaced verbatim rather than replaced with a generic 422.
        raise HTTPException(400, f"invalid authority rule: {exc}") from exc
    written = _view().declare(org, [rule])
    return {"org_id": org, "written": written, "rule": rule_record(rule)}


@router.post("/api/org/{org_id}/authority/rules/{rule_id}/supersede")
def supersede_rule(org_id: str, rule_id: str, valid_from: str, valid_until: str | None = None,
                   org: str = Depends(_org)) -> dict:
    """Close a rule's window. `valid_from` identifies WHICH version (it is part of the key), and
    the row is never deleted: March's answer has to survive September's edit."""
    ends = _instant(valid_until)
    starts = _instant(valid_from)
    if ends <= starts:
        raise HTTPException(400, "valid_until must be after valid_from — a window that ends "
                                 "before it starts matches no instant")
    closed = _view().supersede(org, rule_id, valid_from=starts, valid_until=ends)
    if not closed:
        raise HTTPException(404, f"no authority rule {rule_id!r} effective at {starts.isoformat()}")
    return {"org_id": org, "rule_id": rule_id, "valid_until": ends.isoformat()}


@router.get("/api/org/{org_id}/authority/resolve")
def resolve_authority(org_id: str, subject_type: str, amount_minor_units: int | None = None,
                      currency: str | None = None, as_of: str | None = None,
                      ratio_bp: int | None = None,
                      org: str = Depends(_org)) -> dict:
    """*Who approves a `subject_type` worth `amount_minor_units`, as at `as_of`?*

    Three answers, never two: `enforceable` names an approver; `suggested` means only observed
    behaviour matched and a human must confirm before anybody signs; `no_authority_rule` means we
    hold no rule — which is NOT "anyone may approve", and the distinction is why `reason` is on
    the response instead of an empty object.

    `ratio_bp` asks the second kind of question: a discount policy is bounded in BASIS POINTS,
    not money. A caller that omits it gets no ratio rule matched, which is the safe direction —
    before this parameter existed the store dropped the bound entirely and every ratio rule
    covered every subject, so a 2% discount named the founder as its required approver.
    """
    at = _instant(as_of)
    try:
        answer = _view().resolve(org, subject_type=subject_type, evaluated_at=at,
                                 amount_minor_units=amount_minor_units, currency=currency,
                                 ratio_bp=ratio_bp)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return answer.as_record()


@router.get("/api/org/{org_id}/authority/bottleneck")
def authority_bottleneck(org_id: str, as_of: str | None = None,
                         org: str = Depends(_org)) -> dict:
    """The Founder Bottleneck: who is the ONLY person who may approve a whole class, with nobody
    named to act in their absence. Enforceable rules only — a bottleneck inferred from somebody
    answering their email is a claim about behaviour, not about governance."""
    return _view().bottleneck(org, evaluated_at=_instant(as_of)).as_record()
