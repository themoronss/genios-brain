# GeniOS Integration Guide

**For:** AI agent platforms, SaaS products, and developer teams who want to add **relationship intelligence** to their workflows in minutes — not months.

**Base URL:** `https://squid-app-2zuqf.ondigitalocean.app`
**Auth:** `Authorization: Bearer gn_live_<your_key>`

---

## 1. What GeniOS Provides

GeniOS is the **brain layer** for any AI agent or product that touches people-related data (emails, calendars, contacts, documents). It runs continuously across a customer's connected tools (Gmail, Calendar, Docs, Drive, Slack, Jira, Notion, HubSpot) and exposes:

- **Relationship intelligence** — stage (WARM / AT_RISK / COLD / NEEDS_ATTENTION), EWMA sentiment, sentiment trend, communication style, authority score, freshness score
- **Commitments** — automatically extracted from emails (who promised what, when, status)
- **Proactive insights** — 50+ detectors fire when something matters (going cold, overdue commitment, anomaly, role change)
- **Live tool fetch** — when cached graph misses, GeniOS calls Gmail / Calendar / Docs in real time
- **Reasoning + suggested actions** — every response includes a ready-to-use paragraph and concrete next step

**Pitch in one sentence:** *Pipes (your inbox/phone/CRM) + GeniOS (the brain) = an agent that actually understands context.*

---

## 2. Integration Paths — at a Glance

| # | Path | Setup time | Best for |
|---|---|---|---|
| 1 | **REST API** | 30 min | Any backend / agent in any language |
| 2 | **MCP Server** | 5 min | Claude Desktop, Cursor, Claude Web, ChatGPT, any MCP-compatible agent |
| 3 | **LangGraph Node** | 2 hrs | Modern agents built on LangGraph |
| 4 | **Webhook → Reverse Trigger** | 3 hrs | Proactive agents that act on detected events |
| 5 | **Python / Node SDK** | 15 min | Quick integration for Python or Node services |

You can mix paths. The most powerful combo is **MCP + Webhook** — your agent has on-demand intelligence (MCP) and gets woken up when the brain detects something proactively (webhook).

---

## 3. Path 1 — REST API (universal, language-agnostic)

### When to use
You have an agent, CRM, mailer, or app written in any language. You want to fetch relationship context **just-in-time** before the LLM acts.

### Endpoint

```
POST https://squid-app-2zuqf.ondigitalocean.app/v1/context
```

### Headers

```
Authorization: Bearer gn_live_xxxxx
Content-Type: application/json
```

### Input

```json
{
  "entity": "Alice Chen",
  "situation": "follow up about pricing",
  "agent_id": "my-sales-agent",
  "context_size": "medium"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `entity` | string | yes | Person name, email, or company |
| `situation` | string | no | Free-text context (drives intent classification + live fetch) |
| `agent_id` | string | no | Identifier for which agent is calling |
| `context_size` | string | no | `small` / `medium` / `large` |

### Output (typical response — abridged)

The full response is rich (35+ top-level fields). Below are the most useful ones for an agent integration:

```json
{
  "entity": {
    "id": "uuid",
    "name": "Alice Chen",
    "email": "alice@acme.com",
    "company": "Acme Inc",
    "relationship_stage": "WARM",
    "sentiment_ewma": 0.39,
    "sentiment_trend": "STABLE",
    "interaction_count": 7,
    "what_works": "Short emails with specific metrics",
    "what_to_avoid": "Long narrative emails",
    "is_broadcast": false,
    "response_rate": 0.71,
    "disclosure_level": "public"
  },
  "context_for_agent": "[ANOMALY: Alice's sentiment has declined 2.0 std devs] Alice from Acme — 7 exchanges, last contact 18 days ago, prefers concise + numbers...",
  "action_recommendation": "escalate",
  "narrative": "Synthesized 2–3 sentence story across all interactions",
  "agent_behavior": {
    "do": ["reference Q2 commitment concretely"],
    "avoid": ["generic 'circling back' tone"],
    "escalate_to_human_if": "sentiment dips below -0.3"
  },
  "anomalies": [
    {"type": "sentiment_drop", "z_score": -2.0, "since_days": 14}
  ],
  "scores": {
    "signal": 0.56,
    "authority": 0.30,
    "composite": 0.56,
    "freshness": 0.55,
    "confidence": 0.57,
    "consistency": 1.00
  },
  "confidence": 0.5688,
  "confidence_level": "medium",
  "intent_signal": {
    "intent": "informational",
    "domain": "contact",
    "emotion": "neutral",
    "urgency": "med",
    "requires_live_fetch": false
  },
  "recent_interactions": [
    {"date": "...", "subject": "...", "summary": "...", "direction": "outbound"}
  ],
  "company_contacts": [
    {"name": "...", "email": "...", "stage": "ACTIVE"}
  ],
  "live_fetch": {
    "total": 0,
    "sources_hit": []
  },
  "clm_state": "active",
  "flagged": false,
  "escalation_recommended": false,
  "cache_hit": true,
  "cache_source": "precomputed",
  "latency_ms": 380
}
```

> **Field reference:** the response includes 35+ fields. The ones above are the high-signal ones every agent will use. Other fields available: `match_confidence`, `matched_from`, `resolution_method`, `data_quality`, `coverage_score`, `sources_used`, `disclosure_rules`, `related_outbound`, `situation_signals`, `situation_type`, `hours_since_last_outbound`, `last_signal`, `cooldown_active`, `fingerprint_matches`, `pending_alerts`. Hit the API and inspect the full payload to see them all.

### Code — Node.js / TypeScript

```typescript
async function getRelationshipContext(entity: string, situation?: string) {
  const response = await fetch("https://squid-app-2zuqf.ondigitalocean.app/v1/context", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${process.env.GENIOS_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ entity, situation })
  });
  return await response.json();
}

// Use it
const ctx = await getRelationshipContext("Alice Chen", "follow up about pricing");
console.log(ctx.context_for_agent);    // ready for LLM prompt
console.log(ctx.action_recommendation); // show to user
```

### Code — Python

```python
import requests

def get_relationship_context(entity: str, situation: str = None) -> dict:
    r = requests.post(
        "https://squid-app-2zuqf.ondigitalocean.app/v1/context",
        headers={"Authorization": f"Bearer {GENIOS_KEY}"},
        json={"entity": entity, "situation": situation}
    )
    return r.json()

ctx = get_relationship_context("Alice Chen", "follow up about pricing")
print(ctx["context_for_agent"])
print(ctx["action_recommendation"])
```

### Latency
- Cached graph hit: **< 400 ms**
- Live tool fetch fallback: **2 – 12 sec**
- First call on a fresh contact: **3 – 5 sec**

---

## 4. Path 2 — MCP Server (zero-code for MCP-compatible agents)

### When to use
Your agent already speaks MCP (Model Context Protocol) — Claude Desktop, Cursor, Claude Web, ChatGPT, Cline, Windsurf, Zed, or any custom MCP client. **No code change needed in the agent itself.** The LLM auto-discovers GeniOS tools and decides when to call them.

### Setup

**Claude Web / ChatGPT (UI-based):**

1. Settings → Connectors → Add custom connector
2. Name: `GeniOS`
3. URL: `https://squid-app-2zuqf.ondigitalocean.app/mcp`
4. Advanced settings → Authorization → Bearer token → paste `gn_live_xxxxx`
5. Save → Connect → done

**Claude Desktop / Cursor / VS Code (config file):**

```yaml
mcp_servers:
  - name: genios
    url: https://squid-app-2zuqf.ondigitalocean.app/mcp
    auth:
      type: bearer
      token: gn_live_xxxxx
```

### Tools exposed (auto-discovered by LLM)

| Tool | What it does |
|---|---|
| `genios_get_context` | Full relationship bundle for a person/company |
| `genios_search_contacts` | Search contacts by partial name, stage, attention flags |
| `genios_list_insights` | Pull proactive alerts (anomalies, going cold, overdue) |
| `genios_live_search` | Real-time multi-tool search (Gmail / Calendar / Docs) |
| `genios_recent` | Latest brain activity (recommendations, transitions) |
| `genios_org_info` | Org profile, plan, usage |
| `genios_log_interaction` | Write-back: log an action just taken |
| `genios_log_outcome` | Feedback: was the context useful? |
| `genios_trigger_scan` | Manually trigger a proactive scan |
| `genios_sync_status` | Status of connected data sources |
| `genios_list_segments` | List contact segments |
| `genios_get_segment_members` | Members of a specific segment |

### What the LLM does

The agent's LLM sees the tool list and calls them naturally:
- *"What's the latest with Alice?"* → calls `genios_get_context`
- *"Anything I should know today?"* → calls `genios_list_insights`
- *"Find Razorpay invoices in my email"* → calls `genios_live_search`

**Bonus:** Every tool response includes a `pending_alerts` field. The LLM is instructed to surface these naturally as *"By the way, the brain noticed..."* — a built-in proactive interjection.

---

## 5. Path 3 — LangGraph Node (for graph-based agents)

### When to use
Your agent is built with **LangGraph** — the most common framework for production AI agents. GeniOS slots in as a dedicated node in the agent graph.

### Architecture

```
   Inbound trigger (email / scheduled)
                ↓
   ┌────────────────────────┐
   │  fetch_genios_context  │  ← GeniOS REST call
   └────────────┬───────────┘
                ▼
   ┌────────────────────────┐
   │  draft_reply (LLM)     │  ← uses ctx in prompt
   └────────────┬───────────┘
                ▼
   ┌────────────────────────┐
   │  send_via_<channel>    │  ← Inkbox / Gmail / etc
   └────────────────────────┘
```

### Code — LangGraph (Python)

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict
import requests

class AgentState(TypedDict):
    incoming_email: dict
    genios_context: dict
    draft_reply: str

GENIOS_URL = "https://squid-app-2zuqf.ondigitalocean.app"
GENIOS_KEY = "gn_live_xxxxx"

# Node 1 — pull GeniOS context
def fetch_genios_context(state: AgentState) -> AgentState:
    email = state["incoming_email"]
    response = requests.post(
        f"{GENIOS_URL}/v1/context",
        headers={"Authorization": f"Bearer {GENIOS_KEY}"},
        json={
            "entity": email["from"],
            "situation": f"replying to: {email['subject']}"
        }
    ).json()
    return {**state, "genios_context": response}

# Node 2 — draft reply with context
def draft_reply(state: AgentState) -> AgentState:
    ctx = state["genios_context"]
    email = state["incoming_email"]
    prompt = f"""Reply to this email using the relationship context.

CONTEXT:
{ctx['context_for_agent']}

Stage:           {ctx['entity']['relationship_stage']}
Sentiment:       {ctx['entity']['sentiment_ewma']} ({ctx['entity']['sentiment_trend']})
What works:      {ctx['entity'].get('what_works', '')}
What to avoid:   {ctx['entity'].get('what_to_avoid', '')}
Agent guidance:  {ctx.get('agent_behavior', {})}
Suggested:       {ctx['action_recommendation']}

EMAIL:
{email['body']}
"""
    reply = llm.invoke(prompt)
    return {**state, "draft_reply": reply}

# Node 3 — send
def send_email(state: AgentState) -> AgentState:
    inkbox.email.send(
        to=state["incoming_email"]["from"],
        body=state["draft_reply"]
    )
    return state

# Build the graph
graph = StateGraph(AgentState)
graph.add_node("fetch_context", fetch_genios_context)
graph.add_node("draft", draft_reply)
graph.add_node("send", send_email)
graph.add_edge("fetch_context", "draft")
graph.add_edge("draft", "send")
graph.add_edge("send", END)
graph.set_entry_point("fetch_context")

agent = graph.compile()
agent.invoke({"incoming_email": {"from": "alice@acme.com", "subject": "...", "body": "..."}})
```

### Why LangGraph specifically
- **State persists** across nodes — GeniOS context available in every later step
- **Resumable** — if agent crashes mid-workflow, restart from last node, GeniOS context still there
- **Observable** — each node's input/output can be logged independently for debugging

---

## 6. Path 4 — Webhook → Reverse Trigger (proactive agents)

### When to use
You want your agent to **act proactively** when GeniOS detects something — without the user having to ask. Examples: send a check-in when a contact goes cold, draft a follow-up when a commitment is overdue, alert sales when an investor goes silent.

### Architecture

```
   GeniOS brain (24/7)
        ↓
   Detector fires: "Alice going AT_RISK + board meeting Friday"
        ↓
   POST your-webhook-url/genios-webhook
        ↓
   Your agent wakes up → composes action → executes
```

### Webhook payload (what GeniOS sends to your endpoint)

```json
{
  "alert_id": "a1b2c3d4-...",
  "insight_type": "going_cold",
  "contact": {
    "name": "Alice Chen",
    "email": "alice@acme.com",
    "stage_change": "WARM → AT_RISK"
  },
  "title": "Alice Chen going cold — 18 days silent",
  "body": "Sentiment dropped 0.4 → 0.1. Q2 deal at risk.",
  "suggested_action": {
    "verb": "send_warm_check_in",
    "target": "alice@acme.com",
    "draft": "Hi Alice, wanted to circle back on the Q2 numbers we discussed last month..."
  },
  "priority": 0.78,
  "confidence": 0.82
}
```

### Your webhook handler (Express example)

```typescript
import express from "express";
const app = express();
app.use(express.json());

app.post("/genios-webhook", async (req, res) => {
  const alert = req.body;

  // Wake up your agent with the suggested action
  await yourAgent.execute({
    instruction: `${alert.title}\nBrain suggests: ${alert.suggested_action.draft}\nAct via the appropriate channel.`,
    contact: alert.contact
  });

  res.json({ ok: true });
});

app.listen(3000);
```

### Registering your webhook
Currently webhook URLs are configured per-org in your GeniOS dashboard or via a one-time API call. Contact your GeniOS rep to wire this up.

---

## 7. Path 5 — Python / Node SDKs

### Python

```bash
pip install genios
```

```python
from genios import Client

client = Client(api_key="gn_live_xxxxx")

ctx = client.context(entity="Alice Chen", situation="follow up")
print(ctx.context_for_agent)
print(ctx.action_recommendation)

insights = client.insights(limit=10)
for i in insights:
    print(i.title, i.priority)
```

### Node

```bash
npm install @genios/sdk
```

```typescript
import { Genios } from "@genios/sdk";

const genios = new Genios({ apiKey: "gn_live_xxxxx" });

const ctx = await genios.context({
  entity: "Alice Chen",
  situation: "follow up"
});
console.log(ctx.contextForAgent);

const insights = await genios.insights({ limit: 10 });
```

---

## 8. Authentication

All requests require a Bearer token in the `Authorization` header.

```
Authorization: Bearer gn_live_xxxxxxxxxxxxxxxxxxxxxxxxx
```

**Get your key:**
1. Log in to `https://brain.thegenios.com`
2. Settings → API Keys → Generate Key
3. Copy the `gn_live_...` token (shown once)

**Treat the key like a password.** Each call is rate-limited per key based on plan tier.

---

## 9. Plan Tiers & Limits

| Tier | Daily contexts | Rate / agent | Max contacts | Live fetches / day |
|---|---|---|---|---|
| Trial (5 days) | 100 | 10 / min | 100 | 10 |
| Hustler (monthly) | 200 | 20 / min | 300 | 100 |
| Startup (monthly) | 666 | 50 / min | 2000 | 1000 |

Overage is supported on Hustler and Startup tiers.

---

## 10. Common Use Cases

### A. Customer support agent (Inkbox-style)
Before the agent replies to an inbound, call `/v1/context` with the customer's email. Use `relationship_stage` + `sentiment_trend` to decide tone (escalate to human if `AT_RISK` or `frustrated`).

### B. Outbound sales agent
Before drafting an outreach, call `/v1/context` to pull `entity.what_works`, `entity.what_to_avoid`, and `recent_interactions`. Reference recent threads concretely instead of generic "circling back".

### C. Founder's executive assistant agent
Subscribe to webhook for `pending_alerts`. Your agent receives proactive alerts (going cold, overdue commitment, anomaly) and drafts the right action automatically.

### D. CRM enrichment
On contact view in your CRM, call `/v1/context` and display the bundle inline — stage, sentiment, last interaction, open commitments, suggested next step.

### E. Proactive notification feed
Hit `/v1/insights` periodically and surface the top items in your product UI as a "What needs your attention" panel.

---

## 11. Recommended Combo for Most Customers

**MCP (Path 2) + Webhook (Path 4)**

```
   ┌─────────────────────────────────────────────────────┐
   │  MCP            → agent has on-demand intelligence  │
   │  Webhook        → agent gets woken up proactively   │
   │                                                      │
   │  Setup time:    ~ 1 day                              │
   │  Code change:   ~ 50 lines                           │
   │  ROI:           agents become context-aware AND      │
   │                 proactive — major leap from default  │
   └─────────────────────────────────────────────────────┘
```

---

## 12. Why GeniOS (vs. building it yourself)

| Capability | DIY effort | Use GeniOS |
|---|---|---|
| Sentiment EWMA tracking | 2 weeks | 0 — built-in |
| 50+ proactive detectors | 6 months | 0 — running |
| Commitment LLM extraction | 1 month + tuning | 0 — built-in |
| Cross-tool graph (Gmail + Cal + Slack) | 2 – 3 quarters | 0 — Day 1 |
| Live email/calendar search fallback | 2 months | 0 — built-in |
| Hebbian learning loop | Research project | 0 — running nightly |
| Per-tenant calibration | Multi-week ML work | 0 — automatic |

---

## 13. Quick Verify (curl, 30 seconds)

```bash
curl -X POST https://squid-app-2zuqf.ondigitalocean.app/v1/context \
  -H "Authorization: Bearer gn_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{"entity":"Alice Chen","situation":"follow up"}'
```

You should see a JSON response with `entity`, `context_for_agent`, `action_recommendation`, `confidence`, `intent_signal`, `scores`, and `latency_ms` fields. If you see this — integration is working.

---

## 14. Support

- **Dashboard:** `https://brain.thegenios.com` (login + API key management)
- **Email:** `homiansmedia@gmail.com`
- **Direct support:** request a Slack/WhatsApp channel from your GeniOS rep

---

*Last updated: 2026-05-04*
*GeniOS Brain — the brain layer for AI agents.*
