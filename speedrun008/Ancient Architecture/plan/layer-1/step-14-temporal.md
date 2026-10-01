# Step 14 — The temporal field set and reply pairing

**Status:** NOT STARTED · **Effort:** days · **Depends on:** 3, 12 · **Engine:** D
**Moves:** metric 6 — P1's reply-latency objects

> **Added after the first plan.** Steps 1–11 left the temporal vocabulary and reply pairing
> unowned.

## 1. Why this step exists

**A timestamp is not temporal meaning.** QES carries exactly two instants today:

```
occurred_at   ·   expires_at   (+ ingested_at, which is a processing fact, not a world fact)
```

Missing: `due_at` · `effective_at` · `resolved_at` · `superseded_at`.

That is why P2 cannot say *"8 days overdue"* from the signal alone — the deadline lives inside the
`Commitment` claim, not on the signal, so nothing can sort or sweep by it.

**And reply pairing has no owner.** `structural/threads.py` produces `last_inbound_at`,
`last_outbound_at`, `turn_index` and `ball_in_court`. The *latency* is computed in
`context/waiting.py` — **Layer 2**. The pairing itself (this inbound, that outbound, Δt) is
mechanical: no judgement, no context, no model. It belongs in L1. The *judgement* — Claude's
*"binary responder: 9 of 14 under 30 minutes"* — is a pattern over many pairs and is correctly
Layer 2's.

## 2. Current status

| Instant | On QES? | Where it lives instead |
|---|---|---|
| `occurred_at` | ✅ | — |
| `expires_at` | ✅ | ALG-19 `plan_expiry` |
| `ingested_at` | ✅ | processing time, not world time |
| `due_at` | ❌ | inside `Commitment.due` |
| `effective_at` | ❌ | nowhere |
| `resolved_at` | ❌ | nowhere |
| `superseded_at` | ❌ | implied by the pointer, not stored |
| reply pair + Δt | ❌ in L1 | `context/waiting.py` (L2) |

`validate/dates.py` ALG-09 is strong and must be reused, not duplicated: *"next Friday" is a range
with a certainty, not a point.* Any new instant that comes from prose goes through it.

## 3. Expected result

| | Before | After |
|---|---|---|
| Instants on the signal | 2 world + 1 processing | 6 world + 1 processing |
| "Days overdue" answerable from the signal | no | yes |
| Reply pairs | derived in L2 | emitted by L1, with both message ids and Δt |
| Clock reads inside logic | 0 | **still 0** |

## 4. Edge cases

| # | Scenario | What must happen |
|---|---|---|
| E1 | A deadline that is a **range** ("next week") | store the range and its certainty — never collapse to a point |
| E2 | Timezone | every instant is tz-aware; a naive one **raises**, as `eval_time` already does |
| E3 | `due_at` in the past at capture time | legal — a stale promise is still a promise |
| E4 | `resolved_at` earlier than `occurred_at` | refuse at the contract, like the self-supersede check |
| E5 | Consecutive outbounds with no reply between | contribute **no** latency — `context/waiting.py:130` already states this rule; do not re-derive it differently |
| E6 | A reply that quotes the whole thread | the pair is by message id, not by content |
| E7 | An auto-reply | **never counts as the counterparty answering** — N-05's existing rule |
| E8 | Business days vs calendar days | `add_business_days` takes an **injected** calendar; weekends-only is the live behaviour and must be stated, not assumed |

## 5. How to do it

| Unit | What |
|---|---|
| 14-U1 | `due_at`, `effective_at`, `resolved_at`, `superseded_at` on C-12, all optional, all tz-aware |
| 14-U2 | populated from the typed claims that already hold them (`Commitment.due` → `due_at`) — **lifted, never re-derived** |
| 14-U3 | a contract validator: ordering constraints (E4) |
| 14-U4 | reply pairing in L1: `(inbound_message_id, outbound_message_id, delta)` per pair |
| 14-U5 | E5 and E7's rules honoured by **reading** `context/waiting.py`'s existing logic, then moving it — not writing a second version |
| 14-U6 | no clock anywhere: every instant is a parameter |

## 6. Test cases

T1 a commitment's `due` appears as `due_at` on its signal (RED today) · T2 a naive datetime raises ·
T3 `resolved_at` before `occurred_at` is refused · T4 a range deadline keeps its certainty ·
T5 two consecutive outbounds produce **one** latency, not two · T6 an auto-reply produces **no**
pair · T7 the purity grep for `datetime.now` in `capture/validate/` stays empty.

## 7. Verify

```bash
uv run --no-sync pytest tests/capture/validate/test_dates.py -q -p no:randomly
uv run --no-sync pytest tests/contracts/test_l1_contracts.py -q -p no:randomly
grep -rn "datetime.now\|date.today" genios_engine/capture/validate/     # must return nothing
```

## 8. Done criteria

**Ticked 2026-09-24. All four closed.**

- [x] **four new instants on C-12, lifted from typed claims** — `due_at` · `effective_at` ·
      `resolved_at` · `superseded_at`, all optional and all tz-aware, plus migration **0179** and
      the store's INSERT, upsert and parameter map. `due_at_of` LIFTS from `Commitment.due` rather
      than re-deriving, takes the **far** end of a range (E1), and the **soonest** when a signal
      rests on several.
- [x] **reply pairs emitted by L1, with both ids** — `pair_replies` returns
      `(outbound_message_id, inbound_message_id, latency_seconds)`. **Integer seconds, not float
      days**: `waiting.py`'s float is fine inside L2 and not fine crossing a seam (V-7).
- [x] **`context/waiting.py`'s two rules preserved exactly — verified by reading it first** — read
      first, as §8 requires, and its loop is reproduced rather than reinvented. E7 reuses the
      gate's `AUTO_REPLY` marker; a second regex is how the gate and this module come to disagree
      about what an out-of-office is.
- [x] **the purity grep is still empty** — it was already empty and remains so. Every instant is a
      parameter, so a replay of last week produces last week's answer.

### 8.1 · Two defects found while wiring, both recorded

**(a) A `getattr` against my own contract.** `getattr(stamp, "superseded_at", None)` — and
`LifecycleStamp` has three fields, so it was **dead code that could never fire**: precisely the
smell step 5 named (*"it cannot fail, so it cannot tell you the field is missing"*). Removed, and
the absence documented as deliberate — a signal is superseded by a LATER sweep, not at publish time.

**(b) A STEP 6 LEAK.** `build_signal` built `domain_hints` by hand as `{domain, source}`, so step
6's `confidence_bp` — carried correctly by `as_dicts` and asserted at that seam — **never reached
`qualified_signals`**. Two hand-written copies of one projection; only one learned the new field.

> That is the drift `situation_bso.py` warns about at the OTHER end of this pipe. **Step 6 was
> reported complete and its headline field was not reaching storage.** Closed, with a test.

## 9. What this step must NOT do

**Do not re-derive a value that a typed claim already holds** — lift it. Do not compute the
latency *judgement* ("binary responder") in L1; that is a pattern over pairs and belongs to L2.
Do not read a clock. Do not collapse a date range to a point.
