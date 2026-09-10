"""`channel_touch` — the interactions that happened somewhere other than the inbox.

`touch-outside-mail.yaml` asks for "an interaction on a non-mail channel, carrying the channel,
the direction, the participants, the outcome", and argues at length that binding it to
`relationship` would be wrong because that "would infer a call from the absence of mail, which is
not evidence of anything". That argument is correct and this module does not weaken it.

What it does instead is notice that one non-mail channel is already CAPTURED rather than inferred.
The calendar connector writes `meeting` nodes — 62 of them on the design partner's org, 48 of them
carrying `meeting.external_counterparty`. A meeting with an outside party is not a guess from
silence; it is a recorded event with a time, a title and participants. The corpus's objection is
to inventing a touch, not to reading one.

SO THIS SERVES ONE OF THE THREE CAPABILITIES BEHIND THE TYPE, AND SAYS SO. `demo` is a meeting and
is now reachable. `cold_calling` and `linkedin_outreach` are NOT: a dialled number and a LinkedIn
message appear in no calendar, and nothing here should let a card about "your calls this week"
render off a graph that has never seen one. The situation carries that in `missing` on every row,
so a capability reading it can tell how much of its channel it is actually looking at.

WHAT IS DELIBERATELY NOT CLAIMED. The corpus asks for the OUTCOME — "a dialled number and a
conversation are the same event to a log and completely different events to a seller" — and a
calendar knows scheduling, not what happened. `meeting.status` distinguishes an event that stands
from one that was cancelled, and that is the whole of what is honest here; whether the demo landed
is not in the graph and is listed as missing rather than guessed from the invite.

The anchor is the `meeting` node itself and `meeting` stays OUT of `ANCHOR_PRIORITY`, for exactly
the reason the tenant node does: `choose_anchors` returns only the strongest tier present, so a
meeting reachable from correspondence would swallow the conversation it belongs to and the
situation about the person would disappear into a situation about one calendar entry.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import bindparam, text

from genios_engine.context.domain_spec import domains_declaring, spec_for
from genios_engine.context.situations import SCORE_MAX, freshness_score
from genios_engine.platform.ids import new_id

#: The anchor this module mints. WHICH DOMAIN CLAIMS IT IS NOT NAMED HERE — it is asked of the
#: registry, because a domain named in Layer 2 means adding a domain requires editing Layer 2, and
#: `test_domain_names_appear_in_exactly_one_file_in_the_context_layer` rejects it. Declaring
#: `"meeting": "channel_touch"` in a spec is the whole opt-in, exactly as `tenant` is for the
#: period sweep.
ANCHOR = "meeting"

#: Identity is certain — the subject is one calendar event with its own id, and there is no merge
#: question about it. Coverage is not: a calendar sees that a meeting was held and never what came
#: of it, which is most of what the corpus asks for.
CONFIDENCE_PCT = 70
COVERAGE_CAP_PCT = 35

#: How far back a meeting may be and still be a live follow-through situation.
#:
#: There was no window at all. Every external meeting the calendar has ever held minted an
#: `active` situation — one from three years ago included — and `domain_shadow` served every one
#: of them to Layer 3 forever.
#:
#: A DEFAULT, NOT A LAW, and `refresh_channel_touch_situations` takes it as an argument. Ninety
#: days suits a founder's calendar; an enterprise whose sales cycle runs two quarters would lose
#: every meeting that still matters. When a per-tenant source is needed,
#: `capture/esqe/qualification.org_qualification_floors` is the proven shape — a table, a
#: documented default, an owner, and an append-only change log.
FOLLOW_THROUGH_DAYS = 90

#: Stated on every row so a capability can see the shape of its own blindness rather than reading
#: a partial view as a whole one. These are the corpus's asks that a calendar cannot answer.
MISSING = [
    "the outcome — whether it connected and what was shown",
    "calls and dialler activity (no telephony source connected)",
    "LinkedIn and other social touches (no source connected)",
    "what was demonstrated, as opposed to what was scheduled",
]

_MEETINGS = (
    "select n.node_id, n.display_name, "
    "  max(case when f.field = 'meeting.start_at' then f.value #>> '{}' end) as start_at, "
    "  max(case when f.field = 'meeting.status' then f.value #>> '{}' end) as status, "
    "  array_agg(distinct att.display_name) as counterparties "
    "from graph_nodes n "
    "left join graph_facts f "
    "  on f.org_id = n.org_id and f.subject_node_id = n.node_id and f.status = 'active' "
    # WHO WAS THERE IS NOT RECORDED ON THE MEETING. `meeting.external_counterparty` is written on
    # the PERSON — 48 of them here, and zero on any meeting node. The first version asked the
    # meeting for its own counterparty and matched NOTHING: 62 meetings, 331 facts, every one
    # filtered out by a `having` on a fact that is never there. The link is the `attended` edge.
    "join graph_edges e "
    # `valid_to is null` — AN ATTENDANCE THAT WAS CLOSED IS NOT AN ATTENDANCE. `merge.py`
    # dedupes and closes edges during an identity merge, and without this filter a closed edge
    # kept contributing a counterparty to the channel-touch situation forever: the meeting
    # reported an attendee the graph had already retired, and the situation's own counterparty
    # list said so on the card. Every other edge read in this layer carries the same predicate.
    "  on e.org_id = n.org_id and e.edge_type = 'attended' and e.valid_to is null "
    "  and (e.from_node_id = n.node_id or e.to_node_id = n.node_id) "
    "join graph_nodes att "
    "  on att.org_id = n.org_id and att.valid_to is null "
    "  and att.node_id = case when e.from_node_id = n.node_id "
    "                         then e.to_node_id else e.from_node_id end "
    # EVERY external attendee, not one of them. The first fix aggregated with `max()`, which picks
    # the alphabetically-last name among the people who were there — so four unrelated meetings,
    # including one titled "Intro: Hirdesh & Rohit", all reported the same counterparty. A single
    # name is a claim about who the meeting was with; picking it by sort order is a wrong one.
    "join graph_facts xf "
    "  on xf.org_id = n.org_id and xf.subject_node_id = att.node_id "
    "  and xf.field = 'meeting.external_counterparty' and xf.status = 'active' "
    "where n.org_id = :o and n.node_type = 'meeting' and n.valid_to is null "
    # US IS NOT A COUNTERPARTY. `meeting.external_counterparty` is written on the owner's own
    # person node too, so every meeting listed the founder as someone it reached — and one
    # meeting listed ONLY him, which is an internal calendar entry reported as an outside touch.
    # The internal set is derived the way `runner._internal_emails` derives it: seats, the account
    # owner, and the connected mailbox. A meeting left with nobody external is not a touch and
    # falls out through the `having`.
    "  and lower(coalesce(att.canonical_key, '')) not in ( "
    "     select lower(email) from org_seats where org_id = :o and active and email is not null "
    "     union select lower(email) from orgs where id = :o and email is not null "
    "     union select lower(external_account_id) from connections "
    "       where org_id = :o and external_account_id like '%@%' ) "
    "group by n.node_id, n.display_name "
    "having count(distinct att.node_id) > 0"
)


def _as_utc(value) -> datetime | None:
    """The meeting's start, tz-aware. A driver may hand back a string; Postgres does not."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _freshness(start_at: datetime | None, now: datetime) -> int:
    """The row's real currency, from the MEETING's instant.

    `freshness_score` returns `known=False` for an undated meeting, and an undated meeting is not
    a stale one — it is one we cannot date. `CONFIDENCE_PCT` is the honest fallback there: the
    same number the other axes carry, which says "as sure as anything else on this row" rather
    than manufacturing either currency or staleness.
    """
    score, known = freshness_score(last_seen_at=start_at, now=now)
    return score if known else CONFIDENCE_PCT


def refresh_channel_touch_situations(store, org_id: str, *,
                                     now: datetime | None = None,
                                     follow_through_days: int = FOLLOW_THROUGH_DAYS) -> int:
    """Open or refresh one `channel_touch` situation per external meeting. Returns rows written.

    Idempotent: the correlation id is derived from the meeting node, so a sweep that runs six
    times in a week produces one situation per meeting rather than six. Same conflict target the
    period sweep uses, for the same reason.
    """
    now = now or datetime.now(timezone.utc)
    domains = domains_declaring(ANCHOR)
    if not domains:
        return 0                    # no domain opted in — nothing to mint, and nothing to guess
    written = 0
    live: dict[str, set[str]] = {}

    with store.engine.begin() as c:
        rows = c.execute(text(_MEETINGS), {"o": org_id}).fetchall()
        for r in rows:
            # A cancelled meeting is a real fact about the relationship and NOT a touch: nobody
            # met. It is left out rather than recorded at low confidence, because a card advising
            # follow-up on a demo that never happened is worse than no card at all.
            if str(r.status or "").strip().lower() == "cancelled":
                # NOT `continue` ANY MORE — see `live` below. A meeting later marked cancelled
                # had its situation left standing forever, because the only thing that ever
                # closed one was never reaching this loop.
                continue

            start_at = _as_utc(r.start_at)
            if start_at is not None and (now - start_at).days > follow_through_days:
                # OUTSIDE THE WINDOW. Skipped before minting, and reconciled below if a row for
                # it already exists — a three-year-old demo is not follow-through work.
                continue

            inputs = {
                "channel": "meeting",
                "counterparties": [x for x in (r.counterparties or []) if x],
                "occurred_at": r.start_at,
                # Names the reader's own blind spot in the row, not only in `missing`: this served
                # `demo` and could not have served the other two capabilities on the type.
                "serves": ["sales.discovery_and_solution.demo"],
                "not_served": ["sales.prospecting_and_outreach.cold_calling",
                               "sales.prospecting_and_outreach.linkedin_outreach"],
            }
            for domain in domains:
                stype = spec_for(domain).type_for(ANCHOR)
                # The DOMAIN is in the correlation id, not only the meeting. One calendar event is
                # a different situation to each domain that claims the anchor, and keying on the
                # node alone would make the second domain's upsert overwrite the first's — the
                # same collision the escalation reading hit on (account, date).
                corr_id = f"corr_touch_{domain}_{r.node_id}"
                held = c.execute(text(
                    "select situation_id from context_situations "
                    "where org_id = :o and correlation_id = :c"),
                    {"o": org_id, "c": corr_id}).scalar()
                c.execute(text(
                    "insert into context_situations (situation_id, org_id, correlation_id, "
                    "  anchor_node_id, situation_type, domain, status, confidence_overall, "
                    "  confidence_evidence, confidence_freshness, confidence_consistency, "
                    "  confidence_identity, coverage, missing, inputs, first_seen_at, last_seen_at, "
                    "  computed_at) "
                    "values (:sid, :o, :c, :n, :st, :d, 'active', :conf, :conf, :fresh, :conf, "
                    "  :ident, :cov, cast(:missing as jsonb), cast(:inputs as jsonb), :seen, :seen, :now) "
                    "on conflict (org_id, correlation_id) do update set "
                    "  confidence_overall = excluded.confidence_overall, "
                    "  confidence_freshness = excluded.confidence_freshness, "
                    "  coverage = excluded.coverage, inputs = excluded.inputs, "
                    "  missing = excluded.missing, last_seen_at = excluded.last_seen_at, "
                    "  situation_type = excluded.situation_type, computed_at = excluded.computed_at"),
                {"sid": held or new_id("sit"), "o": org_id, "c": corr_id, "n": r.node_id,
                 "st": stype, "d": domain, "now": now,
                 "conf": CONFIDENCE_PCT,
                 # FRESHNESS IS THE MEETING'S, not a constant. It was hard-coded to
                 # `CONFIDENCE_PCT` — so a row about a meeting eleven weeks ago claimed the same
                 # currency as one about yesterday, and `last_seen_at` below made it worse by
                 # reporting the SWEEP instant as its newest evidence. A situation may not claim
                 # a currency it does not have.
                 "fresh": _freshness(start_at, now),
                 "ident": SCORE_MAX, "cov": COVERAGE_CAP_PCT,
                 # LAST SEEN IS WHEN THE MEETING HAPPENED. Bumping it to `now` every six hours
                 # put a three-year-old meeting at the top of `domain_shadow.py`'s
                 # newest-evidence ordering, ahead of this morning's mail.
                 "seen": start_at or now,
                 "missing": json.dumps(MISSING), "inputs": json.dumps(inputs)})
                written += 1
                live.setdefault(domain, set()).add(corr_id)

        # THE CLOSING HALF, which did not exist. A meeting that fell out of the window or was
        # later cancelled simply stopped being visited, and its situation stayed `active`
        # forever — the same "a finding that stops being produced is not a finding that ended"
        # defect `waiting.py` carried. Resolved by fact, exactly as the state readings do it.
        for domain in domains:
            stype = spec_for(domain).type_for(ANCHOR)
            keep = live.get(domain) or set()
            closed = c.execute(text(
                "update context_situations set status='resolved', resolved_at=:now, "
                "  resolution_note='meeting outside the follow-through window' "
                "where org_id=:o and status='active' and situation_type=:st "
                "  and correlation_id like :prefix and resolved_by is null "
                + ("and correlation_id not in :keep " if keep else "")
                ).bindparams(*([bindparam("keep", expanding=True)] if keep else [])),
                {"o": org_id, "now": now, "st": stype,
                 "prefix": f"corr_touch_{domain}_%",
                 **({"keep": sorted(keep)} if keep else {})})
            written += int(closed.rowcount or 0)
    return written
