"""STEP-12 · a playbook has a version — the content hash of what the expert reads from it.

    pytest tests/packs/test_a_playbook_has_a_version.py -q

`packs/compiler/playbook_reader.KindPlaybook.version` (tree `yc2_w27_s12` M32.C2.L-data.V0.U03). A review
is made against a playbook — its spine (stages, what doing nothing costs, the stop rule), its moves and
its claims, and whether a named human reviewed each — and a file's fingerprint must move when any of
that does (STEP-12 §8.4 item 3): a review made against the unreviewed playbook is not the review of the
reviewed one. The version is `pb-` and twelve hex of the canonical hash of everything `as_dict` shows
the expert, and `as_dict` carries it beside them.
"""
from __future__ import annotations

import dataclasses
import json
import re

import pytest

from genios_engine.contracts.company_brief import WORK_KINDS
from genios_engine.packs.compiler import playbook_reader as R
from tests.packs.test_a_file_reads_its_playbook import _corpus

pytestmark = pytest.mark.unit

_VERSION = re.compile(r"^pb-[0-9a-f]{12}$")


def _program(tmp_path, **kw):
    return R.playbook_for("program", catalog=_corpus(tmp_path, **kw)).playbook


def test_every_shipped_playbook_has_a_version_that_reads_the_same_twice():
    seen = {}
    for kind in WORK_KINDS:
        answer = R.playbook_for(kind)
        if answer.playbook is None:
            continue
        assert _VERSION.match(answer.playbook.version), (kind, answer.playbook.version)
        assert R.playbook_for(kind).playbook.version == answer.playbook.version
        seen[kind] = answer.playbook.version
    assert seen, "no shipped kind has a playbook — this test is checking nothing"
    assert len(set(seen.values())) == len(seen), seen


def test_the_same_content_from_a_fresh_read_is_the_same_version(tmp_path):
    first = _program(tmp_path / "a")
    again = _program(tmp_path / "b")
    assert first == again and first.version == again.version


@pytest.mark.parametrize("change", ["claim", "stage", "move", "reviewed", "do_nothing"])
def test_anything_the_expert_reads_moves_the_version(tmp_path, change):
    pb = _program(tmp_path)
    if change == "claim":
        moved = dataclasses.replace(pb, claims=(dataclasses.replace(
            pb.claims[0], statement=pb.claims[0].statement + " — usually"),) + pb.claims[1:])
    elif change == "stage":
        stage = pb.stages[0]
        moved = dataclasses.replace(pb, stages=(dataclasses.replace(
            stage, typical=dataclasses.replace(stage.typical, value=stage.typical.value + 1)),)
            + pb.stages[1:])
    elif change == "move":
        moved = dataclasses.replace(pb, moves=(dataclasses.replace(
            pb.moves[0], steps=pb.moves[0].steps + ("follow up once",)),) + pb.moves[1:])
    elif change == "reviewed":
        moved = dataclasses.replace(pb, reviewed=not pb.reviewed,
                                    review_label=None if not pb.reviewed else R.REVIEW_LABEL)
    else:
        moved = dataclasses.replace(pb, do_nothing_consequence="the window closes")
    assert moved.version != pb.version


def test_a_review_the_expert_cannot_see_does_not_move_the_version(tmp_path):
    """A spine a human reviewed on a capability not admitted is still read as unreviewed (both halves
    of the ceremony, `test_a_file_reads_its_playbook`) — the expert is shown the same playbook, so it is
    the same version. What the expert is shown is what a version is of."""
    unreviewed = _program(tmp_path / "a")
    reviewed_spine = _program(tmp_path / "b", spine_reviewed=True)
    assert reviewed_spine.reviewed is False and reviewed_spine.as_dict() == unreviewed.as_dict()
    assert reviewed_spine.version == unreviewed.version


def test_the_read_model_carries_its_version_and_the_version_is_of_the_rest(tmp_path):
    from genios_engine.platform.canonical import semantic_hash
    shape = R.playbook_for("program", catalog=_corpus(tmp_path)).as_dict()
    assert json.loads(json.dumps(shape)) == shape
    body = dict(shape["playbook"])
    version = body.pop("version")
    assert version == "pb-" + semantic_hash(body)[:12]
