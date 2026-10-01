# YCW27 — the working folder for the new architecture

> ## ⛔ 2026-10-01 · START WITH THESE
>
> 1. **`17-THE-THREE-LAYERS-end-to-end.md`** — L1, L2 and L3 end to end, every number measured
> 2. ⛔ **`layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md`** — **why the product has
>    produced no card since 2026-09-25**, traced link by link. L4 needs no build work
> 3. **`02-DECISIONS.md` decision #5** — three options, one line, Rohit's. **No card is produced
>    until it is answered**
> 4. **`STATUS.md`, LAST section** — the live task list. The table at line 745 is stale

**Branch:** `speedrun008` @ `c7cdf4c1` (harsh/mvp merged in, 30 Sep 2026)
**Supersedes:** `../Ancient Architecture/` — every document that planned the system before the
Design Atlas v2. Nothing in there is deleted and nothing in there is authoritative any more.

---

## ⛔ START WITH [`07-LEDGER-every-step-what-why-how-outcome.md`](07-LEDGER-every-step-what-why-how-outcome.md)

**Every step in the programme, with the task it was given, why it mattered, and what actually came
out** — layer by layer, including where the outcome differed from the plan. One page covers all six
layers, both planes, and the five cross-cutting audits.

Then, depending on who you are:

| You are | Read |
|---|---|
| **Rohit** | [`STATUS.md`](STATUS.md) — the ALARMS table at the bottom is your decision list |
| **Harsh** | [`HANDOFF-HARSH.md`](HANDOFF-HARSH.md) — five items, ordered by what they unblock. **H1 is breaking a write path right now** |
| **a coding agent** | [`HANDOFF-CODING-AGENT.md`](HANDOFF-CODING-AGENT.md) — three standalone briefs, and the twelve rules this repo will fail your build over |
| **auditing a decision** | [`05-FIX-LOG.md`](05-FIX-LOG.md) — append-only, 958 lines, every fix with its reasoning |

### ⛔ Where the programme actually stands — 2026-10-01

    40 step files        34 DONE · 3 PENDING · 2 WITHDRAWN · 1 RETIRED
    full suite           14,534 passed · 0 failed
    prod receipts (29)   21 PASS · 7 FAIL · 1 ERROR

**All six layers and both planes are built.** L1, L2 (spine + Plane D + Plane R), L3, L4 (M12),
L5 (M13), L6 (M14). Every remaining red is a deployment, a connector or a decision — **not one is a
mis-asked question**, and every one has a named mover on the table in `07-LEDGER` PART 4.

⛔ *The line that used to be here said "Layer 3 is finished, Layer 2 is planned, no code written."
That was true on 2026-09-30. It is corrected rather than deleted, because a stale status line reads
as a status somebody checked — the defect that cost seven step files their titles, recorded in
`07-LEDGER` PART 3.*

⛔ **Why the layer numbers look backwards.** We build in DATA-FLOW order, not Atlas number order:
`L1 capture → L3 context → L2 reason → L4 → L5 → L6`. Nothing above can be fed better than the layer
below hands up. So *"layer 1, then layer 3, then layer 2"* is correct. **"Next layer" always means
next in the data flow, never next number.**

---

## What this folder is

One folder per layer, plus the four documents that have to be true before any layer is touched.
Work happens **inside a layer folder**, never across two at once, and every change is addressed by
a unit id from `tree.yaml` (`M8`…`M14`) so a second session can pick up the same work without
guessing what was meant.

## How it is organised

```
YCW27/
  README.md                        ← you are here
  00-ARCHITECTURE.md               what the architecture IS, and how it works
  01-BASELINE.md                   what is measurably true on 30 Sep — the floor we build from
  02-DECISIONS.md                  four questions that block every layer until answered
  03-PROGRAM.md                    what we are going to do, in order, with the unit ids

  layer-1-enterprise-signals/      capture/
  layer-2-reasoning/               reason/ + packs/   ← the primary layer
      plane-r-reasoning-units/       how a professional THINKS
      plane-d-domain-expertise/      what a professional KNOWS
  layer-3-context-graph/           context/
  layer-4-executive/               executive/
  layer-5-delivery/                deliver/
  layer-6-learning/                feedback/
```

## How to use it

1. **Read `01-BASELINE.md` before anything.** It is the only document here written from runs
   rather than plans. If a sentence elsewhere disagrees with it, the baseline wins.
2. **`02-DECISIONS.md` gates the rest.** Four decisions; each one is recorded as *enforced code*,
   not prose, when it is made. Until a decision lands, the layers that depend on it stay shut.
3. **Then one layer folder at a time**, in the order `03-PROGRAM.md` gives — which is the data-flow
   order, not the Atlas's numbering.

## The two rules this folder exists to protect

**A badge is not evidence.** The Atlas calls several things `gap` that are already built, and one
of them — coverage receipts — is built *better* than the Atlas specifies. A previous plan already
made this mistake once with the DecisionObject and the code investigation had to correct it. Every
claim here carries the file that settles it.

**A layer is finished when it is measured, not when it is merged.** Every unit in `tree.yaml`
carries one command that exits 0. A skip is not a pass, and an incomplete run is not green.
