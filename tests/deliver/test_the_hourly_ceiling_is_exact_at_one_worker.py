r"""The per-recipient hourly ceiling is exact at one drain worker, and approximate at two.

⛔ WHY THIS EXISTS. `STEP-16` asked Rohit to decide whether a per-recipient hourly ceiling should
exist. **It already did**, and the question was manufactured by reading one module and not searching
the layer:

    deliver/timing.py:59     _BURST_WINDOW = timedelta(hours=1)
    deliver/timing.py:86     max_interrupts_per_hour: int = 3
    deliver/timing.py:229    interrupts_last_hour >= max_interrupts_per_hour  ->  DEFER

reached on every delivery through `outbox.drain -> gate.admit -> evaluate_delivery ->
evaluate_timing`. The step was **withdrawn**; what survived is this, which is not a decision but a
**latent condition**:

⛔ THE CEILING IS A READ-THEN-ACT CHECK, AND THE GAP IS DELIBERATE.
`PgDeliveryContext.resolve` counts the hour's deliveries and then calls `_release()`, because *"the
connection stops sitting `idle in transaction` across an outbound HTTP call."* **Holding a
transaction across a webhook POST would be worse than the overshoot.** So two workers draining two
rows for the same recipient both read `2 < 3`, both pass, and both send: four interrupts against a
ceiling of three.

⛔ THAT CANNOT HAPPEN TODAY, AND NOTHING SAID SO. One uvicorn process, one sweep thread, one drain
worker. The `for update skip locked` in the drain is for a deployment that does not exist yet, and
`deliver/rate_limiter.py` — declared tier 4 of the un-cut-over control plane — is the race-free
replacement, which is why deleting it would be wrong.

**So this module pins the worker count.** Raising it is a legitimate deployment change; doing it
without wiring `rate_limiter` silently widens a ceiling in production, and that is what fails here.
"""
from __future__ import annotations

import inspect
import pathlib
import re

from genios_engine.deliver import delivery_health as H
from genios_engine.deliver import timing
from genios_engine.deliver.gate import PgDeliveryContext
from genios_engine.executive.unreached import qualified_call_counts

_REPO = pathlib.Path(H.__file__).resolve().parents[2]


# ---------------------------------------------------------------------------------------------
# 1 · the ceiling exists and is live — the fact STEP-16 missed
# ---------------------------------------------------------------------------------------------

def test_a_per_recipient_hourly_ceiling_exists_and_has_a_default() -> None:
    """⛔ The fact that withdrew STEP-16. It is not a question; it is a default."""
    assert timing._BURST_WINDOW.total_seconds() == 3600
    assert timing.AttentionProfile().max_interrupts_per_hour == 3, (
        "the default ceiling moved -- that is a product change and belongs in a decision record")


def test_the_ceiling_is_reached_on_every_delivery() -> None:
    """⛔ Measured with the qualified resolver, link by link:
    `outbox.drain -> gate.admit -> gate.evaluate_delivery -> timing.evaluate_timing`."""
    counts = qualified_call_counts(H.engine_sources())
    for link in (("outbox", "drain"), ("gate", "admit"),
                 ("gate", "evaluate_delivery"), ("timing", "evaluate_timing")):
        assert counts.get(link, 0) > 0, f"{link[0]}.{link[1]} has no caller -- the chain is broken"
    assert counts.get(("rate_limiter", "reserve_slot"), 0) == 0, (
        "rate_limiter is now wired -- there would be TWO ceilings on one question, and two "
        "implementations answering one question disagree the first time somebody tunes one")


def test_the_ceiling_defers_and_never_drops() -> None:
    """A held message is not a lost one. ⛔ The whole reason this is politeness rather than data
    loss: `outbox._defer` *"does not touch `attempts`, and does not write `last_error`, because
    nothing failed."*

    ⛔ THIS WAS FIRST WRITTEN AS `"SUPPRESS" not in source` AND WOULD HAVE FAILED ON CORRECT CODE.
    `evaluate_timing`'s own docstring says *"Returns SEND or DEFER — never SUPPRESS"* — so the
    forbidden word is in the sentence that promises it will not happen. **Eighteenth time a
    substring check in this programme matched the author's own words**, caught before it shipped.

    The structural form: `DeliveryDecision.suppress` EXISTS on the contract, and this unit never
    reaches for it. That is a claim about code, and the AST can answer it.
    """
    import ast

    from genios_engine.contracts.delivery import DeliveryDecision

    assert callable(DeliveryDecision.suppress), (
        "the contract no longer offers `suppress`, so this test proves nothing")

    fn = ast.parse(inspect.getsource(timing.evaluate_timing).lstrip()).body[0]
    constructed = {n.func.attr for n in ast.walk(fn)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and isinstance(n.func.value, ast.Name)
                   and n.func.value.id == "DeliveryDecision"}
    assert constructed == {"combine", "defer", "send"}, (
        f"the timing unit now constructs {sorted(constructed)} -- it may only SEND or DEFER, and a "
        "ceiling that drops is a different product")


# ---------------------------------------------------------------------------------------------
# 2 · ⛔ the latent condition — one worker
# ---------------------------------------------------------------------------------------------

def test_the_deployment_runs_exactly_one_drain_worker() -> None:
    """⛔ THE POINT OF THIS MODULE.

    The ceiling is a read-then-act check across a RELEASED transaction, so it is exact at one
    worker and approximate at N. Raising the worker count is a legitimate deployment change; doing
    it without wiring `rate_limiter` widens a ceiling in production and nothing else would say so.
    """
    procfile = (_REPO / "Procfile").read_text(encoding="utf-8")
    assert "uvicorn" in procfile
    assert not re.search(r"--workers\s+\d+", procfile), (
        "the web process now runs multiple uvicorn workers, so two drains can read the same "
        "interrupt count and both send -- wire `rate_limiter.reserve_slot` or lower the ceiling")

    scheduler = (_REPO / "genios_engine" / "platform" / "scheduler.py").read_text(encoding="utf-8")
    assert "max_workers=1" in scheduler, (
        "the sweep executor is no longer single-threaded, so two ticks can drain concurrently")


def test_the_read_and_the_act_are_separated_on_purpose() -> None:
    """⛔ The gap is NOT a defect to close by holding the transaction. `resolve` releases it
    deliberately, and the docstring gives the cost of not doing so."""
    source = " ".join(inspect.getsource(PgDeliveryContext.resolve).split())
    assert "_release()" in source, (
        "resolve no longer releases its read transaction -- if that was deliberate it changes this "
        "module's whole argument, and if it was not it holds a transaction across a webhook POST")
    release_doc = inspect.getdoc(PgDeliveryContext._release) or ""
    assert "idle in transaction" in release_doc


# ---------------------------------------------------------------------------------------------
# 3 · the declaration says all of this
# ---------------------------------------------------------------------------------------------

def test_the_declaration_records_the_worker_count_as_its_mover() -> None:
    """⛔ `STEP-16` was withdrawn, so the thing that survived must live in the code rather than in a
    plan nobody reads. `rate_limiter`'s entry moves with the WORKER COUNT, not only the cutover."""
    _tier, why, measured_by, mover = H.UNCUT_OVER["rate_limiter.reserve_slot"]
    assert measured_by is None
    assert "WORKER COUNT" in mover.upper(), (
        "the mover no longer names the worker count, which is the only thing that makes this "
        "wanted before the cutover")
    assert "timing.py" in why, (
        "the entry no longer records that the ceiling is ALREADY enforced -- without that, somebody "
        "reads this as a missing feature and wires a second limiter")


def test_the_bucket_difference_is_recorded_not_lost() -> None:
    """⛔ The one thing `rate_limiter` does *better* rather than merely more safely: it shares one
    bucket across a chat family, because two messages in the same stream are one interruption.
    `timing.py` counts per (org, recipient, channel)."""
    _tier, why, _m, _v = H.UNCUT_OVER["rate_limiter.hour_recipient_key"]
    assert "chat famil" in why.lower()
    assert "timing.py" in why
