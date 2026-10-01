r"""L5 STEP-01 · the lane reaches the card — and an unrouted card says so.

⛔ WHY THIS FILE EXISTS. `layer-2-reasoning/STEP-05` added `OutputLane`, routed every decision,
migrated two columns onto `signals` and wrote them. Then:

    grep -rn "output_lane\|lane_reason" genios_engine/deliver/   ->   nothing

Built, tested, green, called by nothing — in the vocabulary added one step earlier to end a
different instance of that. These tests are what make a future deletion of the reader fail.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from genios_engine.contracts.reasoning import OUTPUT_LANES, OutputLane
from genios_engine.deliver import lane_display
from genios_engine.deliver.lane_display import (LANE_COPY, TALLY_KEYS, UNROUTED, describe,
                                                tally_lane)

REPO = pathlib.Path(__file__).resolve().parents[2]


# ── the vocabulary is total, both directions ──────────────────────────────────────────────────

@pytest.mark.parametrize("lane", sorted(OUTPUT_LANES))
def test_every_lane_a_router_can_return_has_words_a_founder_can_read(lane):
    """A lane with no copy renders as a bare enum value on a surface a founder reads."""
    copy = LANE_COPY[lane]
    assert copy.strip()
    # ⛔ AN EARLIER VERSION OF THIS ASSERTION WAS ITSELF A BLUNT CHECK ON TEXT: it demanded the
    # lane's own word be ABSENT from its copy, and of course "a decision — GeniOS has a move"
    # contains the word "decision". The property that actually matters is that the copy is not
    # merely the machine value handed to a human.
    assert copy != lane.value
    assert len(copy) > len(lane.value) + 10, (
        f"{lane}: {copy!r} is the machine value dressed up, not an explanation")


def test_the_copy_table_holds_nothing_that_is_not_a_lane():
    """The other direction. A typo here is a label no card can ever reach."""
    assert set(LANE_COPY) - {UNROUTED} == set(OUTPUT_LANES)


def test_unrouted_is_a_word_and_not_a_missing_key():
    """⛔ Every downstream reader — a count, a filter, a group-by — treats a missing key
    differently from a present one, and "nobody routed this" must survive all three alike."""
    assert isinstance(UNROUTED, str) and UNROUTED
    assert UNROUTED not in OUTPUT_LANES, "unrouted must not be smuggled into the router's own set"


# ── the read is total, and never guesses ──────────────────────────────────────────────────────

@pytest.mark.parametrize("lane", sorted(OUTPUT_LANES))
def test_a_routed_signal_keeps_its_lane_and_its_reason(lane):
    seen = describe(lane, "because the router said so")
    assert seen.lane == lane
    assert seen.reason == "because the router said so"
    assert seen.routed is True
    assert seen.label == LANE_COPY[lane]


@pytest.mark.parametrize("absent", [None, "", "   "])
def test_a_signal_with_no_lane_is_labelled_not_defaulted(absent):
    """⛔ THE WHOLE RISK OF THE STEP. Defaulting to `decision` would have the card assert the
    authority of a routed decision that no router granted it."""
    seen = describe(absent, None)
    assert seen.lane == UNROUTED
    assert seen.routed is False
    assert seen.lane != OutputLane.DECISION.value


def test_an_unknown_lane_value_is_unrouted_rather_than_raised_on():
    """A card is a read of a row somebody else wrote. Refusing to render it would lose the card."""
    seen = describe("escalation", "a word this layer does not know")
    assert seen.lane == UNROUTED
    assert seen.reason is None, (
        "a reason explaining a route we refused to honour reads on the card as though we had")


@pytest.mark.parametrize("blank", [None, "", "  \n "])
def test_half_a_pair_is_no_route(blank):
    """⛔ `0189` makes the pair atomic in the database because "a card in the wrong lane with no
    recorded reason is undiagnosable". A lane without one is something the writer was not allowed
    to write, and honouring it here would ALSO violate `cards_lane_has_a_reason` on the way in."""
    assert describe(OutputLane.DECISION.value, blank).lane == UNROUTED


def test_suppressed_is_a_question_this_layer_asks_and_does_not_act_on():
    assert describe(OutputLane.SUPPRESS.value, "nothing to do").suppressed is True
    assert describe(OutputLane.DECISION.value, "a move").suppressed is False
    assert describe(None).suppressed is False, "an unrouted card is not a suppressed one"


# ── the counts ────────────────────────────────────────────────────────────────────────────────

def test_the_tally_keys_do_not_collide_with_the_path_name_pipeline_already_writes():
    """⛔ `deliver/pipeline` writes `cards_lane`, meaning which CODE PATH built the card. Two
    nearly identical prefixes over two unrelated vocabularies is how somebody later reads a path
    name as a lane name and reports the wrong number with total confidence."""
    assert all(k.startswith("cards_output_lane_") for k in TALLY_KEYS)
    assert "cards_lane" not in TALLY_KEYS
    assert not any(k == "cards_lane" or k.startswith("cards_lane_") for k in TALLY_KEYS)


def test_every_lane_including_suppress_and_unrouted_is_counted():
    """⛔ "A suppression nobody can see the size of is indistinguishable from a bug that lost
    cards" — `card_source`, one file over."""
    counts: dict = {}
    for lane in sorted(OUTPUT_LANES):
        tally_lane(counts, lane=describe(lane, "the router's reason"))
    tally_lane(counts, lane=describe(None))
    assert sum(counts.values()) == len(OUTPUT_LANES) + 1
    assert counts["cards_output_lane_suppress"] == 1
    assert counts["cards_output_lane_unrouted"] == 1
    assert set(counts) == set(TALLY_KEYS)


def test_a_pass_that_saw_nothing_still_declares_every_key():
    """A key that appears only when it fires is a key nobody knows exists."""
    from genios_engine.deliver import pipeline

    src = inspect.getsource(pipeline.build_cards_for_org)
    assert "**{k: 0 for k in TALLY_KEYS}" in src


# ── the wiring, asserted on structure ─────────────────────────────────────────────────────────

def test_the_selector_actually_reads_the_two_columns():
    src = inspect.getsource(__import__(
        "genios_engine.deliver.pipeline", fromlist=["_open_signals_without_cards"]
    )._open_signals_without_cards)
    assert "s.output_lane" in src and "s.lane_reason" in src, (
        "a lane the selector does not read cannot reach the card, whatever the builder does")


def test_the_builder_puts_the_lane_on_the_card_it_returns():
    """⛔ AST, NOT A GREP. The family rule: assert on structure — the returned mapping's keys —
    never on text that happens to sit near a thing. An earlier version of a test like this matched
    `def _persist_live(` instead of the call to it."""
    from genios_engine.deliver import card_builder

    tree = ast.parse(inspect.getsource(card_builder.build_draft))
    returned: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            returned |= {k.value for k in node.value.keys
                         if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    for field in ("output_lane", "lane_reason", "lane_label"):
        assert field in returned, f"build_draft returns no {field}"


def test_the_insert_lists_as_many_values_as_columns():
    """The store's SQL is Postgres-only (`cast(... as jsonb)`, `xmax`), so it runs under the `pg`
    gate alone. A column/placeholder mismatch is still catchable here, by counting.

    ⛔ REASSEMBLE THE SQL FIRST, THEN SPLIT IT. An earlier version split the Python source on
    `") values ("` and then stripped the comments, which left two interleaved `#` comment lines
    standing where columns should have been and counted them as columns. The fragments are the
    structure; the comments between them are not part of the statement at all.
    """
    import re

    from genios_engine.deliver import store

    src = inspect.getsource(store.CardStore.insert_card)
    sql = " ".join(re.findall(r'"([^"]*)"', src))
    head = sql.split("insert into cards (", 1)[1]
    columns, rest = head.split(") values (", 1)
    # ⛔ Paren-AWARE. `cast(:sb as jsonb)` closes a paren that is not the end of the list, so a
    # split on the first ")" cuts the values list after six of thirty-eight.
    depth, end = 0, len(rest)
    for i, ch in enumerate(rest):
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                end = i
                break
            depth -= 1
    values = rest[:end]
    cols = [c.strip() for c in columns.split(",") if c.strip()]
    vals = [v.strip() for v in values.split(",") if v.strip()]
    assert len(cols) == len(vals), f"{len(cols)} columns, {len(vals)} values"
    assert "output_lane" in cols and "lane_reason" in cols
    assert ":lane" in vals and ":lreason" in vals


def test_the_refresh_can_move_a_card_between_lanes():
    """A re-routed decision must be able to change its card's lane. Carrying the old one forward
    would show a founder a conclusion the engine has since withdrawn."""
    from genios_engine.deliver import store

    src = inspect.getsource(store.CardStore.insert_card)
    on_conflict = src.split("on conflict (signal_id) do update set", 1)[1]
    assert "output_lane=excluded.output_lane" in on_conflict
    assert "lane_reason=excluded.lane_reason" in on_conflict


# ── the migration ─────────────────────────────────────────────────────────────────────────────

def test_the_migration_admits_unrouted_on_cards_and_not_on_signals():
    """⛔ The asymmetry is deliberate. On `signals` a NULL means no router ever looked — a fact
    about the WRITER. On `cards` the layer HAS looked and found nothing it could honour — a fact
    about the READ, and the answer the card displays."""
    cards = (REPO / "migrations/0190_card_lane.sql").read_text()
    signals = (REPO / "migrations/0189_output_lane.sql").read_text()
    assert "'unrouted'" in cards
    assert "'unrouted'" not in signals


def test_the_migration_lets_unrouted_stand_without_a_router_reason():
    """Inventing a sentence to satisfy a constraint would put words in the row no component said."""
    cards = (REPO / "migrations/0190_card_lane.sql").read_text()
    clause = cards.split("cards_lane_has_a_reason\n", 1)[1].split(";", 1)[0]
    assert "output_lane = 'unrouted'" in clause


def test_the_migration_records_the_correction_to_its_predecessor():
    """⛔ `0189`'s header claims the lane is inside `decision_hash`. It was, it broke four replay
    tests, and it was removed — `route` is pure over inputs already in the hash, so the lane adds
    zero information and a derived value has no business in a content hash. A migration cannot be
    edited (its checksum IS its immutability), so the correction is append-only, here."""
    cards = (REPO / "migrations/0190_card_lane.sql").read_text()
    assert "0189" in cards and "decision_hash" in cards


def test_no_model_decides_a_lane_anywhere_in_this_reader():
    """⛔ AST import check, not a grep — grepping for "model" matched a router's own docstring
    once already. §4: "if the output is a number, a route or a permission, no model produces it"."""
    tree = ast.parse(pathlib.Path(lane_display.__file__).read_text())
    imported = {
        (node.module or "") for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any("llm" in m or "anthropic" in m or "openai" in m for m in imported), imported
