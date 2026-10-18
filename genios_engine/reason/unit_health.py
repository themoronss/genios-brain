r"""⛔ A unit that COMPLETED and computed NOTHING — declared, with a reason and a mover.

WHAT THIS IS. The one place that says which reasoning units succeed on every run and produce nothing,
why, and who can change it. Two readers import it — `scripts/l2_unit_said_nothing.py` and
`platform/receipts.py` — and **neither keeps a copy**, which is the whole point of the module existing
rather than the list living in the probe where it started.

⛔ WHY IT EXISTS. Measured against production on 2026-10-01, with the full suite at 14,397 passed:

    core.impact        1,973 completions   100% silent   output = {"impact_signal_count": 0}
    core.opportunity   1,088 completions    94% silent

`core.impact` succeeds on every run and computes nothing. Its status is `completed`, so every probe
asking *does this unit speak* reports it as speaking.

⛔ AND THE UNIT IS RIGHT TO BE QUIET. Its own docstring: *"Silence is not zero. A dimension with no
evidence contributes no observation and publishes no metric … a fabricated zero silently lies."* The
defect is not the silence. **The defect is that nothing downstream can tell an honest silence from a
measurement.**

⛔ WHAT IT COST, MEASURED. `tradeoff_unit.AXIS_SOURCES` names `benefit_source -> core.impact ->
impact_bp`, which `core.impact` never publishes. `tradeoff.cost_vs_benefit` has fired **0 times in
1,200 production rows**, while `tests/reason/test_tradeoff_cost_axis.py` proves the axis works — on a
prior the test supplies itself. **A green test over 1,200 rows where the axis has never spoken.**

⛔ WHY THE OBVIOUS FIX WAS REFUSED. Having `core.tradeoff` publish which axis it lost would add a field
to the output of ~100% of runs, and `contracts/reasoning.py:845` states the consequence:
*"every trace in `reasoning_runs` would fail replay verification against a run that computed the
identical result."* The established rule is conditional inclusion, and conditional inclusion does not
help when the condition holds on every run. `axis_count` is ALREADY published on every run and read by
nobody — so the fix is a reader, not a field.

⛔ WHY THE RECEIPT ASKS THIS QUESTION AND NOT THE OBVIOUS ONE. `api/routes.py:161` computes
`ready = not failed` from this same receipt list, and it is what the release gate runs. A receipt
asserting *"no unit is silent"* would be **permanently red** for an upstream reason this layer cannot
clear (`deal.status` has no writer). A gate that is always red is a gate nobody reads. So the claim is
the one that is true today and false the moment it gets worse: **every silent unit is a declared one.**

This is the codebase's own doctrine — *every silent lane carries a reason and a mover* — applied to the
units themselves.

PURE. No I/O, no clock, no model.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class DeclaredSilence:
    """One unit that completes and says nothing, and what would change that."""

    #: Why it is silent — the CAUSE, not the symptom. "No findings" is the symptom.
    reason: str
    #: ⛔ Who can change it. A declared silence with no named mover is an undeclared silence with
    #: paperwork — the distinction `declared silence` exists to make.
    mover: str
    #: The measured share of completions that were silent, and the date it was measured.
    #: ⛔ Both, because *an audit is a measurement with a date on it, and a measurement read six
    #: weeks later is a claim.*
    share_pct: int
    measured_on: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a declared silence with no reason is an undeclared one")
        if not self.mover.strip():
            raise ValueError(
                "a declared silence with no mover cannot be cleared by anybody; name who can")
        if not 0 <= self.share_pct <= 100:
            raise ValueError(f"share_pct must be a percentage, got {self.share_pct}")
        if not self.measured_on.strip():
            raise ValueError("a share with no date is a claim, not a measurement")


#: ⛔ THE DECLARATION. Exactly the units measured silent on production, and nothing else.
#:
#: Adding an entry here is how a new silence becomes legitimate, and it costs a reason, a mover, a
#: share and a date. Removing one is what happens when a unit starts speaking.
DECLARED_SILENT: Mapping[str, DeclaredSilence] = MappingProxyType({
    "core.impact": DeclaredSilence(
        reason=(
            "all three plugins need a deal value or core.relationship.coverage_bp. "
            "core.relationship has NEVER completed — 708 insufficient_context, 221 skipped — "
            "because deal.status has no writer. So impact_signal_count is 0 on every run and "
            "impact_bp is correctly omitted rather than fabricated as a zero."),
        mover="Harsh — a writer for deal.status, upstream of this layer",
        share_pct=100,
        measured_on="2026-10-01"),
    "core.opportunity": DeclaredSilence(
        reason=(
            "its three plugins gate on an inbound moment, a status and an owner. The roster binds "
            "them to thread.last_inbound, deal.status and deal.owner, and the same missing "
            "deal.status that starves core.relationship starves two of the three here."),
        mover="Harsh — the same deal.status writer",
        share_pct=94,
        measured_on="2026-10-01"),
})

#: The units declared silent, as a plain frozenset — what a SQL `not in` list is built from.
DECLARED_SILENT_IDS: frozenset[str] = frozenset(DECLARED_SILENT)


@dataclass(frozen=True, slots=True)
class UnwrittenFact:
    """A fact path a reasoning unit binds to and that nothing in the product ever writes."""

    reason: str
    #: ⛔ Who or WHAT can change it. For most of these it is not a person — it is a connector that
    #: does not exist. Saying so once, against fourteen paths, is the finding.
    mover: str
    #: ⛔ Which unit roles bind this path. REQUIRED, and it is the point of the declaration: a list
    #: of empty paths is a list of strings, while `deal.value` bound by BOTH
    #: `core.impact.value_field` and `core.policy.approval_value_field` tells a reader what one
    #: missing connector costs.
    bound_by: tuple[str, ...]
    measured_on: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("an unwritten fact with no reason is an undeclared gap")
        if not self.mover.strip():
            raise ValueError(
                "name what can write it — a connector, a sync, a person. Without a mover this is a "
                "gap nobody can close")
        if not self.bound_by:
            raise ValueError(
                "name the unit roles that bind this path; a declaration for a path nothing reads is "
                "dead paperwork")
        if not self.measured_on.strip():
            raise ValueError("a census with no date is a claim, not a measurement")


#: ⛔ THE FOURTEEN FACT PATHS THE ROSTER BINDS AND NOTHING WRITES.
#:
#: Measured 2026-10-01 against production: `expertise._ROSTER` binds **22** fact paths and **14** have
#: zero rows in `graph_facts`. Every present path is `thread.*`, `derived.*`, `commitment.due_at`,
#: `meeting.start_at`; every `deal.*` path beyond `status` (3 rows) and `last_inbound` (34) is empty.
#:
#: ⛔ ONE ROOT, FOURTEEN SYMPTOMS. There is no CRM connector, so the deal object barely exists — and
#: `core.policy` skips on every run because ALL FOUR of its essential fields are in this list.
#:
#: ⛔ AND THIS IS WHAT `no_declared_input_available` CANNOT SAY. That skip reason conflates "this
#: situation did not carry the field" with "nothing has ever written the field anywhere" — two facts
#: with completely different movers, the second not fixable by looking at the situation at all.
_CRM = ("a connector that writes the deal object. None exists, so `deal.*` is empty beyond "
        "`status` (3 rows) and `last_inbound` (34)")
_APPROVALS = ("a connector or form that records an approval workflow. Nothing writes any gate "
              "status, so every dependency gate reads as absent rather than as cleared")
_CONSENT = ("a consent/preference source. Nothing writes either field, so the policy unit cannot "
            "tell 'may contact' from 'never asked'")
_CALENDAR_FWD = ("a forward-looking calendar read. `meeting.start_at` is written (49 rows) and the "
                 "NEXT-meeting and quiet-window projections are not")

DECLARED_UNWRITTEN: Mapping[str, UnwrittenFact] = MappingProxyType({
    "deal.value": UnwrittenFact(
        reason=_CRM, mover="Harsh — a CRM connector",
        bound_by=("core.impact.value_field", "core.policy.approval_value_field"),
        measured_on="2026-10-01"),
    "deal.owner": UnwrittenFact(
        reason=_CRM, mover="Harsh — a CRM connector",
        bound_by=("core.dependency.owner_field", "core.opportunity.owner_field",
                  "core.resource.owner_field"),
        measured_on="2026-10-01"),
    "deal.close_date": UnwrittenFact(
        reason=_CRM, mover="Harsh — a CRM connector",
        bound_by=("core.resource.deadline_field", "core.scheduling.deadline_field",
                  "core.timeline.deadline_fields"),
        measured_on="2026-10-01"),
    "deal.last_outbound": UnwrittenFact(
        reason=_CRM, mover="Harsh — a CRM connector",
        bound_by=("core.opportunity.outbound_field", "core.scheduling.last_contact_field",
                  "core.timeline.timeline_fields"),
        measured_on="2026-10-01"),
    "deal.approval_status": UnwrittenFact(
        reason=_APPROVALS, mover="Harsh — an approval-workflow source",
        bound_by=("core.policy.approval_status_field",), measured_on="2026-10-01"),
    "approval.status": UnwrittenFact(
        reason=_APPROVALS, mover="Harsh — an approval-workflow source",
        bound_by=("core.dependency.gate_fields",), measured_on="2026-10-01"),
    "finance.approval_status": UnwrittenFact(
        reason=_APPROVALS, mover="Harsh — an approval-workflow source",
        bound_by=("core.dependency.gate_fields",), measured_on="2026-10-01"),
    "legal.review_status": UnwrittenFact(
        reason=_APPROVALS, mover="Harsh — an approval-workflow source",
        bound_by=("core.dependency.gate_fields",), measured_on="2026-10-01"),
    "procurement.status": UnwrittenFact(
        reason=_APPROVALS, mover="Harsh — an approval-workflow source",
        bound_by=("core.dependency.gate_fields",), measured_on="2026-10-01"),
    "security.review_status": UnwrittenFact(
        reason=_APPROVALS, mover="Harsh — an approval-workflow source",
        bound_by=("core.dependency.gate_fields",), measured_on="2026-10-01"),
    "contact.do_not_contact": UnwrittenFact(
        reason=_CONSENT, mover="Rohit — whether this product holds consent state at all",
        bound_by=("core.policy.do_not_contact_field",), measured_on="2026-10-01"),
    "contact.consent_status": UnwrittenFact(
        reason=_CONSENT, mover="Rohit — whether this product holds consent state at all",
        bound_by=("core.policy.consent_status_field",), measured_on="2026-10-01"),
    "calendar.next_meeting_at": UnwrittenFact(
        reason=_CALENDAR_FWD, mover="Harsh — a forward calendar projection",
        bound_by=("core.scheduling.next_interaction_field",), measured_on="2026-10-01"),
    "schedule.quiet_until": UnwrittenFact(
        reason=_CALENDAR_FWD, mover="Harsh — a quiet-hours/quiet-window writer",
        bound_by=("core.scheduling.quiet_until_field",), measured_on="2026-10-01"),
})

#: The declared paths, as a plain frozenset — what a SQL `not in` list is built from.
DECLARED_UNWRITTEN_PATHS: frozenset[str] = frozenset(DECLARED_UNWRITTEN)


@dataclass(frozen=True, slots=True)
class ClosedDefect:
    """A defect that WAS real, is fixed, and still sits in append-only history forever.

    ⛔ WHY THIS IS A THIRD KIND OF DECLARED FACT. `DeclaredSilence` and `UnwrittenFact` both
    describe something absent NOW, so both demand a mover. A closed defect demands no mover —
    nobody has to act — but it demands the one thing neither of those needs: a **boundary**. The
    instant after which the defect must never recur, and the commit that establishes it.

    ⛔ WHAT IT IS FOR. `reasoning_candidates` is append-only and this codebase soft-deletes only,
    so a row written by a defect outlives the fix. A receipt that scans all of history therefore
    reports a fixed defect as a live failure, permanently, and `api/routes.py:161` computes
    `ready = not failed` over those receipts. **A receipt over append-only history needs a lower
    bound, or it is not a gate — it is a monument.** This class is where the bound is declared, so
    the receipt reads it instead of carrying a date nobody can trace.
    """

    #: What was actually wrong — the CAUSE. Not "rows were bad".
    reason: str
    #: ⛔ The instant after which this must never happen again, as an ISO date. Everything written
    #: at or after it is the fixed code's work and is what the receipt judges.
    boundary: str
    #: What closed it: the commit, and the module. A boundary with no cause for being where it is
    #: is a date somebody chose, which is the thing this class exists to stop.
    closed_by: str
    #: Rows carrying the defect, measured, and the date measured. ⛔ Both — *an audit is a
    #: measurement with a date on it, and a measurement read six weeks later is a claim.*
    rows: int
    measured_on: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a closed defect with no reason cannot be recognised if it returns")
        if not self.boundary.strip():
            raise ValueError(
                "a closed defect with no boundary is an open one; name the date it stopped")
        if not self.closed_by.strip():
            raise ValueError(
                "a boundary with nothing that establishes it is a date somebody chose; "
                "name the commit or the module that closed it")
        if self.rows < 0:
            raise ValueError(f"rows is a count, got {self.rows}")
        if not self.measured_on.strip():
            raise ValueError("a count with no date is a claim, not a measurement")


#: ⛔ THE DECLARATION. Defects measured closed on production, and nothing else.
#:
#: An entry here is a promise that the receipt reading it can still fail — it narrows WHEN the
#: question is asked, never WHAT is asked.
CLOSED_DEFECTS: Mapping[str, ClosedDefect] = MappingProxyType({
    "score_components.neutral_default": ClosedDefect(
        reason=(
            "both candidate seams built PlayDefinition without impact/success/effort/risk, so the "
            "dataclass defaults of 5_000 apiece stood in for measurements. 53 of the 59 affected "
            "rows carry ALL FIVE of guards.CANDIDATE_COMPONENTS at 5000 — the whole ranking "
            "formula was one constant — and the other 6 carry four of five. Every reasoning unit "
            "that adjusts those components was a no-op on those rows."),
        boundary="2026-09-08",
        closed_by=("75096bab 'Layer 4: the formula's dead components, and the chain that was "
                   "never checkable' — reason/adapters/play_priors.py for the compiled lane; "
                   "reason/adapters/legacy_pack.py:285 had already closed the legacy lane"),
        rows=59,
        measured_on="2026-10-01"),
})


def neutral_default_boundary() -> str:
    """The date the frozen-formula defect stopped, for the receipt that watches it.

    A function and not a constant so the receipt cannot drift from the declaration by copying it.
    """
    return CLOSED_DEFECTS["score_components.neutral_default"].boundary


@dataclass(frozen=True, slots=True)
class ReasoningEra:
    """When the CURRENT reasoning implementation began writing, and what makes it current.

    ⛔ WHY AN ERA IS A DECLARATION AND NOT A DATE SOMEBODY MEASURED. `reasoning_runs` holds two
    populations that answer a receipt's question differently: 2,681 runs carry per-unit results and
    9,489 do not, because unit results only began being written on 2026-09-29. A receipt asking
    "does reasoning select anything" over both at once averages a live implementation with a
    retired one and reports neither.

    The boundary is therefore stated here, with the observation that establishes it, rather than
    inferred inside a query from `min(created_at) where results exist` — which would move on its
    own the first time an old run was backfilled.
    """

    #: ISO date the current implementation's first run was evaluated.
    boundary: str
    #: What changed at the boundary, in one sentence a reader can go and check.
    what_changed: str
    #: How the boundary was established — the count, not the reasoning.
    measured: str


#: ⛔ The reasoning implementations this codebase has had, newest LAST.
#:
#: Appended to, never edited: the boundary of a past era is a fact about history and a receipt that
#: cites it must keep citing the same number. A new era is a new entry.
REASONING_ERAS: tuple[ReasoningEra, ...] = (
    ReasoningEra(
        boundary="2026-09-29",
        what_changed="per-unit results began being persisted — `reasoning_reasoner_results` has "
                     "rows for runs from this date and none before it",
        measured="measured 2026-10-01: of 12,170 runs, 2,681 carry unit results (evaluated "
                 "2026-09-29 to 09-30) and 9,489 carry none (2026-08-17 to 09-29)"),
)


def current_reasoning_era() -> ReasoningEra:
    """The era a receipt about reasoning behaviour should scope itself to.

    A function and not a constant for the same reason `neutral_default_boundary` is one: the
    receipt must not carry its own copy of a date the declaration owns.
    """
    return REASONING_ERAS[-1]


@dataclass(frozen=True, slots=True)
class NeverCompleted:
    """A unit that RUNS and has never once completed — absent, not quiet.

    ⛔ WHY A THIRD GRAIN WAS NEEDED. `DeclaredSilence` asks whether a **completed** output said
    anything; `UnwrittenFact` asks whether a bound fact path has a writer. Measured 2026-10-01,
    `core.relationship` escapes both: it has **929 runs and 0 completions**, so
    `_UNDECLARED_SILENT_UNITS_SQL` cannot see it — that query filters `status = 'completed'` and
    groups by unit, and a unit with no completed rows is not a row with a low share, **it is not a
    row**. And it binds `deal.status`, which has 3 rows, so it is not an unwritten path either; the
    sibling receipt states that boundary on purpose — *"A path with one row has a writer; that is
    the whole question. How WELL it is covered is `deal.status`'s 3-of-293 problem, a different
    measurement with a different mover."*

    So the fact was written down twice in prose — once in `receipts.py` and once inside
    `DECLARED_SILENT["core.impact"]`'s own reason text, as an argument for a different unit's
    entry — and declared nowhere a receipt could read.

    > **A unit that never completes is not a quiet unit; it is an absent one, and a question asked
    > only of completions cannot see it.**

    ⛔ NOT FOR A UNIT ALREADY DECLARED THROUGH ITS INPUTS. `core.policy` also has zero completions
    (165 runs, all `skipped: no_declared_input_available`), and it is deliberately **not** declared
    here: all four fact paths it binds are in `DECLARED_UNWRITTEN`, so it is already accounted for
    at the grain that names the real mover. A second declaration of one fact is exactly the drift
    this module exists to prevent, and a test asserts the two sets do not overlap.
    """

    #: Why it never completes — the CAUSE. "No output" is the symptom.
    reason: str
    #: ⛔ Who can change it. Same rule as `DeclaredSilence`: a declared absence with no named mover
    #: is an undeclared absence with paperwork.
    mover: str
    #: Runs observed with zero completions, and the date measured. ⛔ The run count is what makes
    #: this an absence rather than a unit that simply has not been scheduled yet — one run proves
    #: nothing, 929 proves the lane is live and the unit still never answers.
    runs: int
    measured_on: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a unit declared never-completing with no reason is an undeclared one")
        if not self.mover.strip():
            raise ValueError(
                "a never-completing unit with no mover cannot be cleared by anybody; name who can")
        if self.runs <= 0:
            raise ValueError(
                f"runs must be positive -- a unit that has never been scheduled is a different "
                f"fact from one that runs and never answers, got {self.runs}")
        if not self.measured_on.strip():
            raise ValueError("a count with no date is a claim, not a measurement")


#: ⛔ THE DECLARATION. Units measured with runs and zero completions, and nothing else.
#:
#: `core.signal_composition` is NOT here: it has **zero runs**, because the capability that
#: schedules it (`DEAL_HEALTH_V1`) has never been swept. That is ALARM A2 — a roster activation,
#: not a silence — and `runs <= 0` is refused above so it cannot be mis-filed here.
DECLARED_NEVER_COMPLETED: Mapping[str, NeverCompleted] = MappingProxyType({
    "core.relationship": NeverCompleted(
        reason=(
            "708 insufficient_context and 221 skipped:no_declared_input_available. It binds "
            "deal.status, which has 3 rows across 293 candidate nodes -- the path is written, so it "
            "is not an unwritten fact, but it is not usefully written, so the unit can never reach "
            "its threshold. This starves core.impact (100% silent) and through it "
            "tradeoff.cost_vs_benefit, which has fired 0 times in 1,200 rows."),
        mover="Harsh -- a CRM connector writing deal.status across more than 3 of 293 nodes",
        runs=929,
        measured_on="2026-10-01"),
})

#: The units declared never-completing, as a plain frozenset — what a SQL `not in` list is built from.
DECLARED_NEVER_COMPLETED_IDS: frozenset[str] = frozenset(DECLARED_NEVER_COMPLETED)


def starved_by_declared_paths() -> frozenset[str]:
    """Units whose EVERY bound fact path is already declared unwritten.

    ⛔ DERIVED, NEVER LISTED. `core.policy` has 165 runs and 0 completions and is nonetheless fully
    accounted for: all four paths it binds are in `DECLARED_UNWRITTEN`, so it is declared at the
    grain that names the real mover. Hard-coding its id here would put one fact in two places,
    which is the drift this module exists to prevent — and it would go stale the moment a path
    gained a writer. Computed from the roster, so it cannot.

    A unit that binds no roster path is NOT in this set: having nothing to bind is not the same as
    binding something nobody writes.
    """
    bound: dict[str, set[str]] = {}
    for path, roles in roster_fact_paths().items():
        for role in roles:
            unit = role.rsplit(".", 1)[0]
            bound.setdefault(unit, set()).add(path)
    return frozenset(unit for unit, paths in bound.items()
                     if paths and paths <= set(DECLARED_UNWRITTEN_PATHS))


def undeclared_never_completed(runs: Mapping[str, int],
                               completions: Mapping[str, int]) -> tuple[str, ...]:
    """Units with runs and no completions that nobody declared. Empty is the passing answer.

    ⛔ Takes BOTH maps rather than a ratio. A ratio of 0/0 and 0/929 are the same number and
    completely different facts — the first is a unit nobody scheduled, the second is a unit that
    answers nothing. Only the second belongs here.

    Accounted for means EITHER grain: declared here, or starved by paths already declared unwritten.
    """
    excused = DECLARED_NEVER_COMPLETED_IDS | starved_by_declared_paths()
    return tuple(sorted(
        unit for unit, n in runs.items()
        if n > 0 and completions.get(unit, 0) == 0 and unit not in excused))


def completed_after_all(completions: Mapping[str, int]) -> tuple[str, ...]:
    """Declared units that have now completed — the good direction, and a thing to go and delete."""
    return tuple(sorted(unit for unit in DECLARED_NEVER_COMPLETED_IDS
                        if completions.get(unit, 0) > 0))


def roster_fact_paths() -> Mapping[str, tuple[str, ...]]:
    """Every fact path `expertise._ROSTER` binds, to the `unit.role` names that bind it.

    ⛔ DERIVED FROM THE ROSTER, NEVER A COPY. A seventh role added to a unit appears here without an
    edit — the rule `S5.U02` established for `AXIS_SOURCES`, applied one level up. A hand-kept list
    would be the fifth instance of two declarations of one fact in this programme.

    Imported inside the function because `reason.adapters.expertise` imports a great deal, and this
    module is read by `platform/receipts` and by scripts that must stay cheap to import.
    """
    from genios_engine.reason.adapters.expertise import _ROSTER

    out: dict[str, list[str]] = {}
    for unit in _ROSTER:
        for key, names in (unit.roles + unit.list_roles):
            for name in names:
                out.setdefault(name, []).append(f"{unit.unit_id}.{key}")
    return {path: tuple(sorted(set(binders))) for path, binders in sorted(out.items())}


def undeclared_unwritten(row_counts: Mapping[str, int]) -> tuple[str, ...]:
    """Bound paths with no rows that nobody declared. Empty is the passing answer."""
    return tuple(sorted(path for path in roster_fact_paths()
                        if row_counts.get(path, 0) == 0
                        and path not in DECLARED_UNWRITTEN_PATHS))


def written_after_all(row_counts: Mapping[str, int]) -> tuple[str, ...]:
    """Declared-unwritten paths that now carry rows — the good direction, and still a thing to update."""
    return tuple(sorted(path for path in DECLARED_UNWRITTEN_PATHS
                        if row_counts.get(path, 0) > 0))


def is_silent(output: Any) -> bool:
    """Did this completed result say anything at all?

    ⛔ THREE OUTPUT KINDS, ALL THREE CHECKED, AND THE FIRST VERSION CHECKED ONE. Counting empty
    `findings` alone reports `core.constraint` (2,681 completions, 0 findings) and
    `legacy.score_gate` (708, 0) as broken. **Both are fine** — their `output_kind` is
    `candidate_checks` and they emit CHECKS. *A crude slice that happens to fail looks exactly like
    a real finding.*

    ⛔ `isinstance(v, bool)` IS EXCLUDED DELIBERATELY. `True` is an `int` in Python, so a unit
    publishing only `matched: True` would read as having measured something numeric.

    ⛔ AND A STRING PAYLOAD IS PARSED, NOT ASSUMED. The column comes back as a dict on psycopg and as
    text on other drivers; a reader that assumed one would report every row silent on the other and
    look like a catastrophe.
    """
    import json

    doc = output if isinstance(output, dict) else json.loads(output or "{}")
    if doc.get("findings") or doc.get("checks"):
        return False
    metrics = doc.get("metrics") or {}
    return not any(value for value in metrics.values()
                   if isinstance(value, int) and not isinstance(value, bool))


#: ⛔ Above this share a unit is reported as silent rather than quiet. 90 and not 100: a unit that
#: speaks on one run in fifty is not working either, and demanding exactly 100 would let
#: `core.opportunity`'s 94% pass as healthy.
SILENT_THRESHOLD_PCT = 90

#: The SQL fragment both the receipt and any report use to express `is_silent` in the database.
#:
#: ⛔ ONE EXPRESSION OF ONE RULE, IN TWO LANGUAGES, AND A TEST COMPARES THEM ON REAL ROWS. Two
#: definitions that are supposed to agree and are never compared eventually disagree — the shape
#: this programme has found five times. `tests/reason/test_a_unit_that_says_nothing_is_not_working.py`
#: runs both over the same production rows under the `pg` gate.
#:
#: `jsonb_typeof` guards the metric scan: a `metrics` key that is not an object would make
#: `jsonb_each` raise, and a receipt that raises is reported as ERROR rather than answering.
SILENT_SQL = """
    coalesce(jsonb_array_length(nullif(output->'findings', 'null'::jsonb)), 0) = 0
    and coalesce(jsonb_array_length(nullif(output->'checks', 'null'::jsonb)), 0) = 0
    and not exists (
        select 1 from jsonb_each(case when jsonb_typeof(output->'metrics') = 'object'
                                      then output->'metrics' else '{}'::jsonb end) as m(k, v)
        where jsonb_typeof(v) = 'number' and (v)::text not in ('0', '0.0')
    )
"""


def undeclared_silent(shares: Mapping[str, int]) -> tuple[str, ...]:
    """Units silent above the threshold that nobody declared. Empty is the passing answer."""
    return tuple(sorted(unit for unit, pct in shares.items()
                        if pct >= SILENT_THRESHOLD_PCT and unit not in DECLARED_SILENT_IDS))


def drifted(shares: Mapping[str, int]) -> tuple[str, ...]:
    """Declared units that now speak — the good direction, and still a thing to go and update."""
    return tuple(sorted(unit for unit in DECLARED_SILENT_IDS
                        if shares.get(unit, 0) < SILENT_THRESHOLD_PCT))


__all__ = ["CLOSED_DEFECTS", "DECLARED_NEVER_COMPLETED", "DECLARED_NEVER_COMPLETED_IDS",
           "DECLARED_SILENT", "DECLARED_SILENT_IDS", "DECLARED_UNWRITTEN",
           "DECLARED_UNWRITTEN_PATHS", "SILENT_SQL", "SILENT_THRESHOLD_PCT", "ClosedDefect",
           "DeclaredSilence", "NeverCompleted", "UnwrittenFact", "completed_after_all",
           "drifted", "is_silent", "neutral_default_boundary", "roster_fact_paths",
           "starved_by_declared_paths",
           "undeclared_never_completed", "undeclared_silent", "undeclared_unwritten",
           "written_after_all"]
