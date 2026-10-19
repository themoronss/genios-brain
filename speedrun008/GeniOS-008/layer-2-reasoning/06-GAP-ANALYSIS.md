# L2 Reasoning — gap analysis: what exists, what is new, and exactly how it will run

**Written for:** Rohit (decisions) and Harsh (what will reach production). **Measured at:** `speedrun008`, 18 Oct 2026,
read-only. Paths are under `genios_engine/`. LOC = lines in the file today. No code was changed for this document.

Read with [`05-SPEC-layer-2.md`](05-SPEC-layer-2.md) (the spec), [`01-AS-IS.md`](01-AS-IS.md) (the audit) and
[`02-PLAN.md`](02-PLAN.md) (the plan). This file answers four questions:
1. How much of the spec's L2 is already built? (§1)
2. Component by component: what exists, what is new? (§2)
3. Exactly how will one run go, with real data? (§3)
4. What happens to today's code: kept, reshaped, retired? (§4)

---

## 1 · How much is built — the short answer

**The spec's *shape* is about half built. The spec's *flow* is not built at all.**

- **The judgment pass exists, but only for files.** `reason/expert/` (STEP-12/13, 5,451 LOC) already does what the
  spec asks of L2's LLM pass:
  - a bounded dossier: brief, file, timeline, numbers with their n, playbook stage, past judgments, outcomes,
    corrections, promises, coverage, what-if-nothing;
  - one Sonnet-class call that thinks through Plane R Groups 1–4 as prompt sections;
  - a structured `ExpertReview`: facts, inferences, patterns, hypotheses, unknowns, frames, expected vs actual,
    scenarios, appraisal, mode, next move, alternative, wait/stop, done-when, draft;
  - a line-by-line claim check (`verify.py`);
  - replay with no model call.

  It runs only on a **file** (one counterparty's work), only where `expert_review` is activated, at most 10 a pass.
- **The flow around it is the old one.** L3 (`context/`, 9 situation writers, 9,778 LOC) forms situations *before*
  any reasoning. Then 23 formula reasoners (8,038 LOC) and the pack rules score and decide. The LLM decider only picks
  between candidates the formulas produced. The output is a `signals` row, not a `ReasoningResult`.

| Measure | Built | Missing |
|---|---|---|
| 10 runtime components (R1–R10, `02-PLAN` §1) | 2 reusable as they are (R1 request, change gate); 6 need reshaping (R2, R3, R4, R6, R7, R9/R10) | 2 new (R5 depth, R8 evidence coordinator) |
| `ReasoningResult` fields (19) | 11 already in `ExpertReview` under other names | 8: `history_used`, `decision_need`, six-dimension `confidence`, `lane`, `proposed_mutations`, `evidence_needs`, `coverage_limitations`, `receipt_ref` (exists as a store row, not a field) |
| Plane R groups in the prompt | Groups 1–4 | Groups 5–6 (options/trade-offs, decision need/authority) |
| Subject of reasoning | files (counterparty work) | any situation seed from the L1 bundle that is not a file |
| New code, estimate | — | **≈3.5–4.5k LOC + tests**, mostly glue around existing parts. Planning estimate, not a measurement |

---

## 2 · Component by component

Verdicts as in `01-AS-IS`: **REUSE** (lift as is) · **ADAPT** (reshape) · **BUILD** (new) · **RETIRE**.
"New file" names are proposals; they are fixed when Group A is opened.

### R1 · Request Handler — REUSE + small BUILD

| | |
|---|---|
| Exists | `contracts/reasoning.py:728` `ReasoningRequest`; its trigger is a free string (`legacy.rule_scan`, `expert.review`, …) |
| Exists | `reason/change_gate.py:71` + `reason/fingerprint.py:187` (STEP-02): same inputs, clocks removed → 0 model calls, receipt only. Runs on all lanes today |
| New | A closed trigger set (L2-A3): `bundle`, `new_evidence`, `deadline_crossed`, `expected_reply_absent`, `owner_change`, `outcome`, `human_ask`. `reason/expert/triggers.py` (200 LOC) already detects four of these for files: new evidence, a correction, a deadline closing in, a reply later than *their usual* / *our usual* |
| How | The request id = hash(org, seed, trigger, bundle hash). Same id → stored result returned, nothing runs |

### R2 · Context Adapter — ADAPT (the read exists, nobody calls it)

| | |
|---|---|
| Exists | `context/bounded_read.py:182` `read_bounded(conn, org_id, ReadRequest) -> BoundedView` (node ids, edges, revision, truncated, hops walked). **No caller.** |
| Exists | `contracts/reasoning.py:414` `ContextSnapshot`. Today it is filled from a **whole-org** read (`reason/runner.py:196 _bulk_load_facts`, `:242 _bulk_load_obs`) |
| New | `reason/l2/snapshot.py`: seeds from the bundle → `read_bounded` (hops, max nodes) → `ContextSnapshot` pinned to its `revision`, with stale/conflicting marks. Needs L3's as-of read (an L3 unit) |
| Rule | Nothing in the run reads the database after this point. Everything below reads the frozen snapshot |

### R3 · History Assembler — ADAPT (pieces exist inside the dossier)

| | |
|---|---|
| Exists | `reason/expert/dossier.py:read_parts` already pulls: `timeline_for`, `judgments_for` (what we judged before), `ended_for_cards` (outcomes), `standing_for` (corrections), `numbers_for` (reply times with n), `read_asks_closed`. Behind them: `context/workstream_timeline.py`, `file_judgments.py`, `file_outcomes.py`, `workstream_numbers.py` |
| Missing | "**Similar past situations**" across counterparties — e.g. *the last three investors who went quiet after a deck*. Today history is one file's own past only |
| New | `contracts/` `HistoricalContext` (L2-A2) + `reason/l2/history.py` that wraps those readers and adds a similar-cases query by work kind + stage |

### R4 · Expertise Resolver — REUSE + fold in

| | |
|---|---|
| Exists | `packs/compiler/*` (4,030 LOC): Domain Compiler → hash-pinned ExpertisePackage (`contracts/domain_expertise.py:766`). Admin is live |
| Exists | Playbooks: `packs/compiler/playbook_reader.py` + `Domain Expertise/Founder Office Expertise`; the dossier reads them by `work_kind` (`investor`, `program`, `compliance`, `hiring`, `intro`, `partner`, `vendor` — `contracts/company_brief.py:48`) |
| Exists | Company brief (STEP-07), four brains (`packs/compiler/runtime_brains.py`) |
| New | One package object carrying all of it with **one version + hash**, so the receipt can say exactly which expertise was used. Counter-patterns and evidence standards are already in the YAML; they are not yet passed to the prompt as their own block |

### R5 · Plan Compiler (depth) — BUILD on top of `reason/plan.py`

| | |
|---|---|
| Exists | `reason/plan.py:442` `ReasoningPlanner` + `_ROSTER`: picks which **formula units** run. Stage only in `reason/expert/stage_dwell.py` |
| Missing | Need classification and depth (none / shallow / standard / deep), which Plane R groups to switch on, skipped groups with reasons, budgets, stop conditions |
| New | `reason/l2/plan.py`. Depth is chosen from **measured** inputs only (contradictions in the snapshot, coverage gaps, linked situations, deadline distance from the tools, impact markers in the package) plus the model's own request for more depth, with its reason. Both go in the receipt. This is routing, not judgment: it decides *how much* to think, never *what* to conclude |

### R6 · The judgment pass — ADAPT (this is the core; most of it exists)

| | |
|---|---|
| Exists | `reason/expert/prompt.py` (248, `expert-review.v4`): Plane R Groups 1–4 as prompt sections; "no number of its own" |
| Exists | `reason/expert/review.py` (201): one call through the one R-site gate (`reason/bundle/gate.RSiteGate`): budget, cache, retry, receipt. Sonnet-class, $2/day, `MAX_PER_PASS = 10` (`sweep.py:92`) |
| Exists | `reason/expert/dossier.py` (1,055): builds the bounded input |
| Change 1 | **Subject.** From "a file" to "a situation seed": a file when the bundle's counterparty has one (most founder work), else the seed entity/thread from the bundle |
| Change 2 | **Input blocks.** The dossier becomes the spec's six labelled blocks (A–F in `02-PLAN` §4): signals · snapshot · history · expertise · tool results · coverage |
| Change 3 | **Groups 5–6** added to the prompt (options and trade-offs; decision need and authority) |
| Change 4 | **Depth-aware routing** (L2-D2): the model and thinking budget come from R5. ⛔ Claude 5 thinks by default and thinking eats `max_tokens` — a Sonnet pass was once 203/203 truncated. The budget is set per depth and tested on 1–2 calls before any paid pass |
| Change 5 | Output schema = `ReasoningResult` (R9), not `ExpertReview` |

### R7 · Tool Gateway — ADAPT (the tools exist, scattered)

| Tool | Exists today in |
|---|---|
| Numbers with their n (reply time, cadence) | `context/workstream_numbers.py`, `context/kind_numbers.py`, `reason/bundle/numbers.py` |
| Baselines | `reason/baselines.py` |
| Dates, windows, deadlines | inside `reason/reasoners/temporal.py`, `timeline_unit.py`, `scheduling_unit.py` |
| Retrieval over the snapshot | `context/bounded_read.expand` |
| Money | **missing** |

New: `reason/tools/`, one read-only gateway over the frozen snapshot, no clock (gets `eval_time`), no DB, no network.
The formula reasoners' useful arithmetic moves here (see §4). Tool results go to the model **as evidence with their n**,
never as a verdict.

### R8 · Evidence Coordinator — BUILD (the wire exists at both ends, not in the middle)

| | |
|---|---|
| Exists | `contracts/evidence.py:213` `EvidenceNeed` (question, why it matters, acceptable *and unacceptable* sources, window, cost cap, states open/met/unavailable) |
| Exists | The queue: `context/evidence_need_store`; L3 raises needs (`context/hold_needs.py`, `context/evidence_needs.py`) |
| Exists | L1's executor `capture/acquire/need_executor.py`, read by `reason/domain_shadow.work_the_needs`. It **refuses to start** while no fetcher is wired — `build_fetchers` is empty today (L1 E2) |
| Missing | L2 never raises a need from its own unknowns, and never re-enters reasoning when a need is met |
| New | `reason/l2/evidence.py`: an `unknown` the model marks *decision-changing* → one `EvidenceNeed` (idempotent `need_id`) → queue. When L1 closes it `met`, a `new_evidence` trigger re-runs the situation **once**, on the new evidence only (CALL 2). `unavailable` closes the unknown with its reason; it never loops |
| Waits on | L1 E2 fetchers. Until then L2 raises needs and they stay `open`; the result says "incomplete, waiting on X" |

### R9 · Result Synthesizer — ADAPT (`ExpertReview` → `ReasoningResult`)

| `ReasoningResult` field | From `ExpertReview` today | Work |
|---|---|---|
| `facts`, `inferences`, `hypotheses`, `unknowns` | same names | rename only; `unknowns` gains `decision_changing: bool` |
| `frame`, `alternative_frames` | `frames` | split |
| `expected_vs_actual` | same | — |
| `consequences` (incl. doing nothing) | `scenarios` + dossier `what_if_nothing` | merge |
| `options` | `alternative`, `wait_or_stop` (one string each) | **new structure**: benefit, downside, reversibility, who is affected, what evidence would change the choice |
| `intervention_mode` | `mode` | widen to the spec's 10 modes |
| `best_next_move` | `next_move` + `done_when` | — |
| `patterns` | `patterns` | kept (feeds `history_used`) |
| `history_used` | — | **new**: which past cases were compared and why they do / do not apply |
| `decision_need` | — | **new**: does a human have to decide, and who |
| `confidence` | `appraisal` (words) | **new structure**: six dimensions — evidence, framing, temporal, causal, authority, coverage — each a level + reason + evidence refs. No composite number. (`contracts/situation.py:331 ConfidenceVector` measures *data* quality — freshness, identity, consistency — and stays as a tool input; it is not this) |
| `lane` | computed later from `mode` in `reason/expert/decide.py` | the model proposes; `reason/output_lane.py:71` (5 lanes) validates |
| `proposed_mutations` | `proposed_kind` (a file's kind only) | **new**: situation create / update / merge / close, as proposals to L3 |
| `evidence_needs` | — | from R8 |
| `coverage_limitations` | dossier `_coverage` section (input only) | **new output field** |
| draft | `draft` | moves out of L2: prepared content is L4/L5's |

### R10 · Validators + receipts — ADAPT

| | |
|---|---|
| Exists | `reason/expert/verify.py` (1,320): every cited id exists, every quote is in the mail, names on their own lines, every number matches a tool result |
| Exists | `reason/audit.py:283 persist_execution`, `reason/replay.py` (replays expert decisions with no model) |
| New | Run the claim check on **every** `ReasoningResult` (L2-F1); add structure, time (no claim dated after `eval_time`), epistemic (an inference must cite a fact; a hypothesis must carry counter-evidence) and authority checks (L2-F2). A failed material check → one repair call (CALL 3) or `review_required` |
| New | Receipt v2 (L2-A2): request, snapshot revision, package hash, depth + skipped groups with reasons, tool results, model + prompt version, validation, retrieval attempts, termination reason, output hash |
| DB load | Today: two transactions per situation (`audit.py:283` + `domain_shadow._persist_live`). New: one batched write per sweep (L2-G1) |

---

## 3 · Exactly how one run will go — a real example

**The case** (illustrative: the dates, n and numbers below are made up to show the shape, not measured): Boardy emails Rohit an intro to an investor at a fund. Today this dies at the gate or in the 16-type
vocabulary (memory: *founder workstreams lost*). Under the new L2:

| # | Step | Who | What happens, concretely | Model calls |
|---|---|---|---|---|
| 1 | Capture | L1 | Gmail sync → event → semantic extraction → `QualifiedEnterpriseSignalBundle` (L1 E1): the intro, the two people, `introduced` edge, the ask, coverage receipt | (L1's own) |
| 2 | Request | R1 | Trigger `bundle`. Request id = hash(org, seed = investor's address, bundle hash). Seen before → return the stored result, stop | 0 |
| 3 | Change gate | STEP-02 | Fingerprint vs last run for this seed. Nothing material changed → receipt only, stop | 0 |
| 4 | Snapshot | R2 | `read_bounded` from the investor's node: the person, their fund, Boardy, the thread, open loops, Rohit's in-motion brief line "fundraising — investor"; pinned at revision N | 0 |
| 5 | History | R3 | This file's timeline (new: empty). Similar cases: earlier Boardy intros and what happened (2 replied in ≤2 days, 1 went quiet), Rohit's usual reply time with its n | 0 |
| 6 | Expertise | R4 | Founder Office package, playbook `investor` (stage: *introduced*; expected next: founder replies within 48h with a short note + deck), counter-pattern *warm intro gone cold*; company brief. Package hash H | 0 |
| 7 | Plan | R5 | No contradiction, one counterparty, a 48h clock from the playbook → depth **standard**, Groups 1–4 + 5 | 0 |
| 8 | Tools | R7 | Intro received 2 days ago; ball in our court; Rohit's median reply 1.4 days (n = 37); deadline from the playbook = 48h → crossed by 4h | 0 |
| 9 | Judgment | R6 | CALL 1 with the six blocks. Returns a `ReasoningResult`: **facts** (Boardy introduced X on 16 Oct, cited); **frame** "a warm investor intro waiting on us", alternative "X is a scout, not a decision maker"; **unknown** "is X a partner?" (decision-changing: no — the move is the same); **consequence** of nothing: intro goes cold; **options**: reply today with a short note / reply after the deck update; **mode** prepare decision; **next move**: reply today, thank Boardy; **confidence**: evidence high, framing medium (role unknown), temporal high, …; **lane** decision; **proposed mutation**: create situation *investor intro — X* | 1 |
| 10 | Evidence | R8 | No decision-changing unknown → no need. (If the model had asked "did Rohit already reply from another address?", that is decision-changing → `EvidenceNeed` → L1 fetches the sent folder → `met` → step 9 once more, on that evidence only) | 0 (or +1) |
| 11 | Validate | R10 | Every cited id exists, the quote is in the mail, "1.4 days" matches the tool, no date after `eval_time`. A failure → one repair call or `review_required` | 0 (or +1) |
| 12 | Store | R9/R10 | `ReasoningResult` + receipt, in one batched write per sweep (shadow table first) | 0 |
| 13 | Admission | L3 | The proposed mutation goes to L3: ADMIT / HOLD / REJECT. Admitted → situation *investor intro — X* exists in memory | 0 |
| 14 | Act / deliver | L4 → L5 | L4 turns lane + next move into the action; L5 renders the card from the result | (theirs) |

**Total: 1 model call in the normal case, at most 3.** In shadow (Group I) steps 1–12 run beside today's path, write
only their own table, and change no card; the golden set scores both.

---

## 4 · What happens to today's code

| Today's code | LOC | Becomes |
|---|---|---|
| `reason/expert/*` | 5,451 | **The core of L2.** Generalised from file to situation seed (R3, R6, R9, R10) |
| `reason/change_gate.py`, `fingerprint.py` | 327 | Kept at the front (R1) |
| `contracts/reasoning.py` `ReasoningRequest`, `ContextSnapshot` | — | Kept; triggers closed (R1), snapshot filled from the bounded read (R2) |
| `context/bounded_read.py` | 195 | Gets its first caller (R2) |
| `packs/compiler/*`, playbooks, brief, brains | ~6,000 | Kept; folded into one versioned package (R4) |
| `reason/output_lane.py`, `reason/replay.py`, `reason/audit.py` | ~700 | Kept; audit writes batched |
| `contracts/evidence.py` `EvidenceNeed`, the need store, L1's executor | — | Kept; L2 starts raising needs (R8) |
| `reason/reasoners/*` (23 formula units) | 8,038 | **Demoted to tools** (L2-H1). Date/window/number logic moves behind `reason/tools`; risk/priority/confidence scores stop deciding anything. Retired at cutover |
| `reason/plan.py` `ReasoningPlanner` | 571 | Its roster logic retires; its shape (plan, skip reasons) is reused for depth (R5) |
| `reason/llm_decision_maker.py`, `llm_interpretation.py` | 1,287 | **Retired** (L2-H2): the judgment pass replaces "the model picks between formula candidates" |
| `reason/situation_reasoner.py` (R-6) | 286 | Already retired 11 Oct. Its law — *"the formula decides; the model cannot raise confidence"* — is the opposite of the spec and is **not** carried over |
| `reason/runner.py` legacy pack lane, `reason/domain_shadow.py` | ~4,000 | Run in parallel until cutover, then the per-pack rule lane retires (L2-H3) per situation type |
| `context/*_situations.py` + `situations.py` + `situation_bso.py` (9 writers) | 9,778 | **Stop forming situations** at each type's cutover. Their *detection* (e.g. outreach: our turn, no reply in N days) becomes a trigger or a tool input; situations are created only by L3 admitting an L2 proposal. The situation-writer ratchet guard counts them down |
| `context/workstreams.py` (files) | 608 | Kept: a file is the natural seed for founder work |

### The one decision this raises (added to `00-START-HERE` as L2-Q6)

**What is the subject of one reasoning run?** Recommended: **the file when the bundle's counterparty has one, else the
seed entity/thread from the bundle.** Why: the expert pass already reasons well per file, and the founder asks "where
are we with X", not "what does this one email mean". A seed that is not founder work (a vendor invoice, a portal
notice) still gets a run, scoped to its own thread.

---

## 5 · Order of work (unchanged from `02-PLAN` §7, with what is reused marked)

| Group | New vs reused | Blocked by |
|---|---|---|
| A · Contracts | new: `ReasoningResult`, `HistoricalContext`, receipt v2, triggers, confidence | — |
| B · Context assembly | mostly reuse: `read_bounded`, dossier readers, compiler, numbers | L3 as-of snapshot (B1 only) |
| C · Plan + gate | gate reused; depth new | A |
| D · Judgment pass | ~70% reuse of `reason/expert` | A, B, C |
| E · Evidence loop | new middle; both ends exist | L1 E2 fetchers (to *meet* needs; raising works without) |
| F · Validation | `verify.py` reused; three validators new | D |
| G · Handoff | store + batch new; replay reused | A; L3 admission (G2) |
| H · Demote / retire | removal | D + cutover |
| I · Shadow + first switch (awaiting reply / outreach) | new compare harness on the golden set | A–G |

~~Nothing here is started.~~ **Superseded 18 Oct evening:** Rohit opened the build; what is built, unit by unit,
is in [`00-START-HERE.md`](00-START-HERE.md) "Build status".
