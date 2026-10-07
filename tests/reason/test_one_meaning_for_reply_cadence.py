"""STEP-10 · one meaning for "reply cadence" — how often a person writes is stored and asked for as
`write_interval`, and their reply time keeps the name.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_one_meaning_for_reply_cadence.py -q

`reason/baselines.py` (tree `yc2_w27_s10 · M29.C1.L-logic.V0.U04`, decision `06` D41). Two numbers
shared one name. `context/waiting.py` writes `party.reply_cadence_days` — THEIR reply latency, from our
outbound to their next inbound. `reason/baselines.py` stored `reply_cadence:<node>` — the median gap
between a person's OWN messages, how often they write — and that is the number every rule written
`{baseline: reply_cadence}` resolved: `general_v1.champion_quiet` and 77 thresholds in 38 corpus files,
authored by people who read the name as a reply time. In golden F15 the founder's own node got 0.04
days (n = 4, measured in STEP-10 §8.1): the gap between his five wave sends.

Now the send interval is stored, routed and asked for as `write_interval`. No reader resolves the old
name — an old `reply_cadence:` row is never read, a rule still written with it gets no baseline — and
the waiting fact keeps its name and its meaning.
"""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from sqlalchemy import text

from genios_engine.context import waiting
from genios_engine.packs.general_v1 import GENERAL_V1
from genios_engine.reason import baselines as B
from genios_engine.reason import runner
from genios_engine.reason.engine import NodeContext, _resolve_value, evaluate
from genios_engine.reason.rules import rule_from_dict

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "Domain Expertise"
VOCABULARY = CORPUS / "_schema" / "vocabulary.yaml"

OLD, NEW = "reply_cadence", "write_interval"
WAITING_FACT = "party.reply_cadence_days"

ORG = "org_s10_write_interval"
NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
PERSON, EMAIL = "p_s10_writer", "writer@cadence.test"
#: Five messages the person WROTE: gaps 6, 6, 6 and 18 days — median 6.0, mean 9.0, so no other
#: statistic can pass for the one the baseline is defined as, and four gaps cross `MIN_SAMPLES`.
WROTE = tuple(NOW - timedelta(days=d) for d in (40, 34, 28, 22, 4))
SEND_INTERVAL, GAPS = 6.0, 4


def _vocabulary() -> dict:
    return yaml.safe_load(VOCABULARY.read_text(encoding="utf-8"))


# ═════ the database: one person who writes every six days ════════════════════════════════════════

@pytest.fixture
def store(pg_store):
    _drop(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                  {"o": ORG, "e": f"owner@{ORG}.test"})
        c.execute(text(
            "insert into graph_nodes (node_id, version, org_id, node_type, canonical_key, "
            "display_name, identity_strength, attributes, valid_from) "
            "values (:n, 1, :o, 'person', :k, 'Writer', 1.0, '{}'::jsonb, :t)"),
            {"n": PERSON, "o": ORG, "k": EMAIL, "t": WROTE[0]})
        for i, at in enumerate(WROTE):
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                " source_object_id, dedup_key, actor, occurred_at, outcome) "
                "values (:e, :o, 'con_s10', 'gmail', 'email_message', :e, :e, "
                " cast(:actor as jsonb), :at, 'emitted')"),
                {"e": f"evt_s10_wrote_{i}", "o": ORG, "actor": f'{{"email": "{EMAIL}"}}',
                 "at": at})
    yield pg_store
    _drop(pg_store)


def _drop(store) -> None:
    with store.engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _stored(store) -> dict[str, tuple]:
    with store.engine.connect() as c:
        return {r.key: (float(r.value), r.sample_size, r.cold_start) for r in c.execute(text(
            "select key, value, sample_size, cold_start from baselines where org_id = :o"),
            {"o": ORG})}


def _row(store, key: str, value: float) -> None:
    with store.engine.begin() as c:
        c.execute(text("insert into baselines (org_id, key, value, sample_size, cold_start) "
                       "values (:o, :k, :v, 9, false) "
                       "on conflict (org_id, key) do update set value = excluded.value"),
                  {"o": ORG, "k": key, "v": value})


# ═════ 1 · the stored number is named for what it is ═════════════════════════════════════════════

def test_how_often_they_write_is_stored_as_the_write_interval(store):
    B.build_baselines(store, ORG, NOW)

    rows = _stored(store)
    assert rows[f"{NEW}:{PERSON}"] == (SEND_INTERVAL, GAPS, False), (
        "the median gap between the person's OWN messages, over four gaps, measured")
    assert not [k for k in rows if k.startswith(f"{OLD}:")], (
        "the send interval is still written under the name of a reply time")


def test_every_reader_hands_the_rules_the_send_interval_under_the_new_name(store):
    """The live reader (`runner._bulk_load_metrics`) and the two single-node ones agree — three
    copies of one mapping, and a name moved in one and not the others is a value written, stored,
    and silently dropped on the way to a rule."""
    B.build_baselines(store, ORG, NOW)

    live, _ = runner._bulk_load_metrics(store, ORG)[PERSON]
    assert live == {NEW: SEND_INTERVAL}
    assert B.load_node_metrics(store, ORG, PERSON)[0] == {NEW: SEND_INTERVAL}
    assert B.load_baselines(store, ORG, PERSON) == {NEW: SEND_INTERVAL}


def test_a_row_still_stored_under_the_old_name_is_never_read(store):
    """⛔ THE ROWS ALREADY IN THE TABLE. A sweep rebuilds every person's baseline before it reads one
    (`runner.run`: `build_baselines`, then `_bulk_load_metrics`), so an old `reply_cadence:` row is
    never needed — and it must never be resolved either, or one release would hold two meanings."""
    B.build_baselines(store, ORG, NOW)
    _row(store, f"{OLD}:{PERSON}", 99.0)
    _row(store, f"{OLD}:n_s10_only_old", 99.0)     # beside no new row, whatever order rows return in

    bulk = runner._bulk_load_metrics(store, ORG)
    assert bulk[PERSON][0] == {NEW: SEND_INTERVAL}, "an old row reached a rule"
    assert bulk.get("n_s10_only_old", ({}, {}))[0] == {}, "an old row reached a rule"
    assert B.load_node_metrics(store, ORG, PERSON)[0] == {NEW: SEND_INTERVAL}
    assert B.load_node_metrics(store, ORG, "n_s10_only_old")[0] == {}
    assert B.load_baselines(store, ORG, PERSON) == {NEW: SEND_INTERVAL}
    assert B.load_baselines(store, ORG, "n_s10_only_old") == {}


def test_every_baseline_the_vocabulary_declares_is_one_the_engine_routes_and_no_other(store):
    """Both directions, against the reader the sweep uses: the corpus may ask only for a baseline
    the engine publishes, and the engine publishes nothing the vocabulary does not declare."""
    declared = set(_vocabulary()["substrate"]["baselines"])
    node = "n_s10_every_name"
    for name in sorted(declared | {OLD, "not_a_baseline"}):
        _row(store, f"{name}:{node}", 1.0)

    routed, _ = runner._bulk_load_metrics(store, ORG)[node]
    assert set(routed) == declared


# ═════ 2 · a rule written with the new name resolves the send interval ═══════════════════════════

def _ctx(baselines: dict, *, heard_days_ago: float) -> NodeContext:
    return NodeContext(
        node_id=PERSON, node_type="person", baselines=baselines,
        facts={"thread.ball_in_court": {"value": "them"},
               "thread.last_inbound": {"value": (NOW - timedelta(days=heard_days_ago)).isoformat()}})


def test_a_rule_written_with_the_new_name_resolves_the_send_interval(store):
    B.build_baselines(store, ORG, NOW)
    live, _ = runner._bulk_load_metrics(store, ORG)[PERSON]

    ctx = _ctx(live, heard_days_ago=1)
    assert _resolve_value(ctx, {"baseline": NEW, "mult": 2, "floor": 1}) == 2 * SEND_INTERVAL


def test_a_rule_still_written_with_the_old_name_gets_only_its_floor(store):
    B.build_baselines(store, ORG, NOW)
    live, _ = runner._bulk_load_metrics(store, ORG)[PERSON]

    ctx = _ctx(live, heard_days_ago=1)
    assert _resolve_value(ctx, {"baseline": OLD, "mult": 2, "floor": 1}) == 1, (
        "the old name resolved a baseline")


def test_champion_quiet_is_judged_against_how_often_they_write(store):
    """The one shipped pack rule that reads the baseline: quiet means 2.5 x their send interval,
    and never before day 10. Six days x 2.5 is 15, so twelve days of silence is NOT quiet for
    this person — it would be, at the floor, if the rule's name resolved nothing."""
    B.build_baselines(store, ORG, NOW)
    live, _ = runner._bulk_load_metrics(store, ORG)[PERSON]
    [quiet] = [rule_from_dict(r) for r in GENERAL_V1["rules"] if r["id"] == "champion_quiet"]

    assert [c["value"]["baseline"] for c in quiet.when if isinstance(c.get("value"), dict)] \
        == [NEW]
    assert not evaluate(_ctx(live, heard_days_ago=12), quiet, NOW), (
        "12 days is under 2.5 x 6 — the rule fired at its floor, so its baseline did not resolve")
    assert evaluate(_ctx(live, heard_days_ago=16), quiet, NOW)


# ═════ 3 · no reader names the old key ═══════════════════════════════════════════════════════════

def _old_key_literals(path: Path, root: Path = REPO) -> list[str]:
    """Every string literal in `path` that IS the old key: the bare name, or a `name:<node>` key —
    an f-string's literal head is its own constant node, so `f"name:{node}"` is seen too. Prose
    that mentions the name is not a reader and is not counted."""
    return [f"{path.relative_to(root)}:{node.lineno}"
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and (node.value == OLD or node.value.startswith(f"{OLD}:"))]


def test_no_engine_module_names_the_old_key():
    sources = sorted((REPO / "genios_engine").rglob("*.py")) + sorted((REPO / "scripts").rglob("*.py"))
    assert len(sources) > 100, "scanned almost nothing — the walk is blind"
    found = [hit for path in sources for hit in _old_key_literals(path)]
    assert found == [], f"a reader still resolves {OLD!r}: {found}"


def test_the_scan_finds_the_old_key_where_it_is_written(tmp_path):
    """The negative control: the scan above passes over a walk that cannot see the key."""
    module = tmp_path / "probe.py"
    module.write_text(f'K = "{OLD}"\nF = f"{OLD}:{{n}}"\nP = "the {OLD} prose"\n'
                      f'D = "{WAITING_FACT}"\n')
    assert _old_key_literals(module, tmp_path) == ["probe.py:1", "probe.py:2"]


def _corpus_baselines() -> dict[str, list[str]]:
    """Every `{baseline: X}` threshold in the corpus -> where it is written."""
    asked: dict[str, list[str]] = {}

    def walk(node, where):
        if isinstance(node, dict):
            if isinstance(node.get("baseline"), str):
                asked.setdefault(node["baseline"], []).append(where)
            for value in node.values():
                walk(value, where)
        elif isinstance(node, list):
            for value in node:
                walk(value, where)

    for path in sorted(CORPUS.rglob("*.yaml")):
        walk(yaml.safe_load(path.read_text(encoding="utf-8")), str(path.relative_to(CORPUS)))
    return asked


def test_no_corpus_rule_asks_for_the_old_name():
    asked = _corpus_baselines()
    assert OLD not in asked, f"still asked for under the old name in {sorted(set(asked[OLD]))}"
    assert NEW in asked, "the corpus asks for the send interval nowhere — the rules did not move"
    assert set(asked) <= set(_vocabulary()["substrate"]["baselines"])


def test_the_vocabulary_declares_the_new_name_and_not_the_old():
    vocabulary = _vocabulary()
    assert NEW in vocabulary["substrate"]["baselines"]
    for section in ("substrate", "planned_substrate"):
        assert OLD not in (vocabulary[section].get("baselines") or ())


# ═════ 4 · their reply time keeps its name and its meaning ═══════════════════════════════════════

def test_the_waiting_fact_keeps_its_name():
    assert WAITING_FACT in _vocabulary()["substrate"]["fact_paths"]
    tree = ast.parse((REPO / "genios_engine/context/waiting.py").read_text(encoding="utf-8"))
    written = [t.slice.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
               for t in n.targets if isinstance(t, ast.Subscript)
               and isinstance(t.slice, ast.Constant)]
    assert WAITING_FACT in written, "`context/waiting.py` no longer writes their reply time"
    # The CODE, not the text: `baselines.py`'s own comments name the waiting fact to say what this
    # number is not, and a text read would fail on that prose.
    module = ast.parse((REPO / "genios_engine/reason/baselines.py").read_text(encoding="utf-8"))
    docstrings = {id(n.body[0].value) for n in ast.walk(module)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    literals = [n.value for n in ast.walk(module) if isinstance(n, ast.Constant)
                and isinstance(n.value, str) and id(n) not in docstrings]
    assert literals, "read no literals — the scan is blind"
    assert not [s for s in literals if "party.reply_cadence" in s], (
        "the two numbers share a module again")


def test_their_reply_time_and_how_often_they_write_are_different_numbers(store):
    """The same person, one outbound from us: they answer five days later and then write every
    six days. Their reply time is 5.0 (waiting); how often they write is 6.0 (baselines)."""
    asked = WROTE[0] - timedelta(days=5)
    timeline = [("out", asked), *(("in", at) for at in WROTE)]
    assert waiting.reply_gaps_of(timeline) == [5.0], "their reply time is our ask -> their answer"

    B.build_baselines(store, ORG, NOW)
    assert _stored(store)[f"{NEW}:{PERSON}"][0] == SEND_INTERVAL
