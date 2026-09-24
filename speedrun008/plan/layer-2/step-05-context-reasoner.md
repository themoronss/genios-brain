# L2-5 · The Context Reasoner — a new R-SITE, not a new gate

⛔ **CORRECTED by the pre-flight pass.** This step used to say *"the one new model site, metered,
its own prompt version, its own cache key."* **That would have built a second gate.**

`reason/llm_sites.py`:

> **"THERE IS EXACTLY ONE C5 GATE, AND IT IS `reason/bundle/gate.RSiteGate`. This module does not
> re-implement activation, budget, retry or receipting; it delegates all four, so a tenant's spend
> is one number measured against one ledger."**

`reason/bundle/gate.py`: **"no R-site may call a model directly."** `consult` runs seven steps —
activation · precondition · budget (else a deterministic template) · cache · tier and timeout ·
**the caller's validator** · deterministic fallback, every one recorded.

**So the Context Reasoner registers as an R-site. It does not build metering, caching, budget or
fallback — all four exist, behind one door, with a property test.**

### And R-1 already holds the contract this site needs

`reason/interpretation.py`:

> *"The model returns `{classification, confidence_bp}` **as evidence**; a unit reads it like any
> other input; **the formula decides**. The model never says 'this is urgent.'"*
>
> *"IT RUNS BEFORE THE UNITS, NOT INSIDE THEM... the model's output is an input to a deterministic
> computation, **which is the only shape in which a model may participate in a decision at all**."*
>
> ⛔ *"**IT CANNOT RAISE CONFIDENCE.**"*

**"Cannot raise confidence" is stronger than anything this plan wrote. Copy it verbatim.**

And R-1 *"has never fired on the pilot tenant"* — the third thing in this engine built correctly and
never switched on.

---

# The original step follows, with its units corrected

**Needs Harsh:** cost check needs the pilot's situation count · **Migration:** none

---

## 1. Premise — this is the missing half

Everything before this step prepares an input. Nothing before this step *reads* it.

```
candidate + ExpertisePackage + slice + goals   ──→  ??? ──→  interpretation
                                                    ⛔ nothing here today
```

`context/angles/__init__.py` states what the layer is today:

> *"Layer 2 is a rule engine that looks like a model. Nine of its correlators call none, its
> situation assembly calls none, and of the four model sites in the layer three never execute on a
> sweep."*

And `support_situations` prices it: **"that costs recall, and buys replayability."**

⛔ **This step spends part of that price deliberately.** The assembly stays deterministic and
replayable. The *interpretation* becomes model work, and is labelled as interpretation everywhere it
appears — which is what L2-2's three-way split exists to make possible.

---

## 2. ⛔ The cost law: the call goes on the SITUATION, not the event

```
L1 `extract`      per event      465 threads → 465 calls
L2 reasoning      per situation  same month  → ~40 calls
```

**A 10× difference for free, from where the call is attached.** Decide this before choosing a model.

| | |
|---|---|
| unit | **one call per situation** |
| tier | **Haiku** default · Sonnet only on escalation |
| input | the slice — ~900 tokens, not the thread's 10,000 |
| output | **structured, not prose** — fewer output tokens and a parseable result |

### The escalation rule — two numbers, no guessing

```
                    IMPORTANCE
              low          high
           ┌──────────┬───────────┐
 conf high │ accept   │ accept    │
           ├──────────┼───────────┤
 conf low  │ UNKNOWN  │ SONNET    │
           │ (do not  │ (escalate)│
           │  spend)  │           │
           └──────────┴───────────┘
```

⛔ **Low confidence + low importance = `unknown`, and do not ask again.** The largest saving in the
plan, and the most honest answer available.

---

## 3. What the reasoner may and may not emit

| may write | may never write |
|---|---|
| `inferred_state` | `observed_facts` |
| `hypotheses` (with confidence) | `evidence` |
| `implications` | any fact in the Evidence Graph |
| `unknowns` | its own `evidence_ref` — it cites, it does not mint |

**It proposes. It does not commit.** L2-6 commits.

---

## 4. Units

### L2-5-U0 · ⛔ The cost check, before the prompt is written
Situations per sweep on the pilot, by type × slice weight from L2-3-U0 × Haiku rate. **Every L1 step
did this first and it changed the plan twice.** Writing the prompt before the number is how a per-
event call gets shipped by accident.

**Blocked on Harsh** for the situation count. The slice weight is already measured.

### L2-5-U1 · The prompt — structured output, its own version
Its own `prompt_version`, its own `schema_version`, its own cache key. **Not folded into L1's
extraction key** — a change here must not invalidate every extraction in the corpus.

### L2-5-U2 · ⛔ Register the site — do not build a gate
Declare the reasoner as an R-site with **its precondition** (step 2 of `consult`: *"the SITE's own,
never 'just in case'"*) and **its validator** (step 6). Activation, budget, cache, tier, timeout and
deterministic fallback come from the gate.

**A parallel gate would split the tenant's spend across two ledgers — the one thing `llm_sites.py`
says it exists to prevent.**

```
verify:  pytest tests/test_every_llm_call_site_is_metered.py -q
```

### L2-5-U3 · Escalation, on the two numbers
Haiku runs first. Low confidence **and** high importance escalates once. Low + low writes `unknown`
and stops.

```
verify:  pytest tests/reason/test_escalation_spends_only_where_it_should.py -q
```

### L2-5-U4 · The cache key — supplied to the gate, not implemented
The gate caches on *"decision hash / fact digest"*. **The reasoner supplies a slice digest** and the
gate does the rest. R-1 is keyed on a fact digest for the same reason and has no decision at all.

### L2-5-U5 · Refusal is a valid answer
A reasoner that cannot conclude must be able to say so and have that recorded. **`unknown` is a
result, not a failure**, and the gate must accept it.

---

## 5. What this step does NOT do

* **It does not assemble situations.** The nine correlators and seven producers are untouched; the
  reasoner reads what they built.
* **It does not become a fifth angle.** Different site, different contract, different queue.
* **It does not write to the graph.** L2-6 validates, then L2-7 writes.
* **It does not run per event.** If it ever does, the cost check was ignored.

---

## 6. Completion criteria

1. Cost check done **before** the prompt, with real situation counts, written into findings.
2. ⛔ **Registered as an R-site behind `RSiteGate`** — zero new metering, caching or budget code.
3. Haiku default, one escalation path, and low+low producing `unknown` without a call.
4. Structured output only — the parser refuses prose.
5. The reasoner **cannot** write `observed_facts` or `evidence`, proven by a test that tries.
6. ⛔ **It cannot raise a confidence** — R-1's rule, carried over and tested the same way.
