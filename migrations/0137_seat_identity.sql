-- 0137 · SEAT IDENTITY — every teammate gets their own login, their own seat, and sessions
-- that can be revoked.
--
-- ONE IDENTITY. `org_seats` (0008) stays the single ROUTING identity — cards (`card_recipients`,
-- 0135), escalations and the internal-email set all read it. `org_members` (0018) becomes the
-- LOGIN half of the same person: accepting an invite writes both rows with the same `seat_id`,
-- so a member can never be able to sign in without being routable, or routable without a
-- membership an admin can see and deactivate. Nothing wrote `org_members` before this; there is
-- no existing row to reconcile.
--
-- The owner still lives in `orgs` (email + pass_hash) and keeps logging in exactly as before; their
-- seat is the `seat_owner` row `platform/seats.ensure_owner_seat` derives from `orgs.email`.

-- ── members: the login half of a seat ─────────────────────────────────────────────────────
alter table org_members add column if not exists seat_id        text;
-- pbkdf2$iterations$salt$hash — the SAME scheme `orgs.pass_hash` uses (platform/auth.hash_password)
alter table org_members add column if not exists pass_hash      text;
alter table org_members add column if not exists deactivated_at timestamptz;
alter table org_members add column if not exists updated_at     timestamptz not null default now();
create unique index if not exists org_members_by_seat
    on org_members (org_id, seat_id) where seat_id is not null;
-- The sign-in lookup is by address ACROSS orgs (one person may belong to several workspaces) —
-- the one index here that cannot lead with org_id, exactly like `orgs_by_email` (0009).
create index if not exists org_members_login_email
    on org_members (lower(email)) where status = 'active';

-- ── invites: a single-use, expiring token ─────────────────────────────────────────────────
-- Only the SHA-256 of the token is stored; the raw token is shown once to the admin who invited.
-- Invites created before this migration carry no token and cannot be accepted — re-sending the
-- invite mints one.
alter table org_invites add column if not exists token_hash       text;
alter table org_invites add column if not exists invited_by       text;
alter table org_invites add column if not exists accepted_at      timestamptz;
alter table org_invites add column if not exists accepted_seat_id text;
create unique index if not exists org_invites_by_token
    on org_invites (token_hash) where token_hash is not null;

-- ── sessions: short-lived access JWT + rotating refresh token ─────────────────────────────
-- One row per signed-in device. `refresh_hash` is the CURRENT refresh token's SHA-256; each
-- refresh replaces it and files the old hash in `auth_refresh_rotations`, so presenting a token
-- that was already rotated is recognisable as reuse — and revokes the whole session.
create table if not exists auth_sessions (
    session_id     text primary key,
    org_id         text not null references orgs (id) on delete cascade,
    seat_id        text not null,
    device_id      text,
    refresh_hash   text not null,
    created_at     timestamptz not null default now(),
    last_used_at   timestamptz,
    expires_at     timestamptz not null,
    revoked_at     timestamptz,
    revoked_reason text
);
create unique index if not exists auth_sessions_by_refresh on auth_sessions (refresh_hash);
create index if not exists auth_sessions_by_seat
    on auth_sessions (org_id, seat_id) where revoked_at is null;

create table if not exists auth_refresh_rotations (
    refresh_hash text primary key,
    org_id       text not null references orgs (id) on delete cascade,
    session_id   text not null references auth_sessions (session_id) on delete cascade,
    rotated_at   timestamptz not null default now()
);
create index if not exists auth_refresh_rotations_by_session
    on auth_refresh_rotations (org_id, session_id);

-- ── uploads: company knowledge vs a seat's personal file ──────────────────────────────────
-- `company` is every upload that exists today (org visibility, canon path for SOP/policy tags).
-- `personal` is private to the uploading seat: its events carry `private` visibility naming only
-- that seat's address, and it is listed to nobody else.
alter table resource_uploads add column if not exists scope   text not null default 'company';
alter table resource_uploads add column if not exists seat_id text;
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'resource_uploads_scope_check') then
        alter table resource_uploads add constraint resource_uploads_scope_check
            check (scope in ('company', 'personal') and (scope = 'company' or seat_id is not null));
    end if;
end $$;
create index if not exists resource_uploads_by_seat
    on resource_uploads (org_id, seat_id) where seat_id is not null;
