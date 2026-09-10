"""Credits + plan primitives for billing. Deterministic, atomic, idempotent.

Single credit pool: balance = orgs.credits (plan, reset each period) + orgs.topup_credits (rolls
over). Deduct drains topup first, then plan, in one atomic UPDATE. Every mutation appends an
immutable credit_ledger row; a double charge is blocked by a unique idempotency_key. Plan
activation is idempotent on payment_id (paid-but-no-credits and double-grant both guarded).
Prices are in minor units (paise / cents). No gateway calls here — pure DB + crypto.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

# ── the plan table ──────────────────────────────────────────────────────────────────────────
#
# ONE definition of what a tier is worth. This used to live in four places — `PLAN_PRICES` and
# `PLAN_CREDITS` here, `_CREDIT_LIMIT`/`_SEAT_LIMIT` in account_routes and `_DAILY_QUERIES` in
# intelligence_routes — and the four disagreed: `early` is a sellable Rs.4,500/mo plan that was
# missing from two of them (so a paying Early customer fell to a 100-credit default), `startup`
# read 100,000 credits in one file and 2,000 in another, and `growth`/`scale` were priced by
# nothing. A plan's worth is one row now, and `test_billing_plans.py` fails if a route defines
# a rival table.
#
# `price_inr`/`price_usd` are minor units (paise / cents). `None` means the tier is not
# self-serve purchasable: `trial` is granted at signup and `enterprise` is sold by hand, so
# neither may appear in the checkout list. `ingest_usd_day` is the per-org daily ceiling on
# INGESTION model spend (L1/L2 extraction), which is never charged to the customer in credits
# but must still be bounded — see `plan_ingest_usd_cap`.


@dataclass(frozen=True)
class Plan:
    tier: str
    credits: int                 # intelligence allowance granted per period
    seats: int
    domains: int                 # how many expertise domains may be live at once (L3 activation)
    sync_messages: int           # messages that may be INGESTED per period — a separate meter
    backfill_messages: int       # ONE-TIME extra, first period only: the history import
    period_days: int
    price_inr: int | None
    price_usd: int | None
    ingest_usd_day: float


#: TWO METERS, and this is the load-bearing decision in the whole file.
#:
#: `credits` meters INTELLIGENCE — the things the customer chooses to do (ask, analyse, draft).
#: `sync_messages` meters INGESTION — the mail that arrives whether they want it or not.
#:
#: They are not one meter because one email costs MORE to ingest than one question costs to
#: answer. Measured, not guessed: the L2 extraction prompt is ~2,950 tokens (the pack vocabulary
#: is baked into it), so at Haiku list price one message costs ~Rs 0.16 against a query's ~Rs 0.12
#: — about 1.3 credits. Charged in credits, a founder connecting a 3,000-message mailbox would
#: burn ~4,000 credits before asking a single question, and a free plan of 3,000 would be gone
#: before the product had said anything. Worse, it prices the one thing the customer cannot
#: control: how much mail other people send them.
#:
#: So ingestion is INCLUDED and BOUNDED — a message count per period, plus the per-day dollar
#: ceiling below — and the credit balance is only ever spent on something the user clicked.
#: This is also what the workspace rule means by charging user-facing credits on the
#: intelligence surface only.
#:
#: THE FIRST SYNC IS NOT A MONTH. Connecting a mailbox imports history — two months of mail is
#: ~5,000 messages against an ongoing ~1,800/month — and it is the single most expensive moment
#: in an account's life. A monthly quota big enough to absorb it would be twelve times too big
#: for every month after it, and one sized for the steady state would refuse the import that
#: makes the product work at all. So `backfill_messages` is a ONE-TIME allowance granted on top
#: of the period quota, in the period the account was created, and never again.
#:
#: The two classes of email cost very differently and the quotas are sized against the mix:
#: an email the junk gate DROPS costs ~0.23 credits of work (its share of a 12-email batched
#: call); one that PASSES costs ~4.27 (it gets its own ~2,800-token L2 extraction). A noisy
#: mailbox is CHEAPER for us, not dearer.
#: `ingest_usd_day` is a RUNAWAY guard, not a second plan bound — the message quota above is the
#: plan bound, and it is the precise one. Sizing this against the plan instead cost real quality:
#: at $1/day a trial's cost governor demoted the extraction tier on nearly every message, and
#: `test_g7_the_formula_is_actually_deciding_on_the_production_path` caught it — the importance
#: distribution collapsed from a rankable spread to p90-p50 = 1080, i.e. a month of mail that
#: cannot be ordered. So each ceiling is set to comfortably cover the plan's OWN backfill in a
#: single day (~$0.002 of model spend per message, measured) and never below it. The deployed
#: global cap still binds alongside it (`wiring.make_cost_governor` takes the tighter of the two),
#: so this can only ever make a small plan tighter than a large one — never tighter than its own
#: work needs.
PLANS: dict[str, Plan] = {
    #             tier          credits  seats dom   sync  backfill days   INR      USD   ingest$
    "trial":      Plan("trial",      3_000,  1,   1,   1_000,   2_000,  15,    None,  None,  10.0),
    "individual": Plan("individual",10_000,  1,   1,   3_000,  10_000,  30, 450000,  2900,  30.0),
    "startup":    Plan("startup",  100_000,  5,   3,  25_000,  50_000,  30, 2500000, 9900, 150.0),
    "growth":     Plan("growth",   300_000, 15,  10,  75_000, 150_000,  30,    None, 29900, 450.0),
    "enterprise": Plan("enterprise", 1_000_000, 50, 25, 250_000, 500_000, 30, None, None, 1500.0),
}

#: Burst factor over the plan's even daily pace, used to derive the per-day ceiling. The BALANCE
#: is the real limit; this ceiling only stops a runaway loop or a stolen key from draining a
#: period in an afternoon. At 1x it would be a second, stricter price — and that is exactly the
#: bug it replaces: `_DAILY_QUERIES["trial"]` was 200/day against a 15-day, 10,000-credit trial,
#: so 7,000 of the granted credits could never be spent by anyone.
DAILY_BURST = 3
DAILY_FLOOR = 60                 # never derive a ceiling meaner than this

#: A credit is divisible, and the database stores POINTS. Reading one email is a fifth of a
#: credit and one attachment page is three tenths — units far smaller than a question — and an
#: integer credit could not express either without rounding a real charge to zero or to one.
#: Points are to credits what paise are to rupees: every balance, ledger row and deduction is a
#: whole number of points, and only the API divides. No floats ever reach the database, so no
#: balance can drift by a rounding error.
POINTS_PER_CREDIT = 100


def to_points(credits: float) -> int:
    """Credits -> points. A POSITIVE charge never lands on zero: rounding a real charge to free
    is how a whole surface stops being billed without anyone noticing."""
    if credits <= 0:
        return 0
    return max(1, round(credits * POINTS_PER_CREDIT))


def to_credits(points: int) -> float:
    """Points -> credits, for display. Two decimals, which is all the unit has."""
    return round(int(points) / POINTS_PER_CREDIT, 2)


#: Credits charged per billable action. One credit is priced at roughly what one Haiku-class
#: synthesis costs us at list (~1,400 in / ~70 out => ~$0.0015, about Rs 0.12), so the table
#: tracks spend instead of guessing. `deep` analysis runs on Sonnet 5 at $3/$15 per Mtok against
#: Haiku's $0.80/$4.00 — ~3.7x per token on the same prompt shape — so it is 4 credits, not 1.
#: A draft is output-heavy (500-token ceiling against the query's 700 on a much smaller prompt)
#: and is a deliverable rather than an explanation, so it is 2.
#:
#: Nothing in the SYNC path appears here, deliberately — see the note on `sync_messages`.
#: THE UNIT TABLE, in POINTS (100 = 1 credit). One rule decides every row: the customer pays for
#: WORK THAT PRODUCED SOMETHING FOR THEM, and for nothing else.
#:
#: So an email the junk gate threw away is FREE — we did work, they got nothing, and charging for
#: spam would mean a noisy mailbox costs more than a clean one for no benefit. A cached answer is
#: free because no work was redone. A message already captured is free because it is only ever
#: read once. What IS charged is what entered their graph or came back on their screen.
#:
#: Nothing costs more than 2 credits. The ladder is deliberately shallow: a customer should be
#: able to hold it in their head, and a single click that costs five of something is a click
#: people stop making.
COSTS: dict[str, int] = {
    # ingestion — charged per UNIT of what was actually read, not per email that arrived
    "message_read":               20,     # 0.2 — one message extracted into the context graph
    "document_page":              30,     # 0.3 — one attachment page read (OCR + extraction)
    # intelligence — charged per thing the user asked for
    "intelligence_query":        100,     # 1
    "intelligence_analyze":      100,     # 1
    "intelligence_analyze_deep": 200,     # 2   — the bigger model
    "intelligence_draft":        150,     # 1.5 — a deliverable, not an explanation
}

#: Named so the free cases are a decision on the record rather than an absence. Every one of
#: these does real work inside the engine and none of it is billable.
FREE_UNITS = (
    "message_dropped_as_junk",            # the gate filtered it — they got nothing
    "message_already_captured",           # dedup; a message is read once, ever
    "cached_answer",                      # nothing was recomputed
    "feedback",                           # telling us we were wrong must never cost money
)

TOPUP_PACKS = {
    "small":  {"credits": 5_000,   "inr": 250000,  "usd": 3500,  "label": "Small"},
    "medium": {"credits": 25_000,  "inr": 1000000, "usd": 12900, "label": "Medium"},
    "large":  {"credits": 100_000, "inr": 3500000, "usd": 44900, "label": "Large"},
}
GRACE_DAYS = 7
#: `early` was the old name for what the pricing page now calls Individual, and `hustler` the one
#: before that. Existing rows carry them, so they resolve rather than falling to the trial row.
_ALIAS = {"hustler": "individual", "early": "individual", "free": "trial"}
_DEFAULT_TIER = "trial"

#: Back-compat views over PLANS. Kept because callers and tests read them by name, but DERIVED —
#: they cannot drift from the table the way two hand-maintained dicts did.
PLAN_CREDITS: dict[str, int] = {t: p.credits for t, p in PLANS.items()}
PLAN_PRICES: dict[str, dict] = {
    t: {"inr": p.price_inr, "usd": p.price_usd, "credits": p.credits,
        "period_days": p.period_days}
    for t, p in PLANS.items() if p.price_inr is not None
}
TRIAL_DAYS = PLANS["trial"].period_days


def plan_of(tier: str | None) -> Plan:
    """The Plan row for a tier, falling back to trial. Never raises: an org carrying a tier we
    retired must still be servable, and the trial row is the least generous thing to fall to."""
    return PLANS.get(normalize_plan(tier or ""), PLANS[_DEFAULT_TIER])


def plan_points(tier: str | None) -> int:
    """The plan's allowance in POINTS — what a period reset actually writes to `orgs.credits`."""
    return plan_of(tier).credits * POINTS_PER_CREDIT


def plan_seat_limit(tier: str | None) -> int:
    return plan_of(tier).seats


def plan_ingest_usd_cap(tier: str | None) -> float:
    return plan_of(tier).ingest_usd_day


def plan_domain_limit(tier: str | None) -> int:
    return plan_of(tier).domains


def plan_sync_messages(tier: str | None, *, first_period: bool = False) -> int:
    """Messages this plan may INGEST in a period. Not credits — see the note on `sync_messages`.

    `first_period` adds the one-time history-import allowance. It is the difference between a new
    tenant seeing two months of their own mail on day one and seeing the last three weeks of it.
    """
    plan = plan_of(tier)
    return plan.sync_messages + (plan.backfill_messages if first_period else 0)


def daily_credit_ceiling(tier: str | None) -> int:
    """Per-org, per-day credit ceiling — an abuse guard derived from the plan's own allowance,
    so it can never make part of a granted balance unreachable."""
    p = plan_of(tier)
    even_pace = -(-plan_points(tier) // max(1, p.period_days))   # ceil, in POINTS
    return max(DAILY_FLOOR * POINTS_PER_CREDIT, even_pace * DAILY_BURST)


def cost_of(action: str, *, deep: bool = False, units: int = 1) -> int:
    """POINTS for `units` of one billable action.

    Unknown actions cost one credit rather than nothing: a new endpoint that forgets to register
    its price should be cheap, never free — a silent zero is how a whole surface (analyze) ran
    free for months without anyone noticing.
    """
    if action in FREE_UNITS:
        return 0
    key = f"{action}_deep" if deep else action
    return COSTS.get(key, COSTS.get(action, POINTS_PER_CREDIT)) * max(0, int(units))


def normalize_plan(plan: str) -> str:
    p = (plan or "").lower()
    return _ALIAS.get(p, p)


def balance(conn, org_id: str) -> dict:
    row = conn.execute(text(
        "select coalesce(credits,0) plan_credits, coalesce(topup_credits,0) topup_pool, "
        "subscription_tier, plan_status from orgs where id=:o"), {"o": org_id}).first()
    if row is None:
        return {"balance": 0, "plan": 0, "topup": 0}
    plan_c, topup_c = int(row.plan_credits), int(row.topup_pool)
    # `balance`/`plan`/`topup` are POINTS — the unit every gate, deduct and ledger row uses.
    # `*_credits` are the same numbers as the customer reads them. Both are returned so a caller
    # never has to remember which unit it is holding, which is exactly how a 100x bug starts.
    return {"balance": plan_c + topup_c, "plan": plan_c, "topup": topup_c,
            "balance_credits": to_credits(plan_c + topup_c),
            "plan_credits_display": to_credits(plan_c), "topup_credits_display": to_credits(topup_c),
            "tier": row.subscription_tier, "plan_status": row.plan_status}


def _ledger(conn, org_id: str, *, kind: str, amount: int, balance_after: int,
            reason: str, idem: str | None, bucket: str = "credits",
            units: int | None = None) -> bool:
    """Append a ledger row. Returns False if the idempotency key already recorded a row.

    `units` is what the row COVERS — 1,240 messages read, 30 attachment pages. A charge the
    customer cannot decompose is a charge they cannot check, and ingestion is charged in batches
    of hundreds, so the count has to travel with the amount or the line reads as an unexplained
    248 credits.
    """
    import json as _json
    meta = _json.dumps({"units": int(units)}) if units is not None else None
    result = conn.execute(text(
        "insert into credit_ledger (org_id,kind,amount,balance_after,reason,bucket,"
        "idempotency_key,metadata) values (:o,:k,:a,:b,:r,:bk,:idem,cast(:m as jsonb)) "
        "on conflict (org_id, idempotency_key) where idempotency_key is not null "
        "do nothing returning id"),
        {"o": org_id, "k": kind, "a": amount, "b": balance_after, "r": reason,
         "bk": bucket, "idem": idem, "m": meta}).first()
    return result is not None


def grant_topup(conn, org_id: str, credits: int, *, idem: str, reason: str = "topup") -> int:
    """Add topup credits (roll-over pool). Idempotent on idem; returns the new total balance."""
    if not _ledger(conn, org_id, kind="topup", amount=credits, balance_after=0,
                   reason=reason, idem=idem):
        return balance(conn, org_id)["balance"]           # already granted
    conn.execute(text("update orgs set topup_credits = coalesce(topup_credits,0) + :c where id=:o"),
                 {"c": credits, "o": org_id})
    new = balance(conn, org_id)["balance"]
    conn.execute(text("update credit_ledger set balance_after=:b where org_id=:o "
                      "and idempotency_key=:idem"), {"b": new, "o": org_id, "idem": idem})
    return new


def activate_plan(conn, org_id: str, plan: str, *, payment_id: str) -> bool:
    """Set the org's tier/status/period + reset plan credits. Idempotent on payment_id.

    Returns True if newly activated, False if this payment was already applied.
    """
    plan = normalize_plan(plan)
    credits = plan_points(plan)                           # the allowance, in points
    period_days = PLAN_PRICES.get(plan, {}).get("period_days", 30)
    if not _ledger(conn, org_id, kind="reset", amount=credits, balance_after=credits,
                   reason=f"plan:{plan}", idem=f"activate:{payment_id}"):
        return False
    now = datetime.now(timezone.utc)
    conn.execute(text(
        "update orgs set subscription_tier=:t, plan_status='active', credits=:c, "
        "plan_started_at=:now, plan_expires_at=:exp, credit_period_start=:now, "
        "credit_period_end=:exp, grace_until=null where id=:o"),
        {"t": plan, "c": credits, "now": now, "exp": now + timedelta(days=period_days),
         "o": org_id})
    return True


# ── plan lifecycle ──────────────────────────────────────────────────────────────────────────
#
# NOTHING used to run at a plan boundary. No code path wrote `plan_status='expired'` or set
# `grace_until`, so a 15-day trial still answered questions on day 400 (until its credits ran
# out), the dashboard's expired-plan banner rendered a state the backend could not produce, and
# `subscription.in_grace` was permanently false. This is the tick that closes that.
#
# It does NOT grant credits. Razorpay orders here are one-time payments, not a subscription
# mandate, so there is no authority to renew anyone: renewal is the customer paying again, which
# runs `activate_plan` and rolls the period there. A tick that topped everyone up on a schedule
# would be giving the product away every 30 days.
#
# It also does not SUSPEND. `plan_status='suspended'` is refused at login by `platform/auth.py`,
# and locking an unpaid customer out of the page they would pay on is the one failure that
# cannot recover itself. Expiry is enforced where the money is spent — see
# `refusal_for` — and the dashboard stays reachable.


def expiry_state(plan_status: str | None, plan_expires_at, grace_until, *, now=None) -> str:
    """`active` | `grace` | `expired`, from the three columns alone. Pure, so the route, the tick
    and the read model cannot disagree about what a row means."""
    now = now or datetime.now(timezone.utc)
    status = (plan_status or "").lower()
    if status in ("suspended", "cancelled"):
        return "expired"
    if status == "expired" or (plan_expires_at is not None and plan_expires_at <= now):
        if grace_until is not None and grace_until > now:
            return "grace"
        return "expired"
    return "active"


def refusal_for(conn, org_id: str) -> dict | None:
    """The 402 body a billable call must refuse with, or None to proceed.

    Checks the plan boundary BEFORE the balance, because "your trial ended" and "you are out of
    credits" send the customer to two different buttons and the wrong message wastes the support
    round-trip.
    """
    row = conn.execute(text(
        "select subscription_tier, plan_status, plan_expires_at, grace_until, "
        "coalesce(credits,0)+coalesce(topup_credits,0) as bal from orgs where id=:o"),
        {"o": org_id}).first()
    if row is None:
        return None                                       # unknown org: auth owns that refusal
    state = expiry_state(row.plan_status, row.plan_expires_at, row.grace_until)
    if state == "expired":
        tier = normalize_plan(row.subscription_tier or "")
        return {"code": "PLAN_EXPIRED",
                "message": ("Your trial has ended — upgrade to keep asking."
                            if tier == "trial" else
                            "Your plan has expired — renew to keep asking.")}
    if int(row.bal or 0) < min(COSTS.values()):            # cannot afford the CHEAPEST unit
        return {"code": "OUT_OF_CREDITS",
                "message": "Out of credits — top up or upgrade to keep asking."}
    return None


def run_billing_tick(engine, *, now=None) -> dict:
    """Move every past-due org into expiry + its grace window. Idempotent: the guard makes an
    already-expired org a zero-row update, so running this every scheduler tick is free.

    Returns a small count dict for the log — the scheduler is the only caller and a silent
    lifecycle job is how the last one stayed dead for months without anyone noticing.
    """
    now = now or datetime.now(timezone.utc)
    with engine.begin() as conn:
        expired = conn.execute(text(
            "update orgs set plan_status='expired', "
            "grace_until = coalesce(grace_until, :grace) "
            "where plan_expires_at is not null and plan_expires_at <= :now "
            "and coalesce(plan_status,'') not in ('expired','suspended','cancelled') "
            "returning id, subscription_tier"),
            {"now": now, "grace": now + timedelta(days=GRACE_DAYS)}).all()
    for row in expired:                                   # audit outside the write txn
        try:
            from genios_engine.platform.audit import record
            record(row.id, "plan_expired", actor_type="system",
                   metadata={"tier": row.subscription_tier, "grace_days": GRACE_DAYS})
        except Exception:                                 # noqa: BLE001 — never break the sweep
            pass
    return {"expired": len(expired)}


def deduct(conn, org_id: str, cost: int, *, reason: str, idem: str, bucket: str = "context",
           units: int | None = None) -> bool:
    """Atomically drain topup first then plan credits. Idempotent. False if insufficient."""
    if cost <= 0:
        return True
    existing = conn.execute(text("select 1 from credit_ledger where org_id=:o and idempotency_key=:i"),
                            {"o": org_id, "i": idem}).first()
    if existing:
        return True                                       # already deducted
    updated = conn.execute(text(
        "update orgs set topup_credits = greatest(0, coalesce(topup_credits,0) - :c), "
        "credits = credits - greatest(0, :c - coalesce(topup_credits,0)) "
        "where id=:o and (coalesce(credits,0)+coalesce(topup_credits,0)) >= :c "
        "returning coalesce(credits,0)+coalesce(topup_credits,0) as bal"),
        {"c": cost, "o": org_id}).first()
    if updated is None:
        return False                                      # insufficient balance
    _ledger(conn, org_id, kind="deduct", amount=-cost, balance_after=int(updated.bal),
            reason=reason, idem=idem, bucket=bucket, units=units)
    # Reported from inside the idempotency guard, so a retried request never double-counts credit
    # usage in PostHog the way it never double-charges the ledger.
    try:
        from genios_engine.platform import analytics
        analytics.capture(org_id, "credits_used", {
            "credits": cost, "bucket": bucket, "reason": reason,
            "balance_after": int(updated.bal),
        })
    except Exception:      # noqa: BLE001 — billing is committed; telemetry is best-effort
        pass
    return True


def charge_units(conn, org_id: str, action: str, units: int, *, idem: str,
                 bucket: str, deep: bool = False) -> bool:
    """Charge `units` of one billable action, priced from the unit table. The ONE way ingestion
    is billed: a sweep that read 1,240 messages files ONE ledger row for 248 credits carrying
    `units: 1240`, not 1,240 rows and 1,240 writes on the ingestion path.

    A zero-unit or free action is a no-op that still returns True — "nothing to charge" and
    "could not charge" must never look the same to the caller."""
    points = cost_of(action, deep=deep, units=units)
    if points <= 0:
        return True
    return deduct(conn, org_id, points, reason=action, idem=idem, bucket=bucket, units=units)


def razorpay_signature(order_id: str, payment_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(),
                    hashlib.sha256).hexdigest()


def verify_razorpay(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    if not (order_id and payment_id and signature and secret):
        return False
    return hmac.compare_digest(razorpay_signature(order_id, payment_id, secret), signature)


def verify_webhook(raw_body: bytes, signature: str, secret: str) -> bool:
    if not (signature and secret):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
