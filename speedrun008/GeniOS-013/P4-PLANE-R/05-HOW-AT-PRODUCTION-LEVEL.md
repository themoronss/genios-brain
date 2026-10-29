# P4 · Plane R · 05 · How it will be done at production level

**Owner:** Harsh and the agents Harsh assigns for the code. The founder (or a named reviewer) for the patterns. Rohit approves each tenant's activation.
**Rule:** each step first passes in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)).

---

## 1 · One reasoning path

- **One judge on pages.** The product's L2 pass (`reason/l2/`) becomes the only judge, judging **pages**: the saved situation page plus only what is new (P2). It keeps the expert prompt's checklist order, the depth plan, the tool gateway, and "the playbook is a prior". It drops "never say something is absent" in favour of the coverage-aware rule.
- **The 23 units stop deciding.** Their arithmetic moves into the tool gateway as evidence (L2-H1, as already planned). Their scores stop deciding cards once the compiled lane is retired for a tenant (P1 §4).
- **One goal judge**, `reason/l2/goal_judge.py`. It takes the same frame, with the goal page's schema.
- **One analyse pass,** weekly, on the batch API.

## 2 · The pattern library

- **Where:** `Domain Expertise/_reasoning/patterns/` (or `Plane R/` beside it), one YAML per pattern, in the same schema as Plane D's rules of thumb.
- **How it's loaded:** compiled into the same `expertise_items` index (P3 §1), with `plane = 'R'`.
- **How it's chosen:** by the same selection as Plane D, by a situation's kind, stage and events.
- **Review** is the same workflow as Plane D (P3 §4). Patterns not yet reviewed are labelled.

## 3 · Prompts are generated, never hand-written

`reason/l2/prompt.py` builds each prompt from:
- the role;
- the order of judging;
- the precedence (D-P4-2);
- the selected patterns and expertise, rendered whole (P3 §2);
- the calculators' output;
- the dossier.

**A CI test refuses a prompt module that contains rule text** not taken from the library.

## 4 · The answer's shape and the API's limits

- Every answer schema (situation page, goal page) is **probed against the API's compiled-grammar limit in CI**. A failed probe costs nothing; a passing one costs under a cent.
- A schema change that doesn't compile fails the build, not the tenant's sweep. That is what happened to the notebook's first full judge on 29 Oct: 12 of 12 calls refused.

## 5 · Citations and checks run before anything is kept

- The checks of P4-5 are part of admission (P2 §2).
- Each check has its tests and a mutation proof.
- A page whose cited pattern's conditions fail has that conclusion held with the reason. The rest of the page is kept.

## 6 · Company patterns

- The weekly analyse pass writes the company's own patterns: usual reply times per counterparty, which moves led to outcomes, how long each stage really takes here. They are stored in L3 with their n and dates (P2).
- They are printed as "yours" beside the playbook's prior, as the expert dossier already does for stage durations.
- They connect to L6's existing brains (`packs/brains/behavior_distill.py`, `adaptive_lease.py`). Those are the supply side; the driver is `feedback/brain_pipeline`.
- **A company pattern never overrides the founder's word**, and never crosses tenants.

## 7 · Model policy

- **A per-tenant row** sets the model and its thinking setting for each site: situation judge, goal judge, analyse, placement.
- **The default is production parity**, claude-sonnet-5 with thinking off.
- **A stronger model is used only after it beats the default on the acceptance set**, with its cost measured.
- **Every model call is registered** in `reason/llm_sites.py`, with its budget.

## 8 · Monitoring

**Per pattern and per week:**
- times selected;
- times cited;
- times its conditions failed the check;
- the founder's verdicts on the cards that rested on it.

**Per judge:**
- pages admitted;
- changes held, by reason;
- cost;
- depth used.

The daily health report (P1 §5) shows the judge's line.

## 9 · What must never happen

- **Rule text in a prompt** that isn't in the library.
- **A number on a page with no tool or quote behind it.**
- **A rule used where its own conditions say it doesn't apply.**
- **"Unknown" written as zero.**
- **A schema change shipped without its grammar probe.**
