-- 049: Companies table + WORKS_AT relationship
-- Per Graph Enrichment spec: Company nodes as separate entities (rounded squares)
-- linked to contacts via company_id FK.

-- 1. Companies table
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    domain TEXT,
    category TEXT,  -- investor_firm, customer_org, vendor, partner, other
    data_sources TEXT[] DEFAULT '{}',
    interaction_count INTEGER DEFAULT 0,
    last_interaction_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, domain)
);

CREATE INDEX IF NOT EXISTS idx_companies_org_domain ON companies(org_id, domain);
CREATE INDEX IF NOT EXISTS idx_companies_org_category ON companies(org_id, category);

-- 2. Link contacts to companies (WORKS_AT edge)
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id);
CREATE INDEX IF NOT EXISTS idx_contacts_company_id ON contacts(company_id);

-- 3. Backfill: create companies from existing contacts with company_domain
INSERT INTO companies (org_id, name, domain, category, created_at)
SELECT DISTINCT
    c.org_id,
    COALESCE(c.company, c.company_domain),
    c.company_domain,
    CASE
        WHEN c.entity_type IN ('investor', 'lead') THEN 'investor_firm'
        WHEN c.entity_type = 'customer' THEN 'customer_org'
        WHEN c.entity_type = 'vendor' THEN 'vendor'
        WHEN c.entity_type = 'partner' THEN 'partner'
        ELSE 'other'
    END,
    NOW()
FROM contacts c
WHERE c.company_domain IS NOT NULL
  AND c.company_domain != ''
ON CONFLICT (org_id, domain) DO NOTHING;

-- 4. Backfill: link existing contacts to their companies
UPDATE contacts c
SET company_id = co.id
FROM companies co
WHERE c.company_domain = co.domain
  AND c.org_id = co.org_id
  AND c.company_id IS NULL;
