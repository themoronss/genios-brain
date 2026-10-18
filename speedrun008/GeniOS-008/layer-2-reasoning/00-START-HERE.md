# L2 Reasoning (`reason/` + `packs/`) — start here

**Status 18 Oct 2026 (evening):** Rohit opened the build ("saari cheezein code karo"). **The judgment pass is built
and runs in SHADOW** behind the `l2_reasoning` switch (off by default). Built: A1–A4, B1, B2, B4, C1, C2, D1, E1,
F1, F2, G1, G3, I1 (report). Partly: B3, D2. Not yet: G2 (needs L3's admission), H1–H3 and I2 (need the shadow
comparison first). The L2-Q1…Q6 defaults were taken as answers — see the table below. Harsh: section G-1 of
[`04-FOR-HARSH.md`](04-FOR-HARSH.md).

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

## Build status, unit by unit (18 Oct)

| Unit | What | State | Where |
|---|---|---|---|
| L2-A1 | `ReasoningResult` | ✅ built | `contracts/reasoning_result.py` |
| L2-A2 | `HistoricalContext`, receipt v2 (`ReasoningReceipt`) | ✅ built | same |
| L2-A3 | `L2Request`, closed triggers | ✅ built | same |
| L2-A4 | six-dimension confidence, levels + reasons | ✅ built | same |
| L2-B1 | Context Adapter: bounded snapshot, revision, cap printed | ✅ built (live read; as-of is L3's) | `reason/l2/snapshot.py` |
| L2-B2 | History Assembler: comparable past work | ✅ built | `reason/l2/history.py` |
| L2-B3 | Expertise package, one version + hash | ◐ partly: the file's playbook, brief, corrections ride in the file dossier and are hashed into `expertise_ref`; Plane D domain packages for a *seed* subject are not folded in yet | `reason/l2/sweep.py` |
| L2-B4 | Tool gateway | ✅ built (dates, turn, due, waiting, quiet; **no money tool**) | `reason/l2/tools.py` |
| L2-C1 | Plan compiler: depth from measured inputs + the model's own request | ✅ built | `reason/l2/plan.py` |
| L2-C2 | Change gate at the front | ✅ built (the fingerprint, every clock a rung) | `reason/l2/sweep.py` |
| L2-D1 | The judgment pass, file → subject; six blocks; Groups 1–6 | ✅ built | `reason/l2/dossier.py`, `prompt.py`, `judge.py` |
| L2-D2 | Model routing per depth | ◐ partly: one site (R-9, Sonnet-class); depth sets the repair (deep may spend a third call) and the prompt's emphasis. Per-depth models wait for a measurement | `reason/bundle/sites.py` |
| L2-E1 | Evidence coordinator: raise, re-enter once | ✅ built (needs stay open until L1 fetchers are armed) | `reason/l2/evidence.py` |
| L2-F1 | Claim check on every result | ✅ built (STEP-13 `check_review`, reused) | `reason/l2/judge.py` |
| L2-F2 | Structure, time, epistemic, authority validators | ✅ built | `contracts/reasoning_result.validate_judgment` |
| L2-G1 | Store, one transaction per sweep | ✅ built | `reason/l2/store.py`, migration 0243 |
| L2-G2 | Proposed mutations → L3 admission | ⏳ L2 side done (proposals stored, validated); L3 builds the gate | — |
| L2-G3 | Replay with no model | ✅ built | `reason/l2/replay.py` |
| L2-H1 | Formula reasoners → tools | ⏳ the new path uses none of their scores; their removal waits for the cutover | — |
| L2-H2, H3 | Retire the LLM decider, the per-pack rule lane | ⏳ at cutover, per situation type | — |
| L2-I1 | Shadow beside the old path; compare | ✅ shadow runs; report built (`scripts/l2_shadow_report.py`); golden-set scoring of the new path is next | — |
| L2-I2 | First switch (awaiting reply / outreach) | ⏳ after I1 shows it is at least as good | — |

## Read order

1. [`05-SPEC-layer-2.md`](05-SPEC-layer-2.md) — Rohit's L2 spec, verbatim.
2. [`01-AS-IS.md`](01-AS-IS.md) — what the code has, judged against the spec.
3. [`02-PLAN.md`](02-PLAN.md) — the plan.
4. [`04-FOR-HARSH.md`](04-FOR-HARSH.md) — Harsh: start there.
5. [`06-GAP-ANALYSIS.md`](06-GAP-ANALYSIS.md) — what exists vs what is new, component by component, and one run step by step.
6. [`03-LOG.md`](03-LOG.md) — what was done, with proof.

## What Rohit decides (asked once — defaults TAKEN on 18 Oct when the build was opened; say if any is wrong)

| # | Question | Recommended default |
|---|---|---|
| L2-Q1 | Is `02-PLAN.md` §0 right: the LLM judges meaning, materiality, priority and confidence in words with evidence; deterministic code never decides; routing, recipients, permissions and approvals stay outside the model? | Yes |
| L2-Q2 | Do the 23 deterministic reasoners become tools only (their scores decide nothing)? | Yes |
| L2-Q3 | Should the judgment pass start from the STEP-12 expert pass, generalised from files to situations? | Yes |
| L2-Q4 | The first situation type to switch | Awaiting reply / outreach (same as `../03-QUESTIONS.md` A3) |
| L2-Q5 | Model and budget for the judgment pass | Sonnet-class, $2/day for your org (same as A6); the strongest class only where the golden set shows it pays — **built as R-9, its own $2/day** |
| L2-Q6 | The subject of one reasoning run (`06-GAP-ANALYSIS.md` §4) | The file when the bundle's counterparty has one, else the seed entity/thread from the bundle |

Already asked in `../03-QUESTIONS.md`, not repeated here: A1, A2, A4, A5 (retire the LLM decider), E2 (budget for live evaluations).
