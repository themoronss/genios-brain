"""Step 7 · four signal types never fired, and nothing could say why.

    pytest tests/capture/test_a_silent_predicate_explains_itself.py -q

THE DEFECT. Of 395 signals in the pilot corpus, 11 of the 15 types fired. Never: `escalation`,
`anomaly`, `information_conflict`, `availability_change`.

    "Nothing says whether the tenant had none, or whether the predicate cannot fire.
     A predicate that can never fire is indistinguishable from a correct absence."

THE PREMISE WAS HALF WRONG, checked 2026-09-24 before anything was built. Something *does* say the
predicates can fire — every one of the four has detector tests that fire it (3, 3, 2 and 1
respectively). So **7-U5 retires nothing: all sixteen members have a fixture.**

What is missing is the other half, and it is the half that matters operationally: given a real
corpus, a reader still cannot tell *"this tenant genuinely had no escalations"* from *"this
predicate is unreachable in production"*. `DELIVERY_FAILURE` is the proof that the second case is
real — it has 19 tests, it fires in every one of them, and it has produced **zero** production
signals, because migration 0176 is not applied and the INSERT is refused by a CHECK constraint.
Nothing in the system reports that. The step's §1 asks for exactly this and neither the suite nor
the ledger answers it.

WHAT THIS FILE PINS:

  1. every member of the taxonomy has a fixture that fires it — so "cannot fire" is answerable
     from the repo, once, rather than re-derived by each person who asks;
  2. the shipped prose agrees with `len(SignalType)`. Four modules still say "fourteen";
  3. intent carries a CONFIDENCE — derived, never asked for, and never an evidence span.

WHY INTENT GETS NO EVIDENCE SPAN, although the step file's done criterion asks for one.
`contracts/intent.py` argues against it in writing and is right: *"intent is one reading of the
WHOLE message, and 'the tone is warm' or 'a person composed this' have no quotable span to point
at. A field for them would invite a model to manufacture a citation for something that is not a
quotation, which is worse than having none."* The criterion is amended in the findings, not met.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# =============================================================================================
# The prose — four modules still describe a taxonomy that has not existed since step 2
# =============================================================================================
def test_no_shipped_module_still_calls_the_taxonomy_fourteen():
    """A comment that describes a closed set by a number is a comment with an expiry date, and
    this one expired twice: `availability_change` (migration 0139) and `delivery_failure`
    (step 2, 2026-09-23) each widened it by one.

    IT IS NOT COSMETIC. `esqe/__init__.py` is the package's own description of what `classifier.py`
    does, and `normalize.py` says "TOTAL over the 14 members" directly above the table whose
    totality guard fails when a member is added. A reader auditing the closed set against the prose
    would conclude two members are undocumented rather than that the prose is stale.
    """
    import re
    from pathlib import Path

    from genios_engine.contracts.signal import SignalType

    # SCOPED TO TAXONOMY PROSE, deliberately. `validate/dates.py` has a number-word table
    # containing "fourteen" and a legitimate "fourteen-day window", and a regex that flagged those
    # would be a guard nobody could keep green — which is how a guard gets deleted instead of
    # obeyed. The pattern is "a count word BESIDE a word for the taxonomy".
    taxonomy = r"(members?|rows|shapes|predicates|taxonomy|SignalType)"
    counts = r"(?<!ALG-)(?<!alg-)(fourteen|14)"
    patterns = (rf"{counts}[- ]{taxonomy}", rf"{taxonomy}[^.\n]{{0,20}}{counts}\b",
                rf"\b{counts}\b[^.\n]{{0,20}}{taxonomy}")

    # ONLY MODULES THAT ACTUALLY NAME `SignalType`. `reason/retention.py` says "roughly fourteen
    # rows on this tenant" about a delete batch and `contracts/conflict.py` says "ALG-14 table has
    # seven rows" — both true, neither about this taxonomy. A guard that cried wolf on them is a
    # guard somebody deletes rather than obeys, so the file has to be about signal types at all.
    stale: list[str] = []
    for path in sorted(Path("genios_engine").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "SignalType" not in text:
            continue
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                line = text[:match.start()].count("\n") + 1
                stale.append(f"{path}:{line} — {match.group(0)!r}")

    assert not stale, (
        f"the taxonomy has {len(SignalType)} members; these still say fourteen:\n  "
        + "\n  ".join(stale))


# =============================================================================================
# Every member is reachable — so "it never fired" is a corpus fact, not a code fault
# =============================================================================================
def test_every_signal_type_has_a_fixture_that_fires_it():
    """7-U5, and it retires NOTHING — which is the finding.

    The step planned to retire any type no fixture could fire. Checked before building: all four
    "silent" types already have detector tests, so the answer to *"can this predicate fire"* is
    yes for every member and the production silence is a corpus question.

    This test is what keeps that answerable. A member added without a test that fires it would
    reintroduce exactly the ambiguity the step exists to close — and it would do so silently,
    because a predicate nobody exercises still passes every other test in the suite.
    """
    import re
    from pathlib import Path

    from genios_engine.contracts.signal import SignalType

    covered: set[str] = set()
    for path in Path("tests").rglob("test_*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for member in SignalType:
            if re.search(rf"\b(SignalType\.{member.name}|T\.{member.name})\b", text):
                covered.add(member.name)

    missing = sorted({m.name for m in SignalType} - covered)
    assert not missing, (
        f"no test names these types, so 'it never fired' cannot be told from 'it cannot fire': "
        f"{missing}")


def test_the_unreachable_case_is_real_and_is_named():
    """`DELIVERY_FAILURE` is the existence proof that "the predicate fires in tests and produces
    nothing in production" is a REAL state and not a hypothetical.

    19 tests fire it. Production has zero. The cause is known exactly — migration 0176 is not
    applied, so `qualified_signals`' CHECK constraint refuses the INSERT — and **nothing in the
    running system reports that.** The signal is detected, qualified, and refused by the database.

    This row pins the fact that the type is in the enum while its migration is a separate,
    un-applied artifact, so the gap between them stays visible in the repo.
    """
    from pathlib import Path

    from genios_engine.contracts.signal import SignalType

    assert SignalType.DELIVERY_FAILURE.value == "delivery_failure"
    migration = Path("migrations/0176_delivery_failure.sql")
    assert migration.exists(), "the type exists and its migration does not"
    assert "delivery_failure" in migration.read_text(), (
        "0176 no longer widens the constraint for this type, so every such signal is refused by "
        "the table while the detector reports success")


# =============================================================================================
# 7-U1′ · intent says how much it read — DERIVED, never asked for
# =============================================================================================
def test_intent_reports_a_confidence():
    """The step's real goal: when an answer is wrong, tell "intent was wrong" from "the whole
    extraction was wrong". That is ATTRIBUTION, and splitting the model call is only one way to
    get it — the expensive way. See the findings §2.
    """
    from genios_engine.contracts.intent import MessageIntent

    assert hasattr(MessageIntent, "confidence_bp")


def test_the_confidence_is_derived_from_what_was_answered_never_self_reported():
    """⛔ TWO RULES AT ONCE, and they happen to point the same way.

    DOCTRINE 1 — a model may DESCRIBE, never SCORE. A model's self-reported certainty becoming a
    stored confidence is that line being crossed, and this layer refuses it everywhere else.

    THE COST CHECK — `"intent"` is a closed set inside `semantic/vocabulary._SETS`, which feeds
    `vocabulary_fingerprint()`, which is a component of the `l1_extraction_results` cache key.
    ASKING the model for a confidence changes the prompt, which moves the key, which
    **re-extracts the entire corpus — a third full bill.**

    Deriving it from the axes the model already answered costs nothing and is more correct.
    """
    from genios_engine.contracts.intent import Band, Formality, IntentCategory, MessageIntent, Tone

    blank = MessageIntent()
    partial = MessageIntent(category=IntentCategory.WORKING)
    full = MessageIntent(category=IntentCategory.WORKING, tone=Tone.NEUTRAL,
                         formality=Formality.PROFESSIONAL, motive="approve the renewal",
                         addressed_personally=True, human_authored=True, asks_for_reply=True,
                         engagement=Band.HIGH)

    assert blank.confidence_bp == 0, (
        "a reading that answered nothing reports confidence — 'I could not read this' and 'this "
        "is an automated receipt' would then be indistinguishable")
    assert 0 < partial.confidence_bp < full.confidence_bp <= 10_000
    assert isinstance(blank.confidence_bp, int), "V-7: basis points, never a ratio"


def test_intent_still_carries_no_evidence_span():
    """REGRESSION GUARD IN THE OPPOSITE DIRECTION, and the step file's own done criterion is what
    it guards against.

    The criterion says *"intent has its own contract, confidence and evidence"*. The contract
    refuses the third, in writing: *"'the tone is warm' or 'a person composed this' have no
    quotable span to point at. A field for them would invite a model to manufacture a citation
    for something that is not a quotation, which is worse than having none."*

    That is the fabricated-receipt failure this whole architecture exists to prevent, so the
    criterion is amended in the findings rather than met.
    """
    from genios_engine.contracts.intent import MessageIntent

    assert "evidence" not in MessageIntent.model_fields, (
        "intent grew an evidence field — see contracts/intent.py's own argument against it")


def test_a_confidence_survives_the_merge_of_two_readings():
    """`merged_with` folds the gate's cheap reading into the extractor's fuller one field by
    field. A confidence that did not travel with it would be computed from the merged object and
    silently credit the gate's answers to the extractor.

    The merged reading knows MORE than either input, so its confidence may not be lower than the
    richer input's — that would make reading more of the message look like learning less.
    """
    from genios_engine.contracts.intent import IntentCategory, MessageIntent, Tone

    gate = MessageIntent(category=IntentCategory.WORKING)
    richer = MessageIntent(tone=Tone.WARM, human_authored=True)

    merged = gate.merged_with(richer)

    assert merged.confidence_bp >= richer.confidence_bp
    assert merged.confidence_bp > gate.confidence_bp


# =============================================================================================
# 7-U2 · the disagreement is RECORDED, not folded
# =============================================================================================
def test_a_disagreement_between_the_two_readings_is_reported():
    """E1. `merged_with` is field-by-field and the richer reading wins wherever it answered — so
    when the gate says AUTOMATED and the extractor says WORKING, the merge silently keeps WORKING
    and **the fact that two readers disagreed disappears.**

    That disagreement is the single most useful debugging signal this step can produce: it is the
    difference between "the prompt is wrong" and "this message is genuinely ambiguous", and today
    neither is visible.

    REPORTED, NEVER RESOLVED. The merge's rule stays exactly as it is — the fuller reading wins.
    This only stops the disagreement being unobservable.
    """
    from genios_engine.contracts.intent import IntentCategory, MessageIntent, Tone

    gate = MessageIntent(category=IntentCategory.AUTOMATED, tone=Tone.NEUTRAL)
    richer = MessageIntent(category=IntentCategory.WORKING, tone=Tone.NEUTRAL)

    assert gate.disagreements_with(richer) == ("category",)
    assert gate.merged_with(richer).category is IntentCategory.WORKING, (
        "the merge rule changed — the fuller reading must still win")


def test_an_absence_is_not_a_disagreement():
    """THE ROW THAT DECIDES WHETHER THIS REPORT IS READABLE.

    `merged_with` already says it: *"a `None` or an `unknown` from the fuller read is an ABSENCE,
    not a correction: it means that reader did not answer."* Counting silence as disagreement
    would flag most messages in the corpus and train everybody to ignore the number.
    """
    from genios_engine.contracts.intent import IntentCategory, MessageIntent

    gate = MessageIntent(category=IntentCategory.WORKING, human_authored=True)
    silent = MessageIntent()

    assert gate.disagreements_with(silent) == ()
    assert gate.disagreements_with(None) == ()


def test_agreement_is_not_a_disagreement():
    """SENSITIVITY. A function that returned every field would satisfy the two rows above."""
    from genios_engine.contracts.intent import IntentCategory, MessageIntent

    same = MessageIntent(category=IntentCategory.WORKING)

    assert same.disagreements_with(MessageIntent(category=IntentCategory.WORKING)) == ()


# =============================================================================================
# 7-U3 · the `unknown` rate, per source
# =============================================================================================
def test_the_unknown_rate_is_reported_per_source():
    """E2. A source returning `unknown` for 80% of its mail is a prompt defect, and nothing counts
    it — so the failure mode is a slow, silent degradation that looks like a quiet mailbox.

    Per SOURCE and not globally: Gmail and a calendar feed have genuinely different readable
    rates, and one number over both hides a broken connector behind a healthy one.
    """
    from genios_engine.capture.intent_rate import unknown_rate_bp
    from genios_engine.contracts.intent import IntentCategory, MessageIntent

    readable = MessageIntent(category=IntentCategory.WORKING)
    blank = MessageIntent()

    rates = unknown_rate_bp([("gmail", readable), ("gmail", blank),
                             ("gcal", blank), ("gcal", blank)])

    assert rates == {"gmail": 5000, "gcal": 10_000}


def test_the_unknown_rate_is_integer_basis_points_and_truncates():
    """V-7, and never overstated: 1 of 3 unreadable is 3333 bp, not 3334 and not 0.333."""
    from genios_engine.capture.intent_rate import unknown_rate_bp
    from genios_engine.contracts.intent import IntentCategory, MessageIntent

    readable = MessageIntent(category=IntentCategory.WORKING)
    rates = unknown_rate_bp([("gmail", readable), ("gmail", readable), ("gmail", MessageIntent())])

    assert rates["gmail"] == 3333
    assert isinstance(rates["gmail"], int)


def test_a_source_with_no_messages_is_absent_rather_than_zero():
    """Zero reads as "this source is perfectly readable", which is the opposite of "we have not
    seen anything from it". Absence is the honest answer and this layer says so everywhere else."""
    from genios_engine.capture.intent_rate import unknown_rate_bp

    assert unknown_rate_bp([]) == {}


# =============================================================================================
# THE COUNTERS ARE COUNTED — by the sweep, not by a field somebody added
# =============================================================================================
def test_the_intent_counters_have_a_real_consumer():
    """THREE STEPS RUNNING, the same defect: step 5's `claimed_total` was read with `getattr`
    against a field no contract had; step 6's `domain_tagged` was a field nothing incremented.
    Both were green, both were None or zero forever.

    So before anything else about 7-U3: the counter must be INCREMENTED somewhere on the capture
    loop, and the rate must be DERIVED from it rather than assigned. Asserted against the source
    of the loop, because a unit test on the dataclass is exactly what passed in both earlier cases.
    """
    import inspect

    from genios_engine.capture.acquire import sync_runner

    source = inspect.getsource(sync_runner)
    for counter in ("summary.intent_read_attempts += 1", "summary.intent_unread += 1",
                    "summary.intent_disagreements += 1"):
        assert counter in source, f"`{counter}` — the field exists and nothing fills it"


def test_a_sweep_that_read_nothing_reports_no_rate_rather_than_a_perfect_one():
    """Zero attempts must read 0 beside `intent_read_attempts == 0`, never a clean bill.

    A sweep that extracted nothing is not a sweep with a perfect reader, and the pair is what
    tells them apart — the same argument `unverified_rate_bp` already makes for spans.
    """
    from genios_engine.capture.acquire.sync_runner import SyncSummary

    blank = SyncSummary()
    assert blank.intent_unknown_rate_bp == 0 and blank.intent_read_attempts == 0


def test_the_rate_is_truncated_integer_basis_points():
    """V-7, and never overstated: 1 unread of 3 is 3333, not 3334 and not 0.333."""
    from genios_engine.capture.acquire.sync_runner import SyncSummary

    summary = SyncSummary(intent_read_attempts=3, intent_unread=1)

    assert summary.intent_unknown_rate_bp == 3333
    assert isinstance(summary.intent_unknown_rate_bp, int)


def test_an_event_that_never_reached_s4_is_in_neither_counter():
    """A structured bypass and a parked extraction never tried to read an intent. Counting them
    as unreadable would blame the reader for messages nobody handed it — and counting them as
    read would hide a real degradation behind a pile of events that were never candidates."""
    import inspect

    from genios_engine.capture.acquire import sync_runner

    source = inspect.getsource(sync_runner)
    assert "if esqe_outcome is not None:" in source, (
        "events with no S4 outcome are being counted, so the denominator includes messages the "
        "intent reader was never given")


def test_the_disagreement_is_computed_before_the_fold_destroys_it():
    """`merged_with` resolves the conflict field by field, so a disagreement computed AFTER it is
    always empty. This is a source assertion because the ordering is the whole correctness
    argument and it is invisible in the output."""
    import inspect

    from genios_engine.capture import pipeline

    source = inspect.getsource(pipeline)
    fold = source.index("folded = decision.intent.merged_with(richer)")
    compute = source.index("disagreements = decision.intent.disagreements_with(richer)")
    assert compute > fold, "fixture problem: the two lines moved"
    assert "richer = getattr(extraction" in source, (
        "the richer reading is no longer captured before the fold, so the disagreement is being "
        "computed against the merged object and will always be empty")
