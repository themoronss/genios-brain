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

from datetime import datetime, timedelta, timezone

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

#: One conditional statement nobody could turn into a checkable predicate. Its own anchor: a
#: counterparty can leave several across months and they close separately.
ANCHOR_CONDITION = "condition"

#: L2.3 · Cross Organization. The counterparty FIRM, not the person and not the campaign.
#:
#: The pilot writes to two partners at Peak XV and two at Afore and holds four situations; nothing
#: says "Peak XV — both of them, both silent". `ANCHOR_COHORT` cannot say it either, and
#: deliberately: it keys on the OBJECTIVE because "of everyone I contacted about the raise, who
#: has gone quiet?" spans funds. That is a different question from "has this firm gone quiet",
#: and answering the second by re-keying the first would break the first.
#:
#: Its own anchor because a firm's silence outlives any one campaign and closes on its own terms —
#: one partner replying changes the firm's answer without changing the campaign's.
ANCHOR_ORGANIZATION = "organization"

#: L2.3 · Cross Conversation. The MESSAGE we actually sent, and everyone it went to.
#:
#: `ANCHOR_COHORT` was supposed to answer this and cannot on a real tenant. It groups on
#: `thread.objective`, and that field has ZERO facts in the pilot's graph — not superseded, never
#: written, because it is an LLM label and the extractor never placed one. Measured: 0 of 141
#: waiting rows carry it, so `read_outreach_cohorts` returns 0 findings and
#: `admin.sit.campaign_going_quiet` — authored, approved, content-hashed — is structurally
#: unfireable. `relationship.nature`, its sibling label, has exactly one fact across every node.
#:
#: This anchor keys on OBSERVED EVIDENCE instead: one sentence we wrote, sent to at least three
#: counterparties inside a day and a half, with the verbatim line and the real event ids behind
#: it. On the pilot that finds two campaigns from 11 August, 7 and 6 recipients.
#:
#: Its own anchor rather than a second key on `cohort` because the two carry different evidence
#: and must not silently substitute for one another — see `read_campaign_silence`, which yields to
#: an objective-keyed cohort covering the same people rather than minting a second card about them.
ANCHOR_CAMPAIGN = "campaign"

#: How far back a campaign may have been sent and still be worth a card.
#:
#: A DEFAULT, NOT A LAW. `refresh_state_situations` takes it as an argument and `find_campaigns`
#: has never had a default at all — its docstring says why: "a caller choosing the window is a
#: caller who knows which window their answer is about." Ninety days is a founder's fundraise; a
#: procurement cycle is longer and a support desk's is far shorter. When a per-tenant source is
#: needed, `capture/esqe/qualification.org_qualification_floors` is the proven shape.
CAMPAIGN_WINDOW_DAYS = 90

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

#: commitment node -> the person who MADE the promise.
#:
#: THE EDGE HAS ALWAYS EXISTED AND NOBODY READ IT. `context/pipeline.py` writes
#: `owns` from the commitment ACTOR to the commitment node, with `evidence={"derived":
#: "commitment actor"}` — so the graph has always known whose promise it was. This reading never
#: asked, and its docstring says "one finding per promise of OURS", which is true only when the
#: actor happens to be us. On the pilot tenant it frequently was not: three of the nine cards
#: rendered a counterparty's promise as the founder's own overdue obligation, at critical urgency,
#: in the founder's voice.
#:
#: Bulk, keyed by the commitment node, read once per sweep beside `_EMPLOYERS` — the same
#: discipline every other pass in this layer keeps, and for the same reason: a per-finding read
#: here is one round trip per card against a table that answers the whole org in one.
_COMMITMENT_OWNERS = (
    "select e.to_node_id as commitment, e.from_node_id as owner_node, "
    "       n.display_name as owner_name, n.canonical_key as owner_key "
    "from graph_edges e "
    "join graph_nodes n on n.org_id = e.org_id and n.node_id = e.from_node_id "
    "     and n.valid_to is null "
    "where e.org_id = :o and e.edge_type = 'owns' and e.valid_to is null"
)

#: THREADS WHOSE COUNTERPARTY IS ALREADY WAITING IN THEIR OWN RIGHT.
#:
#: `waiting.py` writes `thread.*` onto BOTH subjects — the thread node and the party who
#: corresponded on it — because "this thread has waited 28 days" and "this person has waited 28
#: days" are genuinely different facts and a later reader may want either. This reading wanted
#: neither in duplicate: it mints one anchor per node carrying the facts, so it produced two
#: situations for every waiting conversation. Measured on the pilot: 41 `awaiting_response`
#: situations covering 22 distinct counterparties, the thread-anchored twin of each pair carrying
#: `confidence_overall = 0` and a display name of "Thread with vatsa@valiron.co" beside the real
#: one's "vatsa@valiron.co".
#:
#: THE PERSON IS THE SUBJECT, so the thread yields. A card reads "Vidushi has not replied in 28
#: days"; "Thread with vidushi@peakxv.com has not replied" is the same sentence said worse.
#:
#: The party must ALSO be waiting, not merely exist. Three of the pilot's twenty-one waiting
#: threads have no waiting party — a thread whose counterparty node was never resolved, which is
#: exactly the case that must keep its situation rather than vanish into a gap nobody sees.
_THREAD_COVERED_BY_PARTY = (
    "select distinct e.to_node_id as thread, e.from_node_id as party, "
    "       p.display_name as party_name "
    "from graph_edges e "
    "join graph_nodes t on t.org_id = e.org_id and t.node_id = e.to_node_id "
    "                  and t.node_type = 'thread' and t.valid_to is null "
    "join graph_nodes p on p.org_id = e.org_id and p.node_id = e.from_node_id "
    "                  and p.valid_to is null "
    "join graph_facts f on f.org_id = e.org_id and f.subject_node_id = e.from_node_id "
    "                  and f.field = 'thread.days_waiting' and f.status = 'active' "
    "                  and f.valid_to is null "
    "where e.org_id = :o and e.edge_type = 'corresponded_with' and e.valid_to is null"
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
        # Reserved keys carry the condition queue and the mailbox owner, not a node's facts.
        if node_id.startswith("_") or not isinstance(held, dict):
            continue
        waited = _num(held.get("thread.days_waiting"))
        if waited is None or waited < _WAITING_AFTER_DAYS:
            continue
        if held.get("_covered_by_party"):
            # ONE SITUATION PER CONVERSATION. This node is a thread whose counterparty carries
            # the same waiting facts and will mint the anchor themselves — see
            # `_THREAD_COVERED_BY_PARTY`. Skipped here rather than deduplicated afterwards
            # because the two rows are not near-duplicates to be merged: one of them is simply
            # the wrong subject to address a card to.
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
        # Reserved keys carry the condition queue and the mailbox owner, not a node's facts.
        if node_id.startswith("_") or not isinstance(held, dict):
            continue
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
        # WHOSE PROMISE IT IS. Read from the `owns` edge the extractor has always written from the
        # commitment ACTOR. Absent when the graph cannot say, and absent is left absent rather
        # than defaulted to us — "we do not know who promised this" and "the founder promised
        # this" are different cards, and the second one was being shown for both.
        owner_name = held.get("_owner_name")
        owner_key = held.get("_owner_key")
        if owner_name:
            facts.append(("commitment.owner", str(owner_name), "string"))
        if owner_key:
            facts.append(("commitment.owner_key", str(owner_key), "string"))
        findings.append(_Finding(
            anchor=ANCHOR_COMMITMENT,
            canonical_key=f"commitment:{node_id}",
            display_name=(f"{owner_name} — promise to {name} past due" if owner_name
                          else f"{name} — promise past due"),
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
        # Reserved keys carry the condition queue and the mailbox owner, not a node's facts.
        if node_id.startswith("_") or not isinstance(held, dict):
            continue
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
                    # WHO THIS COVERS, so a second group-shaped reading can yield to it instead of
                    # minting a competing card about the same people. `read_campaign_silence`
                    # reads exactly this; without it the scope of a cohort is legible only by
                    # re-deriving the grouping, which is how two readings drift apart.
                    "members": sorted(node_id for node_id, _held in waiting),
                    "derived_from": "per-counterparty waiting state, grouped by stated objective"},
        ))
    return findings


def read_campaign_silence(rows: dict, now: datetime, employers: dict) -> list[_Finding]:
    """One finding per authored MESSAGE that went out to several people and came back from few.

    `_gather` stamps the campaigns onto `rows` under `_campaigns`, the same reserved-key route
    `_conditions` and `_organizations` take.

    WHY THIS EXISTS ALONGSIDE `read_outreach_cohorts` AND NOT INSTEAD OF IT. They answer the same
    question from different evidence. The cohort reading groups on `thread.objective` — what the
    model judged the exchange was FOR — and that is the better key when it exists, because two
    different messages about one raise are one campaign to a founder. It does not exist here: zero
    `thread.objective` facts in the pilot's graph, so the reading returns nothing and its authored,
    approved, content-hashed card can never fire. This groups on the sentence actually sent, which
    is observed rather than inferred and carries a verbatim receipt.

    IT YIELDS RATHER THAN COMPETES. A campaign whose still-waiting recipients are already inside an
    objective-keyed cohort mints nothing: one group of people gets one group card, and the one
    backed by a stated purpose wins. The same rule `_THREAD_COVERED_BY_PARTY` applies to a
    conversation, applied one level up.
    """
    campaigns = rows.get("_campaigns") or ()
    covered: set[str] = set()
    for finding in read_outreach_cohorts(rows, now, employers):
        covered.update(finding.inputs.get("members") or ())

    findings: list[_Finding] = []
    # LARGEST FIRST, so the yield below resolves in favour of the send that reaches more people.
    # `find_campaigns` already returns them this way; sorting here as well keeps the rule true of
    # any sequence a caller stamps on, including a hand-built one in a test.
    for campaign in sorted(campaigns, key=lambda c: -c.size):
        waiting: list[tuple[str, str, float]] = []
        for node_id in campaign.recipients:
            held = rows.get(node_id)
            if not isinstance(held, dict) or held.get("_covered_by_party"):
                continue
            waited = _num(held.get("thread.days_waiting"))
            if waited is None or waited < _WAITING_AFTER_DAYS:
                continue
            waiting.append((node_id, str(held.get("_name") or node_id), waited))
        if len(waiting) < _MIN_COHORT_AWAITING:
            continue
        silent = {node for node, _n, _d in waiting}
        # A SEND WHOSE SILENT PEOPLE ARE ALL ALREADY ON A CARD SAYS NOTHING NEW. This covers both
        # directions: an objective-keyed cohort that already groups them, and a larger campaign
        # emitted above. SUBSET, not overlap — the founder sent two different lines on 11 August
        # and their recipient sets intersect without either containing the other, which is two
        # real sends and not one duplicated. An overlap threshold here would be a policy invented
        # in Layer 2, which is the choice this module refuses everywhere else.
        if silent <= covered:
            continue
        covered |= silent
        waiting.sort(key=lambda item: -item[2])
        facts: list[tuple[str, object, str]] = [
            ("campaign.contacted", campaign.size, "number"),
            ("campaign.awaiting", len(waiting), "number"),
            ("campaign.longest_wait_days", int(waiting[0][2]), "number"),
            ("campaign.sent_on", campaign.first_sent.date().isoformat(), "string"),
            ("campaign.people", ", ".join(name for _n, name, _d in waiting[:8]), "string"),
            # THE VERBATIM LINE, which is the whole reason this key is trustworthy where the
            # objective key is not. It is what L1 extracted and verified from the message we sent;
            # nothing here re-reads a body or paraphrases one.
            # WHITESPACE-FOLDED FOR THE CARD, and only that. The words are untouched; a mail body
            # wraps its lines and a line break inside a headline slot breaks the sentence a reader
            # sees. `normalise_sentence` is the same fold the grouping key uses, minus the
            # lower-casing, so display and identity cannot disagree about what the line was.
            ("campaign.quote", " ".join(campaign.sentence.split()), "string"),
        ]
        # WHAT THIS OUTREACH WAS FOR IS NOT KNOWN AND IS NOT GUESSED. `cohort.objective` is a
        # closed enum and a sentence is not a member of it; writing the quote there would put a
        # free-text value into a field rules gate on. It stays missing, and the card says what was
        # SENT rather than what it was for.
        missing = ["campaign.objective"]
        findings.append(_Finding(
            anchor=ANCHOR_CAMPAIGN,
            canonical_key=f"campaign:{campaign.campaign_id}",
            display_name=f"Sent {campaign.first_sent:%d %b} — {len(waiting)} unanswered",
            facts=facts,
            concerns_node=waiting[0][0],
            correlation_id=f"campaign:{campaign.campaign_id}",
            missing=missing,
            inputs={"reading": ANCHOR_CAMPAIGN,
                    "campaign_id": campaign.campaign_id,
                    "events": list(campaign.event_ids[:20]),
                    "derived_from": "one authored sentence, its recipients, and their waiting state"},
        ))
    return findings


def read_organization_silence(rows: dict, now: datetime, employers: dict) -> list[_Finding]:
    """One finding per counterparty ORGANISATION where more than one person has gone quiet.

    `_gather` stamps the org groups onto `rows` under `_organizations`, the same reserved-key
    route `_conditions` takes, so this stays a pure function over facts and the dispatch loop
    keeps one signature.

    WHAT MAKES THIS DIFFERENT FROM THE COHORT READING, which is the question a reviewer will ask
    first. `read_outreach_cohorts` groups by OBJECTIVE and says "the raise has stalled across nine
    funds". This groups by FIRM and says "Peak XV has stopped answering". A campaign and a
    relationship close on different terms: one partner replying revives the firm without reviving
    the campaign, and the campaign ending does not mean the firm ever answered. Both were measured
    on the pilot — the cohort reading returns findings keyed on the raise, this one returns four
    firms, and the sets are not the same rows.

    IT MINTS NOTHING WHEN ONE PERSON IS SILENT AND ANOTHER ANSWERED. A firm where one of two
    contacts replied is not a firm that has gone quiet, and a card saying so would be wrong about
    the single fact it exists to report — so the group is narrowed to the waiting members BEFORE
    the floor is applied, never filtered afterwards.
    """
    from genios_engine.context.correlation_organization import MIN_MEMBERS

    groups = rows.get("_organizations") or ()
    findings: list[_Finding] = []
    for group in groups:
        waiting: list[tuple[str, str, float]] = []
        for member in group.members:
            held = rows.get(member.node_id)
            if not isinstance(held, dict) or held.get("_covered_by_party"):
                continue
            waited = _num(held.get("thread.days_waiting"))
            if waited is None or waited < _WAITING_AFTER_DAYS:
                continue
            waiting.append((member.node_id, member.name, waited))
        if len(waiting) < MIN_MEMBERS:
            continue
        waiting.sort(key=lambda item: -item[2])
        longest = waiting[0]
        facts: list[tuple[str, object, str]] = [
            ("organization.name", group.company, "string"),
            ("organization.contacted", group.size, "number"),
            ("organization.awaiting", len(waiting), "number"),
            ("organization.longest_wait_days", int(longest[2]), "number"),
            ("organization.people", ", ".join(name for _n, name, _d in waiting[:8]), "string"),
        ]
        # CC-37 AT THE CARD SEAM. `organization.relationship` is written ONLY when every member
        # carries a role and the roles agree. A firm that is a supplier in one process and a
        # customer in another shares an identity and shares nothing else — obligation direction,
        # money direction and confidentiality all differ — and one label over both would be the
        # exact flattening the case names. Where the graph holds nothing (every group on the
        # pilot, which carries one role fact in total) the field stays absent and lands in
        # `missing`: "we do not know what they are to us" is not "they are one thing to us".
        missing: list[str] = []
        if group.relationship_is_uniform is True:
            facts.append(("organization.relationship", group.roles[0], "enum"))
        else:
            missing.append("organization.relationship")
        if group.is_multi_role:
            facts.append(("organization.roles", ", ".join(group.roles), "string"))
        findings.append(_Finding(
            anchor=ANCHOR_ORGANIZATION,
            canonical_key=f"organization:{group.company_node_id}",
            display_name=f"{group.company} — nobody has answered",
            facts=facts,
            # The person waiting longest, so the card has a real subject to hang evidence and an
            # owner on. A REPRESENTATIVE, not the finding's scope — `organization.awaiting` says
            # how many this is really about.
            concerns_node=longest[0],
            correlation_id=f"organization:{group.company_node_id}",
            missing=missing,
            inputs={"reading": ANCHOR_ORGANIZATION,
                    "organization": group.company,
                    "derived_from": "works_at membership over per-counterparty waiting state"},
        ))
    return findings


def read_conditions_for_dispatch(rows: dict, now: datetime, employers: dict) -> list[_Finding]:
    """The dormant-condition reading, in the shape the dispatch loop hands every reader.

    `_gather` stamps the review queue onto `rows` under `_conditions` — one entry, not one per
    node — because these rows are keyed by SUBJECT NODE in their own store and do not belong in
    the `thread.*` map the other three readings share. Unpacking here keeps the dispatch a plain
    lookup rather than a per-reader signature check.
    """
    from genios_engine.context.condition_situations import read_conditions_in_review

    queue = rows.get("_conditions") or {}
    owner = rows.get("_mailbox_owner")
    return read_conditions_in_review(queue, now, owner)


#: The dormant-condition review queue, read from its own store rather than from `_gather`'s
#: `thread.*` rows — see `_gather`, which stamps it on. Wired here so it travels the same
#: `find_or_create_node` / `_write_fact` / `concerns`-edge path every other state reading takes,
#: instead of a second persistence route that would drift from this one.
READINGS = (
    (ANCHOR_OUTREACH, read_awaiting_response),
    (ANCHOR_COMMITMENT, read_overdue_commitments),
    (ANCHOR_COHORT, read_outreach_cohorts),
    (ANCHOR_CONDITION, read_conditions_for_dispatch),
    (ANCHOR_ORGANIZATION, read_organization_silence),
    (ANCHOR_CAMPAIGN, read_campaign_silence),
)


def state_domains() -> tuple[str, ...]:
    """Every domain that declares one of these anchors — asked of the registry, never listed here.
    Naming a domain in Layer 2 would mean adding a domain requires editing Layer 2, and the
    registry exists precisely so it does not."""
    out: set[str] = set()
    for anchor, _ in READINGS:
        out.update(domains_declaring(anchor))
    return tuple(sorted(out))


#: WHO WE ARE, AS AN ADDRESS. The `mailbox` node's canonical key is
#: `mailbox:<org>:<connection>` — an internal identifier, not an email — so reading it gave
#: `condition.actor_is_us` a string that could never match a human name and the flag was silently
#: always false. The owner is instead the address that SENT our outbound mail, which is a fact the
#: events already carry.
#:
#: A TENANT WITH TWO SENDING SEATS GETS `None`, deliberately. `_is_owner` then declines the claim
#: rather than guessing which seat is "us", and the condition still surfaces — see
#: `condition_situations._is_owner`, where absent beats wrong.
_MAILBOX_OWNER = (
    "select distinct lower(e.actor #>> '{email}') as email "
    "from graph_facts f "
    "join graph_source_refs r "
    "  on r.fact_version_id = f.fact_version_id and r.org_id = f.org_id "
    "join source_events e on e.event_id = r.event_id and e.org_id = r.org_id "
    "where f.org_id = :o and f.field = 'thread.last_outbound' and f.status = 'active' "
    "  and e.actor #>> '{email}' is not null"
)


def _mailbox_owner(c, org_id: str) -> str | None:
    """The address our outbound mail is sent from, or `None` when it is not one address.

    `None` covers both "no outbound observed" and "several sending seats", and both are the same
    honest answer to `condition.actor_is_us`: this pass cannot say.
    """
    try:
        rows = c.execute(text(_MAILBOX_OWNER), {"o": org_id}).all()
    except Exception:      # noqa: BLE001 — a driver without the jsonb operator is a gap, not a crash
        return None
    seats = {str(r[0]).strip() for r in rows if r[0]}
    return next(iter(seats)) if len(seats) == 1 else None


def _gather(store, org_id: str, *, now: datetime | None = None,
            campaign_window_days: int = CAMPAIGN_WINDOW_DAYS) -> tuple[dict, dict, dict]:
    """Everything the readings share, read once. `now` is THE SWEEP CLOCK, not the wall clock.

    It has a default only because two tests call this directly; every production caller passes
    `refresh_state_situations`' `now`, which `runner.py` reads once at the process boundary. The
    campaign window used `datetime.now(timezone.utc)` here and that broke the replay contract
    `runner.py:477` establishes — a replay at a past `eval_time` would have looked back ninety
    days from TODAY and found campaigns the sweep it is replaying could not have seen.
    """
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
        # Stamped onto the held row rather than passed as a fourth mapping, so the readers keep
        # the signature the dispatch loop depends on and stay pure functions over their facts.
        # Stamped, not filtered, for the same reason the owner is: the readers stay pure
        # functions over their facts and the dispatch loop keeps one signature.
        for row in c.execute(text(_THREAD_COVERED_BY_PARTY), {"o": org_id}):
            entry = held.get(str(row.thread))
            if entry is not None:
                entry["_covered_by_party"] = str(row.party_name or "") or str(row.party)
        # The review queue and the mailbox owner, under reserved keys rather than node ids: the
        # readings iterate `rows` by node, and a leading underscore cannot collide with one.
        from genios_engine.context.condition_situations import gather_conditions_in_review
        held["_conditions"] = gather_conditions_in_review(c, org_id)
        held["_mailbox_owner"] = _mailbox_owner(c, org_id)
        # The counterparty organisations, under the same reserved-key route. Computed over the
        # WHOLE tenant rather than over `held`: `works_at` membership is what makes two people one
        # firm, and a firm's size — "two of the two partners we know are silent" — is only true if
        # the denominator counts everyone there, not only the ones who happen to be waiting.
        from genios_engine.context.correlation_organization import find_organizations
        held["_organizations"] = find_organizations(c, org_id)
        # The campaigns, same route. `find_campaigns` requires an explicit window and has no
        # default: an unbounded read over a founder's whole mailbox is the query that makes a
        # sweep unpredictable.
        from genios_engine.context.correlation_conversation import find_campaigns
        held["_campaigns"] = find_campaigns(
            c, org_id, since=(now or datetime.now(timezone.utc))
            - timedelta(days=CAMPAIGN_WINDOW_DAYS))
        for row in c.execute(text(_COMMITMENT_OWNERS), {"o": org_id}):
            entry = held.get(str(row.commitment))
            if entry is None:
                continue
            entry["_owner_node"] = str(row.owner_node)
            entry["_owner_name"] = str(row.owner_name or "") or None
            entry["_owner_key"] = str(row.owner_key or "") or None
    return held, counts, employers


def refresh_state_situations(store, org_id: str, *, now: datetime | None = None,
                             campaign_window_days: int = CAMPAIGN_WINDOW_DAYS) -> int:
    """Open, refresh or close the state readings for this org. Returns rows written.

    Idempotent for the same reasons the support readings are: every fact overwrites its own
    deterministic version id and every situation conflicts on `(org_id, correlation_id)`, so six
    sweeps a day produce one row per finding rather than six.
    """
    now = now or datetime.now(timezone.utc)
    if not state_domains():
        return 0
    held, counts, employers = _gather(store, org_id, now=now,
                                      campaign_window_days=campaign_window_days)
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
