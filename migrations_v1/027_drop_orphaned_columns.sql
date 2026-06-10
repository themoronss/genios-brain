-- Migration 027: Drop orphaned columns from contacts table
-- These columns are not read or written by any app code.

-- DB-1: communication_style_jsonb — orphaned, only communication_style (TEXT) is used
ALTER TABLE contacts DROP COLUMN IF EXISTS communication_style_jsonb;

-- DB-2: topics_weighted — orphaned, only topics_aggregate (TEXT[]) is used
ALTER TABLE contacts DROP COLUMN IF EXISTS topics_weighted;

-- DB-3: last_sentiment — orphaned, compiler.py now uses sentiment_ewma instead
ALTER TABLE contacts DROP COLUMN IF EXISTS last_sentiment;
