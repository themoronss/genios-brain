'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Copy, Check, ChevronDown, ChevronRight, Code2, Zap, FileText } from 'lucide-react';

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <Button variant="outline" size="sm" onClick={handleCopy} className="gap-1.5 h-7 text-xs shrink-0">
      {copied ? <><Check className="h-3 w-3 text-green-500" />Copied</> : <><Copy className="h-3 w-3" />Copy</>}
    </Button>
  );
}

function CodeBlock({ code, language }: { code: string; language?: string }) {
  return (
    <div className="relative group">
      <div className="absolute right-3 top-3 opacity-0 group-hover:opacity-100 transition-opacity">
        <CopyButton text={code} />
      </div>
      <pre className="p-4 bg-[#0d1117] rounded-lg text-sm text-slate-200 font-mono leading-relaxed overflow-x-auto">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function MethodBadge({ method }: { method: 'GET' | 'POST' }) {
  return (
    <Badge
      variant="default"
      className={method === 'POST'
        ? 'bg-indigo-600 hover:bg-indigo-700 text-white'
        : 'bg-emerald-600 hover:bg-emerald-700 text-white'}
    >
      {method}
    </Badge>
  );
}

function SectionHeader({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="flex items-start gap-3 mb-6">
      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
        {icon}
      </div>
      <div>
        <h2 className="text-xl font-bold text-foreground">{title}</h2>
        <p className="text-sm text-muted-foreground mt-0.5">{description}</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Collapsible Endpoint Card                                          */
/* ------------------------------------------------------------------ */

function EndpointCard({
  method,
  path,
  description,
  children,
  defaultOpen = false,
}: {
  method: 'GET' | 'POST';
  path: string;
  description: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Card className="overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left"
      >
        <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors">
          <div className="flex items-center gap-3">
            {open
              ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
              : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
            <MethodBadge method={method} />
            <span className="font-mono text-sm font-semibold tracking-tight text-foreground">{path}</span>
          </div>
          <CardDescription className="ml-[4.25rem]">{description}</CardDescription>
        </CardHeader>
      </button>
      {open && (
        <CardContent className="space-y-5 border-t border-border pt-5">
          {children}
        </CardContent>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Collapsible Guide Card                                             */
/* ------------------------------------------------------------------ */

function GuideCard({
  icon,
  title,
  description,
  code,
  defaultOpen = false,
}: {
  icon: string;
  title: string;
  description: string;
  code: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Card className="overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left"
      >
        <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors">
          <div className="flex items-center gap-3">
            {open
              ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
              : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
            <span className="text-lg">{icon}</span>
            <div>
              <span className="font-semibold text-sm text-foreground">{title}</span>
              <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
            </div>
          </div>
        </CardHeader>
      </button>
      {open && (
        <CardContent className="border-t border-border pt-5">
          <CodeBlock code={code} />
        </CardContent>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-section label                                                   */
/* ------------------------------------------------------------------ */

function SubLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2">{children}</h3>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function ApiDocsPage() {
  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-12">

        {/* Page header */}
        <div>
          <h1 className="text-3xl font-extrabold text-foreground mb-2">GenIOS Context API</h1>
          <p className="text-lg text-muted-foreground">
            Complete reference for injecting organizational awareness into your agents.
          </p>
        </div>

        {/* ============================================================ */}
        {/*  SECTION 1 — API Reference                                    */}
        {/* ============================================================ */}
        <section className="space-y-4">
          <SectionHeader
            icon={<FileText className="h-5 w-5 text-primary" />}
            title="API Reference"
            description="All available endpoints with request/response schemas."
          />

          {/* 1. POST /v1/context — kept from original */}
          <EndpointCard
            method="POST"
            path="/v1/context"
            description="Fetch a synthesized context paragraph about an entity (person or company) based on your communications graph."
            defaultOpen={false}
          >
            <div>
              <SubLabel>Headers</SubLabel>
              <CodeBlock code={`Authorization: Bearer <YOUR_API_KEY>
Content-Type: application/json`} />
            </div>
            <div>
              <SubLabel>Request Body</SubLabel>
              <CodeBlock code={`{
  // The name of the person or company your agent is engaging with.
  "entity": "Rajan Mehta",

  // (Optional) What the agent is trying to do, for tailored instructions.
  "situation": "investor follow-up"
}`} />
            </div>
            <div>
              <SubLabel>Response</SubLabel>
              <CodeBlock code={`{
  "matched_from": "Rajan",
  "match_confidence": 0.94,
  "context_for_agent": "Rajan Mehta from Sequoia Capital. Relationship: WARM. You've exchanged 12 messages. Last contact 3 days ago. Recent conversations have been positive and engaged. Primary topics: Series A, Retention data. Open commitment: Share updated LTV/CAC numbers.",
  "entity": {
    "name": "Rajan Mehta",
    "company": "Sequoia Capital",
    "relationship_stage": "WARM",
    "last_interaction": "3 days ago",
    "sentiment_trend": "positive",
    "communication_style": "concise emails",
    "topics_of_interest": ["Series A", "Retention data"],
    "open_commitments": ["Share updated LTV/CAC numbers"],
    "interaction_count": 12
  },
  "confidence": 0.85
}`} />
            </div>
            <div className="pt-2 border-t border-border">
              <SubLabel>Error Codes</SubLabel>
              <ul className="text-sm text-muted-foreground list-disc pl-5 space-y-1">
                <li><strong className="text-foreground">401 Unauthorized:</strong> Missing or incorrectly formatted Bearer token.</li>
                <li><strong className="text-foreground">404 Not Found:</strong> No contacts matching your entity query.</li>
              </ul>
            </div>
          </EndpointCard>

          {/* 2. POST /v1/context/outcome */}
          <EndpointCard
            method="POST"
            path="/v1/context/outcome"
            description="Report action outcomes back to GenIOS so the brain learns from every interaction."
          >
            <div>
              <SubLabel>Request Body</SubLabel>
              <CodeBlock code={`{
  "org_id": "org_abc123",
  "session_id": "sess_xyz789",
  "agent_id": "agent_outreach_01",
  "action_type": "send_email",
  "target_entity": "Rajan Mehta",
  "outcome": {
    "type": "EXECUTED",       // EXECUTED | EDITED | REJECTED | ESCALATED
    "result": "Email sent successfully",
    "human_edited": false,
    "edit_delta": null
  },
  "interaction_record": {
    "subject": "Follow-up: Series A metrics",
    "direction": "outbound",
    "topics": ["Series A", "LTV/CAC"],
    "commitment_made": "Send updated deck by Friday"
  }
}`} />
            </div>
            <div>
              <SubLabel>Response</SubLabel>
              <CodeBlock code={`{
  "learned": true,
  "graph_updated": true,
  "aer_delta": 0.02
}`} />
            </div>
            <div className="pt-2 border-t border-border">
              <SubLabel>Outcome Types</SubLabel>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { type: 'EXECUTED', desc: 'Agent action was carried out as-is' },
                  { type: 'EDITED', desc: 'Human modified the agent output before sending' },
                  { type: 'REJECTED', desc: 'Human rejected the agent suggestion entirely' },
                  { type: 'ESCALATED', desc: 'Action was escalated to a human for review' },
                ].map(({ type, desc }) => (
                  <div key={type} className="bg-muted/50 rounded-lg p-3">
                    <code className="text-xs font-semibold text-primary">{type}</code>
                    <p className="text-xs text-muted-foreground mt-1">{desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </EndpointCard>

          {/* 3. GET /v1/graph/stats */}
          <EndpointCard
            method="GET"
            path="/v1/graph/stats"
            description="Retrieve health and status metrics for your organization's knowledge graph."
          >
            <div>
              <SubLabel>Headers</SubLabel>
              <CodeBlock code={`Authorization: Bearer <YOUR_API_KEY>`} />
            </div>
            <div>
              <SubLabel>Response</SubLabel>
              <CodeBlock code={`{
  "nodes_count": 1284,
  "edges_count": 3721,
  "communities_count": 18,
  "quality_score": 0.87,
  "brain_status": "ACTIVE",   // "ACTIVE" | "BUILDING" | "DEGRADED"
  "avg_confidence": 0.82,
  "last_computed_at": "2026-03-22T08:15:00Z"
}`} />
            </div>
            <div className="pt-2 border-t border-border">
              <SubLabel>Brain Status Values</SubLabel>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { status: 'ACTIVE', desc: 'Graph is fully built and serving queries', color: 'text-emerald-500' },
                  { status: 'BUILDING', desc: 'Initial ingestion in progress', color: 'text-amber-500' },
                  { status: 'DEGRADED', desc: 'Source offline or quality below threshold', color: 'text-red-500' },
                ].map(({ status, desc, color }) => (
                  <div key={status} className="bg-muted/50 rounded-lg p-3">
                    <code className={`text-xs font-semibold ${color}`}>{status}</code>
                    <p className="text-xs text-muted-foreground mt-1">{desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </EndpointCard>

          {/* 4. POST /v1/context/search */}
          <EndpointCard
            method="POST"
            path="/v1/context/search"
            description="Search and filter your relationship graph with temporal or semantic queries."
          >
            <div>
              <SubLabel>Request Body</SubLabel>
              <CodeBlock code={`{
  "org_id": "org_abc123",
  "query_type": "temporal",    // "temporal" | "semantic"
  "filter": {
    "stages": ["WARM", "HOT"],
    "last_contact_days_min": 7,
    "last_contact_days_max": 30,
    "entity_types": ["person", "company"]
  },
  "limit": 20
}`} />
            </div>
            <div>
              <SubLabel>Response</SubLabel>
              <CodeBlock code={`{
  "results": [
    {
      "entity": "Rajan Mehta",
      "company": "Sequoia Capital",
      "relationship_stage": "WARM",
      "last_contact": "2026-03-15T10:30:00Z",
      "confidence": 0.91,
      "relevance_score": 0.95,
      "topics": ["Series A", "Retention data"],
      "open_commitments": 1
    }
  ],
  "total_matches": 47,
  "returned": 20,
  "query_type": "temporal"
}`} />
            </div>
            <div className="pt-2 border-t border-border">
              <SubLabel>Query Types</SubLabel>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-muted/50 rounded-lg p-3">
                  <code className="text-xs font-semibold text-primary">temporal</code>
                  <p className="text-xs text-muted-foreground mt-1">Filter by recency, last contact window, and interaction frequency.</p>
                </div>
                <div className="bg-muted/50 rounded-lg p-3">
                  <code className="text-xs font-semibold text-primary">semantic</code>
                  <p className="text-xs text-muted-foreground mt-1">Search by topic similarity, relationship context, and entity attributes.</p>
                </div>
              </div>
            </div>
          </EndpointCard>
        </section>

        {/* ============================================================ */}
        {/*  SECTION 2 — Integration Guides                               */}
        {/* ============================================================ */}
        <section className="space-y-4">
          <SectionHeader
            icon={<Code2 className="h-5 w-5 text-primary" />}
            title="Integration Guides"
            description="Copy-paste snippets to connect GenIOS to your stack."
          />

          <GuideCard
            icon="🔁"
            title="n8n"
            description="HTTP Request node setup with body template"
            code={`// n8n HTTP Request Node Configuration
// ─────────────────────────────────────

Node Type:       HTTP Request
Method:          POST
URL:             https://api.genios.io/v1/context

Authentication:  Header Auth
  Header Name:   Authorization
  Header Value:  Bearer gn_live_YOUR_API_KEY

Body (JSON):
{
  "entity": "{{ $json.contact_name }}",
  "situation": "{{ $json.task_type }}"
}

// Wire the output into your next node:
//   {{ $json.context_for_agent }}  → system prompt
//   {{ $json.confidence }}         → confidence gate`}
          />

          <GuideCard
            icon="🦜"
            title="LangGraph"
            description="Python orchestrator pattern with StateGraph: fetch_context -> confidence_router -> execute/escalate"
            code={`from langgraph.graph import StateGraph, END
from typing import TypedDict
import requests

API_KEY = "gn_live_YOUR_API_KEY"

class AgentState(TypedDict):
    contact: str
    situation: str
    org_context: dict
    confidence: float
    result: str

def fetch_context(state: AgentState) -> AgentState:
    resp = requests.post(
        "https://api.genios.io/v1/context",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"entity": state["contact"], "situation": state["situation"]}
    )
    data = resp.json()
    state["org_context"] = data
    state["confidence"] = data.get("confidence", 0)
    return state

def confidence_router(state: AgentState) -> str:
    if state["confidence"] >= 0.80:
        return "execute"
    return "escalate"

def execute(state: AgentState) -> AgentState:
    state["result"] = f"Executed with context: {state['org_context']['context_for_agent']}"
    return state

def escalate(state: AgentState) -> AgentState:
    state["result"] = "Escalated to human — confidence too low"
    return state

graph = StateGraph(AgentState)
graph.add_node("fetch_context", fetch_context)
graph.add_node("execute", execute)
graph.add_node("escalate", escalate)
graph.set_entry_point("fetch_context")
graph.add_conditional_edges("fetch_context", confidence_router)
graph.add_edge("execute", END)
graph.add_edge("escalate", END)

app = graph.compile()
result = app.invoke({"contact": "Rajan Mehta", "situation": "investor follow-up"})`}
          />

          <GuideCard
            icon="🤖"
            title="CrewAI"
            description="@tool decorator pattern with get_org_context function"
            code={`from crewai import Agent, Task, Crew
from crewai.tools import tool
import requests

API_KEY = "gn_live_YOUR_API_KEY"

@tool("Get Org Context")
def get_org_context(entity: str, situation: str = "") -> str:
    """Fetch organizational context about a person or company from GenIOS.
    Returns a rich context paragraph with relationship history, sentiment,
    open commitments, and communication preferences."""
    resp = requests.post(
        "https://api.genios.io/v1/context",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"entity": entity, "situation": situation}
    )
    data = resp.json()
    return data.get("context_for_agent", "No context found.")

outreach_agent = Agent(
    role="Outreach Specialist",
    goal="Send personalized, context-aware messages",
    tools=[get_org_context],
    verbose=True
)

task = Task(
    description="Draft a follow-up email to Rajan Mehta about Series A.",
    agent=outreach_agent
)

crew = Crew(agents=[outreach_agent], tasks=[task])
result = crew.kickoff()`}
          />

          <GuideCard
            icon="🐍"
            title="REST / Custom"
            description="Minimal 10-line Python snippet using the requests library"
            code={`import requests

def get_genios_context(entity: str, situation: str = "") -> dict:
    response = requests.post(
        "https://api.genios.io/v1/context",
        headers={"Authorization": "Bearer gn_live_YOUR_API_KEY"},
        json={"entity": entity, "situation": situation}
    )
    response.raise_for_status()
    return response.json()

# Usage
ctx = get_genios_context("Rajan Mehta", "investor follow-up")
print(ctx["context_for_agent"])
print(f"Confidence: {ctx['confidence']}")`}
          />
        </section>

        {/* ============================================================ */}
        {/*  SECTION 3 — Quick Reference                                  */}
        {/* ============================================================ */}
        <section className="space-y-4">
          <SectionHeader
            icon={<Zap className="h-5 w-5 text-primary" />}
            title="Quick Reference"
            description="Confidence thresholds, error codes, and latency contracts at a glance."
          />

          <div className="grid md:grid-cols-3 gap-4">

            {/* Confidence Thresholds */}
            <Card>
              <CardHeader className="pb-3">
                <h3 className="text-sm font-semibold text-foreground">Confidence Thresholds</h3>
                <CardDescription>How to gate agent actions based on confidence score.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {[
                  { range: '> 0.80', action: 'Execute', color: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400', desc: 'Safe to auto-execute' },
                  { range: '0.60 - 0.80', action: 'Caution', color: 'bg-amber-500/15 text-amber-600 dark:text-amber-400', desc: 'Proceed with care' },
                  { range: '0.40 - 0.60', action: 'Ask Human', color: 'bg-orange-500/15 text-orange-600 dark:text-orange-400', desc: 'Escalate for review' },
                  { range: '< 0.40', action: 'Block', color: 'bg-red-500/15 text-red-600 dark:text-red-400', desc: 'Do not auto-act' },
                ].map(({ range, action, color, desc }) => (
                  <div key={range} className={`rounded-lg px-3 py-2.5 ${color}`}>
                    <div className="flex items-center justify-between">
                      <code className="text-xs font-bold">{range}</code>
                      <span className="text-xs font-semibold">{action}</span>
                    </div>
                    <p className="text-xs opacity-80 mt-0.5">{desc}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Error Codes */}
            <Card>
              <CardHeader className="pb-3">
                <h3 className="text-sm font-semibold text-foreground">Error Codes</h3>
                <CardDescription>Machine-readable error codes returned in the response body.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-1.5">
                  {[
                    'graph_not_ready',
                    'entity_not_found',
                    'entity_ambiguous',
                    'confidence_too_low',
                    'source_offline',
                    'conflict_detected',
                    'authority_blocked',
                    'rate_limit_exceeded',
                  ].map((code) => (
                    <div key={code} className="flex items-center gap-2 bg-muted/50 rounded-md px-3 py-1.5">
                      <code className="text-xs font-mono text-foreground">{code}</code>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Latency Contracts */}
            <Card>
              <CardHeader className="pb-3">
                <h3 className="text-sm font-semibold text-foreground">Latency Contracts</h3>
                <CardDescription>p95 response times by query type.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {[
                  { type: 'Cache hit', latency: '< 15 ms', bar: 'w-[8%]' },
                  { type: 'Entity-anchored', latency: '< 200 ms', bar: 'w-[50%]' },
                  { type: 'Temporal', latency: '< 300 ms', bar: 'w-[75%]' },
                  { type: 'Situational', latency: '< 400 ms', bar: 'w-[100%]' },
                ].map(({ type, latency, bar }) => (
                  <div key={type} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">{type}</span>
                      <code className="font-mono font-semibold text-foreground">{latency}</code>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div className={`h-full bg-primary/60 rounded-full ${bar}`} />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

          </div>
        </section>

        {/* Footer link */}
        <div className="text-center text-sm text-muted-foreground pb-8">
          Looking for live code snippets with your API key?{' '}
          <a href="/dashboard/integrations" className="text-primary hover:text-primary/80 underline underline-offset-4">
            Integrations Dashboard
          </a>
        </div>

      </div>
    </div>
  );
}
