'use client';

import { useSession } from 'next-auth/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Copy, Check, Plug, Terminal, BookOpen, Zap } from 'lucide-react';

const TAB_META: Record<string, { label: string; icon: string; description: string }> = {
  python:   { label: 'Python',    icon: '🐍', description: 'Use with any Python-based agent or script' },
  n8n:      { label: 'n8n',       icon: '🔁', description: 'Drop into any n8n HTTP Request node' },
  openclaw: { label: 'OpenClaw',  icon: '⚙️', description: 'For OpenClaw workflow automations' },
  langgraph:{ label: 'LangGraph', icon: '🦜', description: 'Use inside a LangGraph agent state node' },
};

export default function IntegrationsPage() {
  const { data: session } = useSession();
  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;
  const [activeTab, setActiveTab] = useState('python');
  const [copied, setCopied] = useState(false);

  const { data: keyData } = useQuery<{ api_key: string }>({
    queryKey: ['apikey', orgId],
    queryFn: () => api.org.getApiKey(orgId, token),
    enabled: !!orgId && !!token,
  });

  const apiKey = keyData?.api_key || 'gn_live_YOUR_API_KEY_HERE';

  const snippets: Record<string, string> = {
    python: `import requests

def get_genios_context(entity: str, situation: str) -> dict:
    response = requests.post(
        "https://api.genios.io/v1/context",
        headers={"Authorization": "Bearer ${apiKey}"},
        json={"entity": entity, "situation": situation}
    )
    return response.json()

context = get_genios_context("Rajan Mehta", "investor follow-up")

system_prompt = f"""You are an investor relations assistant.

ORGANIZATIONAL CONTEXT — read this before acting:
{context}

Use this context in everything you do."""`,

    n8n: `Node Type: HTTP Request
Method: POST
URL: https://api.genios.io/v1/context
Authentication: Header Auth
  Header Name: Authorization
  Header Value: Bearer ${apiKey}

Body (JSON):
{
  "entity": "{{ $json.contact_name }}",
  "situation": "{{ $json.situation }}"
}`,

    openclaw: `STEP 2: HTTP Request  ← THIS IS THE GENIOS CALL
  Method: POST
  URL: https://api.genios.io/v1/context
  Headers:
    Authorization: Bearer ${apiKey}
    Content-Type: application/json
  Body:
    {
      "entity": "{{contact_name}}",
      "situation": "investor follow-up"
    }
  Save response as: org_context`,

    langgraph: `from langgraph.graph import StateGraph
import requests

def fetch_org_context(state: AgentState) -> AgentState:
    response = requests.post(
        "https://api.genios.io/v1/context",
        headers={"Authorization": "Bearer ${apiKey}"},
        json={
            "entity": state["contact"],
            "situation": "investor follow-up"
        }
    )
    state["org_context"] = response.json()
    return state`,
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(snippets[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const activeMeta = TAB_META[activeTab];

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">

        {/* Header */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
              <Plug className="h-5 w-5 text-primary" />
            </div>
            <h1 className="text-2xl font-bold text-foreground">Integrations</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Connect GenIOS to your AI agents and automations. Copy any snippet below — your live API key is already embedded.
          </p>
        </div>

        {/* Code snippets card */}
        <div className="bg-card border border-border rounded-2xl overflow-hidden">

          {/* Tab row */}
          <div className="flex items-center gap-1 px-4 pt-4 pb-0 border-b border-border overflow-x-auto">
            {Object.entries(TAB_META).map(([key, meta]) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg border-b-2 transition-colors shrink-0
                  ${activeTab === key
                    ? 'border-primary text-primary bg-primary/5'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/50'
                  }`}
              >
                <span>{meta.icon}</span>
                {meta.label}
              </button>
            ))}
          </div>

          {/* Tab description */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-muted/30">
            <p className="text-xs text-muted-foreground">{activeMeta.description}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="gap-2 h-8"
            >
              {copied
                ? <><Check className="h-3.5 w-3.5 text-green-500" />Copied!</>
                : <><Copy className="h-3.5 w-3.5" />Copy Code</>
              }
            </Button>
          </div>

          {/* Code block — intentionally dark always (code editors are always dark) */}
          <div className="overflow-x-auto">
            <pre className="p-6 bg-[#0d1117] text-sm text-slate-200 font-mono leading-relaxed min-h-[220px]">
              <code>{snippets[activeTab]}</code>
            </pre>
          </div>
        </div>

        {/* Info cards row */}
        <div className="grid sm:grid-cols-3 gap-4">

          <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <Terminal className="h-4 w-4 text-primary" />
            </div>
            <h3 className="font-semibold text-foreground text-sm">API Reference</h3>
            <p className="text-xs text-muted-foreground">Full OpenAPI docs for the context endpoint — all fields, request formats and response shapes.</p>
            <Button variant="outline" size="sm" asChild className="w-full">
              <a href="/docs" target="_blank">View API Docs</a>
            </Button>
          </div>

          <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <Zap className="h-4 w-4 text-emerald-500" />
            </div>
            <h3 className="font-semibold text-foreground text-sm">How it works</h3>
            <p className="text-xs text-muted-foreground">
              Your agent sends a contact name. GenIOS returns a rich relationship context paragraph. Agent uses it for smarter replies.
            </p>
          </div>

          <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
              <BookOpen className="h-4 w-4 text-amber-500" />
            </div>
            <h3 className="font-semibold text-foreground text-sm">Get your API key</h3>
            <p className="text-xs text-muted-foreground">
              Your live API key is on the Settings page. Never expose it in client-side code or public repositories.
            </p>
            <Button variant="outline" size="sm" asChild className="w-full">
              <a href="/dashboard/settings">Go to Settings</a>
            </Button>
          </div>

        </div>

      </div>
    </div>
  );
}
