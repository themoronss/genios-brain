# L5 · re-cross-check — the silences of the delivery spine

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01. **No code written yet.**
**Reads with:** `01-CROSSCHECK.md` (2026-09-30, before M13 was built) and `02-PLAN.md`.

M13 closed on 2026-09-30 with four steps and 89 new tests. This document re-measures `deliver/`
**after** that build, the way `layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md` re-measured
L4 after its own. It exists because a crosscheck written before a build cannot describe what the build
changed, and because the Design Atlas v2's L5 cell was written against a `deliver/` that has since moved.

---

## 0 · The headline, before the detail

| | |
|---|---|
| `deliver/` today | **40 files · 9,431 lines** (36 top-level · 8,997 + `channels/` 4 · 434) |
| the Atlas says | *"36 files · 8,674 lines"* — the **36 matches the top-level count exactly**, so the Atlas counted top-level only and 323 lines have landed since |
| Atlas claims superseded by this programme's own L5 pass | **three** |
| Atlas claims about L5 that the code already satisfies | **five** |
| an entire architecture the Atlas does not mention | **Layer 5.2** — six modules, five phases |
| public functions in `deliver/` | ⛔ **123** top-level — *this table first said 133, which included `channels/`* |
| of those, reached by nothing | ⛔ **24** — *this table first said 4; see `06-AUDIT`* |
| of those 24, declared anywhere | **0** |
| of those 24, having no test caller either | **4** — *the number first reported here* |
| production receipts carrying L5 | **2 of 32**, and one of the two cannot run |

⛔ **The one-line verdict: `deliver/` is the most heavily built layer in the product and the most
lightly guarded.** Nothing in it is wrong in the way L4's queue was wrong. What it lacks is the
machinery every sibling package already has for saying *what it deliberately does not do*.

---

## 1 · ⛔ The Atlas is three claims out of date on L5, and the code is why

The Atlas v2 L5 cell makes two large claims. Both were true when it was written. Neither is true now,
and in both cases **this programme is what changed them** — which means the Atlas is not wrong so much
as superseded, and the correction belongs in the scorecard rather than in a bug list.

| Atlas claim | Badge it carries | What is actually there now |
|---|---|---|
| claim-level validation | `target` | ⛔ **BUILT.** `deliver/claim_validator.py` + `deliver/claims.py`, M13 STEP-03/04, shared 34 tests |
| *"no lanes on the card"* — called **L5's biggest gap** | `gap` | ⛔ **BUILT.** `deliver/lane_display.py` + `deliver/lane_recall.py`, M13 STEP-01/02, 55 tests, plus `migrations/0190_card_lane.sql` |
| three delivery failures *"to design out"* — duplicates across paths, card flattening, stale fire | `target` | ⛔ **ALL THREE ALREADY GUARDED.** See §2 |

And two more the earlier crosscheck already corrected, restated here so this document stands alone:

| Atlas claim | What is actually there |
|---|---|
| *"replace the scalar publication floor"* | there is **no scalar floor in `deliver/`**. The score gate is `reason/runner.py:1133`, and `executive/explain.py` already reads its `below_gate` receipt |
| the invention validator is missing | `render.py:334`, called at `:861`, re-exported by `executive/validate.py:69`, tested |

> **The pattern, now six layers running:** the Atlas describes the engine as it was designed, and the
> code has moved past it in exactly the places the design was most specific. Correcting the badge is
> cheap. Building from the stale badge is what costs six units — which is what L2 paid.

---

## 2 · The three delivery failures the Atlas asks us to design out are designed out

Measured one at a time, because "we probably handle that" is not a measurement.

### 2.1 Duplicates across paths — ⛔ guarded, and **better** than the Atlas asks

| Mechanism | Where |
|---|---|
| a logical dedupe key over `(org_id, execution_id, event_kind)` | `spine.logical_dedupe_key` |
| a unique index electing exactly one winner | `(org_id, dedupe_key)`, `spine.materialize`'s `on conflict` |
| the two writer paths made **mechanically disjoint** | the legacy drain takes `dedupe_key is null`; the v2 claimer takes `dedupe_key is not null` |
| two workers never fighting over one row | `for update skip locked` + an expiring fence token |

⛔ **`outbox.py:838` wrote the risk down before closing it**, and the comment is worth quoting because it
is the single most useful sentence in the package:

> *"this legacy drain and `spine.claim_due` were not mechanically disjoint: neither excluded rows the
> OTHER path could also claim. **Risk was zero only because the v2 path has never written a row yet;**
> the moment it does, both workers could select the same one and double-send."*

That is a hazard found, written down, and closed with a predicate that costs no new column. It is the
standard the rest of this document measures against.

### 2.2 Card flattening — ⛔ guarded, by a counted cutover rather than a switch

`card_source.COMPARISON_KEYS` runs **both** card paths and counts both on every sweep —
`cards_from_situation` (one card per situation, the new path) against `cards_from_signal` (one card per
signal, the old one) — *before either is retired*. `reason/situation_binding.py:21` states the rule in
the strongest terms available: a change there *"would corrupt the measurement that decides the cutover."*

`slots.py:95-103` holds the second half, with its evidence in the comment: a sentinel that collapsed and
shipped the string **"Raised severald ago"** to a reader. The guard is the fault, written down.

### 2.3 Stale fire — ⛔ guarded, at four grains

| Grain | Where |
|---|---|
| one staleness test shared by the claim **and** the upsert, so the two can never disagree | `store.py:54` |
| a lease that only its own caller can release — *"an expired successor can never be deleted by it"* | `store.py:99` |
| a terminal card (`acted`/`expired`/`resolved`) that cannot be resurrected | `store.py:296` |
| non-terminal cards past `expires_at` expired and logged as `window.lapsed`, feeding L6's ignore-rate | `store.py:317` |

> ⛔ **So all three "failures to design out" are already designed out, two of them with the fault that
> taught the lesson recorded in the code.** The Atlas's L5 `target` badge on this row should read `built`.

---

## 3 · ⛔ The Atlas does not mention the architecture that is actually there

The Atlas L5 cell describes a delivery layer of surfaces and a budget. `deliver/` contains a five-phase
pipeline the Atlas names nowhere:

| Phase | Module | What it is |
|---|---|---|
| 2 | `presence.py` | the Delivery Context Resolver — who is reachable, where, right now |
| 2 | `orchestrator.py` | seven responsibilities collapsed into one materialised `DeliveryObject` |
| 3 | `spine.py` | the **durable outbox spine** — claim, fence, attempt, settle |
| 4 | `tracker.py` | the Delivery Tracker |
| 5 | `units.py` | the **eleven delivery units** and their capability registry |
| 5 | `analytics.py` | Delivery Analytics |

This is not a gap in the code. It is a gap in the document that is supposed to describe the code, and it
is the larger of the two — because the next person to plan L5 from the Atlas will plan to build
`presence.py`.

**Action: a scorecard row, not a unit.** Recorded as STEP-11.

---

## 4 · ⛔ The real finding · `deliver/` is the one big package with no declared silence

Three of the four large packages state, in code, what they deliberately do not do:

| Package | Its declaration |
|---|---|
| `reason/` | `unit_health.py` — four grains of declared silence, `neutral_default_boundary()`, `REASONING_ERAS` |
| `context/` | `lane_health.DORMANT_LANES` |
| `executive/` | `unreached.py` — `UNREACHED` (5), `PULL_ONLY` (4), each with a reason and a mover |
| **`deliver/`** | ⛔ **nothing** |

So I ran L4's own tooling — `executive/unreached.public_functions` and `.called_names`, which resolves
aliased imports — over `deliver/`:

```
123 top-level public functions · 24 reached by nothing · 0 declared
   of the 24, 4 have no test caller either    (⛔ corrected — see 06-AUDIT)
```

Every one of the four was then read in full, because an unreached function is not automatically a
defect — L4 established that *"an unreached function is not always forgotten; sometimes it is
unreachable."* The four turned out to be **four different kinds of thing**, which is the whole value of
having measured them:

| Function | What its own docstring says | Kind |
|---|---|---|
| `spine.recover_expired_claims` | *"we must never silently retry over that ambiguity"* | ⛔ an **unguarded cutover** — §5 |
| `push.push_card_to_agents` | *"fan a freshly-emitted card out to every active agent"* | **PULL_ONLY** — the pull half works — §6 |
| `card_builder.resolved_person_name` | *"35 of 38 person cards named an address in the headline"* | ⛔ a **measured defect whose fix is unwired** — §7 |
| `gate.describe_decision` | *"the loggable record of one admission"* | an unlogged record — §8 |

> **This is why a declared-silence module is the first unit and not the last.** Four functions, four
> different reasons, and a reader of the package today cannot tell any of them apart from an oversight.

---

## 5 · ⛔ `recover_expired_claims` — and the live-harm finding I did not get to write

**What I was about to write.** `recover_expired_claims` marks an expired claim's unsettled attempt
`unknown` so nobody retries over a provider POST that may already have landed. Nothing calls it.
`claim_due`'s own SQL frees an expired row regardless — `and (claimed_by is null or claim_expires_at <
:at)` — and it writes a **new** fence token on reclaim, while the recovery matches on `a.claim_token =
d.fence_token`. So after a reclaim the recovery can *never* match that attempt: the orphan is permanent
and the retry happens over exactly the ambiguity the docstring forbids. That is a tight, alarming,
well-evidenced finding.

⛔ **It is also wrong, and one more grep is what makes it wrong.** `spine.claim_due` is called by
**nothing in production** — two tests and an `inspect.getsource` assertion, nothing else. The
`capture/parked/refetch.py:267` hit is a different function with a different signature. The production
drain is `outbox.drain`, and the codebase states plainly that *"the v2 path has never written a row
yet."*

**So the honest finding is narrower, and cheaper to fix:**

> The v2 spine is a complete, correct, mechanically disjoint path that **has not been cut over to**.
> `recover_expired_claims` is the one component of it that nothing calls — *including its own tests*.
> `claim_due` at least has tests proving its claim-and-reclaim semantics. The recovery has none. So the
> cutover, on the day it is taken, takes a path whose ambiguity-marking step has never executed, and
> nothing in the repo would tell anyone.
>
> **The defect is an unguarded cutover, not a double-send.**

⛔ **Fifth time in this programme that measuring the callers first prevented a wrong finding** — after
`no_model_wired` (L1), the graph-revision guard (L3), `manager_seat_id` (L4), and F9/F10 in L4, both of
which were retracted because the fix would have caused harm. **New doctrine rule: *an uncalled function
on an un-cut-over path is not a bug; it is an unguarded cutover.*** The two want opposite fixes — a bug
wants wiring now, an unguarded cutover wants a guard that fires when the cutover is taken.

And the legacy path is **not** exposed: `outbox.drain` pushes an in-flight row's `next_attempt_at` into
the future so *"a crashed drain retries them on schedule instead of double-sending on the very next
tick."* Time-based, no attempt table, no fence. Different mechanism, already correct.

---

## 6 · `push_card_to_agents` is PULL_ONLY, and the comment above it says otherwise

`deliver/agent_api.py` gives agents a working pull surface — `poll_signals`, `get_artifact`, `claim`,
`result` — and `push.py`'s own header states *"Body == the /v1/signals poll projection, so push and poll
are interchangeable."* So an agent that polls gets everything a pushed agent would get. That is L4's
`PULL_ONLY` shape exactly: a surface whose pull half is wired and whose push half is not.

⛔ **But `push.py:19` reads:**

> *"`push_card_to_agents` — proactive "here's a new signal" **(fired by L5 when a card is emitted)**."*

Nothing fires it. **A stale comment reads as a measurement** — this programme's own rule, and the sixth
time it has fired. The harm is specific: the next person asking *"do agents get notified?"* reads that
parenthesis and answers yes.

⛔ **A second stale comment, in the same subsystem.** `units.py` justifies `PUSH_REQUIRES_ADAPTER` with:

> *"`channels/base.get_channel` returns Slack or None — **one implementation** across every push channel
> named here."*

Measured: `get_channel` returns Slack **or `AgentWebhookChannel`**. `channels/agent.py` is 11,906 bytes
— the largest adapter in the folder — dated two days after `base.py`. So the agent transport was built
after the comment and the comment was never revisited.

⛔ **The behaviour is correct and the prose is not**, which is the dangerous combination: `_implemented_channels()`
computes the answer at runtime, so `capability_report` has always been right. Only the sentence a human
reads is wrong.

---

## 7 · ⛔ `resolved_person_name` — a measured defect whose fix was built and never wired

`card_builder.py:610` carries its own evidence:

> *"35 of 38 person cards named an address in the headline"* — a `mention:person` observation carries the
> real name.

So: somebody measured 38 person cards, found 35 with an email address where a human name belonged, wrote
the function that resolves it, and **never called it**. Zero references in the repo — not in
`card_builder.py` itself, not in tests.

This is the one of the four that is a plain defect. Its two open questions, which STEP-08 must answer in
this order:

1. **Is the 35-of-38 still live?** Needs a read-only production read (`set transaction read only`). ⛔ Not
   available in this checkout — no database URL is configured, only `.env.example`. So the step builds
   the wiring and its test, and the production confirmation is logged as a separate read.
2. **Does wiring it change a rendered headline that the invention validator would then refuse?**
   `invention_ok` rejects any name not in the grounded corpus. A `mention:person` observation **is** in
   the corpus, so the expected answer is no — but it is a prediction until the test exists, and the
   validator must not be weakened to accommodate the fix.

---

## 8 · `describe_decision` — the gate decides and does not write it down

`gate.py:493`, in `__all__`, called by nothing. *"The loggable record of one admission — verdict, reason,
and the settings behind it."* The gate's decisions are therefore not auditable in that shape.

Lowest severity of the four, and it is still worth a unit: `gate.py` is the module that decides whether a
card may go out at all, and the why-not vocabulary (`below_gate · budget · cooldown · muted · shadow ·
situation`) is one of the things this layer got right. A gate that cannot say why it refused is one
production incident away from being the most expensive silence in the package.

---

## 9 · ⛔ Two receipts for nine thousand lines

The production receipt set is **32**, distributed:

| L1 | L2 | L3 | **L5** | L6 | L7 | L4 |
|---|---|---|---|---|---|---|
| 6 | 7 | 2 | **2** | 4 | 4 | 7 |

| Layer | Lines | Receipts | Lines per receipt |
|---|---|---|---|
| L4 `executive/` | 6,167 | 7 | 881 |
| **L5 `deliver/`** | **9,431** | **2** | ⛔ **4,715** |
| ⛔ **CORRECTED 2026-10-02** | — | — | **5** · **1,886** → [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](08-CORRECTION-a-receipt-label-is-not-a-package.md) |

And **one of the two cannot run**: the *lane* receipt — *"every delivered card carries a lane, or is labelled
unrouted"* — **ERRORs**, because `cards.output_lane` does not exist until `0190` is applied. So the layer
that physically touches the customer has **one** working production guard: #24, *"decisions become
tracked commitments."*

⛔ **This is the largest gap in L5 and it is not a feature gap.** L5 is where the product meets a human
being. A delivery failure here is the only kind of failure a customer experiences directly, and there is
one question being asked of production about it.

> **The rule this must respect:** count guards are **per layer**, never global —
> `test_activation_changes_the_pass.py` for L4, `tests/deliver/test_nothing_dies_of_low_confidence.py`
> for L5 — and its docstring already says why: *"the cheap fix for that is to bump the number, which is
> how a decision gate becomes a rubber stamp."* New L5 receipts raise the **L5** count, with the decision
> written in. And every new receipt must be able to **fail** — *a receipt that cannot fail is not a gate.*

---

## 10 · What is NOT wrong, measured rather than assumed

| | |
|---|---|
| `capability_report` | ⛔ **honest, and fail-closed.** 4 of 6 push channels have no adapter (`api`, `email`, `teams`, `webhook`) and 3 of 11 units have no reachable channel — and the report says so per channel, with `no_adapter` named as **our** gap rather than the tenant's |
| the `email` unit | the only one declaring `engine_ready=False`. The honest one |
| the channel seam | *"send failures are RESULTS, not exceptions"* — a throwing channel would be smuggling retry policy out of the outbox |
| the bridge direction | Executive never imports Delivery; it writes `execution_events` and L5 reads it |
| `in_app` / `dashboard` | deliberately excluded from `PUSH_REQUIRES_ADAPTER`, because demanding an adapter *"would report the one delivery path that actually works today as broken"* |
| the priority rank | generated from `contracts.delivery._PRIORITY_RANK`, after a text column sorted `background < critical` alphabetically and claimed critical work last |
| the lane | carried and counted, **never gating delivery** — because under the spend limit that column has never once been written in production |

⛔ On the capability report in particular: `api` and `webhook` declare `engine_ready=True` with zero
reachable channels. That reads oddly, and it is correct — `engine_ready` is a statement about the engine,
`operational` is the statement about the surface, and `operational` is `False` for both. **Two fields
answering two questions. Not a finding.**

---

## 11 · The eight steps this produces

Order is bottom-up: the declaration module first, because the next four steps write into it.

| Step | Unit | Why here | Owner |
|---|---|---|---|
| 05 | `deliver/` declares what it does not call | the foundation the next four need | me |
| 06 | the unguarded cutover (`recover_expired_claims`) | deepest in the stack; a guard, not a wiring | me |
| 07 | two comments that read as measurements | cheapest, and both actively mislead | me |
| 08 | the headline fix nobody wired | a measured defect, 35 of 38 | me |
| 09 | the gate's own record | lowest severity of the four | me |
| 10 | two receipts for nine thousand lines | the largest gap; needs 05–09 to know what to assert | me |
| 11 | the Atlas does not know Layer 5.2 exists | a document correction, three claims plus an omission | me |
| 12 | the *lane* receipt cannot run until `0190` is applied | ⛔ **blocked on H1** | Harsh |

Each step is specified in its own `STEP-NN-*.md`. **Nothing is built until Rohit has read them.**

---

## 12 · The doctrine this re-cross-check produced

| Rule | Where it came from |
|---|---|
| ⛔ **an uncalled function on an un-cut-over path is not a bug; it is an unguarded cutover** | §5 — the live-harm finding one grep away from being written |
| **four unreached functions can be four different kinds of thing** | §4 — and a package with no declaration cannot tell them apart |
| **the behaviour can be right while the sentence a human reads is wrong** | §6 — `_implemented_channels()` was always correct |
| **guards per line, not guards per layer, is the number that shows the gap** | §9 — 2 receipts over 9,431 lines |
| ⛔ **CORRECTED 2026-10-02** | ⛔ the RULE survives; the NUMBER was wrong — 5 receipts over 9,431 lines. [`08-CORRECTION-a-receipt-label-is-not-a-package.md`](08-CORRECTION-a-receipt-label-is-not-a-package.md) |
| **a document that has fallen behind the code is not wrong, it is superseded — and it is still dangerous** | §1, §3 |
