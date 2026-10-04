"""Two reads of an unchanged graph produce the same slice — whatever order the rows arrive in.

    pytest tests/context/test_a_slice_identity_cannot_depend_on_row_order.py -q

⛔ WHY THIS FILE EXISTS. Measured on the design partner's org, 2026-10-04: `expertise_packages`
held THREE rows per situation in three hours, each ~118 kB, each with a fresh `expertise_id`. A
field-by-field diff of two consecutive payloads for one situation found EXACTLY TWO differences:

    .metadata.context_slice_hash   879267ec…  vs  c91d26e7…
    .id                            expertise_a4795afc…  vs  expertise_800944fa…   (derived from it)

Everything else — objects, capabilities, expert_rules, evidence — was byte-identical, and NO graph
table had a single row written between the two mints: `graph_facts` 0, `graph_observations` 0,
`graph_edges` 0, `graph_nodes` 0.

⛔ THE CAUSE. Both loaders read `graph_observations` with no ORDER BY. Postgres may return those
rows in a different order on any run — a plan flip, a heap page rewritten by an update, a vacuum.
`build_context_slice` put them in a TUPLE, `canonical_dumps` sorts dict KEYS but preserves LIST
ORDER, and that order reached `semantic_hash` → `metadata.context_slice_hash` → `expertise_id`.
The publisher's `on conflict do nothing` therefore never fired.

⛔ SECOND TIME, SAME COST. `SituationContextSlice.to_semantic_dict`'s docstring records the first:
`graph_version` in the slice's identity reached 4,086 rows and 995 MB — 67% of the database — and
took production into read-only, which stops every write the product makes. That fix removed the
clock. This one removes the row order: the same defect in the other disguise.

⛔ AND THE HAZARD WAS ALREADY KNOWN AT THIS CALL SITE. `neighbor_observations` on the very next
line has been `tuple(sorted(...))` all along. One of the two was sorted and the other was not.
"""

from __future__ import annotations

import random

import pytest

from genios_engine.context.situation_bso import _observation_order
from genios_engine.platform.canonical import canonical_dumps, semantic_hash

pytestmark = pytest.mark.unit

#: The shape both loaders actually select: `{"kind": …, "occurred_at": …}`.
_ROWS = [
    {"kind": "commitment_made", "occurred_at": "2026-09-14T10:00:00+00:00"},
    {"kind": "deadline_stated", "occurred_at": "2026-09-02T08:30:00+00:00"},
    {"kind": "commitment_made", "occurred_at": "2026-09-01T09:15:00+00:00"},
    {"kind": "approval_requested", "occurred_at": "2026-09-20T17:45:00+00:00"},
    {"kind": "deadline_stated", "occurred_at": "2026-09-02T08:30:00+00:00"},  # a true duplicate
]


def _ordered(rows):
    return tuple(sorted(rows, key=_observation_order))


def test_every_arrival_order_yields_one_slice_identity():
    """⛔ THE MUTATION THIS FILE REJECTS: dropping the sort in `build_context_slice`. The database
    is free to hand these rows over in any order, and each order used to mint its own package."""
    hashes = set()
    rng = random.Random(20261004)
    for _ in range(200):
        shuffled = _ROWS[:]
        rng.shuffle(shuffled)
        hashes.add(semantic_hash({"observations": _ordered(shuffled)}))
    assert len(hashes) == 1, (
        f"{len(hashes)} distinct slice identities for ONE unchanged set of observations — every "
        "one of them mints a fresh ~118 kB expertise package that nothing asked for")


def test_the_reverse_of_a_sorted_list_is_the_same_slice():
    """The adversarial case, named: the database returning the exact opposite order."""
    assert _ordered(_ROWS) == _ordered(list(reversed(_ROWS)))


def test_duplicates_are_kept_not_collapsed():
    """⛔ Sorting must not become de-duplication. Two identical observations are two observations;
    silently dropping one would change what the slice SAYS, which is a different bug from the one
    being fixed and a far worse one."""
    assert len(_ordered(_ROWS)) == len(_ROWS)


def test_list_order_really_does_change_the_hash():
    """The premise, asserted — so this file cannot pass vacuously if canonicalisation ever starts
    sorting lists on its own and the sort above is then deleted as redundant."""
    a = semantic_hash({"observations": [{"kind": "a"}, {"kind": "b"}]})
    b = semantic_hash({"observations": [{"kind": "b"}, {"kind": "a"}]})
    assert a != b, (
        "canonical_dumps now sorts list order; re-read this file before removing anything, "
        "because its whole argument rests on list order being significant")


def test_dict_key_order_does_not_change_the_hash():
    """The other half of the premise: keys are already sorted, so only ORDER was ever the hazard."""
    assert (semantic_hash({"kind": "a", "occurred_at": "x"})
            == semantic_hash({"occurred_at": "x", "kind": "a"}))


def test_rows_identical_in_both_fields_still_get_a_total_order():
    """A key that ties on `kind` and `occurred_at` must still break the tie deterministically,
    or the sort is stable-but-input-dependent and the churn survives in a narrower form."""
    tied = [{"kind": "k", "occurred_at": "t", "extra": 2},
            {"kind": "k", "occurred_at": "t", "extra": 1}]
    assert _ordered(tied) == _ordered(list(reversed(tied)))


def test_the_sort_key_is_canonical_not_a_python_repr():
    """`canonical_dumps` is the tiebreak, not `str(dict)`: dict repr follows insertion order, so a
    repr-based tiebreak would reintroduce exactly the dependence this file exists to remove."""
    one = {"kind": "k", "occurred_at": "t", "a": 1, "b": 2}
    other = {"b": 2, "a": 1, "occurred_at": "t", "kind": "k"}
    assert str(one) != str(other), "the two dicts must differ by repr for this test to mean anything"
    assert _observation_order(one) == _observation_order(other)
    assert canonical_dumps(one) == canonical_dumps(other)


def test_every_observation_read_either_orders_or_cannot_care():
    """The cheaper half of the fix, asserted on the SQL itself.

    ⛔ NOT "every read must be ordered". `reason/runner` has three reads of `graph_observations`
    and only two of them can affect a hash: those two build a LIST, whose order is preserved by
    `canonical_dumps`. The third collects `kind` into a SET — order is unobservable there, and
    demanding an ORDER BY would be paying a sort for nothing.

    So the rule asserted is the real one: a read whose rows land in a list is ordered; a read
    whose rows land in a set need not be. A new read that lands in a list and is unordered fails
    here, which is exactly the regression that cost 118 kB a sweep — and it is also what this
    test caught on its first run, a third read neither I nor the fix had noticed.
    """
    import inspect

    from genios_engine.reason import runner

    source = inspect.getsource(runner)
    starts = [i for i in range(len(source))
              if source.startswith("from graph_observations", i)]
    assert len(starts) == 3, (
        f"expected 3 graph_observations reads in reason/runner, found {len(starts)} — a read was "
        "added or moved; decide for the new one whether its row order can reach a hash")

    for start in starts:
        window = source[start:start + 520]
        lands_in_a_set = ".add(" in window
        assert lands_in_a_set or "order by" in window, (
            "a graph_observations read builds a LIST and has no ORDER BY; that list is hashed "
            "into the slice identity, and an unordered read re-mints a ~118 kB expertise "
            "package every sweep for knowledge that never changed")


def test_the_slice_itself_sorts_not_merely_the_helper():
    """⛔ THE MUTATION EVERY TEST ABOVE MISSES, AND THE REASON THIS ONE IS ON THE AST.

    Every assertion above calls `_observation_order` directly. Deleting the `sorted(...)` at
    `build_context_slice`'s call site therefore leaves them all green while putting the whole
    defect back — verified by doing exactly that: 8 passed. A test that cannot fail on the change
    it exists to prevent is decoration.

    So this reads the FUNCTION, and asserts the keyword argument the slice is actually built with.
    """
    import ast
    import inspect
    import textwrap

    from genios_engine.context import situation_bso

    tree = ast.parse(textwrap.dedent(inspect.getsource(situation_bso.build_context_slice)))
    call = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "SituationContextSlice"), None)
    assert call is not None, "build_context_slice no longer constructs a SituationContextSlice"

    by_name = {kw.arg: kw.value for kw in call.keywords}
    assert "observations" in by_name, "the slice is built without an `observations` argument"

    sorted_calls = {c.func.id for c in ast.walk(by_name["observations"])
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "sorted" in sorted_calls, (
        "`observations` reaches the slice unsorted again — the database's row order becomes the "
        "slice's identity, and every sweep mints a fresh ~118 kB expertise package for knowledge "
        "that has not changed")

    # And the neighbour beside it, which was right all along and is the reason this was findable.
    assert "neighbor_observations" in by_name
    assert "sorted" in {c.func.id for c in ast.walk(by_name["neighbor_observations"])
                        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
