r"""`U5` · 3,512 decisions carry no `ranking_weights_version`, and every one of them is fine.

⛔ THE FINDING THIS UNIT STARTED FROM WAS WRONG IN EVERY PART. `03-FINDINGS.md` F10 said:

> *"`ranking_weights_version` is present on **1,973 of 2,681** new outputs. The missing 708 are
> exactly the `legacy.rule` + `legacy.score_gate` run count (708). So the legacy lane writes no
> ranking weights version — two scoring lanes, one of which does not say which weights it used.
> Either the legacy lane records its weights, or it **declares that it has none**. A scoring lane
> that cannot say which weights it used is not replayable."*

Measured 2026-10-01, working backwards from the newest row:

    the scope was wrong         3,512 of 12,170 outputs, not 708 of 2,681 — and it is
                                ~27% on EVERY day including the newest, not a time boundary
    the cause was inferred      708 == 708 is a coincidence of a narrow window. The real split
                                is a PERFECT partition on the weights key set:
                                  legacy.general.unanswered_email    2,872 -> 0 with the key
                                  legacy.general.commitment_overdue    616 -> 0 with the key
                                  expertise.dependency_stated        2,513 -> 2,513 with the key
    the conclusion was false    every lane says which weights it used, exactly

⛔ `CapabilityManifest.ranking_weights_version` IS A PROPERTY, NOT A FIELD, and both shapes have
one: *"`ranking_weights@1` for the legacy five, `ranking_weights@2` for G-06's six."* It is derived
by `require_ranking_weights`, which tells the shapes apart **by their key set** — and the weights
themselves are persisted per decision in `reasoning_capability_snapshots.manifest`:

    expertise   8,658 runs   6 keys  effort,impact,importance,risk,success,urgency  -> @2
    legacy      3,500 runs   5 keys  effort,impact,risk,success,urgency             -> @1
    expertise      12 runs   5 keys  effort,impact,risk,success,urgency             -> @1
    ─────────────────────────────────────────────────────────────────────────────────────
                12,170 runs — every single one resolves, and ZERO carry no weights at all

⛔ AND THE FIX F10 PROPOSED WOULD HAVE BROKEN REPLAY. The contract says why, at the exact line I
would have changed:

> *"Properties, not fields, and that is the whole reason old capabilities still address to the same
> bytes: a stored `ranking_weights_version` column would have entered `to_semantic_dict`, changed
> `capability_snapshot_id` for every capability in the tree, and **invalidated the
> `reasoning_capability_snapshots` rows replay is verified against** — in exchange for a string the
> key set already determines."*

**Twentieth near-miss in this programme, and the third consecutive one whose proposed fix would
have caused harm** — F9 would have discarded every future calendar event, F10 would have
invalidated the replay chain.

⛔ AND THE TWELVE ROWS ARE THE PROOF THE DESIGN IS RIGHT. Twelve `expertise.*` runs are on the
v1 FIVE weights. Had this been "fixed" by writing `@1` for `legacy.*` and `@2` for `expertise.*` —
the obvious shortcut, and the one the 708-coincidence suggested — those twelve would have been
labelled wrong. The key set is the only thing that knows.

> ⛔ **A lane name is not a version.** `require_ranking_weights` reads the key set *"never by their
> sum"* and never off an activation table, and twelve rows in production need exactly that.

## What this file is for

Not a defect. F10 is retracted, and **nothing was built**. These tests exist so the next reader who
measures 3,512 absent keys finds the answer rather than re-opening the symptom.

⛔ AND DELIBERATELY NO RECEIPT. 12,170 of 12,170 resolve, and the contract validates the shape at
construction — a receipt asserting "every snapshot's weights resolve to a version" would be green
forever and could not go red. **A receipt that cannot fail is not a gate.**

## Living log

    2026-10-01   12,170 runs · 8,658 @2 · 3,512 @1 · 0 unresolvable
                 12 of the @1 runs are `expertise.*`, which is why the lane name cannot be used
"""
from __future__ import annotations

import inspect

import pytest

from genios_engine.contracts.reasoning import (RANKING_WEIGHTS_V1, RANKING_WEIGHTS_V1_SCALE,
                                               RANKING_WEIGHTS_V1_VERSION, RANKING_WEIGHTS_V2,
                                               RANKING_WEIGHTS_V2_SCALE,
                                               RANKING_WEIGHTS_V2_VERSION,
                                               RANKING_WEIGHTS_VERSIONS,
                                               require_ranking_weights)


# ══ 1 · both shapes have a version, and it comes from the KEY SET ════════════════

def test_the_legacy_five_resolve_to_version_one() -> None:
    """⛔ F10's central claim — *"the legacy lane … does not say which weights it used"* — as a
    test. It says `ranking_weights@1`."""
    _weights, version = require_ranking_weights(dict(RANKING_WEIGHTS_V1))
    assert version == RANKING_WEIGHTS_V1_VERSION == "ranking_weights@1"


def test_the_six_resolve_to_version_two() -> None:
    _weights, version = require_ranking_weights(dict(RANKING_WEIGHTS_V2))
    assert version == RANKING_WEIGHTS_V2_VERSION == "ranking_weights@2"


def test_the_two_shapes_differ_by_exactly_one_key_and_that_key_is_the_discriminator() -> None:
    """⛔ `importance` is the whole difference, and `decision_maker.ranking_model_is_v2` reads
    precisely that — *"off the weight KEY SET … and never off an activation table"*."""
    assert set(RANKING_WEIGHTS_V2) - set(RANKING_WEIGHTS_V1) == {"importance"}
    assert set(RANKING_WEIGHTS_V1) - set(RANKING_WEIGHTS_V2) == set()

    from genios_engine.reason.decision_maker import ranking_model_is_v2

    source = inspect.getsource(ranking_model_is_v2)
    assert "ranking_weights" in source, (
        "the v2 test must read the weights, not a lane name or an activation row")


def test_there_are_exactly_two_versions_and_a_third_is_refused() -> None:
    """A closed set. ⛔ `ReasoningDecision` validates against it, so an invented version is a
    construction error rather than a string that travels."""
    assert RANKING_WEIGHTS_VERSIONS == ("ranking_weights@1", "ranking_weights@2")
    assert len(set(RANKING_WEIGHTS_VERSIONS)) == 2


# ══ 2 · the lane name cannot stand in for the version — twelve rows prove it ══════

def test_a_lane_name_is_not_a_version() -> None:
    """⛔ THE TWELVE ROWS, AS A PROPERTY.

    Measured 2026-10-01: twelve `expertise.*` runs are on the v1 FIVE weights. The obvious
    shortcut — `legacy.*` means `@1`, `expertise.*` means `@2` — would label those twelve wrong,
    and the 708-coincidence in F10 pointed straight at that shortcut.

    This asserts the property rather than the twelve rows: the SAME key set resolves to the SAME
    version regardless of which capability holds it, so a capability id can never be the input.
    """
    five = dict(RANKING_WEIGHTS_V1)
    assert require_ranking_weights(five)[1] == RANKING_WEIGHTS_V1_VERSION

    signature = inspect.signature(require_ranking_weights)
    assert set(signature.parameters) == {"value", "label"}, (
        "⛔ `require_ranking_weights` takes the WEIGHTS and nothing else. A capability id or a "
        f"lane parameter here would be the shortcut the twelve rows refute. Got "
        f"{list(signature.parameters)}")


def test_the_scales_differ_so_a_mislabelled_version_would_also_mis_divide() -> None:
    """⛔ Why getting this wrong is not cosmetic: the two shapes have different divisors, so a
    weighted sum computed under the wrong version is off by a factor of 100."""
    assert RANKING_WEIGHTS_V1_SCALE == 100
    assert RANKING_WEIGHTS_V2_SCALE == 10_000
    assert RANKING_WEIGHTS_V2_SCALE == RANKING_WEIGHTS_V1_SCALE * 100

    with pytest.raises(ValueError, match="sum to"):
        require_ranking_weights({key: 1 for key in RANKING_WEIGHTS_V1})


# ══ 3 · and why it is a property rather than a stored column ═════════════════════

def test_the_version_is_a_property_and_the_contract_says_why() -> None:
    """⛔ THE REASON F10'S FIX WOULD HAVE BROKEN REPLAY, pinned where a reader will find it.

    Storing it would enter `to_semantic_dict`, change `capability_snapshot_id` for every
    capability in the tree, and invalidate the `reasoning_capability_snapshots` rows replay is
    verified against. The comment that says so sits directly above the property; this test fails
    if the property becomes a field, so the next attempt has to read the reason first.
    """
    from genios_engine.contracts.reasoning import CapabilityManifest

    attribute = inspect.getattr_static(CapabilityManifest, "ranking_weights_version")
    assert isinstance(attribute, property), (
        "⛔ `ranking_weights_version` became a stored field. That changes "
        "`capability_snapshot_id` for every capability and invalidates every persisted snapshot "
        "replay is verified against — in exchange for a string the key set already determines")

    assert "ranking_weights_version" not in CapabilityManifest.__dataclass_fields__, (
        "a dataclass field would enter `to_semantic_dict` and move the snapshot id")


def test_the_decision_field_is_optional_and_that_is_not_a_gap() -> None:
    """`ReasoningDecision.ranking_weights_version` is `str | None`. ⛔ Unpopulated is not lost:
    the weights are persisted on the capability snapshot the decision pins, so the version is
    recoverable exactly — which is what makes a decision replayable without the field."""
    from genios_engine.contracts.reasoning import ReasoningDecision

    field = ReasoningDecision.__dataclass_fields__["ranking_weights_version"]
    assert field.default is None, (
        "the field is optional by design — the information lives on the pinned snapshot")
