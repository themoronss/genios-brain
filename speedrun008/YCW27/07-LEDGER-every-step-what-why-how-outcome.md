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

---
---

# 2026-10-01 · L4 RE-CROSSCHECK — the step with no build in it

| | |
|---|---|
| **Task** | answer doc 17's PART 9 question: *is the 150 expired cards a delivery defect, or the downstream shadow of H2?* |
| **Why it mattered** | it decides whether L4 needs building. Planning an L4 build on the wrong cause would have produced correct code for a problem that does not exist |
| **Expected** | one of the two named causes, and then an L4 build plan |
| **Outcome** | ⛔ **neither cause. Two blocks, at two different places, and L4 needs no build work at all.** Nothing was built, and that is the finding |

## How it was done — measure which things STOPPED, never name a cause

    1  the last timestamp of every stage
         L1/L2/L3 wrote rows 2026-09-30 · L4 stopped 09-25 · L5 stopped 09-25
         -> the OCR guess dies here: it would have starved L1, and L1 is running

    2  decompose L4's own gate join by join
         42 open signals survive joins 1-5, join 6 -> 0
         join 6 = core.constraint completed on the run behind the signal

    3  is it the status filter?
         NO — all 2,681 core.constraint rows are 'completed'

    4  then what?
         the 98 runs behind every open signal have ZERO reasoner results of any kind
         because reasoner results only began being written on 2026-09-29

    5  so why did the new era emit no signals?
         2,681 outputs · 8,044 candidates · 7,872 'eligible' · selected_candidate_id NULL on ALL
         outcome_kind: defer 2,669 · blocked 12 · decision ZERO

    6  read the component VALUES, not the key names
         impact 7,351 · risk 1,758 · effort 6,610 · urgency 5,182 · success 6,658
         formula_utility 5,469   ✅ THE DETERMINISTIC SCORER IS HEALTHY
         llm_utility         0   ⛔ zero on all 8,044
         final_utility_bp    0   ⛔ zero on all 8,044

    7  ⛔ BEFORE CALLING IT A DEFECT — read the module
         llm_decision_maker.py:20 "Failure is DEFER, never the formula."
         GENIOS_L4_LLM_DECISION_MAKER = true, no allowlist -> every org

    8  and re-run STEP-02's own diagnostic rather than assuming it was superseded
         seats 1 ✅ · channels 1 ✅ · reporting_line 0 ⛔
         466 escalations: day 1 ✅ · day 3 ✅ · day 7 -> 124 scheduled, 0 fired, 0 targeted

**Step 7 is the whole step.** It was the **tenth** time in this programme that a state would have
been named a defect before the declaration that created it was read — and the first nine are
listed in doc 17 PART 4.4.

## What it produced

| | |
|---|---|
| **DECISION #5** | three options, one line, Rohit's. Recommendation: **B now, C as a unit, A when the budget allows** |
| **F6–F12** | seven findings in `layer-4-executive/03-FINDINGS.md` |
| **six units** | `layer-4-executive/02-PLAN.md` round 2 — four buildable, two blocked on a product number |
| **a correction** | doc 17 PART 9's open question is answered; PART 8 raises R2 from 🟠 to 🔴 |
| **a narrowing** | STEP-02's finding stands, scoped to the **ladder** rather than the queue's input |
| **code written** | ⛔ **none** |

## The doctrine rules this step produced

> ⛔ **A deliberate refusal to degrade is still a stop.** The design was right that a measurement
> must not be faked. What nothing declared is that **the measurement mode is the production mode**
> — so a budget ceiling became a full product outage with six layers reporting healthy.

> ⛔ **Measure which things stopped, never name a cause.** Both obvious explanations were refuted
> by one query over thirteen tables' last timestamps.

> ⛔ **A gate is decomposed, not read.** Ten joins, added one at a time, named the exact one. The
> same gate read as prose would have suggested the authority predicate, which never ran.

> ⛔ **Re-run the earlier step's own diagnostic instead of assuming it was superseded.** STEP-02
> built `readiness.py` for exactly this question; running it turned "superseded" into "narrowed,
> and it cost 124 escalations".

> ⛔ **Read the component VALUES, not the key names.** All seven score components were present on
> all 8,044 candidates. The presence check says healthy; the values say one is zero.

---
---

# ⛔ L5 DELIVERY · the re-cross-check and five steps · 2026-10-01

Read **reverse-chronological**: the newest step first, because *start at the newest row*. Folder:
[`layer-5-delivery/`](layer-5-delivery/) — 25 files, 4,130 lines.

**Entry point:** `05-RECROSSCHECK-the-silences-of-the-delivery-spine.md` → `06-AUDIT` → `07-AUDIT` →
the step files. ⛔ The two audits **correct the re-cross-check's own numbers**, which is why they are
read second rather than skipped.

---

## The shape of the whole layer, in one table

| | |
|---|---|
| `deliver/` | **40 files · 9,431 lines** — the largest layer in the product |
| public functions (top-level) | **123** |
| ⛔ not called by production | **24** → **25 declared** after STEP-13 and STEP-14 moved two |
| production receipts carrying L5 | **2 → 3**, and one of the three still **ERRORs** on `0190` |
| Atlas L5 badges superseded | **3**, two of them by this programme four days earlier |
| ⛔ architecture the Atlas never mentions | **Layer 5.2** — six modules, five phases |

⛔ **The one-line verdict: `deliver/` is the most heavily built layer in the product and the most
lightly guarded.** Nothing in it was wrong the way L4's queue was wrong; what it lacked was the
machinery every sibling package already had for saying what it deliberately does not do.

---

## STEP-17 · nine packages nobody asked the question

| | |
|---|---|
| **the task** | only `executive/` and `deliver/` had a reachability guard. **147** public functions across the other nine were unreached by production and declared nowhere — and *a guard that exists in two places out of eleven reads, from either of those two, as a solved problem* |
| **expected** | a level: nine units, one per package, in data-flow order |
| ⛔ **what came out** | **one guard over eleven packages, and a scope of 109 rather than 147.** A function is reached FOUR ways and only three can be measured: a call, a decorator, ⛔ **a reference** — 46 of them, `platform/auth.require_owner` has **35** references and zero calls — and ⛔ **duck-typed dispatch, which cannot be measured at all** |
| ⛔ **46 entries would have been lies** | declaring the 123 without measuring references would have filed `require_owner`, twelve dispatch-table readers, twelve feedback units and five MCP tools as deliberate silences. **`mcp/` went to ZERO and needs no declaration module** |
| ⛔ **and one rescue by hand** | `realtime.purge_expired` looked unreached and claimed *"(maintenance heartbeat)"* — **it is called** behind a `hasattr` at `api/routes.py:964`. Retention IS enforced, and I was one grep from a false *stale comment* finding. Sixteen other candidates were name collisions (`list.extend` 96, `Path.resolve` 74) |
| ⛔ **the sharpest finding, already written down by the code** | `need_executor.py:125` names `context/evidence_need_store.read_open_needs` and adds *"which this layer may not import."* **`capture/` is layer 1, `context/` is 2 — the EvidenceNeed executor cannot read its own queue.** Four functions, one with **22 test callers**, broken at a layer boundary. The Atlas listed EvidenceNeed as VERIFIED MISSING when this programme began |
| **code** | `platform/reachability.py` (shared, imports nothing from the engine) · **8 new declaration modules** · 2 existing pointed at it · **109 entries** · 71 tests |
| ⛔ **why it moved to `platform/`** | not "a third user" — **the layer topology.** `capture/` is layer 1, so `capture/ -> executive/` is an UPWARD import the build fails over. *The eleventh package could not have imported it from where it was* |
| ⛔ **three faults of mine** | the self-exclusion was a hand-maintained list I forgot to extend **within a minute** · the generic mover check failed on two CORRECT tables · and the decorator check took a union instead of going per module — **the same collision class the qualified resolver exists to fix** |

---

## STEP-11 · the Atlas does not know Layer 5.2 exists

| | |
|---|---|
| **the task** | put L5 on the Atlas scorecard, date the superseded badges, and write down the architecture the document omits |
| **expected** | *"a document correction, not code"* |
| **what came out** | `08-ATLAS-SCORECARD-L1-to-L4.md` → **`-L1-to-L5.md`**, 35 → **45 claims**, 125 → **200 lines**. L5 contributes **5 superseded, 1 OMISSION, 2 imprecise** — the least accurate layer in the Atlas, and **three of the five supersessions were created by this programme four days earlier** |
| ⛔ **the omission is the finding** | six modules, five phases, named **nowhere**: `presence` · `orchestrator` · `spine` · `tracker` · `units` · `analytics`. **A `gap` badge on built work costs a wasted unit; an OMISSION costs a rebuild**, because nothing tells you to look. L2 paid six units for one absent fact |
| ⛔ **and it was not only a document correction** | `STEP-10`'s two receipts failed a test in `tests/executive/` — a directory **neither targeted run touched**. It asserted `sum("channel" in c for c in claims) == 1`: **it counted the WORD, not the QUESTION.** The two receipts are opposite-conditioned (`from org_channels`, passes > 0 · `from delivery_outbox`, passes == 0 and only counts when a channel exists) and cannot disagree |
| ⛔ **rewritten stricter, not looser** | it now counts receipts whose **outer subject** is `org_channels`, catching a duplicate even if its claim never says "channel". **And my first attempt at that was substring-shaped too** — `"from org_channels" in r.sql` caught the new receipt via its `EXISTS`. Two substring guards in a row, the second mine |
| **also** | doc 17's **live** pointer updated; `STATUS.md`'s **historical** row dated rather than rewritten — *a log records the state on the day it was written*, the rule that keeps `receipts.py:190`'s numbering correct forever |

---

## STEP-10 · two receipts for nine thousand lines

| | |
|---|---|
| **the task** | L5 is **9,431 lines** and carried **2 of 33** receipts — 4,715 lines per guard against L4's 881 — and one of the two **ERRORs** until `0190` lands. So the layer that physically touches the customer had ONE working production guard |
| ⛔ **CORRECTED 2026-10-02** | `L5` is a hand-written LABEL, not a package. `deliver/`'s four tables are guarded by **8** receipts (4 labelled `L5` + 4 labelled `L6`); before YCW27 by **5**, of which **4 worked**. **1,886** lines per guard, not 4,715 — and 1,886 was already true before this pass began. → [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md) |
| **expected** | four candidates, *"each one gets a scope measurement before it is written"* |
| ⛔ **what came out** | **two of five could not fail, and that is the valuable half.** A delivery row with no attempt is 0 forever while nothing calls `spine.materialize`; a card delivered on an adapter-less channel is impossible because the send path parks first; and the `UNDELIVERABLE`-vs-`failed_terminal` separation is a CODE property already guarded by a test |
| ⛔ **the window was measured** | my instinct was one hour. `sweep_lifecycle` runs on the heavy tick, and `config.sync_interval_hours` is **6.0** — so one hour would have fired on every card that expired in the normal gap between ticks. **Latency reported as an alarm**, and *the fix for a false alarm is always to loosen the check.* Twelve hours = two cycles, asserted arithmetically |
| ⛔ **and L4's docstring promised a guard that did not exist** | it ends *"L5's own count is guarded in `tests/deliver/test_nothing_dies_of_low_confidence.py`"* — that file held only presence filters. In `STEP-06` I read it and concluded there was no L5 count guard: **I was right and the docstring was wrong.** The guard now exists where it points |
| ⛔ **eleven of my own references rotted** | inserting two receipts moved `STEP-06`'s from **#21 to #23**. Every test filtered by CLAIM and stayed green; eleven document cross-references and one filename did not. **But `receipts.py:190` quotes numbers under *"Measured 2026-10-01"* and is correct forever** — a snapshot's numbering is part of its measurement |
| ⛔ **and a test failed on its own assertion string** | it scanned its module for `len(receipts(None))` to forbid a global total, and that text is in the `assert` forbidding it. **Seventeenth instance**, first where the match was the guard itself. Deleted with the reason recorded |
| **code** | 2 receipts + the L5 count guard · 11 tests · 6 mutations · receipts **33 → 35**, L5 **3 → 5** |

---

## STEP-15 · a card must become deliverable the moment a channel exists

| | |
|---|---|
| **the task** | call `outbox.revive_undeliverable` — *"the answer to 'a card must become deliverable the moment a channel exists'"*, with the alternative designs it rejected listed in its own docstring — which had **no caller** |
| **why it mattered** | a tenant registers Slack on Tuesday, and every card parked before Tuesday — parked ONLY because there was nowhere to send it — stays parked forever |
| **expected** | wire it at one of three candidate triggers, and **add an `expires_at` bound** |
| ⛔⛔ **what came out** | **the bound would have caused harm, and the docstring had already said so**: *"Waking an old message and letting the authority check kill it is strictly better than leaving it dead, because the second option cannot tell 'we chose not to send' from 'we lost it'."* **Third retracted fix in the programme**, and like F9 and F10 it was caught by reading the thing being changed |
| ⛔ **and the trigger had a trap** | `org_channels` has TWO writers. `platform/seats.py` writes the `in_app` PULL surface and says *"Making that row a transport is what produced production's entire delivery history: 3 rows, all `failed_terminal`."* So the gate is `deliverable_channels` — never a hand-written `if body.active`, because *"every historical delivery failure in this database is one of [its two conditions] being assumed rather than checked"* |
| **code** | `api/channel_routes.set_slack` revives inside the upsert's transaction, count returned · 12 tests · 6 mutations |
| ⛔ **the milestone** | **`KNOWN_UNWIRED` is EMPTY.** Five defects when `STEP-05` drew the table; `STEP-14` closed three (two by **reclassifying** them as build-time guards), `STEP-08` one, this step the last |
| ⛔ **and a third membership list of mine broke** | written in `STEP-08` — **the step where I wrote the rule against it.** *A doctrine applied only to the instance that produced it is not a doctrine* |

---

## STEP-09 · the gate writes down why it refused

| | |
|---|---|
| **the task** | call `gate.describe_decision` — *"the loggable record of one admission"* — which was in `__all__` and called by nothing |
| **why it mattered** | `gate.admit` had written the purpose down years earlier: *"so the caller can put the resolved settings into the audit row. 'It was held because quiet hours' is only half an answer; '…and this tenant's quiet hours are 21:00-08:00 Asia/Kolkata' is the half that ends the support ticket."* |
| **expected** | *"wire it or declare it"*, and the plan called it **the lowest severity of the four** |
| ⛔ **what came out** | **a THREE-part unit, and the plan had none of the three right** |
| ⛔ part 1 | both refusal paths are handed `(decision, context)` and wrote `{"reason": …}` — one key, not even the contract's name for it. ⛔ **And `_defer` took `context` and read nothing from it.** Neither candidate sink was right: `spine.log_delivery_event` is *the right table, the wrong call*; `store.log_event` is card-scoped. **The answer was `_mark_lifecycle`'s own `detail` dict, which the plan never listed** |
| ⛔ part 2 | `describe_decision` was **not keeping its own docstring's third promise** — *"and the settings behind it"* read only `config_error`. The settings are `to_semantic_dict()`, which is literally `admit`'s worked example (`timezone: Asia/Kolkata`, `quiet 21→8`), 437 bytes. ⛔ **And it was already exposed on the PREVIEW endpoint** — a dry run could show a founder their quiet hours while the live refusal recorded none |
| ⛔ part 3 | `GET /delivery/results/{id}` selected `kind, occurred_at, actor` and **not `detail`**. **Nothing in the engine read `delivery_events.detail`** — so the writer alone would have been decoration. **The reader is half the unit**, and it is one word in one SELECT |
| **code** | `gate.py` + `outbox.py` (both paths) + `api/delivery_routes.py` · `UNREACHED` 11→10 · 13 tests · 6 mutations |
| ⛔ **and the contract caught me** | a test built a `SUPPRESS` decision carrying a `not_before`. `DeliveryDecision` refused it — *"only a deferral carries a clock."* **The contract knew something my test assumed away** |

---

## STEP-08 · the headline fix nobody wired

| | |
|---|---|
| **the task** | call `card_builder.resolved_person_name`, which carries its own measurement — *"35 of 38 person cards named an address in the headline"* — and had **zero callers anywhere, including tests** |
| **why it mattered** | the headline spent its 60-character budget on `maria@alystventures.com` while the real name sat one join away on a `mention:person` observation |
| **expected** | one line |
| ⛔ **what came out** | **one line, and it needed two decisions the plan did not have.** The resolver must go **LAST** in a chain whose precedence is load-bearing (`outreach.counterparty` is a FACT; a mention is an OBSERVATION), and it must be **gated** on `node_type == "person"` — ungated, a **company** card is renamed after whichever of its people spoke first |
| ⛔ **and a fifth stale statement** | the function's own docstring said *"the invention guard rejected any draft that wrote 'Maria'"*. It does not: `render._corpus` appends `q["name"]`, so the name is grounded. **The grounding half of the defect was already closed; only the headline half was open** |
| ⛔ **the 35 was not re-measured** | no database URL in this checkout, and `GENIOS_ALLOW_PROD_WRITE` is never set to run a report. **The wiring is justified by the function being correct, not by the number** |
| **code** | one line in `card_builder.py` + its docstring · `KNOWN_UNWIRED` 2→1 · 14 tests · 6 mutations |
| ⛔ **a test of mine failed twice** | `test_the_defects_are_not_filed_as_decisions` hard-coded the defect list. The first repair **diagnosed it and left the names in**. Rewritten as an invariant — *a membership list shrinks every time the work succeeds; an invariant does not* |

---

## STEP-07 · four comments that read as measurements

| | |
|---|---|
| **the task** | correct two stale comments and guard the general case |
| **why it mattered** | `push.py:19` claimed an unreached function was *"fired by L5 when a card is emitted"*; the next person asking *"do agents get notified?"* read that parenthesis and answered yes |
| **expected** | two edits, one test |
| ⛔ **what came out** | **four** stale statements, and the fourth was in the **docstring of the test that guards the behaviour** — so anybody checking whether the claim was guarded found a test repeating it |
| **also** | `push.py` announced *"Two flavours"* and listed **one**: a deleted bullet had left its tail behind, parsing as English attached to the wrong bullet |
| **code** | 4 corrections · `test_a_comment_is_not_a_measurement.py`, 6 tests, 5 mutations · baseline 35, restore 35 |
| ⛔ **not guarded** | correction #4. Restoring that docstring sentence would fail nothing, and that is written down rather than papered over |

---

## STEP-06 · the cutover nobody guards

| | |
|---|---|
| **the task** | make it impossible to take the v2 spine cutover with its ambiguity-marker unwired |
| **why it mattered** | `spine.recover_expired_claims` — *"we must never silently retry over that ambiguity"* — was exercised by **nothing: not production, not a test** |
| **expected** | a guard, a receipt, and the recovery's first tests |
| ⛔ **what came out** | the guard works — **mutation M4, one production call to `claim_due`, turned 4 tests red**. And the step's own claim that the cutover had *no* measurement was **wrong**: `outbox.shadow_resolve_v2` measures tier 1 of four |
| ⛔ **the design decision** | the recovery joins the fence; `claim_due` rewrites it on reclaim — so the **permanently lost** orphans can never match. Receipt #21 is deliberately **fence-free** |
| **code** | receipt #21 (L5 2→3) · 14 database-free tests · ⛔ **4 tests written and NOT RUN** |
| ⛔ **honest gap** | `tests/test_delivery_spine.py` needs real PostgreSQL; all 7 of its tests skip here. **A skip is not a pass.** → `HANDOFF-HARSH.md` **H6** |

---

## STEP-14 · the recall guard nothing calls

| | |
|---|---|
| **the task** | wire `lane_recall`, built on 2026-09-30 with 24 tests and imported by nothing |
| **why it mattered** | `pipeline.py:516` was **reasoning about `recall_verdict`'s correctness** in a comment — the code was shaped around a verdict nobody computed |
| **expected** | three unwired functions to wire |
| ⛔ **what came out** | **one**. The other two take no production data at all — one takes **no arguments** — and the module header says *"PURE. No I/O, no clock, no model."* Wiring them would have re-derived a settled question on every org on every tick |
| ⛔ **and my harness lied** | the mutation run never re-established a baseline, so a stale `STEP-05` assertion inflated every count — **and hid a surviving mutation** |
| **code** | `recall_verdict` wired into `build_cards_for_org`, warning and never raising · 12 tests · `KNOWN_UNWIRED` 5→2 |

---

## STEP-13 · a call resolved by name alone

| | |
|---|---|
| **the task** | promote the precise resolver and **re-derive L4's declaration against it** |
| **why it mattered** | `queue.claim_due()` in `capture/` — a different function — made `deliver/spine.claim_due` read as reached, hiding a whole tier of the v2 path |
| **expected** | *"nothing changes in L4"* |
| ⛔ **what came out** | L4's existing 5 entries **were** clean — and **five more were missing.** `executive/readiness.py` is an **entirely unreached module**; `is_terminal`/`is_open`/`is_live` are **three** spellings of one closed set, two with no docstring, none called |
| ⛔ **the largest finding in the programme** | **147** public functions engine-wide, unreached and declared nowhere — **18** hidden by the collision, **129** visible all along. Only two packages out of eleven have a guard |
| **code** | `qualified_call_counts` + `_file_bindings` in `executive/unreached.py` · `UNREACHED` 5→10 · 9 tests |

---

## STEP-05 · `deliver/` declares what it does not call

| | |
|---|---|
| **the task** | the declared-silence module `deliver/` was the only large package without |
| **expected** | 4 unreached functions, one table |
| ⛔ **what came out** | **24 unreached** — the "4" had counted `tests/` as callers — in **three** different kinds, so **three tables**: an un-cut-over architecture (12), deliberate silences (7), and ⛔ **defects** (5) |
| ⛔ **the shape IS the finding** | collapsing them would file a broken product promise beside a shim that **raises on purpose**, under one word |
| **code** | `delivery_health.py` · 16 tests · 8 mutations · and ⛔ **five steps the plan did not have** (13–17) |

---

## ⛔ The doctrine L5 produced — ten rules, each one paid for

> ⛔ **Establish the baseline, or the harness is theatre.** A mutation run that never re-runs clean
> cannot tell you what it caught. Mine hid a surviving mutation and I reported it as caught.

> ⛔ **A call resolved by name alone is a call to any function with that name.** The reachability
> form of the blunt grep, failing toward *declaring things reached* — the direction that reports
> fewer problems. The shortest names are the least visible: `read` had 11 apparent callers.

> ⛔ **A resolver that is merely stricter is not more correct.** My first fix reported two live
> functions as dead because both are called through an alias.

> ⛔ **A grep for a known-false phrase matches the record of its own correction.** A factual claim is
> guarded by making the fact derivable and named in one place, never by forbidding its wrong form.

> ⛔ **A guard must not inherit the blind spot of the thing it guards.**

> ⛔ **A function that takes no data cannot be measuring production.**

> ⛔ **An uncalled function on an un-cut-over path is not a bug; it is an unguarded cutover** — and
> the two want opposite fixes.

> ⛔ **A measurement can be present under a name you did not search for.** I searched for both-path
> counters; this codebase calls it a `shadow`.

> ⛔ **A finding's fix is the most likely place for the next instance of the same finding.** The unit
> that closed *"a lane nothing reads"* produced *"a guard nothing calls"*.

> ⛔ **A behavioural test that skips everywhere it is run is not a guard — and a skip is not a pass.**

Also: *a comment that reasons about a guard's correctness is not evidence the guard runs* · *a
declaration can be answering a question the tool cannot ask, and then nothing goes red* · *"I could
not measure this" and "I measured it and it is wrong" are different sentences* · *no file imports
itself* · *a receipt that cannot fail **yet** is not the same as one that cannot fail* · *a reachability
number is meaningless without its source set* · *never pipe a suite run through `tail -5`*.

---

## What is left in L5

| | Item | Whose |
|---|---|---|
| `08` | the headline fix nobody wired — *"35 of 38 person cards named an address"* | me |
| `09` | `gate.describe_decision` — wire it or declare it, by measuring the sink | me |
| `15` | `outbox.revive_undeliverable` — a stated product promise with no caller | me |
| `10` | L5 receipts — 4 candidates, each measured before it is written | me |
| `11` | the Atlas scorecard → `-L1-to-L5`, three badges dated, Layer 5.2 written down | me |
| ⛔ `17` | **nine packages, 147 functions** — a level, and the **last** thing in the programme | me |
| ⛔ `16` | is there a per-recipient hourly ceiling? | **Rohit** |
| ⛔ `12` | `0190` — `insert_card` fails on write without it | **Harsh** |
| ⛔ `H6` | run `tests/test_delivery_spine.py` where a database exists | **Harsh** |


---
---

# ⛔ 2026-10-02 · L6's SECOND PASS, and the correction it forced on L5

## ⛔ THE CORRECTION ON STEP-10 · a receipt's layer label is not a package

| | |
|---|---|
| **the claim** | *"L5 is 9,431 lines and carried 2 of 33 receipts — 4,715 lines per guard — and one of the two ERRORs, so the layer that physically touches the customer had ONE working production guard."* |
| **how it was made** | `[r for r in receipts(None) if r.layer == "L5"]`. ⛔ `Receipt.layer` is a **hand-written string**, and `genios_engine/LAYERS.py` warns in its docstring: *"Atlas 5.2 is our `deliver` (6), and Atlas 6 is our `feedback` (7) — so always name the package, never the digit alone."* |
| **what is true** | resolved by the table each receipt queries, `deliver/` carried **5** receipts and **4** worked. **1,886** lines per guard — ⛔ **already true before the pass began.** Today: **8** receipts, **7** working, **1,252** |
| **why the label is useless for counting** | it follows neither vocabulary: `L3` is `packs/`; `L2`, `L4` and `L5` each span **two** packages. `decisions become tracked commitments` is labelled `L5` and reads `executions` — `executive/`'s table |
| **not retracted** | the two new receipts (each shown able to go red), the three rejections (structurally 0 forever, or already a code property), the 12-hour window from a measured 6.0-hour sweep |
| **why it survived** | ⛔ **no assertion depended on it.** *A guard that asserts the label is correct cannot notice that the label means nothing* — second instance of *a guard must not inherit the blind spot of the thing it guards* |
| **outcome** | 11 documents + 1 test docstring marked **in place**, not rewritten. ⛔ **No label touched** — `receipts(layer)` filters on it, so a relabel changes operator behaviour. Rohit's call |

## ⛔⛔ L6 · the loop runs, and is never questioned

| | |
|---|---|
| **the layer** | `feedback/` — **14 files · 3,111 lines**, the smallest in the product (12 · 2,737 at M14's crosscheck) |
| **the status it carried** | `00-START-HERE.md` said **`COMPLETE`**. M14's three units ARE done; what was complete was **the milestone**, not the layer |
| ✅ **it runs** | `run_learning_sweep` is **inside the heartbeat** (`api/routes.py:1274-1278`), calibration too (`:1247-1264`), org-rule discovery on upload. Weekly per-tenant PostgreSQL claim. **Eleven functions reached from outside the package.** ⛔ The opposite of L5's dead control plane — **so this is a reading pass, not a wiring pass** |
| ⛔⛔ **the finding** | **4 receipts, all four PRESENCE checks** — `expect(0)` False. `deliver/` has **5 correctness of 8**; `feedback/` has **0 of 4**. All four are satisfied by one successful tick |
| ⛔⛔ **and the evidence exists** | `feedback/` writes **19 tables**; **4 are read by nothing** — and each holds exactly the column a correctness receipt needs: `learning_transitions (from_state, to_state)` against the existing `ALLOWED_LEARNING_TRANSITIONS`; `learning_object_evaluations (run_id, policy_revision, sink_reason)`; `learning_input_rejections (seam, reason_code)`; `learning_metrics` |
| ⛔ **two indexes for queries nobody wrote** | `learning_object_evaluations_replay` and `_by_run`. **An index is a statement that a query exists** |
| ⛔ **the defect in its own docstring** | `record_refusal`: *"A refusal that lives only in a return value is indistinguishable from a candidate the model never produced."* The ledger it was promoted into **has no reader** |
| ⛔ **the skips** | **27, and all the same thing**: two files entirely, both `GENIOS_TEST_DATABASE_URL`. *"filled through the routes"*, *"filled through the paths"* — **the two that prove the brains fill** → `H7` |
| ⛔ **two near-misses of mine** | `counterfactual_ledger` *has no writer* — true, and it is a **VIEW**; and the reader scan **undercounts**, because `context/authority_view.py:55` reaches `authority_rules` through a name constant. ⛔ **A name-constant is a read** |
| **the plan** | 10 units, `U01` measured on the day it was planned, **0 built**. `U03`–`U05` are each gated on *can this receipt fail?* → `layer-6-learning/06-PLAN-the-second-pass.md` |

## ⛔ Doctrine this pass produced

| Rule | What it cost |
|---|---|
| ⛔ **a receipt's layer label is its author's intent; the table it queries is what it guards** | STEP-10's headline number, in eleven documents |
| ⛔ **"always name the package, never the digit alone" binds the COUNTER as much as the writer** | `LAYERS.py` said it; the count ignored it |
| ⛔ **a name-constant is a read** | `authority_rules` read as 1 reader and has 3 |
| ⛔ **a presence receipt cannot fail for the right reason** | four of them are one successful tick |
| ⛔ **guards per line counts guards; it does not read them** | `feedback/` has the best ratio in the product and zero correctness guards |
| **a number repeated in eleven documents was derived once** | repetition is not corroboration |
| **a motivation number no step depends on is a number nobody checks** | — |
| **an index is a statement that a query exists** | two of them, maintained on every insert |


---

## S2 · the North Star ledger has never had a writer

| | |
|---|---|
| **the task** | *"a stale `value_state` string"* — `/v1/insights/stats` returned `value_state: "unavailable_no_counterfactual_ledger"` and commented the ledger *"does not exist"* |
| **the gate** | *the fix for a wrong reason is the reason, not the answer* → **measure what is actually missing** before writing a new reason |
| **what the gate found** | ⛔ step 1: nothing branches on the literal. ⛔ step 2: `counterfactual_ledger` **exists** (`0072`, with a receipt) and carries **no monetary column**. ⛔⛔ step 3: the table built for this number is **`macv_ledger`** (`0012`) — *"the North Star … the number the customer can verify"* |
| ⛔⛔ **the finding** | **five occurrences repo-wide and not one is a read or a write** — the migration, the cascade FK, `api/account_routes.py`'s **deletion list**, the retention test, and `docs/LAYER_MAP.md`, which **claimed `feedback/` writes it.** The only code that touches it deletes it |
| **what changed** | the comment (the measurement, quoting the old sentence so the record survives) · `value_state` → `unavailable_macv_ledger_has_no_writer` · ⛔ the **docstring**, stale in both halves · `docs/LAYER_MAP.md`'s `feedback/` cell |
| **what did NOT change** | ⛔ `value_recovered_inr` stays `None`. Reading the empty ledger to report `0` is exactly the defect the handler's own first sentence exists to prevent |
| **the guard** | 18 tests, and the teeth point at the reason: **add an `insert into macv_ledger` and it fails**, naming the three places to update together. ⛔ **6/6 mutations caught, baseline green before AND after** |
| ⛔ **my own fault** | my first guard asserted the false sentence was ABSENT and **failed on the correct fix** — the correction quotes it. ⛔ **The rule was in the docstring directly above the assertion.** 18th instance. Repaired generally: **check attribution, not presence** |
| ⛔ **measured consequence** | **104** source-text phrase-absence guards share that shape. ⛔ *"104 broken"* would be an overstatement — all are structurally vulnerable, which are actually at risk needs 104 readings → `S9` |
| **outcome** | full suite **14,891 passed · 0 failed**. ⛔ **Rohit's:** the MACV writer is a product decision, not a quiet fix |


---

## S3 · a policy that did not load may not learn — Atlas gap #10 CLOSED

| | |
|---|---|
| **the task** | Atlas Layer 7 `#10`'s residue: the `SELECT` had been fixed, the LOAD had not. `_as_tuple` returned `()` for `None`, a dict, a bare string and a list of integers alike |
| ⛔⛔ **the defect** | **a fail-OPEN on an authority list.** A tenant's *"never learn about these targets"* list that failed to read was indistinguishable from *"nothing is blocked"*, and `preflight` returned **`admitted`** for the exact target they meant to forbid |
| ⛔ **the comment that described the missing guard** | the seed writes `cast('[]' as jsonb)` *"so the guard below can tell a deliberate empty policy from one that failed to load."* **There was no guard below.** The database kept the two facts apart and the load collapsed them one line later |
| ⛔ **why the fix could not go in `_as_tuple`** | it received only the value, never the revision, so it **could not** tell an absence from a decision. *A docstring can promise a behaviour the signature makes impossible* |
| **how** | five units, bottom-up: ① `contracts/learning.prohibitions_state` — ⛔ a tuple has no third state ② the resolver that reports WHICH case ③ `preflight`, ⛔ **before** the block-list checks and shared by all three producers ④ `run_learning`, ⛔⛔ **before `_claim_week`** ⑤ ⛔ `run_learning_sweep`'s `skipped_by_reason` |
| ⛔ **the sharpest detail** | **a fail-closed placed after the claim converts a policy problem into a LOST WEEK** — `on conflict (org_id, week_key) do nothing` means a claimed week stays claimed, so a policy fixed on Tuesday would wait until the following Monday. The harm appears only on the *second* tick, so it is asserted on the **AST** |
| ⛔ **the second half nobody had asked for** | the sweep counted skips and never said why — consent-off, already-ran and a **crashed** tenant were one number. **A refusal nobody can see is a silent stop**, worse than the fail-open it replaces. *The reader is half the unit* |
| **the guard** | 40 tests · ⛔ **8/8 mutations caught**, baseline green before AND after |
| ✅ **a false finding refuted** | `knowledge_requires_review` is selected and overwritten with `True` — I began writing *"a column that configures nothing"*. `0045:37` holds `check (knowledge_requires_review)` and the comment *"CHECK-locked true"*. ⛔ **Sixth time verifying first prevented a false finding.** *A redundant read is not a lie* |
| **what I could not measure** | ⛔ whether any stored row holds NULL **today** — the seed's comment implies it was changed, so legacy rows are possible. **That is why the fail-closed is a SKIP, not an exception**: no week is burned, and the tenant resumes once somebody backfills `[]` |
| **outcome** | full suite **14,931 passed · 0 failed**. Atlas L7: **4 CLOSED · 3 PARTLY · 1 LIVE · 3 unmeasured** |


---

## S4 · a silent unit names its producer — Atlas gap #2 CLOSED by refutation

| | |
|---|---|
| **the task** | Atlas Layer 7 `#2`, *"direct personalization evolution is missing"* — the **only fully LIVE** gap after `S3`. Gate: *"measure first: build, or DECLARE"* |
| ⛔⛔ **what the gate found** | **neither.** Both components are built one package down — `packs/brains/behavior_distill.distill` (776 lines → `BEHAVIOR`) and `packs/brains/adaptive_lease.lease_proposals` (301 → `RUNTIME`, 7-day TTL) — and `brain_pipeline.brain_pipeline_proposals` appends both into the **same weekly run**, each in a savepoint, from the line after `run_all_units` |
| ⛔ **why nobody saw it** | the stub (`365cf7a6`, 2026-08-08) **predates the implementation** (`ed1b10c3`, 2026-09-07) by a month, and `ALL_ANALYSIS_UNITS` — the list a reader scans for Layer 7 components — still shows a silent unit where a built one belongs |
| ⛔⛔ **two readers, one wrong verdict** | the Atlas, and this programme, which filed #2 as *"LIVE — and now less visible"*. ⛔ **That note was itself wrong**: *"one step from recording this CLOSED"* — **it IS closed** |
| ⛔ **and a grep made it worse** | `behavior_distill.py:551` reads *"NOTHING wires this adapter today"* — about the optional **LLM labeler**. **A grep hands over a sentence without its subject** |
| **how** | DECLARED, not deleted: `target_policy.DELEGATED` = `{unit: (producer, target, why, mover)}`, with **five links** guarded — the producer exists · does work · the driver calls it · `run_learning` calls the driver · ⛔ **it still emits the declared TARGET** |
| ⛔ **the blind spot it closed** | `S1`'s `durable_from_a_measurement()` reads `UNIT_TARGETS` — `units.py`'s registry — so *"which producer may write which brain"* was guarded for **eleven units** and **unguarded for the two that produce**. *A guard that stops at a package boundary catches nothing across it* |
| ⛔ **a widening I did not make** | `unit_temporary_memory` returns `[]` and `adaptive_lease` writes its sink — but one wants an **explicit human directive** and the other **infers** from card verdicts. **Same sink, different input.** Recording it as a delegation would have been a lie about which capability exists |
| **the guard** | 23 tests, 50 with `S1`'s. ⛔ **8/8 mutations caught**, baseline green before AND after |
| ⛔ **an honest survival** | `M2` survived first time because I placed the stub **before** the real `def` — at module level the last definition wins, so it was dead code, not a stub. **An invalid mutation is not a surviving mutation**, and only a harness that reports the survival can tell them apart |
| **outcome** | full suite **14,954 passed · 0 failed**. Atlas L7: **5 CLOSED · 3 PARTLY · ⛔ 0 LIVE · 3 unmeasured** — ⛔ **no Layer 7 gap is fully live any more** |


---

## S5 · the inbox landed, and nothing consumes it — Atlas gap #1 NARROWED

| | |
|---|---|
| **the task** | Atlas `#1`'s residue: `unit_preference_learning` and `unit_temporary_memory` both `return []` with *"Empty until the inbox lands."* Gate: *declare, do not build* |
| ⛔⛔ **what the gate found** | **the sentence was STALE.** `learning_event_inbox` (0046) exists, is written in production by `reason/moments/store.record_feedback` (via `api/moment_routes.py:746`), is loaded into EVERY weekly batch — and ⛔ **no unit reads it.** `run_learning` counts the rows it drops as `inbox_unconsumed` |
| ⛔ **the comment's own prediction** | *"Empty at both ends today … **but the day something starts writing to that table**, rows would be read and dropped on the floor."* **That day had come.** The reasoning was right; the premise went stale |
| ⛔ **the narrowing** | **the gap is a `kind`, not a table.** Every row is `payload.kind == "moment_feedback"`. A table is a migration; a `kind` is a **SURFACE** where a founder states a preference — ⛔ **Rohit's, and the Atlas's own P1** |
| **what is already built** | `LearningTarget.RUNTIME` · `govern()` → `TEMPORARY` · `publish_runtime` → `temporary_memories` (`expires_at NOT NULL`) · `preflight`'s three expiry checks · `expire_leases` · the inbox's `lease_until`. **The missing input is the whole of the gap** |
| ⛔ **and not a model** | the Atlas, now quoted in the code: *"adding a model directly to empty units would produce eloquent ungrounded preferences. First wire typed evidence"* |
| ⛔⛔ **what was BUILT** | **the layer's first CORRECTNESS receipt.** `feedback/` had 4 receipts, all presence; `inbox_unconsumed` was written into `learning_runs.counts` and read by nothing. Receipts **35 → 36**, correctness **0 → 1** |
| ⛔ **why that claim** | a receipt on `inbox_unconsumed > 0` would be red forever — `receipts.py`'s own rule: *a gate that is always red is a gate nobody reads.* So it guards whether the count is **recorded at all** |
| **the guard** | 27 tests · ⛔ **8/8 mutations caught**, baseline green before AND after. `M4`/`M6` first reported *ANCHOR MISSING — COUNTS NOTHING* |
| ⛔⛔ **my own fault, third of a class in one session** | `assert "batch.inbox" not in units` **failed on correct code** — the corrected docstring explains the inbox. ⛔ **A claim about CODE must be checked against the AST, not the text** — and an attribution window would have been the wrong tool |
| **outcome** | full suite **14,981 passed · 0 failed**. Atlas L7: **5 CLOSED · 3 PARTLY · ⛔ 0 LIVE · 3 unmeasured** |


---

## S6 · the no-silent-drop contract, and an illegal lifecycle edge

| | |
|---|---|
| **the task** | *"the four unread ledgers, demoted to monitoring"* |
| ⛔⛔ **what asking them found** | **two LIVE defects.** (1) all three refusal paths in `run_learning` discarded a reason the callee had computed — `ok, _ = validate_learning(...)` — so a refused proposal was **counted and never named**, and `learning_object_evaluations` recorded only successes. (2) `publisher.publish` wrote **`governed → published`** on every brain publish, and `ALLOWED_LEARNING_TRANSITIONS[GOVERNED]` is `(temporary, human_review, promoted, rejected)` |
| **the Atlas** | *"Every rejected or deferred candidate must retain … **reason code** … A weekly sweep that returns zero objects without this accounting is operationally indistinguishable from broken wiring."* And `L7-30` for the skipped `PROMOTED` hop |
| ⛔ **why nobody saw either** | both ledgers are written and read by **nothing**. `ALLOWED_LEARNING_TRANSITIONS` existed from the start; nothing checked it on that path |
| ⛔ **no migration needed** | `learning_object_evaluations` already carried every field the Atlas asks for, `migrations/0046` **names the held case itself**, and `learning_id` has no FK — so a proposal that never reached `persist` can still be recorded. Checked before writing |
| **how** | three refusal paths record their reason · the missing `governed → promoted` hop · ⛔ `log_transition` **refuses** an illegal edge and an unknown state (`from_state=None` exempt) · two correctness receipts, the legal pairs **derived** from the contract |
| ⛔ **six callers enumerated before the raise** | one — the API review route — uses raw SQL for a deterministic idempotency id; both its edges are legal and a test asserts it from source. **An unguarded writer checked at build time is not an unguarded writer** |
| ⛔⛔ **a retraction I owed** | `07-ATLAS-CHECK` §3 had **retracted** `U03` because the SECOND writer was the repaired approval path. The **first** writer was the one emitting the illegal edge. ⛔ **Un-retracted.** *A retraction needs its own measurement, not a neighbouring one* — fifth retraction, first of a retraction |
| **the guard** | 46 tests · ⛔ **9/9 mutations caught**, baseline green before AND after. ⛔ `M6` — widening the map so the bug becomes legal — is caught by **three** tests |
| **outcome** | receipts **36 → 38**, `feedback/` correctness **1 → 3**, unread ledgers **4 → 2**. Full suite **15,027 passed · 0 failed** |


---

## S7 · the count becomes data, and a lost seam gets a name

| | |
|---|---|
| **the task** | two halves: (b) the unread ledgers' last question, (a) guards per package as DATA |
| ⛔ **(b) what the gate found** | the refusal RATIO was already complete — `org_rule_discovery_runs.counters` holds `candidates`/`admitted`/`refused` per run, in a table that IS read. **The gap was the ledger's other writer**: `store._read_optional_seam` quarantines a failed read, records it, and returned `()` — so a LOST seam reached `run_learning` identical to an EMPTY one (`L7-29`: *expose the empty reason*) |
| ⛔⛔ **(b) a second defect in the same block** | `degraded_seams` read `getattr(batch, "deliveries", ())` and the field is `delivery`, so the delivery seam was reported degraded on **every run, forever**, and `degraded` was always True. *A flag that is always set is a flag nobody reads* |
| ⛔⛔ **(a) the number, derived** | `context/` **50,877 lines / 2 guards = 25,438** — ⛔ **5.4x worse than the 4,715 that triggered `STEP-10`**, which was spent on `deliver/`; `deliver/` is now third-best at 1,431. `packs/` has one PRESENCE receipt and zero correctness |
| **(a) why declared, not parsed** | an outer-`from` resolver fails on **4 of 40** receipts (derived tables), and two earlier parsing attempts produced confident wrong answers. ⛔ Plus a third category, `READINESS`, for claims no package can repair |
| ⛔ **the second direction, twice** | I built the declaration from a dump truncated at 62 chars; direction one called two keys undeclared and direction two called them stale — **both halves of one mistake** |
| ⛔⛔ **a harness defect** | `S7(a)`'s baseline-after failed with a layer `L8` present nowhere in source: **a stale `__pycache__` made a restored file read as the mutant**, biasing toward FALSE KILLS. **All seven harnesses re-run** with caching off — `6·0 8·0 8·0 8·0 9·0 9·0 8·0`, ⛔ **every count identical.** Known only because the harness asserts its baseline AFTER as well as before |
| ✅ **a guard forced its own update** | `S6`'s declared-silence test failed on cue when `S7` gave its ledger a reader, so the `F11` tally moved **deliberately** |
| ⛔ **and one mistake of mine** | I killed a healthy suite run at 64%, reading post-cache-wipe slowness as a stall. **Slow is not stalled** |
| **outcome** | receipts **38 → 40**, `feedback/` correctness **3 → 5**, unread ledgers **2 → 1**. Full suite **15,101 passed · 0 failed** |


---

## S8 · the scorecard reaches the learning layer

| | |
|---|---|
| **the task** | `08-ATLAS-SCORECARD-L1-to-L5.md` → `L1-to-L6`, claim by claim against the master coverage matrix's eleven `L7 Learning` rows |
| ⛔ **the gate caught my own numbering** | I planned it as *"`L1-to-L7`"*. **This scorecard numbers `deliver/` as L5**, so the learning layer is **L6** here, while the matrix labels the same rows `L7 Learning`. ⛔ **Third time the programme has paid for that collision** — after `STEP-10`'s count and the three `L5`-labelled receipts I added to `deliver/` |
| **the result** | 45 → **56** claims · **4 EXPIRED · 4 PARTLY · 3 still true** |
| ⛔⛔ **the direction** | **all four expirations run the same way: the Atlas calls built things stubs.** `L6-06` — *"Behavior cohort builder returns `[]`"* — against a **776-line component wired into the weekly run** |
| ⛔⛔ **four cells hid a defect the Atlas did not name** | `L6-01` the health gate was BROKEN · `L6-09` an illegal lifecycle edge on every brain publish · `L6-10` the module's stated reason is now false · `L6-11` the North Star ledger has no writer. ⛔ **Three of the four sit under badges that read as reassuring** |
| ⛔ **the new defect** | `feedback/reset.py` justified not superseding Behavior with *"an unwired stub … there is no live Behavior Brain content to decay"* — **true when written, false now**. ⛔ **Corrected, not repaired**: the supersession is a governed decision and Rohit's. A **cross-package guard** now ties the prose to the fact, checked by **attribution** because the correction quotes what it corrects |
| **the guard** | 21 tests · ⛔ **2/2 mutations caught**, baseline green before AND after. `M1` survived first time because I removed one marker while two others remained in the window — ⛔ **fourth invalid mutation refused rather than rounded up** |
| ⛔ **paperwork rot** | `08-PLAN-v2`'s order block needed **rebuilding**, like `19-PENDING`'s table (`F33`): eight incremental edits left the v1 `S3` and `S9` lines behind plus a doubled `← next`. *A list edited one line at a time accumulates the lines nobody edited* |
| **outcome** | full suite **15,102 passed · 0 failed**. Scorecard **56** Atlas claims verified or refuted |


---

## S9 · the paperwork, and a finding of mine refuted by its own gate

| | |
|---|---|
| **the task** | `F16` the status counts · `F17` the mover convention · `F18` `wipe_org_data` · `F22`/`F32` the 104 absence guards |
| ⛔⛔ **`F17` RETRACTED** | **my own false finding.** `MOVES WITH` appears **29 times across nine of the thirteen** declaration modules against 115 `MOVES WHEN` — a **convention**, saying what `MOVES WHEN` cannot (*"moves when its PAIR moves"*). ⛔ The gate *"measure the distribution before touching either side"* stopped me tightening a guard onto **29 correct entries**, and `F17`'s own closing line was *"do not tighten one to make it fail"* |
| ⛔ **the mutation executes the refutation** | narrowing `MOVER_FORMS` to `("MOVES WHEN",)` fails **9 modules** |
| ⛔ **a third form DID exist** | one `MOVES ON` in `context_health.py`, normalised. A new guard (+10 tests) rejects a third form ⛔ **without demanding a mover** — three tables correctly have none, and demanding one is the mistake the guard above it records making |
| ⛔⛔ **the 104 guards: the rule, not the rewrite** | a resolver meant to check each guard's phrase against its own target file **resolved 1 of 104** (`inspect.getsource(<function>)` needs an import, not a parse). ⛔ **A resolver that answers for 1 of 104 answers nothing** — an earlier version reported *"0 at risk"* from that sample. The rule is in `tests/README.md`: **prose → attribution, code → AST, SQL construct → text is fine** |
| `F18` closed | `wipe_org_data.py` blamed MATERIALIZED views; `0072` is a **plain** view and says why. ⛔ **No second cause invented** — not recoverable from the file. The fix is right independently: `table_type='BASE TABLE'` excludes every non-table, present and future |
| `F16` closed | three counts, three meanings, none wrong when written. ⛔ **The fix is the date, not the number** — and the command, with `-rs`, because the 27 skips are `H7` |
| **outcome** | +10 tests · **2/2 mutations caught**, baseline green before AND after. Full suite **15,112 passed · 0 failed** |


---

## S10 · the three gaps nobody had measured — the LAST unit of `M14.C2`

| | |
|---|---|
| **the task** | Atlas Layer 7 `#3` outcome reconciliation · `#5` permitted-use propagation · `#6` company reset — the three marked *"not measured"* |
| **the method** | ⛔ measurement FIRST, plan second: there was nothing to plan against until they were measured. Pinned to the Atlas v2 source, claim by claim |
| ⛔⛔ **`#3`** | two clauses already closed — `unique (org_id, execution_id)` makes *"counted once"* a **database guarantee**, `label_class` keeps `unknown` neutral; the third is **blocked behind `#1`**. ⛔⛔ **THE REAL FINDING: the durable ADAPTIVE path is unreachable by ARITHMETIC** (`distinct_days=1` vs a floor of 2, validated **before** governance) — **and the obvious repair springs it.** A tripwire, not a fix: ADR-10 is Rohit's |
| ⛔ **`#5`** | enforcement **PROVEN** on the decision path (audience ⊆ principals; fail-closed on an unknown scope). The rendered surface drops visibility but is **unreached** — all three durable producers declare `ORGANIZATION`. Declared as a PAIR + receipt **41** for the approval path only the data can answer. ⛔ The `VisibilityScope` ↔ `SCOPES` bijection was unguarded |
| ⛔ **`#6`** | the reset **propagates into delivery**, which the Atlas does not credit. Two seat callers are **deliberate**, justified in writing — candidate retired. ⛔⛔ **My own declaration was wrong**: the reader is one layer DOWN and the duplication is **forced by the topology** |
| ⛔⛔ **cost** | **four of my own guards failed their mutations** — a word inside a cited path, `all` vs `any`, a call under `if False`, and a line scan a split SQL string defeats. ⛔ The repair of an existing guard was gated on a **negative control** |
| **outcome** | 69 tests · **27/27 actionable mutations caught** · receipts 40 → **41** · `feedback/` correctness 5 → **6** · ⛔⛔ **0 of 11 Atlas gaps unmeasured** · full suite **15,182 passed · 1,067 skipped · 152 xfailed · 0 failed** |


---

## L3 · the `context/` coverage audit — the worst-covered package, and six retractions

| | |
|---|---|
| **the task** | `S7` made *receipts per package* data and it pointed at `context/`: 2 receipts, 50,885 lines, 124 files — never audited |
| ⛔ **the headline was wrong** | `context/` is heavily tested — **306 test files** import it, only 2 modules of 100+ lines are named by no test (both live and reached), and **both** receipts are CORRECTNESS receipts. The gap is that nothing checks the **44 tables it writes** in production |
| **the method** | every SQL statement in `genios_engine/` **and** `scripts/` — 2,867 — cross-referenced against readers, writers and all 42 receipts, with table-name constants substituted |
| ⛔⛔ **six retractions** | each from a BROADENING: a digit in a table name · a reader in `scripts/` · a mention that was prose · SQL in a module constant · a name constant passed as an ARGUMENT · a printed query that is not a read. **Nine findings survived three broadenings** |
| ⛔⛔ **the near-catastrophe** | 77 org-scoped tables in neither erasure list read as a retention hole including verbatim customer mail. ⛔ **It is not one** — `/reset` keeps the account by contract, ACCOUNT erasure is foreign keys, and a receipt already asks the deployed schema. **Read the endpoint's contract before calling a list incomplete** |
| **what shipped** | `platform/table_coverage.py` (9 write-only tables declared, 2 retractions recorded, `resolution()` reporting 639 unresolved of 2,867) · **receipt 42**, derived from `merge.py`'s own constants · `scripts/context_coverage_report.py` and the generated `05-AUDIT-context-file-by-file.md` · `HANDOFF-HARSH.md` §H8 |
| **outcome** | 37 tests · **11/11 mutations caught** · receipts 41 → **42** · `context/` correctness 2 → **3** · full suite **15,220 passed · 1,067 skipped · 152 xfailed · 0 failed** |


---

## 2026-10-03 · the plan to production, and the audit of all eleven packages

| | |
|---|---|
| **the task** | Rohit: *"plan bana ke do ki kya kya bacha hai, steps wise list do… make everything at production level… write notes to harsh and detailed auditing report"* |
| ⛔⛔ **the crux** | everything is **built**, almost nothing is **live**, and the three things between them — `H1` migrations, `R1` the spend limit, `R2` activation — are **not mine**. Said plainly rather than buried under a list of my own work |
| **the definition** | ⛔ *production level* got **seven checkable conditions**, each from a defect this programme failed to catch. **By them nothing qualifies today**, because the migration and activation conditions fail for everything |
| **the audit** | all **eleven** packages, generated — `20-AUDIT-every-package/`. ⛔ `api/` is the worst on three columns at once and ⛔ **never appeared in `S7`'s ranking**, because *lines per receipt* with a zero denominator does not sort. `contracts/` is the control: 0 receipts **and** 0 tables written |
| ✅ **a list closed** | the original brief's eight VERIFIED-MISSING items: **7 built, 1 declared unnecessary** |
| ⛔ **four defects in my own paperwork** | a declaration column that read 0 for four packages (the module name was derived from the directory) · context-specific prose in a reusable tool · a total added instead of measured, **twice**, the second breaking a correct file count · `164` unreceipted tables where the number is **141** |
| **for Harsh** | the handoff said *"five items"* and has **eight**; it now opens with a do-this-in-this-order table and names the three that are read-only or one command |
| **for Rohit** | `R1`–`R15`, `D1`/`D2`, `P` — stable ids, introduced in the plan and mirrored into `19-PENDING`, because the same item was named four ways across four files |
| **outcome** | 94 affected tests green · `resolution()` 639 of 2,872 (0.222) · plan, audit index and ten new audit pages written · ⛔ **no source behaviour changed** — one report generator was corrected |


---

## 1.1 · the `api/` audit — eleven candidates, eleven retirements, one real finding

| | |
|---|---|
| **why first** | `20-AUDIT-every-package` ranked on *tables written that no receipt asks anything of*, and `api/` led with **28** over a package with **zero receipts**, in the layer a customer touches. ⛔ It never appeared in `S7`'s ranking: a ratio with a zero denominator does not sort |
| ⛔⛔ **eleven retirements** | `decisions` (the route binds the envelope it returned) · `approvals_queue` and `policy_routes.evaluate` (**already declared**, and the declaration is sharper than the candidate) · `learning_objects`' third writer (state only, `for update`, 404+409) · `api_keys`' four writers · `card_events`' eight · `agent_registry` (left as a measurement) · ⛔⛔ **`api/`'s "thin" declarations — my own mis-signal, 25 route handlers are decorator-excluded by design** · the zero-receipts filing (reasoned) · the two "no test names it" columns |
| ✅ **the survivor** | **`learning_objects` is write-once except `state`, and nothing asserted it.** `publisher.persist` states it in its first line and keeps it; the engine holds exactly two updates and both set `state` |
| **the repair** | `platform/table_coverage.WRITE_ONCE_TABLES` + `illegal_column_updates()`, guarded both ways — a value column fails **and** a third updater fails. The producer's half is behavioural, with a double that records every statement. ⛔ **No receipt, deliberately**: the data cannot answer it without reimplementing `semantic_hash` in SQL |
| ⛔ **one mutation survived** | a paren-depth split whose removal changed no answer, because an identifier filter catches the same wreckage. ⛔ **The branch was deleted and the filter named as the safeguard** — a branch whose mutation cannot fail is complexity |
| **outcome** | 22 tests · **10/10 mutations caught** · one audit-index correction · full suite **15,242 passed · 1,067 skipped · 152 xfailed · 0 failed** |


---

## 1.2 · the `platform/` audit — fifteen retirements, and a park the health check excludes

| | |
|---|---|
| **why second** | one receipt over 12,651 lines, 18 writers, 25 unreceipted tables — and ⛔ **the package every other package imports**, so one wrong invariant travels furthest |
| ⛔⛔ **fifteen retirements** | `pipeline_counters` (read through `funnel`'s own accessor) · the four activation tables (⛔ a cross-layer ordering would have to be **invented** — declined) · `use_domain_compiler` (kept in capitals, deliberately) · `org_run_leases` (self-healing, 120 s heart-beaten) · `presence_leases` / `warm_lane_slots` / `rate_counters` / `auth_sessions` / `seat_slice_versions` / … (read through their own modules) · ⛔⛔ **Atlas `L2-02`, which was mine and wrong five minutes after I wrote it** — `LINEAGE_UNPROTECTED` declares it with a reason and a mover |
| ✅ **the survivor** | **`warm_lane` parks a row "for a human" and every reader excludes it.** `_OPEN`, the backlog count and the staleness warning all filter `parked_at is null`; nothing selects a parked row; the prune only removes finished ones. ⛔ A stuck tenant reports a clean lane, and the invisible set **grows** |
| **the repair** | **Receipt 43** — *"no warm-lane row is parked where nothing can see it"* — predicate **derived** from `warm_lane._OPEN`, with the builder asserting the shape so it cannot drift. ⛔ A **precedent**: L1 already makes this claim for `parked_events`, and a test pins that the precedent exists |
| ⛔ **what it handed on** | the mover of a declared silence became a **one-line query** — `H8.5`: how many connector kinds does any live tenant have? **Three or more and `LINEAGE_UNPROTECTED` becomes work** |
| ⛔ **the receipt broke a test** | and the break was the **test's** defect: `[r for r in receipts(None) if "lane" in r.claim][0]` matched three claims, one of them `lane` **inside `plane`**. ⛔ The rule, not the rewrite — one site named its claim, and a guard now fails on any future collision. ⛔⛔ **The guard needed three corrections of its own**, each a rule already written: the AST not the text, a lookup is not an assertion, and a surviving mutation fixed by extracting a pure function rather than deleting the check |
| **outcome** | 23 tests · **16/16 mutations caught** · receipts 42 → **43** · `platform/` 1 → **2** · three stale counts corrected in `HANDOFF-HARSH.md` · full suite **15,266 passed · 1,067 skipped · 152 xfailed · 0 failed** |
