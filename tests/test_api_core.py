"""
Core API integration tests — run against a live brain.

These verify the contract that external agents and MCP tools depend on.
If any of these fail, the MCP server, dashboard, or customer integrations
will break.

Run:
    cd genios-brain
    GENIOS_TEST_API_KEY=gn_live_... pytest tests/ -v
"""
import pytest


class TestOrg:
    def test_org_returns_200(self, api):
        r = api.get("/v1/org")
        assert r.status_code == 200

    def test_org_has_required_fields(self, api):
        d = api.get("/v1/org").json()
        assert "org_id" in d
        assert "name" in d
        assert "plan" in d
        assert "tier" in d["plan"]
        assert "status" in d["plan"]
        assert "graph" in d
        assert "contact_count" in d["graph"]


class TestSync:
    def test_sync_returns_200(self, api):
        r = api.get("/v1/sync")
        assert r.status_code == 200

    def test_sync_has_status(self, api):
        d = api.get("/v1/sync").json()
        assert "sync_status" in d


class TestContacts:
    def test_contacts_returns_200(self, api):
        r = api.get("/v1/contacts")
        assert r.status_code == 200

    def test_contacts_returns_list(self, api):
        d = api.get("/v1/contacts").json()
        assert "contacts" in d
        assert isinstance(d["contacts"], list)
        assert "count" in d

    def test_contacts_search_by_name(self, api):
        r = api.get("/v1/contacts?q=a&limit=5")
        d = r.json()
        assert r.status_code == 200
        assert d["count"] <= 5

    def test_contacts_stage_filter(self, api):
        r = api.get("/v1/contacts?stage=WARM&limit=5")
        d = r.json()
        assert r.status_code == 200
        for c in d["contacts"]:
            assert c["relationship_stage"] == "WARM"

    def test_contacts_has_is_broadcast(self, api):
        d = api.get("/v1/contacts?limit=1&exclude_broadcast=false").json()
        if d["count"] > 0:
            assert "is_broadcast" in d["contacts"][0]

    def test_contacts_exclude_broadcast_default(self, api):
        d = api.get("/v1/contacts").json()
        # Default is exclude_broadcast=true — no broadcast senders should appear
        for c in d["contacts"]:
            assert c.get("is_broadcast") is not True, f"{c['email']} is broadcast but not filtered"


class TestContext:
    def test_context_known_contact(self, api):
        """Find a real contact, then fetch context for them."""
        contacts = api.get("/v1/contacts?limit=1").json()
        if contacts["count"] == 0:
            pytest.skip("No contacts in brain")

        email = contacts["contacts"][0]["email"]
        r = api.post("/v1/context", json={"entity": email, "agent_id": "pytest"})
        # Accept 200 (success) or 422 (low confidence) — both are correct behavior
        assert r.status_code in (200, 422)

    def test_context_unknown_contact(self, api):
        r = api.post("/v1/context", json={"entity": "zzz_totally_fake_9999@impossible-domain-xyz.invalid", "agent_id": "pytest"})
        assert r.status_code in (404, 422, 504)

    def test_context_bundle_has_required_fields(self, api):
        contacts = api.get("/v1/contacts?limit=1").json()
        if contacts["count"] == 0:
            pytest.skip("No contacts")
        email = contacts["contacts"][0]["email"]
        r = api.post("/v1/context", json={"entity": email, "agent_id": "pytest"})
        if r.status_code != 200:
            pytest.skip(f"Context returned {r.status_code} — can't check fields")

        d = r.json()
        assert "entity" in d
        assert "context_for_agent" in d
        assert "confidence" in d

        entity = d["entity"]
        assert "name" in entity
        assert "relationship_stage" in entity
        assert "is_broadcast" in entity
        assert isinstance(entity.get("communication_style"), str), "communication_style must be string, not None"

    def test_context_situation_type_classified(self, api):
        contacts = api.get("/v1/contacts?limit=1").json()
        if contacts["count"] == 0:
            pytest.skip("No contacts")
        email = contacts["contacts"][0]["email"]
        r = api.post("/v1/context", json={
            "entity": email, "situation": "follow up on our recent chat", "agent_id": "pytest",
        })
        if r.status_code != 200:
            pytest.skip(f"Context returned {r.status_code}")
        d = r.json()
        assert d.get("situation_type") is not None, "situation_type should be classified for a follow-up prompt"

    def test_context_agent_signals_consistent(self, api):
        contacts = api.get("/v1/contacts?limit=1").json()
        if contacts["count"] == 0:
            pytest.skip("No contacts")
        email = contacts["contacts"][0]["email"]
        r = api.post("/v1/context", json={"entity": email, "agent_id": "pytest"})
        if r.status_code != 200:
            pytest.skip(f"Context returned {r.status_code}")
        d = r.json()
        ab = d.get("agent_behavior")
        ar = d.get("action_recommendation")
        # F1 fix: block/proceed should never contradict
        if ab == "block":
            assert ar != "proceed", f"agent_behavior=block but action_recommendation=proceed — signals contradict"


class TestSegments:
    def test_segments_returns_200(self, api):
        r = api.get("/v1/segments")
        assert r.status_code == 200

    def test_segments_has_list(self, api):
        d = api.get("/v1/segments").json()
        assert "segments" in d
        assert isinstance(d["segments"], list)


class TestHealth:
    def test_root_returns_200(self, api):
        r = api.get("/")
        assert r.status_code == 200
