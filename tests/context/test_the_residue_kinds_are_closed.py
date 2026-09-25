"""L3-10 · the layer's account of what it could not explain, and the guard it did not have.

`context/residue.py` is the correlation decision record this plan was going to build, and it is a
better design than the one the spec describes: the spec wants a LOG of rejected candidates, which
needs bounded retention and a permissions policy of its own; residue records CURRENT STATE — "still
unexplained as of the last sweep" — deletes a row when a reading finally covers the subject, and
therefore cannot grow unbounded and shrinks as coverage improves.

⛔ WHAT IT DID NOT HAVE is a vocabulary. Four bare string constants, no collection, no guard — and
for THIS table the failure direction is one-way: a kind that silently stops being recorded makes
the sweep look MORE COMPLETE THAN IT IS. Nothing goes red, no row appears, and "what is happening
in my mailbox that this thing never mentioned" quietly starts answering "nothing".
"""
from __future__ import annotations

import inspect
import re

from genios_engine.context import residue as R


# =================================================================================================
# 1 · ⛔ TOTALITY, BOTH DIRECTIONS
# =================================================================================================

def _recorded_kinds() -> set[str]:
    """Every kind actually passed to `_record`, read from the source rather than assumed."""
    src = inspect.getsource(R)
    return set(re.findall(r"_record\(conn,\s*([A-Z_]+),", src))


def test_every_declared_kind_is_actually_recorded():
    """⛔ THE DANGEROUS DIRECTION. A declared kind nobody records reads as "there is none of this",
    and a reader has no way to tell that from "we stopped looking". On a table whose whole job is
    to say what we MISSED, that is the worst possible silent failure."""
    declared = {k for k in R.RESIDUE_KINDS}
    recorded_names = _recorded_kinds()
    recorded = {getattr(R, name) for name in recorded_names}
    missing = declared - recorded
    assert not missing, (
        f"declared but never recorded: {sorted(missing)}. The sweep now reports full coverage of "
        "something it stopped measuring.")


def test_every_recorded_kind_is_declared():
    for name in _recorded_kinds():
        assert getattr(R, name) in R.RESIDUE_KINDS, (
            f"{name} is recorded into context_residue but not declared in RESIDUE_KINDS — a row "
            "nothing knows how to describe")


def test_each_kind_says_what_it_means():
    """A kind name is a column value; the meaning is what tells the next reader whether their new
    case is one of these four or genuinely a fifth."""
    assert len(R.RESIDUE_KINDS) == 4
    for kind, meaning in R.RESIDUE_KINDS.items():
        assert len(meaning) > 30, f"{kind} is declared without a meaning"


# =================================================================================================
# 2 · ⛔ THE PROPERTIES THAT MAKE IT A WORK QUEUE RATHER THAN A LOG
# =================================================================================================

def test_first_seen_at_is_never_updated():
    """⛔ "How long has this gone unexplained" is the number that turns the table into a work queue.
    Refreshing it on every sweep would make everything look new for ever."""
    src = inspect.getsource(R)
    # ⛔ COMMENTS STRIPPED FIRST. The first draft sliced raw source and matched the comment that
    # explains the rule — the eighth time in this project a text assertion matched prose rather
    # than code. The SQL is what runs.
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    upsert = code[code.index("on conflict (org_id, residue_kind, subject_ref)"):]
    upsert = upsert[:upsert.index('")')]
    assert "first_seen_at" not in upsert.split("do update set")[-1], (
        "first_seen_at is being refreshed on conflict — every unexplained subject now looks like "
        "it appeared today, and the age that makes this a queue is gone")


def test_a_truncated_pass_says_that_it_truncated():
    """⛔ CC-30 / FX-13 on this table: "a top-k result treated as an exhaustive search produces
    false absence". Here the direction inverts — a truncated residue scan UNDER-reports what was
    missed, so a capped pass must say so or the coverage number is a lie in the flattering
    direction."""
    src = inspect.getsource(R)
    assert "truncated.add(kind)" in src
    assert "if len(rows) >= limit:" in src


def test_it_calls_no_model_and_takes_its_instant_as_a_parameter():
    """Its own docstring: "deterministic and cheap, on purpose… no model, no clock of its own".

    ⛔ THE MODEL HALF IS EXACTLY TRUE. A residue detector that judged which items MATTER would be a
    second opinion competing with the readings it exists to audit, and there is none.

    ⛔ THE CLOCK HALF IS NOT LITERALLY TRUE, AND THIS TEST SAYS SO RATHER THAN REPEATING THE
    DOCSTRING. `detect_residue` does `now = eval_time or datetime.now(timezone.utc)` — a DEFAULTED
    clock, not an absent one. The production caller (`context/runner.py`) passes `eval_time=
    sweep_at`, so the fallback is reachable only from a direct call, and what actually matters —
    that a replay can pin the instant — holds. Pinned as the parameter rather than as the absence,
    because a test that asserted "no clock" would be asserting a sentence rather than a property.
    """
    src = inspect.getsource(R)
    for banned in ("llm", "model(", "openai", "anthropic"):
        assert banned not in src.lower(), f"{banned} in the detector that audits the readings"
    assert "eval_time" in inspect.signature(R.detect_residue).parameters, (
        "eval_time stopped being a parameter — the pass is no longer replayable")
    caller = inspect.getsource(__import__("genios_engine.context.runner", fromlist=["x"]))
    assert "detect_residue(store, org_id, eval_time=" in caller, (
        "the production caller stopped pinning the instant, so the fallback clock is now live")


# =================================================================================================
# 3 · ⛔ THE LIMITATION CORRELATION STATES, PINNED SO IT CANNOT BE "FIXED" SILENTLY
# =================================================================================================

def test_correlation_still_refuses_to_split_deals_by_wording():
    """⛔ `correlation.py` declares this honestly and nothing guarded it:

        "Two independent deals with the same company, with no CRM connected, correlate into one
         situation… Guessing the split from wording would be exactly the over-correlation this
         module refuses to do."

    That is BS-07, CC-26 and INT-08's case. The tempting fix — split them by subject similarity —
    is the one the module exists to refuse, and it would look like an improvement: more situations,
    finer granularity, and two customers' problems fused or split on a guess. The governing rule is
    one line up: "wrongly MERGING two situations builds a chimera and reasons about it at full
    confidence".
    """
    from genios_engine.context import correlation as C
    # ⛔ WHITESPACE NORMALISED. The raw docstring wraps "…exactly the over-correlation this\nmodule
    # refuses to do", so a substring match spanning the wrap fails against correct prose. Any
    # assertion about documented reasoning has to be reflow-proof or it pins the line width.
    doc = " ".join((C.__doc__ or "").split())
    assert "KNOWN LIMITATION, STATED RATHER THAN HIDDEN" in doc
    assert "over-correlation this module refuses" in doc, (
        "the refusal is gone — splitting two deals by wording is now unguarded")
    assert "under-correlate rather than over-correlate" in doc, (
        "the governing principle is gone — without it the limitation above reads as a bug to fix")
    assert "Wrongly MERGING two situations builds a chimera" in doc, (
        "the reason the principle exists must stay beside it")
