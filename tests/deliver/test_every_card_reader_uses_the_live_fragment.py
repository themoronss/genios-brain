"""⛔ A new door cannot again reach one reader only — GeniOS-011 S36.U2 (hermetic, AST).

`surfaces-question-and-team-cards-reach-only-the-cards-page`: STEP-13 added the question door to the Cards queue
and nowhere else, and P4's situation door before it, because every other reader of open cards had joined the
DECISION's authority (`reason/authority.AUTHORITATIVE_SIGNAL_PREDICATE`) on its own. A door added in one place
reached one reader.

The doors now live in one fragment, `deliver/store.LIVE_CARD_FROM` (and `PUSH_CARD_FROM`, the decision door alone
that the push lanes declare by `PUSH_CARD_DOORS`). This guard reads the engine's AST: every SQL expression that
reads `cards` and names a door itself — the decision's predicate, `SITUATION_CARD_SQL`, `QUESTION_CARD_SQL`,
`QUESTION_SIGNAL_PREDICATE` — instead of a fragment fails, unless it is DECLARED below with why it reads one door
on purpose. Checked both ways: a declaration nothing matches any more is stale and fails too.

The unit of the scan is the OUTERMOST `+` expression (a statement and its pieces, as `platform/statement_plans`
reads them), inside its enclosing function — never a substring of the file's text.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "genios_engine"

#: The names a statement uses to open a door itself.
DOOR_NAMES = frozenset({"AUTHORITATIVE_SIGNAL_PREDICATE", "SITUATION_CARD_SQL", "QUESTION_CARD_SQL",
                        "QUESTION_SIGNAL_PREDICATE"})
#: The fragments (`deliver/store`): every door, or the push lanes' declared door.
FRAGMENT_NAMES = frozenset({"LIVE_CARD_FROM", "LIVE_CARD_FROM_LOCKED", "PUSH_CARD_FROM"})
#: A statement that reads the cards table (any alias).
READS_CARDS = re.compile(r"\b(?:from|join)\s+cards\s+(?!set\b)[a-z_]+\b", re.IGNORECASE)

#: ⛔⛔ THE READERS THAT OPEN ONE DOOR ON PURPOSE — `{(path, function): why}`. Each is a statement about ONE card
#: (an action, a claim, a re-proof before a send) bound to the authority of the door it names, or the doors' own
#: statements in the module that holds them. A list reader of open cards does not belong here: it reads the fragment.
SINGLE_DOOR_READERS: dict[tuple[str, str], str] = {
    # the doors' own module: each door's statement, and the reads that prove a write under one door's lock
    ("genios_engine/deliver/store.py", "<module>"):
        "FILE_CARD_DOORS asks which door each file card passes — one statement per door, by design",
    ("genios_engine/deliver/store.py", "CardStore.get_authoritative_card"):
        "the card detail tries each door in turn and returns the first that holds (the doors' own reader)",
    ("genios_engine/deliver/store.py", "CardStore.surface_context_match"):
        "a page match surfaces a decision card under the decision's own locks (context_tags are a decision's)",
    ("genios_engine/deliver/store.py", "CardStore.queue"):
        "the Cards queue: one statement per door so each door keeps its own lock set and ranking",
    # one card, acted on, under the authority its action binds to
    ("genios_engine/deliver/actions.py", "ingest_action"):
        "a founder's press proves the card through the door its own action belongs to, under that door's locks",
    ("genios_engine/deliver/verdicts.py", "<module>"):
        "a verdict is bound to the decision (or question) it judges — its pack, rule and run columns",
    ("genios_engine/deliver/agent_api.py", "get_artifact"):
        "an agent fetches a DECISION's rendered artifact by signal; executors act on decisions only",
    ("genios_engine/deliver/agent_api.py", "claim"):
        "a claim hands a decision's authority to an external executor — a question or a situation is no move",
    ("genios_engine/deliver/agent_api.py", "result"):
        "a result closes a claimed decision; only a decision can be claimed",
    ("genios_engine/deliver/outbox.py", "_drain_claimed"):
        "the drain re-proves the QUEUED decision's own run, hash and revision immediately before the POST",
    ("genios_engine/api/intelligence_routes.py", "intelligence_feedback"):
        "feedback is a verdict on the decision's rule (pack, capability, rule columns) — calibration's input",
    # writers of cards: an open signal WITHOUT a live card, by the door its builder writes through
    ("genios_engine/deliver/pipeline.py", "<module>"):
        "the question card builder's selector: an open question signal with NO card yet — a writer, not a reader",
    ("genios_engine/deliver/pipeline.py", "_open_signals_without_cards"):
        "the decision card builder's selector: an open decision signal with NO card yet — a writer, not a reader",
    # a reader whose subject IS a decision
    ("genios_engine/reason/brief_ranking.py", "<module>"):
        "ranks open DECISIONS by their contract decision id and utility — a question or a situation has neither "
        "(not S36.U2's file; the morning brief the dashboard reads is workspace_routes.build_morning_brief)",
}

#: The readers DONE WHEN names — each reads a fragment, and names no door itself.
FRAGMENT_READERS: dict[tuple[str, str], str] = {
    ("genios_engine/api/workspace_routes.py", "build_morning_brief"): "LIVE_CARD_FROM",
    ("genios_engine/api/workspace_routes.py", "context_bundle"): "LIVE_CARD_FROM",
    ("genios_engine/api/intelligence_routes.py", "list_insights"): "LIVE_CARD_FROM_LOCKED",
    ("genios_engine/api/intelligence_routes.py", "dismiss_insight"): "LIVE_CARD_FROM_LOCKED",
    ("genios_engine/mcp/server.py", "_session_cards"): "LIVE_CARD_FROM",
    # Ask's recall: `reason/` may not import `deliver/`, so its statement lives in store (`_LIVE_CARDS_ABOUT`)
    # and the route injects the reader — held by the test below
    ("genios_engine/deliver/store.py", "<module>"): "LIVE_CARD_FROM",
    ("genios_engine/deliver/agent_api.py", "poll_signals"): "PUSH_CARD_FROM",
    ("genios_engine/deliver/push.py", "_card_projection"): "PUSH_CARD_FROM",
    ("genios_engine/deliver/outbox.py", "<module>"): "PUSH_CARD_FROM",
}


def _names(node: ast.AST) -> set[str]:
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            out.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            out.add(sub.attr)
    return out


def _strings(node: ast.AST) -> str:
    return " ".join(sub.value for sub in ast.walk(node)
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str))


def statements(source: str):
    """`(function, names, text)` for every outermost `+` expression (and lone string) of a module."""
    tree = ast.parse(source)
    found = []

    def visit(node: ast.AST, where: str, outer: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = child.name if where == "<module>" else f"{where}.{child.name}"
                visit(child, name, True)
                continue
            is_add = isinstance(child, ast.BinOp) and isinstance(child.op, ast.Add)
            if is_add and outer:
                found.append((where, _names(child), _strings(child)))
                visit(child, where, False)
                continue
            visit(child, where, outer and not is_add)

    visit(tree, "<module>", True)
    return found


def _qualified(where: str) -> str:
    """A method keeps its class (`CardStore.queue`); a nested function is named by its outer function."""
    parts = where.split(".")
    return ".".join(parts[:2]) if parts and parts[0][:1].isupper() else parts[0]


def single_door_readers(root: Path = ENGINE) -> dict[tuple[str, str], int]:
    """Every (path, function) holding a statement that reads `cards` through a door it names itself."""
    hits: dict[tuple[str, str], int] = {}
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        for where, names, text in statements(path.read_text()):
            if READS_CARDS.search(text) and names & DOOR_NAMES and not names & FRAGMENT_NAMES:
                key = (rel, _qualified(where))
                hits[key] = hits.get(key, 0) + 1
    return hits


def test_no_reader_of_cards_opens_a_door_by_itself_undeclared():
    undeclared = sorted(set(single_door_readers()) - set(SINGLE_DOOR_READERS))
    assert not undeclared, (
        "these read `cards` through a door they name themselves, not `deliver/store.LIVE_CARD_FROM` — a door added "
        "later reaches the Cards queue and not them (GeniOS-011 S36.U2). Read the fragment, or declare why one "
        f"door is right in SINGLE_DOOR_READERS:\n  {undeclared}")


def test_every_declaration_still_names_a_single_door_reader():
    stale = sorted(set(SINGLE_DOOR_READERS) - set(single_door_readers()))
    assert not stale, f"declared single-door readers the scan no longer finds (remove them): {stale}"
    assert all(len(why) > 30 for why in SINGLE_DOOR_READERS.values())


def test_every_reader_done_when_names_reads_its_fragment_and_names_no_door():
    by_key: dict[tuple[str, str], list[set[str]]] = {}
    for rel, _function in FRAGMENT_READERS:
        for where, names, _text in statements((ROOT / rel).read_text()):
            by_key.setdefault((rel, _qualified(where)), []).append(names)
    for key, fragment in FRAGMENT_READERS.items():
        used = set().union(*by_key.get(key, [set()]))
        assert fragment in used, f"{key} does not read {fragment}"
        if key[1] != "<module>":
            assert not used & DOOR_NAMES, f"{key} still names a door itself: {used & DOOR_NAMES}"


def test_asks_recall_reads_the_fragment_through_the_reader_its_route_injects():
    import inspect
    from genios_engine.deliver import store
    from genios_engine.reason.moments import recall
    assert store.LIVE_CARD_FROM in store._LIVE_CARDS_ABOUT
    param = inspect.signature(recall.read).parameters["live_cards"]
    assert param.default is inspect.Parameter.empty, "required: a default would be a door chosen by nobody"
    recall_names = set().union(*[n for w, n, _t in statements(inspect.getsource(recall)) if w == "read"])
    assert not recall_names & DOOR_NAMES, "the recall names no door itself"
    calls = [node for node in ast.walk(ast.parse((ENGINE / "api" / "moment_routes.py").read_text()))
             if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "read"]
    handed = {kw.value.id for call in calls for kw in call.keywords
              if kw.arg == "live_cards" and isinstance(kw.value, ast.Name)}
    assert handed == {"_live_cards"}, "the moment route hands recall its live-card reader"
    route = ast.parse((ENGINE / "api" / "moment_routes.py").read_text())
    (helper,) = [n for n in route.body if isinstance(n, ast.FunctionDef) and n.name == "_live_cards"]
    assert any(isinstance(n, ast.Call) and getattr(n.func, "id", None) == "live_cards_about"
               for n in ast.walk(helper)), "which calls store.live_cards_about"


def test_the_push_lanes_declare_their_doors_and_questions_are_not_one():
    from genios_engine.deliver import outbox
    from genios_engine.deliver import store
    assert store.LIVE_CARD_DOORS == ("decision", "situation", "question")
    assert store.PUSH_CARD_DOORS == ("decision",), "a push lane sends a decision only (store.PUSH_CARD_DOORS)"
    assert "question" not in store.PUSH_CARD_DOORS
    assert outbox.PUSHABLE_CARDS_SQL.startswith(store.PUSH_CARD_FROM)
    for door_sql in (store.SITUATION_CARD_SQL, store.QUESTION_CARD_SQL):
        assert door_sql in store.LIVE_CARD_FROM and door_sql in store.LIVE_CARD_FROM_LOCKED
        assert door_sql not in store.PUSH_CARD_FROM


def test_the_scan_catches_a_decision_only_reader():
    """⛔ THE NEGATIVE CONTROL: the shape every reader had before this unit is caught, its fragment form is not."""
    before = ('def feed(c):\n'
              '    return c.execute(text("select k.card_id from cards k join signals s on s.signal_id=k.signal_id "\n'
              '        + AUTHORITATIVE_SIGNAL_JOINS + " where k.org_id=:o and " + AUTHORITATIVE_SIGNAL_PREDICATE))\n')
    after = ('def feed(c):\n'
             '    return c.execute(text("select k.card_id" + LIVE_CARD_FROM + " where k.org_id=:o"))\n')
    (where, names, text), = [s for s in statements(before) if "cards" in s[2]]
    assert where == "feed" and READS_CARDS.search(text) and names & DOOR_NAMES
    assert all(not (names & DOOR_NAMES) for _w, names, _t in statements(after))
