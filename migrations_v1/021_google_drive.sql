-- Migration 021: Google Drive Integration
-- Run: psql $DATABASE_URL -f migrations/021_google_drive.sql

-- ─── GDrive Connections ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdrive_connections (
  id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                     UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  access_token               TEXT,
  refresh_token              TEXT,
  token_expires_at           TIMESTAMPTZ,
  changes_page_token         TEXT,
  changes_token_valid_until  TIMESTAMPTZ,
  last_changes_sync_at       TIMESTAMPTZ,
  last_full_metadata_sync_at TIMESTAMPTZ,
  last_shared_drive_sync_at  TIMESTAMPTZ,
  is_workspace_admin         BOOLEAN DEFAULT FALSE,
  drive_watch_channel_id     TEXT,
  drive_watch_expiry         TIMESTAMPTZ,
  created_at                 TIMESTAMPTZ DEFAULT NOW(),
  updated_at                 TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id)
);

-- ─── GDrive Shared Drives ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdrive_shared_drives (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id               UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  drive_id             TEXT NOT NULL,
  drive_name           TEXT,
  created_time         TIMESTAMPTZ,
  dept_classification  TEXT,
  dept_confidence      FLOAT DEFAULT 0.0,
  authority_node_id    TEXT,
  last_member_sync_at  TIMESTAMPTZ,
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, drive_id)
);

CREATE INDEX IF NOT EXISTS idx_gdrive_shared_drives_org ON gdrive_shared_drives(org_id);

-- ─── GDrive Shared Drive Members ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdrive_shared_drive_members (
  id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                     UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  drive_id                   TEXT NOT NULL,
  email                      TEXT NOT NULL,
  person_id                  UUID REFERENCES contacts(id) ON DELETE SET NULL,
  drive_role                 TEXT CHECK (drive_role IN ('organizer', 'fileOrganizer', 'writer', 'commenter', 'reader')),
  authority_level            INTEGER DEFAULT 50,
  is_external                BOOLEAN DEFAULT FALSE,
  joined_at                  TIMESTAMPTZ,
  written_to_authority_graph BOOLEAN DEFAULT FALSE,
  created_at                 TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, drive_id, email)
);

CREATE INDEX IF NOT EXISTS idx_gdrive_drive_members_org ON gdrive_shared_drive_members(org_id);
CREATE INDEX IF NOT EXISTS idx_gdrive_drive_members_person ON gdrive_shared_drive_members(person_id)
  WHERE person_id IS NOT NULL;

-- ─── GDrive Files ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdrive_files (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  file_id             TEXT NOT NULL,
  file_name           TEXT,
  mime_type           TEXT,
  content_type        TEXT CHECK (content_type IN ('document', 'spreadsheet', 'presentation', 'pdf', 'image', 'video', 'binary', 'other')),
  parent_folder_id    TEXT,
  folder_path         TEXT,
  dept_domain         TEXT,
  owner_email         TEXT,
  owner_person_id     UUID REFERENCES contacts(id) ON DELETE SET NULL,
  drive_id            TEXT,
  is_shared_externally BOOLEAN DEFAULT FALSE,
  external_share_count INTEGER DEFAULT 0,
  anyone_with_link    BOOLEAN DEFAULT FALSE,
  trashed             BOOLEAN DEFAULT FALSE,
  created_time        TIMESTAMPTZ,
  modified_time       TIMESTAMPTZ,
  content_indexed     BOOLEAN DEFAULT FALSE,
  synced_at           TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, file_id)
);

CREATE INDEX IF NOT EXISTS idx_gdrive_files_org ON gdrive_files(org_id);
CREATE INDEX IF NOT EXISTS idx_gdrive_files_owner ON gdrive_files(owner_person_id)
  WHERE owner_person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gdrive_files_external ON gdrive_files(org_id, is_shared_externally)
  WHERE is_shared_externally = TRUE;
CREATE INDEX IF NOT EXISTS idx_gdrive_files_modified ON gdrive_files(org_id, modified_time DESC);

-- ─── GDrive Permissions ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdrive_permissions (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  file_id               TEXT NOT NULL,
  permission_id         TEXT NOT NULL,
  grantee_email         TEXT,
  grantee_type          TEXT CHECK (grantee_type IN ('user', 'group', 'domain', 'anyone')),
  role                  TEXT CHECK (role IN ('owner', 'organizer', 'fileOrganizer', 'writer', 'commenter', 'reader')),
  is_external           BOOLEAN DEFAULT FALSE,
  expiration_time       TIMESTAMPTZ,
  allow_file_discovery  BOOLEAN DEFAULT FALSE,
  person_id             UUID REFERENCES contacts(id) ON DELETE SET NULL,
  revoked               BOOLEAN DEFAULT FALSE,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, file_id, permission_id)
);

CREATE INDEX IF NOT EXISTS idx_gdrive_permissions_file ON gdrive_permissions(org_id, file_id);
CREATE INDEX IF NOT EXISTS idx_gdrive_permissions_person ON gdrive_permissions(person_id)
  WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gdrive_permissions_expiry ON gdrive_permissions(expiration_time)
  WHERE expiration_time IS NOT NULL AND revoked = FALSE;

-- ─── GDrive Activity ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdrive_activity (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id               UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  file_id              TEXT NOT NULL,
  actor_email          TEXT,
  actor_person_id      UUID REFERENCES contacts(id) ON DELETE SET NULL,
  actor_is_external    BOOLEAN DEFAULT FALSE,
  action_type          TEXT CHECK (action_type IN ('create', 'edit', 'view', 'comment', 'share', 'move', 'rename', 'delete', 'restore', 'download')),
  timestamp            TIMESTAMPTZ NOT NULL,
  target_email         TEXT,
  target_person_id     UUID REFERENCES contacts(id) ON DELETE SET NULL,
  processed_for_graph  BOOLEAN DEFAULT FALSE,
  created_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdrive_activity_org ON gdrive_activity(org_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_gdrive_activity_file ON gdrive_activity(org_id, file_id);
CREATE INDEX IF NOT EXISTS idx_gdrive_activity_actor ON gdrive_activity(actor_person_id)
  WHERE actor_person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gdrive_activity_unprocessed ON gdrive_activity(org_id, processed_for_graph)
  WHERE processed_for_graph = FALSE;

-- ─── GDrive Access Expiry State ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdrive_access_expiry_state (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id            UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  file_id           TEXT NOT NULL,
  file_name         TEXT,
  grantee_email     TEXT NOT NULL,
  grantee_person_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
  role              TEXT,
  expiration_time   TIMESTAMPTZ NOT NULL,
  alert_sent_14d    BOOLEAN DEFAULT FALSE,
  alert_sent_3d     BOOLEAN DEFAULT FALSE,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, file_id, grantee_email)
);

CREATE INDEX IF NOT EXISTS idx_gdrive_expiry_state_org ON gdrive_access_expiry_state(org_id, expiration_time);

-- ─── GDrive Folder Structure ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdrive_folder_structure (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  folder_id           TEXT NOT NULL,
  folder_name         TEXT,
  parent_folder_id    TEXT,
  folder_level        INTEGER DEFAULT 0,
  dept_classification TEXT,
  dept_confidence     FLOAT DEFAULT 0.0,
  owner_email         TEXT,
  owner_person_id     UUID REFERENCES contacts(id) ON DELETE SET NULL,
  authority_node_id   TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(org_id, folder_id)
);

CREATE INDEX IF NOT EXISTS idx_gdrive_folder_structure_org ON gdrive_folder_structure(org_id);
CREATE INDEX IF NOT EXISTS idx_gdrive_folder_structure_parent ON gdrive_folder_structure(org_id, parent_folder_id);

-- ─── GDrive Change Log ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gdrive_change_log (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  change_type           TEXT,
  file_id               TEXT,
  page_token_at_receipt TEXT,
  raw_change            JSONB,
  status                TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'skipped', 'failed')),
  processed_at          TIMESTAMPTZ,
  received_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gdrive_change_log_org ON gdrive_change_log(org_id, status);
CREATE INDEX IF NOT EXISTS idx_gdrive_change_log_pending ON gdrive_change_log(org_id, received_at)
  WHERE status = 'pending';

-- ─── ALTER interactions: add Drive columns ───────────────────────────────────
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS gdrive_file_id TEXT;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS gdrive_share_role TEXT;
