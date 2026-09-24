"""17-U5 + 17-U7 · the twelve invariants as walking tests, and the matrix as a countable table.

    pytest tests/scenarios/test_invariants.py -q

**§2 technique 4, in one sentence:** *"'the vocabulary must not import the rules' — a code review
cannot enforce this; a test can."*

ARCHITECTURE.md §10 lists twelve invariants and names an enforcer for each. Several are enforced by
a **grep somebody has to remember to run**, which is the same class of protection as a comment. This
file turns those into rows that fail on their own.

⛔ **THE PURITY GREP IN §7 IS WRONG AND THIS FILE CORRECTS IT.**

    grep -rn "float(" genios_engine/capture/validate/

returns three hits today — and all three are the code **defending against** floats:
`require_no_float(...)`, and two docstrings saying *"never `float()` on the way past"*. A verify
command that cries wolf on its own guard rails is a verify command nobody runs twice.
"""
from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = pytest.mark.unit

CAPTURE = pathlib.Path("genios_engine/capture")
VALIDATE = CAPTURE / "validate"


def _lines(directory: pathlib.Path, pattern: str) -> list[str]:
    """Matching lines, **with comments and docstring prose excluded**.

    Stripping them is not leniency — a grep that fires on the sentence explaining the rule reports
    the guard as the violation, and its next reader turns it off.
    """
    found = []
    for path in sorted(directory.rglob("*.py")):
        in_doc = False
        for n, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.count('"""') == 1:
                in_doc = not in_doc
                continue
            if in_doc or stripped.startswith("#") or stripped.startswith('"""'):
                continue
            if re.search(pattern, line):
                found.append(f"{path}:{n}: {stripped}")
    return found


# =================================================================================================
# Invariant 1 · a lower layer never imports a higher one
# =================================================================================================
def test_invariant_1_contracts_never_import_capture():
    """The direction the whole architecture rests on. `tests/test_layer_topology.py` owns the full
    walk; this is the one edge §4f's *"L2 decides"* depends on."""
    offenders = [p.name for p in pathlib.Path("genios_engine/contracts").glob("*.py")
                 if re.search(r"^\s*(from|import)\s+genios_engine\.capture", p.read_text(), re.M)]

    assert offenders == [], f"contracts import capture: {offenders}"


def test_invariant_1_capture_never_imports_context_or_higher():
    """L1 may not reach into L2, L3, L4 or L5. A capture module that imported `context` could
    resolve an entity mid-capture, which is precisely the decision §4f says is **not L1's**."""
    higher = ("context", "packs", "reason", "executive", "deliver")
    pattern = r"^\s*(from|import)\s+genios_engine\.(" + "|".join(higher) + r")\b"
    offenders = [f"{p}" for p in CAPTURE.rglob("*.py")
                 if re.search(pattern, p.read_text(), re.M)]

    assert offenders == [], f"capture reaches upward: {offenders}"


# =================================================================================================
# Invariant 2 · integer basis points — no float crosses a boundary
# =================================================================================================
def test_invariant_2_no_float_conversion_in_the_validators():
    """⛔ **§7's grep, corrected.** The raw command reports `require_no_float(...)` — the guard — as
    a violation. This excludes prose and the guard's own name, so a real `float(x)` is the only
    thing that can fire it."""
    hits = [h for h in _lines(VALIDATE, r"\bfloat\(")
            if "require_no_float" not in h and "no_float" not in h]

    assert hits == [], f"a float conversion inside the validators: {hits}"


def test_invariant_2_the_guard_the_grep_kept_flagging_actually_exists():
    """The other half, and the reason the correction is safe: the hits §7's grep found were **real
    protection**, so excluding them must not mean excluding nothing."""
    from genios_engine.capture.validate.conflict import NormalizedClaim

    assert NormalizedClaim is not None
    assert _lines(VALIDATE, r"require_no_float"), "the float guard itself has gone"


# =================================================================================================
# Invariant 4 · no clock inside logic
# =================================================================================================
def test_invariant_4_no_clock_is_read_inside_the_validators():
    """*"Time arrives as `eval_time`."* A validator that read a clock would give a different answer
    to a replay of last week than it gave last week — and a replay that cannot reproduce a verdict
    cannot audit one."""
    hits = _lines(VALIDATE, r"datetime\.now|date\.today|time\.time\(")

    assert hits == [], f"a clock inside the validators: {hits}"


def test_invariant_4_the_scoring_path_takes_its_time_as_a_parameter():
    """The positive statement of the same rule, at the seam that matters: step 12's resolver."""
    import inspect

    from genios_engine.capture.esqe.signal_states import CommitmentFacts

    assert "eval_time" in inspect.get_annotations(CommitmentFacts)


# =================================================================================================
# Invariant 5 · no model on a scoring path
# =================================================================================================
def test_invariant_5_no_model_client_reaches_the_validators():
    """**Doctrine 1: a model may DESCRIBE, never SCORE.** An LLM import inside `validate/` is that
    doctrine breaking, and it would not fail any other test."""
    hits = _lines(VALIDATE, r"\b(LLMClient|anthropic|openai)\b")

    assert hits == [], f"a model on the validation path: {hits}"


def test_invariant_5_no_model_client_reaches_the_scorer():
    """`esqe/importance.py` is ALG-17. §10 records what happens without this rule: before ALG-17,
    `situation_bso.py` stamped a constant and **193 of 223 signals carried an identical score —
    with a green suite the entire time.**"""
    hits = _lines(CAPTURE / "esqe", r"\b(LLMClient|anthropic|openai)\b")
    hits = [h for h in hits if "relevance.py" not in h]   # relevance ASKS; it does not score

    assert hits == [], f"a model on the scoring path: {hits}"


# =================================================================================================
# Invariant 8 · domain mapping tags, never filters
# =================================================================================================
def test_invariant_8_the_indiscriminate_flag_is_a_threshold_and_not_a_limit():
    """*"Nothing is refused for crossing it; it sets `is_indiscriminate` so the condition is
    visible in a report. Refusing tags here would be filtering, which §9 forbids in as many
    words."*"""
    from genios_engine.capture.domain.coverage import domain_distribution

    everything = domain_distribution([["sales", "hiring", "fundraising"]] * 5)

    assert everything.is_indiscriminate is True
    assert everything.tagged == 5, "flagged AND counted — the flag must not drop the events"


# =================================================================================================
# 17-U7 · the failure log is countable, and the matrix has no holes
# =================================================================================================
def _scenario_ids_with_tests() -> set[str]:
    """Every `SNN` a test function actually covers, read off the test names."""
    ids: set[str] = set()
    for path in pathlib.Path("tests/scenarios").glob("test_4*.py"):
        # The suffix keeps its case deliberately: `S01b` is a distinct row from `S01`, and
        # upper-casing the whole id would mint `S01B`, which the registry has never heard of.
        for number, suffix in re.findall(r"^def test_s(\d+)(b?)_", path.read_text(), re.M):
            ids.add(f"S{number}{suffix}")
    return ids


def test_every_scenario_in_the_registry_has_a_test():
    """⛔ **THE TOTALITY GUARD, and the repo's own idiom** — the one `PRECEDENCE`,
    `SIGNAL_TYPE_WEIGHT_BP` and `ANCHOR_FAMILIES` already use.

    Without it §8's *"all 39 scenarios encoded"* is a claim in a document, which is the exact kind
    of claim §1's table is made of.
    """
    from tests.scenarios._registry import SCENARIOS

    missing = sorted(set(SCENARIOS) - _scenario_ids_with_tests())

    assert missing == [], f"scenarios with no test: {missing}"


def test_every_scenario_test_has_a_registry_row():
    """The other direction. A test with no row **cannot be counted, compared or trended** — §6
    condition 5 — so it is invisible to the failure log even while it runs."""
    from tests.scenarios._registry import SCENARIOS

    unregistered = sorted(_scenario_ids_with_tests() - set(SCENARIOS))

    assert unregistered == [], f"tests with no failure class: {unregistered}"


def test_the_matrix_covers_all_thirty_nine_rows_of_section_four():
    """§4 lists S01–S39. The registry carries **40** — S01b is the split §1's premise forced:
    `assemble_chain` being correct and the pipeline feeding it one message are **two different
    facts**, and one row could only record one of them."""
    from tests.scenarios._registry import SCENARIOS

    numbered = {s for s in SCENARIOS if re.fullmatch(r"S\d{2}", s)}

    assert len(numbered) == 39, f"§4 has 39 rows; the registry has {len(numbered)}"
    assert "S01b" in SCENARIOS


def test_every_open_or_blocked_scenario_states_its_reason():
    """*"A verdict with no reason is a label"*, and §1's complaint is entirely about labels that
    looked like evidence."""
    from tests.scenarios._registry import CORPUS, IMPOSSIBLE, OPEN, SCENARIOS

    for one in SCENARIOS.values():
        if one.verdict in (OPEN, CORPUS, IMPOSSIBLE):
            assert one.note, f"{one.id} is {one.verdict} with no reason"


def test_the_three_trust_rows_are_closed_and_not_merely_encoded():
    """§8 singles these out: *"S21, S22, S25 green — the three `unknown` rows, which are the trust
    of the product."*"""
    from tests.scenarios._registry import CLOSED, SCENARIOS

    for sid in ("S21", "S22", "S25"):
        assert SCENARIOS[sid].verdict == CLOSED, f"{sid} is not closed"


def test_the_failure_log_counts_match_the_registry():
    """⛔ **A SCOREBOARD THAT DRIFTS FROM ITS SOURCE IS THE FAILURE §1's TABLE IS MADE OF**, and
    this one drifted while it was being written: the summary said 31 closed / 3 corpus where the
    registry says 29 / 4.

    Caught by counting rather than by reading, which is the whole argument of this step.
    """
    import collections
    import pathlib

    from tests.scenarios._registry import SCENARIOS

    counts = collections.Counter(s.verdict for s in SCENARIOS.values())
    log = pathlib.Path("speedrun008/plan/layer-1/FAILURE-LOG.md").read_text()

    for verdict, label in (("closed", "CLOSED"), ("guard", "GUARD"), ("corpus", "CORPUS"),
                           ("open", "OPEN"), ("impossible", "IMPOSSIBLE")):
        row = next(l for l in log.splitlines() if l.startswith(f"| **{label}**"))
        stated = int(re.search(r"\d+", row.split("|")[2]).group())
        assert stated == counts[verdict], (
            f"the log says {stated} {label} rows; the registry has {counts[verdict]}")

    assert f"{len(SCENARIOS)} rows" in log
