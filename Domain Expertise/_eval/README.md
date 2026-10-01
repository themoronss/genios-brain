# `_eval/` — the cases this corpus is allowed to be judged on

⛔ **WHY THIS EXISTS.** Before it, *"the expertise is correct"* was a claim with nothing under it. The
corpus validates (0 errors), every capability is admitted, every object is authored and reachable —
and **none of that is evidence that the expertise gives the right answer.** A schema check proves a
file is well-formed. It cannot prove a situation routes to the capability a professional would
consult, or that an unreviewed one declines to instruct.

## ⛔ Half the cases are MUST-ABSTAIN, and that is the point

A corpus evaluated only on cases it should answer will be tuned until it answers everything. The
expensive failures in this product are not wrong answers — they are **confident answers to questions
the evidence could not settle**, which is the failure the abstention vocabulary, the admission
ceremony and the `unrouted_l2_types` census all exist to prevent.

So every case declares one of two expectations:

| `expect` | meaning |
|---|---|
| `resolve` | this situation MUST reach the named capability |
| `abstain` | this situation MUST NOT produce an instruction, and the named reason is why |

A case with `expect: abstain` that resolves is a **worse** failure than one with `expect: resolve`
that abstains. The first ships an instruction nobody could justify; the second stays quiet.

## What a case is

```yaml
- id: admin.reply_owed.routes
  situation_type: reply_owed        # what Layer 2 emits
  domain_hints: [admin]
  expect: resolve
  capability: admin.executive_support.inbox_and_correspondence
  why: >
    One sentence. Why a professional would consult this capability, in the words of somebody who
    would have to defend the answer.
```

⛔ **`why` is mandatory on every case, including the abstentions.** A case with no stated reason is a
regression test for current behaviour rather than an assertion about correct behaviour, and the two
diverge the first time current behaviour is wrong.

## What runs it

`tests/packs/test_the_corpus_answers_its_own_cases.py`. **Deterministic and model-free** — every case
is decided by the routing resolver and the admission gates, which is what makes the corpus's
correctness checkable at all today. Cases needing a model to judge belong in a separate file when
there is one, and putting them here would make this suite unrunnable under the spend limit.

## ⛔ What this is NOT

**Not a benchmark.** Twenty-odd cases over 155 capabilities is a floor, not coverage. It is the set
of claims somebody was willing to write down and be wrong about, and it grows one case at a time,
each one added because something was got wrong once.
