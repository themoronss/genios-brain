-- Add has_unsubscribe to interactions.
--
-- email_parser.py detects the `List-Unsubscribe` header and stages
-- has_unsubscribe=True in the parsed payload, but no INSERT path persists it
-- and no migration ever added the column. relationship_calculator.py
-- nevertheless runs `BOOL_OR(has_unsubscribe = TRUE)` on the table, which
-- aborts every contact-stage recalc with "column has_unsubscribe does not exist".
--
-- Default FALSE so existing rows have a safe value. Writes to this column
-- will be wired up separately once we audit which INSERT paths should set it.

ALTER TABLE interactions ADD COLUMN IF NOT EXISTS has_unsubscribe BOOLEAN NOT NULL DEFAULT FALSE;
