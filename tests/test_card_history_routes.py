"""Cards on the web dashboard — the History tab, one card's timeline, and where a button was pressed.

The desktop app and the web dashboard read the same `cards` rows, so "done on the Mac shows done
on the web" needs no sync of its own. What was missing was a way to READ what already happened:
`/cards` returns only live cards and `/cards/{id}` refuses anything closed. These tests pin the
three routes that close that gap, with the database doubled and the credential boundary real:

  * ``/cards/history`` is routed before ``/cards/{card_id}`` (otherwise "history" is a card id),
    keeps the queue's visibility rule, and pages with one extra row rather than a count query.
  * ``/cards/{id}/timeline`` is tenant- and seat-scoped, and names a card past its deadline
    ``expired`` even before the sweep has moved it.
  * the action route records a known ``surface`` and silently drops an unknown one, so an older
    client keeps working.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import routes
from genios_engine.deliver import actions
from genios_engine.deliver.store import CardStore
from genios_engine.platform import auth
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

ORG = "org_hist"
NOW = datetime.now(timezone.utc)

OWNER = AuthCtx(org_id=ORG, actor_id="founder@example.com")
# An agent-bound key reads only its own lane — the member case for the visibility rule.
MEMBER = AuthCtx(org_id=ORG, actor_id="seat_a", agent_id="seat_a",
                 scopes=["cards.read", "cards.act"])


class FakeStore:
    def __init__(self, cards=None, events=None, history_rows=None):
        self.cards = cards or {}
        self.events = events or {}
        self.history_rows = history_rows or []
        self.history_calls: list[dict] = []

    def get_card(self, card_id):
        return self.cards.get(card_id)

    def timeline(self, org_id, card_id):
        return [e for e in self.events.get(card_id, []) if e["org_id"] == org_id]

    def history(self, org_id, **kwargs):
        self.history_calls.append({"org_id": org_id, **kwargs})
        return list(self.history_rows)


def client(monkeypatch, store: FakeStore, ctx: AuthCtx = OWNER) -> TestClient:
    monkeypatch.setattr(routes, "_card_store", store)
    monkeypatch.setattr(routes, "_graph", object())
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app)


def card(card_id="card_1", *, org=ORG, state="acted", assignee=None, expires=None) -> dict:
    return {"card_id": card_id, "signal_id": "sig_1", "org_id": org, "assignee": assignee,
            "domain": "sales", "urgency_band": "high", "headline": "Reply to Asha",
            "situation": "Pricing question unanswered for 3 days", "score": 71,
            "why": [{"field": "last_reply", "value": "3d", "source": "gmail"}],
            "state": state, "created_at": NOW - timedelta(days=1),
            "expires_at": expires or NOW + timedelta(days=6), "resolved_at": None,
            "snooze_until": None}


# ── /cards/history ────────────────────────────────────────────────────────────────────
def test_history_is_routed_before_the_card_id_route(monkeypatch):
    store = FakeStore(history_rows=[{"card_id": "card_1", "state": "acted"}])
    res = client(monkeypatch, store).get("/cards/history")

    assert res.status_code == 200
    assert res.json() == {"cards": [{"card_id": "card_1", "state": "acted"}], "has_more": False}
    call = store.history_calls[0]
    assert call["org_id"] == ORG
    assert call["states"] == CardStore.HISTORY_STATES
    assert call["admin"] is True                       # an owner session reads the whole org


def test_history_filters_to_one_state_and_rejects_an_unknown_one(monkeypatch):
    store = FakeStore()
    api = client(monkeypatch, store)

    assert api.get("/cards/history", params={"state": "expired"}).status_code == 200
    assert store.history_calls[0]["states"] == ("expired",)
    bad = api.get("/cards/history", params={"state": "deleted"})
    assert bad.status_code == 422
    assert bad.json()["detail"]["error"] == "unknown_state"


def test_a_member_sees_only_their_own_history(monkeypatch):
    store = FakeStore()
    client(monkeypatch, store, MEMBER).get("/cards/history", params={"assignee": "someone_else"})

    call = store.history_calls[0]
    assert call["admin"] is False
    assert call["assignee"] == "seat_a"                # a caller-supplied assignee is ignored


def test_history_pages_with_one_extra_row(monkeypatch):
    rows = [{"card_id": f"card_{i}"} for i in range(3)]
    store = FakeStore(history_rows=rows)
    body = client(monkeypatch, store).get("/cards/history", params={"limit": 2}).json()

    assert [r["card_id"] for r in body["cards"]] == ["card_0", "card_1"]
    assert body["has_more"] is True
    assert store.history_calls[0]["limit"] == 3


# ── /cards/{id}/timeline ──────────────────────────────────────────────────────────────
def test_timeline_returns_the_card_and_its_events(monkeypatch):
    events = [
        {"id": "cev_1", "org_id": ORG, "kind": "card.created", "cause": None,
         "actor_id": "system", "detail": {}, "occurred_at": NOW - timedelta(hours=5)},
        {"id": "cev_2", "org_id": ORG, "kind": "human.card_action", "cause": "do_it_myself",
         "actor_id": "founder@example.com", "detail": {"surface": "desktop"},
         "occurred_at": NOW - timedelta(hours=1)},
    ]
    store = FakeStore(cards={"card_1": card()}, events={"card_1": events})
    body = client(monkeypatch, store).get("/cards/card_1/timeline").json()

    assert body["card"]["headline"] == "Reply to Asha"
    assert body["card"]["state"] == "acted"
    assert "org_id" not in body["card"]
    assert [e["kind"] for e in body["events"]] == ["card.created", "human.card_action"]
    assert body["events"][1]["detail"]["surface"] == "desktop"


def test_timeline_calls_an_open_card_past_its_deadline_expired(monkeypatch):
    stale = card(state="queued", expires=NOW - timedelta(minutes=5))
    store = FakeStore(cards={"card_1": stale})
    body = client(monkeypatch, store).get("/cards/card_1/timeline").json()
    assert body["card"]["state"] == "expired"


def test_timeline_of_another_orgs_card_is_not_found(monkeypatch):
    store = FakeStore(cards={"card_1": card(org="org_other")})
    assert client(monkeypatch, store).get("/cards/card_1/timeline").status_code == 404


def test_timeline_of_a_card_routed_to_another_seat_is_refused_for_a_member(monkeypatch):
    store = FakeStore(cards={"card_1": card(assignee="seat_b")})
    assert client(monkeypatch, store, MEMBER).get("/cards/card_1/timeline").status_code == 403
    # …while the owner, who reads the org queue, may see it.
    assert client(monkeypatch, store, OWNER).get("/cards/card_1/timeline").status_code == 200


# ── /cards/{id}/action · surface ──────────────────────────────────────────────────────
def test_action_records_a_known_surface_and_drops_an_unknown_one(monkeypatch):
    seen: list[dict] = []

    def fake_ingest(**kwargs):
        seen.append(kwargs)
        return {"ok": True, "state": "acted"}

    monkeypatch.setattr(actions, "ingest_action", fake_ingest)
    api = client(monkeypatch, FakeStore())

    assert api.post("/cards/card_1/action",
                    json={"action": "do_it_myself", "surface": "web"}).status_code == 200
    assert api.post("/cards/card_1/action",
                    json={"action": "do_it_myself", "surface": "fax"}).status_code == 200
    assert api.post("/cards/card_1/action", json={"action": "do_it_myself"}).status_code == 200
    assert [k["surface"] for k in seen] == ["web", None, None]
