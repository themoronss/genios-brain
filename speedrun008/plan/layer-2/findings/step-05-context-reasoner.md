# L2-5 · The Context Reasoner — findings

**Run:** 2026-09-24 · **cost check ran BEFORE the prompt** · migration **0183**
**Against:** `speedrun008` @ `96cdb4fb`
**Result:** 35 tests, **13,080 passed · 14 failed (all pre-existing) · 0 regressions**

---

## 1. ⛔ The cost check ran first and corrected the plan twice

U0: *"Every L1 step did this first and it changed the plan twice. Writing the prompt before the
number is how a per-event call gets shipped by accident."* It also said **blocked on Harsh** for
the situation count.

**It was not blocked.** `situation_bso.l1_refusal` records the number: **159 active situations on
the pilot.** The slice weight was measured in L2-3. Both halves existed.

| | |
|---|---|
| situations | **159** (the plan says *"~40"*) |
| slice p50 / p90 | 1,279 / 4,934 tokens |
| output ceiling | 400 |

```
all Haiku,  p50 slice        $0.52 / sweep      ~$15.64 / month, daily
all Sonnet, p50 slice        $1.04 / sweep      2×
per EVENT   (465 calls)      $1.52 / sweep
per SITUATION (159 calls)    $0.52 / sweep      → 2.9× fewer
```

### 1.1 · ⛔ The plan claims a 10× saving. It is 2.9×.

§2: *"L1 extract per event 465 threads → 465 calls / L2 reasoning per situation, same month →
~40 calls. **A 10× difference for free.**"* The pilot carries **159**, not ~40. The law is right —
**attach the call to the situation** — and the number is 2.9×.

### 1.2 · ⛔ And *"the largest saving in the plan"* is about $3 a month

§2 calls low-confidence + low-importance → `unknown` **the largest saving in the plan**. At the
measured shape it saves **$0.10 a sweep.**

**The rule is still right, and for a reason the plan does not give.** It is a **quality** rule: a
low-confidence reading of a low-importance situation is a wrong answer nobody needed, and a wrong
card costs more than no card. L1 wrote the same sentence about promises — *"telling a founder they
broke a promise they kept is the failure that loses trust rather than quality."*

**Saying this out loud is what stops the next person defending the rule with a number that does
not exist.**

---

## 2. It registers as a site and builds nothing the gate already has

`reason/llm_sites.py`: *"THERE IS EXACTLY ONE C5 GATE… a parallel gate would split the tenant's
spend across two ledgers."*

| the site supplies | the gate supplies |
|---|---|
| a precondition | activation · budget · cache · tier · timeout · retry · deterministic fallback · the receipt |
| a prompt with its own `PROMPT_VERSION` | |
| a **slice-digest seed** the gate keys on | |
| a validator — **L2-6's, not a second one** | |

Proven by AST rather than by grep: the module names `run_site` and reaches for no
`NarrativeBudget`, `record_call`, `RSiteGate`, `cache_key` or client.

### 2.1 · R-1's law, copied verbatim

> ⛔ *"**IT CANNOT RAISE CONFIDENCE.**"*

`clamp_confidence` returns `min(proposed, current)`, and `None` when nobody measured — **a model
does not get to be the first.** And the fallback is **silence**, never a neutral reading: *"a
default reading would be a fact the model never stated, injected into the evidence layer where the
formula would weigh it."*

---

## 3. ⛔ The topology test moved the module, and the pre-flight had already said so

The first draft put it in `context/`:

```
genios_engine/context/situation_reasoner.py (layer 2) imports genios_engine.reason (layer 4)
— upward
```

**A lower layer may never import a higher one**, and the whole R-site apparatus is Plane R. The
pre-flight correction had already said the right thing — *"step-05 must register an R-site behind
`RSiteGate`"* — and the first draft did not follow it. **An R-site lives where R-sites live.**

---

## 4. The debts L2-2 and L2-3 deferred here, paid — and the shape changed

### 4.1 · L2-2's four fields

`hypotheses` · `implications` · `reasoning_trace` · `valid_until`, on v2, **because
`proposal_gate` validates against `FIELD_CLAIMS` and a model cannot propose a field the contract
does not have.**

⛔ **`hypotheses` is the only field in `ClaimState.HYPOTHESISED`.** L2-2 created that state and
nothing held one, which made it decorative. This is what makes the third claim state real.

And two of the four are **`ENVELOPE` — a model may write neither**:

| field | why a model may not write it |
|---|---|
| `reasoning_trace` | **the gate mints it.** `EvidenceSpan.verified` records what self-set receipts cost: *"the moment another caller can set that flag, it stops meaning 'checked'"* |
| `valid_until` | L2-2's own table put it under the gate. A model that could set it could make its own reading immortal |

### 4.2 · ⛔ The home is a table, not four columns — and measuring is why

L2-2 assumed four columns on `context_situations`. **Measured before building: the v2 object is
never persisted as a row.** `publish_situation` returns it in memory; only the admission *receipt*
is stored.

And an interpretation has its own lifecycle:

* it **expires** while the situation does not;
* it is re-made every sweep, so there are **many readings of one situation over time**;
* **a column would keep the latest and lose the history** — which is exactly what *"why did GeniOS
  say that last Tuesday"* needs.

So `situation_interpretations` (migration 0183), beside `situation_admission_decisions` — the same
pattern for the same reason.

### 4.3 · And it pays L2-3's debt in the same table

> *"The hash is stored, the slice is not. A hash proves sameness and cannot reproduce the input —
> a fingerprint, not a record."*

`context_slice jsonb` holds the bytes the reading was made from, so `reasoning_trace` points at a
conclusion whose premises are **still there**. Its only reader is a reasoner trace, which is why it
waited for this step rather than shipping empty in L2-3.

---

## 5. ⛔ Four guards caught this build, and every one was right

| guard | what it caught |
|---|---|
| `test_import_direction` | the module was in the wrong layer — §3 |
| `test_every_org_scoped_table_has_a_proven_account_delete_cascade` | `situation_interpretations` had **no schema-enforced path to `orgs`**. An org-scoped table without one survives an account erasure, which is a promise this product makes |
| `test_the_five_features_are_the_plans_five_in_wave_order` | the feature had a **wave and no `EFFECTS` or `PRECONDITIONS` row** — *"a feature an operator can switch on and nobody can describe is a switch with no meaning"* |
| `test_the_tiers_are_the_ones_doc_11_budgeted` | it asserted `tier_for("R-6")` **raises** — R-6 was literally the example of an unbudgeted site. Re-aimed at `R-99` and **strengthened** with R-6's real tier |

**And one of my own tests was widened rather than weakened**: L2-6 asserted every
`RECEIPT_REQUIRED` field is `INFERRED`, which was true only while `HYPOTHESISED` had no members.
The true claim — *a receipt is owed by an interpretation and never demanded of an observation* —
now covers both interpreting states.

---

## 6. The wire, end to end

```
shadow_compile            one gate per sweep (make_gate, as R-1 builds its own)
   ↓                      situation + slice both in hand — the only such point
next_step(conf, imp)      the quadrant. UNKNOWN spends nothing
   ↓
run_site(R-6)             activation · budget · cache · tier · retry · receipt
   ↓
proposal_gate             six checks, four outcomes — L2-6's, not a second copy
   ↓
record_interpretation     the reading AND its slice, durable, replayable
```

Every arm is counted — `reasoner_unknown`, `reasoner_consulted`, `reasoner_failed` — and **the
consult cannot kill the compile**: a reading is worth less than the sweep. A null client is a
first-class answer: *"plainer cards, never missing ones."*

**It proposes and does not commit.** A test asserts the payload reaches no `write_fact`, no
situation upsert and no `context_situations` update.

---

## 7. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | cost check **before** the prompt, real counts, in findings | ✅ **and not blocked** — the count was already recorded. It corrected the plan twice |
| 2 | registered as an R-site behind `RSiteGate`, zero new metering | ✅ proven by AST · id, tier, ceiling, **and its activation feature with a wave, an effect and a precondition** |
| 3 | Haiku default, one escalation, low+low → `unknown` with no call | ✅ and `None` lands on `unknown`, never on an assumed middle |

**All three closed**, plus both deferred debts, plus the migration and the writer.

---

## 8. What this step does NOT do

* **It does not assemble situations.** The nine correlators and seven producers are untouched.
* **It does not write to the graph.** It proposes; the reading is recorded, not applied.
* **It does not run per event.** One call per situation, and the quadrant may make it zero.
* **It does not switch itself on.** `situation_reasoner` is a per-tenant activation row, and
  without it the sweep runs exactly as it does today.
