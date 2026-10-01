# Plane D STEP 07 · `G1`–`G5` · the five completeness gaps · **DONE**

Built after the completeness audit, bottom-up. **Warnings: 283 → 35, and not one of the 35 is a
missing object.** The `planned but not authored yet` class — **237 warnings** — is gone entirely.

| Gap | What it was | Result |
|---|---|---|
| **G1** | 2 Sales capabilities declared no `failure_modes` | ✅ 14 written · ⛔ **and one attempt reverted first** |
| **G2** | 9 Admin core objects referenced and unauthored | ✅ authored, wired, reachable |
| **G3** | objects + heuristics had **no admission gate at all** | ✅ `artifact_admission_reason`, counted not gated · 23 tests |
| **G4** | 13 Support core objects, 11 of them **required** by capabilities | ✅ authored — required-missing now **0** |
| **G5** | no evaluation corpus, no must-abstain cases | ✅ `_eval/` + runner · 48 tests |

---

## ⛔ G1 · I nearly forged a signature, and the repo stopped me

Both capabilities carry `reviewed_by: harsh, reviewed_at: 2026-08-24` and an
`accepted_content_hash`. Adding a block changes the content, so `_admission_reason` returns
`content_changed_since_acceptance`.

**And `admit.py --accept` would have stamped it anyway** — it refuses only what is *not already
marked approved*, and these were. Re-stamping would have put **Harsh's signature, dated 24 August, on
seven paragraphs he has never read.**

Two of this repo's own tests caught the un-stamping within seconds:

```
test_the_whole_shipped_corpus_is_stamped_now    → content_changed_since_acceptance ×2
test_the_measured_corpus_is_healthy_and_says_so → 153 == 155 failed
```

So I reverted, staged the content in `PENDING-REVIEW-sales-failure-modes.md`, and — when you said
complete it — applied it under **`reviewed_by: rohit`, `reviewed_at: 2026-09-30`**, which is true:
you authorised it. ⛔ **You have still not read the fourteen paragraphs.** They are in the staged file,
and changing anything means re-running `admit.py --accept --all`.

---

## ⛔ G2 · Three of the "thirteen" were my own regex truncating on a hyphen

My first census said 13 missing Admin objects. `domain.yaml`'s roster said **9**. `budget-line`,
`compliance-obligation` and `employee-record` were all authored; my pattern stopped at the `-`.

> **The roster is the authoritative list. A grep is not.** Same lesson as `no_model_wired`,
> the graph-revision guard, `invention_ok` and `index.py` — the fifth this session.

**And every one of the 9 was already defined by exclusion**, by objects that pointed at it:

| object | what the corpus had already decided |
|---|---|
| `delegate` | *"NOT the delegate. The covering person and the delegation instrument are…"* — `approver.yaml` |
| `service_level` | *"the request holds the clock; the service level sets it"* — `request.yaml` |
| `purchase_order` | *"the invoice arrives long after the money was committed"* — `invoice.yaml` |
| `facility` | *"hybrid working broke most registers"* — `asset.yaml` |
| `itinerary` | *"the trip survives the itinerary being rewritten mid-journey"* — `trip.yaml` |
| `admin_risk` | *"a probability and an impact; an obligation is a duty that exists whether or not anyone has assessed it"* — `compliance-obligation.yaml` |

Authoring them invented almost nothing. It wrote down what nine files already implied.

## ⛔ And authoring them found a defect NOTHING checked

I invented six `owner_capability` ids — `risk_administration`, `audit_readiness`,
`travel_coordination` and three more. **The validator reported zero errors on all six.** It surfaced
only because the load-set wiring could not find the capability.

> An object id at least produces a *"planned but not authored yet"* warning. A dangling
> `owner_capability` produced **nothing at all** — and it decides whose review covers the object.

`_tools/validate.py` now errors on it, and a test proves the error fires.

⛔ **All nine are `core.optional`, never `required`.** They are `draft` and unreviewed; a `required`
entry makes a compile NEED one, and every `objects.yaml` defines `optional` as *"absence lowers
confidence rather than blocking"*. A draft object must never block an answer somebody is waiting on.

---

## ⛔ G4 · Support's were worse: eleven were REQUIRED

Admin's nine were cross-references that blocked nothing. Support's were in **load-sets**:
`support_agent` required by 6 capabilities, `queue`/`intent`/`resolution` by 3 each. Those compiles
could not have run.

13 authored (12 on the roster plus `stakeholder`, which the `core_objects` roster listed separately).
⛔ **`customer_support.obj.core.stakeholder` has `referenced_by: 0`** — the only one of the 22 that
closed a *declaration* rather than a reference, and its own header says so, because an object nothing
references is one edit from being the defect this programme has found nine times.

Support stays **on hold**. An object activates nothing.

---

## ⛔ G3 · The ceremony reached two layers and skipped the two with the most files

```
capabilities   155   stable + approved + hash-accepted
objects         75 → 88   66 draft, ZERO with an admission hash
heuristics     283        218 draft, ZERO with an admission hash
```

**And `heuristics/` is where `reads:` lives** — the declaration of what a piece of doctrine consults.
The widest surface in the corpus is the one where somebody can change what the expertise looks at
with nothing noticing.

`artifact_admission_reason` asks the same three questions the other two ceremonies ask, and the
counts reach `ExpertisePackage.metadata` as `unreviewed_object_ids` / `unreviewed_artifact_ids`.

⛔ **It COUNTS, it does not GATE.** Refusing 284 documents in one step on a corpus whose capabilities
all pass is not a measurement, it is an outage. `card_source` wrote the rule for the other cutover
here: measure both paths on one sweep before retiring either. A test fails the day somebody turns it
into a refusal without removing that test.

---

## ⛔ G5 · Half the cases must be refusals, or the corpus gets tuned to answer everything

`Domain Expertise/_eval/` — 18 cases across three domains, and **10 of them expect `abstain`**.

> A case expecting `abstain` that resolves is a **worse** failure than the reverse. The first ships
> an instruction nobody could justify; the second stays quiet.

What it asserts that nothing asserted before:

| | |
|---|---|
| the five `unrouted_l2_types` stay unbound | if one starts resolving, a route was widened past its subject |
| a hint naming no corpus refuses on the **hint** | `unknown_domain_hint`, not `no_situation_binds_type` — different people fix them |
| no `draft` situation anywhere may instruct | over the whole corpus, so a new draft cannot acquire authority by being added later |
| **a deferral is structural, not a label** | ⛔ `deferrals.yaml` CLAIMS the capability appears in no route and its situations are suppressed. That is a claim about the generator and **nothing checked it** |
| `why` is mandatory on every case | a case with no reason is a regression test for current behaviour, not an assertion about correct behaviour |

**Deterministic and model-free.** Under the spend limit that is not a limitation — it is the only
evaluation that can run at all.

### ⛔ Two of my own cases were wrong on the first run

`sales.unanswered_email.routes` named a type **Sales does not bind** — I wrote the case from what the
substrate emits rather than from what the corpus binds. Corrected to `opportunity`, with the mistake
recorded in the case.

And `test_every_deferred_capability_is_absent_from_its_generated_map` searched everything before
`routed_l2_types:`, which **includes the `deferred_capabilities:` block** — so it found all 31
deferrals inside the list of deferrals and called each a routing leak. **A crude slice that happens to
fail looks exactly like a real finding**, which is why it is written down.
