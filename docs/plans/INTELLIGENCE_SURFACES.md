> **Created:** 2026-08-26 · **Status:** Active — PARTIALLY SHIPPED (item 1 done, item 2 half done, items 3-5 open)
> **Purpose:** One intelligence, four surfaces. Define what each surface is FOR, and stop shipping the same card to all of them.

## Where this actually stands — verified against code 2026-08-30

| # | The work | State | Evidence |
|---|---|---|---|
| 1 | A card knows its surfaces | **DONE** | `migrations/0075_card_surfaces.sql`; `deliver/card_builder.py:230 _surfaces()` computes `{app, agent, ask, api}` at build time; `deliver/store.py:126,156` persists it. A settled deal (`_SETTLED_STATUSES`) at momentum ≤ 0 now returns `["ask","api"]` only — the Antler card is off the app queue. |
| 2 | Each surface filters on it | **HALF DONE** | The app filter shipped: `deliver/store.py:310` — `and 'app' = any(k.surfaces)`. **The agent gateway never got its filter**: `deliver/agent_api.py:82` still selects from `cards` with no `surfaces` predicate, so an agent is still offered every card including ones with nothing to execute. This is the single smallest open item in this plan. |
| 3 | The app's card becomes an instruction | **PARTIAL** | `do_nothing_consequence` now travels the whole way (`migrations/0070_signal_decision_columns.sql` → `deliver/pipeline.py:64` → `card_builder.py:444`). `why_now` is populated by `card_builder.py:87 _why_now()` for **three reason codes only** (`commitment_overdue`, `meeting_no_followup`, `unanswered_email`) and returns `None` for every other one — deliberately, so it cannot invent a reason, but the coverage gap is real. |
| 4 | The agent's card becomes executable | **PARTIAL** | `migrations/0073_agent_delegations.sql` and the agent delivery lane exist (`99ed200`, `d360677`). The plan's actual bar — "prove one delegation end to end **against a real agent**" — has not been met; that is a live-integration step, not code. |
| 5 | The package surface | **NOT STARTED** | No LangChain/LangGraph/npm client on the current engine. The only such code on disk is under `_legacy_brain/sdks/`, which the engine does not use. Correctly last. |

The plan's ordering section also lists **"corpus content — 136 of 153 capabilities carry identity and purpose only"** as item 4 of 5. That number is stale: the Sales, Admin and Customer Support corpora were authored to completion between 2026-08-26 and 2026-08-29 (`e6de45d`, `e5851c1`, `bd75aa1`, `a112026` — corpus validate at zero errors). Routing coverage, not authoring, is now the live constraint — see `ADMIN_SUPPORT_WIRING.md`.

# The problem, stated once

Everything below traces to one card on the design partner's live app:

```
antler.co: Residency program rejected 6 Aug
They evaluated us for their Residency program with a 14 August deadline. They rejected on 6 Aug.

  deal.status = rejected · derived.momentum = 0 · derived.engagement = 0
  ball_in_court = them   · last inbound = 7 Aug · deadline = 14 Aug (passed)
```

Sitting inside **62 OPEN LOOPS** in a desktop app whose job is to say what needs you now.

Nothing about it is factually wrong. The extraction is right, the dates are right, the reasoning is
right, and the evidence is grounded. It is still the wrong card, because a deal the system's own
evidence marks `rejected` with zero momentum past its deadline needs nothing from anyone.

And here is the part that makes this a design problem rather than a bug: **the same card is
correct on a different surface.** Asked "what happened with Antler?", that text is the complete
and ideal answer.

So the defect is not the content. It is that one `cards` row is written once, shaped for nobody,
and pushed to every surface — and no code anywhere asks what the surface is for.

# The four surfaces, and what each is actually for

| Surface | The question it answers | Antler card belongs? |
|---|---|---|
| **Desktop app** — ambient advisor | "What should I do right now that I wouldn't otherwise?" | **No** — closed, no step |
| **Agent** (Hermes, OpenClaw) | "What should I execute, under what conditions?" | **No** — nothing to execute |
| **Ask** (`/v1/intelligence/query`) | "Tell me what you know about X" | **Yes** — this IS the answer |
| **Package / API** (LangChain, LangGraph, npm) | "Give me the structured facts, I decide" | **Yes** — a fact with provenance |

Two surfaces want the closed case. Two do not. Nothing currently distinguishes them.

## Each surface's own contract

**Desktop app — fewer cards, every one earning its place.** The measure is not how many loops are
open; it is whether a person who reads every card acts on every card. A closed situation belongs in
history, not the queue. Today the count itself (62) is presented as the value, which is the wrong
metric to optimise and the app optimises it perfectly.

**Agent — an instruction, not a description.** An agent needs the action, its target, the
preconditions that make it safe, and the boundary where it must stop and hand back. A card that
says "several open items blocking commitment" cannot be executed by anything. Execution stays on
the customer's side (agent_api.py already holds this line correctly) — but what we hand over has to
be executable in the first place.

**Ask — completeness, including what is closed.** Here suppression is the failure. If someone asks,
answer with everything: rejected deals, lapsed threads, the whole history.

**Package / API — structure and provenance, no editorial.** The caller decides relevance. Our job
is that every fact arrives with its evidence and its source, and that nothing is quietly filtered.

# What exists today (verified on the live org, 2026-08-26)

| | State |
|---|---|
| `/cards` (app) | Live — 62 queued, 53 from the compiled brain |
| `/v1/intelligence/query` (Ask) | Live |
| `/v1/intelligence/analyze`, `/draft` | Live |
| `deliver/agent_api.py` | Built — claim lock, 409 on double claim, failure re-surfaces |
| `agent_registry` | 1 row |
| `agent_delegations` | **0 rows — never used in production** |
| Surface-awareness anywhere | **Does not exist** |

The plumbing is not the gap. Four surfaces are built and reachable. The gap is that a card carries
no notion of which surface it is for, so the routing decision is never made — it is skipped.

# The work

## 1 — A card knows its surfaces

Add `surfaces` to the card contract: which of {app, agent, ask, api} this card is valid on.
Computed at build time from the decision, not configured per tenant.

The rules that follow from the contracts above:

- `deal.status` in (rejected, lost, won) **and** `derived.momentum = 0` → `ask`, `api`. Not `app`.
- an authority deadline already past with no candidate step → `ask`, `api`.
- the selected candidate carries an executable play with preconditions → add `agent`.
- everything else with a live next step → `app`, `ask`, `api`.

`ask` and `api` are the default for everything the system knows. `app` and `agent` have to be
earned. That asymmetry is the whole design.

## 2 — Each surface filters on it

`/cards` serves `surfaces @> '{app}'`. The agent gateway serves `{agent}`. Ask and the API do not
filter. One column, four readers, no duplicated logic.

## 3 — The app's card becomes an instruction

A card reaching `app` must carry: the action, why now, what changes if ignored, and the one next
step. `do_nothing_consequence` and `why_now` already exist on the row and are not consistently
populated by the compiled lane.

## 4 — The agent's card becomes executable

`agent_delegations` has zero rows. Before authoring more corpus, prove one delegation end to end
against a real agent: hand over a signal, have it claim, execute, and report back.

## 5 — The package surface

LangChain / LangGraph / npm: a thin client over the API. Not started. It should be last — a package
around an intelligence that is not yet right per surface would ship the same undifferentiated
content with a nicer import statement.

# Order, and why

1. **Surface tagging + app filter** — this is what removes the Antler card from the queue. Smallest
   change, largest visible effect, and it makes the app honest about what it is.
2. **App card as instruction** — populate `why_now` and `do_nothing_consequence` from the compiled
   decision.
3. **Agent delegation proven once** — one real round trip before any more building.
4. **Corpus content** — 136 of 153 capabilities carry identity and purpose only. This is what a new
   tenant with different data will hit immediately, and it is the largest body of work.
5. **Package surface** — last, for the reason above.

# The standing check

`scripts/card_audit.py` asks the live queue every question at once. Extend it with a surface check:
any card on `app` whose situation is closed is a regression of item 1, and should be caught by the
tool rather than by the owner reading his own app.
