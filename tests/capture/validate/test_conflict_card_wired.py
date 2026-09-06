"""L1.5.5-U3 · `render_conflict_card` wired — the only thing a HUMAN ever sees of a conflict.

**WHY THIS FILE EXISTS.** ALG-12 detected conflicts on every sweep, `conflict_store` filed them
into `signal_conflicts`, and `render_conflict_card` — doc 05's card contract, the unit that puts
both values, both authorities and both verbatim quotes in front of the founder — had NO caller
anywhere in `genios_engine/`. A grep for the name found its own definition, its own docstring
and `__all__`. So the disagreement between a signed PDF and the email that quotes it was
computed, escalated, stored, and never once rendered: the row existed and no surface could turn
it into a sentence. That is the sixth unit this build has shipped with no production caller.

Two paths, because a conflict becomes visible on two:

* the INGESTION path — `capture_event` -> `ConflictLane.observe` -> `escalate_conflicts`, where
  the `INFORMATION_CONFLICT` signal is raised. The escalation now carries the rendered cards, so
  the signal that says "your sources disagree" carries what to show;
* the READ path — `GET /conflicts`, which reads `signal_conflicts` and renders each stored row.

Every assertion goes through one of those two entry points. Nothing here calls
`render_conflict_card` itself; a test that did would prove the unit and leave the hole.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import routes
from genios_engine.capture import pipeline as P
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.validate import conflict as C
from genios_engine.capture.validate.conflict_store import InMemoryConflictStore, rows_for
from genios_engine.contracts.conflict import ConflictResolution
from genios_engine.contracts.signal import SignalType
from genios_engine.platform.auth import AuthCtx, get_auth_ctx, get_current_org

from tests.capture.validate.test_conflict import (DETECTED, EMAIL_84K, NOW, OWNER, SIGNED_74K,
                                                  _AmountGrouper, _answer, _attachment,
                                                  _message, claim, detect, span, usd)
from genios_engine.contracts.conflict import Authority

ORG = "org_card"
OTHER = "org_other"


# ── the ingestion path ───────────────────────────────────────────────────────────────
@pytest.mark.gate
def test_the_information_conflict_signal_carries_the_card_a_human_reads(fake_llm):
    """THE WIRING ASSERTION, on the path a sweep actually takes: two `capture_event` calls, an
    email and its signed attachment, and the escalation the second one raises carries a rendered
    card — both values, both authorities, both verbatim quotes.

    Before this, `ConflictEscalation` carried a headline string and the raw `Conflict` objects,
    and every consumer of an `INFORMATION_CONFLICT` had to invent its own rendering — which is
    how one surface says "the signed document has higher authority" and the next one quietly
    shows the newest number.
    """
    llm = fake_llm(_answer(8_400_000, "$84K"), _answer(7_400_000, "$74,000"))
    repo = InMemorySourceEventRepository()
    lane = C.ConflictLane(grouper=_AmountGrouper(executed=frozenset({"att1"})),
                          detected_at=DETECTED)

    def capture(raw):
        return P.capture_event(raw, org_id=ORG, connection_id="con_card", repo=repo,
                               mailbox_owner=OWNER,
                               semantic=P.SemanticLane(llm=llm, eval_time=NOW),
                               conflict_lane=lane)

    capture(_message())
    second = capture(_attachment())

    escalation, = second.conflicts.escalations
    assert escalation.signal_type is SignalType.INFORMATION_CONFLICT

    card, = escalation.cards
    assert card.resolution is ConflictResolution.RESOLVED_BY_AUTHORITY
    assert {line.value_text for line in card.lines} == {"$84K", "$74,000"}, "both values"
    assert len(card.lines) == 2, "the losing claim is never dropped from the card"
    assert card.verdict is not None and "$74,000" in card.verdict
    assert "Conflict detected." in card.render()


# ── the read path ────────────────────────────────────────────────────────────────────
@pytest.fixture
def client(monkeypatch):
    """The router with an in-memory `signal_conflicts`. Swapped rather than mocked, so a route
    that forgot the tenant boundary cannot pass here and leak in production.

    `get_current_org` is overridden as well as `get_auth_ctx` because the real dependency reads
    the org kill switch out of Postgres, and this file is about RENDERING: making the card
    assertions depend on a database being configured would mean the wiring they prove is
    unverified on a fresh clone, which is the state the hole was found in.
    """
    monkeypatch.setattr(routes, "_conflict_store", InMemoryConflictStore())
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id="seat_founder")
    app.dependency_overrides[get_current_org] = lambda: ORG
    return TestClient(app)


def _file(detection, org_id: str = ORG) -> None:
    """File a detection exactly as a sweep does — `rows_for` is the same function
    `persist_sweep_conflicts` calls, so what this test stores is what production stores."""
    routes._conflict_store.put(rows_for(detection, org_id=org_id))


@pytest.mark.gate
def test_a_stored_conflict_renders_as_the_card_doc_05_specifies(client):
    """Doc 05 L1.5.5-U3's worked card, read back out of `signal_conflicts`:

        Signed document says $74,000 — "total annual commitment of $74,000" (chunk 42)
        An email says $84K — "the $84K annual contract" (thread 8f2a)
        Conflict detected. The signed document has higher authority.

    Both values, both authorities, both verbatim quotes — and the quotes are the SOURCE's own
    bytes, so a card cannot show a founder a sentence that does not contain the disputed number.
    """
    _file(detect(EMAIL_84K, SIGNED_74K))

    body = client.get("/conflicts").json()

    row, = body["conflicts"]
    assert row["field"] == "contract.value"
    assert row["resolution"] == "resolved_by_authority"
    assert [line["value"] for line in row["card"]["lines"]] == ["$74,000", "$84K"], \
        "strongest claim first, and both sides present"
    assert [line["authority"] for line in row["card"]["lines"]] == \
        ["Signed document", "An email"]
    assert [line["quote"] for line in row["card"]["lines"]] == \
        ["total annual commitment of $74,000", "the $84K annual contract"]
    assert row["card"]["headline"] == "Conflict detected."
    assert "$74,000" in row["card"]["verdict"]


@pytest.mark.gate
def test_a_conflict_authority_could_not_settle_offers_no_recommendation(client):
    """Doc 05's hardest line: **no recommendation about which is right** unless authority
    actually settled it. Two emails one rank apart is `unresolved_surface_both`, and a card that
    picked a winner there would be the confident-wrong failure ALG-12 exists to end."""
    _file(detect(EMAIL_84K, claim("c_mail2", usd(9_400_000, "$94K"), Authority.EMAIL_PROSE,
                                  quote="closer to $94K", at=NOW, event_id="evt_other")))

    row, = client.get("/conflicts").json()["conflicts"]

    assert row["resolution"] == "unresolved_surface_both"
    assert row["card"]["verdict"] is None, "no recommendation without authority"
    assert len(row["card"]["lines"]) == 2, "both sides are still shown"


def test_one_tenants_contract_amounts_are_not_rendered_for_another(client):
    """The card quotes verbatim source text. A conflict route that leaked across tenants would
    leak another company's contract sentences, not just a count."""
    _file(detect(EMAIL_84K, SIGNED_74K), org_id=OTHER)

    assert client.get("/conflicts").json()["conflicts"] == []
