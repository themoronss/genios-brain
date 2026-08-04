"""general pack v1.0.0 — DATA, not code. Relationship-hygiene rules that apply to ANY contact,
sales-linked or not: an overdue promise, an unanswered message, a contact gone quiet, a meeting
with no follow-up. These four rules used to live inside sales_v1 — every card they produced got
mislabeled "sales" regardless of who the contact actually was. Moved here so the engine (and the
extension) can tell a genuine deal-risk signal apart from plain relationship upkeep. Same rule
engine, same scoring math, zero engine change (see packs/wiring.py: "Adding a pack = import it +
register it here")."""

GENERAL_V1 = {
    "id": "general",
    "version": "1.0.0",
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
        "impact": {"i_floor": 40, "i_floor_scope": "deal_linked", "p90_default": 50000},
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
        "_version": "cards.v1",
        "commitment_overdue": {
            "artifact_kind": "draft_delivery",
            "render_hint": ("Headline: the promised thing is overdue, name it. Situation: what was "
                            "promised, to whom, how overdue. Artifact: a short note delivering or "
                            "rescheduling the commitment."),
            "fallback": {"headline": "Overdue: {action}",
                         "situation": "Promised to {entity} · {days}d overdue"}},
        "unanswered_email": {
            "artifact_kind": "draft_reply",
            "render_hint": ("Headline: name the thread and that a reply is owed. Situation: who is "
                            "waiting and since when. Artifact: a concise reply moving it forward."),
            "fallback": {"headline": "Reply owed: {entity}",
                         "situation": "Waiting on us · {days}d since their last message"}},
        "champion_quiet": {
            "artifact_kind": "draft_reengage",
            "render_hint": ("Headline: the contact has gone quiet vs their own cadence. Situation: "
                            "who, how long vs normal. Artifact: a light-touch check-in."),
            "fallback": {"headline": "{entity} quieter than usual",
                         "situation": "No word in {days}d · past their normal cadence"}},
        "meeting_no_followup": {
            "artifact_kind": "draft_recap",
            "render_hint": ("Headline: a meeting has no follow-up yet. Situation: which meeting, "
                            "how long since. Artifact: a crisp recap + next step."),
            "fallback": {"headline": "No recap sent: {entity}",
                         "situation": "Met {days}d ago · no follow-up on record"}},
    },

    "schema": {
        "fields": ["commitment.due_at", "commitment.action", "thread.last_inbound",
                   "thread.ball_in_court", "meeting.status", "meeting.start_at"],
        "signal_vocab": ["commitment_overdue", "unanswered_email", "champion_quiet",
                         "meeting_no_followup"],
    },
    "capture": {"classifier_hints": "general: any relationship — overdue promises, unanswered "
                                    "messages, quiet contacts, meetings without follow-up"},
}
