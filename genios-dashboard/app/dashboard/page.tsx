'use client';

import { useSession } from 'next-auth/react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { GraphData, GraphNode, ContextBundle, ConnectionStatus } from '@/types';
import RelationshipGraph from '@/components/RelationshipGraph';
import { DraftModal } from '@/components/DraftModal';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  X, Copy, Check, Sparkles, RefreshCcw, Mail, Plus, AlertCircle, Inbox,
} from 'lucide-react';
import { formatDate, getStageColor } from '@/lib/utils';

const ENTITY_TAG_CONFIG: Record<string, { label: string; color: string }> = {
  all:       { label: 'All',        color: '#475569' },
  investor:  { label: 'Investors',  color: '#8b5cf6' },
  customer:  { label: 'Customers',  color: '#10b981' },
  lead:      { label: 'Leads',      color: '#f97316' },
  vendor:    { label: 'Vendors',    color: '#f59e0b' },
  partner:   { label: 'Partners',   color: '#3b82f6' },
  advisor:   { label: 'Advisors',   color: '#06b6d4' },
  candidate: { label: 'Candidates', color: '#6366f1' },
  media:     { label: 'Media',      color: '#ec4899' },
  team:      { label: 'Team',       color: '#64748b' },
  other:     { label: 'Other',      color: '#94a3b8' },
};

export default function DashboardPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const qc = useQueryClient();

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [copied, setCopied] = useState(false);
  const [draftModalOpen, setDraftModalOpen] = useState(false);
  const [activeEntityFilter, setActiveEntityFilter] = useState('all');

  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  // ── Overall org status ──────────────────────────────────────────────────
  const { data: status, refetch: refetchStatus } = useQuery<ConnectionStatus>({
    queryKey: ['connection-status', orgId],
    queryFn: () => api.org.getStatus(orgId, token),
    enabled: !!orgId && !!token,
    refetchInterval: (q) => {
      const d = q.state.data as ConnectionStatus | undefined;
      return d?.sync_status === 'running' ? 3000 : false;
    },
  });

  // ── Redirect if not connected ───────────────────────────────────────────
  useEffect(() => {
    if (status && !status.gmail_connected) router.push('/dashboard/connect');
  }, [status, router]);

  // ── Per-account list ────────────────────────────────────────────────────
  const { data: accountsData, refetch: refetchAccounts } = useQuery<{ accounts: any[]; count: number }>({
    queryKey: ['gmail-accounts', orgId],
    queryFn: () => api.gmail.listAccounts(orgId, token),
    enabled: !!orgId && !!token,
    refetchInterval: (q) => {
      const d = q.state.data as any;
      const hasSyncing = d?.accounts?.some((a: any) => a.sync_status === 'syncing' || a.sync_status === 'running');
      return hasSyncing ? 3000 : false;
    },
  });

  // ── Graph data ──────────────────────────────────────────────────────────
  // We check if either the global org is syncing, or any individual account is syncing
  const isAnySyncing =
    status?.sync_status === 'running' ||
    accountsData?.accounts?.some((a: any) => a.sync_status === 'syncing' || a.sync_status === 'running');

  const { data: graphData, isLoading: graphLoading, refetch: refetchGraph } = useQuery<GraphData>({
    queryKey: ['graph-data', orgId, activeEntityFilter],
    queryFn: () => {
      const fp = activeEntityFilter !== 'all' ? `?entity_type=${activeEntityFilter}` : '';
      return api.org.getGraph(orgId, token, fp);
    },
    enabled: !!orgId && !!token && !!status?.gmail_connected,
    // Poll graph every 10s while any account is syncing so data appears progressively
    refetchInterval: isAnySyncing ? 10000 : false,
  });

  // ── Sync a specific account ─────────────────────────────────────────────
  const syncAccountMutation = useMutation({
    mutationFn: (accountEmail: string) => api.gmail.syncAccount(orgId, accountEmail, token),
    onSuccess: () => {
      refetchAccounts();
      refetchStatus();
    },
  });

  // ── Auto-refresh graph when sync completes ──────────────────────────────
  // Initialize to false (not undefined) so the true → false transition is always caught
  const prevIsSyncing = useRef<boolean>(false);

  useEffect(() => {
    if (prevIsSyncing.current === true && isAnySyncing === false) {
      // Sync just finished — do a final graph refresh
      refetchGraph();
    }
    prevIsSyncing.current = !!isAnySyncing;
  }, [isAnySyncing, refetchGraph]);

  // ── Context for selected node ───────────────────────────────────────────
  const { data: contextBundle, isLoading: contextLoading } = useQuery<ContextBundle>({
    queryKey: ['context', orgId, selectedNode?.name],
    queryFn: () => api.context.getBundle(orgId, selectedNode!.name, token),
    enabled: !!orgId && !!token && !!selectedNode,
  });

  const handleNodeClick = (node: GraphNode) => {
    if (!node.email) return;
    setSelectedNode(node);
    setCopied(false);
  };

  const handleCopyContext = () => {
    if (contextBundle?.context_for_agent) {
      navigator.clipboard.writeText(contextBundle.context_for_agent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const entityTypeCounts = graphData?.entity_type_counts ?? {};
  const availableFilters = ['all', ...Object.keys(entityTypeCounts).filter(k => k !== 'self').sort()];

  const stageCounts = (graphData?.nodes ?? []).reduce((acc, n) => {
    acc[n.relationship_stage] = (acc[n.relationship_stage] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // ── Sync-in-progress state ─────────────────────────────────────────────
  // Aggregate sync_processed / sync_total across all accounts
  const totalSynced = accountsData?.accounts?.reduce((s: number, a: any) => s + (a.sync_processed || 0), 0)
    ?? (status?.sync_processed ?? 0);
  const totalEmails = accountsData?.accounts?.reduce((s: number, a: any) => s + (a.sync_total || 0), 0)
    ?? (status?.sync_total ?? 0);
  const syncPct = totalEmails > 0 ? Math.min(Math.round((totalSynced / totalEmails) * 100), 99) : null;

  // While syncing AND no graph data yet — show sync progress screen
  if (isAnySyncing && (!graphData || graphData.nodes.length === 0)) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-sm space-y-5 px-4">
          <div className="relative mx-auto w-16 h-16">
            <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary/20 border-t-primary" />
            <Mail className="absolute inset-0 m-auto h-6 w-6 text-primary" />
          </div>
          <div>
            <p className="text-foreground font-semibold text-base">Syncing your emails…</p>
            {totalEmails > 0 ? (
              <p className="text-sm text-muted-foreground mt-1">
                {totalSynced} of {totalEmails} emails processed
                {syncPct !== null ? ` (${syncPct}%)` : ''}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground mt-1">Fetching emails from Gmail…</p>
            )}
          </div>
          {totalEmails > 0 && (
            <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-500"
                style={{ width: `${syncPct ?? 5}%` }}
              />
            </div>
          )}
          <p className="text-xs text-muted-foreground">The graph will appear automatically once sync completes. This page refreshes every 10 seconds.</p>
        </div>
      </div>
    );
  }

  // ── Loading state (graph query in-flight, not syncing) ──────────────────
  if (graphLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4" />
          <p className="text-muted-foreground text-sm">Loading your relationship graph…</p>
        </div>
      </div>
    );
  }

  // ── Empty state ─────────────────────────────────────────────────────────
  // Distinguish between "wiped but connected" vs "no connection at all"
  const hasConnectedAccounts = (accountsData?.accounts?.length ?? 0) > 0;

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-sm space-y-4 px-4">
          {hasConnectedAccounts ? (
            <>
              <Inbox className="h-12 w-12 text-muted-foreground mx-auto" />
              <p className="text-foreground font-semibold">Graph is empty</p>
              <p className="text-sm text-muted-foreground">
                Your accounts are still connected. Sync an account to rebuild your relationship graph.
              </p>
              <Button
                onClick={() => {
                  const firstAccount = accountsData?.accounts?.[0]?.account_email;
                  if (firstAccount) syncAccountMutation.mutate(firstAccount);
                }}
                disabled={syncAccountMutation.isPending}
                className="gap-2"
              >
                <RefreshCcw className={`h-4 w-4 ${syncAccountMutation.isPending ? 'animate-spin' : ''}`} />
                {syncAccountMutation.isPending ? 'Starting Sync…' : 'Sync Now'}
              </Button>
            </>
          ) : (
            <>
              <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto" />
              <p className="text-foreground font-semibold">No contacts yet</p>
              <p className="text-sm text-muted-foreground">
                Your relationship graph is empty. Connect a Gmail account to get started.
              </p>
              <Button onClick={() => router.push('/dashboard/connect')} variant="outline">
                Connect Gmail
              </Button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">

      {/* ── LEFT: Graph area (70%) ──────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden border-r border-border">

        {/* Filter bar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-card overflow-x-auto shrink-0 flex-wrap">
          <span className="text-xs text-muted-foreground shrink-0">Filter:</span>
          {availableFilters.map((fk) => {
            const cfg = ENTITY_TAG_CONFIG[fk] ?? { label: fk, color: '#94a3b8' };
            const count = fk === 'all'
              ? graphData.nodes.filter(n => n.entity_type !== 'self').length
              : (entityTypeCounts[fk] ?? 0);
            const isActive = activeEntityFilter === fk;
            return (
              <button
                key={fk}
                onClick={() => { setActiveEntityFilter(fk); setSelectedNode(null); }}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border transition-all shrink-0
                  ${isActive ? 'text-white shadow-sm' : 'text-muted-foreground bg-card border-border hover:border-foreground/30'}`}
                style={isActive ? { backgroundColor: cfg.color, borderColor: cfg.color } : {}}
              >
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: isActive ? 'rgba(255,255,255,0.7)' : cfg.color }} />
                {cfg.label}
                <span className={`ml-0.5 px-1.5 rounded-full text-[10px] font-semibold ${isActive ? 'bg-white/20 text-white' : 'bg-muted text-muted-foreground'}`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Graph + Legend layer */}
        <div className="flex-1 relative overflow-hidden">

          {/* Bottom-left Legend bar - COMMENTED OUT: Node colors now represent entity types, not relationship stages */}
          {/* <div className="absolute bottom-4 left-4 z-10 flex flex-col gap-2">
            {/* Stage dots */}
            {/* <div className="flex items-center gap-3 bg-card/80 backdrop-blur-sm border border-border rounded-xl px-4 py-2.5">
              {(['ACTIVE', 'WARM', 'DORMANT', 'COLD'] as const).map((stage) => (
                <div key={stage} className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: getStageColor(stage) }} />
                  <span className="text-[11px] text-muted-foreground font-medium">{stage} <span className="text-foreground">({stageCounts[stage] || 0})</span></span>
                </div>
              ))}
            </div> */}
            {/* Edge type legend */}
            {/* <div className="flex items-center gap-4 bg-card/80 backdrop-blur-sm border border-border rounded-xl px-4 py-2">
              <div className="flex items-center gap-2">
                <div className="w-6 h-0 border-t border-dashed border-indigo-400" />
                <span className="text-[11px] text-muted-foreground">CC shared</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-0 border-t border-muted-foreground/50" />
                <span className="text-[11px] text-muted-foreground">Direct</span>
              </div>
            </div> */}
          {/* </div> */}


          {/* Graph Canvas */}
          <RelationshipGraph
            data={graphData}
            onNodeClick={handleNodeClick}
            activeEntityFilter={activeEntityFilter}
          />

          {/* Node Detail Slide-in Panel */}
          {selectedNode && (
            <div className="absolute top-0 right-0 h-full w-full md:w-96 bg-card border-l border-border shadow-2xl overflow-y-auto z-20 animate-in slide-in-from-right">
              <div className="sticky top-0 bg-card border-b border-border z-10 p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">{selectedNode.name}</h2>
                    {selectedNode.company && <p className="text-sm text-muted-foreground">{selectedNode.company}</p>}
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => setSelectedNode(null)}>
                    <X className="h-5 w-5" />
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  <Badge style={{ backgroundColor: getStageColor(selectedNode.relationship_stage), color: 'white', border: 'none' }}>
                    {selectedNode.relationship_stage}
                  </Badge>
                  {selectedNode.entity_type && selectedNode.entity_type !== 'other' && selectedNode.entity_type !== 'self' && (
                    <Badge style={{ backgroundColor: ENTITY_TAG_CONFIG[selectedNode.entity_type]?.color ?? '#94a3b8', color: 'white', border: 'none' }}>
                      {ENTITY_TAG_CONFIG[selectedNode.entity_type]?.label ?? selectedNode.entity_type}
                    </Badge>
                  )}
                  <span className="text-sm text-muted-foreground">{selectedNode.interaction_count} interactions</span>
                </div>
              </div>

              <div className="p-4 space-y-6">
                {contextLoading ? (
                  <div className="flex justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                  </div>
                ) : contextBundle ? (
                  <>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wide">Context for Agent</h3>
                        <Button variant="outline" size="sm" onClick={handleCopyContext} className="h-7 gap-1">
                          {copied ? <><Check className="h-3 w-3" />Copied</> : <><Copy className="h-3 w-3" />Copy</>}
                        </Button>
                      </div>
                      <div className="bg-muted rounded-lg p-4 text-sm leading-relaxed text-foreground">
                        {contextBundle.context_for_agent}
                      </div>
                      {contextBundle.confidence && (
                        <p className="text-xs text-muted-foreground mt-1">Confidence: {(contextBundle.confidence * 100).toFixed(0)}%</p>
                      )}
                      <Button onClick={() => setDraftModalOpen(true)} className="w-full mt-4 gap-2">
                        <Sparkles className="h-4 w-4" /> Draft with AI
                      </Button>
                    </div>

                    {contextBundle.entity && (
                      <>
                        {contextBundle.entity.topics_of_interest?.length > 0 && (
                          <div>
                            <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wide mb-2">Topics</h3>
                            <div className="flex flex-wrap gap-2">
                              {contextBundle.entity.topics_of_interest.map((t, i) => <Badge key={i} variant="secondary">{t}</Badge>)}
                            </div>
                          </div>
                        )}
                        {contextBundle.entity.open_commitments?.length > 0 && (
                          <div>
                            <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wide mb-2">Open Commitments</h3>
                            <div className="space-y-2">
                              {contextBundle.entity.open_commitments.map((c, i) => (
                                <div key={i} className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-sm text-foreground">⚠️ {c}</div>
                              ))}
                            </div>
                          </div>
                        )}
                        <div>
                          <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wide mb-2">Stats</h3>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Last interaction</span>
                              <span className="font-medium text-foreground">{contextBundle.entity.last_interaction}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Sentiment</span>
                              <span className="font-medium text-foreground">{contextBundle.entity.sentiment_trend}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Total interactions</span>
                              <span className="font-medium text-foreground">{contextBundle.entity.interaction_count}</span>
                            </div>
                            {contextBundle.entity.communication_style && (
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Comm. style</span>
                                <span className="font-medium text-foreground">{contextBundle.entity.communication_style}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </>
                    )}
                  </>
                ) : (
                  <div className="text-center py-8 text-muted-foreground text-sm">No context available for this contact.</div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── RIGHT: Data Sources panel (30%) ────────────────────────── */}
      <aside className="w-72 shrink-0 flex flex-col overflow-y-auto bg-card">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Data Sources</h2>
          <button
            onClick={() => api.gmail.connect(orgId)}
            className="p-1.5 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            title="Connect new account"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 p-4 space-y-4">
          {accountsData?.accounts && accountsData.accounts.length > 0 ? (
            accountsData.accounts.map((acc, idx) => {
              const isSyncing = acc.sync_status === 'syncing' || acc.sync_status === 'running';
              return (
                <div key={idx} className="border border-border rounded-xl p-4 space-y-3 bg-background">
                  {/* Account header */}
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center shrink-0">
                      <Mail className="h-4 w-4 text-red-500" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">{acc.account_email}</p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {isSyncing ? '⏳ Syncing…' : acc.sync_status === 'completed' ? '✅ Synced' : acc.sync_status || 'Idle'}
                      </p>
                    </div>
                  </div>

                  {/* Progress bar + tally (visible while syncing) */}
                  {isSyncing && (
                    <div className="space-y-1">
                      <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                        {acc.sync_total > 0 ? (
                          <div
                            className="h-full bg-primary rounded-full transition-all duration-500"
                            style={{ width: `${Math.min(Math.round((acc.sync_processed / acc.sync_total) * 100), 99)}%` }}
                          />
                        ) : (
                          <div className="h-full w-1/3 bg-primary rounded-full animate-pulse" />
                        )}
                      </div>
                      {acc.sync_total > 0 && (
                        <p className="text-[10px] text-muted-foreground text-right">
                          {acc.sync_processed ?? 0} / {acc.sync_total} emails
                        </p>
                      )}
                    </div>
                  )}

                  {/* Last synced */}
                  {acc.last_synced_at && !isSyncing && (
                    <p className="text-xs text-muted-foreground">
                      Last sync: {new Date(acc.last_synced_at).toLocaleString()}
                    </p>
                  )}

                  {/* Sync button */}
                  <Button
                    size="sm"
                    variant="outline"
                    className="w-full gap-2"
                    disabled={syncAccountMutation.isPending || isSyncing}
                    onClick={() => syncAccountMutation.mutate(acc.account_email)}
                  >
                    <RefreshCcw className={`h-3.5 w-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
                    {isSyncing ? 'Syncing…' : 'Sync Now'}
                  </Button>
                </div>
              );
            })
          ) : (
            <div className="text-center py-8 space-y-3">
              <Mail className="h-8 w-8 text-muted-foreground mx-auto" />
              <p className="text-sm text-muted-foreground">No accounts connected.</p>
              <Button size="sm" variant="outline" onClick={() => api.gmail.connect(orgId)} className="gap-2">
                <Plus className="h-3.5 w-3.5" /> Connect Gmail
              </Button>
            </div>
          )}
        </div>
      </aside>

      {/* Draft Modal */}
      {selectedNode && (
        <DraftModal
          open={draftModalOpen}
          onOpenChange={setDraftModalOpen}
          entityName={selectedNode.name}
        />
      )}
    </div>
  );
}
