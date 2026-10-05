# STEP-14 · TO BUILD · the card — one file, one living card, in the gold shape

**Owner:** Claude. **Depends on:** `STEP-13`. **Decision:** `06` D8 (screen reminders). **Moves:**
duplicate cards per subject **→ 0**; every card passes the contract check.

---

## 1 · What is true now

| | Evidence |
|---|---|
| A card per **signal**, not per subject | `[CODE]` `deliver/pipeline.py:46-131, 381`; the per-situation grouping (`:134-179`) is measurement only and `cards_from_situations` sets a label only (`:374-378`). `[PROD]` the offer to Khushi became six cards; nine `dependency_stated` cards for related asks |
| The copy prompt is contaminated | `[CODE]` `deliver/render.py:750` hard-codes *"Send Titan Capital your traction metrics"*, *"Answer Divyanshu's pricing question"*; `:767` writes *"for a salesperson"* |
| The copy never sees the reasoning | `[CODE]` `render_copy` receives facts and quotes — not the decider's rationale, the rejected options, the unit findings or any history (`deliver/render.py:787-904`) |
| False claims from fallbacks | `[PROD]` *"nsrcel — a dated payment obligation is open"* (`money-owed-either-way.yaml`'s gate is any `commitment.due_at`); internal field names on cards — *"party.role"*, *"8 data points, 1 unreadable"* |
| Screen reminders hidden | `[CODE]` `reason/moments/guards.py:68-71`; `capture_policies.moments_display` defaults false (`platform/capture_policy.py:254, 498`). `[PROD]` 65 hidden |
| Already right on `harsh/mvp` | expired cards are rebuilt, human-decided ones never (`c22d0f00`, `2c42722d`); the drawer no longer crashes on structured values (`2f595277`) |

## 2 · Why

The card is the only part you see. Everything upstream is wasted if the card is one of six, names
the wrong person, or invents a payment.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | one file, one card | `deliver/pipeline.py`, `deliver/card_builder.py` | cards are built per **workstream** (`situation_id` carried end to end); signals of the same file merge into its card |
| 3.2 | a living card | `deliver/store.py`; `card_events` | a material change updates the card — a new version and a `card.updated` event naming what changed — never a second card. Its versions are visible |
| 3.3 | the gold shape | `deliver/card_builder.py` | **situation** · **subject and role** · **what remains** · **why now** · **recommended** (who, what, for whom, by when) · **alternative** · **wait or stop** · **done when** · outcome window · evidence receipts · the confidence vector · *"playbook not yet reviewed"* when that is true (D3) — the Atlas's gold card and the Secret War audit's actionable contract |
| 3.4 | clean copy | `deliver/render.py:698-784` | synthetic examples only; the persona *"a founder's chief of staff"*; the expert's explanation and scenarios passed in as the render hint, under the existing V-01/V-02 validators |
| 3.5 | the contract check | new `deliver/card_contract.py`, before insert | refuse — to Investigation, or abstain with a reason — when: the subject or recipient is us · no dated fact · the value is a quote and no quote is present · an internal field name appears · money is claimed with no money in the evidence |
| 3.6 | screen reminders | D8 | shown inside the morning brief (`STEP-15`) first, then in the moment |

## 4 · What will happen

| Today | After |
|---|---|
| Six cards about Khushi's offer | **one**: *"Khushi — offer sent 5 Aug. Waiting on: her acceptance and the signed documents. Blocked on: the ESOP board approval (yours)."* |
| *"nsrcel — a dated payment obligation is open"* | refused by the contract check; NSRCEL's real item — the assignment due — on the program's card |
| *"Which is right? Maria Exconde: party.role"* | gone — an internal field name; the real item is *"Maria replied 11 Aug; your reply is owed"* on her intro card |

## 5 · Expected

- duplicate cards per subject: **0**;
- contract-check failures reaching the dashboard: **0**;
- cards with you as the subject: **0**;
- the copy prompt holds no real names.

## 6 · Verify

```
.venv/bin/python -m pytest tests/deliver -q
#   one workstream with five signals → one card; a change → a new version, not a new card;
#   each contract rule refuses its case — by mutation; render.py contains no real names (AST check of the literals)
```
