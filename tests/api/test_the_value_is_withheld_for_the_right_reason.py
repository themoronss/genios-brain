r"""`/v1/insights/stats` withholds `value_recovered_inr` — and the reason it gives must be true.

⛔ WHAT WAS WRONG. The handler returned `value_state: "unavailable_no_counterfactual_ledger"` and
commented that *"value attribution needs the counterfactual ledger (L7-12), **which does not
exist**"*. ⛔ It exists: `counterfactual_ledger` is created by migration 0072, joins
signal → card → card_events → verdict → delivery_outbox → executions → execution_outcomes →
llm_costs one row per recommendation, and carries a production receipt asserting the join reaches
end to end. It answers *"did this recommendation lead to anything"* — not *"how much money"*.

⛔ THE REAL REASON IS SHARPER, AND NOBODY HAD WRITTEN IT DOWN. The table built for this number is
`macv_ledger` (migration 0012), whose own comment calls it *"the North Star … the number the
customer can verify"* and gives it `period`, `deal_id`, `amount`, `resolved_signal_id`. Measured
across the whole repository, it appears in five places: the migration that creates it, the cascade
FK (0033), `api/account_routes.py`'s deletion list, `tests/test_reasoning_retention.py`'s table
list, and `docs/LAYER_MAP.md`. ⛔ **Nothing ever inserts a row and nothing ever selects one — the
only code that touches the North Star ledger deletes it.**

⛔ WHY `None` STAYS. The handler's own first sentence is the principle: *"`0` and 'we have no way to
know yet' are different claims, and returning 0 for both is how an absent measurement becomes a
reported result."* Reading the empty ledger to report `0` would be exactly that defect. **So this
was a REASON change, not a value change** — *the fix for a wrong reason is the reason, not the
answer.*

⛔ WHAT THIS FILE IS FOR. It binds the `value_state` string to the measurement that justifies it:
**add a writer for `macv_ledger` and this fails**, naming the endpoint that must then stop claiming
the ledger has none. A string that states a fact about the repository and is checked by nothing goes
stale the first time somebody fixes the thing it describes.

⛔ THE ENDPOINT IS NOT CALLED HERE. `insight_stats` raises 400 when `_graph is None`, and no
database is configured in this checkout, so calling it would skip rather than assert — **and a skip
is not a pass.** The literal is read from the AST of the returned dict instead, which is the same
shape as this repo's other build-time guards.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ROUTES = _ROOT / "genios_engine" / "api" / "intelligence_routes.py"
_MIGRATIONS = _ROOT / "migrations"
_LAYER_MAP = _ROOT / "docs" / "LAYER_MAP.md"

#: The table that would hold the number, and the one the old string blamed instead.
_NORTH_STAR = "macv_ledger"
_CAUSALITY = "counterfactual_ledger"

#: Where a write would come from if one were added. `tests/` is excluded for the usual reason:
#: nobody runs a test to learn something about production.
_PRODUCTION_TREES = ("genios_engine", "scripts")


def _stats_return() -> dict[str, ast.expr]:
    """The literal dict `insight_stats` returns, keyed by its string keys, read from the AST."""
    tree = ast.parse(_ROUTES.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "insight_stats"), None)
    assert fn is not None, "insight_stats is gone — this guard needs re-pointing, not deleting"
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            return {k.value: v for k, v in zip(node.value.keys, node.value.values)
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    raise AssertionError("insight_stats no longer returns a literal dict")


def _writers(table: str) -> list[str]:
    """`insert into <table>` / `update <table>` across production code, as `path:line`."""
    hits: list[str] = []
    pattern = re.compile(rf"(?:insert\s+into|update)\s+{table}\b", re.I)
    for tree in _PRODUCTION_TREES:
        for path in (_ROOT / tree).rglob("*.py"):
            for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{path.relative_to(_ROOT)}:{i}")
    return hits


def _readers(table: str) -> list[str]:
    """`from <table>` / `join <table>`, plus any bare mention inside a SQL-looking string."""
    hits: list[str] = []
    pattern = re.compile(rf"(?:from|join)\s+{table}\b", re.I)
    for tree in _PRODUCTION_TREES:
        for path in (_ROOT / tree).rglob("*.py"):
            for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{path.relative_to(_ROOT)}:{i}")
    return hits


# ---------------------------------------------------------------------------------------------
# 1 · the value is still withheld, and the reason names the right ledger
# ---------------------------------------------------------------------------------------------

def test_the_value_is_still_null() -> None:
    """⛔ A reason change, not a value change. `0` and 'we cannot know yet' are different claims."""
    returned = _stats_return()
    assert "value_recovered_inr" in returned
    node = returned["value_recovered_inr"]
    assert isinstance(node, ast.Constant) and node.value is None, (
        "value_recovered_inr is no longer None — if a writer for macv_ledger landed, this guard "
        "and the endpoint's comment both need updating; if it is computed from something else, "
        "say what")


def test_the_reason_names_the_north_star_ledger() -> None:
    node = _stats_return()["value_state"]
    assert isinstance(node, ast.Constant)
    assert node.value == "unavailable_macv_ledger_has_no_writer"


def test_the_reason_no_longer_blames_the_counterfactual_ledger() -> None:
    """⛔ The old string said `unavailable_no_counterfactual_ledger`, which was false in two ways:
    that ledger exists, and it was never the one that would carry money."""
    node = _stats_return()["value_state"]
    assert isinstance(node, ast.Constant)
    assert "counterfactual" not in node.value


#: The old, false sentence. Kept verbatim because the guard below has to find it to check how it
#: is being used — ⛔ which is the whole lesson of this test.
_FALSE_CLAIM = "ledger (L7-12), which does not exist"

#: Words that can only appear around a QUOTATION of the false claim, never around an assertion of
#: it. Any one is enough; requiring all of them would make the guard brittle about wording.
_QUOTATION_MARKERS = ("used to read", "CITATION WAS WRONG", "CORRECTED")


def test_the_false_claim_survives_only_as_a_quotation_of_itself() -> None:
    """⛔ THIS TEST FAILED ON CORRECT CODE THE FIRST TIME IT RAN, and the rule it broke was written
    in its own docstring: *a grep for a known-false phrase matches the record of its own
    correction.* The corrected comment **quotes** *"the counterfactual ledger (L7-12), which does
    not exist"* in order to say it is false, so `assert _FALSE_CLAIM not in src` failed on the
    very fix it was guarding. **Eighteenth instance of this pattern in this programme, and the
    first where I wrote the rule into the docstring of the test that then broke on it.**

    ⛔ So the guard checks ATTRIBUTION, not PRESENCE: the phrase may appear, and every occurrence
    must sit inside a window that marks it as the old wording. A new bare claim adds an unmarked
    occurrence and fails. **A log is append-only and corrections are new lines — a guard that
    forbids the words cannot tell a correction from a relapse.**
    """
    lines = _ROUTES.read_text(encoding="utf-8").splitlines()
    unattributed = []
    for i, line in enumerate(lines):
        if _FALSE_CLAIM not in line:
            continue
        window = "\n".join(lines[max(0, i - 4):i + 5])
        if not any(marker in window for marker in _QUOTATION_MARKERS):
            unattributed.append(i + 1)
    assert unattributed == [], (
        f"⛔ the false claim is asserted, not quoted, at line(s) {unattributed}: "
        "`counterfactual_ledger` IS created by migration 0072")


def test_the_handler_states_the_correction_in_its_own_words() -> None:
    """The positive half. Forbidding the false sentence proves nothing if the true one is absent —
    ⛔ *a record nobody reads is presence without effect*, and a correction nobody states is the
    same thing."""
    src = _ROUTES.read_text(encoding="utf-8")
    assert "counterfactual_ledger` is created by migration 0072" in src
    assert _NORTH_STAR in src, "the handler must name the ledger that would carry the number"


# ---------------------------------------------------------------------------------------------
# 2 · the measurement the string rests on — ⛔ this is the part with teeth
# ---------------------------------------------------------------------------------------------

def test_the_north_star_ledger_still_has_no_writer() -> None:
    """⛔ THE GUARD. The endpoint tells a founder *why* the number is absent. The moment anything
    inserts a `macv_ledger` row that reason stops being true, and this fails pointing at the
    endpoint rather than letting a false cause ship.

    *A claim worth asserting is worth storing as data* — and a claim a string makes about the
    repository is worth checking against the repository."""
    writers = _writers(_NORTH_STAR)
    assert writers == [], (
        f"⛔ {_NORTH_STAR} now has {len(writers)} writer(s): {writers}. "
        "`/v1/insights/stats` still returns value_state='unavailable_macv_ledger_has_no_writer' "
        "and value_recovered_inr=None — update genios_engine/api/intelligence_routes.py, the "
        "comment above its return, and docs/LAYER_MAP.md's feedback/ row together.")


def test_the_north_star_ledger_still_has_no_reader_either() -> None:
    """⛔ Both directions. A writer with no reader and a reader with no writer are different
    failures, and the second would mean the endpoint is the reader it is waiting for."""
    readers = _readers(_NORTH_STAR)
    assert readers == [], (
        f"⛔ {_NORTH_STAR} is now read at {readers} — if that reader is this endpoint, the "
        "value_state string is stale by definition.")


def test_the_north_star_ledger_exists_in_the_schema() -> None:
    """The ledger is not missing — it is unwritten. *A table nobody writes is not a table nobody
    built*, and the distinction is the whole finding."""
    created = [p.name for p in _MIGRATIONS.glob("*.sql")
               if re.search(rf"create table if not exists {_NORTH_STAR}\b",
                            p.read_text(encoding="utf-8"), re.I)]
    assert created == ["0012_l6_feedback.sql"], created


def test_the_north_star_ledger_calls_itself_the_number_the_customer_can_verify() -> None:
    """⛔ Quoted because it is the reason this is a finding and not a tidy-up: the table that holds
    the product's headline number has never been written to."""
    src = (_MIGRATIONS / "0012_l6_feedback.sql").read_text(encoding="utf-8")
    assert "the North Star" in src
    assert "The number the customer can verify" in src


# ---------------------------------------------------------------------------------------------
# 3 · and the ledger the old string blamed cannot carry money anyway
# ---------------------------------------------------------------------------------------------

def test_the_counterfactual_ledger_exists() -> None:
    """⛔ Atlas gap #7 is CLOSED. Asserted so the retracted claim cannot be reinstated quietly."""
    src = (_MIGRATIONS / "0072_counterfactual_ledger.sql").read_text(encoding="utf-8")
    assert re.search(rf"create or replace view {_CAUSALITY}\b", src, re.I)


@pytest.mark.parametrize("migration,table", [
    ("0072_counterfactual_ledger.sql", _CAUSALITY),
    ("0041_l5_execution.sql", "execution_outcomes"),
    ("0004_l2_context_graph.sql", "llm_costs"),
])
def test_no_monetary_column_in_the_tables_the_endpoint_already_reads(migration: str,
                                                                    table: str) -> None:
    """⛔ Why `None` is the right answer rather than a missing join. None of the three carries an
    amount: `llm_costs` holds tokens, `execution_outcomes` holds a label and durations, and the
    causality view carries neither.

    ⛔ `0072` does contain the token `usd` — `count(*) as usd_calls` inside a lateral, selected out
    as `llm_calls`. **The inner alias says USD and the value is a count of calls.** It is named here
    rather than fixed, because an applied migration is not edited."""
    src = (_MIGRATIONS / migration).read_text(encoding="utf-8")
    money = re.findall(r"^\s*(\w*(?:amount|paise|inr|minor_units)\w*)\s+"
                       r"(?:numeric|bigint|int)", src, re.I | re.M)
    assert money == [], f"{table}: {money} — if an amount landed, the endpoint can compute value"


def test_the_usd_alias_in_the_view_is_a_count_not_money() -> None:
    """⛔ Pinned so the next reader of `0072` is not misled the way I nearly was."""
    src = (_MIGRATIONS / "0072_counterfactual_ledger.sql").read_text(encoding="utf-8")
    assert "count(*) as usd_calls" in src
    assert "as llm_calls" in src


# ---------------------------------------------------------------------------------------------
# 4 · the authoritative layer map said feedback/ writes it
# ---------------------------------------------------------------------------------------------

def test_the_layer_map_no_longer_says_feedback_writes_macv() -> None:
    """⛔ `docs/LAYER_MAP.md` is the table `genios_engine/LAYERS.py` names as authoritative, and its
    `feedback/` cell listed *"Precision windows, nudges, mutes, MACV."* The other three are
    measured and real; MACV was not. **A false claim in the authoritative map is the most expensive
    place for one.**"""
    row = next(ln for ln in _LAYER_MAP.read_text(encoding="utf-8").splitlines()
               if ln.startswith("| `feedback/`"))
    assert "Precision windows, nudges, mutes." in row
    assert "nudges, mutes, MACV" not in row
    assert "CORRECTED 2026-10-02" in row


@pytest.mark.parametrize("claim,needle,tree", [
    ("precision windows", r"_PRECISION_SQL|def precision_28d", "genios_engine/feedback"),
    ("nudges", r"insert\s+into\s+calibration_nudges", "genios_engine/feedback"),
    ("mutes", r"insert\s+into\s+rule_mutes", "genios_engine/feedback"),
])
def test_the_layer_maps_three_remaining_claims_are_real(claim: str, needle: str,
                                                        tree: str) -> None:
    """⛔ Correcting one cell is where a second false claim slips in. Each survivor is measured."""
    blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore")
                     for p in (_ROOT / tree).rglob("*.py"))
    assert re.search(needle, blob, re.I), f"LAYER_MAP still claims {claim} and nothing matches"
