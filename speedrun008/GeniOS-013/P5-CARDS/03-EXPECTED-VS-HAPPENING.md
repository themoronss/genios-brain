# P5 · Cards · 03 · What's expected, and what's happening

**Expected,** from six sources: the Atlas v2; Rohit's own card work (GeniOS-009 to GeniOS-012, with Rohit's review rounds of 22 Oct); the ideal dashboard; the expected outcomes card by card ([10](../10-ACCEPTANCE.md)); the launch film; and what the other four parts of GeniOS-013 hand to P5. **Happening:** the product at `a729b968` with the first week of the design partner's org, the dashboard's `origin/main`, and the notebook `b2` ([01](01-WHATS-EXACTLY-THERE.md)).

---

## 1 · The Atlas v2

| # | Expected | Product | Notebook |
|---|---|---|---|
| 1 | **A card reports a situation, arrives unasked, carries the thinking and tracks whether it worked** (A.1) | Reports a signal; tracks nothing (0 resolved) | Reports a work; no outcome |
| 2 | **Downstream of truth:** situation → ReasoningResult → DecisionObject → card vN, never edited in place (A.1) | Downstream of signals; non-file cards rebuilt in place | Downstream of the page ✅ |
| 3 | **Nine parts:** header (lane, severity, audience, version), title, why it matters, why now, evidence, still unknown, options, authority, actions, footer (confidence and receipt) (A.2) | Lane, a 3-band dot, no audience; no unknowns, options or authority; no receipt | Lane and version; no severity, audience, unknowns, authority, actions; confidence empty |
| 4 | **Five lanes from the reasoning outcome, never from tone** (A.3) | `output_lane.route`; L2's lane only as a hold (16 of 33 agree) | The page's lane or the clock's; a "deadline" lane |
| 5 | **Uncertainty routes, never deletes; every suppress has a why-not** (A.3, A.8) | No per-card why-not; legacy suppression rows only | A list of works that only wait |
| 6 | **Six confidence bars, each gating a different claim** (A.4) | None on the Cards page; four chips on the Goals page | Always empty |
| 7 | **One situation, one card, many versions; re-notify only when lane or severity rises** (A.7) | ✅ for file cards; one card per signal elsewhere | ✅ per work; duplicates across works |
| 8 | **Severity 1–4 by rules; about 1 critical a week, 3 act-this-week a day, 1 an hour; budget-lost cards folded into the brief** (A.8) | A utility band; 20 critical pushes in 7 days | None |
| 9 | **The brief: Needs you, Handled without you, Checked and quiet, with coverage** (A.8) | A separate brief; not on the card path | None |
| 10 | **Cards for agents: a task contract with may and may_not; draft, never send; approval before anything external** (A.9) | The approve-before-dispatch ledger is built; no task contract; 0 agents | Not represented |
| 11 | **Five roles never collapse; only a person approves** (L4) | The decision object exists; no card shows roles | Not represented |
| 12 | **Claim-level validation; L5 never invents a fact; the model only words** (L5) | Claim checks exist; the narrator and R-10 word; R-10 off | Quotes checked word for word only |
| 13 | **Eight surfaces, one intelligence** (L5) | In-app only; moments in shadow | Files only |
| 14 | **"Wrong because …" blames the layer that failed** (L6) | 11 reasons mapped to six layers ✅; 0 used | None |
| 15 | **Close on outcome evidence, not a click** (V.6 rule 11) | Done marks acted | None |
| 16 | **Five pipeline counters; `card_delivered` is L5's** (I.4) | Not instrumented | Not instrumented |

## 2 · Rohit's card work (GeniOS-009 to GeniOS-012)

Rohit's words in the review rounds of 22 Oct, and the decisions of GeniOS-009:
- "Goals banenge, goals ke regarding cards banenge" (goals come first, then the cards about them);
- "Ek goal ke andar kai cards … jab tak goal complete nahi ho jata" (one goal holds many cards until it is complete);
- "Card aane ka matlab … task abhi tak complete nahi hua hai" (a card means the task isn't done yet);
- every card must say "which goal it will affect";
- tool tags on top; a clear verb-first subject; one or two lines of what to do and how; only the buttons the brain takes; every card's details its own; no system timeline on the card.

| # | Expected | Product and screens | Notebook |
|---|---|---|---|
| 1 | **A card asks one thing:** decide, answer one question, or wait while GeniOS watches | Mostly; 33 of 64 decision cards cannot be done | Partly; "waiting" means "we owe" |
| 2 | **The face:** tool tags, a verb-first subject of about ten words that is never cut, two lines of what and how | Tool tags ✅; 20 headlines cut mid-sentence; "Needs a decision —" on 40 | 40 page headlines ✅; 23 template headlines |
| 3 | **The panel in Rohit's order:** recommendation, What · Why · How, what doing it gets you, goal, deadline, details, where the data came from | ✅ on `origin/main`; the goal row fixed text | One page per work |
| 4 | **Goal and Deadline always shown,** any other empty field left out | ✅ the rows; the goal never filled | Goal links on 55 of 63 |
| 5 | **Every card's details its own;** no stock sentence | Lines repeated across cards removed at read; 77 template consequences | Own ✅ (page-written cards) |
| 6 | **Only the buttons the brain takes; a refused press shows its reason and stays** | ✅ on the web; Delegate drawn everywhere and locked; the Mac swallows refusals | No buttons |
| 7 | **Done means claimed, never verified;** the situation closes only on proof (STEP-G7) | Done marks acted | No closing reason |
| 8 | **Delegate to a person or an agent;** nothing runs before approval (STEP-G8) | Locked; no person route; the agent ledger unused | Not represented |
| 9 | **Feedback in Rohit's words:** the card's reasons, "wrong because ___", "should be ___", a scope | ✅ on the web; refused on the Mac | None |
| 10 | **One goal is one card;** its cards numbered `G-xxxxxx · C01`, never shifting | Numbered by position; `goal.cards` always empty | No numbers |
| 11 | **Cards not linked to a goal counted, never hidden** | Counted; 14 of 65 hidden as "locked domain" | Not counted |
| 12 | **One reader for every surface** | Three readers | One page |
| 13 | **The Mac: one card at a time, dropping from the menu bar, with Done, Delegate, Later, Feedback** | Approved as a dummy; the shipped app is a scroll list | — |
| 14 | **Dummy first, then Rohit's approval, then real files** | Followed for 06-CARDS and the Mac dummy | — |
| 15 | **Held cards speak in the founder's words,** never "We held the one we found" (GeniOS-009 A2) | The sentence on 13 open cards | None ✅ |
| 16 | **The ideal's 20 cards are the acceptance test** (GeniOS-011 07) | 0 same, 9 partial, 11 missing | 4 same, 2 close, 4 partly, 2 opposite, 5 missed |

## 3 · The ideal dashboard

| # | Expected | Today |
|---|---|---|
| 1 | Every card has a number from its goal (`G-19E3CB · C01`), never renumbered; `C-xxxxxx` with no goal | Positions only |
| 2 | Every card has a version beside its number, and a history of what happened, with two times | Versions on 16 file cards; the tag never shows |
| 3 | The age is the open loop's, not the card's (`f3` 24d, `s1` 6mo) | The card's age |
| 4 | The headline in the lane's form: verb first; "Which is right?"; a question; "Waiting –" | Prefixes; cut sentences |
| 5 | Who acts, for whom and by when, typed | `recommended` on 9 of 103 |
| 6 | Done when always; "if you don't" on decision, question and conflict; "if you can't" when an alternative exists; "wait or stop" on waiting cards | Done-when on 63 of 103, often a code |
| 7 | Quotes verbatim with source and date on every card | Quotes on 8 of 111 |
| 8 | Absence named as one of four kinds | Not named |
| 9 | Six confidence dimensions, each with its reason when not strong | None |
| 10 | Four lanes in the order conflict, decision, question, waiting | Decide first; lane lost past the 40th card |
| 11 | A waiting card asks nothing, has GeniOS as the actor, sends no notification | Monitor cards read as decisions |
| 12 | Close only on proof: "Verified" and "Closed on proof: …" | 0 resolved |
| 13 | Delegate with a person and an agent tab; "you approve before anything is sent" | Locked |
| 14 | Every card names its goal, relation and through; "Not linked to a goal yet" counted | 0 of 111 |
| 15 | Critical, high, standard by a written rule; 2 / 6 / 12 | 22 critical of 103 open |
| 16 | A home banner for the single most urgent card, chosen by rule | None |
| 17 | A trace in fixed stages from L1 to L6, with the real model calls | None |
| 18 | Many threads that are one situation become one card, and the card says how many | One counterparty, 25–31 cards |

## 4 · The expected outcomes ([10](../10-ACCEPTANCE.md)): the cards P5 owns

| Card | Expected | Live product | Notebook `b2` |
|---|---|---|---|
| `p1` | One conflict card, critical, the banner; every side with its date, source and rank; GeniOS never picks | Lost | The same call, raised twice |
| `f3` | A gap card from the goal, high, anchored to the platform's 29 Sep promise | Not judged | Missed |
| `f4` | A waiting card: next check Mon 26 Oct 10:00, nothing to do | Held | A dated deadline card |
| `i1` | Version 4 of one card on the milestone; one update, then stop; delegable; nothing sent before approval | Held; an old card says "71 days late" | No card; the opposite call on its page |
| `i4` | One question over the wave of 12: which still matter? | Partly, late | Became the numbers card |
| `i5` | One card, a row per bounce | The bounce on the address | One complaint only |
| `b1` | One card, a row per introduction, each with its recommended answer | One held, one never judged | One offer carded; four stale ones too |
| `c1` | One card, high, due Mon 26 Oct; the portal not verifiable | Filed as an investor | Two cards, a later date |
| `c2` | No goal, counted, its own number; kept, downgraded or credited on proof | Not recognised | Filed as noise |
| The replay | 27 Oct: one "goal reached, confirm" card; `p1` grows with no card per recipient | Not run | Not run |
| Targets | ≥ 15 of 17 same or close; 0 opposite; ≤ 30 open, no ideal card lost | 0 same | 6 same or close; 63 open |

## 5 · The film and Rohit's words

- **"Intelligence: what to do, and why":** every card states a verb-first action and its reason. *Product:* often a stock sentence. *Notebook:* ✅ on the 40 page-written cards.
- **The four kinds** (reactive, proactive, predictive, prescriptive), visible on every surface. *Both:* none.
- **"So I delegate it to people or an agent" … "you approve before anything is sent":** *Product:* locked, and the agent ledger unused. *Notebook:* none.
- **"Every Done teaches":** Done carried back as evidence, and feedback changing how similar cards rank for this company. *Product:* in the fingerprint, 3 verdicts. *Notebook:* none.
- **The goal page:** what happened, the plan, the reasoning, then "Intelligence on this goal". *Product:* `goal.cards` empty. *Notebook:* goals are sentences.
- **The phone notification:** the headline and the why, opening the same card. *Product:* no phone channel. *Notebook:* none.
- **A new customer's first screen:** honest progress, "Connected. Reading your last 30 days first", the company page to confirm, the first intelligence within 2 hours. *Product:* "Ready" at 3 h 39 min with 14 old-lane cards and no goal.

## 6 · What to keep

- **The living card** (STEP-14): one card per file, versions with the words before and after, material changes, quiet versions never pushed.
- **The action door** and its refusals, and the eleven feedback reasons mapped to layers.
- **The delegation ledger:** propose, approve with frozen bytes, reject, one result.
- **R-10, the card writer:** cited facts, a sentence dropped when it rests on nothing, a cache by digest, its own budget.
- **The timing gate, the policy, the rate limiter and the outbox:** built and tested, waiting for a real delivery.
- **The Cards page on `origin/main`** (Rohit's order, the 600-pixel panel, refusals kept on screen) and **the approved Mac dummy.**
- **The notebook's page-written card content** (verb-first headlines, a why-now, a recommendation, at most 4 steps, quotes checked word for word, a draft where a message is due), and its comparison page.
