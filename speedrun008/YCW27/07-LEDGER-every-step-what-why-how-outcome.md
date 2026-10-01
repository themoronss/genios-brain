# THE LEDGER · every step in the programme — what, why, how, expected, outcome

> **Written:** 2026-10-01 · **the one document to read if you read one.**
> Each layer below names its package, its test count, and every step with the task it was given, why
> it mattered, and what actually came out. **Where the outcome differs from what was expected, the
> difference is the entry** — a step whose outcome matched its plan exactly is the least interesting
> row on the page.
> **Status counts, verified by test** (`tests/test_programme_step_status_is_consistent.py`):

    40 step files      34 DONE      3 PENDING      2 WITHDRAWN      1 RETIRED

---

## PART 0 · HOW TO READ THIS, AND THE TWO THINGS THAT ARE NOT HERE

**Build order follows the data flow, never the Atlas numbering.** `capture → context → reason →
executive → deliver → feedback`. The Atlas numbers L1–L6 in a different order and following it would
have built consumers before producers.

**A layer is the PRODUCT layer, not the package.** `context/` spans product L2 and L3; `reason/`
spans L2 and L4. `genios_engine/LAYERS.py` is the single source of layer numbers and
`tests/test_layer_topology.py` fails the build on an upward import. `contracts/`, `platform/`, `api/`
and `mcp/` are CROSS_CUTTING, and **`contracts/` may depend on platform and stdlib only.**

**Not in this ledger, on purpose:**
* the *decisions* — those are the ALARMS table in `STATUS.md`
* the *fixes with their reasoning* — those are `05-FIX-LOG.md`, 958 lines, append-only

---
---

# L1 · ENTERPRISE SIGNALS · `capture/` · 5,499 tests

*What arrives, and whether it is worth anything.*

| Step | Task | Why it mattered | Outcome |
|---|---|---|---|
| **01** DONE | relevance judgment | S4's relevance page was re-asking a model what S2's one call already answered | **at most ONE AI call per object**, recorded as rule `K3` in the file |
| **02** DONE | `temperature` sent to models that refuse it | the parameter was being sent to models that reject it outright — a silent per-call failure | removed at the seam that knew which models accept it |
| **03** DONE | nothing noticed when the provider stopped answering | the provider could stop answering and no surface said so | an alert path that fires on provider silence |
| **04** PENDING | the API spend limit · **Rohit (account) / Harsh (ops)** | since **2026-09-25 11:09 UTC** every model call returns `400 invalid_request_error — "You have reached your specified API usage limits"` | ⛔ **not a code fault, and not GeniOS's own cost governor** — that works and was never the blocker. **Every production number taken since is model-off** |
| **05** DONE | where the four objects live | four object types had no agreed producing layer; two product layers editing one package collide | the rule recorded in `docs/LAYER_MAP.md` + `LAYERS.py` **with the rejected option named**, and each unit is a **guard** that fails if a producer changes layer — not a move |
| **06** DONE | the signal bundle | the signals that arrived **together** were stored as unrelated rows | `capture/esqe/bundle.py` + `contracts/signal.py`. ⛔ **needs `0186`** |
| **07** DONE | the evidence-need door | nothing could name *the one fact that would change the conclusion* | `capture/acquire/evidence_need.py` + `need_executor.py`. ⛔ **needs `0187`** |
| **08** PENDING | OCR has never run · **Harsh** | 872 `document_jobs` unreadable; **0** rows ever carried an engine | §3 of that step (*a defect in our own test suite*) was **closed on 2026-10-01 by audit E**; §2, the deploy, is still open |
| **09** PENDING | the 60-day window · **Harsh** | benchmark prompts **P3 (6mo)** and **P4 (12mo)** are not unproven, they are **structurally unanswerable** — the mail was never fetched | widen 60 → 365. Prerequisite `0184` **is applied**, and it is what stops a widened window backdating a year of edges into the as-of history |
| **10** DONE | the pass that works the needs queue | an evidence need that nothing acts on is a wish | the sweep pass that works the queue |

---

# L2 · REASONING · `reason/` + `packs/` · 1,392 tests in `tests/reason`

*The layer this product is. Two planes plus the spine.*

### The spine

| Step | Task | Why it mattered | Outcome |
|---|---|---|---|
| **01** DONE | prove the claims before changing anything | the Atlas badged several things as gaps that were **already built**; 1 of the first 3 spot-checked was wrong, and the whole build order rested on those badges | a claim-by-claim corrected baseline. ⛔ **Verified already built but badged a gap:** coverage receipts, absence machinery, `ReasoningRequest`, `ContextSnapshot`, `CritiqueVerdict`, `DeliveryObject`, `brief.v1` |
| **02** RETIRED | a dropped unit leaves a receipt naming its missing input | — | ⛔ **retired, not built** — the existing test file already proved the behaviour, and proved a *different* gap S2 actually has |
| **03** DONE | a kept unit that lost a source says so | a unit that loses an input mid-run went quiet indistinguishably from one with nothing to say | the degraded-step record |
| **04** DONE | the five pipeline counters | *"we made 28 cards"* is not a diagnosis; `signals_detected → situations_formed → capability_resolved → decision_emitted → card_delivered` is | the five counters. ⛔ **needs `0188`** |
| **05** DONE | the five output lanes, and the router | there was no vocabulary for **which kind** of output a reader gets | `decision / investigation / conflict / monitor / suppress`. ⛔ **needs `0189`** |

### Plane D · domain expertise · `packs/` + `Domain Expertise/` · 203 tests
*What a professional knows.*

| Step | Task | Outcome |
|---|---|---|
| **01** DONE `M11.C5.U05` | a refusal says which kind it is | `NoExpertiseRoute.REASONS` — 4 closed reasons, `reason` **required and keyword-only** |
| **02** DONE `M11.C5.U02` | the unrouted list cannot drift | ⛔ the list was believed hand-kept; `_tools/index.py:205` **generates** it. Found by reading the code the comment pointed at |
| **03** WITHDRAWN `M11.C5.U03` | the draft guard | ⛔ **it was already built.** A corpus comment said in capitals *"a situation's status gates nothing"* — true when written, and `capability_resolver.situation_admission_reason` had closed it since. Measured: all 23 draft situations flagged, **zero** can instruct |
| **04** DONE `M11.C5.U06` | refusals counted by (reason × type) | **a count without its dimension is not a measurement** |
| **05** DONE `M11.C5.U04` | every capability has a door or a reason | `deferrals.yaml` for Customer Support — all 7, `blocked_on_l2_type` |
| **06** DONE `M11.C5.U07` | read the field, never the message | the validator was reading a human-readable message where a field existed |
| **07** DONE `G1`–`G5` | the five completeness gaps | 22 new core objects (9 Admin, 13 Support), all `status: draft`; `Domain Expertise/_eval/` — 18 cases, **10 `expect: abstain`** |

### Plane R · reasoning units · `reason/reasoners/` · 59 guard tests
*How a professional thinks.* **17 core + 6 supplementary = 23 units, 56 plugins**, across 4
categories: Situation Understanding (4), Business Evaluation (5), Optimization (5), Decision
Support (3).

| Step | Task | Outcome |
|---|---|---|
| **01** DONE `S5.U01` | the unit source contract | `DEFAULT_RELATIONSHIP_SOURCE` becomes a named constant at `impact_unit.py:127` — it had been an inline literal |
| **02–08** DONE | the seven remaining source declarations | every reasoner now declares `source_units`; `core.tradeoff`'s is **derived** from `AXIS_SOURCES` so two lists cannot drift; `U07` proves the declaration is load-bearing, `U08` that it agrees with the roster |

⛔ **What the whole section was for, and what it did not do.** `tradeoff.cost_vs_benefit` had fired
**0 times in 1,200 production rows** while its test passed — on a prior the test supplied itself.
Nothing anywhere said which units a unit reads, so a source could stop publishing and the consumer
would go quiet with no error. The section made that **declarable**. It did **not** make the axis
fire: `core.impact` is 100% silent because `deal.status` has no writer, and that is declared in
`reason/unit_health.DECLARED_SILENT` with its reason and its mover.

---

# L3 · CONTEXT GRAPH · `context/` · 2,949 tests

*What is known, and how certain.*

| Step | Task | Why it mattered | Outcome |
|---|---|---|---|
| **01** DONE | the bounded query API | an unbounded graph read is a latency incident waiting for the right tenant | `context/bounded_read.py` — `ReadRequest` frozen and **bounded by default**, refuses a seedless read; `expand` + `read_bounded` cap breadth-first, report truncation, carry the revision |
| **02** WITHDRAWN | compare-and-set on write | — | ⛔ withdrawn — the guard it would add already existed |
| **03** DONE | a hold that asks | a hold that does not ask for what would clear it is a dead end | the hold raises an evidence need |
| **04** DONE | a met need clears its hold | a need met with the hold still standing is worse than no need | the need clears the hold |
| **05** DONE | residue reaches the sweep | residue that never reaches the sweep accumulates invisibly | wired into the sweep |

---

# L4 · EXECUTIVE · `executive/` · 63 tests

*Who acts, and whether anyone can.*

| Step | Task | Why it mattered | Outcome |
|---|---|---|---|
| **01** DONE | the reporting line, tested | rung 7 of the escalation ladder (escalate → manager) climbed into nothing | tested — **⛔ and a spec retired**: `seat_responsibilities` has 0 rows and there is no `reports_to` column, so the receipt asking for a manager is **right to fail at 0** |
| **02** DONE | why this tenant cannot be routed to | *"not ready"* with no reason is not actionable | the per-tenant readiness reason |
| **03** DONE | activated is not the same as ran | an activation row with no live run reports itself on while changing nothing | the activation receipt |
| **04** DONE | activity is not outcome (Rule 11) | counting activity as outcome is how a system congratulates itself | Rule 11 enforced |

---

# L5 · DELIVERY · `deliver/` · 222 tests · M13

*What a founder actually receives.*

| Step | Task | Why it mattered | Outcome |
|---|---|---|---|
| **01** DONE `M13.C2.U03` | the lane reaches the card | ⛔ `0189` put the lane on `signals`; grepped 2026-09-30, `deliver/` referenced it **nowhere**. Built, tested, green, **called by nothing** — the eighth instance of that defect and the first this programme produced itself | `lane_display.py` + `0190`. **Three real defects the tests found**, see below |
| **02** DONE `M13.C2.U04` | ⛔ **rewritten** · the recall guard | the first version made the check a tautology | `lane_recall.py` — `low_confidence_is_never_silent()` |
| **03** DONE `M13.C1.U01` | the claim extractor | a card's claims were not separable from its prose, so nothing could grade them | `claims.py`, reusing `contracts/claim_state.ClaimState`; precedence: instruction→ENVELOPE, **hedge outranks grounding** |
| **04** DONE `M13.C1.U02` | widen the invention validator | | `claim_validator.py` — `claims_ok()` **calls** `invention_ok` first and its verdict is final |

### ⛔ The three defects L5's own tests found, because they are the pattern

1. **`str(OutputLane.DECISION)` is `"OutputLane.DECISION"`, not `"decision"`.** Every in-process
   caller would have been labelled `unrouted`. The DB path stored plain text and **hid it.** Fixed
   with `getattr(x, "value", x)`.
2. **`tally_lane` gave two answers.** It re-described the raw column with no reason, and `describe`
   treats a lane without its reason as no route — so one card was *displayed* `decision` and
   *counted* `unrouted`.
3. **The tally was at the wrong place.** Counting on the composed draft described a population
   nobody received **and** made the recall check a tautology. Moved to the two persist sites.

Plus: the lane was briefly put inside `decision_hash`, which broke four replay tests. Removed —
`route()` is a pure function of inputs already in the hash, so the lane adds **zero** information to
a decision's identity. The correction is recorded in `0190`'s header because `0189` is immutable.

---

# L6 · LEARNING · `feedback/` · 87 tests · M14

*What the system learns when it was wrong.*

| Step | Task | Why it mattered | Outcome |
|---|---|---|---|
| **01** DONE `M14.C1.U01` | the attribution vocabulary | "this card was wrong" with no reason teaches nothing | `contracts/learning_attribution.py` — `WrongReason` (**11**, closed), `DEBITABLE_LAYERS` (**6** — `feedback` excluded on purpose) |
| **02** DONE `M14.C1.U02` | eleven reasons, and **all five readers** | widening the vocabulary without widening every reader is how four real failures get counted by nothing | all five readers widened |
| **03** DONE `M14.C1.U03` | ⛔ **narrowed** · the layer debit | | the debit, narrowed from its plan |

### ⛔ The defect the widening would have shipped
`feedback/units.py` branched on **one literal**: `elif reason == "bad_timing"`. Going from 3 to 11
reasons would have made **four new "card was right" reasons debit accuracy**, and `_PRECISION_SQL`'s
2-reason list would have left **four real quality failures counted by nothing**. Changed to
`elif not _grades_accuracy(reason)` — a predicate over the closed set, not a literal.

⛔ `contracts/learning_attribution.py` first imported `LAYERS` and
`test_contracts_import_nothing_above_platform` **failed the build. The gate was right** — layer names
are plain strings there and the `LAYERS.py` check moved into a test.

---
---

# PART 2 · THE FIVE CROSS-CUTTING AUDITS

Every receipt on the operator page was examined. Ten findings, five audits.

| | Audit | What it found | Where |
|---|---|---|---|
| **A** | the lost-axis receipt | `core.tradeoff` loses axes silently. ⛔ **I first refused the correct fix on a false reading** — claimed it would rehash ~100% of 12,170 traces; `_verify_replay_bundle` hashes **stored content against its stored hash** and never re-runs a unit. **Zero rows rewritten.** Recorded in PART 0, not edited away | `09-AUDIT` |
| **B** | the fact-writer census | **14 of 22** bound fact paths have no writer, across **5** movers. And the `evaluate()` cascade: one failing receipt left the connection invalid, so **12 phantom ERRORs hid 9 real findings** and named the wrong twelve. Fixed with `c.rollback()` in a **`finally`**, not an `except` | `10-AUDIT-B` |
| **C** | the nine findings | **one** receipt asked the wrong question — the L6 draft receipt asked `render_mode <> 'llm'` while its own detail said *"empty artifact body"*. It **counted 35** cards that do have a body and **missed 13** that do not; of 38 empty-body cards **19 abstained** and correctly carry no draft. Rewritten, and it **still FAILS at 18** — *a receipt is not fixed by making it green*. The other eight were correct, including **three I suspected and cleared** | `06-C-AUDIT` |
| **D** | the frozen-formula receipt | a **correct question with no date on it.** 59 candidates had `impact`/`risk`/`effort` all at the forbidden 5000 default — **53 with all five**, the whole formula one constant. Closed **2026-09-08** by `75096bab`; last affected row **2026-09-07 23:55**, and **34,167** clean since. The table is append-only, so the receipt returned 59 **forever** | `12-AUDIT-D` |
| **E** | the test that measured the host | the suite's only red test stubbed one of two prerequisites and asserted the positive outcome. **Product was correct.** And the unstubbed half is the half that broke production — with the bindings check replaced by `return True` the **old suite stayed green** | `11-AUDIT-E` |

---

# PART 3 · THE ALIGNMENT PASS · 2026-10-01

### ⛔ Seven step files disagreed with themselves
`layer-3-context-graph` had four and `layer-1-enterprise-signals` three where the **filename** said
`DONE`, the body carried `# ✅ DONE — 2026-09-30` with the artifacts named, and the **title line**
still said `TO BUILD` or `NEXT`. Three labels on one piece of work, one disagreeing.

A heading that says *TO BUILD* on finished work is the same defect as a stale comment — it reads as a
status somebody checked, and the expensive version of that mistake is **rebuilding something that
already exists.** Each title was corrected only after its named artifacts were verified present, and
each file carries a dated note saying what the title used to say.

**Now wired so it cannot drift again:** `tests/test_programme_step_status_is_consistent.py`, 4 tests.
Proved by mutation — reverting one title to `TO BUILD` turns it red.

* filename status and title status must agree ← the defect
* every step declares a status from a closed set
* a **PENDING** step must name its owner in the title — the codebase's own doctrine (*every silent
  lane carries a reason **and a mover***) applied to its plan
* and one check that was written, run, and **dropped**: it asserted a completion-section convention
  the programme never adopted. Widening it until it passed would have left it asserting that a
  markdown file contains a heading. The reason is recorded in the module.

### Plane R's missing record
Eight units landed and only `STEP-01` had a note. A built unit with no record is indistinguishable
from one nobody built. Written up as `STEP-02-to-08-DONE-the-remaining-source-declarations.md`.

---

# PART 4 · WHERE IT STANDS, MEASURED

    full suite                     14,534 passed · 1,063 skipped · 152 xfailed · 0 failed
    production receipts (29)       21 PASS · 7 FAIL · 1 ERROR
    reasoning runs measured        12,170      expertise packages  1,150      cards  165
    orgs                           3           reasoning candidates  34,232

⛔ **Not one remaining receipt failure is a mis-asked question.** All ten findings were examined; one
asked the wrong question, one asked a correct question undated, eight were right. Every remaining red
is a true statement about a real gap with a named mover — which is what makes the handoffs short.

| | Remaining | Value | Whose | Handoff |
|---|---|---|---|---|
| 🔴 | `0186`–`0190` unapplied | — | **Harsh** | `HANDOFF-HARSH.md` **H1** |
| 🔴 | attachments carry readable text | 872 | **Harsh** | **H2** |
| 🟠 | the 60-day window | — | **Harsh** | **H3** |
| 🟠 | a writer for `deal.status` | 3 rows / 293 | **Harsh** | **H4** |
| 🟡 | an approval-workflow source | 6 paths | **Harsh** | **H5** |
| 🔴 | the API spend limit | — | **Rohit** | `STEP-04` |
| 🔴 | roster activation (ALARM A2) | — | **Rohit** | ⛔ ALARM A5 first |
| 🟠 | the parked queue | 1,662 | measure first | `HANDOFF-CODING-AGENT.md` **CA3** |
| 🟠 | `or ""` instead of a refusal (A6) | — | coding agent | **CA1** |
| 🟠 | `axis_count` read by nobody | — | coding agent | **CA2** |
| ⚪ | nothing is committed | 300+ files | **Rohit** | last commit `c7cdf4c1` predates this work |

---

# PART 5 · THE DOCTRINE THIS PROGRAMME PRODUCED

Rules that did not exist before, each bought with a defect:

1. **A count without its dimension is not a measurement.**
2. **A declared silence with no mover is an undeclared silence with paperwork.**
3. **An audit is a measurement with a date on it; a measurement read six weeks later is a claim.**
4. **A crude slice that happens to fail looks exactly like a real finding.**
5. **A receipt is not fixed by making it green.**
6. **A stale comment is more dangerous than no comment** — it reads as a measurement somebody took.
7. **A receipt over append-only history needs a lower bound, or it is not a gate but a monument.**
8. **A test that leaves one prerequisite to the host is not asserting a product property** — a
   verify that only runs on one machine is a local observation.
9. **Assert on structure — the AST, the column list — never on text that happens to sit near a
   thing.** The blunt-grep family, **seven** instances, every one matching the author's own prose.
10. **A guard that must modify the corpus to prove it works cannot be trusted in CI**, and the fix
    for a flaky test is never to weaken the check it guards.
11. **The roster is authoritative; a grep is not.** A regex truncating hyphenated ids reported 13
    missing objects where the roster said 9 — three were already authored.
12. **Two targeted test runs are not a suite run.**

---
---

# PART 6 · THE FULL ALIGNMENT PASS · 2026-10-01 · what was out of line and what now holds it

PART 3 above records the seven step titles. That was the first thing found, not the only one. The
whole programme folder was then checked for the same defect shape — **a label that reads as a status
somebody checked** — and five more instances were found.

| | What disagreed | With what | Fixed how |
|---|---|---|---|
| **1** | 7 step **titles** said `TO BUILD` / `NEXT` | their own filenames and their own `✅ DONE — 2026-09-30` sections, artifacts present in the tree | titles corrected **after** verifying the named artifacts exist, each with a dated note saying what it used to say |
| **2** | `README.md` said *"Layer 3 is finished. Layer 2 is planned, no code written. Next action is Layer 2, Section S1."* | all six layers and both planes are built | rewritten as a **who-you-are** index, with the superseded line quoted and dated rather than deleted |
| **3** | `02-DECISIONS.md` said *"all four open"* | **#4 is closed in code** (`LAYERS.py` + `docs/LAYER_MAP.md`, enforced by `tests/test_layer_topology.py`) and **#2 is closed in practice** (correlation stayed in `context/`) | a dated status table appended; #1 and #3 remain open and are **Rohit's** |
| **4** | 7 crosscheck/plan docs say *"No code written yet"* | every one of their layers is now built | **not retracted** — a crosscheck is *supposed* to say that, and the date makes it honest. A dated footer on each names what has since been built and points here |
| **5** | 3 folders had no `03-FINDINGS.md` | the four-document convention; L2's findings were spread across seven numbered files | three findings **indexes** written — pointers to records that already existed, no new claims |
| **6** | the ledger was numbered `01-` | `01-BASELINE.md` already held that number | renamed to `07-`, and the 7 references to the old name in the step notes updated with it |

### ⛔ The decision inside #3 that is worth more than the fix

Decisions **#1** (ConfidenceVector axes) and **#3** (the naming freeze) were both declared *blocking*
at the start of this programme — *"every upper layer depends on them."* **All six layers and both
planes were then built without either being settled.** They turned out to be about axis labels and
names, not data flow.

**#4 was the one that actually blocked, and it blocked because it was enforceable in a test.** That is
the general rule: *a decision that can be enforced by a test is the kind that blocks; a decision about
what to call something can almost always be deferred, and deferring it made it cheaper rather than
more expensive.*

### Now wired, so none of the six can recur

`tests/test_programme_step_status_is_consistent.py` — **6 tests**, each proved by mutation:

| Check | Catches |
|---|---|
| filename status == title status | **#1** — reverting one title to `TO BUILD` turns it red |
| every step declares a status from a closed set | an invented status that no reader would question |
| a `PENDING` step names its owner in the title | the codebase's own doctrine — *every silent lane carries a reason **and a mover*** — applied to its plan |
| every layer/plane folder carries all four documents | **#5** — removing `02-PLAN.md` from one folder turns it red |
| the folder list is **derived** from where step files are, not hard-coded | a ninth folder being added and silently never checked |
| the step list is non-empty | the four checks above passing vacuously |

⛔ And one check was written, run, and **dropped**: it asserted that a settled step carries a
completion section matching one heading convention. It failed on six files that were all correct —
the programme genuinely has three conventions. Widening it until it passed would have left it
asserting that a markdown file contains a heading. **A test that enforces a convention the repo never
adopted is noise, and widening one until it passes is the same mistake as narrowing a verify until it
passes.** The reason is recorded in the module rather than deleted with the code.

### Measured after the pass

    full suite                        14,540 passed · 1,063 skipped · 152 xfailed · 0 failed
    (14,534 before the pass, +6 — exactly the six programme-consistency tests, re-run after
     the last two were added. The 14,538 first recorded here was measured mid-pass and is
     corrected rather than deleted: a number taken before the work finished is not the number.)
    step files                        40 · 34 DONE · 3 PENDING · 2 WITHDRAWN · 1 RETIRED
    layer/plane folders               8 · all four documents each
    production receipts (29)          21 PASS · 7 FAIL · 1 ERROR

---
---

# PART 7 · THE ATLAS RE-CHECK · 2026-10-01 · the two planes, re-measured against their own matrix

Full audit: `layer-2-reasoning/13-ATLAS-RECHECK-the-two-planes-and-the-third-silence.md`.

The Atlas's own synthesis — `Rohit_Updates/Secret War Updates/08-Cross-Layer-Synthesis/
01-Master-Atlas-vs-Code-Coverage-Matrix.md`, seven layer audits against `harsh/mvp@b739bd5c`,
**2026-08-22** — was re-measured rather than read, under the programme's own rule: *a measurement
read six weeks later is a claim.*

## ⛔ First, the vocabulary, because it is why this looks misaligned and is not

The matrix numbers **seven** layers; YCW27 has **six** folders. `genios_engine/LAYERS.py` documents
**four** vocabularies in its header, including the collision:

    package     layer   name                       Atlas   PRODUCT (the YCW27 folders)
    capture       1     Enterprise Signals           1       L1
    context       2     Situation Intelligence       2       L2 + L3
    packs         -     Plane D · Domain Expertise   3       into L2
    reason        -     Plane R · Reasoning          4       L2 + L4
    executive     5     Executive Intelligence       5       L4
    deliver       6     Intelligence Distribution    5.2     L5
    feedback      7     Learning Engine              6       L6

So **"layer 1, layer 2, layer 3" in the YCW27 vocabulary spans Atlas L1, L2, L3 and L4**, with both
planes inside YCW27's L2. `packs` and `reason` carry dashes on purpose: *a digit implies a position
in a pipeline; these two are what `context` reasons WITH.*

⛔ **I nearly filed this as the programme's largest defect** — five of six folder names contradict
`LAYERS.py`'s digits. That file explains the collision in capitals and states the rule: **"always
name the package, never the digit alone."** Reading it first stopped the finding. Fifth instance in
this programme of reading the thing a name points at before writing anything down.

## Both planes are in good standing. What changed is the Atlas's description of them.

> ⛔ **READ THE VERDICT COLUMN AS A VERDICT ON THE ATLAS'S OLD CLAIM, NOT ON THE PLANE.**
> An earlier draft of this table put the word *FALSE* in a column headed "Now", beside the row
> labelled **Plane D**, and it scanned as *"Plane D: false"* — the exact opposite of the
> measurement. **Plane D is complete: 155 capabilities, every one admitted, zero hollow.** The
> accusation is what expired. Corrected 2026-10-01 rather than deleted, because it is the same
> defect this programme has now paid for seven times: a label that reads as a status somebody
> checked.

| | The Atlas claimed, 2026-08-22 | Measured 2026-10-01 | That claim today |
|---|---|---|---|
| **Plane D** | *"**Stub.** Admin: 57 files, all 57 stubs, zero reviewed/accepted, zero routes"*, and *"zero reviewed or accepted"* across the corpus | Admin **59 capabilities, all admitted, 0 hollow, 34 situations**; corpus **155, all admitted, 0 hollow** | ⛔ **the claim has EXPIRED** — the corpus was authored since |
| **Plane R** | *"Seventeen registered; the manifest schedules roughly six. Registered is not active"* | `CORE_UNITS` **17**, `BUILTIN_CAPABILITIES` schedules **7**, and **22 of 23** units run in production; registry and production agree exactly | **counts were exact; the conclusion has expired** |

**Plane D's matrix entry expired because the corpus was authored out from under it.** The code had
already met this exact failure: `capability_resolver._hollow` carries its own dated retraction —
*"THAT COUNT IS HISTORY, NOT A FACT ABOUT TODAY'S CORPUS, AND LEAVING IT UNMARKED COST A PLAN"* —
and fixed it by moving the count into **a function a test can run** (`corpus_health()`). The matrix
has no such function, which is why it had to be re-measured by hand.

## ⛔ The finding: a third kind of silence, and exactly one unit in it

`core.relationship` — **929 runs, 0 completions** — escaped both existing grains:

* not `DeclaredSilence`: that receipt filters `where status = 'completed'`, and a unit with no
  completed rows **is not a row with a low share, it is not a row**
* not `UnwrittenFact`: it binds `deal.status`, which has **3 rows**, and that declaration is for
  paths with *zero*

> **A unit that never completes is not a quiet unit; it is an absent one, and a question asked only
> of completions cannot see it.**

The fact had been written in prose **twice** — in `receipts.py`, and inside
`DECLARED_SILENT["core.impact"]`'s own reason as an argument for a *different* unit's entry — and
declared nowhere a receipt could read.

**Built:** `NeverCompleted`, the third grain, demanding the **run count** beside reason/mover/date
because that separates *absent* from *never scheduled* (`runs <= 0` refused at construction, so
`core.signal_composition`'s 0 runs cannot be mis-filed). A 30th receipt whose only difference from
its sibling is one clause. 17 tests, mutation-proved.

⛔ **My first version would have made that receipt permanently red** by reporting `core.policy`
undeclared, when all four paths it binds are already in `DECLARED_UNWRITTEN`. Closed with
`starved_by_declared_paths()`, derived from the roster — hard-coding the id would have put one fact
in two places and gone stale the moment a path gained a writer.

⛔ **And my own measurement manufactured a finding first.** It reported *"6 registered units never
ran"*; five had run thousands of times. The six supplementary units carry no `unit_id` class
attribute and are identified by `spec.reasoner_id` on an **instance**, so the id helper returned
class names. The artefact was indistinguishable from a real finding until the run counts were read.

### State after the re-check

    30 receipts, fleet-wide   22 PASS · 7 FAIL · 1 ERROR     (was 21/7/1 of 29)
    remaining Plane D gap     23 DRAFT situations, and they are TWO states: 18 draft+unreviewed
                              (need a reader) and 5 draft+APPROVED (need one word). Corrected
                              2026-10-01 — see 14-PLANE-D-AND-R; 'unreviewed' was wrong for 5
    remaining Plane R gap     core.signal_composition, 0 runs — ALARM A2, roster activation
