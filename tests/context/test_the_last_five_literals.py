"""CTX-L3 · LRN-PAIR-04 · CORR-05 — three word lists and two registries, each one business's.

    pytest tests/context/test_the_last_five_literals.py -q

Each fix ADDS to the shipped set and never replaces it, so every assertion here that today's
behaviour is unchanged is the load-bearing half.
"""

from __future__ import annotations

import textwrap

import pytest

from genios_engine.context.analytic.correlator import (
    REGISTERED_PAIRS,
    _PAIR_INDEX,
    authored_pairs,
)
from genios_engine.context.correlation_resource import (
    _CONTRACT_TYPES,
    _SPEND_TYPES,
    resource_kinds,
)
from genios_engine.context.derived import _PROGRESS_KINDS, _PROGRESS_KINDS_FALLBACK
from genios_engine.context.vocabulary import (
    CANONICAL_OBS_KINDS,
    OBS_NEGATIVE,
    OBS_NEUTRAL,
    OBS_POSITIVE,
    kinds_where,
    load_meanings,
)
from genios_engine.context.waiting import _ASK_KINDS, _ASK_KINDS_FALLBACK

pytestmark = pytest.mark.unit


# =============================================================================================
# CTX-L3 — what an observation kind MEANS, in one place instead of three.
# =============================================================================================
def test_the_three_tables_still_say_exactly_what_they_said():
    """A kind was authorable at the EXTRACTION end and hardcoded at the MEANING end, across
    three literals in three files. Deriving them from one row per kind must change nothing."""
    assert kinds_where(polarity="positive") == OBS_POSITIVE
    assert kinds_where(polarity="negative") == OBS_NEGATIVE
    assert kinds_where(polarity="neutral") == OBS_NEUTRAL
    assert _ASK_KINDS == _ASK_KINDS_FALLBACK
    assert _PROGRESS_KINDS == _PROGRESS_KINDS_FALLBACK


def test_every_canonical_kind_has_a_meaning():
    """A kind the extractor may emit and nothing has weighted scores ZERO everywhere: neutral
    sentiment, not an ask, not progress. Not refused, not flagged — silently weightless."""
    from genios_engine.context.vocabulary import OBSERVATION_MEANINGS

    assert set(OBSERVATION_MEANINGS) == CANONICAL_OBS_KINDS


def test_a_kind_can_be_an_ask_and_neutral_at_once():
    """Asking is a fact about the exchange, not a verdict on it — an approval REQUEST is
    neither good nor bad news until it is answered."""
    asks = kinds_where(is_ask=True)

    assert "approval_requested" in asks
    assert "approval_requested" in OBS_NEUTRAL


def test_a_new_kind_is_one_row(tmp_path):
    path = tmp_path / "kinds.yaml"
    path.write_text(textwrap.dedent("""
        kinds:
          - {kind: sample_collected, polarity: positive, is_progress: true}
          - {kind: report_requested, polarity: neutral, is_ask: true}
    """))

    got = load_meanings(path)

    assert got["sample_collected"].is_progress is True
    assert got["report_requested"].is_ask is True
    assert got["report_requested"].polarity == "neutral"


def test_an_unrecognised_polarity_reads_as_neutral_not_as_a_crash(tmp_path):
    path = tmp_path / "kinds.yaml"
    path.write_text("kinds:\n  - {kind: odd, polarity: purple}\n")

    assert load_meanings(path)["odd"].polarity == "neutral"


def test_an_unreadable_file_does_not_empty_the_polarity_table(tmp_path):
    """It must not make every observation in the tenant read neutral — the shipped sets are
    what was there yesterday, and keeping them is strictly safer."""
    path = tmp_path / "kinds.yaml"
    path.write_text("kinds: [unclosed\n")

    assert load_meanings(path) == {}
    assert CANONICAL_OBS_KINDS == OBS_POSITIVE | OBS_NEGATIVE | OBS_NEUTRAL


# =============================================================================================
# LRN-PAIR-04 — "does X move with Y".
# =============================================================================================
def test_the_shipped_six_are_the_registry_today():
    assert authored_pairs() == ()
    assert len(_PAIR_INDEX) == len(REGISTERED_PAIRS)


def test_a_business_can_ask_its_own_question(tmp_path):
    path = tmp_path / "correlations.yaml"
    path.write_text(textwrap.dedent("""
        pairs:
          - metric_a: engagement_touch_count_28d
            metric_b: deal_stage_age_days
            question: do the clinics that reschedule most also pay slowest?
    """))

    got = authored_pairs(path)

    assert len(got) == 1
    assert got[0].question.startswith("do the clinics")


def test_a_pair_with_no_question_is_refused(tmp_path):
    """The question is not documentation: it is what stops the registry becoming a fishing
    expedition over every pair of metrics, which is the multiple-comparisons failure this file
    exists to bound."""
    path = tmp_path / "correlations.yaml"
    path.write_text("pairs:\n  - {metric_a: a, metric_b: b}\n")

    assert authored_pairs(path) == ()


def test_the_validation_runs_over_the_merged_list():
    """An authored pair that duplicates a shipped one must fail at import rather than quietly
    become a seventh hypothesis."""
    import inspect

    from genios_engine.context.analytic import correlator

    source = inspect.getsource(correlator)

    assert "_validated_registry(\n    (*REGISTERED_PAIRS, *authored_pairs()))" in source


# =============================================================================================
# CORR-05 — what a commitment and a draw are.
# =============================================================================================
def test_the_shipped_pair_is_unchanged():
    commitments, draws = resource_kinds()

    assert commitments == _CONTRACT_TYPES
    assert draws == _SPEND_TYPES


def test_a_firm_can_model_a_retainer_against_time_entries(tmp_path):
    path = tmp_path / "resource_kinds.yaml"
    path.write_text("commitment_types: [retainer]\ndraw_types: [time_entry]\n")

    commitments, draws = resource_kinds(path)

    assert "retainer" in commitments and "time_entry" in draws
    assert set(_CONTRACT_TYPES) <= set(commitments), "shipped types are added to, not replaced"
    assert set(_SPEND_TYPES) <= set(draws)


def test_a_type_may_not_be_both_a_commitment_and_a_draw(tmp_path):
    """A node that is its own draw would attribute against itself and report a contract as
    fully spent the moment it existed."""
    path = tmp_path / "resource_kinds.yaml"
    path.write_text("commitment_types: [retainer]\ndraw_types: [retainer]\n")

    commitments, draws = resource_kinds(path)

    assert "retainer" in commitments
    assert "retainer" not in draws


def test_a_shipped_type_cannot_be_redeclared_into_the_other_role(tmp_path):
    path = tmp_path / "resource_kinds.yaml"
    path.write_text("commitment_types: [invoice]\n")

    commitments, _draws = resource_kinds(path)

    assert commitments == _CONTRACT_TYPES


def test_an_unreadable_file_leaves_the_shipped_pair(tmp_path):
    path = tmp_path / "resource_kinds.yaml"
    path.write_text("commitment_types: [unclosed\n")

    assert resource_kinds(path) == (_CONTRACT_TYPES, _SPEND_TYPES)


# =============================================================================================
# CTX-L1 — the one lane that WAS open, and the corpus refusing it.
# =============================================================================================
def test_every_pattern_emitted_type_is_one_an_author_may_bind_to():
    """The audit claimed a situation type could not be authored at all; that was overstated —
    `context/patterns/` is a real data lane, activation is a per-tenant operator switch, and
    `situation_bso._situation_type` says an ACTIVATED pattern's type REPLACES the anchor-derived
    one. Six types already ship that way.

    The real gap was coordination. NONE of the six is in `domain_spec.py`, and
    `substrate.l2_situation_types` was transcribed from that file alone — so an author binding
    to `relationship_going_cold` got "is not a type Layer 2 emits" and was told to move it to
    `pending_l2_situation_types`, a wish list for types nobody writes, while the type was live,
    minted every sweep, and already routing. The corpus was refusing the one lane that worked.
    """
    import pathlib

    import yaml

    corpus = pathlib.Path(__file__).resolve().parents[2] / "Domain Expertise"
    declared = set(yaml.safe_load(
        (corpus / "_schema/vocabulary.yaml").read_text())["substrate"]["l2_situation_types"])

    seeds = pathlib.Path(__file__).resolve().parents[2] / \
        "genios_engine/context/patterns/seed"
    emitted = set()
    for path in sorted(seeds.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        situation_type = str((data.get("emits") or {}).get("situation_type") or "").strip()
        if situation_type:
            emitted.add(situation_type)

    assert emitted, "the pattern lane has no seeds — this test would pass vacuously"
    assert emitted <= declared, sorted(emitted - declared)
