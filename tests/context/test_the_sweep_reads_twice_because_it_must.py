"""Four readings consume something written after they first run.

The order in `process_pending` is a CYCLE, and it is not an accident of layout:

    state situations -> residue (coverage) -> angles (gate on residue) -> readings again

`detect_residue` measures what the state readings did NOT explain, so it must run after them. The
angles gate on that residue, so they must run after it. And four readings consume what those
passes produce — `stated_dependency` reads `derived.dependency.stated`, `unreported` reads residue
plus a verdict, `reworded_outreach` reads a candidate plus a verdict, `condition_met` reads the
timeline correlator's facts.

Run once, every one of them is a full sweep behind. On a tenant's FIRST sweep they produce nothing
at all — which is exactly what the live graph showed: sixty findings computable in memory and not
one of the new types persisted.

REORDERING IS THE WRONG FIX and this file says so, because it is the change somebody will reach
for. Moving the readings below the angles would make residue measure coverage against readings
that had already consumed residue's own output — the measurement would then describe a graph that
only exists after it was taken.
"""
import ast
import inspect

from genios_engine.context import runner

SRC = inspect.getsource(runner.process_pending)


def _positions(*names: str) -> dict[str, int]:
    """Where each pass is CALLED, by AST rather than by string search: a name in a comment is not
    a call, and this file is mostly comments."""
    tree = ast.parse(SRC.lstrip())
    found: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            label = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if label in names and label not in found:
                found[label] = node.lineno
    return found


def test_the_readings_run_before_residue_so_coverage_is_measured_against_them() -> None:
    """Residue exists to say what the readings could not explain. Measured after them or it
    measures nothing."""
    at = _positions("refresh_state_situations", "detect_residue")
    assert at["refresh_state_situations"] < at["detect_residue"]


def test_the_angles_run_after_the_residue_they_gate_on() -> None:
    at = _positions("detect_residue", "evaluate_angles")
    assert at["detect_residue"] < at["evaluate_angles"]


def test_the_readings_run_again_after_the_angles() -> None:
    """THE FIX. Without a second call, `unreported` and `reworded_outreach` can never appear on a
    first sweep and are a full cycle late on every one after it."""
    tree = ast.parse(SRC.lstrip())
    calls = sorted(node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and (getattr(node.func, "id", None) == "refresh_state_situations"
                        or getattr(node.func, "id", None) == "_reread"))
    angles = _positions("evaluate_angles")["evaluate_angles"]
    assert len(calls) >= 2, "the state readings must run twice — once before residue, once after"
    assert calls[-1] > angles, "the second reading pass must follow the angles"


def test_the_correlators_run_before_the_second_pass() -> None:
    """`stated_dependency` reads what `refresh_dependency_chains` writes."""
    at = _positions("refresh_dependency_chains", "_reread")
    assert at["refresh_dependency_chains"] < at["_reread"]


def test_the_second_pass_is_reported() -> None:
    """A pass whose effect nothing counts is one nobody can tell ran."""
    assert '"second_pass_rows": second_pass_rows' in SRC


def test_reading_twice_is_safe_because_the_writes_are_idempotent() -> None:
    """THE PROPERTY THE FIX DEPENDS ON, quoted from the function it depends on: "every fact
    overwrites its own deterministic version id and every situation conflicts on
    `(org_id, correlation_id)`, so six sweeps a day produce one row per finding rather than six."
    If that ever stops being true, a second call would double every card rather than refresh it.
    """
    from genios_engine.context.outreach_situations import refresh_state_situations

    doc = inspect.getdoc(refresh_state_situations) or ""
    assert "Idempotent" in doc or "idempotent" in doc


def test_the_second_pass_cannot_break_the_sweep() -> None:
    """Every pass here is contained to itself; losing this one costs a cycle of the model-gated
    cards, never the ingestion."""
    tree = ast.parse(SRC.lstrip())
    guarded = [h for node in ast.walk(tree) if isinstance(node, ast.Try)
               for h in node.handlers
               if any(getattr(c.func, "id", None) == "_reread"
                      for c in ast.walk(node) if isinstance(c, ast.Call))]
    assert guarded, "the second reading pass must be contained like every other pass"
