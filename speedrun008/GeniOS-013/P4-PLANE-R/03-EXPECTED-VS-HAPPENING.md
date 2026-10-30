# P4 · Plane R · 03 · What's expected, and what's happening

**What is expected, in the sources' own words:**
- **Rohit, 5 Oct:** "a company doesn't run on formulas and rules … it runs on patterns and analytics … use the LLM so GeniOS reasons over the context like a full-time 30-year expert." Code is memory, calculator and checker.
- **Rohit, 6 Oct:** "don't add very rigid rules … keep it sensible … I should get proper intelligent cards."
- **Rohit's L2 spec** (GeniOS-008 `05-SPEC-layer-2.md`): "Company kabhi bhi rules pe kaam nahi karti. Company kaam karti hai patterns pe, history pe, current situations pe, knowledge pe …" (a company never runs on rules; it runs on patterns, history, current situations and knowledge). And: routing must be predictable and auditable, but the content of the reasoning is not predetermined.
- **The Atlas:** "Tools calculate. Units interpret. Humans authorise." The model may describe and propose; code validates; company state commits.
- **The film:** the engine combines "company patterns, domain expertise, reasoning patterns, and the current status of your company", for "every department, every departmental goal, every situation … without hundreds of prompts", and shows the "multidimensional patterns" one person cannot see. "Every Done teaches."
- **The ideal dashboard:** reasoning lines that name the rule they used and its condition ("investors do not chase"), that count ("Counted, not guessed"), and that say "Unknown, not 0" and "Blocked, not late"; a trace per card listing the units that ran and those that declined, and why.

**Key:** ✅ meets it · 🟡 partly · ❌ not at all. "Fixed by" names the step in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md).

## 1 · The Atlas v2

| # | Expected | Product today | Notebook `b2` | Fixed by |
|---|---|---|---|---|
| 1 | **A library of reasoning units:** versioned thinking contracts in six groups; fourteen composites in V1, plus quantitative and trend | ❌ 23 scorers in four categories; the six groups are prompt steps | ❌ One hand-written prompt | P4-1 |
| 2 | **A unit applies reasoning on D-Units, using the evidence,** and names no domain | 🟡 The units bind sales-shaped roles; 2 of 20 declined for Admin on every run | ❌ Domain rules sit in the prompt | P4-1 |
| 3 | **The twelve-step run** | 🟡 3 steps in full, 7 in part, 1 missing (expertise) | 🟡 One pass, no plan | P4-10, P4-11 |
| 4 | **The need classified by rules and tables, never the model** | 🟡 Depth from literals; 0 of 138 runs shallow; 69 of 71 deep only because of an L1 conflict | ❌ | P4-10 |
| 5 | **Dependency-complete plans;** every skipped unit with a receipt | 🟡 Receipts for skipped units in the compiled lane (102); risk still half-blind (43 of 43) | ❌ | P4-10 |
| 6 | **Tools calculate, units interpret** | 🟡 Six tools, printed in every dossier, cited in 85 of 86 results; UTC only | ❌ None shown to the model | P4-3 |
| 7 | **One bounded pass, 0–3 calls;** a targeted second pass only on disputed claims | 🟡 One call and one repair; no second pass; 39% of spend wasted | 🟡 One call per page | P4-13 |
| 8 | **No evidence id, no claim** | ✅ The claim check on every result, line by line; but 66 of 86 held, 52 of them for an id in the wrong form | ✅ Admission change by change | P4-5 |
| 9 | **Confidence computed by units, six dimensions** | ❌ Written by the model; "coverage low" in 73 of 86, measured by nothing | ❌ Cut to fit the API | P4-3 |
| 10 | **Uncertainty picks a lane; it never deletes** | 🟡 `lane_for` by code on the model's words; the card uses the old lane (agrees on 16 of 33) | 🟡 One lane per page, the model's | P4-11 |
| 11 | **One of fourteen outcomes,** and an intervention mode | 🟡 Ten modes; no outcome field | ❌ | P4-11 |
| 12 | **An EvidenceNeed instead of a guess** | 🟡 115 raised, 0 met | ❌ | P4-11 |
| 13 | **Write-back with compare-and-set** | ❌ L2 admission in shadow, no applier | 🟡 Pages written; no compare-and-set | P2 (the door) |
| 14 | **Receipts; replay without the model** | 🟡 A receipt on every row; replay has no caller | 🟡 Runs logged | P4-14 |
| 15 | **The four brains' precedence,** one order | 🟡 "The playbook is a prior" and "follow the founder's correction" as prompt rules; the brains are empty | ❌ "The playbook is more specific" | P4-2 |
| 16 | **No package, no domain judgment: abstain** | ❌ 0 of 138 runs had a package, and nothing abstains | ❌ The playbook printed whole, unselected | P4-8 (RC-10), with P3-7 |
| 17 | **Reasoning across situations;** higher-order situations from shared blockers | ❌ | 🟡 One relate call; 3 "evidence for" links among 296 | P4-7 |
| 18 | **Priority across situations, by code** | ❌ Cards ordered by lane only | ❌ | P5, with P4-3's `g.*` tools |
| 19 | **Attribute first ("wrong because …"), then adapt;** units change only by review | 🟡 11 reasons map to 6 old layers and change nothing | ❌ | P4-15 |
| 20 | **Prediction against actual** | ❌ No prediction stored | ❌ | P4-15 |
| 21 | **The model never scores, ranks, routes, permits or does arithmetic** | ❌ The test-mode decision maker (Haiku) decided all 242 compiled and legacy candidates | 🟡 The model does its own date arithmetic | P4-17, P4-3 |
| 22 | **The ten mechanisms of seniority** (attention, framing, expected against actual, the right questions, patterns, counterexamples, consequences, time windows, reversibility, options) | 🟡 Most are checklist steps; none has knowledge behind it (0 packages) | 🟡 The order of judging covers some | P4-1, with P3 |
| 23 | **Cost and latency bounded per situation** | 🟡 $0.09 a result at the median; the $2 cap binds every day | ✅ $8.41 for the build | P4-13, P4-16 |

## 2 · The GeniOS-008 L2 plan and Rohit's L2 spec

| # | Expected | Product today | Notebook `b2` | Fixed by |
|---|---|---|---|---|
| 24 | **Context first, never rules first;** deterministic code subordinate | 🟡 The judge is LLM-led; but 77 of 111 cards come from rule lanes, decided by a model in test mode | 🟡 LLM-led, with five hand rules | P4-17 |
| 25 | **The model judges materiality, priority and confidence in words, with evidence** | 🟡 Stakes, urgency and reversibility as levels with reasons; the confidence words unchecked | 🟡 Importance in words | P4-3, P4-11 (levels computed from the words) |
| 26 | **Patterns are evidence, not laws** | ✅ "The playbook is a prior" | ❌ "More specific" | P4-2 |
| 27 | **Five kinds of statement never mixed** (observed, reported, inference, hypothesis, unknown) | ✅ Kept apart and checked | 🟡 | P4-5 (RC-12) |
| 28 | **Absence only with coverage** | 🟡 The rule is coverage-aware; coverage is never computed | ✅ "An absence is a finding when the mail was read" | P4-3 (`cf.coverage`), RC-11 |
| 29 | **Ten runtime components (R1–R10)** | 🟡 Built, live for this tenant; history and model routing partial; the units' demotion (L2-H1), the decider's retirement (L2-H2), the legacy lane's retirement (L2-H3) and the first switch not built | — | P4-10 (the components, 07 §2.7), P4-17 |
| 30 | **Golden scenarios:** the same mail with a different history; the same company with different commitments; a similar history with a different cause; conflicting stakeholders; missing data that must not become absence; a stale status against recent evidence; "investigate" as the right answer; a first reading that must change | ❌ Not built | ❌ | P4-1 (the fixtures), §19 |
| 31 | **Model routing benchmarked; thinking budget explicit** | 🟡 Constants per tier; no per-tenant row | 🟡 One model setting | P4-16 |
| 32 | **One runtime; no agent per unit** | ✅ | ✅ | keep |
| 33 | **The draft leaves the judgment** | ❌ The draft is in the judge's answer | ❌ | P4-8 (the draft task) |

## 3 · The ideal dashboard

| # | Expected | Product today | Notebook `b2` | Fixed by |
|---|---|---|---|---|
| 34 | **A trace per card:** the units that ran, those that declined, and why ("returned no number", "needs your answer") | ❌ Group names only | ❌ | P4-10, P4-14 |
| 35 | **Goal lines that count:** "Counted: …", "Unknown, not 0: …", "Blocked, not late: …" | ❌ No goal judged as a goal | ❌ | P4-4, P4-6 |
| 36 | **Every rule a card names prints its condition and the inputs that made it apply** | ❌ Rules are not cited with conditions | ❌ Conditions cut to 260 characters | P4-5 (RC-2), with P3-2 |
| 37 | **Six confidence dimensions, strong, medium or weak; the weakest wins; every weak one with its reason** | ❌ | ❌ | P4-3 |
| 38 | **Cards that need no judgment come from code alone** (9 of the ideal's 20 make no call) | 🟡 The compiled lane makes cards, but a model decides them | ❌ Every page is a call | P4-12 |
| 39 | **Dates and weekdays from a calculator; every elapsed time names its anchor** | ❌ UTC hours | ❌ | P4-3 |
| 40 | **The company's own patterns, "yours", with n and denominators** | ❌ 0 learned entries; "yours" in 0 of 50 dossiers | ❌ | P4-7 |
| 41 | **Goals with a plan from evidence, a next move that agrees with the cards, and gap cards** | ❌ Per-file goal impacts; 11 goals proposed, 0 approved, 0 cards linked to a goal | ❌ | P4-6 |

## 4 · The expected outcomes ([10](../10-ACCEPTANCE.md)): the cards P4 owns

| # | Card | The reasoning it needs | Product today | Notebook `b2` | Fixed by |
|---|---|---|---|---|---|
| 42 | `p1` | Compare the figures by metric, basis and tense; hold the conflict; never pick one | ❌ Amounts stored plainly, never compared | ✅ Same call | `n.claims`, `u.one_number` (P4-3, P4-12) |
| 43 | `f1` | The review is **today**, in the company's time: join early, lead with one number | ❌ Points the wrong way | 🟡 Right twice, then wrong on a re-judge | P4-3, RC-14 |
| 44 | `i1` | The incubator's milestone reaches the reconsideration; a written door outranks a stage prior: one update, then stop | 🟡 Right reading, held | ↔️ Opposite | P4-6, P4-2, with P2-6 |
| 45 | `i2` | A reply that gave a projection did not answer "current traction" | ❌ Never judged | ❌ Counted as answered | RC-5, RC-8, `l.asked_vs_answered` |
| 46 | `i3` | The follow-up after the call is ours; "silence reads by stage" does not apply | ❌ Held | ❌ "Soft no" | P4-2, RC-3, RC-4 |
| 47 | `i4` | Of 12 recipients with no reply in 10 weeks, which still matter | 🟡 Late, partly | ◐ Became the numbers card | `u.wave`, `r.context`, `r.intervention` |
| 48 | `i5` | Mail that bounced was never received: resend to working addresses | ❌ The bounce stays on the address | ◐ One of five | `u.delivery_failure` |
| 49 | `b2` | Two calls, no written next step: the collaboration note is ours | ❌ No card | ❌ Marked done | `r.commitment`, with P2's status by code |
| 50 | `b3` | The ball is in their court; let it close on its date | ❌ Never judged | ↔️ "You owe them times" | `l.whose_move`, `u.stop_rule` |
| 51 | `c2` | Renews within the week: decide before the notice date; ask for credits | ❌ Read, nothing recognised | ❌ A stale page, never re-judged | `d.decision_deadline`, with P3's renewal units |
| 52 | `f3` | A promised referral silent 24 days against the platform's own same-day pace | ❌ The file is too big to judge | ❌ Buried in a pile of 30 threads | `t.quiet_vs_usual`, P4-6's gap card, P4-9 |
| 53 | Goals | At least 8 of 9 in-copy goals with target, plan, progress and next move; health and next move equal on at least 7 | ❌ | 🟡 6 of 9 matched, none with those four | P4-4, P4-6 |
| 54 | Replay | Each day's event moves the right page, goal and card on that day | ❌ | not run | P4-12, with P1-8 |
| 55 | Cost | Evolve under $0.50 a day; Maintain under $1 a week | ❌ About $5.70 a day | not run | P4-13, P4-7 |

## 5 · The film and Rohit's words

| # | Expected | Product today | Notebook `b2` | Fixed by |
|---|---|---|---|---|
| 56 | **Every judgment uses the four inputs:** company patterns, domain expertise, reasoning patterns, current status | ❌ Current status partly; no expertise, no company patterns; reasoning only as prompt text | ❌ The same | P4-8 |
| 57 | **"Without hundreds of prompts":** a fixed number of prompts, generated | ❌ Many hand-written prompts | ❌ One per phase, by hand | P4-8 |
| 58 | **"Multidimensional patterns"** | ❌ | 🟡 Good whole-picture notes, one call | P4-7 |
| 59 | **The four kinds of intelligence,** each with what it needs | ❌ Not labelled | ❌ | P4-11 (RC-18), with P5 |
| 60 | **Delegate to people or an agent; approve before anything is sent** | ❌ No delegation in the judgment | ❌ | `r.planning`, RC-13, with L4 |
| 61 | **"Every Done teaches"** | ❌ 0 cards resolved; no outcome loop for the judge's cards | ❌ | P4-15 |
| 62 | **Every department and goal, with the same reasoning;** only knowledge grows | 🟡 The units are domain-shaped | ❌ | P4-1 (RG-2) |
| 63 | **Rohit, 5 Oct: the LLM reasons like a 30-year expert** | 🟡 The judge does; the rule lanes are decided by a Haiku-class model in test mode | 🟡 | P4-17 |
| 64 | **Rohit, 6 Oct: no rigid rules** | 🟡 | 🟡 | P4-1, P4-5 (units guide, never decide; conditions keep a rule from being rigid) |

## 6 · What to keep

**From the product:**
- the L2 judge itself: its gate, fingerprints, store, needs and the "unchanged costs nothing" rule;
- the claim check (check v8), the strongest piece of Plane R today;
- "the playbook is a prior"; "follow the founder's correction, or say why not";
- the checklist's order (true → frame → expected against actual → patterns → unknowns → scenarios → appraisal → mode → move), which becomes the units' order;
- `lane_for` (code picks the lane), with computed inputs;
- the receipts and the replay;
- the units' checks: the constraint gate's eliminations and the planning unit's "outcome not observable".

**From the notebook:**
- the order of judging that ends in "is the founder needed now?";
- admission change by change, with every reason kept;
- "an absence is a finding when the mail was read";
- the code that finds what no thread shows: numbers told two ways, mail that never arrived;
- the whole-picture notes.
