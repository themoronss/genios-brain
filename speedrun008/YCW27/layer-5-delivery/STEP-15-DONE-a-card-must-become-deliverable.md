# Step 15 — DONE · a card must become deliverable the moment a channel exists

**Unit:** `M13.C3.U15` · **Owner:** me · ✅ **2026-10-01** · 12 tests · 6 mutations
⛔ **This step's own proposed fix would have caused harm — the third retraction in the programme. And `KNOWN_UNWIRED` is now EMPTY.**

## 1 · What is there

`outbox.revive_undeliverable` (`outbox.py:400`), in the module's public surface, called by nothing:

> *"Re-open every row this org parked only because it had nowhere to send it. Returns the count. **This
> is the answer to "a card must become deliverable the moment a channel exists".** The alternative
> designs were considered and rejected: …"*

⛔ **A stated product promise, the reasoning that produced it, the rejected alternatives — and no
caller.** So the promise is not kept, and the failure has a specific shape:

> A tenant registers Slack on Tuesday. Every card parked before Tuesday — parked **only** because there
> was nowhere to send it — stays parked.

## 2 · Why the parking itself is correct, and only the un-parking is missing

`outbox.py` separately records that conflating *nowhere-to-send* with a terminal failure
*"burned the card forever"*, and reports `UNDELIVERABLE` apart from terminal failures for exactly that
reason — so *"3 terminal failures"* stops meaning *"3 tenants never registered a channel."*

⛔ **So this is not a design gap. It is a two-part design with one part wired.** The park is deliberate,
documented, and reported separately; the revive is written and never invoked. That makes it a cheaper
and safer unit than it first reads as — nothing needs designing, only connecting, and the function
already states what it refuses to do.

## 3 · ⛔ The measurement this step does FIRST

*When* does a channel come into existence? The revive has to run on that event, and there are three
candidate moments with different properties:

| Candidate | Must measure |
|---|---|
| the write that inserts into `org_channels` | the most precise trigger. ⛔ Where is it? If it is an API route, `deliver/` must not be imported upward from `api/` — `api/` is CROSS_CUTTING, so the call belongs on the `deliver/` side of the seam |
| the next sweep after a channel appears | ⛔ needs a *"has this org's channel set changed"* read, which may not exist. Cheap if `org_channels` carries a timestamp, a new column if it does not |
| every sweep, unconditionally | simplest and idempotent — the function only touches rows parked *for this reason* — but it runs a write on every tick for every org forever |

⛔ **Expected answer, to be confirmed rather than assumed: the channel-registration write.** But four of
L4's seven unit plans were wrong and every one was caught by measuring first, so the route is read
before anything is wired.

⛔ **And one risk the measurement must settle:** a revived card must not resurrect a card that has since
**expired**. `store.py:296` already refuses to resurrect a terminal card (`acted`/`expired`/`resolved`),
and `store.py:317` expires non-terminal cards past `expires_at` and logs `window.lapsed` into L6's
ignore-rate. So reviving a stale parked card could feed L6 a delivery for a card whose window closed —
*which would be a measurement error in a different layer, caused by a fix in this one.*

## 4 · What to build

| | |
|---|---|
| whichever trigger §3 measures to be right | the call site |
| `deliver/outbox.py` | ⛔ only if §3 shows it is needed: an `expires_at` bound, so a revive cannot re-open a card whose window has closed |
| `platform/receipts.py` | ⛔ a receipt counting rows parked as undeliverable for an org that **now has an active channel**. It reads non-zero **today** if any such row exists, and that is the point — it answers the question in production rather than asserting the fix in a test |
| `deliver/delivery_health.py` | delete the `KNOWN_UNWIRED` entry when it is wired |
| `tests/deliver/test_a_parked_card_revives_when_a_channel_appears.py` | ⛔ NEW |

## 5 · The tests

| Test | Assertion |
|---|---|
| `test_a_card_parked_for_no_channel_revives` | the promise |
| `test_a_terminally_failed_card_does_not_revive` | ⛔ the whole reason `UNDELIVERABLE` is reported apart |
| `test_an_expired_card_does_not_revive` | ⛔ §3's risk: L6's ignore-rate must not be fed a closed window |
| `test_a_card_parked_for_a_different_reason_does_not_revive` | *"only because it had nowhere to send it"* is a narrow predicate and must stay narrow |
| `test_the_revive_actually_REACHES_the_registration_path` | the M2 mutation shape — imported and unused |
| `test_the_revive_is_idempotent` | two registrations in one window must not double-send |

## 6 · Verify

```
.venv/bin/pytest tests/deliver/test_a_parked_card_revives_when_a_channel_appears.py -q
.venv/bin/pytest tests/deliver/ tests/platform/ -q
```

## 7 · Mutations

| # | Mutation | Must go red |
|---|---|---|
| M1 | widen the predicate to every parked row | the different-reason test |
| M2 | drop the `expires_at` bound | the expired-card test |
| M3 | revert the call site, keep the import | the REACHES test |
| M4 | `and false and` into the receipt's predicate | its tautology test |

## 8 · Expected outcome

The sentence `revive_undeliverable`'s docstring quotes becomes true, and a receipt says how many cards
were waiting on it.


---
---

# ✅ DONE — 2026-10-01

## 1 · ⛔⛔ THE FIX THIS PLAN PROPOSED WOULD HAVE CAUSED HARM — RETRACTED

`§3` named *"the risk nobody has checked"*: a revived card must not resurrect one whose `expires_at`
has passed, because `store.py:317` expires non-terminal cards and logs `window.lapsed` into **L6's
ignore-rate**. It proposed adding an `expires_at` bound.

⛔ **`revive_undeliverable`'s own docstring had already answered it, and the answer is the opposite:**

> *"Reviving a stale card is SAFE, and that is not an accident of ordering: the drain **re-proves
> graph/pack/card authority immediately before every send**, so a revived row whose card has since
> expired or been revoked is `cancelled` on its way out rather than delivered. **Waking an old
> message and letting the authority check kill it is strictly better than leaving it dead, because
> the second option cannot tell "we chose not to send" from "we lost it".**"*

> ⛔ **An `expires_at` bound destroys exactly that distinction.** A bounded revive leaves the row
> dead, and a dead row is indistinguishable from a decision not to send — which is the one thing
> this layer must never be unable to tell apart.

**Third retracted fix in this programme**, after L4's F9 (bounding `occurred_at` at ingest would have
discarded every future calendar event) and F10 (storing `ranking_weights_version` would have
invalidated every persisted capability snapshot). ⛔ **All three were caught by reading the thing
being changed before changing it**, and `test_the_revive_does_not_bound_on_expires_at` now asserts
the absence so nobody re-adds it. **Mutation M4 adds it and a test fails.**

## 2 · ⛔ The trigger · one of the two `org_channels` writers is a trap

`§3` listed three candidate triggers — the registration write, the next sweep, every sweep — and
guessed the first. ⛔ **Right, and incomplete: `org_channels` has TWO writers and only one is a
channel.**

| Writer | Verdict |
|---|---|
| `api/channel_routes.set_slack` — `PUT /channels/slack` | ⛔ **the trigger.** `api/` is `CROSS_CUTTING`, so importing `deliver/` is legal — `tests/test_layer_topology.py` confirms |
| `platform/seats.py` — the `in_app` PULL surface | ⛔ **NOT a trigger, and its own docstring says why:** *"It is emphatically NOT a transport… `get_channel('in_app')` is None — there is nothing to send… **Making that row a transport is what produced production's entire delivery history: 3 rows, all `failed_terminal`.**"* |

## 3 · ⛔ The gate · `deliverable_channels`, never a hand-written condition

My first instinct was `if body.active and ch == "slack"`. ⛔ **That is the defect
`deliverable_channels` exists to remove, written by hand.** Its docstring:

> *"Two conditions, and **every historical delivery failure in this database is one of them being
> assumed rather than checked**: 1. the tenant registered it (`org_channels`, active), and 2. we have
> a transport for it."*

So the call site loops the canonical answer:

```python
revived = sum(revive_undeliverable(c, org, ch) for ch in deliverable_channels(c, org))
```

Which buys three things by construction rather than by three hand-written conditions:

| | |
|---|---|
| registered **and active** | the query is `where org_id=:o and active` |
| **has an adapter** | `_implemented_channels()` — so `in_app` can never be revived |
| **not an agent transport** | `- AGENT_TRANSPORTS`, because *"a human delivery may never ride an agent transport"* |

⛔ **And a second channel route needs no edit here.** Today the intersection is exactly `{slack}`;
the day `teams` gets an adapter, this line is already right.

⛔ **In the SAME transaction as the upsert**, deliberately: the revive must see the row it was
triggered by, and a registration that commits without it leaves the backlog parked until somebody
re-saves the same webhook. **Mutation M3 splits the transaction and a test fails.**

## 4 · The count is returned, not merely done

```python
return {"saved": True, "channel": "slack", "active": body.active, "revived": revived}
```

⛔ **The lesson `STEP-09` paid for**, applied one step later without having to be re-learned: a
record nobody reads is presence without effect. The one question this answers is *"did registering
the channel actually clear my backlog?"* — and now the response says so. **Mutation M6 drops it and
a test fails.**

## 5 · What was built

| | |
|---|---|
| `api/channel_routes.py` | the revive, gated by `deliverable_channels`, inside the upsert's transaction, with the count returned |
| `deliver/delivery_health.py` | the last `KNOWN_UNWIRED` entry **deleted** |
| `tests/deliver/test_a_parked_card_revives_when_a_channel_appears.py` | ⛔ NEW, **12 tests** |

```
KNOWN_UNWIRED   1 -> 0      ⛔ EMPTY
DECLARED       23 -> 22
```

### ⛔ `KNOWN_UNWIRED` is empty · `deliver/` has no known-unwired defects left

It held **five** on 2026-10-01 when `STEP-05` first drew it:

| | Closed by |
|---|---|
| `lane_recall.recall_verdict` | `STEP-14` — wired into `build_cards_for_org` |
| `lane_recall.low_confidence_is_never_silent` | ⛔ `STEP-14` — **reclassified**: a build-time property guard, not a defect |
| `lane_recall.every_lane_is_visible_or_deliberately_silent` | ⛔ `STEP-14` — same |
| `card_builder.resolved_person_name` | `STEP-08` — wired, gated on `person`, last in the chain |
| `outbox.revive_undeliverable` | **this step** |

## 6 · ⛔ A THIRD membership list of mine broke — and I had written the rule against it in `STEP-08`

`test_one_defect_is_left_in_the_known_unwired_table`, written **in `STEP-08`**, asserted
`set(H.KNOWN_UNWIRED) == {"outbox.revive_undeliverable"}`. This step emptied the table and it failed
on correct code.

⛔ **`STEP-08` is the step where I diagnosed exactly this pattern** — rewrote
`test_the_defects_are_not_filed_as_decisions` as an invariant and wrote down *"a membership list
shrinks every time the work succeeds; an invariant does not"* — **and then wrote a new membership
list a few sections later in the same session.**

> ⛔ **The rule was right and I did not generalise it.** Twice now: once by fixing a docstring and
> leaving the names, once by writing the rule and then breaking it. **A doctrine applied only to the
> instance that produced it is not a doctrine.**

Rewritten as `test_every_remaining_defect_names_the_step_that_closes_it`: however many entries
exist, each names its step, explains itself, and refers to a function that exists — and **an empty
table is a legitimate state.** The milestone is asserted as a *state* in the new test, with the
history in prose where a log belongs.

## 7 · Mutations

```
baseline        28 passed
restore verify  12 passed
```

| # | Mutation | Result |
|---|---|---|
| M1 | remove the revive from the route | 🔴 **7 failed** |
| M2 | ⛔ **hand-write the gate as `if body.active` + `"slack"`** | 🔴 3 failed — the `in_app` trap is guarded |
| M3 | move the revive into its own transaction | 🔴 1 failed |
| M4 | ⛔ **add the `expires_at` bound this plan proposed** | 🔴 1 failed |
| M5 | widen the predicate to every parked status | 🔴 1 failed |
| M6 | stop returning the count | 🔴 1 failed |

## 8 · Verify

```
.venv/bin/pytest tests/deliver/test_a_parked_card_revives_when_a_channel_appears.py -q   # 12 passed
.venv/bin/pytest tests/deliver/ tests/test_delivery_gate.py \
                 tests/test_proactive_channel_resolution.py tests/test_delivery_routes.py -q
                                                                                 # 424 passed
.venv/bin/pytest tests/test_layer_topology.py -q      # api/ is CROSS_CUTTING, so api -> deliver is legal
```

## 9 · Doctrine

| Rule |
|---|
| ⛔ **a dead row cannot tell "we chose not to send" from "we lost it"** — which is why waking it and letting authority kill it is strictly better |
| ⛔ **a doctrine applied only to the instance that produced it is not a doctrine** |
| ⛔ **re-deriving a canonical gate's conditions by hand is that gate's own defect, by hand** |
| **two writers of one table need not be two of the same thing** |
| **a count nobody can see is a count nobody checks** |
| **read the thing being changed before changing it** — three retracted fixes, all three caught this way |
