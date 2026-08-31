# Admin Expertise — signal backlog

> GENERATED — `python "Domain Expertise/_tools/backlog.py"`

Every row is a signal the authored expertise needs and the pipeline does not
emit. Ranked by how many inference patterns it unblocks, then by the confidence
of the strongest pattern waiting on it.

Rows marked `l2_situation_type` are the expensive ones. A blocked *pattern*
lowers one object's confidence; a blocked *situation* means the capability
behind it never compiles at all, and nothing errors or logs when it doesn't.

## Where the brain stands

- **123** patterns executable against the pipeline today
- **232** patterns blocked, waiting on **214** distinct signals
- **4** situation binding(s) waiting on an L2 type no pack emits
- Substrate today: **106** fact paths · **34** observation kinds · **2** baselines

## The backlog

| # | Signal | Kind | Owner | Unblocks | Top conf | Objects |
|---|---|---|---|---|---|---|
| 1 | `employee.end_at` | fact_path | L1 | 10 | 9800 | Access Right, Approver, Budget Line, Compliance Obligation, Document, Employee Record, Escalation, Standard Operating Procedure |
| 2 | `approval.state` | fact_path | L1/L2 | 9 | 10000 | Access Right, Action Item, Approval, Approver, Commitment, Deadline, Escalation, Request |
| 3 | `obligation.due_at` | fact_path | L1 | 9 | 10000 | Commitment, Compliance Obligation, Deadline, Escalation, Filing, Request |
| 4 | `leaver_confirmed` | obs_kind | L2 | 9 | 9800 | Access Right, Approver, Asset, Budget Line, Commitment, Compliance Obligation, Document, Employee Record, Standard Operating Procedure |
| 5 | `contract.end_at` | fact_path | L1 | 9 | 9600 | Asset, Budget Line, Contract, Deadline |
| 6 | `approval.approver` | fact_path | L1 | 7 | 10000 | Approval, Approver, Escalation |
| 7 | `document.approved_at` | fact_path | L1/L2 | 7 | 10000 | Action Item, Compliance Obligation, Document, Filing, Meeting, Standard Operating Procedure |
| 8 | `employee.start_at` | fact_path | L1 | 7 | 10000 | Compliance Obligation, Document, Employee Record, Expense Claim, Policy, Standard Operating Procedure |
| 9 | `contract.notice_period_days` | fact_path | L1 | 7 | 9500 | Asset, Budget Line, Contract, Deadline |
| 10 | `obligation.authority` | fact_path | L1 | 6 | 10000 | Commitment, Compliance Obligation, Deadline, Filing |
| 11 | `document.version` | fact_path | L1 | 6 | 9800 | Action Item, Document, Policy, Standard Operating Procedure |
| 12 | `approval.requested_at` | fact_path | L1/L2 | 6 | 9500 | Approval, Deadline, Escalation, Expense Claim, Trip |
| 13 | `document.retention_until` | fact_path | L1 | 6 | 9500 | Compliance Obligation, Deadline, Document, Employee Record |
| 14 | `evidence_provided` | obs_kind | L2 | 6 | 9000 | Action Item, Commitment, Compliance Obligation, Policy, Standard Operating Procedure |
| 15 | `approval.threshold_value` | fact_path | L1 | 5 | 10000 | Approval, Approver, Escalation, Expense Claim, Invoice |
| 16 | `policy_acknowledged` | obs_kind | L2 | 5 | 10000 | Document, Employee Record, Policy |
| 17 | `invoice.amount` | fact_path | L1 | 5 | 9800 | Contract, Invoice, Vendor |
| 18 | `document.review_due_at` | fact_path | L1 | 5 | 9500 | Deadline, Document, Policy, Standard Operating Procedure |
| 19 | `request.created_at` | fact_path | L1 | 5 | 9500 | Approval, Escalation, Request, Standard Operating Procedure |
| 20 | `access.granted_at` | fact_path | L1 | 5 | 9000 | Access Right, Approver, Request |
| 21 | `document_superseded` | obs_kind | L2 | 5 | 9000 | Action Item, Contract, Document, Policy, Standard Operating Procedure |
| 22 | `obligation.jurisdiction` | fact_path | L1 | 4 | 10000 | Compliance Obligation, Deadline, Filing |
| 23 | `invoice.po_ref` | fact_path | L1 | 4 | 9800 | Approval, Contract, Invoice |
| 24 | `approval_granted` | obs_kind | L2 | 4 | 9600 | Approval, Approver, Budget Line, Expense Claim |
| 25 | `access.last_used_at` | fact_path | L1 | 4 | 9500 | Access Right, Approver, Vendor |
| 26 | `approval_requested` | obs_kind | L2 | 4 | 9500 | Action Item, Approval, Commitment |
| 27 | `commitment.owner` | fact_path | L2 | 4 | 9500 | Action Item, Commitment |
| 28 | `derived.approval_latency` | derived | L2 | 4 | 9200 | Approval, Approver, Deadline, Escalation |
| 29 | `approval_turnaround` | baseline | L2 | 4 | 9000 | Approval, Approver, Deadline, Escalation |
| 30 | `asset.custodian` | fact_path | L1 | 3 | 9800 | Asset, Vendor |
| 31 | `budget.consumed` | fact_path | L1 | 3 | 9800 | Budget Line |
| 32 | `document_signed` | obs_kind | L1/L2 | 3 | 9800 | Asset, Contract, Document |
| 33 | `event.confirmed_attendees` | fact_path | L1 | 3 | 9800 | Event |
| 34 | `contract.auto_renew` | fact_path | L1 | 3 | 9600 | Budget Line, Contract, Deadline |
| 35 | `invoice.state` | fact_path | L1 | 3 | 9500 | Invoice, Vendor |
| 36 | `joiner_confirmed` | obs_kind | L2 | 3 | 9500 | Approver, Policy, Standard Operating Procedure |
| 37 | `meeting.attendees_actual` | fact_path | L1 | 3 | 9500 | Meeting |
| 38 | `request.state` | fact_path | L1 | 3 | 9500 | Escalation, Request, Standard Operating Procedure |
| 39 | `access_granted` | obs_kind | L2 | 3 | 9000 | Access Right, Request |
| 40 | `approval_delegated` | obs_kind | L2 | 3 | 9000 | Approval, Approver, Escalation |
| 41 | `commitment.state` | fact_path | L2 | 3 | 9000 | Action Item, Commitment |
| 42 | `document.classification` | fact_path | L1 | 3 | 9000 | Action Item, Document, Employee Record |
| 43 | `handover_completed` | obs_kind | L2 | 3 | 9000 | Action Item, Commitment, Standard Operating Procedure |
| 44 | `po_raised` | obs_kind | L2 | 3 | 9000 | Budget Line, Invoice |
| 45 | `derived.obligation_pressure` | derived | L2 | 3 | 8500 | Commitment, Compliance Obligation, Contract |
| 46 | `filing_accepted` | obs_kind | L2 | 2 | 10000 | Compliance Obligation, Filing |
| 47 | `bank_details_change_requested` | obs_kind | L2 | 2 | 9900 | Vendor |
| 48 | `budget.allocated` | fact_path | L1 | 2 | 9800 | Budget Line |
| 49 | `budget.committed` | fact_path | L1 | 2 | 9800 | Budget Line |
| 50 | `filing_rejected` | obs_kind | L2 | 2 | 9800 | Compliance Obligation, Filing |
| 51 | `goods_receipted` | obs_kind | L2 | 2 | 9800 | Invoice |
| 52 | `leave.category` | fact_path | L1 | 2 | 9800 | Leave Request |
| 53 | `minutes_circulated` | obs_kind | L2 | 2 | 9800 | Action Item, Meeting |
| 54 | `notice_served` | obs_kind | L2 | 2 | 9700 | Contract |
| 55 | `approval_rejected` | obs_kind | L2 | 2 | 9600 | Approval, Approver |
| 56 | `expense.amount` | fact_path | L1 | 2 | 9600 | Expense Claim |
| 57 | `asset_returned` | obs_kind | L2 | 2 | 9500 | Asset |
| 58 | `leave.balance_remaining` | fact_path | L1 | 2 | 9500 | Leave Request |
| 59 | `leave.end_at` | fact_path | L1 | 2 | 9500 | Leave Request |
| 60 | `leave.start_at` | fact_path | L1 | 2 | 9500 | Leave Request |
| 61 | `request.priority` | fact_path | L1 | 2 | 9500 | Escalation, Request |
| 62 | `retention_review_due` | obs_kind | L2 | 2 | 9500 | Document, Event |
| 63 | `trip.booked_at` | fact_path | L1 | 2 | 9500 | Trip |
| 64 | `trip.depart_at` | fact_path | L1 | 2 | 9500 | Trip |
| 65 | `access.reviewed_at` | fact_path | L1 | 2 | 9000 | Access Right, Policy |
| 66 | `agenda_circulated` | obs_kind | L2 | 2 | 9000 | Action Item, Meeting |
| 67 | `approver.unavailable_until` | fact_path | L1 | 2 | 9000 | Approval, Approver |
| 68 | `commitment.recipient` | fact_path | L2 | 2 | 9000 | Commitment |
| 69 | `card.transaction_at` | fact_path | L1 | 2 | 8800 | Expense Claim |
| 70 | `meeting.series_id` | fact_path | L1 | 2 | 8800 | Action Item |
| 71 | `access_revoked` | obs_kind | L2 | 2 | 8200 | Access Right, Asset |
| 72 | `commitment_delivery_rate` | baseline | L2 | 2 | 8200 | Action Item, Commitment |
| 73 | `contract.counterparty` | fact_path | L1 | 2 | 8000 | Contract, Vendor |
| 74 | `derived.budget_burn_rate` | derived | L2 | 2 | 8000 | Budget Line |
| 75 | `expense.merchant` | fact_path | L1 | 2 | 8000 | Expense Claim |
| 76 | `admin_request_volume` | baseline | L2 | 2 | 7500 | Request, Standard Operating Procedure |
| 77 | `prebrief_delivered` | obs_kind | L2 | 2 | 7500 | Action Item, Meeting |
| 78 | `asset_in_custody` | l2_situation_type | L1 | 1 | 10000 | [situation] Asset in Custody |
| 79 | `document_published` | obs_kind | L2 | 1 | 10000 | Document |
| 80 | `employee_lifecycle_event` | l2_situation_type | L1 | 1 | 10000 | [situation] Employee Lifecycle Event |
| 81 | `filing.reference_number` | fact_path | L2 | 1 | 10000 | Filing |
| 82 | `obligation_falls_due` | l2_situation_type | L1 | 1 | 10000 | [situation] Obligation Falls Due |
| 83 | `spend_against_a_commitment` | l2_situation_type | L1 | 1 | 10000 | [situation] Spend Against a Commitment |
| 84 | `vendor.bank_account_fingerprint` | fact_path | L1 | 1 | 9900 | Vendor |
| 85 | `approver.effective_to` | fact_path | L1 | 1 | 9800 | Approver |
| 86 | `contract_countersigned` | obs_kind | L2 | 1 | 9800 | Contract |
| 87 | `escalation_requested` | obs_kind | L2 | 1 | 9800 | Escalation |
| 88 | `event.capacity` | fact_path | L1 | 1 | 9800 | Event |
| 89 | `leave.state` | fact_path | L1 | 1 | 9800 | Leave Request |
| 90 | `minutes_adopted` | obs_kind | L2 | 1 | 9800 | Meeting |
| 91 | `request.category` | fact_path | L1 | 1 | 9800 | Request |
| 92 | `screening_result_returned` | obs_kind | L1 | 1 | 9800 | Vendor |
| 93 | `employee.right_to_work_expires_at` | fact_path | L1 | 1 | 9700 | Employee Record |
| 94 | `auto_renewal_imminent` | obs_kind | L2 | 1 | 9600 | Deadline |
| 95 | `expense.receipt_present` | fact_path | L1 | 1 | 9600 | Expense Claim |
| 96 | `asset.due_back_at` | fact_path | L1 | 1 | 9500 | Asset |
| 97 | `calendar.event.previous_start_at` | fact_path | L1 | 1 | 9500 | Time Block |
| 98 | `contract.cancellation_schedule` | fact_path | L1 | 1 | 9500 | Event |
| 99 | `derived.entitlement_set_by_identity` | derived | L2 | 1 | 9500 | Access Right |
| 100 | `document_review_overdue` | obs_kind | L2 | 1 | 9500 | Document |
| 101 | `event.final_numbers_due_at` | fact_path | L1 | 1 | 9500 | Event |
| 102 | `event.start_at` | fact_path | L1 | 1 | 9500 | Event |
| 103 | `invoice.due_at` | fact_path | L1 | 1 | 9500 | Invoice |
| 104 | `meeting.quorum_required` | fact_path | L1 | 1 | 9500 | Meeting |
| 105 | `notifiable_event_detected` | obs_kind | L2 | 1 | 9500 | Compliance Obligation |
| 106 | `payroll.cutoff_at` | fact_path | L1 | 1 | 9500 | Deadline |
| 107 | `request.acknowledged_at` | fact_path | L1 | 1 | 9500 | Request |
| 108 | `sod.conflict_pairs` | fact_path | L1 | 1 | 9500 | Access Right |
| 109 | `trip.visa_state` | fact_path | L1 | 1 | 9500 | Trip |
| 110 | `vendor.bank_verification_method` | fact_path | L1 | 1 | 9500 | Vendor |
| 111 | `vendor.diligence_expires_at` | fact_path | L1 | 1 | 9500 | Vendor |
| 112 | `expense.incurred_at` | fact_path | L1 | 1 | 9400 | Expense Claim |
| 113 | `policy.claim_window_days` | fact_path | L1 | 1 | 9400 | Expense Claim |
| 114 | `record.access_log` | fact_path | L1 | 1 | 9400 | Employee Record |
| 115 | `derived.onboarding_completeness` | derived | L2 | 1 | 9200 | Employee Record |
| 116 | `filing_due` | obs_kind | L2 | 1 | 9200 | Deadline |
| 117 | `filing_overdue` | obs_kind | L2 | 1 | 9200 | Deadline |
| 118 | `vendor_bank_detail_change` | obs_kind | L2 | 1 | 9200 | Invoice |
| 119 | `asset_issued` | obs_kind | L2 | 1 | 9000 | Asset |
| 120 | `calendar.event.category` | fact_path | L1 | 1 | 9000 | Time Block |
| 121 | `calendar.event.transparency` | fact_path | L1 | 1 | 9000 | Time Block |
| 122 | `derived.approver_availability` | derived | L2 | 1 | 9000 | Leave Request |
| 123 | `derived.document_cluster_key` | derived | L2 | 1 | 9000 | Document |
| 124 | `derived.document_live_copies` | derived | L2 | 1 | 9000 | Document |
| 125 | `derived.incident_window` | derived | L2 | 1 | 9000 | Access Right |
| 126 | `derived.instrument_version_current` | derived | L2 | 1 | 9000 | Compliance Obligation |
| 127 | `derived.performer_diversity` | derived | L2 | 1 | 9000 | Standard Operating Procedure |
| 128 | `derived.recipient_is_external` | derived | L2 | 1 | 9000 | Document |
| 129 | `derived.threshold_position` | derived | L2 | 1 | 9000 | Compliance Obligation |
| 130 | `escalation_accepted` | obs_kind | L2 | 1 | 9000 | Escalation |
| 131 | `event.contracted_minimum` | fact_path | L1 | 1 | 9000 | Event |
| 132 | `event.licences_required` | fact_path | L1 | 1 | 9000 | Event |
| 133 | `expense_claim_submitted` | obs_kind | L2 | 1 | 9000 | Trip |
| 134 | `filing.penalty_basis` | fact_path | L1 | 1 | 9000 | Filing |
| 135 | `filing_submitted` | obs_kind | L2 | 1 | 9000 | Filing |
| 136 | `leave.evidence_due_at` | fact_path | L1 | 1 | 9000 | Leave Request |
| 137 | `leave_evidence_received` | obs_kind | L2 | 1 | 9000 | Leave Request |
| 138 | `licence_evidenced` | obs_kind | L2 | 1 | 9000 | Event |
| 139 | `meeting.convened_at` | fact_path | L1 | 1 | 9000 | Meeting |
| 140 | `meeting.notice_period_days` | fact_path | L1 | 1 | 9000 | Meeting |
| 141 | `meeting.papers_deadline_at` | fact_path | L1 | 1 | 9000 | Meeting |
| 142 | `request.type` | fact_path | L1 | 1 | 9000 | Request |
| 143 | `retention_period_elapsed` | obs_kind | L2 | 1 | 9000 | Deadline |
| 144 | `sla.target_resolution_at` | fact_path | L1 | 1 | 9000 | Request |
| 145 | `sop.tooling_referenced` | fact_path | L1 | 1 | 9000 | Standard Operating Procedure |
| 146 | `sop_executed` | obs_kind | L2 | 1 | 9000 | Standard Operating Procedure |
| 147 | `system_change_recorded` | obs_kind | L2 | 1 | 9000 | Standard Operating Procedure |
| 148 | `trip.claim_due_at` | fact_path | L1 | 1 | 9000 | Trip |
| 149 | `trip.itinerary_source` | fact_path | L1 | 1 | 9000 | Trip |
| 150 | `trip_departed` | obs_kind | L2 | 1 | 9000 | Trip |
| 151 | `vendor.registration_number` | fact_path | L1 | 1 | 9000 | Vendor |
| 152 | `calendar.event.hold_expires_at` | fact_path | L1 | 1 | 8800 | Time Block |
| 153 | `derived.identity_owner_resolvable` | derived | L2 | 1 | 8800 | Access Right |
| 154 | `renewal_window_open` | obs_kind | L2 | 1 | 8800 | Budget Line |
| 155 | `vendor.onboarding_state` | fact_path | L1 | 1 | 8800 | Vendor |
| 156 | `derived.attestation_coverage` | derived | L2 | 1 | 8500 | Policy |
| 157 | `derived.days_by_jurisdiction_12m` | derived | L2 | 1 | 8500 | Trip |
| 158 | `derived.escalation_pressure` | derived | L2 | 1 | 8500 | Escalation |
| 159 | `derived.grant_provenance_completeness` | derived | L2 | 1 | 8500 | Access Right |
| 160 | `derived.reporting_distance` | derived | L2 | 1 | 8500 | Approver |
| 161 | `derived.vendor_first_seen` | derived | L2 | 1 | 8500 | Invoice |
| 162 | `event.attendee_data_retention_until` | fact_path | L1 | 1 | 8500 | Event |
| 163 | `event.end_at` | fact_path | L1 | 1 | 8500 | Event |
| 164 | `final_invoice_received` | obs_kind | L2 | 1 | 8500 | Event |
| 165 | `leave.carry_over_expires_at` | fact_path | L1 | 1 | 8500 | Leave Request |
| 166 | `meeting.attendees` | fact_path | L1 | 1 | 8500 | Action Item |
| 167 | `meeting.interests_declared` | fact_path | L1 | 1 | 8500 | Meeting |
| 168 | `payment_released` | obs_kind | L2 | 1 | 8500 | Approval |
| 169 | `person.working_hours` | fact_path | L1 | 1 | 8500 | Time Block |
| 170 | `policy.exception_count` | fact_path | L1 | 1 | 8500 | Policy |
| 171 | `policy.exception_expiry_at` | fact_path | L1 | 1 | 8500 | Policy |
| 172 | `return_to_work_recorded` | obs_kind | L2 | 1 | 8500 | Leave Request |
| 173 | `sop_step_skipped` | obs_kind | L2 | 1 | 8500 | Standard Operating Procedure |
| 174 | `trip.unused_credit_expires_at` | fact_path | L1 | 1 | 8500 | Trip |
| 175 | `vendor.last_reviewed_at` | fact_path | L1 | 1 | 8500 | Vendor |
| 176 | `verbal_request_captured` | obs_kind | L2 | 1 | 8500 | Request |
| 177 | `derived.reporting_line` | derived | L2 | 1 | 8400 | Expense Claim |
| 178 | `commitment.previous_due_at` | fact_path | L2 | 1 | 8200 | Commitment |
| 179 | `derived.invoice_fingerprint` | derived | L2 | 1 | 8200 | Invoice |
| 180 | `derived.reschedule_count` | derived | L2 | 1 | 8200 | Time Block |
| 181 | `expense.state` | fact_path | L1 | 1 | 8200 | Expense Claim |
| 182 | `asset.last_verified_at` | fact_path | L1 | 1 | 8000 | Asset |
| 183 | `calendar.free_capacity_minutes` | fact_path | L2 | 1 | 8000 | Time Block |
| 184 | `derived.absence_occasions_12m` | derived | L2 | 1 | 8000 | Leave Request |
| 185 | `derived.claim_fingerprint` | derived | L2 | 1 | 8000 | Expense Claim |
| 186 | `derived.concurrent_travel_to_destination` | derived | L2 | 1 | 8000 | Trip |
| 187 | `derived.contains_personal_data` | derived | L2 | 1 | 8000 | Document |
| 188 | `derived.control_enforcement_rate` | derived | L2 | 1 | 8000 | Policy |
| 189 | `derived.preparation_lead_time` | derived | L2 | 1 | 8000 | Deadline |
| 190 | `derived.request_similarity` | derived | L2 | 1 | 8000 | Request |
| 191 | `derived.supplier_role_count_per_event` | derived | L2 | 1 | 8000 | Event |
| 192 | `derived.team_absence_overlap` | derived | L2 | 1 | 8000 | Leave Request |
| 193 | `sla_breach` | obs_kind | L2 | 1 | 8000 | Vendor |
| 194 | `sop_execution_observed` | obs_kind | L2 | 1 | 8000 | Standard Operating Procedure |
| 195 | `vendor.service_level_target` | fact_path | L1 | 1 | 8000 | Vendor |
| 196 | `asset.last_seen_at` | fact_path | L1 | 1 | 7500 | Asset |
| 197 | `decision_recorded` | obs_kind | L2 | 1 | 7500 | Meeting |
| 198 | `derived.approval_rejection_rate` | derived | L2 | 1 | 7500 | Approver |
| 199 | `derived.backlog_age` | derived | L2 | 1 | 7500 | Request |
| 200 | `derived.calendar_density` | derived | L2 | 1 | 7500 | Time Block |
| 201 | `derived.decision_density` | derived | L2 | 1 | 7500 | Meeting |
| 202 | `derived.merchant_category_sensitivity` | derived | L2 | 1 | 7500 | Expense Claim |
| 203 | `derived.period_activity` | derived | L2 | 1 | 7500 | Filing |
| 204 | `derived.request_repeat_rate` | derived | L2 | 1 | 7500 | Request |
| 205 | `policy_breach_observed` | obs_kind | L2 | 1 | 7500 | Policy |
| 206 | `contract.price_uplift_index` | fact_path | L1 | 1 | 7000 | Contract |
| 207 | `derived.meeting_attendance_rate` | derived | L2 | 1 | 7000 | Meeting |
| 208 | `derived.policy_clause_coverage` | derived | L2 | 1 | 7000 | Expense Claim |
| 209 | `person.seniority` | fact_path | L1 | 1 | 7000 | Request |
| 210 | `trip.return_at` | fact_path | L1 | 1 | 7000 | Time Block |
| 211 | `derived.vendor_channel_norm` | derived | L2 | 1 | 6800 | Invoice |
| 212 | `asset.issued_at` | fact_path | L1 | 1 | 6500 | Asset |
| 213 | `derived.commitment_clustering` | derived | L2 | 1 | 6500 | Budget Line |
| 214 | `derived.pool_loan_duration` | derived | L2 | 1 | 6500 | Asset |

## Why each one matters

### `employee.end_at` · fact_path

- blocks **Access Right** / `acr.leaver_still_entitled` (would yield 9800 bp)
- blocks **Approver** / `apr.leaver_still_holds_the_entitlement` (would yield 9500 bp)
- blocks **Budget Line** / `bl.owner_unknown_or_departed` (would yield 8500 bp)
- blocks **Compliance Obligation** / `obl.accountable_owner_has_left` (would yield 9200 bp)
- blocks **Document** / `doc.owner_left_the_organisation` (would yield 9000 bp)
- blocks **Document** / `doc.retention_clock_never_started` (would yield 9000 bp)
- blocks **Employee Record** / `emp.leaver_confirmed_offboarding_not_started` (would yield 9600 bp)
- blocks **Employee Record** / `emp.retention_period_elapsed` (would yield 9000 bp)
- blocks **Escalation** / `esc.rung_is_absent_not_refusing` (would yield 9000 bp)
- blocks **Standard Operating Procedure** / `sop.owner_left_and_nobody_inherited` (would yield 9000 bp)
- Compliance Obligation: Needed to distinguish a leaver from long-term absence — identical silence, opposite responses, and the second one has an end date.
- Document: The commonest trigger in practice for personnel records, and the join nobody makes. A schedule whose clock never starts looks complete and disposes of nothing — the quiet way an estate becomes permanent.
- Document: The date. Needed to distinguish an owner who has left from one who is on leave — the two produce identical silence and demand opposite responses.
- Employee Record: Also the origin of every retentioncalculation on this object. Its absence means retention_until cannot be computed at all, only asserted.
- Escalation: Absence and delegation records live in HRIS and the calendar out-of-office, neither of which is projected. This is the highest-value false-positive suppressor on the object: it stops the system escalating past people who are asleep in a different timezone.

### `approval.state` · fact_path

- blocks **Access Right** / `acr.no_recorded_reason` (would yield 8500 bp)
- blocks **Action Item** / `ai.item_blocked_not_neglected` (would yield 8400 bp)
- blocks **Approval** / `apv.blocked_behind_a_prior_serial_step` (would yield 8000 bp)
- blocks **Approval** / `apv.explicit_state_field` (would yield 10000 bp)
- blocks **Approver** / `apr.overloaded_not_absent` (would yield 7000 bp)
- blocks **Commitment** / `cmt.blocked_on_a_signature` (would yield 8600 bp)
- blocks **Deadline** / `dl.blocking_approval_not_started` (would yield 9000 bp)
- blocks **Escalation** / `esc.approval_pending_past_its_own_turnaround` (would yield 8800 bp)
- blocks **Request** / `req.exception_worked_without_approval` (would yield 9000 bp)
- Action Item: Being blamed at three consecutive sittings for a signature somebody else owes is the most reliable way to teach a manager never to accept a minuted action again.
- Approval: Every ERP, P2P and ITSM tool exposes an approval state on its API and none of them are read. This single path would convert most of this object from inference to fact — the highest-leverage unbuilt connector field in the Admin domain.
- Approval: Serial chains are invisible today, so a position-4 approver is chased for a delay caused entirely at position 1. The chase is wasted, the real blocker is never contacted, and position 4 learns to ignore chases.
- Approver: Counting what is open with one person requires approval state at all. Load and absence present identically in an inbox and want opposite remedies — one wants fewer approvals routed here, the other wants a delegate — and choosing wrongly makes both worse.
- Commitment: Needed to tell pending from stuck. Same row, different move: one wants a reminder, the other wants a different approver.
- Escalation: No typed approval state exists. Everything administrative about stalled decisions is currently inferred from email shape, which is why this object leans so hard on commitment.due_at.
- Request: The control that matters most in intake — an exception worked by an operator rather than routed to an approver — is undetectable, because neither half of the comparison exists as a fact.


### `obligation.due_at` · fact_path

- blocks **Commitment** / `cmt.promise_restates_an_obligation` (would yield 9000 bp)
- blocks **Compliance Obligation** / `obl.continuous_duty_never_examined` (would yield 8500 bp)
- blocks **Compliance Obligation** / `obl.duty_of_record_from_the_register` (would yield 9500 bp)
- blocks **Compliance Obligation** / `obl.filing_rejected_does_not_discharge` (would yield 9800 bp)
- blocks **Compliance Obligation** / `obl.retention_floor_breached_by_internal_schedule` (would yield 9000 bp)
- blocks **Deadline** / `dl.statutory_date_from_the_obligation_register` (would yield 9800 bp)
- blocks **Escalation** / `esc.protected_deadline_inside_the_ladder_time` (would yield 9200 bp)
- blocks **Filing** / `fil.statutory_calendar` (would yield 10000 bp)
- blocks **Request** / `req.jumped_the_queue_on_seniority` (would yield 7000 bp)
- Commitment: Requires an obligation register connector — a statutory calendar, a filing portal, or the contract's own dates. Until it exists the engine cannot distinguish the most negotiable commitment in the queue from the least, and treats both as movable.
- Compliance Obligation: The obligations register exists as a spreadsheet in most organisations and as a typed fact in none. Without it every judgement in this file is inferred from email.
- Compliance Obligation: Needed to know whether the resubmission window still lands inside the deadline, which is the only question that matters at that moment.
- Compliance Obligation: Its ABSENCE is the whole pattern. A continuous duty has no date, so it never appears on a deadline report, and deadline reports are how organisations decide what to look at.
- Compliance Obligation: The other side, as the record-keeping duty's own horizon. A tidy internal retention policy destroying records a statute required for six years is the rare compliance failure caused entirely by diligence.
- Deadline: The central absence in the Admin brain. The pipeline knows when a person promised something and has never heard of a statute, which is why an administrative queue built on it ranks a board pack above a filing.
- Escalation: Escalate to the deadline, not to the elapsed time. Without an external date the system can only reason about patience, which is exactly the reasoning administrators are told to stop using.
- Request: The comparison becomes possible only when the statutory deadline is visible alongside the diary query. Today only one side of it is, which is precisely why the queue-jump is invisible and universal. This is the pattern that would let a function prove its median turnaround is excellent AND its statutory work is late, which are the two facts nobody currently sees together.

- Filing: There is no regulatory calendarconnector and no statutory date feed. The single most consequential date in the administrative function is typed by a human into a spreadsheet and copied forward each year, which is exactly how a leap-year quarter-end gets a wrong date and nobody notices until the penalty notice arrives.

### `leaver_confirmed` · obs_kind

- blocks **Access Right** / `acr.leaver_still_entitled` (would yield 9800 bp)
- blocks **Approver** / `apr.leaver_still_holds_the_entitlement` (would yield 9500 bp)
- blocks **Asset** / `ast.custodian_left_still_holding` (would yield 9800 bp)
- blocks **Budget Line** / `bl.owner_unknown_or_departed` (would yield 8500 bp)
- blocks **Commitment** / `cmt.promise_to_a_departing_party` (would yield 7000 bp)
- blocks **Compliance Obligation** / `obl.accountable_owner_has_left` (would yield 9200 bp)
- blocks **Document** / `doc.owner_left_the_organisation` (would yield 9000 bp)
- blocks **Employee Record** / `emp.leaver_confirmed_offboarding_not_started` (would yield 9600 bp)
- blocks **Standard Operating Procedure** / `sop.owner_left_and_nobody_inherited` (would yield 9000 bp)
- Access Right: Reaches HR weeks before it reaches anyone who can revoke. Shared with employee_record and asset — one event, three objects, and the highest-consequence gap in the Admin brain.
- Approver: The leaving event exists in the HRIS and is projected nowhere the approval routing can see it.
- Asset: The single highest-value missing signal for this object, and shared with employee_record and access_right. Departure is known to HRIS weeks in advance and reaches the asset register, if at all, after the last working day — which is precisely when recovery stops being possible.
- Budget Line: An orphaned budget line is the quietest failure in this file. Nothing breaks, nothing alerts, and spend continues against a line whose owner left in March — discovered at year end by whoever inherits the variance.
- Commitment: Joiner-mover-leaver events are visible in HRIS and never reach the commitment register. The correct move is to ask the successor whether they still want it; the default move is to deliver a report to a mailbox nobody reads. This is also the only pattern that would catch an unowned promise before the audit does.
- Compliance Obligation: Joiner-mover-leaver reliably reaches access rights and payroll. It reaches the obligations register in almost no organisation, so duties keep an owner who has been gone for a year and every escalation path terminates in a disabled mailbox.
- Document: Joiner-mover-leaver reaches access rights in most organisations and document ownership in almost none. The leaver's documents keep their review dates, keep sending reminders into a disabled mailbox, and are discovered unowned at the next audit.
- Employee Record: The highest-value signal missingfrom the whole people-administration set. HR knows about a departure during the notice period; asset recovery and access removal find out afterwards, when neither is achievable.

### `contract.end_at` · fact_path

- blocks **Asset** / `ast.contractor_holding_with_no_leaver_route` (would yield 7000 bp)
- blocks **Asset** / `ast.lease_return_window_opening` (would yield 9400 bp)
- blocks **Budget Line** / `bl.auto_renewal_commits_the_line` (would yield 9000 bp)
- blocks **Contract** / `ct.amendment_chain_obscures_the_terms` (would yield 6500 bp)
- blocks **Contract** / `ct.default_renewal_imminent` (would yield 9000 bp)
- blocks **Contract** / `ct.evergreen_never_re_decided` (would yield 7000 bp)
- blocks **Contract** / `ct.term_and_notice_are_known` (would yield 9500 bp)
- blocks **Deadline** / `dl.auto_renewal_already_locked` (would yield 9600 bp)
- blocks **Deadline** / `dl.contract_notice_date` (would yield 9500 bp)
- Asset: For a contractor the recovery trigger is the end of the engagement contract, not an HR leaver event — the population that holds equipment is always larger than the population the HRIS knows about, and the gap is never reconciled.
- Contract: No connector reads a contract register or CLM. The most consequential administrative date in the business — the last day we can walk away — does not exist in the pipeline in any form.
- Contract: Needs the term as restated by the LATEST instrument in the chain, not the first. Without it, a register with four amendments shows four end dates and no way to tell which one governs.
- Contract: Its ABSENCE is the trigger, so the field must exist before the absence is distinguishable from an unread register.
- Deadline: The consequence that generates no letter, no penalty and no alert — just another twelve months of a contract somebody wanted out of, discovered at the renewal invoice.

### `approval.approver` · fact_path

- blocks **Approval** / `apv.explicit_state_field` (would yield 10000 bp)
- blocks **Approval** / `apv.segregation_breach_on_this_decision` (would yield 9000 bp)
- blocks **Approver** / `apr.doa_matrix_row` (would yield 10000 bp)
- blocks **Approver** / `apr.four_eyes_partner_reports_to_holder` (would yield 8500 bp)
- blocks **Approver** / `apr.named_in_a_resolution_or_mandate` (would yield 10000 bp)
- blocks **Approver** / `apr.undocumented_delegation_in_operation` (would yield 8200 bp)
- blocks **Escalation** / `esc.repeat_stall_against_the_same_rung` (would yield 8500 bp)
- Approval: State without a holder is still unactionable: you know it is open, not who to chase.
- Approver: Who may approve what. Exists as a spreadsheet appended to a finance policy in essentially every organisation over fifty people, and is read by no connector.
- Approver: The strongest instrument that exists and the narrowest in scope. It is also the one that lags reality longest — mandates outlive the people on them by years, because changing a bank mandate requires wet signatures from people who have left.
- Approver: Comparing the intended approver against the actual granting actor is a one-line rule that cannot be written today. It detects the assistant approving under a verbal instruction — extremely common, entirely undocumented, operationally invaluable, and the first thing an examiner finds.

### `document.approved_at` · fact_path

- blocks **Action Item** / `ai.adopted_at_the_next_sitting` (would yield 9600 bp)
- blocks **Compliance Obligation** / `obl.discharged_but_unevidenced` (would yield 8000 bp)
- blocks **Compliance Obligation** / `obl.exemption_claimed_without_a_basis` (would yield 8500 bp)
- blocks **Document** / `doc.approval_recorded_in_the_register` (would yield 10000 bp)
- blocks **Filing** / `fil.dependency_not_signed_off` (would yield 8500 bp)
- blocks **Meeting** / `mtg.minute_adopted_at_the_next_sitting` (would yield 9800 bp)
- blocks **Standard Operating Procedure** / `sop.review_date_passed_unverified` (would yield 8500 bp)
- Action Item: The moment of adoption is the moment an action item becomes independently enforceable. It happens in every governed forum on earth, every month, and is recorded in a file the pipeline cannot see.
- Compliance Obligation: An unapproved artefact is not evidence. Without this the object cannot distinguish a controlled record from a draft somebody wrote after being asked.
- Compliance Obligation: The written basis has to be an approved artefact or it is a conversation. Exemptions are narrower than the people relying on them believe — the Art. 30 small-organisation derogation evaporates on special-category data or non-occasional processing, which is essentially every employer.
- Document: Every document management system holds this on every controlled artefact. No connector projects it, so the single field that separates a draft from a document is invisible to reasoning — the highest-value missing path in this file and arguably in the Admin brain.
- Meeting: Adoption, not circulation, is what turns a minute into a record. It happens once a month in every governed organisation, it is announced aloud, and nothing captures it — so `minuted_rate` is everywhere computed on circulation and everywhere overstates compliance.

- Standard Operating Procedure: Needed to distinguish 'never reviewed since approval' from 'reviewed and due again', which are different problems with different owners.
- Filing: Annual filings fail on theirdependency, not on their preparation. An audit that slips two weeks moves the real start of the filing by two weeks and moves the statutory date by nothing, and no current signal expresses that squeeze.

### `employee.start_at` · fact_path

- blocks **Compliance Obligation** / `obl.threshold_crossed_pulls_us_into_scope` (would yield 9000 bp)
- blocks **Document** / `doc.acknowledgement_population_incomplete` (would yield 8500 bp)
- blocks **Employee Record** / `emp.start_date_approaching_file_incomplete` (would yield 9200 bp)
- blocks **Expense Claim** / `exp.approver_cannot_have_known` (would yield 8400 bp)
- blocks **Policy** / `pol.acknowledgement_recorded` (would yield 10000 bp)
- blocks **Policy** / `pol.joiners_bound_but_never_told` (would yield 9500 bp)
- blocks **Standard Operating Procedure** / `sop.new_joiner_followed_a_stale_version` (would yield 8500 bp)
- Compliance Obligation: Headcount is the commonest threshold and the easiest to compute. Nobody sends a letter on the day you hire your 250th employee, and no internal system treats it as an event.
- Document: The denominator moves. Nothing binds a new starter to a document published before they arrived — the single largest hole in every acknowledgement number ever reported to a board.
- Employee Record: Every HRIS holds this and noconnector projects it. Without it, the one deadline in onboarding that is genuinely fixed and genuinely known in advance is invisible to the engine, and onboarding is reduced to whoever remembers.
- Policy: Needed for the denominator and for on-joining attestation. Without it, coverage is computed over whoever already signed, which always reports as complete.
- Standard Operating Procedure: This is the object's central failure made detectable, and it is worth stating plainly: the only people who follow the SOP exactly are the people who cannot tell it is wrong. Everyone experienced corrects it silently. Detecting this requires knowing which version reached the joiner, which requires version identity on the copy rather than on the master.

### `contract.notice_period_days` · fact_path

- blocks **Asset** / `ast.lease_return_window_opening` (would yield 9400 bp)
- blocks **Budget Line** / `bl.auto_renewal_commits_the_line` (would yield 9000 bp)
- blocks **Budget Line** / `bl.renewal_window_closing_unnoticed` (would yield 8800 bp)
- blocks **Contract** / `ct.default_renewal_imminent` (would yield 9000 bp)
- blocks **Contract** / `ct.evergreen_never_re_decided` (would yield 7000 bp)
- blocks **Contract** / `ct.term_and_notice_are_known` (would yield 9500 bp)
- blocks **Deadline** / `dl.contract_notice_date` (would yield 9500 bp)
- Asset: The deadline that matters on a lease is not the end date, it is the notice date before it. Missing the notice triggers automatic extension at full rate, which is the most expensive silent failure in this object and is knowable years in advance.
- Budget Line: Independent of the auto-renew flag: this fires on the calendar rather than on the contract terms, which is why it may raise confidence rather than restate it. The decision to renew is taken by default, and the only moment it can be taken deliberately is inside this window.
- Contract: Extractable from the termination clause with document-level extraction. Today it lives only in the PDF, and therefore only in the memory of whoever last read it.
- Contract: On an evergreen the notice period is the entire exit mechanism; there is no expiry to fall back on.
- Deadline: Two fields that would generate an entire notice calendar automatically. The date that gets missed is never printed on the contract — it is ninety clear days before a date that is.

### `obligation.authority` · fact_path

- blocks **Commitment** / `cmt.promise_restates_an_obligation` (would yield 9000 bp)
- blocks **Compliance Obligation** / `obl.duty_of_record_from_the_register` (would yield 9500 bp)
- blocks **Compliance Obligation** / `obl.instrument_amended_invalidates_our_reading` (would yield 9000 bp)
- blocks **Compliance Obligation** / `obl.notification_clock_running` (would yield 9500 bp)
- blocks **Deadline** / `dl.statutory_date_from_the_obligation_register` (would yield 9800 bp)
- blocks **Filing** / `fil.statutory_calendar` (would yield 10000 bp)
- Commitment: Who set the date. Determines whether an extension is even conceptually available, which is a different question from whether one would be granted.
- Compliance Obligation: Who has to be satisfied. Determines self-report credit, notification tolerance and whether the outcome gets published — three things that change the plan completely.
- Compliance Obligation: The subscription key for horizon scanning — you monitor an authority, not a topic.
- Compliance Obligation: Which authority must be told, and therefore which window applies. 72 hours is the famous one and is not universal.

### `document.version` · fact_path

- blocks **Action Item** / `ai.minute_line_reference` (would yield 9800 bp)
- blocks **Action Item** / `ai.reworded_between_sittings` (would yield 7800 bp)
- blocks **Document** / `doc.version_conflict_in_circulation` (would yield 9000 bp)
- blocks **Policy** / `pol.superseded_but_still_circulating` (would yield 9000 bp)
- blocks **Standard Operating Procedure** / `sop.new_joiner_followed_a_stale_version` (would yield 8500 bp)
- blocks **Standard Operating Procedure** / `sop.two_versions_in_circulation` (would yield 9000 bp)
- Action Item: Needed to distinguish draft minutes from the circulated version. An action lifted from an uncirculated draft is not yet binding on anyone, and treating it as though it were is how a secretariat loses the room.
- Action Item: Comparing an item across successive minute versions is what catches 'draft the policy' quietly becoming 'consider options for the policy' at sitting four. Nobody does this by hand, and it is the mechanism by which a matters-arising list stays short while achieving nothing.
- Document: SATISFIED 2026-08-29 by context/documents.py, which projects file-store metadata onto a document node. Read what it is before resting anything on it: this is a per-file REVISION COUNTER, not a semantic version. Two independent copies of the handbook are both revision 1 on the day they are made and both revision 40 after a year of equal editing, so equality of this field proves nothing and inequality proves less.
- Policy: Requires version identity across copies rather than only on the master. Until it exists, 'which version was I bound by' — the only version question a tribunal ever asks — cannot be answered from the system, and the honest reply is that we do not know.
- Standard Operating Procedure: Requires version identity across copies, not just on the master. Until it exists, 'which version did they follow' — the only version question ever asked in anger — cannot be answered from the system, and the honest response to a tribunal is that we do not know.

### `approval.requested_at` · fact_path

- blocks **Approval** / `apv.approval_requested_observation` (would yield 9500 bp)
- blocks **Approval** / `apv.retrospective_collection` (would yield 8500 bp)
- blocks **Deadline** / `dl.blocking_approval_not_started` (would yield 9000 bp)
- blocks **Escalation** / `esc.approval_pending_past_its_own_turnaround` (would yield 8800 bp)
- blocks **Expense Claim** / `exp.pre_approval_absent_for_restricted_category` (would yield 9200 bp)
- blocks **Trip** / `trp.approval_after_booking` (would yield 9500 bp)
- Approval: The clock start. Every duration metric on this object is uncomputable without it, which makes this the single ask that unblocks the most other work.
- Expense Claim: Needed to prove the approval predates the spend. An approval record without a timestamp cannot distinguish pre-approval from retrospective cover, which is the entire point of the control.
- Trip: The quietest and most important control failure on this object. It is the normal state wherever travellers book their own travel, and it converts the approval step into a signature on a decision already taken.

### `document.retention_until` · fact_path

- blocks **Compliance Obligation** / `obl.retention_floor_breached_by_internal_schedule` (would yield 9000 bp)
- blocks **Deadline** / `dl.retention_period_elapsed` (would yield 9000 bp)
- blocks **Document** / `doc.personal_data_without_retention_rule` (would yield 8000 bp)
- blocks **Document** / `doc.retention_clock_never_started` (would yield 9000 bp)
- blocks **Document** / `doc.retention_period_elapsed` (would yield 9500 bp)
- blocks **Employee Record** / `emp.retention_period_elapsed` (would yield 9000 bp)
- Compliance Obligation: One side of the comparison. Internal schedules may exceed the external floor and never fall short, and today nothing can perform the comparison at all.
- Deadline: The deadline that runs the other way: holding the data is the breach. Nothing visibly bad happens on the day, which is exactly why it is never diarised and why over-retention is the commonest data-protection finding.
- Document: Retention schedules exist on paper in most organisations and in no queryable field. Over-retention is a storage-limitation breach in its own right and the only one that gets worse purely by the passage of time with nobody touching anything.
- Document: Its ABSENCE against a populated retention class is the finding. Schedules are written as 'six years from termination' and the termination date lives in HRIS, unjoined.
- Document: Its absence against a positive personal-data finding is the whole pattern. Personal data, no series, no disposal date — the shape of an over-retention breach that grows every day nobody acts.
- Employee Record: Retention is authoredin a schedule document and never projected onto the records it governs, so no system anywhere in the organisation can answer 'what should be destroyed this month'. Over-retention is therefore the default state of every personnel archive, and it is invisible because nothing breaks.

### `evidence_provided` · obs_kind

- blocks **Action Item** / `ai.closed_before_the_next_sitting` (would yield 9000 bp)
- blocks **Commitment** / `cmt.closed_without_evidence` (would yield 8500 bp)
- blocks **Compliance Obligation** / `obl.discharged_but_unevidenced` (would yield 8000 bp)
- blocks **Compliance Obligation** / `obl.exemption_claimed_without_a_basis` (would yield 8500 bp)
- blocks **Policy** / `pol.control_claimed_but_never_tested` (would yield 8000 bp)
- blocks **Standard Operating Procedure** / `sop.control_steps_skipped` (would yield 8500 bp)
- Action Item: Distinguishes an item closed against a deliverable from one closed against a verbal assurance. In an assurance forum only the first is closure.
- Commitment: The absence of an evidence event against a closure is what separates a compliance record from a tidy queue. Every register that has run for a year is mostly assumed closures, and no report distinguishes them.
- Compliance Obligation: Its ABSENCE against a discharged state is the finding. Compliance work is performed far more often than it is evidenced, and from outside the organisation those two situations are identical.
- Compliance Obligation: Links the reasoning to the entry. An exemption with no traversable basis will be re-argued from scratch at every audit, by people who were not there.
- Policy: Testing a control means attempting the prohibited thing and confirming it fails. Almost nobody records having done it, and the absence is the strongest available indicator that the claimed control has never fired — which is discovered, invariably, by the first outsider who tests it.
- Standard Operating Procedure: The control steps are the ones that produce evidence and do not advance the work, so their omission shows up as missing evidence rather than as a missing output. Nobody is inconvenienced by a control step being skipped until an auditor samples, which is why this drift is always found late and always found by an outsider.

### `approval.threshold_value` · fact_path

- blocks **Approval** / `apv.doa_threshold_covers_the_value` (would yield 9500 bp)
- blocks **Approver** / `apr.doa_matrix_row` (would yield 10000 bp)
- blocks **Escalation** / `esc.missing_authority_not_missing_answer` (would yield 8600 bp)
- blocks **Expense Claim** / `exp.split_below_the_approval_threshold` (would yield 6500 bp)
- blocks **Invoice** / `inv.approver_over_their_limit` (would yield 9600 bp)
- Approval: The DOA matrix exists in every organisation past about fifty people, usually as a spreadsheet appended to a finance policy. No connector reads it, so the system cannot tell a correctly routed approval from a wrongly routed one — and wrongly routed approvals age identically to correct ones until somebody notices by hand.
- Approver: The limit. Without it the system cannot tell a correctly routed approval from a wrongly routed one, and wrongly routed approvals age exactly like correct ones.
- Escalation: The governance gap that masquerades as a delay. Climbing a ladder whose top rung still cannot sign wastes weeks and ends in an improvised approval that fails audit later.
- Expense Claim: Deliberately weak at 6500 even once available. Splitting is far more often the claimant doing what the form encouraged — one line per receipt — than an attempt to evade a limit, and treating it as the latter is how a control loses the goodwill it runs on.
- Invoice: Delegation-of-authority matrices live in a policy document, not a system. Until the DOA is machine-readable, over-limit approval is only ever caught at audit, months after the cash left.

### `policy_acknowledged` · obs_kind

- blocks **Document** / `doc.acknowledgement_population_incomplete` (would yield 8500 bp)
- blocks **Employee Record** / `emp.handbook_attestation_never_returned` (would yield 8500 bp)
- blocks **Policy** / `pol.acknowledgement_recorded` (would yield 10000 bp)
- blocks **Policy** / `pol.attestation_cycle_never_ran` (would yield 8500 bp)
- blocks **Policy** / `pol.joiners_bound_but_never_told` (would yield 9500 bp)
- Document: The positive return. Counting them is trivial once emitted; today acknowledgement is proved by a spreadsheet somebody maintains by hand and abandons in month three.
- Employee Record: Attestation platforms existand are rarely joined to the personnel file, so the organisation can say a policy was published but not that any given person is bound by it — which is the only version of the fact a disciplinary process can use.
- Policy: Every LMS, HR platform and policy portal emits this on every attestation. Nothing consumes it, so the one fact that decides whether a policy is enforceable at all is invisible to reasoning. The highest-value ask in this file by a wide margin.
- Policy: The structural enforceability hole, and it opens continuously rather than at review time. Every joiner between attestation runs is bound by a rule nobody showed them, and an annual cycle means the average new starter spends six months in that state. This is also the population most likely to breach, because they are the ones still learning what is normal.

### `invoice.amount` · fact_path

- blocks **Contract** / `ct.price_uplift_applied_without_a_decision` (would yield 7000 bp)
- blocks **Invoice** / `inv.approver_over_their_limit` (would yield 9600 bp)
- blocks **Invoice** / `inv.duplicate_suspected_by_amount` (would yield 8200 bp)
- blocks **Invoice** / `inv.three_way_match_clean` (would yield 9800 bp)
- blocks **Vendor** / `vn.concentration_risk` (would yield 7500 bp)

### `document.review_due_at` · fact_path

- blocks **Deadline** / `dl.document_review_due` (would yield 8500 bp)
- blocks **Document** / `doc.review_due_date_passed` (would yield 9500 bp)
- blocks **Policy** / `pol.review_date_passed` (would yield 9500 bp)
- blocks **Standard Operating Procedure** / `sop.never_verified_against_practice` (would yield 8000 bp)
- blocks **Standard Operating Procedure** / `sop.review_date_passed_unverified` (would yield 8500 bp)
- Deadline: Internally set and genuinely movable, and included deliberately as the contrast case: this is what an internal target looks like when it is well run, and it must not be ranked alongside a filing.
- Document: A trivially computable date that no connector emits. Note this is a SELF-imposed date; the object it must not be confused with is compliance_obligation, whose dates cannot be moved by anyone here at all.
- Policy: The policy's own self-imposed date, carried on the controlled document. Independent of the commitment path — one comes from the document register and one from somebody's written promise — which is why it may corroborate rather than merely repeat.
- Standard Operating Procedure: The self-imposed date carried on the controlled document. Note the contrast with an external filing deadline: this one can be moved by the organisation that set it, which is exactly why it is missed so often.
- Standard Operating Procedure: Needed to separate 'reviewed, never verified' — the theatre case — from 'never reviewed at all', which is at least honest.

### `request.created_at` · fact_path

- blocks **Approval** / `apv.segregation_breach_on_this_decision` (would yield 9000 bp)
- blocks **Escalation** / `esc.request_ageing_against_service_level` (would yield 8000 bp)
- blocks **Request** / `req.aging_against_its_peer_group` (would yield 7500 bp)
- blocks **Request** / `req.state_from_the_service_desk` (would yield 9500 bp)
- blocks **Standard Operating Procedure** / `sop.cycle_time_diverged_from_the_written_duration` (would yield 7500 bp)
- Approval: Requires the requester identity alongside the approver identity. Self-approval is the control failure most often committed in good faith and most reliably found in the first walkthrough, and detecting it is a string comparison no system currently performs.
- Request: thread.last_inbound approximates arrival only while the ask lives in a mail thread. A portal submission has no thread at all, and a corridor ask has neither.


### `access.granted_at` · fact_path

- blocks **Access Right** / `acr.break_glass_never_withdrawn` (would yield 9000 bp)
- blocks **Access Right** / `acr.dormant_entitlement` (would yield 9000 bp)
- blocks **Access Right** / `acr.orphaned_service_account` (would yield 8800 bp)
- blocks **Approver** / `apr.authority_without_the_entitlement` (would yield 8800 bp)
- blocks **Request** / `req.entitlement_not_checked_before_grant` (would yield 8500 bp)
- Access Right: Needed to separate never-used from not-recently-used. The two are different conversations.
- Approver: New approvers are named in a matrix long before IT provisions the approval role, so the first three weeks of a mover's authority are theoretical. Everybody works around it by asking the predecessor, which quietly recreates the undocumented delegation above — the two failures are the same failure at opposite ends.
- Request: Least privilege is enforced at intake or it is not enforced at all. The grant is visible in the access log and the entitlement question is recorded nowhere, so the control is unauditable by construction.


### `document_superseded` · obs_kind

- blocks **Action Item** / `ai.reworded_between_sittings` (would yield 7800 bp)
- blocks **Contract** / `ct.amendment_chain_obscures_the_terms` (would yield 6500 bp)
- blocks **Document** / `doc.version_conflict_in_circulation` (would yield 9000 bp)
- blocks **Policy** / `pol.superseded_but_still_circulating` (would yield 9000 bp)
- blocks **Standard Operating Procedure** / `sop.two_versions_in_circulation` (would yield 9000 bp)
- Document: STILL ABSENT, and it is the whole difference between this pattern and the weaker claim Layer 2 can already make. Supersession has a timestamp in every DMS and no emitter here, so v2 published with v1 correctly withdrawn is indistinguishable from two teams editing in parallel. `document_under_control` therefore carries `derived.document_live_copies` and says only that two live copies exist; promoting this pattern to executable on the two signals above would turn that into an assertion that the wrong version is in circulation, which nothing here can support.

### `obligation.jurisdiction` · fact_path

- blocks **Compliance Obligation** / `obl.duty_of_record_from_the_register` (would yield 9500 bp)
- blocks **Deadline** / `dl.local_cutoff_unresolved` (would yield 7500 bp)
- blocks **Deadline** / `dl.statutory_date_from_the_obligation_register` (would yield 9800 bp)
- blocks **Filing** / `fil.statutory_calendar` (would yield 10000 bp)
- Compliance Obligation: One row per jurisdiction, not one row per topic. A single 'data protection' entry spanning six countries is wrong in five of them.
- Deadline: Without jurisdiction the holiday calendar and the local cut-off cannot be resolved, and a multi-entity group gets one wrong every year.
- Deadline: Registries close at counters, portals cut off at 23:59 local, payment files leave in the early afternoon. Storing a bare date silently loses between four hours and a full day of the window, and always on the day it matters.
- Filing: Without jurisdictiona multi-entity group cannot be sequenced at all — the same form name means different dates in different countries.

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
- Approver: Needed with the granting actor attached, not merely the fact of a grant.

### `access.last_used_at` · fact_path

- blocks **Access Right** / `acr.dormant_entitlement` (would yield 9000 bp)
- blocks **Access Right** / `acr.physical_pass_outlives_account` (would yield 8000 bp)
- blocks **Approver** / `apr.leaver_still_holds_the_entitlement` (would yield 9500 bp)
- blocks **Vendor** / `vn.offboarding_left_something_live` (would yield 8500 bp)
- Access Right: The single highest-value signal this object generates. Present in every IAM platform and most SaaS admin APIs, read by nobody. It converts access reduction from a negotiation into an observation, because a ninety-day dormant entitlement is removable without an argument.
- Access Right: Physical access sits in a separate system owned by facilities, and the leaver process that disables the account almost never reaches it. The pass in the drawer is the most common unrevoked entitlement in any organisation with an office.
- Approver: Joins the leaver to the live entitlement. Together these produce the orphaned-approver finding automatically; separately they produce nothing, which is why every organisation finds it by hand at audit.
- Vendor: Third-party accounts survive offboarding routinely, because the leaver process is built for employees and a vendor has no leaving date.

### `approval_requested` · obs_kind

- blocks **Action Item** / `ai.item_blocked_not_neglected` (would yield 8400 bp)
- blocks **Approval** / `apv.approval_requested_observation` (would yield 9500 bp)
- blocks **Approval** / `apv.information_missing_not_unwillingness` (would yield 8000 bp)
- blocks **Commitment** / `cmt.blocked_on_a_signature` (would yield 8600 bp)
- Approval: L2 already classifies asks in email, and approval asks are lexically distinctive — 'please approve', 'for your sign-off', 'awaiting your authorisation'. They are not extracted.
- Approval: Needed with direction attached, so a clarifying question can be told from a decision. Today an approval where the ball has bounced back to us looks identical to one the approver is sitting on, and the two have opposite remedies: send the quote comparison, or escalate.
- Commitment: An approval ask is a distinct speech act from a promise and the extractor collapses them. Without it a stuck approval is reported as an owner who is not delivering — wrong, and corrosive in a way that outlasts the commitment.

### `commitment.owner` · fact_path

- blocks **Action Item** / `ai.owner_named_in_the_minute` (would yield 9400 bp)
- blocks **Action Item** / `ai.owner_was_not_in_the_room` (would yield 8500 bp)
- blocks **Commitment** / `cmt.chronic_owner` (would yield 7500 bp)
- blocks **Commitment** / `cmt.owner_is_named` (would yield 9500 bp)
- Action Item: The extractor drops the subject of the sentence, so 'Priya to circulate the paper' and 'Finance to circulate the paper' are the same fact to the engine. The distinction between them is the difference between an item that gets done and one that is read out four times.
- Action Item: Without an owner there is nobody to compare the roster against.
- Commitment: The extractor emits the action and the date and drops the subject of the sentence. Every executable pattern above therefore assumes the promise is ours, which is the exact failure this object exists to prevent — roughly half of a real administrator's register is other people's promises to the organisation. Highest-value gap in the Admin brain by a distance.

### `derived.approval_latency` · derived

- blocks **Approval** / `apv.latency_beyond_this_approver_norm` (would yield 7800 bp)
- blocks **Approver** / `apr.batching_rhythm_is_not_absence` (would yield 8000 bp)
- blocks **Deadline** / `dl.lead_time_from_actuals` (would yield 8000 bp)
- blocks **Escalation** / `esc.protected_deadline_inside_the_ladder_time` (would yield 9200 bp)
- Approval: reply_cadence is a thread-level proxy that counts a one-line acknowledgement as a response. A real per-approver, per-type decision-latency baseline is what separates a slow approver from a stuck approval, and it can only be built once approval_requested and approval_granted both exist.
- Approver: The suppression this enables is worth more than the classification: without it, apr.silent_far_past_own_cadence fires weekly against the organisation's most reliable approvers.

### `approval_turnaround` · baseline

- blocks **Approval** / `apv.latency_beyond_this_approver_norm` (would yield 7800 bp)
- blocks **Approver** / `apr.batching_rhythm_is_not_absence` (would yield 8000 bp)
- blocks **Deadline** / `dl.blocking_approval_not_started` (would yield 9000 bp)
- blocks **Escalation** / `esc.approval_pending_past_its_own_turnaround` (would yield 8800 bp)
- Approver: A per-approver decision-time distribution, not a mean. Batching shows as low variance around a weekday, and a mean alone hides it entirely.
- Deadline: The deadline is not missed on the due date; it is missed on the day the sign-off should have started. This pattern is the earliest honest warning the object can generate.
- Escalation: Per-approver, per-value-band. The band matters: the same person clears £500 in a day and £50,000 in a fortnight.

### `asset.custodian` · fact_path

- blocks **Asset** / `ast.contractor_holding_with_no_leaver_route` (would yield 7000 bp)
- blocks **Asset** / `ast.custodian_left_still_holding` (would yield 9800 bp)
- blocks **Vendor** / `vn.offboarding_left_something_live` (would yield 8500 bp)
- Asset: Requires the register to be readable as typed facts rather than a spreadsheet export.
- Vendor: Recovery fails silently because nobody is inconvenienced by an unreturned asset except the balance sheet.

### `budget.consumed` · fact_path

- blocks **Budget Line** / `bl.burn_ahead_of_phasing` (would yield 8000 bp)
- blocks **Budget Line** / `bl.line_specific_commitment_recorded` (would yield 9800 bp)
- blocks **Budget Line** / `bl.material_underspend_late_in_period` (would yield 7000 bp)

### `document_signed` · obs_kind

- blocks **Asset** / `ast.issued_without_signed_acceptance` (would yield 9000 bp)
- blocks **Contract** / `ct.executed_copy_exists` (would yield 9800 bp)
- blocks **Document** / `doc.signed_original_exists` (would yield 9800 bp)
- Asset: e-signature platforms are a solved L1 integration everywhere except here; the completion callback is not projected as an observation, so the difference between an issued item and an accepted one cannot be computed — and that difference is the whole of enforceability.
- Contract: Every e-signature platform emits a completion webhook per envelope, with signer identity and timestamp. No connector consumes it.
- Document: E-signature platforms emit a completion webhook on every executed document. Nothing consumes it, so the exact moment an artefact becomes dispositive evidence is the moment the system stops watching it.

### `event.confirmed_attendees` · fact_path

- blocks **Event** / `evt.attrition_exposure_material` (would yield 9000 bp)
- blocks **Event** / `evt.capacity_exceeded` (would yield 9800 bp)
- blocks **Event** / `evt.final_numbers_deadline_approaching` (would yield 9500 bp)
- Event: The pair that makes attrition visible before it is billed. Without them, invitation lists get cut to save costs that were already incurred at signature.
- Event: A fire-safety and licensing limit, not a comfort figure. Exceeding it is an offence in most jurisdictions and voids the insurance at the same instant.

### `contract.auto_renew` · fact_path

- blocks **Budget Line** / `bl.auto_renewal_commits_the_line` (would yield 9000 bp)
- blocks **Contract** / `ct.auto_renewal_declared` (would yield 9500 bp)
- blocks **Deadline** / `dl.auto_renewal_already_locked` (would yield 9600 bp)
- Budget Line: Renewal commits money by nobody doing anything, which is why it is absent from every commitment figure built around purchase orders. Three cheap fields from a contract register close the largest structural hole in this object.
- Contract: Until this exists every contract must be assumed auto-renewing, which is the correct default and an expensive one — it puts a diary entry and a brief on instruments that never needed either.

### `invoice.state` · fact_path

- blocks **Invoice** / `inv.overdue_against_contractual_terms` (would yield 9500 bp)
- blocks **Invoice** / `inv.unknown_payee_plausible_project` (would yield 8500 bp)
- blocks **Vendor** / `vn.paid_without_approval` (would yield 8800 bp)

### `joiner_confirmed` · obs_kind

- blocks **Approver** / `apr.authority_without_the_entitlement` (would yield 8800 bp)
- blocks **Policy** / `pol.joiners_bound_but_never_told` (would yield 9500 bp)
- blocks **Standard Operating Procedure** / `sop.new_joiner_followed_a_stale_version` (would yield 8500 bp)

### `meeting.attendees_actual` · fact_path

- blocks **Meeting** / `mtg.attendance_and_quorum` (would yield 9500 bp)
- blocks **Meeting** / `mtg.chronic_apologies_are_a_vacancy` (would yield 7000 bp)
- blocks **Meeting** / `mtg.conflicted_member_counted_towards_quorum` (would yield 8500 bp)
- Meeting: The calendar connector projects start_at and status and discards the response list entirely. Acceptances, declines and tentatives are already in the payload — this is a projection gap, not a source gap, and it is the cheapest high-value fix in the Admin backlog.

- Meeting: The quiet governance failure. The declaration is made, minuted and then forgotten for the arithmetic, so the item is decided by a meeting that was not quorate for that item alone. Discovered, when it is discovered, by someone contesting the decision.


### `request.state` · fact_path

- blocks **Escalation** / `esc.request_ageing_against_service_level` (would yield 8000 bp)
- blocks **Request** / `req.state_from_the_service_desk` (would yield 9500 bp)
- blocks **Standard Operating Procedure** / `sop.cycle_time_diverged_from_the_written_duration` (would yield 7500 bp)
- Escalation: Admin queues publish response targets and measure nothing against them. Three fields would make the whole of service-level escalation automatic and remove the credibility cost from it.
- Request: Where a ticketing tool exists it is the system of record and the engine cannot read it, so Layer 3 is reasoning about a copy of the queue held in email.


### `access_granted` · obs_kind

- blocks **Access Right** / `acr.break_glass_never_withdrawn` (would yield 9000 bp)
- blocks **Access Right** / `acr.review_overdue` (would yield 9000 bp)
- blocks **Request** / `req.entitlement_not_checked_before_grant` (would yield 8500 bp)
- Access Right: Without a grant event there is no clock to start the interval from.

### `approval_delegated` · obs_kind

- blocks **Approval** / `apv.stuck_because_the_approver_is_absent` (would yield 8800 bp)
- blocks **Approver** / `apr.out_of_office_with_no_delegate` (would yield 9000 bp)
- blocks **Escalation** / `esc.rung_is_absent_not_refusing` (would yield 9000 bp)
- Approval: Needed to tell absent-with-cover from absent-without-cover. Only the second is stuck; chasing the first is noise and chasing the second is futile.
- Approver: Absence with cover is routine; absence without cover is a stoppage. Without the delegation signal the two are indistinguishable and both get chased.

### `commitment.state` · fact_path

- blocks **Action Item** / `ai.reported_with_no_update` (would yield 8000 bp)
- blocks **Commitment** / `cmt.closed_without_evidence` (would yield 8500 bp)
- blocks **Commitment** / `cmt.discharge_recorded` (would yield 9000 bp)
- Action Item: A per-sitting status against an action, distinct from the action's own state. It exists in every action tracker as a column and nowhere in the substrate.
- Commitment: The planned state field. followup_sent covers outbound email only; a call made, a form signed in a portal, a file dropped in a shared drive, or anything at all the counterparty did is invisible.

### `document.classification` · fact_path

- blocks **Action Item** / `ai.reserved_forum_item` (would yield 9000 bp)
- blocks **Document** / `doc.classification_exceeded_by_distribution` (would yield 9000 bp)
- blocks **Employee Record** / `emp.special_category_data_in_the_general_file` (would yield 8800 bp)
- Action Item: Board reserved business, HR matters and privileged legal work are classified at the document and forum level and the classification never reaches the action. Every automated action digest ever built has surfaced one of these at least once, and it is a governance incident rather than a bug report.
- Document: Labels exist in most DMS and DLP tooling and reach no typed fact. Until they do, the pipeline can see that an artefact was sent externally and not whether it was allowed to be.
- Employee Record: Classification is appliedby a human at filing time, if at all. Automated classification of a fit note or an occupational-health report is well within reach of L2 extraction and would catch the commonest quiet breach in this domain: sensitive content in an ordinary folder.

### `handover_completed` · obs_kind

- blocks **Action Item** / `ai.closed_before_the_next_sitting` (would yield 9000 bp)
- blocks **Commitment** / `cmt.discharge_recorded` (would yield 9000 bp)
- blocks **Standard Operating Procedure** / `sop.owner_left_and_nobody_inherited` (would yield 9000 bp)
- Action Item: Without any completion signal, ai.past_its_date_and_still_open will insist an item is overdue while the owner holds the finished document. Committees forgive a missed nudge and do not forgive being told, in front of the chair, that they have not done something they have.
- Commitment: The one closure event administrators already write down in words — 'handed over to Priya, done' — and which no pack extracts.
- Standard Operating Procedure: The absence of this is the signal, not its presence. Joiner-mover-leaver has a documented handover step in every organisation and an enforced one in almost none, because the leaver is the least motivated author in the building and their notice period is consumed by live work.

### `po_raised` · obs_kind

- blocks **Budget Line** / `bl.approved_uninvoiced_services_running` (would yield 7500 bp)
- blocks **Budget Line** / `bl.year_end_buying_season` (would yield 6500 bp)
- blocks **Invoice** / `inv.no_po_is_maverick_spend` (would yield 9000 bp)
- Budget Line: The invisible half of commitment: services engaged on an email thread. Detectable as an approval with no PO behind it, and both halves of that test are missing today.

### `derived.obligation_pressure` · derived

- blocks **Commitment** / `cmt.owner_is_saturated` (would yield 7800 bp)
- blocks **Compliance Obligation** / `obl.continuous_duty_never_examined` (would yield 8500 bp)
- blocks **Contract** / `ct.obligation_load_never_abstracted` (would yield 6000 bp)
- Commitment: Count and proximity of open obligations per owner. commitment.action resolves to a single latest value, so the substrate cannot express a SET of open commitments at all — the defining administrative insight, that a person holding fourteen due items effectively holds none, is unexpressible.
- Compliance Obligation: Ranking by something other than date. Record-keeping and technical-control duties are where inspections most often land findings, and they are precisely the ones a date-sorted register can never surface.
- Contract: Requires clause-level extraction of duties owed by us. Deliberately weak at 6000 — the absence of a record is evidence about our administration, not about the contract.

### `filing_accepted` · obs_kind

- blocks **Compliance Obligation** / `obl.filing_accepted_discharges_the_duty` (would yield 10000 bp)
- blocks **Filing** / `fil.acknowledgement_received` (would yield 10000 bp)
- Compliance Obligation: Acceptance by the authority is the only 10000-confidence discharge signal that exists in this domain, because it is the only one we did not write ourselves. Portals emit it; nothing consumes it.
- Filing: Every portal emails an acknowledgementcontaining a reference number in a stable format. Nothing parses it, so `submitted` and `accepted` are the same state to the pipeline and the gap where late filings hide is invisible by construction.

### `bank_details_change_requested` · obs_kind

- blocks **Vendor** / `vn.bank_details_changed` (would yield 9900 bp)
- blocks **Vendor** / `vn.verified_by_the_wrong_channel` (would yield 9500 bp)
- Vendor: The request almost always arrives by email, on a real thread, from a real-looking address, with a plausible reason and an urgent invoice attached. L2 already reads that mailbox; it is simply not looking for this. Cheapest high-value extractor in the entire Admin backlog.

### `budget.allocated` · fact_path

- blocks **Budget Line** / `bl.line_specific_commitment_recorded` (would yield 9800 bp)
- blocks **Budget Line** / `bl.overcommitted` (would yield 9600 bp)
- Budget Line: Overcommitment is a governance event, not an accounting one — somebody committed money they were not authorised to commit. It cannot be detected at all without both figures, and today the stack has neither.

### `budget.committed` · fact_path

- blocks **Budget Line** / `bl.line_specific_commitment_recorded` (would yield 9800 bp)
- blocks **Budget Line** / `bl.overcommitted` (would yield 9600 bp)
- Budget Line: The single most valuable unmet ask in the finance subdomain. Most ERPs already compute this and report it on a screen nobody opens; nothing projects it into a typed fact, so the number that surprises everybody at period end stays invisible to the one system that could warn them in advance.

### `filing_rejected` · obs_kind

- blocks **Compliance Obligation** / `obl.filing_rejected_does_not_discharge` (would yield 9800 bp)
- blocks **Filing** / `fil.rejection_detected` (would yield 9800 bp)
- Compliance Obligation: The nastiest gap in this file. Submission is what every internal tracker records, and a submitted-and-rejected filing reads as done everywhere inside the organisation while the deadline continues to run outside it. Rejections arrive by post or portal notice, days later, to whoever filed — who is frequently on leave by then.
- Filing: The highest-urgency administrativeevent in this object. A rejection consumes buffer that was already planned against, and it currently arrives as an email in one person's inbox with no route into the system that is reporting the filing as done.

### `goods_receipted` · obs_kind

- blocks **Invoice** / `inv.service_invoice_never_receipted` (would yield 7000 bp)
- blocks **Invoice** / `inv.three_way_match_clean` (would yield 9800 bp)
- Invoice: The receipt leg has no emitter at all. Its absence is why every match on this pipeline would be two-way, which proves ordering and never delivery.
- Invoice: Services are the blind spot inside the blind spot. Even organisations running a working three-way match routinely waive the receipt leg for consultancy and support — which is where the money is, and where nothing physical fails to arrive to prompt a question.

### `leave.category` · fact_path

- blocks **Leave Request** / `lvr.absence_trigger_reached` (would yield 8000 bp)
- blocks **Leave Request** / `lvr.statutory_category_refused` (would yield 9800 bp)
- Leave Request: The single most valuable signal this object generates. Without the category, every downstream rule about refusability, evidence, pay and balance is guesswork — and the specific failure it prevents is a manager declining statutory leave for coverage reasons, which is unlawful and currently invisible.
- Leave Request: Must be computed on sickness occasions only and must never fire automatically as an action. A trigger surfaced to a human is a management prompt; a trigger wired to a consequence is a discrimination claim, because the index cannot distinguish unreliability from a chronic condition.

### `minutes_circulated` · obs_kind

- blocks **Action Item** / `ai.minute_line_reference` (would yield 9800 bp)
- blocks **Meeting** / `mtg.minutes_actually_circulated` (would yield 9500 bp)
- Action Item: Minutes are the single richest administrative artefact in any organisation — dated, attributed, owner-assigned, and agreed by the silence of everyone who received them — and no connector reads them. Every gap on this object collapses to this one signal.
- Meeting: Distinguishing a minute from any other post-meeting email needs attachment-level extraction, not thread-level. Without it the governance metric that matters most is approximated by the weakest observation in the vocabulary.


### `notice_served` · obs_kind

- blocks **Contract** / `ct.default_renewal_imminent` (would yield 9000 bp)
- blocks **Contract** / `ct.notice_served_and_proved` (would yield 9700 bp)
- Contract: Absence of service is the trigger for the renewal alarm, so the signal must exist for its absence to mean anything. Today an unserved notice and a served-but-unrecorded notice are indistinguishable, and only one of them costs a renewal term of spend.
- Contract: The trigger is an absence, so the signal has to exist for its absence to be meaningful.

### `approval_rejected` · obs_kind

- blocks **Approval** / `apv.approval_decision_observation` (would yield 9600 bp)
- blocks **Approver** / `apr.rubber_stamp` (would yield 7500 bp)
- Approval: Rejections matter more than grants. A queue whose rejection rate is zero is a postbox, and only the rejected set tells you whether the control is doing anything at all.
- Approver: Grants without rejections cannot distinguish a working control from a postbox. The zero is the signal, and it can only be computed once refusals are visible at all.

### `expense.amount` · fact_path

- blocks **Expense Claim** / `exp.receipt_missing_above_threshold` (would yield 9600 bp)
- blocks **Expense Claim** / `exp.split_below_the_approval_threshold` (would yield 6500 bp)
- Expense Claim: No expense-system connector exists. The amount — the field every threshold in every expense policy turns on — is not projected into a typed fact anywhere in the stack.

### `asset_returned` · obs_kind

- blocks **Asset** / `ast.issued_and_never_returned` (would yield 9500 bp)
- blocks **Asset** / `ast.licence_seat_still_billing_after_return` (would yield 8200 bp)
- Asset: Returns live in a spreadsheet or a ticket, never as a typed event, so the closing half of the custody cycle cannot be seen and every overdue report over-reports.

### `leave.balance_remaining` · fact_path

- blocks **Leave Request** / `lvr.carry_over_about_to_lapse` (would yield 8500 bp)
- blocks **Leave Request** / `lvr.entitlement_would_go_negative` (would yield 9500 bp)
- Leave Request: A deadline with a financial consequence and no owner. Nobody is accountable for an employee losing days, so nothing warns them — and the December scramble that follows is a coverage problem the organisation created for itself.

### `leave.end_at` · fact_path

- blocks **Leave Request** / `lvr.entitlement_would_go_negative` (would yield 9500 bp)
- blocks **Leave Request** / `lvr.return_to_work_outstanding` (would yield 8500 bp)
- Leave Request: Start and end are also what turn lvr.commitment_falls_in_window from a candidate into a finding.

### `leave.start_at` · fact_path

- blocks **Leave Request** / `lvr.coverage_gap_in_team` (would yield 8000 bp)
- blocks **Leave Request** / `lvr.entitlement_would_go_negative` (would yield 9500 bp)

### `request.priority` · fact_path

- blocks **Escalation** / `esc.request_ageing_against_service_level` (would yield 8000 bp)
- blocks **Request** / `req.state_from_the_service_desk` (would yield 9500 bp)

### `retention_review_due` · obs_kind

- blocks **Document** / `doc.retention_period_elapsed` (would yield 9500 bp)
- blocks **Event** / `evt.attendee_data_past_retention` (would yield 8500 bp)
- Document: The scheduled prompt. Without it, disposal happens when somebody runs out of storage, which selects for size rather than for schedule.
- Event: Dietary and accessibility requirements are special-category data collected on an open form and emailed to a caterer. The list survives in a shared drive indefinitely, and it is a retention breach with no incident to make it visible.

### `trip.booked_at` · fact_path

- blocks **Trip** / `trp.approval_after_booking` (would yield 9500 bp)
- blocks **Trip** / `trp.late_booking_cost_penalty` (would yield 9000 bp)

### `trip.depart_at` · fact_path

- blocks **Trip** / `trp.documentation_not_ready` (would yield 9500 bp)
- blocks **Trip** / `trp.late_booking_cost_penalty` (would yield 9000 bp)
- Trip: Together these give lead_time_days, the single most actionable number on the object. Cost is dominated by it, and it is mostly a function of approval throughput — which makes travel overspend an administrative problem the administrative function can actually fix.
- Trip: Documentation queue times are measured in weeks and sit entirely outside the organisation's control. This is what actually cancels trips, and it is resolved after the flights are booked rather than before.

### `access.reviewed_at` · fact_path

- blocks **Access Right** / `acr.review_overdue` (would yield 9000 bp)
- blocks **Policy** / `pol.control_claimed_but_never_tested` (would yield 8000 bp)
- Policy: For access policies the review date on the entitlement is the control test date, and it already exists in every IAM platform.

### `agenda_circulated` · obs_kind

- blocks **Action Item** / `ai.carried_across_consecutive_sittings` (would yield 8800 bp)
- blocks **Meeting** / `mtg.papers_missed_their_deadline` (would yield 9000 bp)
- Action Item: An item reappearing on successive agendas is the observable form of carry-over, and agendas are easier to parse than minutes.

### `approver.unavailable_until` · fact_path

- blocks **Approval** / `apv.stuck_because_the_approver_is_absent` (would yield 8800 bp)
- blocks **Approver** / `apr.out_of_office_with_no_delegate` (would yield 9000 bp)
- Approval: The calendar connector reads timed meetings and discards all-day absence events, so the system knows the approver is not in a meeting and not that they are in Lisbon for a fortnight. Cheapest fix in the whole backlog and it removes the most common cause of a stuck approval.
- Approver: The calendar connector reads timed meetings and discards all-day absence events, so the pipeline knows an approver is not in a meeting and cannot know they are away for a fortnight. Cheapest item in this backlog and it removes the most common cause of a stuck approval.

### `commitment.recipient` · fact_path

- blocks **Commitment** / `cmt.promise_to_a_departing_party` (would yield 7000 bp)
- blocks **Commitment** / `cmt.recipient_is_named` (would yield 9000 bp)
- Commitment: Without the recipient the negotiability of the date is unknowable, so every overdue item gets an identical treatment. A slip owed to the audit committee and a slip owed to a colleague are not the same row and must not produce the same message.

### `card.transaction_at` · fact_path

- blocks **Expense Claim** / `exp.card_transaction_never_claimed` (would yield 8800 bp)
- blocks **Expense Claim** / `exp.unsubmitted_at_period_end` (would yield 8200 bp)
- Expense Claim: Requires a card feed. This inverts every control in the object — the money is already gone and the missing artefact is the EXPLANATION, not the payment. Unreconciled card spend is the largest silent exposure in expense administration and nothing here can see a single transaction.
- Expense Claim: The draft state — money spent, claim not raised — is invisible to every dashboard because nothing has been created yet to count. It is also the single largest source of surprise at period end, and it is entirely predictable.

### `meeting.series_id` · fact_path

- blocks **Action Item** / `ai.carried_across_consecutive_sittings` (would yield 8800 bp)
- blocks **Action Item** / `ai.forum_never_closes_anything` (would yield 8200 bp)
- Action Item: Recurring meetings arrive as unrelated calendar events, so a weekly committee is thirty separate meetings to the pipeline and carry-over cannot be computed at all. The single most diagnostic administrative number about a forum is therefore unavailable.

### `access_revoked` · obs_kind

- blocks **Access Right** / `acr.physical_pass_outlives_account` (would yield 8000 bp)
- blocks **Asset** / `ast.licence_seat_still_billing_after_return` (would yield 8200 bp)
- Asset: Hardware recovery closes a visible loop and licence reclamation closes an invisible one, so only the first gets done. The recurring cost lands on a cost centre nobody reads and compounds for years.

### `commitment_delivery_rate` · baseline

- blocks **Action Item** / `ai.forum_never_closes_anything` (would yield 8200 bp)
- blocks **Commitment** / `cmt.chronic_owner` (would yield 7500 bp)
- Action Item: Learned per forum rather than per person. Averaging closure across forums hides the one committee that has closed nothing in a year, and that committee is always the one whose items matter most.
- Commitment: A per-person learned baseline of promises kept by the first agreed date. Cheap once commitment.owner exists, and it converts the register from a list of dates into a forecast. Today every owner is modelled as equally reliable, which no administrator has ever believed.

### `contract.counterparty` · fact_path

- blocks **Contract** / `ct.spend_without_paper` (would yield 8000 bp)
- blocks **Vendor** / `vn.concentration_risk` (would yield 7500 bp)
- Vendor: Concentration is a join across contracts and spend by counterparty, rolled up to the group parent. Neither side is projected, so exposure is only ever seen one contract at a time — which is the same as not seeing it.

### `derived.budget_burn_rate` · derived

- blocks **Budget Line** / `bl.burn_ahead_of_phasing` (would yield 8000 bp)
- blocks **Budget Line** / `bl.material_underspend_late_in_period` (would yield 7000 bp)
- Budget Line: Must be phasing-adjusted or it is worse than nothing. An unadjusted burn alert fires every January on every seasonal line and trains its audience to ignore it within one cycle, after which the real alert also goes unread.
- Budget Line: Underspend is never investigated because nothing is on fire, and it is the earliest available evidence that a programme has quietly halted. The lowest-urgency, highest-insight pattern on this object.

### `expense.merchant` · fact_path

- blocks **Expense Claim** / `exp.duplicate_across_payment_methods` (would yield 8000 bp)
- blocks **Expense Claim** / `exp.special_category_merchant_in_the_approval_route` (would yield 7500 bp)

### `admin_request_volume` · baseline

- blocks **Request** / `req.repeat_ask_means_a_broken_answer` (would yield 7500 bp)
- blocks **Standard Operating Procedure** / `sop.cycle_time_diverged_from_the_written_duration` (would yield 7500 bp)
- Standard Operating Procedure: Divergence in either direction is a signal. Slower means steps have been added that the document does not carry; faster almost always means steps are being skipped, and the skipped ones are the controls. The second case is the dangerous one and it looks like a productivity improvement on every dashboard.

### `prebrief_delivered` · obs_kind

- blocks **Action Item** / `ai.chair_asked_for_it` (would yield 7500 bp)
- blocks **Meeting** / `mtg.prebrief_never_delivered` (would yield 7000 bp)
- Action Item: Chair sponsorship is visible in a transcript and in the pre-brief and nowhere in structured data. It is the strongest single predictor of a minuted action being done and it is entirely invisible to every action tracker ever built.
- Meeting: Executive support's core deliverable and it leaves no typed trace — a brief is an attachment or a five-minute corridor conversation. Without it the function's most valuable output is also its least measurable, which is a familiar and expensive combination.


### `asset_in_custody` · l2_situation_type

- blocks **[situation] Asset in Custody** / `admin.sit.asset_in_custody` (would yield 10000 bp)
- Asset in Custody: WHAT THE TYPE MUST MEAN. A specific identified asset with a current holder, a custody start date, a condition state and a next-due date. Identity must survive transfer — the same laptop moving between three people is one asset with three custody spells, and a type that mints a new asset per mention makes recovery impossible, which is the single thing asset_issuance_and_recovery exists to do.
WHAT WOULD EMIT IT. `asset.id`, `asset.holder`, `asset.custody_from`, `asset.condition` and `asset.next_due_at`, from an asset register, an MDM or a facilities system. No writer exists and none should be extracted: an asset mentioned in an email is not an asset in custody, and treating it as one produces a register that is confidently wrong.
WHAT GOES WRONG TODAY. Nothing fires for asset_register, asset_issuance_and_recovery, maintenance_coordination, workplace_management or health_and_safety_administration.
WHY BINDING TO admin_contact WOULD BE WRONG, specifically. (1) No identity. The same asset named in two threads would be two assets, inverting recovery. (2) No custody transfer — correspondence records that something was sent, not that responsibility moved, and those differ exactly when someone leaves. (3) Health and safety carries statutory inspection dates; there is no such date in a mailbox, so the capability with legal exposure would be the one advising from the thinnest evidence. (4) Compound: a register assembled from correspondence looks like a register and is not one, and the difference surfaces during an insurance claim.

- Asset in Custody: closest type emitted today is `admin_contact` — close enough to be tempting, not close enough to be true

### `document_published` · obs_kind

- blocks **Document** / `doc.approval_recorded_in_the_register` (would yield 10000 bp)
- Document: Publication is a distinct event from approval and is currently unobservable. The gap between the two is where approved policies live unread for a quarter.

### `employee_lifecycle_event` · l2_situation_type

- blocks **[situation] Employee Lifecycle Event** / `admin.sit.employee_lifecycle_event` (would yield 10000 bp)
- Employee Lifecycle Event: WHAT THE TYPE MUST MEAN. A person's employment state changing on a date, carrying the direction (join, change, leave), the effective date, and the set of administrative steps that state change requires — with each step's owner and completion state. Direction and date are not optional: the same checklist run backwards is offboarding, and a type that cannot tell them apart would advise granting access to someone who has left.
WHAT WOULD EMIT IT. `employment.status`, `employment.effective_at`, `employment.direction` and per-step completion facts, from an HRIS or an identity provider. None has a writer and none should be extracted: employment status inferred from correspondence is a guess about a person's job, and being wrong about that is a category of wrong this system should not risk.
WHAT GOES WRONG TODAY. Nothing fires for any of the six capabilities — onboarding_administration, offboarding_administration, access_and_identity_administration, employee_records_administration, attendance_and_leave, payroll_input_administration.
WHY BINDING TO admin_contact WOULD BE WRONG, specifically. (1) Inference about a person's employment from their mail is a guess with consequences — an offboarding checklist raised against someone who has not left is both wrong and insulting. (2) The steps are invisible in correspondence. Access revocation happens in an identity provider, not in an email, so the capability that matters most would be blind precisely where it matters. (3) Employment data carries its own access constraints; putting it in a graph built for commercial correspondence, with commercial visibility rules, is a privacy design decision that no situation file should make by implication. (4) Compound: an offboarding surface that cannot see revocation would report the risk as handled.

- Employee Lifecycle Event: closest type emitted today is `admin_contact` — close enough to be tempting, not close enough to be true

### `filing.reference_number` · fact_path

- blocks **Filing** / `fil.acknowledgement_received` (would yield 10000 bp)

### `obligation_falls_due` · l2_situation_type

- blocks **[situation] Obligation Falls Due** / `admin.sit.obligation_falls_due` (would yield 10000 bp)
- Obligation Falls Due: WHAT THE TYPE MUST MEAN. A named external obligation — a filing, a licence renewal, a board resolution, a data-protection deadline — with its statutory date, the authority that set it, its owner, and the evidence artefact that will prove it was met. It must carry whether the date is fixed or rolling, because a rolling one recurs and a system that forgets that is useful once.
WHAT WOULD EMIT IT. `obligation.authority`, `obligation.due_at`, `obligation.owner`, `obligation.evidence_ref` and `obligation.recurrence`. None has a writer. The source is a compliance register or a filing calendar — a connector — not an inbox: an obligation exists whether or not anybody emailed about it, and an obligation nobody emailed about is precisely the one that gets missed.
WHAT GOES WRONG TODAY. Nothing fires. All six capabilities — statutory_filing, licence_and_registration, policy_administration, board_and_secretarial, audit_support, data_protection_administration — are authored against a trigger that does not exist.
WHY BINDING TO commitment.due_at WOULD BE WRONG, specifically. (1) Category error. A commitment is a promise a person made and can renegotiate; an obligation is imposed and cannot. Advice that treats a filing deadline as reschedulable is advice to breach. (2) Coverage inverted. The obligations that get missed are the ones nobody discussed, so binding to correspondence would cover exactly the obligations that were already visible and miss exactly the ones that were not. (3) No evidence chain. `commitment` carries no artefact reference, so `audit_support` — whose entire job is producing the proof — would have nothing to point at. (4) Compound: the system would show a compliance surface built from a founder's promises. In an audit that is not a gap, it is a misrepresentation.

- Obligation Falls Due: closest type emitted today is `commitment.due_at` — close enough to be tempting, not close enough to be true

### `spend_against_a_commitment` · l2_situation_type

- blocks **[situation] Spend Against a Commitment** / `admin.sit.spend_against_a_commitment` (would yield 10000 bp)
- Spend Against a Commitment: WHAT THE TYPE MUST MEAN. A committed amount or entitlement, the limit it is committed against, the amount consumed so far, and the state of the paperwork that authorises it. Both sides are required — a commitment with no limit is just a payment, and a limit with no commitments is just a number. The comparison IS the situation.
WHAT WOULD EMIT IT. `purchase_order.id`, `purchase_order.matched_state`, `budget_line.limit`, `budget_line.consumed`, `expense.state` and `authorisation.reference`, from a finance system, an expense tool or a travel desk. No writer exists and none is an inbox: the authoritative record of a purchase order is in the system that raised it, and the email about it is a copy at best.
WHAT GOES WRONG TODAY. Nothing fires for budget_tracking, purchase_order_management, travel_expense_administration or visa_and_documentation.
WHY BINDING TO commitment.due_at WOULD BE WRONG, specifically. (1) A `commitment` is a promise a person made in a message; it carries no amount and no limit, so the comparison that defines this situation cannot be made. (2) It would fire on every dated promise — `admin.sit.money_owed_either_way` already reads those correctly, and a second door onto the same fact would spend the signal budget twice to say less. (3) Three-way match — order, receipt, invoice — is the core of purchase_order_management and needs three records the substrate has one of. (4) A visa application has a lodgement date and a decision date set by a consulate, which is an external clock of the same kind as a statutory obligation and must not be modelled as something we promised.

- Spend Against a Commitment: closest type emitted today is `commitment.due_at` — close enough to be tempting, not close enough to be true

### `vendor.bank_account_fingerprint` · fact_path

- blocks **Vendor** / `vn.bank_details_changed` (would yield 9900 bp)
- Vendor: No connector reads the vendor master or the payments ledger, so the single highest-risk event in the administrative function produces no signal at all. Today the pipeline can see the payment leave and not the destination change — which is the wrong half.

### `approver.effective_to` · fact_path

- blocks **Approver** / `apr.authority_expiry_recorded` (would yield 9800 bp)
- Approver: DOA matrices are re-issued annually with partial adoption, so at any moment part of the organisation approves under a superseded version. No system holds the version, so no system can tell that a decision made yesterday is void.

### `contract_countersigned` · obs_kind

- blocks **Contract** / `ct.executed_copy_exists` (would yield 9800 bp)
- Contract: L2 emits contract_requested and never contract_countersigned. The exact moment obligations attach to us — the one event that changes our legal position — is unobserved, so the register learns of it whenever somebody remembers to update it. Cheapest high-value line in this object's backlog.

### `escalation_requested` · obs_kind

- blocks **Escalation** / `esc.explicitly_asked_for` (would yield 9800 bp)
- Escalation: The strongest possible grounds and the pipeline drops it. When a requester asks to escalate, the object exists at near certainty and no inference is required.

### `event.capacity` · fact_path

- blocks **Event** / `evt.capacity_exceeded` (would yield 9800 bp)

### `leave.state` · fact_path

- blocks **Leave Request** / `lvr.statutory_category_refused` (would yield 9800 bp)

### `minutes_adopted` · obs_kind

- blocks **Meeting** / `mtg.minute_adopted_at_the_next_sitting` (would yield 9800 bp)

### `request.category` · fact_path

- blocks **Request** / `req.intake_form_classification` (would yield 9800 bp)
- Request: No service-desk or form connector exists. Category is the cheapest field in the whole domain — the requester types it — and it does not reach Layer 2, so every request arrives unclassified and is triaged by whoever opens the inbox first.


### `screening_result_returned` · obs_kind

- blocks **Vendor** / `vn.screening_hit` (would yield 9800 bp)
- Vendor: Screening runs inside a third-party tool whose result never leaves it, so a hit is actioned only if a human happens to open the report. A blocking control that depends on somebody reading an attachment is not a blocking control.

### `employee.right_to_work_expires_at` · fact_path

- blocks **Employee Record** / `emp.right_to_work_expiring` (would yield 9700 bp)
- Employee Record: A statutorydeadline, known years in advance, held in a scanned document and tracked by whoever last thought about it. The most avoidable compliance failure in people administration.

### `auto_renewal_imminent` · obs_kind

- blocks **Deadline** / `dl.auto_renewal_already_locked` (would yield 9600 bp)

### `expense.receipt_present` · fact_path

- blocks **Expense Claim** / `exp.receipt_missing_above_threshold` (would yield 9600 bp)
- Expense Claim: Receipt presence is trivially available in every expense tool ever built and reachable by nothing here.

### `asset.due_back_at` · fact_path

- blocks **Asset** / `ast.issued_and_never_returned` (would yield 9500 bp)
- Asset: No connector projects an expected return date. Until one does, an item can be issued indefinitely and never become overdue — the register is structurally incapable of reporting the failure it exists to prevent.

### `calendar.event.previous_start_at` · fact_path

- blocks **Time Block** / `tb.displacement_recorded` (would yield 9500 bp)
- Time Block: The connectoroverwrites the event on update rather than retaining the prior start. The single most valuable administrative fact in a calendar — what moved, and for what — is destroyed by the sync that ingests it.

### `contract.cancellation_schedule` · fact_path

- blocks **Event** / `evt.cancellation_ladder_step_imminent` (would yield 9500 bp)
- Event: Cancellation cost rises in steps written into the contract. A decision made the day before a step is materially cheaper than the same decision the day after, and nothing currently tells anybody a step is coming.

### `derived.entitlement_set_by_identity` · derived

- blocks **Access Right** / `acr.segregation_of_duties_breach` (would yield 9500 bp)
- Access Right: The conflict is a property of the SET, never of a member. No per-entitlement review can find it, which is why every organisation that reviews access quarterly still fails an SoD test.

### `document_review_overdue` · obs_kind

- blocks **Document** / `doc.review_due_date_passed` (would yield 9500 bp)
- Document: The prompt that makes the date operational. A due date nothing watches is a preference.

### `event.final_numbers_due_at` · fact_path

- blocks **Event** / `evt.final_numbers_deadline_approaching` (would yield 9500 bp)
- Event: The single highest-value signal this object generates. It is the moment the bill stops being an estimate, it sits a few working days before the event, and it is treated as an administrative formality by everybody except the venue.

### `event.start_at` · fact_path

- blocks **Event** / `evt.cancellation_ladder_step_imminent` (would yield 9500 bp)

### `invoice.due_at` · fact_path

- blocks **Invoice** / `inv.overdue_against_contractual_terms` (would yield 9500 bp)
- Invoice: commitment.due_at is the nearest live equivalent, and binding invoice ageing to it would report every unrelated promise on the thread as a late payment. That is precisely the stretch this library exists to refuse.

### `meeting.quorum_required` · fact_path

- blocks **Meeting** / `mtg.attendance_and_quorum` (would yield 9500 bp)
- Meeting: Quorum lives in terms of reference, which are a document nobody has parsed. Until it is a number, no system can tell a valid board meeting from an invalid one, and neither can the room.


### `notifiable_event_detected` · obs_kind

- blocks **Compliance Obligation** / `obl.notification_clock_running` (would yield 9500 bp)
- Compliance Obligation: Invented; planned_substrate has nothing for it. The 72-hour GDPR Art. 33 clock starts on awareness, not on confirmation, and the single most common way it is missed is an organisation waiting for the facts to settle. Nothing anywhere in the stack starts a clock on awareness today.

### `payroll.cutoff_at` · fact_path

- blocks **Deadline** / `dl.payroll_cutoff` (would yield 9500 bp)
- Deadline: Internally set and functionally external: a clearing window sits behind it. The clean proof that the discriminator is who can MOVE the date, not who set it. Also the one administrative deadline where being a day late is visible to every employee simultaneously.

### `request.acknowledged_at` · fact_path

- blocks **Request** / `req.acknowledgement_recorded` (would yield 9500 bp)
- Request: The single number that governs requester experience, and there is no field for it. Acknowledgement is currently inferred from an observation that cannot tell an acknowledgement from any other outbound message.


### `sod.conflict_pairs` · fact_path

- blocks **Access Right** / `acr.segregation_of_duties_breach` (would yield 9500 bp)
- Access Right: The toxic-combination matrix. Usually exists as a spreadsheet held by internal audit and is never connected to anything.

### `trip.visa_state` · fact_path

- blocks **Trip** / `trp.documentation_not_ready` (would yield 9500 bp)

### `vendor.bank_verification_method` · fact_path

- blocks **Vendor** / `vn.verified_by_the_wrong_channel` (would yield 9500 bp)
- Vendor: The most dangerous configuration in the function is a change marked verified where the verification ran through the compromised mailbox. Without this field, verified and verified-by-email are the same value in every report.

### `vendor.diligence_expires_at` · fact_path

- blocks **Vendor** / `vn.diligence_expired` (would yield 9500 bp)
- Vendor: Most vendor masters hold the completion date and never the expiry, which converts a control into a record of a control. Cheapest structural fix on this object.

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

### `filing_due` · obs_kind

- blocks **Deadline** / `dl.filing_window_signalled` (would yield 9200 bp)

### `filing_overdue` · obs_kind

- blocks **Deadline** / `dl.filing_window_signalled` (would yield 9200 bp)
- Deadline: Portal notifications and regulator correspondence already arrive by email; they are simply not extracted. This is among the cheapest signals in the whole Admin backlog.

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

### `derived.approver_availability` · derived

- blocks **Leave Request** / `lvr.approver_absent_no_delegate` (would yield 9000 bp)
- Leave Request: The highest-value false-positive suppressor across the whole Admin brain. It stops the system chasing, escalating and eventually alarming about people who are demonstrably not there — and it is shared with approval, escalation and commitment.

### `derived.document_cluster_key` · derived

- blocks **Document** / `doc.version_conflict_in_circulation` (would yield 9000 bp)
- Document: SATISFIED 2026-08-29 by context/document_register.py. NAMED FOR WHAT WAS BUILT: this entry used to read derived.document_identity_cluster, a path nothing writes and nothing ever will, so the prose said satisfied while the machine-readable half sent a reader (and signal-backlog.md) after an identifier that appears nowhere in the engine. The key is the title reduced past its decoration (v2, _FINAL, Copy of, (1), dates) and compared by EXACT equality — deliberately not fuzzy, because a false merge hides a second document behind the first.

### `derived.document_live_copies` · derived

- blocks **Document** / `doc.version_conflict_in_circulation` (would yield 9000 bp)
- Document: SATISFIED 2026-08-29 by context/document_register.py, and it is the second half of what the old derived.document_identity_cluster name was standing in for: how many members of the cluster were edited recently enough to still be live, with a content hash separating a fork from a mirrored copy. Together these two turn a filename into a conflict detector; neither of them, alone or together, says which copy is the right one.

### `derived.incident_window` · derived

- blocks **Access Right** / `acr.break_glass_never_withdrawn` (would yield 9000 bp)
- Access Right: Break-glass is granted under pressure, correctly, and withdrawn under no pressure at all — which is to say, not withdrawn. The withdrawal has no owner because the incident that justified it is closed.

### `derived.instrument_version_current` · derived

- blocks **Compliance Obligation** / `obl.instrument_amended_invalidates_our_reading` (would yield 9000 bp)
- Compliance Obligation: A regulatory-change feed compared against instrument_version. Commercially available and connected almost nowhere, so most registers are pinned to whatever the law said on the day the spreadsheet was built.

### `derived.performer_diversity` · derived

- blocks **Standard Operating Procedure** / `sop.performed_by_exactly_one_person` (would yield 9000 bp)
- Standard Operating Procedure: Distinct performers over executions in a window. Trivial arithmetic once executions are visible, impossible without them.

### `derived.recipient_is_external` · derived

- blocks **Document** / `doc.classification_exceeded_by_distribution` (would yield 9000 bp)
- Document: Domain comparison against the tenant's own domains. Cheap, and currently absent, which is why the single most preventable data-protection incident is also the least detectable one.

### `derived.threshold_position` · derived

- blocks **Compliance Obligation** / `obl.threshold_crossed_pulls_us_into_scope` (would yield 9000 bp)
- Compliance Obligation: Current value against each recorded threshold_test, with the crossing emitted as an event. The whole class of silent scope-change is invisible without it, and silent scope-change is how a compliant organisation becomes non-compliant with nobody doing anything wrong.

### `escalation_accepted` · obs_kind

- blocks **Escalation** / `esc.prior_escalation_accepted_and_nothing_moved` (would yield 9000 bp)
- Escalation: Acceptance without movement is worse than silence: it consumes the escalation, resets everyone's patience, and produces no decision. It should advance the ladder immediately rather than restart the clock.

### `event.contracted_minimum` · fact_path

- blocks **Event** / `evt.attrition_exposure_material` (would yield 9000 bp)

### `event.licences_required` · fact_path

- blocks **Event** / `evt.licences_not_confirmed` (would yield 9000 bp)

### `expense_claim_submitted` · obs_kind

- blocks **Trip** / `trp.unreconciled_past_claim_window` (would yield 9000 bp)
- Trip: Two opposite failures share this signal: the traveller is personally out of pocket, or the organisation has spent money it has not recorded. Which one it is depends on who paid, and nothing currently distinguishes them.

### `filing.penalty_basis` · fact_path

- blocks **Filing** / `fil.penalty_basis_known` (would yield 9000 bp)
- Filing: Attached to the form type,not to the instance, so it is a small reference dataset rather than a feed. Its absence is why every overdue filing currently looks equally urgent, which in practice means none of them do.

### `filing_submitted` · obs_kind

- blocks **Filing** / `fil.submission_detected` (would yield 9000 bp)
- Filing: Cheaper than filing_acceptedand much less useful on its own; worth emitting only alongside it, because knowing something was sent without knowing it landed creates false comfort rather than information.

### `leave.evidence_due_at` · fact_path

- blocks **Leave Request** / `lvr.evidence_overdue` (would yield 9000 bp)
- Leave Request: Drives pay treatment. Missing evidence past the window usually converts paid absence to unpaid, and doing that retrospectively is visible to the employee in the worst possible way.

### `leave_evidence_received` · obs_kind

- blocks **Leave Request** / `lvr.evidence_overdue` (would yield 9000 bp)

### `licence_evidenced` · obs_kind

- blocks **Event** / `evt.licences_not_confirmed` (would yield 9000 bp)
- Event: Usually the venue's responsibility and almost never confirmed to be. The assumption is discovered by an inspector, and the liability does not transfer just because the assumption was reasonable.

### `meeting.convened_at` · fact_path

- blocks **Meeting** / `mtg.convened_inside_the_notice_period` (would yield 9000 bp)

### `meeting.notice_period_days` · fact_path

- blocks **Meeting** / `mtg.convened_inside_the_notice_period` (would yield 9000 bp)
- Meeting: Notice is a validity condition, not a courtesy. A statutory meeting convened short of notice is not validly convened whatever happens in the room, and the defect is discovered by whoever later dislikes the decision.


### `meeting.papers_deadline_at` · fact_path

- blocks **Meeting** / `mtg.papers_missed_their_deadline` (would yield 9000 bp)
- Meeting: A real, dated, enforced administrative deadline that exists only in the secretary's head and a recurring reminder. Nothing else in the stack knows the pack was two days late, so the pattern of lateness never becomes evidence at the board — which is the one place it would change behaviour.


### `request.type` · fact_path

- blocks **Request** / `req.exception_worked_without_approval` (would yield 9000 bp)

### `retention_period_elapsed` · obs_kind

- blocks **Deadline** / `dl.retention_period_elapsed` (would yield 9000 bp)

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

### `trip.claim_due_at` · fact_path

- blocks **Trip** / `trp.unreconciled_past_claim_window` (would yield 9000 bp)

### `trip.itinerary_source` · fact_path

- blocks **Trip** / `trp.traveller_not_locatable` (would yield 9000 bp)
- Trip: Off-programme bookings never reach the tracking feed. The duty-of-care obligation is unaffected by how the ticket was bought, which is the whole problem.

### `trip_departed` · obs_kind

- blocks **Trip** / `trp.traveller_not_locatable` (would yield 9000 bp)

### `vendor.registration_number` · fact_path

- blocks **Vendor** / `vn.duplicate_vendor_record` (would yield 9000 bp)
- Vendor: Duplicates are how the same invoice is paid twice and how a rejected supplier reappears under a variant spelling. Detectable the moment the master is readable, and undetectable until then.

### `calendar.event.hold_expires_at` · fact_path

- blocks **Time Block** / `tb.hold_expired_unreleased` (would yield 8800 bp)
- Time Block: No system storesa hold expiry, because no system distinguishes a hold from a booking. Holds are released by an assistant remembering, which means they are not released.

### `derived.identity_owner_resolvable` · derived

- blocks **Access Right** / `acr.orphaned_service_account` (would yield 8800 bp)
- Access Right: Service accounts fail every control designed for people: no leaver event, no manager to attest, no mailbox to chase. They are the entitlements most likely to be both over-privileged and unowned.

### `renewal_window_open` · obs_kind

- blocks **Budget Line** / `bl.renewal_window_closing_unnoticed` (would yield 8800 bp)

### `vendor.onboarding_state` · fact_path

- blocks **Vendor** / `vn.paid_without_approval` (would yield 8800 bp)
- Vendor: The join that finds every supplier admitted by exception. Almost always a short list, and almost always a surprising one — it is where the urgent 2022 project supplier is still sitting.

### `derived.attestation_coverage` · derived

- blocks **Policy** / `pol.attestation_cycle_never_ran` (would yield 8500 bp)
- Policy: Coverage across a defined population over a window. Trivial arithmetic once acknowledgements and the joiner feed exist; impossible without both, which is why it is universally reported from the LMS's own completion figure instead — a number whose denominator is the people the LMS was told about.

### `derived.days_by_jurisdiction_12m` · derived

- blocks **Trip** / `trp.tax_presence_accumulating` (would yield 8500 bp)
- Trip: A property of the sequence of trips, never of one. Nobody owns the aggregate, so it is discovered by a tax authority rather than by the organisation.

### `derived.escalation_pressure` · derived

- blocks **Escalation** / `esc.repeat_stall_against_the_same_rung` (would yield 8500 bp)
- Escalation: Turns a sequence of incidents into a design finding. The output is not another escalation but a delegation change, and no organisation can see this today.

### `derived.grant_provenance_completeness` · derived

- blocks **Access Right** / `acr.no_recorded_reason` (would yield 8500 bp)
- Access Right: Cheap to compute once grants and approvals are joined, and it is the field that decides whether a recertification campaign can do anything at all.

### `derived.reporting_distance` · derived

- blocks **Approver** / `apr.four_eyes_partner_reports_to_holder` (would yield 8500 bp)
- Approver: Independence is a property of the org chart and it is currently checked against the approval form, which is why it always passes. The HRIS holds the reporting line and nothing joins it to the approver pair.

### `derived.vendor_first_seen` · derived

- blocks **Invoice** / `inv.unknown_payee_plausible_project` (would yield 8500 bp)
- Invoice: The classic redirection fraud. It survives because the project is real and the amount is plausible. Detecting it needs only the vendor master's first-seen date, which no connector supplies.

### `event.attendee_data_retention_until` · fact_path

- blocks **Event** / `evt.attendee_data_past_retention` (would yield 8500 bp)

### `event.end_at` · fact_path

- blocks **Event** / `evt.unreconciled_after_event` (would yield 8500 bp)

### `final_invoice_received` · obs_kind

- blocks **Event** / `evt.unreconciled_after_event` (would yield 8500 bp)
- Event: The final bill arrives weeks later and against a headcount fixed at the final-numbers deadline. Nobody who attended is still looking, so the reconciliation is the step most reliably skipped.

### `leave.carry_over_expires_at` · fact_path

- blocks **Leave Request** / `lvr.carry_over_about_to_lapse` (would yield 8500 bp)

### `meeting.attendees` · fact_path

- blocks **Action Item** / `ai.owner_was_not_in_the_room` (would yield 8500 bp)
- Action Item: Calendar is connected and meeting.start_at is projected, but the attendee roster is discarded at ingestion. This is the cheapest unbuilt signal in the Admin brain: the roster is already inside the payload and is thrown away.

### `meeting.interests_declared` · fact_path

- blocks **Meeting** / `mtg.conflicted_member_counted_towards_quorum` (would yield 8500 bp)

### `payment_released` · obs_kind

- blocks **Approval** / `apv.retrospective_collection` (would yield 8500 bp)
- Approval: Comparing the decision timestamp against the execution timestamp is a two-line rule that cannot be written because neither timestamp exists. The rate of retrospective approvals is the sharpest available diagnostic of which control is too slow to be complied with.

### `person.working_hours` · fact_path

- blocks **Time Block** / `tb.outside_working_hours` (would yield 8500 bp)
- Time Block: No working-hours or timezonemodel exists, so a 07:00 block in London and a 07:00 block in Singapore are indistinguishable to the pipeline even when the same person holds both.

### `policy.exception_count` · fact_path

- blocks **Policy** / `pol.exceptions_outnumber_compliance` (would yield 8500 bp)
- Policy: Exception registers live in spreadsheets and GRC tools no connector touches. This is the fastest read on whether a policy fits the organisation, and it cuts both ways: a policy that has never granted an exception is usually not being applied rather than perfectly drafted.

### `policy.exception_expiry_at` · fact_path

- blocks **Policy** / `pol.exceptions_outnumber_compliance` (would yield 8500 bp)
- Policy: Without an expiry, an exception is indistinguishable from a permanent private amendment granted by whoever was on duty.

### `return_to_work_recorded` · obs_kind

- blocks **Leave Request** / `lvr.return_to_work_outstanding` (would yield 8500 bp)
- Leave Request: The single most effective absence control there is, consistently skipped because it is a conversation rather than a form, and therefore leaves no artefact unless one is deliberately created.

### `sop_step_skipped` · obs_kind

- blocks **Standard Operating Procedure** / `sop.control_steps_skipped` (would yield 8500 bp)

### `trip.unused_credit_expires_at` · fact_path

- blocks **Trip** / `trp.unused_ticket_credit_expiring` (would yield 8500 bp)
- Trip: A real asset held by the airline, tracked by nobody, written off by default. Usually surfaced only when a travel management company volunteers the balance.

### `vendor.last_reviewed_at` · fact_path

- blocks **Vendor** / `vn.never_reviewed_since_onboarding` (would yield 8500 bp)
- Vendor: Absent this field the answer defaults to 'presumably fine', which is the answer the vendor master has been giving for years. The cheapest way to make third-party risk real is to make the ABSENCE of a review visible rather than the presence of one.

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
- Asset: Not in the planned list and it should be. Every register has an issue date; almost none has a last-verified date, which is why the first stock count in a decade always produces a double-digit variance and a governance paper.

### `calendar.free_capacity_minutes` · fact_path

- blocks **Time Block** / `tb.commitment_due_with_no_hour_reserved` (would yield 8000 bp)
- Time Block: Requires a working-hoursmodel plus an aggregation over the block set. commitment.due_at exists today and is genuinely administrative; what is missing is the other half — whether there is anywhere for the work to go.

### `derived.absence_occasions_12m` · derived

- blocks **Leave Request** / `lvr.absence_trigger_reached` (would yield 8000 bp)

### `derived.claim_fingerprint` · derived

- blocks **Expense Claim** / `exp.duplicate_across_payment_methods` (would yield 8000 bp)
- Expense Claim: Merchant, date and amount hashed per claimant. The overwhelming majority of genuine duplicates are this exact honest mistake, and catching them cheaply is worth more than any fraud model — and costs a fraction of one.

### `derived.concurrent_travel_to_destination` · derived

- blocks **Trip** / `trp.duplicate_travel_to_one_event` (would yield 8000 bp)
- Trip: Each approval is individually reasonable and the aggregate is a decision nobody made. Only a cross-request view can see it, and no approval workflow has one.

### `derived.contains_personal_data` · derived

- blocks **Document** / `doc.personal_data_without_retention_rule` (would yield 8000 bp)
- Document: Content classification for personal data. Available in every DLP product and in no signal here. Its absence means storage limitation under GDPR Art. 5(1)(e) cannot be reasoned about at all.

### `derived.control_enforcement_rate` · derived

- blocks **Policy** / `pol.enforced_only_by_self_declaration` (would yield 8000 bp)
- Policy: Needs policy-to-control mapping plus control test outcomes. Nothing in Layer 1 reaches the systems that would prove enforcement — the IAM platform, the expense tool, the procurement gate — so the difference between a policy that stops behaviour and one that merely describes it is currently unknowable, and every policy therefore reads as equally strong.

### `derived.preparation_lead_time` · derived

- blocks **Deadline** / `dl.lead_time_from_actuals` (would yield 8000 bp)
- Deadline: Measured from first activity to submission across the last three occurrences. Without it, lead time is an estimate, estimates are optimistic, and every deadline looks safe until the week it is not.

### `derived.request_similarity` · derived

- blocks **Request** / `req.duplicate_of_an_open_request` (would yield 8000 bp)
- Request: Multi-channel intake guarantees duplicates — the same person asks by email on Monday and in person on Tuesday because the first went unacknowledged. Nothing dedupes them, so demand is over-reported and the requester receives two different answers, one of which is wrong.


### `derived.supplier_role_count_per_event` · derived

- blocks **Event** / `evt.single_supplier_concentration` (would yield 8000 bp)
- Event: Convenient at booking and a single point of failure on the day. On an immovable date, concentration is a decision to accept a specific failure mode rather than a risk to monitor.

### `derived.team_absence_overlap` · derived

- blocks **Leave Request** / `lvr.coverage_gap_in_team` (would yield 8000 bp)
- Leave Request: Coverage is the ground most refusals actually rest on and the one nobody can evidence, which makes every refusal an argument rather than a calculation.

### `sla_breach` · obs_kind

- blocks **Vendor** / `vn.service_level_failing` (would yield 8000 bp)
- Vendor: Planned in the support block but ticket-scoped rather than vendor-scoped. A breach BY our supplier and a breach BY US to a customer are opposite facts and would land in the same bucket unless the direction is carried on the observation.

### `sop_execution_observed` · obs_kind

- blocks **Standard Operating Procedure** / `sop.never_verified_against_practice` (would yield 8000 bp)
- Standard Operating Procedure: A gemba walk leaves no digital trace today. Even a calendar entry titled 'process walkthrough' with the performer as attendee would be a usable proxy, and nothing currently reads it.

### `vendor.service_level_target` · fact_path

- blocks **Vendor** / `vn.service_level_failing` (would yield 8000 bp)

### `asset.last_seen_at` · fact_path

- blocks **Asset** / `ast.device_stopped_checking_in` (would yield 7500 bp)
- Asset: MDM and endpoint management already hold this and expose it over API. It is the cheapest custody verification available to any organisation and no admin system consumes it — the security team watches it for compromise and nobody watches it for custody.

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
- Meeting: Decisions per meeting across a series. Needs a decision_recorded observation extracted from the minute, which means reading the attachment rather than the thread. The cheapest recurring saving in the whole domain and entirely unprovable today.


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
- Policy: Requires policy-aware detection over the systems where breaches actually show up — expense claims, access grants, procurement outside the gate. The unescalated breach is more diagnostic than the breach itself: it is the precise point at which the policy stopped being a rule and became advice, and everyone who saw it now knows.

### `contract.price_uplift_index` · fact_path

- blocks **Contract** / `ct.price_uplift_applied_without_a_decision` (would yield 7000 bp)
- Contract: New backlog line. Indexed uplift is the most common form of value leakage in a managed estate precisely because it arrives as a slightly larger invoice and is approved by being paid.

### `derived.meeting_attendance_rate` · derived

- blocks **Meeting** / `mtg.chronic_apologies_are_a_vacancy` (would yield 7000 bp)
- Meeting: Per-member attendance across a series. A committee whose quorum depends on someone who has not come since March is one apology away from being unable to decide anything, and the first person to notice is usually the auditor.


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

- blocks **Budget Line** / `bl.year_end_buying_season` (would yield 6500 bp)
- Budget Line: Entirely predictable and almost never modelled. It is a rational response to use-it-or-lose-it, so the useful output is a rule change rather than a challenge to each individual buyer — who is doing precisely what the rule rewards.

### `derived.pool_loan_duration` · derived

- blocks **Asset** / `ast.pool_item_held_beyond_the_pool_window` (would yield 6500 bp)
- Asset: A learned per-category baseline, exactly like reply_cadence. Pool assets have no formal due date, so the only workable definition of overdue is statistical: far longer than this category is normally out for.

