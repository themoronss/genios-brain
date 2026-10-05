"""A unit id must be addressable — the collision `tree.yaml` carries, and the rule that answers it.

    pytest tests/test_tree_ids_are_addressable.py -q

⛔ THE DEFECT. `tree.yaml` holds five programme blocks and three of them number milestones from M8, so
`M11.C1.L-logic.V0.U01` exists twice with different meanings. Every later stage — build, crosscheck,
QA, trace — addresses work by unit id, and an ambiguous id makes that addressing a guess.

⛔ THE FIX IS A RULE, NOT A RENUMBER, and these tests hold the rule rather than the numbers:

  * an id is RETIRED, never reused and never changed — renumbering an older block would rewrite the
    address of work already logged against it
  * ~800 lines of step documents under `speedrun008/YCW27/` say M8–M14 for `atlas_v2_alignment`

Same shape as the layer-vocabulary collision `genios_engine/LAYERS.py` documents, and the same answer:
**always name the namespace, never the digit alone.**
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

_TREE = Path(__file__).resolve().parents[1] / "tree.yaml"


def _blocks() -> dict[str, list[dict]]:
    """{block name: milestones}. The root's own list is the block called `<root>`."""
    data = yaml.safe_load(_TREE.read_text())
    out: dict[str, list[dict]] = {}
    if isinstance(data.get("milestones"), list):
        out["<root>"] = data["milestones"]
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(value.get("milestones"), list):
            out[key] = value["milestones"]
    return out


def _unit_ids(milestones: list[dict]) -> list[str]:
    ids: list[str] = []
    for milestone in milestones:
        for category in milestone.get("categories") or ():
            for layer in category.get("layers") or ():
                for level in layer.get("levels") or ():
                    for unit in level.get("units") or ():
                        if unit.get("id"):
                            ids.append(unit["id"])
    return ids


# =================================================================================================
# 1 · the file parses and the blocks are what we think
# =================================================================================================
def test_the_tree_parses():
    assert yaml.safe_load(_TREE.read_text()) is not None


def test_the_five_programme_blocks_are_present():
    assert set(_blocks()) == {"<root>", "persona_brain_and_layer_repair",
                             "l1_signal_quality_seam", "atlas_v2_alignment", "yc2_w27"}


def test_the_ycw27_block_is_the_one_this_programme_builds():
    ids = {m["id"] for m in _blocks()["atlas_v2_alignment"]}
    assert ids == {"M8", "M9", "M10", "M11", "M12", "M13", "M14"}


# =================================================================================================
# 2 · ⛔ the collision is REAL, and asserted rather than hidden
# =================================================================================================
def test_milestone_ids_collide_across_blocks_and_that_is_recorded():
    """⛔ Asserted in the positive. A test that merely required uniqueness would fail today and tempt
    somebody into a renumber — which is the wrong fix. This states the fact so the rule below has
    something to be a rule about."""
    seen: dict[str, list[str]] = defaultdict(list)
    for block, milestones in _blocks().items():
        for milestone in milestones:
            seen[milestone["id"]].append(block)
    collisions = {mid: blocks for mid, blocks in seen.items() if len(blocks) > 1}
    assert collisions, "if this passes, the collision is gone and this file can be simplified"
    assert set(collisions) >= {"M8", "M9", "M10", "M11", "M12"}


def test_a_unit_id_is_unique_INSIDE_its_own_block():
    """⛔ THE PROPERTY THAT MAKES `<block>/<id>` AN ADDRESS. Ambiguity across blocks is survivable
    because the block names it; ambiguity within one is not survivable at all."""
    for block, milestones in _blocks().items():
        ids = _unit_ids(milestones)
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        assert dupes == [], f"{block} repeats unit ids: {dupes}"


def test_every_block_qualified_id_is_globally_unique():
    """The canonical form, checked end to end: `<block>/<unit id>` must name exactly one thing."""
    qualified = [f"{block}/{uid}"
                 for block, milestones in _blocks().items()
                 for uid in _unit_ids(milestones)]
    assert len(qualified) == len(set(qualified))


# =================================================================================================
# 3 · ⛔ the rule is written where a reader will hit it
# =================================================================================================
def test_the_addressing_rule_is_documented_at_the_top_of_the_tree():
    """An undocumented collision is indistinguishable from a mistake, and the next person renumbers."""
    head = _TREE.read_text()[:4000]
    assert "HOW A UNIT ID IS ADDRESSED" in head
    assert "THE CANONICAL FORM IS" in head
    assert "WHY NOT RENUMBER" in head


def test_the_rule_names_the_precedent_it_follows():
    head = _TREE.read_text()[:4000]
    assert "LAYERS.py" in head
    assert "never the digit alone" in head


# =================================================================================================
# 4 · ⛔ a new block may not widen the collision
# =================================================================================================
def test_no_sixth_block_has_appeared_without_updating_this_guard():
    """⛔ THE FORWARD HALF. Four blocks already collide and that is now documented; a new block added
    silently would collide again with nobody having decided to accept it. Adding one is fine — update
    this test on purpose, and say in the tree why the ids were chosen. The fifth, `yc2_w27`
    (2026-10-05), was added that way: numbered from M16, past every other block."""
    assert len(_blocks()) == 5, (
        "a programme block was added or removed — update the header note in tree.yaml and this test, "
        "deliberately")


def test_the_newest_block_widens_no_collision():
    """⛔ The reason `yc2_w27` could be added: its milestone ids appear in no other block. If a later
    edit gives it an id another block already uses, this fails before the ambiguity ships."""
    blocks = _blocks()
    newest = {m["id"] for m in blocks["yc2_w27"]}
    others = {m["id"] for name, ms in blocks.items() if name != "yc2_w27" for m in ms}
    assert newest and not (newest & others), sorted(newest & others)


#: ⛔ RETIRED IN PLACE. `<root>`'s M1–M7 predate the YCW27 programme; the header note says so and
#: memory records it. Five of its units carry no verify command, and that is not a debt to pay: a
#: retired unit is never built, so a verify for it would be a command nobody will ever run — the
#: same "green and called by nothing" shape this programme keeps finding.
#:
#: Scoping this assertion to LIVE blocks is not weakening it. Applying it to retired work would make
#: it fail forever on five rows nobody may touch, and a permanently red test is a test people learn
#: to ignore.
_RETIRED_BLOCKS = frozenset({"<root>"})


def test_the_retired_block_is_the_one_we_think_it_is():
    """If this ever fails, the exemption below is covering something live."""
    retired = _blocks()["<root>"]
    assert {m["id"] for m in retired} == {"M1", "M2", "M3", "M4", "M5", "M6", "M7"}


def test_every_unit_in_a_LIVE_block_carries_a_verify_command():
    """Unrelated to addressing, and the cheapest place to check it: a unit with no verify is a wish.
    `decompose`'s own rule — write the verify before the description."""
    missing = []
    for block, milestones in _blocks().items():
        if block in _RETIRED_BLOCKS:
            continue
        for milestone in milestones:
            for category in milestone.get("categories") or ():
                for layer in category.get("layers") or ():
                    for level in layer.get("levels") or ():
                        for unit in level.get("units") or ():
                            if not unit.get("verify"):
                                missing.append(f"{block}/{unit.get('id')}")
    assert missing == [], f"units with no verify command: {missing}"
