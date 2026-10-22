"""A stand-in brain for a local render check: brain-shaped JSON for the home page's routes.

Serves on 127.0.0.1:8000 and allows CORS from http://localhost:3917 (change ORIGIN for another
port). Paths use the org id `org_preview` — plant that as `genios_org_id` in the browser (see
../06-RUN-AND-TEST.md §4). Every body mirrors the shape the real route returns; edit a value to
see an edge case (a failing source, a succeeded delegation, outcomes > 0). Unknown paths → 404.
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
    "/v1/seats/me/weekly-report": {"week_start": "2026-10-19", "week_end": "2026-10-25", "promises_caught": 3, "promises_kept": 1, "asks_flagged": 4, "asks_answered": 2, "deadlines_flagged": 1, "risks_flagged": 0, "popups_shown": 2, "useful": 1, "not_useful": 0},
    "/v1/agents": {"agents": [{"agent_id": "a1", "name": "Default", "status": "active", "connectors": [], "is_default": True}], "count": 1},
    "/v1/delegations": {"delegations": []},
    "/auth/me": {"role": "owner", "seat_id": "s1", "email": "preview@example.com"},
}

class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-GeniOS-Source, X-Dev-Org, If-None-Match")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        body = ROUTES.get(self.path.split("?")[0])
        self.send_response(200 if body is not None else 404)
        self._cors(); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(body if body is not None else {"detail": "not in mock"}).encode())

    do_POST = do_GET

    def log_message(self, *a):
        pass

ThreadingHTTPServer(("127.0.0.1", 8000), H).serve_forever()
