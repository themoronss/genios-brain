# Layer 6 Delivery (Atlas 5.2) — Customer Expectation and HKS

## Customer promise

The Customer should receive already-correct intelligence where it can be acted on with the least friction and least unwanted attention. Expected delivery means the right authorized person or agent, current surface, humane moment, appropriate format, visible evidence, one idempotent action path, and an auditable result. It does not mean broadcasting more cards.

| Customer need | Expected delivery behavior | Current Failure risk |
|---|---|---|
| Founder in email flow | Grounded inline suggestion/draft for the exact recipient and thread | Only a Slack webhook adapter is real in the live channel registry |
| Team member owns the work | Deliver to accountable active owner, preserving approver and visibility | Legacy bridge copies frozen assignee; v2 late resolver is not live-composed |
| Founder is in a meeting/focus state | Queue silently; surface after the context lease changes | Presence modules exist, but no proof the live legacy sender uses v2 context routing |
| Agent can execute | Signed scoped instruction, approval, one executor and result receipt | Intended handoff route returns 501; engine-ready labels cannot imply operational execution |
| Message becomes stale while queued | Cancel/suppress before contact, with reason | Cards revalidate strongly; reminders only prove execution open/unexpired at send |
| Delivery fails | Bounded retry, fallback when lawful, visible attempt/dead letter | Legacy adapter retries same Slack route; v2 fallback/fenced worker is not production-composed |
| User clicks/acts | Delivery accepted/executed receipt joins the same Executive action/outcome | Client lifecycle and legacy card action can drift from ExecutionObject |
| Customer asks “why didn’t I see it?” | Distinguish defer, suppress, cancel, failure, expiry and ignore | Rich distinction exists across code, but canonical live lifecycle is split |

## HKS register

HKS is preserved as the supplied high-consequence scenario label; no expansion is invented.

| HKS | Business situation | Harm if wrong | Required delivery behavior | Prohibited output | Fail-closed result | Golden replay | Exit gate |
|---|---|---|---|---|---|---|---|
| HKS-L6-01 Theresa update | A consented periodic investor/partner update becomes eligible after material progress | Spam, missed reconsideration window, relationship damage | Resolve Theresa’s exact identity/thread; deliver once on eligible surface; record send and response window | Generic “last chance,” repeated reminders, send to wrong Antler contact | Defer/review if cadence, consent, materiality or recipient is unresolved | Two previous sends, silence, new milestone, quiet hours, duplicate worker | One lawful delivery and one joined execution/outcome trace |
| HKS-L6-02 Boardy introduction | Connector introduced several people via similar threads | Shared connector receives reply; identities and facts leak across relationships | Route each target-specific execution to introduced human/thread; connector is evidence only | One Boardy destination or one giant person/node card | Suppress prescriptive send; open source review | Connector plus three introduced contacts and independent completion states | Zero connector-as-target; separate dedupe keys/results |
| HKS-L6-03 Meeting/focus interruption | Critical insight becomes due while founder presents in a meeting | Notification fatigue and loss of trust | Known presence downgrades push to durable pull or defers until allowed; business priority retained | Buzz during known focus because “critical” bypasses all policy | DEFER with `not_before`, without retry consumption | Presence lease starts/ends across quiet-hours boundary | Exact defer/send times; attempts unchanged during holds |
| HKS-L6-04 Visibility restriction | Support/private/community evidence informs an execution | Confidential data delivered to commercial or unauthorized audience | Re-resolve recipient against inherited visibility at send | Send because stored assignee/channel exists | SUPPRESS with policy reason, never fallback louder | Visibility revoked after materialization | No adapter call; suppression appears in result/analytics |
| HKS-L6-05 Provider timeout ambiguity | Slack accepted POST but response is lost | Same customer receives duplicate nudge | Preserve unknown attempt; reconcile provider id/idempotent effect before retry | Blind resend after timeout | Hold/dead-letter for reconciliation when certainty is impossible | Provider records message then times out | One external message across worker restart |
| HKS-L6-06 Card acceptance | Founder taps “I’ll do it” after viewing card | UI says accepted/executed while no accountable execution exists | Receipt must call one Executive command and remain distinct from completion | Delivery `executed` or card `acted` from a click alone | Keep accepted/claim-pending with integration error | Repeated click plus concurrent agent claim | One execution claim; no business completion without evidence |
| HKS-L6-07 Agent/API handoff | Approved Sales agent should execute exact next step | Duplicate, unauthorized or over-broad agent action | Signed envelope, one lease, idempotency, constraints, revocation and result | Generic webhook counted as governed handoff | 501/unavailable until complete protocol | Duplicate approvals, stale token, result retry | Exactly one executor and attributable result |
| HKS-L6-08 Cross-channel completion | Counterparty already replied elsewhere while reminder waits in outbox | Embarrassing duplicate outreach | Revalidate exact execution semantic authority before send | Send because execution row has not yet closed | Cancel/review uncertain queued reminder | Reply arrives between Executive sweep and Delivery drain | Zero reminder after verified completion |
| HKS-L6-09 Multi-tenant channel config | One tenant has corrupt/missing credential while another is healthy | Cross-tenant blockage or secret leakage | Fail only affected row/org; capability reports operational false | Treat configured row as working or expose secret in error | Terminal/dead-letter with sanitized reason | Two tenants, one invalid Slack secret | Healthy tenant sends; bad tenant isolated; no secret output |
| HKS-L6-10 Route fallback | Primary destination fails and secondary is permitted | Message disappears or retries wrong/loud channel indefinitely | Re-gate every fallback rung for audience, visibility, timing and budget | Blind Slack→email→mobile escalation | Dead-letter if no lawful route | Primary unavailable, secondary quiet/restricted | One lawful fallback or explicit no-delivery result |
| HKS-L6-11 Expired projection rebuild | Old card expires while signal remains truly unresolved | Permanent suppression or duplicate/stale intelligence | Permit fresh projection only after current semantic validation | “Expired means resolved” or rebuild same wrong card automatically | Review/suppress on unchanged ambiguity | Old expired card, current open signal, newer completion evidence variants | Rebuild once only for valid unresolved variant |
| HKS-L6-12 Receipt spoof/clock error | Client posts viewed/accepted/executed with impossible time or illegal order | False engagement, learning and ROI | Tenant-scoped, authenticated, chronological legal transition with trusted actor/device/provider data | Accept arbitrary lifecycle string as business outcome | Reject with 409/422; preserve attempt | Receipt before creation, future receipt, duplicate key, illegal jump | All invalid receipts rejected; duplicate is no-op |

## Delivery boundary versus intelligence quality

Layer 6 must reject or suppress unsafe material, but it cannot make a wrong recommendation intelligent. If a card says “Reply to Boardy,” dumps a person’s facts, or mistakes a completed meeting for an open loop, routing it to Slack, email, browser and agent multiplies the harm. The correct action is to require the Layer 5 execution to carry a bounded target and current authority, then fail closed when that contract is absent.

## Operational truth for the Customer

| Label | Truth required | Current evidence |
|---|---|---|
| Engine-ready | Internal contract/seam exists | Registry reports most unit seams ready; email is explicitly false |
| Operational | Tenant has usable configured adapter/credential and reachable client | Capability API computes this per channel; it must remain fail-closed |
| Delivered | Adapter/provider/client receipt establishes arrival according to channel | Legacy Slack `200` marks delivered; richer provider reconciliation remains a gap |
| Viewed/accepted/executed | Legal receipt with actor and chronology | Tracker/API can record lifecycle, but source trust and Executive join must be strengthened |
| Outcome-proven | Business result and attribution window exist | Not established by delivery analytics alone |

## Acceptance standard

The Customer experience is acceptable only when every HKS resolves to exactly one authorized DeliveryResult or a visible defer/suppress/cancel/failure, never silent loss. A delivery click cannot become business completion. Operational capability labels must match real adapters. The live sender must use the canonical v2 object/worker or explicitly retire that contract; parallel truth is not acceptable.

Pilot evidence must report right-recipient precision, stale-send rate, duplicate external messages, deferrals without retry burn, delivery/view/accept/execute receipt coverage, correction burden, notification fatigue, and business outcome attribution separately.

## Verdict

The Expected experience is architecturally represented but not yet delivered across its promised surfaces. The live Slack path is materially safer than a direct webhook, yet v2 audience/context/fallback/receipt machinery is not the production sender, card acceptance is not welded to Executive completion, and agent handoff is intentionally unavailable. These are functional gaps, not copy problems.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M4.C2.L-contract.V0.U01)
include "../../00-Methodology/04-Customer-Intelligence-Contract.md" (M1.C2.L-contract.V0.U01)
-->
