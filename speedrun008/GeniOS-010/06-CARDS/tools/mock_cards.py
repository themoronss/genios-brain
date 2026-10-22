"""Stand-in brain for a render check of the Cards page, in the REAL route shapes.

Card bodies follow what `deliver/card_builder.build_draft` stores and `api/routes.get_card` returns:
gold lines, the expert's `why` rows, the request-time `decision` projection, `context`, `actions`.

The cards:
  c-evokoa   a formula-generation card (graph readings, a meeting, a promise, doctrine) — the shape
             most live cards have today
  c-f24      an expert card with gold lines and quoted mail (golden F24), 3 versions
  c-f26      an expert card with a draft (golden F26)
  c-f22      a question card (golden F22) — offers answer, never Done
  c-f15      a held question (golden F15)
  c-f55      a monitor-lane card (golden F55) — drawn as a waiting line
SHARED_MEETINGS / SHARED_PROMISE sit on three cards on purpose: the person-level context the brain
attaches to every card about the same node, which the page must leave out as nobody's reason.

Also: /cards/history, /cards/{id}/timeline, POST /cards/{id}/action (a question refuses Done with
422 not_offered, as deliver/actions.py does), /api/org/org_preview/members, /v1/agents.
Port 8031, CORS for http://localhost:3931.
"""
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ORIGIN = "http://localhost:3931"
now = datetime.now(timezone.utc)
iso = lambda h: (now - timedelta(hours=h)).isoformat()

CARDS = [
    {"card_id": "c-evokoa", "signal_id": "s90", "assignee": None, "domain": "admin", "urgency_band": "high",
     "headline": "Confirm the call time with Evokoa", "subject_node_id": "n90",
     "situation": "Evokoa proposed Thursday 4 pm for the pilot review and is waiting for your confirmation. The calendar has no invite yet.",
     "score": 82, "state": "surfaced", "render_mode": "llm", "created_at": iso(26), "expires_at": iso(-900)},
    {"card_id": "c-f24", "signal_id": "s24", "assignee": None, "domain": "admin", "urgency_band": "high",
     "headline": "Upload the Phase-1 review deck to the cohort folder", "subject_node_id": "n24",
     "situation": "The accelerator's Phase-1 review is on the 28th; the cohort folder has no deck from you yet.",
     "score": 78, "state": "surfaced", "render_mode": "review", "created_at": iso(30), "expires_at": iso(-900)},
    {"card_id": "c-f26", "signal_id": "s26", "assignee": None, "domain": "admin", "urgency_band": "standard",
     "headline": "Reply to Neha to confirm Tuesday 30 Sep at 11 am IST", "subject_node_id": "n26",
     "situation": "Neha proposed a time for the partner call and is waiting for your yes.",
     "score": 55, "state": "surfaced", "render_mode": "review", "created_at": iso(5), "expires_at": iso(-900)},
    {"card_id": "c-f22", "signal_id": "s22", "assignee": None, "domain": "admin", "urgency_band": "standard",
     "headline": "Can you tell us whether you are a startup incubated on the university's campus?",
     "subject_node_id": "n22",
     "situation": "A university startup cell announced a seed grant; whether you qualify turns on one fact.",
     "score": 40, "state": "surfaced", "render_mode": "question", "created_at": iso(20), "expires_at": iso(-900)},
    {"card_id": "c-f55", "signal_id": "s55", "assignee": None, "domain": "admin", "urgency_band": "standard",
     "headline": "Send Dev Malhotra the pricing sheet", "subject_node_id": "n55",
     "situation": "Dev asked for pricing four weeks ago; nothing has gone out since.",
     "score": 35, "state": "surfaced", "render_mode": "review", "created_at": iso(60), "expires_at": iso(-900)},
    {"card_id": "c-f15", "signal_id": "s15", "assignee": None, "domain": "admin", "urgency_band": "standard",
     "headline": "What is the next step with Cobalt Peak? We held the one we found: a fact your move rests on quotes nothing from the mail it cites.",
     "subject_node_id": "n15", "situation": "Your outreach to Cobalt Peak has had no reply in eight weeks.",
     "score": 30, "state": "surfaced", "render_mode": "question", "created_at": iso(80), "expires_at": iso(-900)},
]

SHARED_MEETINGS = [
    {"title": "Weekly founders sync", "start_at": iso(-30), "status": "confirmed", "state": "scheduled", "state_label": "Scheduled", "source": "gcal"},
    {"title": "Investor update call", "start_at": iso(20), "status": "confirmed", "state": "past_scheduled", "state_label": "Past, not confirmed it happened", "source": "gcal"},
    {"title": "Hiring sync", "start_at": iso(44), "status": "confirmed", "state": "past_scheduled", "state_label": "Past, not confirmed it happened", "source": "gcal"},
    {"title": "Board prep", "start_at": iso(70), "status": "confirmed", "state": "past_scheduled", "state_label": "Past, not confirmed it happened", "source": "gcal"},
]
SHARED_PROMISE = {"text": "Share the monthly update with investors", "due_at": iso(-48), "status": "open"}

EXPERT_ACTIONS = [
    {"type": "run_play", "play_id": "expert.file_review", "label": "Draft response", "artifact_ready": True},
    {"type": "do_it_myself"}, {"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]},
    {"type": "wrong", "reasons": ["not_relevant", "wrong_facts", "bad_timing", "misread_source", "stale_data",
                                  "wrong_subject", "bad_link", "wrong_conclusion", "not_how_we_work",
                                  "wrong_person", "wrong_channel"]},
]
QUESTION_ACTIONS = [{"type": "answer"}, {"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]},
                    {"type": "wrong", "reasons": ["not_relevant", "wrong_facts", "bad_timing"]}]

def inference(sentence, text):
    return {"sentence": sentence, "inference": text, "source": "expert_check"}

DETAILS = {
    "c-evokoa": {
        "domain": "admin", "output_lane": "decision", "business_subject": "Ananya Rao", "relationship_role": "Evokoa · pilot customer",
        "do_nothing_consequence": "The pilot review slips a week and Evokoa's renewal decision moves with it.",
        "success_signal": "Ananya accepts a calendar invite for Thursday 4 pm.",
        "outcome_window_days": 2, "context_tags": ["app:gmail"],
        "actions": [{"type": "do_it_myself"}, {"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]},
                    {"type": "wrong", "reasons": ["not_relevant", "wrong_facts", "bad_timing"]}],
        "why": [{"field": "thread.last_inbound", "value": iso(26), "source": "gmail"},
                {"field": "thread.ball_in_court", "value": "us", "source": "gmail"},
                {"field": "commitment.action", "value": "send the invite with the meeting link once the time is fixed", "source": "gmail"},
                {"statement": "A proposed time left unconfirmed for two days is usually lost; confirm or counter within a day.", "source": "expertise"}],
        "context": {"profile": [{"field": "role", "value": "Head of Operations"}, {"field": "company", "value": "Evokoa"}],
                    "signals": [{"kind": "meeting_request", "label": "Meeting proposed", "count": 1}, {"kind": "question", "label": "Open question", "count": 1}],
                    "interactions": [{"title": "Evokoa pilot review", "start_at": iso(-50), "status": "proposed", "state": "scheduled", "state_label": "Proposed, no invite yet", "source": "gcal"}] + SHARED_MEETINGS,
                    "commitments": [{"text": "We will send the invite with the meeting link once the time is fixed", "due_at": iso(-20), "status": "open"}, SHARED_PROMISE],
                    "freshness": {"label": "fresh", "note": ""}},
        "actionability": {"state": "actionable"},
        "decision": {"card_version": "v2", "recommendation": {"verdict": "reply", "objective": "Confirm Thursday 4 pm with Ananya and send the calendar invite with the meeting link",
                     "steps": ["Reply in the thread: Thursday 4 pm works", "Send the calendar invite with the meeting link to Ananya", "Add the pilot numbers she asked for to the invite"], "avoid": "Proposing a new time without saying why"},
                     "confidence": {"evidence": 0.9, "identity": None, "situation": None, "recommendation": 0.8}, "grounding": {}},
    },
    "c-f24": {
        "output_lane": "decision", "lane_label": "Decision", "level": "prescriptive",
        "business_subject": "Divya Raman", "relationship_role": "watched",
        "why_now": "Nothing in 13 days — longer than this file has gone quiet before (11.96 days)",
        "unresolved_item": "Divya Raman asked a question — waiting on you since 1 Sep; Divya Raman asked a question — waiting on you since 13 Sep",
        "recommended": {"who": "you", "what": "Upload the Phase-1 review deck to the cohort folder by the twenty-eighth, and check the folder holds the unit economics sheet — if it does not, upload it and tell Divya.",
                        "for_whom": "the programme", "by_when": "2026-09-28"},
        "alternative": "If the deck cannot be ready by the twenty-eighth, tell Divya before the date and ask what the programme allows.",
        "wait_or_stop": "Nothing to wait for; the moves are ours, and they are done when both are in the folder before the review.",
        "outcome_window_days": 2, "success_signal": "Both files are in the cohort folder before the review.",
        "do_nothing_consequence": "The review goes ahead without your deck.",
        "confidence_vector": {"C": 8000, "I": 5600, "U": 8000}, "capability_key": "expert.file_review",
        "context_tags": ["app:gmail"], "actions": EXPERT_ACTIONS,
        "why": [
            {"sentence": "headline", "evidence": [3, 7], "quotes": ["Please upload your Phase-1 review deck to the cohort folder by 28 Sep.", "Could you also add the unit economics sheet?"], "source": "expert_check"},
            inference("situation", "the expert's reading of the file — an inference, not a quote"),
            inference("done_when", "what done looks like, as the expert judges it — an inference, not a quote"),
            inference("do_nothing", "what doing nothing costs, as the expert judges it — an inference, not a quote"),
            {"window": "two days before the review", "days": 2, "from": "the programme's mail", "source": "card_lines"},
            {"field": "thread.last_inbound", "value": "2026-09-13T10:12:00+00:00", "source": "gmail"},
        ],
        "context": {"profile": [{"field": "role", "value": "Programme manager"}], "signals": [{"kind": "question", "label": "Asked a question", "count": 2}],
                    "interactions": SHARED_MEETINGS, "commitments": [SHARED_PROMISE], "freshness": {"label": "fresh", "note": ""}},
        "actionability": {"state": "actionable"},
        "decision": {"card_version": "v2", "recommendation": {"verdict": "reply", "objective": "Reply to what they actually asked",
                     "steps": ["Answer their open question"], "avoid": None},
                     "confidence": {"evidence": 0.8, "identity": None, "situation": None, "recommendation": 0.56}, "grounding": {}},
    },
    "c-f26": {
        "output_lane": "decision", "lane_label": "Decision", "level": "prescriptive",
        "business_subject": "Neha Kapoor", "relationship_role": "partner",
        "why_now": "She proposed Tuesday 11 am two days ago; the slot is in four days.",
        "unresolved_item": "Neha asked whether Tuesday 30 Sep at 11 am IST works — waiting on you since 24 Sep",
        "recommended": {"who": "you", "what": "Reply to Neha to confirm Tuesday 30 Sep at 11 am IST and send the invite.", "for_whom": "Neha", "by_when": "2026-09-27"},
        "alternative": "If Tuesday does not work, offer two other times this week.",
        "wait_or_stop": "Stop once the invite is accepted.",
        "outcome_window_days": 3, "success_signal": "Neha accepts the invite.",
        "do_nothing_consequence": "The slot lapses and the call slips a week.",
        "confidence_vector": {"C": 9000, "I": 8500, "U": 7000}, "capability_key": "expert.file_review",
        "context_tags": ["app:gmail"], "actions": EXPERT_ACTIONS,
        "why": [
            {"sentence": "headline", "evidence": [12], "quotes": ["Would Tuesday 30 Sep, 11 am IST work for a call?"], "source": "expert_check"},
            inference("situation", "the expert's reading of the file — an inference, not a quote"),
            {"sentence": "draft", "to": "neha@cleanwave.io", "evidence": [12], "quotes": ["Would Tuesday 30 Sep, 11 am IST work for a call?"], "source": "expert_check"},
            {"window": "before Tuesday", "days": 3, "from": "her mail", "source": "card_lines"},
        ],
        "context": {"profile": [], "signals": [{"kind": "meeting_request", "label": "Proposed a meeting", "count": 1}], "interactions": SHARED_MEETINGS, "commitments": [SHARED_PROMISE], "freshness": {"label": "fresh", "note": ""}},
        "actionability": {"state": "actionable"},
        "decision": {"card_version": "v2", "recommendation": {"verdict": "reply", "objective": "Reply to what they actually asked",
                     "steps": ["Confirm or decline the proposed meeting"], "avoid": None},
                     "confidence": {"evidence": 0.9, "identity": None, "situation": None, "recommendation": 0.7}, "grounding": {}},
    },
    "c-f22": {
        "output_lane": "investigation", "lane_label": "Question", "level": "abstain",
        "abstained_because": "the file asks you one question before any move — answer it on the file's card",
        "business_subject": "University startup cell", "relationship_role": None,
        "why_now": "The seed grant's applications close on 31 Oct.", "unresolved_item": None,
        "recommended": None, "alternative": None, "wait_or_stop": None, "outcome_window_days": None,
        "confidence_vector": {"C": 6000, "I": 5000, "U": 4000}, "capability_key": "expert.file_review",
        "context_tags": ["app:gmail"], "actions": QUESTION_ACTIONS,
        "why": [{"sentence": "headline", "question": "Are you a startup incubated on the university's campus?",
                 "because": "the grant is open only to startups incubated on campus, and nothing in your mail says whether you are", "source": "expert_check"}],
        "context": {"profile": [], "signals": [], "interactions": [], "commitments": [], "freshness": {"label": "fresh", "note": ""}},
        "actionability": {"state": "context_incomplete", "missing": ["commitment.action"], "message": "We could not confirm what is being asked.",
                          "recommended": "Open the source and review the request"},
        "decision": {"card_version": "v2", "recommendation": {"verdict": "review_source", "objective": "Verify what's actually needed before acting",
                     "steps": ["Open the source and review the request"], "avoid": None},
                     "confidence": {"evidence": 0.6, "identity": None, "situation": None, "recommendation": None}, "grounding": {}},
    },
    "c-f55": {
        "output_lane": "monitor", "lane_label": "Monitor", "level": "prescriptive",
        "business_subject": "Dev Malhotra", "relationship_role": None,
        "why_now": "Four weeks with no outbound while he waits.",
        "unresolved_item": "Dev Malhotra asked for the pricing sheet — waiting on you since 2 Sep",
        "recommended": None, "alternative": None, "wait_or_stop": None, "outcome_window_days": None,
        "confidence_vector": {"C": 7000, "I": 6000, "U": 5000}, "capability_key": None,
        "context_tags": ["app:gmail"], "actions": EXPERT_ACTIONS,
        "why": [{"field": "thread.last_inbound", "value": "2026-09-02T08:00:00+00:00", "source": "gmail"},
                {"evidence_id": "ev_91c2", "source": "reasoning_trace"}],
        "context": {"profile": [], "signals": [], "interactions": [], "commitments": [], "freshness": {"label": "fresh", "note": ""}},
        "actionability": {"state": "actionable"},
        "decision": {"card_version": "v2", "recommendation": {"verdict": "review", "objective": "Dev asked for pricing four weeks ago; nothing has gone out since.",
                     "steps": [], "avoid": None},
                     "confidence": {"evidence": 0.7, "identity": None, "situation": None, "recommendation": None}, "grounding": {}},
    },
    "c-f15": {
        "output_lane": "investigation", "lane_label": "Question", "level": "abstain",
        "abstained_because": "the file asks you one question before any move — answer it on the file's card",
        "business_subject": "Cobalt Peak", "relationship_role": None, "why_now": "Eight weeks without a reply.",
        "confidence_vector": {"C": 4000, "I": 7000, "U": 3000}, "capability_key": "expert.file_review",
        "context_tags": ["app:gmail"], "actions": QUESTION_ACTIONS,
        "why": [{"sentence": "headline", "question": "What is the next step with Cobalt Peak?",
                 "because": "a fact your move rests on quotes nothing from the mail it cites", "source": "expert_check"}],
        "context": {"profile": [], "signals": [], "interactions": [], "commitments": [], "freshness": {"label": "fresh", "note": ""}},
        "actionability": {"state": "actionable"},
        "decision": {"card_version": "v2", "recommendation": {"verdict": "review", "objective": "Your outreach to Cobalt Peak has had no reply in eight weeks.", "steps": [], "avoid": None},
                     "confidence": {"evidence": 0.4, "identity": None, "situation": None, "recommendation": None}, "grounding": {}},
    },
}

TIMELINE = {
    "c-evokoa": [("card.created", None, 26), ("card.surfaced", "dashboard", 25), ("card.rebuilt", None, 4)],
    "c-f24": [("card.created", None, 30), ("card.surfaced", "dashboard", 29), ("card.rebuilt", None, 20),
              ("card.pushed", None, 20), ("card.rebuilt", None, 6)],
}

HISTORY = [
    {"card_id": "h1", "signal_id": "x1", "assignee": None, "domain": "admin", "urgency_band": "high",
     "headline": "Sign the mutual NDA and send it to Zoya.", "situation": "Zoya sent the NDA for signature.",
     "score": 70, "state": "resolved", "created_at": iso(200), "expires_at": iso(-900), "resolved_at": iso(150),
     "last_event_kind": "success.detected", "last_action": None, "last_actor": None, "last_detail": None,
     "last_event_at": iso(150), "closed_at": iso(150)},
    {"card_id": "h2", "signal_id": "x2", "assignee": None, "domain": "admin", "urgency_band": "standard",
     "headline": "Send Leah a short note on the pilot teams", "situation": "Leah asked for news only on real milestones.",
     "score": 40, "state": "acted", "created_at": iso(300), "expires_at": iso(-900), "resolved_at": None,
     "last_event_kind": "human.card_action", "last_action": "wrong", "last_actor": "preview@example.com",
     "last_detail": {"surface": "desktop", "reason": "bad_timing"}, "last_event_at": iso(260), "closed_at": iso(260)},
]

MOMENTS = {"moments": [
    {"moment_id": "m1", "kind": "reminder", "priority": "high", "headline": "You promised Neha the deck by Friday",
     "body": "Seen in WhatsApp · 2 days ago", "display": False, "suppressed_reason": "shadow", "created_at": iso(3), "feedback": []},
    {"moment_id": "m2", "kind": "advice", "priority": "normal", "headline": "Kiran asked for the data-room link",
     "body": "Seen in Gmail", "display": False, "suppressed_reason": "shadow", "created_at": iso(9), "feedback": []},
]}

FOLLOWUPS = {"followups": [
    {"id": "f1", "kind": "promise_mine", "text": "Send Neha the deck", "who": "Neha Kapoor", "app": "whatsapp",
     "due_at": iso(-30), "quote": "will send the deck by Friday", "created_at": iso(40)},
    {"id": "f2", "kind": "ask_theirs", "text": "Kiran asked for the data-room link", "who": "Kiran", "app": "gmail",
     "due_at": None, "created_at": iso(9)},
]}

ROUTES = {
    "/cards": {"cards": CARDS},
    "/cards/history": {"cards": HISTORY, "has_more": False},
    "/auth/me": {"role": "owner", "seat_id": "s1", "email": "preview@example.com"},
    "/v1/seats/me/weekly-report": {"week_start": "2026-10-19", "week_end": "2026-10-25", "promises_caught": 3, "promises_kept": 1,
                                   "asks_flagged": 4, "asks_answered": 2, "deadlines_flagged": 1, "risks_flagged": 0,
                                   "popups_shown": 2, "useful": 1, "not_useful": 0},
    "/v1/moments": MOMENTS, "/moments": MOMENTS,
    "/api/org/org_preview/members": {"members": [
        {"id": "owner", "name": "Rohit", "email": "preview@example.com", "role": "owner", "status": "active", "seat_id": "s1"},
        {"id": "m2", "name": "Harsh", "email": "harsh@example.com", "role": "admin", "status": "active", "seat_id": "s2"}]},
    "/v1/agents": {"agents": [], "count": 0},
}


class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-GeniOS-Source, X-Dev-Org, If-None-Match")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _send(self, status, body):
        self.send_response(status)
        self._cors(); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_GET(self):
        path = self.path.split("?")[0]
        parts = path.strip("/").split("/")
        if parts[0] == "cards" and len(parts) == 3 and parts[2] == "timeline":
            card = next((c for c in CARDS + HISTORY if c["card_id"] == parts[1]), None)
            if card is None:
                return self._send(404, {"detail": "no card"})
            events = [{"id": f"e{i}", "kind": k, "cause": cause, "actor_id": None, "detail": None, "occurred_at": iso(h)}
                      for i, (k, cause, h) in enumerate(TIMELINE.get(card["card_id"], [("card.created", None, 30)]))]
            return self._send(200, {"card": {**card, "why": DETAILS.get(card["card_id"], {}).get("why"), "snooze_until": None,
                                             "resolved_at": card.get("resolved_at")}, "events": events})
        if parts[0] == "cards" and len(parts) == 2 and parts[1] != "history":
            card = next((c for c in CARDS if c["card_id"] == parts[1]), None)
            if card is None:
                return self._send(404, {"detail": "card not found"})
            return self._send(200, {**card, **DETAILS.get(card["card_id"], {})})
        for prefix in ("/v1/followups", "/followups", "/v1/seats/me/followups"):
            if path.startswith(prefix):
                return self._send(200, FOLLOWUPS)
        body = ROUTES.get(path)
        self._send(200 if body is not None else 404, body if body is not None else {"detail": "not in mock"})

    def do_POST(self):
        path = self.path.split("?")[0]
        size = int(self.headers.get("Content-Length") or 0)
        sent = json.loads(self.rfile.read(size) or b"{}")
        parts = path.strip("/").split("/")
        if parts[0] == "cards" and parts[-1] == "action":
            card = next((c for c in CARDS if c["card_id"] == parts[1]), None)
            # deliver/actions.py: a question card offers answer/snooze/requeue/wrong only.
            if card and card["render_mode"] == "question" and sent.get("action") not in ("answer", "snooze", "requeue", "wrong"):
                return self._send(422, {"detail": {"ok": False, "error": "not_offered", "offered": ["answer", "requeue", "snooze", "wrong"]}})
            if sent.get("action") == "wrong" and not sent.get("reason"):
                return self._send(422, {"detail": {"ok": False, "error": "invalid_wrong_reason"}})
            return self._send(200, {"ok": True, "state": "acted"})
        self._send(200, {"ok": True})

    def log_message(self, *a):
        pass


ThreadingHTTPServer(("127.0.0.1", 8031), H).serve_forever()
