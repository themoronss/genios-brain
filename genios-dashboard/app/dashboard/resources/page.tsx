'use client';

import { BookOpen, Zap, Brain, Link2, Mail, ArrowRight } from 'lucide-react';

const USE_CASES = [
  {
    icon: Mail,
    title: 'Pre-meeting prep',
    description: 'Before any call or meeting, ask GeniOS for context on who you\'re meeting. Get relationship history, sentiment, open commitments, and a recommended tone — in seconds.',
    example: '"Tell me about John Smith before my 3pm call"',
  },
  {
    icon: Zap,
    title: 'Outreach prioritization',
    description: 'Stop guessing who to reach out to. GeniOS surfaces warm contacts who\'ve gone quiet, relationships at risk, and follow-ups you\'ve missed.',
    example: '"Who in my network needs attention this week?"',
  },
  {
    icon: Brain,
    title: 'Agent-ready context',
    description: 'Connect GeniOS to your AI agents via the API. Your agents get structured relationship context before composing emails, scheduling meetings, or updating CRMs.',
    example: 'POST /v1/context with entity name → get relationship bundle',
  },
  {
    icon: Link2,
    title: 'CRM augmentation',
    description: 'GeniOS doesn\'t replace your CRM — it augments it. While your CRM tracks deals and pipeline, GeniOS tracks relationship quality, momentum, and trust.',
    example: 'Combine GeniOS context with HubSpot deals for complete picture',
  },
];

const CONCEPTS = [
  {
    term: 'Relationship Stage',
    definition: 'Each contact is classified: ACTIVE (engaged recently), WARM (fading), NEEDS_ATTENTION (at risk), DORMANT (cold), AT_RISK (negative sentiment). Stages update after every sync.',
  },
  {
    term: '5-Score System',
    definition: 'Every contact gets 5 scores: Freshness (recency), Confidence (data completeness), Consistency (agreement across sources), Signal (email engagement quality), Authority (source reliability). Composite ≥ 0.45 required to include in context.',
  },
  {
    term: 'Context Bundle',
    definition: 'A structured JSON package containing entity details, relationship scores, recent interactions, open commitments, and a ready-to-use context paragraph for LLM prompts.',
  },
  {
    term: 'Community Detection',
    definition: 'GeniOS automatically groups your contacts into communities using the Louvain algorithm — clusters of people who\'re connected through shared interactions.',
  },
  {
    term: 'AER (Autonomous Execution Rate)',
    definition: 'The percentage of AI-generated actions executed without human edits. A rising AER means your agents are becoming more trusted over time.',
  },
];

export default function ResourcesPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-10 pb-10">
      {/* Hero */}
      <div className="text-center pt-4 space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-xs text-primary font-medium">
          <BookOpen className="w-3.5 h-3.5" />
          Resources
        </div>
        <h1 className="text-3xl font-bold text-foreground">What is GeniOS Brain?</h1>
        <p className="text-muted-foreground max-w-2xl mx-auto">
          GeniOS Brain is a relationship intelligence layer for AI-powered founders and executives.
          It turns your Gmail history into a live, scored relationship graph — so your agents
          always have context before acting.
        </p>
      </div>

      {/* Use Cases */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-4">Use Cases</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {USE_CASES.map((uc) => {
            const Icon = uc.icon;
            return (
              <div key={uc.title} className="border border-border rounded-xl p-5 bg-card space-y-2">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-primary/10">
                    <Icon className="w-4 h-4 text-primary" />
                  </div>
                  <h3 className="font-semibold text-foreground text-sm">{uc.title}</h3>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">{uc.description}</p>
                <p className="text-xs text-primary/70 bg-primary/5 rounded-lg px-3 py-2 font-mono">
                  {uc.example}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Key Concepts */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-4">Key Concepts</h2>
        <div className="space-y-3">
          {CONCEPTS.map((c) => (
            <div key={c.term} className="border border-border rounded-xl p-4 bg-card">
              <p className="text-sm font-semibold text-foreground">{c.term}</p>
              <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{c.definition}</p>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="border border-border rounded-xl p-6 bg-card text-center space-y-3">
        <h3 className="font-semibold text-foreground">Ready to build with GeniOS?</h3>
        <p className="text-sm text-muted-foreground">
          Check the API documentation for full endpoint reference, integration guides, and code examples.
        </p>
        <a
          href="/dashboard/settings"
          className="inline-flex items-center gap-2 text-sm text-primary hover:underline font-medium"
        >
          Get your API key <ArrowRight className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
}
