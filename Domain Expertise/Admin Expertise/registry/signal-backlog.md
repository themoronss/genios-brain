# Admin Expertise — signal backlog

> GENERATED — `python "Domain Expertise/_tools/backlog.py"`

Every row is a signal the authored expertise needs and the pipeline does not
emit. Ranked by how many inference patterns it unblocks, then by the confidence
of the strongest pattern waiting on it.

Rows marked `l2_situation_type` are the expensive ones. A blocked *pattern*
lowers one object's confidence; a blocked *situation* means the capability
behind it never compiles at all, and nothing errors or logs when it doesn't.

## Where the brain stands

- **88** patterns executable against the pipeline today
- **159** patterns blocked, waiting on **152** distinct signals
- **0** situation binding(s) waiting on an L2 type no pack emits
- Substrate today: **12** fact paths · **18** observation kinds · **1** baselines

## The backlog

| # | Signal | Kind | Owner | Unblocks | Top conf | Objects |
|---|---|---|---|---|---|---|
| 1 | `leaver_confirmed` | obs_kind | L2 | 7 | 9800 | Approver, Asset, Budget Line, Commitment, Document, Employee Record, Standard Operating Procedure |
| 2 | `employee.end_at` | fact_path | L1 | 7 | 9600 | Budget Line, Document, Employee Record, Escalation, Standard Operating Procedure |
| 3 | `approval.approver` | fact_path | L1 | 5 | 10000 | Approval, Approver, Escalation |
| 4 | `approval.state` | fact_path | L1/L2 | 5 | 10000 | Approval, Commitment, Escalation, Request |
| 5 | `approval.threshold_value` | fact_path | L1 | 5 | 10000 | Approval, Approver, Escalation, Expense Claim, Invoice |
| 6 | `employee.start_at` | fact_path | L1 | 5 | 10000 | Document, Employee Record, Expense Claim, Policy, Standard Operating Procedure |
| 7 | `document.version` | fact_path | L1 | 5 | 9800 | Action Item, Document, Policy, Standard Operating Procedure |
| 8 | `invoice.amount` | fact_path | L1 | 5 | 9800 | Contract, Invoice, Vendor |
| 9 | `contract.end_at` | fact_path | L1 | 5 | 9500 | Budget Line, Contract |
| 10 | `request.created_at` | fact_path | L1 | 5 | 9500 | Approval, Escalation, Request, Standard Operating Procedure |
| 11 | `document.approved_at` | fact_path | L1/L2 | 4 | 10000 | Action Item, Document, Filing, Standard Operating Procedure |
| 12 | `obligation.due_at` | fact_path | L1 | 4 | 10000 | Commitment, Escalation, Filing, Request |
| 13 | `policy_acknowledged` | obs_kind | L2 | 4 | 10000 | Document, Employee Record, Policy |
| 14 | `invoice.po_ref` | fact_path | L1 | 4 | 9800 | Approval, Contract, Invoice |
| 15 | `approval_granted` | obs_kind | L2 | 4 | 9600 | Approval, Approver, Budget Line, Expense Claim |
| 16 | `approval.requested_at` | fact_path | L1/L2 | 4 | 9500 | Approval, Escalation, Expense Claim |
| 17 | `contract.notice_period_days` | fact_path | L1 | 4 | 9500 | Budget Line, Contract |
| 18 | `document.retention_until` | fact_path | L1 | 4 | 9500 | Document, Employee Record |
| 19 | `document.review_due_at` | fact_path | L1 | 4 | 9500 | Document, Policy, Standard Operating Procedure |
| 20 | `document_superseded` | obs_kind | L2 | 4 | 9000 | Contract, Document, Policy, Standard Operating Procedure |
| 21 | `budget.consumed` | fact_path | L1 | 3 | 9800 | Budget Line |
| 22 | `document_signed` | obs_kind | L1/L2 | 3 | 9800 | Asset, Contract, Document |
| 23 | `approval_requested` | obs_kind | L2 | 3 | 9500 | Approval, Commitment |
| 24 | `commitment.owner` | fact_path | L2 | 3 | 9500 | Action Item, Commitment |
| 25 | `invoice.state` | fact_path | L1 | 3 | 9500 | Invoice, Vendor |
| 26 | `request.state` | fact_path | L1 | 3 | 9500 | Escalation, Request, Standard Operating Procedure |
| 27 | `approval_delegated` | obs_kind | L2 | 3 | 9000 | Approval, Approver, Escalation |
| 28 | `commitment.state` | fact_path | L2 | 3 | 9000 | Action Item, Commitment |
| 29 | `handover_completed` | obs_kind | L2 | 3 | 9000 | Action Item, Commitment, Standard Operating Procedure |
| 30 | `po_raised` | obs_kind | L2 | 3 | 9000 | Budget Line, Invoice |
| 31 | `obligation.authority` | fact_path | L1 | 2 | 10000 | Commitment, Filing |
| 32 | `budget.allocated` | fact_path | L1 | 2 | 9800 | Budget Line |
| 33 | `budget.committed` | fact_path | L1 | 2 | 9800 | Budget Line |
| 34 | `goods_receipted` | obs_kind | L2 | 2 | 9800 | Invoice |
| 35 | `minutes_circulated` | obs_kind | L2 | 2 | 9800 | Action Item, Meeting |
| 36 | `notice_served` | obs_kind | L2 | 2 | 9700 | Contract |
| 37 | `approval_rejected` | obs_kind | L2 | 2 | 9600 | Approval, Approver |
| 38 | `expense.amount` | fact_path | L1 | 2 | 9600 | Expense Claim |
| 39 | `contract.auto_renew` | fact_path | L1 | 2 | 9500 | Budget Line, Contract |
| 40 | `meeting.attendees_actual` | fact_path | L1 | 2 | 9500 | Meeting |
| 41 | `request.priority` | fact_path | L1 | 2 | 9500 | Escalation, Request |
| 42 | `derived.approval_latency` | derived | L2 | 2 | 9200 | Approval, Escalation |
| 43 | `agenda_circulated` | obs_kind | L2 | 2 | 9000 | Action Item, Meeting |
| 44 | `approver.unavailable_until` | fact_path | L1 | 2 | 9000 | Approval, Approver |
| 45 | `commitment.recipient` | fact_path | L2 | 2 | 9000 | Commitment |
| 46 | `document.classification` | fact_path | L1 | 2 | 9000 | Document, Employee Record |
| 47 | `access.granted_at` | fact_path | L1 | 2 | 8800 | Approver, Request |
| 48 | `approval_turnaround` | baseline | L2 | 2 | 8800 | Approval, Escalation |
| 49 | `card.transaction_at` | fact_path | L1 | 2 | 8800 | Expense Claim |
| 50 | `evidence_provided` | obs_kind | L2 | 2 | 8500 | Commitment, Standard Operating Procedure |
| 51 | `contract.counterparty` | fact_path | L1 | 2 | 8000 | Contract, Vendor |
| 52 | `derived.budget_burn_rate` | derived | L2 | 2 | 8000 | Budget Line |
| 53 | `expense.merchant` | fact_path | L1 | 2 | 8000 | Expense Claim |
| 54 | `derived.obligation_pressure` | derived | L2 | 2 | 7800 | Commitment, Contract |
| 55 | `admin_request_volume` | baseline | L2 | 2 | 7500 | Request, Standard Operating Procedure |
| 56 | `prebrief_delivered` | obs_kind | L2 | 2 | 7500 | Action Item, Meeting |
| 57 | `document_published` | obs_kind | L2 | 1 | 10000 | Document |
| 58 | `filing.reference_number` | fact_path | L2 | 1 | 10000 | Filing |
| 59 | `filing_accepted` | obs_kind | L2 | 1 | 10000 | Filing |
| 60 | `obligation.jurisdiction` | fact_path | L1 | 1 | 10000 | Filing |
| 61 | `bank_details_change_requested` | obs_kind | L2 | 1 | 9900 | Vendor |
| 62 | `vendor.bank_account_fingerprint` | fact_path | L1 | 1 | 9900 | Vendor |
| 63 | `approver.effective_to` | fact_path | L1 | 1 | 9800 | Approver |
| 64 | `asset.custodian` | fact_path | L1 | 1 | 9800 | Asset |
| 65 | `contract_countersigned` | obs_kind | L2 | 1 | 9800 | Contract |
| 66 | `escalation_requested` | obs_kind | L2 | 1 | 9800 | Escalation |
| 67 | `filing_rejected` | obs_kind | L2 | 1 | 9800 | Filing |
| 68 | `request.category` | fact_path | L1 | 1 | 9800 | Request |
| 69 | `screening_result_returned` | obs_kind | L1 | 1 | 9800 | Vendor |
| 70 | `employee.right_to_work_expires_at` | fact_path | L1 | 1 | 9700 | Employee Record |
| 71 | `expense.receipt_present` | fact_path | L1 | 1 | 9600 | Expense Claim |
| 72 | `access.last_used_at` | fact_path | L1 | 1 | 9500 | Approver |
| 73 | `asset.due_back_at` | fact_path | L1 | 1 | 9500 | Asset |
| 74 | `asset_returned` | obs_kind | L2 | 1 | 9500 | Asset |
| 75 | `calendar.event.previous_start_at` | fact_path | L1 | 1 | 9500 | Time Block |
| 76 | `document_review_overdue` | obs_kind | L2 | 1 | 9500 | Document |
| 77 | `invoice.due_at` | fact_path | L1 | 1 | 9500 | Invoice |
| 78 | `meeting.quorum_required` | fact_path | L1 | 1 | 9500 | Meeting |
| 79 | `request.acknowledged_at` | fact_path | L1 | 1 | 9500 | Request |
| 80 | `retention_review_due` | obs_kind | L2 | 1 | 9500 | Document |
| 81 | `vendor.diligence_expires_at` | fact_path | L1 | 1 | 9500 | Vendor |
| 82 | `expense.incurred_at` | fact_path | L1 | 1 | 9400 | Expense Claim |
| 83 | `policy.claim_window_days` | fact_path | L1 | 1 | 9400 | Expense Claim |
| 84 | `record.access_log` | fact_path | L1 | 1 | 9400 | Employee Record |
| 85 | `derived.onboarding_completeness` | derived | L2 | 1 | 9200 | Employee Record |
| 86 | `vendor_bank_detail_change` | obs_kind | L2 | 1 | 9200 | Invoice |
| 87 | `asset_issued` | obs_kind | L2 | 1 | 9000 | Asset |
| 88 | `calendar.event.category` | fact_path | L1 | 1 | 9000 | Time Block |
| 89 | `calendar.event.transparency` | fact_path | L1 | 1 | 9000 | Time Block |
| 90 | `derived.document_identity_cluster` | derived | L2 | 1 | 9000 | Document |
| 91 | `derived.performer_diversity` | derived | L2 | 1 | 9000 | Standard Operating Procedure |
| 92 | `derived.recipient_is_external` | derived | L2 | 1 | 9000 | Document |
| 93 | `escalation_accepted` | obs_kind | L2 | 1 | 9000 | Escalation |
| 94 | `filing.penalty_basis` | fact_path | L1 | 1 | 9000 | Filing |
| 95 | `filing_submitted` | obs_kind | L2 | 1 | 9000 | Filing |
| 96 | `meeting.papers_deadline_at` | fact_path | L1 | 1 | 9000 | Meeting |
| 97 | `request.type` | fact_path | L1 | 1 | 9000 | Request |
| 98 | `sla.target_resolution_at` | fact_path | L1 | 1 | 9000 | Request |
| 99 | `sop.tooling_referenced` | fact_path | L1 | 1 | 9000 | Standard Operating Procedure |
| 100 | `sop_executed` | obs_kind | L2 | 1 | 9000 | Standard Operating Procedure |
| 101 | `system_change_recorded` | obs_kind | L2 | 1 | 9000 | Standard Operating Procedure |
| 102 | `vendor.registration_number` | fact_path | L1 | 1 | 9000 | Vendor |
| 103 | `calendar.event.hold_expires_at` | fact_path | L1 | 1 | 8800 | Time Block |
| 104 | `meeting.series_id` | fact_path | L1 | 1 | 8800 | Action Item |
| 105 | `vendor.onboarding_state` | fact_path | L1 | 1 | 8800 | Vendor |
| 106 | `access_granted` | obs_kind | L2 | 1 | 8500 | Request |
| 107 | `derived.attestation_coverage` | derived | L2 | 1 | 8500 | Policy |
| 108 | `derived.escalation_pressure` | derived | L2 | 1 | 8500 | Escalation |
| 109 | `derived.vendor_first_seen` | derived | L2 | 1 | 8500 | Invoice |
| 110 | `joiner_confirmed` | obs_kind | L2 | 1 | 8500 | Standard Operating Procedure |
| 111 | `meeting.attendees` | fact_path | L1 | 1 | 8500 | Action Item |
| 112 | `payment_released` | obs_kind | L2 | 1 | 8500 | Approval |
| 113 | `person.working_hours` | fact_path | L1 | 1 | 8500 | Time Block |
| 114 | `policy.exception_count` | fact_path | L1 | 1 | 8500 | Policy |
| 115 | `policy.exception_expiry_at` | fact_path | L1 | 1 | 8500 | Policy |
| 116 | `sop_step_skipped` | obs_kind | L2 | 1 | 8500 | Standard Operating Procedure |
| 117 | `vendor.last_reviewed_at` | fact_path | L1 | 1 | 8500 | Vendor |
| 118 | `verbal_request_captured` | obs_kind | L2 | 1 | 8500 | Request |
| 119 | `derived.reporting_line` | derived | L2 | 1 | 8400 | Expense Claim |
| 120 | `commitment.previous_due_at` | fact_path | L2 | 1 | 8200 | Commitment |
| 121 | `derived.invoice_fingerprint` | derived | L2 | 1 | 8200 | Invoice |
| 122 | `derived.reschedule_count` | derived | L2 | 1 | 8200 | Time Block |
| 123 | `expense.state` | fact_path | L1 | 1 | 8200 | Expense Claim |
| 124 | `asset.last_verified_at` | fact_path | L1 | 1 | 8000 | Asset |
| 125 | `calendar.free_capacity_minutes` | fact_path | L2 | 1 | 8000 | Time Block |
| 126 | `derived.claim_fingerprint` | derived | L2 | 1 | 8000 | Expense Claim |
| 127 | `derived.contains_personal_data` | derived | L2 | 1 | 8000 | Document |
| 128 | `derived.control_enforcement_rate` | derived | L2 | 1 | 8000 | Policy |
| 129 | `derived.request_similarity` | derived | L2 | 1 | 8000 | Request |
| 130 | `sla_breach` | obs_kind | L2 | 1 | 8000 | Vendor |
| 131 | `sop_execution_observed` | obs_kind | L2 | 1 | 8000 | Standard Operating Procedure |
| 132 | `vendor.service_level_target` | fact_path | L1 | 1 | 8000 | Vendor |
| 133 | `asset.last_seen_at` | fact_path | L1 | 1 | 7500 | Asset |
| 134 | `commitment_delivery_rate` | baseline | L2 | 1 | 7500 | Commitment |
| 135 | `decision_recorded` | obs_kind | L2 | 1 | 7500 | Meeting |
| 136 | `derived.approval_rejection_rate` | derived | L2 | 1 | 7500 | Approver |
| 137 | `derived.backlog_age` | derived | L2 | 1 | 7500 | Request |
| 138 | `derived.calendar_density` | derived | L2 | 1 | 7500 | Time Block |
| 139 | `derived.decision_density` | derived | L2 | 1 | 7500 | Meeting |
| 140 | `derived.merchant_category_sensitivity` | derived | L2 | 1 | 7500 | Expense Claim |
| 141 | `derived.period_activity` | derived | L2 | 1 | 7500 | Filing |
| 142 | `derived.request_repeat_rate` | derived | L2 | 1 | 7500 | Request |
| 143 | `policy_breach_observed` | obs_kind | L2 | 1 | 7500 | Policy |
| 144 | `contract.price_uplift_index` | fact_path | L1 | 1 | 7000 | Contract |
| 145 | `derived.meeting_attendance_rate` | derived | L2 | 1 | 7000 | Meeting |
| 146 | `derived.policy_clause_coverage` | derived | L2 | 1 | 7000 | Expense Claim |
| 147 | `person.seniority` | fact_path | L1 | 1 | 7000 | Request |
| 148 | `trip.return_at` | fact_path | L1 | 1 | 7000 | Time Block |
| 149 | `derived.vendor_channel_norm` | derived | L2 | 1 | 6800 | Invoice |
| 150 | `asset.issued_at` | fact_path | L1 | 1 | 6500 | Asset |
| 151 | `derived.commitment_clustering` | derived | L2 | 1 | 6500 | Budget Line |
| 152 | `derived.pool_loan_duration` | derived | L2 | 1 | 6500 | Asset |

## Why each one matters

### `leaver_confirmed` · obs_kind

- blocks **Approver** / `apr.leaver_still_holds_the_entitlement` (would yield 9500 bp)
- blocks **Asset** / `ast.custodian_left_still_holding` (would yield 9800 bp)
- blocks **Budget Line** / `bl.owner_unknown_or_departed` (would yield 8500 bp)
- blocks **Commitment** / `cmt.promise_to_a_departing_party` (would yield 7000 bp)
- blocks **Document** / `doc.owner_left_the_organisation` (would yield 9000 bp)
- blocks **Employee Record** / `emp.leaver_confirmed_offboarding_not_started` (would yield 9600 bp)
- blocks **Standard Operating Procedure** / `sop.owner_left_and_nobody_inherited` (would yield 9000 bp)
- Approver: The leaving event exists in theHRIS and is not projected anywhere the approval routing can see it.
- Asset: The single highest-value missingsignal for this object. Departure is known to HRIS weeks in advance and reaches the asset register, if at all, after the last working day — which is precisely when recovery stops being possible.
- Budget Line: An orphaned budget line is thequietest failure in this file. Nothing breaks, nothing alerts, and the spend continues against a line whose owner left in March — discovered at year end by whoever inherits the variance.
- Commitment: Joiner-mover-leaver events are visible in HRIS and never reach the commitment register. The correct move is to ask the successor whether they still want it; the default move is to deliver a report to a mailbox nobody reads. This is also the only pattern that would catch an unowned promise before the audit does.
- Document: Joiner-mover-leaver reaches access rights in most organisations and document ownership in almost none. The leaver's documents keep their review dates, keep sending reminders into a disabled mailbox, and are discovered unowned at the next audit.
- Employee Record: The highest-value signal missingfrom the whole people-administration set. HR knows about a departure during the notice period; asset recovery and access removal find out afterwards, when neither is achievable.

### `employee.end_at` · fact_path

- blocks **Budget Line** / `bl.owner_unknown_or_departed` (would yield 8500 bp)
- blocks **Document** / `doc.owner_left_the_organisation` (would yield 9000 bp)
- blocks **Document** / `doc.retention_clock_never_started` (would yield 9000 bp)
- blocks **Employee Record** / `emp.leaver_confirmed_offboarding_not_started` (would yield 9600 bp)
- blocks **Employee Record** / `emp.retention_period_elapsed` (would yield 9000 bp)
- blocks **Escalation** / `esc.rung_is_absent_not_refusing` (would yield 9000 bp)
- blocks **Standard Operating Procedure** / `sop.owner_left_and_nobody_inherited` (would yield 9000 bp)
- Document: The commonest trigger in practice for personnel records, and the join nobody makes. A schedule whose clock never starts looks complete and disposes of nothing — the quiet way an estate becomes permanent.
- Document: The date. Needed to distinguish an owner who has left from one who is on leave — the two produce identical silence and demand opposite responses.
- Employee Record: Also the origin of every retentioncalculation on this object. Its absence means retention_until cannot be computed at all, only asserted.
- Escalation: Absence and delegation records live in HRIS and the calendar out-of-office, neither of which is projected. This is the highest-value false-positive suppressor on the object: it stops the system escalating past people who are asleep in a different timezone.

### `approval.approver` · fact_path

- blocks **Approval** / `apv.explicit_state_field` (would yield 10000 bp)
- blocks **Approval** / `apv.segregation_breach_on_this_decision` (would yield 9000 bp)
- blocks **Approver** / `apr.doa_matrix_row` (would yield 10000 bp)
- blocks **Approver** / `apr.undocumented_delegation_in_operation` (would yield 8200 bp)
- blocks **Escalation** / `esc.repeat_stall_against_the_same_rung` (would yield 8500 bp)
- Approval: State without a holder is still unactionable: you know it is open, not who to chase.
- Approver: Who may approve what. Existsas a spreadsheet appended to a finance policy in essentially every organisation over fifty people and is read by no connector.
- Approver: Comparing the intended approveragainst the actual granting actor is a one-line rule that cannot be written today. It detects the assistant approving under a verbal instruction — extremely common, entirely undocumented, and the first thing an examiner finds.

### `approval.state` · fact_path

- blocks **Approval** / `apv.blocked_behind_a_prior_serial_step` (would yield 8000 bp)
- blocks **Approval** / `apv.explicit_state_field` (would yield 10000 bp)
- blocks **Commitment** / `cmt.blocked_on_a_signature` (would yield 8600 bp)
- blocks **Escalation** / `esc.approval_pending_past_its_own_turnaround` (would yield 8800 bp)
- blocks **Request** / `req.exception_worked_without_approval` (would yield 9000 bp)
- Approval: Every ERP, P2P and ITSM tool exposes an approval state on its API and none of them are read. This single path would convert most of this object from inference to fact — the highest-leverage unbuilt connector field in the Admin domain.
- Approval: Serial chains are invisible today, so a position-4 approver is chased for a delay caused entirely at position 1. The chase is wasted, the real blocker is never contacted, and position 4 learns to ignore chases.
- Commitment: Needed to tell pending from stuck. Same row, different move: one wants a reminder, the other wants a different approver.
- Escalation: No typed approval state exists. Everything administrative about stalled decisions is currently inferred from email shape, which is why this object leans so hard on commitment.due_at.
- Request: The control that matters most in intake — an exception worked by an operator rather than routed to an approver — is undetectable, because neither half of the comparison exists as a fact.


### `approval.threshold_value` · fact_path

- blocks **Approval** / `apv.doa_threshold_covers_the_value` (would yield 9500 bp)
- blocks **Approver** / `apr.doa_matrix_row` (would yield 10000 bp)
- blocks **Escalation** / `esc.missing_authority_not_missing_answer` (would yield 8600 bp)
- blocks **Expense Claim** / `exp.split_below_the_approval_threshold` (would yield 6500 bp)
- blocks **Invoice** / `inv.approver_over_their_limit` (would yield 9600 bp)
- Approval: The DOA matrix exists in every organisation past about fifty people, usually as a spreadsheet appended to a finance policy. No connector reads it, so the system cannot tell a correctly routed approval from a wrongly routed one — and wrongly routed approvals age identically to correct ones until somebody notices by hand.
- Approver: The limit. Without itthe system cannot tell a correctly routed approval from a wrongly routed one, and wrongly routed approvals age exactly like correct ones.
- Escalation: The governance gap that masquerades as a delay. Climbing a ladder whose top rung still cannot sign wastes weeks and ends in an improvised approval that fails audit later.
- Expense Claim: Deliberately weak at 6500 even once available. Splitting is far more often the claimant doing what the form encouraged — one line per receipt — than an attempt to evade a limit, and treating it as the latter is how a control loses the goodwill it runs on.
- Invoice: Delegation-of-authority matrices live in a policy document, not a system. Until the DOA is machine-readable, over-limit approval is only ever caught at audit, months after the cash left.

### `employee.start_at` · fact_path

- blocks **Document** / `doc.acknowledgement_population_incomplete` (would yield 8500 bp)
- blocks **Employee Record** / `emp.start_date_approaching_file_incomplete` (would yield 9200 bp)
- blocks **Expense Claim** / `exp.approver_cannot_have_known` (would yield 8400 bp)
- blocks **Policy** / `pol.acknowledgement_recorded` (would yield 10000 bp)
- blocks **Standard Operating Procedure** / `sop.new_joiner_followed_a_stale_version` (would yield 8500 bp)
- Document: The denominator moves. Nothing binds a new starter to a document published before they arrived — the single largest hole in every acknowledgement number ever reported to a board.
- Employee Record: Every HRIS holds this and noconnector projects it. Without it, the one deadline in onboarding that is genuinely fixed and genuinely known in advance is invisible to the engine, and onboarding is reduced to whoever remembers.
- Policy: Needed for the denominatorand for on-joining attestation. Without it, coverage is computed over whoever already signed, which always reports as complete.
- Standard Operating Procedure: This is the object's central failure made detectable, and it is worth stating plainly: the only people who follow the SOP exactly are the people who cannot tell it is wrong. Everyone experienced corrects it silently. Detecting this requires knowing which version reached the joiner, which requires version identity on the copy rather than on the master.

### `document.version` · fact_path

- blocks **Action Item** / `ai.minute_line_reference` (would yield 9800 bp)
- blocks **Document** / `doc.version_conflict_in_circulation` (would yield 9000 bp)
- blocks **Policy** / `pol.superseded_but_still_circulating` (would yield 9000 bp)
- blocks **Standard Operating Procedure** / `sop.new_joiner_followed_a_stale_version` (would yield 8500 bp)
- blocks **Standard Operating Procedure** / `sop.two_versions_in_circulation` (would yield 9000 bp)
- Action Item: Needed to distinguish draftminutes from the circulated version. An action lifted from an uncirculated draft is not yet binding on anyone.
- Document: Requires a version string per artefact plus identity resolution across copies. Without it the commonest document-control incident in any organisation is structurally undetectable — and it is the one whose symptom is two teams in a meeting with different numbers.
- Policy: Requires version identity acrosscopies. Until it exists, 'which version was I bound by' — the only version question a tribunal ever asks — cannot be answered from the system.
- Standard Operating Procedure: Requires version identity across copies, not just on the master. Until it exists, 'which version did they follow' — the only version question ever asked in anger — cannot be answered from the system, and the honest response to a tribunal is that we do not know.

### `invoice.amount` · fact_path

- blocks **Contract** / `ct.price_uplift_applied_without_a_decision` (would yield 7000 bp)
- blocks **Invoice** / `inv.approver_over_their_limit` (would yield 9600 bp)
- blocks **Invoice** / `inv.duplicate_suspected_by_amount` (would yield 8200 bp)
- blocks **Invoice** / `inv.three_way_match_clean` (would yield 9800 bp)
- blocks **Vendor** / `vn.concentration_risk` (would yield 7500 bp)

### `contract.end_at` · fact_path

- blocks **Budget Line** / `bl.auto_renewal_commits_the_line` (would yield 9000 bp)
- blocks **Contract** / `ct.amendment_chain_obscures_the_terms` (would yield 6500 bp)
- blocks **Contract** / `ct.default_renewal_imminent` (would yield 9000 bp)
- blocks **Contract** / `ct.evergreen_never_re_decided` (would yield 7000 bp)
- blocks **Contract** / `ct.term_and_notice_are_known` (would yield 9500 bp)
- Contract: No connector reads a contract register or CLM. The most consequential administrative date in the business — the last day we can walk away — does not exist in the pipeline in any form.
- Contract: Needs the term as restated by the LATEST instrument in the chain, not the first. Without it, a register with four amendments shows four end dates and no way to tell which one governs.
- Contract: Its ABSENCE is the trigger, so the field must exist before the absence is distinguishable from an unread register.

### `request.created_at` · fact_path

- blocks **Approval** / `apv.segregation_breach_on_this_decision` (would yield 9000 bp)
- blocks **Escalation** / `esc.request_ageing_against_service_level` (would yield 8000 bp)
- blocks **Request** / `req.aging_against_its_peer_group` (would yield 7500 bp)
- blocks **Request** / `req.state_from_the_service_desk` (would yield 9500 bp)
- blocks **Standard Operating Procedure** / `sop.cycle_time_diverged_from_the_written_duration` (would yield 7500 bp)
- Approval: Requires the requester identity alongside the approver identity. Self-approval is the control failure most often committed in good faith and most reliably found in the first walkthrough, and detecting it is a string comparison no system currently performs.
- Request: thread.last_inbound approximates arrival only while the ask lives in a mail thread. A portal submission has no thread at all, and a corridor ask has neither.


### `document.approved_at` · fact_path

- blocks **Action Item** / `ai.adopted_at_the_next_sitting` (would yield 9600 bp)
- blocks **Document** / `doc.approval_recorded_in_the_register` (would yield 10000 bp)
- blocks **Filing** / `fil.dependency_not_signed_off` (would yield 8500 bp)
- blocks **Standard Operating Procedure** / `sop.review_date_passed_unverified` (would yield 8500 bp)
- Action Item: The moment of adoption isthe moment an action item becomes independently enforceable. It happens in every governed forum on earth, every month, and is recorded in a file the pipeline cannot see.
- Document: Every document management system holds this on every controlled artefact. No connector projects it, so the single field that separates a draft from a document is invisible to reasoning — the highest-value missing path in this file and arguably in the Admin brain.
- Standard Operating Procedure: Needed to distinguish 'never reviewed since approval' from 'reviewed and due again', which are different problems with different owners.
- Filing: Annual filings fail on theirdependency, not on their preparation. An audit that slips two weeks moves the real start of the filing by two weeks and moves the statutory date by nothing, and no current signal expresses that squeeze.

### `obligation.due_at` · fact_path

- blocks **Commitment** / `cmt.promise_restates_an_obligation` (would yield 9000 bp)
- blocks **Escalation** / `esc.protected_deadline_inside_the_ladder_time` (would yield 9200 bp)
- blocks **Filing** / `fil.statutory_calendar` (would yield 10000 bp)
- blocks **Request** / `req.jumped_the_queue_on_seniority` (would yield 7000 bp)
- Commitment: Requires an obligation register connector — a statutory calendar, a filing portal, or the contract's own dates. Until it exists the engine cannot distinguish the most negotiable commitment in the queue from the least, and treats both as movable.
- Escalation: Escalate to the deadline, not to the elapsed time. Without an external date the system can only reason about patience, which is exactly the reasoning administrators are told to stop using.
- Request: The comparison becomes possible only when the statutory deadline is visible alongside the diary query. Today only one side of it is, which is precisely why the queue-jump is invisible and universal. This is the pattern that would let a function prove its median turnaround is excellent AND its statutory work is late, which are the two facts nobody currently sees together.

- Filing: There is no regulatory calendarconnector and no statutory date feed. The single most consequential date in the administrative function is typed by a human into a spreadsheet and copied forward each year, which is exactly how a leap-year quarter-end gets a wrong date and nobody notices until the penalty notice arrives.

### `policy_acknowledged` · obs_kind

- blocks **Document** / `doc.acknowledgement_population_incomplete` (would yield 8500 bp)
- blocks **Employee Record** / `emp.handbook_attestation_never_returned` (would yield 8500 bp)
- blocks **Policy** / `pol.acknowledgement_recorded` (would yield 10000 bp)
- blocks **Policy** / `pol.attestation_cycle_never_ran` (would yield 8500 bp)
- Document: The positive return. Counting them is trivial once emitted; today acknowledgement is proved by a spreadsheet somebody maintains by hand and abandons in month three.
- Employee Record: Attestation platforms existand are rarely joined to the personnel file, so the organisation can say a policy was published but not that any given person is bound by it — which is the only version of the fact a disciplinary process can use.
- Policy: Every LMS, HR platform andpolicy portal emits this on every attestation. Nothing consumes it, so the one fact that decides whether a policy is enforceable at all is invisible to reasoning — the highest-value ask in this file.

### `invoice.po_ref` · fact_path

- blocks **Approval** / `apv.duplicate_of_an_existing_approval` (would yield 8500 bp)
- blocks **Contract** / `ct.spend_without_paper` (would yield 8000 bp)
- blocks **Invoice** / `inv.no_po_is_maverick_spend` (would yield 9000 bp)
- blocks **Invoice** / `inv.three_way_match_clean` (would yield 9800 bp)
- Approval: Duplicate requests are routine where an item arrives by both email and portal. Without a subject key the same invoice is approved twice and paid twice — the failure the three-way match exists to prevent and routinely does not.
- Contract: The three-way match is a Layer 2 join across invoice, purchase order and contract. None of the three is projected, so maverick spend is found in the annual audit rather than in the month it starts.
- Invoice: No ERP or purchase-to-pay connector exists. The single most automatable control in the whole administrative function is unreachable because nothing projects a PO reference into a typed fact.
- Invoice: Requires the ABSENCE of a PO to be observable, which means the PO register must be readable. Absence of a signal is not a signal of absence, and today we have neither.

### `approval_granted` · obs_kind

- blocks **Approval** / `apv.approval_decision_observation` (would yield 9600 bp)
- blocks **Approver** / `apr.undocumented_delegation_in_operation` (would yield 8200 bp)
- blocks **Budget Line** / `bl.approved_uninvoiced_services_running` (would yield 7500 bp)
- blocks **Expense Claim** / `exp.pre_approval_absent_for_restricted_category` (would yield 9200 bp)
- Approver: Needed with the granting actorattached, not just the fact of a grant.

### `approval.requested_at` · fact_path

- blocks **Approval** / `apv.approval_requested_observation` (would yield 9500 bp)
- blocks **Approval** / `apv.retrospective_collection` (would yield 8500 bp)
- blocks **Escalation** / `esc.approval_pending_past_its_own_turnaround` (would yield 8800 bp)
- blocks **Expense Claim** / `exp.pre_approval_absent_for_restricted_category` (would yield 9200 bp)
- Approval: The clock start. Every duration metric on this object is uncomputable without it, which makes this the single ask that unblocks the most other work.
- Expense Claim: Needed to prove the approval predates the spend. An approval record without a timestamp cannot distinguish pre-approval from retrospective cover, which is the entire point of the control.

### `contract.notice_period_days` · fact_path

- blocks **Budget Line** / `bl.auto_renewal_commits_the_line` (would yield 9000 bp)
- blocks **Contract** / `ct.default_renewal_imminent` (would yield 9000 bp)
- blocks **Contract** / `ct.evergreen_never_re_decided` (would yield 7000 bp)
- blocks **Contract** / `ct.term_and_notice_are_known` (would yield 9500 bp)
- Contract: Extractable from the termination clause with document-level extraction. Today it lives only in the PDF, and therefore only in the memory of whoever last read it.
- Contract: On an evergreen the notice period is the entire exit mechanism; there is no expiry to fall back on.

### `document.retention_until` · fact_path

- blocks **Document** / `doc.personal_data_without_retention_rule` (would yield 8000 bp)
- blocks **Document** / `doc.retention_clock_never_started` (would yield 9000 bp)
- blocks **Document** / `doc.retention_period_elapsed` (would yield 9500 bp)
- blocks **Employee Record** / `emp.retention_period_elapsed` (would yield 9000 bp)
- Document: Retention schedules exist on paper in most organisations and in no queryable field. Over-retention is a storage-limitation breach in its own right and the only one that gets worse purely by the passage of time with nobody touching anything.
- Document: Its ABSENCE against a populated retention class is the finding. Schedules are written as 'six years from termination' and the termination date lives in HRIS, unjoined.
- Document: Its absence against a positive personal-data finding is the whole pattern. Personal data, no series, no disposal date — the shape of an over-retention breach that grows every day nobody acts.
- Employee Record: Retention is authoredin a schedule document and never projected onto the records it governs, so no system anywhere in the organisation can answer 'what should be destroyed this month'. Over-retention is therefore the default state of every personnel archive, and it is invisible because nothing breaks.

### `document.review_due_at` · fact_path

- blocks **Document** / `doc.review_due_date_passed` (would yield 9500 bp)
- blocks **Policy** / `pol.review_date_passed` (would yield 9500 bp)
- blocks **Standard Operating Procedure** / `sop.never_verified_against_practice` (would yield 8000 bp)
- blocks **Standard Operating Procedure** / `sop.review_date_passed_unverified` (would yield 8500 bp)
- Document: A trivially computable date that no connector emits. Note this is a SELF-imposed date; the object it must not be confused with is compliance_obligation, whose dates cannot be moved by anyone here at all.
- Policy: The policy's own self-imposeddate, carried on the controlled document. Note the contrast with compliance_obligation: this date can be moved by the organisation that set it, which is exactly why it is missed so often and matters so much less than an external one.
- Standard Operating Procedure: The self-imposed date carried on the controlled document. Note the contrast with an external filing deadline: this one can be moved by the organisation that set it, which is exactly why it is missed so often.
- Standard Operating Procedure: Needed to separate 'reviewed, never verified' — the theatre case — from 'never reviewed at all', which is at least honest.

### `document_superseded` · obs_kind

- blocks **Contract** / `ct.amendment_chain_obscures_the_terms` (would yield 6500 bp)
- blocks **Document** / `doc.version_conflict_in_circulation` (would yield 9000 bp)
- blocks **Policy** / `pol.superseded_but_still_circulating` (would yield 9000 bp)
- blocks **Standard Operating Procedure** / `sop.two_versions_in_circulation` (would yield 9000 bp)
- Document: The discriminator between a conflict and an orderly lineage. Supersession has a timestamp in every DMS and no representation here, so without it two live versions and a published successor look identical.

### `budget.consumed` · fact_path

- blocks **Budget Line** / `bl.burn_ahead_of_phasing` (would yield 8000 bp)
- blocks **Budget Line** / `bl.line_specific_commitment_recorded` (would yield 9800 bp)
- blocks **Budget Line** / `bl.material_underspend_late_in_period` (would yield 7000 bp)

### `document_signed` · obs_kind

- blocks **Asset** / `ast.issued_without_signed_acceptance` (would yield 9000 bp)
- blocks **Contract** / `ct.executed_copy_exists` (would yield 9800 bp)
- blocks **Document** / `doc.signed_original_exists` (would yield 9800 bp)
- Asset: e-signature platforms are a solvedL1 integration everywhere except here; the completion callback is not projected as an observation, so the difference between an issued item and an accepted one cannot be computed.
- Contract: Every e-signature platform emits a completion webhook per envelope, with signer identity and timestamp. No connector consumes it.
- Document: E-signature platforms emit a completion webhook on every executed document. Nothing consumes it, so the exact moment an artefact becomes dispositive evidence is the moment the system stops watching it.

### `approval_requested` · obs_kind

- blocks **Approval** / `apv.approval_requested_observation` (would yield 9500 bp)
- blocks **Approval** / `apv.information_missing_not_unwillingness` (would yield 8000 bp)
- blocks **Commitment** / `cmt.blocked_on_a_signature` (would yield 8600 bp)
- Approval: L2 already classifies asks in email, and approval asks are lexically distinctive — 'please approve', 'for your sign-off', 'awaiting your authorisation'. They are not extracted.
- Approval: Needed with direction attached, so a clarifying question can be told from a decision. Today an approval where the ball has bounced back to us looks identical to one the approver is sitting on, and the two have opposite remedies: send the quote comparison, or escalate.
- Commitment: An approval ask is a distinct speech act from a promise and the extractor collapses them. Without it a stuck approval is reported as an owner who is not delivering — wrong, and corrosive in a way that outlasts the commitment.

### `commitment.owner` · fact_path

- blocks **Action Item** / `ai.owner_was_not_in_the_room` (would yield 8500 bp)
- blocks **Commitment** / `cmt.chronic_owner` (would yield 7500 bp)
- blocks **Commitment** / `cmt.owner_is_named` (would yield 9500 bp)
- Action Item: Without an owner there is nobodyto compare the roster against.
- Commitment: The extractor emits the action and the date and drops the subject of the sentence. Every executable pattern above therefore assumes the promise is ours, which is the exact failure this object exists to prevent — roughly half of a real administrator's register is other people's promises to the organisation. Highest-value gap in the Admin brain by a distance.

### `invoice.state` · fact_path

- blocks **Invoice** / `inv.overdue_against_contractual_terms` (would yield 9500 bp)
- blocks **Invoice** / `inv.unknown_payee_plausible_project` (would yield 8500 bp)
- blocks **Vendor** / `vn.paid_without_approval` (would yield 8800 bp)

### `request.state` · fact_path

- blocks **Escalation** / `esc.request_ageing_against_service_level` (would yield 8000 bp)
- blocks **Request** / `req.state_from_the_service_desk` (would yield 9500 bp)
- blocks **Standard Operating Procedure** / `sop.cycle_time_diverged_from_the_written_duration` (would yield 7500 bp)
- Escalation: Admin queues publish response targets and measure nothing against them. Three fields would make the whole of service-level escalation automatic and remove the credibility cost from it.
- Request: Where a ticketing tool exists it is the system of record and the engine cannot read it, so Layer 3 is reasoning about a copy of the queue held in email.


### `approval_delegated` · obs_kind

- blocks **Approval** / `apv.stuck_because_the_approver_is_absent` (would yield 8800 bp)
- blocks **Approver** / `apr.out_of_office_with_no_delegate` (would yield 9000 bp)
- blocks **Escalation** / `esc.rung_is_absent_not_refusing` (would yield 9000 bp)
- Approval: Needed to tell absent-with-cover from absent-without-cover. Only the second is stuck; chasing the first is noise and chasing the second is futile.
- Approver: Absence with cover is routine;absence without cover is a stoppage. Without the delegation signal the two are indistinguishable and both get chased.

### `commitment.state` · fact_path

- blocks **Action Item** / `ai.reported_with_no_update` (would yield 8000 bp)
- blocks **Commitment** / `cmt.closed_without_evidence` (would yield 8500 bp)
- blocks **Commitment** / `cmt.discharge_recorded` (would yield 9000 bp)
- Action Item: A per-sitting status againstan action, distinct from the action's own state. It exists in every action tracker as a column and nowhere in the substrate.
- Commitment: The planned state field. followup_sent covers outbound email only; a call made, a form signed in a portal, a file dropped in a shared drive, or anything at all the counterparty did is invisible.

### `handover_completed` · obs_kind

- blocks **Action Item** / `ai.closed_before_the_next_sitting` (would yield 9000 bp)
- blocks **Commitment** / `cmt.discharge_recorded` (would yield 9000 bp)
- blocks **Standard Operating Procedure** / `sop.owner_left_and_nobody_inherited` (would yield 9000 bp)
- Action Item: Without any completion signal,ai.past_its_date_and_still_open will insist an item is overdue while the owner sits in the meeting holding the finished document. That specific embarrassment is why committees stop trusting automated action trackers.
- Commitment: The one closure event administrators already write down in words — 'handed over to Priya, done' — and which no pack extracts.
- Standard Operating Procedure: The absence of this is the signal, not its presence. Joiner-mover-leaver has a documented handover step in every organisation and an enforced one in almost none, because the leaver is the least motivated author in the building and their notice period is consumed by live work.

### `po_raised` · obs_kind

- blocks **Budget Line** / `bl.approved_uninvoiced_services_running` (would yield 7500 bp)
- blocks **Budget Line** / `bl.march_buying_season` (would yield 6500 bp)
- blocks **Invoice** / `inv.no_po_is_maverick_spend` (would yield 9000 bp)
- Budget Line: The invisible half of commitment: servicesengaged on an email thread. Detectable as an approval with no PO behind it, and both halves of that test are missing today.

### `obligation.authority` · fact_path

- blocks **Commitment** / `cmt.promise_restates_an_obligation` (would yield 9000 bp)
- blocks **Filing** / `fil.statutory_calendar` (would yield 10000 bp)
- Commitment: Who set the date. Determines whether an extension is even conceptually available, which is a different question from whether one would be granted.

### `budget.allocated` · fact_path

- blocks **Budget Line** / `bl.line_specific_commitment_recorded` (would yield 9800 bp)
- blocks **Budget Line** / `bl.overcommitted` (would yield 9600 bp)
- Budget Line: Overcommitment is a governanceevent, not an accounting one — somebody committed money they were not authorised to commit. It cannot be detected at all without both figures, and today the stack has neither.

### `budget.committed` · fact_path

- blocks **Budget Line** / `bl.line_specific_commitment_recorded` (would yield 9800 bp)
- blocks **Budget Line** / `bl.overcommitted` (would yield 9600 bp)
- Budget Line: The single most valuable unmetask in the finance subdomain. Most ERPs compute this and report it on a screen nobody opens; nothing projects it into a typed fact, so the number that surprises everyone at period end stays invisible to the one system that could warn them.

### `goods_receipted` · obs_kind

- blocks **Invoice** / `inv.service_invoice_never_receipted` (would yield 7000 bp)
- blocks **Invoice** / `inv.three_way_match_clean` (would yield 9800 bp)
- Invoice: The receipt leg has no emitter at all. Its absence is why every match on this pipeline would be two-way, which proves ordering and never delivery.
- Invoice: Services are the blind spot inside the blind spot. Even organisations running a working three-way match routinely waive the receipt leg for consultancy and support — which is where the money is, and where nothing physical fails to arrive to prompt a question.

### `minutes_circulated` · obs_kind

- blocks **Action Item** / `ai.minute_line_reference` (would yield 9800 bp)
- blocks **Meeting** / `mtg.minutes_actually_circulated` (would yield 9500 bp)
- Action Item: Minutes are the single richestadministrative artefact in any organisation — dated, attributed, owner-assigned, and agreed by the silence of everyone who received them — and no connector reads them. Every gap on this object collapses to this one signal.
- Meeting: Distinguishing a minute fromany other post-meeting email needs attachment-level extraction, not thread-level. Without it the governance metric that matters most is approximated by the weakest observation in the vocabulary.

### `notice_served` · obs_kind

- blocks **Contract** / `ct.default_renewal_imminent` (would yield 9000 bp)
- blocks **Contract** / `ct.notice_served_and_proved` (would yield 9700 bp)
- Contract: Absence of service is the trigger for the renewal alarm, so the signal must exist for its absence to mean anything. Today an unserved notice and a served-but-unrecorded notice are indistinguishable, and only one of them costs a renewal term of spend.
- Contract: The trigger is an absence, so the signal has to exist for its absence to be meaningful.

### `approval_rejected` · obs_kind

- blocks **Approval** / `apv.approval_decision_observation` (would yield 9600 bp)
- blocks **Approver** / `apr.rubber_stamp` (would yield 7500 bp)
- Approval: Rejections matter more than grants. A queue whose rejection rate is zero is a postbox, and only the rejected set tells you whether the control is doing anything at all.
- Approver: Grants without rejections cannotdistinguish a working control from a postbox. The zero is the signal, and it can only be computed once rejections are visible at all.

### `expense.amount` · fact_path

- blocks **Expense Claim** / `exp.receipt_missing_above_threshold` (would yield 9600 bp)
- blocks **Expense Claim** / `exp.split_below_the_approval_threshold` (would yield 6500 bp)
- Expense Claim: No expense-system connector exists. The amount — the field every threshold in every expense policy turns on — is not projected into a typed fact anywhere in the stack.

### `contract.auto_renew` · fact_path

- blocks **Budget Line** / `bl.auto_renewal_commits_the_line` (would yield 9000 bp)
- blocks **Contract** / `ct.auto_renewal_declared` (would yield 9500 bp)
- Budget Line: Renewal commits money bynobody doing anything, which is why it is absent from every commitment figure built around purchase orders. Three cheap fields from a contract register close the largest structural hole in this object.
- Contract: Until this exists every contract must be assumed auto-renewing, which is the correct default and an expensive one — it puts a diary entry and a brief on instruments that never needed either.

### `meeting.attendees_actual` · fact_path

- blocks **Meeting** / `mtg.attendance_and_quorum` (would yield 9500 bp)
- blocks **Meeting** / `mtg.chronic_apologies_are_a_vacancy` (would yield 7000 bp)
- Meeting: The calendar connectorprojects start_at and status and discards the response list entirely. Acceptances, declines and tentatives are already in the payload — this is a projection gap, not a source gap, and it is the cheapest high-value fix in the Admin backlog.

### `request.priority` · fact_path

- blocks **Escalation** / `esc.request_ageing_against_service_level` (would yield 8000 bp)
- blocks **Request** / `req.state_from_the_service_desk` (would yield 9500 bp)

### `derived.approval_latency` · derived

- blocks **Approval** / `apv.latency_beyond_this_approver_norm` (would yield 7800 bp)
- blocks **Escalation** / `esc.protected_deadline_inside_the_ladder_time` (would yield 9200 bp)
- Approval: reply_cadence is a thread-level proxy that counts a one-line acknowledgement as a response. A real per-approver, per-type decision-latency baseline is what separates a slow approver from a stuck approval, and it can only be built once approval_requested and approval_granted both exist.

### `agenda_circulated` · obs_kind

- blocks **Action Item** / `ai.carried_across_consecutive_sittings` (would yield 8800 bp)
- blocks **Meeting** / `mtg.papers_missed_their_deadline` (would yield 9000 bp)
- Action Item: An item reappearing on successiveagendas is the observable form of carry-over.

### `approver.unavailable_until` · fact_path

- blocks **Approval** / `apv.stuck_because_the_approver_is_absent` (would yield 8800 bp)
- blocks **Approver** / `apr.out_of_office_with_no_delegate` (would yield 9000 bp)
- Approval: The calendar connector reads timed meetings and discards all-day absence events, so the system knows the approver is not in a meeting and not that they are in Lisbon for a fortnight. Cheapest fix in the whole backlog and it removes the most common cause of a stuck approval.
- Approver: The calendar connectorreads timed meetings and discards all-day absence events, so the pipeline knows an approver is not in a meeting and cannot know they are away for a fortnight. It is the cheapest item in this backlog and it removes the most common cause of a stuck approval.

### `commitment.recipient` · fact_path

- blocks **Commitment** / `cmt.promise_to_a_departing_party` (would yield 7000 bp)
- blocks **Commitment** / `cmt.recipient_is_named` (would yield 9000 bp)
- Commitment: Without the recipient the negotiability of the date is unknowable, so every overdue item gets an identical treatment. A slip owed to the audit committee and a slip owed to a colleague are not the same row and must not produce the same message.

### `document.classification` · fact_path

- blocks **Document** / `doc.classification_exceeded_by_distribution` (would yield 9000 bp)
- blocks **Employee Record** / `emp.special_category_data_in_the_general_file` (would yield 8800 bp)
- Document: Labels exist in most DMS and DLP tooling and reach no typed fact. Until they do, the pipeline can see that an artefact was sent externally and not whether it was allowed to be.
- Employee Record: Classification is appliedby a human at filing time, if at all. Automated classification of a fit note or an occupational-health report is well within reach of L2 extraction and would catch the commonest quiet breach in this domain: sensitive content in an ordinary folder.

### `access.granted_at` · fact_path

- blocks **Approver** / `apr.authority_without_the_entitlement` (would yield 8800 bp)
- blocks **Request** / `req.entitlement_not_checked_before_grant` (would yield 8500 bp)
- Approver: New approvers are named ina matrix long before IT provisions the approval role, so the first three weeks of a mover's authority are theoretical. Everybody works around it by asking the predecessor, which quietly recreates the undocumented delegation above.
- Request: Least privilege is enforced at intake or it is not enforced at all. The grant is visible in the access log and the entitlement question is recorded nowhere, so the control is unauditable by construction.


### `approval_turnaround` · baseline

- blocks **Approval** / `apv.latency_beyond_this_approver_norm` (would yield 7800 bp)
- blocks **Escalation** / `esc.approval_pending_past_its_own_turnaround` (would yield 8800 bp)
- Escalation: Per-approver, per-value-band. The band matters: the same person clears £500 in a day and £50,000 in a fortnight.

### `card.transaction_at` · fact_path

- blocks **Expense Claim** / `exp.card_transaction_never_claimed` (would yield 8800 bp)
- blocks **Expense Claim** / `exp.unsubmitted_at_period_end` (would yield 8200 bp)
- Expense Claim: Requires a card feed. This inverts every control in the object — the money is already gone and the missing artefact is the EXPLANATION, not the payment. Unreconciled card spend is the largest silent exposure in expense administration and nothing here can see a single transaction.
- Expense Claim: The draft state — money spent, claim not raised — is invisible to every dashboard because nothing has been created yet to count. It is also the single largest source of surprise at period end, and it is entirely predictable.

### `evidence_provided` · obs_kind

- blocks **Commitment** / `cmt.closed_without_evidence` (would yield 8500 bp)
- blocks **Standard Operating Procedure** / `sop.control_steps_skipped` (would yield 8500 bp)
- Commitment: The absence of an evidence event against a closure is what separates a compliance record from a tidy queue. Every register that has run for a year is mostly assumed closures, and no report distinguishes them.
- Standard Operating Procedure: The control steps are the ones that produce evidence and do not advance the work, so their omission shows up as missing evidence rather than as a missing output. Nobody is inconvenienced by a control step being skipped until an auditor samples, which is why this drift is always found late and always found by an outsider.

### `contract.counterparty` · fact_path

- blocks **Contract** / `ct.spend_without_paper` (would yield 8000 bp)
- blocks **Vendor** / `vn.concentration_risk` (would yield 7500 bp)
- Vendor: Concentration is a joinacross contracts and spend by counterparty. Neither side is projected, so exposure is only ever seen one contract at a time — which is the same as not seeing it.

### `derived.budget_burn_rate` · derived

- blocks **Budget Line** / `bl.burn_ahead_of_phasing` (would yield 8000 bp)
- blocks **Budget Line** / `bl.material_underspend_late_in_period` (would yield 7000 bp)
- Budget Line: Must be phasing-adjustedor it is worse than nothing — an unadjusted burn alert fires every January on every seasonal line and trains its audience to ignore it within one cycle.
- Budget Line: Underspend is never investigatedbecause nothing is on fire, and it is the earliest available evidence that a programme has quietly halted. The lowest-urgency, highest-insight pattern on this object.

### `expense.merchant` · fact_path

- blocks **Expense Claim** / `exp.duplicate_across_payment_methods` (would yield 8000 bp)
- blocks **Expense Claim** / `exp.special_category_merchant_in_the_approval_route` (would yield 7500 bp)

### `derived.obligation_pressure` · derived

- blocks **Commitment** / `cmt.owner_is_saturated` (would yield 7800 bp)
- blocks **Contract** / `ct.obligation_load_never_abstracted` (would yield 6000 bp)
- Commitment: Count and proximity of open obligations per owner. commitment.action resolves to a single latest value, so the substrate cannot express a SET of open commitments at all — the defining administrative insight, that a person holding fourteen due items effectively holds none, is unexpressible.
- Contract: Requires clause-level extraction of duties owed by us. Deliberately weak at 6000 — the absence of a record is evidence about our administration, not about the contract.

### `admin_request_volume` · baseline

- blocks **Request** / `req.repeat_ask_means_a_broken_answer` (would yield 7500 bp)
- blocks **Standard Operating Procedure** / `sop.cycle_time_diverged_from_the_written_duration` (would yield 7500 bp)
- Standard Operating Procedure: Divergence in either direction is a signal. Slower means steps have been added that the document does not carry; faster almost always means steps are being skipped, and the skipped ones are the controls. The second case is the dangerous one and it looks like a productivity improvement on every dashboard.

### `prebrief_delivered` · obs_kind

- blocks **Action Item** / `ai.chair_asked_for_it` (would yield 7500 bp)
- blocks **Meeting** / `mtg.prebrief_never_delivered` (would yield 7000 bp)
- Action Item: Chair sponsorship is visiblein a transcript and in the pre-brief, and nowhere in structured data. It is the strongest single predictor of a minuted action being done, and it is entirely invisible to every action tracker ever built.
- Meeting: Executive support's core deliverableand it leaves no typed trace — a brief is an attachment or a five-minute corridor conversation. Without it the function's most valuable output is also its least measurable, which is a familiar and expensive combination.

### `document_published` · obs_kind

- blocks **Document** / `doc.approval_recorded_in_the_register` (would yield 10000 bp)
- Document: Publication is a distinct event from approval and is currently unobservable. The gap between the two is where approved policies live unread for a quarter.

### `filing.reference_number` · fact_path

- blocks **Filing** / `fil.acknowledgement_received` (would yield 10000 bp)

### `filing_accepted` · obs_kind

- blocks **Filing** / `fil.acknowledgement_received` (would yield 10000 bp)
- Filing: Every portal emails an acknowledgementcontaining a reference number in a stable format. Nothing parses it, so `submitted` and `accepted` are the same state to the pipeline and the gap where late filings hide is invisible by construction.

### `obligation.jurisdiction` · fact_path

- blocks **Filing** / `fil.statutory_calendar` (would yield 10000 bp)
- Filing: Without jurisdictiona multi-entity group cannot be sequenced at all — the same form name means different dates in different countries.

### `bank_details_change_requested` · obs_kind

- blocks **Vendor** / `vn.bank_details_changed` (would yield 9900 bp)
- Vendor: The request almostalways arrives by email, on a real thread, from a real-looking address. L2 already reads that mailbox; it is not looking for this. Cheapest high-value extractor in the Admin backlog.

### `vendor.bank_account_fingerprint` · fact_path

- blocks **Vendor** / `vn.bank_details_changed` (would yield 9900 bp)
- Vendor: No connectorreads the vendor master or the payments ledger, so the single highest-risk event in the administrative function produces no signal at all. Invoice-redirection fraud is the most expensive thing an administrator can fail to catch, and today the pipeline cannot see the change happen — only the payment leave.

### `approver.effective_to` · fact_path

- blocks **Approver** / `apr.authority_expiry_recorded` (would yield 9800 bp)
- Approver: DOA matrices are re-issuedannually with partial adoption, so at any moment part of the organisation approves under a superseded version. No system holds the version, so no system can tell that a decision made yesterday is void.

### `asset.custodian` · fact_path

- blocks **Asset** / `ast.custodian_left_still_holding` (would yield 9800 bp)
- Asset: Requires the register to be readableas typed facts rather than a spreadsheet export.

### `contract_countersigned` · obs_kind

- blocks **Contract** / `ct.executed_copy_exists` (would yield 9800 bp)
- Contract: L2 emits contract_requested and never contract_countersigned. The exact moment obligations attach to us — the one event that changes our legal position — is unobserved, so the register learns of it whenever somebody remembers to update it. Cheapest high-value line in this object's backlog.

### `escalation_requested` · obs_kind

- blocks **Escalation** / `esc.explicitly_asked_for` (would yield 9800 bp)
- Escalation: The strongest possible grounds and the pipeline drops it. When a requester asks to escalate, the object exists at near certainty and no inference is required.

### `filing_rejected` · obs_kind

- blocks **Filing** / `fil.rejection_detected` (would yield 9800 bp)
- Filing: The highest-urgency administrativeevent in this object. A rejection consumes buffer that was already planned against, and it currently arrives as an email in one person's inbox with no route into the system that is reporting the filing as done.

### `request.category` · fact_path

- blocks **Request** / `req.intake_form_classification` (would yield 9800 bp)
- Request: No service-desk or form connector exists. Category is the cheapest field in the whole domain — the requester types it — and it does not reach Layer 2, so every request arrives unclassified and is triaged by whoever opens the inbox first.


### `screening_result_returned` · obs_kind

- blocks **Vendor** / `vn.screening_hit` (would yield 9800 bp)
- Vendor: Screening runs insidea third-party tool whose result never leaves it, so a hit is actioned only if a human happens to read the report. A blocking control that depends on somebody opening an attachment is not a blocking control.

### `employee.right_to_work_expires_at` · fact_path

- blocks **Employee Record** / `emp.right_to_work_expiring` (would yield 9700 bp)
- Employee Record: A statutorydeadline, known years in advance, held in a scanned document and tracked by whoever last thought about it. The most avoidable compliance failure in people administration.

### `expense.receipt_present` · fact_path

- blocks **Expense Claim** / `exp.receipt_missing_above_threshold` (would yield 9600 bp)
- Expense Claim: Receipt presence is trivially available in every expense tool ever built and reachable by nothing here.

### `access.last_used_at` · fact_path

- blocks **Approver** / `apr.leaver_still_holds_the_entitlement` (would yield 9500 bp)
- Approver: Joins the leaver to the liveentitlement. Together these two produce the orphaned-approver finding automatically; separately they produce nothing, which is why every organisation finds it manually at audit.

### `asset.due_back_at` · fact_path

- blocks **Asset** / `ast.issued_and_never_returned` (would yield 9500 bp)
- Asset: No connector projects an expectedreturn date. Until it does, an asset can be issued indefinitely and never become overdue — the register is structurally incapable of reporting the failure it exists to prevent.

### `asset_returned` · obs_kind

- blocks **Asset** / `ast.issued_and_never_returned` (would yield 9500 bp)
- Asset: Returns are recorded in a spreadsheetor a helpdesk ticket, never as a typed event, so the closing half of the custody cycle is invisible.

### `calendar.event.previous_start_at` · fact_path

- blocks **Time Block** / `tb.displacement_recorded` (would yield 9500 bp)
- Time Block: The connectoroverwrites the event on update rather than retaining the prior start. The single most valuable administrative fact in a calendar — what moved, and for what — is destroyed by the sync that ingests it.

### `document_review_overdue` · obs_kind

- blocks **Document** / `doc.review_due_date_passed` (would yield 9500 bp)
- Document: The prompt that makes the date operational. A due date nothing watches is a preference.

### `invoice.due_at` · fact_path

- blocks **Invoice** / `inv.overdue_against_contractual_terms` (would yield 9500 bp)
- Invoice: commitment.due_at is the nearest live equivalent, and binding invoice ageing to it would report every unrelated promise on the thread as a late payment. That is precisely the stretch this library exists to refuse.

### `meeting.quorum_required` · fact_path

- blocks **Meeting** / `mtg.attendance_and_quorum` (would yield 9500 bp)
- Meeting: Quorum lives in termsof reference, which are a document nobody has parsed. Until it is a number, no system can tell a valid board meeting from an invalid one.

### `request.acknowledged_at` · fact_path

- blocks **Request** / `req.acknowledgement_recorded` (would yield 9500 bp)
- Request: The single number that governs requester experience, and there is no field for it. Acknowledgement is currently inferred from an observation that cannot tell an acknowledgement from any other outbound message.


### `retention_review_due` · obs_kind

- blocks **Document** / `doc.retention_period_elapsed` (would yield 9500 bp)
- Document: The scheduled prompt. Without it, disposal happens when somebody runs out of storage, which selects for size rather than for schedule.

### `vendor.diligence_expires_at` · fact_path

- blocks **Vendor** / `vn.diligence_expired` (would yield 9500 bp)
- Vendor: New backlog line.Most vendor masters hold the completion date and not the expiry, which converts a control into a record of a control.

### `expense.incurred_at` · fact_path

- blocks **Expense Claim** / `exp.claim_outside_the_submission_window` (would yield 9400 bp)
- Expense Claim: The spend date, distinct from the submission date, which is the only one correspondence can approximate. Approximating incurrence from an email timestamp gets the window wrong by exactly the amount that matters.

### `policy.claim_window_days` · fact_path

- blocks **Expense Claim** / `exp.claim_outside_the_submission_window` (would yield 9400 bp)
- Expense Claim: Policy thresholds live in a PDF. Until the policy is machine-readable, every limit in this object is enforced by a human remembering it, inconsistently, under time pressure.

### `record.access_log` · fact_path

- blocks **Employee Record** / `emp.file_read_by_someone_outside_the_reader_list` (would yield 9400 bp)
- Employee Record: Document stores emit auditlogs and nothing consumes them for this purpose. This is the only pattern in the object that would detect an unlawful disclosure while it is still recent enough to act on; without it, discovery happens through a complaint, months later.

### `derived.onboarding_completeness` · derived

- blocks **Employee Record** / `emp.start_date_approaching_file_incomplete` (would yield 9200 bp)
- Employee Record: Requires the mandatory-documentlist to be checkable rather than a checklist in a document.

### `vendor_bank_detail_change` · obs_kind

- blocks **Invoice** / `inv.bank_detail_change_before_payment` (would yield 9200 bp)
- Invoice: The highest-value fraud control in payables and the one with no emitter. An email extractor could plausibly catch the request language today; the authoritative version needs the vendor master.

### `asset_issued` · obs_kind

- blocks **Asset** / `ast.issued_without_signed_acceptance` (would yield 9000 bp)

### `calendar.event.category` · fact_path

- blocks **Time Block** / `tb.declared_focus_block` (would yield 9000 bp)
- Time Block: Both Google and Microsoftemit a native event type for focus time, out of office and working location. The connector reads title, time and attendees and drops the type, so the one field where the principal has already declared intent is discarded at ingest.

### `calendar.event.transparency` · fact_path

- blocks **Time Block** / `tb.declared_focus_block` (would yield 9000 bp)
- Time Block: Busy/free transparencydistinguishes a hold from a commitment and is present on every event object in both APIs.

### `derived.document_identity_cluster` · derived

- blocks **Document** / `doc.version_conflict_in_circulation` (would yield 9000 bp)
- Document: Content or title-plus-hash clustering across attachments and links. The expensive half of the ask, and the half that turns a version field into a conflict detector.

### `derived.performer_diversity` · derived

- blocks **Standard Operating Procedure** / `sop.performed_by_exactly_one_person` (would yield 9000 bp)
- Standard Operating Procedure: Distinct performers over executions in a window. Trivial arithmetic once executions are visible, impossible without them.

### `derived.recipient_is_external` · derived

- blocks **Document** / `doc.classification_exceeded_by_distribution` (would yield 9000 bp)
- Document: Domain comparison against the tenant's own domains. Cheap, and currently absent, which is why the single most preventable data-protection incident is also the least detectable one.

### `escalation_accepted` · obs_kind

- blocks **Escalation** / `esc.prior_escalation_accepted_and_nothing_moved` (would yield 9000 bp)
- Escalation: Acceptance without movement is worse than silence: it consumes the escalation, resets everyone's patience, and produces no decision. It should advance the ladder immediately rather than restart the clock.

### `filing.penalty_basis` · fact_path

- blocks **Filing** / `fil.penalty_basis_known` (would yield 9000 bp)
- Filing: Attached to the form type,not to the instance, so it is a small reference dataset rather than a feed. Its absence is why every overdue filing currently looks equally urgent, which in practice means none of them do.

### `filing_submitted` · obs_kind

- blocks **Filing** / `fil.submission_detected` (would yield 9000 bp)
- Filing: Cheaper than filing_acceptedand much less useful on its own; worth emitting only alongside it, because knowing something was sent without knowing it landed creates false comfort rather than information.

### `meeting.papers_deadline_at` · fact_path

- blocks **Meeting** / `mtg.papers_missed_their_deadline` (would yield 9000 bp)
- Meeting: A real, dated, enforcedadministrative deadline that exists only in the secretary's head and a recurring reminder. Nothing else in the stack knows the pack was two days late, so the pattern of lateness never becomes evidence at the board.

### `request.type` · fact_path

- blocks **Request** / `req.exception_worked_without_approval` (would yield 9000 bp)

### `sla.target_resolution_at` · fact_path

- blocks **Request** / `req.published_service_level` (would yield 9000 bp)
- Request: Service catalogues exist as documents, not as data. Until the target is a fact, every breach the engine can see is a broken personal promise and every published standard is unenforceable — which is a fair description of most administrative functions.


### `sop.tooling_referenced` · fact_path

- blocks **Standard Operating Procedure** / `sop.tooling_renamed_underneath_it` (would yield 9000 bp)
- Standard Operating Procedure: Requires the tool list to be structured rather than buried in prose.

### `sop_executed` · obs_kind

- blocks **Standard Operating Procedure** / `sop.performed_by_exactly_one_person` (would yield 9000 bp)
- Standard Operating Procedure: No connector reaches the systems where procedures are actually executed — the ERP, the ticket queue, the finance platform. This is the highest-value ask in this file: performer diversity is the one number that says whether writing the SOP achieved anything, and it is computable from execution records the moment they exist.

### `system_change_recorded` · obs_kind

- blocks **Standard Operating Procedure** / `sop.tooling_renamed_underneath_it` (would yield 9000 bp)
- Standard Operating Procedure: A change-management feed. The commonest silent invalidator of a procedure set, and the one that never reaches the document owner: a field rename in the finance system invalidates six procedures nobody has connected to it, and the first person to notice is a joiner who cannot find the field.

### `vendor.registration_number` · fact_path

- blocks **Vendor** / `vn.duplicate_vendor_record` (would yield 9000 bp)
- Vendor: Duplicates are howthe same invoice is paid twice and how a rejected supplier reappears under a variant spelling. Detectable the moment the master is readable and undetectable until then.

### `calendar.event.hold_expires_at` · fact_path

- blocks **Time Block** / `tb.hold_expired_unreleased` (would yield 8800 bp)
- Time Block: No system storesa hold expiry, because no system distinguishes a hold from a booking. Holds are released by an assistant remembering, which means they are not released.

### `meeting.series_id` · fact_path

- blocks **Action Item** / `ai.carried_across_consecutive_sittings` (would yield 8800 bp)
- Action Item: Recurring meetings arrive asunrelated calendar events, so a weekly committee is thirty separate meetings to the pipeline and carry-over cannot be computed at all. The single most diagnostic administrative number about a meeting is therefore unavailable.

### `vendor.onboarding_state` · fact_path

- blocks **Vendor** / `vn.paid_without_approval` (would yield 8800 bp)
- Vendor: The join that would findevery supplier admitted by exception. Almost always a short list, and almost always a surprising one.

### `access_granted` · obs_kind

- blocks **Request** / `req.entitlement_not_checked_before_grant` (would yield 8500 bp)

### `derived.attestation_coverage` · derived

- blocks **Policy** / `pol.attestation_cycle_never_ran` (would yield 8500 bp)
- Policy: Coverage across adefined population over a window. Trivial arithmetic once acknowledgements and the joiner feed exist; impossible without both.

### `derived.escalation_pressure` · derived

- blocks **Escalation** / `esc.repeat_stall_against_the_same_rung` (would yield 8500 bp)
- Escalation: Turns a sequence of incidents into a design finding. The output is not another escalation but a delegation change, and no organisation can see this today.

### `derived.vendor_first_seen` · derived

- blocks **Invoice** / `inv.unknown_payee_plausible_project` (would yield 8500 bp)
- Invoice: The classic redirection fraud. It survives because the project is real and the amount is plausible. Detecting it needs only the vendor master's first-seen date, which no connector supplies.

### `joiner_confirmed` · obs_kind

- blocks **Standard Operating Procedure** / `sop.new_joiner_followed_a_stale_version` (would yield 8500 bp)

### `meeting.attendees` · fact_path

- blocks **Action Item** / `ai.owner_was_not_in_the_room` (would yield 8500 bp)
- Action Item: Calendar is connected and meeting.start_atis projected, but the attendee roster is discarded at ingestion. This is the cheapest unbuilt signal in the Admin brain: the roster is already in the payload.

### `payment_released` · obs_kind

- blocks **Approval** / `apv.retrospective_collection` (would yield 8500 bp)
- Approval: Comparing the decision timestamp against the execution timestamp is a two-line rule that cannot be written because neither timestamp exists. The rate of retrospective approvals is the sharpest available diagnostic of which control is too slow to be complied with.

### `person.working_hours` · fact_path

- blocks **Time Block** / `tb.outside_working_hours` (would yield 8500 bp)
- Time Block: No working-hours or timezonemodel exists, so a 07:00 block in London and a 07:00 block in Singapore are indistinguishable to the pipeline even when the same person holds both.

### `policy.exception_count` · fact_path

- blocks **Policy** / `pol.exceptions_outnumber_compliance` (would yield 8500 bp)
- Policy: Exception registers livein spreadsheets and GRC tools that no connector touches. This is the fastest read on whether a policy fits the organisation, and a policy that has never granted an exception is usually not being applied rather than perfectly drafted.

### `policy.exception_expiry_at` · fact_path

- blocks **Policy** / `pol.exceptions_outnumber_compliance` (would yield 8500 bp)
- Policy: Without expiry, anexception is indistinguishable from a permanent private amendment.

### `sop_step_skipped` · obs_kind

- blocks **Standard Operating Procedure** / `sop.control_steps_skipped` (would yield 8500 bp)

### `vendor.last_reviewed_at` · fact_path

- blocks **Vendor** / `vn.never_reviewed_since_onboarding` (would yield 8500 bp)
- Vendor: Absent this field theanswer defaults to 'presumably fine', which is the answer the vendor master has been giving for years. The cheapest way to make third-party risk real is to make the absence of a review visible.

### `verbal_request_captured` · obs_kind

- blocks **Request** / `req.arrived_off_queue` (would yield 8500 bp)
- Request: The corridor ask leaves no artefact by definition. The only realistic capture is an administrator retro-logging it, which means the signal must come from a deliberate act rather than from extraction — an honest limit, not a missing parser.


### `derived.reporting_line` · derived

- blocks **Expense Claim** / `exp.approver_cannot_have_known` (would yield 8400 bp)
- Expense Claim: The reporting line exists in every HR system and nowhere in this stack. Without it, approval routing degrades silently from 'somebody who would know' to 'somebody with a licence', and the resulting control checks arithmetic rather than truth.

### `commitment.previous_due_at` · fact_path

- blocks **Commitment** / `cmt.date_moved_again` (would yield 8200 bp)
- Commitment: commitment.due_at resolves to the latest value only, so the pipeline overwrites the very history that predicts the outcome. Retaining the prior value on revision is a small change at L2 and yields the single most predictive administrative field there is.

### `derived.invoice_fingerprint` · derived

- blocks **Invoice** / `inv.duplicate_suspected_by_amount` (would yield 8200 bp)
- Invoice: A vendor-amount-period hash. Cheap to compute, nothing computes it. Number-based deduplication is the version that ships everywhere and the version that catches nothing, because reissued duplicates always carry new numbers.

### `derived.reschedule_count` · derived

- blocks **Time Block** / `tb.repeatedly_moved` (would yield 8200 bp)
- Time Block: Derivable only if calendar.event.previous_start_atis retained. Depends on the same discarded field as tb.displacement_recorded, which is why that one is the highest-value calendar ask in the library.

### `expense.state` · fact_path

- blocks **Expense Claim** / `exp.unsubmitted_at_period_end` (would yield 8200 bp)

### `asset.last_verified_at` · fact_path

- blocks **Asset** / `ast.register_row_never_reconciled` (would yield 8000 bp)
- Asset: Not in the planned listand it should be. Every register has an issue date; almost none has a last-verified date, which is why the first stock count in a decade always produces a double-digit variance and a governance paper.

### `calendar.free_capacity_minutes` · fact_path

- blocks **Time Block** / `tb.commitment_due_with_no_hour_reserved` (would yield 8000 bp)
- Time Block: Requires a working-hoursmodel plus an aggregation over the block set. commitment.due_at exists today and is genuinely administrative; what is missing is the other half — whether there is anywhere for the work to go.

### `derived.claim_fingerprint` · derived

- blocks **Expense Claim** / `exp.duplicate_across_payment_methods` (would yield 8000 bp)
- Expense Claim: Merchant, date and amount hashed per claimant. The overwhelming majority of genuine duplicates are this exact honest mistake, and catching them cheaply is worth more than any fraud model — and costs a fraction of one.

### `derived.contains_personal_data` · derived

- blocks **Document** / `doc.personal_data_without_retention_rule` (would yield 8000 bp)
- Document: Content classification for personal data. Available in every DLP product and in no signal here. Its absence means storage limitation under GDPR Art. 5(1)(e) cannot be reasoned about at all.

### `derived.control_enforcement_rate` · derived

- blocks **Policy** / `pol.enforced_only_by_self_declaration` (would yield 8000 bp)
- Policy: Would need policy-to-controlmapping and control test outcomes. Nothing in Layer 1 reaches the systems that would prove enforcement — the IAM platform, the expense tool, the procurement gate — so the difference between a policy that stops behaviour and one that describes it is currently unknowable.

### `derived.request_similarity` · derived

- blocks **Request** / `req.duplicate_of_an_open_request` (would yield 8000 bp)
- Request: Multi-channel intake guarantees duplicates — the same person asks by email on Monday and in person on Tuesday because the first went unacknowledged. Nothing dedupes them, so demand is over-reported and the requester receives two different answers, one of which is wrong.


### `sla_breach` · obs_kind

- blocks **Vendor** / `vn.service_level_failing` (would yield 8000 bp)
- Vendor: Planned in the support block but ticket-scoped,not vendor-scoped. A breach by OUR supplier and a breach by US to a customer are opposite facts and would land in the same bucket unless the direction is carried.

### `sop_execution_observed` · obs_kind

- blocks **Standard Operating Procedure** / `sop.never_verified_against_practice` (would yield 8000 bp)
- Standard Operating Procedure: A gemba walk leaves no digital trace today. Even a calendar entry titled 'process walkthrough' with the performer as attendee would be a usable proxy, and nothing currently reads it.

### `vendor.service_level_target` · fact_path

- blocks **Vendor** / `vn.service_level_failing` (would yield 8000 bp)

### `asset.last_seen_at` · fact_path

- blocks **Asset** / `ast.device_stopped_checking_in` (would yield 7500 bp)
- Asset: MDM and endpoint managementalready hold this and expose it over API. It is the cheapest custody verification available to any organisation and no admin system consumes it — the security team watches it for compromise and nobody watches it for custody.

### `commitment_delivery_rate` · baseline

- blocks **Commitment** / `cmt.chronic_owner` (would yield 7500 bp)
- Commitment: A per-person learned baseline of promises kept by the first agreed date. Cheap once commitment.owner exists, and it converts the register from a list of dates into a forecast. Today every owner is modelled as equally reliable, which no administrator has ever believed.

### `decision_recorded` · obs_kind

- blocks **Meeting** / `mtg.standing_series_producing_no_decisions` (would yield 7500 bp)

### `derived.approval_rejection_rate` · derived

- blocks **Approver** / `apr.rubber_stamp` (would yield 7500 bp)

### `derived.backlog_age` · derived

- blocks **Request** / `req.aging_against_its_peer_group` (would yield 7500 bp)
- Request: Age is meaningless without a peer group. Ageing must be computed per category and per service level, and neither category nor service level is a fact today.


### `derived.calendar_density` · derived

- blocks **Time Block** / `tb.back_to_back_density` (would yield 7500 bp)
- Time Block: Computable today fromthe event stream and computed by nothing. Density is the property that determines whether adding one more thirty-minute block costs thirty minutes or costs the afternoon.

### `derived.decision_density` · derived

- blocks **Meeting** / `mtg.standing_series_producing_no_decisions` (would yield 7500 bp)
- Meeting: Decisions per meetingacross a series. Needs a decision_recorded observation extracted from minutes, which requires reading the attachment rather than the thread. The cheapest recurring saving in the whole domain and entirely unprovable today.

### `derived.merchant_category_sensitivity` · derived

- blocks **Expense Claim** / `exp.special_category_merchant_in_the_approval_route` (would yield 7500 bp)
- Expense Claim: A merchant-category classifier flagging spend that reveals special-category personal data under GDPR Article 9. Nobody designs an expense form to carry health data, and every expense form does. The routing default — send everything to the line manager — is the leak.

### `derived.period_activity` · derived

- blocks **Filing** / `fil.nil_period_detected` (would yield 7500 bp)
- Filing: Requires a ledger or payrollfeed scoped to the period. Worth building specifically because the nil return is the highest-frequency missed filing in existence and the cheapest one to never miss again.

### `derived.request_repeat_rate` · derived

- blocks **Request** / `req.repeat_ask_means_a_broken_answer` (would yield 7500 bp)
- Request: Repeat rate per requester and per category is the single most useful process-improvement signal the function could have. It needs a category and a stable requester identity, and neither exists yet. It is also the only route to Seddon's failure-demand share — chases, repeats and reopens as a proportion of total volume. Administrative queues are typically majority failure demand and almost none measure it, so every capacity argument is fought on total volume, which is the wrong number.


### `policy_breach_observed` · obs_kind

- blocks **Policy** / `pol.breach_observed_and_unescalated` (would yield 7500 bp)
- Policy: Requires policy-aware detectionover the systems where breaches actually show up — expense claims, access grants, procurement outside the gate. The unescalated breach is more diagnostic than the breach: it is the point at which the policy stopped being a rule and became advice.

### `contract.price_uplift_index` · fact_path

- blocks **Contract** / `ct.price_uplift_applied_without_a_decision` (would yield 7000 bp)
- Contract: New backlog line. Indexed uplift is the most common form of value leakage in a managed estate precisely because it arrives as a slightly larger invoice and is approved by being paid.

### `derived.meeting_attendance_rate` · derived

- blocks **Meeting** / `mtg.chronic_apologies_are_a_vacancy` (would yield 7000 bp)
- Meeting: Per-member attendanceacross a series. A committee whose quorum depends on someone who has not come since March is one apology away from being unable to decide anything, and the first person to notice is usually the auditor.

### `derived.policy_clause_coverage` · derived

- blocks **Expense Claim** / `exp.policy_clause_does_not_cover_this` (would yield 7000 bp)
- Expense Claim: Requires the policy parsed into addressable clauses. The highest-leverage signal in the whole object: it converts a recurring per-claim argument into a one-off amendment, and it is the only ask here whose value compounds rather than repeats.

### `person.seniority` · fact_path

- blocks **Request** / `req.jumped_the_queue_on_seniority` (would yield 7000 bp)
- Request: Requires title normalisation from the directory.

### `trip.return_at` · fact_path

- blocks **Time Block** / `tb.travel_with_no_recovery` (would yield 7000 bp)
- Time Block: The Trip object is authored inLayer 3 and no connector projects an itinerary into a fact, so the calendar cannot see the one thing that most reliably predicts the next fortnight's rescheduling.

### `derived.vendor_channel_norm` · derived

- blocks **Invoice** / `inv.channel_deviation` (would yield 6800 bp)
- Invoice: A per-vendor channel baseline. Weak alone — plenty of legitimate invoices arrive by email — but it is the cheapest signal correlating with the expensive ones, and it is genuinely independent of the bank-change signal, which is why it may raise confidence rather than merely restate it.

### `asset.issued_at` · fact_path

- blocks **Asset** / `ast.pool_item_held_beyond_the_pool_window` (would yield 6500 bp)

### `derived.commitment_clustering` · derived

- blocks **Budget Line** / `bl.march_buying_season` (would yield 6500 bp)
- Budget Line: Entirely predictableand almost never modelled. It is a rational response to use-it-or-lose-it, so the useful output is a rule change rather than a challenge to each individual buyer.

### `derived.pool_loan_duration` · derived

- blocks **Asset** / `ast.pool_item_held_beyond_the_pool_window` (would yield 6500 bp)
- Asset: A learned per-categorybaseline, exactly like reply_cadence. Pool assets have no formal due date, so the only workable definition of overdue is statistical: far longer than this category is normally out for.
