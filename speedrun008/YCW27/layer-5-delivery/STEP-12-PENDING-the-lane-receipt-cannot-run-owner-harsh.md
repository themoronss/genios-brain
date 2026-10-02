# Step 12 — PENDING · the lane receipt cannot run · owner: Harsh (CTO)

**Unit:** `M13.C3.U12` · ⛔ **Blocked on H1.** Not buildable by me, and the code is already written.

## 1 · What is there

The **lane receipt** — *"every delivered card carries a lane, or is labelled unrouted"* — **ERRORs** in
production. Not FAILs. **ERRORs**, because `cards.output_lane` does not exist.

The migration that adds it, `migrations/0190_card_lane.sql`, is the **fifth unapplied migration**:
`0186`, `0187`, `0188`, `0189`, `0190`. None has ever run in production.

## 2 · ⛔ Why this is the most urgent item in L5 and the one I cannot touch

`0190` does not merely block a receipt. **`insert_card` fails on write without it.**

M13 STEP-01 added `cards.output_lane` and `cards.lane_reason` as columns the card writer populates. The
code shipped. The migration did not run. So the moment a card is written in production, the insert
references a column that is not there.

> ⛔ It has not been hit yet **only because no production signal has been routed since the Anthropic API
> spend limit began refusing every model call on 2026-09-25 11:09 UTC.** The spend limit is masking a
> broken write path. Clearing one without the other turns a silent outage into a loud one.

## 3 · What Harsh has to do

```
Apply migrations 0186, 0187, 0188, 0189, 0190 — in order, in one window.
```

| Migration | What it adds | What it unblocks |
|---|---|---|
| `0186` – `0188` | see `HANDOFF-HARSH.md` H1 | — |
| `0189` | `signals.output_lane`, `signals.lane_reason` | the router's writes |
| `0190` | `cards.output_lane`, `cards.lane_reason` | ⛔ `insert_card` · the *lane* receipt · the `0189` header correction |

⛔ **`0190` carries the `0189` header correction, append-only.** `0189`'s header states the lane is inside
`decision_hash`. It was, it broke four replay tests, and it was removed — `route()` is pure over inputs
already in the hash, so a derived value has no business in a content hash. A migration's checksum is its
immutability, so the correction could not be edited into `0189` and lives in `0190`, with a test asserting
it is there. **Applying `0190` without `0189` is not a shortcut; it is a different thing.**

## 4 · How anyone confirms it landed

```
.venv/bin/python scripts/runtime_receipts.py          # the lane receipt must move from ERROR to PASS or FAIL
```

⛔ **PASS or FAIL are both acceptable outcomes; ERROR is not.** A FAIL would mean cards exist that carry no
lane and are not labelled `unrouted` — a real answer to a real question. ERROR means the question cannot be
asked at all, and an unaskable question is the only outcome that teaches nothing.

⛔ Any confirming read runs in `set transaction read only`. **`GENIOS_ALLOW_PROD_WRITE` is never set to run
a report** — that variable is named for writes because it was written for writes, and setting it to run a
report is the wrong shape of permission. Applying a migration is a write and uses the migration tooling,
not that flag.

## 5 · Expected outcome

`insert_card` can write. The lane receipt asks its question and gets an answer. L5 goes from **one** working
production guard to two, before STEP-10 adds any.

## 6 · Why it is recorded as a step rather than left in the handoff

It is already in `HANDOFF-HARSH.md` as H1. It is repeated here because L5's own step sequence would
otherwise read as eight items I can finish, and the one item nobody on the code side can finish is the one
breaking a write path. ⛔ **A plan that lists only the work its author can do is not a plan for the
layer.**


---

## ⛔ RENAMED 2026-10-01 · this file was `STEP-12-PENDING-receipt-20-cannot-run-owner-harsh.md`

`STEP-10` added two L5 receipts earlier in the list, so the lane receipt's position moved from #20
and **the number in this filename stopped being true.** Nothing referenced the old name, so the
rename cost nothing — but the lesson is cheaper to learn here than in a support thread:

> ⛔ **Refer to a receipt by its claim, never by its position — unless you are quoting a dated run,
> where the position is part of what was measured.**

`platform/receipts.py:190` quotes `#19 / #21 / #22 / #14` with values under *"Measured 2026-10-01"*.
That is a **snapshot of one run**: the numbering is part of the measurement and correct forever. A
filename is not a snapshot, and neither is a cross-reference in a plan.

⛔ **Every test in the repo already filtered by claim** — `[r for r in receipts(None) if "lane" in
r.claim]` — which is why the full suite stayed green while the prose and this filename went wrong.
