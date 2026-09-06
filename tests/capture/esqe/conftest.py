"""Builders for the ESQE units: an `ExtractionResult` you can vary one field at a time.

Every predicate in ALG-15 reads a different corner of the extraction, so a table-driven test
needs to construct twelve near-identical results that differ in one claim each. Hand-writing
those is how a row ends up asserting against a fixture that also changed in a second place; the
factories here vary exactly what they are asked to and nothing else.

Spans are FOUND in the fixture text by the `span_of` fixture from `tests/capture/conftest.py`,
never hand-counted, so a receipt in a test is built the same way L1.5.1 verifies one.
"""

from __future__ import annotations

from datetime import timezone

import pytest

from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                EntityMention, ExtractionResult)
from genios_engine.contracts.units import DateCertainty, Money, ResolvedDate

#: Provenance every built result carries. Required by the contract for replay; irrelevant to
#: every predicate, which is why it is one constant instead of a parameter.
PROVENANCE = dict(model_snapshot="fake-model-1", prompt_version="p1", schema_version="1",
                  extraction_profile="email", input_tokens=1000, output_tokens=200)


@pytest.fixture
def a_span(span_of):
    """One reusable receipt from the worked-example text — for claims whose content the test
    does not care about."""
    return span_of("Finance")


@pytest.fixture
def result(a_span):
    """An `ExtractionResult` with everything empty, overridden field by field.

    `intent="inform"` and `stance="neutral"` are the neutral floor: neither fires a predicate,
    so a row that sets `intent="escalate"` is testing the escalate predicate and not the
    accidental interaction of two defaults.
    """
    def _result(**over) -> ExtractionResult:
        kwargs = dict(intent="inform", stance="neutral", **PROVENANCE)
        kwargs.update(over)
        return ExtractionResult(**kwargs)
    return _result


@pytest.fixture
def commitment(a_span):
    def _commitment(*, is_conditional: bool = False, due: ResolvedDate | None = None,
                    actor: str = "Finance", action: str = "confirm") -> Commitment:
        return Commitment(actor=actor, action=action, is_conditional=is_conditional, due=due,
                          evidence=[a_span], confidence_bp=8000)
    return _commitment


@pytest.fixture
def decision(a_span):
    def _decision(state: str, *, subject: str = "annual contract") -> DecisionState:
        return DecisionState(subject=subject, state=state, evidence=[a_span], confidence_bp=8000)
    return _decision


@pytest.fixture
def dependency(a_span):
    def _dependency(dependency_type: str = "approval") -> Dependency:
        return Dependency(blocker="Finance", blocked="Rohit", dependency_type=dependency_type,
                          evidence=[a_span], confidence_bp=7900)
    return _dependency


@pytest.fixture
def entity(a_span):
    def _entity(surface_form: str = "Acme", entity_type: str = "organization") -> EntityMention:
        return EntityMention(surface_form=surface_form, entity_type=entity_type,
                             evidence=[a_span], confidence_bp=9000)
    return _entity


@pytest.fixture
def dated(eval_time, a_span):
    """A `ResolvedDate` a given number of days from the frozen eval_time, at a given certainty.

    Days from `eval_time`, never a literal: the 7-day horizon is the thing under test, and a
    hardcoded date would silently stop straddling it the day the frozen clock moves.
    """
    from datetime import timedelta

    def _dated(days: int, certainty: DateCertainty = DateCertainty.EXACT) -> ResolvedDate:
        when = eval_time + timedelta(days=days)
        return ResolvedDate(as_written=f"in {days} days", earliest=when, latest=when,
                            certainty=certainty, resolved_against=eval_time.astimezone(timezone.utc),
                            evidence=[a_span])
    return _dated


@pytest.fixture
def money():
    def _money(as_written: str = "$84K", minor_units: int = 8_400_000) -> Money:
        return Money(minor_units=minor_units, currency="USD", as_written=as_written)
    return _money
