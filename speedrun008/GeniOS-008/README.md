# GeniOS 008 — one layer at a time, until the results match what we expect

**Written for:** Rohit, Harsh and any coding agent picking up a layer. **Started:** 2026-10-17.

**Read first: [`00-ARCHITECTURE.md`](00-ARCHITECTURE.md) — the architecture we build to.**

## Why this folder exists

The work so far is spread over three plan folders (`YCW27/`, `YC-II W27/`, and the layer folders
inside `YCW27/`), two branches (`speedrun008` and `harsh/mvp`, which is what production runs), and
documents from outside the repo (the Design Atlas, the Layer 1 Blueprint, the database-load analysis).
Much of it is built. Some of it is built and never called. Some of it is claimed and not true. It is
hard to say, for any one layer, **what works, what does not, and what is left**.

This folder answers that, layer by layer, checked against the code — never against a document.

## What GeniOS is, in one paragraph (the north star every layer is judged against)

LLMs generate, agentic SaaS executes, dashboards track — but no company has a continuously updated
understanding of what matters, what is going wrong and what must happen next. GeniOS connects the
company's data, workflows, dependencies and goals; detects execution gaps; decides the next action;
directs it to the right person or AI agent; monitors progress; and keeps adapting until the goal is
reached or human judgement is needed. *Palantir for company managers.*

## The layers — the new architecture (Design Atlas v2, 29 Sep), and the order we work in

```
L1 Enterprise Signals   capture/            what happened, how reliable, which incoming signals belong
                                            together — out: QualifiedEnterpriseSignalBundle + coverage receipt
L2 Reasoning (primary)  reason/ + packs/    what it means and the best next move — Orchestrator,
                                            Plane R (how a pro thinks), Plane D (what a pro knows), Tools
L3 Context Graph        context/            the company's trusted memory; admits what L2 concluded
L4 Executive            executive/          who decides; a decision becomes owned, dated work
L5 Delivery             deliver/            the card a human actually sees
L6 Learning             feedback/           attribute the miss to the layer that failed, then adapt
```

Target flow (Atlas v2 II.0): L1 bundle → **L2 reasons** (reads a bounded ContextSnapshot from L3,
asks L1 for missing evidence through EvidenceNeed) → L3 admits the situation → L4 → L5 → L6.
**We work in that order: L1, L2, L3, L4, L5, L6.**

⛔ **The code today still runs the OLD flow**: `capture/` → `context/` forms and admits the situation
→ `packs/` + `reason/` consulted → a `signals` row → a card (Atlas v2 L2.2 "today versus target").
Every layer here is judged against the **new architecture's target**, not against what the old
flow happens to do. Where the code does it the old way, that is a finding to fix, not a reason to
move the item to another layer.

## How each layer folder is laid out

| File | What it answers |
|---|---|
| `00-START-HERE.md` | where the layer stands in one screen, what is done and what is next, and who owns what |
| `01-AS-IS.md` | what was already there · what works · what does not — every line with its `file:line` |
| `02-PLAN.md` | what must change, in order: each item's problem, the fix, why that fix, how we prove it |
| `03-LOG.md` | what was done, when, with its commit and the command that proved it (append-only) |
| `04-FOR-HARSH.md` | what production needs: what changed, what to run, in what order, what to watch |

**Rules for every layer.**

1. A claim in a document is not a fact. It is checked against the code first; if it disagrees, the
   document is corrected first.
2. "Built" is not "working". A module counts only if production reaches it — its caller chain is named.
3. Nothing is called done until its test runs, its mutation (the fix removed) makes the test fail, and
   CI is green (full suites run in CI, not locally).
4. Anything noticed outside the item being fixed becomes a new line in `02-PLAN.md`, never a silent fix.

## Layers

| Layer | Folder | State |
|---|---|---|
| L1 Enterprise Signals | [`layer-1-enterprise-signals/`](layer-1-enterprise-signals/00-START-HERE.md) | as-is written 17 Oct · plan written · fixing |
| L2 Reasoning | — | next, after L1 |
| L3 Context Graph | — | |
| L4 Executive | — | |
| L5 Delivery | — | |
| L6 Learning | — | |
