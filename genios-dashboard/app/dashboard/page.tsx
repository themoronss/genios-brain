'use client';

import { useSession } from 'next-auth/react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import { GraphData, GraphNode, ContextBundle, ConnectionStatus } from '@/types';
import RelationshipGraph from '@/components/RelationshipGraph';
import { DraftModal } from '@/components/DraftModal';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { X, Copy, Check, Network, Search, Sparkles, RefreshCw } from 'lucide-react';
import { formatDate, getStageColor } from '@/lib/utils';

export default function DashboardPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [copied, setCopied] = useState(false);
  const [draftModalOpen, setDraftModalOpen] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncStarting, setSyncStarting] = useState(false); // bridge gap between click and first poll
  const prevSyncStatus = useRef<string | undefined>(undefined);

  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  const { data: status, refetch: refetchStatus } = useQuery<ConnectionStatus>({
    queryKey: ['connection-status', orgId],
    queryFn: () => api.org.getStatus(orgId, token),
    enabled: !!orgId && !!token,
    refetchInterval: (query) => {
      // Poll every 3 seconds while syncing — use query.state.data to avoid circular ref
      const data = query.state.data as ConnectionStatus | undefined;
      if (data?.sync_status === 'running') {
        return 3000;
      }
      return false;
    },
  });

  const isSyncing = status?.sync_status === 'running';

  useEffect(() => {
    if (status && !status.gmail_connected) {
      router.push('/dashboard/connect');
    }
  }, [status, router]);

  const { data: graphData, isLoading: graphLoading, refetch: refetchGraph } = useQuery<GraphData>({
    queryKey: ['graph-data', orgId],
    queryFn: () => api.org.getGraph(orgId, token),
    enabled: !!orgId && !!token && !!status?.gmail_connected,
  });

  // Manual sync mutation
  const syncMutation = useMutation({
    mutationFn: () => api.gmail.triggerSync(orgId, token),
    onSuccess: () => {
      setSyncStarting(true);
      setSyncMessage('🔄 Sync started...');
      // Refetch immediately to pick up running status
      refetchStatus();
    },
    onError: (error: any) => {
      setSyncStarting(false);
      setSyncMessage(`❌ ${error.message || 'Failed to start sync'}`);
      setTimeout(() => setSyncMessage(null), 5000);
    },
  });

  // Monitor sync status changes using previous value ref
  useEffect(() => {
    if (!status) return;
    const prev = prevSyncStatus.current;
    const curr = status.sync_status;

    if (curr === 'running') {
      // Clear the "starting" bridge state — we're confirmed running
      setSyncStarting(false);
      const prog = status.sync_total > 0
        ? `Processing ${status.sync_processed}/${status.sync_total} emails...`
        : 'Preparing sync...';
      setSyncMessage(`🔄 ${prog}`);
    } else if (prev === 'running' && curr === 'completed') {
      // Transition: running → completed (works even if page loaded mid-sync)
      setSyncMessage('✅ Sync completed! Your graph has been updated.');
      refetchGraph();
      setTimeout(() => setSyncMessage(null), 5000);
    } else if (prev === 'running' && curr === 'error') {
      setSyncMessage(`❌ Sync error: ${status.sync_error || 'Unknown error'}`);
      setTimeout(() => setSyncMessage(null), 8000);
    }

    prevSyncStatus.current = curr;
  }, [status, refetchGraph]);

  const handleManualSync = () => {
    syncMutation.mutate();
  };

  const { data: contextBundle, isLoading: contextLoading } = useQuery<ContextBundle>({
    queryKey: ['context', orgId, selectedNode?.name],
    queryFn: () => api.context.getBundle(orgId, selectedNode!.name, token),
    enabled: !!orgId && !!token && !!selectedNode,
  });

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
    setCopied(false);
  };

  const handleClosePanel = () => {
    setSelectedNode(null);
  };

  const handleCopyContext = () => {
    if (contextBundle?.context_for_agent) {
      navigator.clipboard.writeText(contextBundle.context_for_agent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (graphLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Loading your relationship graph...</p>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>No Contacts Yet</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600 mb-4">
              Your relationship graph is empty. Make sure Gmail sync has completed.
            </p>
            <Button onClick={() => router.push('/dashboard/connect')}>
              Check Connection Status
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const stageCounts = graphData.nodes.reduce((acc, node) => {
    acc[node.relationship_stage] = (acc[node.relationship_stage] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Tab Navigation */}
      <div className="bg-white border-b border-slate-200 px-6 py-3 flex justify-between items-center">
        <div className="flex gap-4">
          <button className="px-4 py-2 font-medium text-slate-900 border-b-2 border-indigo-600">
            <Network className="h-4 w-4 inline mr-2" />
            Relationship Graph
          </button>
          <Link
            href="/dashboard/tester"
            className="px-4 py-2 font-medium text-slate-600 hover:text-slate-900 border-b-2 border-transparent hover:border-slate-200 transition"
          >
            <Search className="h-4 w-4 inline mr-2" />
            Context Tester
          </Link>
        </div>

        {/* Manual Sync Button */}
        <div className="flex items-center gap-3">
          {syncMessage && (
            <div className="flex items-center gap-2">
              {isSyncing && (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-indigo-600"></div>
              )}
              <span className="text-sm font-medium text-slate-700 animate-in fade-in">
                {syncMessage}
              </span>
            </div>
          )}
          {isSyncing && status && status.sync_total > 0 && (
            <div className="flex items-center gap-2">
              <div className="w-32 h-2 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-600 rounded-full transition-all duration-500"
                  style={{ width: `${Math.round((status.sync_processed / Math.max(status.sync_total, 1)) * 100)}%` }}
                />
              </div>
              <span className="text-xs text-slate-600">
                {status.sync_processed}/{status.sync_total}
              </span>
            </div>
          )}
          <Button
            onClick={handleManualSync}
            disabled={syncMutation.isPending || isSyncing || syncStarting}
            variant="outline"
            size="sm"
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${(syncMutation.isPending || isSyncing || syncStarting) ? 'animate-spin' : ''}`} />
            {(isSyncing || syncStarting) ? 'Syncing...' : 'Sync Gmail'}
          </Button>
          {status?.last_sync && !isSyncing && (
            <span className="text-xs text-slate-500">
              Last: {new Date(status.last_sync).toLocaleString()}
            </span>
          )}
        </div>
      </div>

      {/* Graph Container */}
      <div className="flex-1 relative">
        {/* Header with stats */}
        <div className="absolute top-4 left-4 z-10 bg-white rounded-lg shadow-lg p-4">
          <h2 className="text-lg font-semibold mb-3">Relationship Graph</h2>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getStageColor('ACTIVE') }}></div>
              <span className="text-sm">Active ({stageCounts['ACTIVE'] || 0})</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getStageColor('WARM') }}></div>
              <span className="text-sm">Warm ({stageCounts['WARM'] || 0})</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getStageColor('DORMANT') }}></div>
              <span className="text-sm">Dormant ({stageCounts['DORMANT'] || 0})</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getStageColor('COLD') }}></div>
              <span className="text-sm">Cold ({stageCounts['COLD'] || 0})</span>
            </div>
          </div>
        </div>

        {/* Graph */}
        <RelationshipGraph data={graphData} onNodeClick={handleNodeClick} />

        {/* Detail Panel */}
        {selectedNode && (
          <div className="absolute top-0 right-0 h-full w-full md:w-96 bg-white shadow-2xl overflow-y-auto z-20 animate-in slide-in-from-right">
            <div className="sticky top-0 bg-white border-b z-10 p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-xl font-semibold">{selectedNode.name}</h2>
                  {selectedNode.company && (
                    <p className="text-sm text-slate-600">{selectedNode.company}</p>
                  )}
                </div>
                <Button variant="ghost" size="icon" onClick={handleClosePanel}>
                  <X className="h-5 w-5" />
                </Button>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <Badge
                  style={{
                    backgroundColor: getStageColor(selectedNode.relationship_stage),
                    color: 'white',
                    border: 'none',
                  }}
                >
                  {selectedNode.relationship_stage}
                </Badge>
                <span className="text-sm text-slate-600">
                  {selectedNode.interaction_count} interactions
                </span>
              </div>
            </div>

            <div className="p-4 space-y-6">
              {contextLoading ? (
                <div className="flex justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                </div>
              ) : contextBundle ? (
                <>
                  {/* Context Paragraph */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold text-sm uppercase text-slate-600">
                        Context Paragraph
                      </h3>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCopyContext}
                        className="h-8"
                      >
                        {copied ? (
                          <>
                            <Check className="h-3 w-3 mr-1" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy className="h-3 w-3 mr-1" />
                            Copy
                          </>
                        )}
                      </Button>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-4 text-sm leading-relaxed">
                      {contextBundle.context_for_agent}
                    </div>
                    {contextBundle.confidence && (
                      <p className="text-xs text-slate-500 mt-2">
                        Confidence: {(contextBundle.confidence * 100).toFixed(0)}%
                      </p>
                    )}

                    {/* Draft with AI Button */}
                    <div>
                      <Button
                        onClick={() => setDraftModalOpen(true)}
                        className="w-full gap-2"
                        variant="default"
                      >
                        <Sparkles className="h-4 w-4" />
                        Draft with AI
                      </Button>
                      <p className="text-xs text-slate-500 mt-2 text-center">
                        Generate messages using full relationship context
                      </p>
                    </div>
                  </div>

                  {/* Entity Details */}
                  {contextBundle.entity && (
                    <>
                      {contextBundle.entity.topics_of_interest.length > 0 && (
                        <div>
                          <h3 className="font-semibold text-sm uppercase text-slate-600 mb-2">
                            Topics of Interest
                          </h3>
                          <div className="flex flex-wrap gap-2">
                            {contextBundle.entity.topics_of_interest.map((topic, idx) => (
                              <Badge key={idx} variant="secondary">
                                {topic}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {contextBundle.entity.open_commitments.length > 0 && (
                        <div>
                          <h3 className="font-semibold text-sm uppercase text-slate-600 mb-2">
                            Open Commitments
                          </h3>
                          <div className="space-y-2">
                            {contextBundle.entity.open_commitments.map((commitment, idx) => (
                              <div key={idx} className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm">
                                ⚠️ {commitment}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div>
                        <h3 className="font-semibold text-sm uppercase text-slate-600 mb-2">
                          Stats
                        </h3>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-slate-600">Last interaction:</span>
                            <span className="font-medium">{contextBundle.entity.last_interaction}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-600">Sentiment trend:</span>
                            <span className="font-medium">{contextBundle.entity.sentiment_trend}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-600">Total interactions:</span>
                            <span className="font-medium">{contextBundle.entity.interaction_count}</span>
                          </div>
                          {contextBundle.entity.communication_style && (
                            <div className="flex justify-between">
                              <span className="text-slate-600">Communication style:</span>
                              <span className="font-medium">{contextBundle.entity.communication_style}</span>

                              {/* Draft Modal */}
                              {selectedNode && (
                                <DraftModal
                                  open={draftModalOpen}
                                  onOpenChange={setDraftModalOpen}
                                  entityName={selectedNode.name}
                                />
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </>
                  )}
                </>
              ) : (
                <div className="text-center py-8 text-slate-600">
                  No context available for this contact.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
