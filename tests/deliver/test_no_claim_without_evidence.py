r"""L5 STEP-04 · `M13.C1.U02` — no claim without its evidence, and nothing weakened.

⛔ THE CROSS-CHECK NEARLY RECORDED THAT THE INVENTION VALIDATOR DID NOT EXIST. It does —
`deliver/render.py:334`, called at `render.py:861`, re-exported by `executive/validate.py:69`,
covered by `tests/test_delivery.py`. The wrong conclusion came from grepping `reminder_facts`, the
name its own docstring uses, and finding no validator among the three files that matched. A
conclusion drawn from one name's absence: the same mistake as `no_model_wired` in L1 and the
graph-revision guard in L3. `test_the_old_validator_still_exists_and_is_called` makes it permanent.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from genios_engine.contracts.claim_state import CLAIM_STATES, ClaimState
from genios_engine.deliver import claim_validator, claims as C
from genios_engine.deliver.claim_validator import claims_ok, observed_claims
from genios_engine.deliver.claims import Claim, by_state, classify, extract, split_sentences
from genios_engine.deliver.render import invention_ok

CORPUS = "nikhil@addis.im wrote on tuesday about the series a round. sofía padrón replied."
NUMS = {"4", "12"}


# ── the split ─────────────────────────────────────────────────────────────────────────────────

def test_the_old_validator_still_exists_and_is_called():
    """⛔ THE CROSS-CHECK'S NEAR-MISS, AS A TEST. It exists, and this widening CALLS it rather than
    reimplementing it — which is what lets its own tests stand as the proof of no weakening."""
    assert callable(invention_ok)
    tree = ast.parse(pathlib.Path(claim_validator.__file__).read_text())
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "invention_ok" in imported



@pytest.mark.parametrize("text,corpus,nums", [
    ("Acme raised 99m.", CORPUS, NUMS),
    ("Mesco replied yesterday.", CORPUS, NUMS),
    ("The round closed at 40m.", CORPUS, NUMS),
])
def test_everything_the_old_validator_refuses_the_new_one_refuses(text, corpus, nums):
    """⛔ WIDENING IS NOT LOOSENING. A caller swapping one for the other can only ever see MORE
    refusals, never fewer."""
    old_ok, old_detail = invention_ok(text, corpus, nums)
    new_ok, new_detail, _ = claims_ok(text, corpus, nums)
    assert old_ok is False and new_ok is False
    assert new_detail == old_detail, "a widened validator that renames the old refusals breaks " \
                                     "every reader of cards.reject_detail"



def test_the_old_refusal_is_reported_before_any_new_one():
    src = inspect.getsource(claims_ok)
    assert src.index("invention_ok(") < src.index("for claim in extract(")



def test_a_grounded_card_of_mixed_claim_kinds_passes():
    ok, detail, refusals = claims_ok(
        "Nikhil wrote on tuesday. This may slip. Send a reply today.",
        CORPUS, NUMS, quotes_something=True)
    assert ok and detail is None and refusals == ()



def test_a_refusal_names_the_sentence_a_reviewer_has_to_read():
    ok, _, refusals = claims_ok("Nikhil wrote on tuesday. Acme raised 99m.", CORPUS, NUMS)
    assert not ok
    assert refusals[0].sentence


# ── the two guards that cannot fire through the public entry point ────────────────────────────


def test_an_observed_claim_with_nothing_cited_is_refused():
    """⛔ DRIVEN DIRECTLY, BECAUSE IT CANNOT BE REACHED THROUGH `claims_ok`. `claims.classify` will
    not write `OBSERVED` without the same `quotes_something` the validator checks, so the branch is
    an INVARIANT GUARD over the classifier, not a live refusal. It fails the day somebody tags a
    claim from a field instead of from the sentence — a change somebody will one day want."""
    fabricated = Claim("Nikhil wrote on tuesday.", ClaimState.OBSERVED, "tagged from a field")
    assert claim_validator._observed_is_cited(fabricated, quotes_something=False)
    assert claim_validator._observed_is_cited(fabricated, quotes_something=True) is None



def test_a_hypothesis_not_marked_in_its_own_wording_is_refused():
    fabricated = Claim("This deal is dead.", ClaimState.HYPOTHESISED, "tagged from a field")
    assert claim_validator._hypothesis_is_marked(fabricated)
    marked = Claim("This deal may be dead.", ClaimState.HYPOTHESISED, "hedged on 'may'")
    assert claim_validator._hypothesis_is_marked(marked) is None



def test_the_unreachable_branches_are_labelled_as_such_in_the_source():
    """⛔ An unreachable branch nobody labelled is how somebody later reads a passing test, believes
    a refusal is protecting production, and relaxes something upstream."""
    doc = claim_validator.__doc__ or ""
    assert "unreachable" in doc.lower()


# ── totality ──────────────────────────────────────────────────────────────────────────────────


def test_every_claim_state_has_a_rule():
    assert set(claim_validator._RULES) == set(ClaimState)



def test_every_state_that_is_actually_a_claim_has_teeth():
    """`ENVELOPE` is the only state allowed an empty rule tuple, because an instruction has nothing
    to ground. Any other state reaching that would be a claim nothing checks."""
    for state in CLAIM_STATES:
        assert claim_validator._RULES[state], f"{state.value} has no actual check"
    assert claim_validator._RULES[ClaimState.ENVELOPE] == ()



def test_envelope_is_written_down_rather_than_left_out():
    """⛔ The guard runs against `ClaimState`, not `CLAIM_STATES` — and the import-time check is
    what found the difference. `CLAIM_STATES` is *"the three that are actually claims"*, so
    guarding against it would have left `ENVELOPE` sentences with no declared rule, passing
    silently forever."""
    assert ClaimState.ENVELOPE in claim_validator._RULES
    assert ClaimState.ENVELOPE not in CLAIM_STATES



def test_observed_claims_are_listable_for_a_reviewer():
    seen = observed_claims("Nikhil wrote on tuesday. Send a reply.", CORPUS, NUMS,
                           quotes_something=True)
    assert len(seen) == 1 and seen[0].state is ClaimState.OBSERVED


# ── and it is actually called ──────────────────────────────────────────────────────────────────


def test_the_renderer_calls_the_widened_validator():
    """⛔ THE DEFECT THIS PROGRAMME HAS FOUND EIGHT TIMES, INCLUDING ONCE IN ITS OWN WORK ONE STEP
    AGO: built, tested, green, and called by nothing. AST, not a grep — the call, not the def."""
    from genios_engine.deliver import render

    tree = ast.parse(inspect.getsource(render.render_copy))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "claims_ok" in called
    assert "invention_ok" not in called, (
        "both validators called from one place would give the same field two verdicts")



def test_the_renderer_imports_the_validator_locally_because_of_the_cycle():
    """`claim_validator` imports `invention_ok` from `render`, so a module-level import here is a
    cycle. Structural, not style — and worth a test so nobody 'tidies' it to the top."""
    from genios_engine.deliver import render

    assert "from .claim_validator import claims_ok" in inspect.getsource(render.render_copy)
    top = pathlib.Path(render.__file__).read_text().split("def ", 1)[0]
    assert "claim_validator" not in top
