> **Created:** 2026-09-10 · **Status:** Active — unit-level credit system built and proven; two pricing decisions open (§6)

**Purpose:** Decide and implement what a credit is, where it is charged, and how the ingestion lane — which is the bigger spender — is metered without being charged to the customer.

---

## 1. The question this answers

> "Agar sync karte samay 4 LLM call ho rahe hain har layer pe, to 1 email = 4 credit? Ye to kuch hai nahi."

Correct instinct. Measured against the code rather than assumed, here is what one email actually costs.

### LLM calls on the sync path

| Stage | Batched? | Calls per email | Runs on |
|---|---|---|---|
| L1 junk gate (`capture/gate/relevance.py`) | yes, **12/call** | 1/12 | unknown senders only — a known sender is whitelisted, no spend |
| L1 ESQE relevance (`capture/esqe/relevance.py`) | yes, **20/call** | ≤1/20 | only items the deterministic rules could not decide |
| L1 semantic extraction (`capture/semantic/extractor.py`) | no, per chunk, max 2 | 0 today | **dark in prod** — `l1_semantic_activation` is empty |
| L2 extraction (`context/extract/extractor.py`) | no, 1 + 1 repair | ~1 | only emails that PASS the gate (~27% measured on the pilot); content-hash cached, so a duplicate is free |
| L2 lifecycle / L3 / L4 | — | 0 | per situation and per org, not per message |

So it is **not** 4 calls per email. It is about **0.35 calls per captured email** — one twelfth of a gate call, plus one extraction for the ~27% that survive it.

### What that costs (Haiku 4.5 at list, ₹83/$)

| | tokens | ₹ per email |
|---|---|---|
| Gate share (2,189 tok / 12 emails) | 182 in | **₹0.027** |
| L2 extraction (only the 27% that pass) | 2,809 in / ~900 out | ₹0.485 → **₹0.131** amortised |
| **Total per captured email** | | **≈ ₹0.16** |

| Mailbox | LLM calls | Cost |
|---|---|---|
| 500 | 176 | ₹80 |
| 1,000 | 353 | ₹161 |
| 3,000 | 1,060 | **₹482** |
| 10,000 | 3,533 | ₹1,605 |

---

## 2. The design: charge by UNIT, and only for work that produced something

A credit is divisible. The store keeps **points** (100 points = 1 credit) the way money keeps
paise, so every balance and ledger row is a whole number and no float reaches the database, while
the API and the customer see two decimals.

### The unit table

| Unit | Credits | Why |
|---|---|---|
| Email scanned, junk gate dropped it | **0** | we did work, they got nothing |
| Email read into the context graph | **0.2** | this is the work that produced something |
| Attachment page read | **0.3** | a separate unit of work |
| Same message synced again | **0** | a message is read once, ever |
| Question | **1** | |
| Analyze | **1** | |
| Deep analyze | **2** | the bigger model |
| Draft | **1.5** | a deliverable, not an explanation |
| Cached answer | **0** | nothing was recomputed |
| Feedback | **0** | telling us we were wrong must never cost money |

Nothing exceeds 2 credits. The ladder is deliberately shallow — a customer should be able to hold
it in their head, and a click that costs five of something is a click people stop making.

**A noisy mailbox costs LESS, not more.** Same 5,000 messages: half spam is charged half as much.
This is the opposite of a flat per-email rate, which bills the customer for the spam we filtered.

### One row per sweep, carrying its count

Ingestion is charged in one ledger row per sweep with `units` on it — `1,240 × message_read =
248 credits` — not 1,240 rows and 1,240 writes on the ingestion path. The count travels with the
amount because a charge the customer cannot decompose is a charge they cannot check.

### A real free account

| | Credits |
|---|---|
| Signup | 3,000 |
| First sync: 5,000 mails — 2,500 junk (free), 2,500 read, 100 attachment pages | −530 |
| 50 questions + 5 deep analyses + 10 drafts | −75 |
| **Left** | **2,395** |

Sync takes ~18% of the plan; the rest stays for intelligence.

## 3. The plans

| | Free (trial) | Individual | Startup | Growth | Enterprise |
|---|---|---|---|---|---|
| **Credits / period** | 3,000 | 10,000 | 100,000 | 300,000 | 1,000,000 |
| Period | 15 d | 30 d | 30 d | 30 d | 30 d |
| Seats | 1 | 1 | 5 | 15 | 50 |
| Domains | 1 | 1 | 3 | 10 | 25 |
| **Sync messages / period** | 1,000 | 5,000 | 50,000 | 150,000 | 500,000 |
| Daily credit ceiling | 600 | 1,002 | 10,002 | 30,000 | 100,002 |
| Ingestion $/day | $1 | $3 | $15 | $40 | $100 |
| Price (INR, unchanged) | — | ₹4,500 | ₹25,000 | not set | sold by hand |

`early` and `hustler` resolve to `individual`, so live rows do not silently downgrade.

### Credit prices per action

| Action | Credits | Why |
|---|---|---|
| `intelligence_query` | 1 | ~1,400 in / 70 out on Haiku ≈ ₹0.12 |
| `intelligence_analyze` | 1 | same prompt shape |
| `intelligence_analyze` `deep=true` | 4 | Sonnet 5 at $3/$15 vs Haiku $0.80/$4 ≈ 3.7× |
| `intelligence_draft` | 2 | output-heavy, and a deliverable rather than an explanation |

Cache hits are free on both query and analyze. A replay is free — every charge is idempotent on the decision's cache key.

---

## 4. The ingestion bound, and why it is a count

Two ceilings guard ingestion and they answer **different** questions:

| Ceiling | Question | Clears |
|---|---|---|
| `sync_messages` (new, `platform/quota.py`) | how much mail, this period | at the next billing period |
| `ingest_usd_day` (`billing.plan_ingest_usd_cap`) | how much money, today | at midnight |

A backfill can sit inside the dollar ceiling and still be a free-plan tenant pulling a 40,000-message mailbox; the reverse is also true. One number cannot express both.

**Counted from `source_events.captured_at`** — the row that proves a message was actually taken in, not a connector's page count which includes everything dedup threw away. Counted from the org's **own** billing period, not the calendar month, so a plan bought on the 28th does not get two days of quota for its first month.

**Trimmed, never refused.** When a sweep finds partial headroom the page budget is cut to what the plan still allows, rather than the connection being skipped: half a mailbox read is worth more than none, and the remainder is still there when they upgrade.

**Fails open, everywhere.** A meter that cannot be read must never be the reason a customer's mail stops arriving.

---

## 5. What each plan actually costs us, at 100% burn

| Plan | Revenue | Credits cost | Sync cost | Total cost | Margin |
|---|---|---|---|---|---|
| Free | ₹0 | ₹360 | ₹160 | **₹520** | CAC |
| Individual ₹4,500 | ₹4,500 | ₹1,200 | ₹800 | ₹2,000 | **56%** |
| Startup ₹25,000 | ₹25,000 | ₹12,000 | ₹8,000 | ₹20,000 | **20%** |

Real utilisation is far below 100%, so these are liability ceilings, not expected cost. But the ceiling is what a plan promises, and Startup's is thin.

### The cost lever nobody has pulled

`build_prompt` in `context/extract/extractor.py` produces an **11,238-char prompt that is 99% identical between any two emails** — but the message sits in the **middle** of it, so only the first 1,260 chars are a cacheable prefix. Moving the untrusted message block to the **end** would make ~2,800 tokens cacheable at 10% of input price.

Honest sizing: input is ₹0.187 of the ₹0.485 extraction; **output (900 tokens) is ₹0.299, the larger half.** So prompt caching is worth roughly **30%**, not 5×. The bigger lever is the 900-token output ceiling — but that is a quality decision, not a billing one, and belongs to whoever owns L2.

---

## 6. Open — needs an owner decision

1. **Growth is priced at $299 on the pricing page but has no INR price in code**, because USD checkout does not exist (Stripe is not built; see `DELIVERY_BILLING_READINESS.md` D-7). It cannot be sold until it gets an INR price or Stripe lands.
2. **The pricing page's USD ladder does not support these allowances.** At $99 ≈ ₹8,200, Startup's 100,000 credits + 50,000 messages costs ₹20,000 at full burn — a loss. The current code keeps Startup at **₹25,000**, which is the number that works. If the price moves to $99, the allowance has to move with it (≈30,000 credits) or the ceiling is loss-making.
3. **Tool access per plan** (Core / Core+premium / All) from the pricing page — deliberately not built here; agreed to discuss separately.

---

## 7. Proven

- `tests/test_billing_plans.py` — 18 hermetic contract tests: one plan table, no rival tables, ladder never goes backwards, ingestion never appears in the credit price table, old tier names still resolve.
- `tests/test_sync_quota.py` — 9 tests on real Postgres: counting, period reset, exhaustion, headroom, bigger plan buys a bigger mailbox, **ingesting never moves the credit balance**, unreadable meter fails open.
- Full hermetic suite: **9,198 passing**, zero regressions (23 pre-existing failures unchanged).
- Migration `0128_sync_quota_index.sql` — without it the meter is a sequential scan of the largest table on every sync page.

**Plan alignment:** user-facing credits stay on the intelligence surface only (§2); no new Celery periodic task — the meter is read inline on the existing in-process sweep, because the broker is a quota-limited Upstash Redis.
