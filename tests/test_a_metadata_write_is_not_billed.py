"""STEP-05 · a metadata write is not billed as a message read (`06` D21).

    pytest tests/test_a_metadata_write_is_not_billed.py -q

Tree `yc2_w27_s05 · M23.C3.L-logic.V2.U05`. An archived mail now enters memory as metadata only — who
wrote to whom, when, in which thread — and no model read it; the customer pays for what a model read.
`api/routes._BILLABLE_L2_OUTCOMES` names what is billed, so the drain's `committed_metadata` is free by
being left off it — held here by name on both sides, so a rename in either module, or a well-meant
"every committed outcome is billable", fails here and not in somebody's invoice. A mail below the floor
IS billed: Layer 1's model read it, and it enters memory with its words (D20) as `committed`.
"""
from __future__ import annotations

import pytest

from tests.test_ingestion_charge import _charge

pytestmark = pytest.mark.unit


def test_a_sweep_of_archives_files_no_charge(monkeypatch):
    assert _charge(monkeypatch, {"committed_metadata": 240}) == []


def test_only_what_a_model_read_is_charged(monkeypatch):
    charged = _charge(monkeypatch, {"committed": 30, "committed_structured": 4,
                                    "committed_metadata": 240})
    assert [units for _org, _action, units, _kw in charged] == [34]


def test_the_metadata_outcome_is_the_one_done_outcome_left_unbilled():
    from genios_engine.api import routes
    from genios_engine.context import runner

    committed = {o for o in runner._DONE_OUTCOMES if o.startswith("committed")}
    assert committed - set(routes._BILLABLE_L2_OUTCOMES) == {"committed_metadata"}
