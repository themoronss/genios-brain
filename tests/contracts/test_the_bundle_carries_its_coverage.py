"""L1 → L2 · the signals that arrived together, and the coverage that licenses a claim about them.

    pytest tests/contracts/test_the_bundle_carries_its_coverage.py -q

Four signals about one vendor renewal crossed this seam as four loose events, and Layer 2 rebuilt
the grouping from whatever survived the projection — four weak situations instead of one strong
one. `QualifiedEnterpriseSignalBundle` is the group, made once, where the evidence for it still
exists.

⛔ THE ONE RULE THIS FILE EXISTS TO HOLD: **coverage is per source, never blended.**

    "A tenant with complete calendar coverage and 8% email coverage has two different licences to
     make a negative claim, and one blended number would grant the stronger one to both."

A single `completeness_bp` on the bundle is refused at construction, because by the time a reader
sees one it is already too late to know which source it came from.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from genios_engine.contracts.signal import QualifiedEnterpriseSignalBundle

pytestmark = pytest.mark.unit

_COVERAGE = {
    "window_from": "2026-08-01T00:00:00+00:00",
    "window_to": "2026-09-30T00:00:00+00:00",
    "sources": [
        {"source": "gmail", "indexed": 37, "claimed_total": 465,
         "is_estimate": True, "cursor_exhausted": False, "completeness_bp": 795},
        {"source": "gcal", "indexed": 55, "claimed_total": 55,
         "is_estimate": False, "cursor_exhausted": True, "completeness_bp": 10000},
        # ⛔ Drive is connected and gave no count. `None`, not zero, not everything.
        {"source": "drive", "indexed": 0, "claimed_total": None,
         "is_estimate": False, "cursor_exhausted": False, "completeness_bp": None},
    ],
}


def _bundle(**over):
    kwargs = dict(bundle_id="SB-104", org_id="org_x", trace_id="8f2a",
                  signal_ids=("SIG-101", "SIG-102", "SIG-103"),
                  subject_key="contract:CTR-441",
                  entity_keys=("vendor:acme", "contract:CTR-441"),
                  candidate_relationships=("SIG-101 concerns CTR-441",),
                  coverage=_COVERAGE,
                  unresolved=("signed contract version", "accountable renewal owner"))
    kwargs.update(over)
    return QualifiedEnterpriseSignalBundle(**kwargs)


# =================================================================================================
# 1 · ⛔ coverage is per source, never blended
# =================================================================================================
def test_a_blended_completeness_is_refused():
    with pytest.raises(ValidationError) as exc:
        _bundle(coverage={"completeness_bp": 9000, "sources": []})
    assert "per source" in str(exc.value)


def test_each_source_keeps_its_own_licence():
    bundle = _bundle()
    assert bundle.coverage_for("gmail")["completeness_bp"] == 795
    assert bundle.coverage_for("gcal")["completeness_bp"] == 10000


def test_an_unknown_denominator_stays_none_and_never_becomes_zero():
    """⛔ *"We read 8% of the mail"* and *"we do not know what we read"* license different claims.
    A caller that cannot tell them apart will eventually make the wrong one."""
    drive = _bundle().coverage_for("drive")
    assert drive["claimed_total"] is None
    assert drive["completeness_bp"] is None


def test_a_source_we_have_no_coverage_for_is_none_not_a_default():
    assert _bundle().coverage_for("slack") is None


# =================================================================================================
# 2 · what a bundle IS
# =================================================================================================
def test_an_empty_bundle_is_refused():
    """A grouper that ran and had nothing to say belongs in a receipt, not on this seam."""
    with pytest.raises(ValidationError) as exc:
        _bundle(signal_ids=())
    assert "at least one signal" in str(exc.value)


def test_a_repeated_signal_is_refused():
    """A repeat means the grouper double-counted, and every denominator computed from this bundle
    is then wrong by that much."""
    with pytest.raises(ValidationError) as exc:
        _bundle(signal_ids=("SIG-101", "SIG-101"))
    assert "double-counted" in str(exc.value)


def test_the_bundle_is_frozen():
    """It crosses a boundary. A mutable one would let a later reader rewrite what L1 published."""
    bundle = _bundle()
    with pytest.raises(ValidationError):
        bundle.org_id = "someone_else"


def test_an_unnamed_subject_is_allowed():
    """A group can be real — *'these three arrived in one thread'* — before anybody can say which
    business object it concerns. Forcing a subject would invent one."""
    assert _bundle(subject_key=None).subject_key is None


# =================================================================================================
# 3 · the words that keep a proposal a proposal
# =================================================================================================
def test_relationships_are_named_candidate():
    """⛔ *"SIG-101 concerns CTR-441"* is a proposal made from what arrived together. The field is
    called `candidate_relationships` so a downstream reader cannot mistake a time-window
    coincidence for a fact."""
    assert "candidate_relationships" in QualifiedEnterpriseSignalBundle.model_fields
    assert "relationships" not in QualifiedEnterpriseSignalBundle.model_fields


def test_unresolved_is_carried_on_the_boundary():
    """It is not an error list. Layer 2 reads it to decide whether to ASK rather than guess, which
    is why it rides the contract instead of a log."""
    assert "signed contract version" in _bundle().unresolved


# =================================================================================================
# 4 · ⛔ incoming only — the bundle cannot reach the graph
# =================================================================================================
def test_the_contract_names_no_graph_concept():
    """The grouper joins what ARRIVED together. Relating it to what the company already knows is
    reasoning, and it happens above this seam — `capture/` importing `context/` is an upward import
    the topology test fails the build on."""
    forbidden = {"situation_id", "situation", "node_id", "graph", "correlation_id"}
    assert not (forbidden & set(QualifiedEnterpriseSignalBundle.model_fields))
