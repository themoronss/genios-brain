# Step 11 — DONE · the Atlas does not know Layer 5.2 exists

**Unit:** `M13.C3.U11` · **Owner:** me · ✅ **2026-10-01** · a document correction, not code
⛔ **And one code change it did not plan: a cross-layer test my targeted runs had missed.**

## 1 · What is there

`08-ATLAS-SCORECARD-L1-to-L4.md` carried 35 verified claims (now `-L1-to-L5`, **45**). **L5 is not in it** — the scorecard stops at
L4. Measuring L5's claims produced three badge corrections and one omission.

## 2 · The three badges to correct

| Atlas claim | Badge | What is actually there |
|---|---|---|
| claim-level validation | `target` | ⛔ **BUILT** — `claim_validator.py` + `claims.py`, M13 STEP-03/04, shared 34 tests |
| *"no lanes on the card"*, called **L5's biggest gap** | `gap` | ⛔ **BUILT** — `lane_display.py` + `lane_recall.py`, M13 STEP-01/02, 55 tests, `migrations/0190_card_lane.sql` |
| three delivery failures *"to design out"* | `target` | ⛔ **ALL THREE ALREADY GUARDED** — evidence in `05-RECROSSCHECK §2` |

Plus two the 2026-09-30 crosscheck already corrected, restated so the scorecard row stands alone: there is
**no scalar publication floor in `deliver/`** (the gate is `reason/runner.py:1133`, its `below_gate`
receipt already read by `executive/explain.py`), and **the invention validator exists**
(`render.py:334` → `:861` → `executive/validate.py:69`).

⛔ **Two of these three were changed by this programme itself**, four days ago and one step before the
document that calls them gaps. So the Atlas is not wrong — it is **superseded**, and the distinction
matters: a wrong claim gets argued with, a superseded one gets dated.

## 3 · ⛔ The omission, which is the larger half

`deliver/` contains a five-phase pipeline the Atlas names **nowhere**:

| Phase | Module | What it is |
|---|---|---|
| 2 | `presence.py` | the Delivery Context Resolver — who is reachable, where, right now |
| 2 | `orchestrator.py` | seven responsibilities → one materialised `DeliveryObject` |
| 3 | `spine.py` | the durable outbox spine — claim, fence, attempt, settle |
| 4 | `tracker.py` | the Delivery Tracker |
| 5 | `units.py` | the **eleven delivery units** and their capability registry |
| 5 | `analytics.py` | Delivery Analytics |

⛔ **This is a gap in the document that is supposed to describe the code, and it is the dangerous
direction.** A badge that says `gap` on built work costs a wasted unit. An omission costs a *rebuild*: the
next person planning L5 from the Atlas plans to build `presence.py`. L2 paid **six units** for one absent
fact, which is the most expensive single lesson in this programme.

## 4 · The size claim, which is nearly right and worth recording as such

| | |
|---|---|
| Atlas | *"36 files · 8,674 lines"* |
| measured 2026-10-01 | **40 files · 9,431 lines** — 36 top-level (8,997) + `channels/` 4 (434) |

⛔ The **36 matches the top-level count exactly**, so the Atlas counted top-level files only and did not
descend into `channels/`. Then 323 lines landed in those 36 files since. **Not an error — a counting
convention plus four days.** Recorded because a reader comparing 36 to 40 would otherwise conclude the
Atlas was careless, and it was not.

## 5 · The eight-surface claim

The Atlas names eight delivery surfaces and marks *"Budget and surfaces"* as `target`. Measured:
`units.py` has **11 units over 11 distinct channels**, with a fail-closed `capability_report`.

| | |
|---|---|
| push channels with an adapter | **2 of 6** — `slack`, `agent_push` |
| missing | `api`, `email`, `teams`, `webhook` |
| units with no reachable channel | **3 of 11** — `api`, `webhook`, `email` |
| units declaring `engine_ready=False` | **1** — `email`, the honest one |

⛔ **This row stays `target`, and the reason must be written in: it is a deployment and product fact, not a
code gap.** `capability_report` reports every one of these correctly and errs toward claiming *less*
capability — it names `no_adapter` as **our** gap rather than the tenant's, and it deliberately excludes
`in_app`/`dashboard` from needing an adapter because demanding one *"would report the one delivery path
that actually works today as broken."*

## 6 · What to build

| | |
|---|---|
| `speedrun008/YCW27/08-ATLAS-SCORECARD-L1-to-L4.md` | ⛔ **rename to `-L1-to-L5.md`** and add the L5 claims. The file was already renamed once, L1-to-L3 → L1-to-L4 |
| `speedrun008/YCW27/STATUS.md` | the L5 re-crosscheck and its eight steps |
| `speedrun008/YCW27/07-LEDGER-every-step-what-why-how-outcome.md` | the L5 re-crosscheck as a programme step, with the doctrine rules from `05-RECROSSCHECK §12` |
| `layer-5-delivery/00-START-HERE.md` | ⛔ it currently says **COMPLETE** with four steps. Eight more exist. Correct it — *a stale status reads as a status somebody checked* |

## 7 · Verify

```
.venv/bin/pytest tests/test_programme_step_status_is_consistent.py -q
```

⛔ Four checks, and they are the reason this step is verifiable at all: a status from the closed set in
**both** filename and title, filename and title agreeing, a `PENDING` step naming its owner, and all four
programme documents present in every layer folder.

## 8 · Expected outcome

The scorecard covers L5. The three superseded badges are dated rather than argued with. And the
architecture the Atlas omits is written down where the next planner will look, so nobody rebuilds
`presence.py`.


---
---

# ✅ DONE — 2026-10-01

## 1 · The scorecard now covers L5 — 10 claims, **5 superseded and 1 omission**

`08-ATLAS-SCORECARD-L1-to-L4.md` → **`08-ATLAS-SCORECARD-L1-to-L5.md`**, 125 → **200 lines**,
**35 → 45 claims.** The second rename of this file; the first was `-L1-L2-L3` → `-L1-to-L4`.

```
L1 + L2 + L3    24 claims
L4              11 claims    2 superseded, 2 imprecise
L5              10 claims    ⛔ 5 superseded, 1 OMISSION, 2 imprecise
───────────────────────────
total           45 claims
```

⛔ **L5 is the layer the Atlas is most out of date about, and the direction is consistent: it calls
built things gaps.** Three of the five supersessions were created by **this programme, four days
before the document was read.**

| | What the Atlas said | Verdict |
|---|---|---|
| **L5-02** | claim-level validation is a `target` | ⛔ built — `claim_validator.py` + `claims.py` |
| **L5-03** | *"no lanes on the card"* is **L5's biggest gap** | ⛔ built — and **this programme created that gap one step earlier** |
| **L5-04** | three delivery failures *"to design out"* | ⛔ **all three already guarded**, two with the fault that taught the lesson recorded in the code |
| **L5-05** | *"replace the scalar publication floor"* | ⛔ there is no scalar floor in `deliver/`; the gate is `reason/runner.py:1133` and its receipt is already read |
| **L5-06** | the invention validator is missing | ⛔ `render.py:334`, called, re-exported, tested |
| **L5-01** | 36 files, 8,674 lines | ⚠️ **40 / 9,431** — the 36 matches the top-level count exactly, so it is a counting convention plus four days |
| **L5-07** | *"Budget and surfaces"* is a `target` | ⚠️ **stays `target`** — 2 of 6 push channels have an adapter, 3 of 11 units have no reachable channel, and `capability_report` is **honest and fail-closed**. A deployment fact, not a code gap |
| ⛔ **L5-08** | — | **THE OMISSION.** Six modules, five phases, named **nowhere**: `presence` · `orchestrator` · `spine` · `tracker` · `units` · `analytics` |
| ⛔ **L5-09** | — | and that architecture is **connected at one tier of four**, shadow-measured at tier 1 only |
| ⛔ **L5-10** | — | and the reachability question is **not L5's alone**: 147 functions engine-wide |

## 2 · ⛔ Why the omission is worse than any wrong badge

> **A `gap` badge on built work costs a wasted unit. An omission costs a REBUILD** — because nothing
> in the document tells you to look. The next person planning L5 from the Atlas plans to build
> `presence.py`.

L2 paid **six units** for one absent fact. That is the price of the direction this document errs in.

## 3 · ⛔ The code change this step did not plan

`STEP-10` added two L5 receipts, and the **full suite** failed one test in `tests/executive/` —
which my targeted runs (`tests/platform/`, `tests/deliver/`) never touched.

```
test_the_two_new_receipts_exist_and_the_channel_one_was_not_duplicated
    assert sum("channel" in c for c in claims) == 1      ->   assert 2 == 1
```

⛔ **It counted the WORD, not the QUESTION.** Measured, the two are opposite-conditioned:

| | L6 | L5 (new) |
|---|---|---|
| claim | *"there is a channel this tenant can be reached on"* | *"a card parked for want of a channel is revived when one appears"* |
| subject | `from org_channels` | `from delivery_outbox` |
| passes when | count **> 0** | count **== 0** |
| precondition | none | ⛔ **a channel EXISTS** |

They cannot disagree: one asks whether a channel exists at all, the other only measures a backlog
once one does. So the guard's **intent** — *one receipt owns the channel-existence question* — was
right and its **mechanism** was too broad.

⛔ **Rewritten STRICTER, not looser:** it now counts receipts whose **outer subject** is
`org_channels`, so a duplicate is caught even if its claim never says "channel" — which the substring
count would have missed entirely.

⛔ **And my first attempt at that was substring-shaped too.** I checked `"from org_channels" in
r.sql` and caught the new L5 receipt as well, because that table appears in its `EXISTS` subquery.
**A receipt's subject is what its first `from` names; everything after is a condition on it.** Two
substring-shaped guards in a row, and the second was mine.

> ⛔ **Two targeted test runs are not a suite run.** Written down twice in this programme before
> today, and this is what it costs when ignored: a cross-layer break that sat green through two
> targeted passes.

⛔ **And an arbitrary subset is not a smaller suite.** Re-running every receipt-touching file by hand
produced **8 errors** in `tests/reason/adapters/test_play_cap.py` — which passes alone (13) and had
**zero** errors in the full run. A hand-assembled file list can manufacture failures the real suite
does not have, which is a second reason the full suite is the authority.

## 4 · What was written

| | |
|---|---|
| `08-ATLAS-SCORECARD-L1-to-L5.md` | ⛔ renamed; 35 → **45** claims; 125 → **200** lines |
| `17-THE-THREE-LAYERS-end-to-end.md` | the **live** pointer updated to the new name and count |
| `STATUS.md` | ⛔ the **historical** row kept as written, with a forward pointer — *a log records the state on the day it was written*, the same rule that keeps `receipts.py:190`'s numbering correct forever |
| `tests/executive/test_an_unroutable_tenant_says_why.py` | the channel-duplication guard now counts the question |

## 5 · Verify

```
.venv/bin/pytest tests/executive/test_an_unroutable_tenant_says_why.py -q     # 30 passed
.venv/bin/pytest tests/test_programme_step_status_is_consistent.py -q         # 6 passed
.venv/bin/pytest -q                                                          # ⛔ the FULL suite
```

## 6 · Doctrine

| Rule |
|---|
| ⛔ **an omission costs a rebuild; a wrong badge costs a unit** |
| ⛔ **two targeted test runs are not a suite run** — and **an arbitrary subset is not a smaller suite** |
| ⛔ **a guard that counts a word is not counting the question** |
| **a receipt's subject is what its first `from` names; everything after is a condition on it** |
| **a log records the state on the day it was written — date it, do not rewrite it** |
| **a document that has fallen behind the code is superseded, not wrong — and still dangerous** |
