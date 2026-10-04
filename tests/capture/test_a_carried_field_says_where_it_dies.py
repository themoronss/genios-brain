"""⛔⛔ U02 · Atlas L1-09, and a rule this contract states about itself.

The Atlas claim is *"the coverage snapshot is not mandatory on each emitted signal"*, and it is
true: `GatedEvent.coverage_ready` is `bool | None = None`, `qualified_signals.coverage_ready` is a
nullable boolean. **Receipt 47** turns the contract's own promise about it — *"a freshly gated event
always carries a real bool"* — into a production check, with the horizon derived from the sweep
tick because the same comment says an OLD row is legitimately null.

⛔⛔ And measuring that turned up something larger. `coverage_ready`'s comment states a rule:

    A dead field on a contract is worse than a missing one: IT INVITES A CONSUMER TO TRUST A SEAM
    THAT CARRIES NOTHING.

**Five of this object's own twenty-one fields break it** — set on the boundary object and then read
by nothing, stored in no column, absent from the declared envelope key set. `degraded_compile` is
the worst, because its own comment says this exact defect was fixed: the fix moved the field onto
`GatedEvent` and stopped, and L2 reads the STORED signal.

⛔ HOW THE SWEEP ERRS, STATED BECAUSE A RESOLVER THAT HIDES ITS DIRECTION READS AS A PROOF. It
counts attribute loads named `X` anywhere in the engine, which **over-counts**: a load may be on a
different object. So **0 loads proves never-read**, and more than 0 proves nothing. Four of the five
are proven by the sweep; `degraded_compile`'s two loads are pinned here to the tagging object
instead. ⛔ A first version excluded the carrying module, **under**-counted, and produced two false
positives.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from genios_engine.capture.esqe.signal_store import ENVELOPE_KEYS
from genios_engine.contracts.gated_event import CARRIED_BUT_NOT_PERSISTED, GatedEvent
from genios_engine.platform import receipt_coverage as C
from genios_engine.platform import receipts as R

CLAIM = "every recently qualified signal carries a coverage verdict"
ENGINE = Path(R.__file__).resolve().parent.parent
REPO = ENGINE.parent
GATED = ENGINE / "contracts" / "gated_event.py"


def _receipt(org=None):
    found = [r for r in R.receipts(org) if r.claim == CLAIM]
    assert len(found) == 1, f"expected one receipt claiming {CLAIM!r}, got {len(found)}"
    return found[0]


def _schema_columns() -> set[str]:
    sql = "\n".join(p.read_text(encoding="utf-8") for p in sorted((REPO / "migrations").glob("*.sql")))
    return set(re.findall(r"^\s*([a-z_]+)\s+(?:text|jsonb|boolean|integer|timestamptz)", sql, re.M))


def _attribute_loads() -> dict[str, list[tuple[str, int, str]]]:
    """`{attr: [(module, line, the value it is loaded off)]}` — OVER-counting, by design."""
    out: dict[str, list[tuple[str, int, str]]] = {}
    for path in sorted(ENGINE.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                                     # pragma: no cover
            continue
        rel = path.relative_to(ENGINE).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                out.setdefault(node.attr, []).append((rel, node.lineno,
                                                      ast.unparse(node.value)))
    return out


# --------------------------------------------------------------- the declaration, both ways

def test_the_table_is_not_empty():
    """⛔ An empty table makes every assertion over it vacuous."""
    assert len(CARRIED_BUT_NOT_PERSISTED) >= 5, sorted(CARRIED_BUT_NOT_PERSISTED)


def test_every_declared_field_is_actually_on_this_contract():
    unknown = sorted(set(CARRIED_BUT_NOT_PERSISTED) - set(GatedEvent.model_fields))
    assert not unknown, f"declared fields that `GatedEvent` does not have: {unknown}"


def test_no_carried_dead_field_is_undeclared():
    """⛔⛔ Backward, and the direction that found four of the five.

    A field is reported only when the sweep is CONCLUSIVE — zero loads anywhere, no column, not in
    the envelope key set. That is the side the over-counting resolver is sound on.
    """
    columns = _schema_columns()
    loads = _attribute_loads()
    undeclared = sorted(
        name for name in GatedEvent.model_fields
        if name not in CARRIED_BUT_NOT_PERSISTED
        and name not in columns and name not in ENVELOPE_KEYS and not loads.get(name))
    assert not undeclared, (
        f"fields carried across the boundary, stored nowhere and read by nothing: {undeclared}. "
        "This contract's own rule is that a dead field invites a consumer to trust a seam that "
        "carries nothing -- declare them with a mover, or take them off the object")


def test_every_declared_field_is_still_dead():
    """Forward. ⛔ `degraded_compile` is excepted and pinned separately, because its loads exist
    and are on another object -- an exception stated here rather than hidden in the resolver."""
    columns = _schema_columns()
    loads = _attribute_loads()
    for name in sorted(CARRIED_BUT_NOT_PERSISTED):
        if name == "degraded_compile":
            continue
        assert name not in columns, (
            f"{name} is now a column; it crosses the boundary and the entry should go")
        assert name not in ENVELOPE_KEYS, (
            f"{name} is now an envelope key; it round-trips and the entry should go")
        assert not loads.get(name), (
            f"{name} is now read at {loads[name][:3]}. Either it came alive -- good, drop the "
            "entry -- or a same-named attribute on another object is being counted, which is the "
            "resolver over-counting and needs the hand-check `degraded_compile` gets")


def test_degraded_compiles_two_loads_are_on_the_TAGGING_object_not_this_one():
    """⛔⛔ The hand-check, made mechanical. If a load of `.degraded_compile` ever appears on
    anything other than a `.domains` expression, the entry's central claim is stale."""
    loads = _attribute_loads()["degraded_compile"]
    assert loads, "no `.degraded_compile` load at all -- the measurement moved"
    off = [(m, ln, v) for m, ln, v in loads if not v.endswith(".domains")]
    assert not off, (
        f"`.degraded_compile` is loaded off something other than the tagging result: {off}. The "
        "declaration says the only two loads are `outcome.domains` and `esqe_outcome.domains`; "
        "if L2 now reads it off the gated event, the entry is closed")


def test_every_entry_names_what_was_measured_and_carries_a_house_form_mover():
    """⛔ Each grade has to cite the evidence a re-reader would check, not assert a conclusion."""
    for name, (what, mover) in CARRIED_BUT_NOT_PERSISTED.items():
        assert mover.startswith(("MOVES WHEN", "MOVES WITH")), f"{name}: {mover[:40]!r}"
        assert any(token in what for token in ("column", "ENVELOPE_KEYS", "attribute loads",
                                               "GAP FLAG", "persisted")), (
            f"{name}'s grade cites no measurement -- it reads as an opinion")


def test_the_worst_entry_says_WHY_it_is_the_worst():
    """⛔ `degraded_compile` is the only one whose own comment claims the defect was fixed, and an
    entry that did not say so would lose the finding."""
    what = CARRIED_BUT_NOT_PERSISTED["degraded_compile"][0]
    assert "fixed" in what.lower()
    assert "coverage_ready" in what, (
        "the entry must record that the FIRST half of the same answer is a column -- that "
        "asymmetry is what makes this a defect rather than a design")


def test_the_already_declared_one_credits_the_existing_flag():
    """✅ `prepared_content_ref` was declared before this unit, in the signal contract, and well.
    ⛔ An entry that claimed the finding would be taking credit for somebody else's."""
    what = CARRIED_BUT_NOT_PERSISTED["prepared_content_ref"][0]
    assert "GAP FLAG" in what and "contracts/signal" in what
    signal = (ENGINE / "contracts" / "signal.py").read_text(encoding="utf-8")
    assert "GAP FLAG — no `payload_ref` / `prepared_content_ref`" in signal, (
        "the flag this entry credits is gone; re-read whether the finding is still somebody "
        "else's before keeping the credit")
    assert "HALF EXPIRED" in what, (
        "the entry must record that the flag's own claim has half expired -- `payload_ref` IS a "
        "column now, so a reader who trusts the flag's wording is misled about which half is open")


RULE = "A dead field on a contract is worse than a missing one"


def test_the_contracts_own_rule_still_exists_OUTSIDE_the_table_that_quotes_it():
    """⛔⛔ FOUND BY A SURVIVING MUTATION, AND IT IS A THIRD KIND OF FALSE WITNESS.

    The first version asserted the rule was `in` the file. ⛔ But `CARRIED_BUT_NOT_PERSISTED`
    **quotes the rule as its own justification**, so deleting the ORIGINAL sentence from
    `coverage_ready`'s comment left the quote behind and the check passed. **A declaration that
    cites its source satisfies the test that the source exists.**

    `2.1` found a file's NAME standing in for its content, and a declaration falsifying its own
    count. This is the same family: the evidence and the thing it is evidence for were in one file
    and nothing kept them apart.

    So the rule is now required to exist somewhere that is NOT inside the declaration block.
    """
    lines = GATED.read_text(encoding="utf-8").splitlines()
    first = next(i for i, l in enumerate(lines) if l.startswith("CARRIED_BUT_NOT_PERSISTED"))
    header = first
    while header and lines[header - 1].startswith("#:"):     # the whole `#:` comment block
        header -= 1
    end = next(i for i, l in enumerate(lines) if l.startswith("class GatedEvent"))
    outside = "\n".join(lines[:header] + lines[end:])
    body = "\n".join(lines)
    assert RULE in outside, (
        "the rule exists only inside the table that quotes it as justification. The table is not "
        "evidence for itself -- if `coverage_ready`'s comment no longer states the rule, either "
        "restore it or stop citing it")
    assert body.count(RULE) >= 2, (
        f"the rule appears {body.count(RULE)}x; the declaration quotes it and the field comment "
        "states it, and both are wanted -- the quote is what tells a reader why the table exists")


# ----------------------------------------------------------------------------------- receipt 47

def test_the_receipt_exists_and_can_go_red():
    receipt = _receipt()
    assert receipt.layer == "L1"
    assert receipt.expect(0) is True
    assert receipt.expect(1) is False


def test_it_is_bounded_by_a_derived_window_and_not_by_all_of_history():
    """⛔ THE WHOLE DESIGN. The contract says an old row is legitimately null (*a pre-S4 row*), so
    an unbounded query would be red for ever and tell nobody anything."""
    sql = _receipt().sql
    assert "created_at >" in sql and "make_interval" in sql
    from genios_engine.platform.config import get_settings

    hours = 4 * float(get_settings().sync_interval_hours or 6.0)
    assert f"hours => {hours:g}" in sql, (
        "the horizon is not 4 sweep ticks off `sync_interval_hours` -- it must be derived, "
        "because a chosen number here decides what counts as a defect")


def test_it_asks_for_null_and_not_for_false():
    """⛔ `coverage_ready = false` is an ANSWER (this domain is not covered). Only `null` means
    nobody looked, and conflating them would report honest degradation as a defect."""
    sql = _receipt().sql
    assert "coverage_ready is null" in sql
    assert "coverage_ready = false" not in sql and "coverage_ready is false" not in sql


def test_it_is_org_scoped():
    assert "org_id = :org" in _receipt("org-1").sql
    assert "org_id = :org" not in _receipt(None).sql
    assert _receipt().fleet_wide is False


def test_the_builder_refuses_if_the_field_becomes_required(monkeypatch):
    """⛔⛔ THE ALWAYS-GREEN FAILURE, GUARDED. A required field means no gated event can be built
    without a verdict, so the query could only ever return 0."""
    import pytest
    from pydantic.fields import FieldInfo

    required = FieldInfo(annotation=bool)
    monkeypatch.setitem(GatedEvent.model_fields, "coverage_ready", required)
    with pytest.raises(AssertionError, match="REQUIRED|go green by itself"):
        R._UNSCOPED_COVERAGE_VERDICT_SQL(None)


def test_the_schema_still_allows_the_null_this_receipt_counts():
    """⛔ The other half of always-green: a NOT NULL column makes the receipt unfalsifiable too,
    and the schema is the source of truth for that, not the contract."""
    sql = (REPO / "migrations" / "0089_qualified_signals.sql").read_text(encoding="utf-8")
    line = next(l for l in sql.splitlines() if re.match(r"\s*coverage_ready\s+boolean", l))
    assert "not null" not in line.lower(), (
        "`qualified_signals.coverage_ready` is NOT NULL now, so receipt 47 can never go red. "
        "✅ That is the better world -- retire it deliberately")


def test_the_receipt_declares_the_package_an_operator_would_read():
    package, why = C.RECEIPT_PACKAGE[CLAIM]
    assert package == "capture"
    assert "tag_domains" in why or "domain" in why


def test_nothing_is_undeclared_or_stale():
    assert C.undeclared_receipts() == ()
    assert C.stale_declarations() == ()
