"""L2 · State-based situations — what is HAPPENING, not who it is about.

Every situation this layer produced until now was named after the ANCHOR it hung on:
`domain_spec.type_for` maps a node type to a type name, so a person became `admin_contact`, a
company `account_admin`, a deal `investor_relationship`.  Those say WHO.  None of them says what
is presently true, and Layer 3 routes on the situation type — so a capability written for "an
outbound message has gone unanswered" had nothing to attach to, and the corpus's own gates
collapsed to the one predicate a person-shaped situation could offer, `thread.ball_in_court`.
Every waiting relationship in the org therefore reached the same lane and produced the same card.

This module mints the two readings that are pure STATE:

    awaiting_response    we wrote, they have not answered, and it has been long enough to say so
    commitment_overdue   we promised something, the date has passed, and nothing shows it landed

Both follow the pattern `support_situations.py` established and for the same reasons: an anchor
node the correlation engine cannot reach, the computed facts written onto it as ordinary facts,
one situation upserted there — so `_load_context`, `_neighborhood`, `build_context_slice` and the
whole compile path need no new concept.  Neither anchor is in `correlation.ANCHOR_PRIORITY`:
`choose_anchors` returns only the strongest tier present, and a synthetic anchor reachable from
correspondence would swallow the conversation it describes.

It computes almost nothing itself.  `waiting.py` already derived the durations, the follow-up
count and the counterparty's own cadence; this reads them back and gives them a NAME a capability
can route on.  The split is deliberate — a fact is true whether or not anyone has a situation for
it, and a situation is a claim about which facts, together, are worth a decision.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.context.domain_spec import domains_declaring, spec_for
from genios_engine.context.situations import (
    evidence_score,
    freshness_score,
    identity_score,
)
# The support readings' persistence helpers, imported rather than copied. They already encode
# decisions this module must not make differently — a recompute overwrites its own deterministic
# fact version instead of appending a row per sweep, coverage is capped honestly, `overall` is the
# MINIMUM of the trust dimensions, and a finding that stops being true is resolved BY FACT so it
# reopens by itself. A second copy of that reasoning would drift from this one within a month.
from genios_engine.context.support_situations import (
    _coverage,
    _reconcile,
    _upsert,
    _write_fact,
)

#: One outbound conversation waiting on an answer. Not `thread`: support already anchors its
#: first-response reading there, and two readings cannot share an anchor because `type_for` maps
#: an anchor to exactly one name per domain.
ANCHOR_OUTREACH = "outreach"

#: One promise WE made whose date has passed. The mirror image of support's `backlog_item`, which
#: is one unmet ask THEY made — opposite owner, opposite remedy, and a card that confuses them
#: tells the user to chase somebody for something the user themselves owes.
ANCHOR_COMMITMENT = "commitment"

#: One CAMPAIGN — everyone contacted with the same stated objective. The first anchor in this
#: system whose subject is a GROUP rather than a thing: every situation until now was about one
#: person, one promise or one meeting, so the question "of everyone I contacted about the raise,
#: who has gone quiet?" could only be answered by reading N separate cards and doing the
#: arithmetic by hand.
ANCHOR_COHORT = "cohort"

#: How overdue a promise must be before it is a situation. Zero: a commitment is overdue the
#: moment its own stated date passes, and that date came from the user's own words rather than
#: from a threshold this layer invented.
_OVERDUE_AFTER_DAYS = 0

#: Below this, silence is not yet a finding. Deliberately low and deliberately here rather than in
#: the corpus: this is the point at which the situation is worth NAMING, not the point at which
#: anyone should act. What counts as late for a given counterparty is a domain judgment, and the
#: evidence for it — `party.reply_cadence_days` — travels on the anchor for Layer 3 to rule on.
_WAITING_AFTER_DAYS = 2

_WAITING_ROWS = (
    "select f.subject_node_id as node_id, f.field as field, f.value as value, "
    "       n.display_name as name "
    "from graph_facts f "
    "join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id "
    "     and n.valid_to is null "
    # A READING MAY NEVER CONSUME ITS OWN OUTPUT.
    #
    # `read_overdue_commitments` writes `commitment.action` and `commitment.due_at` onto the
    # anchor it mints. Without this exclusion the next sweep read those facts back, saw a node
    # carrying an overdue commitment, and minted an anchor FOR THE ANCHOR — keyed
    # `commitment:<the previous anchor>`. Every sweep multiplied the set: one real promise on the
    # design partner's org became fifteen identical cards, all "reply to confirm receipt", all
    # 39 days overdue, all with the same due date, and it would have kept doubling.
    #
    # Filtered on node TYPE rather than on the fact names, because the same trap is waiting for
    # any future reading that projects a fact onto its own anchor — and because a reading is
    # about real subjects by definition. `outreach` escaped only by accident: it happens to
    # project `outreach.*` rather than the `thread.*` names it reads.
    "and n.node_type not in ('outreach', 'commitment', 'cohort') "
    "where f.org_id = :o and f.valid_to is null and f.status = 'active' "
    "and f.field in ('thread.days_waiting', 'thread.follow_up_count', 'thread.last_heard_days', "
    "                'thread.response_expected', 'party.reply_cadence_days', "
    "                'relationship.nature', 'party.role', 'thread.ball_in_court', "
    "                'thread.objective', "
    "                'commitment.due_at', 'commitment.action', 'thread.last_outbound')"
)

#: A campaign of one is a thread, and the per-counterparty reading already covers it. Three is the
#: smallest number where "how is this outreach GOING" is a different question from "what about this
#: person" — below it the aggregate says nothing the individual rows do not.
_MIN_COHORT = 3

#: …and at least two of them still waiting, or the cohort has nothing to report. One straggler in
#: an otherwise-answered campaign is that person's situation, not the campaign's.
_MIN_COHORT_AWAITING = 2

#: How many names a cohort fact may carry. A card that can say WHO is waiting longest is worth
#: reading; a card carrying forty names is a spreadsheet.
_COHORT_NAMES = 5

_EMPLOYERS = (
    "select e.from_node_id as person, n.display_name as company "
    "from graph_edges e "
    "join graph_nodes n on n.org_id = e.org_id and n.node_id = e.to_node_id "
    "     and n.valid_to is null and n.node_type = 'company' "
    "where e.org_id = :o and e.edge_type = 'works_at' and e.valid_to is null"
)

_EVENT_COUNTS = (
    "select o.subject_node_id as node_id, count(*) as events, "
    "       count(distinct r.source) as sources, min(o.occurred_at) as first_at, "
    "       max(o.occurred_at) as last_at "
    "from graph_observations o "
    "left join graph_source_refs r on r.observation_id = o.observation_id and r.org_id = :o "
    "where o.org_id = :o and o.status = 'active' and o.subject_node_id is not null "
    "group by o.subject_node_id"
)


def _num(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ts(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class _Finding:
    """One state reading, ready to be persisted. Deliberately not a dataclass with a schema of its
    own: `support_situations.Finding` already names these fields and this module writes through
    that module's `_upsert`, so a second, subtly different shape would be a trap."""

    __slots__ = ("anchor", "canonical_key", "display_name", "facts", "concerns_node",
                 "correlation_id", "missing", "inputs")

    def __init__(self, **kw):
        for name in self.__slots__:
            setattr(self, name, kw.get(name))


def read_awaiting_response(rows: dict, now: datetime, employers: dict) -> list[_Finding]:
    """One finding per counterparty we are waiting on. (`employers` is unused here: every
    reader takes the same arguments so the dispatch loop stays a plain lookup rather than a
    per-reader signature check.)

    Fires on `thread.days_waiting`, which `waiting.py` writes ONLY while the last message in the
    exchange is ours. So the reading cannot fire on a conversation they have already answered,
    and it closes itself the moment they do — `_reconcile` resolves it by fact on the next sweep.
    """
    findings: list[_Finding] = []
    for node_id, held in rows.items():
        waited = _num(held.get("thread.days_waiting"))
        if waited is None or waited < _WAITING_AFTER_DAYS:
            continue
        name = held.get("_name") or "this contact"
        facts: list[tuple[str, object, str]] = [
            ("outreach.days_waiting", int(waited), "number"),
            ("outreach.counterparty", name, "string"),
        ]
        for source, target, kind in (
                ("thread.follow_up_count", "outreach.follow_up_count", "number"),
                ("thread.last_heard_days", "outreach.days_since_last_heard", "number"),
                ("party.reply_cadence_days", "outreach.their_normal_reply_days", "number"),
        ):
            value = _num(held.get(source))
            if value is not None:
                facts.append((target, int(value), kind))
        expected = held.get("thread.response_expected")
        if expected is not None:
            facts.append(("outreach.response_expected", bool(expected), "bool"))
        # WHAT THEY ARE TO US is the field that changes the advice — an investor who has gone
        # quiet and a prospect who has need opposite messages — so it travels on the anchor
        # rather than being left one hop away for a reader who may not walk it.
        role = held.get("relationship.nature") or held.get("party.role")
        if role:
            facts.append(("outreach.counterparty_role", str(role), "enum"))
        # WHY WE WROTE. The field that separates a follow-up from a reminder, and the one this
        # situation declared missing on every row until `pipeline.objective_of` gave it a writer.
        # Still absent whenever the extractor could not place the message, which is the honest
        # state and keeps it in `missing` rather than satisfied by a meaningless label.
        objective = held.get("thread.objective")
        if objective:
            facts.append(("outreach.objective", str(objective), "enum"))
        findings.append(_Finding(
            anchor=ANCHOR_OUTREACH,
            canonical_key=f"outreach:{node_id}",
            display_name=f"{name} — awaiting reply",
            facts=facts,
            concerns_node=node_id,
            correlation_id=f"outreach:{node_id}",
            # EMPTY, because `_coverage` already derives it. The gap that matters here —
            # `outreach.objective`, since nothing in this system knows what an outbound was FOR —
            # is declared in `domain_spec.expected_fields`, and naming it a second time here
            # printed it twice on every row. One declaration, one source, and it is the one the
            # coverage score is computed against.
            missing=[],
            inputs={"reading": ANCHOR_OUTREACH,
                    "derived_from": "message timeline; no source system reports silence"},
        ))
    return findings


def read_overdue_commitments(rows: dict, now: datetime, employers: dict) -> list[_Finding]:
    """One finding per promise of ours whose own stated date has passed.

    The date is the USER'S, extracted from their own sentence, so this reading invents no
    deadline. A commitment with no date is not overdue and produces nothing here — an obligation
    without a time is a different situation and needs a different card.
    """
    findings: list[_Finding] = []
    for node_id, held in rows.items():
        due = _ts(held.get("commitment.due_at"))
        if due is None:
            continue
        overdue = (now - due).total_seconds() / 86400.0
        if overdue <= _OVERDUE_AFTER_DAYS:
            continue
        name = held.get("_name") or "this contact"
        action = held.get("commitment.action")
        facts: list[tuple[str, object, str]] = [
            ("commitment.days_overdue", int(overdue), "number"),
            ("commitment.owed_to", name, "string"),
            ("commitment.due_at", due.isoformat(), "timestamp"),
        ]
        if action:
            facts.append(("commitment.action", str(action), "string"))
        findings.append(_Finding(
            anchor=ANCHOR_COMMITMENT,
            canonical_key=f"commitment:{node_id}",
            display_name=f"{name} — promise past due",
            facts=facts,
            concerns_node=node_id,
            correlation_id=f"commitment:{node_id}",
            # Same reason as above: `commitment.delivered_at` — no delivery receipt exists
            # anywhere in this system — is declared once, in `expected_fields`, and `_coverage`
            # is what puts it on the row.
            missing=[],
            inputs={"reading": ANCHOR_COMMITMENT,
                    "derived_from": "the user's own stated date; no completion receipt exists"},
        ))
    return findings


def read_outreach_cohorts(rows: dict, now: datetime, employers: dict) -> list[_Finding]:
    """One finding per OBJECTIVE somebody is running as a campaign.

    THE COHORT KEY IS THE OBJECTIVE, NOT THE ORGANISATION, and that is the load-bearing choice.
    The question this exists to answer — "of everyone I contacted about the raise, who has gone
    quiet?" — spans funds; two partners at two different firms are one campaign, while a
    fundraising thread and a vendor thread with the SAME firm are two different things needing
    opposite answers. Keying on the company would have split the first and merged the second.
    Organisations still travel, as a facet inside the cohort, because "which firms are in this"
    is a real question — it is just not what makes these people one group.

    LATE IS COMPARATIVE HERE TOO. `cohort.awaiting_beyond_normal` counts against each person's own
    measured reply cadence, falling back to the cohort's median where an individual has too little
    history — never against a fixed number of days, which would be a policy invented in Layer 2
    and would call a fund that answers monthly late every fortnight.

    Nothing is minted below `_MIN_COHORT` contacted or `_MIN_COHORT_AWAITING` still waiting: an
    aggregate over two people says nothing their own two situations do not already say, and a
    situation that adds no information is noise with a confidence score attached.
    """
    by_objective: dict[str, list[tuple[str, dict]]] = {}
    for node_id, held in rows.items():
        objective = held.get("thread.objective")
        if objective:
            by_objective.setdefault(str(objective), []).append((node_id, held))

    findings: list[_Finding] = []
    for objective, members in sorted(by_objective.items()):
        if len(members) < _MIN_COHORT:
            continue
        # THE SAME THRESHOLD THE PER-PERSON READING USES. Counting anyone whose last message was
        # ours — including somebody we wrote to yesterday — would report a campaign as "gone
        # quiet" the day it was sent. The two readings must agree about what waiting means or the
        # cohort's numbers will not match the cards underneath it.
        waiting = [(node_id, held) for node_id, held in members
                   if (_num(held.get("thread.days_waiting")) or 0.0) >= _WAITING_AFTER_DAYS]
        if len(waiting) < _MIN_COHORT_AWAITING:
            continue

        cadences = [c for c in (_num(held.get("party.reply_cadence_days"))
                                for _, held in members) if c is not None]
        median_reply = round(median(cadences), 2) if cadences else None

        beyond = never_chased = chased_twice = measurable = 0
        for _, held in waiting:
            waited = _num(held.get("thread.days_waiting")) or 0.0
            # Their own history first; the cohort's median only where they have none. A person
            # with no measured cadence is not evidence that the cohort's is theirs — it is the
            # best available stand-in, and it is why this is a count and not a verdict.
            normal = _num(held.get("party.reply_cadence_days"))
            if normal is None:
                normal = median_reply
            if normal is not None:
                # COUNTED SEPARATELY from the verdict. A zero `beyond` means two completely
                # different things — "we checked everyone and nobody is late" and "we could not
                # check anybody" — and the fallback printed the second as the first: "0 past
                # their own usual reply time" on a campaign where not one person's cadence was
                # knowable. `measurable` is what tells them apart.
                measurable += 1
                if waited > normal:
                    beyond += 1
            chased = _num(held.get("thread.follow_up_count"))
            if chased is not None:
                if chased == 0:
                    never_chased += 1
                elif chased >= 2:
                    chased_twice += 1

        # REPLIED means we have ever heard back, not that the current thread is answered — a
        # campaign's reply rate is about who engaged at all.
        replied = sum(1 for _, held in members
                      if _num(held.get("thread.last_heard_days")) is not None)
        orgs = sorted({employers[node_id] for node_id, _ in members
                       if node_id in employers})
        # Longest wait first: the names most worth putting on a card.
        longest = [held.get("_name") or "unknown" for _, held in
                   sorted(waiting, key=lambda pair: -(_num(pair[1].get("thread.days_waiting"))
                                                      or 0.0))][:_COHORT_NAMES]

        facts: list[tuple[str, object, str]] = [
            ("cohort.objective", objective, "enum"),
            ("cohort.contacted", len(members), "number"),
            ("cohort.replied", replied, "number"),
            ("cohort.awaiting", len(waiting), "number"),
            ("cohort.never_chased", never_chased, "number"),
            ("cohort.chased_twice_plus", chased_twice, "number"),
            ("cohort.reply_rate_bp", int(round(10000 * replied / len(members))), "number"),
            # WHERE A NEXT STEP EXISTS. The gate used to be `awaiting_beyond_normal >= 1` alone,
            # and on a real campaign that number is usually ZERO for an honest reason:
            # `party.reply_cadence_days` needs two prior replies from a person, and early in a
            # raise almost nobody has replied twice. So the one card that answers "who has gone
            # quiet across all of this" could never fire on the campaigns that most need it.
            #
            # Never-chased is equally good evidence and needs no history at all — somebody nobody
            # has followed up is a next step whether or not we know their usual rhythm. Summed
            # rather than OR'd because the predicate grammar is AND-only: one number the gate can
            # compare, meaning "people where something can actually be done".
            ("cohort.chaseable", never_chased + beyond, "number"),
            ("cohort.cadence_known", measurable, "number"),
            ("cohort.waiting_longest", ", ".join(longest), "string"),
        ]
        # WRITTEN ONLY WHEN IT WAS MEASURABLE. Absent is the honest state when nobody in the
        # campaign has replied twice — the slot then holds its sentinel and the clause carrying
        # it is cut from the card, which says nothing rather than saying zero.
        if measurable:
            facts.append(("cohort.awaiting_beyond_normal", beyond, "number"))
        if median_reply is not None:
            facts.append(("cohort.median_reply_days", median_reply, "number"))
        if orgs:
            facts.append(("cohort.organizations", ", ".join(orgs[:8]), "string"))
            facts.append(("cohort.organization_count", len(orgs), "number"))

        findings.append(_Finding(
            anchor=ANCHOR_COHORT,
            canonical_key=f"cohort:{objective}",
            display_name=objective.replace("_", " "),
            facts=facts,
            # The cohort concerns the person waiting longest, so the card has a real subject to
            # hang evidence and an owner on. It is a REPRESENTATIVE, not the finding's scope —
            # `cohort.contacted` says how many this is really about.
            concerns_node=(sorted(waiting,
                                  key=lambda pair: -(_num(pair[1].get("thread.days_waiting"))
                                                     or 0.0))[0][0]),
            correlation_id=f"cohort:{objective}",
            missing=[],
            inputs={"reading": ANCHOR_COHORT, "objective": objective,
                    "derived_from": "per-counterparty waiting state, grouped by stated objective"},
        ))
    return findings


READINGS = (
    (ANCHOR_OUTREACH, read_awaiting_response),
    (ANCHOR_COMMITMENT, read_overdue_commitments),
    (ANCHOR_COHORT, read_outreach_cohorts),
)


def state_domains() -> tuple[str, ...]:
    """Every domain that declares one of these anchors — asked of the registry, never listed here.
    Naming a domain in Layer 2 would mean adding a domain requires editing Layer 2, and the
    registry exists precisely so it does not."""
    out: set[str] = set()
    for anchor, _ in READINGS:
        out.update(domains_declaring(anchor))
    return tuple(sorted(out))


def _gather(store, org_id: str) -> tuple[dict, dict, dict]:
    with store.engine.connect() as c:
        held: dict[str, dict] = {}
        for row in c.execute(text(_WAITING_ROWS), {"o": org_id}):
            entry = held.setdefault(str(row.node_id), {})
            entry[str(row.field)] = row.value
            entry["_name"] = row.name
        counts = {str(r.node_id): r for r in c.execute(text(_EVENT_COUNTS), {"o": org_id})}
        # person -> employing company NAME. Read here rather than per finding: the cohort reading
        # needs it for every member at once, and one bulk read is the same discipline every other
        # pass in this layer keeps.
        employers = {str(r.person): str(r.company)
                     for r in c.execute(text(_EMPLOYERS), {"o": org_id}) if r.company}
    return held, counts, employers


def refresh_state_situations(store, org_id: str, *, now: datetime | None = None) -> int:
    """Open, refresh or close the state readings for this org. Returns rows written.

    Idempotent for the same reasons the support readings are: every fact overwrites its own
    deterministic version id and every situation conflicts on `(org_id, correlation_id)`, so six
    sweeps a day produce one row per finding rather than six.
    """
    now = now or datetime.now(timezone.utc)
    if not state_domains():
        return 0
    held, counts, employers = _gather(store, org_id)
    if not held:
        return 0

    written = 0
    with store.engine.begin() as c:
        for anchor, reader in READINGS:
            claiming = domains_declaring(anchor)
            if not claiming:
                continue
            minted: dict[str, set[str]] = {d: set() for d in claiming}
            for finding in reader(held, now, employers):
                node_id = store.find_or_create_node(
                    c, org_id=org_id, node_type=anchor,
                    canonical_key=finding.canonical_key,
                    display_name=finding.display_name, event_id=None)
                for field_name, value, value_type in finding.facts:
                    _write_fact(c, org_id=org_id, node_id=node_id, field_name=field_name,
                                value=value, value_type=value_type, now=now,
                                key=f"{org_id}_{node_id}_{field_name}")
                    written += 1
                # One hop to the person, so the context slice and the neighbourhood walk pull
                # their facts in through the path they already take.
                store.write_edge(c, org_id=org_id, edge_type="concerns",
                                 from_node_id=node_id, to_node_id=finding.concerns_node,
                                 confidence=0.9, occurred_at=now,
                                 event_id=f"state:{org_id}",
                                 evidence={"derived": "l2 state reading"}, source="engine",
                                 authority_rank=2)
                stats = counts.get(finding.concerns_node)
                present = {name for name, _, _ in finding.facts}
                for domain in claiming:
                    stype = spec_for(domain).type_for(anchor)
                    corr = f"{finding.correlation_id}_{domain}"
                    minted[domain].add(corr)
                    coverage, gaps = _coverage(domain, stype, present, 100)
                    last_at = getattr(stats, "last_at", None)
                    fresh, fresh_known = freshness_score(last_seen_at=last_at, now=now)
                    _upsert(c, org_id=org_id, corr=corr, node_id=node_id, stype=stype,
                            domain=domain, now=now, coverage=coverage,
                            missing=list(finding.missing) + gaps,
                            inputs=finding.inputs,
                            evidence=evidence_score(
                                event_count=int(getattr(stats, "events", 0) or 0),
                                source_count=int(getattr(stats, "sources", 0) or 0)),
                            freshness=fresh if fresh_known else None,
                            identity=identity_score(open_merge_proposals=0),
                            first_seen=getattr(stats, "first_at", None), last_seen=last_at)
                    written += 1
            for domain, live in minted.items():
                written += _reconcile(c, org_id=org_id,
                                      stype=spec_for(domain).type_for(anchor),
                                      live=live, now=now)
    return written


__all__ = ["refresh_state_situations", "state_domains",
           "ANCHOR_OUTREACH", "ANCHOR_COMMITMENT"]
