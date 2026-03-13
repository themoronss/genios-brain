# Context Graph Flow & Relationship Architecture

This document tracks the technical lifecycle of data within GeniOS Brain—from raw payload, to LLM extraction, to database storage, and finally to API delivery. It outlines exactly *what* keys are extracted and *how* logic is applied without needing to read the codebase.

## Step 1: Ingestion & Text Processing
When an organization triggers a sync, a background worker queries limits batches of Gmail threads. The email parser (`app/ingestion/email_parser.py`) standardizes the payload:
- **Header Parsing**: Extracts `Subject`, `Date`, `To_Name`, `To_Email`, `From_Name`, `From_Email`.
- **Deduplication**: Message parts are recursively searched, prioritizing `text/plain` payloads. If none exist, `text/html` is extracted and forcibly stripped of all HTML tags.
- **Pruning**: Excessive whitespace, newlines, and footers are regex-cleaned. The text is forcefully truncated to **5,000 characters** to protect LLM context windows securely focusing on the core message.

## Step 2: LLM Entity Intelligence Array
The `app/ingestion/entity_extractor.py` passes the pruned 5000-character email to **Llama 3.3 70B** (via Groq) or **Gemini 2.5 Flash** (Fallback). The LLM is strictly constrained to output JSON mapped to the following precise keys:

1. **`summary`**: A concise one-sentence description of the email's purpose (max 200 chars).
2. **`sentiment`**: A calculated float metric scaling from `-1.0` (Negative) to `+1.0` (Positive).
3. **`intent`**: An enumerated string. Must be exactly one of: `[follow_up, request, commitment, introduction, negotiation, update, question, other]`.
4. **`commitments`**: An array of explicit promises and action items (e.g., `"Will send retention data by Friday"`). Limited to 10 items.
5. **`topics`**: An array of 2-5 overarching themes. Limited to 5 items, max 50 chars each (e.g., `["pricing", "API docs"]`).

## Step 3: Graph Structuring & Upsertion
The processed LLM payload is handed to the Database builder (`app/ingestion/graph_builder.py`).

- **Company Inference**: Email domains are parsed. Identifiers like `gmail.com` or `icloud.com` are skipped. B2B domains (like `company.com`) are split, capitalized, and stored as the Contact's associated `Company` field.
- **Node Upsertion**: A Contact Node is strictly merged by `email` and `org_id` uniquely.
- **Edge Construction**: An Interaction Edge is inserted into the graph binding the Contact Node and Org Node, harboring the specific `intent`, `commitments`, `sentiment`, and `topics` from Step 2.

## Step 4: The Relationship Stage Algorithm
Because raw interactions don't provide actionable context to an agent, `app/graph/relationship_calculator.py` recalculates the health of every Node based on its edges. 

The system averages the sentiment across all interactions (`sentiment_avg`) and logs the date of the most recent interaction (`days_since`). It applies a strict overriding waterfall logic:

1. **Critical Risk Override**: IF `sentiment_avg` < **-0.3** ➡️ **`AT_RISK`** 🚨 (Overrides all recency checks).
2. **Recently Active**: IF `days_since` < **7** AND `sentiment_avg` > **0** ➡️ **`ACTIVE`** 🟢.
3. **Slightly Aged**: IF `days_since` < **30** ➡️ **`WARM`** 🟡.
4. **Aging**: IF `days_since` < **60** ➡️ **`DORMANT`** 🟠.
5. **Dead**: IF `days_since` > **60** (or no interactions exist) ➡️ **`COLD`** 🔘.

Alongside the label, the Contact Node is enriched with the Top 10 recurring topics and an exact count of historic interactions.

## Step 5: Final Delivery (The Context Bundle)
When a third-party AI Agent queries `/v1/context` for a contact (e.g., "Sarah Chen"):
1. The backend performs a fuzzy/exact look-up against Contact Nodes.
2. It amalgamates the historic extracted `commitments`, preferred `topics`, and overall `Relationship Stage`.
3. It packages everything into a formatted Markdown paragraph.
4. This result is encrypted, **Redis Cached for 60 seconds** (Hash key: `org_id:person`), and delivered to the Agent to prepend to its Generation Context.
