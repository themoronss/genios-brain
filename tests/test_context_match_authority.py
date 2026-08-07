from __future__ import annotations

from types import SimpleNamespace

from genios_engine.api import routes
from genios_engine.platform.auth import AuthCtx


def test_context_match_cannot_surface_a_card_with_a_live_agent_claim(monkeypatch):
    calls = []
    card_store = SimpleNamespace(surface_context_match=lambda *args, **kwargs:
                                 calls.append((args, kwargs)) or
                                 {"ok": True, "surfaced": False, "card_id": "card_1"})
    monkeypatch.setattr(routes, "_graph", object())
    monkeypatch.setattr(routes, "_card_store", card_store)
    response = routes.context_match(
        routes.ContextMatch(card_id="card_1", matched_tag="app:gmail"),
        ctx=AuthCtx(org_id="org_1", actor_id="seat_1", scopes=["cards.act"]))

    assert response["surfaced"] is False
    assert calls[0][0] == ("org_1", "card_1", "app:gmail")
    assert calls[0][1] == {"actor_id": "seat_1", "allow_any_assignee": False}
