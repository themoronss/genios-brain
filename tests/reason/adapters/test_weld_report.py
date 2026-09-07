"""J1 · `scripts/weld_report.py` — the gate that measures the weld, and refuses to lie about it.

A gate script is exactly the kind of "harmless" tool that ends up pointed at production, and
exactly the kind that returns green on an empty table. Both are tested here.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts import weld_report as wr
from scripts._db import UnsafeDatabaseTarget

pytestmark = pytest.mark.unit

AT = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _sample(**overrides) -> wr.WeldSample:
    """A sample that passes every J1 row, so each test can break exactly one thing."""
    statement = "Urgency belongs to the buyer."
    from genios_engine.contracts.domain_expertise import citation_statement_hash
    base = dict(
        source="fixture", capability_id="expertise.deal",
        receipt={
            "by_class": {
                "rule": {"consumed_as_compiled_constraint": 2, "fired": 1},
                "heuristic": {"cited": 1},
                "mental_model": {"framing": 1},
                "decision_framework": {"framing": 1},
                "playbook": {"consumed_as_play": 3},
            },
            "refusals": [{"reason": "no_tag_overlap", "count": 2}],
            "play_receipt": {"plays_selected": 2, "plays_situation_fit": 2,
                             "plays_truncated": ["p3"]},
        },
        citations=({"artifact_id": "h1", "artifact_class": "heuristic",
                    "statement": statement,
                    "statement_hash": citation_statement_hash(statement)},),
        constraints=({"rule_id": "r1"},),
        framing_blocks=(),
        rule_verdicts=({"rule_id": "r1", "outcome": "fired", "severity": "blocking",
                        "blocked_play_ids": ["p1"]},),
        eliminations={"p1": ("r1",)},
        reproducible=True,
    )
    base.update(overrides)
    return wr.WeldSample(**base)


def test_a_healthy_sample_passes_every_row():
    verdict = wr.score([_sample()], at=AT, lane="test")
    assert verdict.passed, verdict.as_dict()["checks"]
    assert verdict.classes_with_consumer == wr.ARTIFACT_CLASSES


def test_an_empty_run_is_not_a_pass():
    """A gate that returns green for nothing measured is how "the weld never ran" reads as
    success — the same rule `importance_distribution` states for an empty window."""
    verdict = wr.score([], at=AT, lane="test")
    assert not verdict.passed
    assert verdict.samples == 0


def test_a_class_with_no_consumer_fails():
    sample = _sample()
    receipt = dict(sample.receipt)
    receipt["by_class"] = {k: v for k, v in receipt["by_class"].items() if k != "heuristic"}
    verdict = wr.score([_sample(receipt=receipt)], at=AT, lane="test")
    assert not verdict.classes_passed
    assert not verdict.passed


def test_a_legacy_unsupported_receipt_fails():
    sample = _sample()
    receipt = dict(sample.receipt)
    receipt["refusals"] = [{"reason": wr.LEGACY_UNSUPPORTED, "count": 1}]
    verdict = wr.score([_sample(receipt=receipt)], at=AT, lane="test")
    assert verdict.legacy_unsupported_receipts == 1
    assert not verdict.passed


def test_a_coerced_unknown_fails():
    """An `unevaluable` rule that blocked something, or that cannot name what it did not know,
    is a rule that was coerced. Both are the failure step 4 exists to prevent."""
    blocked = _sample(rule_verdicts=({"rule_id": "r1", "outcome": "unevaluable",
                                      "severity": "blocking", "missing": ["x"],
                                      "blocked_play_ids": ["p1"]},))
    assert not wr.score([blocked], at=AT, lane="test").unknown_passed
    silent = _sample(rule_verdicts=({"rule_id": "r1", "outcome": "unevaluable",
                                     "severity": "blocking", "missing": [],
                                     "blocked_play_ids": []},))
    assert not wr.score([silent], at=AT, lane="test").unknown_passed


def test_a_paraphrased_citation_fails():
    citation = dict(_sample().citations[0])
    citation["statement"] = citation["statement"].replace("buyer", "customer")
    verdict = wr.score([_sample(citations=(citation,))], at=AT, lane="test")
    assert not verdict.verbatim_passed
    assert not verdict.passed


def test_a_cut_that_removed_a_situation_fit_play_fails():
    receipt = dict(_sample().receipt)
    receipt["play_receipt"] = {"plays_selected": 2, "plays_situation_fit": 5,
                               "plays_truncated": ["p3", "p4", "p5"]}
    verdict = wr.score([_sample(receipt=receipt)], at=AT, lane="test")
    assert verdict.play_cap_alphabetical_wins == 3
    assert not verdict.passed


def test_a_non_reproducible_weld_fails():
    assert not wr.score([_sample(reproducible=False)], at=AT, lane="test").passed


def test_no_llm_call_site_exists_in_the_adapters():
    assert wr.llm_call_sites() == 0


def test_the_fixtures_lane_passes_against_the_shipped_corpus():
    """The command doc 06 names, run for real. Exit 0 means every J1 row held over packages
    compiled from `Domain Expertise/`."""
    assert wr.main(["--fixtures", "--at", "2026-08-08T12:00:00Z"]) == 0


def test_the_report_never_inherits_the_applications_database():
    """`scripts/_db.py`'s whole contract, asserted at this script's boundary: with no target
    named, the org lane refuses rather than reaching for `.env`."""
    with pytest.raises(UnsafeDatabaseTarget):
        wr.main(["--org", "org_1", "--at", "2026-08-08T12:00:00Z"])


def test_an_instant_is_required_and_must_carry_an_offset():
    with pytest.raises(SystemExit):
        wr.main(["--fixtures"])
    with pytest.raises(Exception):
        wr.parse_instant("2026-08-08T12:00:00")


def test_exactly_one_lane():
    with pytest.raises(SystemExit):
        wr.main(["--fixtures", "--org", "org_1", "--at", "2026-08-08T12:00:00Z"])


def test_the_no_samples_guard_stands_on_its_own():
    """`bool(self.samples)` is deliberately redundant with the other rows — with nothing measured
    they all read zero anyway — and it is the row that says WHY an empty run is red. Asserted
    directly, because a redundant guard is exactly the kind that gets deleted as dead."""
    verdict = wr.WeldVerdict(
        at=AT, lane="test", samples=0, classes_with_consumer=wr.ARTIFACT_CLASSES,
        legacy_unsupported_receipts=0, blocking_eliminations=1,
        decisions_with_a_heuristic_citation=1, unknown_rules=0,
        unknown_rules_that_fired_or_blocked=0, citations_checked=1, citations_verbatim=1,
        play_cap_situation_fit_wins=1, play_cap_alphabetical_wins=0, llm_call_sites=0,
        reproducible=True, refusals={})
    assert not verdict.passed, "a gate with nothing measured must never read green"
