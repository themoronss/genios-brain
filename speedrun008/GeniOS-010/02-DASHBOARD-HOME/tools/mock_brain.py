"""A stand-in brain for a local render check: brain-shaped JSON for the home, Goals and Screen pages' routes.

Serves on 127.0.0.1:8000 and allows CORS (with credentials) from http://localhost:3917 — change ORIGIN
for another port. Paths use the org id `org_preview`; plant it as `genios_org_id` in the browser (see
../06-RUN-AND-TEST.md §4). Every body mirrors the shape the real route returns; edit a value to see an
edge case (a failing source, a succeeded delegation, outcomes > 0). The Goals page's writes work too:
POST /v1/company-brief/lines adds a goal; POST …/proposals/{id}/decide accepts (in the sent `text`,
as the brain does) or rejects one — in memory. One card is in the locked Sales domain on purpose.
The Screen page's follow-ups and popups are here too: resolve, snooze, draft a reply and popup feedback
work in memory; one follow-up names a person GeniOS does not know (no `subject_node_id`).
Unknown paths → 404.
"""
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ORIGIN = "http://localhost:3917"
now = datetime.now(timezone.utc)
iso = lambda h: (now - timedelta(hours=h)).isoformat()

ROUTES = {
    "/api/org/org_preview/home-summary": {
        "snapshot": {"health": [{"label": "Evidence coverage", "value": "71%", "note": ""},
                                {"label": "Freshness", "value": "42%", "note": ""},
                                {"label": "Policy-safe actions", "value": "0%", "note": ""}]},
        "cards": [
            {"key": "decisions", "label": "Intelligent Decisions", "value": "0", "unit": "this week", "delta": "+0%", "direction": "up", "note": "", "bars": [4] * 12, "href": ""},
            {"key": "situations", "label": "Situations formed", "value": "6", "unit": "from 118 signals", "delta": "+50%", "direction": "up", "note": "Business reality, not raw events", "bars": [4, 4, 4, 4, 4, 4, 4, 17, 33, 50, 67, 100], "href": ""},
            {"key": "verified", "label": "Verified outcomes", "value": "0", "unit": "results observed", "delta": "+0%", "direction": "up", "note": "", "bars": [4] * 12, "href": ""},
            {"key": "intervention", "label": "Human intervention", "value": "0%", "unit": "", "delta": "+0%", "direction": "down", "note": "", "bars": [4] * 12, "href": ""},
        ],
        "graphKnowledge": [
            {"label": "Facts", "value": "1,830", "change": ""}, {"label": "Entities", "value": "212", "change": ""},
            {"label": "Relationships", "value": "604", "change": ""}, {"label": "Documents indexed", "value": "470", "change": ""},
            {"label": "Active sources", "value": "2 connected", "change": "Live", "live": True},
            {"label": "Context calls served", "value": "0", "change": ""}],
    },
    "/api/org/org_preview/first-scan": {"generated_at": iso(0), "footprint": {"items_read": 470, "entities": 212, "facts": 1830}},
    "/activity": {"events": [
        {"event_type": "insight_generated", "event_data": {"title": "DPIIT certificate is ready to download", "detail": "", "badge_label": "high"}, "created_at": iso(3)},
        {"event_type": "contact_created", "event_data": {"contact_name": "Asha Verma", "detail": "New person in your graph"}, "created_at": iso(5)},
        {"event_type": "insight_generated", "event_data": {"title": "Reply owed to an incubator", "detail": "", "badge_label": "standard"}, "created_at": iso(20)},
        {"event_type": "contact_updated", "event_data": {"contact_name": "Northwind", "detail": "Updated company in your graph"}, "created_at": iso(30)},
        {"event_type": "insight_generated", "event_data": {"title": "Investor follow-up is 9 days late", "detail": "", "badge_label": "critical"}, "created_at": iso(50)}]},
    "/api/org/org_preview/network-health": {"network_health": {"total_contacts": 212, "active_now": 14, "warm": 31, "needs_attention": 6, "cold": 22, "at_risk": 139},
                                            "open_commitments": {"total": 7, "overdue": 2}},
    "/integrations/status": {
        "gmail": {"connected": True, "freshness": "healthy", "lastSyncAt": iso(1), "metadata": {"recordsPulled": 402, "factsExtracted": 1510, "entitiesExtracted": 180}},
        "googlecalendar": {"connected": True, "freshness": "aging", "lastSyncAt": iso(14), "metadata": {"recordsPulled": 68, "factsExtracted": 320, "entitiesExtracted": 32}},
        "slack": {"connected": False}},
    "/v1/seats/me/weekly-report": {"week_start": "2026-10-19", "week_end": "2026-10-25", "promises_caught": 3, "promises_kept": 1, "asks_flagged": 4, "asks_answered": 2, "deadlines_flagged": 1, "risks_flagged": 0, "popups_shown": 2, "useful": 1, "not_useful": 0,
                                    "nudged_then_closed": 1, "handled_elsewhere": 0},
    "/v1/agents": {"agents": [{"agent_id": "a1", "name": "Default", "status": "active", "connectors": [], "is_default": True}], "count": 1},
    "/v1/delegations": {"delegations": []},
    "/auth/me": {"role": "owner", "seat_id": "s1", "email": "preview@example.com"},
    # Screen page: the seat's follow-ups (GET /v1/followups, item_out(full=True)) and its popups.
    "/v1/followups": {"followups": [
        {"id": "fu_4c1a2e77d0b94f13a8e5c602", "kind": "ask", "text": "Send Priya the October purchase invoices",
         "who": "Priya Shah", "thread_key": "wa:priya", "app": "whatsapp", "due_at": iso(-20), "nudge_at": iso(-12),
         "created_at": iso(2), "subject_node_id": "n_priya", "remind_at": [iso(-12), iso(-19)],
         "quote": "kal tak October ke purchase invoices bhej dena", "updated_at": iso(2), "resolved_at": None, "resolution": None},
        {"id": "fu_7a2c19e3b5d04c8f91a6e270", "kind": "risk", "text": "Northwind renews at the old price unless notice by 3 Nov",
         "who": "Northwind Traders", "thread_key": "ol:northwind", "app": "outlook", "due_at": iso(-260), "nudge_at": None,
         "created_at": iso(5), "subject_node_id": "n_northwind", "remind_at": [iso(-200)],
         "quote": "renews on 3 Dec unless written notice is received 30 days prior", "updated_at": iso(5), "resolved_at": None, "resolution": None},
        {"id": "fu_a90c57d3e2b84f16c7a0d9e3", "kind": "ask", "text": "Sameer asked for the pitch deck",
         "who": "Sameer", "thread_key": "wa:sameer", "app": "whatsapp", "due_at": None, "nudge_at": iso(-10),
         "created_at": iso(26), "subject_node_id": None, "remind_at": [iso(-10)],
         "quote": "Can you share the deck?", "updated_at": iso(26), "resolved_at": None, "resolution": None},
        {"id": "fu_e6d9a0b17c3f4a28d0e9b6c4", "kind": "ask", "text": "Meera needs the ESOP pool size by Friday",
         "who": "Meera Iyer", "thread_key": "sl:meera", "app": "slack", "due_at": iso(-30), "nudge_at": iso(20),
         "created_at": iso(30), "subject_node_id": "n_meera", "remind_at": [],
         "quote": "can you confirm the pool by Friday?", "updated_at": iso(4), "resolved_at": iso(4), "resolution": "answered"},
        {"id": "fu_0f4d88a6b3c24e97d1a5f2b0", "kind": "my_promise", "text": "Signed PO to Cloudline by Wednesday",
         "who": "Cloudline", "thread_key": "ol:cloudline", "app": "outlook", "due_at": iso(30), "nudge_at": iso(40),
         "created_at": iso(52), "subject_node_id": "n_cloudline", "remind_at": [],
         "quote": "I'll send the signed PO by Wednesday", "updated_at": iso(28), "resolved_at": iso(28), "resolution": "done"},
    ]},
    "/v1/moments": {"moments": [
        {"moment_id": "mo_1", "kind": "verify", "priority": "high", "headline": "Northwind renews on 3 Dec — notice is due by 3 Nov",
         "body": None, "origin": "server", "capability_id": "moment.screen_insight", "display": True, "suppressed_reason": None,
         "created_at": iso(5), "expires_at": None, "actions": [], "feedback": [{"action": "shown", "reason": None, "at": iso(5)}]},
        {"moment_id": "mo_2", "kind": "reminder", "priority": "normal", "headline": "Priya's invoices are due tomorrow 18:00",
         "body": None, "origin": "server", "capability_id": "moment.screen_insight", "display": False, "suppressed_reason": "dnd",
         "created_at": iso(2), "expires_at": None, "actions": [], "feedback": []},
    ], "next_before": None},
    # Goals page: the brief's goal lines (accepted) and one goal the drafter proposed.
    "/v1/company-brief": {
        "version": "b1", "text": "", "truncated": [], "last_review": None,
        "lines": [
            {"line_id": "l-seed", "section": "goals", "text": "Raise the seed round", "kind": None,
             "proposed_by": "brief_drafter", "accepted_at": iso(400)},
            {"line_id": "l-dpiit", "section": "goals", "text": "StartupSetu recognition for Nimbus Labs", "kind": None,
             "proposed_by": "brief_drafter", "accepted_at": iso(390)},
            {"line_id": "l-hire", "section": "goals", "text": "Hire a Founding AI Engineer", "kind": None,
             "proposed_by": "founder", "accepted_at": iso(200)},
            {"line_id": "l-who", "section": "who_we_are", "text": "Nimbus Labs builds GeniOS", "kind": None,
             "proposed_by": "founder", "accepted_at": iso(500)},
        ],
        "proposals": [
            {"line_id": "p-design", "section": "goals", "text": "Land three design partners", "kind": None,
             "proposed_by": "brief_drafter", "evidence": [], "proposed_at": iso(20)},
        ],
    },
    "/cards": {"cards": [
        {"card_id": "c-dpiit", "signal_id": "s1", "assignee": None, "urgency_band": "high",
         "headline": "Download the DPIIT recognition certificate", "score": 70, "state": "surfaced",
         "situation": "The portal says the certificate is issued; nobody has downloaded it.",
         "created_at": iso(3), "expires_at": iso(-200)},
        {"card_id": "c-incub", "signal_id": "s2", "assignee": None, "urgency_band": "standard",
         "headline": "Reply owed to the incubator's programme office", "score": 40, "state": "surfaced",
         "situation": "The programme office asked whether you are incubated on campus; no reply yet.",
         "created_at": iso(20), "expires_at": iso(-200)},
        {"card_id": "c-vendor", "signal_id": "s3", "assignee": None, "urgency_band": "critical",
         "headline": "Northwind renewal: notice date in 12 days", "score": 85, "state": "surfaced",
         "situation": "Northwind renews automatically on 3 Dec unless notice is given 30 days before.",
         "created_at": iso(50), "expires_at": iso(-200)},
        {"card_id": "c-sales", "signal_id": "s4", "assignee": None, "urgency_band": "standard",
         "headline": "Follow up on the Acme pilot proposal", "score": 30, "state": "surfaced",
         "situation": "A sales thread — its domain is locked for this workspace.",
         "created_at": iso(60), "expires_at": iso(-200)},
    ]},
    "/v1/expertise/domains": {"active_count": 2, "available_count": 2, "domains": [
        {"id": "founder_office", "name": "Founder Office", "version": "1", "status": "ga", "description": "",
         "question": "", "subdomain_count": 0, "capability_count": 0, "artifact_count": 0, "subdomains": [],
         "active": True},
        {"id": "admin", "name": "Admin", "version": "1", "status": "ga", "description": "", "question": "",
         "subdomain_count": 0, "capability_count": 0, "artifact_count": 0, "subdomains": [], "active": True},
    ]},
}

# GET /cards/{id}: card.v1 plus the decision projection, the way the brain's get_card returns it.
CARD_DETAILS = {
    "c-sales": {"domain": "sales", "output_lane": "decision"},
    "c-dpiit": {"domain": "founder_office", "output_lane": "decision", "business_subject": "StartupSetu desk",
                "relationship_role": "the programme", "why_now": "Banks and two programmes asked for it this month.",
                "unresolved_item": "Download it and save it to Compliance.",
                "do_nothing_consequence": "The tax-holiday application waits on a file you already have.",
                "success_signal": "The PDF is in the Compliance folder.",
                "why": [{"field": "certificate.status", "value": "issued", "source": "Gmail · StartupSetu · 13 Oct"},
                        {"sentence": "headline", "question": "Has the certificate been downloaded?",
                         "because": "no download seen", "source": "expert_check"}],
                "decision": {"card_version": "v2", "recommendation": {
                    "verdict": "Download the certificate today and save it to Compliance.",
                    "objective": "Recognition in hand", "steps": ["Sign in to the portal", "Download the PDF"],
                    "avoid": None},
                    "confidence": {"evidence": 0.9, "identity": 0.95, "situation": 0.7, "recommendation": 0.8},
                    "grounding": {}}},
    "c-incub": {"domain": "founder_office", "output_lane": "investigation", "business_subject": "Programme office",
                "relationship_role": "incubator", "why_now": "Forms close on 31 Oct.",
                "unresolved_item": "One answer: on campus or virtual.",
                "why": [{"field": "thread.last_from", "value": "programme office", "source": "Gmail · 15 Oct"}],
                "decision": {"card_version": "v1", "recommendation": {"verdict": "Answer: virtual incubation.",
                    "objective": "", "steps": [], "avoid": None},
                    "confidence": {"evidence": 0.8, "identity": 0.6, "situation": 0.5, "recommendation": 0.45},
                    "grounding": {}}},
    "c-vendor": {"domain": "admin", "output_lane": "decision", "business_subject": "Northwind Traders",
                 "relationship_role": "vendor", "why_now": "12 days left to give notice; usage fell 40% since July.",
                 "unresolved_item": "Renew, renegotiate or give notice.",
                 "do_nothing_consequence": "It renews for a year at the old price.",
                 "alternative": "Give notice now and renegotiate from there.",
                 "success_signal": "Northwind confirms the new tier in writing, or notice is sent.",
                 "why": [{"statement": "Renewal notice periods are counted back from the renewal date.",
                          "source": "expertise"},
                         {"field": "contract.notice_days", "value": {"days": 30, "clause": "9.2"},
                          "source": "Drive · Northwind MSA.pdf"}],
                 "decision": {"card_version": "v3", "recommendation": {
                     "verdict": "Ask Northwind for the lower tier before 3 Nov; give notice if they refuse.",
                     "objective": "", "steps": ["Send the usage figures", "Ask for the lower tier"],
                     "avoid": "Letting it renew silently"},
                     "confidence": {"evidence": 0.92, "identity": 0.9, "situation": 0.85, "recommendation": 0.7},
                     "grounding": {}}},
}

class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-GeniOS-Source, X-Dev-Org, If-None-Match")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/cards/") and path.count("/") == 2:
            card_id = path.rsplit("/", 1)[1]
            card = next((c for c in ROUTES["/cards"]["cards"] if c["card_id"] == card_id), None)
            body = None if card is None else {**card, **CARD_DETAILS.get(card_id, {})}
        else:
            body = ROUTES.get(path)
        self.send_response(200 if body is not None else 404)
        self._cors(); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(body if body is not None else {"detail": "not in mock"}).encode())

    def do_POST(self):
        path = self.path.split("?")[0]
        size = int(self.headers.get("Content-Length") or 0)
        sent = json.loads(self.rfile.read(size) or b"{}")
        brief = ROUTES["/v1/company-brief"]
        body = None
        if path.startswith("/v1/followups/") and path.count("/") == 4:
            fid, verb = path.split("/")[3], path.split("/")[4]
            item = next((f for f in ROUTES["/v1/followups"]["followups"] if f["id"] == fid), None)
            if item is not None and verb == "resolve":
                item.update(resolution=sent.get("resolution"), resolved_at=iso(0))
                body = item
            elif item is not None and verb == "snooze":
                body = item
            elif item is not None and verb == "draft":
                body = {"text": f"Hi {(item['who'] or '').split()[0]}, on it — you'll have it by tomorrow evening."}
        elif path.startswith("/v1/moments/") and path.endswith("/feedback"):
            mid = path.split("/")[3]
            m = next((x for x in ROUTES["/v1/moments"]["moments"] if x["moment_id"] == mid), None)
            if m is not None:
                m["feedback"].append({"action": sent.get("action"), "reason": sent.get("reason"), "at": iso(0)})
                body = {"moment_id": mid, "recorded": True}
        elif path == "/v1/company-brief/lines":
            line_id = f"l-{len(brief['lines']) + 1}"
            brief["lines"].append({"line_id": line_id, "section": sent.get("section"), "text": sent.get("text"),
                                   "kind": None, "proposed_by": "founder", "accepted_at": iso(0)})
            body = {"line_id": line_id, "status": "accepted", "promoted": 0}
        elif path.startswith("/v1/company-brief/proposals/") and path.endswith("/decide"):
            line_id = path.split("/")[4]
            proposal = next((p for p in brief["proposals"] if p["line_id"] == line_id), None)
            if proposal is not None:
                brief["proposals"].remove(proposal)
                if sent.get("decision") == "accept":
                    # The brain accepts in the founder's own words when `text` is sent (store.accept words=…).
                    brief["lines"].append({**{k: proposal[k] for k in ("line_id", "section", "kind", "proposed_by")},
                                           "text": sent.get("text") or proposal["text"], "accepted_at": iso(0)})
                body = {"line_id": line_id, "status": "accepted" if sent.get("decision") == "accept" else "rejected",
                        "promoted": 0}
        else:
            body = ROUTES.get(path)
        self.send_response(200 if body is not None else 404)
        self._cors(); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(body if body is not None else {"detail": "not in mock"}).encode())

    def log_message(self, *a):
        pass

ThreadingHTTPServer(("127.0.0.1", 8000), H).serve_forever()
