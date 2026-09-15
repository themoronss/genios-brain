"""95 of 95 dependency claims had neither end resolve, and the correlator was right to refuse.

`correlation_dependency` will not invent a node for an endpoint the identity cascade cannot match
— "a false chain is worse than a missing one" — and Layer 1 extracts dependencies between
OUTCOMES: "Shortlisting and showcase participation", "interview slot offer for GeniOS", "Meeting
between Sehan and Rohit". Measured on the live tenant, every claim was dropped `UNRESOLVED_BLOCKED`
and the whole dependency lane produced nothing.

THIS DOES NOT RELAX THE RULE. Nothing is resolved, nothing is joined, no node is minted and no
edge appears. The two ends travel as the TEXT they were written as; what anchors them is the
party whose THREAD carried the sentence — a node the graph already held, because the message was
addressed to somebody. `chains`, `circular_wait` and `blocked_count` never see any of this.

The two tests that matter are `test_only_the_both_ends_unresolved_case_is_taken` — the other drop
reasons are refusals this lane must not quietly undo — and
`test_neither_end_is_ever_presented_as_identified`, which is what stops a quoted sentence turning
into a claimed relationship one renderer later.
"""
from datetime import datetime, timezone

import pytest

from genios_engine.context.stated_dependency import (ANCHOR_STATED, MAX_PER_SWEEP,
                                                     read_stated_dependencies, statement_key)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
PERSON = "n_sehan"
NAMES = {PERSON: "Sehan Sanjula"}


def _stated(blocker="Rohit's availability this week", blocked="Meeting between Sehan and Rohit",
            quote="the meeting depends on Rohit's availability this week", kind="blocks"):
    return {"blocker_text": blocker, "blocked_text": blocked, "dependency_type": kind,
            "quote": quote, "stated_at": "2026-08-30T10:00:00+00:00", "event_id": "evt_1"}


def _rows(*entries, node=PERSON):
    return {node: {"stated": list(entries)}}


def _facts(f):
    return {n: v for n, v, _k in f.facts}


def test_the_sentence_becomes_a_card() -> None:
    [card] = read_stated_dependencies(_rows(_stated()), NOW, NAMES)
    d = _facts(card)
    assert card.anchor == ANCHOR_STATED
    assert card.concerns_node == PERSON
    assert d["dependency_blocked_text" if False else "dependency.blocked_text"] == \
        "Meeting between Sehan and Rohit"
    assert d["dependency.blocker_text"] == "Rohit's availability this week"
    assert "waiting on" in card.display_name


def test_both_ends_are_quoted_exactly_as_written() -> None:
    """Paraphrasing either half is how a DESCRIBED thing turns into a CLAIMED one."""
    card = read_stated_dependencies(
        _rows(_stated(blocker="Theresa Hoffmann's reconsideration",
                      blocked="GeniOS advancement in Antler Singapore")), NOW, NAMES)[0]
    d = _facts(card)
    assert d["dependency.blocker_text"] == "Theresa Hoffmann's reconsideration"
    assert d["dependency.blocked_text"] == "GeniOS advancement in Antler Singapore"


def test_neither_end_is_ever_presented_as_identified() -> None:
    """THE RULE THE CORRELATOR REFUSED TO BREAK, held one layer up. Nothing resolved either end —
    that absence is why this is a sentence and not an edge — so a card implying either had been
    matched would be claiming the resolution the traversal explicitly declined to invent."""
    [card] = read_stated_dependencies(_rows(_stated()), NOW, NAMES)
    assert card.missing == ["dependency.blocker_identity", "dependency.blocked_identity"]
    assert not any(name.endswith(("_node", "_node_id", "_identity")) for name, _v, _k in card.facts)


def test_a_statement_with_one_end_is_not_a_card() -> None:
    """"Something is waiting on something" names nothing a reader can act on, and a card carrying
    one half invites the reader to supply the other."""
    assert read_stated_dependencies(_rows(_stated(blocker="   ")), NOW, NAMES) == []
    assert read_stated_dependencies(_rows(_stated(blocked="")), NOW, NAMES) == []


def test_the_anchor_is_the_thread_not_either_end() -> None:
    """The counterparty may be neither side of the dependency. They are who the sentence was said
    to, which is the one thing the graph actually knows."""
    [card] = read_stated_dependencies(_rows(_stated()), NOW, NAMES)
    assert _facts(card)["dependency.counterparty"] == "Sehan Sanjula"
    assert card.concerns_node == PERSON


def test_the_same_statement_is_the_same_card_next_sweep() -> None:
    a = read_stated_dependencies(_rows(_stated()), NOW, NAMES)[0]
    b = read_stated_dependencies(_rows(_stated()), NOW, NAMES)[0]
    assert a.canonical_key == b.canonical_key
    assert statement_key(PERSON, " Rohit's Availability This Week ",
                         "meeting between sehan and rohit") == \
           statement_key(PERSON, "Rohit's availability this week",
                         "Meeting between Sehan and Rohit")


def test_a_free_text_end_cannot_break_the_canonical_key() -> None:
    """Both ends are free text out of somebody's sentence, and a canonical key is split on a
    delimiter elsewhere in this layer."""
    [card] = read_stated_dependencies(_rows(_stated(blocker="legal: the india entity")), NOW, NAMES)
    assert card.canonical_key.count(":") == 1


@pytest.mark.parametrize("value", ["not json", "[]", '{"stated": "x"}', 42, None, {}])
def test_a_malformed_row_costs_one_statement_not_the_tenant(value) -> None:
    assert read_stated_dependencies({PERSON: value}, NOW, NAMES) == []


def test_one_sweep_cannot_become_a_feed() -> None:
    many = [_stated(blocked=f"outcome {i}") for i in range(MAX_PER_SWEEP + 6)]
    assert len(read_stated_dependencies(_rows(*many), NOW, NAMES)) == MAX_PER_SWEEP


# ── the correlator side ──────────────────────────────────────────────────────────────────────

def test_only_the_both_ends_unresolved_case_is_taken() -> None:
    """THE OTHER DROP REASONS ARE REFUSALS AND MUST STAY REFUSED. `NO_EVIDENCE` is a claim with no
    receipt; `SELF_LOOP` and `RESOLVED` are claims the traversal understood and correctly
    declined; `UNRESOLVED_BLOCKER` already has its own typed absence in `missing_prerequisite`,
    where the waiting party IS known. Widening this lane to any of them would undo a refusal
    somebody made on purpose."""
    import inspect

    from genios_engine.context import correlation_dependency as cd

    src = inspect.getsource(cd._stated_rows)
    assert "DropReason.UNRESOLVED_BLOCKED" in src
    for other in ("NO_EVIDENCE", "SELF_LOOP", "RESOLVED", "UNRESOLVED_BLOCKER"):
        assert f"DropReason.{other}" not in src, other


def test_no_edge_or_node_is_minted_for_a_stated_dependency() -> None:
    """The module's own rule, checked where it could be broken: this lane writes a FACT and
    nothing else — no `find_or_create_node`, no edge write."""
    import inspect

    from genios_engine.context import correlation_dependency as cd

    src = inspect.getsource(cd._stated_rows)
    for forbidden in ("find_or_create_node", "write_edge", "edge_type", "resolve("):
        assert forbidden not in src, forbidden


def test_the_anchor_routes_and_is_dispatched() -> None:
    from genios_engine.context.domain_spec import domains_declaring, spec_for
    from genios_engine.context.outreach_situations import READINGS

    assert domains_declaring(ANCHOR_STATED) == ("admin",)
    assert spec_for("admin").type_for(ANCHOR_STATED) == "dependency_stated"
    assert ANCHOR_STATED in {a for a, _ in READINGS}
