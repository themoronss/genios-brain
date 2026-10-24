# 15 · Harsh's debug of the live cards, 23 Oct: what is broken, where, and whose unit it is

**Written for:** Rohit, and the agents building GeniOS-012.
**Date:** 23 Oct 2026. **Status:** findings, each verified. One fix built on `harsh/g012-h01-l2-order` (H-01).
**Purpose:** every defect below was measured on the design partner's production rows (read-only, 23 Oct
08:34 UTC; 34 cards, 24 L2 results, 12 expert reviews), and traced to a code line. Each one says which unit of
[09](09-STEPS.md) owns the file, so it is fixed once, by that unit's agent.

No mail text and no person's name is in this file. Counts and code lines only.

---

## What a manager sees today

34 cards. About 5 are worth a founder's minute. The rest:
- **"What to do" is empty on 34 of 34.** `cards.recommended` is NULL on every row.
- **"Why" is engine telemetry.** Across the 11 `dependency_stated` cards: 112 `situation.*` rows, 17 `thread.*`, 11 `derived.*`, and 0 quotes of what anyone said.
- **10 "We held the one we found…" question cards**, from 11 of 12 expert reviews held.
- **7 of 7 overdue-commitment cards are someone else's promise**, written as "You committed to…".
- **Other noise:**
  - 9 headlines start "Needs a decision —";
  - 2 duplicate pairs;
  - 11 cards name the founder in the third person;
  - 8 of 11 `dependency_stated` cards hang on one intro-platform node.

---

## The defects, worst first

| # | Defect (verified) | Code | Production number | Owner unit (09) | Smallest fix |
|---|---|---|---|---|---|
| **P0-1** | **Someone else's promise shown as the founder's overdue one** | `packs/general_v1.py:85` fires `commitment_overdue` on every commitment past due. The `owns` edge is correct (`context/pipeline.py:2219`), but `commitment.owner` is written only when the speaker's address resolves (`pipeline.py:2253-2262`). So the card has no owner, and the render model writes "You committed to…". | 7 of 7 `commitment_overdue` cards. All 7 came from inbound mail; owner edges point at the senders. `commitment.owner` is missing on 7 of 7. | `context/pipeline.py` → **N1b**; the voice → **S34.U3** / L5.2 | Always write `commitment.owner` (name or node when no address) plus whether the owner is us. Fire `deliver_commitment` only on our promises. Theirs is a "waiting on them" card, not "you owe". |
| **P0-2** | **L1 never stores a signal's thread, direction or turn** | `capture/esqe/publisher.py:580-645` `_row_for` does not copy `thread_key`, `direction`, `turn_index`, `thread_depth`, `ball_in_court` (the in-memory signal has them, `publisher.py:385-396`). | `qualified_signals` for the org: `thread_key` NULL on **1,383 of 1,383**, `ball_in_court` NULL on 1,383; 1,263 of those events do have a thread. | `capture/esqe/*` → **S12.U2 → U12-07** | Copy the five fields in `_row_for`; backfill from `source_events.parent_object_id`. **This is why L2 subjects split into `thread:X:commitment` / `:date`** (`reason/l2/inputs.py:157-165`). Three stored moves were spent on "which thread does this signal belong to". |
| **P0-3** | **The claim check holds what the model got right** | (a) The dossier prints `[sig:sig_x]`, `[node:node_x]`, `[sit:sit_x]`, `[loop:loop_x]`; a live model cites `sig_x`, and it drops as `unknown_evidence`. (b) One failed decisive fact holds the whole move (`reason/expert/verify.py:1268`). | Held: 11 of 12 expert reviews; offline replay of the 24 L2 results gives 23 of 24. **(a) is 112 of 182 drops (62%).** | `reason/expert/verify.py` → **S20.U2** (13b port) | (a) Attached below: `printed_ids`, measured offline on the 24 stored results (`unknown_evidence` 182 → 70, shown 1 → 3; 4 of 4 mutations killed). (b) Keep the move when at least one decisive fact stands: 22 of 24 would show. That is a design decision for Rohit. |
| **P1-4** | **The model is never told who the founder is** | `reason/l2/sweep.py:338-341` reads `us` / `our_names` and never passes them to `build_l2_dossier`. Identity reaches a prompt only through the company brief, which has 0 accepted lines. | 24 of 24 dossiers say "No company brief is accepted". One judgment wrote the vendor's move to the founder. | `reason/l2/dossier.py` → **U12-08 / U12-15**; the brief → **S02.U4** | One "who you work for" line from `orgs.name` / `orgs.company` and `identity_for` in the dossier head. Keep it out of `compose` (`tests/platform/test_company_brief.py:63-69`). |
| **P1-5** | **A held or find_out review becomes a question card** | `reason/domain_shadow.py:837-840`: INSUFFICIENT_CONTEXT → `asks.ask_the_founder`. The small-move rule covers only `act` (`reason/expert/small_move.py:33-40`). | 10 cards. 17 of 24 L2 results are `find_out`, 10 of them about whether a May–July meeting happened. | `reason/domain_shadow.py` → **U12-03 → S18.U4** | Low stakes plus low urgency plus nothing owed → a brief line, not a card. |
| **P1-6** | **Compiled-lane cards: no move, telemetry why, the situation's phrase as headline** | `deliver/card_builder.py:1336` (only `expert.file_review` writes `recommended`); `card_builder._why` filters nothing (all snapshot evidence, `deliver/pipeline.py:63`); the authored hint "in the words the record used" (`dependency-stated.yaml:73`); the name chain skips `dependency.counterparty` (`card_builder.py:1082`). | 13 compiled cards; the counts above. | `deliver/*` → **S34.U3 / S34.U2 / S34.U1** | Drop `situation.*` / `derived.*` / `interpretation.*` from `why` and add the grounding quotes. Verb-led headline: a YAML change, which needs re-stamping. |
| **P1-7** | **"Needs a decision —" on cards that are not decisions** | `deliver/render.py:210`; a card reaches `review` because a gate failed. | 9 cards | **U12-18** | The lane as a chip (already planned). |
| **P2-8** | **One promise, two commitments** | `context/pipeline.py:2214-2216` keys on the subject, the verbatim quote and the due date. | 2 duplicate pairs (two due dates; two quotes) | **N1b** | Key on owner plus normalised action; due as a fact, latest wins. Merge the existing pairs once. |
| **P2-9** | **One counterparty, many situations** | Each stated dependency is its own situation and signal (`context/stated_dependency.py:88-130`, cap 6 per node at `correlation_dependency.py:189`). | 8 of 11 `dependency_stated` cards on one node | `context/` → **S15.U1 / N4** | One finding per counterparty (or per thread), the statements carried as a list. |
| **P2-10** | Support readings run for every tenant | `context/runner.py:882` runs `refresh_support_situations` with no activation check. Shadow by design: no card. | 192 `first_response_overdue` (domain `support`, not activated). They fire on newsletters and bots too. | none | Cost only. Optional: skip automated senders. |

---

## Built: H-01 · the L2 pass judges what is live first

- **Branch:** `harsh/g012-h01-l2-order` (on `speedrun008` `f289ca55`), commit `7e17ddfa`.
- **File:** `reason/l2/sweep.py`. No other unit owns it.
- **The defect:** nearest-due-first with signed hours judged the *most overdue* subject first. All 24 judged rows were 2,087–4,227 hours past due.
- **Now:** a deadline within a week either side, closest first; then the newest evidence first.
- **Proof:** a pure test, plus a Postgres call-site test at one judgment a pass. 4 of 4 mutations killed. No flag, no migration, no prompt change.

---

## Appendix · `printed_ids` (for S20.U2)

Called at the two parse sites before `ExpertReview.from_mapping`:
- `reason/l2/judge.py _parse`
- `reason/expert/review.py _parse`

Then the review, its validation, the check and the stored row all carry the printed id. The function only rewrites a string that IS a bare id with exactly one printed match. The full patch with tests is with Harsh.

```python
def printed_ids(payload, evidence_ids):
    by_tail = {}
    printed = set(evidence_ids)
    for ref in printed:
        if ":" in ref:
            by_tail.setdefault(ref.split(":", 1)[1], []).append(ref)
    alias = {t: refs[0] for t, refs in by_tail.items() if len(refs) == 1 and t not in printed}
    def walk(v):
        if isinstance(v, str):
            return alias.get(v, v)
        if isinstance(v, (list, tuple)):
            return type(v)(walk(x) for x in v)
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        return v
    return walk(payload) if alias else payload
```

---

## Update, 23 Oct evening · the local run with production's models

Run on a local copy of the design partner's org: same models as production, `eval_time` 24 Oct 00:30 UTC, nothing sent. Spend about $5.

**Scorecard** (`ideal_card_gap.py`):

| | Cards found | Fields filled |
|---|---|---|
| Start | 4 / 20 | 9 / 220 |
| After round 2 | **9 / 20** | **37 / 220** |

Three cards now carry 8 fields each.

### Built on this branch

| Commit | What changed | Proof |
|---|---|---|
| H-03 | `commitment_overdue` fires on our own promises only (general 1.6.0) | 6/6 mutations |
| H-04 | `printed_ids` | 4/4 mutations |
| H-05 | With `l2_cards`, a file is judged before a seed that no file holds. 70 of the 239 due subjects were such seeds | 2/2 mutations |
| H-06 | R-9 output ceiling 8,000 → 12,000 tokens; per-call cap 15 → 25 cents. **Spend policy: needs the owner's yes** | Measured: 3 of 8 deep calls were cut at 8,000 |
| H-07 | Claim check v5 (see below) | 10/10 mutations |
| H-08 | A `nothing`/`wait` review with an all-null move reads as no move. 4 of 41 calls had been refused as malformed | 2/2 mutations |

H-07 in detail:
- EARNED gains the counts and connectives the check was reading as names ("Two" ×6, "One", "Three", "Separately", "Earlier", "Someone").
- A time zone (`_ZONE`) is never a name.
- A bare id (`_BARE_ID`) is never a number.
- A statement the dossier prints with no id can be cited by its own words, or by its section when that section prints no id (`statements_cited`).
- **P-c:** a move stands when one of its rested facts that cites mail still stands.
- Replay of the 21 file judgments: 5 shown → 10 shown. Golden 63 → 63 on every commit.

### Found, and owned by your units

1. **Throughput is the first limit.** 239 subjects were due, at 10 per pass and $2 a day for R-9 (about 20 judgments a day).
   - 12 of the 20 ideal cards were on files never judged.
   - Production needs about 8 days to judge the backlog, longer than the 7-day trial.
   - A one-time backlog budget is about $17: 169 files at about $0.10.
2. **A reviewed file in `sales` stays shadow** (`expert_shadow`). Only `admin` and `founder_office` are live.
   - One of the 3 files is a VC (IIMA Ventures) filed as a `sales/opportunity`.
   - Switching `sales` on would also put 95 `channel_touch` situations live.
   - Better: route a covered file by what its counterparty is, not by the situation's domain (`domain_shadow._decide_covered_files`).
3. **The intro-platform file's dossier is 294k characters** (p90 is 32k). It was over every per-call cap until H-06. It needs a size bound (`reason/expert/dossier`).
4. **Steps, how, goal and avoid stay 0/20.** Only the card writer (R-10, `card_copy`, off) writes them, and the dashboard (main) reads no `cards.copy` field at all. That is Step 7.1 / 7.4.
5. **The org's company is "Homians"**, while the founder's mail says GeniOS, so "GeniOS" fails the check as a name. This is tenant data.
6. Still held, because the model wrote something its lines do not hold:
   - glosses on readings, such as "turn is with them (Antler/Theresa)";
   - absence claims with no quote;
   - "(n=19)", which the check strips from the lines but not from the claim.

---

## Update, 24 Oct · the goals (Step 6), built on this branch

Harsh asked for goals first, and so did Rohit (WhatsApp, 24 Oct: "Goals pahle banaiye… goals se related cards aane easy hain"). On 24 Oct the design partner had **no goal anywhere**: 0 brief goal lines and no goal object. The drafter (S27.U1) was run once locally and proposed 4 goals, about 2 of the ideal 10 (NSRCEL, Boardy).

Built exactly as `07-GOALS.md` and `GeniOS-008/00-ARCHITECTURE.md` "Goals" describe:

| Unit | Commit | What |
|---|---|---|
| S28.U1 | `932b98ea` | `contracts/goals.py`; migration 0254 `company_goals` (revision rows; approved/active require an approver, as a constraint) and `goal_situation_links`; `context/goals.sync_from_brief`, run first in every sweep. |
| S29.U1–U3 | `b2186e68` | Block G in the L2 dossier (live goals with `[goal:<id>]`; waiting proposals listed apart, with no id). `goal_impacts` and `goal_proposal` on `L2Judgment` (validated and pruned like every judgment line). Prompt `l2-judgment.v2`. `context/goal_admission` HOLDs a duplicate for the same work, anything over the weekly cap (D12: 3), and a proposal with no act of our own; ADMIT writes a pending brief goals line. |
| S30.U1 | `1e2d9fe0` | Each impact on a live goal is linked to the situations L3 admitted. |
| S31.U1 | `2c8800cd` | Migration 0255 `cards.goal_refs`, refreshed at every card build: the live goals proposed for the card's file, or linked to its admitted situations. The queue's three doors serve it. `ideal_card_gap` reads it, and the goal field is `shared_ok`. |

### Not built

- Block G in the **expert** dossier. Rohit's org judges files through L2 under `l2_cards`.
- S28.U2 `GET /v1/goals`.
- S30.U2 progress.
- S31.U2–U3, the goal board and the dashboard goal row.
- N2 categories.

### Decision for Rohit: D12

The weekly cap of 3 L2 goal proposals conflicts with a new tenant's first week: `/preview` expects 10 goals on day one. Proposed: an onboarding allowance, for example 10 in the first week after connect, and 3 a week after that.
