# GeniOS Brain - AI Agent Intelligence Layer

**Status:** Prototype (Segments 1-3 Complete ✅)

GeniOS Brain is a decision and cognition layer that sits between AI agents (like OpenClaw) and their actions, providing:
- Context-aware enrichment
- Policy checking and enforcement
- Organizational memory
- Risk flagging
- Intelligent decision guidance

---

## Architecture

```
User Intent
    ↓
OpenClaw / AI Agent
    ↓
GeniOS Brain (/v1/enrich)
    ├─ Context Retrieval (Qdrant + Supabase)
    ├─ Reasoning Engine (Gemini)
    └─ Structured Verdict
    ↓
OpenClaw (uses enriched context)
    ↓
Action Execution
    ↓
Logging & Learning
```

---

## What's Built (Prototype - 48 Hour Plan)

### ✅ Segment 1: Context Store & Seed Data
- Supabase tables: `org_context`, `entity_state`, `interaction_log`
- Qdrant vector collection: `genios_context` (384-dim)
- Seed data: Organization profile, policies, investor relationships, entity states

### ✅ Segment 2: Context Retriever & Reasoning Engine
- Semantic search with Qdrant
- Structured context retrieval (policies, relationships, entity states)
- Gemini-powered reasoning with decision rules
- Structured output: verdict, enriched_brief, flags, key_context_used

### ✅ Segment 3: FastAPI Core Loop
- `/v1/enrich` - Main enrichment endpoint
- `/health` - Health check
- Entity extraction
- Interaction logging
- **10/10 core tests passing**
- **3/3 edge case tests passing**

### 🔄 Segment 4: OpenClaw Integration (In Progress)
- Deployment guide ready
- Integration documentation complete
- Comparison test suite ready
- **Next:** Deploy to Railway and run baseline tests

### ⏸️ Segment 5: Validation & Documentation (Planned)
- 20-test comprehensive validation
- Log analysis
- Cost baseline calculation
- MVP roadmap

---

## Quick Start

### Local Development

1. **Install dependencies:**
```bash
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

2. **Setup environment:**
Create `.env` file:
```
GEMINI_API_KEY=your_key
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
ORG_ID=genios_internal
```

3. **Setup databases:**
```bash
# Create Qdrant collection
python3 setup_qdrant.py

# Seed data
python3 data/seed.py
```

4. **Start API:**
```bash
uvicorn main:app --reload --port 8000
```

5. **Test:**
```bash
# Run core tests
python3 test_system.py

# Test manually
curl -X POST http://127.0.0.1:8000/v1/enrich \
  -H "Content-Type: application/json" \
  -d '{"org_id":"genios_internal","raw_message":"follow up with Rahul"}'
```

---

## OpenClaw Integration

See `OPENCLAW_INTEGRATION.md` for complete guide.

**Quick version:**

1. Deploy to Railway (see `DEPLOYMENT_CHECKLIST.md`)
2. Add this to OpenClaw system prompt:

```
Before executing investor outreach, follow-ups, or sharing data, 
call GeniOS Brain:

POST https://your-app.railway.app/v1/enrich
Body: {"org_id": "genios_internal", "raw_message": "[intent]"}

Use enriched_brief as context. Respect verdict:
- BLOCK → Stop
- ESCALATE → Get approval
- PROCEED → Execute with enriched context
- CLARIFY → Ask for details
```

3. Test with comparison suite: `python3 test_openclaw_comparison.py`

---

## API Reference

### POST /v1/enrich
Enrich user intent with organizational context and reasoning.

**Request:**
```json
{
  "org_id": "genios_internal",
  "raw_message": "follow up with Rahul about our prototype",
  "entity_name": "Rahul"  // optional
}
```

**Response:**
```json
{
  "verdict": "PROCEED",
  "enriched_brief": "Rahul is a warm lead at SeedFund, last contacted 10 days ago...",
  "recommended_action": "Draft personalized follow-up email...",
  "flags": [],
  "key_context_used": ["Rahul warm lead", "10 days since contact", "policy allows"],
  "confidence": 0.95
}
```

### GET /health
Health check endpoint.

### GET /v1/logs/{org_id}
Retrieve interaction logs (when deployed).

---

## Project Structure

```
genios-brain/
├── main.py                    # FastAPI app, routes
├── context/
│   ├── retriever.py          # Vector + structured context fetch
│   └── store.py              # Write context to DBs
├── reasoning/
│   └── engine.py             # Gemini reasoning + decision rules
├── data/
│   └── seed.py               # Seed organizational data
├── test_system.py            # Core validation tests
├── test_openclaw_comparison.py  # OpenClaw comparison suite
├── setup_qdrant.py           # Qdrant setup script
├── create_index.py           # Index creation (if needed)
├── OPENCLAW_INTEGRATION.md   # Integration guide
├── DEPLOYMENT_CHECKLIST.md   # Pre-deployment checklist
├── requirements.txt
└── .env                      # Environment variables (not in git)
```

---

## Tech Stack

- **API:** FastAPI + Uvicorn
- **Vector DB:** Qdrant (semantic search)
- **Structured DB:** Supabase (PostgreSQL)
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2)
- **Reasoning:** Google Gemini 2.0 Flash
- **Deployment:** Railway.app

---

## Testing

### Core Tests (10 tests)
```bash
python3 test_system.py
```

Tests:
- Policy blocking (financial data sharing)
- Policy escalation (meeting requests)
- Valid follow-ups
- Cold investor blocking
- Info requests
- Ambiguous entity clarification

### OpenClaw Comparison
```bash
python3 test_openclaw_comparison.py
```

Guides you through baseline vs enhanced testing.

---

## Current Status

**Working:**
- ✅ Context store (Qdrant + Supabase)
- ✅ Semantic retrieval with structured metadata
- ✅ Policy-aware reasoning
- ✅ Entity state tracking
- ✅ Risk flagging
- ✅ All core tests passing

**Next Steps:**
1. Deploy to Railway
2. Run OpenClaw baseline tests (without GeniOS)
3. Integrate GeniOS with OpenClaw
4. Run same tests with GeniOS
5. Document intelligence lift
6. Move to Segment 5 (full validation)

---

## Configuration

### Seed Data
Edit `data/seed.py` to add:
- Your organization profile
- Your policies
- Your investor relationships
- Entity states (warm/cold/very_warm)

### Decision Rules
Edit `reasoning/engine.py` prompt to adjust:
- When to BLOCK vs ESCALATE
- Policy enforcement logic
- Context usage guidance

### Retrieval
Edit `context/retriever.py` to adjust:
- Relevance threshold (default: 0.3)
- Number of results (default: 8)
- Context structure

---

## Environment Variables

Required:
- `GEMINI_API_KEY` - Google Gemini API key
- `QDRANT_URL` - Qdrant cloud URL
- `QDRANT_API_KEY` - Qdrant API key
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_KEY` - Supabase anon/service key
- `ORG_ID` - Your organization ID (default: genios_internal)

Optional:
- `OPENAI_API_KEY` - If using OpenAI instead of Gemini

---

## Contributing

This is a prototype. For production use:
- Add authentication
- Add rate limiting
- Improve error handling
- Add caching
- Add monitoring
- Expand test coverage

---

## License

Proprietary - GeniOS Brain Prototype

---

## Support

For issues or questions:
- Review `OPENCLAW_INTEGRATION.md` for integration help
- Check `DEPLOYMENT_CHECKLIST.md` for deployment steps
- Run `python3 test_system.py` to validate local setup

---

## Roadmap

**Prototype (Now):** Intelligence proof
**MVP:** Hard enforcement, multi-agent support
**Enterprise:** Regulatory-grade governance layer

See `prototype.txt` for full 48-hour build plan.
