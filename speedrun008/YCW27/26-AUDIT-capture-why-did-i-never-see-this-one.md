# 26 · `capture/` AUDIT — "why did I never see X?" becomes a receipt

**Written for:** Rohit. **Date:** 2026-10-03. ⛔ Step `1.4` of
[`21-PLAN-TO-PRODUCTION.md`](21-PLAN-TO-PRODUCTION.md) — **the last of Phase 1.**

```
capture/    158 files · 47,184 lines · 25 writers · 25 tables · ⛔ 19 with no receipt
new tests   12  ·  mutations 10 caught · 0 survived
receipts    43 → 44 · ⛔ capture/ 5 → 6, all correctness
```

---

## 1 · What the package already had, and why that shaped the search

`capture/` arrives with the strongest receipt set in the product — **five, all correctness**: no
sync cursor ahead of the clock · the parked queue is not a black hole · every drop we might be
wrong about can still be reviewed · the tenant is still being fed · attachments carry readable
text.

⛔ So the nineteen uncovered tables were checked for a **different** gap, not a repeat. Every one of
`publication_rejections`, `unclassified_observations`, `signal_lifecycle`,
`org_qualification_floors`, `qualification_floor_changes` and `message_fingerprints` is read inside
`capture/` by the module that owns it — ⛔ **none is an orphan**, and `source_waitlist` was already
declared in `table_coverage.UNREAD_WRITES`.

---

## 2 · ⛔⛔ The claim, and the module that was built for it

`capture/journey.py` opens on the sentence it exists to satisfy, quoted from `qualification.py`:

> *"a system that discards 92% of what a founder was sent has to be able to answer **"why did I
> never see X?"** in one query"*

and then records what it cost to not have the join:

> *"Every layer kept its half of that bargain and wrote its refusal down. **Nothing ever joined
> them.** Measured on the pilot org: `event_trace` holds 10,840 rows and had **NO read surface at
> all** — not an endpoint, not a script … Of 138 events one support question was really about, 103
> stopped at `s4_esqe short_circuit bulk_headers` and 33 at `llm5_not_business`; **a founder
> reading `/qualification/drops` would have found nothing and concluded the events were lost.**"*

✅ `journey.event_journey` **is** the join, and it is reachable — `api/routes.py`, a script and a
test. ⛔⛔ **What nothing checked is that every event HAS an answer for it to render.**

### Receipt **44** · *"every captured event that reached no signal says where it stopped"*

⛔ **Five derivations, nothing spelled:**

| | |
|---|---|
| the stopping actions | `journey.TRACE_STOPPING` — `drop`, `park`, `short_circuit` |
| the event-keyed ledgers | `journey._LEDGERS` **minus** `journey._PER_SIGNAL_LEDGERS`, because ⛔ **a per-SIGNAL refusal cannot name an event that never produced a signal** — the module declares that distinction itself |
| the "did it reach a signal" test | `qualified_signals`, that tuple's success member |
| the horizon | **4 × `config.sync_interval_hours`** — the declared sweep tick, so an event mid-flight is never counted |
| ⛔ the one judgement | the multiplier **4**, stated in the builder's docstring rather than buried in the SQL |

⛔ A fifth event-keyed ledger joins this check **without an edit**. And the builder **refuses rather
than guesses** when its source changes: it raises if `_LEDGERS` loses the success ledger, and ⛔
raises if every refusal becomes per-signal — *"a bigger finding than this receipt, and should be
read before it is deleted."*

⛔ **It does not duplicate its sibling.** *"Every drop we might be wrong about can still be
reviewed"* asks whether a model's **judgment** can be re-examined (its SQL requires the raw payload
to be **gone**); this one asks whether an answer exists **at all**. A test pins that the sibling
still asks the narrower question, so the two cannot converge unnoticed.

---

## 3 · ⛔ Two mutations survived, and both were about EMPTINESS

| | |
|---|---|
| ⛔⛔ **`_PER_SIGNAL_LEDGERS = frozenset()`** | My test looped over that set to assert its members are absent from the SQL — and an **empty** set made the loop run zero times while the per-signal tables flowed into an event-keyed query. ⛔ *An empty collection makes an assertion over it vacuous* — the same defect as a gate that can never be red. Repaired: the non-emptiness is asserted **first**, and the two known members are named |
| **the quoted sentence reworded** | ⛔ **an invalid mutation, not a survivor**: the phrase appears **three** times, and changing one left it present. Re-run against all three — caught |

⛔ And a third was a **no-op**: `_LEDGERS = () or (…)` evaluates to the original tuple, because `()`
is falsy. ⛔ *An invalid mutation is not a surviving mutation*, and that case is already covered by
the two builder tests that monkeypatch `_LEDGERS` and assert it raises.

### ⛔ The harness itself needed two repairs

| | |
|---|---|
| a **missing file** crashed it | and took the results of every mutation that had already run with it. It now reports `NOT APPLIED — no such file` and continues. *A missing file is not a surviving mutation either* |
| a phrase that appears **more than once** | was reported as not-applied, which is correct but useless when the intent is to change all of them. The harness can now do that deliberately and prints the occurrence count |

---

## 4 · Doctrine

| Rule |
|---|
| ⛔⛔ **an empty collection makes an assertion over it vacuous** — assert non-emptiness before iterating |
| ⛔ **a no-op mutation is not a survivor** — `() or (x,)` is `(x,)` |
| ⛔ **a phrase that appears three times needs all three changed**, or the mutation is invalid |
| ⛔ **a missing file must be reported, not raised** — a crashing harness loses the run |
| ⛔ **name the one judgement in a derived query** — here the multiplier, in the builder's docstring |
| ⛔ **a builder refuses rather than guesses** when its declared source changes shape |
| **two receipts about the same ledger must each pin what the other does not ask** |

---

## 5 · Phase 1 is closed

| step | package | result |
|---|---|---|
| `1.1` | `api/` | 11 candidates, 11 retired · `learning_objects` write-once guard |
| `1.2` | `platform/` | 15 retired · **receipt 43** (a park the health check excludes) |
| `1.3` | `reason/` | 20 retired, 0 receipts · ⛔ the audit's own naming column **deleted** |
| `1.3b` | — | ⛔⛔ a health-data privacy guard, and a destructive-merge gate |
| `1.4` | `capture/` | ⛔ 6 candidates retired · **receipt 44** — *"why did I never see X?"* |

```
52 candidates raised across five steps · 52 retired · 3 receipts · 6 guard suites
receipts 41 → 44, measured: feedback 10 · reason 8 · deliver 7 · capture 6 · readiness 5
                           context 3 · platform 2 · executive 2 · packs 1 · api 0 · mcp 0
⛔ the first draft of this line listed six packages as if that were all of them
```

⛔ **Next: `2.1` — Atlas L2's nine open claims**, the largest remaining block, and `L2-02`'s mover
is already a read-only query on Harsh's page (`H8.5`).
