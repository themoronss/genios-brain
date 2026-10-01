# ⛔ CORRECTIONS — this dossier is stale in 5 of its 8 central claims

**Added 2026-10-01. Nothing below is deleted from the six README files; this is an appended
correction, because *how* a claim went stale is the part worth keeping.**

**This dossier's own evidence baseline:** `harsh/mvp@b739bd5c`, **audited 2026-08-22**.
**Re-measured against:** the `speedrun008` working tree, **2026-10-01** — six weeks and one
architecture programme later.

> ⛔ **Read as current, this dossier would send the next person to build things that already exist
> and to trust things that were fixed.** Full measurement in
> `speedrun008/YCW27/layer-2-reasoning/06-L2-VERIFICATION.md`.

---

## The eight claims

| # | Claim as written | State | What is true on 2026-10-01 |
|---|---|---|---|
| 1 | *"17 registered reasoning units"* | ⚠️ **count changed** | **23 registered** — 17 core in 4 categories **plus 6 supplementary** (`legacy.rule`, `legacy.score_gate`, `core.temporal`, `core.relationship`, `core.signal_composition`, `core.planning`). The 17 are real; the roster is larger |
| 2 | *"`legacy_pack.py:24-145` turns a matched rule into one play and a **six-unit** DAG"* | ⛔ **STALE** | It schedules **ten**: `legacy.rule`, `legacy.score_gate`, `core.constraint`, `core.priority`, `core.confidence`, `core.temporal`, `core.relationship`, `core.planning`, **`core.alternative`**, **`core.validation`** |
| 3 | *"Alternative, trade-off, validation and recommendation units are not part of that default path"* | ⛔ **STALE** | True of `expertise._default_dag` (still 6). **False overall:** `core.alternative` and `core.validation` are on the **live** legacy lane, and a **20-unit `_ROSTER`** exists in `expertise.py` carrying all four, bound to fact paths, with latency budgets, dependency edges, `gates_on`/`essential` roles and per-unit `sources` |
| 4 | *"All four brain values are **hash-only**; a Company approval rule can change the hash while leaving judgment unchanged"* | ⛔ **STALE** | `WAVE Y1 · THE WELD` reads `organization_rules` into `blocked_play_ids`, which reaches `core.constraint` and **eliminates plays before ranking** — the code calls it *"the Organisation Brain's one hard lever … the difference between a policy and a preference."* `adaptive_preferences` are read too. ⛔ **But see A3 below** |
| 5 | *"`api/intelligence_routes.py:503-527` maps card score to `confidence_score`"* | ⛔ **FIXED** | `"confidence_score": conf01, # L4's calibrated confidence, or null — never the score`, with a separate `"priority_score": sc01, # ... NOT confidence` |
| 6 | *"`api/routes.py:2056-2098` explicitly emits `stakes: missing`, `completion: missing`"* | ⛔ **FIXED** | Both are computed: `gs(bool(card.get("do_nothing_consequence")))` and `gs(bool(card.get("success_signal")))`, with columns from migration `0065`. The code records the old bug: *"These were hardcoded to 'missing' — not absent by accident but written that way"* |
| 7 | *"The 17-unit native candidate is deliberately excluded from the manifest sweep"* | ✅ **HOLDS** | `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)`. `DEAL_COOLING_FULL_V2` is imported, usable and out of the sweep, with the activation step named in the comment |
| 8 | *"`_plays()` … stops after a **four-play cap**"* | ⛔ **STALE** | Replaced by a cap *"that RANKS instead of sorting by filename"* (CLG-07) |

---

## ⛔ The two claims that still hold are the load-bearing ones

**H1 · *"'17 units exist' is architecture proof, not evidence that a screenshot used 17-unit
reasoning."*** As true today as in August. The 20-unit roster is **built, budgeted and unswept** — the
largest built-and-not-called surface in the product. Switching it on is an activation with a runbook.

**H2 · The brain-mutation proof is still unavailable — for a different reason.** In August the wire was
missing. Today the wire exists (claim 4) and **the three runtime brains are empty**:
`learned_brain_entries` and `temporary_memories` have had machinery since migration `0045` and nothing
has produced a proposal. ⛔ **A policy mechanism that has never carried a policy.** The dossier's
required acceptance test — *hold three brains fixed, mutate the fourth, assert the one intended
semantic delta* — cannot run because there is nothing to mutate.

---

## What the dossier got RIGHT, and should be quoted rather than re-derived

The reasoning that has held up entirely, and which every later document has leaned on:

- **Hard elimination before total-order ranking** is the correct ordering, and it is implemented.
- **Confidence has one authority** and a below-floor decision returns `DEFER` with no selected
  candidate.
- **The explanation model may not decide** — action and confidence are fixed first, grounding is
  validated, invention rejected.
- **Score, confidence, urgency and coverage must be separate, and no scalar may substitute for
  another.** Claim 5 is fixed *because* this dossier said it.
- *"Wiring all 17 units without richer Layer 3 plays and golden decisions would add machinery, not
  judgment."* ⛔ **Still the sharpest sentence in the file**, and the reason the roster staying unswept
  is a decision rather than an oversight.

---

## Why it went stale, stated plainly

Nothing here was wrong when written. Five claims were **fixed or superseded** by work done between
2026-08-22 and 2026-10-01 — the L2 sections S1–S4, the `WAVE Y1` weld, the `WAVE Z1` staged roster, and
migration `0065`'s stakes/completion columns.

⛔ **The lesson is about dossiers, not about this one:** an audit is a measurement with a date on it,
and a measurement read six weeks later is a claim. This file exists so the next reader checks the date
before trusting the table — and the same warning applies to **this** file on 2026-11-15.
