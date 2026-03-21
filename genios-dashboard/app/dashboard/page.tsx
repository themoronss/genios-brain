'use client';

import { useSession } from 'next-auth/react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { GraphData, GraphNode, ContextBundle, ConnectionStatus } from '@/types';
import RelationshipGraph from '@/components/RelationshipGraph';
import { DraftModal } from '@/components/DraftModal';
import DashboardLayout from '@/components/DashboardLayout';
import StatsBar from '@/components/StatsBar';
import ActivityFeed from '@/components/ActivityFeed';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  X, Copy, Check, Sparkles, RefreshCcw, Mail, Plus, AlertCircle, Inbox,
  Network, GitBranch, User,
} from 'lucide-react';
import { formatDate, getStageColor } from '@/lib/utils';

type GraphMode = 'community' | 'stage' | 'ego';

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
  const [graphMode, setGraphMode] = useState<GraphMode>('community');
  const [egoNodeId, setEgoNodeId] = useState<string | null>(null);

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
    <div className="flex flex-col h-full overflow-hidden">

      {/* Stats Bar */}
      <StatsBar />

      <div className="flex flex-1 overflow-hidden">

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


          {/* Graph Mode Switcher */}
          <div className="absolute top-3 left-3 z-10 flex items-center gap-1 bg-card/90 backdrop-blur-sm border border-border rounded-lg p-1">
            {([
              { mode: 'community' as const, icon: Network, label: 'Community' },
              { mode: 'stage' as const, icon: GitBranch, label: 'Stage' },
              { mode: 'ego' as const, icon: User, label: 'Ego' },
            ]).map(({ mode, icon: Icon, label }) => (
              <button
                key={mode}
                onClick={() => {
                  setGraphMode(mode);
                  if (mode === 'ego' && selectedNode) setEgoNodeId(selectedNode.id);
                }}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs transition-colors
                  ${graphMode === mode ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-accent'}`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>

          {/* Graph Canvas */}
          <RelationshipGraph
            data={graphData}
            onNodeClick={(node) => {
              handleNodeClick(node);
              if (graphMode === 'ego') setEgoNodeId(node.id);
            }}
            activeEntityFilter={activeEntityFilter}
            graphMode={graphMode}
            egoNodeId={egoNodeId}
          />

          {/* Node Detail Slide-in Panel */}
          {selectedNode && (
            <div className="absolute top-0 right-0 h-full w-full md:w-96 bg-card border-l border-border shadow-2xl flex flex-col z-20 animate-in slide-in-from-right">

              {/* Top strip: stage counts + close */}
              <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border text-xs shrink-0">
                {(['ACTIVE', 'WARM', 'COLD'] as const).map(stage => {
                  const count = stageCounts[stage];
                  if (!count) return null;
                  const stageColors: Record<string, string> = { ACTIVE: '#10b981', WARM: '#f59e0b', COLD: '#ef4444' };
                  return (
                    <span key={stage} className="flex items-center gap-1 text-muted-foreground">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: stageColors[stage] }} />
                      <span className="font-semibold text-foreground">{count}</span> {stage.toLowerCase()}
                    </span>
                  );
                })}
                {(contextBundle?.entity?.open_commitments?.length ?? 0) > 0 && (
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                    <span className="font-semibold text-foreground">{contextBundle?.entity?.open_commitments?.length}</span> open commits
                  </span>
                )}
                <button
                  onClick={() => setSelectedNode(null)}
                  className="ml-auto p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Avatar + Name + Role */}
              <div className="px-4 pt-4 pb-3 border-b border-border shrink-0">
                <div className="flex items-start gap-3">
                  <div
                    className="w-11 h-11 rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0"
                    style={{ backgroundColor: ENTITY_TAG_CONFIG[selectedNode.entity_type]?.color ?? '#6366f1' }}
                  >
                    {selectedNode.name.split(' ').map((w: string) => w[0]).slice(0, 2).join('').toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="text-sm font-semibold text-foreground">{selectedNode.name}</h2>
                      <span
                        className="text-[9px] font-semibold px-2 py-0.5 rounded-full text-white"
                        style={{ backgroundColor: getStageColor(selectedNode.relationship_stage) }}
                      >
                        {selectedNode.relationship_stage.toLowerCase()}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {ENTITY_TAG_CONFIG[selectedNode.entity_type]?.label ?? selectedNode.entity_type}
                      {selectedNode.company && ` · ${selectedNode.company}`}
                    </p>
                  </div>
                </div>
              </div>

              {/* Scrollable body */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {contextLoading ? (
                  <div className="flex justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                  </div>
                ) : contextBundle ? (
                  <>
                    {/* Stats grid — 4 metrics per spec */}
                    <div className="grid grid-cols-4 gap-2">
                      <div className="bg-background rounded-xl p-2.5 border border-border text-center">
                        <p className="text-lg font-bold text-foreground leading-none">
                          {contextBundle.entity?.interaction_count ?? selectedNode.interaction_count}
                        </p>
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider mt-1">Interactions</p>
                      </div>
                      <div className="bg-background rounded-xl p-2.5 border border-border text-center">
                        <p className="text-xs font-bold text-foreground leading-tight">
                          {contextBundle.entity?.last_interaction ?? '—'}
                        </p>
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider mt-1">Last Contact</p>
                      </div>
                      <div className="bg-background rounded-xl p-2.5 border border-border text-center">
                        <p className="text-lg font-bold text-foreground leading-none">
                          {contextBundle.entity?.response_rate != null ? `${(contextBundle.entity.response_rate * 100).toFixed(0)}%` : '—'}
                        </p>
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider mt-1">Reply Rate</p>
                      </div>
                      <div className="bg-background rounded-xl p-2.5 border border-border text-center">
                        <p className={`text-lg font-bold leading-none ${(typeof contextBundle.entity?.open_commitments === 'number' ? contextBundle.entity.open_commitments : 0) > 0 ? 'text-amber-400' : 'text-foreground'}`}>
                          {typeof contextBundle.entity?.open_commitments === 'number' ? contextBundle.entity.open_commitments : 0}
                        </p>
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider mt-1">Open Commits</p>
                      </div>
                    </div>

                    {/* 5-Score Confidence Panel */}
                    {contextBundle.scores && (
                      <div className="bg-background rounded-xl p-3 border border-border space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider">Context Scores</span>
                          <span className="text-xs font-semibold text-foreground">
                            {((contextBundle.scores.composite ?? contextBundle.confidence) * 100).toFixed(0)}%
                          </span>
                        </div>
                        {(['freshness', 'confidence', 'consistency', 'authority', 'signal'] as const).map((key) => {
                          const val = contextBundle.scores?.[key] ?? 0;
                          const barColor = val > 0.7 ? 'bg-emerald-500' : val > 0.45 ? 'bg-amber-400' : 'bg-red-400';
                          return (
                            <div key={key} className="flex items-center gap-2">
                              <span className="text-[10px] text-muted-foreground w-20 capitalize">{key}</span>
                              <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${barColor} transition-all duration-700`} style={{ width: `${(val * 100).toFixed(0)}%` }} />
                              </div>
                              <span className="text-[10px] text-muted-foreground w-8 text-right">{(val * 100).toFixed(0)}%</span>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Interaction timeline */}
                    {(contextBundle.context_for_agent || (contextBundle.entity?.topics_of_interest?.length ?? 0) > 0) && (
                      <div className="bg-background rounded-xl p-3 border border-border space-y-3">
                        {contextBundle.context_for_agent && (
                          <div className="flex gap-3">
                            <div className="flex flex-col items-center shrink-0">
                              <span className="w-2 h-2 rounded-full bg-green-500 mt-0.5" />
                              <span className="w-px flex-1 bg-border mt-1" />
                            </div>
                            <div className="pb-3 min-w-0">
                              <div className="flex items-center justify-between gap-2">
                                <p className="text-xs font-medium text-foreground">Last interaction</p>
                                <span className="text-[10px] text-muted-foreground shrink-0">{contextBundle.entity?.last_interaction ?? ''}</span>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1 leading-relaxed line-clamp-3">
                                {contextBundle.context_for_agent.slice(0, 140).trim()}…
                              </p>
                            </div>
                          </div>
                        )}
                        {contextBundle.entity?.topics_of_interest?.slice(0, 2).map((topic: string, i: number) => (
                          <div key={i} className="flex gap-3">
                            <div className="flex flex-col items-center shrink-0">
                              <span className={`w-2 h-2 rounded-full mt-0.5 ${i === 0 ? 'bg-green-500' : 'bg-amber-400'}`} />
                              {i === 0 && <span className="w-px flex-1 bg-border mt-1" />}
                            </div>
                            <div className={i === 0 ? 'pb-3' : ''}>
                              <p className="text-xs font-medium text-foreground capitalize">{topic}</p>
                              <p className="text-[10px] text-muted-foreground mt-0.5">
                                {i === 0 ? 'Recent topic' : 'Earlier exchange'}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Open Commitments */}
                    {(contextBundle.entity?.open_commitments?.length ?? 0) > 0 && (
                      <div className="space-y-1.5">
                        <h3 className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider">Open Commitments</h3>
                        {contextBundle.entity?.open_commitments?.map((c: string, i: number) => (
                          <div key={i} className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-2.5 text-xs text-foreground flex gap-2">
                            <span className="shrink-0">⚠️</span> {c}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Communication style */}
                    {contextBundle.entity?.communication_style && (
                      <div>
                        <h3 className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider mb-2">Communication Style</h3>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-3">
                            <p className="text-[10px] font-semibold text-green-400 mb-2">✓ DO THIS</p>
                            <p className="text-xs text-foreground leading-relaxed">
                              {contextBundle.entity.communication_style}
                            </p>
                          </div>
                          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3">
                            <p className="text-[10px] font-semibold text-red-400 mb-2">✗ AVOID</p>
                            <div className="space-y-1.5">
                              <p className="text-xs text-muted-foreground">→ Vague follow-ups</p>
                              <p className="text-xs text-muted-foreground">→ Long narrative emails</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-8 text-muted-foreground text-sm">No context available for this contact.</div>
                )}
              </div>

              {/* Sticky action buttons */}
              <div className="shrink-0 border-t border-border p-3 flex gap-2">
                <Button onClick={() => setDraftModalOpen(true)} className="flex-1 gap-2 text-sm">
                  <Sparkles className="h-4 w-4" /> Draft with AI
                </Button>
                <Button
                  variant="outline"
                  onClick={handleCopyContext}
                  disabled={!contextBundle?.context_for_agent}
                  className="gap-2 text-sm"
                >
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {copied ? 'Copied' : 'Copy context'}
                </Button>
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
          {/* Activity Feed */}
          <div className="px-4 pb-4">
            <ActivityFeed />
          </div>
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
      </div>{/* close flex wrapper */}
    </div>
  );
}
