# 05 · The source — what the Goal Achievement Loop document asks for

**Source file:** [`source/GeniOS-Goal-Achievement-Loop-Chat.md`](source/GeniOS-Goal-Achievement-Loop-Chat.md)
(a ChatGPT conversation, copied byte for byte from `~/Downloads`, 22 Oct 2026).
**Written for:** Rohit, Harsh and every coding agent.
**Status of every claim below:**
- *source* — what the document says;
- *code* — measured in this repository at `21b7ae10`;
- *decision* — a choice this folder makes, with the reason.

---

## 1 · The idea in one paragraph

GeniOS should not stop at telling a manager what happened. It should do six things:
- know the company's **departmental goals**;
- see the **business situations** that move those goals;
- work out what would help, and **delegate** it to a person or an agent within that party's authority;
- **check in** until the outcome is verified;
- adapt when the plan stops working;
- learn from what actually worked.

The goal is the organising principle; situations, cards, tasks and agents serve it. *(source, §1 and §2)*

## 2 · What the document agrees with — already our architecture

Each item below is the same as [`../GeniOS-008/00-ARCHITECTURE.md`](../GeniOS-008/00-ARCHITECTURE.md).
**We build to it; nothing changes.**

| The document says | Our architecture section |
|---|---|
| L1 observes and qualifies; it never concludes a situation | "The layers", L1 row |
| L2 reasons; it is the primary layer; L2 proposes and L3 admits (ADMIT / HOLD / REJECT) | "Inside L2", "Inside L3" |
| Orchestrator = controller; Plane D = what to know; Plane R = how to think; the LLM judges | "Inside L2" |
| 0–3 bounded model calls; no change means 0 calls | "The model rules" |
| The model never writes state, scores, routes or decides for a human | "The model rules" |
| One card = a living view of one situation (versions, not new pings) | "Cards — five lanes, a confidence vector" |
| Confidence as dimensions, never one score | same |
| Four brains: expert, organisation, behaviour, adaptive; the expert brain changes only by reviewed release | "Inside L2", Plane D |
| Reviewed knowledge in Git; live company state in Postgres; caches are disposable | Atlas v2 storage map |
| L4 authority, L5 delivery, L6 learning | "The layers" |

## 3 · What is NEW in the document — the reason this folder exists

| # | New requirement | Today in the code |
|---|---|---|
| N1 | **Departmental goals are first-class objects**: owner, metric, baseline, target, deadline, approval state, revisions | Goals exist only as free-text lines in the company brief's `goals` section. The founder accepts or rejects each line in `company_brief_lines`. There is no goal table. |
| N2 | **Goal ↔ situation relationships**, many-to-many, with evidence, held as hypotheses until supported | Nothing. `ReasoningResult` / `L2Judgment` have no goal field. |
| N3 | **Goal-impact reasoning** in L2: which goal a situation advances or threatens, through what, and how sure we are | Nothing. The brief's goal lines reach the prompts as text only. |
| N4 | **Check-in semantics**: verified complete ≠ reported complete; unknown ≠ overdue; conflicted; withdrawn | Partly built at card level: `context/file_outcomes.py` — VERIFIED vs REPLIED, TAKEN, LAPSED, CLEARED, UNRECORDED. Not on the situation, and not on goals. |
| N5 | **Delegation to people and agents within authority**, then verify the outcome | Built for agents (`executive/delegation.py`: propose → approve → dispatch → result). L4 still auto-plans from `signals` (`executive/sweep.py`). Nothing reads the DecisionObject Harsh writes. |
| N6 | **Outcome → goal progress**: a completed task is not a reached goal | `execution_outcomes` and `situation_outcomes` are written. Nothing moves a goal, because no goal exists. `macv_ledger` has no writer. |
| N7 | **Learning extracted from reasoning into the brains**, governed | `learned_brain_entries` and `feedback/brain_pipeline` exist. The behaviour and adaptive learning units are stubs. |
| N8 | A **Persona brain** for individual preferences | Not in the Atlas. The document itself calls it an extension. |

## 4 · What we do NOT import from the document, and why

| The document says | Decision | Why |
|---|---|---|
| "Reasoning Plane = L2" in one answer, and "Layer 1/2/3 inside the reasoning plane" | **Rejected** | It collides with L1/L2/L3. Atlas v2 is canonical: L1 + L2 + L3 are the Reasoning Plane. Inside L2 we say "Orchestrator steps", never "layers". |
| A model may help L3 with ambiguous identity | **Rejected** | `00-ARCHITECTURE` gives L3 no model; L3-7 moves the remaining L3 model calls into L2. |
| New tables named `business_situations`, `departmental_goals`, `context_snapshots`, `reasoning_receipts`, … | **Mapped, not copied** | We already have `context_situations`, `graph_*`, `reasoning_results`, `l2_admissions`, `situation_interpretations`, `cards`. Only the goal tables are new (see `02-PLAN` G1). |
| A hybrid retrieval ranking formula `S = w_v V + w_t T + …` | **Rejected as a spec** | The conversation invented it. Retrieval stays exact first (ids, revisions, `read_bounded`). |
| Cost ≈ $0.002–$0.007 per card | **Replaced by our measurement** | Measured 12 Oct: Haiku pass $2.17 for 86 reviews ≈ $0.025 per review. Today's golden L2 pass logs `cost_micro_usd` per run (F03: 29,560 µ$ ≈ $0.03). |
| "Goals belong to L3" and "goals belong to the Organisation brain" (it says both) | **Decided in `08-DECISIONS` D2** | One home is needed. Default: L3 holds the goal object; Plane D reads a pinned copy. |

## 5 · The document's own invariants we adopt word for word

1. **Signal ≠ situation ≠ goal ≠ task ≠ decision ≠ execution ≠ outcome.** Each has its own contract.
2. **An inferred goal never becomes an approved goal without a human.**
3. **Unknown is never false.** A connector outage reads "unknown", never "overdue".
4. **Task completion is not outcome completion.**
5. **A continuing situation keeps one identity, and its card keeps one identity.** A new signal is not a new situation; no signal is not "done".
6. **Re-reason only on a material change.** Never on every write.
7. **L2 proposes; L3 admits.** No L2 output is accepted state until it is admitted.
8. **Learning is governed.** One observation never becomes a rule.
