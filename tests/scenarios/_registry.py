"""Step 17 · the 39 scenarios, their failure classes, and what each one is actually worth.

§6 condition 5: *"It carries a failure class. An untyped failure cannot be counted, compared or
trended."* So the class has to be **machine-readable**, and `--strict-markers` plus twenty new
pytest markers would be a taxonomy nobody maintains. This is the repo's own totality-guard idiom
instead — the one `PRECEDENCE`, `SIGNAL_TYPE_WEIGHT_BP` and `ANCHOR_FAMILIES` already use: a table
with a row per member, and an import-time check that nothing is missing from either side.

⛔ **THE PREMISE CORRECTION THAT SHAPES THIS WHOLE STEP.**

§8 says *"every one of them was RED first, for the stated reason"*. **That criterion cannot be met,
and meeting it would mean the previous sixteen steps failed.** The plan was written before they ran.
S01's *"fails today because `In-Reply-To` never captured"* was true when it was written and step 16
closed it; S03's attendee `responseStatus` was closed by step 13; S21/S22's coverage gate is step
12's and step 15's.

A scenario describing a defect that has since been **fixed** cannot go red — and rewriting the code
to make it red would be the one thing §9 forbids.

**So RED-first is replaced, for those, by something strictly stronger: technique 3.** §2 already
names it and §6 condition 2 already requires it —

> *"a fix is not accepted until technique 3 has been applied to it — neutralise the fix and confirm
> the probe goes red. A probe that passes with the fix removed proves nothing."*

Neutralising the fix and watching the probe go red proves the probe is sensitive **to that fix
specifically**, which is more than RED-first ever proved: a test can be red today for a reason that
has nothing to do with the change. `test_sensitivity.py` does exactly that, scenario by scenario.

**Every verdict below is a claim this suite proves, not a label.**
"""
from __future__ import annotations

from dataclasses import dataclass

# =================================================================================================
# The verdicts. Each one is a different KIND of evidence, and conflating them is how a green
# scoreboard stops meaning anything.
# =================================================================================================

#: A step in this round fixed it. RED-first is unavailable; **sensitivity is proven instead**, by
#: neutralising that step's fix and watching the probe go red. The stronger bar.
CLOSED = "closed"
#: It was always green and must stay green. §4 marks five of these itself. A regression guard is
#: not evidence of progress and is not counted as such — it is evidence that progress cost nothing.
GUARD = "guard"
#: **Still fails.** The scenario is encoded, it is red, and it is written into the failure log with
#: its class. This is the output §1 asks for: *"a list of things that are wrong."*
OPEN = "open"
#: Needs the pilot corpus, which is Harsh's. Encoded against the real unit with synthetic data so
#: the LOGIC is proven; the DISTRIBUTION claim is what waits.
CORPUS = "corpus"
#: **Cannot be satisfied as written.** Recorded, with the reason, so nobody re-opens it.
IMPOSSIBLE = "impossible"


@dataclass(frozen=True, slots=True)
class Scenario:
    """One row of §4."""

    id: str
    #: F01…F20 from §3. Two classes where §4 gives two.
    failure_class: tuple[str, ...]
    title: str
    verdict: str
    #: The step that owns the behaviour — §3's last column, corrected where §4 was written before
    #: the step ran.
    owner: str
    #: Required for OPEN, CORPUS and IMPOSSIBLE. **A verdict with no reason is a label.**
    note: str = ""


def _s(id_: str, classes: str, title: str, verdict: str, owner: str, note: str = "") -> Scenario:
    return Scenario(id=id_, failure_class=tuple(classes.split("/")), title=title,
                    verdict=verdict, owner=owner, note=note)


SCENARIOS: dict[str, Scenario] = {s.id: s for s in (
    # --- 4a · ingestion and fields -------------------------------------------------------------
    _s("S01", "F04/F05", "a branched thread reconstructs the branch", CLOSED, "16",
       "Headers captured by step 16. The BRANCH claim is proven at `assemble_chain`; the PIPELINE "
       "still hands it a one-message list, which step 16 recorded rather than papered over — see "
       "S01b."),
    _s("S01b", "F05", "the pipeline feeds assemble_chain a whole thread", OPEN, "18",
       "⛔ **RE-SCOPED — THE ORIGINAL VERDICT OVERSTATED IT.** `pipeline.py` does construct a list "
       "of ONE message, and full RFC 5322 parent resolution has never run on real data. But the "
       "only value the caller READS is `ball_in_court`, and `reconstruct_thread` derives that "
       "**from the most recent message BY TIME** — which at capture IS this event. Verified by "
       "execution: a four-message thread and its newest message alone both answer `us`; a "
       "three-message thread and its newest both answer `them`. **So the one-message call is "
       "correct for its purpose.** What genuinely still needs siblings is `last_inbound_at` — you "
       "cannot know the previous inbound time from one message — which strands exactly two "
       "benchmark objects, `who_sent_last` and `p3_who_sent_last`. Step 18 carried the four that "
       "did NOT need it."),
    _s("S02", "F04/F17", "a bcc'd recipient is captured and governed", IMPOSSIBLE, "16",
       "**Gmail's API does not supply bcc**, and on a message we RECEIVED it is invisible by "
       "definition — that is what bcc means. Step 13 added `bcc_recipients` so the contract can "
       "carry one if a source ever offers one. What IS testable is that `visibility_rules` governs "
       "the recipient set it is given, and that is asserted."),
    _s("S03", "F04", "a tentative invite keeps responseStatus", CLOSED, "13"),
    _s("S04", "F02", "a long backfill exhausts its cursor and says so", CLOSED, "5"),
    _s("S05", "—", "an attachment-only email from an unknown sender survives N-06", GUARD, "1"),
    _s("S06", "F18", "a re-synced message gains a field without re-landing", CLOSED, "16"),
    # --- 4b · bounces and delivery -------------------------------------------------------------
    _s("S07", "F01", "a hard bounce is a delivery failure", CLOSED, "2"),
    _s("S08", "F20", "a soft 4.x.x bounce is NOT a failure", CLOSED, "2"),
    _s("S09", "F20", "a delay notice still retrying is UNKNOWN", CLOSED, "2"),
    _s("S10", "F12", "a bounce with no parseable original id still publishes", CLOSED, "2"),
    _s("S11", "—", "an out-of-office takes the N-05 path", GUARD, "2"),
    _s("S12", "—", "a noreply newsletter still drops at N-03", GUARD, "2"),
    # --- 4c · claims, evidence and the seam ----------------------------------------------------
    _s("S13", "F12", "a role claim with a quotable span resolves", CLOSED, "4"),
    _s("S14", "F12/F20", "an unanchorable claim is kept and flagged, never invented", CLOSED, "4"),
    _s("S15", "F09", "two signals on one event each resolve their own extraction", CORPUS, "3",
       "The `array_agg[1]` finding. Step 3 WITHDREW the unit after production showed LLM-2 runs "
       "once per event, so the projection is proven and the multiplicity is a corpus question."),
    _s("S16", "F09", "a published signal and its refused sibling share a subject_key", CLOSED, "13"),
    _s("S17", "F09", "a composed situation carries domains, confidence and occurred_at", CORPUS, "3",
       "Needs migration 0177 and a Postgres replay — Harsh items 1 and 3."),
    _s("S18", "F19", "the same sweep replayed is byte-identical", CLOSED, "5"),
    # --- 4d · judgement, and what must not be manufactured -------------------------------------
    _s("S19", "F15", "a promise with a later satisfying message is FULFILLED", CLOSED, "12"),
    _s("S20", "F15", "overdue with HIGH coverage is BROKEN", CLOSED, "12"),
    _s("S21", "F20", "overdue with LOW coverage is UNKNOWN", CLOSED, "12",
       "**The single most important row in the table.** Telling a founder they broke a promise "
       "they kept is the failure that loses trust rather than quality."),
    _s("S22", "F20", "overdue with NO coverage figure is UNKNOWN", CLOSED, "12",
       "`None` is not a low number — it is nobody having measured — and it must land on the same "
       "side as low."),
    _s("S23", "F15", "fulfilled two days late is FULFILLED, delta recorded", CLOSED, "12"),
    _s("S24", "F18", "a re-promise supersedes rather than breaks", CLOSED, "12"),
    _s("S25", "F20", "a conditional needing company state is UNKNOWN", CLOSED, "12"),
    _s("S26", "F11", "hearsay composes below the same person's first-hand claim", CLOSED, "9"),
    _s("S27", "F08", "a multi-domain sentence yields ≥2 domains, each with confidence", CLOSED, "6"),
    _s("S28", "F13", "a signal whose domains are uncovered still emits, degraded", CLOSED, "6"),
    # --- 4e · the gate and recall --------------------------------------------------------------
    _s("S29", "F13", "low confidence + high importance is a REVIEW candidate", CORPUS, "10",
       "Step 10 GATED ITSELF on a measurement. 10-U0 measures the population; `PublicationOutcome` "
       "stays closed at three until a real count says the fourth is worth existing."),
    _s("S30", "F14", "low confidence + low importance parks or drops WITH a reason", CLOSED, "8"),
    _s("S31", "—", "a signal carrying a conflict travels regardless of score", GUARD, "8"),
    _s("S32", "—", "an unscored signal travels", GUARD, "8"),
    _s("S33", "F13", "the 68 pilot floor-refusals replay to neither 0 nor 68", CORPUS, "10",
       "Literally the pilot's 68 rows. Harsh item 15."),
    _s("S34", "F14", "a newsletter drops WITH a ledger row", CLOSED, "8"),
    # --- 4f · identity and cross-source --------------------------------------------------------
    _s("S35", "F06", "two addresses for one human stay TWO identities in L1", CLOSED, "13"),
    _s("S36", "F06", "one address with two display names is one identity", CLOSED, "13"),
    _s("S37", "F16", "L1 preserves both keys and lets L2 decide", CLOSED, "13"),
    _s("S38", "F16", "a cohort session is distinguishable from an external meeting", CLOSED, "13"),
    _s("S39", "F16", "a warm intro is answerable from the recipient graph", CLOSED, "13"),
)}

#: §3's twenty classes. Present so a typo in a row cannot invent a class, which is the same reason
#: `--strict-markers` is on.
FAILURE_CLASSES: frozenset[str] = frozenset(
    [f"F{n:02d}" for n in range(1, 21)] + ["—"])

VERDICTS: frozenset[str] = frozenset({CLOSED, GUARD, OPEN, CORPUS, IMPOSSIBLE})

#: A verdict that is not simply "it works" owes a reason. **A verdict with no reason is a label**,
#: and §1's whole complaint is about labels that looked like evidence.
_NEEDS_A_REASON: frozenset[str] = frozenset({OPEN, CORPUS, IMPOSSIBLE})


def _check() -> None:
    """Import-time totality, the way this codebase does it everywhere else."""
    for one in SCENARIOS.values():
        assert one.verdict in VERDICTS, f"{one.id}: unknown verdict {one.verdict!r}"
        for klass in one.failure_class:
            assert klass in FAILURE_CLASSES, f"{one.id}: unknown failure class {klass!r}"
        if one.verdict in _NEEDS_A_REASON:
            assert one.note, f"{one.id} is {one.verdict} and gives no reason"


_check()


def by_verdict(verdict: str) -> tuple[Scenario, ...]:
    return tuple(s for s in SCENARIOS.values() if s.verdict == verdict)


__all__ = ["CLOSED", "CORPUS", "FAILURE_CLASSES", "GUARD", "IMPOSSIBLE", "OPEN", "SCENARIOS",
           "VERDICTS", "Scenario", "by_verdict"]
