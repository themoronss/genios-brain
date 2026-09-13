-- 0144 · MESSAGE FINGERPRINTS — one message, seen twice, extracted once (SCREEN_INTEL_P2 §3.3).
--
-- The same email can reach the engine twice: from the Gmail/Outlook connector, and from the desktop
-- app reading the seat's screen. Both copies become source events. Without this table both are
-- extracted, every fact is "corroborated" by itself, and the model is paid twice for one sentence.
--
-- `fp` = sha256("v1|" + sender_key + "|" + utc_minute + "|" + body_key), computed by
-- `genios_engine/capture/screen/fingerprint.py`. It is a one-way key, never the text.
--
-- ONE ROW PER (message, source). The primary key includes `source`, so the connector copy and the
-- screen copy of a message are two rows; the CANONICAL event is the one seen first (`seen_at`,
-- written with clock_timestamp() under a per-fingerprint advisory lock by `claim`). A retry of the
-- same source is `on conflict do nothing`.
create table if not exists message_fingerprints (
    org_id     text not null references orgs (id) on delete cascade,
    fp         text not null,
    source     text not null,
    event_id   text not null,
    delta_key  text,
    seen_at    timestamptz not null default now(),
    primary key (org_id, fp, source)
);
-- "Which messages did this event claim?" — replay, erasure of one event, and the promoter's audit.
create index if not exists message_fingerprints_by_event
    on message_fingerprints (org_id, event_id);
