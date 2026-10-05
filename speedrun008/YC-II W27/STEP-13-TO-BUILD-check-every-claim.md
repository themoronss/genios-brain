# STEP-13 · TO BUILD · check every claim, choose the lane, ask for what is missing

**Owner:** Claude. **Depends on:** `STEP-12`. **Moves:** forbidden outputs on the golden set **→ 0**;
every sentence on a card maps to evidence or is labelled an inference; `output_lane` is **never
NULL**.

---

## 1 · What is true now

| | Evidence |
|---|---|
| A proposal validator exists | `[CODE]` `context/proposal_gate.as_gate_validator` (used by R-6) and `contracts/claim_state.model_writable_fields()` |
| The card copy has field validators only | `[CODE]` `deliver/render.py:832-887` — V-01 length, V-02 invention |
| The lane router exists and is deterministic | `[CODE]` `reason/output_lane.py` — conflict first, failed/blocked ours, insufficient context → investigation, a decision under the 6,000 bp floor → monitor, DEFER → monitor, no-action → suppress |
| The model path skips it | `[CODE]` `reason/llm_decision_maker.py:827-846` builds the decision without `output_lane` |
| The question queue exists and nothing consumes it | `[CODE]` `evidence_needs` is written (`context/evidence_need_store.py:43`, from residue `signal_unreached`); `read_open_needs`, `close_need` and the executor `capture/acquire/need_executor.run_needs` have no production caller |
| Already-done work resurfaces | `[ATLAS]` golden replay 04 — blocked |

## 2 · Why

A fluent, wrong card is the fastest way to lose your trust (Atlas V.5: *"a confident wrong card to
a CFO ends a pilot"*). The expert may judge; nothing it says is shown until it is checked.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | every claim has a source | new `reason/expert/verify.py`, on `context/proposal_gate` | each `fact` must cite evidence ids that resolve; each `inference` names what it is based on; each `hypothesis` stays a hypothesis. An unsupported fact is dropped; if it was decisive, the file goes to Investigation |
| 3.2 | every number is a calculation | same | every number in the expert's text must equal a calculator's output in the dossier — days, counts, dates, amounts. A mismatch is replaced by the calculator's value or the sentence is dropped (RULE 08) |
| 3.3 | the right people | same + `STEP-04` + `STEP-09` | the recipient is never us; the target is never the connector; requester and target agree with the headers |
| 3.4 | not already done | same | before any card: is there a completion event — a reply in any connected mailbox, a booked meeting, a screen item marked done — that matches this exact ask? Then suppress, with the reason (replay 04: close the exact request, never every loop with that person) |
| 3.5 | the lane | `reason/output_lane.route` | outcome from the expert's `mode` (decide → decision · investigate → insufficient context · conflict → conflict · monitor → defer · suppress → no action); confidence from the **validated evidence state**, never asserted by the model; with D1 = A, the appraisal informs stakes. `output_lane` always written |
| 3.6 | ask for what is missing | `context/evidence_needs.py`; `capture/acquire/need_executor.py` | an unknown marked high-relevance becomes an `evidence_need`: fetched if a source can answer it, otherwise **one question to you** — *"Is saka.vc a fund?"*, *"Did you reply to Maria from ceo@thegenios.com?"* — and your answer feeds the brief or the file |

## 4 · What will happen

| The expert wrote | The check does |
|---|---|
| *"Maria replied 52 days ago"* | 52 is recomputed from the timeline; it matches → kept |
| *"Neel asked for your deck"* | no span in his mail says so → dropped; if decisive → Investigation: *"What did Neel ask for?"* |
| *"Send Boardy the update"* | the target is the connector → refused; the expert's alternative (the contact) is used |
| *"Follow up with Sal"* — but you already answered Sal later in the same thread | the reply is found in your sent mail → suppressed, with the reason |

## 5 · Expected

- forbidden outputs on the golden set: **0**;
- 100% of card sentences carry an evidence id or an inference label;
- `output_lane` NULL on new signals: **0**;
- `evidence_needs` read and closed — the executor has a caller.

## 6 · Verify

```
.venv/bin/python -m pytest tests/reason/expert/test_verify.py -q
#   an uncited fact is dropped; a wrong number is corrected; a connector target is refused;
#   a completed ask is suppressed — each by mutation
.venv/bin/python -m pytest tests/replays -q          # replays 01, 02, 04, 05, 07 tighten from "must not" to "must"
```
