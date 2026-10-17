# GeniOS 008 — one layer at a time, until the results match what we expect

**Written for:** Rohit, Harsh and any coding agent picking up a layer. **Started:** 2026-10-17.

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

## The layers, and the order data flows through them

```
L1 Enterprise Signals      capture/            what happened, from which source, with what evidence
L3 Context Graph           context/            what the company remembers
L2 Signals Qualification   packs/ + reason/    what it means, and what should happen (Plane D + Plane R)
L4 Executive               executive/          the decision and the plan
L5 Delivery                deliver/            the card, the brief, the draft
L6 Learning                feedback/           what the founder's corrections and the outcomes teach
```

Data flows L1 → L3 → L2 → L4 → L5 → L6. A layer can only reason as well as the layer below it
remembers, so we go in that order.

## How each layer folder is laid out

| File | What it answers |
|---|---|
| `00-START-HERE.md` | where the layer stands in one screen, what is done and what is next, and who owns what |
| `01-AS-IS.md` | what was already there · what works · what does not — every line with its `file:line` |
| `02-PLAN.md` | what must change, in order: each item's problem, the fix, why that fix, how we prove it |
| `03-LOG.md` | what was done, when, with its commit and the command that proved it (append-only) |

**Rules for every layer.**

1. A claim in a document is not a fact. It is checked against the code first; if it disagrees, the
   document is corrected first.
2. "Built" is not "working". A module counts only if production reaches it — its caller chain is named.
3. Nothing is called done until its test runs, its mutation (the fix removed) makes the test fail, and
   the repo-wide guards are green.
4. Anything noticed outside the item being fixed becomes a new line in `02-PLAN.md`, never a silent fix.

## Layers

| Layer | Folder | State |
|---|---|---|
| L1 Enterprise Signals | [`layer-1-enterprise-signals/`](layer-1-enterprise-signals/00-START-HERE.md) | as-is written 17 Oct · plan written · fixing |
| L3 Context Graph | — | next, after L1 |
| L2 Signals Qualification | — | |
| L4 Executive | — | |
| L5 Delivery | — | |
| L6 Learning | — | |
