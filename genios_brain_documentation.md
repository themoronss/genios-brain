# GeniOS Brain - Full Technical & Product Overview

GeniOS Brain is an AI-powered relationship relationship intelligence platform that automatically constructs a "Context Graph" from a user's email history. By converting raw emails into structured social intelligence, GeniOS allows external AI Agents to query a contact's history, interaction health, and communication style *before* writing an email to them, achieving a personalized, "How did it know that?" moment.

## 1. Current Progress & Status (V1.1 MVP)
- **Data Ingestion**: ✅ Connecting to Gmail via OAuth, syncing historical emails in the background using Celery/Redis.
- **AI Processing**: ✅ Email bodies are cleaned, and Groq (Llama 3.3 70B) or Gemini 2.5 Flash extracts intents, topics, and sentiments.
- **Graph Engine**: ✅ Relationship stages are automatically calculated and pushed to PostgreSQL.
- **Context API**: ✅ Real-time `/v1/context` endpoint functional, authenticated via Bearer tokens (`gn_live_...`), and cached by Redis for 60s.
- **Dashboard**: ✅ Next.js frontend implemented with OAuth, synchronization controls, and visual graph exploration.

## 2. Technical Stack
- **Backend Infrastructure**: Python FastAPI serving the Core API. PostgreSQL handles the structured context graph. Redis acts as both a task broker (for Celery workers pulling emails) and a 60-second caching layer for API requests.
- **LLM Pipeline**: Primary LLM: **Groq API** (`llama-3.3-70b-versatile`). Fallback LLM: **Google Gemini API** (`gemini-2.5-flash`).
- **Frontend App**: Next.js (React) Dashboard, styled with Tailwind CSS. Incorporates `react-force-graph` to visually map relationship nodes.

## 3. Core Capabilities & Architecture

### Backend API Endpoints
- `POST /api/org/{org_id}/sync`: Triggers asynchronous Celery worker to fetch last 6 months of Gmail history in background batches.
- `GET /api/org/{org_id}/sync/status`: Polling endpoint that returns real-time progression of the background sync, tracking contacts and interactions counted.
- `POST /v1/context`: **The Main Product Endpoint.** Used by AI agents to request context. Requires `entity_name`. Returns a structured paragraph (the "Context Bundle") summarizing the contact, along with a confidence match score.

### AI Engine (Entity Extraction)
Rather than simple regex, the system feeds raw emails to Llama/Gemini to extract highly specific data:
- **Intents**: Is this email a `request`, `follow_up`, `question`, `negotiation`, `commitment`, `introduction`, or `update`?
- **Commitments**: The system parses the email body to extract open action items or promises made.
- **Summarization**: 200-character one-sentence summaries of the entire thread.
- **Sentiment**: Floats between `-1.0` (Highly Negative) to `+1.0` (Highly Positive).

### Graph Processing
- **Nodes**: Contacts. Merged by exact email address match. Company names are algorithmically inferred from email domains (e.g., `john@sequoiacap.com` creates a `Sequoia Cap` company node, bypassing personal domains like `@gmail`).
- **Edges**: Interactions. The metadata from the LLM extraction (Topics, Sentiment, Intent) sits on the edges linking the Organization to the Contact.
- **Relationship Jobs**: The backend runs recurring tasks over the graph database to aggregate edge data. Nodes are dynamically labeled with a "Relationship Stage" depending on how long it has been since the last interaction and the overall health of the sentiment. 

*See `context_graph_flow.md` for the exact parameters and technical keys determining the Relationship Stages.*
