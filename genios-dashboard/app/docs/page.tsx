import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function ApiDocsPage() {
  return (
    <div className="max-w-4xl mx-auto py-12 px-4 sm:px-6 lg:px-8 space-y-8">
      <div>
        <h1 className="text-3xl font-extrabold text-slate-900 mb-2">GenIOS Context API</h1>
        <p className="text-lg text-slate-600">The single endpoint to inject organizational awareness into your agents.</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-4 mb-2">
            <Badge variant="default" className="bg-indigo-600 hover:bg-indigo-700">POST</Badge>
            <span className="font-mono text-lg font-semibold tracking-tight">/v1/context</span>
          </div>
          <CardDescription>
            Fetch a concise, fully synthesized context paragraph about an entity (person or company) based on your Gmail communications graph.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <h3 className="text-sm font-semibold uppercase text-slate-500 tracking-wider mb-2">Headers</h3>
            <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 font-mono text-sm text-slate-300">
              <span className="text-indigo-400">Authorization</span>: Bearer &lt;YOUR_API_KEY&gt;<br />
              <span className="text-indigo-400">Content-Type</span>: application/json
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold uppercase text-slate-500 tracking-wider mb-2">Request Body</h3>
            <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 font-mono text-sm text-slate-300">
              {`{
  // The name of the person or company your agent is engaging with.
  "entity": "Rajan Mehta",
  
  // (Optional) What the agent is trying to do, for tailored instructions.
  "situation": "investor follow-up"
}`}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold uppercase text-slate-500 tracking-wider mb-2">Response JSON</h3>
            <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 font-mono text-sm text-slate-300">
              {`{
  // The name we matched your query to (fuzzy matching applied)
  "matched_from": "Rajan",
  "match_confidence": 0.94,
  
  // Ready-to-inject text block for your agent's system prompt!
  "context_for_agent": "Rajan Mehta from Sequoia Capital. Relationship: WARM. You've exchanged 12 messages. Last contact 3 days ago. Recent conversations have been positive and engaged. Primary topics: Series A, Retention data. ⚠️ Open commitment: Share updated LTV/CAC numbers. Prefers: concise emails. You last said: I'll get those numbers over to you on Monday.",
  
  // Detailed metadata structure
  "entity": {
    "name": "Rajan Mehta",
    "company": "Sequoia Capital",
    "relationship_stage": "WARM",
    "last_interaction": "3 days ago",
    "sentiment_trend": "positive",
    "communication_style": "concise emails",
    "topics_of_interest": [
      "Series A",
      "Retention data"
    ],
    "open_commitments": [
      "Share updated LTV/CAC numbers"
    ],
    "interaction_count": 12
  },
  
  // Measure of how completely we know this entity
  "confidence": 0.85
}`}
            </div>
          </div>
          
          <div className="pt-4 border-t border-slate-100">
            <h3 className="text-sm font-medium text-slate-900 mb-2">Error Codes</h3>
            <ul className="text-sm text-slate-600 list-disc pl-5 space-y-1">
              <li><strong>401 Unauthorized:</strong> Missing or incorrectly formatted Bearer token. Ensure your token starts with <code>gn_live_</code>.</li>
              <li><strong>404 Not Found:</strong> GenIOS could not find any contacts matching your entity query, even with fuzzy logic.</li>
            </ul>
          </div>
        </CardContent>
      </Card>
      
      <div className="text-center text-sm text-slate-500">
        Looking for code snippets? Go to your <a href="/dashboard/integrations" className="text-indigo-600 hover:text-indigo-800 underline">Integrations Dashboard</a>.
      </div>
    </div>
  );
}
