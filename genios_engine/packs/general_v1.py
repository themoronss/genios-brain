"""general pack v1.0.0 — DATA, not code. Relationship-hygiene rules that apply to ANY contact,
sales-linked or not: an overdue promise, an unanswered message, a contact gone quiet, a meeting
with no follow-up. These four rules used to live inside sales_v1 — every card they produced got
mislabeled "sales" regardless of who the contact actually was. Moved here so the engine (and the
extension) can tell a genuine deal-risk signal apart from plain relationship upkeep. Same rule
engine, same scoring math, zero engine change (see packs/wiring.py: "Adding a pack = import it +
register it here")."""

GENERAL_V1 = {
    "id": "general",
    "version": "1.1.0",              # 1.1.0 +intro_followup
    "requires": {"engine": ">=0.1.0"},

    "scoring_defaults": {
        "weights": {"u": 45, "i": 35, "r": 20},
        "c_weights": {"conf": 50, "fresh": 30, "corr": 20},
        "corroboration": {"one": 60, "two": 85, "three_plus": 100, "rank3_full": True},
        "gate": {"s_min": 55, "c_min": 60},
        # same value as sales — the daily signal budget is shared org-wide (runner._budget_used
        # counts every signal regardless of pack), so matching numbers keeps the cap at 7/day
        # combined, not 7+7.
        "budget_per_user_day": 7,
        # matched to sales_v1 deliberately — one org's cards are ranked against each
        # other in a shared 7/day budget, so a different floor here would silently make
        # general-pack cards lose (or win) every tie on scale alone. See sales_v1 for
        # why unknown deal value floors at 55.
        "impact": {"i_floor": 55, "i_floor_scope": "deal_linked", "p90_default": 50000},
        "r_half_life": {"countdown_h": 24, "elapsed_h": 72},
        "bands": {"high": 70, "critical": 85},
    },

    "rules": [
        {"id": "commitment_overdue", "level": "prescriptive", "scope": "person",
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
         "when": [{"path": "meeting.status", "op": "=", "value": "confirmed"},
                  {"fn": "hours_since", "path": "meeting.start_at", "op": ">=", "value": 24},
                  {"no_obs": "followup_sent"}],
         "urgency": {"type": "elapsed", "path": "meeting.start_at", "h": 1},
         "reason_code": "meeting_no_followup", "play": "send_recap", "cooldown_hours": 72,
         "linked_deal": False, "evidence_fields": ["meeting.status", "meeting.start_at"]},

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
                   "thread.ball_in_court", "meeting.status", "meeting.start_at"],
        "signal_vocab": ["commitment_overdue", "unanswered_email", "champion_quiet",
                         "meeting_no_followup", "intro_followup"],
    },
    "capture": {"classifier_hints": "general: any relationship — overdue promises, unanswered "
                                    "messages, quiet contacts, meetings without follow-up"},
}
