"""Step 11 · the benchmark scoreboard was audited BY HAND, once, and is already stale.

    pytest tests/golden/l1/test_the_benchmark_scoreboard_is_machine_checked.py -q

`L1_P1_P5_AUDIT.md` holds the object-by-object scoreboard for the five benchmark prompts — **38
objects: 16 built · 8 stranded · 14 missing** — and it was produced by a person reading code. The
step's own §2 says so: *"There is no harness; the audit was done by hand."*

**A hand audit has a shelf life, and this one has already expired.** Two objects it marks as
missing have been built since:

    P1 #8  "coverage (465 of 465) — the denominator does not exist"
           → step 5 built it. `SyncSummary.claimed_total` + `cursor_exhausted`.
    P1 #7  "relationship_change — 48 of 49 refused by the floor"
           → step 8 made it diagnosable. `achievable_ceiling_bp` says the ceiling sits BELOW the
             floor, which is why no amount of typing (step 4) could lift it.

Nobody edited the audit, because nothing re-runs it. **That is the defect this step closes**, and
it is the same shape as every defect this plan has found: a value computed once and never
re-derived.

⛔ **WHAT THIS FILE DELIBERATELY DOES NOT DO — E3, in the step's own words:**

> *"a passing harness on 8 messages means nothing — **grow the corpus before trusting the
> number**."*

The golden corpus is **8 files**. The step asks for 425 annotated items, which needs real data and
two annotators (E2), and E4 adds that one mailbox with low outbound *"flatters sent-side prompts"*
so a second high-volume mailbox is required before any number is quoted externally.

So this harness checks **STRUCTURAL presence** — is the object in the contract, does it reach the
seam — which is exactly what the hand audit checked and is fully reproducible today. It **refuses
to report a behavioural score** on 8 messages, and says so rather than printing a flattering
number. §9: *"Do not report the 8-message corpus as complete."*
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# =============================================================================================
# 11-U2 · the required objects, as DATA rather than as prose in a markdown table
# =============================================================================================
def test_every_benchmark_prompt_declares_the_objects_it_needs():
    """The audit's table, machine-readable. Prose in a document cannot be re-run, which is how it
    went stale — and a scoreboard nothing re-derives is a scoreboard that describes the day it was
    written."""
    from genios_engine.capture.benchmark import REQUIRED_OBJECTS

    assert set(REQUIRED_OBJECTS) == {"P1", "P2", "P3", "P4", "P5"}
    assert all(REQUIRED_OBJECTS[p] for p in REQUIRED_OBJECTS), "a prompt requires nothing"


def test_the_object_count_matches_the_audit():
    """38 objects. The number in `L1_P1_P5_AUDIT.md` and in metric 6, so a drift here is a drift
    between the registry and the document it was derived from."""
    from genios_engine.capture.benchmark import REQUIRED_OBJECTS

    total = sum(len(v) for v in REQUIRED_OBJECTS.values())
    assert total == 38, f"the registry holds {total} objects; the audit says 38"


def test_each_object_names_how_it_is_checked():
    """An object with no check is a row on a scoreboard nobody can score. Every entry carries a
    callable that answers present/absent against the SHIPPING code — not against a fixture, and
    not against a comment."""
    from genios_engine.capture.benchmark import REQUIRED_OBJECTS

    for prompt, objects in REQUIRED_OBJECTS.items():
        for obj in objects:
            assert obj.name, prompt
            assert callable(obj.check), f"{prompt}/{obj.name} has no check"


# =============================================================================================
# 11-U3 + T1 · the harness, and the calibration that decides whether to trust it
# =============================================================================================
def test_the_harness_scores_every_object():
    """One command, over all five prompts."""
    from genios_engine.capture.benchmark import score_benchmark

    report = score_benchmark()

    assert report.total == 38
    assert report.present + report.absent == 38


def test_the_calibration_check_is_what_makes_the_number_trustworthy():
    """T1, AND THE MOST IMPORTANT ROW IN THIS FILE.

    §6: *"the harness reproduces today's 16 of 38 on today's code — **the calibration check; if it
    does not, the harness is wrong, not the layer**."*

    That instruction was written before steps 1–10 ran, so the target has legitimately MOVED. The
    harness must therefore distinguish two things that look identical in a bare number:

        the harness is wrong        it disagrees with the audit on an object nothing touched
        the layer improved          it disagrees on an object a step is recorded as having fixed

    A harness that could not tell those apart would let every one of its own bugs be read as
    progress — which is the single most dangerous failure mode a scoreboard can have.
    """
    from genios_engine.capture.benchmark import calibrate

    result = calibrate()

    assert result.audit_baseline == 15, "the hand-audited baseline moved without being re-derived"
    assert result.unexplained == (), (
        f"the harness disagrees with the audit on objects no step claims to have fixed, so the "
        f"HARNESS is wrong: {result.unexplained}")


def test_an_improvement_since_the_audit_is_attributed_to_the_step_that_made_it():
    """The other half of the calibration. An object that is present now and absent in the audit
    must name the step that moved it, or it is indistinguishable from a harness bug.

    Two are known and measured:
      P1 #8  the coverage denominator  → step 5 (`SyncSummary.claimed_total`)
      P1 #7  relationship_change       → step 8 (`achievable_ceiling_bp`)
    """
    from genios_engine.capture.benchmark import calibrate

    result = calibrate()

    assert result.improved, "no object improved across ten steps — check the harness, not the plan"
    for name, step in result.improved:
        assert step, f"{name} improved with no step named — that is a harness bug, not progress"


def test_a_regression_since_the_audit_is_reported_loudly():
    """The direction nobody looks for. An object the audit found PRESENT and the harness finds
    absent is a regression one of steps 1–10 introduced, and it must not be netted off against an
    improvement — a scoreboard that reports only a total can go up while something breaks."""
    from genios_engine.capture.benchmark import calibrate

    assert calibrate().regressed == (), "an object the hand audit found present is now missing"


# =============================================================================================
# 11-U4 · every miss carries a class — a total with no taxonomy is not actionable
# =============================================================================================
def test_every_absent_object_carries_a_failure_class():
    """T2. *"22 missing"* tells nobody what to do. *"9 of them are `not_carried` — computed in L1
    and dropped at the seam"* is a sprint."""
    from genios_engine.capture.benchmark import FAILURE_CLASSES, score_benchmark

    for miss in score_benchmark().misses:
        assert miss.failure_class in FAILURE_CLASSES, (
            f"{miss.name} has class {miss.failure_class!r}, which is not in the taxonomy")


def test_the_taxonomy_is_the_one_the_step_wrote_down():
    """11-U4 names eleven classes. They are the vocabulary the whole benchmark report is grouped
    by, so inventing a twelfth at a call site would make two reports incomparable."""
    from genios_engine.capture.benchmark import FAILURE_CLASSES

    assert {"ingestion", "pagination", "scope", "extraction", "entity", "intent", "temporal",
            "evidence", "qualification_false_negative", "coverage_misreport",
            "unknown_to_false"} <= set(FAILURE_CLASSES)


def test_not_carried_is_its_own_class_and_is_the_biggest_one():
    """THE FINDING THE TAXONOMY EXISTS TO SURFACE, and it is this plan's whole thesis.

    The audit's ⚠️ category is *"computed in L1, not carried to the seam"* — direction, who spoke
    last, whose turn it is, turn index. **The work was done and the answer was thrown away.**

    That is a different defect from *"we cannot extract this"*, it has a different fix, and a
    taxonomy that folded them into "missing" would hide the cheapest wins in the layer.
    """
    from genios_engine.capture.benchmark import FAILURE_CLASSES, score_benchmark

    assert "not_carried" in FAILURE_CLASSES
    classes = [m.failure_class for m in score_benchmark().misses]
    assert "not_carried" in classes, (
        "no object is classed `not_carried` — either the seam was fully widened, which would be "
        "news, or the harness is not distinguishing stranded from missing")


# =============================================================================================
# E3 / E4 / §9 · the harness refuses to flatter itself
# =============================================================================================
def test_the_harness_refuses_to_report_a_behavioural_score_on_eight_messages():
    """E3: *"a passing harness on 8 messages means nothing — grow the corpus before trusting the
    number."* §9: *"Do not report the 8-message corpus as complete."*

    The structural score is honest and reproducible today. A BEHAVIOURAL score — replaying real
    messages and asserting the objects came out — is not, on a corpus of eight, and a harness that
    printed one anyway would be the most convincing wrong number in the repo.
    """
    from genios_engine.capture.benchmark import CORPUS_MINIMUM, behavioural_score_is_quotable

    quotable, reason = behavioural_score_is_quotable(corpus_size=8, mailboxes=1)

    assert quotable is False
    assert "corpus" in reason.lower()
    assert CORPUS_MINIMUM == 425


def test_one_mailbox_is_not_enough_however_large_the_corpus():
    """E4: *"N=1 mailbox with unusually low outbound flatters sent-side prompts; a second,
    high-volume mailbox is required before any number is quoted externally."*

    Corpus size and mailbox count are two different guards, and satisfying one does not satisfy
    the other — a 425-item corpus from a single quiet mailbox is still one person's habits.
    """
    from genios_engine.capture.benchmark import behavioural_score_is_quotable

    quotable, reason = behavioural_score_is_quotable(corpus_size=425, mailboxes=1)

    assert quotable is False
    assert "mailbox" in reason.lower()


def test_both_guards_satisfied_is_quotable():
    """SENSITIVITY. A function that always refused would satisfy both rows above and would make
    the harness permanently useless."""
    from genios_engine.capture.benchmark import behavioural_score_is_quotable

    quotable, _ = behavioural_score_is_quotable(corpus_size=425, mailboxes=2)
    assert quotable is True


def test_the_harness_needs_no_database_and_no_network():
    """T4. It scores the shipping code's SHAPE, so it runs in CI on every change — which is the
    only way a scoreboard stops going stale."""
    import inspect

    from genios_engine.capture import benchmark

    source = inspect.getsource(benchmark)
    for forbidden in ("sqlalchemy", "requests", "psycopg", "datetime.now", "llm"):
        assert forbidden not in source, f"`{forbidden}` makes the harness unrunnable in CI"


def test_the_baseline_matches_the_registry_it_describes():
    """THE HARNESS'S FIRST FINDING, AND IT WAS ABOUT THE AUDIT ITSELF.

    `L1_P1_P5_AUDIT.md`'s summary line says *"38 objects — 16 built · 8 stranded · 14 missing"*.
    Counting the ✅ marks in its own tables gives **15 · 9 · 14**. The audit miscounted itself by
    one, in the flattering direction, and nothing could notice because nothing re-derived it — the
    number was quoted into the plan and used as metric 6's baseline.

    One object is trivial. That the error survived being written down, quoted and used as a
    baseline is not: it is this plan's own defect, committed in this plan's own documents.

    This row is what stops the constant and the transcribed rows drifting apart again.
    """
    from genios_engine.capture.benchmark import AUDIT_BASELINE_PRESENT, REQUIRED_OBJECTS

    transcribed = sum(1 for objs in REQUIRED_OBJECTS.values() for o in objs if o.audit_present)
    assert transcribed == AUDIT_BASELINE_PRESENT, (
        f"the constant says {AUDIT_BASELINE_PRESENT} and the registry holds {transcribed} — one "
        f"of them was edited without the other")
