'use client';

import { useSession } from 'next-auth/react';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { ContextBundle } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Search, Copy, Check, FlaskConical, AlertCircle,
  MessageSquare, Bookmark, TrendingUp, Target,
  ShieldAlert, Sparkles,
} from 'lucide-react';
import { DraftModal } from '@/components/DraftModal';

export default function ContextTesterPage() {
  const { data: session } = useSession();
  const [contactName, setContactName] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [copied, setCopied] = useState(false);
  const [draftOpen, setDraftOpen] = useState(false);

  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  const { data: bundle, isLoading, error } = useQuery<ContextBundle>({
    queryKey: ['context-tester', orgId, submitted],
    queryFn: () => api.context.getBundle(orgId, submitted, token),
    enabled: !!orgId && !!token && submitted.length > 0,
    retry: false,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (contactName.trim()) setSubmitted(contactName.trim());
  };

  const handleCopy = () => {
    if (bundle?.context_for_agent) {
      navigator.clipboard.writeText(bundle.context_for_agent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const confidence = Math.round((bundle?.confidence || 0) * 100);

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">

        {/* Header */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
              <FlaskConical className="h-5 w-5 text-primary" />
            </div>
            <h1 className="text-2xl font-bold text-foreground">Context Tester</h1>
          </div>
          <p className="text-muted-foreground text-sm">
            Search any contact in your network to see exactly what your AI agents will know about them.
          </p>
        </div>

        {/* Search Box */}
        <div className="bg-card border border-border rounded-2xl p-6">
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Enter contact name — e.g. Mohit Jain, Flipkart..."
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                className="pl-9 bg-background border-border h-11"
                autoFocus
              />
            </div>
            <Button type="submit" disabled={!contactName.trim() || isLoading} className="gap-2 h-11 px-6">
              {isLoading ? (
                <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-foreground" />Searching…</>
              ) : (
                <><Search className="h-4 w-4" />Search</>
              )}
            </Button>
          </form>
        </div>

        {/* Error State */}
        {error && submitted && (
          <div className="bg-card border border-border rounded-2xl p-8 text-center space-y-3">
            <AlertCircle className="h-10 w-10 text-muted-foreground mx-auto" />
            <p className="font-semibold text-foreground">No contact found for "{submitted}"</p>
            <p className="text-sm text-muted-foreground">
              {error instanceof Error ? error.message : 'Try a different name or partial spelling.'}
            </p>
            <p className="text-xs text-muted-foreground/60">Fuzzy matching is supported — try just the first name.</p>
          </div>
        )}

        {/* Empty State */}
        {!submitted && !isLoading && (
          <div className="bg-card border border-border rounded-2xl p-12 text-center space-y-3">
            <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center mx-auto">
              <Search className="h-7 w-7 text-muted-foreground" />
            </div>
            <p className="font-medium text-foreground">Search for a contact</p>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
              Type a name above and hit Search — you'll see the full relationship context your AI agents will use.
            </p>
          </div>
        )}

        {/* Results */}
        {!isLoading && bundle && (
          <div className="space-y-5">

            {/* Identity + Confidence Row */}
            {bundle.entity && (
              <div className="bg-card border border-border rounded-2xl p-6 flex items-center justify-between gap-6">
                <div>
                  <h2 className="text-xl font-bold text-foreground">{bundle.entity.name}</h2>
                  {bundle.entity.company && (
                    <p className="text-sm text-muted-foreground mt-0.5">{bundle.entity.company}</p>
                  )}
                  <div className="flex flex-wrap gap-2 mt-3">
                    <Badge className="bg-primary/10 text-primary border-primary/20 hover:bg-primary/10">
                      {bundle.entity.relationship_stage}
                    </Badge>
                    <Badge variant="secondary">{bundle.entity.interaction_count} interactions</Badge>
                    <Badge variant="secondary">Last: {bundle.entity.last_interaction}</Badge>
                  </div>
                </div>
                {/* Confidence ring */}
                <div className="text-center shrink-0">
                  <div className="relative w-16 h-16">
                    <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
                      <circle cx="32" cy="32" r="26" strokeWidth="6" className="stroke-muted fill-none" />
                      <circle
                        cx="32" cy="32" r="26" strokeWidth="6"
                        className="fill-none stroke-primary transition-all duration-700"
                        strokeDasharray={`${(confidence / 100) * 163.4} 163.4`}
                        strokeLinecap="round"
                      />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-foreground">
                      {confidence}%
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Confidence</p>
                </div>
              </div>
            )}

            {/* Stats Row */}
            {bundle.entity && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {[
                  { label: 'Sentiment', value: bundle.entity.sentiment_trend },
                  { label: 'Last Contact', value: bundle.entity.last_interaction },
                  { label: 'Total Emails', value: bundle.entity.interaction_count },
                  { label: 'Open Items', value: Array.isArray(bundle.entity.open_commitments) ? bundle.entity.open_commitments.length : (bundle.entity.open_commitments || 0) },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-card border border-border rounded-xl px-4 py-4">
                    <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">{label}</p>
                    <p className="text-lg font-semibold text-foreground truncate">{value}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Context for Agent — the hero card */}
            <div className="bg-primary/5 border border-primary/20 rounded-2xl overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-primary/20">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <h3 className="font-semibold text-foreground">Context for AI Agent</h3>
                </div>
                <Button variant="outline" size="sm" onClick={handleCopy} className="gap-2 h-8 border-primary/30 hover:bg-primary/10">
                  {copied ? <><Check className="h-3.5 w-3.5 text-green-500" />Copied!</> : <><Copy className="h-3.5 w-3.5" />Copy</>}
                </Button>
              </div>
              <div className="px-6 py-5">
                <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap font-mono">
                  {bundle.context_for_agent}
                </p>
              </div>
              <div className="px-6 py-4 border-t border-primary/20">
                <Button onClick={() => setDraftOpen(true)} className="w-full gap-2">
                  <Sparkles className="h-4 w-4" />
                  Draft a Message with AI
                </Button>
              </div>
            </div>

            {/* Detail cards grid */}
            {bundle.entity && (
              <div className="grid md:grid-cols-2 gap-4">

                {/* Communication Style */}
                {bundle.entity.communication_style && (
                  <div className="bg-card border border-border rounded-2xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <MessageSquare className="h-4 w-4 text-muted-foreground" />
                      <h4 className="text-sm font-semibold text-foreground">Communication Style</h4>
                    </div>
                    <p className="text-sm text-muted-foreground">{bundle.entity.communication_style}</p>
                  </div>
                )}

                {/* Topics of Interest */}
                {bundle.entity.topics_of_interest?.length > 0 && (
                  <div className="bg-card border border-border rounded-2xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <Bookmark className="h-4 w-4 text-muted-foreground" />
                      <h4 className="text-sm font-semibold text-foreground">Topics of Interest</h4>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {bundle.entity.topics_of_interest.map((t: string) => (
                        <Badge key={t} variant="secondary">{t}</Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* What Works */}
                {bundle.entity.what_works && (
                  <div className="bg-card border border-border rounded-2xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingUp className="h-4 w-4 text-green-500" />
                      <h4 className="text-sm font-semibold text-foreground">What Works</h4>
                    </div>
                    <p className="text-sm text-muted-foreground">✅ {bundle.entity.what_works}</p>
                  </div>
                )}

                {/* What to Avoid */}
                {bundle.entity.what_to_avoid && (
                  <div className="bg-card border border-destructive/30 rounded-2xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <ShieldAlert className="h-4 w-4 text-destructive" />
                      <h4 className="text-sm font-semibold text-foreground">What to Avoid</h4>
                    </div>
                    <p className="text-sm text-muted-foreground">❌ {bundle.entity.what_to_avoid}</p>
                  </div>
                )}
              </div>
            )}

            {/* Open Commitments */}
            {bundle.entity?.open_commitments && Array.isArray(bundle.entity.open_commitments) && bundle.entity.open_commitments.length > 0 && (
              <div className="bg-card border border-amber-500/30 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Target className="h-4 w-4 text-amber-500" />
                  <h4 className="text-sm font-semibold text-foreground">Open Commitments</h4>
                </div>
                <div className="space-y-2">
                  {bundle.entity.open_commitments.map((c: string, i: number) => (
                    <div key={i} className="flex items-start gap-3 p-3 bg-amber-500/5 border border-amber-500/20 rounded-xl">
                      <span className="text-amber-500 mt-0.5 shrink-0">⚠️</span>
                      <p className="text-sm text-foreground">{c}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommended Next Step */}
            {bundle.entity?.recommended_action && (
              <div className="bg-card border border-green-500/30 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-2">
                  <Target className="h-4 w-4 text-green-500" />
                  <h4 className="text-sm font-semibold text-foreground">Recommended Next Step</h4>
                </div>
                <p className="text-sm text-muted-foreground">🎯 {bundle.entity.recommended_action}</p>
              </div>
            )}

          </div>
        )}
      </div>

      {/* Draft Modal */}
      {bundle?.entity && (
        <DraftModal
          open={draftOpen}
          onOpenChange={setDraftOpen}
          entityName={bundle.entity.name}
        />
      )}
    </div>
  );
}
