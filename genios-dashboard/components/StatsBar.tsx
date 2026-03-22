'use client';

import { useSession } from 'next-auth/react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Users, Mail, Activity, Zap, Brain, Gauge } from 'lucide-react';

interface DashboardMetrics {
  contacts_count: number;
  interactions_count: number;
  active_relationships_count: number;
  context_calls_count: number;
}

export default function StatsBar() {
  const { data: session } = useSession();
  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  const { data: metrics, isLoading } = useQuery<DashboardMetrics>({
    queryKey: ['dashboard-metrics', orgId],
    queryFn: () => api.dashboard.getMetrics(orgId, token),
    enabled: !!orgId && !!token,
    refetchInterval: 30000,
  });

  const { data: graphStats } = useQuery<any>({
    queryKey: ['graph-stats', orgId],
    queryFn: () => api.graph.getStats(orgId, token),
    enabled: !!orgId && !!token,
    refetchInterval: 60000,
  });

  // Brain status indicator
  const brainStatus = graphStats?.brain_status || 'BUILDING';
  const brainColor = brainStatus === 'ACTIVE' ? 'text-emerald-400' : brainStatus === 'DEGRADED' ? 'text-red-400' : 'text-amber-400';
  const brainBg = brainStatus === 'ACTIVE' ? 'bg-emerald-500/10' : brainStatus === 'DEGRADED' ? 'bg-red-500/10' : 'bg-amber-500/10';

  // Graph quality score
  const qualityScore = graphStats?.quality_score ?? 0;

  const stats = [
    { label: 'Contacts', value: metrics?.contacts_count, icon: Users, color: 'text-blue-400', bg: 'bg-blue-500/10' },
    { label: 'Interactions', value: metrics?.interactions_count, icon: Mail, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    { label: 'Active', value: metrics?.active_relationships_count, icon: Activity, color: 'text-amber-400', bg: 'bg-amber-500/10' },
    { label: 'Context Calls', value: metrics?.context_calls_count, icon: Zap, color: 'text-indigo-400', bg: 'bg-indigo-500/10' },
  ];

  return (
    <div className="px-4 py-2.5 border-b border-border bg-card shrink-0 space-y-2">
      {/* Main stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 border border-border bg-background hover:border-primary/30 transition-colors cursor-default group"
            >
              <div className={`${stat.bg} rounded-lg p-2 group-hover:scale-105 transition-transform`}>
                <Icon className={`w-4 h-4 ${stat.color}`} />
              </div>
              <div className="min-w-0">
                {isLoading ? (
                  <div className="h-5 w-12 bg-muted rounded animate-pulse" />
                ) : (
                  <p className="text-lg font-bold text-foreground leading-none tracking-tight">
                    {typeof stat.value === 'number' ? stat.value.toLocaleString() : '—'}
                  </p>
                )}
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mt-0.5">{stat.label}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Brain status + quality row */}
      {graphStats && (
        <div className="flex items-center gap-4 px-1">
          <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${brainStatus === 'ACTIVE' ? 'bg-emerald-500' : brainStatus === 'DEGRADED' ? 'bg-red-500' : 'bg-amber-500'}`} />
            <span className="text-[10px] text-muted-foreground">Brain: <span className={brainColor}>{brainStatus}</span></span>
          </div>
          <div className="flex items-center gap-1.5">
            <Gauge className="w-3 h-3 text-muted-foreground" />
            <span className="text-[10px] text-muted-foreground">
              Quality: <span className="text-foreground font-medium">{qualityScore}/100</span>
            </span>
          </div>
          {graphStats.avg_confidence != null && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground">
                Avg Confidence: <span className="text-foreground font-medium">{(graphStats.avg_confidence * 100).toFixed(0)}%</span>
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
