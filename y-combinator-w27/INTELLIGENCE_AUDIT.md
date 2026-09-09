# The intelligence audit — what comes out, what is suppressed, and exactly where it breaks

**Tenant:** `org_e97e86f858ad48b2bbf64b8a` (Rohit Swerashi) · read-only, 9 Sep 2026
**Method:** the actual row contents, not counts. Every quote below is a `select` from the tables
the sweep wrote. Nothing re-run, nothing written.

This is the companion to `LIVE_RUN.md`. That page counted. **This page reads.**

---

## Part 1 — The 15 cards, judged one by one

| # | Score | Headline | Verdict |
|---|---|---|---|
| 1 | **63 critical** | Deliver fundraising opportunities to sanchiconnect.tech NOW | ❌ **Not Rohit's promise.** Owner is `sunil.s@sanchiconnect.tech`. Also duplicated as #2. |
| 2 | 50 | Deliver fundraising opportunities to healthcare leaders | ❌ Duplicate of #1 |
| 3 | 50 | Deliver mentorship guidance from expert mentors now | ❌ Marketing blast rendered as Rohit's obligation |
| 4 | 49 | Reply to Sehan Sanjula now | ⚠️ Real person, but the commitment attached belongs to `willow@myzyner.com` |
| 5 | 48 | Reply to Sunil about HealthX Elevate visibility | ✅ **Real** |
| 6 | 46 | Deliver six months free Growth plan access now | ❌ **Inverted.** Composio offered *Rohit* six months free. The card tells Rohit to deliver it. |
| 7 | 46 | Renew Growth plan at $599/month now | ❌ A vendor's auto-renewal clause, not Rohit's promise |
| 8 | 46 | Deliver $2,000 monthly savings to myzyner.com | ❌ Owner is `willow@myzyner.com`. Duplicated as #9. |
| 9 | 46 | Deliver $2,000 monthly savings now | ❌ Duplicate of #8 |
| 10 | 46 | Deliver share further details regarding individual review | ⚠️ Broken grammar ("Deliver share…"). Duplicated as #11. |
| 11 | 46 | Share review meeting details and links now | ⚠️ Duplicate of #10 |
| 12 | 44 | **(NULL)** | ❌ **Headline NULL and situation NULL.** Queued anyway, at score 44. |
| 13 | 43 | Send Lalitha A R the product context materials | ✅ Real (situation text NULL) |
| 14 | 42 | Reply to Manik about GeniOS demo access | ✅ **Real, and the best card in the feed** |
| 15 | 42 | Book time with Sal Stabler on her calendar link | ✅ Real (situation text NULL) |

**5 usable. 3 pairs of duplicates. 6 that accuse the founder of a promise he never made. 1 blank.**

### Every card fails parts 4, 5 and 7 of your ten-part structure

| Field | All 15 cards say |
|---|---|
| `do_nothing_consequence` | "The commitment overdue condition may remain unresolved." · "The unanswered email condition may remain unresolved." |
| `why_now` | "A promise came due" · "They are waiting on a reply" |
| `relationship_role` | `NULL` — every card |

Part 4 ("why it matters *now*") is a **restatement of the situation type**. Not "you have a call
with them Thursday" — a tautology. Part 5 ("who is accountable") is empty everywhere.

---

## Part 2 — What the system computed and refused to show you

This is the `awaiting_response` list. It is **held**, all 41 of it, and never rendered:

| Counterparty | Days waiting | Follow-ups |
|---|---|---|
| `rohit@crescerelabs.com` | **50** | 0 |
| `boardy@boardy.ai` | 49 | 0 |
| `notification@accubate.app` | 47 | 1 |
| Leslie Omonzane | 46 | 1 |
| `vatsa@valiron.co` | 46 | 1 |
| `tripathihk2014@gmail.com` | 42 | 1 |
| **`siddhant@neon.fund`** | **28** | **0** |
| **`vidushi@peakxv.com`** | **28** | **0** |
| **`harshita@peakxv.com`** | **28** | **0** |
| **`manik@titancapital.vc`** | **28** | **0** |
| **`joseph@afore.vc`** | **28** | **0** |
| **`madison@afore.vc`** | **28** | **0** |
| **`shivam@together.fund`** | **28** | **0** |
| **`piyush@3one4capital.com`** | **28** | **0** |
| **`apply@surgeahead.com`** | **28** | **0** |
| **`team@zfellows.com`** | 28 | 1 |
| `adityad@iima.ac.in` | 28 | 2 |

**Eleven of these are VCs and accelerators** — Peak XV, Titan Capital, Afore, Neon Fund, Together
Fund, 3one4, Surge, Z Fellows. Twenty-eight days. Zero follow-ups.

And the `first_response_overdue` list, also held, all 40:

| `ball_in_court` | Overdue | Last heard |
|---|---|---|
| **us** | 1381 hours (**57 days**) | 60 days |
| **us** | 1381 hours | 60 days |
| **us** | 1380 hours | 58 days |
| **us** | 1363 hours | 55 days |
| … 36 more, every one `ball_in_court = us` | 1211–1381 hours | 43–60 days |

> **This is your example, verbatim.** *"Rohit, tumne investors ko mail nahi kiya tha, tumhe
> follow-up lena chahiye."* The system computed it — the names, the day counts, the follow-up
> counts, whose court the ball is in — and showed you "Deliver fundraising opportunities to
> sanchiconnect.tech NOW" instead.

---

## Part 3 — The fault map

Sixteen defects. Layer, component, and what proves it.

### L1 — Knowledge · **3 defects. I was wrong to call this layer clean.**

`LIVE_RUN.md` said L1 was the strongest layer, based on signal counts and a 96% span-verification
rate. Reading the actual spans changes that verdict. **The verifier only checks that the quoted
text exists in the source. It does not check that the text means anything.**

| # | Defect | Evidence | Size |
|---|---|---|---|
| **L1-1** | **Reply-attribution headers are extracted as business signals.** `'On Sat, 8 Aug 2026 at 14:22, Manik Pasricha wrote:'` is stored as a `financial_obligation` at **4560 bp** — the second-highest importance on the tenant. `'On Tue, 24 Jun 2025 at 11:37, Surge wrote:'` likewise. | 23 of 395 signals match `^On …wrote:` — 16 `deadline_stated`, 7 `financial_obligation` | **23 signals** |
| **L1-2** | **Meaningless spans pass verification.** 49 signals quote a bare ISO timestamp (`'2026-07-24T12:30:00+05:30'`). 39 quote fewer than 25 characters. **`'Hi Rohit,'` is stored three times as a `relationship_change`.** | `evidence_refs[0].quote` | **~90 of 395 (23%)** |
| **L1-3** | ~~One sentence produces up to twelve signals.~~ **WITHDRAWN — see the correction below.** | | **0** |

> ### L1-3 is withdrawn, and the reason matters more than the finding did
>
> The table below is real, but the conclusion drawn from it was wrong. Measured afterwards:
> **every repeated quote on the tenant has exactly ONE distinct sender, and zero signals quote a
> `>`-prefixed line.** These are not templates and not reply history. They are **one sender's
> campaign.**
>
> "Pitching GeniOS (Software That Thinks For Your Company) From India" appears ten times because
> Rohit sent the same pitch to ten VCs. "we can expect the numbers to hit nearly ~$2-3k MRR"
> appears ten times for the same reason. **Ten investors, ten threads, ten situations — that is
> correct**, and it is precisely the investor-outreach intelligence this whole effort exists to
> surface. The deduplication rule that was planned for it would have deleted the Peak XV, Titan,
> Afore and Neon signals. The unit was retired before it was built.
>
> One residual is real: `"If you are unable to attend, please inform us at least one hour in
> advance"` produced 13 `commitment_due` signals from 13 meeting invitations. That sentence is an
> **instruction to the recipient, not a promise by anyone** — so it is a misclassification in
> extraction, not a duplication, and the fix is a prompt, not deterministic code. Recorded as a
> known gap.

The duplicate table, measured:

| Quote | Classified as | Copies |
|---|---|---|
| "If you are unable to attend, please inform us at least one hour in advance" | `commitment_due` | **12** |
| "As we can see the need of the product, we can expect the numbers to hit nearly ~$2-3k MRR" | `contract_renewal` | **10** |
| "Pitching GeniOS (Software That Thinks For Your Company) From India" *(a subject line)* | `relationship_change` + `opportunity_signal` | **10** |
| "I am sharing a few details here as well for your reference…" | `commitment_made` + `opportunity_signal` | **11** |
| "I applied to Afore Capital FIR and writing here to justify my credibility" | `decision_pending` | **5** |
| **"Hi Rohit,"** | `relationship_change` | **3** |

> ### The root cause of L1-1, and it is the same shape as everything else on this branch
>
> **The quoted-history stripper exists, is tested, and is on the wrong side of the pipeline.**
>
> `genios_engine/context/lifecycle/textguard.py:49` holds `_ATTRIBUTION` — a careful,
> deliberately-narrow regex for `"On 12 Feb, X wrote:"`, Outlook forward headers, `>` quote lines,
> with a comment explaining exactly why it is anchored to line start. It has an adversarial test
> suite at `tests/context/lifecycle/test_h6_adversarial.py`.
>
> **Its only importer is `genios_engine/context/lifecycle/judge.py:41`.** Grep `genios_engine/capture/`
> for `quoted_regions` or `in_quoted_history`: **zero hits.** L1 extracts from raw body text,
> reply history included. L2 knows how to tell live text from history and is asked the question
> only much later, for a different purpose.

### L2 — Context · **5 defects. This is still the worst layer.**

| # | Defect | Evidence |
|---|---|---|
| **L2-1** | **Every outreach situation is minted twice.** 41 `awaiting_response` situations for **22 distinct counterparties** — once anchored on the person node (`vatsa@valiron.co`), once on the thread node (`Thread with vatsa@valiron.co`). | `count(*)=41` vs `count(distinct counterparty)=22` |
| **L2-2** | **Absence situations have no ranking at all.** `awaiting_response`: 41 rows, `count(distinct importance_bp) = 1`, every one exactly **4000**. Same for `first_response_overdue` (40), `ticket_aging` (19), `commitment_overdue` (3). 4000 is `DEFAULT_IMPORTANCE_BP` — the fallback. A 60-day silence from Peak XV ranks identically to a 1-day silence from a newsletter. | compare `relationship`: 19 distinct values, 1040–5000 |
| **L2-3** | **`outreach.response_expected` is `false` on 40 of 41** — including every 28-day investor thread. Only one row in the entire tenant says `true`. | `graph_facts` |
| **L2-4** | **Confidence is near zero on exactly the situations that matter.** `awaiting_response` 0–30; the thread-anchored twins are all **0**. Compare `admin_period_review` at 70. | `confidence_overall` |
| **L2-5** | **The publisher holds 367 and admits 18**, and 349 of those holds carry `qes_required + verified_evidence_required` — two names for one starvation. **Only relationship-shaped situations get through**: of the 18 admitted, 10 are `investor_relationship`, 6 `relationship`, 2 `opportunity`. **Zero action-shaped situations have ever reached L3.** | `situation_admission_decisions` |

L2-2 and L2-5 are the same root cause, and it is the one this branch fixes: the L1 bundle never
arrives, so `importance_base()` falls to the default *and* `importance_source` never becomes
`l1_qualified_signals`.

### L3 — Expertise · **1 defect, total**

| # | Defect | Evidence |
|---|---|---|
| **L3-1** | **Three of the four brains are empty in all 381 packages.** `behavior_patterns = 0`, `organization_rules = 0`, `adaptive_preferences = 0` — every single package. Only `capabilities` is populated. And 130 situations were packaged while only 18 were admitted: L3 compiles expertise for situations the gate below it is holding. | `jsonb_array_length` over `expertise_packages` |

### L4 — Reasoning · **2 defects**

| # | Defect | Evidence |
|---|---|---|
| **L4-1** | **270 of 512 candidates come from the `sales` pack** on a tenant whose only activated domain is `admin` — and they hold the top of the utility table. `sales.pb.upsell.usage_triggered_upsell` scores **6643 bp**; `deliver_commitment` scores 6300. There are no customers to upsell. | `reasoning_candidates` by `play_id` |
| **L4-2** | ~~The best-scoring candidates are being killed.~~ **WITHDRAWN — see below.** | |

> ### L4-2 is withdrawn: Layer 4 was doing its job
>
> The 30 eliminated candidates are **15 `sales.pb.upsell.usage_triggered_upsell` and 15
> `sales.pb.churn_prevention.save_play_with_dignity`**, and every one of them was eliminated by
> `core.constraint` at the `policy` stage with `reason_code = tenant_policy_block`.
>
> They score high on the utility formula and are refused by a guard rail — which is the correct
> outcome for an upsell play on a tenant with no customers. **Layer 4 received a ballot polluted
> by Layer 3 and refused the worst of it.** Framing that as "the best candidates are being killed"
> was wrong: the check counts are 2109 pass, 571 warn, 30 eliminate, and the 30 are the only
> plays that should never have been on the ballot at all.
>
> **Layer 4 has no defect of its own. Both L4 findings trace to L3-1** — its plays come from the
> capabilities Layer 3 compiled, and Layer 3 was compiling from corpora this tenant never
> activated.

### L5.2 — Delivery · **5 defects, and these are the cheapest to fix**

| # | Defect | Evidence |
|---|---|---|
| **L5.2-1** | **`do_nothing_consequence` is a template on 15 of 15 cards.** Two strings, both restating the situation type. | every card |
| **L5.2-2** | **`why_now` is a template on 15 of 15.** "A promise came due" / "They are waiting on a reply". | every card |
| **L5.2-3** | **The headline discards the situation.** The `situation` field holds *"Manik at Titan Capital last wrote 31 days ago sharing product links and asking you to mention something succinctly. Ball is in your court."* The headline renders *"Reply to Manik about GeniOS demo access"*. **The good prose is already computed and stored — the headline replaces it with an order.** | cards 5, 14, 15, 4 |
| **L5.2-4** | **Two builders produce the same commitment twice**, and they disagree about their own fields. One sets `unresolved_item` and puts the counterparty in `business_subject` (3 cards, queued). The other leaves `unresolved_item` null and puts the *commitment action text*, truncated to 76 characters, in `business_subject` (`"provide mentorship guidance from expert mentors on healthcare, technology, opera"`). | 3 duplicate pairs |
| **L5.2-5** | **Null-content cards are queued.** Card 12: `headline` NULL, `situation` NULL, score 44, state `queued`. Four cards have a NULL `situation`. | cards 8, 12, 13, 15 |

---

## Part 4 — What to fix, in the order the evidence justifies

Ranked by *intelligence gained per unit of work*, not by layer order.

| Rank | Fix | Layer | Why first |
|---|---|---|---|
| **1** | **Stop the headline discarding the situation.** Render `situation` as the card body and demote the imperative. | L5.2 | The best prose in the system already exists and is being thrown away at the last step. Pure rendering change. Nothing upstream moves. |
| **2** | **Deploy this branch's absence-receipt fix.** | L2 | 81 of 84 held absences have a verified receipt already in the graph. This is what unblocks the investor list above. |
| **3** | **Import `textguard` into the capture path** before extraction. | L1 | The stripper is written, tested and unused. Removes 23 header signals and most of the 49 timestamp spans at the source. |
| **4** | **Dedup the extracted span.** One sentence must not yield twelve signals. | L1 | "Hi Rohit," is not a relationship change, and it certainly is not three of them. |
| **5** | **One anchor per outreach reading.** | L2 | Halves the situation count and removes the confidence-0 twins. |
| **6** | **Deactivate the `sales` pack on this tenant.** | L4 | Configuration, not code. Frees the top of the utility table for admin plays. |
| **7** | **Refuse to queue a card with a NULL headline or situation.** | L5.2 | A blank card at score 44 is a gate that is not checking. |
| **8** | **Write real `do_nothing_consequence` and `why_now`.** | L5.2 | Two of your ten card parts are currently tautologies. |
| **9** | **Fix `outreach.response_expected`.** | L2 | 40 of 41 say "no reply expected" about threads where the ball is demonstrably with the other side. |
| **10** | **The three empty brains.** | L3 | Real work, and everything above lands without it. |

---

## Part 5 — The honest one-paragraph answer

**The intelligence is not missing. It is computed, stored, ranked at a flat constant, held at the
publishing gate, and replaced at the last step by a template.** The system knows that eleven VCs
have not replied in twenty-eight days and that the ball is with Rohit on forty threads averaging
fifty days. It shows a marketing email's promise as the founder's own overdue obligation, at
critical urgency, twice. **Every layer contributes, but they contribute unequally:** L5.2 is
discarding good text it already has, L2 is starving and duplicating, L1 is extracting greetings
and reply headers as business signals, L3 is three-quarters empty, and L4 is ranking upsell plays
on a mailbox with no customers.
