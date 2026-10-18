"""STEP-11 · `06` D3 — a card built on a founder playbook nobody has reviewed says so.

    .venv/bin/python -m pytest tests/deliver/test_an_unreviewed_playbook_says_so.py -q

Tree `yc2_w27_s11 · M30.C3.L-interface.V2.U02`. Rohit's answer to D3 (9 Oct): before a playbook is
reviewed the expert may advise from it, and the card says *"playbook not yet reviewed"* — for the pilot
org only. The Founder Office is the corpus Rohit reviews line by line (D45) and the one switched on for
that org alone, so the label is decided on the card's corpus and on the selected play's review state,
both carried off the audited snapshot (M30.C3.L-data.V1.U03, M30.C2.L-logic.V1.U06). An Admin card,
whose corpus nobody was asked to review, is unchanged. Hermetic: `build_draft` with its graph reads
stood in.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.deliver import card_builder

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
LABEL = {"review": "playbook not yet reviewed", "play": "founder_office.pb.x.follow",
         "source": "expertise_review"}


@pytest.fixture(autouse=True)
def _graph(monkeypatch):
    monkeypatch.setattr(card_builder, "load_node",
                        lambda *_a, **_k: ("Gulf Launchpad", "company", {}, {}))
    monkeypatch.setattr(card_builder, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(card_builder, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))


def _why(**signal_extra) -> list:
    signal = {"signal_id": "sig_1", "subject_node_id": "n1", "reason_code": "investor_relationship",
              "level": "observation", "score": 60, "play": "founder_office.pb.x.follow",
              "evidence": [{"field": "thread.ball_in_court", "value": "us"}], **signal_extra}
    return card_builder.build_draft(object(), "org_1", signal,
                                    {"pack_id": "founder_office", "templates": {}}, NOW)["why"]


def test_an_unreviewed_founder_playbook_is_labelled_first():
    why = _why(capability_domain="founder_office", play_review_state="unreviewed")
    assert why[0] == LABEL
    assert any(item.get("field") == "thread.ball_in_court" for item in why[1:])


def test_a_reviewed_one_is_not():
    why = _why(capability_domain="founder_office", play_review_state="accepted")
    assert not [item for item in why if "review" in item]


def test_no_review_state_is_not_a_review():
    assert _why(capability_domain="founder_office")[0] == LABEL


@pytest.mark.parametrize("domain", ["admin", "customer_support", "sales", None])
def test_other_corpora_are_unchanged(domain):
    why = _why(capability_domain=domain, play_review_state="unreviewed")
    assert not [item for item in why if "review" in item]


def test_the_words_are_d3_s():
    assert card_builder.PLAYBOOK_NOT_YET_REVIEWED == "playbook not yet reviewed"
    assert card_builder.REVIEWED_BY_THE_FOUNDER == frozenset({"founder_office"})
