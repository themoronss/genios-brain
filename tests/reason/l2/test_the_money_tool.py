"""L2 rebuild · the money tool — the arithmetic on amounts the model is never asked to do (Context-First §3).

Golden F56: a vendor's renewal names $1,000 and $1,320. "32% more" is a number the L2 check refuses unless the
dossier printed it, and a model asked to work it out may get it wrong. The tool prints the amounts per currency
and, where one currency names two or more, how far the largest is above the smallest — never which is the old
price and which the new: that is a reading of the words, and the model's.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from genios_engine.reason.l2.inputs import _amounts_of
from genios_engine.reason.l2.tools import amounts_tool, run_tools

pytestmark = pytest.mark.unit


def _sig(*amounts):
    return NS(amounts=tuple(amounts), occurred_at=None, due_at=None, thread_key=None, ball_in_court=None,
              direction=None)


def test_a_renewal_at_a_higher_price_is_said_in_money_and_percent():
    t = amounts_tool([_sig(("USD", 132000), ("USD", 100000))])
    assert t.tool_id == "tool:amounts"
    assert t.says == "amounts the signals name: USD 1,000.00, 1,320.00 — the largest is 32% above the smallest " \
                     "(USD 320.00 more)"
    assert t.value == {"USD": {"amounts": [100000, 132000], "difference": 32000, "percent": 32}}


def test_one_amount_is_named_with_no_comparison_and_currencies_never_mix():
    t = amounts_tool([_sig(("INR", 5000000)), _sig(("USD", 99900))])
    assert t.says == "amounts the signals name: INR 50,000.00; USD 999.00"
    assert "%" not in t.says


def test_no_amount_is_no_tool():
    assert amounts_tool([_sig()]) is None
    assert all(r.tool_id != "tool:amounts" for r in run_tools([], eval_time=None))


def test_an_extraction_amount_is_read_only_when_well_formed():
    raw = [{"currency": "usd", "minor_units": 132000, "as_written": "$1,320"}, {"currency": "USD"},
           {"currency": "USD", "minor_units": True}, {"currency": "", "minor_units": 5}, "junk"]
    assert _amounts_of(raw) == (("USD", 132000),)
