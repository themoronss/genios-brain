"""`availability_change` — SignalType member fifteen, and the path that publishes it.

An availability window has to cross Layer 1's publication boundary or Layer 2 never reads it
(`context/runner._pull` joins `qualified_signals`). These are the hermetic halves: the detector
fires on the extraction's `availability` lane, the tables are total over the new member, the
qualification floor lets it through at its deliberately-low importance, and no deal/reply rule
is keyed on it."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from genios_engine.capture.esqe import classifier, importance, lifecycle, normalize
from genios_engine.capture.esqe.detector import DetectionInput, detect_signals
from genios_engine.capture.esqe.qualification import QualificationReason, _decide
from genios_engine.contracts.extraction import ExtractionResult
from genios_engine.contracts.signal import SignalType

NOW = datetime(2026, 9, 10, 9, tzinfo=timezone.utc)
AVAIL = SignalType.AVAILABILITY_CHANGE


def _extraction(**kw) -> ExtractionResult:
    return ExtractionResult(intent="inform", stance="neutral", model_snapshot="m",
                            prompt_version="p", schema_version="s", extraction_profile="email",
                            input_tokens=1, output_tokens=1, **kw)


def test_the_member_exists_with_its_wire_value():
    assert SignalType("availability_change") is AVAIL


def test_detector_fires_on_the_availability_lane_only():
    lane = [{"person": "sender", "kind": "leave", "from": "from 15th", "to": "22nd",
             "evidence_text": "I am on leave from 15th to 22nd"}]
    fired = detect_signals(DetectionInput(extraction=_extraction(availability=lane),
                                          eval_time=NOW))
    assert AVAIL in fired.types
    assert [s.predicate for s in fired.signals if s.signal_type is AVAIL] == ["availability_stated"]
    # ...and a message with no availability claim never produces one
    none = detect_signals(DetectionInput(extraction=_extraction(questions=["seat count?"]),
                                         eval_time=NOW))
    assert AVAIL not in none.types


def test_it_suppresses_the_anomaly_catch_all_and_ranks_below_every_business_type():
    both = detect_signals(DetectionInput(
        extraction=_extraction(availability=[{"kind": "ooo", "evidence_text": "away"}],
                               questions=["can you confirm?"]),
        eval_time=NOW))
    assert SignalType.ANOMALY not in both.types
    order = list(classifier.PRECEDENCE)
    assert order.index(AVAIL) == order.index(SignalType.ANOMALY) - 1
    assert all(order.index(t) < order.index(AVAIL)
               for t in SignalType if t not in (AVAIL, SignalType.ANOMALY))


def test_every_esqe_table_is_total_over_the_new_member():
    assert importance.SIGNAL_TYPE_WEIGHT_BP[AVAIL] == min(importance.SIGNAL_TYPE_WEIGHT_BP.values())
    assert lifecycle.expiry_window_days(AVAIL) == 30
    assert normalize.DATE_POLICY[AVAIL] is normalize.DatePolicy.NONE      # never a deadline
    assert normalize.ANCHOR_FAMILIES[AVAIL][0].__name__ == "EntityMention"


@dataclass
class _Sig:
    signal_type: object
    internal_kind: str | None = None


@dataclass
class _Candidate:
    signal: _Sig
    importance_bp: int | None
    carries_conflict: bool = False


def test_qualification_lets_availability_through_below_the_floor_and_nothing_else():
    assert _decide(_Candidate(_Sig(AVAIL), 1200), 2500) == (
        True, QualificationReason.AVAILABILITY_OVERRIDE)
    assert _decide(_Candidate(_Sig(SignalType.RELATIONSHIP_CHANGE), 1200), 2500) == (
        False, QualificationReason.BELOW_FLOOR)
    # at/above the floor it is an ordinary pass, not an override
    assert _decide(_Candidate(_Sig(AVAIL), 2600), 2500)[1] is QualificationReason.AT_OR_ABOVE_FLOOR


def test_no_card_or_capability_path_is_keyed_on_it():
    """Availability produces `person.availability` facts, not cards. Nothing above Layer 2 may
    route, render or rank on the type until team-intelligence capabilities are written."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "genios_engine"
    hits = [str(p.relative_to(root)) for pkg in ("packs", "reason", "executive", "deliver",
                                                 "feedback", "api")
            for p in (root / pkg).rglob("*.py")
            if "availability_change" in p.read_text() or "AVAILABILITY_CHANGE" in p.read_text()]
    assert hits == []
