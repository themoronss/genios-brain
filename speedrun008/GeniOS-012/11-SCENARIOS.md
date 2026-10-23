# 11 · Scenarios: for each kind of situation, what GeniOS must do live, and what makes it work

**Written for:** Harsh (to know what "ready" means per scenario), coding agents (the test cases to write), Rohit (what can be shown in the pitch as live vs as target).
**How to read:** each scenario names the ideal behaviour (what the local session did, or the Admin Atlas describes), the units that must be live for it (from files 03–08), its `/preview` cards where there are any, the synthetic golden case that proves it, and its status today.

Status: 🟢 works live today · 🟡 works partly (named) · 🔴 does not work live yet. Every scenario below is 🔴 or 🟡 on 23 Oct. The step that turns it 🟢 is named.

---

## A · The founder's own work (Rohit's org, `/preview`)

| # | Scenario | Ideal behaviour | Must be live | `/preview` | Golden case to write | Today → turns 🟢 after |
|---|---|---|---|---|---|---|
| A1 | **An investor passed, then offered to reconsider** | one card: what changed since, the new fact that makes now the moment, a 5-line draft, the pre-seed goal it moves | 365-day window (S09); Founder Office on (S02.U3) and labelled (S23.U2); one live situation (S15.U2); a quiet file re-looked at (S21.U2); the "today" block (U12-15); goals (S28–S31); card writer (S34.U3) | `i1` | F72 (exists in the plan, S28.U3) | 🔴 → Step 6 |
| A2 | **An investor asked for X; the reply did not give X** | "they asked for traction; your reply didn't answer it" | U12-08 + U12-16 | `i2` | new: synthetic ask + non-answer | 🔴 → Step 5 |
| A3 | **One update sent to many investors, no replies** | one wave card: "10 weeks, 0 replies; follow up the 3 warmest individually, drafts attached" | S21.U1 (L3 + L2) | `i4`, `s2` | new: 12 recipients, 0 replies, 70 days | 🔴 → Step 5 |
| A4 | **The founder told different people different numbers** | one conflict card: who got which number; GeniOS never picks the true one | N1a, N1b, conflict lane, card writer | `p1` | F73 (07's N1) | 🔴 → Step 7 |
| A5 | **A programme application is incomplete; two reminders** | "finish the application by <date>; these fields are missing" | portal sender kept (S02.U4 / U12-05); `application_status` (S12.U2); `program_applications` routed (U12-12) | `f2` | new: two portal reminders | 🔴 → Step 3 |
| A6 | **A panel or review on the calendar today** | prep: who is on it, what was promised last time, what to bring | meetings as events (U12-07); the meeting card | `f1` | new: today's external meeting with prior mail | 🔴 → Step 3 |
| A7 | **A call happened, nobody followed up** | "send the follow-up; here is the draft" | U12-07; `meeting_without_follow_through`; the follow-up card door (S36.U1 ✅) | `i3`, `b2` | new: past external meeting, no mail after | 🔴 → Step 3 |
| A8 | **Intros offered through an intro platform** | "two intros wait for your yes" | the intro platform kept (U12-05, S02.U4); old intros promoted (S06.U4); `introduction` type; `introductions` routed | `b1`, `b3`, `f3` | new: platform intro with List-Unsubscribe | 🔴 → Step 2 (old lanes), Step 5 (expert) |
| A9 | **Waiting on someone's review** | "waiting on X since <date>; nudge or wait" | only the chain running (Step 1) | `f4` | exists (awaiting reply) | 🔴 → Step 1 |
| A10 | **Mail that never arrived** | "6 of your mails bounced, 3 to investors; check the addresses" | N4 | `i5`, part of `c1` | new: planted DSNs | 🔴 → Step 4 |
| A11 | **A government registration needs a correction** | the obligation, the deadline, and that half the complaint bounced | portal kept; `registrations_and_recognition` routed (U12-12); N4 | `c1` | new | 🔴 → Step 5 |
| A12 | **A subscription renews in days** | "renews in 6 days at $X; keep, downgrade or cancel" | renewal notices not junked; S23.U3 | `c2` | exists in the Admin pack (renewal) | 🟡 the play exists, the mail is junked → Step 5 |
| A13 | **A prospect replied once and was never answered** | "they asked for the benchmark in April; still unanswered" | 365-day window; customer kind (U12-13); quiet file re-looked (S21.U2) | `s1` | new | 🔴 → Step 5 |
| A14 | **An offer whose answer is not in mail** | a question card: "did they accept? the answer isn't in your mail" | typed unknowns (S16.U3 + U12-09); question cards (S36 ✅) | `h1` | new: offer sent, no reply, partial coverage | 🔴 → Step 5 |
| A15 | **A decision long answered** | shown as done, with the evidence | 365-day window; resolution from sent mail | `i6` | exists | 🔴 → Step 2 |
| A16 | **The founder's goals** | 10 goals, each with its cards and progress; 2 proposals to approve | Step 6 | Goals page | F72 + a synthetic founder with 10 works in motion | 🔴 → Step 6 |

---

## B · Every customer, any company (the Admin Possibility Atlas)

| # | Scenario | Ideal behaviour | Must be live | Today → turns 🟢 after |
|---|---|---|---|---|
| B1 | **Day one of a new customer** | connect Gmail + Calendar; 10-minute setup (roles, approvers, critical vendors, the people and programmes they work with); first situations within about an hour; first brief with ≤ 3 items, each with evidence and what was checked | onboarding writes what was set by hand for Rohit (see [12 §A](12-PRODUCTION-READY.md)): plan, switches, brief lines, window, self identity; the catch-up budget (U12-17) | 🔴 → Step 8 |
| B2 | **Commitments and follow-ups** (Atlas wedge 1) | a promise made in mail is tracked to proof; overdue promises name what they block | S16.U1 (every promise in memory); one live situation per file (S15.U2); the card writer | 🟡 promises exist for the file's own events only → Steps 4–7 |
| B3 | **Decisions and approvals** (wedge 2) | a stuck approval and its real reason; the right approver | org data: seats, reports-to, approval limits (S32.U3, L4); today no engine writer for org data | 🔴 → after Step 7 (S32) |
| B4 | **Meetings to actions** (wedge 3) | every action leaves the meeting with an owner; follow-through verified | U12-07; meeting notes or transcripts as a source (not connected today) | 🔴 → Step 3 for mail-and-calendar only |
| B5 | **Vendor and subscription renewals** (wedge 4) | the real decision date (expiry − notice − approval time), computed by a tool | S23.U3; the signed contract as a source (Drive, not connected) → an Investigation card asking for it | 🟡 → Step 5; contract terms need Drive |
| B6 | **A quiet day** | "checked and quiet: N threads, M meetings; nothing needs you", with what was not checked | the brief from `daily_health` and the coverage receipt (S10.U1); justified-silence receipts | 🔴 → Step 7 (S36.U3 one morning brief) |
| B7 | **A source is down or partly read** | the card says what was not checked; absence is never "it didn't happen" | coverage receipts per source (S10.U1); "stopped at 5,000 of N" | 🟡 the receipt exists, the founder never sees it → Step 2 |
| B8 | **A lapsed trial** | spending stops; the customer and the team are told | U12-01; Rohit's product call on read-only cards (D-12-1) | 🔴 → Step 1 |
| B9 | **A larger company with several seats** | the right card to the right person; a conclusion never shown wider than its evidence | org data (S32.U3); seat visibility (exists); approvers | 🔴 → after Step 7 |
| B10 | **Screen moments feeding company cards** | a promise typed in WhatsApp becomes a tracked commitment | Screen lanes A–E (built, defaults off); promotion into the graph only for activated orgs (Step 1); migration 0250 applied | 🟡 Screen is live on the desktop; the company half needs Step 1 |
| B11 | **Sales and Support domains** | the same machinery, other expertise | each domain passes the same bar as Admin (its own golden set, parity); Sales `default_on: false` until then | 🔴 by decision: Admin first |

---

## C · Scenes for the pitch and the product video

The video is made from `/preview`. To say it honestly:

| Scene | Say |
|---|---|
| The Cards page with the 20 cards | "This is what GeniOS produces when every layer works. We built it from the founder's own mail to show the target." Label: **Target**. |
| GeniOS Screen on WhatsApp | live today ("Live"). |
| A card's evidence, quotes and draft | target behaviour, from the founder's real threads ("Target"). |
| Goals with progress | target ("Target"); goals are proposed from the founder's work and approved in one click. |

When Gate 7 passes ([09](09-STEPS.md)), the same scenes can be re-recorded from the live product and labelled "Live".

---

## The scenario test set (what to add to the golden set)

Every 🔴 above gets **one synthetic golden case** before its step is called done, written by the unit that turns it green: F72 (A1), F73 (A4), and new cases for A2, A3, A5, A6, A7, A8, A10, A11, A13, A14, A16, B1, B6, B8. Each case is synthetic (no real names), lives in `tests/golden/`, and runs on both paths (the old lane and L2) until S25.U4 retires the old lane for its type. The board (63/4 on 23 Oct) is reported in 13-LOG after each step.
