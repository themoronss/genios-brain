"""Decision Brief — deterministic composition, Law 08 honesty, and THE BOUNDARY:
a brief never carries who/when/channel (that's Layer 6)."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

from genios_engine.executive.brief import BRIEF_VERSION, compose_brief
from genios_engine.executive.validate import validate_text
from genios_engine.reason.foresight import play_stat_key

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)

# play stats are keyed by (pack_id, pack_version, play_id) — a play's measured win rate
# under pack v1.7 is not evidence about v2.0 (the L4 authority integration's key shape).
_PLAY_KEY = play_stat_key("sales", "1.7.0", "follow_up")


def _brief(**over):
    signal = {"signal_id": "sig_1", "rule_id": "stalled_deal", "level": "prescriptive",
              "subject_node_id": "n1", "score": 73,
              "score_inputs": {"U": 90, "I": 50, "R": 100, "C": 77},
              "reason_code": "stalled_deal", "evidence": [], "play": "follow_up",
              "pack_id": "sales", "pack_version": "1.7.0",
              "eval_time": NOW.isoformat(), "open_discrepancies": 0}
    signal.update(over.pop("signal", {}))
    kw = dict(signal=signal,
              facts={"deal.value": {"value": "25500"},
                     "thread.ball_in_court": {"value": "us"}},
              entity_name="Chat360",
              play_stats={_PLAY_KEY: {"wins": 7, "n": 11, "rate_lb": 0.35}},
              templates={}, scoring_cfg={}, eval_time=NOW)
    kw.update(over)
    return compose_brief(**kw)


def test_brief_shape_and_determinism():
    a, b = _brief(), _brief()
    assert a == b                                       # same inputs, byte-same brief
    assert a["version"] == BRIEF_VERSION
    assert a["recommendation"]["verb"] == "do"          # prescriptive, high band, C=77
    assert a["band"] == "high" and a["mode"] == "proactive"
    assert a["grounded"] is True


def test_law_08_small_n_play_says_new_never_a_percentage():
    b = _brief(play_stats={_PLAY_KEY: {"wins": 2, "n": 3, "rate_lb": 0.2}})
    measured = b["recommendation"]["play"]["measured"]
    assert measured == {"label": "new play — no data yet", "n": 3}
    ok = _brief()["recommendation"]["play"]["measured"]
    assert ok == {"win_rate_lb_pct": 35, "n": 11}       # ≥5 obs → the honest Wilson bound
    # stats from a DIFFERENT pack version are not evidence about this one
    other = _brief(play_stats={play_stat_key("sales", "2.0.0", "follow_up"):
                               {"wins": 7, "n": 11, "rate_lb": 0.35}})
    assert other["recommendation"]["play"]["measured"]["n"] == 0


def test_risks_come_only_from_stored_truth():
    b = _brief(signal={"open_discrepancies": 2})
    assert any("conflict" in r for r in b["risks"])
    assert any("ball is in our court" in r for r in b["risks"])
    none = _brief(facts={"deal.value": {"value": "25500"}}, signal={"open_discrepancies": 0})
    assert none["risks"] == []                          # nothing stored → nothing claimed


def test_pack_template_words_win():
    b = _brief(templates={"stalled_deal": {"fallback": {"situation": "{entity} went quiet"}}})
    assert b["situation"] == "Chat360 went quiet"


def test_boundary_no_owner_channel_or_schedule_fields():
    b = _brief()
    forbidden = {"assignee", "owner", "channel", "notify_at", "push", "delegate_to", "tool"}
    assert not (forbidden & set(b)), "who/when/where belongs to Layer 6, never the brief"


def test_executive_never_imports_deliver():
    """Ratchet double-check at the source level: layer 5 must not import layer 6."""
    root = Path(__file__).resolve().parents[1] / "genios_engine" / "executive"
    for py in root.rglob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for m in mods:
                assert not m.startswith("genios_engine.deliver"), f"{py.name} imports deliver"


def test_validator_blocks_ungrounded_render():
    facts = {"deal.value": {"value": "25500"}, "close": {"value": "2026-08-15"}}
    ok, _ = validate_text("Deal worth 25500 closes August 15", facts)
    assert ok
    bad, tok = validate_text("Deal worth 99000 closes March 15", facts)
    assert not bad and tok == "number:99000"
    bad2, tok2 = validate_text("Call Priya about it", facts)
    assert not bad2 and tok2 == "name:Priya"
