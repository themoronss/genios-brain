# Sales Expertise — signal backlog

> GENERATED — `python "Domain Expertise/_tools/backlog.py"`

Every row is a signal the authored expertise needs and the pipeline does not
emit. Ranked by how many inference patterns it unblocks, then by the confidence
of the strongest pattern waiting on it.

Rows marked `l2_situation_type` are the expensive ones. A blocked *pattern*
lowers one object's confidence; a blocked *situation* means the capability
behind it never compiles at all, and nothing errors or logs when it doesn't.

## Where the brain stands

- **169** patterns executable against the pipeline today
- **142** patterns blocked, waiting on **148** distinct signals
- **2** situation binding(s) waiting on an L2 type no pack emits
- Substrate today: **34** fact paths · **34** observation kinds · **2** baselines

## The backlog

| # | Signal | Kind | Owner | Unblocks | Top conf | Objects |
|---|---|---|---|---|---|---|
| 1 | `account.industry` | fact_path | L1 | 8 | 10000 | Disqualifier, Fit Analysis, ICP, Market Map |
| 2 | `contract_signed` | obs_kind | L2 | 6 | 10000 | Account, Contract, Deal, Decision Maker, Market Map, Proposal |
| 3 | `account.geography` | fact_path | L1 | 3 | 10000 | Disqualifier, Fit Analysis, ICP |
| 4 | `crm.contact.role` | fact_path | L1 | 3 | 10000 | Buying Committee, Champion, Decision Maker |
| 5 | `account.retention_months` | fact_path | L1 | 3 | 9200 | Disqualifier, Fit Analysis |
| 6 | `person.seniority` | fact_path | L1 | 3 | 8200 | Business Need, Buying Signal, Decision Maker |
| 7 | `research.finding.collected_at` | fact_path | L1 | 2 | 10000 | Market Finding |
| 8 | `contract.end_date` | fact_path | L1 | 2 | 9800 | Account, Contract |
| 9 | `account.employee_count` | fact_path | L1 | 2 | 9500 | Fit Analysis, ICP |
| 10 | `closed_lost_reason` | obs_kind | L2 | 2 | 9500 | Competitor, Risk |
| 11 | `crm.contact.approval_limit` | fact_path | L1 | 2 | 9500 | Contract, Decision Maker |
| 12 | `account.segment` | fact_path | L1 | 2 | 9200 | Market Finding, Market Map |
| 13 | `derived.segment_aggregate` | derived | L2 | 2 | 9200 | Market Finding, Market Map |
| 14 | `account_trigger_event` | obs_kind | L1 | 2 | 8500 | ICP, Market Map |
| 15 | `crm.contact.title_normalised` | fact_path | L1 | 2 | 8500 | Contact, Persona |
| 16 | `pain_stated` | obs_kind | L2 | 2 | 8500 | Pain Point |
| 17 | `account.prior_deal_outcomes` | fact_path | L2 | 2 | 8000 | Buying Committee, ICP |
| 18 | `party.role` | fact_path | L2 | 2 | 8000 | Investor Conversation |
| 19 | `competing_initiative` | obs_kind | L2 | 2 | 7500 | Budget, Business Need |
| 20 | `channel_touch` | l2_situation_type | L1 | 1 | 10000 | [situation] Touch Outside Mail |
| 21 | `contract.executed_at` | fact_path | L1 | 1 | 10000 | Contract |
| 22 | `email_bounced` | obs_kind | L1 | 1 | 10000 | Contact |
| 23 | `icp.active_profile_version` | fact_path | L1 | 1 | 10000 | Fit Analysis |
| 24 | `market_period_review` | l2_situation_type | L2 | 1 | 10000 | [situation] Touch Outside Mail |
| 25 | `opportunity.status` | fact_path | L2 | 1 | 10000 | Opportunity |
| 26 | `catalogue.list_price` | fact_path | L1 | 1 | 9800 | Pricing |
| 27 | `contract.renewal_date` | fact_path | L1 | 1 | 9800 | Opportunity |
| 28 | `contract.renewal_notice_days` | fact_path | L1 | 1 | 9800 | Contract |
| 29 | `crm.deal.stage` | fact_path | L1 | 1 | 9800 | Deal |
| 30 | `account.incumbent_contract_end` | fact_path | L1 | 1 | 9500 | Timeline |
| 31 | `commitment.owner` | fact_path | L2 | 1 | 9500 | Next Action |
| 32 | `company.parent_domain` | fact_path | L1 | 1 | 9500 | Company |
| 33 | `contact_departed` | obs_kind | L2 | 1 | 9500 | Contact |
| 34 | `crm.account.arr` | fact_path | L1 | 1 | 9500 | Account |
| 35 | `crm.account.id` | fact_path | L1 | 1 | 9500 | Account |
| 36 | `crm.deal.close_date_history` | fact_path | L1 | 1 | 9500 | Timeline |
| 37 | `crm.deal.loss_reason` | fact_path | L1 | 1 | 9500 | Deal |
| 38 | `crm.opportunity.stage` | fact_path | L1 | 1 | 9500 | Opportunity |
| 39 | `crm.pricing.max_discount` | fact_path | L1 | 1 | 9500 | Pricing |
| 40 | `derived.claim_key` | derived | L2 | 1 | 9500 | Market Finding |
| 41 | `need.baseline_value` | fact_path | L2 | 1 | 9500 | Business Need |
| 42 | `need.target_value` | fact_path | L2 | 1 | 9500 | Business Need |
| 43 | `objection_resolved` | obs_kind | L2 | 1 | 9500 | Objection |
| 44 | `outbound.sent_at` | fact_path | L1 | 1 | 9500 | Lead |
| 45 | `proposal_revised` | obs_kind | L2 | 1 | 9500 | Proposal |
| 46 | `risk.owner` | fact_path | L1 | 1 | 9500 | Risk |
| 47 | `churn_event` | obs_kind | L2 | 1 | 9200 | Disqualifier |
| 48 | `pain.annual_cost` | fact_path | L2 | 1 | 9200 | Pain Point |
| 49 | `quantification_stated` | obs_kind | L2 | 1 | 9200 | Pain Point |
| 50 | `accountability_stated` | obs_kind | L2 | 1 | 9000 | Pain Point |
| 51 | `clause_conceded` | obs_kind | L2 | 1 | 9000 | Contract |
| 52 | `commitment_completed` | obs_kind | L2 | 1 | 9000 | Next Action |
| 53 | `compelling_event_stated` | obs_kind | L2 | 1 | 9000 | Timeline |
| 54 | `competitor.name` | fact_path | L2 | 1 | 9000 | Competitor |
| 55 | `contact.email_domain` | fact_path | L1 | 1 | 9000 | Company |
| 56 | `contract.clause.nonstandard` | fact_path | L1 | 1 | 9000 | Contract |
| 57 | `crm.contact.buying_role` | fact_path | L1 | 1 | 9000 | Stakeholder |
| 58 | `crm.contact.manager_id` | fact_path | L1 | 1 | 9000 | Contact |
| 59 | `crm.deal.budget` | fact_path | L1 | 1 | 9000 | Budget |
| 60 | `deal.created_at` | fact_path | L1 | 1 | 9000 | Market Map |
| 61 | `deal.outcome` | fact_path | L2 | 1 | 9000 | Persona |
| 62 | `derived.contact_duplicate_cluster` | derived | L2 | 1 | 9000 | Lead |
| 63 | `derived.cycle_days` | derived | L2 | 1 | 9000 | Market Map |
| 64 | `derived.persona_win_rate` | derived | L2 | 1 | 9000 | Persona |
| 65 | `funding_announced` | obs_kind | L2 | 1 | 9000 | Company |
| 66 | `internal_advocacy_statement` | obs_kind | L2 | 1 | 9000 | Champion |
| 67 | `metric_stated` | obs_kind | L2 | 1 | 9000 | Business Need |
| 68 | `need.target_metric` | fact_path | L2 | 1 | 9000 | Business Need |
| 69 | `proposal.valid_until` | fact_path | L1 | 1 | 9000 | Proposal |
| 70 | `renewal_signed` | obs_kind | L2 | 1 | 9000 | Fit Analysis |
| 71 | `research.interview.account_id` | fact_path | L1 | 1 | 9000 | Market Finding |
| 72 | `contract.term_months` | fact_path | L1 | 1 | 8800 | Market Map |
| 73 | `derived.document_viewer_identities` | derived | L2 | 1 | 8800 | Proposal |
| 74 | `forwarded_internally` | obs_kind | L2 | 1 | 8800 | Buying Signal |
| 75 | `account.incumbent_vendor` | fact_path | L1 | 1 | 8500 | Competitor |
| 76 | `budget_period_stated` | obs_kind | L2 | 1 | 8500 | Budget |
| 77 | `company.employee_count` | fact_path | L1 | 1 | 8500 | Company |
| 78 | `company.industry` | fact_path | L1 | 1 | 8500 | Company |
| 79 | `company.revenue_annual` | fact_path | L1 | 1 | 8500 | Company |
| 80 | `contact_role_change` | obs_kind | L1 | 1 | 8500 | Lead |
| 81 | `derived.account_open_deal_count` | derived | L2 | 1 | 8500 | Account |
| 82 | `derived.document_unique_viewers` | derived | L2 | 1 | 8500 | Proposal |
| 83 | `derived.objection_repeat_count` | derived | L2 | 1 | 8500 | Objection |
| 84 | `derived.usage_delta_vs_baseline` | derived | L2 | 1 | 8500 | Buying Signal |
| 85 | `discount_granted` | obs_kind | L2 | 1 | 8500 | Pricing |
| 86 | `form_submitted` | obs_kind | L1 | 1 | 8500 | Lead |
| 87 | `incumbent_named` | obs_kind | L2 | 1 | 8500 | ICP |
| 88 | `loss_reason` | obs_kind | L2 | 1 | 8500 | Disqualifier |
| 89 | `pain.statement_span` | fact_path | L2 | 1 | 8500 | Pain Point |
| 90 | `person.department` | fact_path | L1 | 1 | 8500 | Market Map |
| 91 | `person.reports_to` | fact_path | L1 | 1 | 8500 | Stakeholder |
| 92 | `product.active_users_7d` | fact_path | L1 | 1 | 8500 | Buying Signal |
| 93 | `product.usage_ratio` | fact_path | L1 | 1 | 8500 | Opportunity |
| 94 | `proposal_viewed` | obs_kind | L2 | 1 | 8500 | Proposal |
| 95 | `research.source.account_origin` | fact_path | L1 | 1 | 8500 | Market Finding |
| 96 | `security_questionnaire_received` | obs_kind | L2 | 1 | 8500 | Company |
| 97 | `success_criteria_shared` | obs_kind | L2 | 1 | 8500 | Business Need |
| 98 | `derived.close_date_slip_count` | derived | L2 | 1 | 8200 | Deal |
| 99 | `derived.meeting_attendance_rate` | derived | L2 | 1 | 8200 | Decision Maker |
| 100 | `derived.thread_participant_delta` | derived | L2 | 1 | 8200 | Buying Signal |
| 101 | `derived.timeline_slip_count` | derived | L2 | 1 | 8200 | Risk |
| 102 | `pricing_meeting` | obs_kind | L2 | 1 | 8200 | Decision Maker |
| 103 | `account.health_score` | fact_path | L2 | 1 | 8000 | ICP |
| 104 | `commitment.mitigates_risk` | fact_path | L2 | 1 | 8000 | Risk |
| 105 | `company.tech_stack` | fact_path | L1 | 1 | 8000 | Company |
| 106 | `comparison_requested` | obs_kind | L2 | 1 | 8000 | Competitor |
| 107 | `competitor.list_price` | fact_path | L1 | 1 | 8000 | Market Map |
| 108 | `contract.uplift_cap` | fact_path | L1 | 1 | 8000 | Pricing |
| 109 | `derived.cohort_similarity` | derived | L2 | 1 | 8000 | Fit Analysis |
| 110 | `derived.committee_persona_coverage` | derived | L2 | 1 | 8000 | Persona |
| 111 | `derived.deal_contact_count` | derived | L2 | 1 | 8000 | Deal |
| 112 | `derived.open_commitment_count` | derived | L2 | 1 | 8000 | Next Action |
| 113 | `derived.pain_topic_cluster` | derived | L2 | 1 | 8000 | Pain Point |
| 114 | `derived.sentiment_by_person` | derived | L2 | 1 | 8000 | Buying Committee |
| 115 | `internal_forward` | obs_kind | L2 | 1 | 8000 | Champion |
| 116 | `objection_category` | obs_kind | L2 | 1 | 8000 | Objection |
| 117 | `page_view` | obs_kind | L1 | 1 | 8000 | Buying Signal |
| 118 | `person.current_employer` | fact_path | L1 | 1 | 8000 | Opportunity |
| 119 | `procurement_engaged` | obs_kind | L2 | 1 | 8000 | Stakeholder |
| 120 | `reference_agreed` | obs_kind | L2 | 1 | 8000 | Account |
| 121 | `web.page_path` | fact_path | L1 | 1 | 8000 | Buying Signal |
| 122 | `objection_relayed` | obs_kind | L2 | 1 | 7800 | Objection |
| 123 | `calendar.attendees` | fact_path | L1 | 1 | 7500 | Stakeholder |
| 124 | `calendar.days_to_quarter_end` | fact_path | L1 | 1 | 7500 | Pricing |
| 125 | `derived.commitment_specificity` | derived | L2 | 1 | 7500 | Next Action |
| 126 | `derived.competitor_win_rate` | derived | L2 | 1 | 7500 | Competitor |
| 127 | `derived.reply_ratio` | derived | L2 | 1 | 7500 | Stakeholder |
| 128 | `hiring_surge` | obs_kind | L2 | 1 | 7500 | Company |
| 129 | `migration_concern` | obs_kind | L2 | 1 | 7500 | Market Map |
| 130 | `reopen_condition` | obs_kind | L1 | 1 | 7500 | Investor Conversation |
| 131 | `account.tech_stack` | fact_path | L1 | 1 | 7000 | Fit Analysis |
| 132 | `account_trigger` | obs_kind | L2 | 1 | 7000 | Opportunity |
| 133 | `committee.member_ids` | fact_path | L2 | 1 | 7000 | Pain Point |
| 134 | `crm.deal.close_date` | fact_path | L1 | 1 | 7000 | Timeline |
| 135 | `derived.account_engagement_no_deal` | derived | L2 | 1 | 7000 | Buying Signal |
| 136 | `derived.objection_intensity` | derived | L2 | 1 | 7000 | Objection |
| 137 | `derived.persona_outcome_variance` | derived | L2 | 1 | 7000 | Persona |
| 138 | `derived.reply_hour_histogram` | derived | L2 | 1 | 7000 | Contact |
| 139 | `derived.reply_term_frequency` | derived | L2 | 1 | 7000 | Persona |
| 140 | `derived.thread_seniority_delta` | derived | L2 | 1 | 7000 | Business Need |
| 141 | `page_view_pricing` | obs_kind | L1 | 1 | 7000 | Lead |
| 142 | `person_mentioned` | obs_kind | L2 | 1 | 7000 | Stakeholder |
| 143 | `risk.last_reviewed_at` | fact_path | L1 | 1 | 7000 | Risk |
| 144 | `account.icp_segment` | fact_path | L2 | 1 | 6000 | Persona |
| 145 | `application_status` | fact_path | L2 | 1 | 6000 | Investor Conversation |
| 146 | `programme_deadline` | obs_kind | L1 | 1 | 6000 | Investor Conversation |
| 147 | `funding.round` | fact_path | L2 | 1 | 5000 | Investor Conversation |
| 148 | `intent.topic_surge` | fact_path | L1 | 1 | 4500 | Buying Signal |

## Why each one matters

### `account.industry` · fact_path

- blocks **Disqualifier** / `dq.counterexample_detected` (would yield 9000 bp)
- blocks **Disqualifier** / `dq.regulatory_exclusion` (would yield 10000 bp)
- blocks **Disqualifier** / `dq.repeat_loss_signature` (would yield 8500 bp)
- blocks **Fit Analysis** / `fa.disqualifier_matched` (would yield 9500 bp)
- blocks **Fit Analysis** / `fa.resembles_the_churned_cohort` (would yield 8000 bp)
- blocks **ICP** / `icp.disqualifier_hit` (would yield 9500 bp)
- blocks **ICP** / `icp.firmographic_match` (would yield 9000 bp)
- blocks **Market Map** / `mm.segment_cut_by_budget_owner` (would yield 8500 bp)
- Disqualifier: The most absolute disqualifierclass in existence — no seller can override a licence we do not hold — and it is entirely invisible to the pipeline. Two enrichment fields would make it automatic.

### `contract_signed` · obs_kind

- blocks **Account** / `ac.signature_starts_the_customer_clock` (would yield 10000 bp)
- blocks **Contract** / `ct.executed` (would yield 10000 bp)
- blocks **Deal** / `dl.won_on_signature` (would yield 10000 bp)
- blocks **Decision Maker** / `dm.signed_a_prior_contract` (would yield 9800 bp)
- blocks **Market Map** / `mm.contract_norm_from_signed_paper` (would yield 8800 bp)
- blocks **Proposal** / `pr.signature_returned` (would yield 10000 bp)
- Account: L2 emits contract_requested andstops there. The single most consequential state transition in the whole object — prospect to customer, new business to expansion — happens on every won deal and is invisible to the pipeline.
- Contract: L2 emits contract_requested andnever contract_signed. The single most important state change in the entire revenue motion is invisible to the engine, which is why every downstream clock — renewal, obligation, onboarding — has to be started by hand.
- Deal: L2 emits contract_requested andnever contract_signed. The system can see a deal reach for paper and cannot see it close.
- Decision Maker: L2 emits contract_requested butnever contract_signed — the strongest available authority proof is dropped on the floor at exactly the moment it is proven.
- Proposal: The pipeline sees the paper processstart and never sees it finish.
- Market Map: L2 emits contract_requested andnever contract_signed, so the moment a market's real terms become knowable is the moment the pipeline stops watching.

### `account.geography` · fact_path

- blocks **Disqualifier** / `dq.regulatory_exclusion` (would yield 10000 bp)
- blocks **Fit Analysis** / `fa.disqualifier_matched` (would yield 9500 bp)
- blocks **ICP** / `icp.firmographic_match` (would yield 9000 bp)
- ICP: Firmographics are the cheapestenrichment in the stack and none of it is projected today. This one gap disables most of this object.
- Fit Analysis: The whole anti-fit half ofthis capability sits behind these three facts. They are the cheapest enrichment available anywhere in the stack and none of them is projected, so the disqualifier list can be authored, reviewed and published and still never fire.

### `crm.contact.role` · fact_path

- blocks **Buying Committee** / `bc.roles_from_crm` (would yield 8500 bp)
- blocks **Champion** / `ch.named_as_champion_in_crm` (would yield 8500 bp)
- blocks **Decision Maker** / `dm.crm_role_field` (would yield 10000 bp)
- Decision Maker: CRM connector exists; the contactrole field is not projected into a typed L2 fact yet.

### `account.retention_months` · fact_path

- blocks **Disqualifier** / `dq.churn_signature` (would yield 9200 bp)
- blocks **Disqualifier** / `dq.counterexample_detected` (would yield 9000 bp)
- blocks **Fit Analysis** / `fa.retention_confirms_the_reading` (would yield 9000 bp)
- Disqualifier: The strongest evidenceclass this object recognises, and the pipeline cannot see any of it. Everything downstream of the sale is invisible to Layer 2, which means the profile can only ever be validated on the half of the outcome that arrives first and matters least.
- Disqualifier: The self-correctionmechanism. Without it a disqualifier list only ever grows, because the evidence that would shrink it lives in accounts nobody looks at again.

### `person.seniority` · fact_path

- blocks **Business Need** / `bn.an_executive_joined_the_thread` (would yield 7000 bp)
- blocks **Buying Signal** / `bs.a_more_senior_person_joined_the_thread` (would yield 8200 bp)
- blocks **Decision Maker** / `dm.highest_seniority_across_the_thread` (would yield 6000 bp)
- Business Need: Requires title normalisationfrom the directory or CRM.
- Buying Signal: Requires title normalisation.
- Decision Maker: Requires title normalisation.Weak on its own — VP of Engineering outranks a Finance Manager on paper and cannot approve the spend.

### `research.finding.collected_at` · fact_path

- blocks **Market Finding** / `mf.expired_by_calendar` (would yield 10000 bp)
- blocks **Market Finding** / `mf.superseded_by_a_newer_claim` (would yield 9500 bp)
- Market Finding: The finding's owndate is the cheapest input imaginable and there is no store for it. Without collected_at nothing can expire, and research that cannot expire is cited indefinitely — the defining failure of the discipline, unenforceable today.

### `contract.end_date` · fact_path

- blocks **Account** / `ac.renewal_date_from_the_paper` (would yield 9500 bp)
- blocks **Contract** / `ct.renewal_notice_window_open` (would yield 9800 bp)
- Account: Renewal dates entered by handare wrong on a predictable fraction of accounts, and always in the direction of being too late to act on.
- Contract: No contract dates reach theengine at all, so the renewal clock cannot start. This is the mechanical cause of late-discovered churn — not a customer-success failure, a missing field.

### `account.employee_count` · fact_path

- blocks **Fit Analysis** / `fa.disqualifier_matched` (would yield 9500 bp)
- blocks **ICP** / `icp.firmographic_match` (would yield 9000 bp)

### `closed_lost_reason` · obs_kind

- blocks **Competitor** / `comp.loss_attributed` (would yield 9500 bp)
- blocks **Risk** / `risk.realisation_attributed` (would yield 9500 bp)
- Competitor: closed_lost_mention exists but carries no reason, so losses to the status quo and losses to a rival are indistinguishable. Without this the win-rate calibration that justifies competitive weighting can never be computed.

- Risk: closed_lost_mention fires with no reason attached, so the register never learns. Without attribution, likelihood_bp is permanently a guess and no category base rate can ever be computed — the whole assessment half of this object stays uncalibrated.


### `crm.contact.approval_limit` · fact_path

- blocks **Contract** / `ct.signatory_authority_mismatch` (would yield 9500 bp)
- blocks **Decision Maker** / `dm.declared_approval_limit` (would yield 9500 bp)
- Contract: Deal value is knownand signing authority is not, so the one arithmetic check that would catch an unenforceable signature cannot run.

### `account.segment` · fact_path

- blocks **Market Finding** / `mf.corroborated_across_accounts` (would yield 9200 bp)
- blocks **Market Map** / `mm.segment_shape_from_population` (would yield 9200 bp)
- Market Finding: A grouping key on the account.Nothing in the substrate can express 'these accounts belong together'.
- Market Map: A grouping key on the account.Nothing else in the substrate can express 'these accounts belong together'.

### `derived.segment_aggregate` · derived

- blocks **Market Finding** / `mf.corroborated_across_accounts` (would yield 9200 bp)
- blocks **Market Map** / `mm.segment_shape_from_population` (would yield 9200 bp)
- Market Finding: THE structural gap. Everypredicate is evaluated against one node and its one-hop neighbours, so every executable pattern above is worth exactly one account of evidence — while the object's whole purpose is to record claims about a population. A segment key plus an aggregate over it converts single-deal corroboration into real corroboration and unblocks most of the blocked half of this capability.
- Market Map: THE structural gap forthis object. Every predicate is evaluated against one node and its one-hop neighbours, so no authored pattern here can ever be evidenced by more than one deal — while the object's entire subject is a population. This single addition converts the blocked half of this file into the executable half.

### `account_trigger_event` · obs_kind

- blocks **ICP** / `icp.trigger_event_present` (would yield 8500 bp)
- blocks **Market Map** / `mm.trigger_driven_purchase` (would yield 8000 bp)
- ICP: Requires an external-signalconnector. The difference between a target list and a pipeline.
- Market Map: Requires an external-signalconnector. This is the difference between a target list and a pipeline: without triggers every account in a segment looks equally ready, and almost none of them are.

### `crm.contact.title_normalised` · fact_path

- blocks **Contact** / `contact.crm_states_the_title` (would yield 8000 bp)
- blocks **Persona** / `persona.assigned_from_normalised_title` (would yield 8500 bp)
- Contact: The CRM connector reads the record; the title is never projected into a typed L2 fact, so persona assignment has nothing to key on and every contact starts unclassified.
- Persona: The obvious routeto assignment and the one that does not exist. Without it every contact starts unclassified and outreach falls back to generic copy, which is the failure this object was built to prevent.

### `pain_stated` · obs_kind

- blocks **Pain Point** / `pp.buyer_stated_the_problem` (would yield 8500 bp)
- blocks **Pain Point** / `pp.same_problem_named_across_stakeholders` (would yield 8000 bp)
- Pain Point: The largest single hole in the substrate.Layer 2 emits objection, objection_price and discount_pressure — every commercial reaction to our price — and nothing at all for a buyer describing a problem. The entire discovery half of the sale is invisible, so this object can currently only be inferred from the commercial signals that come after it.

### `account.prior_deal_outcomes` · fact_path

- blocks **Buying Committee** / `bc.decision_style_from_history` (would yield 7500 bp)
- blocks **ICP** / `icp.churn_predictor_present` (would yield 8000 bp)

### `party.role` · fact_path

- blocks **Investor Conversation** / `ic.own_domain_false_party` (would yield 8000 bp)
- blocks **Investor Conversation** / `ic.partner_reached` (would yield 7000 bp)
- Investor Conversation: Also declared expected for `investor_contact` and also unwritten. Seniority is present in signature blocks Layer 1 already reads and is discarded before it reaches the graph.
- Investor Conversation: The design partner's own domain appears in this set today. A self-filter needs a role, and the org-seats path that would have supplied one is empty.

### `competing_initiative` · obs_kind

- blocks **Budget** / `bg.competing_priority_detected` (would yield 7000 bp)
- blocks **Business Need** / `bn.a_competing_initiative_was_named` (would yield 7500 bp)
- Budget: Distinguishes a deprioritiseddeal from a stalled one. They need opposite responses and currently look identical.
- Business Need: Layer 2 has a vocabularyfor rival vendors and none for rival projects, which is the wrong way round: most enterprise losses are to the buyer's own roadmap, not to a competitor's proposal.

### `channel_touch` · l2_situation_type

- blocks **[situation] Touch Outside Mail** / `sales.sit.touch_outside_mail` (would yield 10000 bp)
- Touch Outside Mail: WHAT THE TYPE MUST MEAN. An interaction on a non-mail channel, carrying the channel, the direction, the participants, the outcome and — for a call or a demo — whether it connected and what was shown. Outcome is the requirement: a dialled number and a conversation are the same event to a log and completely different events to a seller.
WHAT WOULD EMIT IT. Layer 1 connectors that do not exist — a dialler or telephony provider, a LinkedIn export, a demo or meeting-recording tool. This is a capture problem, not an extraction one: no amount of reading email recovers a call that happened.
WHAT GOES WRONG TODAY. Nothing fires for cold_calling, linkedin_outreach or demo.
WHY BINDING TO relationship WOULD BE WRONG, specifically. (1) It would infer a call from the absence of mail, which is not evidence of anything. (2) `demo` advice built on a meeting title is advice built on a string somebody typed into a calendar — the design partner's `meeting.title` values are largely cohort session names. (3) Channel-specific expertise is the entire content of these capabilities; opening mechanics for a call and for an email are different disciplines, and serving one with the other's evidence produces confident advice about a conversation that may never have happened.

- Touch Outside Mail: closest type emitted today is `relationship` — close enough to be tempting, not close enough to be true

### `contract.executed_at` · fact_path

- blocks **Contract** / `ct.executed` (would yield 10000 bp)

### `email_bounced` · obs_kind

- blocks **Contact** / `contact.address_hard_bounced` (would yield 10000 bp)
- Contact: Delivery telemetry is available from every mail provider and none of it is ingested. Without it the system cannot tell silence from non-delivery, and those two states want opposite next actions.

### `icp.active_profile_version` · fact_path

- blocks **Fit Analysis** / `fa.profile_version_superseded` (would yield 10000 bp)
- Fit Analysis: Requires the OrganizationBrain's active profile version to be projected as a fact. Without it, staleness can only be approximated by wall-clock age, which is wrong in both directions — a profile can go a year without changing, or change twice in a month.

### `market_period_review` · l2_situation_type

- blocks **[situation] Touch Outside Mail** / `sales.sit.touch_outside_mail` (would yield 10000 bp)
- Touch Outside Mail: WHAT THE TYPE MUST MEAN. A market rather than an account — segment size, reachable share, and where the current customer base actually sits within it. Its anchor is a SEGMENT and a window.
WHAT WOULD EMIT IT. The same tenant-anchored periodic mechanism named in `sales.sit.pipeline_period_review`, plus external market data the graph has no source for.
WHAT GOES WRONG TODAY. Nothing fires for tam_sam_som.
WHY BINDING TO opportunity WOULD BE WRONG, specifically. A market size asserted on one account is not a market size. `icp_definition` and `market_research` — the two neighbours that ARE routed — read a single account against a profile, which is a genuinely different and genuinely per-account question; sizing is not.

- Touch Outside Mail: closest type emitted today is `opportunity` — close enough to be tempting, not close enough to be true

### `opportunity.status` · fact_path

- blocks **Opportunity** / `op.opportunity_node_exists` (would yield 10000 bp)
- Opportunity: The structural gap. L2 materialisesa deal-shaped node as soon as a thread exists, so a possibility with no thread has nowhere to attach and a possibility with a thread is already recorded as a deal. Every executable pattern on this object is therefore firing against a node that has already crossed the boundary the object is meant to police.

### `catalogue.list_price` · fact_path

- blocks **Pricing** / `pr.list_price_from_catalogue` (would yield 9800 bp)
- Pricing: Without list_price, discount_bpcannot be computed at all, so every discount rule in this file is currently unenforceable and every discount metric is uncomputable. The cheapest high-value connector on this object.

### `contract.renewal_date` · fact_path

- blocks **Opportunity** / `op.renewal_window_from_contract` (would yield 9800 bp)
- Opportunity: Renewal is the most predictablerevenue in the business and the only opportunity type that arrives with a known date attached. Nothing emits it, so renewals are worked from memory and discovered late.

### `contract.renewal_notice_days` · fact_path

- blocks **Contract** / `ct.renewal_notice_window_open` (would yield 9800 bp)

### `crm.deal.stage` · fact_path

- blocks **Deal** / `dl.crm_stage_is_authoritative` (would yield 9800 bp)
- Deal: deal.status is projected but isonly open/won/lost. The stage a seller actually manages the deal by is not projected at all, so every stage above is reconstructed from observations that were never designed to carry it.

### `account.incumbent_contract_end` · fact_path

- blocks **Timeline** / `tl.renewal_or_expiry_anchor` (would yield 9500 bp)

### `commitment.owner` · fact_path

- blocks **Next Action** / `na.owner_is_named` (would yield 9500 bp)
- Next Action: The substrate emits the actionand the date and never the owner. Every executable pattern on this object therefore assumes silently that the action is ours — which is precisely the failure the object exists to prevent. Highest-value gap here by some distance.

### `company.parent_domain` · fact_path

- blocks **Company** / `co.parent_from_the_register` (would yield 9500 bp)
- Company: Without it subsidiariesinherit the parent's segment by accident, which is how a forty-person business unit ends up in an enterprise territory.

### `contact_departed` · obs_kind

- blocks **Contact** / `contact.left_the_company` (would yield 9500 bp)
- Contact: L2 emits champion_change, which only fires for a mapped champion. An ordinary contact leaving is invisible, so sequences keep running into a dead mailbox and the org chart silently rots. This is the single highest-value gap on this object: it is cheap to detect from bounce plus auto-reply text and it corrupts every downstream map when missed.

### `crm.account.arr` · fact_path

- blocks **Account** / `ac.crm_account_link` (would yield 9500 bp)

### `crm.account.id` · fact_path

- blocks **Account** / `ac.crm_account_link` (would yield 9500 bp)
- Account: The connector reads deals andcontacts but never the account object above them, so the record that already holds the answer to almost every field here is not projected.

### `crm.deal.close_date_history` · fact_path

- blocks **Timeline** / `tl.close_date_history` (would yield 9500 bp)
- Timeline: Highest-value unbuiltsignal on this object. Slip count is the strongest single loss predictor in most pipelines and it is sitting in CRM field history untouched.

### `crm.deal.loss_reason` · fact_path

- blocks **Deal** / `dl.loss_reason_recorded` (would yield 9500 bp)
- Deal: Without it, Layer 6 cannotseparate a qualification failure from a positioning failure, and every loss is coached the same way.

### `crm.opportunity.stage` · fact_path

- blocks **Opportunity** / `op.crm_opportunity_record` (would yield 9500 bp)
- Opportunity: Most CRMs conflate opportunityand deal into one object, which is exactly the conflation this file exists to undo. The connector must distinguish them or the distinction is unenforceable downstream.

### `crm.pricing.max_discount` · fact_path

- blocks **Pricing** / `pr.approved_discount_ceiling` (would yield 9500 bp)
- Pricing: Policy lives in a spreadsheetin most organisations. Until it is a fact path, approval_risk is judged by whoever is on the call.

### `derived.claim_key` · derived

- blocks **Market Finding** / `mf.superseded_by_a_newer_claim` (would yield 9500 bp)
- Market Finding: Requires normalising claim_typeplus subject_segment into a comparable key. Without it, two findings that contradict each other simply coexist in the same map.

### `need.baseline_value` · fact_path

- blocks **Business Need** / `bn.baseline_and_target_captured` (would yield 9500 bp)

### `need.target_value` · fact_path

- blocks **Business Need** / `bn.baseline_and_target_captured` (would yield 9500 bp)
- Business Need: Baseline without target ishalf a business case and reads as complete, which is worse than having neither.

### `objection_resolved` · obs_kind

- blocks **Objection** / `obj.resolution_recorded` (would yield 9500 bp)
- Objection: The highest-value gap on this object by a distance. Layer 2 opens objections and never closes them, so every objection in the register is permanently open and the `recurring` state can never be distinguished from a first raise. Every recurrence heuristic below is downstream of this one signal.


### `outbound.sent_at` · fact_path

- blocks **Lead** / `lead.response_sla_breached` (would yield 9500 bp)
- Lead: The substrate records when THEYreplied and never when WE did. So the most controllable lever on inbound conversion — measured in minutes, not days — cannot be measured, let alone alerted on. This is the highest-value gap on this object: it is trivially available from the mail connector's own send log.

### `proposal_revised` · obs_kind

- blocks **Proposal** / `pr.version_superseded` (would yield 9500 bp)
- Proposal: L2 emits proposal_sent identicallyfor a first issue and a fourth revision. Revision count is one of the strongest stall indicators in the pipeline and is currently indistinguishable from progress.

### `risk.owner` · fact_path

- blocks **Risk** / `risk.owner_declared` (would yield 9500 bp)
- Risk: The highest-value gap on this object, and the one that decides whether it works at all. Nothing in the pipeline can express who owns a risk, so every inferred risk is born unowned and stays that way. Until a risk can carry an owner and that owner can be chased, this object detects threats accurately and changes nothing about them.


### `churn_event` · obs_kind

- blocks **Disqualifier** / `dq.churn_signature` (would yield 9200 bp)

### `pain.annual_cost` · fact_path

- blocks **Pain Point** / `pp.cost_quantified_by_the_buyer` (would yield 9200 bp)
- Pain Point: Number plus unit plus period.A figure without a period is the most common way a business case inflates by twelve.

### `quantification_stated` · obs_kind

- blocks **Pain Point** / `pp.cost_quantified_by_the_buyer` (would yield 9200 bp)

### `accountability_stated` · obs_kind

- blocks **Pain Point** / `pp.owner_named_explicitly` (would yield 9000 bp)
- Pain Point: Transcripts carry this constantly— 'that sits with me', 'Priya owns that number' — and it is dropped. It is the field the whole object turns on.

### `clause_conceded` · obs_kind

- blocks **Contract** / `ct.nonstandard_clause_agreed` (would yield 9000 bp)

### `commitment_completed` · obs_kind

- blocks **Next Action** / `na.completion_unobservable` (would yield 9000 bp)
- Next Action: followup_sent covers emailactions on our side only. A call made, a document shared outside email, or anything the buyer did is invisible, so na.overdue fires against commitments that were met. Nothing erodes trust in a reminder system faster than being nagged about something already done.

### `compelling_event_stated` · obs_kind

- blocks **Timeline** / `tl.compelling_event_stated` (would yield 9000 bp)
- Timeline: Requires extracting anevent and its consequence together. Extracting the date alone produces exactly the soft timeline this object exists to distinguish.

### `competitor.name` · fact_path

- blocks **Competitor** / `comp.identity_extracted` (would yield 9000 bp)
- Competitor: The highest-value gap on this object. Layer 2 knows a competitor was mentioned and not which one, so historical_win_rate_bp can never be joined, counter_positioning can never be selected, and every competitive deal is handled generically. One named entity would activate the entire counter-strategy half of this file.


### `contact.email_domain` · fact_path

- blocks **Company** / `co.domain_from_correspondent_email` (would yield 9000 bp)
- Company: The highest-value gap onthis object and probably the cheapest in the whole backlog. Every message already ingested carries the company's only durable natural key in its From header, and it is discarded. Without it Company records cannot be deduplicated, cannot be enriched automatically, and cannot be linked to an account by anything except a hand-typed name.

### `contract.clause.nonstandard` · fact_path

- blocks **Contract** / `ct.nonstandard_clause_agreed` (would yield 9000 bp)
- Contract: Structured clauseextraction from the redlined document — clause type, deviation from template, who approved. Without it the nonstandard_clauses list is populated by whoever remembers to type it, which in practice is nobody, and this object's central thesis is unserved.

### `crm.contact.buying_role` · fact_path

- blocks **Stakeholder** / `sh.crm_buying_role_declared` (would yield 9000 bp)
- Stakeholder: The CRM connector readscontacts but does not project role or buying-group membership into a typed L2 fact, so the one place a human already wrote the answer is unreadable.

### `crm.contact.manager_id` · fact_path

- blocks **Contact** / `contact.reporting_line_from_the_org_chart` (would yield 9000 bp)
- Contact: reports_to is the field that makes a missing committee seat visible — two hops up from a user is usually where the money sits — and nothing populates it. The org chart exists in every HRIS and every enrichment vendor, and reaches neither the CRM projection nor the graph, so the escalation path has to be discovered by asking.

### `crm.deal.budget` · fact_path

- blocks **Budget** / `bg.amount_in_crm` (would yield 9000 bp)
- Budget: deal.value is projected today,but deal value is what WE proposed, not what THEY have. Conflating the two is the reason forecasts read high.

### `deal.created_at` · fact_path

- blocks **Market Map** / `mm.cycle_length_from_history` (would yield 9000 bp)
- Market Map: The pipeline cannot compute asingle deal's cycle length, let alone a segment's — there is no creation timestamp in the substrate, only last_inbound.

### `deal.outcome` · fact_path

- blocks **Persona** / `persona.calibrated_from_closed_outcomes` (would yield 9000 bp)
- Persona: deal.status exists; a terminal won/lostoutcome does not.

### `derived.contact_duplicate_cluster` · derived

- blocks **Lead** / `lead.duplicate_of_an_open_lead` (would yield 9000 bp)
- Lead: Duplicates arethe default state of any lead database with more than one source. Nothing clusters them, so two reps run two cadences into one inbox and the buyer concludes we are disorganised before the first call.

### `derived.cycle_days` · derived

- blocks **Market Map** / `mm.cycle_length_from_history` (would yield 9000 bp)

### `derived.persona_win_rate` · derived

- blocks **Persona** / `persona.calibrated_from_closed_outcomes` (would yield 9000 bp)
- Persona: Every closed outcome alreadyexists in the CRM and none of them are joined back to the persona that was targeted. As a result every win_rate_bp in the library is a guess, permanently, and the calibration state validated is unreachable.

### `funding_announced` · obs_kind

- blocks **Company** / `co.funding_event_observed` (would yield 9000 bp)
- Company: A company-level buying signalthat fires with no deal in existence. Every observation kind L2 emits today presupposes an open conversation, so the entire class of pre-deal timing signals is currently unreachable.

### `internal_advocacy_statement` · obs_kind

- blocks **Champion** / `ch.argued_our_case_in_a_meeting` (would yield 9000 bp)
- Champion: Requires speaker-attributedtranscript analysis. The definitive signal, and the hardest to get.

### `metric_stated` · obs_kind

- blocks **Business Need** / `bn.target_metric_stated_by_the_buyer` (would yield 9000 bp)
- Business Need: The defining gap for this object.Layer 2 can see budget approved, price discussed and contracts requested — every commercial event — and cannot see the number the commerce is for. Everything measurable about the sale after signature depends on this one observation kind.

### `need.target_metric` · fact_path

- blocks **Business Need** / `bn.target_metric_stated_by_the_buyer` (would yield 9000 bp)

### `proposal.valid_until` · fact_path

- blocks **Proposal** / `pr.expiry_lapsed` (would yield 9000 bp)
- Proposal: No expiry date is projectedinto a typed fact, so no expiry can ever be enforced automatically — which is precisely why expiries in practice are never enforced.

### `renewal_signed` · obs_kind

- blocks **Fit Analysis** / `fa.retention_confirms_the_reading` (would yield 9000 bp)
- Fit Analysis: Layer 2 emits contract_requestedand nothing at all about the second contract. The profession validates a profile on retention; the pipeline can watch every deal close and never learn whether closing it was a good idea.

### `research.interview.account_id` · fact_path

- blocks **Market Finding** / `mf.sample_size_from_corpus` (would yield 9000 bp)
- Market Finding: No research corpusis ingested at all. Interviews live in documents and recordings that Layer 1 never links to an account, so the strongest evidence this object can hold is invisible to every pattern above.

### `contract.term_months` · fact_path

- blocks **Market Map** / `mm.contract_norm_from_signed_paper` (would yield 8800 bp)

### `derived.document_viewer_identities` · derived

- blocks **Proposal** / `pr.forwarded_to_the_room` (would yield 8800 bp)
- Proposal: The positivecase of the same gap. Unknown viewers are the earliest possible detection of a buying committee that nobody told us about — weeks before the first introduction observation fires.

### `forwarded_internally` · obs_kind

- blocks **Buying Signal** / `bs.email_forwarded_internally` (would yield 8800 bp)
- Buying Signal: The highest-signal behaviourin enterprise email and completely invisible. A buyer forwarding our note to their boss is stronger evidence than any reply they could write, because it is them selling internally rather than us selling externally. Detectable from reply-chain quoting and new participants appearing on a thread.

### `account.incumbent_vendor` · fact_path

- blocks **Competitor** / `comp.incumbent_from_renewal_window` (would yield 8500 bp)
- Competitor: Requires the CRM or contract store to project the current vendor and renewal date. Without it, every displacement deal is run as a greenfield sale and the switching cost is discovered at the redline stage, which is the most expensive place to find it.


### `budget_period_stated` · obs_kind

- blocks **Budget** / `bg.fiscal_period_declared` (would yield 8500 bp)

### `company.employee_count` · fact_path

- blocks **Company** / `co.firmographics_from_enrichment` (would yield 8500 bp)
- Company: Depends on co.domain_from_correspondent_email— enrichment is keyed on domain, so the two are one chain and ordering matters.

### `company.industry` · fact_path

- blocks **Company** / `co.firmographics_from_enrichment` (would yield 8500 bp)

### `company.revenue_annual` · fact_path

- blocks **Company** / `co.firmographics_from_enrichment` (would yield 8500 bp)

### `contact_role_change` · obs_kind

- blocks **Lead** / `lead.past_champion_started_a_new_job` (would yield 8500 bp)
- Lead: The highest-converting leadsource in B2B by a wide margin — they already know the product and already argued for it once — and nothing watches for it. Every won deal creates several of these and all of them are discarded when the champion's address bounces.

### `derived.account_open_deal_count` · derived

- blocks **Account** / `ac.second_live_deal_means_expansion` (would yield 8500 bp)
- Account: The highest-valuegap on this object. Every fact path in the substrate is deal- or thread-scoped, so no account-level aggregate exists at all — the engine literally cannot count how many deals an account has. That single absence is why expansion cannot be told from new business, why coverage falls back to graph degree, and why account recency is approximated from whichever deal happened to be busiest.

### `derived.document_unique_viewers` · derived

- blocks **Proposal** / `pr.never_left_the_champion` (would yield 8500 bp)
- Proposal: Document telemetry— who opened, how many times, from what domain. This is the highest-value missing signal on this object by a wide margin: it converts the single most predictive field, reaches_committee, from a guess into a fact.

### `derived.objection_repeat_count` · derived

- blocks **Objection** / `obj.repeated_objection_is_the_real_one` (would yield 8500 bp)
- Objection: The engine can ask whether an observation kind is present but not how many times it has fired, so recurrence — the strongest diagnostic this object has — is invisible. Needs a per-kind count, or at minimum a repeat flag, on the node.


### `derived.usage_delta_vs_baseline` · derived

- blocks **Buying Signal** / `bs.product_usage_accelerated` (would yield 8500 bp)
- Buying Signal: In any product-ledmotion this is the strongest first-party signal that exists and there is no connector for it. The delta matters, not the level — a flat high-usage account is a customer, a rising one is a buyer.

### `discount_granted` · obs_kind

- blocks **Pricing** / `pr.discount_conceded_without_exchange` (would yield 8500 bp)
- Pricing: The standout gap on this object.L2 emits discount_pressure — the buyer asking — and never discount_granted, the moment we said yes. The concession itself is invisible, so pr.no_discount_without_exchange cannot fire, discount discipline cannot be measured, and Layer 6 has no way to learn which reps give away margin.

### `form_submitted` · obs_kind

- blocks **Lead** / `lead.submitted_an_inbound_form` (would yield 8500 bp)
- Lead: Web and marketing-automation eventsare the single largest intent source in an inbound motion and none of them reach the graph. Today an inbound lead has to announce itself twice — once on the form and again in email — before the system notices it exists, and the SLA clock starts at the second one.

### `incumbent_named` · obs_kind

- blocks **ICP** / `icp.incumbent_detected` (would yield 8500 bp)
- ICP: The `competitor` observation existsbut does not distinguish an incumbent from an evaluated alternative. Those are different sales.

### `loss_reason` · obs_kind

- blocks **Disqualifier** / `dq.repeat_loss_signature` (would yield 8500 bp)
- Disqualifier: closed_lost_mention exists but carriesno reason. Without the reason a loss cohort cannot be grouped, and without grouping there is no evidence base for any disqualifier at all — this is the gate on the entire lifecycle above.

### `pain.statement_span` · fact_path

- blocks **Pain Point** / `pp.buyer_stated_the_problem` (would yield 8500 bp)
- Pain Point: The verbatim span mattersas much as the flag. A paraphrase cannot be quoted back.

### `person.department` · fact_path

- blocks **Market Map** / `mm.segment_cut_by_budget_owner` (would yield 8500 bp)
- Market Map: Department is present in everyemail signature and CRM contact record and is projected into no typed fact. Without it the strongest segmentation basis is unavailable and firmographic segmentation wins by default.

### `person.reports_to` · fact_path

- blocks **Stakeholder** / `sh.reports_to_from_org_chart` (would yield 8500 bp)
- Stakeholder: Without a reporting line, influence_routecan only ever be guessed, and route length is the property that separates a harmless dissenter from a fatal one.

### `product.active_users_7d` · fact_path

- blocks **Buying Signal** / `bs.product_usage_accelerated` (would yield 8500 bp)

### `product.usage_ratio` · fact_path

- blocks **Opportunity** / `op.expansion_from_product_usage` (would yield 8500 bp)
- Opportunity: The highest-yield opportunitysource in any subscription business and the one no sales system sees, because usage lives in the product database and the CRM never asks it.

### `proposal_viewed` · obs_kind

- blocks **Proposal** / `pr.never_left_the_champion` (would yield 8500 bp)

### `research.source.account_origin` · fact_path

- blocks **Market Finding** / `mf.own_funnel_bias_detected` (would yield 8500 bp)
- Market Finding: The most commondefect in market research is entirely invisible to the pipeline. Knowing whether a source was already in our funnel is a one-bit fact and it decides whether a finding can ever be corroborated.

### `security_questionnaire_received` · obs_kind

- blocks **Company** / `co.regime_from_the_security_questionnaire` (would yield 8500 bp)
- Company: security_review_startedfires but carries no payload, so the document that answers the compliance question in full arrives, is read by a human, and leaves no trace in the graph.

### `success_criteria_shared` · obs_kind

- blocks **Business Need** / `bn.success_criteria_written_down` (would yield 8500 bp)
- Business Need: Distinguishable from proposal_sentby direction and content. A mutual action plan or evaluation-criteria document is the strongest late-stage predictor available and currently indistinguishable from any other attachment.

### `derived.close_date_slip_count` · derived

- blocks **Deal** / `dl.repeated_close_date_slip` (would yield 8200 bp)
- Deal: timeline_slip fireson language in a thread, which catches the buyer saying it and misses the rep quietly editing the date. Slip counted from the record itself is the more honest of the two and does not exist.

### `derived.meeting_attendance_rate` · derived

- blocks **Decision Maker** / `dm.attends_every_commercial_meeting` (would yield 8200 bp)

### `derived.thread_participant_delta` · derived

- blocks **Buying Signal** / `bs.a_more_senior_person_joined_the_thread` (would yield 8200 bp)
- Buying Signal: A new senior participantis an internal escalation we did not cause, which outranks every behaviour the buyer performs towards us directly.

### `derived.timeline_slip_count` · derived

- blocks **Risk** / `risk.repeat_timeline_slip` (would yield 8200 bp)
- Risk: The engine can see that timeline_slip fired but not that it fired twice, so the profession's most reliable second-order tell is invisible. One slip is a calendar. Two means something else is untrue — usually an approver nobody has mapped or a budget that was never actually approved — and the risk should be re-categorised away from timing entirely.


### `pricing_meeting` · obs_kind

- blocks **Decision Maker** / `dm.attends_every_commercial_meeting` (would yield 8200 bp)
- Decision Maker: pricing_discussed exists but isthread-scoped, not meeting-scoped, so attendance cannot be computed.

### `account.health_score` · fact_path

- blocks **ICP** / `icp.churn_predictor_present` (would yield 8000 bp)

### `commitment.mitigates_risk` · fact_path

- blocks **Risk** / `risk.mitigation_owner_missed_the_date` (would yield 8000 bp)
- Risk: commitment.action and commitment.due_at both exist, but nothing links a commitment to the risk it was meant to close. So an overdue commitment is visible, an unmitigated risk is visible, and the fact that they are the same failure is not.


### `company.tech_stack` · fact_path

- blocks **Company** / `co.tech_stack_from_the_website` (would yield 8000 bp)
- Company: Names the incumbent beforethe first call. Knowing a competitor is already installed changes the opening question, not merely the fit score.

### `comparison_requested` · obs_kind

- blocks **Competitor** / `comp.trap_questions_arrive_verbatim` (would yield 8000 bp)
- Competitor: Requires matching buyer language against known competitor framing. The clearest evidence of an active, coached evaluation and it currently produces nothing.


### `competitor.list_price` · fact_path

- blocks **Market Map** / `mm.prevailing_price_band` (would yield 8000 bp)
- Market Map: Vendor pricing pages arepublic, static and unscraped. This is the cheapest market fact in existence and none of it is collected.

### `contract.uplift_cap` · fact_path

- blocks **Pricing** / `pr.uncapped_uplift_conceded` (would yield 8000 bp)
- Pricing: Contract terms are neverparsed back into facts, so the most durable commercial concession in the deal is the one nothing can see. It surfaces two years later as a renewal that cannot be priced up.

### `derived.cohort_similarity` · derived

- blocks **Fit Analysis** / `fa.resembles_the_churned_cohort` (would yield 8000 bp)
- Fit Analysis: Needs closed-and-churnedhistory joined to firmographics. The single most useful thing this object could compute and the furthest from being possible.

### `derived.committee_persona_coverage` · derived

- blocks **Persona** / `persona.missing_seat_on_the_committee` (would yield 8000 bp)
- Persona: Predicting theseats and comparing them to the mapped contacts is the single most valuable thing a persona library can do, and it needs a per-deal coverage computation that does not exist. Today an unmapped economic buyer is discovered when the deal stops, not before.

### `derived.deal_contact_count` · derived

- blocks **Deal** / `dl.single_threaded_open_deal` (would yield 8000 bp)
- Deal: fn:edge_count is rawgraph degree — threads, meetings and commitments all count — so a busy single-threaded deal looks well covered and a quiet three-contact deal looks single-threaded. Distinct human contacts on the buying side is the number every enterprise risk model needs and nothing emits it.

### `derived.open_commitment_count` · derived

- blocks **Next Action** / `na.competing_actions` (would yield 8000 bp)
- Next Action: commitment.actionresolves to a single latest value, so the substrate cannot express a SET of open commitments. The object's defining rule — a deal with six next actions has none — is therefore unenforceable today, and the failure it names is invisible.

### `derived.pain_topic_cluster` · derived

- blocks **Pain Point** / `pp.same_problem_named_across_stakeholders` (would yield 8000 bp)
- Pain Point: Needs topic clusteringacross threads and participants — the same problem is rarely described in the same words twice, so string matching will under-count and quietly favour the loudest stakeholder.

### `derived.sentiment_by_person` · derived

- blocks **Buying Committee** / `bc.per_member_sentiment` (would yield 8000 bp)
- Buying Committee: derived.sentiment isdeal-scoped today, so it can say the room is unhappy but never who. Locating the dissenter is the entire value of this object.

### `internal_forward` · obs_kind

- blocks **Champion** / `ch.circulated_material_internally` (would yield 8000 bp)
- Champion: Requires recipient-set diffingacross a thread. High value: it is the clearest observable act of internal selling.

### `objection_category` · obs_kind

- blocks **Objection** / `obj.category_from_classifier` (would yield 8000 bp)
- Objection: Today `objection` is an untyped flag and `objection_price` is the only subtype. Timing, authority, security and trust objections all collapse into the same observation, so the register cannot be read by category at all.


### `page_view` · obs_kind

- blocks **Buying Signal** / `bs.pricing_page_visited` (would yield 8000 bp)
- Buying Signal: The single most-used commercial signalin the industry and the pipeline cannot see it at all. There is no web connector, so every website behaviour — pricing, docs, careers, repeat visits — is invisible.

### `person.current_employer` · fact_path

- blocks **Opportunity** / `op.champion_landed_elsewhere` (would yield 8000 bp)
- Opportunity: champion_change alreadyfires on the account they left, so the system sees the loss and misses the opportunity on the other side of it. The highest-converting cold outreach in B2B and it is thrown away twice a year per champion.

### `procurement_engaged` · obs_kind

- blocks **Stakeholder** / `sh.owns_the_procurement_gate` (would yield 8000 bp)
- Stakeholder: L2 emits legal_review andsecurity_review_started but nothing for procurement, which in most enterprises is the gate that actually sets the signature date.

### `reference_agreed` · obs_kind

- blocks **Account** / `ac.reference_willingness_from_behaviour` (would yield 8000 bp)
- Account: Willingness to be named to astranger is the only satisfaction measure a customer cannot politely fake.

### `web.page_path` · fact_path

- blocks **Buying Signal** / `bs.pricing_page_visited` (would yield 8000 bp)
- Buying Signal: Path plus identified visitor. Anonymousvisits are account-level at best and must set is_first_party true but actor_ref null, which the routing rule then blocks.

### `objection_relayed` · obs_kind

- blocks **Objection** / `obj.relayed_objection_has_no_owner` (would yield 7800 bp)
- Objection: Requires attribution of the concern's origin, not just its speaker. High value — a relayed objection is unanswerable through the person who raised it, and the standard failure mode is spending three weeks convincing the messenger.


### `calendar.attendees` · fact_path

- blocks **Stakeholder** / `sh.attends_but_never_replies` (would yield 7500 bp)
- Stakeholder: Calendar is connected andmeeting.start_at is projected, but the attendee roster is discarded. Attendance without correspondence is the strongest cheap signal of a stakeholder being managed by someone else.

### `calendar.days_to_quarter_end` · fact_path

- blocks **Pricing** / `pr.quarter_end_pressure` (would yield 7500 bp)
- Pricing: Quarter-end is thelargest single driver of unnecessary discount in B2B and nothing in the substrate knows what day of the quarter it is. Cheap to emit and it recontextualises every discount pattern above.

### `derived.commitment_specificity` · derived

- blocks **Next Action** / `na.action_is_vague` (would yield 7500 bp)
- Next Action: A classificationover commitment.action text separating 'send the security questionnaire to Priya' from 'circle back'. Cheap to build and it would remove most fake next actions from every pipeline at once.

### `derived.competitor_win_rate` · derived

- blocks **Competitor** / `comp.win_rate_from_history` (would yield 7500 bp)
- Competitor: Blocked twice over — it needs competitor.name to join on and closed_lost_reason to count. Listed anyway because it is the only pattern here that could ever tell a reviewer whether the competitive weighting is calibrated or invented.


### `derived.reply_ratio` · derived

- blocks **Stakeholder** / `sh.attends_but_never_replies` (would yield 7500 bp)

### `hiring_surge` · obs_kind

- blocks **Company** / `co.hiring_surge_implies_growth` (would yield 7500 bp)
- Company: Job postings are public, cheap topoll and name the exact function that is about to need tooling. The strongest pre-deal timing signal available anywhere and entirely absent today.

### `migration_concern` · obs_kind

- blocks **Market Map** / `mm.switching_cost_from_migration_talk` (would yield 7500 bp)
- Market Map: The generic `objection` kindswallows this. Migration anxiety is a market-structure fact — it predicts every displacement cycle in the segment — and it is indistinguishable from a feature complaint today.

### `reopen_condition` · obs_kind

- blocks **Investor Conversation** / `ic.reopen_condition_stated` (would yield 7500 bp)
- Investor Conversation: Almost always present verbatim in the passing email — 'come back at', 'apply to the next cohort', 'once you have a lead'. Cheap to extract, and its absence is why a pass currently destroys its own follow-up.

### `account.tech_stack` · fact_path

- blocks **Fit Analysis** / `fa.category_naive_buyer` (would yield 7000 bp)
- Fit Analysis: Absence of any category-adjacenttool is the cheapest available proxy for category naivety.

### `account_trigger` · obs_kind

- blocks **Opportunity** / `op.trigger_from_account_change` (would yield 7000 bp)
- Opportunity: Timing is the only variable aseller cannot manufacture, and the whole of it currently arrives through a human reading the news.

### `committee.member_ids` · fact_path

- blocks **Pain Point** / `pp.owner_is_outside_the_buying_committee` (would yield 7000 bp)
- Pain Point: The most expensive silentfailure in enterprise: the pain owner is in operations and the committee is finance and IT, so the business case is presented by people who do not feel the problem.

### `crm.deal.close_date` · fact_path

- blocks **Timeline** / `tl.crm_close_date` (would yield 7000 bp)
- Timeline: This is OUR date, not thebuyer's. Projecting it must not overwrite buyer_decision_date — that conflation is the reason forecasts read confident and land late.

### `derived.account_engagement_no_deal` · derived

- blocks **Buying Signal** / `bs.repeat_engagement_with_no_open_deal` (would yield 7000 bp)
- Buying Signal: The highest-yieldpattern in the object and the one with no route to execution today. Engagement is deal-scoped in the substrate, so an account behaving like a buyer before anyone creates an opportunity is invisible — precisely the population where a signal changes the outcome rather than confirming it.

### `derived.objection_intensity` · derived

- blocks **Objection** / `obj.intensity_separates_a_query_from_a_gate` (would yield 7000 bp)
- Objection: "That seems expensive" and "we cannot spend that this year" produce the identical observation today. Severity is therefore always guessed, and the register cannot be sorted by what actually stops the deal.


### `derived.persona_outcome_variance` · derived

- blocks **Persona** / `persona.split_into_two` (would yield 7000 bp)
- Persona: The most commondefect in a persona library and completely invisible without outcome joins. A bimodal persona averages to an archetype that describes nobody and quietly caps conversion for both halves.

### `derived.reply_hour_histogram` · derived

- blocks **Contact** / `contact.timezone_from_reply_behaviour` (would yield 7000 bp)
- Contact: Every reply already carries a timestamp; nothing aggregates them per contact. Send-time is the cheapest available lever on reply rate and is currently set by the sender's clock.

### `derived.reply_term_frequency` · derived

- blocks **Persona** / `persona.language_learned_from_their_own_replies` (would yield 7000 bp)
- Persona: Reply bodies are alreadyparsed for observations and discarded afterwards. Term frequency per persona is nearly free from the same pass and would replace the guessed vocabulary lists with observed ones.

### `derived.thread_seniority_delta` · derived

- blocks **Business Need** / `bn.an_executive_joined_the_thread` (would yield 7000 bp)
- Business Need: The delta is thesignal, not the absolute. An outcome that pulls a new executive in has just been promoted inside the account, and the org_level recorded during discovery is now understated.

### `page_view_pricing` · obs_kind

- blocks **Lead** / `lead.visited_the_pricing_page` (would yield 7000 bp)
- Lead: The highest-converting anonymoussignal in B2B and completely invisible. It is also the most perishable, which makes the gap worse than its conversion rate suggests.

### `person_mentioned` · obs_kind

- blocks **Stakeholder** / `sh.named_by_a_third_party` (would yield 7000 bp)
- Stakeholder: The highest-value gap on thisobject. An unmapped stakeholder is by construction someone who never appears as a sender or recipient, so the ONLY way the pipeline can ever see them is by extracting third-party name mentions from message bodies. Without it every pattern here is confined to people already in our address book, which is precisely the population that was never the risk.

### `risk.last_reviewed_at` · fact_path

- blocks **Risk** / `risk.stale_since_detection` (would yield 7000 bp)
- Risk: Requires the review surface to write back when a human reads a record. Cheap to build and disproportionately valuable: it is the only way to distinguish a managed register from a decorative one, and the distinction is invisible today.


### `account.icp_segment` · fact_path

- blocks **Persona** / `persona.inherited_from_the_account_segment` (would yield 6000 bp)
- Persona: Segment is decided in theICP capability and never lands as a typed fact on the account node, so the persona roster cannot be narrowed before outreach starts.

### `application_status` · fact_path

- blocks **Investor Conversation** / `ic.party_kind_from_correspondence` (would yield 6000 bp)
- Investor Conversation: The fundraising DomainSpec already declares this as an expected field for `investor_relationship`, and nothing writes it. Declared expectation without a writer is how `derived.*` came to be read by every deep rule and produced by none.

### `programme_deadline` · obs_kind

- blocks **Investor Conversation** / `ic.party_kind_from_correspondence` (would yield 6000 bp)
- Investor Conversation: Cohort dates arrive as dates in body text and are the one genuinely non-negotiable clock in this object.

### `funding.round` · fact_path

- blocks **Investor Conversation** / `ic.round_context` (would yield 5000 bp)
- Investor Conversation: Declared expected by the fundraising DomainSpec; no writer exists.

### `intent.topic_surge` · fact_path

- blocks **Buying Signal** / `bs.third_party_intent_surge` (would yield 4500 bp)
- Buying Signal: Deliberately low confidence.Account-level and never person-level, so it is useful for ranking a territory and useless for writing a message. Authored mainly so the routing rule that forbids quoting it has something to attach to.

