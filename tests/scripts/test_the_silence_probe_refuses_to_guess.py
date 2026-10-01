"""M11.C0.U01 · the probe's verdict logic — and the three ways it refused to guess.

    pytest tests/scripts/test_the_silence_probe_refuses_to_guess.py -q

The script itself talks to production, so what is tested here is the pure part: given rows, what
verdict does it reach. ⛔ Every test below corresponds to a wrong verdict the first draft actually
produced against real data, which is why they exist as tests rather than as comments.

The `--assert-measured` gate deliberately EXITS 1 today, because the per-unit table begins three days
after the model outage started. A verify command that passed would be asserting the question is
answerable when it is not.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_PROBE = Path(__file__).resolve().parents[2] / "scripts" / "l2_unit_silence.py"


def _load():
    spec = importlib.util.spec_from_file_location("l2_unit_silence", _PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load()


def _row(status="completed", skip_reason="(none)", era="before", n=1):
    return {"status": status, "skip_reason": skip_reason, "era": era, "n": n}


# =================================================================================================
# 1 · ⛔ the clean-era rule — the bug the first draft shipped
# =================================================================================================
def test_a_unit_measured_only_during_the_outage_is_unattributable():
    """⛔ THE ONE THAT MATTERS. A unit silent because the model never answered and a unit silent
    because its source was dropped are the SAME ROWS. The first draft asked whether RUNS predated the
    outage — a different question with the opposite answer — and returned a confident verdict on
    evidence that could not support one. That is the L1 `no_model_wired` mistake, reproduced by the
    script written to avoid it."""
    rows = [_row("insufficient_context", era="after", n=532)]
    verdict, why = probe._verdict(rows, clean_era=False)
    assert verdict == "UNATTRIBUTABLE"
    assert "outage-era" in why


def test_the_same_rows_in_the_clean_era_are_a_real_finding():
    rows = [_row("insufficient_context", era="before", n=532)]
    verdict, _why = probe._verdict(rows, clean_era=True)
    assert verdict == "SILENT"


def test_a_speaking_unit_measured_only_in_the_outage_still_flags_its_failures():
    """It completed, so it speaks — but its silences are not attributable, and saying only the first
    half would let the reader treat the second as measured."""
    rows = [_row("completed", era="after", n=28),
            _row("skipped", "no_declared_input_available", era="after", n=1137)]
    verdict, why = probe._verdict(rows, clean_era=False)
    assert verdict == "SPEAKS"
    assert "unattributable" in why


# =================================================================================================
# 2 · ⛔ "silent by design" requires EVERY row, not every reason
# =================================================================================================
def test_a_by_design_skip_is_not_a_defect():
    """`plan.py:229` records at length why dropping a unit with nothing left to read is correct, and
    why the stricter rule was removed — it cost six units to one absent fact."""
    rows = [_row("skipped", "no_declared_input_available", n=53)]
    verdict, why = probe._verdict(rows, clean_era=True)
    assert verdict == "SILENT BY DESIGN"
    assert "plan.py:229" in why


def test_both_select_branches_count_as_by_design():
    """⛔ Measured: `no_declared_input_available` is 3,102 of 26,396 rows and
    `dependency_not_scheduled` is zero. A set holding only the second would have called every one of
    those 3,102 a defect."""
    assert probe._EXPECTED_SILENCE == {"dependency_not_scheduled", "no_declared_input_available"}
    for reason in probe._EXPECTED_SILENCE:
        assert probe._verdict([_row("skipped", reason, n=5)], clean_era=True)[0] == "SILENT BY DESIGN"


def test_insufficient_context_beside_a_by_design_skip_is_not_by_design():
    """⛔ THE SECOND BUG THE PROBE FOUND IN ITSELF. `core.relationship` has 53 by-design skips and 532
    `insufficient_context` rows. Checking only the non-null REASONS labelled it SILENT BY DESIGN and
    hid the 532 — which are the interesting ones. `skipped` means the unit never ran;
    `insufficient_context` means it RAN and declined to assert."""
    rows = [_row("skipped", "no_declared_input_available", n=53),
            _row("insufficient_context", n=532)]
    verdict, why = probe._verdict(rows, clean_era=True)
    assert verdict != "SILENT BY DESIGN"
    assert "532 insufficient_context" in why


def test_the_counts_of_each_kind_of_silence_are_reported_separately():
    rows = [_row("skipped", "no_declared_input_available", n=3),
            _row("insufficient_context", n=7)]
    _verdict, why = probe._verdict(rows, clean_era=True)
    assert "3 skipped by design" in why
    assert "7 insufficient_context" in why


# =================================================================================================
# 3 · the ordinary verdicts
# =================================================================================================
def test_a_unit_that_completed_speaks():
    verdict, why = probe._verdict([_row("completed", n=1165)], clean_era=True)
    assert verdict == "SPEAKS"
    assert "1165 of 1165" in why


def test_a_unit_with_no_rows_is_not_called_silent():
    """⛔ "Never produced a row" and "produced rows and never completed" are different facts. Calling
    the first silent would claim something about a unit nothing ever asked to run."""
    verdict, why = probe._verdict([], clean_era=True)
    assert verdict == "NO ROWS"
    assert "never produced a result row" in why


def test_only_clean_era_rows_are_counted_when_the_clean_era_exists():
    """A unit that completed before the outage and went quiet after it SPEAKS on the evidence that can
    be attributed, and the outage-era rows must not dilute that."""
    rows = [_row("completed", era="before", n=10),
            _row("insufficient_context", era="after", n=1000)]
    verdict, why = probe._verdict(rows, clean_era=True)
    assert verdict == "SPEAKS"
    assert "10 of 10" in why


def test_every_verdict_carries_a_reason():
    for rows, clean in (([], True), ([_row()], True), ([_row(era="after")], False),
                        ([_row("skipped", "no_declared_input_available")], True),
                        ([_row("failed")], True)):
        _v, why = probe._verdict(rows, clean_era=clean)
        assert why and why.strip()


# =================================================================================================
# 4 · ⛔ the script is read-only by construction
# =================================================================================================
def test_the_probe_opens_a_read_only_transaction_and_asks_for_no_write_permission():
    source = _PROBE.read_text()
    assert "set transaction read only" in source
    assert "GENIOS_ALLOW_PROD_WRITE" not in source.replace(
        "`GENIOS_ALLOW_PROD_WRITE` is neither needed nor", "")


def test_the_probe_contains_no_write_statement():
    source = _PROBE.read_text().lower()
    for verb in ("insert into", "update ", "delete from", "drop ", "alter "):
        assert verb not in source, f"a probe must not contain {verb!r}"


def test_the_outage_boundary_is_a_constant_not_a_query():
    """So the script says the same thing on a database whose `llm_costs` has been trimmed by
    retention."""
    from datetime import datetime, timezone

    assert probe._OUTAGE_AT == datetime(2026, 9, 25, 11, 9, tzinfo=timezone.utc)
