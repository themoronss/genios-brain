# Step 7 — ✅ DONE · the evidence-need door · owner: us

> **Status:** TO BUILD · **not blocked on the API limit** · needs [Step 6](STEP-06-signal-bundle.md) to attach to
> **Tree:** `M9.C2`, units `U06`–`U09`
> ⛔ **This is the one architectural edge the whole system is missing.**

---

## 1 · What is true today

Layer 2 can only **HOLD and wait**. If a situation is incomplete, it stays incomplete until some
future sweep happens to bring the missing fact in by luck.

`context/residue.py` **already computes the demand** — its `signal_unreached` measures *"the Layer 1
verdicts no Layer 2 reading consumes"* — and that number reaches the model angles and stops there.
It never reaches `capture/`.

> The measurement half exists. Only the wire does not.

## 2 · What it costs today

| Cost | Detail |
|---|---|
| **the 60-day wall** | P3 asks six months, P4 twelve; the connection fetches 60 days. Those benchmarks are not unproven — they are **structurally impossible**, because the mail was never fetched |
| **`"message 1 of 1"`** | every prompt Layer 1 ever sent told the model this was the only message in its thread, including on a twelve-message negotiation. Fixed — but only for mail arriving from now on, because nothing can ask for the old mail again |

## 3 · The units

| Unit | What | ⛔ The constraint that matters |
|---|---|---|
| `U06` | `EvidenceNeed` contract | **acceptable AND unacceptable sources.** A vendor quote email may not stand in for a signed contract, and the contract is the only place that is enforceable |
| `U07` | `evidence_needs` table | open / met / **unavailable** — never hard-deleted |
| `U08` | the executor — fetch the thread · backfill history · re-extract an attachment | bounded by the need's own cost limit and expiry |
| `U09` | `residue.signal_unreached` raises a need | **the missing wire** |

## 4 · Scenario → expected result

| Scenario | Expected |
|---|---|
| a situation is HELD for a missing signed contract | an `EvidenceNeed` is raised naming the document and what would NOT do instead |
| the document arrives | the need closes `met`; the hold clears on the next sweep |
| the document does not exist anywhere connected | the need closes **`unavailable`, with a reason** — ⛔ never left open, because a permanently open need is a hold that can never clear |
| a thread predates the 60-day window | the need asks for that thread specifically, not a whole re-sync |
| the same need is raised twice | idempotency key collapses it to one |

## 5 · Why this is not "just a backfill"

A backfill fetches everything and hopes. An `EvidenceNeed` names **one fact, for one decision, with
a cost limit and an expiry**, and records what would and would not settle it. That is the difference
between widening a window and asking a question.

## 6 · Known unsound verify

`U07`'s verify names `tests/platform/test_migrations_apply.py`, which does not exist — same as
[Step 6](STEP-06-signal-bundle.md) `U02`. One fix covers both.

---

# ✅ DONE — 2026-09-30 · all four units

| Unit | Artifact | Tests |
|---|---|---|
| `U06` | `contracts/evidence.py` · `EvidenceNeed` | 18 (with U07) |
| `U07` | `migrations/0187_evidence_needs.sql` | ↑ |
| `U08` | `capture/acquire/evidence_need.py` · the executor | 17 |
| `U09` | `context/evidence_needs.py` · **the wire** | 15 |

**Full suite: 13,471 passed · 1 failed** — the 1 is the pre-existing OCR test
([Step 8](STEP-08-PENDING-HARSH-ocr.md)).

## ⛔ U09 · the design is the EXCLUSION, not the inclusion

Residue has four kinds. **Only one becomes a need:**

| Kind | Need? | Why |
|---|---|---|
| `signal_unreached` | ✅ | L1 published a verdict no reading consumed — there may be evidence we never fetched |
| `node_evidence_unread` | ❌ | the evidence is **held**. Nothing is missing; no reading spoke about it |
| `ball_in_court` | ❌ | *"they replied and we went quiet"* is a fact about **us** |
| `open_loop` | ❌ | an ask attached to nothing is a **linking** gap, not an evidence gap |

Raising needs for all four would send Layer 1 fetching for what it already delivered — a backfill
with extra steps — and every one of those needs would then **close successfully**, teaching the
system that its questions are always answered. That is worse than not asking.

**A subjectless residue row raises nothing.** The executor would have nothing to fetch for and no
way to know when it was done: a row that sits open forever, which is the state this step exists to
end.

## ⛔ U08 · the three refusals that keep an executor from being a backfill

1. **An expired need is never fetched** — and a test proves it does not even reach the fetcher. The
   answer would arrive after the decision it was for.
2. **A budget below the cheapest fetch closes rather than half-fetching.** *"A partial fetch would
   answer partly and close fully"* — a partial answer looks like an answer, and the hold clears
   on it.
3. **A substitute source never closes the need.** Something was found and it is not what was asked
   for. Closing on it lets Layer 2 proceed on evidence that cannot carry the claim — worse than the
   hold it replaced, because the hold at least knew it was missing something.

## ⛔ Every path ends in a CLOSED need

`met` or `unavailable`, and `unavailable` always carries a reason — **including when the fetcher
raises.** Leaving it open on an exception re-creates the permanently-open need this contract exists
to prevent, and hides a broken connector behind a hold that simply never clears.

The schema enforces it too: `evidence_needs_unavailable_has_a_reason` means a closure with no
explanation cannot be written by anything holding a connection, not just by the contract.

## ⛔ It flows through data, never by calling capture

`context/` may import `capture/` — but it must not **call** it, because a sweep that fetched inline
would make a graph pass wait on a network. The need is a row; the executor picks it up. A test reads
the module's own source to prove `genios_engine.capture` never appears in it.

## What is NOT wired yet

`U08`'s `fetchers` map is **injected**, and nothing injects real connectors yet. That is deliberate:
the unit is a pure decision over a need and is testable without a network. Wiring the three real
fetchers — thread, backfill, re-extract — is an integration step, and it belongs with the
composition root rather than here.


---

## ⛔ 2026-10-01 · the title line of this file was stale, and is corrected above

This file's **first line** read `Step 7 — TO BUILD · the evidence-need door · owner: us` while the `✅ DONE — 2026-09-30` section below recorded the
work as built, and the filename had already been renamed to `...-DONE-...`. Three labels on one
piece of work and one of them disagreed with the other two.

**Why this is recorded rather than quietly fixed.** A heading that says *TO BUILD* on finished work
is the same defect as a stale comment: it reads as a status somebody checked. Anyone auditing the
programme by scanning headings would have counted this step as outstanding and, worse, might have
rebuilt it. Found while assembling `07-LEDGER-every-step-what-why-how-outcome.md`, which reads the
first line of every step file — the ledger could not have been written without resolving it.

**What was verified before the title was changed:** the artifacts named in the DONE section exist in
the tree, and the full suite is 14,534 passed / 0 failed. The title was not made to agree with the
others; it was made to agree with the code.
