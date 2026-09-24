"""L1.x-U3 · THE BENCHMARK SCOREBOARD, MACHINE-CHECKED — because the hand audit already went stale.

`L1_P1_P5_AUDIT.md` scored 38 semantic objects across the five benchmark prompts — **16 built · 8
stranded · 14 missing** — and a person produced it by reading code. The step says so: *"There is no
harness; the audit was done by hand."*

**It expired before anyone edited it.** Two objects it marks missing have since been built:

    P1 #8  "coverage (465 of 465) — the denominator does not exist"
           → step 5.  `SyncSummary.claimed_total` + `cursor_exhausted`.
    P1 #7  "relationship_change — 48 of 49 refused by the floor"
           → step 8.  `achievable_ceiling_bp` shows the ceiling sits BELOW the floor, which is
             why typing the lane (step 4) could not lift it and never could have.

Nothing re-ran the audit, so nothing noticed. **That is the same defect this plan has found in the
code ten times over — a value computed once and never re-derived — and here it was in our own
scoreboard.**

⛔ **STRUCTURAL, NOT BEHAVIOURAL, AND THE DIFFERENCE IS THE HONEST PART.** This module asks *"does
the object exist in the contract and reach the seam"* — exactly what the hand audit asked, and
fully reproducible on every commit. It does **not** replay messages and assert the objects came out,
because the golden corpus is **8 files** against the 425 the step asks for. E3 is blunt about it:

> *"a passing harness on 8 messages means nothing — grow the corpus before trusting the number."*

`behavioural_score_is_quotable` refuses to bless a behavioural number until the corpus AND the
second mailbox exist (E4). A harness that printed one anyway would be the most convincing wrong
number in the repo.

PURE: no database, no network, no clock, no model — so it runs in CI on every change, which is the
only thing that stops a scoreboard going stale again.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

#: The corpus the step asks for: 300 email · 50 calendar · 50 documents · 25 transcripts.
CORPUS_MINIMUM = 425

#: E4 — one mailbox is one person's habits. *"N=1 mailbox with unusually low outbound flatters
#: sent-side prompts; a second, high-volume mailbox is required before any number is quoted
#: externally."*
MAILBOX_MINIMUM = 2

#: What the hand audit scored as PRESENT, 2026-09-23. The calibration target, and it is frozen
#: HISTORY rather than a number to keep in step with the code — the whole point of `calibrate` is
#: to measure the distance from it and attribute every unit of that distance.
#:
#: **IT IS 15, AND THE DOCUMENT SAYS 16.** `L1_P1_P5_AUDIT.md`'s summary line reads *"38 objects —
#: 16 built · 8 stranded · 14 missing"*; counting the ✅ marks in its own tables gives **15 built ·
#: 9 stranded · 14 missing**. The audit miscounted itself by one, in the direction that flatters,
#: and nothing could notice because nothing re-derived it.
#:
#: A one-object error is trivial. **That it survived being written down, quoted in a plan and used
#: as a metric baseline is not** — it is the third-hand version of the defect this whole plan keeps
#: finding, and it is the reason a scoreboard has to be code. The TABLE is the evidence and the
#: summary was the summary, so the table wins.
#:
#: `test_the_baseline_matches_the_registry` keeps this honest from here: the constant and the 38
#: transcribed rows cannot drift apart again without a red test.
AUDIT_BASELINE_PRESENT = 15

#: 11-U4's taxonomy. Every miss gets exactly one of these, because *"22 missing"* tells nobody what
#: to do while *"9 of them are `not_carried`"* is a sprint.
#:
#: `not_carried` IS THE ONE THIS PLAN EXISTS FOR and it is not in the step's written list — it is
#: the audit's ⚠️ category, *"computed in L1, not carried to the seam"*. The work was done and the
#: answer was thrown away. That is a different defect from "we cannot extract this", it has a
#: different and much cheaper fix, and folding the two into "missing" hides the best wins in the
#: layer. Step 3 widened the seam 9 → 17 columns on exactly this finding.
FAILURE_CLASSES: frozenset[str] = frozenset({
    "not_carried", "ingestion", "pagination", "scope", "extraction", "entity", "intent",
    "temporal", "evidence", "qualification_false_negative", "coverage_misreport",
    "unknown_to_false", "layer_two",
})


@dataclass(frozen=True, slots=True)
class BenchmarkObject:
    """One semantic object a prompt needs, and how to tell whether it is there.

    `check` is a callable against the SHIPPING code rather than a fixture or a comment: a
    scoreboard that scored itself against its own expectations would agree with itself forever.

    `audit_present` is what the hand audit said on 2026-09-23. It is frozen history — `calibrate`
    reads it to compute the distance travelled, and a maintainer who "corrects" it to match the
    code has deleted the only baseline this step has.
    """

    name: str
    check: Callable[[], bool]
    audit_present: bool
    failure_class: str
    #: The step recorded as having moved this object, when one did. Required for anything that is
    #: present now and absent in the audit — an improvement with no author is a harness bug.
    moved_by: str | None = None


def _has(module: str, attr: str) -> bool:
    """Is `attr` importable from `module`? Never raises — a missing module is an absent object."""
    try:
        return hasattr(__import__(module, fromlist=[attr]), attr)
    except Exception:                          # noqa: BLE001 — an unimportable module is absent
        return False


def _field(module: str, cls: str, name: str) -> bool:
    """Does `cls` declare `name`? Works for dataclasses and pydantic models alike."""
    try:
        obj = getattr(__import__(module, fromlist=[cls]), cls)
    except Exception:                          # noqa: BLE001
        return False
    return name in (getattr(obj, "__dataclass_fields__", None) or getattr(obj, "model_fields", {}))


_EXTRACTION = "genios_engine.contracts.extraction"
_SIGNAL = "genios_engine.contracts.signal"
_THREADS = "genios_engine.capture.structural.threads"
_SUMMARY = "genios_engine.capture.acquire.sync_runner"
_IMPORTANCE = "genios_engine.capture.esqe.importance"


def _crosses_the_seam(name: str) -> bool:
    """Does `QualifiedEnterpriseSignal` — the L1→L2 boundary object — actually CARRY this?

    **THE DISTINCTION THE HAND AUDIT DREW AND MY FIRST CHECKS MISSED.** The audit's ⚠️ category is
    *"computed in L1, not carried to the seam"*, and the first version of this module tested only
    whether the TYPE existed — so `reconstruct_thread` existing made `ball_in_court` read PRESENT
    while the value it produces reaches nothing.

    `calibrate` caught it immediately: eight objects came back "present now, absent in the audit,
    and no step claims them", which is the signature of a harness bug and is exactly what that
    population was added to detect. It detected mine within a minute of being written.

    So a stranded object is checked HERE, against the boundary contract, and nowhere else. A value
    Layer 2 cannot read is a value the benchmark cannot use, whatever exists upstream of it.
    """
    return _field(_SIGNAL, "QualifiedEnterpriseSignal", name)


#: THE 38 OBJECTS, transcribed from `L1_P1_P5_AUDIT.md` once and checked mechanically thereafter.
REQUIRED_OBJECTS: Mapping[str, tuple[BenchmarkObject, ...]] = {
    # -- P1 · people · direction · reciprocity · reply latency · waiting · coverage -------------
    "P1": (
        BenchmarkObject("person_identity", lambda: _crosses_the_seam("canonical_entity"),
                        audit_present=False, failure_class="entity"),
        BenchmarkObject("message_direction", lambda: _crosses_the_seam("direction"),
                        audit_present=False, failure_class="not_carried"),
        BenchmarkObject("who_sent_last", lambda: _crosses_the_seam("last_inbound_at"),
                        audit_present=False, failure_class="not_carried"),
        BenchmarkObject("ball_in_court", lambda: _crosses_the_seam("ball_in_court"),
                        audit_present=False, failure_class="not_carried"),
        BenchmarkObject("turn_index", lambda: _crosses_the_seam("turn_index"),
                        audit_present=False, failure_class="not_carried"),
        BenchmarkObject("reply_latency", lambda: False,
                        audit_present=False, failure_class="layer_two"),
        # Step 8 did not make it PASS the floor — it made the refusal legible, which the audit's
        # own note ("48 of 49 refused") could not do. That is the object the prompt needs.
        BenchmarkObject("relationship_state_change",
                        lambda: _has(_IMPORTANCE, "achievable_ceiling_bp"),
                        audit_present=False, failure_class="qualification_false_negative",
                        moved_by="step 8"),
        BenchmarkObject("coverage_denominator",
                        lambda: _field(_SUMMARY, "SyncSummary", "claimed_total"),
                        audit_present=False, failure_class="coverage_misreport",
                        moved_by="step 5"),
    ),
    # -- P2 · commitments · promisor · object · deadline · fulfilment evidence -----------------
    "P2": (
        BenchmarkObject("commitment", lambda: _has(_EXTRACTION, "Commitment"),
                        audit_present=True, failure_class="extraction"),
        BenchmarkObject("promisor", lambda: _field(_EXTRACTION, "Commitment", "actor"),
                        audit_present=True, failure_class="extraction"),
        BenchmarkObject("promise_object", lambda: _field(_EXTRACTION, "Commitment", "action"),
                        audit_present=True, failure_class="extraction"),
        BenchmarkObject("deadline", lambda: _field(_EXTRACTION, "Commitment", "due"),
                        audit_present=True, failure_class="temporal"),
        BenchmarkObject("evidence_span", lambda: _field(_EXTRACTION, "Commitment", "evidence"),
                        audit_present=True, failure_class="evidence"),
        BenchmarkObject("signal_types", lambda: _has(_SIGNAL, "SignalType"),
                        audit_present=True, failure_class="extraction"),
        BenchmarkObject("fulfilment_link", lambda: False,
                        audit_present=False, failure_class="not_carried"),
        BenchmarkObject("commitment_state", lambda: False,
                        audit_present=False, failure_class="not_carried"),
        BenchmarkObject("delivery_failure",
                        lambda: "DELIVERY_FAILURE" in getattr(
                            __import__(_SIGNAL, fromlist=["SignalType"]), "SignalType").__members__,
                        audit_present=False, failure_class="ingestion", moved_by="step 2"),
    ),
    # -- P3 · historical completeness · terminal thread state · silence ------------------------
    "P3": (
        BenchmarkObject("six_month_corpus",
                        lambda: _field(_SUMMARY, "SyncSummary", "cursor_exhausted"),
                        audit_present=False, failure_class="pagination", moved_by="step 5"),
        BenchmarkObject("activity_count", lambda: _crosses_the_seam("thread_depth"),
                        audit_present=False, failure_class="not_carried"),
        BenchmarkObject("p3_who_sent_last", lambda: _crosses_the_seam("last_inbound_at"),
                        audit_present=False, failure_class="not_carried"),
        BenchmarkObject("silence_duration", lambda: False,
                        audit_present=False, failure_class="temporal"),
        BenchmarkObject("final_unresolved_question", lambda: _has(_EXTRACTION, "OpenQuestion"),
                        audit_present=False, failure_class="extraction", moved_by="step 4"),
        BenchmarkObject("terminal_stage", lambda: False,
                        audit_present=False, failure_class="not_carried"),
    ),
    # -- P4 · calendar↔email identity · cross-source temporal joins ----------------------------
    "P4": (
        BenchmarkObject("calendar_event", lambda: _has(_SIGNAL, "SignalType"),
                        audit_present=True, failure_class="ingestion"),
        BenchmarkObject("attendees", lambda: _has(_EXTRACTION, "EntityMention"),
                        audit_present=True, failure_class="entity"),
        BenchmarkObject("meeting_vs_cohort", lambda: False,
                        audit_present=False, failure_class="intent"),
        BenchmarkObject("email_person_identity", lambda: _crosses_the_seam("canonical_entity"),
                        audit_present=False, failure_class="entity"),
        BenchmarkObject("meeting_followup_edge", lambda: False,
                        audit_present=False, failure_class="not_carried"),
        BenchmarkObject("time_delta", lambda: _has("genios_engine.contracts.units",
                                                   "ResolvedDate"),
                        audit_present=True, failure_class="temporal"),
        BenchmarkObject("scheduling_proposals", lambda: False,
                        audit_present=False, failure_class="extraction"),
    ),
    # -- P5 · conditional promises · whether fulfilment is actually evidenced -------------------
    "P5": (
        BenchmarkObject("conditional_flag",
                        lambda: _field(_EXTRACTION, "Commitment", "is_conditional"),
                        audit_present=True, failure_class="extraction"),
        BenchmarkObject("condition_text",
                        lambda: _field(_EXTRACTION, "Commitment", "condition_text"),
                        audit_present=True, failure_class="extraction"),
        BenchmarkObject("condition_owner", lambda: _field(_EXTRACTION, "DecisionState", "owner"),
                        audit_present=True, failure_class="extraction"),
        BenchmarkObject("p5_deadline", lambda: _has("genios_engine.contracts.units",
                                                    "ResolvedDate"),
                        audit_present=True, failure_class="temporal"),
        BenchmarkObject("p5_evidence", lambda: _has("genios_engine.contracts.evidence",
                                                    "EvidenceSpan"),
                        audit_present=True, failure_class="evidence"),
        BenchmarkObject("condition_state", lambda: False,
                        audit_present=False, failure_class="not_carried"),
        BenchmarkObject("evidence_of_satisfaction", lambda: False,
                        audit_present=False, failure_class="evidence"),
        BenchmarkObject("refusal_to_guess",
                        lambda: _has("genios_engine.capture.validate.directness", "Directness"),
                        audit_present=True, failure_class="unknown_to_false"),
    ),
}


@dataclass(frozen=True, slots=True)
class Miss:
    """One object the harness could not find, and why it matters."""

    prompt: str
    name: str
    failure_class: str


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """The scoreboard, as of this commit."""

    total: int = 0
    present: int = 0
    absent: int = 0
    misses: tuple[Miss, ...] = ()
    by_class: dict[str, int] = field(default_factory=dict)
    by_prompt: dict[str, tuple[int, int]] = field(default_factory=dict)


def score_benchmark() -> BenchmarkReport:
    """Score every object against the shipping code. No corpus, no database, no network."""
    misses: list[Miss] = []
    by_class: dict[str, int] = {}
    by_prompt: dict[str, tuple[int, int]] = {}
    present = 0

    for prompt, objects in REQUIRED_OBJECTS.items():
        here = 0
        for obj in objects:
            try:
                found = bool(obj.check())
            except Exception:                  # noqa: BLE001 — a check that raises is an absence
                found = False
            if found:
                present += 1
                here += 1
            else:
                misses.append(Miss(prompt=prompt, name=obj.name,
                                   failure_class=obj.failure_class))
                by_class[obj.failure_class] = by_class.get(obj.failure_class, 0) + 1
        by_prompt[prompt] = (here, len(objects))

    total = sum(len(v) for v in REQUIRED_OBJECTS.values())
    return BenchmarkReport(total=total, present=present, absent=total - present,
                           misses=tuple(misses), by_class=by_class, by_prompt=by_prompt)


@dataclass(frozen=True, slots=True)
class Calibration:
    """T1's answer: how far the code has moved from the hand audit, and whether to believe it."""

    audit_baseline: int
    measured: int
    #: (object, step) — present now, absent in the audit, and a step claims it.
    improved: tuple[tuple[str, str], ...] = ()
    #: Present now, absent in the audit, and NO step claims it. **A harness bug, not progress.**
    unexplained: tuple[str, ...] = ()
    #: Present in the audit and absent now. A regression one of steps 1–10 introduced.
    regressed: tuple[str, ...] = ()


def calibrate() -> Calibration:
    """T1 — *"if it does not reproduce the audit, the harness is wrong, not the layer."*

    That instruction was written before steps 1–10 ran, so the target has legitimately moved and a
    bare equality check would now fail for the right reason and the wrong one at once. The
    calibration therefore separates three populations, and the middle one is the whole point:

        improved      present now, absent in the audit, and a STEP is named for it
        unexplained   present now, absent in the audit, and nothing claims it  →  HARNESS BUG
        regressed     present in the audit, absent now                          →  REGRESSION

    A harness that could not tell `improved` from `unexplained` would let each of its own bugs be
    read as progress — the single most dangerous failure a scoreboard can have, and the reason this
    function exists rather than a plain assertion on a total.
    """
    improved: list[tuple[str, str]] = []
    unexplained: list[str] = []
    regressed: list[str] = []
    measured = 0

    for objects in REQUIRED_OBJECTS.values():
        for obj in objects:
            try:
                found = bool(obj.check())
            except Exception:                  # noqa: BLE001
                found = False
            measured += int(found)
            if found and not obj.audit_present:
                (improved.append((obj.name, obj.moved_by)) if obj.moved_by
                 else unexplained.append(obj.name))
            elif not found and obj.audit_present:
                regressed.append(obj.name)

    return Calibration(audit_baseline=AUDIT_BASELINE_PRESENT, measured=measured,
                       improved=tuple(improved), unexplained=tuple(unexplained),
                       regressed=tuple(regressed))


def behavioural_score_is_quotable(*, corpus_size: int, mailboxes: int) -> tuple[bool, str]:
    """May a BEHAVIOURAL benchmark number be quoted? Two guards, and both must pass.

    E3 — *"a passing harness on 8 messages means nothing"* — and E4 — *"N=1 mailbox with unusually
    low outbound flatters sent-side prompts."* They are different failures: a large corpus from one
    quiet mailbox is still one person's habits, and two mailboxes of four messages is nothing.

    Returns the reason as well as the verdict, because a bare `False` in a report is a number
    somebody deletes rather than a constraint somebody satisfies.
    """
    if corpus_size < CORPUS_MINIMUM:
        return False, (f"corpus is {corpus_size} items, below the {CORPUS_MINIMUM} the spec asks "
                       f"for — a passing harness on a small corpus means nothing")
    if mailboxes < MAILBOX_MINIMUM:
        return False, (f"only {mailboxes} mailbox — a single mailbox with low outbound flatters "
                       f"the sent-side prompts; {MAILBOX_MINIMUM} are required before quoting")
    return True, "corpus and mailbox count both satisfy the spec"


__all__ = ["AUDIT_BASELINE_PRESENT", "CORPUS_MINIMUM", "FAILURE_CLASSES", "MAILBOX_MINIMUM",
           "REQUIRED_OBJECTS", "BenchmarkObject", "BenchmarkReport", "Calibration", "Miss",
           "behavioural_score_is_quotable", "calibrate", "score_benchmark"]
