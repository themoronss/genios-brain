# Step 9 — DONE · the gate writes down why it refused

**Unit:** `M13.C3.U09` · **Owner:** me · ✅ **2026-10-01** · 13 tests · 6 mutations
⛔ **Planned as *wire it or declare it*, and called the lowest severity of the four. It was a THREE-part unit and the plan had none of the three right.**

## 1 · What is there

`deliver/gate.py:493`, in `__all__`, called by nothing:

```python
def describe_decision(decision: DeliveryDecision, context: DeliveryContext) -> dict[str, Any]:
    """The loggable record of one admission — verdict, reason, and the settings behind it."""
```

`gate.py` is the module that decides whether a card may go out at all — moment and permission. Its why-not
vocabulary (`below_gate · budget · cooldown · muted · shadow · situation`) is one of the things this layer
got **right**: written **and** read, by `executive/explain.py`.

So the verdicts are already explainable. What is missing is the per-admission record: *this card, this
tenant, this moment, refused for this reason, under these settings.*

## 2 · Why it is still worth a unit

A gate that cannot say why it refused **one specific card** is one production incident away from being the
most expensive silence in the package. The shape of that incident is predictable: a founder reports a
notification that never arrived, and the only answer available is an aggregate — *"some cards were
deferred for cooldown"* — rather than *"yours was, at 14:02, because the tenant's cooldown was 6h and the
previous card went at 09:30."*

⛔ **And it is the fourth kind of unreached function**, which is why it belongs in this sequence: an
unguarded cutover (06), a PULL_ONLY surface (07), a measured defect (08), and an **unlogged record**. Four
functions, four reasons, one declaration module.

## 3 · The decision this step must make first, and not assume

⛔ **Wire it, or declare it?** `describe_decision` returns a dict — a record for *something* to persist.
So the real question is whether a sink exists:

| Candidate sink | Must measure |
|---|---|
| `spine.log_delivery_event(conn, org_id=…, delivery_id=…, kind=…, at=…)` | ⛔ it takes a `delivery_id`. **A refused admission may have no delivery row** — that is the point of refusing — so this may be structurally wrong |
| `store.log_event(card_id, org_id, kind, cause=…)` | card-scoped, already used for `window.lapsed`. More likely to fit |
| `analytics.py` (Phase 5) | aggregate, not per-admission. Probably the wrong grain |

**If no sink fits the grain, this step declares rather than wires** — and the declaration names the sink
that would have to exist. ⛔ **Inventing a table for a record nobody reads would be presence without
effect**, and *presence is not effect.* A row written and never read is the exact defect this programme has
found eight times.

> **Expected answer, to be confirmed rather than assumed:** `store.log_event` on the card, because a gate
> decision is about a card. But `log_event`'s existing callers must be read before claiming the signature
> fits — four of the seven L4 unit plans were wrong, and every one was caught by measuring before building.

## 4 · What to build

| | |
|---|---|
| `deliver/gate.py` **or** `deliver/delivery_health.py` | ⛔ whichever §3 measures to be correct — the call site, **or** the declaration naming the missing sink and its mover |
| `tests/deliver/test_the_gate_records_the_admission_it_refused.py` | ⛔ NEW, in either case |

## 5 · The tests

| If wired | If declared |
|---|---|
| `test_a_refused_admission_is_recorded_with_its_reason` | `test_describe_decision_is_declared_with_the_sink_it_needs` |
| `test_the_record_names_the_settings_behind_the_verdict` | `test_the_declaration_names_a_mover` |
| `test_an_admitted_card_is_recorded_too` — ⛔ a log of refusals only cannot show the refusal **rate** | `test_no_comment_claims_it_is_called` — STEP-07's general guard, which covers this for free |
| `test_the_recorder_actually_REACHES_the_gate` | |

## 6 · Verify

```
.venv/bin/pytest tests/deliver/test_the_gate_records_the_admission_it_refused.py -q
.venv/bin/pytest tests/deliver/ -q
```

## 7 · Expected outcome

Either the gate's decisions are auditable one card at a time, or `deliver/` states in code that they are
not, names the sink that would make them so, and names who can build it. ⛔ **Both outcomes are
acceptable; silence is not.**


---
---

# ✅ DONE — 2026-10-01

## 1 · ⛔ The sink question, answered — and both of the plan's candidates were wrong

`§3` listed three candidates and said *"if no sink fits the grain, this step declares rather than
wires."* Measured:

| Candidate | Verdict |
|---|---|
| `spine.log_delivery_event` directly | ⛔ **the right TABLE, the wrong CALL.** `_mark_lifecycle` is the canonical wrapper, and its docstring says why — *"column + event row together"* so the two *"cannot disagree"*. Calling the logger directly writes the event and leaves `lifecycle` stale |
| `store.log_event` | ⛔ **card-scoped.** A gate decision is about a DELIVERY |
| `analytics.py` | aggregate, wrong grain — as the plan guessed |
| ⛔ **`_mark_lifecycle`'s own `detail` dict** | **the answer, and the plan never listed it.** Live, `jsonb`, already called from both refusal paths |

⛔ The plan called `store.log_event` *"more likely to fit"*. **It was the wrong one of three, and
the right one was not on the list** — the fourth time in L5 a step's candidate list was wrong, and
the fourth time measuring first cost one command and saved a wrong build.

## 2 · ⛔ `admit` had written down what the record was for, and both refusal paths dropped it

```
"Returns the context alongside the verdict so the caller can put the resolved settings into the
 audit row. 'It was held because quiet hours' is only half an answer; '…and this tenant's quiet
 hours are 21:00-08:00 Asia/Kolkata' is the half that ends the support ticket."
```

`outbox._suppress(engine, row, decision, context, out)` and `_defer(…, decision, context, now, out)`
are handed **both** objects, and wrote:

```python
_mark_lifecycle(c, row, "deferred", "deferred", now, {"reason": decision.reason_code})
```

⛔ One key — and not even the contract's name for it (`reason_code`). `decision.detail` and the whole
resolved context went on the floor **at the one seam where both were in hand.**

⛔ **And `_defer` took `context` as a parameter and read nothing from it.** Presence without effect,
in the signature — and a deferral is the verdict a founder is most likely to ask about (*"why is it
09:00 and I still have not seen it?"*), whose answer was inside the thing being ignored.

## 3 · ⛔ The second missing part · `describe_decision` was not keeping its own third promise

Its docstring: *"verdict, reason, **and the settings behind it**."* It read **only**
`context.config_error`.

The settings are `DeliveryContext.to_semantic_dict()`:

```python
{"policy": describe_policy(self.policy), "profile": describe_profile(self.profile),
 "interrupts_last_hour": self.state.interrupts_last_hour, "config_error": self.config_error}
```

⛔ **That is literally `admit`'s worked example.** Measured on a real context:

```
settings["profile"]["timezone"]         -> "Asia/Kolkata"
settings["profile"]["quiet_start_hour"] -> 21
settings["profile"]["quiet_end_hour"]   -> 8
len(json.dumps(record))                 -> 437 bytes
```

⛔ **And the capability was already exposed, on the wrong path.** `api/delivery_routes.py:168` calls
`context.to_semantic_dict()` for the **preview** endpoint — so a dry run could already show a founder
their own quiet hours while the **live** refusal recorded none of them.

**437 bytes on a refusal, not on every delivery.** `describe_policy` and `describe_profile` both
return flat dicts of scalars, which is what made nesting the whole context affordable — measured
before it was written, because the record is per-refusal and size is a real cost.

### The flag stays separate from the blob, deliberately

`describe_decision` adds top-level `config_error` **only when there is one** — its own contract.
`to_semantic_dict` carries the key **unconditionally**, because that is the shape the preview
endpoint reads. ⛔ **A key that is always present and usually null teaches a reader to ignore it**,
so the two live at two levels and mean two things: the flag says *a setting could not be used*, the
blob says *here is every setting, including that one.* The duplication is the cheap half of the
trade, and it is written into the code.

## 4 · ⛔ The third missing part · the writer alone would have been decoration

```
GET /api/org/{org_id}/delivery/results/{delivery_id}
    select kind, occurred_at, actor from delivery_events ...
```

⛔ **`detail` was not selected.** This is the endpoint a support question lands on, and it returned
the event *kinds* — `deferred`, `suppressed` — and **not why**. `tracker.py` does `select 1`.
**Nothing in the engine read `delivery_events.detail`.**

> ⛔ So enriching the writer alone produces a richer row nothing reads — *presence without effect*,
> the exact defect `§4` of this step's own plan warned about. **The reader is half the unit**, and it
> is one word in one SELECT. **Mutation M3 removes it and a test fails.**

### And one check that made the key rename safe

`feedback/calibrate.py:107` reads `detail->>'reason'` — ⛔ on **`canonical_judgments`**, a different
table. Verified before the key was changed: *a grep that finds something is not evidence it is the
same something.*

## 5 · What was built

| | |
|---|---|
| `deliver/gate.py` | `describe_decision` now carries `"settings": context.to_semantic_dict()` |
| `deliver/outbox.py` | `describe_decision(decision, context)` into **both** refusal paths' lifecycle detail, + the import |
| `api/delivery_routes.py` | ⛔ the result endpoint selects `detail` |
| `deliver/delivery_health.py` | the `UNREACHED` entry **deleted** |
| `tests/deliver/test_the_gate_records_the_admission_it_refused.py` | ⛔ NEW, **13 tests** |

```
UNREACHED (deliver/)  11 -> 10        DECLARED  24 -> 23
```

### The 13 tests, and why they are behavioural

A fake engine that logs its SQL — ~25 lines, no database — so `_defer` and `_suppress` run **for
real** and the `delivery_events` insert is decoded from its own parameters. ⛔ **A behavioural test
beats an AST test wherever one is affordable**; `STEP-06` had to settle for structure because its
code needs real PostgreSQL. This one does not.

| group | what it pins |
|---|---|
| **the record** (4) | a deferral records verdict · unit · reason_code · `not_before` · `decision.detail` · ⛔ **and the settings, asserted on `quiet_start_hour`/`quiet_end_hour`/`timezone`** · a suppression records the same with `not_before is None` · the thin `{"reason": …}` record cannot come back · a `config_error` reaches **both** levels |
| ⛔ **the row with no identity** (1) | `_mark_lifecycle`'s own rule: no `delivery_id` → **column update only**. The record is a bonus, never a precondition |
| ⛔ **the reader** (2) | the endpoint selects `detail` · **and still selects what it always did** — the counterweight, because a test checking only for `detail` would pass on a query returning nothing else |
| ⛔ **the shape** (3) | the record carries **no identity of its own**, which is *why* the sink is keyed on the row · the flag is conditional and the blob's key is not · ⛔ **the whole record stays under 2 KB**, because it is written per refusal |
| **mutation shapes** (2) | both paths actually REACH the recorder (AST) · `_defer` now **READS** the context it accepts |
| **the declaration** (1) | the entry is gone, both directions clean |

## 6 · ⛔ A test of mine built an illegal object, and the contract caught it

`test_a_config_error_reaches_the_record` constructed a `SUPPRESS` decision carrying a `not_before`.
`DeliveryDecision` refused it: ***"only a deferral carries a clock."***

⛔ **That is the contract working, and it is worth recording rather than quietly fixing.** The
contract knows something my test assumed away — a suppression is over, so it has no window — and it
said so at construction rather than letting a nonsense record reach a reader.

## 7 · What this step deliberately did NOT do

| | Why |
|---|---|
| record the **ADMITTED** case | ⛔ every terminal writer already calls `_mark_lifecycle`, so a delivered card gets an event; what it lacks is the gate's reasoning. Adding it writes 437 bytes on **every successful delivery** — a volume decision on the happy path, and `admit`'s docstring is about HELDS. **Recorded, not taken** |
| surface `detail` on the **list** endpoint | the per-delivery endpoint is where a support question lands; the list endpoint returns many rows and widening it is a payload decision |
| touch `_suppress`'s `last_error` | it already carries the note *"the existing operator queries — which all read `last_error` — surface without changing"* |

**Noticed something adjacent? New unit, not a silent fix.**

## 8 · Mutations

⛔ **Baseline first, restore re-verified.**

```
baseline        83 passed
restore verify  13 passed
```

| # | Mutation | Result |
|---|---|---|
| M1 | revert `_defer` to `{"reason": …}` | 🔴 4 failed |
| M2 | revert `_suppress` the same way | 🔴 3 failed |
| M3 | ⛔ **drop `detail` from the endpoint's SELECT** | 🔴 1 failed — the writer alone is decoration |
| M4 | write the event even when the row has no `delivery_id` | 🔴 **12 failed** |
| M5 | make the top-level `config_error` unconditional | 🔴 1 failed |
| M6 | ⛔ **drop `settings` from the record** | 🔴 4 failed |

## 9 · Verify

```
.venv/bin/pytest tests/deliver/test_the_gate_records_the_admission_it_refused.py -q    # 13 passed
.venv/bin/pytest tests/test_delivery_gate.py tests/test_delivery_routes.py \
                 tests/deliver/ tests/test_delivery_control_plane_api.py -q            # 393 passed
```

## 10 · Doctrine

| Rule |
|---|
| ⛔ **a record nobody reads is presence without effect — the reader is half the unit** |
| ⛔ **a parameter accepted and never read is presence without effect, in the signature** |
| ⛔ **the right table can still be the wrong call** — `_mark_lifecycle` exists so a column and its event cannot disagree |
| ⛔ **a function can fail to keep its own docstring's third promise, and nothing will say so** |
| **a capability exposed on the preview path is not exposed on the live one** |
| **a behavioural test beats an AST test wherever one is affordable** |
| **a grep that finds something is not evidence it is the same something** |
| **a key always present and usually null teaches a reader to ignore it** |
