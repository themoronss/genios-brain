# P3 · Plane D · 03 · What's expected, and what's happening

**Expected** comes from four references, and from Rohit's own design rules:
- **the Design Atlas v2** (GeniOS-008 `00-ARCHITECTURE.md`): "L2 · D · Plane D", the storage map, and Part IV on Admin;
- **the ideal dashboard:** its Expertise and Brain pages, and the trace on every card;
- **the expected outcomes:** the acceptance set ([10](../10-ACCEPTANCE.md));
- **the launch film** ([09](../09-WHAT-WHY-HOW.md));
- **Rohit's rules:** the Founder Office's question, "How would a seasoned chief of staff to a founder read this situation?", and "reviewed by that founder line by line" (`06` D45).

**Happening** is measured in [01](01-WHATS-EXACTLY-THERE.md). The failure numbers are [02](02-WHATS-FAILING-AND-WHY.md)'s; the steps are [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)'s; the full specification is [07](07-THE-PLANE-D-SPEC.md).

---

## 1 · The Atlas v2

| # | Expected | Happening | Failure | Fixed by |
|---|---|---|---|---|
| 1 | **Plane D knows; it never reasons, decides or chooses** | ✅ No model runs in `packs/compiler/`; the compiler "never decides" | — | kept (07 §0) |
| 2 | **One meta-schema for every domain,** so a new domain is content, not code | ✅ The same tree and schemas for all four domains. 🟡 The schema lacks the D-Unit's fields | F12 | P3-11 |
| 3 | **Every unit carries the D-Unit contract:** applies when, not when, counter-patterns, facts required, derivation, expected state, evidence requirements, relationships, reasoning bindings, provenance, review with content hash, evaluation cases | 🟡 Statement, why, prose conditions, failure modes, limits, references and version are there. Conditions code can check, facts required, evidence requirements, authority boundary and cases are not | F12 | P3-11 |
| 4 | **Thirteen kinds of unit,** typed and related | 🟡 Eight kinds of file (rules of thumb, playbooks, situations, objects, models, rules, mental models, decision frameworks). No typed relationships between units | F12 | P3-11 (07 §1.2) |
| 5 | **The Domain Compiler builds a bounded ExpertisePackage for every situation,** in nine stages, mostly lookups | 🟡 Built, and it made 100 packages in the first week. But only for the compiled lane, which renders templates. The model's paths never receive one | F8 | P3-1, P3-7 |
| 6 | **The package says what was skipped and why** | ✅ In the compiled lane: skipped, missing and unreviewed ids are in each package's metadata | — | kept, carried to the model (P3-2) |
| 7 | **The package carries expected states, evidence requirements, the outcome definition, reasoning bindings and the authority boundary** | ❌ Not package fields today | F12 | P3-11, P3-7 |
| 8 | **Four brains behind every package, with a fixed precedence** (law and safety → organisation policy → explicit authority → active constraint → domain expertise → observed behaviour → generic heuristic) | ❌ 0 organisation, behaviour or adaptive entries in all 100 packages | F14 | P3-16 (with P2 §8, L6) |
| 9 | **Only reviewed knowledge instructs;** a draft situation's card becomes an observation | 🟡 Gated for capabilities and situations; only reported for rules of thumb, playbooks and objects. 165 approved units never switched on | F11 | P3-12 |
| 10 | **A rule of thumb has a version, a hash, a reviewer, tests, a shadow run and a rollback** | 🟡 A version, yes. A reviewer on 145 of 291. No hash, no tests, no shadow, no rollback | F11, F15 | P3-12, P3-6, P3-13 |
| 11 | **The 19-item maturity checklist decides what a capability may do** (Draft, Shadow, Reliable, Senior-grade) | ⬜ Not scored | — | P3-14 |
| 12 | **The six tests of proper expertise:** recognition, discrimination, explanation, projection, exception awareness, decision usefulness | ⬜ Not shown for any capability | F15 | P3-14, P3-6 |
| 13 | **Each domain is live, shadow or off per tenant;** an off domain gives facts, never judgment | 🟡 On or off per tenant (`l3_activation`). No shadow state in the row | — | P3-17 |
| 14 | **Every fact path a unit names has a writer, and every path has a consumer** | 🟡 68 of 141 fact paths are named by no unit | F12 | P3-11 |
| 15 | **Learning never writes the Expert brain;** L6 may only suggest an edit | ✅ By design (git, human review). Nothing reaches the review queue from feedback yet | F16 | P3-18 |

## 2 · The ideal dashboard

| # | Expected | Happening | Failure | Fixed by |
|---|---|---|---|---|
| 16 | **"Plane D is what an expert knows; Plane R is how to think. L2 uses both on every run"** | ❌ 0 of 138 L2 judgments and 0 of 50 expert reviews got any expertise | F8, F9 | P3-7, P3-8 |
| 17 | **Every card's trace names its domain path, its situation, the expertise package it used and the reasoning units that ran or declined** | 🟡 Compiled-lane cards have packages; the model's cards have none to name | F8 | P3-7, P3-15 |
| 18 | **The founder's office lives inside Admin** ("Admin › Founder office › investor relations"; Admin counted as 65 capabilities and 36 situations) | 🟡 A separate domain since 9 Oct (D2), switched on by hand. The ideal's counts are Admin plus Founder Office | — | D-P3-5 |
| 19 | **"Only stable, approved situations instruct L2"** | 🟡 True for the compiled lane. 5 situations sit in the half-state | F11 | P3-12 |
| 20 | **The 14 situations its cards and Expertise page name exist** | 🟡 9 exist: 7 live, `obligation_falls_due` in the half-state, `live_investor_relationship` unreviewed. **5 are missing:** application deadline, conditional deferral, wave gone silent, information conflict, delivery failure | F13 | P3-10 |
| 21 | **The rules its cards cite exist, one unit each** | 🟡 8 exist. 4 live only inside other units. **4 are missing:** one number, everywhere; investors compare updates; prepare one number, one story, one ask; a dormant thread reopens with news | F13 | P3-10 |
| 22 | **The Expertise page shows the capabilities used on your mail, the situations recognised and the rules used on your cards** | ⬜ Nothing records use | F16 | P3-15, P3-20 |
| 23 | **The Brain page keeps four brains apart:** Expert (git, human-reviewed, never written at runtime), Organisation (changed only by the founder), Behaviour (counted, promoted only on enough evidence), Adaptive (every entry expires); Persona is a profile, not a fifth brain | 🟡 Expert: ✅ in git. The other three: empty (storage is P2 §8) | F14 | P3-16 |
| 24 | **Locked domains show what they would unlock,** and can be requested | 🟡 Activation rows exist; Marketing, Product and Projects have no corpus | — | P3-17, D-P3-10 |

## 3 · The expected outcomes (acceptance set)

| # | Card | The call it needs | What Plane D must give it | Happening | Failure | Fixed by |
|---|---|---|---|---|---|---|
| 25 | `i3` | The follow-up after an investor call was never sent: send it today | "Before an investor call" step 6, "write the same day"; "silence reads by stage" **with** its condition "the turn is theirs" | ❌ The playbook's "silence = soft no" won | F2, F3 | P3-2 |
| 26 | `b2` | Two partner calls, no written next step: send the collaboration note | Admin's "meeting without follow-through" | ❌ Marked "done"; the knowledge never reached the model | F1, F9 | P3-1, P3-7, P3-8 |
| 27 | `c2` | A tool subscription renews within the week: keep or downgrade, ask for credits | Admin's renewal management: "the real deadline is the notice date" | ❌ Filed as noise | F1, F10 | P3-1, P3-9 |
| 28 | `i1` | One update with a new, checkable fact, then stop | The conditional deferral; "a pass is a date, not a verdict"; "investors do not chase"; "an update must carry a new fact" | ↔️ The opposite call in the notebook. The situation is missing; the last rule lives only inside a playbook | F13 | P3-10 |
| 29 | `f2` | Finish the application, or drop it, this week | An application-deadline situation; "the deadline is the only fixed point"; "work back from the deadline" | ✅ in the notebook, without a situation type | F13 | P3-10 |
| 30 | `p1` | Pick one verified traction number | An information-conflict situation; "one number, everywhere" | ✅ in the notebook, without the knowledge | F13 | P3-10 |
| 31 | `i5` | Resend to working addresses | A delivery-failure situation; "a complaint that bounced was not made" | ◐ Partly | F13 | P3-10 |
| 32 | `b1`, `b3`, `f3`, `h1` | Introductions, a stalled intro, a silent referral, an offer | Introductions and hiring knowledge | Stubs | F4 | P3-3 |
| 33 | all | **A step that makes any line worse is not done** | Every unit has cases where it must speak and must stay silent | Only routing cases | F15 | P3-6 |

## 4 · The launch film

| # | Expected | Happening | Failure | Fixed by |
|---|---|---|---|---|
| 34 | **"Domain expertise" for "every department, every departmental goal, every situation"** (Admin, Sales, Finance, Support, Projects, Hiring) | Admin, Sales and Support are deep but generic. Founder Office covers 2 of its 6 kinds. Finance exists only as Admin's finance administration group. Projects, Marketing and Product have no domain. Hiring is a stub | F4 | P3-3, D-P3-10 |
| 35 | **"Without hundreds of prompts"** | ✅ Plane D lives in reviewed YAML, not in prompts. The prompt copies that hold rules are P4's | — | kept |
| 36 | **"A 24/7 consultant for our company, which says: do this instead of that"** for *this* company | ❌ With empty brains, the knowledge is generic consulting advice | F14 | P3-16 |
| 37 | **"Company patterns, domain expertise, reasoning patterns, and the current status of your company"**, combined on every situation | ❌ Domain expertise never reaches the judgment; company patterns are empty | F8, F14 | P3-7, P3-16 |

## 5 · Rohit's rules

| # | Expected | Happening | Failure | Fixed by |
|---|---|---|---|---|
| 38 | **"How would a seasoned chief of staff to a founder read this situation?"** | ✅ The Founder Office's question; its two authored capabilities answer it well | — | kept |
| 39 | **"Reviewed by that founder line by line"** (`06` D45) | ❌ Founder Office: 0 of 29 units reviewed; never scheduled | F5 | P3-4 |
| 40 | **Knowledge that is right** | 🟡 Mostly right and sourced. Two older Admin rules made wrong cards | F6 | P3-5 |
| 41 | **Measured: each piece of knowledge proves itself** | ⬜ No measurement per unit | F16 | P3-15 |

## 6 · Found by the requirements check (29 Oct)

The independent check of P3 against the four references ([08](08-REQUIREMENTS-TRACE.md)) added these:

| # | Reference | Expected | Happening | Failure | Fixed by |
|---|---|---|---|---|---|
| 42 | Atlas | **A package is never wider than its situation's audience** | ⬜ Not stated; today's compiler drops narrower brain entries, but nothing requires it | — | P3-7 (D-13) |
| 43 | Atlas | **Plane D reads no clock;** a run replays with the same labels | ⬜ "Due for review" would be judged by the wall clock | — | P3-7 (D-15) |
| 44 | Atlas | **No package, no domain judgment:** the card is an investigation or observation, never a recommendation | ❌ The package contract refuses an empty package | F8 | P3-7, P3-2 |
| 45 | Ideal | **Goals are reasoned with Plane D's rules,** and their plans follow the stage ladders | ⬜ No goal package | — | P3-7 (07 §4.4), P3-3 |
| 46 | Ideal | **Categories and display paths** ("Admin › Founder office"; eight categories) come from Plane D | ⬜ | — | P3-1, P3-20 |
| 47 | Ideal | **The person's confirmed preferences** reach the moves (Persona, not a fifth brain) | ⬜ | F14 | P3-16 |
| 48 | Expected | **Each ideal case fits its situation** | ❌ Several existing situations cannot describe the ideal's case | F17 | P3-10 (qualifiers) |
| 49 | Film | **Every departmental goal:** a roadmap of departments, and knowledge for their goals | ⬜ | F4 | D-P3-10, P3-23, P3-21, P3-7 |
| 50 | Film | **Your data stays with you:** learning across companies is opt-in and redacted | ⬜ | — | P3-18 (D-P3-13) |

---

## Where the knowledge is already strong

The investor and programme playbooks and their ten rules of thumb are the knowledge the ideal dashboard was written from:
- the stages with typical durations, each a labelled prior with its source;
- what quiet means at each stage;
- the moves step by step;
- the conditions and failure modes of each rule.

Admin's approved items for follow-ups, renewals, filings, commitments and correspondence say what several missed cards needed.

The Domain Compiler already selects several capabilities per situation, carries what it skipped and why, and pins its snapshots.

**None of this needs rewriting.** It needs to arrive whole, at the model, with its conditions, reviewed, tested and measured.
