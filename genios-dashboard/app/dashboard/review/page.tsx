'use client';

import { useSession } from 'next-auth/react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { GitMerge, X, Clock, User, AlertTriangle, CheckCircle, RefreshCcw } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface MergeCandidate {
  id: string;
  match_score: number;
  match_reason: string;
  status: string;
  created_at: string;
  contact_a: ContactSummary;
  contact_b: ContactSummary;
}

interface ContactSummary {
  id: string;
  name: string;
  email: string;
  company: string | null;
  entity_type: string;
  interaction_count: number;
  last_interaction_at: string | null;
  sentiment_ewma: number | null;
}

const REASON_LABELS: Record<string, string> = {
  identical_email: 'Identical email',
  same_email_local_diff_domain: 'Same email, different domain',
  same_name_same_company: 'Same name + company',
  similar_name_same_company: 'Similar name + company',
  near_identical_name: 'Near-identical name',
  similar_name: 'Similar name',
};

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.90 ? 'bg-red-500' :
    score >= 0.75 ? 'bg-amber-500' :
    'bg-blue-500';
  return (
    <span className={`inline-flex items-center gap-1 text-white text-[10px] font-bold px-2 py-0.5 rounded-full ${color}`}>
      {pct}% match
    </span>
  );
}

function ContactCard({ contact, label }: { contact: ContactSummary; label: string }) {
  return (
    <div className="flex-1 bg-muted/30 rounded-xl p-3 space-y-1 border border-border min-w-0">
      <p className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider">{label}</p>
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center text-primary font-bold text-sm shrink-0">
          {(contact.name || '?')[0].toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground truncate">{contact.name}</p>
          <p className="text-[10px] text-muted-foreground truncate">{contact.email}</p>
        </div>
      </div>
      {contact.company && (
        <p className="text-xs text-muted-foreground">{contact.company}</p>
      )}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{contact.entity_type}</span>
        <span className="text-[10px] text-muted-foreground">{contact.interaction_count} interactions</span>
      </div>
    </div>
  );
}

export default function ReviewPage() {
  const { data: session } = useSession();
  const qc = useQueryClient();
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  const headers = token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };

  // Load pending merge queue
  const { data, isLoading, refetch } = useQuery<{ queue: MergeCandidate[] }>({
    queryKey: ['merge-queue', orgId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/v1/merge/${orgId}/queue?status=pending&limit=50`, { headers });
      if (!res.ok) throw new Error('Failed to load merge queue');
      return res.json();
    },
    enabled: !!orgId,
  });

  // Scan mutation — runs entity resolution scan
  const scanMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE}/v1/merge/${orgId}/scan`, { method: 'POST', headers });
      if (!res.ok) throw new Error('Scan failed');
      return res.json();
    },
    onSuccess: (result) => {
      setActionMsg(`Scan complete — found ${result.new_candidates} new candidates from ${result.scanned} contacts.`);
      qc.invalidateQueries({ queryKey: ['merge-queue'] });
      setTimeout(() => setActionMsg(null), 5000);
    },
  });

  const decisionMutation = useMutation({
    mutationFn: async ({ id, action }: { id: string; action: 'merge' | 'reject' | 'defer' }) => {
      const res = await fetch(`${API_BASE}/v1/merge/${orgId}/queue/${id}/${action}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ reviewed_by: (session?.user as any)?.email || 'user' }),
      });
      if (!res.ok) throw new Error(`${action} failed`);
      return res.json();
    },
    onSuccess: (_, variables) => {
      const labels = { merge: 'Merged', reject: 'Rejected', defer: 'Deferred' };
      setActionMsg(`${labels[variables.action]} successfully.`);
      qc.invalidateQueries({ queryKey: ['merge-queue'] });
      setTimeout(() => setActionMsg(null), 3000);
    },
  });

  const pending = data?.queue ?? [];
  const isPending = decisionMutation.isPending;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border bg-card shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold text-foreground flex items-center gap-2">
              <GitMerge className="w-4 h-4 text-primary" />
              Entity Review Queue
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Review potential duplicate contacts found by entity resolution.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => scanMutation.mutate()}
            disabled={scanMutation.isPending}
            className="gap-2 text-xs"
          >
            <RefreshCcw className={`w-3.5 h-3.5 ${scanMutation.isPending ? 'animate-spin' : ''}`} />
            {scanMutation.isPending ? 'Scanning…' : 'Run Scan'}
          </Button>
        </div>

        {actionMsg && (
          <div className="mt-3 flex items-center gap-2 text-xs text-green-600 bg-green-50 dark:bg-green-900/20 rounded-lg px-3 py-2">
            <CheckCircle className="w-3.5 h-3.5 shrink-0" />
            {actionMsg}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        ) : pending.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center gap-4">
            <CheckCircle className="w-12 h-12 text-emerald-500" />
            <div>
              <p className="text-sm font-semibold text-foreground">Queue is empty</p>
              <p className="text-xs text-muted-foreground mt-1">
                No duplicate contacts pending review. Run a scan to check for new candidates.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4 max-w-3xl mx-auto">
            <p className="text-xs text-muted-foreground">
              {pending.length} candidate{pending.length !== 1 ? 's' : ''} pending review — sorted by match confidence
            </p>

            {pending.map((item) => (
              <div
                key={item.id}
                className="bg-card border border-border rounded-2xl p-4 space-y-3 shadow-sm"
              >
                {/* Header row */}
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <ScoreBadge score={item.match_score} />
                    <span className="text-xs text-muted-foreground">
                      {REASON_LABELS[item.match_reason] || item.match_reason}
                    </span>
                  </div>
                  <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </div>

                {/* Contact comparison */}
                <div className="flex gap-3">
                  <ContactCard contact={item.contact_a} label="Contact A" />
                  <div className="flex items-center shrink-0">
                    <div className="text-muted-foreground text-lg font-light">=?</div>
                  </div>
                  <ContactCard contact={item.contact_b} label="Contact B" />
                </div>

                {/* Action buttons */}
                <div className="flex items-center gap-2 pt-1">
                  <Button
                    size="sm"
                    onClick={() => decisionMutation.mutate({ id: item.id, action: 'merge' })}
                    disabled={isPending}
                    className="gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    <GitMerge className="w-3.5 h-3.5" />
                    Merge (keep B)
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => decisionMutation.mutate({ id: item.id, action: 'reject' })}
                    disabled={isPending}
                    className="gap-1.5 text-xs text-red-500 border-red-200 hover:bg-red-50 dark:hover:bg-red-900/20"
                  >
                    <X className="w-3.5 h-3.5" />
                    Not a duplicate
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => decisionMutation.mutate({ id: item.id, action: 'defer' })}
                    disabled={isPending}
                    className="gap-1.5 text-xs text-muted-foreground"
                  >
                    <Clock className="w-3.5 h-3.5" />
                    Defer
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
