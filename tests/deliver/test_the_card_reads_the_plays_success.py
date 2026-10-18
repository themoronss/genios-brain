"""STEP-11 · a card's success line reads the play's authored signal first, the pack's second.

    .venv/bin/python -m pytest tests/deliver/test_the_card_reads_the_plays_success.py -q

Tree `yc2_w27_s11 · M30.C3.L-interface.V2.U04`. `card_builder._play_success` read only the tenant
pack's `plays`, which are `{}` for every corpus pack: no compiled card could ever say what success
looks like. The signal now carries the selected play's `success_events` off the audited snapshot
(M30.C3.L-data.V1.U03); the card reads that first, the pack second, and is NULL only when neither
says one. Hermetic: `build_draft` with its three graph reads stood in for.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.deliver import card_builder

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
AUTHORED = "The programme's decision mail arrives."
PACK = "a reply is received"


@pytest.fixture(autouse=True)
def _graph(monkeypatch):
    monkeypatch.setattr(card_builder, "load_node",
                        lambda *_a, **_k: ("Gulf Launchpad", "company", {}, {}))
    monkeypatch.setattr(card_builder, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(card_builder, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))


def _draft(**signal_extra):
    signal = {"signal_id": "sig_1", "subject_node_id": "n1", "reason_code": "investor_relationship",
              "level": "observation", "score": 60, "play": "founder_office.pb.x.follow",
              **signal_extra}
    effective = {"pack_id": "founder_office", "templates": {},
                 "plays": {"founder_office.pb.x.follow": {"success_signal": PACK}}}
    return card_builder.build_draft(object(), "org_1", signal, effective, NOW)


def test_the_play_s_own_signal_wins():
    assert _draft(play_success_events=[AUTHORED])["success_signal"] == AUTHORED


def test_without_one_the_pack_still_answers():
    assert _draft()["success_signal"] == PACK
    assert _draft(play_success_events=[])["success_signal"] == PACK


def test_a_blank_carried_signal_is_no_signal():
    assert _draft(play_success_events=["  ", None])["success_signal"] == PACK


def test_neither_means_null_not_a_default():
    signal = {"signal_id": "sig_2", "subject_node_id": "n1", "reason_code": "investor_relationship",
              "level": "observation", "score": 60, "play": "founder_office.pb.x.other"}
    draft = card_builder.build_draft(object(), "org_1", signal,
                                     {"pack_id": "founder_office", "templates": {}, "plays": {}}, NOW)
    assert draft["success_signal"] is None
