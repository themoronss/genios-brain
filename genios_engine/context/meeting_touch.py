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

from sqlalchemy import text

from genios_engine.context.domain_spec import domains_declaring, spec_for
from genios_engine.context.situations import SCORE_MAX
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
    "  on e.org_id = n.org_id and e.edge_type = 'attended' "
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


def refresh_channel_touch_situations(store, org_id: str, *,
                                     now: datetime | None = None) -> int:
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

    with store.engine.begin() as c:
        rows = c.execute(text(_MEETINGS), {"o": org_id}).fetchall()
        for r in rows:
            # A cancelled meeting is a real fact about the relationship and NOT a touch: nobody
            # met. It is left out rather than recorded at low confidence, because a card advising
            # follow-up on a demo that never happened is worse than no card at all.
            if str(r.status or "").strip().lower() == "cancelled":
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
                    "values (:sid, :o, :c, :n, :st, :d, 'active', :conf, :conf, :conf, :conf, "
                    "  :ident, :cov, cast(:missing as jsonb), cast(:inputs as jsonb), :now, :now, :now) "
                    "on conflict (org_id, correlation_id) do update set "
                    "  confidence_overall = excluded.confidence_overall, "
                    "  confidence_freshness = excluded.confidence_freshness, "
                    "  coverage = excluded.coverage, inputs = excluded.inputs, "
                    "  missing = excluded.missing, last_seen_at = excluded.last_seen_at, "
                    "  situation_type = excluded.situation_type, computed_at = excluded.computed_at"),
                {"sid": held or new_id("sit"), "o": org_id, "c": corr_id, "n": r.node_id,
                 "st": stype, "d": domain, "now": now,
                 "conf": CONFIDENCE_PCT, "ident": SCORE_MAX, "cov": COVERAGE_CAP_PCT,
                 "missing": json.dumps(MISSING), "inputs": json.dumps(inputs)})
                written += 1
    return written
