# 23 · `platform/` AUDIT — fifteen retirements, and a park the health check excludes

**Written for:** Rohit. **Date:** 2026-10-03. ⛔ **Step `1.2` of
[`21-PLAN-TO-PRODUCTION.md`](21-PLAN-TO-PRODUCTION.md).**

```
platform/   49 files · 12,651 lines · 18 writers · 29 tables · ⛔ 25 with no receipt
new tests   23  ·  mutations 16 caught · 0 survived   (11 + 12 tests, 9 + 7 mutations)
⛔ candidates 15 raised · 15 retired · 1 finding survived
receipts    42 → 43 · ⛔ platform/ 1 → 2
```

---

## 0 · Why `platform/` was second

One receipt over 12,651 lines, 18 writers, 25 unreceipted tables — and ⛔ **it is the package every
other package imports**, so one wrong invariant here travels furthest.

---

## 1 · ⛔⛔ Fifteen candidates, fifteen retirements

| | Candidate | ⛔ Why it died |
|---|---|---|
| 1 | ⛔⛔ `pipeline_counters` — **written by `funnel.py`, zero readers, no receipt**, and one of the original VERIFIED-MISSING items | ✅ **It IS read** — `funnel.read_sweep` / `_READ_LATEST`, and `api/routes.py` calls that accessor. ⛔ **A table read through its module's own API shows zero external SQL readers** — the same class of mis-signal as `api/`'s decorator-wired functions |
| 2 | the four **activation tables** have no receipt, and `P6` (*is anything live?*) is unanswerable | ⚠️ true, and ⛔ **a cross-layer ordering receipt would have to be INVENTED** — no module states that L3 must precede L4. Declined: *a gate derived from an invented claim is a gate nobody reads* |
| 3 | ⛔ `use_domain_compiler` — the anti-pattern all four activation docstrings cite — **still exists in `config.py`** | ✅ **Deliberately kept, and said in capitals:** `l3_activation.py` — *"THIS MODULE DOES NOT RETIRE THE GLOBAL FLAG, AND MUST NOT YET"*; `config.py` — *"being retired, not extended. It is left exactly as it was."* Multiple tests assert it is `False` |
| 4 | `graph_source_refs` — 22 external readers, no receipt | ⚠️ true; the derivable claim turned out to belong one layer over (below) |
| 5 | ⛔ `independence_group` — does anything enforce that `same_message` refs count once? | ✅ Built and read in **five** places — `feedback/units`, `reason/decision_maker`, `reason/reasoners/confidence`, `context_unit`, `derived_provenance`. ⛔ Rule 11 groups by it |
| 5b | ⛔⛔ an **ungrouped** ref counts as independent (`feedback/units.py:401` falls back to `source_ref_id`) — Atlas `L2-02` | ⛔⛔ **ALSO ALREADY DECLARED, and I got this wrong five minutes after writing it.** `reason/runner.py` holds a table — `LINEAGE_UNPROTECTED["cross_channel_quote"]` — saying `independence_group` *"is written only for the screen/email same-message case"*, with the reason in capitals: **NOT BUILT, ON PURPOSE** — *"A two-connector tenant cannot produce the case, and building a lineage system for an unreachable failure is the over-scaffolding this plan refuses."* Mover: **"the third connector"** |
| 6 | `org_run_leases` — a stuck lease would stop a tenant silently | ✅ **self-healing by design**: 120 s TTL, heart-beaten, `where lease_until < now() or holder = …`. A holder that stops beating lapses within two minutes and the next caller takes it |
| 7 | `presence_leases` · `warm_lane_slots` · `rate_counters` | ✅ same shape — lease state read through the module's own accessors |
| 8 | `auth_sessions` · `auth_refresh_rotations` · `device_auth_codes` — 0 external readers | ✅ read inside `platform/auth.py` and `sessions.py`, which is the whole point of a credential boundary |
| 9 | `api_keys` written by four modules | ✅ minting, revocation, the key cache — already checked in step `1.1` |
| 10 | `agent_registry` written by `secret_box.py` | ✅ credential rotation writes the registry row it re-encrypts |
| 11 | `seat_slice_versions` · `realtime_events` — written, 0 external readers | ✅ the realtime slice's own versioning, read by `realtime.py` |
| 12 | `onboarding_progress` · `seat_capture_settings` · `screen_session_deltas` | ✅ per-seat state served back through its own routes |
| 13 | `l2_work_queue` — rows left behind by a run that should have marked them | ✅ the docstring states the rule and the code keeps it: *"no caller can leave a row behind that another caller already covered, and no row is marked by a run that could not have seen its events"* |
| 14 | `sync_jobs` · `audit_log` · `capture_policies` · `devices` | ✅ each read by its own module or an API route through it |

> ⛔⛔ **Two audits, two packages, twenty-six candidates, twenty-six retirements before the one
> that held each time.** That is what the discipline costs and what it buys: *every finding that
> survives has been attacked from five directions first.*

---

## 2 · ⛔⛔ The finding: a park the health check excludes by construction

`migrations/0136_warm_lane.sql` comments the column itself:

> *"`parked_at timestamptz` — **attempts ran out: parked for a human**, never retried, never
> blocking a re-enqueue."*

⛔ **And every reader uses `parked_at` only as an exclusion:**

```
warm_lane.py:480   parked_at = now()                          ← the park
warm_lane.py:383   _OPEN = "done_at is null and parked_at is null"
api/routes.py:225  backlog count — the same predicate
housekeep()        warns on the age of the OPEN backlog · prunes only done_at rows
⛔ statements that SELECT a parked row:  NONE
⛔ receipts about them:                  NONE
```

⛔⛔ **So a tenant whose rows park stops being processed silently and permanently — and the health
signal reports zero open rows and looks fine.** A lane with a hundred parked rows and none open is
indistinguishable from an idle one.

> ⛔ *A refusal nobody can see is a silent stop*, and this is the worst version of it in the
> product: the health check does not merely **miss** the parked rows, it **excludes them by
> construction**. And they are never pruned — `housekeep` deletes only rows with a `done_at` —
> so the invisible set **grows**.

### Receipt **43** · *"no warm-lane row is parked where nothing can see it"*

⛔ **The predicate is DERIVED from `warm_lane._OPEN`, never respelled**, and the builder asserts the
shape: if the lane ever counts parked rows as open they are visible, and the receipt must be deleted
deliberately rather than left asking the wrong question. ⛔ **The mutation proves it** — changing
`_OPEN` fails five tests.

⛔ **And it is a precedent, not an invention**: L1 already makes this exact claim for the other
parked table — *"the parked queue is not a black hole"*, over `parked_events`. This is that claim
applied to the table that lacked it, and a test asserts the precedent still exists.

### What the 11 tests pin

the receipt is correctness-shaped and org-filtered · the lane still excludes parked rows from
`_OPEN` · ⛔ **the builder's assertion fires** when the lane changes its mind (proved with
`monkeypatch`) · ⛔ **nothing but the receipt selects a parked row** — the finding itself, so the day
the human surface is built this fails and the receipt is re-read · the prune still restricts itself
to finished rows · ⛔ **something still parks a row**, because a receipt whose subject cannot occur
is green forever · and the migration comment the claim quotes is still there, because *a claim about
prose needs attribution*.

---

## 2b · ⛔⛔ And adding the receipt BROKE a test — which turned out to be the test's defect

The full suite went red on `tests/deliver/test_nothing_dies_of_low_confidence.py::
test_a_card_with_no_lane_at_all_has_a_receipt`:

```python
found = [r for r in R.receipts(None) if "lane" in r.claim]
receipt = found[0]
assert receipt.layer == "L5"          # ⛔ AssertionError: 'L1' == 'L5'
```

⛔ **Three claims contain the substring `lane`:**

```
[L5] every delivered card carries a lane, or is labelled unrouted    ← the one it meant
[L6] the delivery control plane has run                              ⛔ `lane` INSIDE `plane`
[L1] no warm-lane row is parked where nothing can see it             ⛔ receipt 43, added today
```

⛔⛔ **The test had been one receipt-ordering away from asserting about the wrong receipt since the
L6 claim was written**, and it passed only because the intended one happened to come first. *A grep
hands over a sentence without its subject* — and `[0]` of a substring match is that grep.

### ⛔ The rule, not the rewrite — and the rule is enforceable here

Ten sites use this idiom. ⛔ **Measured rather than assumed:** exactly **one** substring was
ambiguous. So nothing was rewritten; the one site now names its claim exactly, and a new guard —
`tests/platform/test_a_receipt_lookup_is_unambiguous.py` — fails on **any** future collision, in
one named place, instead of inside whichever test loses the ordering. It also fails the other way:
a claim reworded out from under a lookup leaves it matching **nothing**.

### ⛔⛔ The guard needed three corrections of its own, and each is a known rule

| | |
|---|---|
| **a regex over the file text** | matched the **repair comment**, which quotes `if "lane" in r.claim` in order to explain its removal. ⛔ **Fifth instance in this programme** of a text-level guard breaking on the sentence that documents the thing it forbids — and the rule was already written in `tests/README.md`: *a claim about CODE needs the AST* |
| **every `in …claim` comparison** | reported a collision at `assert "declared" in receipt.claim` — ⛔ **an assertion about an already-selected receipt, which is perfectly safe.** Selecting by substring is the defect; asserting a word in one you hold is not, and conflating them is a pattern matching the shape without its subject |
| ⛔ **a surviving mutation** | making the `receipts(...)` check unconditional changed no answer, because every `.claim` filter today happens to sit in a receipts comprehension. ⛔ Rather than delete a check that **will** matter the first time something else is iterated with a `.claim` filter, the scan became a pure function over source text and both branches are now exercised — *one implementation, tested directly*, the same repair as `table_coverage.set_columns` |

⛔ **And my first measurement of the class was wrong too**: a regex said *"5 of 6 unique"*; the AST
found **two** ambiguous, not one — and then one of those two was the false positive above. *A
resolver that answers for part of its input answers for none of it*, in both directions.

**7 more mutations, 0 survived.**

---

## 3 · Doctrine

| Rule |
|---|
| ⛔ **a table read through its module's own accessor shows zero external SQL readers** — the second column mis-signal in two audits |
| ⛔ **a health predicate that excludes a failure state hides it twice** — once from the count, once from the alarm |
| ⛔ **an invisible set that is never pruned grows** — which is what makes it a receipt rather than a note |
| ⛔ **derive the predicate from the module's own constant**, and assert its shape so the receipt cannot drift |
| ⛔ **a receipt whose subject cannot occur is green forever** — pin the writer |
| ⛔ **declined: a cross-layer ordering nobody states** — the claim would have been invented |
| ⛔ **adding a receipt can break a test, and the break can be the TEST's defect** |
| ⛔ **a substring lookup that takes `[0]` tests whichever row is first** — name the exact claim |
| **twenty-six retirements across two packages is the cost of a finding worth keeping** |

---

## 4 · What `platform/` leaves open

| | |
|---|---|
| ⚠️ **the four activation tables** | no receipt, because no module states a cross-layer ordering to derive one from. ⛔ The question *"is this tenant live?"* is `R2`'s, and Phase 0 answers it by **doing** it |
| ⚠️ **`graph_source_refs`** | 22 external readers, no receipt. Its derivable claim is `reason/`'s — step `1.3` |
| ⛔ **handed to step `1.3`, corrected** | Atlas `L2-02` is **declared, not unguarded** — `LINEAGE_UNPROTECTED` names it with a reason and a mover. ⛔ **The open question is the MOVER, not the gap:** *"the third connector — until then the case cannot occur on a live tenant."* So `1.3`'s job is to measure whether the third connector has arrived, not to build the lineage system. ⛔ I framed this as a gap and it is a declared silence — the fifteenth retirement of this audit, and the only one of mine that was five minutes old.

⛔⛔ **AND THE MOVER IS NOW A ONE-LINE QUERY.** The CODE already implements more than two connector
kinds — `calendar`, `drive`, `hubspot`, `linear`, `notion`, `composio`, `database`, `push_ingest`
and more. The mover is about what a **TENANT** has connected, which only production can answer:

```sql
set transaction read only;
select org_id, count(distinct source_type) as kinds
  from connections where status = 'connected' group by 1 order by 2 desc;
```

⛔ **Any tenant at three or more means the cross-channel-quote case has become reachable**, and
`LINEAGE_UNPROTECTED`'s mover has fired — which turns a correct declared silence into real work.
Added to `HANDOFF-HARSH.md` §H8.5 |
