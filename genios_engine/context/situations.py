"""L2 · Situation Engine — the object reasoning actually consumes.

A correlation says "these events are about the same thing". A situation says what that
thing IS, in terms an executive would use: an opportunity, a support case, a relationship
— with how sure we are, how current it is, and what we still do not know.

The Reasoning Engine should never wake up and ask for the graph. It should ask for the
active situations. Traversing nodes and edges to rebuild context on every question is not
thinking; it is assembling. Assembling happens here, once.

WHAT A SITUATION IS NOT
It carries no priority, no risk score and no recommendation. Those are decisions, and
decisions belong to the layer that is allowed to have opinions. This layer answers only
"what is true right now, and how sure are we" — the same discipline the correlation
engine and the context graph already keep.

(The architecture notes list Risk Detector and Opportunity Detector inside this stage.
That contradicts their own rule that context never decides, and this codebase already
detects risk in the packs — building it here too would give two layers an opinion about
the same thing and no way to tell which one was wrong. Detection stays downstream.)

CONFIDENCE IS A VECTOR, AND `overall` IS A MINIMUM
Four dimensions describe whether you can TRUST a situation:

    evidence     how much independent material backs it
    freshness    how current that material is
    consistency  whether the sources contradict each other
    identity     whether we are sure WHO it is about

`overall` is the minimum of those, never the average. They are failure modes, not
features, and averaging lets one strong dimension hide a fatal one: perfect evidence
about an entity we cannot identify is not 60% confidence, it is unusable. You are only
as sure as your weakest link.

COVERAGE IS DELIBERATELY OUTSIDE `overall`
Completeness is a different question from correctness. Not knowing a deal's close date
does not make the stage we DO know less true. Folding coverage into overall would make
absence read as doubt — the same mistake as reading absence as negative evidence, which
this codebase already refuses everywhere else. Coverage is reported beside overall so a
reader can tell "we are unsure" apart from "we are missing pieces".

AN UNKNOWN DIMENSION IS EXCLUDED, NOT ZEROED
Evidence with no timestamps tells us nothing about currency — it does not tell us the
situation is stale. Scoring that as zero would turn missing data into bad news. A
dimension with no basis is left out of the minimum and marked, so the score says
"we cannot tell" rather than "it is old".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.domain_spec import spec_for, spec_version
from genios_engine.platform.ids import new_id

# Lifecycle. `dormant` is not a failure — it is a situation that has gone quiet and
# should stop competing for attention without being forgotten.
STATUS_ACTIVE = "active"
STATUS_DORMANT = "dormant"
STATUS_RESOLVED = "resolved"
STATUS_ARCHIVED = "archived"

# How a resolution was reached — the two behave differently when new evidence arrives.
RESOLVED_BY_FACT = "fact"      # re-derived every refresh; self-correcting
RESOLVED_BY_HUMAN = "human"    # sticks until new evidence, then reopens

DORMANT_AFTER_DAYS = 45        # matches the correlation window: past it, a new
                               # generation opens and this one has genuinely ended
ARCHIVE_AFTER_DAYS = 180       # resolved and long past — out of the working set

# Deal stages that END a situation. Matched case-insensitively on a normalized form so
# "CLOSEDWON", "closed_won" and "Closed Won" all count — a CRM writes all three.
#
# This is the ONE piece of domain vocabulary left in this file, and it is here because it
# is a LIFECYCLE rule (when does a situation stop being live) rather than a statement
# about what sales means. It applies to any domain that produces a `deal.stage` fact.
_TERMINAL_DEAL_STAGES: frozenset[str] = frozenset({"closedwon", "closedlost"})


def situation_type(anchor_type: str, domain: str) -> str:
    """What kind of situation this is, per the domain's registered spec.

    An unregistered domain gets `<domain>_<anchor>` — visibly unmapped rather than
    silently filed as something it is not, and never an error. That is what lets a new
    domain start producing situations before anyone has described it.
    """
    return spec_for(domain).type_for(anchor_type)


def normalize_stage(value) -> str:
    """CRM stage → a comparable token. Strips quotes (values arrive JSON-encoded),
    punctuation and case."""
    raw = str(value or "").strip().strip('"').lower()
    return "".join(ch for ch in raw if ch.isalnum())


# ── the confidence dimensions ────────────────────────────────────────────────────

def evidence_score(*, event_count: int, source_count: int) -> int:
    """How much independent material backs this situation.

    Sources outweigh volume on purpose: twenty emails in one thread are one person's
    account of events, while an email plus a CRM record plus a calendar invite are three
    systems independently agreeing. Corroboration across tools is what makes a situation
    trustworthy, not repetition within one.

    The caps encode that — 60 available for corroboration against 40 for volume — so a
    noisy single-source thread can never outscore genuine cross-tool agreement. An
    earlier split (60 volume / 40 sources) inverted it and made this docstring a lie;
    tests/test_situations.py now pins the ordering.
    """
    volume = min(40, max(0, int(event_count)) * 8)
    corroboration = min(60, max(0, int(source_count)) * 25)
    return max(0, min(100, volume + corroboration))


def freshness_score(*, last_seen_at: datetime | None, now: datetime) -> tuple[int, bool]:
    """How current the evidence is. Returns (score, known).

    `known=False` when nothing is dated. That is NOT staleness — it is an absence of
    information about time, and the caller excludes it from the overall score rather
    than letting missing data masquerade as bad news.
    """
    if last_seen_at is None:
        return 0, False
    age_days = (now - last_seen_at).total_seconds() / 86400.0
    if age_days <= 3:
        return 100, True
    if age_days <= 7:
        return 85, True
    if age_days <= 14:
        return 70, True
    if age_days <= 30:
        return 50, True
    if age_days <= DORMANT_AFTER_DAYS:
        return 30, True
    return 10, True


def consistency_score(*, open_discrepancies: int) -> int:
    """Do the sources contradict each other about this entity?

    A discrepancy is already a recorded product signal (the CRM says closed, Slack says
    the customer is unhappy). One is a real dent in trust; three make the situation
    something a human must look at before anything acts on it.
    """
    return max(0, 100 - min(100, max(0, int(open_discrepancies)) * 34))


def identity_score(*, open_merge_proposals: int) -> int:
    """Are we sure WHO this is about?

    An unresolved duplicate means the evidence may be split across two nodes, so this
    situation is probably missing half its material — or is about the wrong entity
    entirely. Neither is a small doubt, which is why one open proposal costs so much.
    """
    if open_merge_proposals <= 0:
        return 100
    return 40 if open_merge_proposals == 1 else 20


#: The score returned when a domain registers no expectations. Sentinel, not a percentage: it is
#: outside 0..100 on purpose so no consumer can average it into a number and lose the distinction
#: between "nothing is missing" and "we never said what complete means here".
COVERAGE_UNKNOWN = -1


def coverage_is_known(score: int) -> bool:
    """Whether a coverage number means anything. Gates must consult this before trusting it."""
    return score != COVERAGE_UNKNOWN


def coverage_score(*, present_fields: set[str], expected: dict[str, str]) -> tuple[int, list[str]]:
    """How complete the picture is, and the plain-language names of what is missing.

    Reported beside confidence, never inside it: not knowing a close date does not make
    the stage we do know less true.
    """
    # "We expect nothing" is neither 100% covered nor 0% known, and both readings cause harm.
    #
    # Scoring it 0 invents a gap that does not exist and makes every situation in a new domain
    # look broken the day it is added — absence read as negative evidence, which this codebase
    # refuses everywhere else.
    #
    # Scoring it 100 is what let 34 of one org's 73 situations report `missing=[]` and full
    # coverage, and it hands a downstream gate reading "no actionable output when required
    # context is unknown" a green light earned by ignorance.
    #
    # The honest answer is a third state. `coverage_status` carries it so a consumer can tell
    # "complete" from "we never said what complete means here", while the number stays neutral
    # rather than asserting either.
    if not expected:
        return COVERAGE_UNKNOWN, ["coverage unknown — no expectations registered for this domain"]
    missing = [label for f, label in sorted(expected.items()) if f not in present_fields]
    known = len(expected) - len(missing)
    return int(round(100 * known / len(expected))), missing


@dataclass(frozen=True, slots=True)
class Confidence:
    overall: int
    evidence: int
    freshness: int
    consistency: int
    identity: int
    coverage: int
    missing: tuple[str, ...] = ()
    inputs: dict = field(default_factory=dict)


def score_situation(*, event_count: int, source_count: int,
                    last_seen_at: datetime | None, open_discrepancies: int,
                    open_merge_proposals: int, present_fields: set[str],
                    expected_fields: dict[str, str], now: datetime) -> Confidence:
    """The whole confidence vector. Pure — every input explicit, fully replayable."""
    evidence = evidence_score(event_count=event_count, source_count=source_count)
    freshness, freshness_known = freshness_score(last_seen_at=last_seen_at, now=now)
    consistency = consistency_score(open_discrepancies=open_discrepancies)
    identity = identity_score(open_merge_proposals=open_merge_proposals)
    coverage, missing = coverage_score(present_fields=present_fields,
                                       expected=expected_fields)
    coverage_known = coverage_is_known(coverage)

    # Minimum, not average — you are only as sure as your weakest link. A dimension with
    # no basis is left OUT rather than scored zero, so "we cannot tell how current this
    # is" never reads as "this is stale".
    trust = [evidence, consistency, identity]
    if freshness_known:
        trust.append(freshness)

    return Confidence(
        overall=min(trust), evidence=evidence, freshness=freshness,
        consistency=consistency, identity=identity, coverage=coverage,
        missing=tuple(missing),
        inputs={"event_count": event_count, "source_count": source_count,
                "freshness_known": freshness_known,
                # Same shape as freshness: a dimension with no basis is REPORTED as having no
                # basis rather than being scored, so "we never said what complete means for this
                # domain" cannot be read as "this is fully covered".
                "coverage_known": coverage_known,
                "open_discrepancies": open_discrepancies,
                "open_merge_proposals": open_merge_proposals,
                "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
                # Which domain registry typed this situation. A change here explains a
                # re-typing that would otherwise look like the world changed.
                "domain_spec_version": spec_version(),
                "weakest": "freshness" if freshness_known and freshness == min(trust)
                           else ("evidence" if evidence == min(trust)
                                 else "consistency" if consistency == min(trust)
                                 else "identity")})


# ── lifecycle ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LifecycleDecision:
    status: str
    resolved_by: str | None
    reopened: bool = False


def decide_lifecycle(*, current_status: str | None, resolved_by: str | None,
                     last_seen_at: datetime | None, resolved_at: datetime | None,
                     terminal_by_fact: bool, now: datetime) -> LifecycleDecision:
    """What state this situation is in. Deterministic, and re-derived on every refresh.

    The two ways a situation ends behave differently on purpose:

      * RESOLVED BY FACT (the CRM stage went to closed-won) is recomputed each time. If
        the stage moves back, the situation un-resolves by itself — the system should not
        need a human to undo a conclusion it drew from data that has since changed.

      * RESOLVED BY A HUMAN sticks until new evidence arrives, then reopens. Someone
        marking a thing handled is a statement about the past, not a promise about the
        future; when the customer writes again, it is open again.
    """
    if terminal_by_fact:
        return LifecycleDecision(STATUS_RESOLVED, RESOLVED_BY_FACT)

    if current_status == STATUS_RESOLVED and resolved_by == RESOLVED_BY_FACT:
        # It was closed because of a fact, and that fact no longer holds.
        return LifecycleDecision(STATUS_ACTIVE, None, reopened=True)

    if current_status in (STATUS_RESOLVED, STATUS_ARCHIVED):
        if (resolved_by == RESOLVED_BY_HUMAN and last_seen_at is not None
                and resolved_at is not None and last_seen_at > resolved_at):
            return LifecycleDecision(STATUS_ACTIVE, None, reopened=True)
        if (current_status == STATUS_RESOLVED and resolved_at is not None
                and (now - resolved_at) > timedelta(days=ARCHIVE_AFTER_DAYS)):
            return LifecycleDecision(STATUS_ARCHIVED, resolved_by)
        return LifecycleDecision(current_status, resolved_by)

    if last_seen_at is None:
        return LifecycleDecision(STATUS_ACTIVE, None)
    gone_quiet = (now - last_seen_at) > timedelta(days=DORMANT_AFTER_DAYS)
    return LifecycleDecision(STATUS_DORMANT if gone_quiet else STATUS_ACTIVE, None)


# ═══════════════════════════════════════════════════════════════════════════════════
# Persistence — bulk-read the org, score in memory, upsert once per situation. The same
# shape as refresh_attention, for the same reason: one query per concept beats one query
# per row the moment a tenant has real volume.
# ═══════════════════════════════════════════════════════════════════════════════════

def _bulk(conn, sql: str, params: dict) -> list:
    return conn.execute(text(sql), params).fetchall()


def refresh_situations(store, org_id: str, *, eval_time: datetime | None = None) -> int:
    """Rebuild every situation for one org. Returns the number written.

    Idempotent: running it twice changes nothing, because every value is derived from
    graph state plus a stored human decision. A situation you cannot rebuild is a
    situation you cannot trust.
    """
    now = eval_time or datetime.now(timezone.utc)

    with store.engine.connect() as conn:
        correlations = _bulk(conn,
            "select correlation_id, anchor_node_id, anchor_type, domain, generation, "
            "       first_event_at, last_event_at, event_count "
            "from context_correlations where org_id = :o", {"o": org_id})
        if not correlations:
            return 0

        # distinct SOURCES per correlation — corroboration across tools, which is what
        # makes evidence strong, rather than how many emails one thread produced.
        sources: dict[str, int] = {r.correlation_id: int(r.n) for r in _bulk(conn,
            "select m.correlation_id, count(distinct se.source) as n "
            "from context_correlation_members m "
            "join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
            "where m.org_id = :o group by m.correlation_id", {"o": org_id})}

        facts_by_node: dict[str, dict[str, str]] = {}
        for row in _bulk(conn,
                "select subject_node_id, field, value from graph_facts "
                "where org_id = :o and valid_to is null and status = 'active'",
                {"o": org_id}):
            facts_by_node.setdefault(row.subject_node_id, {})[row.field] = row.value

        # Fields the situation's own evidence established, wherever they landed.
        #
        # Checking only the anchor node is wrong and quietly useless: `thread.ball_in_court`
        # and `commitment.due_at` are written to PEOPLE, so a company-anchored opportunity
        # would report "whose turn it is" missing forever — a detector that is always
        # right and never informative, which is the exact failure this module's docstring
        # warns about. Coverage asks what THIS SITUATION knows, not what one node holds.
        fields_by_correlation: dict[str, set[str]] = {}
        for row in _bulk(conn,
                "select distinct m.correlation_id, f.field from context_correlation_members m "
                "join graph_facts f on f.org_id = m.org_id "
                "  and f.created_by_event_id = m.event_id "
                "where m.org_id = :o and f.valid_to is null and f.status = 'active'",
                {"o": org_id}):
            fields_by_correlation.setdefault(row.correlation_id, set()).add(row.field)

        discrepancies: dict[str, int] = {r.subject_node_id: int(r.n) for r in _bulk(conn,
            "select subject_node_id, count(*) as n from discrepancies "
            "where org_id = :o and status = 'open' group by subject_node_id", {"o": org_id})}

        # An open duplicate on EITHER side means we are unsure who this is about.
        proposals: dict[str, int] = {}
        for row in _bulk(conn,
                "select left_node_id, right_node_id from merge_proposals "
                "where org_id = :o and status = 'open'", {"o": org_id}):
            for node in (row.left_node_id, row.right_node_id):
                proposals[node] = proposals.get(node, 0) + 1

        existing = {r.correlation_id: r for r in _bulk(conn,
            "select correlation_id, situation_id, status, resolved_by, resolved_at "
            "from context_situations where org_id = :o", {"o": org_id})}

    written = 0
    with store.engine.begin() as conn:
        for corr in correlations:
            if not corr.event_count:
                continue          # a group with no evidence describes nothing

            stype = situation_type(corr.anchor_type, corr.domain)
            node_facts = facts_by_node.get(corr.anchor_node_id, {})
            expected = spec_for(corr.domain).fields_for(stype)
            confidence = score_situation(
                event_count=int(corr.event_count),
                source_count=sources.get(corr.correlation_id, 0),
                last_seen_at=corr.last_event_at,
                open_discrepancies=discrepancies.get(corr.anchor_node_id, 0),
                open_merge_proposals=proposals.get(corr.anchor_node_id, 0),
                # The anchor's own facts PLUS whatever this situation's evidence
                # established elsewhere — a deal's stage sits on the deal, but whose turn
                # it is sits on a person.
                present_fields=set(node_facts) | fields_by_correlation.get(
                    corr.correlation_id, set()),
                expected_fields=expected, now=now)

            held = existing.get(corr.correlation_id)
            lifecycle = decide_lifecycle(
                current_status=held.status if held else None,
                resolved_by=held.resolved_by if held else None,
                last_seen_at=corr.last_event_at,
                resolved_at=held.resolved_at if held else None,
                terminal_by_fact=normalize_stage(
                    node_facts.get("deal.stage")) in _TERMINAL_DEAL_STAGES,
                now=now)

            situation_id = held.situation_id if held else new_id("sit")
            conn.execute(text(
                "insert into context_situations (situation_id, org_id, correlation_id, "
                "  anchor_node_id, situation_type, domain, status, resolved_by, "
                "  resolved_at, confidence_overall, confidence_evidence, "
                "  confidence_freshness, confidence_consistency, confidence_identity, "
                "  coverage, missing, inputs, first_seen_at, last_seen_at, computed_at) "
                "values (:sid, :o, :cid, :anode, :stype, :dom, :status, :rby, "
                # Archived counts as resolved for this purpose. Clearing resolved_at on
                # archive would strand the row forever: decide_lifecycle needs that
                # timestamp to tell whether new evidence post-dates the resolution, so a
                # null makes an archived situation permanently unable to reopen — the
                # opposite of what the lifecycle rules say, and invisible in a pure test.
                "  case when :status in ('resolved', 'archived') "
                "       then coalesce(:rat, :now) end, "
                "  :c_all, :c_ev, :c_fr, :c_co, :c_id, :cov, cast(:missing as jsonb), "
                "  cast(:inputs as jsonb), :first, :last, :now) "
                "on conflict (org_id, correlation_id) do update set "
                "  status = excluded.status, resolved_by = excluded.resolved_by, "
                "  resolved_at = excluded.resolved_at, "
                # A reopened situation must not keep the note explaining why it was
                # closed — it would read as the current state of something now open.
                "  resolution_note = case when excluded.status in "
                "       ('resolved', 'archived') then context_situations.resolution_note "
                "       end, "
                "  confidence_overall = excluded.confidence_overall, "
                "  confidence_evidence = excluded.confidence_evidence, "
                "  confidence_freshness = excluded.confidence_freshness, "
                "  confidence_consistency = excluded.confidence_consistency, "
                "  confidence_identity = excluded.confidence_identity, "
                "  coverage = excluded.coverage, missing = excluded.missing, "
                "  inputs = excluded.inputs, last_seen_at = excluded.last_seen_at, "
                "  situation_type = excluded.situation_type, "
                "  computed_at = excluded.computed_at"),
                {"sid": situation_id, "o": org_id, "cid": corr.correlation_id,
                 "anode": corr.anchor_node_id, "stype": stype, "dom": corr.domain,
                 "status": lifecycle.status, "rby": lifecycle.resolved_by,
                 "rat": held.resolved_at if held else None,
                 "c_all": confidence.overall, "c_ev": confidence.evidence,
                 "c_fr": confidence.freshness, "c_co": confidence.consistency,
                 "c_id": confidence.identity, "cov": confidence.coverage,
                 "missing": json.dumps(list(confidence.missing)),
                 "inputs": json.dumps(confidence.inputs, default=str),
                 "first": corr.first_event_at, "last": corr.last_event_at, "now": now})
            written += 1
    return written


def resolve_situation(conn, *, org_id: str, situation_id: str, note: str | None = None) -> bool:
    """A human marks a situation handled. Reopens by itself when new evidence arrives —
    see decide_lifecycle."""
    return conn.execute(text(
        "update context_situations set status = 'resolved', resolved_by = 'human', "
        "  resolved_at = now(), resolution_note = :note "
        "where org_id = :o and situation_id = :sid and status <> 'resolved'"),
        {"o": org_id, "sid": situation_id, "note": note}).rowcount > 0


def active_situations(conn, *, org_id: str, domain: str | None = None,
                      limit: int = 100) -> list[dict]:
    """What the Reasoning Engine asks for instead of asking for the graph.

    Ordered by confidence: a situation we are sure about is worth more thought than one
    assembled from a single unverified email. Ordering is NOT prioritisation — which
    situation matters most is a decision, and this layer does not make decisions.
    """
    filters = "and s.domain = :dom " if domain else ""
    params: dict = {"o": org_id, "lim": limit}
    if domain:
        params["dom"] = domain
    rows = conn.execute(text(
        "select s.situation_id, s.situation_type, s.domain, s.status, "
        "       s.confidence_overall, s.confidence_evidence, s.confidence_freshness, "
        "       s.confidence_consistency, s.confidence_identity, s.coverage, s.missing, "
        "       s.first_seen_at, s.last_seen_at, s.anchor_node_id, "
        "       n.display_name as anchor_name, n.node_type as anchor_type, "
        "       c.event_count "
        "from context_situations s "
        "join context_correlations c on c.org_id = s.org_id "
        "     and c.correlation_id = s.correlation_id "
        "left join graph_nodes n on n.org_id = s.org_id and n.node_id = s.anchor_node_id "
        "     and n.valid_to is null "
        "where s.org_id = :o and s.status = 'active' " + filters +
        "order by s.confidence_overall desc, s.last_seen_at desc nulls last limit :lim"),
        params).mappings().all()
    return [dict(r) for r in rows]
