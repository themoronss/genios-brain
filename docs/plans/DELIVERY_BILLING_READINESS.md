> **Created:** 2026-09-09 · **Status:** ✅ Done — P1–P9 all built and proven on a scratch Postgres (2026-09-10). Deployment is the only step left.

**Purpose:** Make the money lane — signup → login → trial → credits → deduct → expiry → upgrade/top-up → renewal — completely correct and provably working end-to-end, while Rohit owns the intelligence lane.

---

## 0. Scope split

| Lane | Owner | This plan |
|---|---|---|
| Intelligence (L1–L4 quality, correlators, packs) | Rohit | untouched |
| Delivery / monetisation (auth, plans, credits, gateway, meters) | this plan | everything below |

The seam between them is `billing.deduct()`. Intelligence work must never need to know the price of anything; this plan owns pricing and enforcement.

---

## 1. What exists today (code-verified)

**Working:**
- `POST /v1/auth/register` — creates org, 15-day trial, grants `PLAN_CREDITS["trial"]` = 10,000, writes a `credit_ledger` `reset` row, provisions seat + delivery surface, mints `gn_live_` key, returns JWT. Idempotent on email (409).
- `POST /v1/auth/login` — pbkdf2 verify, per-email throttle (10/5min, fails open), blocks `plan_status='suspended'`, returns JWT.
- `platform/billing.py` — single pool (`orgs.credits` + `orgs.topup_credits`), atomic drain (topup first), immutable `credit_ledger`, idempotency via unique `(org_id, idempotency_key)`, `activate_plan` idempotent on `payment_id`, Razorpay HMAC verify.
- `GET /api/org/{org}/billing/subscription` + `/invoices` + `GET /v1/billing/stream` (SSE live balance).
- Frontend: `/auth/signup`, `/auth/login`, `/dashboard/upgrade` (Razorpay checkout.js wired), `CreditsProvider` (one SSE per session), `CreditsBanner`.

**Charged today — exactly two places:**
| Endpoint | Cost | Idempotency key |
|---|---|---|
| `POST /v1/intelligence/query` | 1 credit | `q:{cache_key}` |
| `GET /v1/intelligence/draft` | 1 credit | `draft:{org}:{contact}:{yyyymmddHHMM}` |

---

## 2. Defects — the money lane is not closed

### D-1 · Four different plan vocabularies, and they contradict each other
| Table | trial | early | startup | growth | scale | enterprise |
|---|---|---|---|---|---|---|
| `billing.PLAN_CREDITS` | 10,000 | 10,000 | **100,000** | — | — | 1,000,000 |
| `account_routes._CREDIT_LIMIT` | 10,000 | **missing** | **2,000** | 10,000 | 50,000 | missing |
| `account_routes._SEAT_LIMIT` | 2 | **missing** | 5 | 15 | 50 | missing |
| `intelligence_routes._DAILY_QUERIES` | 200 | 1,000 | 5,000 | 20,000 | 50,000 | missing |

`early` is a **real, sellable plan** (₹4,500/mo in `PLAN_PRICES`) that is missing from the seat table and the credit table, so a paying Early customer falls to the `100`-credit default and the default seat cap. `startup` reads 100,000 in one file and 2,000 in another — a 50× disagreement on the ₹25k/mo plan. `growth`/`scale` are sellable in neither `PLAN_PRICES` nor `PLAN_CREDITS`; they are dead vocabulary.

**Fix:** one `PLANS` table in `platform/billing.py` — `{credits, seats, daily_queries, price_inr, price_usd, period_days}` per tier. Delete `_CREDIT_LIMIT`, `_SEAT_LIMIT`, `_DAILY_QUERIES`. A contract test asserts every tier in `PLAN_PRICES` has a full row and no route defines its own table.

### D-2 · Trial credits are unreachable by construction
Trial = 10,000 credits over 15 days, but `_DAILY_QUERIES["trial"] = 200`/day. Ceiling over the whole trial = 3,000. **7,000 of the 10,000 granted credits can never be spent.** Either number is defensible; both together are not.

**Fix:** set the daily ceiling from the plan's own allowance (abuse guard, not a second price), or drop the trial grant to what the trial can actually reach. Decide in §4.

### D-3 · Nothing ever expires a trial or a plan
No code path writes `plan_status='expired'`, sets `grace_until`, or reads `plan_expires_at` to refuse service. `auth.py` blocks only `suspended`. `scheduler.py` runs sync + card lifecycle + weekly L6 — **no billing tick.**

Consequences:
- A 15-day trial keeps working on day 400, until its 10,000 credits run out.
- `CreditsBanner` renders on `plan_status === "expired"` — a value the backend can never produce. **Dead UI.**
- `subscription.in_grace` is computed from `grace_until`, which nothing ever sets. **Always false.**

**Fix:** a `billing_tick` in the existing in-process scheduler (no new Celery periodic task — Upstash quota). Per tick: expire past-due plans → `expired` + `grace_until = now + GRACE_DAYS`; after grace → refuse billable calls; renew active paid plans at `credit_period_end`.

### D-4 · No renewal — a paid plan is a one-shot grant
`activate_plan` sets `credit_period_end = now + 30d` and resets `credits`. Nothing runs at that boundary. Month 2 of a ₹25k/mo Startup customer starts with whatever is left of month 1, and their invoice list shows one row forever.

**Fix:** same `billing_tick` — at `credit_period_end` on an `active` paid plan, reset `credits` to the plan allowance, roll `credit_period_*` forward, append a `reset` ledger row idempotent on `f"renew:{org}:{period_end}"`. Top-up pool is never touched (it rolls over — that is what customers pay extra for).

### D-5 · The extension's main endpoint is free
`/v1/intelligence/analyze` calls the LLM (Sonnet when `deep=true` — the most expensive call we make), calls `record_cost`, and **never calls `deduct`**. Every extension analyze is pure loss.

**Fix:** charge it. `deep` costs more than shallow (see D-6).

### D-6 · Flat 1 credit for calls that differ ~20× in cost
Haiku shallow query and a `deep=true` Sonnet analyze both cost exactly 1 credit. Credit price does not track spend at all.

**Fix:** a `COSTS` table keyed by `(endpoint, tier_of_model)` in `billing.py` — e.g. query 1, analyze 1, analyze-deep 3, draft 2. Never inferred from token counts at runtime (unpredictable for the customer); a fixed published table.

### D-7 · USD / Stripe checkout does not exist
`_create_order` only ever creates a **Razorpay** order. For `currency=USD` it sets `processor="stripe"` then immediately falls through to `order_id = dev_…; processor = "dev"` because no Stripe session is created. The frontend then checks `processor === "stripe" && checkout_url` — never true — and falls through to Razorpay `checkout.js` with `key_id: undefined`. **Every non-INR upgrade attempt silently fails.**

**Fix:** either build the Stripe Checkout Session + fulfil in the webhook, or remove USD from the UI until it is built. Recommend the latter for the trial (India-first), tracked as an explicit gap.

### D-8 · Both webhooks are stubs
`/v1/billing/webhook` and `/v1/billing/stripe/webhook` verify the signature and `return {"ack": True}`. No fulfilment. If a customer's browser closes between payment capture and the `verify` call, **they are charged and get nothing** — and no async path recovers it.

**Fix:** Razorpay webhook resolves `order_id` from the captured payment and runs the same idempotent `activate_plan` / `grant_topup` the verify route runs. The ledger's `payment_id` guard already makes the double path safe.

### D-9 · `/api/org/{org}/usage` reports numbers unrelated to billing
It counts rows in `decisions` since the 1st of the month and divides a hardcoded limit by 30. It never reads `credit_ledger` or the balance. So "period_used" can disagree with the actual credits spent in both directions, and `days_remaining`/`expires_at` are hardcoded `null` despite the columns existing.

**Fix:** rebuild on `credit_ledger` (`sum(-amount) where kind='deduct'` in the current period), grouped by `bucket`, plus real `expires_at` / `days_remaining` from `orgs`.

### D-10 · No per-bucket spend breakdown for the customer
`credit_ledger.bucket` is written (`query` / `draft`) but no customer-facing route reads it. Only `admin_routes` does. The user cannot answer "where did my credits go".

**Fix:** `GET /api/org/{org}/billing/ledger` — paginated rows + a per-bucket rollup for the period.

### D-11 · Ingestion LLM spend is invisible to billing
L1/L2 burn LLM on every sync (`capture/semantic/extractor.py`, `capture/gate/relevance.py`, `capture/esqe/relevance.py`, `context/extract/extractor.py`, `context/pipeline.py`, `deliver/render.py`, `packs/brains/org_rule_extract.py`, `reason/bundle/gate.py`). Only `context/pipeline.py` calls `record_cost`; none charge credits.

Per the working rule **user-facing credits are charged only on `/v1/intelligence/query`** — so not charging is correct. But it must be *bounded*, or a large mailbox on a trial is uncapped loss.

**Fix:** no credit charge. Add a per-org monthly **ingestion $ ceiling** by plan, read from `llm_costs`, enforced in the sync path; breach → stop ingesting and raise an ops alert. Charging stays out of the customer's face.

---

## 3. Build order — status

| # | Item | Defects | Status |
|---|---|---|---|
| P1 | One `PLANS` table; delete the 3 rival tables; contract test | D-1, D-2 | ✅ `platform/billing.py` |
| P2 | `COSTS` table; charge `analyze` (+deep multiplier); prices off one table | D-5, D-6 | ✅ |
| P3 | `run_billing_tick` on the in-process heartbeat: expire → grace | D-3, D-4 | ✅ |
| P4 | `refusal_for` enforced on query + draft + analyze | D-3 | ✅ |
| P5 | Webhook fulfilment (Razorpay), idempotent with `verify` | D-8, D-13 | ✅ one `_fulfil` path |
| P6 | Rebuild `/usage` on the ledger; add `/billing/ledger` + bucket rollup | D-9, D-10 | ✅ |
| P7 | Ingestion $ ceiling by plan | D-11 | ✅ `wiring.make_cost_governor` |
| P8 | USD removed from checkout (Stripe not built) | D-7 | ✅ refused at `_currency` |
| P9 | End-to-end proof against a scratch Postgres | all | ✅ §5, all 10 steps |

**Deployment note:** the webhook needs `RAZORPAY_WEBHOOK_SECRET` (or `RAZORPAY_KEY_SECRET`) set in
prod and `POST /v1/billing/webhook` registered in the Razorpay dashboard for `payment.captured`,
`order.paid` and `payment.failed`. Without the registration the browser return still fulfils —
it just stops being the only thing that does.

### The decided numbers

| | trial | early | startup | enterprise |
|---|---|---|---|---|
| Credits / period | 10,000 | 10,000 | 100,000 | 1,000,000 |
| Period | 15 d | 30 d | 30 d | 30 d |
| Seats | 2 | 5 | 15 | 50 |
| Daily credit ceiling | 2,001 | 1,002 | 10,002 | 100,002 |
| Ingestion cap | $3/day | $10/day | $25/day | $100/day |
| Price | — | ₹4,500 | ₹25,000 | — |

Action prices: **query 1 · analyze 1 · analyze-deep 4 · draft 2**. One credit is priced at roughly
one Haiku-class synthesis at list (~1,400 in / ~70 out ≈ $0.0015 ≈ ₹0.12). Deep analysis is Sonnet 5
at $3/$15 against Haiku's $0.80/$4.00 — ~3.7× on the same prompt shape — hence 4.

So a fully-burned 15-day trial is **10,000 credits ≈ ₹1,200 of query-side model spend**, on top of
an ingestion lane now capped at **$3/day ≈ ₹3,700 over the whole trial** (it was inheriting the
paying tenant's $25/day, i.e. up to ~₹31,000 to give the product away).

The daily ceiling is derived — `ceil(credits / period_days) × DAILY_BURST`, `DAILY_BURST = 3` —
so it is an abuse guard and never a second price. Two contract tests hold both ends: no granted
credit may be unreachable inside the period, and one day may not drain a whole period.

---

## 4. Decisions taken

1. **Trial** — 10,000 credits / 15 days kept, and the daily ceiling derived from it so all
   10,000 are reachable. Was: 200/day, i.e. 3,000 reachable of 10,000.
2. **Action prices** — query 1 · analyze 1 · analyze-deep 4 · draft 2 (deep raised from the
   proposed 3 to match the measured ~3.7× Sonnet/Haiku ratio).
3. **Post-grace** — hard 402 on billable calls, login and dashboard stay open. `suspended` is
   deliberately NOT used: `platform/auth.py` refuses it at login, and locking an unpaid customer
   out of the page they would pay on is the one failure that cannot recover itself.
4. **USD** — India-only. Stripe is not built, so USD is refused at `_currency` with
   `CURRENCY_UNSUPPORTED` instead of silently producing an unverifiable order.

## 4b. Found while building, not in the original audit

- **D-13 · A signed order could redeem any top-up pack.** `verify_topup` took the pack from the
  CALLER and only used the order row to flip a status, so a customer who had paid for a ₹25,000
  subscription could replay that same `order_id` with `pack="large"` and be granted 100,000
  credits — the repo's own test did exactly this and passed. Fulfilment now reads the org, the
  plan and the pack from the paid row and never from the request, on both the browser and the
  webhook path.
- **D-12 · Top-up prices displayed 100× too high.** `price_inr` is minor units everywhere in the
  billing API; both the upgrade page and the settings page rendered it raw, so the ₹2,500 Small
  pack advertised itself at **₹250,000** on its own buy button. Fixed in both.

---

## 5. Proof (P9) — what "working" has to mean

One scripted run against a **real scratch Postgres**, asserting at every step:

1. signup → org row, `credits = trial allowance`, one `reset` ledger row, seat + surface provisioned, JWT works
2. login → same org, throttle fires on the 11th attempt
3. `/billing/subscription` → balance == grant, plan == trial, correct `period_limit`
4. N queries → balance falls by exactly the published price each time; a **replayed** request charges nothing
5. `/usage` and `/billing/ledger` agree with `balance` to the credit
6. drain to 0 → next query is a 402, and `CreditsBanner` shows out-of-credits
7. top-up → balance rises; **replaying the same `payment_id` does not double-grant**
8. upgrade → tier + allowance + period set; replayed `payment_id` is a no-op
9. fast-forward the clock past `credit_period_end` → `billing_tick` renews, plan credits reset, **top-up pool survives**
10. fast-forward a trial past `plan_expires_at` → `expired` + `grace_until` set, banner shows expired, billable calls refused after grace

**Plan alignment:** respects the working rule that user-facing credits are charged only on the intelligence surface (D-11 keeps ingestion uncharged and instead bounded), and adds no Celery periodic task — the billing tick rides the existing in-process scheduler because the Celery broker is quota-limited Upstash Redis.
