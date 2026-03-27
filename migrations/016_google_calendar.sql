-- Migration 016: Google Calendar Integration
-- Run: psql $DATABASE_URL -f migrations/016_google_calendar.sql

-- ─── Calendar Sync State ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS calendar_sync_state (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  calendar_id       TEXT NOT NULL,
  sync_token        TEXT,
  watch_channel_id  TEXT,
  watch_expiry      TIMESTAMPTZ,
  last_webhook_at   TIMESTAMPTZ,
  last_full_sync_at TIMESTAMPTZ,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, calendar_id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_sync_state_org ON calendar_sync_state(org_id);
CREATE INDEX IF NOT EXISTS idx_calendar_sync_watch_expiry ON calendar_sync_state(watch_expiry)
  WHERE watch_expiry IS NOT NULL;

-- ─── Calendar Events ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS calendar_events (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  google_event_id       TEXT NOT NULL,
  recurring_event_id    TEXT,
  calendar_id           TEXT NOT NULL,
  title                 TEXT,
  start_time            TIMESTAMPTZ,
  end_time              TIMESTAMPTZ,
  duration_minutes      INTEGER,
  organizer_email       TEXT,
  organizer_person_id   UUID REFERENCES contacts(id) ON DELETE SET NULL,
  location_type         TEXT CHECK (location_type IN ('video', 'in_person', 'phone', 'unknown')),
  meeting_type          TEXT CHECK (meeting_type IN ('internal', 'sales', 'investor', 'one_on_one', 'group', 'unknown')),
  agenda_summary        TEXT,
  topics_extracted      JSONB DEFAULT '[]',
  commitments_extracted JSONB DEFAULT '[]',
  is_cancelled          BOOLEAN DEFAULT FALSE,
  is_recurring          BOOLEAN DEFAULT FALSE,
  recurrence_rule       TEXT,
  rescheduled_count     INTEGER DEFAULT 0,
  raw_event             JSONB,
  synced_at             TIMESTAMPTZ DEFAULT NOW(),
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, google_event_id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_org ON calendar_events(org_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_start ON calendar_events(org_id, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_calendar_events_organizer ON calendar_events(org_id, organizer_person_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_recurring ON calendar_events(org_id, recurring_event_id)
  WHERE recurring_event_id IS NOT NULL;

-- ─── Calendar Event Attendees ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS calendar_event_attendees (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id               UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  event_id             UUID NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
  person_id            UUID REFERENCES contacts(id) ON DELETE SET NULL,
  email                TEXT NOT NULL,
  display_name         TEXT,
  rsvp_status          TEXT CHECK (rsvp_status IN ('accepted', 'declined', 'tentative', 'needsAction')),
  is_organizer         BOOLEAN DEFAULT FALSE,
  is_optional          BOOLEAN DEFAULT FALSE,
  is_external          BOOLEAN DEFAULT FALSE,
  attended_inferred    BOOLEAN,
  attended_confidence  FLOAT DEFAULT 0.0,
  UNIQUE(event_id, email)
);

CREATE INDEX IF NOT EXISTS idx_event_attendees_event ON calendar_event_attendees(event_id);
CREATE INDEX IF NOT EXISTS idx_event_attendees_person ON calendar_event_attendees(person_id)
  WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_event_attendees_org ON calendar_event_attendees(org_id);

-- ─── Upcoming Meetings ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS upcoming_meetings (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                  UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  event_id                UUID NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
  start_time              TIMESTAMPTZ NOT NULL,
  primary_contact_id      UUID REFERENCES contacts(id) ON DELETE SET NULL,
  prep_context_generated  BOOLEAN DEFAULT FALSE,
  follow_up_due_at        TIMESTAMPTZ,
  follow_up_sent          BOOLEAN DEFAULT FALSE,
  status                  TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show'))
);

CREATE INDEX IF NOT EXISTS idx_upcoming_meetings_org ON upcoming_meetings(org_id, start_time);
CREATE INDEX IF NOT EXISTS idx_upcoming_meetings_contact ON upcoming_meetings(primary_contact_id)
  WHERE primary_contact_id IS NOT NULL;

-- ─── ALTER interactions: add calendar columns ────────────────────────────────
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS calendar_event_id UUID
  REFERENCES calendar_events(id) ON DELETE SET NULL;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS duration_minutes INTEGER;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS attendee_count INTEGER;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS rsvp_status TEXT;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS location_type TEXT;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS is_recurring BOOLEAN DEFAULT FALSE;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS edge_weight_multiplier FLOAT DEFAULT 1.0;

CREATE INDEX IF NOT EXISTS idx_interactions_calendar_event ON interactions(calendar_event_id)
  WHERE calendar_event_id IS NOT NULL;
