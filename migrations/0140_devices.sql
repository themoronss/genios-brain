-- 0140 · DEVICES — the desktop app signs in as a registered device of one seat (RFC 8628).
--
-- WHY A DEVICE ROW AND NOT JUST A SESSION. `auth_sessions.device_id` (0137) is a free-text label
-- a client may send on login; nothing vouches for it. A capture device uploads what is on a
-- person's screen, so it has to be something an admin can SEE (Settings → Devices), something the
-- seat approved in a signed-in browser, and something that can be revoked in one click — which
-- also kills every session opened for it. `devices` is that record; the session a device gets is
-- an ordinary seat session whose `device_id` names a row here.
--
-- WHY DEVICE CODES. The app never sees a password: it shows a short code, the person approves it
-- on the dashboard `/device` page, the app polls and receives tokens. Both codes are stored only
-- as SHA-256 — a leaked table holds nothing that can be exchanged for a session.

create table if not exists devices (
    device_id    text primary key,
    org_id       text not null references orgs (id) on delete cascade,
    seat_id      text not null,
    device_name  text,
    platform     text not null,
    os_version   text,
    app_version  text,
    created_at   timestamptz not null default now(),
    last_seen_at timestamptz,
    revoked_at   timestamptz,
    revoked_by   text
);
-- Settings → Devices lists a seat's devices; seat removal revokes them all.
create index if not exists devices_by_seat on devices (org_id, seat_id);

-- One row per sign-in attempt. `org_id` / `seat_id` are NULL until a signed-in seat approves the
-- code — that approval is what binds the device to a tenant. `device_id` is reserved at approval
-- (so the approving page can name it) and the `devices` row is created at the single-use token
-- exchange (`consumed_at`).
create table if not exists device_auth_codes (
    device_code_hash text primary key,
    user_code_hash   text not null unique,
    org_id           text references orgs (id) on delete cascade,
    seat_id          text,
    device_id        text,
    device_name      text,
    platform         text not null,
    os_version       text,
    app_version      text,
    requested_ip     text,
    created_at       timestamptz not null default now(),
    expires_at       timestamptz not null,
    approved_at      timestamptz,
    denied_at        timestamptz,
    consumed_at      timestamptz,
    last_polled_at   timestamptz
);
-- Housekeeping rides on issuing a new code (a delete of long-expired rows), not on a periodic
-- task — the Celery broker is quota-limited. This is the one index that cannot lead with org_id:
-- an unapproved code has none.
create index if not exists device_auth_codes_by_expiry on device_auth_codes (expires_at);
