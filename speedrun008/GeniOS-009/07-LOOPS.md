# 07 · The loops — business situation, goals, reasoning, context, learning — mapped onto the code

**Written for:** Rohit, Harsh and every coding agent.

**Layer vocabulary.** We use the product layers only: L1 Enterprise Signals (`capture/`) · L2 Reasoning
(`reason/` + `packs/`) · L3 Context Graph (`context/`) · L4 Executive (`executive/`) · L5 Delivery
(`deliver/`) · L6 Learning (`feedback/`).

**What each tag means:**
- **[built]** — exists and runs at `21b7ae10`.
- **[shadow]** — exists, runs, and writes, but nothing a person sees reads it yet.
- **[to build]** — an item in [`02-PLAN.md`](02-PLAN.md).

---

## 1 · The five objects, and which layer owns each

| Object | Meaning | Owner | Table / contract |
|---|---|---|---|
| **Signal** | something happened, with evidence | L1 | `qualified_signals`, `signal_bundles` [built] |
| **Business situation** | what is going on, across signals, that matters | formed by L2, admitted and kept by L3 | `context_situations` [built, still formed by L3 before reasoning] · `l2_admissions` [shadow] · `situation_interpretations` [shadow] |
| **Goal** | what the company or a department wants to achieve | L3 keeps it, a human approves it, L2 reads it | `company_brief_lines` section `goals` (free text) [built] · `company_goals` [to build, G1] |
| **Decision / execution** | who decides, who acts, by when | L4 | DecisionObject (inside `situation_interpretations`) [shadow] · `executions`, `execution_actions`, `delegation` [built] |
| **Outcome** | what actually changed | L6 reads it; L3 records it | `execution_outcomes`, `situation_outcomes` [built] · goal progress [to build, G9] |

A **card** is none of these. It is the L5 *view* of one situation (STEP-14's living card, `cards` + `card_events`).

## 2 · The reasoning loop — "what does it mean and what should happen next" (L2)

Today's pass is `reason/l2/sweep.py`. It runs after the expert pass inside `reason/runner.run_all`, which
`api/routes._run_l2_chain` calls on every sweep.

| Step | What happens | Code | State |
|---|---|---|---|
| R1 request | the bundles L1 stored since the watermark, grouped by subject (a file, else a thread); plus subjects whose evidence need was met | `reason/l2/inputs.read_subjects`, `evidence.reentries` | [built] |
| gate | the subject's inputs are fingerprinted with clocks removed; a standing answer costs **0 calls** | STEP-02 change gate in `sweep.py` | [built] |
| R2 snapshot | a bounded read around the subject from L3, revision pinned, readable as of an instant | `reason/l2/snapshot.read_snapshot` → `context/bounded_read` | [built] |
| **R2+ goals** | **the active goals this subject could touch, printed with ids** | — | **[to build, G2]** |
| R3 history | comparable past work of the same kind | `reason/l2/history.history_for` | [built] |
| R4 expertise | the file's dossier: company brief, playbook (Plane D), numbers with n, corrections, earlier judgments | `reason/l2/dossier.build_l2_dossier`, `packs/` | [built] |
| R7 tools | dates, money, baselines, open conflicts | `reason/l2/tools.run_tools` (money tool `11e31e45`) | [built] |
| R5 plan | depth (0–3 calls) and why | `reason/l2/plan.compile_plan` | [built] |
| R6 judge | **one bounded model pass**: frame, alternatives, consequences, options, decision need, confidence vector, proposed mutations, evidence needs | `reason/l2/judge.judge`, site R-9 (`reason_l2`) | [built] |
| **R6+ goal impact** | **which goal this situation advances, threatens or depends on, why, on what evidence** | — | **[to build, G3]** |
| R9 validate | every claim checked against what the dossier printed (STEP-13 claim check) | `contracts/claim_check`, `reason/expert/verify` | [built] |
| R8 needs | decision-changing questions filed for L1 to fetch | `reason/l2/evidence` → `evidence_needs` | [built, fetchers armed by `GENIOS_NEED_FETCHERS`] |
| G1 write | results, needs, watermark in one transaction | `reason/l2/store` → `reasoning_results` | [built] |

**Triggers that start the loop.** Three exist today: a new bundle, a crossed deadline, and an expected reply
that never came. Two more are [to build]: a **goal change** (G2) and a **check-in due** (G7).

## 3 · The context loop — "what does the company now know" (L3, and its two-way bond with L2)

```
L3 snapshot ──► L2 judges ──► proposed mutations ──► L3 admission (ADMIT / HOLD / REJECT)
     ▲                                                         │
     └──── material change only (version bump, change gate) ◄──┘
```

| Part | What it does | Code | State |
|---|---|---|---|
| Evidence Graph | facts and edges, bitemporal, authority-ranked | `context/graph_store`, `identity`, `merge` | [built] |
| Situation seeds | today's joins and readings still create a situation row per file **before** reasoning | the 9 writers (`refresh_situations`, `outreach_situations`, …) | [built — old flow, to retire per GeniOS-008 L3-2] |
| Admission | L3 decides on L2's proposal: update or close → admit; merge or link → hold; nothing material → reject | `context/l2_admission.decide`, migration 0249 | [shadow] (Harsh `fb429b78`) |
| Interpretation record | an admitted judgment appends what it concluded and the decision object, never overwriting | `situation_interpretations` (`f3cfd3c6`) | [shadow, no reader] |
| Lifecycle | a statement-resolved situation stays resolved; a handled card returns on new evidence; dormancy | `context/situations` on-conflict clause (`df3c2aa8`, `21b7ae10`) | [built] |
| Change propagation | every graph writer bumps the org version, so reads keyed on it see change; the merge now does too | `bump_graph_version` (`8cfe15a6`) | [built] |
| Rewrite only on change | derived facts and receipts are rewritten only when the value moved | `34779fe0`, `ae5b5c7a` | [built] |
| **Goal objects + goal ↔ situation links** | goals with revisions; links written on ADMIT; HOLD when the goal is not active | — | **[to build, G1, G4]** |

**Why two-way and not one-way.** One-way L1 → L2 → L3 cannot do three things:
- ask for a missing fact (the EvidenceNeed loop);
- stop a stale proposal (compare-and-set on the snapshot revision);
- re-reason when accepted state changes (the material-change trigger).

All three exist above in some form. The goal loop adds a fourth: **a goal change re-opens the reasoning
of every situation linked to it.**

## 4 · Business situation × departmental goal — the cross-correlation

The document lists twelve angles: relevance · contribution · dependency · ownership · temporal · magnitude ·
evidence · contradiction · historical pattern · alternative explanation · consequence · actionability.

How we split them, by the model rules (`00-ARCHITECTURE` "The model rules"):

| Angle | Who computes it | Where |
|---|---|---|
| ownership, temporal, magnitude | **code** (tools) — ids, dates, money, counts | `reason/l2/tools` + new goal progress tool (G5) |
| evidence, contradiction | **code** finds them; the **model** reads them | `inputs.read_open_conflicts`, claim check |
| relevance, contribution, dependency, alternative explanation, consequence, actionability, historical pattern | **the model**, in words, citing ids the dossier printed | `L2Judgment.goal_impacts` (G3) |

**The output is a relation, not a score:**
- `advances`
- `threatens`
- `depends_on`
- `unclear`

Each relation comes with a *why* and evidence ids. **Many-to-many:** one situation can touch several
goals, and one goal is touched by many situations.

**Departments today.** A department = a live domain for the tenant. Today that is Admin plus Founder Office
(`platform/l3_activation`). For a founder, a "departmental goal" is usually a workstream goal: *raise the
seed round*, *get DPIIT recognition*, *join an incubator*. Sales and Support stay off until Rohit opens them
(memory: admin-domain-only, D2).

## 5 · Check-in — "is it done?" (L3 + L4 + L5)

| State (document) | Today | Gap |
|---|---|---|
| verified complete | `file_outcomes.VERIFIED`: the ask closed, answered, by the event that closed it | card-level only; not on the situation or the goal |
| reported complete | `file_outcomes.REPLIED`: cleared while the ask closed only replied | same |
| still open | `OPEN` | — |
| overdue | the commitment loop (a conditional promise no longer gets a date, `bda38c3d`) | not tied to coverage |
| unknown (coverage gap) | L1 coverage receipts exist (`context/coverage_receipt`, `capture/coverage/`) | **not read by the check-in**: a connector outage can still look like silence |
| conflicted | `signal_conflicts` now reaches the judgment (`b8a8a43c`) | not a check-in result |
| withdrawn | `CLEARED`, `REPLACED` | — |

G7 lifts these onto the situation (and through G9 onto the goal). It adds two things:
- the **definition of done** written by the judgment;
- the **coverage read**, so "unknown" can never become "overdue".

## 6 · The learning loop — "what did reality teach" (L6 → Plane D, governed)

| Part | Code | State |
|---|---|---|
| your corrections change the next judgment | STEP-16 (`context/founder_corrections`, golden F65–F67) | [built] |
| calibration (mute, thresholds) | `feedback/calibrate.py` (shadow unless armed — memory: calibration-fix-arms-auto-mute) | [built, shadow] |
| brain store | `learned_brain_entries` (organization, behavior, adaptive, runtime — never expert) | [built] |
| proposals → governance → publish | `feedback/brain_pipeline`, `publisher`, `target_policy` | [built]; the behaviour and adaptive learning units are stubs |
| attribution of a miss to a layer | `feedback/attribution.py` (counts, changes nothing) | [built, inert] |
| **goal outcomes as learning input** | — | **[to build, G9]** |

## 7 · How the loops run in time

| When | What runs | Model calls |
|---|---|---|
| a sync lands mail or events | L1 → `_run_l2_chain` → L2 pass → admission → cards | 0 if nothing material changed; 1–3 per changed subject |
| the 6-hourly sweep | the same chain; deadlines and expected replies become triggers | 0 for unchanged subjects |
| a goal is approved or changed | **[G2]** every subject linked to that goal is re-judged once | 1 per linked subject |
| a check-in is due (the execution ladder 1/3/7/14 days) | **[G7]** read the evidence; set verified, reported, unknown, overdue or conflicted | 0 when the evidence is exact; 1 when it needs reading |
| a verified outcome | **[G9]** goal progress moves; a learning candidate is filed | 0 |
