# Layer 2 — Improvements, Acceptance and Metrics

## Outcome and order of work

Do not replace the tested graph machinery. Keep versioned facts, discrepancy healing, exact-key identity, conservative correlation, projections, lifecycle and confidence vector. Fix the **semantic boundary** first: make relationship/request/opportunity—not a person node—the unit of decision context; make incompleteness and policy blocking; then prove the same object is consumed by live expertise/cards. More LLM calls or more corpus rules cannot repair a wrong business subject.

Every Improvement below is a **[PROPOSAL]**, not current capability. Baseline evidence is `harsh/mvp@b739bd5`; the 214 focused Layer 2 tests establish Tested primitives only. Acceptance requires deterministic fixtures plus named Live shadow traces before authority.

## Prioritized improvement register

| Priority | Improvement | Current root cause | Required change | Acceptance replay | Metric | Exit gate |
|---|---|---|---|---|---|---|
| P0.1 | Situation-scoped role graph | BSO emits one anchor; person fields blur requester, connector, owner and target | Add typed relationship/opportunity/thread/request nodes or scoped keys; require `requester`, `business_subject`, `target`, `owner/approver` where applicable | Boardy one connector + three introductions yields three target-specific situations | Wrong-target rate; missing-role rate; cross-role leakage | **0 connector-as-target and 0 cross-role leakage** on HKS; ambiguity abstains 100% |
| P0.2 | Exact qualified membership | BSO reconstructs members and invents synthetic signal/evidence fallback | Persist membership at qualification/correlation; require source receipt, transformation and membership reason | Memberless situation remains observation-only until a real source joins | Synthetic-authority count; orphan BSO rate | **0 prescriptive BSO with synthetic/reconstructed-only evidence** |
| P0.3 | Visibility and permitted-use lattice | `Visibility(scope="org")` is hardcoded at BSO/slice | Carry source ACL, purpose, exclusions; reduce with narrowest/intersection; forbid widening | Private support message correlates with churn but never enters Sales context | Visibility-widening incidents; policy-block precision/recall | **0 widening**, 100% `never_commercial` enforcement in labelled corpus |
| P0.4 | Explicit completeness/readiness | `missing_fields=()` and unknown domain can show 100% coverage | Add `requirements_status`, required role/state fields, source-window readiness and conflict codes; unknown spec ≠ complete | Unknown fundraising variant plus stale Gmail returns `coverage_unknown` and `source_incomplete` | False-complete rate; missing-code accuracy | **0 actionable output when required context/requirements are unknown** |
| P0.5 | Current-state reducer and completion matcher | Proposal, calendar and cross-channel outcome may not resolve same request | Model request/commitment/action identity; reduce ordered events with authority and scoped completion evidence | Proposed→rescheduled→completed; two parallel asks with one Slack answer | Stale-loop rate; wrong-close rate; resolution latency | 100% golden state transitions; **0 unrelated closes** |
| P0.6 | Version-fenced derived context | Fact correction can precede failed situation refresh; consumers may read mixed versions | Stamp correlation/situation/BSO/slice; publish only a complete graph-version generation; quarantine stale outputs | Identity correction with injected refresh failure | Mixed-version reads; stale-authority duration | 0 mixed-version authoritative reads; recovery is idempotent |
| P0.7 | Blocking BSO validator | Typed shape can be valid while roles, policy or evidence are semantically absent | Validator issues deterministic `ready_for_expertise`, `review_source`, `split_required`, `suppressed_policy`, `observation_only` | Remove target, member or policy from otherwise valid BSO | Unsafe-pass rate; abstention precision/recall | 0 unsafe passes in mutation suite; reason code always present |
| P1.1 | Retire person-global operational state | `thread.ball_in_court` and legacy commitments latest-write on person | Migrate reads to scoped thread/request/commitment IDs; retain legacy data as non-authoritative migration evidence | Same person, opposite ball-in-court on two threads | Person-state read count; contamination rate | Authoritative path performs 0 person-global operational reads |
| P1.2 | Bounded context selector | Neighbor/node-wide facts can flood cards/models | Select by membership, role, relationship, time, purpose and capability; enforce evidence/token budget; record exclusions | Boardy high-degree connector and long email thread | Relevant-context precision/recall; slice size p95; exclusion reasons | ≥ agreed labelled precision/recall; no decisive-tail truncation in HKS |
| P1.3 | Identity ambiguity sets | First claimant of same-name alias can receive later name-only mention | Return candidates/ambiguity; require anchored discriminator or reviewed merge; replay dependencies after decision | Two Alex Kim identities + unanchored quote | Silent misattachment rate; merge-review burden | 0 silent same-name attachment; reviewed merge fully replays dependents |
| P1.4 | Opportunity/multi-domain separation | Same-company deals can collapse; first domain hint wins | Introduce deal/opportunity anchors; preserve candidate domains and policy-safe multi-view membership | Two opportunities at one company; mixed Support + Sales evidence | Chimera rate; domain-view disagreement | 0 cross-deal field bleed; restricted domain never leaks into commercial view |
| P1.5 | Source readiness binding | Coverage/confidence ignores partial provider windows | Attach connector cursor health, last complete interval and missing window to every affected situation | Mid-page failure, revoked calendar, restored sync | Incomplete-window visibility; false-silence rate; recovery lag | 0 silence/negative inference during incomplete window; lossless recovery |
| P1.6 | LLM extraction contract/cost repair | Cache omits model/schema; 8k cap is silent; retry/token accounting is layered | Cache on model/prompt/schema/masking versions; semantic thread selector; per-attempt ledger; central retry budget | Long decisive-tail thread, model swap and repeated 429 | High-value extraction recall; repair rate; physical calls/event; ledger variance | Zero stale-model cache; full retry accounting; spend/latency SLO green |
| P1.7 | Runtime lineage trace | Tests do not prove which BSO/card path is Live | Record event IDs→facts→correlation→situation→BSO/slice→expertise/decision/card hashes and flags | Reproduce one supplied bad-card pattern with trace | Trace completeness; unexplainable-card rate | 100% sampled cards have replayable lineage; cause is falsifiable |
| P2.1 | Human review and correction workflow | Merge, split, target and completion ambiguity need governed resolution | Review queue with evidence, proposed effect, approval, replay status and audit receipt | Split chimeric situation; correct connector target; revoke fact | Review time; recurrence; downstream retraction completeness | Every accepted correction retracts/rebuilds all dependent outputs |
| P2.2 | Outcome and value proof | Context quality metrics alone do not show business value | Link recommendation/action/completion/outcome/counterfactual while keeping L2 limited to current reality | Theresa update advances relationship versus baseline | Correction burden; would-have-missed advances; attributed outcome | Design-partner trace shows lower correction and verified decision improvement |

## Acceptance replay suite

| Replay | Input mutation / setup | Required Layer 2 result | Prohibited result | Acceptance evidence |
|---|---|---|---|---|
| Theresa reconsideration | Old rejection, later “send updates/reconsider,” three sends, no reply, optional material milestone | Investor/partner relationship, invitation as current authority, sent cadence, silence unknown, no fabricated stage/deadline | Rejection-only, “last chance,” generic overdue reply | Stable BSO hash; exact evidence spans; missing/readiness codes; downstream action only after expertise |
| Boardy multi-intro | Connector plus three counterparties in separate/forwarded threads | Connector role + three separate subjects/asks | One Boardy person dump or connector target | Three correlation memberships, zero shared commitment facts, target precision 100% |
| Multi-role person | Same human in investor and customer threads | Two relationship-scoped states and visibility sets | Latest person-wide ball-in-court applied to both | Independent request IDs and lifecycle transitions |
| Parallel deals | One company, two opportunities, overlapping dates | Two situations or explicit split-required | One stage/owner/objection chimera | No cross-deal facts in bounded slices |
| Meeting lifecycle | Proposed, rescheduled, cancelled/completed/no-show variants | One authoritative current state with history and occurrence certainty | “Confirm meeting” after completion/cancellation; “met” from past schedule alone | State-transition table and source authority receipt |
| Cross-channel completion | Two asks; one resolved in chat | Only matching request resolves | Person-wide close or both remain overdue | Matching precision/recall and wrong-close rate zero |
| Internal group session | Many internal attendees, no external promise | Observation; no recap obligation | Generic recap card | External-role/commitment precondition fails with reason |
| Restricted support | Private support text correlates with Sales account | Restricted support view only; commercial BSO suppressed/redacted | Org-wide or subject-visible commercial use | Policy trace proves narrowest scope and excluded subject |
| Same-name identity | Two anchored people share display name; prose says only name | Ambiguous mention/merge review | First claimant silently selected | Candidate receipt; no graph attachment until anchored/reviewed |
| Source outage | Partial Gmail page and stale calendar | Affected situations mark incomplete windows; no silence inference | Fresh/complete status or deadline based on missing interval | Cursor/recovery trace; zero lost events after retry |
| Unknown domain | Unregistered domain with sparse facts | `requirements_unknown`, observation-only | 100% complete actionable context | Validator blocks authority, retains evidence |
| Correction/revocation | Human changes identity and source permission; derived refresh fails once | Old BSO loses authority; version-fenced recovery rebuilds/retracts | Old card continues or privacy remains widened | Atomic visible graph version and dependency retraction receipt |
| Long/multilingual thread | Decisive request after 8k chars; Hinglish relative time | Selected decisive span, ambiguity preserved, no invented deadline | Silent truncation/full coverage | Full-text labelled recall and missing/truncation marker |

## Metric dictionary

| Metric | Definition | Slice / guardrail | Initial exit threshold |
|---|---|---|---|
| Business-subject precision | Correct subject situations / reviewed actionable situations | By connector, role, source, language | 100% HKS; pilot target ratified from labelled baseline |
| Cross-role leakage | Situations containing facts from wrong relationship / actionable situations | Multi-role people | **0** |
| Chimera rate | Correlations merging distinct opportunities/requests / reviewed correlations | Company and connector cohorts | **0 HKS**, downward pilot trend |
| False-complete rate | Context marked ready while required role/state/source/policy is missing | Unknown domains and outages | **0** |
| Visibility widening | Derived objects broader than any source permission / derived objects | Sensitive/support cohort | **0** |
| Synthetic-authority count | Prescriptive BSOs using synthetic/memberless evidence | All authoritative outputs | **0** |
| Stale-loop rate | Open situations already resolved by newer scoped evidence / open situations | By source completeness | **0 golden**, pilot target after baseline |
| Wrong-close rate | Resolution applied to wrong request/relationship / closes | Cross-channel and parallel asks | **0** |
| Safe-abstention recall | Unsafe/incomplete cases correctly blocked / labelled unsafe cases | HKS, unknown domains, identity conflict | **100% HKS** |
| Context precision/recall | Relevant selected facts / selected; selected relevant / labelled relevant | High-degree/long-thread cohorts | Threshold must be ratified before authority |
| Correction burden | Founder context/target/state corrections per 100 surfaced situations | Compare baseline and pilot | Sustained reduction, not hidden by lower surfacing |
| Trace completeness | Sampled surfaced cards with replayable lineage / sampled cards | Live/shadow path | **100%** |
| LLM physical calls/event | Provider attempts / uncached eligible event | Success, repair, error cohorts | Central retry ceiling; no storm |
| LLM ledger variance | Absolute provider-bill minus internal ledger / provider bill | Model/month | Agreed finance tolerance |
| Outcome proof | Context-assisted decisions with completion, result and counterfactual / claimed wins | Design partner | No ROI claim without complete receipt |

## Phased rollout and Exit gate

1. **Shadow only:** implement P0.1–P0.7, replay the full HKS/mutation suite, and compare new BSO against current cards without changing authority.
2. **Reviewed pilot:** enable P1 selector/identity/deal/source/cost/trace work for named tenants; every prescriptive candidate is human-reviewed and corrections replayed.
3. **Bounded authority:** promote only scenario cohorts whose business-subject, policy, completeness, lifecycle and lineage gates are green; all other cohorts remain observation/review.
4. **Outcome proof:** measure correction burden and verified decision/outcome improvement before calling the layer customer-ready.

The Layer 2 Exit gate is conjunctive, not an average: all 214 existing focused tests remain green; all golden and negative HKS replays execute with zero skips; zero wrong target, cross-role/deal leakage, visibility widening, synthetic authority and wrong close; every ambiguity safely abstains with a reason; correction/outage recovery is version-fenced; every sampled Live card has lineage; and pilot value has an outcome/counterfactual receipt. Until then, the correct status is **framework-ready, not live-ready**.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../04-Loopholes-Edge-Cases-and-Fail-Closed/README.md" (M2.C2.L-logic.V0.U01)
include "../05-LLM-Use-Cases-and-Cost/README.md" (M2.C2.L-logic.V1.U01)
-->
