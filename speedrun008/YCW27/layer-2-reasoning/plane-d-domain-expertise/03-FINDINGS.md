# Plane D · FINDINGS — the index

> *What a professional knows.* **203 tests.** 7 steps: 6 DONE, 1 WITHDRAWN.
> An index — every finding is recorded in full in the step file or audit named beside it.
> **Date:** 2026-10-01.

---

| | Finding | Full record |
|---|---|---|
| **1** | **A refusal did not say which kind it was.** `NoExpertiseRoute` carried no reason, so four distinct failures were one opaque error | `STEP-01` → `REASONS`, 4 closed, `reason` **required and keyword-only** |
| **2** | ⛔ **The unrouted list was believed hand-kept. `_tools/index.py:205` generates it.** Found by reading the code the comment pointed at rather than the comment | `STEP-02` |
| **3** | ⛔ **A whole unit was specified on a stale comment, then withdrawn.** A corpus comment said, in capitals, *"A situation's status gates nothing."* It was **true when written** — `capability_resolver.situation_admission_reason` had closed the hole since. Measured: all 23 draft situations flagged, **zero** can instruct | `STEP-03-WITHDRAWN` |
| **4** | **Refusals were counted without their dimension.** A total with no (reason × type) breakdown cannot be acted on | `STEP-04` → **a count without its dimension is not a measurement** |
| **5** | **Capabilities had neither a door nor a stated reason for having none.** Customer Support had 7 | `STEP-05` → `deferrals.yaml`, all 7, `blocked_on_l2_type` |
| **6** | **The validator read a human-readable message where a field existed** | `STEP-06` → read the field, never the message |
| **7** | **Five completeness gaps `G1`–`G5`**, including 22 absent core objects (9 Admin, 13 Support) and no evaluation set at all | `STEP-07`, `04-COMPLETENESS-AUDIT.md` → 22 objects authored `status: draft`, `_eval/` with 18 cases of which **10 are `expect: abstain`** |

---

## ⛔ The three mistakes of mine this plane bought, each with a rule

**A grep is not the roster.** A regex that truncated hyphenated ids reported **13** missing Admin
objects when `domain.yaml`'s roster said **9** — `budget-line`, `compliance-obligation` and
`employee-record` were already authored. **The roster is authoritative; a grep is not.**

**I invented six `owner_capability` ids** and the validator reported **zero errors**. It surfaced
only because load-set wiring failed afterwards. The validator now requires `owner_capability` to name
a real capability — a check my own mistake paid for.

**My own tests raced each other.** Two files ran `validate.py` and one edited a real registry.
`registry_staleness()` was extracted as a pure function. **A guard that must modify the corpus in
order to prove it works cannot be trusted in CI, and the fix for a flaky test is never to weaken the
check it guards.**

---

## What is NOT a finding, and must not be read as one

**The expertise is complete.** 155 capabilities, **all admissible**. The remaining gap is 24 `draft`
situations whose cards cannot instruct — which is the **designed** behaviour, not a defect.
Behavioural-adaptive persona and the Company Brain fill from real context only, and 14 Sales failure-mode
paragraphs are awaiting Rohit's read in `PENDING-REVIEW-sales-failure-modes.md`.
