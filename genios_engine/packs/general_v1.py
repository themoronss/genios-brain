"""general pack v1.0.0 — DATA, not code. Relationship-hygiene rules that apply to ANY contact,
sales-linked or not: an overdue promise, an unanswered message, a contact gone quiet, a meeting
with no follow-up. These four rules used to live inside sales_v1 — every card they produced got
mislabeled "sales" regardless of who the contact actually was. Moved here so the engine (and the
extension) can tell a genuine deal-risk signal apart from plain relationship upkeep. Same rule
engine, same scoring math, zero engine change (see packs/wiring.py: "Adding a pack = import it +
register it here")."""

GENERAL_V1 = {
    "id": "general",
    "version": "1.4.0",              # 1.4.0: push bands calibrated to live scores (see sales
                                    #   1.11.0 — kept in lockstep, shared org-wide budget)              # 1.3.1: 1.3.0 was published with an over-damped urgency
                                    #   half-life (h=24 against meeting.end_at) that made the
                                    #   rule unfireable — peak S=23 against s_min 42. Published
                                    #   bytes are immutable, so the correction is a version, not
                                    #   an edit; 1.3.0 has no tenant and no signal.
                                    # 1.3.0: meeting_no_followup reads meeting.open_loop, not
                                    #   meeting.status — 'confirmed' is an INVITATION state, so
                                    #   the rule fired on cohort workshops and proposed recapping
                                    #   a twenty-person room to itself              # 1.2.0: commitment_overdue moves to scope=commitment — the
                                    #   person mirror collided on (subject, field) so one node
                                    #   held one promise, and "us"-actor commitments landed on the
                                    #   self-excluded owner node and were never reachable at all
                                    # 1.1.1: intro_followup rule (content changed vs published 1.1.0)
    "requires": {"engine": ">=0.1.0"},

    "scoring_defaults": {
        "weights": {"u": 45, "i": 35, "r": 20},
        "c_weights": {"conf": 50, "fresh": 30, "corr": 20},
        "corroboration": {"one": 60, "two": 85, "three_plus": 100, "rank3_full": True},
        "gate": {"s_min": 42, "c_min": 50},                  # lowered with sales_v1 so real founder-inbox
        #   loops (overdue commitments, unanswered emails, meeting follow-ups that matter) surface
        #   instead of being cut with the low-value noise; kept in lockstep with sales_v1.
        # same value as sales — the daily signal budget is shared org-wide (runner._budget_used
        # counts every signal regardless of pack), so matching numbers keeps the cap combined,
        # not doubled.
        "budget_per_user_day": 15,
        # matched to sales_v1 deliberately — one org's cards are ranked against each
        # other in a shared 7/day budget, so a different floor here would silently make
        # general-pack cards lose (or win) every tie on scale alone. See sales_v1 for
        # why unknown deal value floors at 55.
        "impact": {"i_floor": 55, "i_floor_scope": "deal_linked", "p90_default": 50000},
        "r_half_life": {"countdown_h": 24, "elapsed_h": 72},
        # Calibrated to the LIVE score distribution (open signals: min 42, median 45.5, max 56),
        # not to aspiration. The old {high: 70, critical: 85} sat ABOVE the maximum reachable
        # score, so `high` was arithmetically unreachable, no card ever cleared the push band,
        # and the entire delivery layer ran with an empty input for months while reading as
        # healthy. 52/60 makes push a real, rare event (top quartile / exceptional) — bounded by
        # the 7/day budget, quiet hours and the interrupt-confidence floor, so miscalibration
        # costs a notification, not a 2am page. Revisit when the L4 formula takes scoring
        # authority from the override and the distribution widens.
        "bands": {"high": 52, "critical": 60},
    },


    "rules": [
        # Scoped to the COMMITMENT, not to the person who made it.
        #
        # `graph_facts` keys on (subject, field), so a person-scoped rule reading
        # `commitment.due_at` off the person node could only ever see ONE promise — the newest
        # write silently superseded every earlier one. 24 commitment nodes existed and the person
        # mirror held a fraction of them.
        #
        # Worse for the promises that matter most: an actor of "us" resolves to the account
        # owner's own node, and Layer 4 self-excludes that node by design. The founder's own
        # commitments were captured, stored, and then structurally unreachable — the one class of
        # promise a chief-of-staff product exists to track.
        #
        # The commitment node already carries due_at/text/status and an `owns` edge from its
        # actor, so this reads the same facts from where they do not collide.
        {"id": "commitment_overdue", "level": "prescriptive", "scope": "commitment",
         "when": [{"fn": "days_since", "path": "commitment.due_at", "op": ">", "value": 0}],
         "urgency": {"type": "elapsed", "path": "commitment.due_at", "h": 1},
         "reason_code": "commitment_overdue", "play": "deliver_commitment", "cooldown_hours": 48,
         "linked_deal": True, "evidence_fields": ["commitment.due_at", "commitment.action"]},

        {"id": "unanswered_email", "level": "prescriptive", "scope": "person",
         "when": [{"path": "thread.ball_in_court", "op": "=", "value": "us"},
                  {"fn": "days_since", "path": "thread.last_inbound", "op": ">=", "value": 2}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 2},
         "reason_code": "unanswered_email", "play": "reply", "cooldown_hours": 72,
         "linked_deal": True, "evidence_fields": ["thread.ball_in_court", "thread.last_inbound"]},

        {"id": "champion_quiet", "level": "predictive", "scope": "person",
         "when": [{"path": "thread.ball_in_court", "op": "=", "value": "them"},
                  {"fn": "days_since", "path": "thread.last_inbound", "op": ">=",
                   "value": {"baseline": "reply_cadence", "mult": 2.5, "floor": 10}}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 5},
         "reason_code": "champion_quiet", "play": "re_engage", "cooldown_hours": 72,
         "linked_deal": True, "evidence_fields": ["thread.last_inbound"]},

        {"id": "meeting_no_followup", "level": "prescriptive", "scope": "meeting",
         # Reads `meeting.open_loop`, NOT `meeting.status`.
         #
         # `meeting.status='confirmed'` is an INVITATION state — Google sets it the moment an
         # event exists and it survives the meeting happening, so this rule was asking "did this
         # meeting end with somebody waiting on me" and being told "the event was not cancelled".
         # It fired on three cohort workshops the founder attended as one participant among
         # twenty, telling him to send a recap to the whole cohort — which is not just useless,
         # it discloses the attendee list to the attendees.
         #
         # `open_loop` is true only when the meeting actually OCCURRED, had an EXTERNAL
         # COUNTERPARTY (not a broadcast), and no follow-up was sent. Five questions, five
         # fields, and no rule may alias them again (context/meeting_lifecycle.py).
         "when": [{"path": "meeting.open_loop", "op": "=", "value": True},
                  {"fn": "hours_since", "path": "meeting.end_at", "op": ">=", "value": 24}],
         # h stays 1, as it was against `start_at`: the clock moved from the meeting's start to
         # its end, which is a correction of WHICH moment, not of how fast follow-up decays.
         "urgency": {"type": "elapsed", "path": "meeting.end_at", "h": 1},
         "reason_code": "meeting_no_followup", "play": "send_recap", "cooldown_hours": 72,
         "linked_deal": False,
         "evidence_fields": ["meeting.open_loop", "meeting.end_at",
                             "meeting.external_counterparty"]},

        # intro follow-up (v1.1.0) — someone made an introduction and no follow-up has gone out. A
        # warm intro is the cheapest pipeline there is and the easiest to waste by going silent.
        {"id": "intro_followup", "level": "prescriptive", "scope": "person",
         "when": [{"has_obs": "introduction"},
                  {"no_obs": "followup_sent"},
                  {"fn": "days_since", "path": "thread.last_inbound", "op": ">=", "value": 1}],
         "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 2},
         "reason_code": "intro_followup", "play": "reply", "cooldown_hours": 72,
         "linked_deal": False, "evidence_fields": ["thread.last_inbound"]},
    ],

    "plays": {
        "deliver_commitment": {"artifact": "draft_delivery", "success_signal": "commitment_met",
                               "window_days": 3},
        "reply":              {"artifact": "draft_reply",    "success_signal": "outbound_sent",
                               "window_days": 2},
        "re_engage":          {"artifact": "draft_reengage", "success_signal": "inbound_received",
                               "window_days": 14},
        "send_recap":         {"artifact": "draft_recap",    "success_signal": "followup_sent",
                               "window_days": 2},
    },

    "templates": {
        # manager mode — headline is a direct order (verb first, name who), never a passive fact.
        "_version": "cards.v2",
        "commitment_overdue": {
            "artifact_kind": "draft_delivery",
            "render_hint": ("Headline: a direct order to deliver the specific overdue thing NOW, "
                            "naming who it's owed to — imperative voice, not a status line. "
                            "Situation: what was promised, how overdue. Artifact: a short note "
                            "delivering or rescheduling the commitment."),
            "fallback": {"headline": "Deliver {action} to {entity} today",
                         "situation": "{days}d overdue — you promised this"}},
        "unanswered_email": {
            "artifact_kind": "draft_reply",
            "render_hint": ("Headline: a direct order to reply to this person now — imperative "
                            "voice ('Reply to X now'), not a status line. Situation: how long they've "
                            "been waiting. Artifact: a concise reply moving it forward."),
            "fallback": {"headline": "Reply to {entity} now",
                         "situation": "{days}d since they wrote — still waiting on you"}},
        "champion_quiet": {
            "artifact_kind": "draft_reengage",
            "render_hint": ("Headline: a direct order to check in with this contact today — "
                            "imperative voice, not a status line. Situation: how long since their "
                            "normal cadence. Artifact: a light-touch check-in."),
            "fallback": {"headline": "Check in with {entity} today",
                         "situation": "Quiet {days}d — past their usual pace"}},
        "meeting_no_followup": {
            "artifact_kind": "draft_recap",
            "render_hint": ("Headline: a direct order to send the recap now, naming who. Situation: "
                            "how long since the meeting. Artifact: a crisp recap + next step."),
            "fallback": {"headline": "Send {entity} a recap now",
                         "situation": "Met {days}d ago — nothing sent since"}},
        "intro_followup": {
            "artifact_kind": "draft_reply",
            "render_hint": ("Headline: a direct order to follow up on the introduction to {entity} "
                            "now, naming them. Situation: you were introduced, nothing's gone back "
                            "yet. Artifact: a warm, concrete note that thanks the connector, opens "
                            "the conversation, and proposes one clear next step."),
            "fallback": {"headline": "Follow up on the {entity} intro now",
                         "situation": "Introduced {days}d ago — no reply sent yet"}},
    },

    "schema": {
        "fields": ["commitment.due_at", "commitment.action", "thread.last_inbound",
                   "thread.ball_in_court", "meeting.status", "meeting.start_at",
                   # The five fields `meeting.status` was aliasing. `status` stays declared —
                   # it is still a real captured fact, it simply may no longer stand in for
                   # "did this happen", "was I there" or "is anyone waiting on me".
                   "meeting.end_at", "meeting.scheduled", "meeting.occurred",
                   "meeting.attended", "meeting.external_counterparty", "meeting.open_loop"],
        "signal_vocab": ["commitment_overdue", "unanswered_email", "champion_quiet",
                         "meeting_no_followup", "intro_followup"],
    },
    "capture": {"classifier_hints": "general: any relationship — overdue promises, unanswered "
                                    "messages, quiet contacts, meetings without follow-up"},
}


# ── Actionability: what each card's ACTION needs, distinct from what its RULE matched on ──
#
# An undeclared reason code fails CLOSED (see reason/actionability.py). This block is the only
# place that keeps a new rule from silently shipping a confident imperative it cannot ground:
# adding a rule below without adding an entry here is a named test failure, not a surprise in
# production three weeks later.
GENERAL_V1_ACTIONABILITY = {

    "commitment_overdue": {
        "facts": ['commitment.action'],
        "label": 'the promised outcome',
        "message": 'We found a due date, but not what was actually promised.',
        "recommended": 'Open the source thread to verify what you committed to before acting.'},
    "unanswered_email": {
        "obs": ['question', 'meeting_request', 'proposal_sent', 'demo_requested', 'contract_requested', 'objection', 'next_step_agreed'],
        "label": 'what response they need',
        "message": 'We verified they wrote and the ball is on you — but not what response they need.',
        "recommended": "Open the email to see what they're actually asking before replying."},
    "champion_quiet": {
        "facts": ['thread.last_inbound'],
        "obs": ['next_step_agreed', 'question'],
        "label": 'what your last exchange was about',
        "message": "They've gone quiet, but we don't have the thread it went quiet on.",
        "recommended": 'Review your last exchange before reaching out.'},
    "meeting_no_followup": {
        "facts": ['meeting.description'],
        "obs": ['next_step_agreed'],
        "label": 'what to recap',
        "message": "A meeting ended with no follow-up, but we don't have its agenda on record.",
        "recommended": 'Open the calendar event to see what was discussed before sending a recap.'},
    "intro_followup": {
        "facts": ['thread.last_inbound'],
        "obs": ['intro_made', 'question', 'meeting_request'],
        "label": 'who was introduced and why',
        "message": 'An introduction happened without the context of what it was for.',
        "recommended": 'Read the intro thread before following up.'},
}
