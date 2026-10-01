# ATLAS RE-CHECK · the two planes, re-measured — and the one silence nothing declares

> **Scope:** the Atlas's own claims about Plane D (Atlas L3 Domain Expertise) and Plane R
> (Atlas L4 Reasoning), re-measured against code and production on **2026-10-01**, read-only.
> **Why these two:** they hold the most data, so a stale claim about them is the most expensive.

---

## PART 0 · THE SOURCE, AND WHY IT HAD TO BE RE-MEASURED RATHER THAN READ

`Rohit_Updates/Secret War Updates/08-Cross-Layer-Synthesis/01-Master-Atlas-vs-Code-Coverage-Matrix.md`
synthesises seven layer audits against `harsh/mvp@b739bd5c` on **2026-08-22**.

It is a good document. It is also **six weeks old**, and this programme's own rule applies to it
exactly as it applies to our own work: *an audit is a measurement with a date on it, and a
measurement read six weeks later is a claim.* Every number below was taken again.

### ⛔ FIRST, THE VOCABULARY, BECAUSE IT IS WHY THIS CHECK LOOKS MISALIGNED AND IS NOT

The matrix numbers **seven** layers. YCW27 numbers **six** folders. They are two different
vocabularies and `genios_engine/LAYERS.py` documents **four** of them in its header, including the
collision:

    package     layer   name                       Atlas   PRODUCT (YCW27 folders)
    capture       1     Enterprise Signals           1       L1
    context       2     Situation Intelligence       2       L2 + L3
    packs         -     Plane D · Domain Expertise   3       into L2
    reason        -     Plane R · Reasoning          4       L2 + L4
    executive     5     Executive Intelligence       5       L4
    deliver       6     Intelligence Distribution    5.2     L5
    feedback      7     Learning Engine              6       L6

So **"layer 1, layer 2, layer 3" in the YCW27 vocabulary covers Atlas L1, L2, L3 and L4** — and the
two planes sit inside YCW27's L2. The folders are not wrong; they are the PRODUCT column, which
`LAYERS.py` names as a legitimate fourth vocabulary.

⛔ **I nearly filed this as the programme's largest defect.** I had measured that five of six YCW27
folder names contradict `LAYERS.py`'s digits and was about to write it up. Reading `LAYERS.py`
first stopped it: the file already explains the collision in capitals and states the rule —
**"always name the package, never the digit alone."** Fifth time in this programme that reading the
thing a name points at prevented a false finding.

### ⛔ ALARM R-A1 · and the receipts break that rule
`platform/receipts.py` labels all 29 receipts `L1`–`L7` — **bare digits in the package vocabulary**,
returned by `GET /health/readiness` as `{"layer": "L2", ...}`. A reader holding the PRODUCT
vocabulary maps `L2` to Reasoning; the receipt means Context. Its own docstring calls the surface
operator material, which lowers the stakes but does not change the rule `LAYERS.py` sets.
Cheap to fix, and it changes a response shape, so it is its own unit. Not done here.

---
---

## PART 1 · PLANE D IS COMPLETE — the Atlas's sharpest accusation about it has EXPIRED

Measured with `packs/compiler/capability_resolver.corpus_health()` — the function the code's own
comment points at, rather than a count of my own.

| | Atlas · 2026-08-22 | Measured · 2026-10-01 |
|---|---|---|
| **Admin** | *"**Stub.** Fifty-seven files, **all 57 stubs**, zero non-stub, zero reviewed/accepted and **zero routes**. No current basis exists for prescriptive Admin expertise"* | **59 capabilities · 59 admitted · 0 inadmissible · 0 hollow · 34 situations** |
| **Customer Support** | 49 total / 40 stubs / 9 non-stub | **49 · 49 admitted · 0 hollow · 20 situations** |
| **Sales** | 46 total / 43 stubs / 3 non-stub | **47 · 47 admitted · 0 hollow · 15 situations** |
| **the whole corpus** | *"All 12 non-stub entries are draft/unreviewed, with **zero reviewed or accepted**"* | **155 capabilities, every one admitted, 0 hollow** |

**The corpus was authored out from under the matrix.** Capability files on disk: Admin **212**,
Support **169**, Sales **157**.

### ⛔ AND THE CODE HAD ALREADY LEARNED THIS LESSON, THE EXPENSIVE WAY

`capability_resolver._hollow`'s docstring:

> *"at the time this rule was written, 136 of the corpus's capabilities were `stable`, `approved`
> and hash-pinned over a file whose own notes read 'Phase 1 stub'. … ⛔ **THAT COUNT IS HISTORY, NOT
> A FACT ABOUT TODAY'S CORPUS, AND LEAVING IT UNMARKED COST A PLAN.** Measured 2026-09-24 by
> `corpus_health`: **0 hollow of 155.** The corpus was authored out from under this paragraph and
> nothing said so, because nothing printed the number."*

That is the same defect the Atlas matrix now has, one level out. The code fixed it by moving the
count into **a function a test can run**. The matrix has no such function, which is why it had to be
re-measured by hand here.

### What remains true, and it is the honest remaining gap

    situations_unreviewed     Customer Support 16 of 20 · Admin 7 of 34 · Sales 0 of 15
    total                     23 unreviewed situations of 69

A `draft` situation's cards **cannot instruct** — `capability_resolver.situation_admission_reason`
enforces that, and all 23 are flagged. So this is the designed refusal, not a leak. Whether `draft`
should also *gate* is a decision with a number under it. **Whose: Rohit.**

⛔ Two earlier records say **24**; measured today it is **23**. Corrected here, not edited there.

---
---

## PART 2 · PLANE R — the Atlas's accusation was RIGHT, and is now LARGELY WRONG

> *"Seventeen units are registered; the common legacy manifest schedules roughly six. **Registered
> is not active.** Every card needs an executed/skipped unit receipt."*

**Both of its counts are exact.** `CORE_UNITS` is **17**. `BUILTIN_CAPABILITIES` is one capability,
`sales.deal_cooling`, scheduling **7** units. The matrix measured the code correctly.

**And the conclusion no longer holds.** Re-measured against `reasoning_reasoner_results`:

    registered in code            23   (17 core + 6 supplementary)
    ever ran in production        22
    ⛔ never ran                   1   core.signal_composition
    ran but not registered        0   — the registry and production agree exactly

| | Unit | Runs | Completed |
|---|---|---|---|
| | core.constraint · core.validation · core.alternative · core.priority · core.confidence | 2,681 | 2,681 |
| | core.temporal | 2,681 | 1,897 |
| | core.planning | 2,681 | 2,681 |
| | core.cost · core.recommendation · core.risk · core.impact · core.tradeoff · core.context · core.dependency | 1,973 | 1,973 |
| | core.timeline | 1,973 | 1,464 |
| | core.opportunity | 1,973 | 1,088 |
| | core.scheduling | 1,973 | 452 |
| | core.resource | 1,973 | 68 |
| | legacy.rule · legacy.score_gate | 708 | 708 |
| ⛔ | **core.relationship** | **929** | **0** |
| ⛔ | **core.policy** | **165** | **0** |

⛔ **My first run of this measurement produced a false finding and is recorded rather than deleted.**
It reported *"6 registered units never ran"* — `legacy.rule`, `core.planning`, `core.temporal`,
`core.relationship`, `legacy.score_gate`, `core.signal_composition`. All but the last had run
thousands of times. **The six supplementary units carry no `unit_id` class attribute** (they predate
the framework and are identified by `spec.reasoner_id` on an *instance*), so my id helper returned
class names and every one failed to match. The artefact looked exactly like a finding. Fixed by
instantiating, which is how the registry itself reads them.

---
---

## PART 3 · ⛔ THE FINDING — a third kind of silence, and exactly one unit in it

`reason/unit_health.py` declares two grains, and a receipt reads each:

| Grain | Question | Covers |
|---|---|---|
| `DeclaredSilence` | a unit **completes** and computes nothing | `core.impact` 100%, `core.opportunity` 94% |
| `UnwrittenFact` | a bound fact path nothing **writes** | 14 of 22 paths, 5 movers |

**`core.policy` is covered — by the second grain, through its inputs.** All four paths it binds
(`contact.consent_status`, `contact.do_not_contact`, `deal.approval_status`, `deal.value`) are in
`DECLARED_UNWRITTEN`. `receipts.py:381` says it in one line: *"it is not failing, it is correctly
refusing to run on nothing, forever."*

**`core.relationship` is covered by neither, and it is the one unit in the gap.**

* Not `DeclaredSilence`: `_UNDECLARED_SILENT_UNITS_SQL` filters `where status = 'completed'`. A unit
  with **zero** completed rows is not a row with a low share — **it is not a row**, so it cannot
  appear in the GROUP BY and the receipt cannot see it. The receipt PASSES while this unit has
  produced nothing in 929 attempts.
* Not `UnwrittenFact`: it binds `deal.status`, which has **3 rows**. The declaration is for paths
  with *zero*, and `receipts.py` states why on purpose: *"A path with one row has a writer; that is
  the whole question. How WELL it is covered is `deal.status`'s 3-of-293 problem, a different
  measurement with a different mover."*

So the gap is **named in prose, in two separate comments, and declared nowhere a receipt can read.**
Worse, `DECLARED_SILENT["core.impact"]`'s own reason text already states *"core.relationship has
NEVER completed — 708 insufficient_context, 221 skipped"*. **The fact is written down as an
argument for another unit's entry and has no entry of its own.**

Measured breakdown:

    core.relationship   929 runs    708 insufficient_context   221 skipped:no_declared_input_available
    core.policy         165 runs      0                        165 skipped:no_declared_input_available

### Why this is the same defect shape the programme keeps finding

A count without its dimension is not a measurement — and *silent* has turned out to have three
dimensions, not one. **Totality guards both directions**, and the silence receipt guards only the
direction where a row exists.

> **A unit that never completes is not a quiet unit; it is an absent one, and a question asked only
> of completions cannot see it.**

---

## PART 4 · THE PLAN — one unit, bottom-up

**R1 · `NeverCompleted` in `reason/unit_health.py`** — the third grain, beside `DeclaredSilence`
and `UnwrittenFact`. It needs what both need (a reason, a mover, a measurement date) plus what
neither needs: the **run count with zero completions**, because that is the number proving it is
absent rather than merely quiet. Refuse an empty field exactly as the siblings do.
Declare `core.relationship`: reason = `deal.status` has 3 rows across 293 candidate nodes, so the
path is written but not usefully written; mover = **Harsh**, a CRM connector.
⛔ Do **not** declare `core.policy` here — it is already declared through its inputs, and a second
declaration of one fact is the drift this module exists to prevent.

**R2 · the receipt that can see it** — `platform/receipts.py`, a fourth `_..._SQL(org)` builder
beside the three that exist. The claim: *every unit that has run and never completed is a declared
one.* It must **not** filter to `status = 'completed'` — that filter is the whole defect. And it
must be able to fail: a twenty-fourth unit going fully quiet turns it red.

**R3 · the proof** — `expect(1) is False`; the SQL carries no `completed` filter; `core.policy` is
**not** in the new declaration; and a test that the reason text in `DECLARED_SILENT["core.impact"]`
and the new entry do not contradict each other.

### ⛔ What this unit does NOT do
It does not make `core.relationship` complete. That needs a CRM connector writing `deal.status`
across more than 3 of 293 nodes — **Harsh, `HANDOFF-HARSH.md` H4**. What it does is stop the
product reporting, through a green receipt, that every silence is accounted for when one is not.

---
---

## PART 5 · BUILT — measured 2026-10-01

**R1 · `reason/unit_health.NeverCompleted` + `DECLARED_NEVER_COMPLETED`** — the third grain. It
demands what the siblings demand (reason, mover, date) plus the **run count**, because that is the
number separating *absent* from *never scheduled*. `runs <= 0` is **refused at construction**, so
`core.signal_composition` (0 runs, unswept capability, ALARM A2) cannot be mis-filed as a silence.

**⛔ The first version of `undeclared_never_completed` reported `core.policy` as undeclared.** That
would have put the receipt permanently red for a unit the codebase already accounts for. Closed with
`starved_by_declared_paths()` — a unit is excused when **every** fact path it binds is in
`DECLARED_UNWRITTEN`, computed from the roster. Derived, never listed:

    starved_by_declared_paths()  ->  core.dependency · core.impact · core.policy

Hard-coding `core.policy` would have put one fact in two places and gone stale the moment a path
gained a writer. A unit that binds **nothing** is deliberately not in the set: having nothing to
bind is not the same as binding something nobody writes.

**R2 · `platform/receipts.py:_UNDECLARED_NEVER_COMPLETED_SQL`** — the fourth builder, and the
receipt is **30th**. One clause is the whole difference from its sibling:

    the silence receipt     where status = 'completed'   ... group by reasoner_id
    this receipt            where 1=1                    ... group by reasoner_id
                            having count(*) > 0
                               and sum(case when status = 'completed' then 1 else 0 end) = 0

`having count(*) > 0` is not redundant — it is what keeps 0/0 and 0/929 from being the same number.

**R3 · `tests/reason/test_a_unit_that_never_completes_is_declared.py` — 17 tests, all passing.**
Proved by mutation: putting the `where status = 'completed'` filter back turns
`test_the_query_does_not_filter_by_completed_status` red. Also asserted: `core.policy` is **not** in
the new declaration; every excused unit's paths really are all declared unwritten; and
`DECLARED_SILENT["core.impact"]`'s reason text and the new entry **do not contradict each other** —
two statements of one fact in one module must agree or the module is the drift.

### VERIFIED ON PRODUCTION, read-only

    the R2 receipt                PASS   value = 0
    all 30 receipts, fleet-wide   22 PASS   7 FAIL   1 ERROR     (was 21/7/1 of 29)

The receipt passes because both never-completing units are now accounted for — one declared here,
one derived from the other grain. It goes red the moment a twenty-fourth unit stops answering.

### ⛔ WHAT THIS DID NOT DO

**It did not make `core.relationship` complete.** That needs a CRM connector writing `deal.status`
across more than 3 of 293 nodes — **Harsh, `HANDOFF-HARSH.md` H4.** What changed is that the
product can no longer report, through a green receipt, that every silence is accounted for while one
is not.

**And the chain it sits on is unchanged and still four deep:**

    deal.status 3 of 293 rows
      -> core.relationship    929 runs, 0 completions      (now declared)
        -> core.impact        1,973 completions, 100% silent  (declared)
          -> core.tradeoff's benefit axis has no prior
            -> tradeoff.cost_vs_benefit  0 fires in 1,200 rows

Every unit in it reports a healthy status. Nothing logs an error. The test for the cost axis is
green — on a prior the test supplies itself. **Three of the four links are now declared facts rather
than prose**, which is the only part of this a layer below the connector could change.
