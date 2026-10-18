"""STEP-03 · which attention tier a mail gets, and why — one function, for every outcome.

    pytest tests/capture/test_attention.py -q

`capture/attention.attention_for` (tree `yc2_w27_s03/M21.C1.L-contract.V0.U03`). The gate no longer
deletes a mail it calls noise: it archives it. Every kept mail then says how much attention it gets
and the reason — the rule that archived it, the whitelist that let it through, the park that holds it.
"""
from __future__ import annotations

import pytest

from genios_engine.capture import attention as at
from genios_engine.capture.gate.context import GateResult


def test_the_tiers():
    assert at.ATTENTIONS == ("deep", "skim", "archive")
    assert at.ARCHIVED == "archived"


@pytest.mark.parametrize("code", ["N-02", "N-03", "N-06", "N-07", "N-10", "llm_junk"])
def test_an_archived_mail_is_archive_with_the_rule_that_archived_it(code):
    assert at.attention_for("archived", GateResult(action="archive", reason_code=code)) == (
        "archive", code)


@pytest.mark.parametrize("gate, reason", [
    (GateResult(action="route", route="needs_extraction", whitelist_code="W-01"), "W-01"),
    (GateResult(action="route", route="needs_extraction", availability="auto_reply"), "N-05"),
    (GateResult(action="short_circuit", route="structured"), "structured"),
    (GateResult(action="route", route="needs_extraction"), "passed"),
])
def test_an_emitted_mail_is_deep_and_says_why(gate, reason):
    assert at.attention_for("emitted", gate) == ("deep", reason)


def test_a_parked_mail_is_deep_and_waiting_with_its_park():
    assert at.attention_for("parked", GateResult(action="park", reason_code="DOC-05")) == (
        "deep", "DOC-05")


@pytest.mark.parametrize("outcome", ["dropped", "duplicate", "superseded"])
def test_anything_else_carries_no_tier(outcome):
    assert at.attention_for(outcome, GateResult(action="drop", reason_code="out_of_scope")) == (
        None, None)


def test_skim_is_declared_and_written_by_nothing_yet():
    """The tier the company brief assigns (STEP-07). Declared so the schema and the code agree."""
    assert at.SKIM in at.ATTENTIONS
