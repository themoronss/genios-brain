"""STEP-16 · s16-F23 — a requested document is an ask: it opens a loop, and the document you send closes it answered.

    .venv/bin/python -m pytest -q tests/contracts/test_a_requested_document_is_an_ask.py

`contracts/open_loop.ASK_KINDS` decides which observations open a loop (`context/pipeline`); `kinds.yaml` says which
kinds are asks (`is_ask`) and which kind DISCHARGES which (`document_sent` → `information_requested`). The two had
drifted: `information_requested` was an ask in the meaning table and opened no loop, so a document you sent closed
nothing but a plain question, `replied`, and a file decision could never end `verified` on it (F57). Every kind the
discharges table closes is an ask that opens a loop — or a gap declared here, with why.
"""
from __future__ import annotations

from genios_engine.context.vocabulary import kinds_where
from genios_engine.contracts.open_loop import ASK_KINDS, is_ask

#: Kinds the meaning table calls asks, with a discharge, that still open no loop — each a decision of its own.
DECLARED_GAPS: dict[str, str] = {
    "approval_requested": "one of L1's fifteen signal types: admitting it opens a loop on every approval mail the "
                          "golden set and production carry — its own decision (s16-F23)",
    "intro_requested": "asked for an introduction: closed by `intro_made`; admitting it moves every intro case's "
                       "open asks — decided with the introductions' own work (s16-F23)",
}


def _discharged() -> set[str]:
    from genios_engine.context.vocabulary import OBSERVATION_MEANINGS
    assert OBSERVATION_MEANINGS, "the meaning table loaded nothing: there is nothing to hold the asks to"
    return {d for meaning in OBSERVATION_MEANINGS.values() for d in meaning.discharges}


def test_a_requested_document_is_an_ask():
    assert is_ask("information_requested") and "information_requested" in kinds_where(is_ask=True)


def test_every_kind_a_discharge_closes_is_an_ask_that_opens_a_loop_or_a_declared_gap():
    missing = sorted(k for k in _discharged() if k not in ASK_KINDS and k not in DECLARED_GAPS)
    assert missing == [], f"discharged kinds that open no loop and are declared nowhere: {missing}"
    assert not set(DECLARED_GAPS) & ASK_KINDS, "a declared gap that now opens a loop: the declaration is the lie"
    assert all(len(why) >= 80 for why in DECLARED_GAPS.values())
