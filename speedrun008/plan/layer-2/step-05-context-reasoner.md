# L2-5 · The Context Reasoner — the one new model site

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

### L2-5-U2 · The call site, metered
A new `purpose` beside `extract`, `relevance_gate`, `l4_bundle`, `l5_render`. **Metered from the
first line** — `tests/test_every_llm_call_site_is_metered.py` fails in both directions, and it
should.

```
verify:  pytest tests/test_every_llm_call_site_is_metered.py -q
```

### L2-5-U3 · Escalation, on the two numbers
Haiku runs first. Low confidence **and** high importance escalates once. Low + low writes `unknown`
and stops.

```
verify:  pytest tests/reason/test_escalation_spends_only_where_it_should.py -q
```

### L2-5-U4 · The replay cache
Same slice + same prompt version + same model = same answer, no second call. The key must include
the **slice hash**, because a slice that moved is a different question.

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
2. One metered call site, its own version, its own cache key including the slice hash.
3. Haiku default, one escalation path, and low+low producing `unknown` without a call.
4. Structured output only — the parser refuses prose.
5. The reasoner **cannot** write `observed_facts` or `evidence`, proven by a test that tries.
