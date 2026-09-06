"""L2.5.5-U1 · BLG-15 · TYPED ABSENCE — the classifier that decides what a gap MEANS.

Three different things look identical downstream today, and every one of them is the empty list:

    no support tickets, the desk connected      genuinely healthy      -> a finding
    no support tickets, no desk connected       UNKNOWABLE             -> nothing at all
    no owner recorded on a work item            a real finding         -> the product

Conflating the first two is how a false churn signal is born. The third is the interesting one:
*"there is a renewal, and no owner is recorded"* is not missing data, it IS the intelligence, and
an Ownership surface is built entirely out of it.

**The cascade, and why its order is the safety rule.**

    fact present, and current              -> PRESENT
    fact present, and too old to rely on   -> STALE
    the expectation does not apply here    -> NOT_EXPECTED
    coverage_ready is not TRUE             -> UNKNOWABLE      (False AND None both land here)
    a source could have carried it,
    every one we can see was checked,
    and none did                           -> GENUINELY_ABSENT

`coverage_ready` is consulted BEFORE absence is ever concluded, and `None` lands with `False`.
Doc 05's own failure table names the alternative — `UNKNOWABLE` read as `GENUINELY_ABSENT` — as
the worst output the quality group can emit, because it is a false negative inference about a
customer delivered with a confident receipt.

**Where this deviates from the doc's cascade, and why.** Doc 05 writes STALE after
GENUINELY_ABSENT (*"elif the fact was present and is now stale"*), which is unreachable: a fact
that WAS present cannot be reached through a branch that has already concluded nothing carried
it. Presence is therefore examined first here and splits PRESENT from STALE. The hard rule the
doc is actually protecting — *"coverage_ready is checked FIRST, before concluding anything is
absent"* — is kept exactly: coverage is the last gate before `GENUINELY_ABSENT`, and nothing
reaches that member without passing it. Recorded as assumption **A-14** in
`docs/plans/L2_MISSING_UNIT_SPECS.md` §3.

**The types are the contract's, not this module's.** `AbsenceType` and `MissingFact` live in
`contracts/quality.py`, where `licenses_negative_inference` is computed and unsettable and
`GENUINELY_ABSENT` is unconstructible without `coverage_ready=True` and a non-empty
`coverage_basis`. This module cannot talk itself past those rules, which is the point: the
argument for an exception is always persuasive at the call site and always wrong.

**PURE, except for the two functions at the bottom that say so.** `classify_absence`,
`classify_all` and `detect_missing` take the coverage lens as a parameter and read no clock;
`refresh_typed_absences` and `read_absences` are the storage seam and take a connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Iterable, Mapping, Sequence

from sqlalchemy import text

from genios_engine.context.domain_spec import canonical_domain, spec_for
from genios_engine.context.quality.epoch import stale_coverage
from genios_engine.context.quality.lens import CoverageLens
from genios_engine.contracts.quality import AbsenceType, MissingFact

ABSENCE_TABLE = "situation_absences"

#: The absence kinds worth STORING. `PRESENT` is not an absence and `NOT_EXPECTED` is not a gap —
#: keeping either would make the table's own row count meaningless and would put a row on every
#: field of every situation of every tenant. `classify_all` still returns them, so a caller that
#: wants the total answer has it without the table carrying it.
STORED_TYPES: frozenset[AbsenceType] = frozenset({
    AbsenceType.UNKNOWABLE, AbsenceType.GENUINELY_ABSENT, AbsenceType.STALE})


@dataclass(frozen=True, slots=True)
class Expectation:
    """One fact a well-formed situation of this type should carry.

    Minimal on purpose. Doc 05's own mitigation for "everything is incomplete, nothing publishes"
    is that *"maps are per situation type and start minimal"*, and the full registry — versioned
    maps, `expected_when` guards, registration-time validation against the fact vocabulary — is
    `L2.5.5-U2`, a unit of its own. What is here is the shape the CLASSIFIER consumes, so that
    unit can supply richer maps without this cascade changing.

    `domain` is the COVERAGE domain — which connected source could have carried this fact — and
    defaults to the situation's own domain. They are the same thing today (a sales situation's
    facts come from the sales domain's sources) and will stop being the same the day one
    situation type expects a fact from a second source family, which is why it is a field rather
    than an assumption.
    """

    field: str
    label: str = ""
    domain: str | None = None
    #: `True` -> a `GENUINELY_ABSENT` here is an OUTPUT ("no owner on this work item"), not a
    #: data-quality complaint. `False` -> the gap lowers coverage and emits no finding.
    finding_if_absent: bool = True
    #: The guard that keeps a map from being blindly universal. Returns whether this expectation
    #: applies to this subject at all; a `False` answer is `NOT_EXPECTED`, which is neither a gap
    #: nor a finding. `None` means "always".
    expected_when: Callable[["AbsenceSubject"], bool] | None = None

    def applies_to(self, subject: "AbsenceSubject") -> bool:
        return True if self.expected_when is None else bool(self.expected_when(subject))

    def coverage_domain(self, subject: "AbsenceSubject") -> str:
        return canonical_domain(self.domain or subject.domain)


@dataclass(frozen=True, slots=True)
class AbsenceSubject:
    """The situation an absence is being classified FOR, flattened to what the cascade reads.

    Every field is already computed by `situations.refresh_situations` at the point it calls this
    — nothing here asks a caller to derive anything new, which is what keeps the classifier on
    the drain rather than in a second pass with its own queries.
    """

    situation_id: str
    subject_node_id: str
    domain: str
    situation_type: str = ""
    #: The fact PATHS this situation holds — the anchor's own facts plus whatever the situation's
    #: evidence established elsewhere. Exactly the set `coverage_score` scores against, so the
    #: two can never disagree about what is present.
    present_fields: frozenset[str] = frozenset()
    #: field path -> when that fact was last observed, for the STALE branch. Absent means "we do
    #: not know how old this is", and an undated fact is PRESENT rather than STALE: evidence with
    #: no timestamp tells us nothing about currency, and scoring it as old would turn missing
    #: metadata into bad news — the rule `freshness_score` already keeps one file over.
    observed_at: Mapping[str, datetime] = field(default_factory=dict)


def expectations_from_spec(domain: str | None, situation_type: str) -> tuple[Expectation, ...]:
    """The expectation map as it exists TODAY: `domain_spec.expected_fields`.

    Not a second declaration. `situations.coverage_score` already scores against this exact map
    and `situation_bso._missing_paths` already reports gaps in it to the pack compiler, so a new
    list here would be a third opinion about what a situation type should know — and the failure
    mode of three opinions is that a field is expected by one of them and a permanent false
    finding under another.

    An unregistered domain declares nothing, and this returns nothing: we cannot name a gap in a
    domain nobody has described. That is the same third state `coverage_score` keeps with
    `COVERAGE_UNKNOWN` — "we never said what complete means here" — and it must not be read as
    "nothing is missing".
    """
    return tuple(Expectation(field=path, label=label)
                 for path, label in sorted(spec_for(domain).fields_for(situation_type).items()))


def classify_absence(subject: AbsenceSubject, expectation: Expectation, lens: CoverageLens, *,
                     eval_time: datetime, stale_after: timedelta | None = None) -> AbsenceType:
    """Which of the five this (subject, expected fact) pair is. PURE.

    `lens` is injected and `eval_time` is a parameter: the same subject against the same lens is
    the same answer on any machine at any time, which is what makes a stored absence replayable.
    """
    if expectation.field in subject.present_fields:
        observed = subject.observed_at.get(expectation.field)
        if stale_after is not None and observed is not None and observed < eval_time - stale_after:
            return AbsenceType.STALE
        return AbsenceType.PRESENT
    if not expectation.applies_to(subject):
        return AbsenceType.NOT_EXPECTED
    domain = expectation.coverage_domain(subject)
    # COVERAGE FIRST, ALWAYS, and `None` is not `False` — both are "not True" and both refuse the
    # licence. An unassessed domain is not evidence that the domain is covered.
    if lens.ready_for(domain) is not True:
        return AbsenceType.UNKNOWABLE
    if not lens.basis_for(domain):
        # Ready, and nothing to name as having been consulted. The contract would refuse the
        # object; refusing it HERE keeps the reason in one place: a claim with no receipt is a
        # guess, and the honest spelling of a guess is `UNKNOWABLE`.
        return AbsenceType.UNKNOWABLE
    return AbsenceType.GENUINELY_ABSENT


def missing_fact(subject: AbsenceSubject, expectation: Expectation, lens: CoverageLens, *,
                 eval_time: datetime, stale_after: timedelta | None = None) -> MissingFact:
    """One classified expectation, as the CONTRACT object.

    The contract re-checks the two rules this module already applied (`GENUINELY_ABSENT` needs
    `coverage_ready=True` and a non-empty basis) and that duplication is deliberate: the
    classifier is not the only thing that will ever construct one of these, and a rule enforced
    only at the one call site that exists today is a rule that a second call site does not have.
    """
    absence = classify_absence(subject, expectation, lens,
                               eval_time=eval_time, stale_after=stale_after)
    domain = expectation.coverage_domain(subject)
    return MissingFact(
        subject_node_id=subject.subject_node_id,
        expected_fact=expectation.field,
        absence_type=absence,
        coverage_ready=lens.ready_for(domain),
        # The basis travels only with the claim it is a receipt FOR. Attaching the connected
        # capability list to an `UNKNOWABLE` would read as "we looked at these and found
        # nothing", which is the sentence this whole type exists to keep unsayable.
        coverage_basis=lens.basis_for(domain)
                       if absence is AbsenceType.GENUINELY_ABSENT else ())


def classify_all(subject: AbsenceSubject, expectations: Sequence[Expectation],
                 lens: CoverageLens, *, eval_time: datetime,
                 stale_after: timedelta | None = None) -> tuple[MissingFact, ...]:
    """The TOTAL answer — every expectation, including the ones that are present.

    A caller must never have to read "no row" as "present"; that absence-of-a-row ambiguity is
    the thing this whole module exists to remove, and it would be reintroduced one layer up if
    the only available answer were the gaps.
    """
    return tuple(missing_fact(subject, expectation, lens,
                              eval_time=eval_time, stale_after=stale_after)
                 for expectation in expectations)


def detect_missing(subject: AbsenceSubject, expectations: Sequence[Expectation],
                   lens: CoverageLens, *, eval_time: datetime,
                   stale_after: timedelta | None = None) -> tuple[MissingFact, ...]:
    """The GAPS: everything the cascade did not answer `PRESENT` or `NOT_EXPECTED`."""
    return tuple(fact for fact in classify_all(subject, expectations, lens,
                                               eval_time=eval_time, stale_after=stale_after)
                 if fact.absence_type in STORED_TYPES)


def findings(facts: Iterable[MissingFact],
             expectations: Mapping[str, Expectation] | None = None) -> tuple[MissingFact, ...]:
    """The absences that are OUTPUT rather than data quality.

    Two conditions, and both are needed. `licenses_negative_inference` says the absence is safe to
    assert; `finding_if_absent` says it is worth asserting. A gap that lowers coverage without
    being interesting is real and is not a card.
    """
    lookup = expectations or {}
    return tuple(fact for fact in facts
                 if fact.is_finding
                 and (fact.expected_fact not in lookup
                      or lookup[fact.expected_fact].finding_if_absent))


# ── storage ──────────────────────────────────────────────────────────────────────
#
# From here down a connection is taken. Everything above is pure.

_UPSERT = f"""
insert into {ABSENCE_TABLE}
    (org_id, situation_id, expected_fact, subject_node_id, absence_type, coverage_ready,
     coverage_basis, coverage_domain, coverage_epoch, licenses_negative_inference, computed_at)
values (:o, :sid, :fact, :node, :kind, :ready, :basis, :dom, :epoch, :licence, :at)
on conflict (org_id, situation_id, expected_fact) do update set
    subject_node_id = excluded.subject_node_id,
    absence_type = excluded.absence_type,
    coverage_ready = excluded.coverage_ready,
    coverage_basis = excluded.coverage_basis,
    coverage_domain = excluded.coverage_domain,
    coverage_epoch = excluded.coverage_epoch,
    licenses_negative_inference = excluded.licenses_negative_inference,
    computed_at = excluded.computed_at
"""


def refresh_typed_absences(conn, org_id: str, subjects: Sequence[AbsenceSubject], *,
                           lens: CoverageLens, eval_time: datetime,
                           stale_after: timedelta | None = None) -> int:
    """Recompute every situation's typed absences. Returns rows written.

    IDEMPOTENT, and a recomputation rather than an append: a gap that has since been filled must
    stop being a finding, so the facts this pass did not produce for a situation are removed from
    that situation's row set. Removal is scoped to the situations actually recomputed — a sweep
    that saw ten situations must not delete the absences of a tenant's other two hundred.

    (This is not the "held candidates are never deleted" rule; that is `L2.5.8`'s and it is about
    a situation that failed to publish. An absence is a derived view of the graph, and a derived
    view that could not shrink would keep asserting a missing owner after the owner was recorded.)
    """
    written = 0
    for subject in subjects:
        expectations = expectations_from_spec(subject.domain, subject.situation_type)
        facts = detect_missing(subject, expectations, lens,
                               eval_time=eval_time, stale_after=stale_after)
        domain = canonical_domain(subject.domain)
        epoch = lens.epoch_for(domain)
        for fact in facts:
            conn.execute(text(_UPSERT), {
                "o": org_id, "sid": subject.situation_id, "fact": fact.expected_fact,
                "node": fact.subject_node_id, "kind": fact.absence_type.value,
                "ready": fact.coverage_ready, "basis": list(fact.coverage_basis),
                "dom": domain, "epoch": epoch,
                "licence": fact.licenses_negative_inference, "at": eval_time})
            written += 1
        conn.execute(text(
            f"delete from {ABSENCE_TABLE} where org_id = :o and situation_id = :sid "
            "and not (expected_fact = any(:keep))"),
            {"o": org_id, "sid": subject.situation_id,
             "keep": [f.expected_fact for f in facts]})
    return written


@dataclass(frozen=True, slots=True)
class StoredAbsence:
    """A typed absence read back, plus the one thing only a READER can know: whether the coverage
    regime it was drawn under still stands.

    `stale_coverage` is computed on read rather than stored, because it is a statement about the
    relationship between this row and the tenant's CURRENT epoch — a stored flag would have to be
    rewritten on every row of every situation each time any connector moved, and the first sweep
    that failed halfway would leave half the tenant confidently wrong.
    """

    situation_id: str
    fact: MissingFact
    coverage_domain: str
    coverage_epoch: int | None
    computed_at: datetime
    stale_coverage: bool = False

    @property
    def licenses_negative_inference(self) -> bool:
        """The licence, AND the epoch it was drawn under still standing.

        This is the read-side half of doc 13's rule and the reason it is a property rather than a
        pass-through: `MissingFact` can only know what was true when it was built. A
        `GENUINELY_ABSENT` from a superseded epoch is not wrong, it is UNVERIFIED — it must be
        re-evaluated before use, and until it is, it licenses nothing.
        """
        return self.fact.licenses_negative_inference and not self.stale_coverage


def read_absences(conn, org_id: str, *, situation_ids: Sequence[str] | None = None,
                  current: Mapping[str, int] | None = None) -> tuple[StoredAbsence, ...]:
    """Typed absences for a tenant, with every superseded one MARKED.

    `current` is the domain -> current epoch mapping; when omitted it is read from the open
    epochs. Marking rather than filtering, and never deleting: doc 13 is explicit that a
    superseded inference is *"marked, not trusted and not deleted — deleting it would lose the
    audit trail of what the system believed and why."*
    """
    if current is None:
        from genios_engine.context.quality.epoch import current_epochs
        current = {d: e.epoch for d, e in current_epochs(conn, org_id).items()}
    sql = (f"select situation_id, expected_fact, subject_node_id, absence_type, coverage_ready, "
           f"coverage_basis, coverage_domain, coverage_epoch, computed_at from {ABSENCE_TABLE} "
           "where org_id = :o")
    params: dict[str, object] = {"o": org_id}
    if situation_ids is not None:
        sql += " and situation_id = any(:sids)"
        params["sids"] = list(situation_ids)
    rows = conn.execute(text(sql + " order by situation_id, expected_fact"), params).mappings().all()
    out: list[StoredAbsence] = []
    for row in rows:
        fact = MissingFact(
            subject_node_id=str(row["subject_node_id"]),
            expected_fact=str(row["expected_fact"]),
            absence_type=str(row["absence_type"]),
            coverage_ready=row["coverage_ready"],
            coverage_basis=tuple(row["coverage_basis"] or ()))
        domain = str(row["coverage_domain"])
        drawn = row["coverage_epoch"]
        out.append(StoredAbsence(
            situation_id=str(row["situation_id"]), fact=fact, coverage_domain=domain,
            coverage_epoch=None if drawn is None else int(drawn),
            computed_at=row["computed_at"],
            stale_coverage=stale_coverage(domain=domain,
                                          drawn_under=None if drawn is None else int(drawn),
                                          current=current)))
    return tuple(out)


def absence_counts(conn, org_id: str) -> dict[str, int]:
    """`absence_type -> count` for one tenant. THE H6 MEASUREMENT.

    The gate row is *"0 negative inferences drawn from UNKNOWABLE facts"*, and a gate stated as a
    count needs something to count. `context_situations.missing` — a jsonb array of human phrases
    — cannot answer it, which is why this table exists at all.
    """
    rows = conn.execute(text(
        f"select absence_type, count(*) as n from {ABSENCE_TABLE} "
        "where org_id = :o group by absence_type"), {"o": org_id}).mappings().all()
    return {str(r["absence_type"]): int(r["n"]) for r in rows}


def unknowable_fields(absences: Iterable[StoredAbsence]) -> tuple[str, ...]:
    """The fact paths no connected source could have carried — what a predicate layer must treat
    as UNKNOWN rather than as a licence to say "there isn't one"."""
    return tuple(sorted({a.fact.expected_fact for a in absences
                         if a.fact.absence_type is AbsenceType.UNKNOWABLE}))


def absent_fields(absences: Iterable[StoredAbsence]) -> tuple[str, ...]:
    """The fact paths a source could have carried and none did, whose epoch still stands.

    The positive half of typed absence, and the reason it is not simply "the missing list": these
    are the only paths on which "there is no owner" may be said out loud.
    """
    return tuple(sorted({a.fact.expected_fact for a in absences
                         if a.licenses_negative_inference}))


__all__ = ["ABSENCE_TABLE", "STORED_TYPES", "AbsenceSubject", "Expectation", "StoredAbsence",
           "absence_counts", "absent_fields", "classify_absence", "classify_all",
           "detect_missing", "expectations_from_spec", "findings", "missing_fact",
           "read_absences", "refresh_typed_absences", "unknowable_fields"]
