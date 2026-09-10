"""RO-06 — the only predicates that consult the analytic layer could not be written down.

    pytest tests/packs/compiler/test_analytic_predicates_are_authorable.py -q

`ContextAdapter.evaluate` dispatches five ANALYTIC forms first, on `kind`, before any of the ten
key-set forms: trend, cohort, anomaly, typed absence and conflict. They are the only part of the
adapter that reads what `context/analytic/` publishes.

`Domain Expertise/_tools/validate.py` judged EVERY predicate by an exact key-set match against
the ten — and none of those key sets contains `kind` — so a situation file carrying one was
rejected by the corpus gate. The family could be evaluated by nothing because nobody could author
one, and the count of authored instances was zero. The adapter's own docstring admitted the gap
and deferred it to "the corpus wave".

Validated PER KIND rather than waved through: `{kind: trend}` with no `metric` answers UNKNOWN
forever, which is the same dead predicate the key-set check exists to prevent, one level in.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def validator():
    spec = importlib.util.spec_from_file_location("v", "Domain Expertise/_tools/validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_VOCAB = yaml.safe_load(open("Domain Expertise/_schema/vocabulary.yaml"))


def refusals(validator, condition: dict) -> list[str]:
    """What the corpus gate says about one predicate. Empty means it may be authored.

    The REAL vocabulary, because the ordinary key-set path consults `closed.predicate_ops` —
    a stub dict would make every `op` form fail for a reason that has nothing to do with the
    variable under test.
    """
    out: list[str] = []
    original = validator.err
    validator.err = lambda path, message: out.append(message)
    try:
        validator.check_predicate(Path("x.yaml"), "when", condition, _VOCAB)
    finally:
        validator.err = original
    return out


# =============================================================================================
# The five that could not be written.
# =============================================================================================
@pytest.mark.parametrize("condition", [
    {"kind": "trend", "metric": "reply_rate", "direction": "DECLINING",
     "min_confidence_bp": 5000},
    {"kind": "cohort", "metric": "reply_rate", "band": "D1", "min_population": 5},
    {"kind": "anomaly", "metric": "spend", "direction": "above", "min_z_like_bp": 30000},
    {"kind": "absence", "fact": "decision.scheduled", "type": "GENUINELY_ABSENT"},
    {"kind": "conflict", "field": "contract.value"},
], ids=["trend", "cohort", "anomaly", "absence", "conflict"])
def test_each_analytic_form_may_now_be_authored(validator, condition):
    assert refusals(validator, condition) == []


@pytest.mark.parametrize("condition", [
    {"kind": "trend", "metric": "reply_rate"},
    {"kind": "conflict", "field": "contract.value"},
], ids=["trend-minimal", "conflict-minimal"])
def test_the_optional_keys_are_optional(validator, condition):
    """A trend with no direction asks "is there a measured trend at all", which is a real
    question. Requiring every key would make the minimal form unwritable."""
    assert refusals(validator, condition) == []


# =============================================================================================
# What it still refuses, and why each refusal exists.
# =============================================================================================
def test_a_kind_the_evaluator_does_not_dispatch_is_refused(validator):
    """`ContextAdapter` refuses an unknown kind BY NAME rather than falling through to the
    `path:` tail, where it would be answered by a different question entirely. The corpus gate
    has to agree, or an author ships a predicate that can only ever abstain."""
    [message] = refusals(validator, {"kind": "wobble", "metric": "x"})

    assert "wobble" in message


def test_a_kind_with_no_metric_is_refused(validator):
    """`_trend` returns `_unknown("trend:no_metric")` — a predicate that answers UNKNOWN forever
    is the dead rule the key-set check exists to prevent, arriving by the other door."""
    [message] = refusals(validator, {"kind": "trend"})

    assert "metric" in message


def test_a_key_the_evaluator_ignores_is_refused(validator):
    """A rule whose author believes it says more than it does. `_cohort` reads `metric`, `band`
    and `min_population`; anything else is silently dropped, and silently is the problem."""
    [message] = refusals(validator, {"kind": "cohort", "metric": "x", "nonsense": 1})

    assert "nonsense" in message


def test_a_blank_kind_is_refused_rather_than_falling_through(validator):
    """`{kind: ''}` must not be judged by the key-set list — that list describes the OTHER
    dispatch route, and answering it there would be answering a different question."""
    assert refusals(validator, {"kind": "", "metric": "x"})


# =============================================================================================
# The ten ordinary forms are untouched.
# =============================================================================================
@pytest.mark.parametrize("condition", [
    {"exists": "deal.status"},
    {"absent": "thread.last_inbound"},
    {"has_obs": "meeting_request"},
    {"path": "deal.value", "op": ">", "value": 1000},
    {"neighbor_fact": "thread.ball_in_court", "op": "=", "value": "us"},
])
def test_an_ordinary_predicate_still_validates(validator, condition):
    assert refusals(validator, condition) == []


def test_a_predicate_matching_no_form_at_all_is_still_refused(validator):
    """The guard may not have become "accept everything"."""
    assert refusals(validator, {"invented": "x"})


# =============================================================================================
# The vocabulary and the validator say the same thing.
# =============================================================================================
def test_the_closed_vocabulary_declares_the_five(validator):
    """`vocabulary.yaml` is the contract between authored expertise and the running engine. A
    form the validator accepts and the vocabulary does not mention is a form no author can
    discover."""
    vocab = yaml.safe_load(open("Domain Expertise/_schema/vocabulary.yaml"))
    declared = vocab["closed"]["analytic_predicate_forms"]

    kinds = {entry["form"].split("kind: ")[1].split(",")[0].rstrip("}") for entry in declared}

    assert kinds == set(validator.ANALYTIC_FORMS)


def test_the_validator_and_the_evaluator_agree_about_the_closed_set():
    """Two lists of "which kinds exist" is how they come to disagree, and the corpus gate would
    then refuse a form the engine answers — or admit one it cannot."""
    from genios_engine.packs.compiler.context_adapter import PREDICATE_KINDS

    spec = importlib.util.spec_from_file_location("v2", "Domain Expertise/_tools/validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert set(module.ANALYTIC_FORMS) == set(PREDICATE_KINDS)
