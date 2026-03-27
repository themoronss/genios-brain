# GeniOS Brain - Backend Reference

## Tech Stack
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL (Supabase) + pgvector
- **Cache:** Redis (60s TTL for context, 24h precomputed bundles)
- **AI:** Google Gemini (extraction, drafts, chat)
- **Embeddings:** 1536-dim vectors via pgvector
- **Auth:** JWT + API key (Bearer token)
- **Real-time:** SSE via sse-starlette
- **Deploy:** Render / Railway

## Environment Variables
```
DATABASE_URL          # PostgreSQL connection
REDIS_URL             # Redis connection
GOOGLE_CLIENT_ID      # Gmail OAuth
GOOGLE_CLIENT_SECRET  # Gmail OAuth
GOOGLE_REDIRECT_URI   # OAuth callback
GEMINI_API_KEY        # Google Generative AI
SYNC_MAX_EMAILS       # Batch size (default: 10)
FRONTEND_URL          # Dashboard URL
```

## API Endpoints

### Auth
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/login` | Email/password login |
| POST | `/auth/register` | Create account |
| GET | `/auth/gmail/connect` | Start Gmail OAuth |
| GET | `/auth/gmail/callback` | OAuth callback |
| GET | `/api/org/{org_id}/apikey` | Get API key |
| POST | `/api/org/{org_id}/apikey/regenerate` | Regenerate API key |

### Context API (API key auth)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/context` | Get context bundle |
| POST | `/v1/context/outcome` | Report agent outcome |
| POST | `/v1/context/search` | Search contacts (temporal/topic) |
| GET | `/v1/context/entity/{id}` | Entity context by ID |

### Graph & Dashboard
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/org/{org_id}/graph` | Graph data (nodes + links) |
| GET | `/api/org/{org_id}/graph/export` | CSV export |
| GET | `/api/org/{org_id}/graph/filter/topic` | Filter by topic |
| GET | `/v1/graph/stats` | Graph health check |
| GET | `/dashboard/metrics` | Dashboard stats |
| GET | `/activity` | Activity feed |
| GET | `/api/org/{org_id}/status` | Org status |
| GET | `/api/org/{org_id}/contacts` | Contact list |
| GET | `/api/org/{org_id}/edge/{contact_id}` | Edge detail |
| GET | `/api/org/{org_id}/company/{domain}` | Company aggregate |
| GET | `/api/org/{org_id}/network-health` | Network health |
| GET | `/api/org/{org_id}/insights` | Insights |
| POST | `/api/org/{org_id}/insights/{id}/dismiss` | Dismiss insight |

### Sync
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/org/{org_id}/sync` | Trigger sync |
| GET | `/api/org/{org_id}/sync/status` | Sync status |
| GET | `/api/org/{org_id}/gmail/accounts` | List Gmail accounts |
| DELETE | `/api/org/{org_id}/gmail/accounts/{email}` | Disconnect account |
| POST | `/api/org/{org_id}/gmail/accounts/{email}/sync` | Sync specific account |

### AI Features
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/generate/draft` | AI email draft (Gemini) |
| POST | `/api/org/{org_id}/chat` | Mr. Elite chat |

### Agent Sessions
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/agents/session/start` | Open session |
| POST | `/v1/agents/session/end` | Close session |

### Facts & Lifecycle
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/org/{org_id}/context/overview` | Health cards |
| GET | `/api/org/{org_id}/facts` | Active facts |
| GET | `/api/org/{org_id}/facts/lifecycle` | Lifecycle timeline |
| GET | `/api/org/{org_id}/commitments` | Commitments |
| PATCH | `/api/org/{org_id}/commitments/{id}` | Update commitment |

### Authority Graph
| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/v1/authority/{org_id}/roles` | List/create roles |
| GET | `/v1/authority/{org_id}/roles/{id}` | Role detail |
| POST | `/v1/authority/{org_id}/permissions` | Add permission |
| GET | `/v1/authority/{org_id}/contacts/{id}/roles` | Contact roles |
| POST | `/v1/authority/{org_id}/contacts/{id}/assign` | Assign role |
| POST | `/v1/authority/{org_id}/check` | Auth check |

### Precedent Graph
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/precedent/{org_id}` | Record precedent |
| GET | `/v1/precedent/{org_id}` | List precedents |
| GET | `/v1/precedent/{org_id}/match` | Find similar |
| PATCH | `/v1/precedent/{org_id}/{id}/outcome` | Record outcome |
| GET | `/v1/precedent/{org_id}/stats` | Stats |

### Entity Merge
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/merge/{org_id}/scan` | Run scan |
| GET | `/v1/merge/{org_id}/queue` | List candidates |
| GET | `/v1/merge/{org_id}/queue/{id}` | Candidate detail |
| POST | `/v1/merge/{org_id}/queue/{id}/merge` | Execute merge |
| POST | `/v1/merge/{org_id}/queue/{id}/reject` | Reject |
| POST | `/v1/merge/{org_id}/queue/{id}/defer` | Defer |

### Manual Context & Upload
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/org/{org_id}/manual-context` | Add manual context |
| GET | `/api/org/{org_id}/manual-context` | List entries |
| DELETE | `/api/org/{org_id}/manual-context/{id}` | Delete entry |
| POST | `/api/org/{org_id}/upload` | Upload file |
| GET | `/api/org/{org_id}/uploads` | List uploads |

### Other
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/events/stream/{org_id}` | SSE stream |
| POST | `/api/org/{org_id}/reset` | Reset data |

## Database Tables

### Core
- **orgs** - Organizations (id, email, api_key, aer, brain_status, graph_quality_score)
- **contacts** - Entities (name, email, company, entity_type, relationship_stage, all 5 scores, embedding)
- **interactions** - Emails/events (contact_id, direction, subject, summary, sentiment, intent, topics, embedding)
- **oauth_tokens** - Gmail tokens (account_email, tokens, sync status/progress)

### Context
- **precomputed_bundles** - Cached context bundles (24h TTL)
- **context_calls** - API call logging
- **commitments** - Tracked promises (status: OPEN/OVERDUE/SOFT/fulfilled)

### Agent
- **outcome_events** - Agent execution feedback
- **agent_sessions** - Session tracking

### Graph
- **communities** - Louvain detection results
- **authority_roles** - Role definitions
- **authority_permissions** - Permission rules
- **authority_assignments** - Role-contact mapping
- **precedent_graph** - Past decisions
- **merge_queue** - Dedup candidates

### System
- **activity_log** - Event audit trail
- **insights** - Generated insights

## Background Jobs
- **Nightly refresh** (24h): Recalculate all scores, rebuild precomputed bundles, run community detection
- **Gmail sync on connect**: Auto-triggers after OAuth callback

## Ingestion Pipeline
```
Gmail API -> Email parser -> 3-tier classifier -> Entity extractor (NER + LLM)
-> Entity resolver -> Graph builder -> Scoring engine -> Community detection
-> Precomputed bundle builder
```
