-- Phase 5: Billing & Subscription
-- subscriptions: payment history and active subscription tracking
-- org_members: team seats per org
-- seat_invites: pending invite tokens

-- ── Subscriptions ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    plan            TEXT NOT NULL CHECK (plan IN ('trial', 'hustler', 'startup')),
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'active', 'failed', 'cancelled', 'expired')),
    period_start    TIMESTAMPTZ,
    period_end      TIMESTAMPTZ,
    payment_id      TEXT,           -- Razorpay payment_id (set after verify)
    order_id        TEXT,           -- Razorpay order_id (set at creation)
    overage_units   INTEGER DEFAULT 0,
    amount_paise    INTEGER,        -- INR amount × 100
    invoice_type    TEXT DEFAULT 'subscription'
                        CHECK (invoice_type IN ('subscription', 'overage')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_org_id  ON subscriptions(org_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status  ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_created ON subscriptions(created_at DESC);

-- ── Org Members (seats) ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS org_members (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    email       TEXT NOT NULL,
    name        TEXT,
    role        TEXT NOT NULL DEFAULT 'viewer'
                    CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
    invited_at  TIMESTAMPTZ DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    UNIQUE (org_id, email)
);

CREATE INDEX IF NOT EXISTS idx_org_members_org_id ON org_members(org_id);

-- ── Seat Invites (pending tokens) ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS seat_invites (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    email       TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'viewer',
    token       TEXT NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 days',
    accepted_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_seat_invites_org_id ON seat_invites(org_id);
CREATE INDEX IF NOT EXISTS idx_seat_invites_token  ON seat_invites(token);
