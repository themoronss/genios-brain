"""306 in, 9 out, and the engine could not say which step lost the other 297.

The dependency correlator has carried a `DropReason` per refused claim since it was written. The
timeline correlator carried nothing, so its census — added in the same unit as dependency's —
reported `read=306, emitted=9, unaccounted=297` and left every reader to guess whether that gap
was a bug in the vocabulary, a broken identity cascade, or mail that simply contained no promises.

TWO DEFECTS, BOTH FIXED HERE:

1. THE DENOMINATOR WAS WRONG. `read` counted CLAIM RECORDS. One record can carry several
   commitments and most carry none, so the census was answering "how much mail did we look at"
   when the question is "how many promises did we look at". Most of the 297 was mail with no
   promise in it — not a loss, and reporting it as one sends somebody hunting a bug in a step
   that behaved correctly.

2. THE REFUSALS HAD NO NAMES. `conditions_from` and `store_condition` refuse at four distinct
   points and all four looked identical from outside. "No resolvable subject" is a fixable
   identity problem; "not conditional" is the vocabulary doing its job. Collapsing them into one
   number makes the fixable one invisible.

WHAT THIS FILE REFUSES TO ADD, same as the dependency census: any opinion about a healthy rate.
A tenant whose mail genuinely contains no conditional promises converts at zero and is perfectly
fine. A threshold here would be tuned on the pilot and wrong for the next customer, which is the
failure the census exists to avoid.
"""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Commitment
from genios_engine.context.correlation_timeline import (CONDITION_DUPLICATE,
                                                        CONDITION_NOT_CONDITIONAL,
                                                        CONDITION_NO_TEXT,
                                                        CONDITION_UNRESOLVED_SUBJECT, ClaimRecord,
                                                        conditions_from, conditions_with_census)

_AT = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)


def span(text: str) -> EvidenceSpan:
    return EvidenceSpan(source_ref="prepared_content:evt", quote=text, start_offset=0,
                        end_offset=len(text), verified=True)


def commitment(*, condition: str | None, actor: str = "Priya",
               action: str = "revisit the deal",
               beneficiary: str | None = "rohit@antler.co") -> Commitment:
    """Built through the contract, so a commitment this suite asserts on is one L1's publishing
    seam would really have accepted."""
    quote = condition or "I'll revisit the deal."
    return Commitment(actor=actor, action=action, beneficiary=beneficiary,
                      is_conditional=condition is not None, condition_text=condition,
                      evidence=[span(quote)], confidence_bp=7000)


def record(*commitments: Commitment, event_id: str = "evt_1",
           at: datetime = _AT) -> ClaimRecord:
    return ClaimRecord(event_id=event_id, occurred_at=at, commitments=tuple(commitments))


def resolves(value: str | None) -> str | None:
    return "node_priya" if value else None


def resolves_nobody(_value: str | None) -> str | None:
    return None


# -------------------------------------------------------------------------------------------------
# THE DENOMINATOR
# -------------------------------------------------------------------------------------------------

def test_the_denominator_is_promises_not_mail() -> None:
    """THE DEFECT THAT MADE 297 LOOK LIKE A LOSS. Three records, one promise between them: the
    census must read 1, not 3. Counting records made mail that never contained a promise
    indistinguishable from a promise the layer failed to process."""
    records = [record(commitment(condition="once legal confirms"), event_id="evt_1"),
               record(event_id="evt_2"),
               record(event_id="evt_3")]
    _, examined, _ = conditions_with_census(records, resolves)
    assert examined == 1, "empty records are being counted as promises the layer lost"


def test_a_record_carrying_several_promises_counts_each_of_them() -> None:
    """The mirror of the above: the count is per commitment, so one email that makes three
    promises is three chances to build a condition, not one."""
    records = [record(commitment(condition="once legal confirms", action="send the contract"),
                      commitment(condition="after the board meets", action="confirm pricing"),
                      commitment(condition=None, action="say hello"))]
    _, examined, _ = conditions_with_census(records, resolves)
    assert examined == 3


# -------------------------------------------------------------------------------------------------
# THE FOUR REFUSALS — each one named, and each one actually reachable
# -------------------------------------------------------------------------------------------------

def test_an_unconditional_promise_is_refused_by_name() -> None:
    """NOT A FAILURE, AND THAT IS THE POINT OF NAMING IT. "I'll send the deck tomorrow" is a
    perfectly good commitment and simply not a dormant condition. Before this, it was
    indistinguishable from a condition the layer could not resolve."""
    conditions, examined, dropped = conditions_with_census([record(commitment(condition=None))],
                                                           resolves)
    assert conditions == ()
    assert (examined, dropped) == (1, {CONDITION_NOT_CONDITIONAL: 1})


def test_a_conditional_promise_with_no_condition_text_is_its_own_reason() -> None:
    """L1 said `is_conditional=True` and gave no text for it. That is an EXTRACTOR defect and a
    different one from every other reason here — it is the only one that points upstream."""
    bare = Commitment(actor="Priya", action="revisit", beneficiary="rohit@antler.co",
                      is_conditional=True, condition_text="   ",
                      evidence=[span("revisit")], confidence_bp=7000)
    _, _, dropped = conditions_with_census([record(bare)], resolves)
    assert dropped == {CONDITION_NO_TEXT: 1}


def test_a_promise_whose_parties_resolve_to_nobody_is_the_fixable_one() -> None:
    """THE REASON THAT MATTERS. Its sibling correlator dropped all 95 of the pilot's dependency
    claims here, and the timeline correlator could not report the same thing happening to it.
    This is the identity cascade failing, not the vocabulary working."""
    _, _, dropped = conditions_with_census([record(commitment(condition="once legal confirms"))],
                                           resolves_nobody)
    assert dropped == {CONDITION_UNRESOLVED_SUBJECT: 1}


def test_the_same_promise_restated_is_counted_apart_from_the_losses() -> None:
    """A promise repeated across three emails is ONE condition and two duplicates — collapsed
    input, not lost input. Folding it in with the refusals would inflate the loss with the thing
    the deduplication is for."""
    said = commitment(condition="once legal confirms")
    records = [record(said, event_id="evt_1"),
               record(said, event_id="evt_2", at=_AT.replace(day=2)),
               record(said, event_id="evt_3", at=_AT.replace(day=3))]
    conditions, examined, dropped = conditions_with_census(records, resolves)
    assert len(conditions) == 1
    assert (examined, dropped) == (3, {CONDITION_DUPLICATE: 2})


def test_the_earliest_statement_is_the_one_kept() -> None:
    """"You said in May" is the sentence the card is built on, so deduplication must not let a
    later restatement overwrite the first. Checked here because the census walk is now the code
    that does the keeping."""
    said = commitment(condition="once legal confirms")
    late = record(said, event_id="evt_late", at=_AT.replace(day=20))
    early = record(said, event_id="evt_early", at=_AT)
    conditions, _, _ = conditions_with_census([late, early], resolves)
    assert len(conditions) == 1
    assert conditions[0].event_id == "evt_early"


# -------------------------------------------------------------------------------------------------
# THE CENSUS MUST ADD UP, AND MUST NOT JUDGE
# -------------------------------------------------------------------------------------------------

def test_every_promise_examined_is_either_emitted_or_named() -> None:
    """THE PROPERTY THE WHOLE UNIT EXISTS FOR. Once every refusal has a name, `examined` minus
    the emitted conditions must equal the sum of the reasons — nothing may vanish unaccounted."""
    records = [record(commitment(condition="once legal confirms", action="send the contract"),
                      commitment(condition=None, action="say hello"),
                      commitment(condition="once legal confirms", action="send the contract"),
                      event_id="evt_1"),
               record(commitment(condition="after the board meets", action="confirm pricing"),
                      event_id="evt_2", at=_AT.replace(day=4))]
    conditions, examined, dropped = conditions_with_census(records, resolves)
    assert examined - len(conditions) == sum(dropped.values()), (
        f"{examined} examined, {len(conditions)} emitted, reasons {dropped} — a promise vanished")


def test_a_reason_that_did_not_happen_is_never_reported() -> None:
    """A zero count is not evidence of anything; `census` drops them and this walk must not
    manufacture them on the way in."""
    _, _, dropped = conditions_with_census([record(commitment(condition="once legal confirms"))],
                                           resolves)
    assert dropped == {}


def test_nothing_here_holds_an_opinion_about_a_healthy_conversion() -> None:
    """THE RULE THIS UNIT REFUSES TO WRITE, checked as code rather than prose — an earlier cut of
    the dependency version grepped for the word "healthy" and caught the docstring explaining why
    there is no such rule. What must be absent is a comparison: a number this walk could measure
    a rate against."""
    import ast
    import inspect

    from genios_engine.context import correlation_timeline

    tree = ast.parse(inspect.getsource(correlation_timeline.conditions_with_census))
    compares = [c for c in ast.walk(tree) if isinstance(c, ast.Compare)
                and any(isinstance(x, ast.Constant) and isinstance(x.value, (int, float))
                        and not isinstance(x.value, bool) and x.value not in (0, 1)
                        for x in c.comparators)]
    assert compares == [], "the census walk is comparing against a threshold"


# -------------------------------------------------------------------------------------------------
# THE WIRING
# -------------------------------------------------------------------------------------------------

def test_the_old_signature_still_answers_the_same_way() -> None:
    """Every existing caller asks for conditions and nothing else. The census must be an addition,
    not a migration — a changed signature here would be a change to the correlator's contract for
    the sake of a diagnostic."""
    records = [record(commitment(condition="once legal confirms"), event_id="evt_1"),
               record(commitment(condition=None), event_id="evt_2", at=_AT.replace(day=2))]
    assert conditions_from(records, resolves) == conditions_with_census(records, resolves)[0]


def test_the_sweep_publishes_the_named_reasons_inside_its_write() -> None:
    """Checked by AST NESTING, not text order: moving the census below the `with` block — outside
    the transaction, which is the defect — still reads as "after the write" to a string compare.
    And the sweep must pass BOTH the commitment count and the reasons, since publishing the
    census without them is the state this unit was written to end."""
    import ast
    import inspect

    from genios_engine.context import correlation_timeline

    tree = ast.parse(inspect.getsource(correlation_timeline))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "record_conversion"]
    assert len(calls) == 1, "exactly one timeline census is expected"
    passed = {k.arg for k in calls[0].keywords}
    assert {"read", "emitted", "dropped"} <= passed, f"census published without reasons: {passed}"

    # `read` must be the commitment count the walk returned, never `len(records)` again.
    read_arg = next(k.value for k in calls[0].keywords if k.arg == "read")
    assert isinstance(read_arg, ast.Name) and read_arg.id == "examined", (
        "the census denominator regressed to counting mail instead of promises")

    holders = [w for w in ast.walk(tree) if isinstance(w, ast.With)
               and any(getattr(c.func, "id", "") == "_write_facts"
                       for c in ast.walk(w) if isinstance(c, ast.Call))]
    assert holders and any(calls[0] in ast.walk(w) for w in holders), (
        "the census is not inside the transaction that writes the facts it counts")
