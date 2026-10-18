# L5 · findings — what measuring `deliver/` actually turned up

**Date:** 2026-09-30. Everything here was measured before any code was written.

---

## ⛔ F1 · The defect we created ourselves, one step earlier

```
grep -rn "output_lane\|lane_reason" genios_engine/deliver/   ->   nothing
```

`0189` added the columns. `decision_maker` routes every decision. `domain_shadow` writes both. The
step document promised *"the card layer can group by lane directly."* **Nothing read either.**

**Built, tested, green, and called by nothing** — the eighth instance this programme has found, and
the first of its own making, in a vocabulary added one step earlier to end a different instance of
exactly that.

---

## ⛔ F2 · There is no scalar publication floor in `deliver/`

`M13.C2.U04` said to replace it.

| Where | What is actually there |
|---|---|
| `gate.py` | moment + permission. Its only "floor" clamps a deferral's `not_before` |
| `bands.py` | an urgency band off the score, from **pack config** — *"data, not engine constants"* |
| `reason/runner.py:1133` | ⛔ the score gate — `out["below_gate"] += 1` |
| `executive/explain.py` | already **reads** its receipt: *"real, but not important enough yet"* |

The Atlas's *"confidence 0.64, below the 0.70 gate"* describes the **old** engine; its own
before/after column says so. `U04` became the recall guard. **Correction #9.**

---

## ⛔ F3 · I nearly recorded that the invention validator did not exist

It is at `deliver/render.py:334`, called at `render.py:861`, re-exported by
`executive/validate.py:69`, covered by `tests/test_delivery.py`.

I grepped `reminder_facts` — the name its own docstring uses — found three files, no validator among
them, and was **one sentence away from writing "it was never written" into a cross-check.** It is a
generic function taking `corpus_text`, so its subject's name appears nowhere near it.

> **A conclusion drawn from one name's absence.** Third occurrence: `no_model_wired` (L1), the
> graph-revision guard (L3), this. The only improvement worth claiming is that this one was caught
> before it reached a document.

---

## ⛔ F4 · Three real bugs, found by my own new tests, fixed in the code

**`str(OutputLane.DECISION)` is `"OutputLane.DECISION"`.** It is a `(str, Enum)`, not a `StrEnum`. So
**every in-process caller holding the enum would have been labelled `unrouted`** — and the database
path, which passes plain text, would have kept working and hidden it indefinitely.

**The count and the label gave two answers to one question.** `tally_lane` re-described the raw column
with no reason in hand, and the pair is atomic, so a routed card was displayed as `decision` and
counted as `unrouted` in the same pass.

**The tally described a population nobody received** — and would have made the recall check a
tautology, since the tally and its comparison would be incremented by the same line.

---

## ⛔ F5 · `0189`'s header is now wrong, and a migration cannot be edited

It states the lane is inside `decision_hash`. It was, it broke four replay tests, and it was removed:
`route()` is pure over inputs already in the hash, so **a derived value has no business in a content
hash**. A migration's checksum is its immutability, so the correction is append-only in `0190`, and a
test asserts it is there.

---

## ✅ F6 · What was already right

| | |
|---|---|
| the bridge direction | Executive never imports Delivery; it writes `execution_events` and L5 reads it |
| the outbox | every outbound notification is a **row**, never a blocking call |
| the why-not vocabulary | `below_gate · budget · cooldown · muted · shadow · situation`, written **and read** |
| `COMPARISON_KEYS` | both card paths counted on **every** sweep, before either is retired |
| `card_source` | a situation-less signal is **labelled**, never dropped |
| the band cuts | from pack config, so a small-deal tenant cannot reach `critical` by construction — documented, not a bug |
| `ClaimState` | the epistemic vocabulary already exists, with a model-write permission table |

---

## What changed because of these findings

| Finding | Effect |
|---|---|
| F1 | `lane_display.py`, `0190`, and readers in pipeline / builder / store |
| F2 | `U04` rewritten as `lane_recall.py`; a test now fails if a confidence floor appears in `deliver/` |
| F3 | `claims_ok` **calls** `invention_ok` rather than replacing it; a test pins its existence |
| F4 | three code fixes, each with the test that found it |
| F5 | the correction lives in `0190`, with a test |
| F6 | nothing rebuilt; `claims.py` binds to `ClaimState` instead of inventing a second vocabulary |

---
---

# ⛔ 2026-10-01 · findings from re-measuring `deliver/` AFTER the build

**F1 – F6 above were measured on 2026-09-30, before M13 was built.** Nothing in them is retracted.
These are what re-measuring the same package after the build turned up. Full evidence in
[`05-RECROSSCHECK-the-silences-of-the-delivery-spine.md`](05-RECROSSCHECK-the-silences-of-the-delivery-spine.md).

---

## ⛔ F7 · The live-harm finding that one more grep disproved

**What I was about to write.** `spine.recover_expired_claims` marks an expired claim's unsettled attempt
`unknown` so nobody retries over a provider POST that may already have landed. Nothing calls it.
`claim_due` frees an expired row regardless (`and (claimed_by is null or claim_expires_at < :at)`) and
writes a **new** fence on reclaim, while the recovery matches `a.claim_token = d.fence_token` — so after
a reclaim it can never match. Permanent orphan, silent retry over exactly the forbidden ambiguity.

⛔ **`spine.claim_due` is called by nothing in production either.** Two tests and one
`inspect.getsource` assertion. The production drain is `outbox.drain`, and `outbox.py:838` already said
it: *"Risk was zero only because the v2 path has never written a row yet."* The paths are now
mechanically disjoint — legacy takes `dedupe_key is null`, v2 takes `is not null`.

**The honest finding:** the v2 spine is complete, correct and **un-cut-over**, and the recovery is the
one component nothing exercises *at all* — `claim_due` at least has tests. The cutover, on the day it is
taken, takes a path whose ambiguity-marker has never executed, and nothing would tell anyone.

> ⛔ **New doctrine: *an uncalled function on an un-cut-over path is not a bug; it is an unguarded
> cutover.*** The two want **opposite** fixes — a bug wants wiring now, an unguarded cutover wants a
> guard that fires when the cutover is taken. Fifth time measuring the callers first prevented a wrong
> finding, after `no_model_wired` (L1), the graph-revision guard (L3), `manager_seat_id` (L4), and L4's
> F9/F10, both retracted because the fix would have caused harm.

---

## ⛔ F8 · `deliver/` is the one large package with no declared silence

| Package | Declaration |
|---|---|
| `reason/` | `unit_health.py` — four grains, `neutral_default_boundary()`, `REASONING_ERAS` |
| `context/` | `lane_health.DORMANT_LANES` |
| `executive/` | `unreached.py` — `UNREACHED` (5), `PULL_ONLY` (4), reason **and** mover each |
| **`deliver/`** | ⛔ nothing |

L4's own tooling, using L4's own source convention (engine-only callers, top-level files):
**123 public functions · ⛔ 24 unreached · 0 declared.** Of the 24, **4** have no test caller either.

⛔ **This finding first said 133 and 4.** Both were wrong, both in the direction of reporting fewer
problems: `tests/` were counted as callers and `channels/` inflated the denominator. The correction,
and a defect it exposed in L4's own resolver, are in
[`06-AUDIT-the-measurement-that-corrected-itself.md`](06-AUDIT-the-measurement-that-corrected-itself.md).

And the four are **four different kinds of thing** — which is the whole value of having read them rather
than counted them:

| Function | Kind |
|---|---|
| `spine.recover_expired_claims` | an unguarded cutover (F7) |
| `push.push_card_to_agents` | PULL_ONLY — the pull half works (F9) |
| `card_builder.resolved_person_name` | ⛔ a measured defect whose fix is unwired (F11) |
| `gate.describe_decision` | an unlogged record |

A reader of the package today cannot tell any of the four apart from an oversight. → `STEP-05`

---

## ⛔ F9 · Two receipts for nine thousand lines

| L1 | L2 | L3 | **L5** | L6 | L7 | L4 |
|---|---|---|---|---|---|---|
| 6 | 7 | 2 | **2** | 4 | 4 | 7 |

| Layer | Lines | Receipts | Lines per receipt |
|---|---|---|---|
| L4 `executive/` | 6,167 | 7 | 881 |
| **L5 `deliver/`** | **9,431** | **2** | ⛔ **4,715** |
| ⛔ **CORRECTED 2026-10-02** | — | — | **5** · **1,886** → [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](08-CORRECTION-a-receipt-label-is-not-a-package.md) |

And **one of the two cannot run**: #20 *"every delivered card carries a lane, or is labelled unrouted"*
**ERRORs**, because `cards.output_lane` does not exist until `0190` is applied.

⛔ **So the layer that physically touches the customer has ONE working production guard** — #24,
*"decisions become tracked commitments."* L5 is where a failure is the only kind a customer experiences
directly. → `STEP-10`, `STEP-12`

---

## ⛔ F10 · The agent surface is PULL_ONLY, and the comment above it says otherwise

`agent_api.py` gives agents a working pull surface — `poll_signals`, `get_artifact`, `claim`, `result` —
and `push.py`'s own header says *"Body == the /v1/signals poll projection, so push and poll are
interchangeable."* So a polling agent gets everything a pushed one would.

⛔ But `push.py:19` reads *"`push_card_to_agents` — proactive … **(fired by L5 when a card is
emitted)**."* **Nothing fires it.** The next person asking *"do agents get notified?"* reads that
parenthesis and answers yes.

⛔ **A second stale comment, same subsystem.** `units.py` justifies `PUSH_REQUIRES_ADAPTER` with
*"`get_channel` returns Slack or None — **one implementation**."* It returns Slack **or**
`AgentWebhookChannel`; `channels/agent.py` is 11,906 bytes, the largest adapter in the folder, dated two
days after `base.py`.

> ⛔ **The dangerous combination: the behaviour is correct and the prose is not.**
> `_implemented_channels()` computes the answer at runtime, so `capability_report` has always been
> right. No test fails, no receipt goes red — and the `units.py` sentence is the **justification** for a
> frozen set governing which units can ever report operational. Sixth occurrence of *a stale comment
> reads as a measurement*. → `STEP-07`

---

## ⛔ F11 · A measured defect whose fix was built and never wired

`card_builder.py:610` carries its own evidence: *"35 of 38 person cards named an address in the
headline"* — and a `mention:person` observation carries the real name. Somebody measured 38 cards, found
35 broken, wrote the resolver, and **never called it.** Zero references anywhere.

⛔ The number is probably stale in a known direction: taken before M13 rebuilt the card path, and no
production signal has been routed since **2026-09-25 11:09 UTC**. So the wiring is justified by the
function existing and being correct, **not** by the 35. → `STEP-08`

---

## ⛔ F12 · Three Atlas L5 badges are superseded, two by this programme itself

| Claim | Badge | Actually |
|---|---|---|
| claim-level validation | `target` | **built** — `claim_validator.py` + `claims.py`, M13 STEP-03/04 |
| *"no lanes on the card"* — called **L5's biggest gap** | `gap` | **built** — `lane_display.py` + `lane_recall.py`, M13 STEP-01/02 |
| three delivery failures *"to design out"* | `target` | ⛔ **all three already guarded** |

The three, measured one at a time: **duplicates across paths** → `logical_dedupe_key` + a unique index +
`on conflict` + the two paths made mechanically disjoint + fence tokens. **Card flattening** →
`COMPARISON_KEYS` counts both card paths on every sweep before either retires, plus `slots.py`'s
sentinel guard carrying the fault that taught it (*"Raised severald ago"*, shipped to a reader). **Stale
fire** → four grains in `store.py`: one staleness test shared by claim and upsert, a lease only its own
caller can release, terminal cards that cannot be resurrected, and `window.lapsed` expiry feeding L6.

⛔ Two of the three were changed by **this programme, four days ago, one step before the document that
calls them gaps.** The Atlas is not wrong — it is **superseded.** A wrong claim gets argued with; a
superseded one gets dated. → `STEP-11`

---

## ⛔ F13 · The Atlas does not mention the architecture that is there

`deliver/` contains a five-phase pipeline the Atlas names **nowhere**: `presence.py` (Ph2, Delivery
Context Resolver), `orchestrator.py` (Ph2, seven responsibilities → one `DeliveryObject`), `spine.py`
(Ph3, the durable outbox spine), `tracker.py` (Ph4, the Delivery Tracker), `units.py` (Ph5, the eleven
delivery units and their capability registry), `analytics.py` (Ph5).

⛔ **This is the dangerous direction.** A `gap` badge on built work costs a wasted unit. An omission
costs a **rebuild** — the next person planning L5 from the Atlas plans to build `presence.py`. L2 paid
**six units** for one absent fact. → `STEP-11`

---

## ✅ F14 · What is right, measured rather than assumed

| | |
|---|---|
| `capability_report` | ⛔ **honest and fail-closed.** 4 of 6 push channels have no adapter and 3 of 11 units have no reachable channel — and it says so **per channel**, naming `no_adapter` as **our** gap, not the tenant's |
| the `email` unit | the only one declaring `engine_ready=False`. The honest one |
| `api` / `webhook` declaring `engine_ready=True` with no reachable channel | ⛔ **not a finding.** `engine_ready` is about the engine, `operational` is about the surface, and `operational` is `False` for both. Two fields, two questions |
| the channel seam | *"send failures are RESULTS, not exceptions"* — a throwing channel would smuggle retry policy out of the outbox |
| `in_app` / `dashboard` excluded from needing an adapter | demanding one *"would report the one delivery path that actually works today as broken"* |
| the priority rank | generated from `contracts.delivery._PRIORITY_RANK`, after a text column sorted `background < critical` alphabetically and claimed critical work last |
| `outbox.py:838` | ⛔ **the best sentence in the package** — a hazard found, written down, and closed with a predicate that costs no new column. The standard the rest of this measurement was held to |

---

## What changed because of F7 – F14

| Finding | Effect |
|---|---|
| F7 | `STEP-06` — a guard on the cutover, a receipt for orphaned attempts, and the first test the recovery has ever had. ⛔ **Not** a wiring |
| F8 | `STEP-05` — `deliver/delivery_health.py`, built first because 06–09 write into it |
| F9 | `STEP-10` — per-layer count raised deliberately; every candidate receipt measured before it is written |
| F10 | `STEP-07` — both comments corrected, plus the **general** guard: a declared-unreached function with a comment claiming it is called fails the build |
| F11 | `STEP-08` — wire the resolver, keep the address as fallback, prove the result passes `invention_ok` without weakening it |
| F12, F13 | `STEP-11` — the scorecard renamed to `-L1-to-L5` and the omission written down |
| F14 | nothing rebuilt, and three things I had to stop myself from reporting |

---
---

# ⛔ 2026-10-01 (later) · findings from BUILDING step 05 — the triage of all 24

F7–F14 above were measured before `delivery_health.py` existed. These came out of actually triaging the
24 entries, one at a time, because the guard requires a reason and a mover per entry and **guessing at
any of them is how a declaration becomes decoration.** Full evidence:
[`06-AUDIT`](06-AUDIT-the-measurement-that-corrected-itself.md) ·
[`07-AUDIT`](07-AUDIT-the-second-delivery-architecture.md).

---

## ⛔ F15 · The count was wrong, and the way it was wrong is the lesson

| | Reported | True |
|---|---|---|
| public functions | 133 | **123** top-level (133 counted `channels/`) |
| unreached | **4** | ⛔ **24** |

The **4** is a real number for a different question — no caller anywhere **including tests**. L4's
convention is engine-only callers. ⛔ **Both deviations erred toward reporting fewer problems.**

> **Doctrine: a reachability number is meaningless without its source set.** L4's number has its
> convention written into the test that produces it; mine was written into a document, where nothing
> checks it. `engine_sources()` now lives in code, and `test_the_source_set_is_the_engine_and_not_the_
> tests` refuses the original error — mutation **M8** re-creates it and three tests go red.

---

## ⛔ F16 · A second delivery architecture, connected at one tier of four

The 24 are not 24 accidents. Most are **one architecture**, and the finding is the **gradient**:

| Tier | Modules | Production evidence |
|---|---|---|
| 1 · resolution | `orchestrator.resolve` · `presence` · `audience` | ⛔ **shadow-measured** — `outbox.shadow_resolve_v2` (`outbox.py:1254`), counters `v2_shadow_resolved`/`v2_shadow_unroutable` at `:1441` |
| 2 · persistence | `spine.materialize` · `logical_dedupe_key` · `record_materialization_failure` | ⛔ none. `outbox.py:804`: *"`materialize`, which has no production caller"* |
| 3 · claiming | `spine.claim_due` · `recover_expired_claims` | ⛔ none, and the recovery has **no test** either |
| 4 · policy | `rate_limiter` ×3 · `retry` ×2 | ⛔ none — **nothing imports either module** |

⛔ **`STEP-06` claimed the cutover has no measurement. It has one**, and I searched for a both-paths
comparison rather than for a **shadow**.

> **Doctrine: a measurement can be present under a name you did not search for.** Sixth instance of *a
> conclusion drawn from one name's absence* in this programme.

**What survives is sharper:** the shadow measures **resolution only**, so a cutover would be decided on
routing evidence while the three tiers that touch the network have none. ⛔ `outbox.py:804` also records
a harm that **already happened**: only `materialize` wrote `delivery_id`, and
`feedback/delivery_facts.py` filters on `delivery_id is not null`, so *"a fully working legacy delivery
path still fed L7 zero DeliveryFacts, forever"* until the legacy row's id was reused.

---

## ⛔ F17 · The recall guard this programme built four days ago is an orphan module

`deliver/lane_recall.py` — M13 `STEP-02`, **2026-09-30**, *"prove nothing died quietly"*, **24 tests**.
Three public functions, **9 test callers, 0 engine callers.** Three files mention it and **all three are
comments** — and `pipeline.py:516` is **reasoning about `recall_verdict`'s correctness**, explaining how
the tally was shaped so the verdict would not be a tautology. **The code was designed around a guard
that never runs.**

> ⛔ **Ninth instance of built-tested-green-and-called-by-nothing, and the second of this programme's own
> making.** F1 was the first: `signals.output_lane` written and read by nothing. The unit that closed F1
> produced F17.
>
> **Doctrine: a finding's fix is the most likely place for the next instance of the same finding.** It
> ships under the confidence of having just understood the problem, and the question that got asked was
> *"what should this compute?"* rather than *"who calls it?"*

`lane_recall.py`'s header says **"THIS UNIT WAS REWRITTEN… A CORRECTION TO THE PLAN."** The rewrite was
right about what to build and never answered who invokes it. → **`STEP-14`**

### ⛔ CORRECTED 2026-10-01 while building `STEP-14` — this finding was right about the module and
### wrong about two thirds of its contents

`lane_recall.py` **was** imported by nothing. But only **one** of its three functions was ever meant
to be called by production, and the tell was in the module's own header: **"PURE. No I/O, no clock,
no model."**

```
recall_verdict(counts: Mapping[str, Any])                      ← takes the pass's tallies   ⛔ REAL GAP
low_confidence_is_never_silent(*, floor_bp=DEFAULT_...)        ← takes NO data
every_lane_is_visible_or_deliberately_silent()                 ← takes NO ARGUMENTS AT ALL
```

The second and third ask questions about **code** — they walk the router and the display vocabulary
and return counter-examples. The answer is identical on every run of the same build, so their test
callers are the correct and only ones. ⛔ **Wiring them would have re-derived a settled question on
every org on every tick**, and this finding as first written would have led there.

> **Doctrine: a function that takes no data cannot be measuring production.**

`KNOWN_UNWIRED` went **5 → 2**; the two property guards moved to `UNREACHED` with the reason in each
entry. The one real gap is wired, with 12 tests and 5 mutations — `STEP-14-DONE`.

---

## ⛔ F18 · A stated product promise with no caller

`outbox.revive_undeliverable`: *"Re-open every row this org parked only because it had nowhere to send
it… **This is the answer to \"a card must become deliverable the moment a channel exists\".** The
alternative designs were considered and rejected."* Nothing calls it.

**The parking is correct** — `outbox.py` records that conflating nowhere-to-send with a terminal failure
*"burned the card forever"*, and reports `UNDELIVERABLE` separately for that reason. ⛔ **So it is a
two-part design with one part wired**, and the failure has a shape: a tenant registers Slack on Tuesday,
and every card parked before Tuesday stays parked. → **`STEP-15`**

---

## ⛔ F19 · There is no per-recipient hourly ceiling in the running path

`deliver/rate_limiter.py` implements one — `hour_recipient_key` (*"a shared stream for chat families,
else the seat"*), `reserve_slot`, `release_slot`. ⛔ **Nothing in the engine imports the module.**

A `budget` suppression **does** run: `reason/runner.py:1294`. But:

| | Grain | Status |
|---|---|---|
| `reason/runner.py:1294` | per **rule**, per **node**, **daily** | live |
| `deliver/rate_limiter.py` | per **recipient**, per rolling **hour** | ⛔ orphan |

> **Doctrine: two implementations of one word can be two different questions.** One asks *"has this rule
> fired too often today?"*, the other *"has this person been interrupted too often this hour?"* — and
> the second is the one a founder would feel.

⛔ **A product question, and under option B the deliverable is a deletion**, because a ceiling nobody
wants is dead code with a convincing docstring. → **`STEP-16`, Rohit**

---

## ⛔ F20 · The resolver the whole programme trusts hides a function behind a name collision

`executive/unreached.called_names` counts an `ast.Attribute` call by `attr` — which correctly resolves
aliased imports, and made `queue.claim_due()` in `capture/parked/refetch.py:267` count as a call to
`deliver/spine.claim_due`, **a different function with a different signature in a different package.**
A whole tier of the v2 path was invisible.

⛔ **And L4's own `UNREACHED` uses that resolver for its "has it acquired a caller" direction** — so an
`executive/` function sharing a name with any method in the engine would be silently dropped from that
declaration. Nothing has been shown wrong in L4; nothing has shown it right either.

> **Doctrine: a call resolved by name alone is a call to any function with that name.** The reachability
> form of the blunt grep, failing toward *declaring things reached*.

`delivery_health.qualified_call_sites` is the precise resolver, proven on the collision. Promoting it
into `executive/unreached.py` is → **`STEP-13`**, separate because it changes a tool four L4 tests
depend on. **Noticed something adjacent is a new unit, not a silent fix.**

---

## ✅ F21 · Two functions whose reason is recorded nowhere, declared as exactly that

`routing.is_agent_transport` and `units.get_unit` have **no docstring**. Each has a test caller and no
production caller, and **why they are unreached is written nowhere in the codebase.**

⛔ Declaring them deliberate would invent a reason; declaring them defects would invent a severity. The
entries say what is true — *nobody wrote down what this is for* — and name the mover as whoever knows.
**An honest "unknown" is a declaration; a guessed reason is decoration.**

---

## What changed because of F15 – F21

| Finding | Effect |
|---|---|
| F15 | ⛔ `engine_sources()` in code + the test that refuses `tests/` as callers. Mutation M8 re-creates the error and 3 tests go red |
| F16 | `UNCUT_OVER` carries a **tier** and a structured `measured_by`; `STEP-06`'s justification corrected in place |
| F17 | ⛔ **`STEP-14`** — and three `KNOWN_UNWIRED` entries that must be **deleted** when it lands, not explained |
| F18 | ⛔ **`STEP-15`** |
| F19 | ⛔ **`STEP-16`** — Rohit's, and it should be answered with L4's `U6d` |
| F20 | ⛔ **`STEP-13`** — and L4's declaration must be **re-derived**, not assumed unaffected |
| F21 | declared as undocumented; flagged for Harsh rather than guessed at |


---
---

# ⛔ 2026-10-01 (later still) · findings from BUILDING steps 06, 07, 13 and 14

F15–F21 came from measuring. These came from **building**, which is where a plan's remaining wrong
assumptions surface. Reverse-chronological: the newest row first, because *start at the newest row.*

---

## ⛔ F22 · Four stale statements in one subsystem, and the fourth was inside a test

`STEP-07` planned two corrections. Measuring found **four**:

| # | Where | Said | Truth |
|---|---|---|---|
| 1 | `push.py:19` | *"(fired by L5 when a card is emitted)"* | ⛔ nothing fired it; agents **poll** |
| 2 | `push.py:18-22` | *"**Two flavours**"* then **one** bullet | ⛔ the second bullet was deleted and **its tail left behind**, parsing as English attached to the wrong bullet |
| 3 | `units.py:70` | *"returns Slack or None — **one implementation**"* | ⛔ Slack **and** `agent_push` — **two of six** |
| 4 | ⛔ `tests/test_delivery_units.py:67` | the same sentence | ⛔ **in the docstring of the test that guards the behaviour** |

⛔ **#4 is the shape that defeats checking.** Anybody asking *"is this claim guarded?"* found a test
repeating the claim. Its **assertion** was always right — it is about `teams`, which genuinely has no
adapter. Only the prose was wrong.

> ⛔ **In all four cases the behaviour was correct and only the sentence a human reads was wrong.**
> `_implemented_channels()` calls `get_channel` and counts the answer, so `capability_report` has
> been right all along. **No test failed, no receipt went red.**

### ⛔ And the obvious guard would have failed on its own correction

Asserting that the string `"returns Slack or None"` appears nowhere **fails on the corrected
comment**, which records *"this comment said 'returns Slack or None' until 2026-10-01."*

> **A grep for a known-false phrase matches the record of its own correction.** Seventeenth
> near-instance of a substring check matching the author's own words in this programme, and the
> first where the match would have been the fix.
>
> **A factual claim is guarded by making the fact DERIVABLE and naming it in exactly one place.**
> A missing claim is guarded structurally, by coverage. Neither is guarded by forbidding a phrase.

### ⛔ What is NOT guarded, stated plainly

**Correction #4 has no guard.** Restoring that docstring sentence would fail nothing. Prose in a
docstring is not checkable without reading it for meaning, and the grep alternative is worse than
nothing. Three of four corrections are defended by a test; the fourth is defended by being written
down. → `STEP-07-DONE`

---

## ⛔ F23 · A guard must not inherit the blind spot of the thing it guards

`spine.recover_expired_claims` joins `a.claim_token = d.fence_token`. `claim_due` writes a **new**
fence when it reclaims. So **once a row is handed to a fresh worker, the previous worker's orphaned
attempt can never match the recovery again** — and those are exactly the cases where a retry has
already happened.

The *unsettled-attempt* receipt is therefore deliberately fence-free: `outcome='started'`, `settled_at is null`,
`started_at < now() - interval '1 hour'`, with **no** `fence_token` and **no** `claim_expires_at`. A
receipt built on the recovery's own predicate would have counted only the still-recoverable orphans
and missed every permanently lost one.

⛔ The blind spot is **recorded, not fixed** — changing the join is a behaviour change on a path
nobody runs — and one test asserts the asymmetry **as a pair**, so whoever fixes it is told which
rationale and which test then need rewriting. → `STEP-06-DONE`

⛔ **And four of that step's tests are written and have NOT been run**: `tests/test_delivery_spine.py`
needs real PostgreSQL and this checkout has none, so all 7 of its tests skip. **A skip is not a
pass.** → `HANDOFF-HARSH.md` **H6**.

---

## ⛔⛔ F24 · My own mutation harness proved nothing, and it hid a surviving mutation

The harness restored each file and **never re-ran the suite clean**, so no baseline was ever
established. A `STEP-05` assertion had been failing since `STEP-14` landed — it still demanded
`lane_recall.recall_verdict` be in `KNOWN_UNWIRED`, which `STEP-14` correctly deleted.

| | reported | ⛔ actual |
|---|---|---|
| STEP-14 M1 | 6 failed | 🔴 5 failed |
| **STEP-14 M4** — *raise on an unbalanced verdict* | 1 failed | ⛔⛔ **52 passed. SURVIVED** |
| STEP-14 M5 | 2 failed | 🔴 2 failed |
| STEP-06 M1–M5 | 2·2·2·5·3 | 🔴 1·1·1·**4**·2 — all caught, every number one too high |

**M4's "1 failed" was that stale test and nothing else.** A mutation making the recall guard **kill
the build pass** was caught by nothing, and I reported it as caught.

### ⛔ Why it survived — a defect in the wiring, not only in the test

The guard sits inside `try/except Exception` so a broken measurement cannot kill the pass. M4's
`raise` lands **inside that try**, so the pass's own safety net swallowed a defect in the half that
ACTS on the verdict, wrote `lane_recall_unmeasured = 1`, and returned normally. Every assertion still
held — all were written before the raise.

> ⛔ **"I could not measure this" and "I measured it and it is wrong" are different sentences**, and
> the guard had one state where it needed two.

**Fixed:** the test now also asserts `"lane_recall_unmeasured" not in out`. M4 → 🔴 1 failed.
⛔ **STEP-14's M2 and M3 were not re-run and remain unverified.**

> **Doctrine: establish the baseline, or the harness is theatre.** And never pipe a suite run through
> `tail -5` — one came back `6 failed` with the FAILED list truncated to four names and **two
> unaccounted for.**

---

## ⛔ F25 · A one-line wiring that needed two decisions, and a fifth stale docstring

`card_builder.resolved_person_name` carried its own measurement — *"35 of 38 person cards named an
address in the headline"* — and **nothing called it.** The plan said "wire it". Measuring first found
the line, and two decisions the plan did not have.

| | |
|---|---|
| **the choke point** | `name` in `build_draft` has exactly **two assignments and three uses**: the override chain, then `compute_slots` and `"business_subject"`. ⛔ One edit covers the headline **and** the slots — a change at either consumer would have fixed half the defect |
| ⛔ **the precedence** | the chain already prefers `outreach.counterparty` / `commitment.owed_to`, because *"A SYNTHETIC ANCHOR'S DISPLAY NAME IS NOT THE CARD'S SUBJECT"*. Those are **facts**; a `mention:person` name is an **observation** — so the resolver goes **last**, replacing only the `or name` fallback |
| ⛔ **the gate** | without `node_type == "person"`, a **company** card is renamed after whichever of its people spoke first. `card_builder`'s own comment: a company node's quotes are *"observations of the people who `works_at` it… the card names the company, and these are its people"* |

### ⛔ And the function's own docstring made a claim that had stopped being true

It said *"the invention guard rejected any draft that wrote 'Maria'."* Measured: `render._corpus`
appends `q["name"]` for every quote, so the name **is** grounded —

```
invention_ok("Maria Exconde asked about pricing")   -> PASS
invention_ok("Nikhil Sharma asked about pricing")   -> FAIL  (name:Nikhil)
```

⛔ **The grounding half of this defect was already closed; only the headline half was open.** Fifth
instance of a stale statement in L5 after `STEP-07`'s four — and this one inside the docstring of the
function being fixed. Now **asserted** rather than repeated.

⛔ **My own probe was wrong first:** `'Maria' in corpus` was `False` while `invention_ok` passed,
because the corpus is case-folded. **A substring check against a normalised corpus is not the test;
the validator is.**

### ⛔ What the 35 is worth

Not re-measured — **no database URL is configured** here, and `GENIOS_ALLOW_PROD_WRITE` is never set
to run a report. And the number predates M13's card rebuild, with no signal routed since 2026-09-25.
**The wiring is justified by the function being correct, not by the number that prompted it.**

→ `STEP-08-DONE` · 14 tests · 6 mutations · `KNOWN_UNWIRED` 2 → **1**

---

## ⛔ F26 · A test of mine failed on correct code twice, and the first repair only diagnosed it

`test_the_defects_are_not_filed_as_decisions` **hard-coded the defect list**, so it failed when
`STEP-14` wired `lane_recall.recall_verdict` and **again** when `STEP-08` deleted
`card_builder.resolved_person_name`'s entry. Both deletions were correct — L4 removed
`monitor.blocking_action` from `UNREACHED` on exactly that trigger.

⛔ **The first repair corrected the docstring to say *"the list of defects is not a constant"* and
left the hard-coded names in place.** The same failure arrived one step later.

> ⛔ **A membership list shrinks every time the work succeeds; an invariant does not.**

Rewritten to assert only the invariant: no function in two tables · the fail-closed shim is
permanently a **decision** · the table may shrink only by a function acquiring a caller, checked from
the other side by `undeclared()`.

⛔ **Caught immediately this time**, because the baseline was taken *before* the patch and the
affected set re-run *immediately after*: 310 → 324, 14 new tests, zero regression.

---

## ⛔ F27 · A three-part unit the plan called "the lowest severity of the four"

`gate.describe_decision` — *"The loggable record of one admission"* — was in `__all__` and called by
nothing, while `gate.admit`'s docstring had already said what it was for: *"so the caller can put the
resolved settings into the audit row. 'It was held because quiet hours' is only half an answer; '…and
this tenant's quiet hours are 21:00-08:00 Asia/Kolkata' is the half that ends the support ticket."*

**Three parts. The plan had none of the three right.**

### ⛔ Part 1 · both refusal paths had both halves in hand and dropped one

`outbox._suppress` and `_defer` are handed `(decision, context)` and wrote
`{"reason": decision.reason_code}` — one key, and not even the contract's name for it.
`decision.detail` and the whole resolved context went on the floor at the one seam where both were in
hand. ⛔ **And `_defer` took `context` as a parameter and read nothing from it** — presence without
effect, in the signature.

⛔ **And the sink was not either of the two the plan listed.** `spine.log_delivery_event` directly is
*the right table, the wrong call* — `_mark_lifecycle` exists so the lifecycle column and its event
*"cannot disagree"*. `store.log_event` is card-scoped; a gate decision is about a delivery. **The
answer was `_mark_lifecycle`'s own `detail` dict, which the plan never listed.**

### ⛔ Part 2 · the function was not keeping its own docstring's third promise

*"verdict, reason, **and the settings behind it**"* — and it read only `context.config_error`. The
settings are `DeliveryContext.to_semantic_dict()`, which is **literally `admit`'s worked example**:

```
settings["profile"]["timezone"] -> "Asia/Kolkata"   quiet_start_hour -> 21   quiet_end_hour -> 8
len(json.dumps(record))         -> 437 bytes
```

⛔ **And the capability was already exposed on the wrong path:** `api/delivery_routes.py:168` calls
`to_semantic_dict()` for the **preview** endpoint, so a dry run could show a founder their own quiet
hours while the **live** refusal recorded none of them.

> ⛔ **A function can fail to keep its own docstring's third promise, and nothing will say so.**

### ⛔ Part 3 · the writer alone would have been decoration

`GET /delivery/results/{delivery_id}` selected `kind, occurred_at, actor` — **not `detail`**. That is
the endpoint a support question lands on, and it returned the event *kinds* and not why. `tracker.py`
does `select 1`. **Nothing in the engine read `delivery_events.detail`.**

> ⛔ **A record nobody reads is presence without effect — the reader is half the unit.** One word in
> one SELECT, and mutation M3 removes it and a test fails.

→ `STEP-09-DONE` · 13 tests · 6 mutations · `UNREACHED` 11 → **10**

⛔ **And a test of mine built an illegal object:** a `SUPPRESS` decision carrying a `not_before`.
`DeliveryDecision` refused it — *"only a deferral carries a clock."* **The contract knew something my
test assumed away, and said so at construction.**

---

## ⛔⛔ F28 · A proposed fix that would have caused harm, and `KNOWN_UNWIRED` reaching zero

`outbox.revive_undeliverable` — *"the answer to 'a card must become deliverable the moment a channel
exists'"*, with its rejected alternatives listed — had **no caller.** A tenant registers Slack on
Tuesday and every card parked before Tuesday stays parked.

### ⛔ The plan's own "risk nobody has checked" was already answered, in the opposite direction

`STEP-15 §3` proposed bounding the revive on `expires_at`. The docstring:

> *"Reviving a stale card is SAFE… the drain re-proves authority immediately before every send, so a
> revived row whose card has since expired is `cancelled` on its way out rather than delivered.
> **Waking an old message and letting the authority check kill it is strictly better than leaving it
> dead, because the second option cannot tell "we chose not to send" from "we lost it".**"*

⛔ **The bound destroys exactly that distinction.** Third retracted fix in the programme, after L4's
F9 and F10 — **and all three were caught by reading the thing being changed before changing it.**
`test_the_revive_does_not_bound_on_expires_at` now asserts its absence.

### ⛔ Two writers of `org_channels`, and one is a trap

`platform/seats.py` writes the `in_app` PULL surface: *"It is emphatically NOT a transport…
**Making that row a transport is what produced production's entire delivery history: 3 rows, all
`failed_terminal`.**"* So the gate is `deliverable_channels`, never a hand-written `if body.active` —
its docstring being the argument: *"every historical delivery failure in this database is one of
[its two conditions] being assumed rather than checked."*

### ⛔ `KNOWN_UNWIRED` is now EMPTY — five defects, all closed

`lane_recall` ×3 (`STEP-14`, two of them **reclassified** as build-time guards rather than fixed),
`card_builder.resolved_person_name` (`STEP-08`), `outbox.revive_undeliverable` (this step).

→ `STEP-15-DONE` · 12 tests · 6 mutations

---

## ⛔ F29 · A THIRD membership list of mine broke, and I had written the rule against it one step earlier

`test_one_defect_is_left_in_the_known_unwired_table` asserted
`set(H.KNOWN_UNWIRED) == {"outbox.revive_undeliverable"}`. `STEP-15` emptied the table and it failed
on correct code.

⛔ **It was written in `STEP-08` — the step where I diagnosed this exact pattern**, rewrote the other
test as an invariant, and wrote down *"a membership list shrinks every time the work succeeds; an
invariant does not"* — **then wrote a new membership list a few sections later in the same session.**

> ⛔ **A doctrine applied only to the instance that produced it is not a doctrine.** F26 recorded the
> first repair that diagnosed without fixing; this is the second failure of the same rule, by the
> same hand, in the same session.

Rewritten so an **empty** table is a legitimate state and the history lives in prose, where a log
belongs.

---

## ⛔ F30 · L5 had 2 receipts for 9,431 lines — and two of five candidates could not fail

⛔ **CORRECTED 2026-10-02 — the count in this heading is wrong.** `L5` is a hand-written LABEL, not a package. `deliver/`'s four tables are guarded by **8** receipts (4 labelled `L5` + 4 labelled `L6`); before YCW27 by **5**, of which **4 worked**. **1,886** lines per guard, not 4,715 — and 1,886 was already true before this pass began. The two rejections and the
window measurement are **not** retracted: neither depended on the count. → [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](08-CORRECTION-a-receipt-label-is-not-a-package.md)


| | Candidate | Verdict |
|---|---|---|
| A | a delivery row with no attempt | ⛔ **0 forever** while nothing calls `spine.materialize` |
| D | a card delivered on an adapter-less channel | ⛔ **impossible** — `outbox.py:935` parks first |
| C | `UNDELIVERABLE` kept apart from `failed_terminal` | ⛔ already guarded by a **test**; it is a code property |
| B | a card past `expires_at`, still live | ✅ built |
| F | a row parked for want of a channel, for an org that now has one | ✅ built |

⛔ **The rejections are the valuable half** — *a receipt that cannot fail is not a gate*, and one
asking the wrong question *"goes green and is believed"*.

### ⛔ The window was measured, and one hour would have cried wolf on every tenant

`sweep_lifecycle` runs on `run_maintenance_sweep`'s heavy tick, whose interval is
`config.sync_interval_hours` — **measured at 6.0**. A one-hour grace (my instinct) fires on every
card that expired in the normal gap between ticks: **latency reported as an alarm**, and *the fix for
a false alarm is always to loosen the check*. Twelve hours is two full cycles, asserted
arithmetically against the live setting.

### ⛔ And the rejections are now checkable rather than prose

`test_the_rejected_candidates_premises_still_hold` asserts `spine.materialize` is **still**
un-cut-over and the send path **still** parks on a missing adapter. **If either premise changes, the
candidate becomes viable and the test says so.**

→ `STEP-10-DONE` · receipts **33 → 35** · L5 **3 → 5** · lines per L5 guard ⛔ **1,886 → 1,252** (the **4,715 → 1,886** first written here counted a label; [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](08-CORRECTION-a-receipt-label-is-not-a-package.md))

---

## ⛔ F31 · Receipt numbers are POSITIONAL, and L4's docstring promised a guard that did not exist

**Two things, both found by adding two receipts.**

⛔ **The count guard.** `tests/platform/test_activation_changes_the_pass.py` is the canonical argument
for per-layer counts and ends *"L5's own count is guarded in
`tests/deliver/test_nothing_dies_of_low_confidence.py`."* **That file held only presence filters.**
In `STEP-06` I looked at it and concluded there was no L5 count guard — **I was right and the
docstring was wrong.** The guard now exists *where the docstring points*, so the promise is kept
rather than redirected. L5: **2 → 5**, every addition named.

⛔ **The numbering.** Inserting two receipts moved `STEP-06`'s from **#21 to #23**, and **eleven live
cross-references in my own documents rotted at once** — plus `STEP-12`'s filename, which said
`receipt-20`. Every test already filtered by **claim**, which is why the suite stayed green while the
prose went wrong.

⛔ **But `platform/receipts.py:190` quotes `#19/#21/#22/#14` with values under *"Measured
2026-10-01"*, and that is correct forever** — a snapshot's numbering is part of its measurement.

> ⛔ **Refer to a receipt by its claim, never by its position — unless you are quoting a dated run.**

⛔ **And a test I wrote here failed on its own assertion string** — it scanned its module for
`len(receipts(None))` to forbid a global total, and the forbidden text is in the `assert` that
forbids it. **Seventeenth instance**, first where the match was the guard itself. Deleted, with the
reason recorded in the file: *a convention is enforced by the guard that implements it, not by a test
that greps for its own prose.*

---

## ⛔ F32 · The scorecard, and a cross-layer break two targeted runs had missed

**The scorecard:** `08-ATLAS-SCORECARD-L1-to-L4.md` → **`-L1-to-L5.md`**, 35 → **45 claims**. L5
contributes **5 superseded badges, 1 OMISSION and 2 imprecise** — the least accurate layer in the
Atlas, and three of the five supersessions were created by **this programme four days earlier**.

> ⛔ **A `gap` badge on built work costs a wasted unit. An OMISSION costs a rebuild**, because
> nothing in the document tells you to look. The next person planning L5 from the Atlas plans to
> build `presence.py`. L2 paid **six units** for one absent fact.

**And a code change the step did not plan.** `STEP-10`'s two receipts failed a test in
`tests/executive/` — a directory neither of my targeted runs touched:

```
assert sum("channel" in c for c in claims) == 1     ->   assert 2 == 1
```

⛔ **It counted the WORD, not the QUESTION.** The two receipts are opposite-conditioned — L6 asks
whether a channel exists (`from org_channels`, passes > 0); L5 asks whether a backlog cleared
(`from delivery_outbox`, passes == 0, **and only counts anything when a channel exists**). They
cannot disagree. Rewritten **stricter**: it counts receipts whose **outer subject** is
`org_channels`, so a duplicate is caught even if its claim never says "channel".

⛔ **And my first attempt at that was substring-shaped too** — `"from org_channels" in r.sql` caught
the new receipt via its `EXISTS` subquery. *A receipt's subject is what its first `from` names.* Two
substring-shaped guards in a row, the second mine.

> ⛔ **Two targeted test runs are not a suite run** — written down twice before today. **And an
> arbitrary subset is not a smaller suite**: re-running every receipt-touching file by hand produced
> 8 errors in a file that passes alone and had zero in the full run.

→ `STEP-11-DONE`

---

## ⛔⛔ F33 · A question I put to Rohit that the code had already answered — WITHDRAWN

`STEP-16` asked **"should a per-recipient hourly ceiling exist?"** Its premise: *"there is no
per-recipient hourly ceiling in the running path."*

⛔ **There is, and it is live with a default:**

```
timing.py:59   _BURST_WINDOW = 1 hour       timing.py:86   max_interrupts_per_hour = 3
timing.py:229  count >= limit -> DEFER      (never drops)

outbox.drain(1) -> gate.admit(1) -> gate.evaluate_delivery(2) -> timing.evaluate_timing(1)
rate_limiter.reserve_slot = 0
```

**So `rate_limiter.py` is not a duplicate — it is the RACE-FREE version.** `timing.py` reads
`interrupts_last_hour` and decides; `rate_limiter` atomically reserves. ⛔ **And the gap is
deliberate**: `resolve()` releases its read transaction because *"the connection stops sitting idle
in transaction across an outbound HTTP call"* — holding one across a webhook POST is worse than the
overshoot.

⛔ **And the race cannot happen today**: `Procfile` runs uvicorn with no `--workers`, and
`scheduler.py` uses `ThreadPoolExecutor(max_workers=1)`. **One drain worker.**

So **A** (wire it) is wrong — two limiters on one question — **B** (delete) is wrong — it is the fix
the cutover needs — and **C** was already what `delivery_health.UNCUT_OVER` tier 4 said, three steps
before the question was written.

> ⛔ **Fourth retraction in this programme, and the first where what is retracted is a QUESTION
> rather than a fix.** F9, F10 and the `expires_at` bound were proposed fixes that would have caused
> harm. **This one spent somebody else's attention on a decision that did not exist.**
>
> ⛔ **I read one module and concluded the layer lacked a capability.** `07-AUDIT §4.1` compared
> grains carefully — `rate_limiter` per-recipient-hourly vs `runner.py:1294` per-rule-daily — and
> never asked whether `deliver/` enforced the same thing under another name. **The comparison was
> right and the search was one module wide.** Sixth instance of *a conclusion drawn from one name's
> absence*, and the first to reach Rohit as a decision.

### ⛔ What survived: a latent condition, declared

The ceiling is **exact at one worker and silently approximate at two**, and nothing said so. The
declaration now records it and `rate_limiter`'s mover is **the worker count, not only the cutover** —
so it is wanted the moment anybody sets `--workers 2`.
`test_the_hourly_ceiling_is_exact_at_one_worker.py` pins it: **7 tests, 6 mutations**, and `--workers
4` in the Procfile fails the build.

→ `STEP-16-WITHDRAWN`

---

## ⛔⛔ F34 · A function is reached FOUR ways, and only three can be measured

`STEP-17` set out to declare 147 unreached functions across nine packages. ⛔ **It found two more
wiring mechanisms first, and the scope fell to 109 before a single entry was written.**

| | Mechanism | Found |
|---|---|---|
| 1 | `f()` — a **call** | the resolver already had it |
| 2 | `@router.get(...)` — a **decorator** | 14 route handlers, no Python caller by design |
| 3 | ⛔ `Depends(f)` · `{"k": f}` — a **reference** | ⛔ **46 of 109. The dominant pattern in this engine** |
| 4 | ⛔ `store.purge_expired()` — **duck-typed dispatch** | ⛔ **unmeasurable. Hand-checked, every entry** |

⛔ **`platform/auth.require_owner` has 35 references and ZERO calls.** `get_auth_ctx` 29,
`require_admin` 25, twelve `context/outreach_situations.read_*_for_dispatch`, twelve
`feedback/units.unit_*`, five `mcp/server.tool_*` — which took **`mcp/` to zero** and means it needs
no declaration module at all.

> ⛔ **Had the 123 been declared without that measurement, 46 of the entries would have been lies**
> — each reading as a considered decision about live code.

⛔ **And the fourth mechanism produced one rescue and sixteen false alarms.**
`realtime.purge_expired` looked unreached and claimed *"(maintenance heartbeat)"* in its own
docstring — which reads exactly like the fifth instance of *a stale comment reads as a measurement*.
**It is called**, at `api/routes.py:964`, as `store.purge_expired()` behind a `hasattr`. Retention IS
enforced, and I was one grep from recording a false finding. The other sixteen were name collisions:
`list.extend` with **96** apparent hits, `Path.resolve` with **74**.

### ⛔ And the sharpest finding was already written down by the code

`capture/acquire/need_executor.py:3` — *"`context/evidence_need_store.py` files needs.
`evidence_need.execute()` works ONE need. **Nothing ran**"* — and at `:125`, naming
`read_open_needs`: **"which this layer may not import."**

**`capture/` is layer 1 and `context/` is 2, so the EvidenceNeed executor cannot read its own
queue.** Four functions carry that chain, one of them (`hold_resolution.resolve_hold`) with **22
test callers — the most of any unreached function in the engine** — and it is broken **at a layer
boundary**, not by an oversight. ⛔ The Atlas listed EvidenceNeed as **VERIFIED MISSING** when this
programme began; it was built since and never connected.

### ⛔ One guard over eleven packages, not nine copies

The plan called this *"a level, one unit per package"*. It is one module, **58 tests**, parametrised
over a registry — **and that is what makes a NEW package forgetting its declaration a build
failure**, which nine hand-written copies could never have caught.

### Three faults of mine, all caught before shipping

⛔ The self-exclusion was a **hand-maintained list**, and I forgot to add my own new module to it
within a minute of writing it — *a list you must remember to extend is a list that will be wrong*.
Now derived. ⛔ The generic mover check demanded two long strings and **failed on two correct
tables** (a `PULL_ONLY` route is eleven characters). ⛔ And the decorator check took a **union**
across `api/` instead of going per module — *the same name-collision class the qualified resolver
exists to fix, reproduced in the test that documents it.*

→ `STEP-17-DONE` · **109 declared entries across ten modules** · 71 tests

---

## What changed because of F22 – F24

| Finding | Effect |
|---|---|
| F22 | 4 corrections + `test_a_comment_is_not_a_measurement.py` (6 tests). ⛔ The general guard covers **all 25** declared entries, not the one that was wrong |
| F23 | the unsettled-attempt receipt is fence-free by design; the asymmetry asserted as a pair; **H6** raised for the 4 unrun tests |
| F24 | ⛔ every mutation run since establishes and re-verifies a baseline; two completion records corrected in place; the rule saved to memory |
| F25 | the resolver wired at the choke point, **last** in the chain and **gated** on `person`; the docstring's stale validator claim corrected and now asserted |
| F26 | ⛔ the assertion rewritten as an **invariant**; `KNOWN_UNWIRED` can now shrink without breaking a test |
| F27 | the record completed (settings nested), written at **both** refusal paths, **and read** by the result endpoint; `_defer` now reads the context it accepts |
| F28 | the revive wired at the registration route, gated by `deliverable_channels`, in the upsert's transaction, count returned. ⛔ **The proposed `expires_at` bound retracted and its absence asserted.** `KNOWN_UNWIRED` → **0** |
| F29 | ⛔ the third membership list rewritten as an invariant; an **empty** table is now a legitimate state |
| F30 | two L5 receipts built, **two candidates rejected with their premises asserted**; the window measured against the scheduler |
| F31 | ⛔ the L5 count guard created **where L4's docstring already promised it**; 11 references + 1 filename moved from numbers to claims |
| F32 | the scorecard covers L5 (**45** claims); doc 17's live pointer updated and STATUS's historical row **dated rather than rewritten**; the channel-duplication guard now counts the question |
| F33 | ⛔ `STEP-16` **withdrawn**; `rate_limiter`'s declaration rewritten with the measured facts and its mover changed to the **worker count**; 7 tests pin it |
| F34 | ⛔ `platform/reachability.py` extracted; **eight new declaration modules**, 109 entries, ONE guard over eleven packages; two new wiring mechanisms measured and a fourth declared unmeasurable |
