-- Phase 4.6 — fact-type taxonomy (13 canonical types) + CHECK constraint
-- Safe flow:
--   1. Create mapping table (old_type → new_type)
--   2. UPDATE contact_facts in one batch
--   3. Verify zero violations
--   4. ADD CONSTRAINT

CREATE TABLE IF NOT EXISTS fact_type_mapping (
    old_type TEXT PRIMARY KEY,
    new_type TEXT NOT NULL
);

-- Seed the mapping. Extend if a legacy type surfaces during UPDATE.
INSERT INTO fact_type_mapping (old_type, new_type) VALUES
    ('role',                 'role'),
    ('commitment',           'commitment'),
    ('preference',           'engagement_state'),
    ('communication_style',  'engagement_state'),
    ('topic',                'mention'),
    ('relationship',         'relation'),
    ('sentiment_pattern',    'engagement_state'),
    ('identity',             'identity'),
    ('membership',           'membership'),
    ('attendance',           'attendance'),
    ('mention',              'mention'),
    ('thread_link',          'thread_link'),
    ('ownership',            'ownership'),
    ('permission',           'permission'),
    ('deal_state',           'deal_state'),
    ('engagement_state',     'engagement_state'),
    ('meeting_state',        'meeting_state')
ON CONFLICT (old_type) DO NOTHING;

UPDATE contact_facts
SET fact_type = m.new_type
FROM fact_type_mapping m
WHERE contact_facts.fact_type = m.old_type
  AND contact_facts.fact_type <> m.new_type;

-- Guard: if any rows are still outside the canonical set, fail loud.
DO $$
DECLARE bad_count INT;
BEGIN
    SELECT COUNT(*) INTO bad_count FROM contact_facts
    WHERE fact_type NOT IN (
        'identity','membership','relation','attendance','mention',
        'thread_link','ownership','role','permission','deal_state',
        'engagement_state','commitment','meeting_state'
    );
    IF bad_count > 0 THEN
        RAISE EXCEPTION 'fact_type cleanup incomplete — % rows still violate the 13-type set', bad_count;
    END IF;
END$$;

ALTER TABLE contact_facts
    DROP CONSTRAINT IF EXISTS fact_type_check;

ALTER TABLE contact_facts
    ADD CONSTRAINT fact_type_check CHECK (
        fact_type IN (
            'identity','membership','relation','attendance','mention',
            'thread_link','ownership','role','permission','deal_state',
            'engagement_state','commitment','meeting_state'
        )
    );
