> **Created:** 2026-09-01 · **Status:** 🟢 Active — diagnosis done on live data, nothing built yet
>
> **Purpose:** Why the Mac app shows facts instead of a manager's advice, proved by opening one
> real production card — and the two things to build so it stops.

## The complaint

> "Mujhe facts nahi chahiye. App manager ki tarah bole — yeh karo achha hai, yeh nahi."

Thirty cards reach the Mac app today. Roughly two or three are what that sentence asks for.

## One real card, opened

Production, design-partner org, 2026-09-01:

```
HEADLINE  : willow@myzyner.com: 34 days, no reply
SITUATION : Email opened 2026-07-28. Our policy targets first response within
            24 hours. We are now 807 hours overdue. Ball is in our court.
WHY NOW   : (empty)
COST      : "The first_response_overdue situation is left unaddressed while its
             evidence compounds."
ACTION    : customer_support.pb.breach_prevention.work_the_at_risk_list_hourly
DRAFT     : "Hi willow, apologies for the delayed response. I saw your message
             about working with Metal, Vibe, Archil and the 80 YC-backed teams
             you support — including Hunter Leath from Archil (YC F24)…
             What's the best way to reconnect on what you were looking to
             discuss?"
```

**Five findings, and none of them is missing data.**

| # | What is wrong | What it means |
|---|---|---|
| 1 | The DRAFT is good | It names real people and reads like a person wrote it. The material is all there. |
| 2 | The headline is a clock | "34 days, no reply" is a measurement. A manager says the move, not the elapsed time. |
| 3 | It invented a policy | *"Our policy targets first response within 24 hours"* — **no such policy exists.** The support corpus states plainly that no per-customer target lives anywhere in this system. The card manufactured an SLA and then reported a breach against it. |
| 4 | Wrong domain entirely | `customer_support.breach_prevention` — a support playbook, running on a **VC/investor thread**. |
| 5 | `why_now` empty, `cost` is boilerplate | The cost line is the adapter's template string (`expertise.py`), identical on every card of that type. |

## The one-sentence diagnosis

> The move is already in the card — it is the draft, at the bottom. The top line is a fact. So
> the product reads as a fact-reporter with a draft attached, instead of a manager with a reason.

## What to build

### A. The card leads with the move

The decision already exists: a play was selected, alternatives were rejected, an artifact was
written. The card's headline and situation are composed from the SITUATION instead.

Invert it:

```
now      →  willow@myzyner.com: 34 days, no reply
           Our policy targets first response within 24 hours…

wanted   →  Reply to Willow today — 34 days, and they asked to reconnect
           Their last message named eight portfolio teams and asked how to
           connect. Nothing has gone back. Draft ready.
```

Facts move down and become the evidence line. The instruction moves up.

Touches: `deliver/card_builder.build_draft` (what the headline is composed from) and
`deliver/render._prompt` (what the model is asked to write first). The authored `render_hint` in
each situation file already describes the move — it is being asked for the situation instead.

**Also fixes finding 3.** A card that leads with the move has no reason to narrate a policy, and
the render contract can forbid stating any threshold that is not a fact on the row.

### B. Domain routing

An investor thread became a customer-support ticket, and a support breach-prevention playbook was
attached to it. That is finding 4, and no amount of better copy repairs it — the wrong expert is
speaking.

Today the domain comes from `capture/domain/hints.py`: an ordered regex, **first match wins,
single label, no confidence**. `general` means "no keyword fired", which is most real mail.

Needs the Universal Domain Router the Admin-Intelligence MD specifies (§6.1): multi-label
candidates with confidence, correctable by a human, independent of entitlements.

## Blocked on one decision, and it is not technical

The two co-founders have given opposite instructions on the same day:

* **"Only Admin Domain Expertise. Rest sabko lock kar dijiye."**
* **"Sales ko fix karna compulsory hai."**

**B cannot be specified until this is answered** — a router's whole job is deciding which domains
exist and which are locked. A also changes: a manager's voice for Admin follow-through is not the
same voice as a sales next-step.

Sales was fully wired on 2026-09-01 (15 situations, gates, copy, admitted). Locking it is a
product call, not a rollback.

## Order

1. **Decide Admin-only vs Admin+Sales.** Everything below depends on it.
2. **A — the card leads with the move.** Independent of the decision for the mechanics; only the
   voice differs. Highest visible impact per hour of work.
3. **B — the router.** Fixes the wrong-expert class of failure, which copy cannot.

## What is NOT the problem

Worth stating, because the last two weeks were spent on it: this is not a data gap. The draft
quoted above proves the substrate holds enough to write a specific, useful message. Every defect
found on live data this week was a DISCONNECT rather than an absence —

* `is_actionable()` existed; the push decision never called it, so 18 of 24 surfaced cards were
  the system saying it could not help
* `observation_vocabulary()` computed the tenant's kinds; the extraction prompt carried its own
  hand-typed copy
* the counterparty's words sat one `concerns` edge away; the quote query had no lane for it
* Layer 6 published a measured success rate per play; the ranking model never read it
* the waiting clock ran only when new mail arrived

The co-founder's read — *"sab kuch already hai, bas connect nahi ho raha"* — is correct, and the
same is true of the card itself: the move is in there, one field too low.
