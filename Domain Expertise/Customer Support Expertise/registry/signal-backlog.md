# Customer Support Expertise — signal backlog

> GENERATED — `python "Domain Expertise/_tools/backlog.py"`

Every row is a signal the authored expertise needs and the pipeline does not
emit. Ranked by how many inference patterns it unblocks, then by the confidence
of the strongest pattern waiting on it.

Rows marked `l2_situation_type` are the expensive ones. A blocked *pattern*
lowers one object's confidence; a blocked *situation* means the capability
behind it never compiles at all, and nothing errors or logs when it doesn't.

## Where the brain stands

- **78** patterns executable against the pipeline today
- **93** patterns blocked, waiting on **106** distinct signals
- **15** situation binding(s) waiting on an L2 type no pack emits
- Substrate today: **12** fact paths · **18** observation kinds · **1** baselines

## The backlog

| # | Signal | Kind | Owner | Unblocks | Top conf | Objects |
|---|---|---|---|---|---|---|
| 1 | `derived.contact_frequency` | derived | L2 | 6 | 9000 | Customer Sentiment, Entitlement, Escalation, Knowledge Article, Requester, Ticket |
| 2 | `angry_language` | obs_kind | L2 | 6 | 8200 | Commitment, Customer Sentiment, Escalation, Incident, Postmortem, Ticket |
| 3 | `incident_declared` | obs_kind | L2 | 5 | 10000 | Escalation, Incident, Postmortem |
| 4 | `entitlement.plan` | fact_path | L1 | 5 | 9500 | Entitlement, Postmortem, Requester, Ticket |
| 5 | `cancellation_threat` | obs_kind | L2 | 5 | 9200 | Commitment, Customer Sentiment, Escalation, Macro, Ticket |
| 6 | `csat.score` | fact_path | L1 | 5 | 9000 | Commitment, Customer Sentiment, Macro, SLA Target, Ticket |
| 7 | `entitlement.expires_at` | fact_path | L1 | 4 | 10000 | Entitlement, Postmortem, Ticket |
| 8 | `sla.clock_state` | fact_path | L1 | 4 | 10000 | Commitment, Escalation, SLA Target, Ticket |
| 9 | `sla.target_first_response_at` | fact_path | L1 | 4 | 10000 | Customer Sentiment, SLA Target, Ticket |
| 10 | `sla.target_resolution_at` | fact_path | L1 | 4 | 10000 | Commitment, SLA Target, Ticket |
| 11 | `macro_applied` | obs_kind | L2 | 4 | 9800 | Macro |
| 12 | `ticket.created_at` | fact_path | L1 | 4 | 9700 | Incident, Postmortem, Ticket |
| 13 | `escalation_requested` | obs_kind | L2 | 4 | 9500 | Escalation, Knowledge Article, Macro, Requester |
| 14 | `ticket.reopen_count` | fact_path | L1 | 4 | 9500 | Customer Sentiment, Escalation, Macro, Ticket |
| 15 | `derived.escalation_pressure` | derived | L2 | 4 | 9200 | Commitment, Incident, Postmortem, Ticket |
| 16 | `self_service_attempted` | obs_kind | L2 | 4 | 9200 | Incident, Knowledge Article, Requester |
| 17 | `contact_rate_per_account` | baseline | L2 | 4 | 9000 | Escalation, Knowledge Article, Requester, Ticket |
| 18 | `self_service_abandoned` | obs_kind | L2 | 4 | 8800 | Customer Sentiment, Incident, Knowledge Article, Requester |
| 19 | `account.renewal_at` | fact_path | L1 | 4 | 8000 | Customer Sentiment, Entitlement, Escalation, Ticket |
| 20 | `incident_resolved` | obs_kind | L2 | 3 | 10000 | Incident, Postmortem |
| 21 | `sla_breach` | obs_kind | L2 | 3 | 10000 | Customer Sentiment, Escalation, SLA Target |
| 22 | `entitlement.coverage_hours` | fact_path | L1 | 3 | 9500 | Entitlement, SLA Target |
| 23 | `incident.severity` | fact_path | L1 | 3 | 9500 | Incident, Postmortem |
| 24 | `incident.started_at` | fact_path | L1 | 3 | 9500 | Postmortem |
| 25 | `ticket_reopened` | obs_kind | L2 | 3 | 9500 | Knowledge Article, Macro, Ticket |
| 26 | `ticket_created` | obs_kind | L2 | 3 | 9200 | Incident, Knowledge Article |
| 27 | `csat_submitted` | obs_kind | L2 | 3 | 9000 | Customer Sentiment, Macro, Ticket |
| 28 | `knowledge_article_linked` | obs_kind | L2 | 3 | 7500 | Knowledge Article, Macro |
| 29 | `account.arr` | fact_path | L1 | 3 | 7000 | Entitlement, Escalation, Ticket |
| 30 | `first_response_time` | baseline | L2 | 3 | 7000 | Incident, Postmortem, SLA Target |
| 31 | `commitment.state` | fact_path | L1 | 2 | 10000 | Commitment |
| 32 | `escalation_accepted` | obs_kind | L2 | 2 | 10000 | Escalation |
| 33 | `incident.status` | fact_path | L1 | 2 | 10000 | Incident, Postmortem |
| 34 | `ticket.assignee` | fact_path | L1 | 2 | 10000 | Escalation, Ticket |
| 35 | `ticket.status` | fact_path | L1 | 2 | 10000 | Commitment, Ticket |
| 36 | `ticket.first_response_at` | fact_path | L1 | 2 | 9800 | SLA Target, Ticket |
| 37 | `entitlement_checked` | obs_kind | L2 | 2 | 9500 | Entitlement, Requester |
| 38 | `commitment.owner` | fact_path | L1 | 2 | 9200 | Commitment |
| 39 | `commitment.recipient` | fact_path | L1 | 2 | 9200 | Commitment |
| 40 | `product.released_at` | fact_path | L1 | 2 | 9000 | Knowledge Article, Macro |
| 41 | `product.surface_version` | fact_path | L1 | 2 | 9000 | Knowledge Article, Macro |
| 42 | `agent_reassigned` | obs_kind | L2 | 2 | 8800 | Escalation |
| 43 | `bug_fixed` | obs_kind | L2 | 2 | 8600 | Macro, Postmortem |
| 44 | `ticket.queue` | fact_path | L1 | 2 | 8600 | Incident, Macro |
| 45 | `bug_filed` | obs_kind | L2 | 2 | 8500 | Postmortem, Ticket |
| 46 | `derived.backlog_age` | derived | L2 | 2 | 8500 | Incident, SLA Target |
| 47 | `reproduction_confirmed` | obs_kind | L2 | 2 | 8500 | Escalation, Requester |
| 48 | `ticket_volume` | baseline | L2 | 2 | 8500 | Incident, Macro |
| 49 | `macro.body_text` | fact_path | L1 | 2 | 8000 | Macro |
| 50 | `bug_awaiting_engineering` | l2_situation_type | L2 | 1 | 10000 | [situation] Bug Awaiting Engineering |
| 51 | `csat_detractor` | l2_situation_type | L2 | 1 | 10000 | [situation] CSAT Detractor |
| 52 | `entitlement_expired` | l2_situation_type | L2 | 1 | 10000 | [situation] Entitlement Expired |
| 53 | `entitlement_mismatch` | l2_situation_type | L2 | 1 | 10000 | [situation] Entitlement Expired |
| 54 | `escalation_requested` | l2_situation_type | L2 | 1 | 10000 | [situation] Escalation Requested |
| 55 | `first_response_overdue` | l2_situation_type | L2 | 1 | 10000 | [situation] SLA Breach Imminent |
| 56 | `incident_unresolved` | l2_situation_type | L2 | 1 | 10000 | [situation] Major Incident Declared |
| 57 | `knowledge_gap` | l2_situation_type | L2 | 1 | 10000 | [situation] Repeat Contact |
| 58 | `major_incident_declared` | l2_situation_type | L2 | 1 | 10000 | [situation] Major Incident Declared |
| 59 | `queue_overloaded` | l2_situation_type | L2 | 1 | 10000 | [situation] Queue Overloaded |
| 60 | `repeat_contact` | l2_situation_type | L2 | 1 | 10000 | [situation] Repeat Contact |
| 61 | `sla_breach_imminent` | l2_situation_type | L2 | 1 | 10000 | [situation] SLA Breach Imminent |
| 62 | `ticket_aging` | l2_situation_type | L2 | 1 | 10000 | [situation] Queue Overloaded |
| 63 | `ticket_reopened` | l2_situation_type | L2 | 1 | 10000 | [situation] Ticket Reopened |
| 64 | `workaround_only` | l2_situation_type | L2 | 1 | 10000 | [situation] Bug Awaiting Engineering |
| 65 | `first_response_sent` | obs_kind | L2 | 1 | 9800 | SLA Target |
| 66 | `macro.edit_distance_at_send` | fact_path | L1 | 1 | 9800 | Macro |
| 67 | `macro.macro_ref` | fact_path | L1 | 1 | 9800 | Macro |
| 68 | `incident.detected_at` | fact_path | L1 | 1 | 9500 | Postmortem |
| 69 | `knowledge.owner_id` | fact_path | L1 | 1 | 9500 | Knowledge Article |
| 70 | `leaver_confirmed` | obs_kind | L2 | 1 | 9500 | Knowledge Article |
| 71 | `callback_promised` | obs_kind | L2 | 1 | 9200 | Commitment |
| 72 | `knowledge.viewed_at` | fact_path | L1 | 1 | 9200 | Knowledge Article |
| 73 | `root_cause_identified` | obs_kind | L2 | 1 | 9200 | Postmortem |
| 74 | `account.contact_role` | fact_path | L1 | 1 | 9000 | Requester |
| 75 | `derived.affected_account_count` | derived | L2 | 1 | 9000 | Incident |
| 76 | `entitlement_expired` | obs_kind | L2 | 1 | 9000 | Entitlement |
| 77 | `ticket.resolved_at` | fact_path | L1 | 1 | 9000 | SLA Target |
| 78 | `derived.sentiment_by_author` | derived | L2 | 1 | 8800 | Customer Sentiment |
| 79 | `rca_requested` | obs_kind | L2 | 1 | 8800 | Postmortem |
| 80 | `search.query_text` | fact_path | L1 | 1 | 8800 | Knowledge Article |
| 81 | `search.result_count` | fact_path | L1 | 1 | 8800 | Knowledge Article |
| 82 | `commitment_renegotiated` | obs_kind | L2 | 1 | 8500 | Commitment |
| 83 | `derived.sentiment_prior` | derived | L2 | 1 | 8500 | Customer Sentiment |
| 84 | `derived.sentiment_trend` | derived | L2 | 1 | 8500 | Customer Sentiment |
| 85 | `diagnostic_artifact_attached` | obs_kind | L2 | 1 | 8500 | Requester |
| 86 | `entitlement.seat_count` | fact_path | L1 | 1 | 8500 | Entitlement |
| 87 | `entitlement.seats_in_use` | fact_path | L1 | 1 | 8500 | Entitlement |
| 88 | `handoff_to_engineering` | obs_kind | L2 | 1 | 8500 | Postmortem |
| 89 | `macro.use_count_30d` | fact_path | L1 | 1 | 8500 | Macro |
| 90 | `ticket.channel` | fact_path | L1 | 1 | 8500 | Entitlement |
| 91 | `workaround_provided` | obs_kind | L2 | 1 | 8500 | Ticket |
| 92 | `blame_attribution` | obs_kind | L2 | 1 | 8000 | Postmortem |
| 93 | `conversation.language` | fact_path | L1 | 1 | 8000 | Requester |
| 94 | `derived.macro_similarity` | derived | L2 | 1 | 8000 | Macro |
| 95 | `derived.requester_active_hours` | derived | L2 | 1 | 8000 | Requester |
| 96 | `customer_tone_baseline` | baseline | L2 | 1 | 7800 | Customer Sentiment |
| 97 | `account.health_score` | fact_path | L1 | 1 | 7500 | Customer Sentiment |
| 98 | `derived.backlog_age` | fact_path | L2 | 1 | 7500 | Postmortem |
| 99 | `entitlement.named_contacts` | fact_path | L1 | 1 | 7500 | Entitlement |
| 100 | `knowledge.body_text` | fact_path | L1 | 1 | 7200 | Macro |
| 101 | `commitment_delivery_rate` | baseline | L2 | 1 | 7000 | Commitment |
| 102 | `derived.escalation_pressure` | fact_path | L2 | 1 | 7000 | Requester |
| 103 | `sla_clock_paused` | obs_kind | L2 | 1 | 7000 | SLA Target |
| 104 | `article_link_rate` | baseline | L2 | 1 | 6800 | Knowledge Article |
| 105 | `knowledge.view_count_30d` | fact_path | L1 | 1 | 3500 | Knowledge Article |
| 106 | `knowledge_feedback_submitted` | obs_kind | L2 | 1 | 3500 | Knowledge Article |

## Why each one matters

### `derived.contact_frequency` · derived

- blocks **Customer Sentiment** / `cs.sent.reopened_or_repeat_contact` (would yield 8200 bp)
- blocks **Entitlement** / `ent.serving_beyond_what_was_bought` (would yield 6500 bp)
- blocks **Escalation** / `esc.the_diagnosis_restarted` (would yield 7500 bp)
- blocks **Knowledge Article** / `ka.repeat_contact_after_self_service` (would yield 7000 bp)
- blocks **Requester** / `req.repeat_contact_inside_a_week` (would yield 9000 bp)
- blocks **Ticket** / `ticket.repeat_contact_from_the_same_account` (would yield 7500 bp)
- Customer Sentiment: Needed to catch repeat contact that arrives as new tickets rather than reopens, which is what happens whenever the customer uses a different channel.
- Entitlement: Support effort is entirely invisible today — the substrate can see a thread going quiet but not an account consuming four times its tier. Over-service is therefore undetectable until the renewal, which is the latest and most expensive moment to find it.
- Escalation: Needed to separate a genuine re-diagnosis from routine follow-up. Without it this pattern flags every reassignment and gets muted within a week.
- Knowledge Article: Already planned. Needs to be sliced by intent, not just by account — an account contacting more overall is not the same as an account contacting again about the SAME thing.
- Requester: The highest-value missing signal on this object. Three individually reasonable tickets from one person in a week is a content gap, a product defect or a failed first resolution, and it is invisible to every capability that reads one ticket at a time. Everything the executable graph-degree heuristic below approximates, this would state.
- Ticket: Repeat contact is where support stops being reactive. Three tickets from one account in a week is a different object from three unrelated tickets, and today the queue cannot see the difference — each one is read as a fresh surprise by a different agent.

### `angry_language` · obs_kind

- blocks **Commitment** / `commitment.broken_promise_became_a_cancellation_conversation` (would yield 8200 bp)
- blocks **Customer Sentiment** / `cs.sent.hostile_language_first_occurrence` (would yield 7800 bp)
- blocks **Escalation** / `esc.the_customer_threatened_to_leave` (would yield 8000 bp)
- blocks **Incident** / `incident.synchronised_angry_language` (would yield 6500 bp)
- blocks **Postmortem** / `postmortem.blame_language_in_the_timeline` (would yield 8000 bp)
- blocks **Ticket** / `ticket.escalation_pressure_building` (would yield 8000 bp)
- Commitment: derived.sentiment is a thread-level balance and reads a formally worded complaint as near-neutral. A discrete observation on the specific message is what allows "this one message changed everything" rather than a slowly drifting average.

- Customer Sentiment: Worth having and worth distrusting in equal measure. Profanity detectors fire on quoted error messages, on stack traces and on people who swear cheerfully at everyone, which is why this needs baseline_temperament beside it to mean anything. The valuable part is not the classification, it is the timestamp of the FIRST occurrence in a relationship — that moment is the strongest de-escalation trigger in support and nothing currently records it.
- Escalation: Separate from the threat and separately useful. Anger without a threat is a de-escalation problem; a threat without anger is a commercial one, and they get opposite responses.
- Postmortem: Distinct signal, related failure. A review thread carrying anger is one where the blameless contract has already broken, whether or not a name was typed.

### `incident_declared` · obs_kind

- blocks **Escalation** / `esc.absorbed_into_a_declared_incident` (would yield 8500 bp)
- blocks **Incident** / `incident.declared_on_the_record` (would yield 10000 bp)
- blocks **Postmortem** / `postmortem.communication_failure_went_unexamined` (would yield 7500 bp)
- blocks **Postmortem** / `postmortem.exists_and_was_reviewed` (would yield 10000 bp)
- blocks **Postmortem** / `postmortem.timeline_is_recollection` (would yield 7000 bp)
- Escalation: 8500 and not higher because absorption is a judgement about shared cause, and escalations get folded into incidents that do not actually explain them — which then leaves the customer with no owner at all once the incident closes. The absorption must be reversible.
- Incident: The highest-value missing signal in the entire support domain. Declaration is a deliberate human act with a timestamp and an author — the cheapest possible signal to capture and the one everything else on this object hangs from.
- Postmortem: Nothing in the pipeline can establish that an incident happened, let alone that it was reviewed. Every attribute on this object is therefore populated by a human typing into a wiki, and this brain's knowledge of postmortems is knowledge of what SHOULD be there.

- Postmortem: The gap between declaration and the first broadcast is support's half of the incident and the half most often absent from the review, because engineering owns the document and the comms failure belongs to whoever was answering tickets at 3am. Customers forgive the fault; they narrate the silence.


### `entitlement.plan` · fact_path

- blocks **Entitlement** / `ent.channel_used_outside_entitlement` (would yield 8500 bp)
- blocks **Entitlement** / `ent.plan_of_record` (would yield 9500 bp)
- blocks **Postmortem** / `postmortem.customer_rca_owed_and_late` (would yield 8800 bp)
- blocks **Requester** / `req.named_contact_on_the_plan` (would yield 9500 bp)
- blocks **Ticket** / `ticket.priority_should_outrank_severity_here` (would yield 7000 bp)
- Entitlement: Not 10000 even from a system of record, because the plan field is what an enterprise agreement most often overrides in a side letter the billing system never sees. Absent this, `plan` is populated by agent assertion, which means the tier is whatever the last person to look believed.
- Entitlement: The channel list hangs off the plan. Without the tier there is nothing to compare the arriving channel against.
- Requester: Plans are in billing systems and CRMs that L1 already connects to; nothing projects the covered-contact list into a typed fact. Without it the system cannot distinguish an uncovered person at a covered company, which is the most common entitlement argument there is.
- Postmortem: Written RCAs are an entitlement line item at enterprise tiers with a stated turnaround, usually five business days. It is the only deadline attached to this object that anyone outside the company can enforce, which is exactly why it wins by default and drags the internal document into the customer document's shape — the failure this object's fourth claim is about.


### `cancellation_threat` · obs_kind

- blocks **Commitment** / `commitment.broken_promise_became_a_cancellation_conversation` (would yield 8200 bp)
- blocks **Customer Sentiment** / `cs.sent.explicit_cancellation_language` (would yield 9200 bp)
- blocks **Escalation** / `esc.the_customer_threatened_to_leave` (would yield 8000 bp)
- blocks **Macro** / `macro.preceded_an_escalation` (would yield 7000 bp)
- blocks **Ticket** / `ticket.escalation_pressure_building` (would yield 8000 bp)
- Commitment: Stated in plain language in threads we already ingest, and extracted by nothing. It is the moment a broken callback stops being a support cost and becomes a revenue one, and it is the single observation most likely to change what an organisation does about promise tracking.

- Customer Sentiment: The clearest sentiment statement a customer ever makes and the pipeline cannot see it. Note this is not the same as churn: most cancellation threats are bids for attention rather than decisions, which is why 9200 and not 10000 — it is near-certain evidence about feeling and weak evidence about intent, and treating it as the second is how support teams get held to ransom.
- Escalation: closed_lost_mention exists in the substrate today and is the near neighbour, but it is scoped to a deal and means the opposite thing — a prospect declining to buy, not a customer leaving. Binding this to it would produce an escalation brain that fires on lost deals, which is precisely the false-coverage failure the domain header warns about.
- Ticket: The single highest-value missing observation for this domain. It is the moment support stops being a cost centre question and becomes a revenue one, it is stated in plain language in the thread, and the extractor whitelist does not include it.
- Macro: The louder version of the same event. A macro that reliably precedes cancellation language has found the exact sentence at which a customer decides we are not worth talking to, and that is the single most valuable thing this object could ever tell anyone.


### `csat.score` · fact_path

- blocks **Commitment** / `commitment.met_every_clock_and_still_broke_our_word` (would yield 8000 bp)
- blocks **Customer Sentiment** / `cs.sent.survey_answer_corroborates_the_read` (would yield 7000 bp)
- blocks **Macro** / `macro.detractor_after_a_canned_reply` (would yield 6500 bp)
- blocks **SLA Target** / `sla.met_the_number_and_failed_the_customer` (would yield 9000 bp)
- blocks **Ticket** / `ticket.detractor_after_resolution` (would yield 9000 bp)
- Commitment: The falsifier. If green SLAs with broken commitments do NOT score worse than red SLAs with kept ones, the thesis of this object is wrong and the weights below should be rebuilt. Authoring the disconfirming signal alongside the claim is the point.

- SLA Target: The only thing that can falsify an SLA programme. Without it, 'we hit our targets' is unfalsifiable — which is exactly why targets get set where they can be hit.
- Ticket: Ranked below reopens deliberately. A survey score is cheap for the customer to give and cheap to game with a well-timed ask; a reopen costs them effort and cannot be prompted. Both are worth having and the reopen is worth more.

### `entitlement.expires_at` · fact_path

- blocks **Entitlement** / `ent.expired_by_date_of_record` (would yield 10000 bp)
- blocks **Entitlement** / `ent.expiry_lands_inside_open_work` (would yield 8000 bp)
- blocks **Postmortem** / `postmortem.customer_rca_owed_and_late` (would yield 8800 bp)
- blocks **Ticket** / `ticket.entitlement_lapsed_at_intake` (would yield 9700 bp)
- Entitlement: The highest-value missing signal in this entire domain. Without it, expiry is invisible: no state changes, no event fires, and the agent keeps reading a cached `premium` for months. Every over-service incident this object is meant to prevent starts here. It is a date on a contract already in a billing system — the ask is projection, not extraction.
- Entitlement: The genuinely nasty case, and the one nobody plans for: work committed in term, delivered out of term. Whether the original entitlement still governs is a real contractual question, and today it surfaces as an argument rather than a flag.
- Ticket: Checked, never assumed — and today not checkable at all. An expired-entitlement ticket gets worked anyway because refusing it in the moment feels worse than absorbing the cost, so the cost lands in a margin nobody attributes to support.

### `sla.clock_state` · fact_path

- blocks **Commitment** / `commitment.met_every_clock_and_still_broke_our_word` (would yield 8000 bp)
- blocks **Escalation** / `esc.clock_breach_triggered_it` (would yield 9000 bp)
- blocks **SLA Target** / `sla.clock_state_from_the_ticketing_system` (would yield 10000 bp)
- blocks **Ticket** / `ticket.clock_breached` (would yield 10000 bp)
- Commitment: The comparison this whole object exists to make, and it is not currently expressible: the commitment side is emitted and the SLA side is not, so the two can never be put beside each other. This is the pattern that would prove the file's central claim to a sceptical executive, and it is the reason SLA attainment reports and customer satisfaction reports disagree in almost every support organisation.

- Escalation: The clock STATE is as load-bearing as the breach — a breach recorded while the clock was paused on the customer is not our failure, and auto-escalating it burns receiver credibility on a false positive. Without clock_state this pattern would be actively harmful, which is why both signals are required rather than one.
- SLA Target: Authoritative where the thread proxies are inferential. Worth noting that having this does NOT retire the proxies — the interesting cases are precisely where the vendor field and the thread disagree, and you need both to see that.
- Ticket: Without clock_state, elapsed time cannot be distinguished from owed time, and every pause looks like negligence.

### `sla.target_first_response_at` · fact_path

- blocks **Customer Sentiment** / `cs.sent.first_response_clock_breached` (would yield 8000 bp)
- blocks **SLA Target** / `sla.breach_imminent_against_the_real_target` (would yield 8500 bp)
- blocks **SLA Target** / `sla.target_timestamp_from_the_ticketing_system` (would yield 10000 bp)
- blocks **Ticket** / `ticket.first_response_overdue` (would yield 9800 bp)
- Customer Sentiment: The machine-readable form of 'nobody has told me anything yet'. It is the cleanest possible uncertainty-attribution signal because it is a fact about us with a timestamp, and it needs no language model at all.
- SLA Target: The actual deadline. Every executable pattern above is a proxy for this one field, and each proxy is weaker in a different direction — this is the highest-value single ask this object generates.

### `sla.target_resolution_at` · fact_path

- blocks **Commitment** / `commitment.met_every_clock_and_still_broke_our_word` (would yield 8000 bp)
- blocks **SLA Target** / `sla.target_timestamp_from_the_ticketing_system` (would yield 10000 bp)
- blocks **SLA Target** / `sla.the_clock_was_never_survivable` (would yield 8000 bp)
- blocks **Ticket** / `ticket.clock_breached` (would yield 10000 bp)
- SLA Target: Separate from first response and must stay separate. A pack that projects one 'sla_due' field has already made the error this object is built to prevent.

### `macro_applied` · obs_kind

- blocks **Macro** / `macro.detractor_after_a_canned_reply` (would yield 6500 bp)
- blocks **Macro** / `macro.followed_by_a_reopen` (would yield 8800 bp)
- blocks **Macro** / `macro.preceded_an_escalation` (would yield 7000 bp)
- blocks **Macro** / `macro.sent_without_a_single_edit` (would yield 9800 bp)
- Macro: The foundational miss for this object. Every helpdesk records which macro an agent inserted; none of it reaches Layer 2, so a support brain cannot tell a written reply from a pasted one. Without this observation every other pattern here is inferring from thread shape what the tool knows for certain.


### `ticket.created_at` · fact_path

- blocks **Incident** / `incident.blast_radius_from_distinct_affected_accounts` (would yield 9000 bp)
- blocks **Postmortem** / `postmortem.detection_gap_is_the_headline` (would yield 9500 bp)
- blocks **Postmortem** / `postmortem.timeline_is_recollection` (would yield 7000 bp)
- blocks **Ticket** / `ticket.entitlement_lapsed_at_intake` (would yield 9700 bp)
- Incident: Needed to bound the count to a window. Without it the count accumulates forever and every long-lived issue eventually looks like an incident.
- Postmortem: The cheapest available proxy for started_at and often the most accurate one — the first ticket usually predates the first alert. This is the argument for support owning the detection timeline rather than merely attending the meeting.

- Postmortem: Ticket arrival times are artefacts and they are free. A timeline anchored on them is checkable by anyone; one anchored on "I think it was around nine" is a set of plausible durations that will be quoted as fact in a board pack within a month.


### `escalation_requested` · obs_kind

- blocks **Escalation** / `esc.customer_asked_for_a_manager` (would yield 9500 bp)
- blocks **Knowledge Article** / `ka.read_then_escalated` (would yield 7500 bp)
- blocks **Macro** / `macro.preceded_an_escalation` (would yield 7000 bp)
- blocks **Requester** / `req.escalation_prone_from_history` (would yield 7000 bp)
- Escalation: The single highest-value missing signal for this object and probably for the domain. The phrasing is stereotyped across every language and channel support runs on — 'can I speak to', 'who is your manager', 'escalate this' — so extraction is unusually tractable. Not 10000 even when it lands: customers say it rhetorically and withdraw it in the next message.
- Knowledge Article: Planned. Needed with a path back to what the customer was shown before they asked for a manager.
- Requester: There is no escalation signal of any kind in the substrate, so escalation history — one of the most predictive facts about a requester — is entirely unobservable today.
- Macro: Needed with a path back to what the customer was actually shown before they asked for someone else. Escalations are recorded with a reason field that never contains the reply that caused them.

### `ticket.reopen_count` · fact_path

- blocks **Customer Sentiment** / `cs.sent.reopened_or_repeat_contact` (would yield 8200 bp)
- blocks **Escalation** / `esc.repeat_contact_on_the_same_problem` (would yield 7200 bp)
- blocks **Macro** / `macro.followed_by_a_reopen` (would yield 8800 bp)
- blocks **Ticket** / `ticket.reopened_by_the_customer` (would yield 9500 bp)
- Customer Sentiment: Repeat contact compounds sentiment non-linearly and is completely invisible to any per-message read — each individual message can be perfectly polite while the sequence is a disaster. Authored at 8200 rather than higher because a reopen is sometimes a compliment: the customer came back to us rather than giving up.
- Escalation: The cheapest strong escalation predictor in support, and it needs no NLP — it is a counter. Its absence is why this brain currently cannot tell a first contact from a fourth.

### `derived.escalation_pressure` · derived

- blocks **Commitment** / `commitment.broken_promise_became_a_cancellation_conversation` (would yield 8200 bp)
- blocks **Incident** / `incident.synchronised_angry_language` (would yield 6500 bp)
- blocks **Postmortem** / `postmortem.this_has_been_written_before` (would yield 9200 bp)
- blocks **Ticket** / `ticket.escalation_pressure_building` (would yield 8000 bp)
- Incident: Must be readable across accounts, not per-ticket. Per-ticket anger says nothing; the same anger appearing in unrelated accounts within an hour says one thing broke.
- Ticket: A single angry message is not pressure. Accumulation over a thread is, and only L2 can accumulate it.
- Postmortem: Second and third occurrences generate materially different customer behaviour from first ones, and the accumulation is the part only L2 can compute.

### `self_service_attempted` · obs_kind

- blocks **Incident** / `incident.self_service_spike_precedes_the_queue` (would yield 6000 bp)
- blocks **Knowledge Article** / `ka.repeat_contact_after_self_service` (would yield 7000 bp)
- blocks **Knowledge Article** / `ka.viewed_then_contacted` (would yield 9200 bp)
- blocks **Requester** / `req.read_the_docs_before_writing_in` (would yield 8000 bp)
- Knowledge Article: Distinguishes a read from a skim. Without it the window is the only discriminator and it will over-attribute.
- Requester: Today both requesters arrive identical and both get the article link back. Sending the doc to someone who already read it is the most reliable way to turn a calm contact into an angry one, and it is entirely avoidable.

### `contact_rate_per_account` · baseline

- blocks **Escalation** / `esc.repeat_contact_on_the_same_problem` (would yield 7200 bp)
- blocks **Knowledge Article** / `ka.repeat_contact_after_self_service` (would yield 7000 bp)
- blocks **Requester** / `req.repeat_contact_inside_a_week` (would yield 9000 bp)
- blocks **Ticket** / `ticket.repeat_contact_from_the_same_account` (would yield 7500 bp)
- Escalation: Three contacts in a week is normal for a heavy integrator and alarming for a quiet one. Without the per-account baseline this fires on the customers who use the product most, which is the exact inverse of the intent.
- Knowledge Article: Needed so 'shortly after' means something relative to how often this account contacts us anyway. Absolute windows mis-fire badly on high-touch enterprise accounts.
- Requester: Needed to make frequency readable — a power user's fourth contact is noise, a quiet customer's second is a signal, and an absolute threshold cannot tell them apart.
- Ticket: Needed to make 'repeatedly' relative. A hundred-seat account opening four tickets a week is normal; a two-seat account doing the same is a churn signal.

### `self_service_abandoned` · obs_kind

- blocks **Customer Sentiment** / `cs.sent.calm_and_leaving` (would yield 7500 bp)
- blocks **Incident** / `incident.self_service_spike_precedes_the_queue` (would yield 6000 bp)
- blocks **Knowledge Article** / `ka.searched_for_and_not_found` (would yield 8800 bp)
- blocks **Requester** / `req.read_the_docs_before_writing_in` (would yield 8000 bp)
- Customer Sentiment: The behavioural tell of the calm leaver: they still have the problem, they have stopped asking us about it, and they went looking themselves and gave up.
- Incident: Attempted alone is meaningless — abandonment is the tell, because it means the article did not answer what people are hitting right now.
- Knowledge Article: Search-then-leave without opening anything. Distinguishes a vocabulary mismatch from a genuine content gap, which need opposite fixes: synonyms versus writing.
- Requester: The stronger half: where they gave up names the content gap precisely, which is what content_gap_analysis needs and cannot get from the ticket text.

### `account.renewal_at` · fact_path

- blocks **Customer Sentiment** / `cs.sent.calm_and_leaving` (would yield 7500 bp)
- blocks **Entitlement** / `ent.expiry_lands_inside_open_work` (would yield 8000 bp)
- blocks **Escalation** / `esc.high_value_account_is_waiting` (would yield 6000 bp)
- blocks **Ticket** / `ticket.priority_should_outrank_severity_here` (would yield 7000 bp)
- Customer Sentiment: The context that turns a benign quiet into an emergency. `dangerous_calm` above is stuck at 6000 precisely because it cannot see this: the same collapsed engagement is a shrug eleven months before renewal and a five-alarm fire six weeks before it. One date changes the whole read.
- Entitlement: Needed to tell a lapse from a renewal in progress. The two demand opposite handling — one stops the promise, the other extends the grace — and without renewal_at they are the same date.
- Escalation: Proximity to renewal compresses the window far more than revenue size does. A modest account six weeks from renewal deserves an earlier escalation than a large one eleven months out, and any implementation that reads only ARR will get that backwards.
- Ticket: The severity/priority inversion is the most valuable judgement in triage and it is entirely unavailable to the engine today: nothing commercial about the account is visible on a support node.

### `incident_resolved` · obs_kind

- blocks **Incident** / `incident.resolved_on_the_record` (would yield 9800 bp)
- blocks **Postmortem** / `postmortem.exists_and_was_reviewed` (would yield 10000 bp)
- blocks **Postmortem** / `postmortem.owed_by_severity` (would yield 9000 bp)
- Incident: Ends the incident clock and nothing else. Covered tickets stay open, the issue stays open, and a system that conflates the three will close forty tickets on customers who were never told anything.
- Postmortem: A postmortem written while impact is live competes with the response for the same five people. Knowing the incident is closed is the precondition for the whole object.

### `sla_breach` · obs_kind

- blocks **Customer Sentiment** / `cs.sent.first_response_clock_breached` (would yield 8000 bp)
- blocks **Escalation** / `esc.clock_breach_triggered_it` (would yield 9000 bp)
- blocks **SLA Target** / `sla.breach_emitted_by_the_platform` (would yield 10000 bp)
- Customer Sentiment: Needed to distinguish a breach from a paused clock; without the pause state a weekend reads as a breach and the read fires on every ticket on Monday.
- SLA Target: Cheap for L2 to emit and immediately useful. Pair it with sla_clock_paused, or a breach arrives with no explanation of which minutes counted, which is a notification rather than a finding.

### `entitlement.coverage_hours` · fact_path

- blocks **Entitlement** / `ent.commitment_lands_outside_coverage` (would yield 8000 bp)
- blocks **Entitlement** / `ent.coverage_of_record` (would yield 9500 bp)
- blocks **SLA Target** / `sla.the_clock_was_never_survivable` (would yield 8000 bp)
- Entitlement: Without it, coverage is inferred from the plan tier, and tier-to-coverage mapping is exactly the thing custom agreements break. The failure is silent and one-directional: nobody complains about being covered too widely.
- Entitlement: commitment.due_at is already live, which makes this the cheapest high-value pattern in the file: one missing field away from executable. It catches the Friday-evening callback promised to a business-hours account — a breach created at the moment of promising, hours before anyone could notice it.
- SLA Target: Turns a breach postmortem into a coverage decision. These breaches are not agent failures and treating them as such is how coaching time gets spent on a rota problem — the fix is a shift pattern or a renegotiated clock, and neither is visible from the ticket.

### `incident.severity` · fact_path

- blocks **Incident** / `incident.severity_recorded_by_the_incident_tool` (would yield 9500 bp)
- blocks **Postmortem** / `postmortem.owed_by_severity` (would yield 9000 bp)
- blocks **Postmortem** / `postmortem.this_has_been_written_before` (would yield 9200 bp)
- Incident: Severity is a human blast-radius judgement made under pressure and it is the most reusable artefact the whole event produces — it is what a postmortem argues about and what the next declaration is calibrated against. Currently discarded.
- Postmortem: The trigger most organisations actually use, and the one this object's first exception argues is insufficient on its own — severity is not the only thing that earns a review, and a four-minute outage with a six-hour detection gap earns one at any severity.


### `incident.started_at` · fact_path

- blocks **Postmortem** / `postmortem.communication_failure_went_unexamined` (would yield 7500 bp)
- blocks **Postmortem** / `postmortem.detection_gap_is_the_headline` (would yield 9500 bp)
- blocks **Postmortem** / `postmortem.owed_by_severity` (would yield 9000 bp)
- Postmortem: The highest-value missing signal for this object by a wide margin, and it is not close. Detection lag is the cheapest gap in an incident to close — usually a threshold on a metric that already exists — and it is the only one with no owner, no budget line and no slide, because the fix belongs to engineering and the gap belongs to nobody. Without started_at, every duration on this object is measured from when we noticed, which silently deletes the finding from the document that exists to produce it.


### `ticket_reopened` · obs_kind

- blocks **Knowledge Article** / `ka.read_then_escalated` (would yield 7500 bp)
- blocks **Macro** / `macro.followed_by_a_reopen` (would yield 8800 bp)
- blocks **Ticket** / `ticket.reopened_by_the_customer` (would yield 9500 bp)
- Knowledge Article: A reopen after an article link is the same failure in a quieter register — the answer was accepted, tried, and did not hold.
- Ticket: Reopens are the only quality signal that costs the customer effort to send, which makes them harder to game than any survey. Cheaper to emit than CSAT and more informative, and currently emitted by nothing.
- Macro: The quality signal a customer has to spend effort to send, which is what makes it harder to game than any survey. Joined to a macro, it is the closest thing available to proof that a canned answer did not hold.


### `ticket_created` · obs_kind

- blocks **Incident** / `incident.same_area_across_unrelated_accounts` (would yield 8600 bp)
- blocks **Incident** / `incident.ticket_creation_burst_above_baseline` (would yield 8000 bp)
- blocks **Knowledge Article** / `ka.viewed_then_contacted` (would yield 9200 bp)
- Incident: The atom of the entire domain. Nothing emits it.
- Knowledge Article: Needed with a requester identity so the view and the contact can be joined. Unjoined, both events are already collected and neither means anything.

### `csat_submitted` · obs_kind

- blocks **Customer Sentiment** / `cs.sent.survey_answer_corroborates_the_read` (would yield 7000 bp)
- blocks **Macro** / `macro.detractor_after_a_canned_reply` (would yield 6500 bp)
- blocks **Ticket** / `ticket.detractor_after_resolution` (would yield 9000 bp)
- Customer Sentiment: Deliberately authored as corroboration at 7000 rather than as ground truth at 9500, which is where most teams would put it. A survey is answered by a self-selected minority, arrives after the feeling has already changed, and is heavily influenced by whether the last agent was likeable. It is the best evidence we will get about a past moment and poor evidence about the present one. Its real value is not the read — it is the calibration pair against whatever this object inferred at the time.
- Macro: Needed with the send so the score can be attributed to the reply that produced it rather than to the ticket in general.

### `knowledge_article_linked` · obs_kind

- blocks **Knowledge Article** / `ka.agents_route_around_it` (would yield 6800 bp)
- blocks **Knowledge Article** / `ka.read_then_escalated` (would yield 7500 bp)
- blocks **Macro** / `macro.diverged_from_its_article` (would yield 7200 bp)
- Knowledge Article: Already planned. The link event is the observable; the absence of it, on an intent this article covers, is the signal.
- Macro: Establishes that the two are meant to be the same answer. Without it, divergence cannot be distinguished from two macros that were never related.

### `account.arr` · fact_path

- blocks **Entitlement** / `ent.serving_beyond_what_was_bought` (would yield 6500 bp)
- blocks **Escalation** / `esc.high_value_account_is_waiting` (would yield 6000 bp)
- blocks **Ticket** / `ticket.priority_should_outrank_severity_here` (would yield 7000 bp)
- Entitlement: The denominator. Without it there is no cost-to-serve, and 'this account is expensive' stays an anecdote a support manager cannot escalate.

### `first_response_time` · baseline

- blocks **Incident** / `incident.first_response_time_collapses_against_baseline` (would yield 5500 bp)
- blocks **Postmortem** / `postmortem.timeline_is_recollection` (would yield 7000 bp)
- blocks **SLA Target** / `sla.systematic_pause_gaming` (would yield 7000 bp)
- SLA Target: The peer comparison. Absolute pause counts are meaningless — some queues genuinely need more information from customers. Only the deviation carries a signal, and only at team level; run this per-agent and you will build a metric that teaches people to stop asking necessary questions.
- Postmortem: Needed to tell an abnormal response window during the incident from a normal one, which is what turns a raw timestamp into a comms finding.

### `commitment.state` · fact_path

- blocks **Commitment** / `commitment.declared_state_from_the_system_of_record` (would yield 10000 bp)
- blocks **Commitment** / `commitment.renegotiated_before_the_due_time` (would yield 8500 bp)
- Commitment: Would let a declared state be compared against the inferred one, which is the comparison that matters: where an agent has marked a promise kept and the thread shows nothing went out, the disagreement is the finding. Ranked below the extraction signal above because most organisations have no commitment record at all to project — this field is usually a free-text note, which is precisely why promises are the least-tracked obligation in support.

- Commitment: Needed to chain the successor to the original. Without it a reset overwrites, the chain disappears, and serial overpromising becomes invisible — each individual due date always looks reasonable.


### `escalation_accepted` · obs_kind

- blocks **Escalation** / `esc.it_bounced_back_down` (would yield 8800 bp)
- blocks **Escalation** / `esc.receiver_accepted_ownership` (would yield 10000 bp)
- Escalation: The only signal that can distinguish an escalation from a complaint, which makes it the one that decides whether escalation rate means anything. 10000 is justified here and almost nowhere else: acceptance is an act, not an inference.

### `incident.status` · fact_path

- blocks **Incident** / `incident.declared_on_the_record` (would yield 10000 bp)
- blocks **Postmortem** / `postmortem.exists_and_was_reviewed` (would yield 10000 bp)
- Incident: Every incident tool exposes this. Nothing projects it into a typed fact, so the brain cannot tell a live incident from a closed one.

### `ticket.assignee` · fact_path

- blocks **Escalation** / `esc.receiver_accepted_ownership` (would yield 10000 bp)
- blocks **Ticket** / `ticket.status_declared_by_the_system_of_record` (would yield 10000 bp)
- Escalation: Needed to resolve WHO accepted. An acceptance with no resolvable person is a queue accepting, which is the failure receiver_named exists to catch.
- Ticket: Status without an owner cannot distinguish 'in progress' from 'sitting in a queue', which are the two states an operator most needs told apart.

### `ticket.status` · fact_path

- blocks **Commitment** / `commitment.declared_state_from_the_system_of_record` (would yield 10000 bp)
- blocks **Ticket** / `ticket.status_declared_by_the_system_of_record` (would yield 10000 bp)
- Commitment: A commitment on a ticket that closed is a different object from one on a ticket still open, and today the two are indistinguishable — so a promise attached to work that finished keeps generating overdue alerts.

- Ticket: The single most embarrassing gap in this domain. The declared state of THE central object is not projected into a typed fact, so a support brain has to infer from email what the ticketing system already knows for certain. Everything else in this backlog is worth less than this one line.

### `ticket.first_response_at` · fact_path

- blocks **SLA Target** / `sla.first_response_actually_recorded` (would yield 9800 bp)
- blocks **Ticket** / `ticket.first_response_overdue` (would yield 9800 bp)
- Ticket: Must record the first SUBSTANTIVE reply, not the auto-acknowledgement. If the connector projects the autoresponder timestamp, this pattern will report perfect first-response attainment on a queue that has answered nothing, and it will do so convincingly.

### `entitlement_checked` · obs_kind

- blocks **Entitlement** / `ent.verified_on_this_contact` (would yield 9000 bp)
- blocks **Requester** / `req.named_contact_on_the_plan` (would yield 9500 bp)
- Entitlement: The difference between an organisation that checks and one that assumes is measurable only if the check emits something. Today verification leaves no trace, so verification_source can never be raised above cached_record by evidence — only by someone claiming it.
- Requester: Also worth having as an event: knowing entitlement was verified, and when, is what stops it being re-litigated on every contact.

### `commitment.owner` · fact_path

- blocks **Commitment** / `commitment.extracted_from_language_that_never_says_promise` (would yield 9200 bp)
- blocks **Commitment** / `commitment.this_promiser_habitually_overpromises` (would yield 7000 bp)
- Commitment: Without an owner the promise is attached to a thread rather than to a person, so it cannot be routed at handover and cannot be aggregated into a per-agent reliability signal. A commitment owned by a queue is owned by nobody.


### `commitment.recipient` · fact_path

- blocks **Commitment** / `commitment.extracted_from_language_that_never_says_promise` (would yield 9200 bp)
- blocks **Commitment** / `commitment.the_person_we_promised_has_gone` (would yield 7500 bp)
- Commitment: Who it was promised to. Needed to detect the case where the promise is still live and the person waiting on it has left the account.

- Commitment: `champion_change` is already emitted by Layer 2, so half of this pattern exists. The missing half is knowing WHO the promise was made to, without which the departure cannot be matched to the obligation. Worth having because this is a case where the correct action inverts: the promise must be re-made to a new person rather than merely delivered, and delivering it to a dead mailbox looks like compliance while being total silence.


### `product.released_at` · fact_path

- blocks **Knowledge Article** / `ka.surface_changed_since_verification` (would yield 9000 bp)
- blocks **Macro** / `macro.describes_behaviour_that_shipped_away` (would yield 8600 bp)
- Knowledge Article: Release timestamps per product area. Available in every deploy pipeline and connected to no knowledge base anywhere.
- Macro: Release timestamps per product area. Present in every deploy pipeline, connected to no macro library anywhere.

### `product.surface_version` · fact_path

- blocks **Knowledge Article** / `ka.surface_changed_since_verification` (would yield 9000 bp)
- blocks **Macro** / `macro.describes_behaviour_that_shipped_away` (would yield 8600 bp)
- Knowledge Article: So verified_against_version has a referent. A verification date with nothing to compare against is a date, not a verification.
- Macro: So verified_against_version has something to compare against.

### `agent_reassigned` · obs_kind

- blocks **Escalation** / `esc.it_bounced_back_down` (would yield 8800 bp)
- blocks **Escalation** / `esc.the_diagnosis_restarted` (would yield 7500 bp)
- Escalation: Marks the ownership change. On its own it says nothing about context.
- Escalation: Acceptance followed by reassignment back to the prior owner. Worth 8800 rather than lower because the sequence is unambiguous once both kinds exist — and worth authoring ahead of the signal because a bounce is the worst outcome this object has and today it is completely unobservable. Nobody logs a bounce; it happens in a hallway.

### `bug_fixed` · obs_kind

- blocks **Macro** / `macro.describes_behaviour_that_shipped_away` (would yield 8600 bp)
- blocks **Postmortem** / `postmortem.actions_never_reached_engineering` (would yield 8500 bp)
- Macro: The sharper half. A release is circumstantial; a FIX to the specific issue a workaround macro documents makes that macro wrong immediately and with certainty. That edge already exists in the model and nothing walks it.

- Postmortem: Also the suppression signal for postmortem.action_overdue_with_no_outbound — with it, a completed action stops looking like an abandoned one.

### `ticket.queue` · fact_path

- blocks **Incident** / `incident.same_area_across_unrelated_accounts` (would yield 8600 bp)
- blocks **Macro** / `macro.carrying_an_outsized_share_of_a_queue` (would yield 8500 bp)
- Incident: Queue is the nearest thing the planned schema has to a product area, and it is a poor substitute — queues are drawn around teams and shifts, not around faults. A real ticket.product_area is what this pattern wants.
- Macro: The denominator has to be a queue, not the whole org. A macro at four percent of all replies and forty percent of the billing queue is a billing product finding, and the org-wide number hides it completely.


### `bug_filed` · obs_kind

- blocks **Postmortem** / `postmortem.actions_never_reached_engineering` (would yield 8500 bp)
- blocks **Ticket** / `ticket.closed_on_a_workaround_over_an_open_issue` (would yield 8500 bp)
- Postmortem: The best available predictor of whether an action will ever be done is whether it exists in the system engineering works from. An action list that produced no filed work is fully decorative and can be detected on the day the document is published rather than at the next review, which is the entire value of this signal.


### `derived.backlog_age` · derived

- blocks **Incident** / `incident.first_response_time_collapses_against_baseline` (would yield 5500 bp)
- blocks **SLA Target** / `sla.breach_imminent_against_the_real_target` (would yield 8500 bp)
- Incident: Needed to separate an inbound surge from an agent shortage; without it the two are indistinguishable and the pattern fires on staffing gaps.
- SLA Target: The second half is what makes this actionable rather than merely alarming. Time-remaining alone tells you a breach is coming; time-remaining against queue depth tells you whether anyone can still stop it, which is the only version worth waking someone for.

### `reproduction_confirmed` · obs_kind

- blocks **Escalation** / `esc.the_diagnosis_restarted` (would yield 7500 bp)
- blocks **Requester** / `req.fluency_from_what_they_attach` (would yield 8500 bp)
- Escalation: A second reproduction request after a reassignment is the machine-visible fingerprint of context that did not travel — the characteristic failure of this object, and currently invisible.
- Requester: Corroborating. Someone who can reproduce on demand has already proved diagnostic_capability; the artifact signal proves fluency, this one proves access.

### `ticket_volume` · baseline

- blocks **Incident** / `incident.ticket_creation_burst_above_baseline` (would yield 8000 bp)
- blocks **Macro** / `macro.carrying_an_outsized_share_of_a_queue` (would yield 8500 bp)
- Incident: Must be per-area and per-hour-of-week, not global. A global daily baseline hides a total outage of one feature inside normal Monday volume, which is the exact failure this pattern is meant to catch.
- Macro: So "substantial" is relative to the queue's own size and season. A fixed threshold fires constantly on small queues and never on large ones, which is the opposite of useful.


### `macro.body_text` · fact_path

- blocks **Macro** / `macro.diverged_from_its_article` (would yield 7200 bp)
- blocks **Macro** / `macro.near_duplicate_of_another_macro` (would yield 8000 bp)
- Macro: The bodies are sitting in the helpdesk. Duplicate detection over them is a solved problem and is performed by nobody, which is why sprawl is discussed as a feeling rather than a number.

### `bug_awaiting_engineering` · l2_situation_type

- blocks **[situation] Bug Awaiting Engineering** / `customer_support.sit.bug_awaiting_engineering` (would yield 10000 bp)
- Bug Awaiting Engineering: Must mean: a customer-facing ticket is blocked on a filed defect owned outside support, carrying the bug reference, its current engineering state, and — separately and most importantly — the time since the customer last heard anything. Those are two clocks and the second one is the one this domain cares about: a bug can be moving briskly through an engineering board while the customer has heard nothing for five weeks, and that is the state that loses accounts. It must also carry the support-side owner, because the defining failure of the handoff is a filed bug on behalf of a customer nobody owns. What would emit it: the handoff_to_engineering and bug_filed obs kinds in planned_substrate, with the ticket held in a waiting_on_engineering state, plus bug_fixed as the closing edge — the fix event is the one that must come back, and today it never does. Why commitment_overdue is not good enough: it fires on the promise, not on the state. It needs someone to have committed to a date, so it catches the well-managed tickets — the ones where an agent said "I will update you Friday" and then did not — and generates nothing at all for the ticket where nobody promised anything. The tickets where nobody promised anything are the entire population this situation exists to find. Nobody is late, so nothing fires, so the silence continues, which is the mechanism by which support organisations lose customers slowly and without a single recorded failure.

- Bug Awaiting Engineering: closest type emitted today is `commitment_overdue` — close enough to be tempting, not close enough to be true

### `csat_detractor` · l2_situation_type

- blocks **[situation] CSAT Detractor** / `customer_support.sit.csat_detractor` (would yield 10000 bp)
- CSAT Detractor: Must mean: a submitted satisfaction or effort response landing in the detractor band of the instrument that was used, carried together with the ticket and interaction it judged, the human who answered, and — critically — the free-text comment. The comment is the content of this signal; the number is a sort key. A type that carries only a score will be used to build a trend line, which is the one use of it that cannot act on anything. The band must be a property of the instrument, not a constant: 1-2 on a five-point CSAT, 0-6 on NPS, and a high-effort answer on CES are different arithmetic and Layer 2 must not hard-code one of them. What would emit it: Layer 1 ingesting survey webhooks as the csat_submitted / nps_submitted / ces_submitted obs kinds with the csat.score and csat.submitted_at fact paths from planned_substrate, and Layer 2 banding per instrument. Why champion_quiet is not good enough: it is what actually happens today, and it happens weeks late and stripped of the reason. A detractor who has given up stops replying, the contact eventually ages into champion_quiet, and the system reports that a relationship has gone cold without knowing that it went cold because of a specific ticket that a specific person told us about in writing. Binding here would also invert the timing that makes this situation worth anything: the recoverable moment is the day of the response, and champion_quiet cannot fire until enough silence has accumulated to prove the moment was missed.

- CSAT Detractor: closest type emitted today is `champion_quiet` — close enough to be tempting, not close enough to be true

### `entitlement_expired` · l2_situation_type

- blocks **[situation] Entitlement Expired** / `customer_support.sit.entitlement_expired` (would yield 10000 bp)
- Entitlement Expired: Must mean: the coverage attached to this account has passed its end date, carrying what expired (channels, hours, response targets, named contacts), when, and whether anything replaced it. It must be emittable BEFORE the expiry as well as after — the useful moment is the approach, where a renewal conversation is still ordinary, not the aftermath, where it is a recovery. It must also distinguish lapsed from cancelled from downgraded, because those are three different commercial conversations and only one of them is bad news. What would emit it: Layer 1 reading entitlement.expires_at and entitlement.plan from the billing or CRM side, with the entitlement_expired and entitlement_checked obs kinds in planned_substrate marking when the check actually happened. account.renewal_at makes the approach case computable. Why commitment_overdue is not good enough: structurally it is the closest thing the pipeline has — a date passed and nobody looked — and semantically it is the reverse. commitment_overdue's subject is a promise WE made and can still keep, and its prescribed action is to go and keep it late. An expired entitlement is a promise that has stopped existing, and the correct action is not support work performed late but a commercial conversation started early. Binding here would produce a system that chases the agent to deliver coverage the company is no longer being paid for, and would still say nothing to anyone who could renew it. What goes wrong today is simply that nothing fires at all: expiry is silent by construction, and the discovery event is a customer being told no.

- Entitlement Expired: closest type emitted today is `commitment_overdue` — close enough to be tempting, not close enough to be true

### `entitlement_mismatch` · l2_situation_type

- blocks **[situation] Entitlement Expired** / `customer_support.sit.entitlement_expired` (would yield 10000 bp)
- Entitlement Expired: Must mean: the entitlement the ticketing system is enforcing differs from the entitlement the signed contract describes. It must carry both readings and their sources, because the finding is the disagreement and an alert that names only one side is unactionable — and because the contract is usually the richer and more correct of the two. The drift is ordinary rather than exceptional: plans get renegotiated in a document and configured in a product by different people at different times, and nobody reconciles them until somebody is upset. What would emit it: Layer 2 comparing entitlement.plan and entitlement.coverage_hours against the contract record, ideally continuously rather than at the moment of contact. Why commitment_overdue is not good enough: it is downstream of the damage by definition. A mismatch becomes visible today only when someone has promised something under the wrong plan and then cannot keep it — at which point a commitment goes overdue and the pipeline finally has something to say. The entire value of this type is firing before anything has been promised, so the nearest available signal is guaranteed to arrive after the only moment it could have helped.

- Entitlement Expired: closest type emitted today is `commitment_overdue` — close enough to be tempting, not close enough to be true

### `escalation_requested` · l2_situation_type

- blocks **[situation] Escalation Requested** / `customer_support.sit.escalation_requested` (would yield 10000 bp)
- Escalation Requested: Must mean: a request for ownership of a piece of work to move, carrying (a) the trigger side — customer_initiated or internally_triggered, because those are different events sharing a word — (b) the specific ask being made of the receiver, and (c) the named receiver where one has been proposed. It must remain live until a receiver ACCEPTS, not until someone replies. That distinction is the whole value of the type: the harmful interval is between raising and acceptance, and every existing product closes it by setting a flag, which nobody has to accept. What would emit it: Layer 1 extraction of escalation language in an inbound message (manager, escalate, VP, account team, unacceptable, formal complaint) plus a Layer 2 rule over a ticket-owner change accompanied by a stated reason. The obs kind pair escalation_requested / escalation_accepted in planned_substrate is the real ask — either alone is close to useless, because the whole point is measuring the gap between them. Why unanswered_email is not good enough: an escalation request only resembles an unanswered email while it is unanswered, which is the shortest part of its life. The moment any agent sends any reply, the compromise binding falls silent — while the escalation is still unaccepted, still unowned and still running. Worse, the two types prescribe opposite handling: unanswered_email asks for a reply from the current owner, and this situation exists because a reply from the current owner is exactly what the customer has already rejected. Today the escalation is invisible until it arrives as an executive email, at which point it is an account event rather than a ticket one.

- Escalation Requested: closest type emitted today is `unanswered_email` — close enough to be tempting, not close enough to be true

### `first_response_overdue` · l2_situation_type

- blocks **[situation] SLA Breach Imminent** / `customer_support.sit.sla_breach_imminent` (would yield 10000 bp)
- SLA Breach Imminent: WHAT THE TYPE MUST MEAN. A ticket entitled to a first response has passed its first-response target with no SUBSTANTIVE human reply. Two constraints have to live inside the type or it is worse than nothing. First, substantive: an autoresponder, a "we have received your request" macro or any reply that could have been sent without reading the ticket must NOT satisfy it — the moment the field is satisfiable without reading, the queue learns to satisfy it that way and the metric detaches from the experience it was measuring. Second, distinct: first response is its own promise with its own target, usually far tighter than resolution, and a type that collapses the two hides the clock that is missed most often.
WHAT WOULD EMIT IT. ticket.created_at, ticket.first_response_at and sla.target_first_response_at from Layer 1, plus a first_response_sent observation carrying a substantiveness judgement — which is a Layer 2 classification problem, not a timestamp comparison, and should be specified as one.
WHAT GOES WRONG TODAY. The most commonly promised and most commonly measured commitment in support is invisible to this brain. Every downstream capability that depends on it — expectation_setting, queue_management, the whole of breach_prevention — is authored against a trigger that does not exist.
WHY BINDING TO unanswered_email WOULD BE WRONG, specifically. It fires on any unanswered inbound, including the fifth message of a long thread, and cannot tell a first contact from an ongoing exchange — which is the ONLY distinction this type is about. It also lives entirely on email: chat, phone and portal contacts are where first response is most often promised in minutes rather than hours, and they are exactly the channels a mail-shaped signal cannot see. Binding here would produce a first-response metric that is silent on the channels with the tightest first-response promises.

- SLA Breach Imminent: closest type emitted today is `unanswered_email` — close enough to be tempting, not close enough to be true

### `incident_unresolved` · l2_situation_type

- blocks **[situation] Major Incident Declared** / `customer_support.sit.major_incident_declared` (would yield 10000 bp)
- Major Incident Declared: Must mean: a declared incident is still open, with elapsed time since declaration and since the last customer-facing update carried separately. The second clock is the one that matters here and the one no incident tool tracks — an incident can be under control technically and completely silent externally, and the silence is what generates the escalations. What would emit it: Layer 2 over incident.status and incident.started_at, ticking against the update cadence promised at declaration rather than against any SLA. Why commitment_overdue is not good enough: it is the right shape and the wrong grain. An incident with forty affected accounts and a promised half-hourly update produces forty overdue commitments, forty nudges to whichever agents own those threads, and forty separately-worded updates — which is the exact failure this situation exists to prevent, now automated. It also fires only where a promise was explicitly recorded, so the accounts nobody thought to promise anything to generate nothing at all, and those are the ones that find out from a competitor's status page.

- Major Incident Declared: closest type emitted today is `commitment_overdue` — close enough to be tempting, not close enough to be true

### `knowledge_gap` · l2_situation_type

- blocks **[situation] Repeat Contact** / `customer_support.sit.repeat_contact` (would yield 10000 bp)
- Repeat Contact: Must mean: a question the help centre does not answer, or answers somewhere nobody finds. Those are the same volume and opposite fixes — write the article versus fix the findability — and a type that cannot distinguish them will be used to commission duplicates, which then compete with the original in search and make findability worse. So the type must carry the discriminator: was an article surfaced and rejected, or was nothing surfaced at all. Its subject is an intent, not a ticket. A gap that exists only as a property of a ticket dies when the ticket closes, and that death is the reason content gap analysis is currently a person reading exports rather than anything the engine does. What would emit it: zero-result and abandoned help-centre searches (self_service_attempted and self_service_abandoned in planned_substrate), knowledge_article_linked observations where the customer had already opened that article, and Layer 2 aggregation of deflection_failed across an intent. Why the nearest is not good enough: there is no near miss available, and that is the honest answer rather than an evasion. Every type the pipeline emits is customer-shaped — a thread, a person, a deal — and this one is content-shaped. Naming any of them as the binding would file the finding against a ticket, which is precisely the category error that makes it disappear. unanswered_email is recorded here as the compromise someone would reach for, not as an approximation worth making.

- Repeat Contact: closest type emitted today is `unanswered_email` — close enough to be tempting, not close enough to be true

### `major_incident_declared` · l2_situation_type

- blocks **[situation] Major Incident Declared** / `customer_support.sit.major_incident_declared` (would yield 10000 bp)
- Major Incident Declared: Must mean: a named human has declared an incident, with a severity, a start time, a blast radius (which product areas, which accounts, or explicitly unknown) and a commander. The declaration is an act, not an inference — a type that fires when the system thinks something looks bad will be argued with in exactly the minutes nobody has spare. What the engine may infer is a CANDIDATE; the type must carry whether it was declared or suspected, because the suppression behaviour this situation drives is far too aggressive to hang on a guess. What would emit it: Layer 1 ingesting the incident tool or status page (the incident_declared obs kind and the incident.severity / incident.status / incident.started_at fact paths in planned_substrate), with Layer 2 additionally raising a candidate on a correlated arrival spike — several unrelated requesters, same product area, short window. Why the nearest is not good enough: the compromise available today is a burst of unanswered_email across unrelated threads, and it is wrong in the way that costs most. It arrives late, because it needs each thread to have aged; it is proportional to who wrote in rather than to who is affected; and it prescribes precisely the wrong action, namely N individual replies. It also cannot express the suppression — an incident-shaped signal has to be able to tell the rest of the system to stand down, and a pile of per-thread signals is structurally incapable of that.

- Major Incident Declared: closest type emitted today is `unanswered_email` — close enough to be tempting, not close enough to be true

### `queue_overloaded` · l2_situation_type

- blocks **[situation] Queue Overloaded** / `customer_support.sit.queue_overloaded` (would yield 10000 bp)
- Queue Overloaded: Must mean: for a named queue, arrivals are exceeding closures and the backlog's age distribution has degraded — expressed as a comparison of two rates plus the shape of the wait, never as a count. It must be emitted per queue, with an owner attached, because a queue with no named owner is not a queue and an alert nobody owns is a dashboard. It should carry the arrival-side attribution where Layer 2 can compute it (a release, a campaign, a broken page, an incident), because the count tells a manager to hire and the composition usually tells them to fix something that will land this week. What would emit it: derived.backlog_age and ticket.queue from planned_substrate, against the ticket_volume baseline so that "overloaded" is relative to this queue's own normal rather than to a constant. The band itself is Layer 4 arithmetic and must not be baked into the type; what Layer 2 owes is the rates and the distribution. Why unanswered_email is not good enough: it is wrong in both dimensions at once. It is per-thread, so counting instances gives you a number of conversations rather than a volume of work — and forty simple password resets and forty escalated integration faults produce the same number. And it counts SIZE, when the entire finding here is AGE: a shrinking pile of steadily older tickets reads as improvement under any count-based signal and is the precise opposite of it. Today the queue's condition is visible only in a reporting tool a human has to open, which means it is discovered on the day someone looks rather than on the day it turned.

- Queue Overloaded: closest type emitted today is `unanswered_email` — close enough to be tempting, not close enough to be true

### `repeat_contact` · l2_situation_type

- blocks **[situation] Repeat Contact** / `customer_support.sit.repeat_contact` (would yield 10000 bp)
- Repeat Contact: Must mean: the same requester, or the same account, contacting again about the same INTENT within a window — counted by intent and not by ticket, because "how do I export this" and "where is the download button" are one gap in two phrasings, and counting tickets splits the evidence exactly where it needs to be joined. It must survive the earlier tickets being closed, merged or handled by a different agent, and it must carry the ordinal (second, third, fifth) because the shape of the curve is the finding: a second contact is noise, a fifth is a defect in the help centre with a customer attached to it. What would emit it: Layer 2 clustering ticket_created observations by requester and intent over derived.contact_frequency, with Layer 1 supplying the intent classification. The contact_rate_per_account baseline in planned_substrate is what makes the window adaptive rather than arbitrary — a weekly contact is normal for some accounts and alarming for others. Why unanswered_email is not good enough: repeat contact is its exact opposite. Every one of these contacts was answered — that is the whole point, that is what makes it interesting, and it is why this situation is invisible on every dashboard a support team already owns. Binding to unanswered_email would let the situation fire only in the single case it does not describe. What goes wrong today is not that the customer is ignored; it is that the second arrival is processed as a first arrival by someone who has never seen the first, and the fact that made it worth reading is discarded at intake.

- Repeat Contact: closest type emitted today is `unanswered_email` — close enough to be tempting, not close enough to be true

### `sla_breach_imminent` · l2_situation_type

- blocks **[situation] SLA Breach Imminent** / `customer_support.sit.sla_breach_imminent` (would yield 10000 bp)
- SLA Breach Imminent: WHAT THE TYPE MUST MEAN. A specific named clock on a specific ticket is forecast to expire before the ticket is next scheduled to be touched, measured in the entitlement's COVERED time rather than wall-clock time, and emitted with enough lead that the cheap rungs of the intervention ladder still exist. The payload must carry which clock (first response, next response, restoration, resolution), how much covered time remains, and the current clock state — a bare boolean produces the permanently amber queue, where every ticket is warning and therefore none is.
WHAT WOULD EMIT IT. Layer 1 must supply sla.target_first_response_at, sla.target_resolution_at, sla.clock_state and entitlement.coverage_hours (all present in planned_substrate.fact_paths and emitted by nothing). Layer 2 then evaluates remaining covered time against the clock state, which requires it to understand business calendars and holidays — that is the genuinely hard part and the reason this cannot be faked with a days_since predicate. The sla_clock_started, sla_clock_paused and sla_breach observation kinds are the audit trail that makes the forecast reviewable after the fact.
WHAT GOES WRONG TODAY. Nothing fires. Breach prevention has no trigger at all, so the earliest anyone learns about a miss is when the customer raises it — at which point the work is apology rather than prevention, and the capability that owns this file has no surface to act on.
WHY BINDING TO unanswered_email WOULD BE WRONG, specifically. (1) It measures elapsed silence on a thread with no knowledge of what was promised, so an entitled four-hour first response and a casual question look identical. Every quiet thread in the company becomes an SLA warning: too loud. (2) It has no working calendar. A four-hour target that started at 09:00 is breached at 13:00, and no tuning of a silence detector that survives contact with a real inbox treats four hours of quiet as remarkable — so the alert lands, if at all, after the deadline it was supposed to prevent: too quiet, at the same time, on the same tickets. (3) It has no notion of a pause. A ticket legitimately waiting on the customer has a stopped clock and is not at risk, and a silence detector cannot tell that state from neglect. (4) The compound failure: bound this way, the system reports SLA coverage it does not have. That is worse than a gap, because a gap gets fixed and a green dashboard does not.

- SLA Breach Imminent: closest type emitted today is `unanswered_email` — close enough to be tempting, not close enough to be true

### `ticket_aging` · l2_situation_type

- blocks **[situation] Queue Overloaded** / `customer_support.sit.queue_overloaded` (would yield 10000 bp)
- Queue Overloaded: Must mean: an individual open item has waited materially longer than comparable work in its queue, with time-since-last-customer-contact carried separately from time-since-open — an old ticket that is being actively worked and an old ticket nobody has touched are completely different findings that share an age. It must also distinguish waiting on the customer from waiting on us, because collapsing those is how a queue reports health it does not have. What would emit it: Layer 2 over ticket.created_at, ticket.status and derived.backlog_age relative to the resolution_time baseline for the queue. Why commitment_overdue is not good enough, and this is the sharp one: commitment_overdue requires a promise to exist before it can fire. The aging tickets that actually matter are precisely the ones nobody promised anything about — no owner, no next step, no committed date, which is exactly why they aged. Nobody committed, so nothing is overdue, so the oldest item in the queue is invisible to the only elapsed-time signal the pipeline has. The tickets that generate commitment_overdue are the well-managed ones.

- Queue Overloaded: closest type emitted today is `commitment_overdue` — close enough to be tempting, not close enough to be true

### `ticket_reopened` · l2_situation_type

- blocks **[situation] Ticket Reopened** / `customer_support.sit.ticket_reopened` (would yield 10000 bp)
- Ticket Reopened: WHAT THE TYPE MUST MEAN. A ticket previously in a resolved, closed or verified state has been returned to open BY THE CUSTOMER. The actor distinction is not a detail: a large share of state changes back to open are our own housekeeping — bulk edits, automation firing on a stale rule, an agent reopening to add a note — and a type that counts those is measuring our workflow rather than our correctness. The payload must carry the reopen index and the elapsed time since closure. Both change the meaning completely: a reopen an hour after closure is a verification failure, a reopen three weeks later is usually a regression, and a third reopen on one ticket is a categorically different event from a first that a system treating them alike has stopped learning from.
WHAT WOULD EMIT IT. Layer 1 must supply ticket.status, ticket.resolved_at and ticket.reopen_count (all in planned_substrate.fact_paths, emitted by nothing today). Layer 2 emits the ticket_reopened observation kind with the actor attached, and should emit it alongside the resolution and article ids that the closure referenced — otherwise the invalidation described at the top of this file has nothing to propagate to, and the signal loses most of its value while looking complete.
WHAT GOES WRONG TODAY. The domain's single best piece of ground truth is unobservable. verification_and_closure cannot measure the failure it exists to prevent. root_cause_analysis never learns which of its conclusions were wrong. knowledge_authoring has no mechanism by which a wrong article is ever demoted. And Layer 6 receives no negative evidence about resolutions at all, so every confidence in this library is free to rise and none can fall.
WHY BINDING TO unanswered_email WOULD BE WRONG, specifically — and this is the most seductive bad binding in the domain, because it half works. A reopen usually does arrive as a new inbound on an old thread, so the silence detector genuinely fires on many of them. What it drops is the entire information content: that this thread was previously declared resolved. Strip that and the event becomes another customer waiting, indistinguishable from a first contact — and the two demand opposite responses. A first contact wants a fast answer. A reopen wants someone to work out why the last answer was wrong BEFORE sending another one, and a system that optimises for speed here produces a second wrong answer faster. It also cannot see reopens that arrive on a fresh thread or through a portal, chat or phone, which in any organisation with a help centre is most of them, and it can never see the reopen count. The result would be a partial, channel-biased, context-stripped view of the one signal worth having most.

- Ticket Reopened: closest type emitted today is `unanswered_email` — close enough to be tempting, not close enough to be true

### `workaround_only` · l2_situation_type

- blocks **[situation] Bug Awaiting Engineering** / `customer_support.sit.bug_awaiting_engineering` (would yield 10000 bp)
- Bug Awaiting Engineering: Must mean: a ticket was resolved by a workaround while the underlying issue remains open. It must carry the workaround, the issue it defers to, and the workaround's ongoing cost to the customer — a one-time configuration change and a manual step performed every morning are recorded identically today and are not remotely the same debt. Crucially it must SURVIVE the ticket closing. Its whole purpose is keeping a customer attached to an open defect after their ticket has gone, so a type scoped to an open ticket is structurally incapable of expressing it. This is the more valuable of the two types on this file, because it marks the customers who are technically resolved and actually still broken, and no support system anywhere can currently list them. What would emit it: Layer 2 joining ticket_resolved with workaround_provided where the linked issue is not closed, and holding the join open until the issue closes. Why unanswered_email is not good enough: there is no thread left to be unanswered. The ticket was closed politely, the customer said thank you, and the conversation ended — that is the defining property of the state. Every compromise the pipeline offers requires a live thread or an open record, and this situation is defined by the absence of both. What goes wrong today: the workaround is the last thing anyone records. The fix ships months later, nobody tells the customer, and the cheapest goodwill available in support — "the thing you reported is fixed, you can stop doing the workaround" — is never collected.

- Bug Awaiting Engineering: closest type emitted today is `unanswered_email` — close enough to be tempting, not close enough to be true

### `first_response_sent` · obs_kind

- blocks **SLA Target** / `sla.first_response_actually_recorded` (would yield 9800 bp)
- SLA Target: Needed alongside the fact path because the timestamp alone cannot distinguish a substantive reply from an auto-acknowledgement — and auto-acknowledgements stopping first-response clocks is the oldest trick in the category.

### `macro.edit_distance_at_send` · fact_path

- blocks **Macro** / `macro.sent_without_a_single_edit` (would yield 9800 bp)
- Macro: Characters changed between the stored template and the sent body. Both strings already exist in the helpdesk and the subtraction is trivial. This single integer is the difference between a macro library reviewed by wording — the only review possible today — and one reviewed by whether agents actually thought before sending. Highest-leverage ask on this object.


### `macro.macro_ref` · fact_path

- blocks **Macro** / `macro.sent_without_a_single_edit` (would yield 9800 bp)
- Macro: The join key. Without it the edit distance cannot be attributed to a macro and becomes an anonymous statistic about typing.

### `incident.detected_at` · fact_path

- blocks **Postmortem** / `postmortem.detection_gap_is_the_headline` (would yield 9500 bp)
- Postmortem: Not in the planned substrate today and it should be. `incident.started_at` alone gives a duration to resolution; the PAIR gives the detection gap. Emitting one without the other produces a dashboard that looks like incident analytics and cannot answer the only question this object exists to ask.


### `knowledge.owner_id` · fact_path

- blocks **Knowledge Article** / `ka.owner_departed` (would yield 9500 bp)
- Knowledge Article: Ownership is stored in the knowledge base and never projected as a fact, so it cannot be joined to anything.

### `leaver_confirmed` · obs_kind

- blocks **Knowledge Article** / `ka.owner_departed` (would yield 9500 bp)
- Knowledge Article: Already on the planned list for Admin. One emitter would serve both domains: Admin uses it for asset recovery, Support for knowledge custody.

### `callback_promised` · obs_kind

- blocks **Commitment** / `commitment.extracted_from_language_that_never_says_promise` (would yield 9200 bp)
- Commitment: The highest-value missing signal for this object by a distance. Today commitment.due_at arrives from a generic extractor built for a sales motion, which catches "I'll send the proposal Monday" and is much shakier on the support phrasings — "let me chase that and revert before end of play", "I'll get an answer from the team and ping you Thursday". Nobody says "I commit". The extraction has to recognise an undertaking from verb and tense, and it has to attribute it to the AGENT rather than to the customer, which is the failure named in the false positive on the first pattern above.


### `knowledge.viewed_at` · fact_path

- blocks **Knowledge Article** / `ka.viewed_then_contacted` (would yield 9200 bp)
- Knowledge Article: Every help centre logs a view with a session and a timestamp. It is discarded at the platform boundary. This is the single highest-value missing signal in the entire Customer Support brain.

### `root_cause_identified` · obs_kind

- blocks **Postmortem** / `postmortem.this_has_been_written_before` (would yield 9200 bp)
- Postmortem: Without a structured causal finding there is nothing to match a recurrence against, so recurrence is detected by whoever happens to remember — which means it is detected reliably for eighteen months and then not at all, because the person who remembered changed teams.


### `account.contact_role` · fact_path

- blocks **Requester** / `req.is_the_account_admin` (would yield 9000 bp)
- Requester: Cheap to source and easy to over-read. Worth emitting for permissions routing, but the moment it is used as a proxy for technical fluency it becomes actively harmful — see the note on technical_fluency.

### `derived.affected_account_count` · derived

- blocks **Incident** / `incident.blast_radius_from_distinct_affected_accounts` (would yield 9000 bp)
- Incident: Distinct accounts, not distinct tickets. The distinction is the whole discriminator: twenty tickets from one account is an escalation, twenty accounts with one ticket each is an incident, and the two demand opposite responses.

### `entitlement_expired` · obs_kind

- blocks **Entitlement** / `ent.verified_on_this_contact` (would yield 9000 bp)
- Entitlement: The paired negative. A check that discovers a lapse is the single most useful observation this domain could emit and currently there is nowhere to put it.

### `ticket.resolved_at` · fact_path

- blocks **SLA Target** / `sla.met_the_number_and_failed_the_customer` (would yield 9000 bp)

### `derived.sentiment_by_author` · derived

- blocks **Customer Sentiment** / `cs.sent.read_from_customer_words_only` (would yield 8800 bp)
- Customer Sentiment: The correctness fix for every executable pattern above. derived.sentiment is thread-level, so it mixes our apologies into their mood — which produces a metric that improves when agents write more contritely and gets worse when they write efficiently. This is the most common defect in commercial sentiment tooling and it is currently ours too. Every confidence in this file is capped several hundred basis points below where it could sit purely because this signal does not exist; shipping it is a re-calibration of the whole object, not an addition to it.

### `rca_requested` · obs_kind

- blocks **Postmortem** / `postmortem.customer_rca_owed_and_late` (would yield 8800 bp)
- Postmortem: Not in the planned substrate and should be. "Can we get an RCA on this" is stated in plain language on threads already ingested, and it is the moment the postmortem acquires a second audience.

### `search.query_text` · fact_path

- blocks **Knowledge Article** / `ka.searched_for_and_not_found` (would yield 8800 bp)
- Knowledge Article: The zero-result query log is the only honest record of what was ASKED as opposed to what was written. Most help centres keep it for thirty days and then bin it.

### `search.result_count` · fact_path

- blocks **Knowledge Article** / `ka.searched_for_and_not_found` (would yield 8800 bp)
- Knowledge Article: Zero-result is the trivially instrumentable case. The harder and more valuable one is a non-zero result the customer scrolled past.

### `commitment_renegotiated` · obs_kind

- blocks **Commitment** / `commitment.renegotiated_before_the_due_time` (would yield 8500 bp)
- Commitment: Not in planned_substrate and proposed here, because nothing in the planned list covers it and the distinction it draws is the most valuable one in the domain. Today a reset is indistinguishable from a fresh promise: both look like a new commitment.due_at, so a team that renegotiates responsibly and a team that silently slips produce identical traces. Since notice-versus-silence is almost the entire de-escalation conversation, an engine that cannot see the difference cannot coach it, cannot reward it, and will report the careful team and the careless one as equally unreliable.


### `derived.sentiment_prior` · derived

- blocks **Customer Sentiment** / `cs.sent.trajectory_recovering` (would yield 8500 bp)
- Customer Sentiment: The previous read and its timestamp, so trajectory survives a restart and does not depend on Layer 3 holding state it has no store for.

### `derived.sentiment_trend` · derived

- blocks **Customer Sentiment** / `cs.sent.trajectory_recovering` (would yield 8500 bp)
- Customer Sentiment: The single highest-value ask this object generates. derived.sentiment is a LEVEL. The most important thing a support brain can say about a customer — 'furious on Monday, merely annoyed today, keep doing exactly this' — is not expressible against a level. Without it, a recovering customer and a collapsing one produce the identical negative score and receive the identical intervention, and the intervention is wrong for one of them every time. Needs a signed delta plus the window it was measured over; a delta without a window is uninterpretable.

### `diagnostic_artifact_attached` · obs_kind

- blocks **Requester** / `req.fluency_from_what_they_attach` (would yield 8500 bp)
- Requester: Nothing in the pipeline inspects attachments or code blocks. This is the single best available evidence of fluency and it arrives in the first message of the ticket, unasked, and is discarded. Cheap to extract and it improves the highest-weighted decision factor on the object.

### `entitlement.seat_count` · fact_path

- blocks **Entitlement** / `ent.seat_limit_reached` (would yield 8500 bp)
- Entitlement: Invented rather than taken from planned_substrate, which has no seat field. Support hits the seat ceiling before sales does — the over-limit user contacts support to ask why they cannot log in.

### `entitlement.seats_in_use` · fact_path

- blocks **Entitlement** / `ent.seat_limit_reached` (would yield 8500 bp)
- Entitlement: The provisioning side. Useful in both directions: seats_in_use far below seat_count is a churn indicator dressed as a happy account.

### `handoff_to_engineering` · obs_kind

- blocks **Postmortem** / `postmortem.actions_never_reached_engineering` (would yield 8500 bp)

### `macro.use_count_30d` · fact_path

- blocks **Macro** / `macro.carrying_an_outsized_share_of_a_queue` (would yield 8500 bp)
- Macro: Sends per macro per window. The numerator, and the only half anybody currently reports.

### `ticket.channel` · fact_path

- blocks **Entitlement** / `ent.channel_used_outside_entitlement` (would yield 8500 bp)
- Entitlement: Everything the pipeline sees is email-shaped, so the channel dimension of entitlement is entirely unmodelled. Channel breach is the most common entitlement breach precisely because it is never a decision — the agent replies on whatever arrived.

### `workaround_provided` · obs_kind

- blocks **Ticket** / `ticket.closed_on_a_workaround_over_an_open_issue` (would yield 8500 bp)
- Ticket: Distinguishing a fix from a workaround is what stops a queue from congratulating itself. Without it, resolution rate counts a symptom suppressed the same as a fault removed, and the same fault reaches the next forty customers with the metrics looking excellent throughout.

### `blame_attribution` · obs_kind

- blocks **Postmortem** / `postmortem.blame_language_in_the_timeline` (would yield 8000 bp)
- Postmortem: Nothing in the planned substrate covers this and it deserves to be there. Blamelessness is currently enforced by whoever facilitates remembering to enforce it, which means it is enforced well for about a year. The detection is cheap — individual names in a timeline where the surrounding sentences use roles — and the cost of missing it is not borne by this document at all. It is borne by the next review, where everyone now knows what gets written down and volunteers less. That delay is precisely why the practice erodes without anyone deciding to abandon it.


### `conversation.language` · fact_path

- blocks **Requester** / `req.reachable_language_and_hours` (would yield 8000 bp)
- Requester: Detectable from message body at ingest with high reliability. Without it every reply is composed in the agent's language and the correctness risk in a translated diagnostic instruction is carried by the customer.

### `derived.macro_similarity` · derived

- blocks **Macro** / `macro.near_duplicate_of_another_macro` (would yield 8000 bp)
- Macro: Pairwise similarity across the library. Must be computed over the BODY and not the title — the duplicates that hurt are the ones with different titles and the same content, because those are the ones that survive every review.


### `derived.requester_active_hours` · derived

- blocks **Requester** / `req.reachable_language_and_hours` (would yield 8000 bp)
- Requester: Timezone alone is the wrong signal — a Berlin requester working US hours is reachable when their timezone says they are asleep. Observed send-times answer it directly and the timestamps are already in the store.

### `customer_tone_baseline` · baseline

- blocks **Customer Sentiment** / `cs.sent.hostile_language_first_occurrence` (would yield 7800 bp)
- Customer Sentiment: Per-person normal tone. Without it the abrasive customer is flagged hostile every week until the team stops reading the field, which is the failure mode that kills sentiment features.

### `account.health_score` · fact_path

- blocks **Customer Sentiment** / `cs.sent.calm_and_leaving` (would yield 7500 bp)
- Customer Sentiment: Corroboration from outside the support thread, so a quiet customer who is using the product heavily is not confused with one who has stopped.

### `derived.backlog_age` · fact_path

- blocks **Postmortem** / `postmortem.communication_failure_went_unexamined` (would yield 7500 bp)
- Postmortem: The ticket pile-up during an outage is the measurable form of a comms failure — every ticket that arrived after a broadcast should have gone out is one the broadcast did not reach.

### `entitlement.named_contacts` · fact_path

- blocks **Entitlement** / `ent.requester_not_on_the_named_list` (would yield 7500 bp)
- Entitlement: Invented — planned_substrate has no named-contact field. Deliberately NOT a blocking signal even when it lands: refusing a stranger mid-outage is almost always the wrong call. Its value is cumulative, because named-contact limits are what enterprise plans charge for, and an unenforced limit is a discount nobody agreed to give.

### `knowledge.body_text` · fact_path

- blocks **Macro** / `macro.diverged_from_its_article` (would yield 7200 bp)
- Macro: Both bodies, so the claims can be compared rather than the timestamps. Comparing edit dates tells you which was touched most recently, which is not the same question.

### `commitment_delivery_rate` · baseline

- blocks **Commitment** / `commitment.this_promiser_habitually_overpromises` (would yield 7000 bp)
- Commitment: Turns individual broken promises into the only support metric that measures character rather than throughput. It is also the metric most likely to be misused, so it needs to be per-promiser AND per-promise-type: an agent who promises resolutions will miss far more than one who promises updates, and ranking them together punishes the braver one. Absent this, every broken promise is read as an isolated incident and the systematic overpromiser is invisible.


### `derived.escalation_pressure` · fact_path

- blocks **Requester** / `req.escalation_prone_from_history` (would yield 7000 bp)
- Requester: Deliberately capped at 7000 even once it ships. Prior escalations are as much a record of how often we failed this person as of how they behave, and a system that quietly derates them for it is punishing the customer for our history.

### `sla_clock_paused` · obs_kind

- blocks **SLA Target** / `sla.systematic_pause_gaming` (would yield 7000 bp)
- SLA Target: A pause event with a timestamp. Without it the pause ledger is reconstructed from thread shape, which is what the 4200-confidence pattern above is doing and why it scores 4200.

### `article_link_rate` · baseline

- blocks **Knowledge Article** / `ka.agents_route_around_it` (would yield 6800 bp)
- Knowledge Article: Per-intent baseline so 'unusually low' is measured against how link-happy this team is, not against an absolute.

### `knowledge.view_count_30d` · fact_path

- blocks **Knowledge Article** / `ka.traffic_without_feedback` (would yield 3500 bp)

### `knowledge_feedback_submitted` · obs_kind

- blocks **Knowledge Article** / `ka.traffic_without_feedback` (would yield 3500 bp)
- Knowledge Article: Any feedback event at all — thumbs, comment, correction. The absence of the event is what carries the meaning here, so it must be emitted reliably or not at all.
