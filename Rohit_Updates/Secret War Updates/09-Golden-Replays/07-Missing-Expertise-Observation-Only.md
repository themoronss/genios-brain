# Golden Replay 07 — Missing Expertise, Observation Only

**Scenario:** GeniOS has credible evidence and a coherent situation, but no complete accepted capability for the actual domain. The base fixture is Theresa’s investor/fundraising reconsideration relationship; a high-risk **[MODELLED]** variant is a vendor bank-detail change while the pinned **[CODE]** Admin corpus has 57 total capabilities, 57 stubs, **zero non-stub**, zero reviewed, zero accepted and zero routes. The correct result is useful **Observation only**, not generic advice.

## Evidence boundary

**[CUSTOMER] Requirement:** the user explicitly wants GeniOS to distinguish actual expert judgment from a generic activity reminder. In the Theresa case, it must preserve her request for meaningful updates and possible reconsideration, avoid inventing rejection or “one last chance,” and either recommend the justified expert move or state honestly that the needed expertise is unavailable. This is demanded behavior; it is not proof that the present runtime meets it.

**[MODELLED] Designed replay:** the Theresa, Admin bank-detail, stub route, legacy-fallback and later-promotion fixtures below are acceptance probes built to test that requirement. Their expected decisions and Layer 1–Layer 7 receipts are design assertions, not observed production behavior or `[TEST]` results.

**[CODE] Pinned corpus truth at `harsh/mvp@b739bd5`:** Sales has 46 capability files—43 stubs and 3 non-stub authored drafts—but **zero reviewed or accepted**; Customer Support has 49—40 stubs and 9 non-stub drafts—but **zero reviewed or accepted**; Admin has 57 total capabilities, 57 stubs, **zero non-stub**, zero reviewed, zero accepted and zero routes. No reviewed/accepted investor or fundraising capability is established. Here “non-stub” does not mean complete, reviewed, accepted, live or outcome-proven.

## Business subject and fixture

The **Business subject** in the **[MODELLED]** fixture is fully role-scoped: Theresa is an investor partner, Rohit owns company updates, and the open condition is “send meaningful progress updates; reconsideration may occur.” Layer 1 and Layer 2 may accurately establish the request, messages sent, silence and current milestone evidence; that context does not make Sales expertise applicable. The pinned **[CODE]** inventory above is the authority for current corpus maturity: all non-stub Sales and Support capabilities remain unreviewed drafts; Admin has zero non-stub, zero reviewed, zero accepted and zero routes; and reviewed/accepted fundraising expertise is absent.

## Current failure

The new domain compiler can exist, validate structurally and run in shadow while the authoritative path continues through legacy `SALES_V1`/`GENERAL_V1`. This creates the dangerous fallback: a known email/open-loop pattern receives “reply now,” “one last chance,” “confirm meeting” or another fluent imperative even though the relevant professional expertise is absent. A 65–94% scalar can then hide that the evidence may be clear but **expertise coverage is zero or partial**.

Wiring alone does not fix this replay. Enabling a compiler whose route points to stubs or whose nearest route is ordinary Sales still produces false authority. Missing expertise is a hard action gate.

## Expected behavior

**[MODELLED]** Return an Observation-only object that says what is known, what remains, why it may matter, and exactly why no recommendation is authorized:

> Theresa requested meaningful company updates and indicated possible reconsideration. Update history and current milestone materiality are available for review. GeniOS has no accepted investor/fundraising capability for deciding cadence, update value, escalation or stop conditions, so it will not recommend an outbound action. Review the source or promote an accepted capability; no action button is available.

The object includes source receipts, role/current-state confidence, missing capability/dependencies, four-brain snapshot status and an authoring/review route. It does **not** select an action. A later accepted capability creates a fresh ExpertisePackage and Decision; it cannot retroactively promote the old observation.

## Prohibited behavior

- Do not substitute the nearest Sales/Admin/general rule for an uncovered domain.
- Do not count a directory, YAML file, schema-valid artifact or route as complete expertise.
- Do not lower one scalar confidence and retain the same imperative.
- Do not let legacy fallback override compiler abstention.
- Do not let an LLM invent a playbook, policy, permission, recipient or action at runtime.
- Do not show “I’ll do it,” send, handoff or approval controls on Observation only.
- Do not treat opening/dismissing the observation as an outcome or learned preference.

## Exact Layer 1–Layer 7 contract

| Layer | Required responsibility | Required output/receipt | Fail-closed result |
|---|---|---|---|
| **Layer 1 — Knowledge** | Preserve exact request/message/actor/thread, source readiness, visibility/use and milestone evidence without assigning professional meaning | Qualified source receipts and role candidates; no fabricated rejection/deadline | Park/Review source only if evidence/visibility is incomplete; clear evidence may proceed |
| **Layer 2 — Context Intelligence** | Resolve Business subject, roles, relationship, exact open condition, sent history, lifecycle, conflicts and missing state | Complete bounded BusinessSituationObject with context confidence/coverage separate from expertise | Review source for context defects; otherwise publish coherent situation even though later expertise is missing |
| **Layer 3 — Domain Expertise** | Resolve exact domain/situation and accepted dependency closure; report corpus/brain coverage honestly | Typed unsupported/incomplete ExpertisePackage receipt: missing capability/objects/rules/plays, corpus version, brain snapshot and `authoritative=false` | Observation only/Defer; **zero action-authorizing playbooks**; legacy generic fallback blocked |
| **Layer 4 — Reasoning** | Preserve Layer 3 abstention as highest authority; explain missing capability/evidence and next review/authoring trigger | `INSUFFICIENT_CONTEXT`/unsupported decision with no selected candidate, no stakes invented and no action text | Observation only; no CTA, ranking or LLM-generated prescription |
| **Layer 5 — Executive** | Refuse to create accountable work from non-actionable observation | No ExecutionObject; optional internal expertise-review ticket only as a distinct governed Admin process | No owner assignment, agent lease or execution for the business action |
| **Layer 6 — Delivery** | Render observation/review safely; enforce absence of action routes and recipients | Observation DeliveryResult/inbox receipt if displayed; no outbound materialization | Suppress any legacy/action projection |
| **Layer 7 — Learning** | Record coverage demand separately from recommendation outcome; require governed human corpus promotion | Aggregated authoring demand may inform backlog; no efficacy/preference/brain proposal from view/click | No promotion and no Expert Brain mutation |

## Mutation matrix

| Mutation | Expected behavior | Prohibited behavior | Outcome / pass evidence |
|---|---|---|---|
| Domain directory exists, capability is Stub | Observation only with exact stub/dependency list | “Capability active” from file count | No selected candidate/action button |
| Situation route exists but required object/playbook is Stub | Incomplete closure blocks package authority | Compile partial route then generic play | Dependency-closure receipt shows blocker |
| No route; nearest Sales capability appears similar | Unsupported situation and authoring hint only | Nearest-neighbor prescription | Route disposition is explicit unsupported |
| New compiler abstains, legacy pack matches silence | New abstention blocks legacy prescription | `SALES_V1` “reply now” wins | Authoritative output remains non-action |
| Evidence confidence is 95%, expertise coverage is 0% | Show high evidence certainty and zero expertise independently | 95% decision confidence/action | Vector plus hard gate visible |
| LLM proposes a plausible investor update | Discard/runtime quarantine; may create offline draft for expert review with citations | Directly use model action | Runtime decision unchanged and replay-stable |
| Organization policy forbids investor outreach | Blocked even if Expert capability later exists | Adaptive preference or model override | Permission resolution trace |
| Adaptive prefers concise updates but Organization allows them | Preference remains visible but cannot create coverage | Treat learned style as investor expertise | Observation-only state persists |
| Accepted investor capability is later promoted | Create new versioned package/decision from current evidence; compare update/wait/connector/stop | Mutate old observation into action silently | New parent ids, corpus/brain snapshot and decision trace |
| **[MODELLED]** Admin bank-detail change; pinned **[CODE]** corpus has 57 total capabilities, 57 stubs, zero non-stub, zero reviewed, zero accepted and zero routes | Observation/Blocked pending a reviewed and accepted high-risk capability, out-of-band verification and dual approval | Generic “complete task” or known-sender trust | No ExecutionObject/financial change |
| Supported Sales cooling capability with complete closure | Proceed through normal candidate/constraint gates | Remain permanently abstained due to historical gap | Actionable only if all L1–L4 fields pass |
| Domain ambiguity between Sales and Support | Review domain/purpose; preserve restricted use | Run both and choose highest score | No prescription until domain/use resolved |

## Required observation schema

| Field | Required value |
|---|---|
| Situation | State-based statement, not action headline |
| Business subject | Correct entity, role and relationship scope |
| Evidence | Reopenable receipts, freshness, conflicts and missing source fields |
| Coverage | Domain/situation attempted, route state, capability/dependency acceptance and four-brain status |
| Why non-actionable | Exact hard gate: unsupported, Stub, missing dependency, permission conflict or shadow-only authority |
| Next safe step | Review source, request domain expert authoring, wait for evidence, or no action |
| Re-evaluation trigger | New accepted capability/version and/or named missing evidence |
| Controls | Open source/details only; no do/send/handoff/execute control |

## Replay assertions

1. Every unsupported/stub mutation returns no selected candidate and no action-authorizing downstream object.
2. Evidence confidence can vary without changing the missing-expertise hard gate.
3. Legacy fallback, card template and LLM explanation cannot add an action after abstention.
4. Corpus/route/capability/brain versions are visible and deterministic.
5. Promotion creates a new chain; replay of the old version remains Observation only.
6. Coverage-demand analytics cannot become recommendation success, customer preference or automatic Expert Brain content.

## Outcome

The replay passes when GeniOS remains useful and honest: it identifies the correct situation and Business subject, shows the Evidence and missing expertise, offers a precise review/authoring path, and exposes **no action button, ExecutionObject or outbound delivery**. Once a complete accepted capability is promoted, only a fresh fully gated replay may become actionable. Success is zero unsupported prescriptions—not more confident wording.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md" (M5.C1.L-contract.V1.U01)
include "../08-Cross-Layer-Synthesis/08-HKS-and-Scenario-Responsibility-Matrix.md" (M5.C1.L-integration.V1.U01)
include "../03-Layer-3-Domain-Expertise/06-Improvements-Acceptance-and-Metrics/README.md" (M3.C1.L-interface.V0.U01)
-->
