# Customer Support Expertise — folder map

> **How would a seasoned support operator read this situation?**
>
> Not what is true — that is Layer 2. Not what to do — that is Layer 4.

[← Authoring guide](../README.md) · [Browsable book](../_book/Customer%20Support%20Expertise/index.md) ·
[Signal backlog](registry/signal-backlog.md)

---

## Where this stands

| | |
|---|---|
| Files | **508**, all passing `validate.py` |
| Subdomains | 9 |
| Capabilities | **49** — 9 complete, 40 stub |
| Knowledge artifacts | **287** playbooks · heuristics · mental models · decision frameworks |
| Objects | **12 authored at 23/23 sections**, 21 declared in `planned_objects` |
| Situations | 14 |
| Model branches | 19 models + 16 verticals |
| Offering branches | 3 families + 9 types |
| Inference patterns | **93 executable · 112 blocked** on 119 distinct signals |
| Layer 2 coverage | **5 of 26** emitted types routed · **15** triggers blocked on a pack that does not exist |

Every object is complete to all twenty-three sections. That was the bar rather than breadth:
a thin object is worse than no object, because it looks finished.

---

## Read this before judging the coverage number

**5 of 26 is not a gap in the authoring. It is the honest ceiling.**

Sales was authored against packs that already shipped. Customer Support was not — there is no
`support_v1` pack. Of the 26 Layer 2 situation types in the substrate, exactly **five** are
domain-neutral (`unanswered_email`, `commitment_overdue`, `champion_quiet`,
`meeting_no_followup`, `intro_followup`), and **zero** observation kinds are support-native.
No ticket. No SLA clock. No CSAT. No escalation. No incident.

There were two honest options and one dishonest one. The dishonest one was to bind *"SLA breach
imminent"* to `unanswered_email` because it is the closest thing available — the situation then
routes, the dashboard shows coverage, and the system nudges about the wrong thing forever. That
is worse than a gap because it looks like the opposite of one.

So this domain does at the situation level what the library already does at the pattern level.
Five situations bind to types Layer 2 genuinely emits and **run today**. The other nine declare
their real trigger under `matches.pending_l2_situation_types`, route nothing, and name exactly
what a `support_v1` pack must emit.

**The backlog is the deliverable, not an apology for one.**

---

## Layout

```
Customer Support Expertise/
├── domain.yaml                    9 subdomains · id scheme · planned_objects · glossary
│
├── capabilities/                  49, numbered by the resolution lifecycle
│   ├── 01-intake-and-triage/          6   ← ticket-triage is complete
│   ├── 02-diagnosis-and-resolution/   6   ← root-cause-analysis
│   ├── 03-customer-communication/     5   ← de-escalation
│   ├── 04-entitlement-and-sla/        5   ← sla-management
│   ├── 05-knowledge-and-deflection/   5   ← self-service-deflection
│   ├── 06-escalation-and-incident/    6   ← escalation-management
│   ├── 07-voice-of-customer/          5   ← churn-signal-detection
│   ├── 08-support-operations/         5   ← queue-management
│   └── 09-support-management/         6   ← quality-assurance
│       each: capability.yaml · objects.yaml · knowledge.yaml · situations/
│
├── objects/
│   ├── core/                      ticket · requester · entitlement · sla-target · escalation
│   │                              incident · knowledge-article · customer-sentiment
│   │                              churn-risk · commitment
│   ├── macro_management/          macro          (scoped — one capability loads it)
│   └── postmortem/                postmortem     (scoped)
│
├── playbooks/ heuristics/         287 artifacts, scoped to their owning capability
├── mental-models/ decision-frameworks/
│
├── models/                        b2b · b2c (with verticals/) · b2b2c · plg-self-serve
│                                  enterprise · mid-market · smb · tiered · swarming
│                                  follow-the-sun · named-tam · community · outsourced-bpo
│                                  ai-first · embedded · field-service · premium · proactive
├── offerings/                     product/ service/ hybrid/  (+ 9 types)
└── registry/                      GENERATED — do not edit
```

---

## Start here

| Reading for | Open |
|---|---|
| The reference object — 23/23 sections, 56 attributes, 16 weighted relationships | [objects/core/ticket.yaml](objects/core/ticket.yaml) |
| The strongest day-one object — most of its patterns fire today | [objects/core/commitment.yaml](objects/core/commitment.yaml) |
| The reference capability | [capabilities/01-intake-and-triage/ticket-triage/capability.yaml](capabilities/01-intake-and-triage/ticket-triage/capability.yaml) |
| A situation that routes today | [.../response-drafting/situations/customer-awaiting-reply.yaml](capabilities/03-customer-communication/response-drafting/situations/customer-awaiting-reply.yaml) |
| A situation that states its own gap | [.../breach-prevention/situations/sla-breach-imminent.yaml](capabilities/04-entitlement-and-sla/breach-prevention/situations/sla-breach-imminent.yaml) |
| What Layers 1 and 2 must build next | [registry/signal-backlog.md](registry/signal-backlog.md) |

---

## What the profession says, and where this brain got it

Every object cites the frameworks it leaned on in its `references` section. The four that do
most of the work:

- **ITIL 4** — the taxonomy the whole industry inherited. An *incident* is an unplanned
  interruption; a *service request* is a formal ask for something to be provided; a *problem*
  is a cause of one or more incidents. Our `issue` **is** ITIL's problem, and what we call a
  `ticket` is what ITIL splits in two. Priority = **impact × urgency**, which is why severity
  and priority are separate attributes everywhere in this brain.
- **KCS v6** (Consortium for Service Innovation) — governs everything touching knowledge.
  Solve loop: Capture, Structure, Reuse, Improve. Evolve loop: collection health driven by
  demand. **"Reuse is review"** shapes `knowledge-article`'s entire state machine — an article
  nobody has reused is not proven good, it is unproven.
- **Google SRE lineage** — severity is *blast radius*, not volume. SEV1–SEV4, a named Incident
  Commander who does not debug, blameless postmortems, and the decomposition
  **MTTD + MTTA + MTTR**. MTTD is the gap nobody funds and the cheapest to close.
- **Published measurement** — FCR of ~70–79% is good, with roughly a **1:1** relationship
  between FCR gain and CSAT gain. **Deflection is not FCR**: deflection only asks whether a
  contact reached an agent, so an abandonment scores as success — which is why it is the most
  gamed metric in support and why this brain treats self-service failure as a churn input.

---

## The three findings this library produced

Outputs of the authoring, not defects in it.

**1 · Support has no signal substrate at all.** 112 of 205 inference patterns are blocked. The
top asks, ranked by how many patterns each unblocks: `csat.score` (8), `derived.contact_frequency`
(8), `incident_declared` (7), `incident.started_at` (6), `cancellation_threat` (6),
`account.renewal_at` (6), `angry_language` (6). None of them is exotic; every one is a field
sitting in a helpdesk the connector does not read.

**2 · The strongest day-one object is `commitment`, not `ticket`.** `commitment.due_at` and
`commitment.action` are in the substrate, so *"you promised this customer a callback and the
time has passed"* fires today — while the central object of the domain cannot see a single
ticket field. That inversion is worth knowing before anyone plans a demo.

**3 · Two mechanisms had to be added to the library for a second domain to be authorable at
all** — `matches.pending_l2_situation_types` on situations, and `planned_substrate` in
`vocabulary.yaml`. Both are the situation-level twin of `needs_signal`. Without them the choice
was a crippled brain or a lying one.

---

## What comes next

| Phase | Work |
|---|---|
| **A** | Author the 21 objects in `planned_objects` — `issue`, `conversation`, `resolution`, `queue`, `support_agent`, `customer_account`, `satisfaction_score` first, since they are the most referenced |
| **B** | Promote the 40 stub capabilities, starting with the subdomains whose flagship is already complete |
| **C** | Ship a `support_v1` pack against `registry/signal-backlog.md`, which turns 15 blocked situations into routed ones and unblocks ~112 patterns |
| **D** | Decompose the 287 artifacts — each currently carries one authored statement, so playbooks have one step and frameworks one criterion |
