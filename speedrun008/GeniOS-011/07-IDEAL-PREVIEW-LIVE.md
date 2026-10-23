# 07 · The ideal preview, live — what Harsh does so every goal and card of /preview comes from the brain

**Written for:** Harsh, and any coding agent who picks up a unit.

On 23 Oct 2026 Rohit asked: *"jab itna locally aa sakta hai toh website pe kya dikkat hai … ye sare cards and goals visible ho website pe bhi"*. In plain words: if this works locally, why not on the website — make all these cards and goals show up there too.

This file answers in four parts:
1. what the preview is;
2. why production does not produce the same today;
3. card by card, what makes each one appear;
4. the order to do it in, with a check that proves it is done.

It uses the step numbers of [02-PLAN](02-PLAN.md). The few units that plan does not have yet are added here as **N1–N6**.

> ⚠ **Privacy.** This repository is public. So this file has no e-mail addresses, no verbatim mail and no org id; it uses `<ORG>` for the org id. The content itself is on the preview, which only Rohit's account can open (see §0).

---

## 0 · What exists now

- **Where:** `https://brain.thegenios.com/preview`. It went live on 23 Oct from dashboard `main` `ff13896`, linked in the sidebar as Intelligence → *Ideal preview*.
- **What it is:** the dashboard as it should look when every layer works. It holds:
  - 10 goals, all in the Admin domain, sorted into 8 categories;
  - 2 proposed goals;
  - 20 cards, each with its full L1 → L6 trace.
- **How it was made:** Claude read Rohit's own Gmail and Calendar through the claude.ai connectors (every thread he started since Nov 2025 and every human reply since Aug) and reasoned over them by hand. In other words, Claude did what L2 is designed to do: read a whole workstream at once, judge it as an expert, tie it to a goal.
- **What it is NOT:** live. It never updates. It is the target and the reference — the clickable dummy that the real pages must match.
- **Access:** owner-only.
  - The HTML is a server-only module in the dashboard repo, `src/server/ideal-preview-html.ts`. The repo is private, and the module never reaches `public/` or a client bundle: 0 hits in `.next/static`.
  - `GET /api/preview` checks the caller's token against the brain's `/auth/me` and allows only `PREVIEW_ALLOWED_EMAILS` / `PREVIEW_ALLOWED_ORGS`. Those are env vars on the dashboard app; the defaults are Rohit's address and his org.
  - **To see it yourself:** add your address to `PREVIEW_ALLOWED_EMAILS` on the dashboard app, or open it on Rohit's session.
- **To refresh it:** re-run the local build on Rohit's machine (`GeniOS-Ideal-Dashboard/build.sh`), then `node scripts/ideal-preview-sync.mjs <index.html>` in the dashboard repo, then commit.

**The finish line:** `/dashboard/cards` and `/dashboard/goals` show the same 20 cards and 10 goals, made by the brain from live mail. The parity check in §4 (N5) is what proves it. After that, `/preview` is retired (N6).

---

## 1 · Why the website does not show it today

The mail behind every one of the 20 cards is in production's mailbox connection. It is lost or never turned into a card at the places below. Each one names the step that fixes it.

| # | Where it breaks | What happens to Rohit's work | Fix |
|---|---|---|---|
| 1 | **The chain may not run at all.** Since `7075014c` (4 Oct), the sweep and the warm lane skip any org whose plan has expired. That commit measured Rohit's grace as closed on 21 Sep. | No new card except through a manual **Sync now**. | [S02.U1](02-PLAN.md#s02). Note: S02.U5 is held until this is done. |
| 2 | **Every switch defaults to off:** `founder_office`, `expert_review`, `l2_reasoning`, `l2_cards`. | The expert and L2 paths never judge his files. | [S02.U3](02-PLAN.md#s02), then [S25](02-PLAN.md#s25) |
| 3 | **The history window is 60 days.** The preview reads back to Nov 2025. | About half the cards rest on older mail and can never appear: Lexsis (Apr), Theia (Mar), the Mar–Apr outreach, the Titan ask and the Antler thread (Aug), the engineer offer (Aug), a stalled intro and FITT (Jul). | [S09](02-PLAN.md#s09): Rohit picks the window (≥ 365 days covers it), then resync and rebuild. |
| 4 | **The gate archives founder mail.** Boardy is dropped on its List-Unsubscribe header (N-02); programme portals are dropped as no-reply; investor and programme mail goes to junk. | Boardy intros, Startup India, The Foundery, FITT and Stripe renewals never reach L3. | [S06](02-PLAN.md#s06) (U1/U2 are built on `speedrun008`, not yet on prod), [S06.U4](02-PLAN.md#s06) promote Boardy, [S02.U4](02-PLAN.md#s02) brief lines that protect these senders, [S08](02-PLAN.md#s08) |
| 5 | **L1 has no words for founder work.** The 16 signal types have no intro, meeting, investor interest or application status. | Those mails never trigger the L2 pass. | [S12](02-PLAN.md#s12), [S13](02-PLAN.md#s13) |
| 6 | **L3 files per thread and per keyword domain.** | One counterparty holds several live situations. A broadcast to 12 never becomes one subject. Rohit's own sent claims are never compared with each other. | [S14](02-PLAN.md#s14) (U1 built), [S15](02-PLAN.md#s15), [S21.U1](02-PLAN.md#s21) wave, **N1** own-claim conflict |
| 7 | **There is no goal object.** | No card carries a goal; goals are free-text brief lines. | [S27.U1](02-PLAN.md#s27) (built, interim), then [S26](02-PLAN.md#s26) decisions, [S28](02-PLAN.md#s28)–[S31](02-PLAN.md#s31) |
| 8 | **There is no card writer.** | A held card prints an engineer sentence; the subject is the move cut at 60 characters; the 5-line drafts never reach the card. | [S20](02-PLAN.md#s20), [S34](02-PLAN.md#s34) |
| 9 | **The brain and the dashboard have no categories,** and the dashboard Goals page reads brief lines. | Rohit's split (investment, funding, business, sales, projects, progress, process, hiring) does not exist anywhere live. | **N2** (brain), **N3** (dashboard, dummy = /preview), [S27.U3](02-PLAN.md#s27), [S31.U3](02-PLAN.md#s31) |
| 10 | **A bounce is linked to its thread but never becomes a card** (`context/delivery.py`). | Six of Rohit's mails never arrived, three of them to investors, and nothing says so. | **N4** |

---

## 2 · Card by card — what makes each one appear live

The ids are the preview's. Click `#/cards/<id>` on `/preview` for the full card and trace.

"First visible after" names the earliest phase in §3 after which the card should be able to appear. Record the real result in [03-LOG](03-LOG.md); never edit this table to match.

| Id | Category | Card (short) | The situation the brain must form | What it needs | Steps | First visible after |
|---|---|---|---|---|---|---|
| p1 | Progress | Four different traction numbers in his own sent mail | `information_conflict` on the tenant node | Numeric claims extracted from **sent** mail as `company.<metric>` facts, rank 2 each, then a `discrepancies` row and the conflict lane. A billing source is needed to verify which is true. | **N1**, S09, S16, S22 | F |
| f1 | Funding | Programme end review today (Calendar) | `meeting_ahead` | Calendar events reaching L3: on 4 Oct, 0 of 22 past meetings did. Meeting cards must open (S36.U1, built). | S02.U1, S12, S36 | B |
| f2 | Funding | Incomplete application with two reminders | `application_deadline` | A programme sender protected by a brief line; an `application_status` kind. | S02.U4, S12, S23 | B |
| f3 | Funding | A scout's referral that never came (via Boardy) | `promise_past_its_date` | Boardy promoted out of the archive; an `introduction` kind; a quiet file re-looked at. | S06.U4, S12, S21.U2 | D |
| f4 | Projects | Waiting on a founder's review of the YC doc | `outbound_awaiting_reply` | Only the chain running: a person, inside the window. | S02.U1, S02.U3 | **A** |
| i1 | Investment | Accelerator pass → a written offer to reconsider; 3 updates unanswered | `conditional_deferral` (Founder Office `live_investor_relationship`, stage passed → reconsideration) | A window of at least 80 days; Founder Office routed; the goal (F72 is this case, synthetic); the card writer for the 5-line draft. | S09, S23, S28–S29, S34 | E |
| i2 | Investment | An investor asked for traction; the reply did not answer | `reply_owed` (answered but not answered) | L2 judging whether the reply answers the ask; the claim check. | S09, S20, S21 | D |
| i3 | Investment | A call held, no follow-up mail after it | `meeting_without_follow_through` | Calendar plus the booking mail; a `meeting` kind. | S12, S36 | B |
| i4 | Investment | One update sent to 12 investors, 0 replies in 10 weeks | `wave_gone_silent` | One wave subject judged once. | S09, S21.U1 | D |
| i5 | Process | 6 mails bounced, 3 of them to investors | `delivery_failure` | Mailer-daemon notices not junked; each bounce made a card on its thread. | S06, **N4** | B |
| i6 | Investment | A deck request answered the same day (done) | resolved `reply_owed` | Window back to March; the resolution claim from sent mail. | S09 | A |
| s1 | Sales | The one prospect who replied (benchmark ask), never answered | `reply_owed` / `dormant_commitment_reopenable` | Window back to April; a quiet file re-looked at. | S09, S21.U2 | D |
| s2 | Sales | 27 of 28 prospects silent since Mar–Apr | `wave_gone_silent` (outbound) | Wave subject for outbound proposals; window. | S09, S21.U1 | D |
| b1 | Business | Two new Boardy intros waiting for a yes | `decision_waiting_on_a_person` | Boardy not archived; a brief line naming Boardy. | S02.U4, S06.U4, S12 | A–B |
| b2 | Business | Two partner calls, no written next step | `meeting_without_follow_through` | Calendar bookings reaching L3; a `meeting` kind. | S12, S36 | B |
| b3 | Business | A stalled intro since July (auto-close) | `outbound_awaiting_reply` | Boardy promoted; window back to July. | S06.U4, S09 | A–B |
| c1 | Process | Startup India correction; half the complaint bounced | `obligation_falls_due` | A government sender protected; Founder Office `registrations-and-recognition` (draft, labelled); the bounce link. | S02.U4, S23.U2, **N4** | D |
| c2 | Process | A tool subscription renews in 6 days | `obligation_falls_due` (vendor renewal) | Stripe renewal notices not junked; the vendor-renewal play. | S06, S23.U3 | D |
| h1 | Hiring | An offer whose answer is not in mail | `outbound_awaiting_reply` with partial coverage, as a question card | Typed unknowns (S16.U3, held); Screen moments (migration 0250 applied). | S09, S16, S02.U2 | C |
| l1 | Funding | Programme Round 2 result outstanding (snoozed) | `outbound_awaiting_reply` | A programme sender protected; window back to July. | S02.U4, S09 | A–B |

### The 10 goals

| Goal (short) | Category | How the brain should produce it | Progress basis | Steps |
|---|---|---|---|---|
| Raise the pre-seed | Investment | In-motion investor files → proposal (S27.U1 drafter today) → G1 goal on approve | counted: funds by stage | S27, S28–S30 |
| Accelerator reconsideration (i1) | Investment | L2 proposes from the conditional reply (F72) | unknown until the accelerator decides | S29 |
| Complete the programme | Funding | Programme threads + calendar | counted: programme steps | S27, S28, S30 |
| Get into an accelerator | Funding | Application threads grouped | unknown until an offer | S27, S28 |
| Paying design partners | Sales | Outreach waves + replies | counted: replies of outreach | S21, S28, S30 |
| One verified traction number | Progress | The **N1** conflict | blocked until a billing source exists | N1, S30 |
| Reviewed YC application | Projects | Review thread | counted: plan steps | S27, S28 |
| Boardy intros → partners | Business | Intro threads | counted: calls booked of intros | S06.U4, S28 |
| Startup India corrected | Process | Portal reminder + complaint | unknown (the portal is not readable) | S23, S28 |
| Founding engineer onboarded | Hiring | Offer thread | unknown (partial coverage) | S16, S28 |

The two proposals on `/preview` are a closing date for the round, and a programme as a goal. They come from S29.U3: L2 proposes, L3 admits it as a proposal, Rohit approves in one click.

---

## 3 · The order — what you do, step by step

Each phase ends with **Sync now → N5 parity → a line in 03-LOG**: which preview cards appeared, which are still missing, and each missing card's `why_no_card` (from `GET /v1/workstreams/{file_id}`, S18.U3).

### Phase A — today, no new code (Harsh, with Rohit's yes where marked)

1. **[S01.U3](02-PLAN.md#s01):** record the deployed brain SHA and date, and which env switches are set.
2. **[S02.U1](02-PLAN.md#s02):** put `<ORG>` on a non-expiring internal plan (`plan_status` active, `plan_expires_at` null, `grace_until` null). Then merge **S02.U5** (branch `g011-S02U5`).
3. **[S02.U2](02-PLAN.md#s02):** confirm migrations 0191–0251 are applied.
4. **Deploy `speedrun008` to `harsh/mvp`** only on a SHA whose CI is green (S03 rule). This carries wave 1 to production: S06.U1/U2, S14.U1, S18.U1–U3, S27.U1, S36.U1/U2, S05.U1 `daily_health`, S03.U1 `/health` SHA. Check that `/health` shows the SHA.
5. **[S02.U3](02-PLAN.md#s02) — Rohit's yes on A5/D1/A4:**
   - run `scripts/activate_tenant.py` for `<ORG>`: `founder_office` active, `expert_review` on, `l2_reasoning` in shadow;
   - leave `GENIOS_L4_LLM_DECISION_MAKER` unset;
   - log one dated line per flip, with its rollback.
6. **[S02.U4](02-PLAN.md#s02) — Rohit accepts the brief lines:**
   - lines naming Boardy, the Startup India portal, the accelerators and programmes he applied to, and the investors he is in conversation with (the names are on `/preview` → Company);
   - declare his self identity.
7. **[S09.U4](02-PLAN.md#s09) — Rohit picks the window; 365 days covers the preview:**
   - PATCH the Gmail and Calendar windows;
   - `resync_deleted_mail` dry run, Rohit reads it, then `--apply`;
   - rebuild.
   - ⚠ The first long backfill spends model budget, and the rule is no paid pass without Rohit's yes. Give him the estimate from the dry run first.
8. **[S06.U4](02-PLAN.md#s06):** promote Boardy's archived intros (dry run → Rohit → `--apply`).

**Expected after A:** f4, i6, b1, b3, l1 can appear on the old path. Write down what actually appears.

### Phase B — L1 words and the bundle (Claude builds, Harsh deploys)

- **[S12](02-PLAN.md#s12):** Rohit picks the new kinds (recommended: introduction, meeting, investor_interest, application_status); Claude builds them end to end.
- **[S13](02-PLAN.md#s13):** the bundle and the evidence loop. Harsh arms `GENIOS_NEED_FETCHERS` per S13.U4.
- **N4:** the bounce card.

**Expected after B:** f1, f2, i3, i5, b2.

### Phase C — L3 holds the work as one file

- **[S15](02-PLAN.md#s15):** one counterparty, one file, one live situation.
- **[S16](02-PLAN.md#s16):** memory holds what was said. S16.U3 merges once the replay harness pins knowledge time.

**Expected after C:** h1, and fewer duplicate or held cards.

### Phase D — L2 judges like the expert on the preview

- **[S20](02-PLAN.md#s20):** held cards in the founder's words.
- **[S21](02-PLAN.md#s21):** the wave subject, quiet files re-looked at, seeds become files.
- **[S23](02-PLAN.md#s23):** Founder Office reaches founder work — renewal, registration, the labelled drafts.
- **[S24](02-PLAN.md#s24):** a situation exists only after L2's judgment.
- **[S25.U3](02-PLAN.md#s25):** `l2_cards` on for `<ORG>`, one type at a time — investor outreach and awaiting reply first. Run a week side by side with `l2_shadow_report`.

**Expected after D:** i2, i4, s1, s2, f3, c1, c2.

### Phase E — goals

- **[S26.U1](02-PLAN.md#s26):** Rohit's goal decisions.
- **[S27.U3–U4](02-PLAN.md#s27):** the Goals page shows the drafter's proposals; Rohit approves.
- **[S28](02-PLAN.md#s28)–[S31](02-PLAN.md#s31):** the goal object, goals in the judgment, L2 proposals, goal↔situation links, progress, the goal on every card, one-click approve.
- **N2:** the category on goals and cards.

**Expected after E:** i1 with its goal; all 10 goals; the 2 proposals.

### Phase F — the card and the website match the preview

- **[S34](02-PLAN.md#s34):** the card writer — subject, steps, the 5-line draft, the goal line.
- **[S35](02-PLAN.md#s35):** queue, quotes, delegate, versions.
- **[S39](02-PLAN.md#s39):** no made-up numbers.
- **N3:** the dashboard reads categories.
  - Cards page: filter chips by category; lanes in the preview's order (conflict, decide, answer, waiting).
  - Goals page: Admin, then category, then goal, then cards; other domains locked.
  - Home: the preview's sections fed by `daily_health` (S05.U1) and the goal routes.
  - **Dummy-first rule:** `/preview` IS the dummy. Rohit confirms "make the real pages like /preview" before real files change, and confirms again after a look at a local render.
  - **Then N1:** the traction conflict reaches the card.

**Done when:** N5 shows ≥ 18 of 20 preview cards and 10 of 10 goals live, or each missing one has a named reason Rohit accepts. Then **N6**.

---

## 4 · Units this file adds (not yet in 02-PLAN)

They take step numbers when 02-PLAN is next revised. One writer per file, as always.

| Unit | What | Files | Done when | Owner |
|---|---|---|---|---|
| **N1** | **Own-claim ledger and conflict.** A quantitative claim in the founder's **sent** mail (metric, value, unit, period, date, recipients) becomes a `company.<metric>` fact on the tenant node at rank 2. A second, different value of the same metric within 120 days opens a `discrepancies` row and a conflict-lane card naming who received which value. GeniOS never picks the true one. | `genios_engine/capture/extract/self_claims.py` (new), `genios_engine/context/pipeline.py`, `genios_engine/reason/l2/inputs.py`, `tests/context/test_own_claims_conflict_pg.py`, a synthetic golden case F73 (no real names, per `REAL_NAMES`) | Two sent mails with "$10k ARR" and "$5K MRR" produce one conflict card with both values and their recipient counts. A third identical value adds no card. A received mail's number does not count as an own claim. Mutation: dropping the sent-only filter turns it red. | claude |
| **N2** | **Admin categories.** A category on goals and cards, derived by code from the capability via a reviewed map in Plane D. The categories: investment, funding, business, sales, projects, progress, process, hiring. | `Domain Expertise/Admin Expertise/registry/category-map.yaml` (new, reviewer stamp), `genios_engine/packs/compiler/`, `genios_engine/deliver/card_builder.py`, `genios_engine/api/goal_routes.py`, tests | `GET /cards` and `GET /v1/goals` carry `category`; an unmapped capability gives `null`, never a guess; a test pins every map entry to an existing capability. | claude |
| **N3** | **Dashboard reads categories and matches `/preview`** (after Rohit's go) | dashboard `src/app/dashboard/cards/page.tsx`, `src/product/internal/dashboard/goals/*`, `src/lib/card-read.ts` | A local render against a stand-in brain matches the preview's Cards and Goals pages. `tsc` and `next build` are green. Rohit approves. | claude |
| **N4** | **A bounce becomes a card.** A delivery failure that `context/delivery.py` already links to its thread becomes one "mail never arrived" card per recipient. Re-sending needs approval. | `genios_engine/context/delivery.py`, `genios_engine/deliver/card_builder.py`, `tests/context/test_a_bounce_is_a_card_pg.py` | A planted mailer-daemon notice on a thread gives one card naming the recipient. A second bounce on the same thread updates that card. The gate keeps DSNs (they are not junk). | claude |
| **N5** | **Preview parity check.** Compares live `GET /cards?state=open` and `GET /v1/goals` for `<ORG>` with the preview's expected list. That list is kept **outside this public repo** and is read from `PREVIEW_EXPECTED_PATH`. | `scripts/preview_parity.py`, `tests/scripts/test_preview_parity.py` | Prints appeared / missing / extra. For each missing card it gives the file's `why_no_card`. Exit code 0 only at ≥ 18/20 cards and 10/10 goals. The hermetic test uses a synthetic list. | claude |
| **N6** | **Retire `/preview`** | dashboard `src/app/preview`, `src/app/api/preview`, `src/server/ideal-preview-html.ts`, the sidebar entry | After N5 passes and Rohit agrees: the route goes, and the module holding his private mail is deleted from the dashboard repo (and from history if he asks). | claude + Rohit |

---

## 5 · Rules that still apply

- New architecture only, built beside, never instead. A switch flips only when the new path is at least as good: [01-RULES](../GeniOS-008/01-RULES.md), and [00-START-HERE](00-START-HERE.md) here.
- No production read without Rohit's yes, and no paid pass without his spend yes. Every paid pass starts with a 1–2-call probe.
- Only green SHAs reach `harsh/mvp`. Check `/health` after every deploy.
- Every code unit has its own tests plus a mutation proof. Full suites run in CI.
- Golden cases never name real people or firms (`REAL_NAMES`): use synthetic analogues of the preview's cases.
