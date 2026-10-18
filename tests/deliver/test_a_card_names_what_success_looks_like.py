"""STEP-11 · the signal select carries the selected play's success signal, review state and domain.

    GENIOS_TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/deliver/test_a_card_names_what_success_looks_like.py -q

Tree `yc2_w27_s11 · M30.C3.L-data.V1.U03`. A card's success line was read from the tenant pack's
`plays` (`card_builder._play_success`), which is `{}` for every corpus pack: no compiled card could
ever say what success looks like, however its playbook put it. The selected play is already proved
against the audited capability snapshot by the authority join (`reason/authority.py`,
`authority_play`); `deliver/pipeline._open_signals_without_cards` now carries that play's
`success_events` and `metadata.review_state`, and the manifest's `domain`, onto the signal the card is
built from — the same snapshot the card's authored copy (`capability_render`) already comes from.

Postgres: the admin pilot tenant driven through the production lane (`l3_pilot_seed`), stopped
before delivery so its open signals are still waiting for cards.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg

SUCCESS = "The counterparty confirms the signed form arrived."


def _seeded(pg_store, org: str):
    """The seed's own clock throughout: its signals' authority runs out weeks before today's."""
    from tests.reason.adapters.l3_pilot_seed import EVAL_TIME, seed_admin_pilot
    with pg_store.engine.begin() as conn:
        conn.execute(text("delete from signals where org_id = :o"), {"o": org})
    counts = seed_admin_pilot(pg_store, org, build_cards=False)
    assert counts["compile"].get("emitted", 0) >= 1, counts
    from genios_engine.deliver.pipeline import _open_signals_without_cards
    return _open_signals_without_cards(pg_store, org, evaluation_time=EVAL_TIME)


def _stored_play(pg_store, org: str, signal: dict) -> dict:
    with pg_store.engine.connect() as conn:
        manifest = conn.execute(text(
            "select rcap.manifest from signals s join reasoning_runs rr on rr.org_id=s.org_id "
            "and rr.run_id=s.reasoning_run_id join reasoning_capability_snapshots rcap "
            "on rcap.org_id=rr.org_id and rcap.capability_snapshot_id=rr.capability_snapshot_id "
            "where s.org_id=:o and s.signal_id=:s"), {"o": org, "s": signal["signal_id"]}).scalar()
    manifest = manifest if isinstance(manifest, dict) else json.loads(manifest)
    [play] = [p for p in manifest["plays"] if p["play_id"] == signal["play"]]
    return play


def test_the_signal_carries_the_selected_play_as_the_audited_manifest_holds_it(pg_store):
    org = "org_s11_success_carried"
    rows = _seeded(pg_store, org)
    assert rows, "the seed left no open signal waiting for a card"
    for row in rows:
        play = _stored_play(pg_store, org, row)
        assert list(row["play_success_events"]) == list(play.get("success_events") or [])
        assert row["play_review_state"] == (play.get("metadata") or {}).get("review_state")
        assert row["play_review_state"] in ("accepted", "unreviewed")
        assert row["capability_domain"] == "admin"


def test_an_authored_success_signal_reaches_the_row(pg_store, monkeypatch):
    """The shipped Admin playbooks author none yet, so the adapter's reading is stood in for: what
    this unit proves is the carriage from the audited play to the row, not the reading."""
    from genios_engine.reason.adapters import expertise
    monkeypatch.setattr(expertise, "_authored_success", lambda _d: ((SUCCESS,), "authored"))
    org = "org_s11_success_authored"
    rows = _seeded(pg_store, org)
    assert rows and all(list(row["play_success_events"]) == [SUCCESS] for row in rows)
