'use client';

import { useSession } from 'next-auth/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Copy, Check, Terminal } from 'lucide-react';

export default function IntegrationsPage() {
  const { data: session } = useSession();
  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;
  const [activeTab, setActiveTab] = useState('python');
  const [copied, setCopied] = useState(false);

  const { data: keyData } = useQuery<{api_key: string}>({
    queryKey: ['apikey', orgId],
    queryFn: () => api.org.getApiKey(orgId, token),
    enabled: !!orgId && !!token,
  });

  const apiKey = keyData?.api_key || 'gn_live_YOUR_API_KEY_HERE';

  const snippets = {
    python: `import requests\n\ndef get_genios_context(entity: str, situation: str) -> dict:\n    response = requests.post(\n        "https://api.genios.io/v1/context",\n        headers={"Authorization": "Bearer ${apiKey}"},\n        json={"entity": entity, "situation": situation}\n    )\n    return response.json()\n\ncontext = get_genios_context("Rajan Mehta", "investor follow-up")\n\nsystem_prompt = f"""You are an investor relations assistant.\\n\nORGANIZATIONAL CONTEXT — read this before acting:\\n{context}\\n\nUse this context in everything you do."""`,
    n8n: `Node Type: HTTP Request\nMethod: POST\nURL: https://api.genios.io/v1/context\nAuthentication: Header Auth\n  Header Name: Authorization\n  Header Value: Bearer ${apiKey}\n\nBody (JSON):\n{\n  "entity": "{{ $json.contact_name }}",\n  "situation": "{{ $json.situation }}"\n}`,
    openclaw: `STEP 2: HTTP Request  ← THIS IS THE GENIOS CALL\n  Method: POST\n  URL: https://api.genios.io/v1/context\n  Headers:\n    Authorization: Bearer ${apiKey}\n    Content-Type: application/json\n  Body:\n    {\n      "entity": "{{contact_name}}",\n      "situation": "investor follow-up"\n    }\n  Save response as: org_context`,
    langgraph: `from langgraph.graph import StateGraph\nimport requests\n\ndef fetch_org_context(state: AgentState) -> AgentState:\n    response = requests.post(\n        "https://api.genios.io/v1/context",\n        headers={"Authorization": "Bearer ${apiKey}"},\n        json={"entity": state["contact"], "situation": "investor follow-up"}\n    )\n    state["org_context"] = response.json()\n    return state`
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(snippets[activeTab as keyof typeof snippets]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Integrations</h1>
      
      <Card>
        <CardHeader>
          <CardTitle>GenIOS Context API Snippets</CardTitle>
          <CardDescription>
            Copy and paste these snippets to integrate your agent with GenIOS. 
            The snippets automatically include your live API key.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2 mb-4 border-b pb-4">
            {Object.keys(snippets).map(k => (
              <Button
                key={k}
                variant={activeTab === k ? "default" : "outline"}
                className="capitalize"
                onClick={() => setActiveTab(k)}
              >
                {k}
              </Button>
            ))}
          </div>
          <div className="relative group">
            <div className="absolute right-2 top-2 z-10">
              <Button 
                variant="secondary" 
                size="sm" 
                onClick={handleCopy}
                className="gap-2 bg-slate-800 text-white hover:bg-slate-700 h-8"
              >
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                {copied ? 'Copied' : 'Copy Code'}
              </Button>
            </div>
            <pre className="p-4 bg-slate-900 rounded-lg overflow-x-auto text-sm text-slate-100 font-mono">
              <code>{snippets[activeTab as keyof typeof snippets]}</code>
            </pre>
          </div>
        </CardContent>
      </Card>
      
      <div className="mt-8 flex gap-4">
         <Card className="flex-1">
           <CardHeader>
             <CardTitle className="text-lg flex items-center gap-2">
               <Terminal className="h-5 w-5" />
               API Reference
             </CardTitle>
             <CardDescription>
               Check out the complete OpenAPI documentation for the context endpoint.
             </CardDescription>
           </CardHeader>
           <CardContent>
             <Button variant="outline" asChild>
               <a href="/docs" target="_blank">View API Docs</a>
             </Button>
           </CardContent>
         </Card>
      </div>
    </div>
  );
}
