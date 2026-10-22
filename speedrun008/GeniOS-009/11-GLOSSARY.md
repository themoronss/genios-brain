# 11 · Glossary — every term in GeniOS-009, one line each

**Written for:** Harsh and coding agents who start cold.

Where a term has code, the code is named.

## The layers (product numbering, always with the package)

| Term | Meaning |
|---|---|
| **L1 Enterprise Signals** · `capture/` | Reads Gmail, Calendar and so on; qualifies what happened; publishes signals and bundles with a coverage receipt. Never concludes a situation. |
| **L2 Reasoning** · `reason/` + `packs/` | The primary layer. Reads a bounded snapshot plus expertise, judges what it means and the next move, and writes a `ReasoningResult`. Proposes; never stores state. |
| **L3 Context Graph** · `context/` | Trusted memory. Admits or holds L2's proposals; keeps situations, goals and links; serves snapshots. No model. |
| **L4 Executive** · `executive/` | Who decides; turns a human decision into owned work (`execution.v1`); the reminder ladder. |
| **L5 Delivery** · `deliver/` | Cards, the board, the morning brief, agent hand-off. |
| **L6 Learning** · `feedback/` | What reality taught; changes data (mutes, brains), never code. |
| **Plane D / Plane R** | Inside L2. D = domain expertise (`packs/`: reviewed YAML compiled into a hash-pinned pack). R = reasoning units (`reason/`). |

## L1 → L2

| Term | Meaning |
|---|---|
| **signal** | One qualified thing that happened, with its evidence (`qualified_signals`). |
| **bundle** | Signals that belong together on arrival; L2's input contract (`signal_bundles`). |
| **subject** | What one L2 judgment is about: a **file**, else a thread (`seed:`); a **goal subject** `goal:<id>` from G9. |
| **file / workstream file** | One piece of work in motion with one counterparty (STEP-09), e.g. "Raise · Kestrel Capital". |
| **coverage receipt** | What was read and what was not, per mailbox and window (`context/coverage_receipt.py`). |

## Inside L2

| Term | Meaning |
|---|---|
| **dossier** | Everything the judgment is shown, in blocks **A–F** today (`reason/l2/dossier.py`): A signals · B context · C history · D expertise and the file · E tools · F coverage. G2 adds **G · the goals**. |
| **catalogue** | The ids and numbers the dossier printed; the claim check refuses anything outside it. |
| **R-9 / the judgment pass** | The one bounded model call per changed subject (`reason/l2/judge.py`, site `reason_l2`). |
| **`L2Judgment`** | The judgment half of the result (`contracts/reasoning_result.py`): mode, options, confidence, decision need, proposed mutations, evidence needs… G3 adds `goal_impacts`; G7 adds `done_when`. |
| **`ReasoningResult`** | The review (the expert's words) plus the judgment, stored in `reasoning_results`. |
| **claim check** | Every line must stand on printed ids. A failing line is **dropped**; the result stays (`validate_judgment`, `drop_unprinted`). |
| **fingerprint / change gate** | The subject's inputs with clocks removed (`reason/l2/sweep.fingerprint_of`). Unchanged → 0 calls. |
| **watermark** | How far the L2 pass has read; it never passes a subject it did not reach. |
| **lane** | Where a result goes: decision · investigation · conflict · monitor · suppress (`reason/output_lane.py`). |
| **tools** | Code that computes dates, money and baselines (`reason/l2/tools.py`); G5 adds goal progress. |

## L3

| Term | Meaning |
|---|---|
| **situation** | A business situation, kept in `context_situations` with a lifecycle (active · dormant · resolved · archived). |
| **seed** | A situation row formed by today's L3 joins before reasoning. From G0.3, invisible until admitted. |
| **admission** | L3's decision on L2's proposal: **ADMIT / HOLD / REJECT** (`context/l2_admission.py`, table `l2_admissions`). |
| **interpretation** | An append-only record of what an admitted judgment concluded, including the **DecisionObject** (`situation_interpretations`). |
| **DecisionObject** | Whether a human must decide, who, what, by when; read by L4 from G8. |
| **goal** | A company or department objective (`company_goals`, G1): approved by the founder, or proposed and waiting. |
| **goal impact** | The model's reading of how a subject bears on a goal: advances · threatens · depends_on · unclear (G3). |
| **link** | The admitted form of a goal impact (`goal_situation_links`, G4). |
| **progress** | measured (a metric counted) · counted (open links + verified outcomes) · unknown (said why) (G5). |
| **done_when** | The judgment's definition of done: one line + the kind of evidence that proves it (G7). |
| **check-in state** | open · reported_complete · verified_complete · overdue · unknown · conflicted · withdrawn (G7). |

## L4–L6

| Term | Meaning |
|---|---|
| **decision request** | A DecisionObject waiting for a human choice (`decision_requests`, G8). |
| **execution** | Owned work after a decision (`execution.v1`), with the reminder ladder 1/3/7/14 days. |
| **delegation** | Handing one action to an agent: propose → approve → dispatch → result (`executive/delegation.py`). No approval, no dispatch. |
| **progress event** | One verified outcome credited to a goal (`goal_progress_events`, G9). |
| **brain** | Plane D's four: **expert** (Git, reviewed, never written at runtime) · organisation · behaviour · adaptive (`learned_brain_entries`). |
| **lease** | A time-limited adaptive brain entry (`packs/brains/adaptive_lease.py`). |

## Cards

| Term | Meaning |
|---|---|
| **living card** | One card per situation; a material change makes a new **version** (`card_events`), never a second card (STEP-14). |
| **gold card / card lines** | The card's fields: why now, what remains, subject and role, recommended, alternative, wait or stop, window. Written by code from the review (`reason/expert/card_lines.py`). |
| **goal line** | G6: *"Moves: <goal> — advances · <progress>"*, written by code from admitted links. |
| **board** | G6: cards grouped by goal, then by lane; "Not linked to a goal" is counted, never hidden. |
| **ending** | How a card ended (`context/file_outcomes.py`): verified · replied · taken · called wrong · lapsed · dismissed · replaced · cleared · open · unrecorded. |

## Testing

| Term | Meaning |
|---|---|
| **golden case** | One founder story, F01–F67 (`tests/replays/specs/founder/`), run through the real chain; **must_detect** or **must_abstain**. |
| **cassette** | The recorded model answers for a case, keyed by the exact prompt. A changed prompt raises **CassetteMiss**. |
| **ideal reader** | Answers each prompt from the case's own expected reading; re-records cassettes at no spend (`tests/replays/ideal_reader.py`). |
| **blocked_on / strict xfail** | A case waiting on a known item; it must fail until that item lands. |
| **mutation proof** | Remove the rule and show its test goes red. |
| **ratchet** | A CI list that may only shrink (e.g. the places in `context/` that create situations). |
| **switch / feature** | A per-tenant flag in `platform/l4_activation.py`, e.g. `l2_reasoning`, `l2_cards`; new in GeniOS-009: `goal_board`, `checkin_states`, `human_decides`, `goal_progress`. |
