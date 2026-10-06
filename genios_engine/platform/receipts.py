"""Semantic-readiness receipts — the runtime half of every structural claim.

Health metrics used to prove that jobs ran and schemas existed: an empty sweep looked healthy,
a skip read as a pass, and "Present / Wired / Tested" was communicated as active intelligence.
These receipts ask the other question — is the DEPLOYED tenant in the state the code implies? —
one read-only SELECT per structural claim, safe to run against production.

`scripts/runtime_receipts.py` is the CLI over this module; `/health/readiness` is the API over
it. One list of claims, two surfaces, so the release gate and the operator dashboard cannot
drift apart about what "ready" means.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text

# ⛔ The organisation-readiness counts, from the FLOOR — not from `executive/`. Both this module and
# `executive/readiness.py` need the same three queries, and duplicating them would let one drift from
# the other. Importing them from `executive/` would have made the floor import a layer, which the
# topology test does not catch because `platform` is cross-cutting and exempt — and an import nothing
# fails the build on is not a safe one, it is an unchecked one.
from genios_engine.platform.org_readiness_sql import COUNT_SQL as _RD_SQL
from genios_engine.platform.org_readiness_sql import COUNT_SQL_FLEET as _RD_SQL_FLEET
from genios_engine.platform import org_readiness_sql as _RD
from genios_engine.platform.self_identity import identity_sql

@dataclass(frozen=True)
class Receipt:
    """One structural claim, its query, and the predicate that decides pass/fail.

    `expect` receives the single scalar the query returns and answers "is the deployed system in
    the state the code implies?". Keeping the predicate next to the claim is what stops a receipt
    from quietly becoming a number nobody reads.
    """
    layer: str
    claim: str
    sql: str
    expect: Callable[[object], bool]
    detail: str = ""
    #: This claim is about the DEPLOYMENT, not the tenant, and its query is therefore not
    #: org-filtered. Declared rather than inferred: a receipt that simply forgot `:org` answers
    #: about every tenant at once while appearing on one tenant's readiness page — their parked
    #: queue reported as this one's — so "no filter" has to be a statement somebody made. The
    #: only members are questions whose answer cannot differ per tenant because the thing asked
    #: about is shared: the schema itself.
    fleet_wide: bool = False


#: ⛔⛔ **EVERY STATUS `evaluate()` CAN RETURN, AND WHETHER IT COUNTS AS READY** —
#: `{status: (ready?, one-line meaning)}`.
#:
#: ⛔ WHY THIS IS A CONSTANT AND NOT A CONVENTION. Two consumers read these strings — `/readiness`
#: in `api/routes.py` and the release-gate CLI `scripts/runtime_receipts.py` — and the endpoint's
#: own docstring promises *"the same list the release-gate CLI runs, so the operator surface and the
#: release gate cannot drift apart about what 'ready' means."*
#:
#: ⛔⛔ THEY HAD ALREADY DRIFTED IN SHAPE. The endpoint computed `status != "PASS"` and the CLI held
#: a literal `{"PASS": …, "FAIL": …, "ERROR": …}[status]` — ⛔ **which raises `KeyError` on a status
#: it has not met.** Adding `NOT_EXERCISED` would have CRASHED the release gate, not merely
#: disagreed with it. *Two implementations of one question will disagree on the day one of them is
#: right* — and here one of them would have stopped running.
#:
#: ⛔ `ready` IS PART OF THE TABLE, not of each caller. A `NOT_EXERCISED` receipt is **not** ready,
#: because `/readiness` exists to stop *"a skip reading as a pass"* and an unexercised correctness
#: receipt is that skip.
RECEIPT_STATUSES: dict[str, tuple[bool, str]] = {
    "PASS": (True, "the claim held and something exercised it"),
    "FAIL": (False, "the claim did not hold"),
    "ERROR": (False, "the query could not run, or its witness could not — an unrunnable receipt "
                     "is a finding, never a skip"),
    "NOT_EXERCISED": (False, "⛔ the claim held and NOTHING exercised it: the table this receipt "
                             "reads has no rows in scope, so 0 means 'nothing happened' rather "
                             "than 'nothing went wrong'. Condition `P2` unmet, and visibly so"),
}


#: ⛔⛔ **RECEIPTS WHOSE WITNESS CANNOT BE DERIVED FROM THEIR OWN OUTER `from`** —
#: `{claim: (witness sql or None, why)}`.
#:
#: ⛔ WHY A WITNESS EXISTS AT ALL. A **correctness** receipt asks *"did the wrong thing happen"* and
#: answers 0 when it did not. ⛔ Over an EMPTY table it also answers 0 — and passes having proved
#: nothing. That is condition `P2` of this programme's definition of production level (*the receipt
#: can fail*), and before this it was unmet and invisible: the readiness surface reported a pass.
#:
#: ✅ A **presence** receipt needs none. It asks *"did anything happen"* and FAILS on an empty
#: table, so it witnesses itself. Measured 2026-10-04: 32 of the 48 receipts are correctness and 16
#: are presence, and the distinction is already in the data (`expect(0)`) rather than in a list
#: anybody maintains.
#:
#: ✅ FOR 45 OF 48 THE WITNESS IS DERIVED, not written: the outer `from <table>` of the receipt's own
#: SQL, counted with the same `:org` filter the receipt carries. ⛔ Only the outer one — a table
#: named in a join or a subquery is not the subject of the claim, and taking it would witness the
#: wrong thing.
#:
#: ⛔⛔ **A WITNESS IS A PRESENCE RECEIPT, AND THREE OF THEM ALREADY EXIST EXPLICITLY.** Measured
#: 2026-10-04: the derived witness for a correctness receipt over `expertise_packages`,
#: `delivery_outbox` and `learning_runs` is **byte-identical** to the SQL of the presence receipts
#: *"compiled expertise packages exist"*, *"the delivery control plane has run"* and *"the learning
#: engine has executed"*. ✅ That is a coherence check on the design rather than a duplication to
#: remove: the question *"was this claim exercised"* and the question *"has this layer ever run"*
#: are the same question, and 28 more of them are now derived instead of waiting to be written.
#:
#: ⛔ It also made a test unanswerable for three attempts — attributing a shared SQL string to the
#: receipt that asked it is not possible, so `test_the_witness_is_asked_only_on_a_pass` uses a
#: fixture of two.
#:
#: Three do not derive, each for a different reason, and `None` means *"needs no witness"*:
WITNESS_EXCEPTIONS: dict[str, tuple[str | None, str]] = {
    "every reasoning unit that says nothing is one we declared": (
        "select count(*) from reasoning_reasoner_results where 1=1",
        "⛔ A DERIVED-TABLE OUTER `from`: the query opens on `jsonb_each(...)`, so the outer name is "
        "a function and not a table. ✅ The real source was ALREADY declared, in "
        "`receipt_coverage`'s own entry for this claim — *'Derived-table outer `from`; the real "
        "source is `reasoning_reasoner_results`'* — so this witness is that declaration's sibling "
        "rather than a new judgement"),
    "a deleted tenant leaves nothing behind": (
        None,
        "⛔ NEEDS NO WITNESS. A `with recursive` over `information_schema`: the claim is about the "
        "SCHEMA's foreign keys, not about any tenant's rows, and the schema always has rows. A "
        "witness here would be noise that always passed, which is the thing this table exists to "
        "stop"),
    "the counterfactual ledger joins end to end": (
        None,
        "⛔⛔ ITS OUTER NAME IS A VIEW, NOT A TABLE — `create or replace view counterfactual_ledger` "
        "in `0072`, which is why `table_coverage._known_tables()` cannot see it. ✅ And it is a "
        "PRESENCE receipt, so it fails on an empty ledger and needs no witness regardless. The "
        "view blindness is declared in `platform/table_coverage.SCHEMA_OBJECTS_NOT_SEEN`"),
}


def witness_sql(receipt: "Receipt", org: str | None) -> str | None:
    """The query whose NON-ZERO result means this receipt's `PASS` meant something.

    `None` means no witness is wanted — either the receipt is a presence receipt (self-witnessing)
    or `WITNESS_EXCEPTIONS` says so with a reason.

    ⛔ ONE IMPLEMENTATION, AND THAT IS DELIBERATE. `3.1b` closed a hole where a guard re-derived a
    metric's logic beside it and the two drifted the day one of them was right. Both `evaluate()`
    and the guard call this.
    """
    # ⛔ THE FILTER IS THE RECEIPT'S, NOT THE CALLER'S. A first version appended
    # `_org_filter(org)` unconditionally, which was right for all 48 receipts TODAY and wrong as a
    # rule: a FLEET-WIDE correctness receipt asks about the schema, its table may carry no `org_id`
    # column at all, and the witness would then raise instead of answering. Measured before the
    # change: 0 of 48 disagreed — ⛔ a coincidence of the current set, not a reason.
    scoped = _org_filter(org) if ":org" in receipt.sql else ""
    if receipt.claim in WITNESS_EXCEPTIONS:
        declared, _why = WITNESS_EXCEPTIONS[receipt.claim]
        return None if declared is None else declared + scoped
    if receipt.expect(0) is not True:
        return None                                # presence: it fails on an empty table already
    match = _OUTER_FROM.match(" ".join(receipt.sql.split()))
    if match is None:                              # pragma: no cover - the exceptions cover these
        return None
    # ⛔⛔ THE DERIVED NAME MUST BE A TABLE, AND THE FIRST VERSION OF THIS DID NOT CHECK. An outer
    # `from` can name a function (`jsonb_each`), a CTE, or a VIEW — `counterfactual_ledger` is one
    # — and a witness over a non-existent relation does not report "unexercised", it raises. ⛔ So
    # it refuses, and the refusal is what makes `WITNESS_EXCEPTIONS` necessary rather than
    # incidental: a receipt whose outer name is not a table has to be declared.
    from genios_engine.platform.table_coverage import _known_tables

    table = match.group(1)
    if table not in _known_tables():
        return None
    return f"select count(*) from {table} where 1=1{scoped}"


#: The outer `from` of a receipt's own SQL — ⛔ the FIRST one, non-greedily, because a join or a
#: subquery names tables the claim is not about.
_OUTER_FROM = re.compile(r"^\s*select\s+.*?\bfrom\s+([a-z_][a-z_0-9]*)", re.IGNORECASE | re.DOTALL)


def _org_filter(org: str | None, alias: str = "") -> str:
    p = f"{alias}." if alias else ""
    return f" and {p}org_id = :org" if org else ""


def _UNDECLARED_UNWRITTEN_FACTS_SQL(org: str | None) -> str:
    r"""How many fact paths a reasoning unit BINDS have no rows and no declaration.

    ⛔ THE BOUND LIST IS DERIVED FROM `expertise._ROSTER`, never copied. A seventh role added to a unit
    enters this query without an edit — the rule `S5.U02` established for `AXIS_SOURCES`.

    ⛔ THE QUESTION IS NOT "IS ANY BOUND PATH EMPTY". Measured 2026-10-01: 14 of 22 are, for one root
    (no CRM connector) this layer cannot clear. `api/routes.py:161` computes `ready = not failed` from
    this list, so that claim would be permanently red, and a gate that is always red is a gate nobody
    reads. The claim is the one that is true today and false when it gets worse.

    ⛔ IT COUNTS ROWS PER PATH, NOT DISTINCT NODES. A path with one row has a writer; that is the whole
    question. How WELL it is covered is `deal.status`'s 3-of-293 problem, a different measurement with
    a different mover.

    The paths are inlined as literals for the reason the sibling builder states: `evaluate()` binds
    exactly one parameter. A test asserts every one matches `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$`.
    """
    from genios_engine.reason.unit_health import DECLARED_UNWRITTEN_PATHS, roster_fact_paths

    candidates = sorted(set(roster_fact_paths()) - set(DECLARED_UNWRITTEN_PATHS))
    if not candidates:
        return "select 0"
    wanted = ", ".join(f"'{path}'" for path in candidates)
    return (
        f"select {len(candidates)} - count(distinct field) from graph_facts "
        f"where field in ({wanted})" + _org_filter(org)
    )


def _PLACEHOLDER_COMPONENTS_SQL(org: str | None) -> str:
    r"""Candidates the CURRENT scorer wrote carrying the neutral-default ranking formula.

    ⛔ THE PREDICATE IS UNCHANGED FROM THE ORIGINAL RECEIPT. The three equalities below are
    byte-for-byte what this receipt has always asked. The ONLY thing added is a lower bound, and
    that is the entire fix — see `speedrun008/YCW27/layer-2-reasoning/12-AUDIT-D-the-frozen-formula-receipt.md`.

    ⛔ WHY A LOWER BOUND IS NOT A WEAKENING. `reasoning_candidates` is append-only and this codebase
    soft-deletes only, so the 59 rows the defect wrote on one org between 2026-08-17 and
    2026-09-07 are permanent. Without a bound the receipt returns 59 forever, for a defect closed
    on 2026-09-08, and `api/routes.py:161` computes `ready = not failed` over it — one unfixable
    receipt holding the release gate shut. **A receipt over append-only history needs a lower
    bound, or it is not a gate but a monument.**

    ⛔ THE BOUND IS IMPORTED, NEVER RESTATED HERE. `reason/unit_health.neutral_default_boundary()`
    owns the date together with the commit that establishes it, so the receipt cannot drift from
    the declaration by carrying its own copy. Measured 2026-10-01: 34,167 candidates written at or
    after the boundary, across all three orgs, **zero** frozen.

    The date is inlined as a literal because `evaluate()` binds exactly one parameter; a test
    asserts it matches `^\d{4}-\d{2}-\d{2}$` before it is interpolated.
    """
    from genios_engine.reason.unit_health import neutral_default_boundary

    boundary = neutral_default_boundary()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", boundary):
        raise ValueError(f"boundary must be an ISO date, got {boundary!r}")
    return (
        "select count(*) from reasoning_candidates where "
        "score_components->>'impact' = '5000' and score_components->>'risk' = '5000' "
        f"and score_components->>'effort' = '5000' and created_at >= '{boundary}'"
        + _org_filter(org)
    )


def _UNATTRIBUTED_APPROVALS_SQL(org: str | None) -> str:
    r"""Actions that announce a sign-off requirement while nothing can name who signs.

    ⛔ THE MEASURED GAP. 2026-10-01: `execution_actions` holds 794 rows and **410 of them carry
    `requires_approval`** — 52% of every action this layer has ever planned. `authority_rules`
    holds **zero** rows, so `AuthorityView.resolve` answers `no_authority_rule` for every subject
    and `assignment.resolve_approver_seat` correctly returns `None` for every call. Per org:
    182, 121 and 107 actions each saying *this needs sign-off* and none able to say whose.

    `resolve_approver_seat`'s own docstring states the cost: *"a card that says 'this needs
    sign-off' and cannot say whose is less useful than one that can, and far better than one that
    quietly drops the requirement."* ⛔ **This receipt is what stops the "less useful" state from
    being silent.** Nothing today counts it.

    ⛔ A CONJUNCTION, NOT A COUNT — the same shape as the era receipt next door, for the same
    reason. `requires_approval` on its own is **healthy**: it is the autonomy gate
    (`contracts/execution.py:233` — `not requires_approval and not external_effect`) doing its
    job, and 410 gated actions is the layer being careful. The defect is a gated action **in an
    org that holds no rule capable of naming an approver**.

    ⛔ AN IN-FORCE RULE, NOT ANY ROW. Three conditions, and each one is a way to hold a rule and
    still name nobody:
      · `approver_node_id is not null`  — a threshold with no approver names nobody
      · `valid_from <= now()`           — a rule that starts next quarter is not in force
      · `valid_until is null or > now()` — an expired rule is not an enforceable one
    Counting rows alone would go green for a tenant whose only rule lapsed last year.

    ⛔ WHY `now()` IS CORRECT HERE AND NOWHERE ELSE. The doctrine is `eval_time` as a parameter,
    never a clock read — because a unit must replay at its original instant. A receipt is the
    opposite question: *is the DEPLOYMENT in the state the code implies, right now.* `evaluate()`
    binds exactly one parameter, and receipt #1 (`watermark > now()`) set this precedent.

    ⛔ AND ZERO IS A TRUE PASS HERE, UNLIKE THE ERA RECEIPT. `_ERA_SELECTS_NOTHING_SQL` returns
    `-1` for an empty window because an era that produced nothing is a dead pipeline. This one is
    different: no gated actions genuinely means no requirement is unattributed. The two receipts
    make opposite choices about emptiness on purpose, because emptiness means opposite things.

    ⛔ WHAT IT DOES *NOT* CLAIM. It does not say every gated action resolves an approver — a
    tenant may hold a rule for one subject type and not another, and that is a finer question with
    a different query. It says the tenant holds **no** way to name one, which is the state that
    makes all 410 unattributable at once. The wiring that would consume an answer is **not built**:
    neither `execution_actions` nor `executions` has an approver column, so it needs a contract
    field and a migration, and `0186`-`0190` have never run. See
    `speedrun008/YCW27/layer-4-executive/02-PLAN.md` U2.
    """
    return (
        "select count(*) from execution_actions a"
        " where a.requires_approval"
        "   and not exists ("
        "         select 1 from authority_rules r"
        "          where r.org_id = a.org_id"
        "            and r.approver_node_id is not null"
        "            and r.valid_from <= now()"
        "            and (r.valid_until is null or r.valid_until > now()))"
        + _org_filter(org, "a")
    )


def _ERA_SELECTS_NOTHING_SQL(org: str | None) -> str:
    r"""Runs in the current reasoning era that produced candidates and selected none of them.

    ⛔ THE DEFECT THIS EXISTS FOR, AND WHY THIRTY RECEIPTS MISSED IT. Measured 2026-10-01: the
    product had produced no card for six days. `reasoning_candidates` held 8,044 candidates on
    2,681 runs, every one `disposition='eligible'`, and `selected_candidate_id` was NULL on all
    2,681 — so no signal was emitted, `executive/`'s gate matched nothing, and the existing cards
    aged out. **Every receipt that could plausibly have caught it was green**, and four of them
    were green for reasons worth stating:

        #19 more than one candidate is ever considered   = 11      candidates ARE produced
        #21 the system has abstained at least once       = 1,772   ⛔ green BECAUSE of the defect
        #22 decisions become tracked commitments         = 75      green on append-only history
        #14 the live pass has actually run               = 2,376   the pass runs, and emits nothing

    `#21` is the one to read twice: abstention is healthy and this receipt measures that it
    happens, so a system abstaining **100% of the time** satisfies it perfectly.

    ⛔ A CONJUNCTION, NOT A COUNT — and this is the whole design. A high defer rate is healthy: the
    previous era deferred 8,208 times and still produced 1,157 decisions. The defect is a
    selection rate of **exactly zero** over runs that had something to select from. Audit D's rule
    one layer down: *a count without its dimension is not a measurement*.

    ⛔ AND IT MUST NOT PASS VACUOUSLY. `count(*) > 0 and count(selected) = 0` expressed as a
    `having` clause returns no rows when the era produced no runs at all — which reads as "no
    violation" and would make this receipt **green on a completely dead pipeline**, the exact
    failure it exists to prevent. So an empty era returns `-1` and fails. The three answers are
    distinct on purpose:

        -1   the era produced no runs with candidates   -> FAIL, and it is a different sentence
         N   N runs had candidates and selected NONE     -> FAIL, and N says how many
         0   at least one selection happened             -> PASS

    ⛔ THE ERA BOUNDARY IS IMPORTED, NEVER RESTATED. `reason/unit_health.current_reasoning_era()`
    owns it together with the measurement that establishes it — the same rule
    `neutral_default_boundary` established, for the same reason: a receipt carrying its own copy
    of a date drifts from the declaration silently.

    ⛔ WHY THE ERA BOUND IS NOT A WEAKENING. Without it this question averages a live
    implementation with a retired one: 9,489 runs predate per-unit results and answer about a
    pipeline that no longer exists. With it, the receipt is about what the deployed code does now.
    **A receipt over append-only history needs a lower bound, or it is not a gate but a monument.**

    ⛔ WHAT IT DOES *NOT* CLAIM. It does not say the cause. The cause on 2026-10-01 was
    `GENIOS_L4_LLM_DECISION_MAKER = true` with the Anthropic spend limit refusing every call and
    `reason/llm_decision_maker.py:20`'s declared *"Failure is DEFER, never the formula"* — a
    deliberate design, not a bug. A receipt reports a state; the reason lives in
    `speedrun008/YCW27/layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md` and the choice
    in `02-DECISIONS.md` decision #5.

    The date is inlined as a literal because `evaluate()` binds exactly one parameter; the ISO
    shape is asserted before interpolation, as the frozen-formula receipt does.
    """
    from genios_engine.reason.unit_health import current_reasoning_era

    boundary = current_reasoning_era().boundary
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", boundary):
        raise ValueError(f"reasoning era boundary must be an ISO date, got {boundary!r}")
    return (
        "select case"
        "         when count(*) = 0 then -1"
        "         when count(ro.selected_candidate_id) = 0 then count(*)"
        "         else 0"
        "       end"
        "  from reasoning_run_outputs ro"
        f" where ro.created_at >= '{boundary}'"
        "   and exists (select 1 from reasoning_candidates rc"
        "                where rc.org_id = ro.org_id and rc.run_id = ro.run_id)"
        + _org_filter(org, "ro")
    )


def _UNDECLARED_NEVER_COMPLETED_SQL(org: str | None) -> str:
    r"""Units that have RUN and never once completed, and that nobody declared.

    ⛔ THIS QUESTION IS NOT THE SILENCE QUESTION, AND THE DIFFERENCE IS ONE CLAUSE.
    `_UNDECLARED_SILENT_UNITS_SQL` filters `status = 'completed'` and asks whether the completions
    said anything. A unit with **zero** completed rows is therefore not a row with a low share —
    **it is not a row** — so it cannot appear in that GROUP BY at all. Measured 2026-10-01,
    `core.relationship` has **929 runs and 0 completions** and the silence receipt PASSES.

    > A unit that never completes is not a quiet unit; it is an absent one, and a question asked
    > only of completions cannot see it.

    ⛔ SO THIS ONE DELIBERATELY DOES NOT FILTER BY STATUS. That filter is the whole defect. It
    groups every result row per unit and keeps the units whose completed count is zero.

    ⛔ `having count(*) > 0` IS NOT REDUNDANT, IT IS THE POINT. A unit with no rows at all is a
    different fact — nobody scheduled it — and belongs to ALARM A2, not here.
    `core.signal_composition` is exactly that: 0 runs, because `DEAL_HEALTH_V1` has never been
    swept. A ratio would make 0/0 and 0/929 the same number.

    ⛔ THE EXCUSED SET IS IMPORTED AND PARTLY DERIVED. `core.policy` also has zero completions (165
    runs) and is legitimately accounted for by the sibling grain: all four fact paths it binds are
    in `DECLARED_UNWRITTEN`. `unit_health.starved_by_declared_paths()` computes that from the
    roster, so this receipt never carries a second copy of the fact and cannot go stale when a path
    gains a writer. Inlined as literals because `evaluate()` binds exactly one parameter; a test
    asserts every id matches `^[a-z][a-z0-9_.]+$`.
    """
    from genios_engine.reason.unit_health import (DECLARED_NEVER_COMPLETED_IDS,
                                                  starved_by_declared_paths)

    excused = sorted(DECLARED_NEVER_COMPLETED_IDS | starved_by_declared_paths())
    for unit in excused:
        if not re.fullmatch(r"[a-z][a-z0-9_.]+", unit):
            raise ValueError(f"not a unit id: {unit!r}")
    declared = ", ".join(f"'{unit}'" for unit in excused) or "''"
    return (
        "select count(*) from ("
        "  select reasoner_id"
        "    from reasoning_reasoner_results"
        "   where 1=1" + _org_filter(org) +
        "   group by reasoner_id"
        "  having count(*) > 0"
        "     and sum(case when status = 'completed' then 1 else 0 end) = 0"
        f"     and reasoner_id not in ({declared})"
        ") as undeclared_never_completed"
    )


def _UNDECLARED_SILENT_UNITS_SQL(org: str | None) -> str:
    """How many units are silent above the threshold and NOT declared in `reason/unit_health`.

    ⛔ THE PREDICATE COMES FROM `reason/unit_health.SILENT_SQL`, NEVER RESTATED HERE. It is the same
    rule `is_silent` applies in Python, and `tests/reason/test_a_unit_that_says_nothing_is_not_working.py`
    runs both over the same production rows under the `pg` gate. Two expressions of one rule that are
    never compared eventually disagree — this programme has found that shape five times.

    ⛔ A SHARE, NOT A COUNT. One silent completion out of a thousand is noise; ninety per cent is a
    unit that does not work. The threshold is `SILENT_THRESHOLD_PCT` and lives with the declaration.

    ⛔ THE DECLARED SET IS INLINED AS LITERALS RATHER THAN BOUND. `evaluate()` passes exactly one
    parameter (`:org`), so a second bound list would need a signature change across every receipt.
    The ids are module constants matching `^[a-z][a-z0-9_.]+$`, asserted by a test, so there is
    nothing here a caller can influence.
    """
    from genios_engine.reason.unit_health import (DECLARED_SILENT_IDS, SILENT_SQL,
                                                  SILENT_THRESHOLD_PCT)

    declared = ", ".join(f"'{unit}'" for unit in sorted(DECLARED_SILENT_IDS)) or "''"
    return (
        "select count(*) from ("
        "  select reasoner_id,"
        f"         100 * sum(case when {SILENT_SQL.strip()} then 1 else 0 end) / count(*) as pct"
        "    from reasoning_reasoner_results"
        "   where status = 'completed'" + _org_filter(org) +
        "   group by reasoner_id"
        f"  having 100 * sum(case when {SILENT_SQL.strip()} then 1 else 0 end) / count(*) "
        f"         >= {int(SILENT_THRESHOLD_PCT)}"
        f"     and reasoner_id not in ({declared})"
        ") as undeclared_silent"
    )


#: ⛔ L5 · AN ATTEMPT THAT STARTED AND NEVER SETTLED IS AN AMBIGUITY, AND IT MUST NOT BE SILENT.
#:
#: `deliver/spine.recover_expired_claims` exists to mark exactly these `unknown` before anyone
#: reclaims the row: *"An expired worker may have POSTed to a provider before dying; we must never
#: silently retry over that ambiguity."* Measured 2026-10-01: **nothing calls it, and nothing calls
#: `claim_due` either** — the v2 control plane is un-cut-over, so this reads 0 today. That is the
#: point. It is the receipt that starts answering the moment the cutover is taken.
#:
#: ⛔ DELIBERATELY FENCE-INDEPENDENT, AND THIS IS THE DESIGN DECISION WORTH READING. The recovery
#: joins on `a.claim_token = d.fence_token`, and `claim_due` writes a NEW fence when it reclaims a
#: row — so the orphans that matter MOST, the ones whose row was already handed to a fresh worker,
#: can never match the recovery's own predicate again. A receipt built on that join would miss
#: precisely the permanently-unrecoverable cases. **A guard must not inherit the blind spot of the
#: thing it guards.**
#:
#: ⛔ AND THE WINDOW IS JUSTIFIED, NOT PICKED. One hour is twelve default leases
#: (`claim_due(lease_seconds=300)`) and nine hundred provider timeouts (`push._TIMEOUT_S = 4.0`), so
#: a merely slow attempt cannot be reported as an ambiguous one. A tighter window would turn
#: latency into an alarm, and the fix for a false alarm is always to loosen the check.
_UNSETTLED_ATTEMPT_SQL = (
    "select count(*) from delivery_attempts a"
    " where a.outcome = 'started'"
    "   and a.settled_at is null"
    "   and a.started_at < now() - interval '1 hour'")


#: ⛔ L5 · A CARD MUST NOT OUTLIVE ITS OWN WINDOW IN A LIVE STATE.
#:
#: `CardStore.sweep_lifecycle` expires non-terminal cards past `expires_at` and logs
#: `window.lapsed`, which feeds L6's ignore-rate — so a card still `queued` long after its window
#: closed is BOTH a card a founder may still act on and a row L6 will never count. The sweep is
#: wired: `api/routes.py:951` calls it "every tick: expire + snooze-wake + claim-release".
#:
#: ⛔ THE TWELVE HOURS ARE MEASURED, NOT PICKED. That tick is `run_maintenance_sweep`'s HEAVY
#: pass, whose interval is `config.sync_interval_hours` — measured at **6.0** — and one sweep is
#: bounded by `scheduler._SWEEP_TIMEOUT_S = 1200`. A one-hour grace (my first instinct) would have
#: fired on every card that expired in the normal six-hour gap between ticks: latency reported as an
#: alarm, and *the fix for a false alarm is always to loosen the check.* Twelve hours is TWO full
#: maintenance cycles, so a card must survive two of them before it counts.
_CARD_OUTLIVED_ITS_WINDOW_SQL = (
    "select count(*) from cards"
    " where state in ('queued', 'surfaced', 'snoozed')"
    "   and expires_at < now() - interval '12 hours'")


#: ⛔ L5 · A CARD PARKED FOR WANT OF A CHANNEL MUST NOT STAY PARKED ONCE ONE EXISTS.
#:
#: `outbox.revive_undeliverable` is "the answer to 'a card must become deliverable the moment a
#: channel exists'", and until 2026-10-01 nothing called it — so a tenant who registered Slack on
#: Tuesday kept every card parked before Tuesday. `api/channel_routes.set_slack` now revives on
#: registration (STEP-15); this is the production question that says whether it worked.
#:
#: ⛔ THE CHANNEL SET IS INJECTED, NOT HARD-CODED. `deliverable_channels` intersects
#: `org_channels` with the channels that HAVE AN ADAPTER, and that half lives in a Python registry
#: (`channels/base.get_channel`) which SQL cannot see. Naming 'slack' in the query would rot the
#: day a second adapter lands; building the literal from `_implemented_channels()` keeps the two
#: halves of that judgement in one place — the same injection receipt #31 uses for its era
#: boundary.
#:
#: ⛔ AND IT MATCHES THE ROW'S OWN CHANNEL. The park is per-channel: a row parked for `teams` is
#: not revived because `slack` appeared. `c.channel = d.channel` is what keeps this a question about
#: THIS row rather than about the org.
def _CONSTRAINED_BRAIN_VALUE_SQL(org: str | None) -> str:
    r"""Active brain values narrower than the surface that renders them.

    ⛔ WHY THE CODE GUARD IS NOT ENOUGH. `feedback/target_policy` proves statically that no
    PRODUCER proposes a constrained durable value — every delegated producer constructs
    `Visibility(scope=ORGANIZATION)`, and the one PRIVATE `LearningObject` in the engine targets
    `METRICS`, which lands in `learning_metrics`. But the human APPROVAL path
    (`api/learning_routes`) rehydrates a persisted proposal and its visibility is a value read back
    from `learning_objects.visibility`. ⛔ **No amount of AST reading can know what is in that
    column**, so the only honest check of the second half is this one, against the data.

    ⛔ WHAT A NON-ZERO COUNT MEANS. `api/brain_routes` selects the VALUE out of both sinks filtered
    only on `org_id` / `active` / `brain`, behind `Depends(get_current_org)` — which admits any
    credential of the tenant, including a `member` seat whose own definition in `platform/auth.py`
    is *"reads and acts on the cards routed to their own seat, **and nothing org-wide**."* So one
    constrained row in either sink is a learned value rendered to people its own visibility
    excludes — Atlas `L7`'s *"prohibited evidence never reaches active brain or rendered
    rationale"*.

    ⛔ THE OPEN SET IS DERIVED FROM THE CONTRACT, NEVER SPELLED. `target_policy.OPEN_SCOPES` holds
    ENUM MEMBER NAMES because it is read off the AST; the column holds enum VALUES. Translating
    through `VisibilityScope[...]` is what keeps a renamed member from widening what this accepts,
    which is the rule `_ILLEGAL_TRANSITION_SQL` follows for lifecycle edges.
    """
    from genios_engine.contracts.learning import VisibilityScope
    from genios_engine.feedback.target_policy import BRAIN_SINKS, OPEN_SCOPES

    open_values = sorted(VisibilityScope[name].value for name in OPEN_SCOPES)
    for v in open_values:                     # SQL text from an Enum: assert the shape, never assume
        assert re.fullmatch(r"[a-z_]+", v), v
    literal = ", ".join(f"'{v}'" for v in open_values)
    # Both sinks, one scalar. `visibility_scope is null` counts: an unrecorded scope is not an open
    # one, which is the same fail-closed reading `contracts/learned_state._visible` takes.
    parts = [f"(select count(*) from {sink} where active "
             f"and (visibility_scope is null or visibility_scope not in ({literal}))"
             f"{_org_filter(org)})"
             for sink in BRAIN_SINKS]
    return "select " + " + ".join(parts)


def _ABSORBED_NODE_REFERENCE_SQL(org: str | None) -> str:
    r"""Live rows still pointing at a node a merge absorbed.

    ⛔ THE MODULE'S OWN WORDS ARE THE CLAIM. `context/merge.py` introduces its node-reference list
    with *"Every table that names a node. **Missing one leaves rows pointing at a closed node —
    invisible in the UI, still returned by any query that joins on node_id.**"* That is a failure
    nothing checked: entity merge is the one operation that rewrites identity across the graph, and
    `context/` had two receipts over 50,877 lines, neither about merge.

    ⛔ THE PAIRS ARE DERIVED FROM THE THREE DECLARED CONSTANTS, NEVER COPIED — `_NODE_REFERENCES`,
    `_CORRELATION_HANDLED_SEPARATELY` and `_EDGE_NODE_COLUMNS`. A sixth table entering the merge
    loop enters this receipt without an edit, which is the `QUARANTINABLE_SEAMS` pattern; a copy
    here would silently stop covering whatever was added last.

    ⛔ `reversed` MERGES ARE EXCLUDED. `reverse_merge` repoints the rows back and reopens exactly
    the edges it closed, so a reversed row legitimately names the formerly-merged node again.
    Counting those would make this red on every tenant that has ever undone a merge — *a gate that
    is always red is a gate nobody reads.*
    """
    from genios_engine.context.merge import (_CORRELATION_HANDLED_SEPARATELY,
                                             _EDGE_NODE_COLUMNS, _NODE_REFERENCES)

    pairs = [*_NODE_REFERENCES, _CORRELATION_HANDLED_SEPARATELY,
             *(("graph_edges", column) for column in _EDGE_NODE_COLUMNS)]
    # SQL text built from Python constants: the shape is asserted, never assumed.
    for table, column in pairs:
        assert re.fullmatch(r"[a-z_][a-z_0-9]*", table), table
        assert re.fullmatch(r"[a-z_][a-z_0-9]*", column), column
    parts = [
        f"(select count(*) from {table} t join merge_history m "
        f"on m.org_id = t.org_id and m.merged_node_id = t.{column} "
        f"where not m.reversed{_org_filter(org, 't')})"
        for table, column in pairs]
    return "select " + " + ".join(parts)


def _PARKED_WARM_LANE_SQL(org: str | None) -> str:
    r"""Warm-lane rows parked for a human that no human can see.

    ⛔ THE SCHEMA STATES THE CLAIM. `migrations/0136_warm_lane.sql` comments the column itself:
    *"attempts ran out: parked for a human, never retried, never blocking a re-enqueue."*

    ⛔⛔ AND EVERY READER USES IT ONLY AS AN EXCLUSION. `warm_lane._OPEN` is
    `"done_at is null and parked_at is null"`; `api/routes.py`'s backlog count uses the same
    predicate, and `warm_lane.housekeep` warns on the age of the OPEN backlog and prunes only
    `done_at` rows. So a row whose attempts ran out is removed from every count, never pruned, and
    **selected by nothing** — the tenant's events stop being processed silently and permanently,
    while the health signal reports zero open rows and looks fine.

    ⛔ *A refusal nobody can see is a silent stop* — and this is the worst version of it in the
    product, because the health check does not merely miss the parked rows, it **excludes them by
    construction**.

    ⛔ THE PREDICATE IS DERIVED FROM `warm_lane._OPEN`, NEVER RESPELLED. This receipt must cover
    exactly what that predicate excludes; a copy here would stop matching the day the lane's own
    definition of "open" changes, which is the rule `_ILLEGAL_TRANSITION_SQL` follows for the
    learning lifecycle edges.

    ⛔ L1 ALREADY HAS THIS RECEIPT FOR THE OTHER PARKED TABLE — *"the parked queue is not a black
    hole"*, over `parked_events`. This is the same claim applied to the table that lacked it, so it
    is a precedent rather than an invention.
    """
    from genios_engine.platform.warm_lane import _OPEN

    # The lane's own "open" is `done_at is null and parked_at is null`. The half this receipt is
    # about is the second clause, taken from that string rather than written again.
    clauses = [c.strip() for c in _OPEN.split(" and ")]
    parked = next((c for c in clauses if c.startswith("parked_at")), None)
    assert parked == "parked_at is null", (
        f"warm_lane._OPEN no longer excludes parked rows the way this receipt assumes: {_OPEN!r}. "
        "⛔ If the lane has started counting parked rows as open, they are visible and this "
        "receipt is redundant — delete it deliberately rather than leaving it asking the wrong "
        "question")
    return ("select count(*) from l2_work_queue where parked_at is not null"
            f"{_org_filter(org)}")


def _UNEXPLAINED_EVENT_SQL(org: str | None) -> str:
    r"""Captured events that never reached a signal and say nowhere why.

    ⛔ THE CLAIM IS `capture/journey.py`'s OPENING SENTENCE, quoted from `qualification.py`:

        a system that discards 92% of what a founder was sent has to be able to answer
        "why did I never see X?" in one query

    ⛔⛔ AND THE SAME MODULE RECORDS WHAT IT COST TO NOT HAVE THIS. *"Every layer kept its half of
    that bargain and wrote its refusal down. **Nothing ever joined them.** Measured on the pilot
    org: `event_trace` holds 10,840 rows and had NO read surface at all … Of 138 events one support
    question was really about, 103 stopped at `s4_esqe short_circuit bulk_headers` and 33 at
    `llm5_not_business`; **a founder reading `/qualification/drops` would have found nothing and
    concluded the events were lost.**"* `journey.event_journey` is the join that answers it — and
    nothing checks that every event HAS an answer.

    ⛔ EVERYTHING HERE IS DERIVED, NOTHING SPELLED:
      * the stopping actions come from `journey.TRACE_STOPPING`;
      * the event-keyed ledgers come from `journey._LEDGERS` minus `journey._PER_SIGNAL_LEDGERS`,
        because a per-SIGNAL refusal cannot name an event that never produced a signal — the module
        declares that distinction itself, and a fifth event-keyed ledger joins this check without
        an edit;
      * `qualified_signals` is that tuple's success member and becomes the "did reach a signal"
        test rather than a refusal;
      * and the horizon is `4 x platform/config.sync_interval_hours`, the declared sweep tick —
        four ticks, so an event still mid-flight is never counted. ⛔ **The multiplier is the one
        judgement in this query and it is stated here rather than buried in the SQL.**

    ⛔ A NON-ZERO COUNT IS A FOUNDER'S QUESTION WITH NO ANSWER. The event was captured, four sweeps
    have passed, it produced no signal, and no layer wrote down what stopped it — which is the one
    outcome `journey.py` exists to make impossible.
    """
    from genios_engine.capture.journey import _LEDGERS, _PER_SIGNAL_LEDGERS, TRACE_STOPPING
    from genios_engine.platform.config import get_settings

    actions = sorted(TRACE_STOPPING)
    for action in actions:                      # SQL text from a frozenset: assert, never assume
        assert re.fullmatch(r"[a-z_]+", action), action
    event_keyed = [name for name, _column in _LEDGERS if name not in _PER_SIGNAL_LEDGERS]
    assert "qualified_signals" in event_keyed, (
        "`journey._LEDGERS` no longer carries the success ledger; this receipt's 'did it reach a "
        f"signal' test came from it. Event-keyed members today: {event_keyed}")
    refusals = [name for name in event_keyed if name != "qualified_signals"]
    assert refusals, (
        "no event-keyed refusal ledger is left in `journey._LEDGERS` — every refusal is now "
        "per-signal, and an event that produced no signal has nowhere to be recorded. That is a "
        "bigger finding than this receipt and should be read before it is deleted")
    for name in event_keyed:
        assert re.fullmatch(r"[a-z_]+", name), name

    hours = 4 * float(get_settings().sync_interval_hours or 6.0)
    clauses = [f"se.captured_at < now() - make_interval(hours => {hours:g})"]
    clauses.append("not exists (select 1 from qualified_signals qs "
                   "where qs.org_id = se.org_id and qs.event_id = se.event_id)")
    clauses.append("not exists (select 1 from event_trace t where t.org_id = se.org_id "
                   f"and t.event_id = se.event_id and t.action in "
                   f"({', '.join(repr(a) for a in actions)}))")
    for name in refusals:
        clauses.append(f"not exists (select 1 from {name} l "
                       "where l.org_id = se.org_id and l.event_id = se.event_id)")
    return ("select count(*) from source_events se where " + " and ".join(clauses)
            + _org_filter(org, "se"))


def _MIXED_AUTHORITY_SCALE_SQL(org: str | None) -> str:
    r"""Active `(node, field)` pairs holding BOTH an on-ladder and an off-ladder authority rank.

    ⛔⛔ ATLAS L2-01, LOCATED. The claim is *"incorrect authority configuration would still be
    applied consistently"*, and `graph_facts.authority_rank` is where it lives: a plain integer
    column carrying two scales that were never reconciled.

    * `capture/validate/authority.AUTHORITY_RANK` is a dense ladder, `0..MAX_AUTHORITY_RANK`,
      seven classes, no ties — `inferred` at the bottom and `signed_document` at the top.
    * `context/analytic/publish.DEFAULT_AUTHORITY_RANK` is **100**, and writes the same column of
      the same table (`FACT_TABLE = "graph_facts"`).

    ⛔ AND THE TWO NUMBERS ARE COMPARED WITH NOTHING ELSE. `context/graph_store.fact_write_action`::

        if held_rank is not None and new_rank < held_rank:
            return "discrepancy"       # lower authority disagrees -> flag, keep held
        return "supersede"

    So a held row at 100 can never be superseded, and a `signed_document` arriving against one
    comes back a `discrepancy` and is discarded in favour of the derived value. The ladder's own
    module says why stretching the scale breaks more than this: ALG-12's gap of `>= 2` *"only means
    anything because the ranks here are a dense, evenly-spaced ladder rather than scores."*

    ⛔ WHAT THIS RECEIPT DOES **NOT** ASSERT, because it was measured instead of assumed. No live
    corruption is claimed. `publish_derived_fact` scopes its own lookup by `version_prefix` and so
    never supersedes an observed row, and the observed and derived writers share no literal field
    name anywhere in the engine. ⛔ But `write_fact`'s lookup is NOT prefix-scoped — it takes the
    first active row for `(org, node, field)` whoever wrote it — so the separation rests on two
    field vocabularies never meeting, which nothing enforces, and 31 call sites pass a `field=`
    that could not be resolved statically. **This receipt is the thing that notices the first
    meeting**, which is the moment the hazard becomes a corruption.

    ⛔ THE PREDICATE IS THE READER'S, NOT A FRESH ONE. `valid_to is null and status = 'active'` is
    exactly what `graph_store.write_fact` selects `held` with; asking a different question here
    would measure rows the comparison never sees.

    DERIVED: the ladder's top from `MAX_AUTHORITY_RANK`, and the existence of an off-ladder writer
    from `UNINTERPRETABLE_RANKS`. ⛔ If nothing wrote off-ladder ranks any more this receipt could
    never go red, so that is a refusal rather than a silent pass.
    """
    from genios_engine.capture.validate.authority import (MAX_AUTHORITY_RANK,
                                                          UNINTERPRETABLE_RANKS)

    top = int(MAX_AUTHORITY_RANK)
    off_ladder = sorted(r for r in UNINTERPRETABLE_RANKS if r > top)
    assert off_ladder, (
        "no rank above the ladder's top is declared in `UNINTERPRETABLE_RANKS` any more, so this "
        f"receipt's `authority_rank > {top}` half can never match and it would pass for ever. If "
        "the derived scale folded into the ladder, retire this receipt deliberately")
    return ("select count(*) from (select subject_node_id, field from graph_facts "
            f"where valid_to is null and status = 'active'{_org_filter(org)} "
            "group by subject_node_id, field "
            f"having bool_or(authority_rank <= {top}) and bool_or(authority_rank > {top})) x")


def _CONNECTED_TO_NOTHING_SQL(org: str | None) -> str:
    r"""Live connections to a source that satisfies no coverage capability.

    ⛔ ATLAS L1-01: *"only eight canonical source IDs are buildable… catalogued is not connected."*
    The counting is still true and the registry is honest about it — `BUILDABLE_SOURCES` is a
    DERIVED view over one descriptor per source, `tests/test_source_registry.py` enforces the
    invariants, and `L1.1-U2` exists so the UI renders one answer. ⛔ But measuring it properly
    turned up something the registry does NOT say.

    **`database` and `mysql` are buildable with `capability = None` and `object_types = 0`.** A
    tenant can connect one and it satisfies no pack's coverage and maps no objects — so it
    contributes to nothing, while the connection screen reports a success. That is the exact
    INVERSE of the drift this registry was built to close: its docstring lists sources that
    *"carried a coverage capability but NO family"*, and nobody asked the other direction.

    ⛔ AND THE REGISTRY'S OWN EXAMPLE HAS EXPIRED. It says *"`hubspot` advertises the `crm`
    capability that the `sales` pack REQUIRES, while no connector can be built for it"* — and
    `hubspot` is buildable now. The sentence is still TRUE of eleven other sources (`salesforce`
    is also `crm`), so its shape survived and its subject did not, which is the worst kind of
    stale comment: it reads as a current measurement.

    ⛔ THE LIST IS DERIVED, NEVER SPELLED. A source that gains a capability leaves this query with
    no edit, and one added without a capability enters it the same way. Two refusals, because
    either would make the receipt always-green:

    1. the capability-less set must be NON-EMPTY -- otherwise `in ()` is a query that cannot match;
    2. every member must be `buildable` -- a catalogued-but-unbuildable source with no capability
       is not a finding, because nobody can connect it in the first place.
    """
    from genios_engine.capture.source_registry import BUILDABLE_SOURCES, descriptor_of

    canonical = {descriptor_of(s).source for s in BUILDABLE_SOURCES}
    orphans = sorted(s for s in canonical if descriptor_of(s).capability is None)
    assert orphans, (
        "every buildable source now advertises a coverage capability, so this query would read "
        "`in ()` and pass for ever. ✅ That is the better world -- retire the receipt deliberately")
    for name in orphans:
        d = descriptor_of(name)
        assert d.buildable, (
            f"{name!r} has no capability and is not buildable either, so no tenant can connect it "
            "and it is not what this receipt is about. Re-derive the set")
        assert re.fullmatch(r"[a-z_0-9]+", name), name
    listed = ", ".join(f"'{name}'" for name in orphans)
    return ("select count(*) from connections c "
            f"where c.status = 'connected' and c.source_type in ({listed})"
            f"{_org_filter(org, 'c')}")


def _UNSCOPED_COVERAGE_VERDICT_SQL(org: str | None) -> str:
    r"""Recently qualified signals carrying no coverage verdict at all.

    ⛔ ATLAS L1-09: *"the coverage snapshot is not mandatory on each emitted signal."* True --
    `GatedEvent.coverage_ready` is `bool | None = None` and `qualified_signals.coverage_ready` is a
    nullable boolean. ⛔ But the shape is not the finding; the CONTRACT'S OWN PROMISE is, because
    it says this about the field one along and nothing checks it:

        `None` means no tagger ran (a pre-S4 row); A FRESHLY GATED EVENT ALWAYS CARRIES A REAL BOOL.

    and about `coverage_ready` itself:

        A dead field on a contract is worse than a missing one: it invites a consumer to trust a
        seam that carries nothing, and `None` READS AS "UNKNOWN" EXACTLY WHERE A CALLER MOST WANTS
        A YES.

    So this receipt asks the promise as a question. ⛔ THE HORIZON IS THE WHOLE DESIGN: the comment
    is explicit that an OLD row is legitimately null (*"a pre-S4 row"*), so counting every null
    would make this red for ever and tell nobody anything. The window is **4 sweep ticks**, derived
    from `sync_interval_hours` exactly as the unexplained-event receipt derives its own -- the one
    judgement is the multiplier, and four ticks is long enough that a signal written during a
    deploy or a paused sweep is not reported as a defect.

    ⛔ THE ALWAYS-GREEN FAILURE, GUARDED. If `coverage_ready` ever became NOT NULL in the schema or
    required on the contract, this query could not return a row and would pass while measuring
    nothing. The contract side is asserted here; the schema side is asserted by the guard suite,
    which reads the migration.
    """
    from genios_engine.contracts.gated_event import GatedEvent
    from genios_engine.platform.config import get_settings

    field = GatedEvent.model_fields.get("coverage_ready")
    assert field is not None, (
        "`GatedEvent.coverage_ready` is gone, and this receipt measures the column it feeds. "
        "Find out what replaced it before trusting the query")
    assert field.is_required() is False, (
        "`GatedEvent.coverage_ready` is now REQUIRED, so a gated event cannot be built without a "
        "verdict and this receipt can only ever return 0. ✅ That is the better world -- retire the "
        "receipt deliberately rather than letting it go green by itself")
    hours = 4 * float(get_settings().sync_interval_hours or 6.0)
    return ("select count(*) from qualified_signals qs where qs.coverage_ready is null "
            f"and qs.created_at > now() - make_interval(hours => {hours:g})"
            f"{_org_filter(org, 'qs')}")


def _MULTI_DOMAIN_ROUTED_PACKAGE_SQL(org: str | None) -> str:
    r"""Published expertise packages whose route selected SEVERAL business domains.

    ⛔ WHY THIS IS NOT A STYLE COMPLAINT ABOUT AN INDEX. `reason/adapters/expertise.py` reaches into
    the package's own metadata and takes the first entry::

        domain_ids = package.metadata.get("domain_ids") or ()
        domain = str(domain_ids[0]) if domain_ids else "general"

    That value becomes `CapabilityManifest.domain`, and `reason/domain_shadow.py` uses that field to
    SELECT THE TENANT PACK the reasoning then reads::

        if manifest.domain not in packs:
            packs[manifest.domain] = _tenant_pack(registry, store, org_id, manifest.domain)

    `reason/runner.py` gates on the same field (`capability.domain == effective["pack_id"]`). So the
    index does not pick a label — it picks the knowledge.

    ⛔⛔ AND THE LIST IS SORTED, WHICH MAKES `[0]` THE ALPHABETICALLY FIRST DOMAIN. `RoutePlan` is
    sealed with `domain_ids=tuple(sorted(selected_domains))` over a `set`, and a situation carrying
    no usable hint resolves against `sorted(self.catalog.domains.keys())` — every authored domain.
    A multi-domain route therefore reasons against whichever pack sorts first alphabetically, and
    **no line anywhere records that a choice was made**. This is Atlas L2-11, *"wrong first domain
    … can still enter the wrong view"*, with its mechanism traced rather than suspected.

    ✅ THE CONTRACT ALREADY OWNS THE ACCESSOR THAT DOES NOT DO THIS. `ExpertisePackage.domain_hints`
    returns every entry, sorted and unique, and `packs/compiler/runtime_brains` consumes it that
    way. The routing site reaches past it into the raw bag.

    ⛔ TWO REFUSALS, BECAUSE EITHER WOULD MAKE THIS RECEIPT ALWAYS-GREEN RATHER THAN CORRECT:

    1. the metadata key is read off `RoutePlan`'s own field names, so a rename is a refusal here
       instead of a query that quietly counts a key nobody writes;
    2. `OBSERVATION_METADATA_KEYS` must NOT contain it. `addressable_metadata` strips that set
       inside `ExpertisePackage.to_semantic_dict`, which is what the publisher stores, so adding
       the key to it would empty this query's column while every test still passed — the
       always-green failure this programme has now hit twice.

    ⛔ RETRACTION, KEPT WHERE THE CLAIM WAS MADE. The first draft of this receipt asserted against
    `ExpertisePackage._NON_CONTENT_METADATA`. **There is no such attribute on this class.**
    `_NON_CONTENT_METADATA` and `address_free_metadata` belong to `SituationCandidate`, several
    hundred lines earlier in the same file, and that object is NOT what the publisher stores. The
    conclusion held — `domain_ids` does survive into the payload — but it held through a different
    filter, and the measurement that nearly went in was of the wrong class. Two `to_semantic_dict`
    methods in one module is enough to make the right-looking name the wrong object.

    DECLARED LIMIT, not an oversight: a `domain_ids` stored as a bare STRING is not counted.
    `domain_hints` tolerates that shape and normalises it to one entry, so it is a single-domain
    route by construction and has nothing to pick between.
    """
    from dataclasses import fields as _fields
    from dataclasses import is_dataclass as _is_dataclass

    from genios_engine.contracts.domain_expertise import OBSERVATION_METADATA_KEYS
    from genios_engine.packs.compiler.models import RoutePlan

    # ⛔ ASKED, NOT ASSUMED. `fields()` raises `TypeError` on a non-dataclass, and a receipt
    # builder that dies with "must be called with a dataclass type or instance" tells the reader
    # nothing about which claim just stopped being checkable.
    assert _is_dataclass(RoutePlan), (
        "`packs.compiler.models.RoutePlan` is no longer a dataclass, so this receipt cannot read "
        "the metadata key off its fields. Re-derive the key before trusting the query")
    plan_fields = {f.name for f in _fields(RoutePlan)}
    key = "domain_ids"
    assert key in plan_fields, (
        f"`RoutePlan` no longer carries a {key!r} field, and `packs/compiler/expertise_builder` "
        f"writes this receipt's metadata key straight from it. Fields today: {sorted(plan_fields)}")
    assert key not in OBSERVATION_METADATA_KEYS, (
        f"{key!r} has joined `OBSERVATION_METADATA_KEYS`, so `addressable_metadata` now strips it "
        "from the payload `ExpertisePackage.to_semantic_dict` hands the publisher. This receipt "
        "would then read an absent column and pass for ever. Either the key moved or the receipt "
        "is obsolete -- decide, do not let it go green by itself")
    path = f"p.payload->'metadata'->'{key}'"
    return ("select count(*) from expertise_packages p "
            f"where p.payload->'metadata' ? '{key}' "
            f"and jsonb_typeof({path}) = 'array' "
            f"and jsonb_array_length({path}) > 1"
            f"{_org_filter(org, 'p')}")


def _PARKED_WITH_A_CHANNEL_SQL() -> str:
    from genios_engine.deliver.routing import AGENT_TRANSPORTS
    from genios_engine.deliver.units import _implemented_channels
    usable = sorted(_implemented_channels() - AGENT_TRANSPORTS)
    literal = ", ".join(f"'{ch}'" for ch in usable) or "''"
    return (
        "select count(*) from delivery_outbox d"
        " where d.status = 'undeliverable'"
        "   and exists (select 1 from org_channels c"
        "                where c.org_id = d.org_id and c.active"
        f"                  and c.channel = d.channel and c.channel in ({literal}))")


def _QUARANTINED_SEAM_SQL(org: str | None) -> str:
    r"""Inputs the learning layer deliberately threw away — its isolation ledger, finally read.

    ⛔ `feedback/store._read_optional_seam` catches a read that raises, records it in
    `learning_input_rejections` and returns `()`. Its own comment states the defect it half-fixed:
    *"`learning_input_rejections` exists (migration 0046) and its own comment calls it 'sanitized
    isolation of a malformed/lineage-less input' — and **nothing in the codebase ever wrote to
    it**. So the layer's isolation ledger recorded nothing, and an input the system deliberately
    quarantined was indistinguishable from one that never arrived. **That is the no-silent-drop
    contract failing in the one place built to uphold it.**"*

    ⛔ The WRITE was then built and the READ never was. This is the read.

    ⛔ THE SEAM FILTER IS NOT OPTIONAL AND IT IS DERIVED. `org_rule_ingest.record_refusal` writes to
    the same table under `seam = "brains.org_discovery"` for every candidate the discovery gate
    turns down — which is **routine, not an alarm**, and is already counted per run in
    `org_rule_discovery_runs.counters` (`candidates`, `admitted`, `refused`, `refused_<reason>`).
    Counting those here would make this receipt red on healthy tenants. The two batch seams come
    from `store.QUARANTINABLE_SEAMS` rather than being spelled again, so a third optional seam
    enters this query without an edit.
    """
    from genios_engine.feedback.store import QUARANTINABLE_SEAMS

    for seam in QUARANTINABLE_SEAMS:
        assert re.fullmatch(r"[a-z_]+", seam), seam
    seams = ", ".join(f"'{s}'" for s in QUARANTINABLE_SEAMS)
    return ("select count(*) from learning_input_rejections j "
            f"where j.seam in ({seams}){_org_filter(org, 'j')}")


def _ILLEGAL_TRANSITION_SQL(org: str | None) -> str:
    r"""Lifecycle edges `learning_transitions` holds that `ALLOWED_LEARNING_TRANSITIONS` forbids.

    ⛔ THE LEGAL SET IS DERIVED FROM THE CONTRACT, NEVER COPIED. A hand-written pair list would
    drift the first time a state is added, and the drift would widen what this receipt accepts —
    the same rule `_UNDECLARED_UNWRITTEN_FACTS_SQL` follows for `expertise._ROSTER`.

    ⛔ `from_state is null` IS EXCLUDED. `publisher.persist` writes the first edge of an object's
    life with no predecessor, and `ALLOWED_LEARNING_TRANSITIONS` has no `None` key by design.

    ⛔ WHAT A NON-ZERO COUNT MEANS TODAY. Until 2026-10-02 `publisher.publish` wrote
    `governed → published` on every brain publish, and `GOVERNED` may only go to
    `(temporary, human_review, promoted, rejected)`. The publisher now logs the missing `promoted`
    hop and `log_transition` refuses an illegal edge — so **new** rows cannot be illegal. Rows
    written before that fix can be, and this receipt does not hide them: it names them. The
    read-only query that settles whether any exist is
    `select from_state, to_state, count(*) from learning_transitions group by 1, 2`, and it answers
    a second question at the same time — whether any brain value has ever been published at all,
    which is what `L7-27` asks.
    """
    from genios_engine.contracts.learning import ALLOWED_LEARNING_TRANSITIONS

    pairs = [(cur.value, nxt.value)
             for cur, nxts in ALLOWED_LEARNING_TRANSITIONS.items() for nxt in nxts]
    # The values come from an Enum, but this builds SQL text, so the shape is asserted rather than
    # assumed — a state named with a quote would otherwise be an injection in a receipt.
    for a, b in pairs:
        assert re.fullmatch(r"[a-z_]+", a) and re.fullmatch(r"[a-z_]+", b), (a, b)
    literal = ", ".join(f"('{a}','{b}')" for a, b in pairs)
    return ("select count(*) from learning_transitions t where t.from_state is not null "
            f"and (t.from_state, t.to_state) not in ({literal})"
            f"{_org_filter(org, 't')}")


#: ⛔ STEP-04 · AN OPEN CARD WHOSE SUBJECT IS THE TENANT ITSELF. Production carried *"Send Mr Rohit
#: Swerashi your traction metrics"* and an offer card naming `ceo@thegenios.com` and the founder as
#: "waiting longest" (`speedrun008/YC-II W27/` STEP-04 §8.2). Who "us" is comes from the same four
#: sources `platform/self_identity.identity_for` reads — the founder's full name and the company's
#: name on `orgs`, its address, the active seats, and what the tenant declared — in SQL, because a
#: receipt is one scalar. A first name alone is not us: another Rohit is somebody else.
_CARD_ABOUT_US_SQL = (
    "select count(*) from cards c where c.state in "
    "('queued', 'surfaced', 'snoozed', 'claimed', 'delivered') "
    "and c.business_subject is not null and ("
    "  exists (select 1 from orgs o "
    # `orgs.name` is the person's FULL name at signup, with or without a title ("Mr Rohit
    # Swerashi"): a subject that holds it, untitled, is about us — "Send Rohit Swerashi your
    # traction metrics". A one-word name only exactly (`platform/self_identity.names_us`).
    "    cross join lateral (select regexp_replace(lower(btrim(coalesce(o.name, ''))), "
    "        '^(mr|mrs|ms|miss|dr|prof|shri|smt)[.]? +', '') as full_name) n "
    "   where o.id = c.org_id and ("
    "      lower(c.business_subject) = lower(o.name) "
    "   or (position(' ' in n.full_name) > 0 "
    "       and lower(c.business_subject) like '%' || n.full_name || '%') "
    "   or (o.first_name is not null and o.last_name is not null "
    "       and lower(c.business_subject) like '%' || lower(o.first_name || ' ' || o.last_name) || '%'))) "
    # Every address and declared domain of ours, from the identity's own SQL correlated per card
    # (`platform/self_identity.identity_sql`) — one list of sources, not a second copy of it that
    # forgot the connected account.
    "  or exists (select 1 from (" + identity_sql("c.org_id") + ") us "
    "      where lower(c.business_subject) like '%' || us.value || '%'))")


def receipts(org: str | None) -> list[Receipt]:
    # THE DORMANCY WINDOW IS THE THRESHOLD, and it is imported rather than restated. L2 decides a
    # situation has ended after `DORMANT_AFTER_DAYS` of silence, so a tenant that has been fed
    # nothing for that long has, provably, no working set left — whatever the other receipts say.
    # Picking any other number here would invent a second opinion about when quiet becomes empty.
    # Imported inside the function, the way `platform/wiring.py` already reaches into `context`.
    from genios_engine.capture.pipeline import (ARCHIVED_PAYLOAD_TTL_DAYS, JUDGED_DROP_CODES,
                                                JUDGED_DROP_PAYLOAD_TTL_DAYS)
    from genios_engine.api.account_routes import RETAINED_AFTER_ERASURE
    from genios_engine.context.runner import MAX_PASSES
    from genios_engine.context.situations import DORMANT_AFTER_DAYS
    from genios_engine.deliver.routing import AGENT_TRANSPORTS
    from genios_engine.deliver.units import _implemented_channels

    # The same intersection `deliver.outbox.deliverable_channels` computes in Python:
    # registered AND implemented AND not an agent transport. Inlined as a literal list so
    # one SQL scalar can answer it, derived from the two sources so it cannot drift from
    # what the drain will actually accept.
    pushable = sorted(_implemented_channels() - set(AGENT_TRANSPORTS))

    o = _org_filter(org)
    return [
        # ── L1 capture ────────────────────────────────────────────────────────────────
        Receipt("L1", "no sync cursor is ahead of the clock",
                f"select count(*) from sync_cursors where watermark > now(){o}",
                lambda n: n == 0,
                "a future watermark asks the provider for changes since a date that has not "
                "happened; the connector goes silent while still reporting success"),
        # ⛔⛔ THE WORST SHAPE OF SILENT STOP IN THE PRODUCT: the health check does not merely
        # miss these rows, `warm_lane._OPEN` excludes them by construction, so a lane with a
        # hundred parked rows and none open reports a clean backlog.
        Receipt("L1", "no warm-lane row is parked where nothing can see it",
                _PARKED_WARM_LANE_SQL(org), lambda n: n == 0,
                "⛔ `migrations/0136_warm_lane.sql` comments the column: *\"attempts ran out: "
                "parked for a human, never retried.\"* Nothing selects a parked row — "
                "`warm_lane._OPEN`, `api/routes`'s backlog count and `housekeep`'s staleness "
                "warning all exclude it, and the hourly prune removes only finished rows. A "
                "non-zero count is a tenant whose events stopped being processed, permanently and "
                "invisibly. ⛔ The predicate is DERIVED from `warm_lane._OPEN`, so it cannot drift "
                "from the lane's own definition of open. Same claim L1 already makes for "
                "`parked_events` — *\"the parked queue is not a black hole\"*"),
        Receipt("L1", "the parked queue is not a black hole",
                f"select count(*) from parked_events where status='pending'{o}",
                lambda n: n == 0,
                "pending forever means a park is a slower delete"),
        # ⛔⛔ `capture/journey.py` EXISTS FOR THIS SENTENCE — *"a system that discards 92% of
        # what a founder was sent has to be able to answer 'why did I never see X?' in one query"* —
        # and the module records that the join was missing while every layer wrote its own refusal
        # down. This checks that every event HAS an answer, which `journey` can then render.
        Receipt("L1", "every captured event that reached no signal says where it stopped",
                _UNEXPLAINED_EVENT_SQL(org), lambda n: n == 0,
                "⛔ A non-zero count is a founder's question with no answer: captured, four sweeps "
                "past, no signal produced, and no layer recorded what stopped it. ⛔ The stopping "
                "actions come from `journey.TRACE_STOPPING` and the event-keyed ledgers from "
                "`journey._LEDGERS` minus `_PER_SIGNAL_LEDGERS` — a per-signal refusal cannot name "
                "an event that never produced a signal. The horizon is four ticks of "
                "`config.sync_interval_hours`, so an event mid-flight is never counted. Walk one "
                "with `journey.event_journey(engine, org_id=..., event_id=...)`"),
        Receipt("L1", "every drop we might be wrong about can still be reviewed",
                # SCOPED TO THE JUDGED DROPS, and that is a correction rather than a narrowing.
                # Asked of EVERY drop this counted 2,818 deterministic refusals that by documented
                # policy retain nothing — "L1 stays a filter, not a warehouse" — so it could never
                # pass, on any tenant, in any state. A receipt that cannot pass is exactly the
                # "a skip read as a pass" failure this module exists to end, wearing the other
                # colour: permanent red teaches an operator to stop reading the page.
                #
                # The window is the retention policy's own, so a judged drop past its TTL is
                # EXPECTED to have no payload and does not count against the tenant. That also
                # means the receipt self-clears: 26 events judged in August, before this retention
                # landed, fail it today and stop counting when they age past 90 days.
                "select count(*) from source_events se where se.outcome='dropped' "
                f"and se.captured_at > now() - interval '{JUDGED_DROP_PAYLOAD_TTL_DAYS} days' "
                "and exists (select 1 from event_trace t where t.org_id=se.org_id "
                "            and t.event_id=se.event_id and t.action='drop' "
                f"            and t.reason_code in ({', '.join(repr(c) for c in sorted(JUDGED_DROP_CODES))})) "
                "and not exists (select 1 from raw_payloads rp where rp.event_id=se.event_id "
                "                and rp.org_id=se.org_id)"
                + _org_filter(org, "se"),
                lambda n: n == 0,
                "a provider's SPAM label is a fact and needs no second look; a model saying "
                "\"this looks like junk\" is a JUDGMENT, and judgments improve. Without the body "
                "\"we improved the filter\" is an assertion about mail that no longer exists. "
                "⛔ Since STEP-03 the gate no longer drops on judgment — it archives — so this asks "
                "only about drops written before the deploy, and clears itself as they age out; "
                "the archive has its own receipt below"),
        # ⛔⛔ STEP-03 · THE GATE'S PROMISE, HELD. The gate ARCHIVES what a noise rule or the AI
        # filter calls noise — 258 of the design partner's 395 mails were deleted before it — and
        # an archive is worth exactly as much as its body: Boardy's introduction to an angel, a
        # government portal's update, read the day they turn out to matter. An archived row with
        # no body is a deletion that says it is not one. EVERY archived mail is asked about,
        # whichever rule or judgment stopped it — unlike the judged-drop receipt above, there is
        # no class of archive that is designed to keep nothing — inside the archive's own window,
        # so one past `ARCHIVED_PAYLOAD_TTL_DAYS` is expected to have none.
        Receipt("L1", "every archived mail can still be read",
                "select count(*) from source_events se where se.outcome = 'archived' "
                f"and se.captured_at > now() - interval '{ARCHIVED_PAYLOAD_TTL_DAYS} days' "
                "and not exists (select 1 from raw_payloads rp where rp.event_id=se.event_id "
                "                and rp.org_id=se.org_id)"
                + _org_filter(org, "se"),
                lambda n: n == 0,
                "the gate keeps what it used to delete — encrypted, read by no model — so the mail "
                "can be read when it turns out to matter. A non-zero count is archived mail whose "
                "body is gone inside its window: a capture door with no payload store, or a purge "
                "that ignored the archive's clock. Walk one with `journey.event_journey`"),
        Receipt("L1", "the tenant is still being fed",
                # `captured_at`, not `occurred_at`: this asks whether OUR pipeline is receiving,
                # and a backfill of last quarter's mail is healthy ingestion of old messages.
                # `coalesce` makes an org with no events at all FAIL rather than return NULL —
                # a tenant nothing has ever arrived for is the loudest version of this failure,
                # and a NULL that slipped through `expect` as falsey would report it as a pass.
                "select coalesce(extract(day from (now() - max(captured_at)))::int, "
                f"{DORMANT_AFTER_DAYS}) from source_events where true{o}",
                lambda days: int(days) < DORMANT_AFTER_DAYS,
                "every other receipt can pass while a tenant's feed is dead: the graph, the packs "
                "and the cards are all still there. What empties is the WORKING SET — L2 marks a "
                f"situation dormant after {DORMANT_AFTER_DAYS} days of silence, so a feed quiet "
                "that long leaves nothing active to reason about, and nothing else says so"),
        Receipt("L1", "attachments carry readable text",
                "select count(*) from document_jobs where status in ('unsupported','fetch_failed')"
                + _org_filter(org),
                lambda n: n == 0,
                "in a fundraising inbox the deck and the rubric ARE the content"),

        Receipt("L1", "a deleted tenant leaves nothing behind",
                # ASKED OF THE DEPLOYED SCHEMA, because that is where the answer lives. Erasure
                # deletes the `orgs` row and migration 0033's foreign keys take everything that
                # hangs off it — directly, or through a parent that does, which is how the four
                # `reasoning_*` children go without any of them being named. So the question is
                # not "is this table in a list" but "is it reachable from `orgs` by CASCADE", and
                # a recursive walk of the constraint graph is the only honest way to ask it.
                #
                # `_ORG_SCOPED_TABLES`'s own comment names the failure this catches: "a name
                # missing here leaks silently". A table added next month with an `org_id` and no
                # foreign key is a deletion request that quietly stops being complete, and
                # nothing anywhere would have said so. Measured 2026-09-17: 178 org-scoped
                # tables, 0 unreachable.
                "with recursive fk(child, parent) as ("
                "  select tc.table_name, ccu.table_name"
                "    from information_schema.table_constraints tc"
                "    join information_schema.referential_constraints rc"
                "      on rc.constraint_name = tc.constraint_name"
                "    join information_schema.constraint_column_usage ccu"
                "      on ccu.constraint_name = tc.constraint_name"
                "   where tc.constraint_type = 'FOREIGN KEY' and rc.delete_rule = 'CASCADE'), "
                "reachable(tbl) as ("
                "  select child from fk where parent = 'orgs' "
                "  union select f.child from fk f join reachable r on r.tbl = f.parent) "
                "select count(*) from information_schema.columns c "
                "  join information_schema.tables t"
                "    on t.table_name = c.table_name and t.table_schema = c.table_schema "
                " where c.table_schema = 'public' and c.column_name = 'org_id' "
                "   and t.table_type = 'BASE TABLE' "
                f"   and c.table_name not in ({', '.join(repr(x) for x in sorted(RETAINED_AFTER_ERASURE))}) "
                "   and c.table_name not in (select tbl from reachable)",
                lambda n: n == 0,
                "every table left over holds a deleted customer's data under an org_id that "
                "resolves to nobody — the three retained financial ledgers are named in "
                "`RETAINED_AFTER_ERASURE` and are the only rows permitted to outlive a tenant",
                # THE SCHEMA IS SHARED, so this answer cannot differ per tenant. Declared, not
                # inferred from the absent filter — see `Receipt.fleet_wide`.
                fleet_wide=True),

        # ── L2 context ────────────────────────────────────────────────────────────────
        Receipt("L2", "the tenant's own identities are known",
                f"select count(*) from org_seats where active{o}",
                lambda n: n > 0,
                "org_seats empty ⇒ internal_emails is empty ⇒ every self-filter is a no-op and "
                "the org models its own founder as a counterparty"),
        Receipt("L2", "no person node holds thread state fed by several threads",
                "select count(*) from (select f.subject_node_id from graph_facts f "
                "where f.field='thread.ball_in_court' and f.valid_to is null"
                + _org_filter(org, "f") +
                " group by f.subject_node_id having count(*) > 1) t",
                lambda n: n == 0,
                "one last-write-wins row per person collapses every conversation into the newest"),

        # ⛔⛔ `context/`'s THIRD receipt, and the first about the operation that rewrites
        # identity. 50,877 lines and 124 files had two receipts, neither covering entity merge —
        # the one place where a missed table leaves live rows naming a node that no longer exists.
        Receipt("L2", "no live row points at a node a merge absorbed",
                _ABSORBED_NODE_REFERENCE_SQL(org), lambda n: n == 0,
                "⛔ `context/merge.py` says it itself: *\"Missing one leaves rows pointing at a "
                "closed node — invisible in the UI, still returned by any query that joins on "
                "node_id.\"* The table/column pairs are DERIVED from `_NODE_REFERENCES`, "
                "`_CORRELATION_HANDLED_SEPARATELY` and `_EDGE_NODE_COLUMNS`, so a sixth table "
                "entering the merge loop enters this check without an edit. Reversed merges are "
                "excluded — `reverse_merge` legitimately repoints those rows back"),
        Receipt("L2", "the sweep settles instead of chasing itself",
                # `_record_convergence` re-hashes the graph after a pass and counts how many it
                # took to stop moving; at `MAX_PASSES` it stamps `exceeded_at` and raises
                # `l2_convergence_exceeded` with the situation ids still changing. That alert is
                # a LOG LINE — greppable by an operator already looking, invisible to one who is
                # not. The stamp is in a table, so it can be asked instead.
                #
                # Measured 2026-09-17: three orgs, `exceeded_at` null on all three and `passes`
                # zero — the hash settles on the first pass every time. Two clean sweeps were
                # called evidence rather than proof, which was right; this is what turns "we
                # watched it twice" into something that stays watched.
                f"select count(*) from l2_convergence where exceeded_at is not null{o}",
                lambda n: n == 0,
                f"a sweep that never settles re-derives the same situations up to {MAX_PASSES} "
                "times and then gives up mid-pass, so the tenant's picture is whatever the last "
                "partial pass left — and `detail` names the situations that were still moving"),

        # ── L3 domain expertise ───────────────────────────────────────────────────────
        Receipt("L3", "compiled expertise packages exist",
                f"select count(*) from expertise_packages where 1=1{o}",
                lambda n: n > 0,
                "zero packages ⇒ the compiler is dark or every situation abstains"),
        Receipt("L3", "the tenant is bound to a pack",
                f"select count(*) from tenant_packs where state='active'{o}",
                lambda n: n > 0),

        # ── L4 executive · ORGANISATION DATA ──────────────────────────────────────────
        #
        # ⛔ WHY THESE THREE ARE NEW. Twenty-three receipts existed and NOT ONE was about organisation
        # data. So a tenant with a compiled pack, a live activation row, a full graph and every receipt
        # green could still be completely unroutable — which is the state the pilot is in, and the whole
        # reason `executive/` "examines nothing every tick".
        #
        # `test_a_tenant_nobody_feeds_is_not_ready` made the identical argument one layer down: *"Every
        # other receipt can pass while a tenant's feed is dead. ... seventeen receipts still say PASS.
        # Nothing said the feed had stopped."* This is that failure one layer up.
        #
        # The SQL is imported from `executive/readiness.COUNT_SQL` rather than retyped, so the receipt
        # and the readiness page cannot drift about what "ready" means — the same rule this module's own
        # docstring states: *"One list of claims, two surfaces."*
        #
        # ⛔ ORG-FILTERED, ALWAYS. Every one of these is a question about a TENANT, so none may be
        # `fleet_wide`: answering it unfiltered would report one tenant's seats on another's page.
        Receipt("L4", "the tenant has at least one active seat",
                _RD_SQL[_RD.SEATS] if org else _RD_SQL_FLEET[_RD.SEATS],
                lambda n: n > 0,
                "no active seat means nobody to assign an owner to, so every execution plan is "
                "refused before it is written"),
        Receipt("L4", "at least one seat has a manager",
                _RD_SQL[_RD.REPORTING_LINE] if org else _RD_SQL_FLEET[_RD.REPORTING_LINE],
                lambda n: n > 0,
                "with no reporting line, rung 7 of the ladder (escalate -> manager) climbs into "
                "nothing and a stalled item is never escalated"),
        # ⛔ ACTIVATED IS NOT THE SAME AS RAN. `platform/l3_activation` shipped once with a reader, a
        # fail-closed gate, an erasure row, an admin API and a report -- AND NO CALLER. The lesson
        # Plane R recorded from it: *"a switch that reports itself on and changes nothing is worse than
        # no switch."*
        #
        # `reasoning_runs.mode` already answers this exactly: `domain_shadow` writes
        # `ExecutionMode.LIVE if live_row else ExecutionMode.SHADOW`, and only the live lane reaches
        # `_persist_live`. So a tenant with an activation row and zero live runs has a switch that is on
        # and doing nothing -- which is precisely the state this receipt exists to make visible.
        Receipt("L4", "the live pass has actually run, not only the shadow pass",
                "select count(*) from reasoning_runs where mode = 'live'" + _org_filter(org),
                lambda n: n > 0,
                "an activation row with no live run means the switch reports itself on and changes "
                "nothing -- the exact defect l3_activation shipped with once"),

        # ⛔ L2 · EVERY REASONING UNIT THAT SAYS NOTHING IS ONE WE DECLARED.
        #
        # Measured 2026-10-01: `core.impact` completes 1,973 times with 100% silent output
        # (`{"impact_signal_count": 0}`) and `core.opportunity` 94%. Both succeed. Both compute
        # nothing. Every reader downstream treats the absence as "no signal here" rather than "this
        # unit had nothing to read" — and `core.tradeoff`'s `cost_vs_benefit` axis has fired 0 times
        # in 1,200 rows as a direct result, while a unit test proves the axis works on a prior the
        # test supplies itself.
        #
        # ⛔ THE CLAIM IS NOT "NO UNIT IS SILENT", AND THAT CHOICE IS THE WHOLE DESIGN.
        # `api/routes.py:161` computes `ready = not failed` from this list, and it is what the
        # release gate runs. Asserting "no unit is silent" would be PERMANENTLY RED for an upstream
        # reason this layer cannot clear — `deal.status` has no writer — and a gate that is always
        # red is a gate nobody reads. So the claim is the one that is true today and false the moment
        # it gets worse: every silent unit is a DECLARED one, with a reason and a mover.
        #
        # ⛔ AND THE SILENCE TEST IS IMPORTED, NOT RESTATED HERE. `reason/unit_health.SILENT_SQL` is
        # the same rule the probe applies in Python, and a test runs both over the same production
        # rows — because two expressions of one rule that are never compared eventually disagree.
        Receipt("L2", "every reasoning unit that says nothing is one we declared",
                _UNDECLARED_SILENT_UNITS_SQL(org),
                lambda n: n == 0,
                "a unit that completes and computes nothing is read downstream as 'no signal here' "
                "rather than 'nothing to read' -- declare it in reason/unit_health with a reason and "
                "a mover, or find out why it went quiet"),

        # ⛔ L2 · A UNIT THAT RUNS AND NEVER COMPLETES IS DECLARED, OR IT IS INVISIBLE.
        #
        # The silence receipt above asks whether COMPLETIONS said anything, so it cannot see a unit
        # with no completions -- that unit is not a low row, it is no row. Measured 2026-10-01:
        # `core.relationship`, 929 runs, 0 completions, and the silence receipt green. The fact had
        # been written in prose twice (once below, once inside DECLARED_SILENT["core.impact"]'s own
        # reason) and declared nowhere a receipt could read.
        Receipt("L2", "every unit that runs and never completes is a declared one",
                _UNDECLARED_NEVER_COMPLETED_SQL(org),
                lambda n: n == 0,
                "a unit with runs and zero completions is absent, not quiet, and the silence "
                "receipt cannot see it -- declare it in reason/unit_health.DECLARED_NEVER_COMPLETED "
                "with a reason, a mover and the run count, or find out what stopped it answering. "
                "A unit with no runs at all is a different fact (nobody scheduled it) and belongs "
                "to the roster, not here"),

        # ⛔ L2 · EVERY FACT PATH A UNIT BINDS IS EITHER WRITTEN OR DECLARED UNWRITTEN.
        #
        # Measured 2026-10-01: `expertise._ROSTER` binds 22 fact paths and **14 have zero rows**. One
        # root — there is no CRM connector, so `deal.*` is empty beyond `status` (3 rows) and
        # `last_inbound` (34). `core.policy` has skipped all 165 of its rows because ALL FOUR of its
        # essential fields are in that list: it is not failing, it is correctly refusing to run on
        # nothing, forever.
        #
        # ⛔ AND THIS IS WHAT `no_declared_input_available` CANNOT SAY. That skip reason conflates
        # "this situation did not carry the field" with "nothing has ever written the field anywhere".
        # Different movers; the second is not fixable by looking at the situation at all.
        #
        # ⛔ THE CLAIM IS NOT "no bound path is empty", for the reason the sibling receipt states:
        # `ready = not failed`, and 14 of 22 are empty for a reason this layer cannot clear. This one
        # passes today and fails when a FIFTEENTH goes quiet — which produces no error anywhere else.
        Receipt("L4", "every action that needs sign-off can name who signs",
                _UNATTRIBUTED_APPROVALS_SQL(org),
                lambda n: n == 0,
                "an action carrying requires_approval in an org that holds no in-force authority "
                "rule announces a requirement it can never attribute \u2014 the card says \"this needs "
                "sign-off\" and cannot say whose, and nothing counts how often. Measured "
                "2026-10-01: 410 of 794 actions, against zero authority rules"),
        Receipt("L2", "the current reasoning era selects, not only defers",
                _ERA_SELECTS_NOTHING_SQL(org),
                lambda n: n == 0,
                "a selection rate of exactly zero over runs that had candidates means no signal "
                "is emitted, so no commitment is planned and no card is built \u2014 while the pass "
                "itself keeps running and every other receipt stays green. -1 means the era "
                "produced no runs at all, which is a different sentence and also a failure"),
        Receipt("L2", "every fact path a reasoning unit binds is written or declared unwritten",
                _UNDECLARED_UNWRITTEN_FACTS_SQL(org),
                lambda n: n == 0,
                "a bound fact path with no writer means a unit role that can never bind -- declare "
                "it in reason/unit_health with a reason and a mover, or find out what stopped "
                "writing it"),

        # ⛔⛔ L2 · TWO AUTHORITY SCALES SHARE ONE COLUMN, AND THE COLUMN DECIDES WHO WINS.
        #
        # Atlas L2-01, located. The ladder is 0..6 and `context/analytic/publish` stamps 100 into
        # the same `graph_facts.authority_rank`. `fact_write_action` compares the raw integers, so
        # a row at 100 is unsupersedable and a signed document arriving against one is returned a
        # `discrepancy` and dropped. ⛔ Measured as NOT firing today — the two writers share no
        # literal field name and the derived writer is prefix-scoped — so this receipt is the
        # thing that notices the first time they meet.
        Receipt("L2", "no fact holds two authority scales at once",
                _MIXED_AUTHORITY_SCALE_SQL(org),
                lambda n: n == 0,
                "a (node, field) carrying both an on-ladder rank and the off-ladder derived rank "
                "is one where fact_write_action compares incomparable numbers -- fold the derived "
                "scale into the ladder, or prefix-scope write_fact's lookup the way "
                "publish_derived_fact's already is"),

        # ⛔ L1 · NOBODY IS CONNECTED TO A SOURCE THAT FEEDS NOTHING.
        #
        # Atlas L1-01, measured properly. `database` and `mysql` are BUILDABLE with no coverage
        # capability and no object mappings, so a tenant can connect one, see a success, and
        # contribute to no pack's readiness. The set is derived from the registry.
        Receipt("L1", "no live connection feeds a source that satisfies no capability",
                _CONNECTED_TO_NOTHING_SQL(org),
                lambda n: n == 0,
                "a connected source with no coverage capability and no object mappings reports "
                "success on the connect screen and feeds nothing -- give it a capability, or stop "
                "offering it as buildable"),

        # ⛔ L1 · A FRESHLY QUALIFIED SIGNAL SAYS WHETHER ITS DOMAINS WERE COVERED.
        #
        # Atlas L1-09. The contract promises it in writing -- "a freshly gated event always carries
        # a real bool" -- and nothing checked it. ⛔ The horizon is four sweep ticks because the
        # same comment says an OLD row is legitimately null, so counting every null would make
        # this red for ever.
        Receipt("L1", "every recently qualified signal carries a coverage verdict",
                _UNSCOPED_COVERAGE_VERDICT_SQL(org),
                lambda n: n == 0,
                "a signal with coverage_ready null inside the sweep window means the domain "
                "tagger did not run for it -- and None reads as 'unknown' exactly where L3 most "
                "wants a yes, so it compiles full expertise over domains nobody vouched for"),

        # ⛔⛔ L2 · A MULTI-DOMAIN ROUTE PICKS ONE PACK ALPHABETICALLY AND SAYS SO NOWHERE.
        #
        # Atlas L2-11, located. `reason/adapters/expertise.py` takes `domain_ids[0]` out of the
        # package metadata; that becomes `CapabilityManifest.domain`; and `domain_shadow.py` uses
        # that field to pick which TENANT PACK the reasoning reads. The list arrives
        # `tuple(sorted(...))` out of a set, so the index selects the alphabetically first domain
        # and nothing records that several were available.
        #
        # ⛔ The receipt is labelled L2 and the table is L3's (`0047_l3_domain_compiler.sql`). The
        # CLAIM is about the pick, which is Layer 2's; the storage is where the evidence happens to
        # live. Said out loud because this programme has already paid once for two vocabularies
        # sharing one field.
        Receipt("L2", "no published reasoning package was routed by picking one of several domains",
                _MULTI_DOMAIN_ROUTED_PACKAGE_SQL(org),
                lambda n: n == 0,
                "a package whose route selected several domains reasoned against whichever pack "
                "sorts first alphabetically -- use ExpertisePackage.domain_hints, which returns "
                "them all, or record the choice where a reader can see it"),

        # ⛔ L5 · EVERY DELIVERED CARD SAYS WHICH KIND OF OUTPUT IT IS, OR SAYS IT WAS NEVER ROUTED.
        #
        # `0190` made `cards.output_lane` nullable so the migration could land on a live table, and
        # a nullable column with no reader is how "built, tested, green, called by nothing" happens
        # — which is the defect this whole lane vocabulary was added to end, and which the lane
        # vocabulary then reproduced for one step. A NULL here means a card written by a path that
        # does not carry a lane at all; `unrouted` means the delivery layer looked and found nothing
        # it could honour, which is an answer and passes.
        Receipt("L5", "every delivered card carries a lane, or is labelled unrouted",
                "select count(*) from cards where output_lane is null" + _org_filter(org),
                lambda n: n == 0,
                "a card with no lane at all was written by a path that never read the signal's "
                "routing -- the founder cannot tell a decision from a thing to watch"),

        Receipt("L5", "no open card's subject is one of us",
                _CARD_ABOUT_US_SQL + _org_filter(org, "c"),
                lambda n: n == 0,
                "a card's subject is the counterparty, always — one about the tenant tells the "
                "founder to act on himself (\"Send Mr Rohit Swerashi your traction metrics\"). A "
                "non-zero count after STEP-04's repair is a card built by a path that does not ask "
                "`platform/self_identity`; read its `business_subject` and its signal's subject node"),

        Receipt("L5", "no card outlives its own window in a live state",
                _CARD_OUTLIVED_ITS_WINDOW_SQL + _org_filter(org),
                lambda n: n == 0,
                "a card still queued twelve hours past `expires_at` is one a founder may act on and "
                "one L6 will never count -- `CardStore.sweep_lifecycle` expires them and logs "
                "`window.lapsed`, so a non-zero here means that sweep is not reaching this org"),

        Receipt("L5", "a card parked for want of a channel is revived when one appears",
                _PARKED_WITH_A_CHANNEL_SQL() + _org_filter(org, alias="d"),
                lambda n: n == 0,
                "this org has an active, adapter-backed channel AND rows still parked as "
                "undeliverable on that same channel -- `outbox.revive_undeliverable` exists to "
                "re-open exactly these, and `api/channel_routes.set_slack` calls it on "
                "registration, so a non-zero here is a backlog that predates that wiring"),

        Receipt("L5", "no delivery attempt is left unsettled long enough to be ambiguous",
                _UNSETTLED_ATTEMPT_SQL + _org_filter(org, alias="a"),
                lambda n: n == 0,
                "an attempt that said `started` an hour ago and never settled may already have "
                "reached a provider -- retrying over it sends the same thing twice, and "
                "`spine.recover_expired_claims` is the function that exists to mark it `unknown` "
                "first. Nothing calls it, because the v2 control plane is not cut over; this goes "
                "non-zero the first time it is"),

        # ⛔ NO CHANNEL RECEIPT HERE, DELIBERATELY. One already exists further down — *"there is a
        # channel this tenant can be reached on"*, over the same `org_channels` table. Adding a second
        # would be two receipts answering one question, and the first time somebody tuned one they
        # would disagree. `executive/readiness.py` still reports channels, because the readiness page
        # needs all three requirements in ONE verdict with a named fix — that is the other surface this
        # module's docstring names, not a duplicate claim.

        # ── L4 reasoning ──────────────────────────────────────────────────────────────
        Receipt("L4", "more than one candidate is ever considered",
                "select coalesce(max(c), 0) from (select count(*) as c from reasoning_candidates"
                + (" where org_id = :org" if org else "") +
                " group by run_id) t",
                lambda n: n > 1,
                "exactly one candidate per run means no alternative, no do-nothing, no ranking"),
        Receipt("L4", "the score components the scorer writes NOW are measured, not placeholders",
                _PLACEHOLDER_COMPONENTS_SQL(org),
                lambda n: n == 0,
                "a candidate whose impact, risk and effort are all the 5000 neutral default was "
                "ranked by nothing -- every reasoning unit that adjusts those components was a "
                "no-op on it. This happened: 59 rows on one org, and 53 of them carried ALL FIVE "
                "of guards.CANDIDATE_COMPONENTS at 5000. It was closed on 2026-09-08 by 75096bab "
                "and 34,167 candidates have been clean since, so the question is dated at that "
                "boundary -- declared in reason/unit_health.CLOSED_DEFECTS, which also records "
                "why the history cannot be repaired. A hit here means the defect returned"),
        Receipt("L4", "the system has abstained at least once",
                "select count(*) from reasoning_run_outputs where outcome_kind <> 'decision'"
                + _org_filter(org),
                lambda n: n > 0,
                "a reasoner that has never once said 'I don't know' is not exercising a "
                "confidence floor — DEFER is unreachable when confidence_floor_bp defaults to 0"),

        # ── L5 executive ──────────────────────────────────────────────────────────────
        Receipt("L5", "decisions become tracked commitments",
                f"select count(*) from executions where 1=1{o}",
                lambda n: n > 0,
                "zero executions ⇒ every recommendation stops at a card; nothing is ever owed, "
                "chased, escalated or closed"),

        # ── L6 delivery ───────────────────────────────────────────────────────────────
        Receipt("L6", "cards distinguish a warning from an order",
                f"select count(distinct level) from cards where 1=1{o}",
                lambda n: n > 1,
                "one distinct level across every card means the pack's predictive rules are "
                "rendered as direct commands"),
        # ⛔ REWRITTEN 2026-10-01. It asked `render_mode <> 'llm'` and expected zero, which was wrong
        # in BOTH directions. Measured on production:
        #
        #     llm        105 cards,  13 with an empty artifact body
        #     raw_slot    59 cards,  24 with an empty artifact body
        #     template     1 card,    1
        #
        #   (1) it COUNTED 35 `raw_slot` cards that do have a body. A deterministic fallback carrying
        #       real content is the designed behaviour when the model refuses or the validator rejects
        #       — not a stub — so `expect n == 0` made that fallback a permanent failure.
        #   (2) it MISSED 13 `llm` cards with an empty body, which by this receipt's own detail ARE
        #       "a card with no content".
        #
        # ⛔ AND THE HONEST QUESTION IS NARROWER STILL. Of the 38 empty-body cards, 19 ABSTAINED — 13
        # `review` and 6 `observation` — and an abstained card is SUPPOSED to carry no draft:
        # `card_builder` strips `run_play` and `render.py` sets `art = ""` when the artifact is
        # rejected. Demanding a body from those 19 would demand a draft the engine deliberately
        # refused to write.
        #
        # What is left is the thing the claim always meant: a card with no content that is
        # nonetheless giving an order. Measured: 18, so this receipt still FAILS. ⛔ A receipt is not
        # fixed by making it green.
        #
        # `level in ('prescriptive','predictive')` is `abstention.ACTIONABLE`, and a NULL level is
        # EXCLUDED rather than assumed — the rule `calibrate._PRECISION_SQL` already states: *"a card
        # whose level nobody recorded is ungradeable, and defaulting it to 'instruction' is how the
        # old behaviour comes back."*
        #
        # Both conditions, not either: a card can be downgraded by level with no abstention reason
        # (one such card exists), and a reason without a downgrade is a contradiction the card layer
        # does not produce.
        Receipt("L6", "no card gives an order with an empty draft",
                "select count(*) from cards "
                "where coalesce(artifact->>'body', '') = '' "
                "  and abstained_because is null "
                "  and level in ('prescriptive', 'predictive')" + _org_filter(org),
                lambda n: n == 0,
                "a card at an instructing level with no artifact body tells the reader to act and "
                "gives them nothing to act with -- an ABSTAINED card correctly carries no draft and "
                "is excluded"),
        Receipt("L6", "there is a channel this tenant can be reached on",
                # THE PRECONDITION, ASKED FIRST. Measured 2026-09-17: all three orgs register
                # `in_app` and nothing else, and `in_app` is the PULL surface — the card is
                # already sitting on it, there is nothing to send. So the intersection is empty,
                # `deliverable_channels` correctly returns [], and every push receipt below it
                # fails for a reason that has nothing to do with the pipeline.
                "select count(*) from org_channels where active "
                f"and channel in ({', '.join(repr(c) for c in pushable)})" + o,
                lambda n: n > 0,
                "a tenant with no push channel is not a broken pipeline and must not read as "
                "one: nothing is wrong upstream, there is simply nowhere to send"),
        Receipt("L6", "the delivery control plane has run",
                f"select count(*) from delivery_outbox where 1=1{o}",
                lambda n: n > 0,
                # The old detail here read "push is gated on a band the scoring formula cannot
                # reach". That was true when it was written and is now false, and a receipt whose
                # detail names the wrong cause sends an operator to rewrite a scoring formula
                # when the answer is "connect a channel". Measured 2026-09-17: 71 of 133 cards
                # sit at high or critical, and 21 pass PUSHABLE_CARDS_SQL — the authority
                # predicate included — at this instant.
                "cards clear the push band and pass the authority predicate; check the channel "
                "receipt above first, because an empty outbox on a tenant with no channel is "
                "the expected state and not a failure of this layer"),

        # ── L7 learning ───────────────────────────────────────────────────────────────
        Receipt("L7", "the learning engine has executed",
                f"select count(*) from learning_runs where 1=1{o}",
                lambda n: n > 0),
        # ⛔ `feedback/`'s FIRST CORRECTNESS RECEIPT. Measured 2026-10-02: the layer had four
        # receipts and all four were PRESENCE checks — "has the learning engine executed", "has
        # calibration executed" — every one satisfied by a single successful tick. A loop that runs
        # weekly and writes four append-only ledgers could be entirely wrong and pass all four.
        #
        # ⛔ WHY THIS CLAIM AND NOT "THE LOOP DROPPED NOTHING". `learning_event_inbox` (0046) is
        # written in production by `reason/moments/store.record_feedback` (reached from
        # `api/moment_routes.py:746`), loaded into every weekly batch by `feedback/store`, and
        # **no unit consumes it** — `orchestrator.run_learning` counts the rows it is about to drop
        # as `inbox_unconsumed`. So `inbox_unconsumed > 0` is the KNOWN state of a declared gap,
        # and this file's own rule applies: *a gate that is always red is a gate nobody reads; the
        # claim is the one that is true today and false when it gets worse.*
        #
        # ⛔ SO THE CLAIM GUARDS THE VISIBILITY. The counter is the only thing that will make the
        # arrival of a consumer — or the arrival of a second writer — discoverable, and until now
        # it was written into `learning_runs.counts` and read by nothing. Delete the counter, or
        # complete a run without it, and this goes red. **The reader is half the unit.**
        Receipt("L7", "no completed learning run hides whether it dropped inbox rows",
                "select count(*) from learning_runs where status = 'completed' "
                f"and counts->>'inbox_unconsumed' is null{o}",
                lambda n: n == 0,
                "⛔ `learning_event_inbox` rows are written, loaded into every batch and consumed "
                "by nothing: `unit_preference_learning` and `unit_temporary_memory` both return "
                "`[]`. `inbox_unconsumed` in `learning_runs.counts` is how many were dropped, and "
                "this receipt is its first reader. A non-zero count is the DECLARED gap (Atlas "
                "Layer 7 #1); a MISSING count is a regression in the only thing that makes the gap "
                "visible"),
        # ⛔⛔ THE NO-SILENT-DROP CONTRACT, which the Atlas states in full: *"Every rejected or
        # deferred candidate must retain run_id, tenant, unit, evidence IDs, REASON CODE, failed
        # gate, policy version, timestamp, and recovery status … A weekly sweep that returns zero
        # objects without this accounting is operationally indistinguishable from broken wiring."*
        #
        # ⛔ Until 2026-10-02 `run_learning` discarded all three refusal reasons — `ok, _ =
        # validate_learning(...)`, and only `.ok` / `.rejected` read off the gate and the decision
        # — so a refused proposal was COUNTED and never NAMED, and
        # `learning_object_evaluations` recorded only the successes. `migrations/0046` describes
        # that ledger as *"every actual per-run decision (new or HELD object)"*: the held case is
        # named in the schema's own comment and was never written.
        #
        # ⛔ WHY IT IS GATED ON `counts->>'evaluations'`. A run completed before that change has
        # `held`/`refused` above zero and no evaluation rows, so an ungated claim would be red for
        # history it could not have recorded — *a gate that is always red is a gate nobody reads.*
        # The key's PRESENCE is the marker that the run executed under the contract.
        #
        # ⛔ AND THE PRECEDENT IS IN `run_learning` ITSELF: its `published` counter once disagreed
        # with this ledger inside one transaction, and the comment there records why that mattered
        # — *"the one number that says 'learning is working' has never been true."* This receipt is
        # the same reconciliation, for the refusals.
        Receipt("L7", "every proposal a completed learning run made is recorded as a decision",
                "select count(*) from learning_runs r where r.status = 'completed' "
                "and r.counts->>'evaluations' is not null "
                "and (r.counts->>'proposals')::int <> "
                "(select count(*) from learning_object_evaluations e "
                f"where e.org_id = r.org_id and e.run_id = r.run_id){_org_filter(org, 'r')}",
                lambda n: n == 0,
                "⛔ One evaluation row per proposal, held and refused included. A non-zero count "
                "means a decision path returned without recording its reason — the Atlas's "
                "no-silent-drop contract — and it also gives `learning_object_evaluations` its "
                "first reader and its `_by_run` index its first query"),
        # ⛔⛔ `learning_transitions` IS THE LEDGER THAT WOULD HAVE SHOWN ITS OWN DEFECT. It is
        # append-only, written by five call sites, and read by NOTHING — and
        # `publisher.publish` wrote `governed → published` on every brain publish while
        # `ALLOWED_LEARNING_TRANSITIONS[GOVERNED]` is `(temporary, human_review, promoted,
        # rejected)`. The map's own docstring states the intended two hops, *"| Promoted→Published
        # | Rejected}"*, and the publisher collapsed them, skipping PROMOTED — which is the state
        # that distinguishes *"promoted, publisher not yet done"* from *"published"*, exactly the
        # ambiguity the Atlas's `L7-30` is about.
        #
        # ⛔ Fixed at the source in the same step — the hop is logged and `log_transition` now
        # REFUSES an illegal edge — so this receipt cannot go red on new rows. It is here because
        # a guard at the writer protects the future and says nothing about the past.
        Receipt("L7", "no learning transition takes an edge the contract forbids",
                _ILLEGAL_TRANSITION_SQL(org), lambda n: n == 0,
                "⛔ The legal pairs are derived from `contracts.learning"
                ".ALLOWED_LEARNING_TRANSITIONS`, never copied. A non-zero count is a row written "
                "before 2026-10-02, when `publisher.publish` logged `governed → published` and "
                "nothing validated it. Settle it with `select from_state, to_state, count(*) from "
                "learning_transitions group by 1, 2` — which also answers whether any brain value "
                "has ever been published at all (`L7-27`)"),
        # ⛔⛔ THE ISOLATION LEDGER, FINALLY READ. `learning_input_rejections` had its WRITE built
        # with a comment naming the contract it was upholding — and no reader, so a quarantined
        # input stayed indistinguishable from one that never arrived. `L7-29` requires the **empty
        # reason** to be exposed, and the no-silent-drop contract requires a quarantine to be an
        # observable state.
        Receipt("L7", "no learning input has been quarantined",
                _QUARANTINED_SEAM_SQL(org), lambda n: n == 0,
                "⛔ A read of `card_feedback_verdicts` or `learning_event_inbox` that RAISED and "
                "was isolated — not a seam that returned nothing. Routine discovery refusals "
                "(`seam = brains.org_discovery`) are excluded: those are counted per run in "
                "`org_rule_discovery_runs.counters` and are healthy. A non-zero count means the "
                "verdict or inbox seam is failing to read, which `L7-29` calls a breach of the "
                "declared health SLO"),
        # ⛔⛔ THE HALF THE CODE CANNOT GUARD. `target_policy` proves no producer makes a
        # constrained durable proposal; the approval path rehydrates visibility from the DATABASE,
        # so only this query can close the loop. *A guard that stops at the source boundary
        # catches nothing past it.*
        Receipt("L7", "no active brain value is narrower than the surface that renders it",
                _CONSTRAINED_BRAIN_VALUE_SQL(org), lambda n: n == 0,
                "⛔ `api/brain_routes` renders the VALUE from `learned_brain_entries` and "
                "`temporary_memories` with no principal check, behind an org-only dependency that "
                "admits a `member` seat. A non-zero count is a learned value shown to people its "
                "own visibility excludes. ⛔ The open set is derived from "
                "`contracts.learning.VisibilityScope` via `target_policy.OPEN_SCOPES`, and a NULL "
                "scope counts — an unrecorded scope is not an open one. Settle it with `select "
                "brain, visibility_scope, count(*) from learned_brain_entries where active group "
                "by 1, 2`"),
        # ⛔ And the run must SAY which seam it lost. Gated on `evaluations` — `S6`'s marker — so a
        # run that completed before either field existed is not judged against a contract it
        # predates. *A gate that is always red is a gate nobody reads.*
        Receipt("L7", "a completed learning run says which seams it lost, not only which were empty",
                "select count(*) from learning_runs where status = 'completed' "
                "and counts->>'evaluations' is not null "
                f"and counts->>'quarantined_seams' is null{o}",
                lambda n: n == 0,
                "⛔ `degraded_seams` says WHICH seams were empty; `quarantined_seams` says which "
                "were LOST. Until 2026-10-02 an isolated read arrived at the run identical to an "
                "empty one — and the same block reported the delivery seam degraded on every run "
                "forever, because it read `getattr(batch, \"deliveries\", ())` and the field is "
                "`delivery`"),
        Receipt("L7", "calibration has executed",
                f"select count(*) from calibration_runs where 1=1{o}",
                lambda n: n > 0,
                "precision → auto-mute → bounded nudges has never fired; the outcome data L5 "
                "starts producing would go unconsumed"),
        Receipt("L7", "the counterfactual ledger joins end to end",
                f"select count(*) from counterfactual_ledger where card_id is not null{o}",
                lambda n: (n or 0) > 0,
                "one row per recommendation: cost, exposure, action, outcome — the denominator "
                "of every ROI claim; zero joined rows means a stage's key is broken"),
        Receipt("L7", "a human verdict has reached the loop",
                f"select count(*) from card_feedback_verdicts where 1=1{o}",
                lambda n: n > 0,
                "no verdicts ⇒ nothing to learn from, whatever the engine is capable of"),
    ]




def evaluate(engine, org: str | None) -> list[dict]:
    """Run every receipt; an unrunnable one is a finding (ERROR), never a skip.

    ⛔⛔ FOUR STATUSES, AND THE FOURTH IS `3.2`'s WHOLE POINT. `PASS` · `FAIL` · `ERROR` ·
    **`NOT_EXERCISED`** — a correctness receipt whose claim held while **nothing exercised it**,
    because the table it reads has no rows in scope. Its 0 means *"nothing happened"*, not
    *"nothing went wrong"*.

    ⛔ A WITNESS THAT RAISES MAKES THE RECEIPT AN `ERROR`, NOT A PASS. An unverifiable pass is not
    a pass, and the detail says which half broke — the same reasoning as the sentence above it: a
    receipt that cannot be run is a finding, never a skip. ⛔ The instrument failing is a finding
    about the instrument, and hiding it behind the receipt's own green is how a measurement stops
    being one.

    ⛔ AND ONE UNRUNNABLE RECEIPT MUST NOT TAKE EVERY RECEIPT AFTER IT. Measured against production
    2026-10-01: migration `0190` is unapplied, so the L5 lane receipt raised `UndefinedColumn` —
    correctly, once. Then **twelve** further receipts reported `InFailedSqlTransaction`, because
    SQLAlchemy opens an implicit transaction on first use and a statement that raises leaves it
    invalid. The page said `13 ERROR` where the truth was `1 ERROR` and twelve untried, and an
    operator reading it could not tell which receipt had actually failed.

    ⛔ THIS IS THE SAME DEFECT `domain_shadow` ALREADY FIXED FOR ITS OWN LOOP, and its comment is the
    diagnosis: *"ONE connection serves the whole loop … a single bad situation silently takes every
    situation after it. Measured on the design partner's org: one persist_error was followed by five
    cascade failures … The six missing situations were not unroutable; they were never attempted."*
    The cure there was an unconditional `rollback()` per iteration, for the same reason it is used
    here: `rollback()` on a healthy connection is a no-op, so it needs no flag anybody must keep
    correct.

    ⛔ AND THE ROLLBACK GOES IN `finally`, NOT IN `except`. A receipt whose query SUCCEEDS still leaves
    an open implicit transaction; putting the reset only on the failure path would leave a successful
    receipt holding one, and the next failure would then be attributed to whichever receipt happened
    to be running. The reset belongs after every receipt, not after the broken ones.
    """
    rows: list[dict] = []
    with engine.connect() as c:
        for r in receipts(org):
            params = {"org": org} if org and ":org" in r.sql else {}
            try:
                value = c.execute(text(r.sql), params).scalar()
                ok = bool(r.expect(value))
                status, detail = ("PASS" if ok else "FAIL"), r.detail
                # ⛔⛔ A PASS OVER AN EMPTY TABLE IS NOT A PASS. The witness is asked only on a
                # PASS: a FAIL already found a bad row, so the table demonstrably has rows and
                # asking would be noise.
                #
                # ⛔ This is condition `P2` — *the receipt can fail* — and before this it was unmet
                # AND INVISIBLE: `/readiness` reported a pass. The endpoint's own docstring says
                # what it exists to prevent — *"an empty sweep looked healthy, A SKIP READ AS A
                # PASS"* — and an unexercised correctness receipt is that skip.
                if ok:
                    probe = witness_sql(r, org)
                    if probe is not None:
                        if not c.execute(text(probe), params).scalar():
                            status = "NOT_EXERCISED"
                            detail = ("⛔ the claim held and nothing exercised it: the table this "
                                      "receipt reads has no rows in scope, so 0 means 'nothing "
                                      "happened', not 'nothing went wrong'. " + r.detail)
                rows.append({"layer": r.layer, "claim": r.claim, "value": value,
                             "status": status, "detail": detail})
            except Exception as exc:                       # noqa: BLE001 — evidence, not control flow
                rows.append({"layer": r.layer, "claim": r.claim, "value": None,
                             "status": "ERROR", "detail": f"{type(exc).__name__}: {exc}"[:160]})
            finally:
                c.rollback()
    return rows


__all__ = ["Receipt", "evaluate", "receipts"]
