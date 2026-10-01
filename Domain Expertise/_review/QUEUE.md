# REVIEW QUEUE · the situations waiting on a human

**Generated** by `scripts/dx_review_queue.py`. Do not edit — approve the situation and
it leaves this list by itself. Re-run to regenerate.

    waiting on a review     15
      fire unconditionally  10   <- read these first
      carry a condition     5
      condition has no writer 0

⛔ **Every predicate across the whole queue was checked against production.** 0 have a path nothing writes.

⛔ **An empty `matches.when` is vacuously TRUE** — `context_adapter.matches(())` returns
`PredicateState.TRUE`, so those situations match on their L2 type alone, with no further
check. They are the most permissive entries here, not the least.

**What approving does.** It sets `metadata.review_status: approved`. It does **not** make
the situation live — `identity.status` must also become `stable`, and that is a separate,
deliberate second step. Five situations are already in that half-state; see ALARM D-A2.

---

## PART 1 · fires unconditionally — 10 situations

Each of these matches every situation of its L2 type. The question is the same for all
of them and it is the only question: **is that right here?**

### 1. Bug Awaiting Engineering

`customer_support.sit.bug_awaiting_engineering` · owner `customer_support.escalation_and_incident.engineering_handoff` · priority **6000bp** · typical **45 days** · card: **draft_reply** · authored confidence: *provisional* · last edited 2026-08-08

A defect has been filed and the customer is waiting on somebody who does not work in support. Support has done its part — reproduced it, written it up, handed it over — and has now entered the state it is worst at: owning a relationship while owning none of the work. The ticket has no next action an agent can take, which is precisely why it stops appearing in anyone's day. Frequently a workaround exists, which makes it worse rather than better: the ticket is marked resolved on the strength of it, the clock stops, the queue reports health, and a customer is left performing a manual step every morning against a defect nobody is telling them about. The situation is live for as long as the customer's problem is real, regardless of what state their ticket is in.

⛔ **Fires on the L2 type alone — no extra condition at all.** An empty `matches.when` is vacuously true, so this is the most permissive shape a situation can have.

**L2 types** `workaround_only` — formed **0** times in production   ⚠ never formed, so nothing real to validate against yet

**Progress** followup_sent, workaround_provided, root_cause_identified, bug_fixed
**Decay** escalation_requested, cancellation_threat, angry_language, ticket_reopened

> **Decide:** is matching on the type alone right here, or does it need a condition? If right → approve. If not → say which condition.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 2. CSAT Detractor

`customer_support.sit.csat_detractor` · owner `customer_support.voice_of_customer.satisfaction_measurement` · priority **6200bp** · typical **7 days** · card: **None** · authored confidence: *provisional* · last edited 2026-08-08

A customer has answered a survey and answered it badly. The interaction is over, the ticket is usually closed, and someone has taken the trouble to say it did not work — which is rarer than the response rate suggests, because most unhappy customers simply leave. The window is short and unusually favourable: a detractor who is contacted quickly, by someone who has read the ticket, about the specific thing they complained about, is one of the few recoverable states in support. The window closes fast, and the two ways it is habitually wasted are ignoring the response entirely because the ticket is closed, and answering it with a templated apology that proves nobody read the comment.

⛔ **Fires on the L2 type alone — no extra condition at all.** An empty `matches.when` is vacuously true, so this is the most permissive shape a situation can have.

**L2 types** `(none)` — formed **0** times in production   ⚠ never formed, so nothing real to validate against yet

**Progress** followup_sent, callback_promised, ticket_resolved, csat_submitted
**Decay** cancellation_threat, escalation_requested, refund_requested, ticket_reopened

> **Decide:** is matching on the type alone right here, or does it need a condition? If right → approve. If not → say which condition.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 3. Entitlement Expired

`customer_support.sit.entitlement_expired` · owner `customer_support.entitlement_and_sla.entitlement_verification` · priority **5500bp** · typical **21 days** · card: **None** · authored confidence: *provisional* · last edited 2026-08-08

The coverage this customer is being served under has lapsed, or the system's belief about it no longer matches what was actually sold. It surfaces almost always at the worst possible moment — mid-ticket, with someone already waiting — because entitlement expires quietly and is checked reactively. There are two distinct sub-cases underneath and they need different first moves: a clean expiry, where the term genuinely ended and there is a renewal conversation to have, and a mismatch, where the contract and the configuration disagree and the customer is very likely right. Both are discovered by an angry customer rather than by an audit, and in both the expensive error is the same one: telling the person in front of you what they are not entitled to, in the middle of the work, as though it were their mistake.

⛔ **Fires on the L2 type alone — no extra condition at all.** An empty `matches.when` is vacuously true, so this is the most permissive shape a situation can have.

**L2 types** `(none)` — formed **0** times in production   ⚠ never formed, so nothing real to validate against yet

**Progress** entitlement_checked, followup_sent, ticket_resolved, contract_countersigned
**Decay** cancellation_threat, escalation_requested, angry_language, refund_requested

> **Decide:** is matching on the type alone right here, or does it need a condition? If right → approve. If not → say which condition.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 4. Escalation Requested

`customer_support.sit.escalation_requested` · owner `customer_support.escalation_and_incident.escalation_management` · priority **8800bp** · typical **5 days** · card: **draft_reply** · authored confidence: *provisional* · last edited 2026-08-08

Someone has asked for this to leave its current owner. Usually the customer — "can I speak to your manager", "who is your VP", "I am taking this to our account team" — and sometimes an agent who has recognised that normal handling will not finish it. The two look identical in a ticket and need opposite first moves, which is why the trigger side is the first thing this situation wants to establish. The defining property is that the request exists and nobody has yet accepted it: for as long as that is true the work has two owners in principle and none in practice, and the interval before a named person says yes is the interval where escalations actually go wrong. What is being asked for is rarely speed. It is almost always confidence, which is why replying faster to the same person is the reflex that makes it worse.

⛔ **Fires on the L2 type alone — no extra condition at all.** An empty `matches.when` is vacuously true, so this is the most permissive shape a situation can have.

**L2 types** `escalation_requested` — formed **6** times in production

**Progress** escalation_accepted, callback_promised, followup_sent, workaround_provided, ticket_resolved
**Decay** cancellation_threat, angry_language, agent_reassigned, refund_requested, champion_change

> **Decide:** is matching on the type alone right here, or does it need a condition? If right → approve. If not → say which condition.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 5. First Response Overdue

`customer_support.sit.first_response_overdue` · owner `customer_support.entitlement_and_sla.breach_prevention` · priority **7000bp** · typical **2 days** · card: **draft_reply** · authored confidence: *experimental* · last edited 2026-08-29

A request arrived by mail, the deadline our own stated first-response policy implies has passed, and nobody has replied. Not a contractual breach and not a forecast — a plain statement that the promise this organisation made to itself has been missed on a specific conversation, while there is still somebody at the other end of it. The value is in the first half of the sentence rather than the second: everybody already knows the queue has old threads in it, and what nobody has is the specific list of people who wrote first and have heard nothing back.

⛔ **Fires on the L2 type alone — no extra condition at all.** An empty `matches.when` is vacuously true, so this is the most permissive shape a situation can have.

**L2 types** `first_response_overdue` — formed **37** times in production

**Progress** followup_sent, first_response_sent
**Decay** escalation_requested, angry_language

> **Decide:** is matching on the type alone right here, or does it need a condition? If right → approve. If not → say which condition.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 6. Major Incident Declared

`customer_support.sit.major_incident_declared` · owner `customer_support.escalation_and_incident.incident_management` · priority **9600bp** · typical **3 days** · card: **None** · authored confidence: *provisional* · last edited 2026-08-08

A fault has stopped being one customer's problem and has been declared as such. The declaration is the event — not the fault, which was already happening, and not the ticket volume, which arrives late and undercounts badly because the customers who did not write in have already formed an opinion. From the moment of declaration the unit of work is the incident and not the ticket: there is a commander who coordinates rather than debugs, one status narrative rather than many replies, and a standing assumption that anything the individual-ticket machinery wants to do right now is probably wrong. The situation stays live through the customer-side cleanup, which routinely outlasts the technical restoration by days and is where the relationship damage is actually repaired or confirmed.

⛔ **Fires on the L2 type alone — no extra condition at all.** An empty `matches.when` is vacuously true, so this is the most permissive shape a situation can have.

**L2 types** `(none)` — formed **0** times in production   ⚠ never formed, so nothing real to validate against yet

**Progress** incident_resolved, root_cause_identified, workaround_provided, followup_sent
**Decay** ticket_created, escalation_requested, cancellation_threat, angry_language

> **Decide:** is matching on the type alone right here, or does it need a condition? If right → approve. If not → say which condition.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 7. Queue Overloaded

`customer_support.sit.queue_overloaded` · owner `customer_support.support_operations.queue_management` · priority **7200bp** · typical **10 days** · card: **brief** · authored confidence: *provisional* · last edited 2026-08-08

A queue is taking in more than it is getting through, and has been for long enough that the oldest end of it has stopped being served at all. Not a busy morning — a rate mismatch that has persisted, which is a different thing with different remedies. The characteristic shape is a queue that looks acceptable by count and terrible by age distribution: the middle of the queue moves, the tail calcifies, and every incentive an individual agent has points away from the tail. The situation is about the team's ability to absorb what arrives, so the useful questions are what changed on the arrival side, what is deliberately not being served while this is true, and who has been forgotten — never simply how many are open.

⛔ **Fires on the L2 type alone — no extra condition at all.** An empty `matches.when` is vacuously true, so this is the most permissive shape a situation can have.

**L2 types** `queue_overloaded, ticket_aging` — formed **3** times in production

**Progress** ticket_resolved, ticket_closed, agent_reassigned, first_response_sent
**Decay** ticket_created, ticket_reopened, sla_breach, escalation_requested, angry_language

> **Decide:** is matching on the type alone right here, or does it need a condition? If right → approve. If not → say which condition.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 8. Repeat Contact

`customer_support.sit.repeat_contact` · owner `customer_support.knowledge_and_deflection.content_gap_analysis` · priority **6800bp** · typical **14 days** · card: **draft_reply** · authored confidence: *provisional* · last edited 2026-08-08

The same person is back about the same thing. Not a reopened ticket — the previous contact was answered, closed, and by the system's own account handled correctly — but a fresh arrival that is, in substance, the same question. Read from the customer's side this is a broken promise wearing a compliant record: they asked, we answered, and they still had to come back. Read from the queue's side it is evidence that the answer was wrong, incomplete, unfindable, or correct but delivered in a form the customer could not use. The second reading is the one that pays, and it is only visible if the two contacts can be seen at once, which is exactly what the ticket-per-contact model prevents.

⛔ **Fires on the L2 type alone — no extra condition at all.** An empty `matches.when` is vacuously true, so this is the most permissive shape a situation can have.

**L2 types** `repeat_contact, knowledge_gap` — formed **1** times in production

**Progress** knowledge_article_linked, self_service_attempted, ticket_resolved, followup_sent
**Decay** ticket_created, self_service_abandoned, ticket_reopened, angry_language

> **Decide:** is matching on the type alone right here, or does it need a condition? If right → approve. If not → say which condition.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 9. SLA Breach Imminent

`customer_support.sit.sla_breach_imminent` · owner `customer_support.entitlement_and_sla.breach_prevention` · priority **9200bp** · typical **1 days** · card: **None** · authored confidence: *provisional* · last edited 2026-08-08

A clock that a contract created is going to run out before anyone is scheduled to touch the ticket, and there is still time to change that. This is forecasting rather than bookkeeping: the useful signal is not the time remaining but everything around it — how many other deadlines the assignee holds in the same window, whether the deadline falls across a coverage handover, and whether the last outbound message actually asked the customer for anything or merely looked like it did. The intervention ladder runs cheapest first (reply, reassign, borrow, escalate, renegotiate) and every rung gets dramatically more expensive as the deadline approaches, which is the whole argument for firing early. The characteristic failure at the other end is alerting at the moment of breach, which is not a warning but a notification about the past.

⛔ **Fires on the L2 type alone — no extra condition at all.** An empty `matches.when` is vacuously true, so this is the most permissive shape a situation can have.

**L2 types** `(none)` — formed **0** times in production   ⚠ never formed, so nothing real to validate against yet

**Progress** first_response_sent, followup_sent, escalation_accepted, agent_reassigned
**Decay** sla_clock_paused, sla_breach, escalation_requested, angry_language

> **Decide:** is matching on the type alone right here, or does it need a condition? If right → approve. If not → say which condition.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 10. Ticket Reopened

`customer_support.sit.ticket_reopened` · owner `customer_support.diagnosis_and_resolution.verification_and_closure` · priority **8800bp** · typical **3 days** · card: **None** · authored confidence: *provisional* · last edited 2026-08-08

Something we declared resolved was not resolved, and the customer has come back to say so. The correct first move is not to answer again — it is to work out which of four categorically different failures this is, because they carry opposite lessons and averaging them into a reopen rate is why that metric is useless in most organisations. It was never fixed (closure without verification, usually an auto-close on silence). It fixed the wrong problem (a diagnosis error, and the most instructive of the four). It was fixed and regressed (a product defect, and not a support failure at all). Or it was fixed for some cases and not others (a scope error, which means other customers are affected and have not written in). The second attempt also starts from a worse position than the first: the customer's patience is already spent and their belief that anyone is tracking their problem is already damaged, so the reply has to acknowledge the first attempt before it does anything else. Answering a reopen as though it were a fresh question is the response most likely to produce an escalation.

⛔ **Fires on the L2 type alone — no extra condition at all.** An empty `matches.when` is vacuously true, so this is the most permissive shape a situation can have.

**L2 types** `(none)` — formed **0** times in production   ⚠ never formed, so nothing real to validate against yet

**Progress** reproduction_confirmed, root_cause_identified, followup_sent, ticket_resolved
**Decay** ticket_reopened, escalation_requested, angry_language, cancellation_threat

> **Decide:** is matching on the type alone right here, or does it need a condition? If right → approve. If not → say which condition.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

## PART 2 · carries a condition — 5 situations

### 11. Customer Awaiting Reply

`customer_support.sit.customer_awaiting_reply` · owner `customer_support.customer_communication.response_drafting` · priority **8200bp** · typical **2 days** · card: **draft_reply** · authored confidence: *provisional* · last edited 2026-08-08

A customer has written and the next move is ours. Nothing else is known — not whether a clock is running, not whether the question is hard, not whether anyone has started on it. The only fact in evidence is that a human asked something and the silence since then belongs to us. That is enough to act on, and treating it as insufficient is how threads rot: teams wait for the ticket record to catch up before replying, and the customer experiences the lag as being ignored rather than as being processed. The expert reading is that the reply owed here is not necessarily the answer — an acknowledgement that names what was asked, what happens next and who owns it discharges most of the obligation, and can be written before the diagnosis exists.

**Fires when** — all of these must hold:
- `{'path': 'thread.ball_in_court', 'op': '=', 'value': 'us'}` → 293 rows in production

**L2 types** `support_case, support_contact` — formed **14** times in production

**Progress** followup_sent, first_response_sent, callback_promised
**Decay** angry_language, escalation_requested, cancellation_threat

> **Decide:** is the description what you would want a card about, and is the priority right against the others? Approve or say what is wrong.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 12. Named Contact Gone Quiet

`customer_support.sit.named_contact_gone_quiet` · owner `customer_support.support_management.account_relationship_management` · priority **6800bp** · typical **30 days** · card: **draft_reengage** · authored confidence: *provisional* · last edited 2026-08-08

A named contact at a supported account has stopped writing in, and the gap is long relative to how often they used to. Nothing is broken, no clock is running, and no ticket is open — which is exactly the problem, because every instrument a support team owns is pointed at open work and this account has none. The expert reading is that silence from an account that used to file tickets is a hypothesis to be tested rather than a result to be enjoyed: either the product got better, or they found another way to get answers, or they stopped believing it was worth asking us. The test is cheap and it is not a survey — it is a specific message that references something real from their history and asks a question only they can answer. A generic check-in gets ignored, and being ignored converts a soft signal into no signal.

**Fires when** — all of these must hold:
- `{'fn': 'days_since', 'path': 'thread.last_inbound', 'op': '>=', 'value': mappingproxy({'baseline': 'reply_cadence', 'mult': 4, 'floor': 14})}` → 198 rows in production

**L2 types** `support_contact, relationship` — formed **4** times in production

**Progress** ticket_created, followup_sent, introduction, self_service_attempted
**Decay** champion_change, cancellation_threat, entitlement_expired

> **Decide:** is the description what you would want a card about, and is the priority right against the others? Approve or say what is wrong.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 13. New Account Contact

`customer_support.sit.new_account_contact` · owner `customer_support.support_management.account_relationship_management` · priority **5500bp** · typical **14 days** · card: **draft_reply** · authored confidence: *provisional* · last edited 2026-08-08

A new person has appeared on a supported account — introduced, handed over to, or simply copied in as the successor to someone who has gone. They arrive with the account's entire support history in our records and none of it in their head, and with no idea what the account is actually entitled to. The correct move is not a welcome message. It is a short, concrete orientation: what you are entitled to and through which channel, what is currently open, what has already been resolved that you may be about to re-report, and who to contact when it is urgent. This costs one message and prevents the first-contact failure that otherwise defines the relationship for a year. It is also, quietly, our own housekeeping — our records still name the person who left, and the ticket that gets routed to them is the one nobody answers.

**Fires when** — all of these must hold:
- `{'has_obs': 'introduction'}` → a condition on an **observation**, not a fact path

**L2 types** `support_contact, relationship` — formed **4** times in production

**Progress** introduction, followup_sent, entitlement_checked, ticket_created
**Decay** champion_change, escalation_requested, angry_language

> **Decide:** is the description what you would want a card about, and is the priority right against the others? Approve or say what is wrong.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 14. Promised Follow-up Overdue

`customer_support.sit.promised_followup_overdue` · owner `customer_support.entitlement_and_sla.commitment_tracking` · priority **9000bp** · typical **1 days** · card: **draft_delivery** · authored confidence: *provisional* · last edited 2026-08-08

Someone on our side said they would do a specific thing by a specific time, and that time has passed with nothing sent. The callback before end of day, the update on Friday, the bug that was going to be filed with engineering. These are the promises no contract created and no clock is watching, and they are the ones customers remember most sharply, because a human said them directly. The load-bearing expert judgement here is that the promise is discharged by CONTACT, not by COMPLETION: an update saying there is no news yet keeps the relationship whole, while silence — even silence spent working hard on the problem — is read as being forgotten. So the correct response to this situation is almost never to rush the underlying work. It is to write, today, with whatever is true, and to re-promise a date that will survive.

**Fires when** — all of these must hold:
- `{'exists': 'commitment.action'}` → 14 rows in production

**L2 types** `support_case, support_contact` — formed **14** times in production

**Progress** followup_sent, callback_promised, first_response_sent
**Decay** angry_language, escalation_requested, cancellation_threat

> **Decide:** is the description what you would want a card about, and is the priority right against the others? Approve or say what is wrong.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

### 15. Support Call Without Recap

`customer_support.sit.support_call_no_recap` · owner `customer_support.customer_communication.proactive_status_updates` · priority **7000bp** · typical **1 days** · card: **draft_recap** · authored confidence: *provisional* · last edited 2026-08-08

A call with the customer happened and nothing was written afterwards. The gap is not courtesy, it is custody: everything established on that call — what was reproduced, what was ruled out, what we said we would do next and by when — currently exists only as two people's recollection, and one of those people is going to be replaced by a colleague on the next shift. The recap is what converts a synchronous hour into a durable record, and it is also the customer's only chance to correct our understanding before we act on it. The expert discipline is that it goes out the same working day, in the customer's language rather than the engineer's, and that it separates what was OBSERVED from what was CONCLUDED — because the conclusion is the part most likely to be wrong and the part they can most usefully challenge.

**Fires when** — all of these must hold:
- `{'path': 'meeting.status', 'op': '=', 'value': 'completed'}` → 49 rows in production

**L2 types** `support_contact, relationship` — formed **4** times in production

**Progress** followup_sent, minutes_circulated, callback_promised, reproduction_confirmed
**Decay** agent_reassigned, escalation_requested, angry_language

> **Decide:** is the description what you would want a card about, and is the priority right against the others? Approve or say what is wrong.

    [ ] approve      [ ] change — what: ______      [ ] defer — why: ______

---

