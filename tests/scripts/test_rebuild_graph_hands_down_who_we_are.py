"""STEP-04 · `scripts/rebuild_graph.py` replays the graph with the whole answer to "who is us".

    pytest tests/scripts/test_rebuild_graph_hands_down_who_we_are.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U21`, found by U16's report. The live drain hands the pipeline
`platform/self_identity.identity_for` — the addresses AND the domains the tenant declared — and the
pipeline keeps our company out of the anchors by the domains (U16). The rebuild script replayed every
event through the same `_safe_process_one` with the addresses alone, so a rebuilt graph anchored the
situations the live drain keeps out. Checked by the AST: the script cannot be run in a test — it
wipes a tenant's graph.
"""
from __future__ import annotations

import ast
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "rebuild_graph.py"


def _calls(name: str) -> list[ast.Call]:
    tree = ast.parse(SCRIPT.read_text())
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and (getattr(n.func, "id", None) == name or getattr(n.func, "attr", None) == name)]


def test_the_replay_hands_the_pipeline_the_identity():
    [call] = _calls("_safe_process_one")
    assert "self_identity" in {k.arg for k in call.keywords}, (
        "the rebuild replays without the declared domains — our company anchors again")


def test_the_identity_is_read_once_from_the_one_answer():
    assert len(_calls("identity_for")) == 1
    assert not _calls("_internal_emails"), "a second reading of who we are, beside the identity"
