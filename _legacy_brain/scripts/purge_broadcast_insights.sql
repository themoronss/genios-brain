-- One-time cleanup: purge anomalies + insights generated for senders that
-- are now classified as broadcast (newsletter / bot / transactional). The
-- code paths in anomaly_scanner.py and proactive.py have been patched to
-- exclude these going forward, but pre-existing rows are still in the DB
-- until this script runs.
--
-- Safety:
--   * Read-only preview blocks first — run them, eyeball the counts, then
--     execute the DELETEs.
--   * Scoped by org_id — replace :org_id with the target org UUID, or
--     remove the org_id clauses to clean across all orgs.
--   * Reversible by re-running the proactive scan; nothing schema-level.
--
-- Execute via psql:
--   psql $DATABASE_URL -v org_id=\'YOUR_ORG_UUID\' -f purge_broadcast_insights.sql
-- Or paste blocks into DO's database console one at a time.

\set ON_ERROR_STOP on

-- ── 1. Preview: how many bad rows exist? ─────────────────────────────────────

SELECT 'anomalies for broadcast contacts' AS what,
       COUNT(*) AS rows_affected
FROM contact_anomalies ca
JOIN contacts c ON ca.contact_id = c.id
WHERE COALESCE(c.classification_override, c.classification, 'unknown')
      IN ('newsletter', 'bot', 'transactional')
  AND ca.org_id = :'org_id';

SELECT 'insights for broadcast contacts' AS what,
       COUNT(*) AS rows_affected
FROM insights i
JOIN contacts c ON i.contact_id = c.id
WHERE COALESCE(c.classification_override, c.classification, 'unknown')
      IN ('newsletter', 'bot', 'transactional')
  AND i.org_id = :'org_id';

SELECT 'baselines for broadcast contacts' AS what,
       COUNT(*) AS rows_affected
FROM contact_baselines cb
JOIN contacts c ON cb.contact_id = c.id
WHERE COALESCE(c.classification_override, c.classification, 'unknown')
      IN ('newsletter', 'bot', 'transactional')
  AND cb.org_id = :'org_id';

-- ── 2. Preview a sample of who'll be removed ────────────────────────────────

SELECT c.name, c.email,
       COALESCE(c.classification_override, c.classification) AS classification,
       COUNT(DISTINCT i.id) AS insights,
       COUNT(DISTINCT ca.id) AS anomalies
FROM contacts c
LEFT JOIN insights i ON i.contact_id = c.id AND i.org_id = c.org_id
LEFT JOIN contact_anomalies ca ON ca.contact_id = c.id AND ca.org_id = c.org_id
WHERE COALESCE(c.classification_override, c.classification, 'unknown')
      IN ('newsletter', 'bot', 'transactional')
  AND c.org_id = :'org_id'
GROUP BY c.id, c.name, c.email, c.classification_override, c.classification
HAVING COUNT(DISTINCT i.id) + COUNT(DISTINCT ca.id) > 0
ORDER BY (COUNT(DISTINCT i.id) + COUNT(DISTINCT ca.id)) DESC
LIMIT 30;

-- ── 3. STOP. If counts above look reasonable, run the DELETEs below. ────────

BEGIN;

DELETE FROM insights
WHERE org_id = :'org_id'
  AND contact_id IN (
    SELECT id FROM contacts
    WHERE org_id = :'org_id'
      AND COALESCE(classification_override, classification, 'unknown')
          IN ('newsletter', 'bot', 'transactional')
  );

DELETE FROM contact_anomalies
WHERE org_id = :'org_id'
  AND contact_id IN (
    SELECT id FROM contacts
    WHERE org_id = :'org_id'
      AND COALESCE(classification_override, classification, 'unknown')
          IN ('newsletter', 'bot', 'transactional')
  );

DELETE FROM contact_baselines
WHERE org_id = :'org_id'
  AND contact_id IN (
    SELECT id FROM contacts
    WHERE org_id = :'org_id'
      AND COALESCE(classification_override, classification, 'unknown')
          IN ('newsletter', 'bot', 'transactional')
  );

-- Final tallies before commit.
SELECT 'remaining broadcast insights' AS what, COUNT(*)
  FROM insights i JOIN contacts c ON i.contact_id = c.id
  WHERE i.org_id = :'org_id'
    AND COALESCE(c.classification_override, c.classification, 'unknown')
        IN ('newsletter', 'bot', 'transactional');

-- Uncomment to make permanent:
-- COMMIT;
ROLLBACK;
