"""L3-07 · how fast evidence goes stale — two curves, two questions, and nothing said so.

`capture/validate/confidence` warns in its own docstring that duplicating its curve would be "two
answers to how fast evidence goes stale — one used while composing and one used while reading,
disagreeing about the same day." A SECOND CURVE EXISTS, in `reason/engine`, and it is not even the
same function family: L1 decays LINEARLY in basis points per day, L4 decays EXPONENTIALLY on a
half-life.

⛔ THAT IS NOT A DEFECT AND THIS FILE DOES NOT TREAT IT AS ONE. They age different things — a
signal's extraction certainty versus a fact's contribution to one rule's decision — and the second
is configurable per pack. What was missing is that NOBODY HAD WRITTEN THAT DOWN, which is exactly
the spec's "double decay" warning: *"assign each transformation one owner and record its
contribution."* An unrecorded divergence is one refactor away from someone "unifying" them, or from
a third appearing because neither looked authoritative.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from genios_engine.capture.validate import confidence as l1_conf
from genios_engine.reason import engine as l4_engine

_ROOT = Path(__file__).resolve().parents[1] / "genios_engine"

#: ⛔ THE TWO OWNERS, AND THE QUESTION EACH ONE ANSWERS. A third entry here is a decision, not a
#: patch: it means a third thing in this product has an opinion about staleness.
DECAY_OWNERS: dict[str, tuple[str, str]] = {
    "capture.validate.confidence": (
        "how much less certain is THIS EXTRACTION because the message is old",
        "linear, basis points per day (DEFAULT_AGE_DECAY_BP_PER_DAY), applied as a READ VIEW in "
        "age_signals so the stored confidence is never itself decayed",
    ),
    "reason.engine": (
        "how much less should THIS FACT weigh in THIS RULE's decision because it is old",
        "exponential, half-life in days (freshness_half_life_days, default 30), applied at "
        "eval_time to the graph fact's occurred_at",
    ),
}


# =================================================================================================
# 1 · ⛔ THE TWO CURVES ARE DIFFERENT ON PURPOSE
# =================================================================================================

def test_l1_decays_linearly_in_basis_points_per_day():
    assert hasattr(l1_conf, "DEFAULT_AGE_DECAY_BP_PER_DAY")
    src = inspect.getsource(l1_conf.decay)
    assert "days_old" in src and "decay_bp_per_day" in src


def test_l4_decays_exponentially_on_a_half_life():
    """⛔ BEHAVIOURAL, NOT TEXTUAL. The first draft asserted the word `half_life` appeared in the
    source and stayed green when the parameter was renamed — the word survived in the body. A curve
    is a shape, so it is pinned by its shape: one half-life halves it, two quarter it, and age zero
    is untouched. That is what "exponential" means and it is what a reader relies on."""
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    hl = 30.0

    def f(days: float) -> float:
        return l4_engine._freshness(t0, t0 + timedelta(days=days), half_life_days=hl)

    assert f(0) == 1.0
    assert f(hl) > f(2 * hl) > f(4 * hl) > 0, "monotonic and never negative"

    # ⛔ AND HERE IS WHAT THE BEHAVIOURAL PIN FOUND, WHICH NO TEXT ASSERTION COULD HAVE.
    # The parameter is called `half_life_days` and the formula is `exp(-age / half_life)`. That is
    # an E-FOLDING time constant, not a half-life: at the named value the weight is 1/e ≈ 0.368,
    # not 0.5. The curve's TRUE half-life is `half_life_days * ln2` ≈ 20.8 days when configured
    # to 30.
    #
    # ⛔ THE FORMULA IS NOT CHANGED HERE, DELIBERATELY. It is a legitimate exponential decay, and
    # altering it would move the confidence term of every decision this product has ever made —
    # a behaviour change with no measurement behind it. The NAME is the wrong half, and renaming
    # it breaks authored pack configs. Both are product decisions with a blast radius, so the
    # actual behaviour is pinned here and the choice is routed to the handoff rather than taken
    # quietly. What must not happen is a pack author reading "half life: 30" and tuning against a
    # mental model that is 30% out.
    import math
    assert abs(f(hl) - math.exp(-1)) < 1e-6, (
        "the curve moved. If it now genuinely halves at half_life_days, the rename happened and "
        "every stored decision's confidence term shifted — that needs a measured migration, not a "
        "green test")
    assert abs(f(hl * math.log(2)) - 0.5) < 1e-6, "the TRUE half-life is half_life_days * ln2"


def test_l1_decays_on_a_straight_line_and_the_two_shapes_differ():
    """The division only means something if the shapes really are different. L1 loses a fixed
    number of basis points per day; L4 loses a fixed FRACTION per half-life. Charging the same age
    on one curve twice would be the spec's double decay; charging it on two curves that answer two
    questions is the design."""
    a = l1_conf.decay(10000, days_old=10, decay_bp_per_day=100)
    b = l1_conf.decay(10000, days_old=20, decay_bp_per_day=100)
    assert (10000 - a) == (a - b), "L1's curve is not linear in days"


def test_l1_decay_is_a_read_view_and_never_writes_back():
    """⛔ THE PROPERTY THAT MAKES THE TWO CURVES SAFE TOGETHER. `age_signals` returns AgedSignal
    objects carrying a decayed `confidence_bp` and leaves `row.confidence_bp` untouched. If it ever
    wrote back, L4 would then decay an already-decayed number and the same age would be charged
    twice — the spec's "double decay" for real."""
    from genios_engine.capture.esqe import signal_store
    src = inspect.getsource(signal_store.age_signals)
    assert "AgedSignal(" in src, "age_signals no longer returns a view object"
    assert "update" not in src.lower() and "insert" not in src.lower(), (
        "age_signals writes. A stored decayed confidence would be decayed AGAIN by reason/engine "
        "at eval_time, charging one age twice.")


def test_l1_calls_its_own_curve_rather_than_copying_it():
    """Its docstring: "`decay` is CALLED, not re-derived: a second copy of that curve here would be
    two answers to how fast evidence goes stale." Pinned so the import cannot become a reimplementation."""
    from genios_engine.capture.esqe import signal_store
    src = inspect.getsource(signal_store.age_signals)
    assert "from genios_engine.capture.validate.confidence import" in src
    assert "decay(" in src


# =================================================================================================
# 2 · ⛔ NO THIRD CURVE
# =================================================================================================

def test_no_third_module_invents_its_own_staleness_curve():
    """A third opinion about how fast evidence goes stale would be invisible: every one of them
    produces a plausible number. This scans for the shapes and requires the module to be a declared
    owner."""
    owners = {k.replace(".", "/") for k in DECAY_OWNERS}
    offenders: list[str] = []
    for py in _ROOT.rglob("*.py"):
        rel = str(py.relative_to(_ROOT).with_suffix(""))
        if rel in owners:
            continue
        src = py.read_text()
        # A curve is a decay CONSTANT plus arithmetic on an age — not a mention, and not a caller.
        if ("half_life" in src or "decay_bp_per_day" in src) and "def " in src:
            body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
            if ("half_life" in body or "decay_bp_per_day" in body) and "import" not in body.split("half_life")[0][-200:]:
                offenders.append(rel)
    # Callers that merely PASS a configured half-life are fine; this asserts the declared owners
    # are still the only two that DEFINE one.
    defining = [o for o in offenders
                if "DEFAULT_AGE_DECAY_BP_PER_DAY =" in (_ROOT / (o + ".py")).read_text()
                or "half_life_days: float =" in (_ROOT / (o + ".py")).read_text()]
    assert not defining, (
        f"modules defining their own staleness curve without being declared owners: {defining}. "
        "A third answer to 'how fast does evidence go stale' is a product decision, not a patch.")


def test_both_owners_state_their_question_and_their_shape():
    """A declaration without the QUESTION is a list of names. The question is what tells the next
    reader whether their new case belongs to an existing owner or is genuinely a third."""
    assert set(DECAY_OWNERS) == {"capture.validate.confidence", "reason.engine"}
    for module, (question, shape) in DECAY_OWNERS.items():
        assert len(question) > 30 and len(shape) > 30, f"{module} is declared without substance"
        assert (_ROOT / Path(*module.split("."))).with_suffix(".py").exists()


# =================================================================================================
# 3 · ⛔ THE DEAD COLUMN
# =================================================================================================

def test_freshness_policy_id_has_no_writer_and_no_reader_and_that_is_declared():
    """⛔ `graph_facts.freshness_policy_id` (migration 0004) APPEARS EXACTLY ONCE IN THIS REPO —
    its own declaration. Zero writers, zero readers, since 0004.

    "A column no writer names is null forever" is this project's own phrase, and the honest
    treatment is not to quietly build something onto it: freshness HAS owners (above), and a
    per-fact policy pointer is a THIRD design nobody has asked for. It is pinned dead here so that
    the next person who finds it does not read an empty column as an unfinished feature and start
    filling it in.
    """
    hits: list[str] = []
    for py in _ROOT.rglob("*.py"):
        if "freshness_policy" in py.read_text():
            hits.append(str(py.relative_to(_ROOT)))
    assert not hits, (
        f"freshness_policy_id now has code touching it: {hits}. If that is deliberate it needs an "
        "owner in DECAY_OWNERS and a reason; if it is not, it is a third staleness opinion "
        "arriving by accident.")

    sql = (_ROOT.parent / "migrations" / "0004_l2_context_graph.sql").read_text()
    assert "freshness_policy_id" in sql, "the column moved; this pin needs re-aiming"
