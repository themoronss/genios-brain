# 01 · What is happening: the detailed reasoning

**Written for:** Rohit first, then Harsh and the agents.
**Measured on:** a local copy of the design partner's org, cut from production at 2026-10-28 12:45 UTC. Code at `harsh/mvp` `7d2c3615`. Every number here comes with its query in [06](06-MEASUREMENTS.md).
**No names:** the ideal cards are referred to by their ids in the private ideal file and by a short description.

---

## §1 · In one paragraph

GeniOS's brain, the L2 model, thinks well. When it was asked about the accelerator application, it reached almost the same conclusion as the Claude session that made the ideal cards. The problems are around the brain:
1. It is handed mail grouped by **sender**, not by **piece of work**.
2. It is woken only when **new mail arrives**, never when something should have happened and didn't.
3. It is given **no company context**: no goals, no "who we are", no expert playbook.
4. When it is right, a **checker often throws its answer out** over wording.
5. Most important: **whatever it concludes is never saved.** The next time, it starts from zero and re-reads everything.

Because of the last point, the cards the founder sees come mostly from simple rules, not from the brain.

---

## §2 · The example we follow

The ideal card `i1`, an accelerator application:
- The accelerator rejected the application on 6 Aug.
- On 7 Aug the evaluator replied: send real updates and "we're always happy to take a look and reconsider".
- The founder sent three updates (11, 13 and 26 Aug). Each one gave a different traction number.
- There has been no reply since.
- The ideal card reads: **"Send one update with a new, checkable fact, then stop until they answer."**

Below, this mail's story is followed through every stage of GeniOS, as it runs today.

---

## §3 · The journey, stage by stage

```
mail ─► 1 gate ─► 2 labels ─► 3 filing ─► 4 notes ─► 5 situations ─► 6 thinking (L2) ─► 7 checker ─► 8 saving ─► 9 cards
                                                                                                                  └► 10 goals
```

### Stage 1 · The gate (L1): which mail is kept

**Should:** keep everything that could matter to the company.

**Does:** it kept all of the accelerator's mails. Across the whole mailbox:
- of 1,829 mails, **1,193 (65%)** went on to reasoning;
- **636 (35%)** were archived, judged only by the sender, the Gmail tab (Promotions, 241) or bulk headers;
- 547 attachments were not read (calendar invites, PDFs, images). The mails that carried them were read;
- nothing older than 180 days is captured.

**Cost to the founder:**
- an application's five "still incomplete" reminders were all archived (`f2`);
- three ideal cards rest on mail from March and April, which is outside the window (`i6`, `s1`, `s2`).

This is a real problem, but a smaller one than it first looked. GeniOS reads most mail.

### Stage 2 · Labels (L1): what each mail is about

**Should:** say what is happening: who asked what, who promised what, which numbers were stated.

**Does:** gives each mail one or more words from a fixed list of 14 types. The founder's update saying "Reached $5K MRR" was labelled `contract_renewal`. The most common label, by far, is `deadline_stated` (581 of 1,611).

**Cost:** the labels are too shallow to reason with, so the brain has to re-read the real mail anyway (stage 6).

### Stage 3 · Filing (L3): which mails belong together

**Should:** put every mail into the **piece of work** it belongs to (one application, one investor conversation, one introduction), whoever sent it and from whichever tool.

**Does:** files by the sender's company or person. The code says it plainly: "a file is one counterparty's correlations." The file is computed on the fly and never stored.
- **One piece of work, split.** The accelerator application sits in 2 files (admin and fundraising). The incubator's programme sits in 4.
- **Many pieces of work, lumped together.** The intro platform is one file holding 500 mails, 322 threads and 61 different people, each introduction its own piece of work.

**Cost:** the brain gets the wrong bundle. The intro platform's file is so big that the brain was stopped 31 times before starting, and never judged it. That loses a scout's referral (`f3`), two new introductions (`b1`) and a stalled one (`b3`).

### Stage 4 · Notes (L3): what code writes down about each file

**Should:** keep **one** up-to-date statement of where each piece of work stands.

**Does:** simple code writes separate notes, each from its own rule. About the accelerator, the graph holds all of these as "current":

| Note | Says | True? |
|---|---|---|
| outreach | waiting on the evaluator: 62 days, 2 follow-ups | ✅ |
| thread | the ball is in their court | ✅ |
| promise | the founder promised updated details by 13 Aug: **open** | ❌ sent on 11, 13 and 26 Aug |
| dependency | their decision is **waiting on the founder's details** | ❌ same reason |
| condition | their offer to reconsider, with the quote | ✅ |

Nothing decides which note is true now, and nothing ever closes a note:
- **all 87** promises in the graph are still open (83 past their date);
- **208 of 212** questions are still open;
- **40 of 44** "conflicts" are about dates, mostly rescheduled meetings and dates quoted from older mail.

**Cost:** the old rule engine turned the wrong note into a card: **"you are 71 days late"** sending the updates, which had already gone out.

### Stage 5 · Situations (L3): what the rules decide is going on

**Should:** a situation is the brain's reading of a piece of work. Atlas v2 says "the situation is formed by reasoning".

**Does:** rules form situations from a fixed list of types, one per file and domain, and put them to sleep after a 45-day default.
- The accelerator application is two situations, `investor_relationship` and `account_admin`, both "dormant".
- 1,528 situations exist, 667 of them support-desk "first response overdue" situations, although Support is off for this org.

**Cost:**
- The pieces of work that most need a nudge are exactly the quiet ones, and those are the ones marked dormant.
- An investor's unanswered traction question (`i2`) and a stalled introduction (`b3`) were never judged at all.

### Stage 6 · Thinking (L2): the brain

**When it thinks:** only when new mail arrives. All 138 runs were started by new mail; none by a missed date or by silence. Yet **13 of the 20 ideal cards are about something that did not happen**: an evaluator who went quiet, a question left unanswered, a follow-up never sent, a referral that never came.

**What it is given:**
- the whole file every time: on average 70,000 characters, up to 280,000;
- **no company brief** (138 of 138 dossiers say so);
- **no expert playbook** (38 of 38 current dossiers). The playbook is chosen by the kind of work, and the kind comes only from brief lines the founder has accepted. None have been;
- a warning that the read was cut short, so it must "never say something is absent". That is wrong for the founder, whose best insights are absences;
- only one line about its own previous judgment of the same file: "valid, mode act".

**How often:**
- re-reading is expensive, so the brain has its own budget of about $2 a day. It hit that limit every day, so about 12 files are judged a day;
- only **80 of 264** files have ever been judged;
- **16 of the 20** re-judgments happened with no new mail in between.

**What it produces:** good reasoning. On the accelerator it:
- named the stalled reconsideration;
- noticed that the founder's traction numbers rose between updates and called it a credibility risk;
- proposed one short follow-up, with a draft, and a time to stop.

When it was unsure it chose "find out" (41 of 86 results), mostly because it was told never to assert an absence.

### Stage 7 · The checker: is every claim backed by the mail?

**Should:** stop the brain from inventing facts.

**Does:** checks word by word against raw mail lines. It **held 66 of 86** results:
- 57 of 63 with the older check (22–27 Oct);
- 9 of 23 with the newer one (from 27 Oct).

The accelerator answer was held for three reasons:
- the claim named the dates of the updates, and the checker could not match those dates to the exact lines quoted;
- it treated the evaluator's first name and "UTC" as unknown names;
- it treated the company's own product name as unknown, because the org record holds the legal name.

**Cost:** instead of the right card, the founder saw **"What is the next step with them? We held the one we found…"**.

### Stage 8 · Saving: the missing stage

**Should:** the brain's conclusion becomes the current state of the piece of work, so the next look starts from it. Atlas v2: "L3 only remembers what L2 concluded."

**Does:** nothing is saved.
- The admission code is marked "SHADOW: nothing here touches the situations".
- Joining two files has "no applier yet".
- 30 interpretations were written, and nothing reads them.
- **Not one of the graph's 16,792 facts came from the brain.**

Example: on 28 Oct the brain concluded that a government registration portal file is "a portal correction, not an investor relationship". It was logged, and the file is still an investor relationship.

### Stage 9 · Cards (L5)

**Should:** one card per piece of work that needs the founder, made from the brain's conclusion.

**Does:** three card makers run at once.

| Card maker | Live cards |
|---|---|
| old signal rules | 38 |
| old situation rules | 33 |
| the brain (22 of them "held" questions) | 31 |
| other | 1 |

On top of that:
- the same subject repeats up to 9 times;
- about 13 cards show the checker's internal text;
- 6 name the founder in the third person.

### Stage 10 · Goals

**Should:** goals tell GeniOS what matters most.

**Does:** 7 goals were proposed (4 by the weekly drafter, 3 by the brain). None is approved, so no card and no file is linked to any goal. The drafts are also built on stage 3's files: they count a government portal and an incubator as investors.

---

## §4 · The one gap underneath everything

A good chief of staff keeps two kinds of memory:
- **the archive:** every email and every fact. GeniOS has this. The graph holds 16,792 facts and 2,352 relations, all timestamped;
- **the notebook:** one page per piece of work, saying where it stands now. *"Accelerator: rejected 6 Aug; open to updates; three sent, none answered; next: one update with a new fact, then stop."* **GeniOS does not have this.**

The architecture planned both:
- the **Evidence Graph**, which records what the sources said;
- the **Intelligence Graph**, which records what GeniOS concluded.

In production only the first exists. This one gap produces most of the other problems:

| Problem | Why the missing notebook causes it |
|---|---|
| It re-reads everything | Without a page, the only way to know where something stands is to read all of its mail again, every time |
| It is expensive, so it is capped | Re-reading costs money, so about 12 files a day; most files are never looked at |
| It can't notice silence | Noticing "they should have replied by now" needs a saved expected-by date. No page, no date |
| Wrong notes stay wrong | The brain understood that the promised updates were sent, and had nowhere to write it |
| The checker throws out good answers | With no trusted page to check against, it can only match words in raw mail |
| The rules make the cards | The brain's understanding goes nowhere, so the rules' notes are what turn into cards |
| Goals, kinds and identity are stuck | They are conclusions too, and nothing may use a conclusion until someone approves it |

The filing problem (stage 3) is the second root. The page has to be about a **piece of work**, not about a sender. Otherwise even a saved page sits in the wrong place.

---

## §5 · Three earlier phrases, made precise

- **"It can't read."** Mostly not true. It reads about two-thirds of mail. Archiving by sender or tab, and skipping attachments, is a real but smaller problem (stage 1).
- **"It can't reason over the context."** It can reason. It is handed the wrong bundle (stage 3), without company context (stage 6), at the wrong moment (only new mail), and the checker throws out good answers (stage 7).
- **"It reads again from scratch."** True, and this is the core: its conclusions are never saved (stage 8).

## §6 · What is NOT the problem

These are measured, so nobody fixes the wrong thing:
- **The model's intelligence.** On the accelerator, the brain's reading matched the ideal card.
- **The amount of data stored.** The graph is rich. The organisation is wrong, and the conclusions are missing.
- **Signals copied from quoted history.** Only 41 of 1,474 signals have no quote in new text.
- **Whole mails parked for an attachment.** No: 547 of 547 parked items are the attachments themselves.
- **The need for a memory product or a third-party service.** The missing piece is the conclusions GeniOS itself produces. They need about 1 MB for this org, in the same database.

## §7 · Each ideal card, and the stage where it is lost today

| Ideal | What it is about | Lost at |
|---|---|---|
| `p1` | four different traction numbers sent to different people | 4 + 8: the numbers are stored as plain amounts on the founder's person record and never compared |
| `f1` | the incubator's final review today | 3 + 9: the card points the wrong way ("share the review slots with them"), plus a question about another startup on the same panel |
| `f2` | an application left incomplete: finish or drop | 1: its reminders were archived |
| `f3` | ask the intro platform about a scout's referral | 3 + 6: the intro platform's file is too big; never judged |
| `f4` | waiting while a founder reviews the application doc | 7: held |
| `i1` | accelerator: one update with a new fact, then stop | 7: the right reading, held; 4: the old rule card "71 days late" |
| `i2` | answer an investor's traction question in three lines | 5 + 6: the file went dormant; never judged |
| `i3` | send the follow-up after an investor call | 7: held |
| `i4` | one update sent to 12 investors, no replies | partly found, late (28 Oct), as "follow up with 7" |
| `i5` | six emails bounced | 3 + 8: the bounce is recorded on the address and never reaches the waiting piece of work |
| `i6`, `s1`, `s2` | older investor and prospect threads | 1: before the 180-day window |
| `b1` | two new introductions waiting for yes or no | 3 + 7: one held, one never judged |
| `b2` | two partner calls, no written next step | 9: the brain chose "decision", but no card was made |
| `b3` | a stalled introduction: let it close | 5 + 6: dormant; never judged |
| `c1` | a registration complaint that reached only one inbox | 5 + 7 + 8: filed as an investor; held; the brain's correction was not saved |
| `c2` | a tool subscription about to renew | 2: read, but nothing recognised |
| `h1` | did the candidate accept the offer? | 5 + 7: filed as an investor contact; held |
| `l1` | a programme's round-2 result, still outstanding | 9: a good question card was made but left in the queue |

Score today (`ideal_card_gap.py`, matched on the counterparty): **8 of 20 cards found, 28 of 220 fields filled**. With the stricter reading above: 0 the same, 9 partial or wrong, 11 missing.
