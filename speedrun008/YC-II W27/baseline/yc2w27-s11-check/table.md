# STEP-11 check — where each founder case's work lands in L2 (2026-10-09, at `353d06ea`)

Replayed from the cassettes through the real chain, every case, no model spend (`measure_expertise.py`; one JSON per case in `out/`, not kept). Only Admin is active (`l3_activation`: `admin:on:system:onboarding`). Situations per domain, how the cards were made, and the board's verdict.

| Case | Verdict | Situations by domain (fundraising ones are dark) | Cards (domain · rule) |
|---|---|---|---|
| F01 A government portal moves the founder's live application | fail (reasoning) | admin 1, fundraising 1, sales 1, support 1 (investor_relationship) | — |
| F02 One application across four mails: the same card updates | fail (reasoning) | admin 4, fundraising 2, sales 2, support 2 (investor_relationship) | — |
| F03 A connector introduces an investor, then nudges twice | pass | admin 3, sales 2, support 3 | general · unanswered_email |
| F04 The introduced contact replied the same day; the reply is  | pass | admin 2, sales 1, support 2 | general · unanswered_email |
| F05 The introduced contact replied five days later; the reply  | pass | admin 3, sales 2, support 3 | general · unanswered_email |
| F06 The introduced contact asks when to meet | pass | admin 3, sales 2, support 3 | general · unanswered_email |
| F07 After a call with an introduced contact: was anything prom | fail (reasoning) | admin 4, sales 3, support 2 | admin · account_admin, admin · meeting_follow_through |
| F08 Two introductions nobody answered | not_expressible | admin 4, sales 2, support 4 | — |
| F09 The connector answers the founder's reply with its own ask | fail (reasoning) | admin 1, fundraising 1, sales 1, support 1 (investor_relationship) | — |
| F10 An investor follows up after a demo day and asks for the d | pass | admin 2, fundraising 1, sales 2, support 3 (investor_relationship) | general · unanswered_email |
| F11 An investor reaches out and asks whether the founder is ra | fail (reasoning) | admin 1, fundraising 1, sales 1, support 2 (investor_relationship) | — |
| F12 An investor's question before a booked call — a prep card  | pass | admin 4, sales 3, support 3 | general · unanswered_email |
| F13 An investor asks for traction metrics before his partners' | pass | admin 2, sales 1, support 1 | admin · account_admin |
| F14 An investor who asked for real news only — the right move  | not_expressible | admin 5, fundraising 1, sales 3, support 4 (investor_relationship) | — |
| F15 The founder's outreach to five funds, eight weeks without  | fail | admin 18, fundraising 5, sales 3, support 3 (investor_relationship) | — |
| F16 The founder's mail to a fund bounced | fail (reasoning) | admin 1, fundraising 1, sales 1, support 1 (investor_relationship) | — |
| F17 An accelerator moves the founder's application to intervie | fail (reasoning) | admin 2, fundraising 1, sales 2, support 2 (investor_relationship) | — |
| F18 A state innovation fund opens a round — read and triaged | not_expressible | admin 1, sales 1, support 2 | — |
| F19 An incubation cell: three people, three asks | fail (reasoning) | admin 3, sales 2, support 5 | general · unanswered_email ×2 |
| F20 A foundation sends its newsletter and a meetup invite | not_expressible | admin 1, fundraising 1, sales 1, support 1 (investor_relationship) | — |
| F21 A management school's enterprise centre writes twice | not_expressible | admin 2, sales 2, support 4 | — |
| F22 A university startup cell announces a seed grant | not_expressible | admin 1, sales 1, support 2 | — |
| F23 A state startup mission writes four times | not_expressible | admin 4, sales 4, support 3 | — |
| F24 An accelerator's assignment and review — each due date see | fail (reasoning) | admin 3, fundraising 1, sales 3, support 6 (investor_relationship) | general · unanswered_email |
| F25 One job offer: one file and one card, not six | pass | admin 8, sales 2, support 2 | admin · dependency_stated |
| F26 A partner proposes a call time, then confirms it | pass | admin 3, sales 2, support 3 | general · unanswered_email |
| F27 A partner's open question before a booked call | fail (reasoning) | admin 4, sales 3, support 3 | admin · account_admin, general · unanswered_email |
| F28 A partner asks for the security questionnaire before a boo | pass | admin 4, sales 3, support 3 | general · unanswered_email |
| F29 Two calls with a partner in one day: prep before, follow-u | fail (reasoning) | admin 8, sales 8, support 4 | general · unanswered_email, admin · meeting_follow_through ×2 |
| F30 The founder's own promises on WhatsApp belong in their fil | not_expressible | admin 1, sales 2, support 1 | — |
| F31 A cohort session of fifty founders: no recap, only the ass | pass | admin 1, fundraising 1, sales 1, support 2 (investor_relationship) | general · unanswered_email |
| F32 Program newsletters are archived, never a card | pass | admin 1, sales 1, support 2 | — |
| F33 Vendor receipts and marketing are archived, never a card | pass | admin 1, sales 1, support 1 | — |
| F34 Co-founder matching digests and a fellowship newsletter ar | pass | admin 1, sales 1, support 3 | — |
| F35 A review notice that says no fee applies is never a paymen | pass | admin 1, fundraising 1, sales 1, support 1 (investor_relationship) | — |
| F36 The founder's own sent mail is never 'awaiting reply' from | pass | admin 4, sales 2, support 2 | — |
| F37 The connector is never the person to reply to | pass | admin 1, fundraising 1, sales 1, support 2 (investor_relationship) | general · unanswered_email |
| F38 A question answered on another channel is not owed again | pass | admin 2, sales 1, support 2 | — |
| F39 The founder's own availability proposal is not a deliverab | pass | admin 3, sales 1, support 1 | — |
| F40 A meeting nobody confirmed took place is never recapped | fail | admin 4, sales 3, support 1 | admin · admin_contact, admin · meeting_follow_through |
| F41 Your own company address is never someone you wait on | pass | admin 4, sales 2, support 2 | — |
| F42 An investor's ask that names the founder is about the inve | pass | admin 2, sales 1, support 1 | admin · account_admin |
| F43 Your own pitch names the thread after the investor, never  | pass | admin 1, fundraising 1, sales 1, support 1 (investor_relationship) | — |
| F44 An investor writing from Gmail is not one of us | pass | admin 2, fundraising 1, sales 2, support 3 (investor_contact) | general · unanswered_email |
| F45 The founder answers an investor's questions at several spe | not_expressible | admin 4, sales 3, support 2 | — |
| F46 An investor answers in the founder's other mailbox - both  | pass | admin 4, fundraising 1, sales 1, support 2 (investor_relationship) | general · unanswered_email |
| F47 A pitch bounced, in the shape Gmail sends it - the report  | fail (reasoning) | admin 1, fundraising 1, sales 1, support 1 (investor_relationship) | — |
