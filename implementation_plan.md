# Relationship Graph Optimization — Implementation Plan

> Based on our chat discussion, this document outlines **what** to change, **why**, and **how** to do it effectively across your current codebase — without breaking the existing graph quality.

---

## Update 1: Gmail Sync — Fetch Exactly 100 Valid Emails (Timeline-Based)

### Problem (Current)
- [gmail_sync.py](file:///home/harshtripathi/Desktop/genios-brain/app/tasks/gmail_sync.py): Fetches 100 INBOX IDs + 100 SENT IDs separately → merges → picks top 100 by date → **then** filters out junk in Python.
- Result: If 35 emails are automated/internal, you end up with only **65** emails for graph building.
- [gmail_connector.py](file:///home/harshtripathi/Desktop/genios-brain/app/ingestion/gmail_connector.py): `fetch_emails()` uses `labelIds` filter but no `q` query string.

### How to Fix

#### Step 1: Add `q` parameter to `fetch_emails()` in [gmail_connector.py](file:///home/harshtripathi/Desktop/genios-brain/app/ingestion/gmail_connector.py)
- Add a new `query` parameter to `fetch_emails()`.
- Default value: `"-label:promotions -label:social -from:noreply -from:no-reply -from:notifications"`.
- Remove `labelIds` parameter when using `q` (Gmail API does not allow both; use `in:inbox OR in:sent` inside the query string instead).
- Updated query example: `q="(in:inbox OR in:sent) -label:promotions -label:social -from:noreply -from:no-reply"`.

#### Step 2: Add a new `fetch_message_headers()` function in [gmail_connector.py](file:///home/harshtripathi/Desktop/genios-brain/app/ingestion/gmail_connector.py)
- Similar to `fetch_message_metadata()` but also returns `From`, `To`, `CC` headers.
- Use `format="metadata"` with `metadataHeaders=["From", "To", "Cc", "Date", "Subject"]`.
- This is **much cheaper** than `fetch_full_message()` (no body downloaded).

#### Step 3: Rewrite the fetch loop in [gmail_sync.py](file:///home/harshtripathi/Desktop/genios-brain/app/tasks/gmail_sync.py) `run_gmail_sync()`
- Replace the current "fetch 200, pick 100, then filter" logic with a `while len(valid_messages) < 100` loop:
  1. Fetch a page of ~50 message IDs using `fetch_emails()` with the Gmail-side `q` filter.
  2. For each ID, call `fetch_message_headers()` (lightweight).
  3. Run `is_automated_email()` and `is_internal_email()` checks against the headers.
  4. If valid, append to `valid_messages` list.
  5. If `len(valid_messages) >= 100`, break. Else, use `nextPageToken` to fetch next batch.
- After the loop, you have **exactly 100 valid message IDs**.
- Only **then** call `fetch_full_message()` for each of these 100 IDs.

> [!IMPORTANT]
> This ensures the graph always has exactly 100 high-quality data points, regardless of how much junk is in the mailbox.

---

## Update 2: Dynamic Contact Tagging (Investors, Customers, etc.)

### Problem (Current)
- [entity_extractor.py](file:///home/harshtripathi/Desktop/genios-brain/app/ingestion/entity_extractor.py): The LLM prompt extracts sentiment, intent, commitments, and topics — but **never** classifies the contact's business role.
- The `contacts` table has an `entity_type` column (read by [bundle_builder.py](file:///home/harshtripathi/Desktop/genios-brain/app/context/bundle_builder.py) line 26) but it is **never populated** during sync.

### How to Fix

#### Step 1: Update the LLM prompt in [entity_extractor.py](file:///home/harshtripathi/Desktop/genios-brain/app/ingestion/entity_extractor.py)
- Add a new field to the extraction prompt:
  ```
  8. "contact_role": ONE of: investor, customer, vendor, partner, candidate, team, lead, advisor, media, other
     — Based on the conversation context, classify the sender's business relationship.
  ```
- Add `"contact_role"` to the returned JSON structure.
- Add it to the return dict: `"contact_role": str(result.get("contact_role", "other"))`.

#### Step 2: Update `upsert_contact()` in [graph_builder.py](file:///home/harshtripathi/Desktop/genios-brain/app/ingestion/graph_builder.py)
- Accept an optional `entity_type` parameter.
- In the `INSERT ... ON CONFLICT DO UPDATE` SQL, add: `entity_type = COALESCE(EXCLUDED.entity_type, contacts.entity_type)`.
- This ensures the tag is set on first extraction but not overwritten with `null` if a later email doesn't provide one.

#### Step 3: Pass the role through in [gmail_sync.py](file:///home/harshtripathi/Desktop/genios-brain/app/tasks/gmail_sync.py)
- After calling `extract_email_intelligence()`, pass `intelligence.get("contact_role")` into `upsert_contact()`.

> [!TIP]
> Using `COALESCE` in the SQL ensures the *first* meaningful tag sticks, and subsequent emails don't accidentally blank it out.

---

## Update 3: Many-to-Many Graph (CC Parsing)

### Problem (Current)
- [email_parser.py](file:///home/harshtripathi/Desktop/genios-brain/app/ingestion/email_parser.py) `parse_headers()`: Only extracts `From` and `To`. **Ignores `CC` and `BCC`** entirely.
- This means if 3 people are on an email thread, the system only creates an edge between you and the sender, missing the other participants.

### How to Fix

#### Step 1: Update `parse_headers()` in [email_parser.py](file:///home/harshtripathi/Desktop/genios-brain/app/ingestion/email_parser.py)
- Add extraction for `Cc` header.
- The `Cc` header contains a comma-separated list of addresses (e.g., `"Priya <priya@seq.com>, Mukesh <mukesh@firm.com>"`).
- Use `email.utils.getaddresses()` (built-in Python) instead of `parseaddr()` to handle multiple addresses.
- Return a new field: `"cc_list": [{"name": "Priya", "email": "priya@seq.com"}, ...]`.

#### Step 2: Process CC participants in [gmail_sync.py](file:///home/harshtripathi/Desktop/genios-brain/app/tasks/gmail_sync.py)
- After processing the primary contact (From/To), loop through `parsed["cc_list"]`.
- For each CC participant: run `is_automated_email()` and `is_internal_email()` checks.
- If valid, call `upsert_contact()` for them and call `create_interaction()` to link them to the **same** interaction (same `gmail_id`, same thread context).
- This naturally creates edges between **all** participants in the interaction, not just you and one person.

> [!NOTE]
> You do **not** need a separate junction table for this. Simply creating an `interaction` row for each participant against the same `gmail_message_id` achieves the many-to-many structure. The `ON CONFLICT (gmail_message_id) DO UPDATE` constraint in `create_interaction` will need to be changed to `ON CONFLICT (gmail_message_id, contact_id)` to allow multiple contacts per email.

---

## Update 4: Multiple Gmail Connections

### Problem (Current)
- [auth.py](file:///home/harshtripathi/Desktop/genios-brain/app/api/routes/auth.py) line 139: The `oauth_tokens` table has `ON CONFLICT (org_id)`, meaning only **one** Gmail token per organization.
- Connecting a second Gmail account **overwrites** the first one.

### How to Fix

#### Step 1: Database Migration
- Alter the `oauth_tokens` table:
  - Add an `account_email` column (VARCHAR, NOT NULL).
  - Drop the existing `UNIQUE(org_id)` constraint.
  - Add a new `UNIQUE(org_id, account_email)` constraint.
- This allows storing multiple Gmail tokens per org.

#### Step 2: Update the OAuth callback in [auth.py](file:///home/harshtripathi/Desktop/genios-brain/app/api/routes/auth.py)
- After `flow.fetch_token()`, call the Gmail API to get the connected account's email address (use `get_user_email()` from `gmail_connector.py`).
- Store this email in the new `account_email` column.
- Change `ON CONFLICT (org_id)` → `ON CONFLICT (org_id, account_email)`.

#### Step 3: Update the sync logic in [gmail_sync.py](file:///home/harshtripathi/Desktop/genios-brain/app/tasks/gmail_sync.py) and [sync.py](file:///home/harshtripathi/Desktop/genios-brain/app/api/routes/sync.py)
- Update `run_gmail_sync()` to accept an optional `account_email` parameter.
- If not provided, query **all** tokens for the `org_id` and loop through each one, running the sync for each connected account.
- The `upsert_contact()` function will naturally merge data from multiple accounts into the same contact node (keyed by external email + org_id).

#### Step 4: Update the sync status endpoint in [sync.py](file:///home/harshtripathi/Desktop/genios-brain/app/api/routes/sync.py)
- Return sync status for **all** connected accounts (not just one).
- Add an API endpoint to **list** all connected Gmail accounts for an org.
- Add an API endpoint to **disconnect** a specific Gmail account.

---

## Update 5: Multi-Source Readiness (Calendar, Docs — Future)

### No Code Changes Needed Now
Your current architecture is already designed for this because:
- `interactions` table has a generic `interaction_type` field.
- `relationship_calculator.py` aggregates **all** interactions regardless of source.
- `bundle_builder.py` consumes the unified contact+interactions data.

When you add Calendar sync later, simply:
1. Create a `calendar_sync.py` that calls `upsert_contact()` and `create_interaction()` with `interaction_type="calendar_meeting"`.
2. The existing `relationship_calculator.py` and `bundle_builder.py` will automatically incorporate meeting data into scores and context bundles.

---

## Execution Order (Recommended)

| Priority | Update | Risk | Why This Order |
|----------|--------|------|----------------|
| 1 | **Update 1** (Fetch exactly 100) | Low | Pure optimization, no schema changes. Immediately improves graph data quality. |
| 2 | **Update 2** (Contact tagging) | Low | Adds a new field to LLM prompt + passes it to DB. No breaking changes. |
| 3 | **Update 3** (CC parsing) | Medium | Requires changing unique constraints on `interactions` table. Test carefully. |
| 4 | **Update 4** (Multiple Gmail) | Medium | Requires DB migration on `oauth_tokens`. Must handle existing data. |
| 5 | **Update 5** (Multi-source) | None | No changes needed now. Architecture is ready. |

---

## Verification Plan

### Automated / Script-Based Testing  
- After Update 1: Run a sync with a test Gmail account and verify the logs print exactly `"Processing 100 new emails"` (not fewer). Check `interactions` table count matches 100.
- After Update 2: Run a sync and query: `SELECT entity_type, COUNT(*) FROM contacts WHERE org_id = '<test_org>' GROUP BY entity_type` — verify roles are populated.
- After Update 3: Send a test email with 2 CC recipients, run sync, and verify 3 `interaction` rows exist for that `gmail_message_id` (one per participant).
- After Update 4: Connect two different Gmail accounts for the same org. Query `SELECT account_email FROM oauth_tokens WHERE org_id = '<test_org>'` — should return 2 rows.

### Manual Verification  
- After all updates: Trigger a full sync from the dashboard, check the sync status page shows progress, verify the contacts list in the dashboard shows entity type labels (Investor, Customer, etc.).
