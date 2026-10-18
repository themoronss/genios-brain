# L2 Reasoning (`reason/` + `packs/`) — start here

**Status 18 Oct 2026:** spec received · as-is measured · plan written · **not built** (waits for Rohit to open the build).

**L2's job:** this is the primary layer. It answers: *what does this mean, given what the company already knows and what
an expert knows, and what is the best next move?*

**How it does it.** An **LLM-led** reasoning pass over:
- bounded company context;
- history;
- domain expertise.

Deterministic code only supports it. The output is a structured `ReasoningResult`, never a decision for a human.

## In one screen

- **What exists:**
  - the change gate;
  - the Domain Compiler and expertise package;
  - the planner;
  - receipts and replay;
  - the claim check;
  - lanes;
  - and above all the **STEP-12 expert pass**: a Sonnet-class review whose output already has the ReasoningResult's shape, but only for *files* and only where switched on.
- **What is wrong for the new architecture:**
  - situations are formed in L3 before reasoning;
  - 23 deterministic reasoners and pack rules decide by formula;
  - no `ReasoningResult`;
  - a whole-org context read;
  - no need classification;
  - L2 raises no EvidenceNeed;
  - the confidence vector is not the six dimensions.
- **The plan.** 9 groups, A to I, 23 units. Contracts first, then context assembly, the orchestrator, the judgment pass, the evidence loop, validation, handoff, demotion of the formula units, shadow + first switch.

## Read order

1. [`05-SPEC-layer-2.md`](05-SPEC-layer-2.md) — Rohit's L2 spec, verbatim.
2. [`01-AS-IS.md`](01-AS-IS.md) — what the code has, judged against the spec.
3. [`02-PLAN.md`](02-PLAN.md) — the plan.
4. [`04-FOR-HARSH.md`](04-FOR-HARSH.md) — Harsh: start there.
5. [`06-GAP-ANALYSIS.md`](06-GAP-ANALYSIS.md) — what exists vs what is new, component by component, and one run step by step.
6. [`03-LOG.md`](03-LOG.md) — what was done, with proof.

## What Rohit decides before the build (asked once)

| # | Question | Recommended default |
|---|---|---|
| L2-Q1 | Is `02-PLAN.md` §0 right: the LLM judges meaning, materiality, priority and confidence in words with evidence; deterministic code never decides; routing, recipients, permissions and approvals stay outside the model? | Yes |
| L2-Q2 | Do the 23 deterministic reasoners become tools only (their scores decide nothing)? | Yes |
| L2-Q3 | Should the judgment pass start from the STEP-12 expert pass, generalised from files to situations? | Yes |
| L2-Q4 | The first situation type to switch | Awaiting reply / outreach (same as `../03-QUESTIONS.md` A3) |
| L2-Q5 | Model and budget for the judgment pass | Sonnet-class, $2/day for your org (same as A6); the strongest class only where the golden set shows it pays |
| L2-Q6 | The subject of one reasoning run (`06-GAP-ANALYSIS.md` §4) | The file when the bundle's counterparty has one, else the seed entity/thread from the bundle |

Already asked in `../03-QUESTIONS.md`, not repeated here: A1, A2, A4, A5 (retire the LLM decider), E2 (budget for live evaluations).
