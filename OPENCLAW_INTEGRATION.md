# OpenClaw + GeniOS Integration Guide

## Overview
This guide shows you how to wire OpenClaw to call GeniOS Brain before executing actions, turning it into an intelligent, context-aware agent.

---

## Integration Architecture

```
User → OpenClaw → GeniOS /v1/enrich → OpenClaw (uses enriched_brief) → Execute Action → Logs
```

**GeniOS Role:** Pre-execution intelligence layer that provides:
- Context-aware enrichment
- Policy checking
- Risk flagging
- Decision guidance

**OpenClaw Role:** Execution layer that:
- Calls GeniOS before acting
- Uses enriched_brief as context
- Respects verdict (BLOCK/ESCALATE/PROCEED)
- Executes the action

---

## Step 1: Deploy GeniOS to Public URL

### Using Railway (Recommended)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Deploy
railway up
```

**After deployment:**
1. Go to Railway dashboard
2. Add environment variables:
   - `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`
   - `QDRANT_URL`
   - `QDRANT_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `ORG_ID=genios_internal`

3. Get your public URL: `https://your-app.railway.app`

4. Test it works:
```bash
curl https://your-app.railway.app/health
```

---

## Step 2: Configure OpenClaw to Call GeniOS

### Option A: System Prompt Integration (Easiest)

Add this to your OpenClaw system prompt:

```
BEFORE executing any task related to:
- Investor outreach
- Follow-ups
- Sharing documents/data
- Scheduling meetings
- Any multi-step workflow

YOU MUST call the GeniOS Brain API first:

API Endpoint: POST https://your-app.railway.app/v1/enrich
Request Body:
{
  "org_id": "genios_internal",
  "raw_message": "[the user's exact request]"
}

Response format:
{
  "verdict": "PROCEED | ESCALATE | BLOCK | CLARIFY",
  "enriched_brief": "detailed context and guidance",
  "recommended_action": "specific next step",
  "flags": ["any policy violations"],
  "key_context_used": ["facts used in decision"],
  "confidence": 0.95
}

HOW TO USE THE RESPONSE:
1. If verdict = "BLOCK" → Stop immediately and explain why to user
2. If verdict = "ESCALATE" → Ask user for approval before proceeding
3. If verdict = "CLARIFY" → Ask user for more details
4. If verdict = "PROCEED" → Use enriched_brief as your full context for the task

ALWAYS use enriched_brief as your working context. It contains:
- Specific names and relationship details
- Policy guidelines
- Past interaction history
- Personalization guidance
- Risk flags

DO NOT execute without calling GeniOS first for the task types above.
```

### Option B: Custom Tool Definition (If OpenClaw Supports)

Define a tool called `genios_brain`:

```json
{
  "name": "genios_brain",
  "description": "Call GeniOS Brain for intelligent context, policy checking, and decision guidance before executing tasks",
  "endpoint": "https://your-app.railway.app/v1/enrich",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json"
  },
  "body_schema": {
    "org_id": "genios_internal",
    "raw_message": "{{user_intent}}"
  },
  "required_for": [
    "investor_outreach",
    "follow_up",
    "document_sharing",
    "meeting_scheduling"
  ]
}
```

---

## Step 3: Test Integration

### Quick Test (Manual)

1. Start OpenClaw
2. Send this prompt: **"Follow up with Rahul about our prototype"**
3. Watch OpenClaw's behavior:
   - Does it call GeniOS API first?
   - Does it receive the enriched_brief?
   - Does it use the context in its response?

**Without GeniOS:**
```
"I'll draft a follow-up email to Rahul about the prototype."
[Generic email with no specific context]
```

**With GeniOS:**
```
"I'll draft a follow-up email to Rahul. He's a warm lead at SeedFund 
interested in AI governance, last contacted 10 days ago. I'll reference 
his interest in governance layers and share our prototype progress."
[Personalized, context-aware email]
```

---

## Step 4: Run Full Comparison Test

Use the comparison test suite in `test_openclaw_comparison.py`:

```bash
# This will guide you through baseline and enhanced testing
python3 test_openclaw_comparison.py
```

Follow the prompts to:
1. Test 10 scenarios WITHOUT GeniOS (baseline)
2. Enable GeniOS integration
3. Test same 10 scenarios WITH GeniOS
4. View side-by-side comparison

---

## Expected Intelligence Lift

| Metric | Without GeniOS | With GeniOS |
|--------|----------------|-------------|
| Uses specific names | ❌ Generic "investor" | ✅ "Rahul at SeedFund" |
| Policy aware | ❌ No | ✅ Flags violations |
| Remembers history | ❌ No | ✅ "Last contacted 10 days ago" |
| Personalized | ❌ Generic | ✅ References interests |
| Risk flagging | ❌ No | ✅ Flags cold investors, policy issues |
| Confidence | Low | High with context |

---

## Troubleshooting

### OpenClaw doesn't call GeniOS
- Check system prompt is properly configured
- Verify API endpoint is accessible
- Test endpoint manually with curl

### GeniOS returns errors
- Check Railway logs: `railway logs`
- Verify environment variables are set
- Test `/health` endpoint

### Integration works but no intelligence lift
- Review enriched_brief content—is it specific?
- Check if OpenClaw is actually using the enriched_brief
- Review seed data—is it complete and relevant?
- Test reasoning prompt in isolation

---

## Next Steps After Validation

1. **Document Results:** Save 5-10 side-by-side comparisons
2. **Identify Gaps:** What context is GeniOS missing?
3. **Improve Seed Data:** Add more investors, policies, history
4. **Refine Prompts:** Improve reasoning quality
5. **Move to MVP:** Add hard enforcement, multi-agent control

---

## Quick Reference

**GeniOS API Endpoint:**
```bash
POST https://your-app.railway.app/v1/enrich
Content-Type: application/json

{
  "org_id": "genios_internal",
  "raw_message": "your user intent here"
}
```

**Response Fields:**
- `verdict`: PROCEED | ESCALATE | BLOCK | CLARIFY
- `enriched_brief`: Use this as context
- `recommended_action`: Specific next step
- `flags`: Policy violations/concerns
- `key_context_used`: Facts supporting decision
- `confidence`: 0.0-1.0
