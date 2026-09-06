"""G7 · the L1.6.8 control surface — the wiring audit's own findings, as tests.

**WHY THIS FILE EXISTS.** Migration 0088 created three tables and the sweep hook wrote to one.
`PostgresFloorStore.set` and `.history` had no caller outside a test, so
`qualification_floor_changes` could not receive a row in production and every tenant ran on
`genios-default` 2500 — doc 06's forbidden global constant, wearing a table. `DropLedger.list`
and `.get` had no caller either, so the components and the payload ref a refusal stores were
written for a question nobody could ask. `explain_importance` (L1.6.7-U3) had no caller at all.

This is the fifth time this build has shipped a unit with no production caller (`extract()`,
the scheduler, the cost governor, the claim_group->conflict seam were the first four), and the
defect is invisible to unit tests by construction: every one of those units was green. So every
assertion here goes through the ROUTER — `app.include_router(routes.router)` — and never calls
the store directly. A test that reached past the route would prove the store and leave the hole.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import routes
from genios_engine.capture.esqe import qualification as Q
from genios_engine.capture.esqe.importance import (BaselineBasis, EntityStanding,
                                                   ImportanceComponents, ImportanceFlag)
from genios_engine.contracts.signal import SignalType
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

ORG = "org_g7"
OTHER = "org_other"
AT = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)


def _components(**over) -> ImportanceComponents:
    """A real components object, so what the ledger stores is what ALG-17 actually produces."""
    base = dict(monetary_exposure_bp=7000, deadline_proximity_bp=6000, actor_authority_bp=9000,
                entity_criticality_bp=10000, signal_type_weight_bp=8000,
                evidence_authority_multiplier_bp=10000, weighted_bp=7600, baseline_used=4_500_000,
                baseline_currency="USD", baseline_basis=BaselineBasis.ORG_HISTORY,
                entity_standing=EntityStanding.MISSION_CRITICAL, eval_time=AT,
                flags=(ImportanceFlag.RELATIVE_DEADLINE,))
    base.update(over)
    return ImportanceComponents(**base)


def _drop(org_id: str = ORG, drop_id: str = "qdr_1", *, importance_bp: int = 1800,
          components=None) -> Q.DropRow:
    return Q.DropRow(
        org_id=org_id, drop_id=drop_id, signal_id="sig_1", event_id="evt_1",
        signal_type=SignalType.CONTRACT_RENEWAL, predicate="renewal_amount_recurs",
        subject_key="contract:northwind", importance_bp=importance_bp,
        importance_version="alg17-v1", floor_bp=2500,
        components=(components if components is not None else _components().as_record()),
        payload_ref="prepared_content:pc_1", evaluated_at=AT,
        retain_until=AT + timedelta(days=90))


@pytest.fixture
def client(monkeypatch):
    """The router, with the two module-level stores the sweep hook already uses swapped for
    in-memory ones. Swapped rather than mocked: `InMemoryFloorStore` keeps the same changelog
    discipline as `PostgresFloorStore`, so a route that forgot to record who moved the floor
    cannot pass here and fail in production."""
    monkeypatch.setattr(routes, "_floor_store", Q.InMemoryFloorStore())
    monkeypatch.setattr(routes, "_drop_ledger", Q.InMemoryDropLedger())
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id="seat_founder")
    return TestClient(app)


# ── the floor ────────────────────────────────────────────────────────────────────────
def test_an_untuned_tenant_reads_the_default_floor_and_says_nobody_set_it(client):
    """`origin` is the whole point of the read. A support engineer looking at a 92% drop rate
    has to tell "somebody chose 6000" from "nobody ever set anything"."""
    body = client.get("/qualification/floor").json()

    assert body["floor_bp"] == Q.DEFAULT_FLOOR_BP
    assert body["origin"] == "default" and body["owner"] == "genios-default"


def test_the_floor_can_be_moved_through_the_route_and_the_move_is_attributed(client):
    """**THE WIRING ASSERTION.** `FloorStore.set` had no production caller, so a per-tenant
    floor was a setting no tenant could set. This drives the HTTP route, then reads the floor
    back through a second route — nothing here touches the store."""
    put = client.put("/qualification/floor",
                     json={"floor_bp": 6000, "reason": "too much noise from newsletters"})

    assert put.status_code == 200 and put.json()["floor_bp"] == 6000
    assert put.json()["origin"] == "tenant" and put.json()["owner"] == "seat_founder"

    after = client.get("/qualification/floor").json()
    assert after["floor_bp"] == 6000 and after["origin"] == "tenant"


def test_moving_the_floor_writes_a_changelog_entry_naming_who_and_why(client):
    """`qualification_floor_changes` could not receive a row in production before this route
    existed. An unattributed threshold that halved a tenant's signal volume is the incident the
    table exists to prevent, and a table nothing writes prevents nothing."""
    client.put("/qualification/floor", json={"floor_bp": 4000, "reason": "first tuning"})
    client.put("/qualification/floor", json={"floor_bp": 6000, "reason": "still noisy"})

    changes = client.get("/qualification/floor/history").json()["changes"]

    assert [c["to_bp"] for c in changes] == [6000, 4000], "newest first"
    assert [c["from_bp"] for c in changes] == [4000, None], "the first setting has no 'from'"
    assert all(c["changed_by"] == "seat_founder" for c in changes)
    assert changes[0]["reason"] == "still noisy"


@pytest.mark.parametrize("floor_bp", [-1, 10001, 99999])
def test_a_floor_outside_the_basis_point_range_is_refused_by_the_route(client, floor_bp):
    """Refused at the door, not by the CHECK constraint three frames away."""
    assert client.put("/qualification/floor", json={"floor_bp": floor_bp}).status_code == 400
    assert client.get("/qualification/floor").json()["origin"] == "default", "nothing was written"


def test_a_scoped_key_cannot_move_the_floor(client):
    """Owner-only. This number decides what the tenant is shown AT ALL, so a read-only
    extension key that could halve their signal volume is a wider grant than any read."""
    client.app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(
        org_id=ORG, actor_id="ext", scopes=["read"])

    assert client.put("/qualification/floor", json={"floor_bp": 9000}).status_code == 403


# ── the drop ledger ──────────────────────────────────────────────────────────────────
def test_the_ledger_answers_why_did_i_never_see_this_with_components_and_a_payload_ref(client):
    """The read the ledger was built for. Both fields are asserted by name because a drop
    without them is regrettable rather than reconstructable — which is what the table's own
    comment promises."""
    routes._drop_ledger.put([_drop()])

    rows = client.get("/qualification/drops").json()["drops"]

    assert len(rows) == 1
    assert rows[0]["importance_bp"] == 1800 and rows[0]["floor_bp"] == 2500
    assert rows[0]["payload_ref"] == "prepared_content:pc_1"
    assert rows[0]["components"]["monetary_exposure_bp"] == 7000
    assert rows[0]["components"]["baseline_used"] == 4_500_000


def test_the_drops_read_narrows_to_one_event(client):
    """"This email produced nothing; why?" is the question a founder can actually ask."""
    routes._drop_ledger.put([_drop(drop_id="qdr_1"),
                             Q.DropRow(**{**_drop(drop_id="qdr_2").__dict__,
                                          "event_id": "evt_2"})])

    assert len(client.get("/qualification/drops").json()["drops"]) == 2
    narrowed = client.get("/qualification/drops", params={"event_id": "evt_2"}).json()["drops"]
    assert [r["drop_id"] for r in narrowed] == ["qdr_2"]


def test_one_drop_renders_the_sentence_l1_6_7_u3_was_written_to_produce(client):
    """**THE SECOND WIRING ASSERTION.** `explain_importance` had no production caller — the
    renderer existed, the components were stored, and the sentence reached nobody. It is
    rendered here FROM THE STORED ROW, so a weight change next month cannot re-explain a
    decision made under the old ones."""
    routes._drop_ledger.put([_drop()])

    body = client.get("/qualification/drops/qdr_1").json()

    assert body["explanation"].startswith("Scored 1800: ")
    assert "mission-critical" in body["explanation"], "the stored standing reached the sentence"
    assert "None" not in body["explanation"]


def test_a_drop_whose_components_predate_this_shape_says_so_instead_of_inventing_a_sentence(
        client):
    """A row written under an older components shape has an honest answer and a dishonest one.
    `None` is the honest one; a sentence assembled from defaults reads as a fact."""
    routes._drop_ledger.put([_drop(components={"monetary_exposure_bp": 7000})])

    body = client.get("/qualification/drops/qdr_1").json()

    assert body["explanation"] is None
    assert body["components"] == {"monetary_exposure_bp": 7000}, "the row still travels"


def test_one_tenants_drops_are_never_visible_to_another(client):
    """The ledger holds the tenant's own subject lines and amounts."""
    routes._drop_ledger.put([_drop(org_id=OTHER, drop_id="qdr_other")])

    assert client.get("/qualification/drops").json()["drops"] == []
    assert client.get("/qualification/drops/qdr_other").status_code == 404


def test_an_unknown_drop_is_a_404_and_not_an_empty_explanation(client):
    assert client.get("/qualification/drops/qdr_nope").status_code == 404
