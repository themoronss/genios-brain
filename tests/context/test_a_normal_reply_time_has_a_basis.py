"""The one adaptive gate in the layer was set on 0 of 453 nodes.

`party.reply_cadence_days` is the median gap between a person's own replies, and it needed TWO
replies from that same person. The test is right — one reply is an anecdote — and it is almost
never satisfiable: in a fundraise nobody replies twice. Measured on the live tenant, not one
counterparty had it.

So every reading built on "later than THEIR normal" was permanently false, and the cohort card
reported "0 people past their usual reply time" — which reads as good news rather than as no
measurement. `read_outreach_cohorts` already records the shape of that failure in its own comment:
a zero means two completely different things and the card printed the wrong one.

THE FIX WIDENS THE MEASUREMENT RATHER THAN WEAKENING THE TEST. Two gaps still describe a habit at
every level; what changes is whose gaps may answer. A person with two replies keeps their own
median; failing that their FIRM answers, because two partners at one fund behave more like each
other than like a stranger; failing that the tenant's own median. The floor is not a cadence and
is never written as one.

`party.reply_cadence_basis` IS WHAT KEEPS IT HONEST, and most of this file is about that. "They
usually reply in two days" and "people at this firm usually do" are different claims. A card
holding only the number will make the first on the evidence of the second.
"""
import pytest

from genios_engine.context.waiting import (CADENCE_FIRM, CADENCE_FLOOR, CADENCE_FLOOR_DAYS,
                                           CADENCE_PERSON, CADENCE_TENANT, MIN_GAPS_FOR_CADENCE,
                                           cadence_for)


def test_a_person_with_a_habit_keeps_their_own_number() -> None:
    days, basis = cadence_for("p", {"p": [2.0, 4.0], "q": [30.0, 30.0]}, {})
    assert (days, basis) == (3.0, CADENCE_PERSON)


def test_one_reply_is_still_an_anecdote() -> None:
    """The original rule, unchanged. What changes is that failing it no longer means silence."""
    _days, basis = cadence_for("p", {"p": [9.0]}, {})
    assert basis != CADENCE_PERSON


def test_a_firm_answers_for_somebody_who_has_not_replied_twice() -> None:
    """THE CASE THAT UNBLOCKS THE FUNDRAISE. Two partners at one fund, one reply each — neither
    describes a habit alone, together they describe the firm's."""
    gaps = {"harshita": [4.0], "vidushi": [6.0]}
    firms = {"harshita": "peakxv", "vidushi": "peakxv"}
    assert cadence_for("harshita", gaps, firms) == (5.0, CADENCE_FIRM)
    assert cadence_for("vidushi", gaps, firms) == (5.0, CADENCE_FIRM)


def test_a_firm_with_one_reply_between_everyone_is_still_an_anecdote() -> None:
    """Pooling is not a way around the habit test — it is a way to satisfy it honestly."""
    _days, basis = cadence_for("solo", {"solo": [7.0]}, {"solo": "tinyco"})
    assert basis != CADENCE_FIRM


def test_a_stranger_falls_to_the_tenants_own_median() -> None:
    gaps = {"a": [2.0], "b": [6.0], "stranger": []}
    assert cadence_for("stranger", gaps, {"a": "x", "b": "y"}) == (4.0, CADENCE_TENANT)


def test_a_tenant_with_no_replies_at_all_gets_the_floor() -> None:
    days, basis = cadence_for("anyone", {}, {})
    assert (days, basis) == (CADENCE_FLOOR_DAYS, CADENCE_FLOOR)


def test_the_floor_is_never_written_as_a_cadence() -> None:
    """THE RULE THAT STOPS THE CASCADE BECOMING AN INVENTION. A number with no evidence behind it
    is indistinguishable from a measured one the moment it leaves the function, and every reading
    downstream compares against it. `compute_waiting` writes nothing when the basis is the floor.
    """
    import ast
    import inspect

    from genios_engine.context import waiting

    src = inspect.getsource(waiting.compute_waiting)
    tree = ast.parse(src.lstrip())
    writes = [n for n in ast.walk(tree) if isinstance(n, ast.If)
              and "CADENCE_FLOOR" in ast.dump(n.test)
              and any("reply_cadence_days" in ast.dump(b) for b in n.body)]
    assert writes, ("compute_waiting must guard the cadence write on the basis not being the "
                    "floor — otherwise a no-evidence default is written as a measurement")


def test_the_person_is_not_excluded_from_their_own_firm() -> None:
    """Their one reply is evidence about the firm even when it cannot describe them."""
    gaps = {"a": [10.0], "b": [10.0]}
    assert cadence_for("a", gaps, {"a": "f", "b": "f"}) == (10.0, CADENCE_FIRM)


@pytest.mark.parametrize("basis", [CADENCE_PERSON, CADENCE_FIRM, CADENCE_TENANT, CADENCE_FLOOR])
def test_every_basis_is_a_distinct_named_level(basis: str) -> None:
    assert isinstance(basis, str) and basis
    assert len({CADENCE_PERSON, CADENCE_FIRM, CADENCE_TENANT, CADENCE_FLOOR}) == 4


def test_the_habit_floor_is_shared_by_every_level() -> None:
    """A firm median built from one reply would be the same invented normal as a person's."""
    assert MIN_GAPS_FOR_CADENCE == 2


def test_the_card_carries_which_level_answered() -> None:
    """Without this the widening becomes a quiet overclaim: the card would say "their normal"
    while holding the tenant's."""
    import inspect

    from genios_engine.context import outreach_situations

    src = inspect.getsource(outreach_situations)
    assert "outreach.their_normal_reply_basis" in src
    assert "party.reply_cadence_basis" in src


# ── the column is jsonb, and `repr` is not a JSON encoder ────────────────────────────────────

def test_a_string_valued_state_field_is_written_as_json() -> None:
    """THE BUG THIS UNIT SHIPPED AND THE SWEEP FOUND. `compute_waiting` wrote every non-bool value
    with `repr(value)` and the type `"number"`. That is correct for a number — `repr(2.5)` is
    `2.5`, which is valid JSON — and wrong for everything else: `repr("person")` is `'person'`,
    and Postgres rejects it with *invalid input syntax for type json, Token "'" is invalid*.

    Every value this pass wrote had been numeric since it was written, so the line was correct
    until `party.reply_cadence_basis` arrived and took down the ENTIRE waiting pass on the first
    sweep that carried a string. Encoded by type now, and asserted here because the failure is
    invisible to every SQLite test in the suite — SQLite has no jsonb and accepts the bad string.
    """
    import ast
    import inspect

    from genios_engine.context import waiting

    src = inspect.getsource(waiting.compute_waiting)
    assert "repr(value)" not in src, "repr is not a JSON encoder"

    tree = ast.parse(src.lstrip())
    dumps = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "dumps"]
    assert dumps, "state values must be JSON-encoded before reaching a jsonb column"


def test_the_basis_is_written_with_a_string_value_type() -> None:
    """A `"number"` type on a string value is the other half of the same defect: a reader that
    trusts the declared type would parse it as one."""
    import inspect

    from genios_engine.context import waiting

    src = inspect.getsource(waiting.compute_waiting)
    assert '"string"' in src, "a non-numeric state value must declare its type"
