-- Billing: single-pool credits + subscriptions/invoices + immutable ledger.
-- Ported from the v1 backend to the v2 model: text org_id (not uuid), no Supabase RLS.

alter table orgs add column if not exists credits            bigint  not null default 0;
alter table orgs add column if not exists topup_credits      bigint  not null default 0;
alter table orgs add column if not exists plan_started_at    timestamptz;
alter table orgs add column if not exists plan_expires_at    timestamptz;
alter table orgs add column if not exists grace_until        timestamptz;
alter table orgs add column if not exists credit_period_start timestamptz;
alter table orgs add column if not exists credit_period_end  timestamptz;
alter table orgs add column if not exists sonnet_daily_count int     not null default 0;
alter table orgs add column if not exists sonnet_daily_reset_at timestamptz;

-- Doubles as the pending-order tracker AND the invoice/payment history.
create table if not exists subscriptions (
    id           text primary key,
    org_id       text not null references orgs(id) on delete cascade,
    plan         text not null,                          -- plan tier, or pack_id for topups
    status       text not null default 'pending',        -- pending | active | failed | cancelled | expired
    invoice_type text not null default 'subscription',   -- subscription | topup | overage
    processor    text,                                    -- razorpay | stripe
    currency     text not null default 'INR',
    amount_paise bigint not null default 0,
    order_id     text,
    payment_id   text,
    period_start timestamptz,
    period_end   timestamptz,
    created_at   timestamptz not null default now()
);
create index if not exists subscriptions_org on subscriptions (org_id, created_at desc);
create unique index if not exists subscriptions_order on subscriptions (org_id, order_id)
    where order_id is not null;

-- Immutable, append-only credit ledger. Double-charge guard = unique idempotency_key.
create table if not exists credit_ledger (
    id              bigserial primary key,
    org_id          text not null references orgs(id) on delete cascade,
    occurred_at     timestamptz not null default now(),
    bucket          text,                                -- context | sync | proactive | credits
    kind            text not null,                       -- deduct | refund | grant | topup | reset
    amount          bigint not null,                     -- signed
    balance_after   bigint not null,
    reason          text,
    related_kind    text,
    related_id      text,
    idempotency_key text,
    metadata        jsonb
);
create index if not exists credit_ledger_org on credit_ledger (org_id, occurred_at desc);
create unique index if not exists credit_ledger_idem on credit_ledger (org_id, idempotency_key)
    where idempotency_key is not null;
