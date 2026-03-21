'use client';

import { useSession } from 'next-auth/react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Users, Mail, Activity, Zap } from 'lucide-react';

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

  const { data: metrics } = useQuery<DashboardMetrics>({
    queryKey: ['dashboard-metrics', orgId],
    queryFn: () => api.dashboard.getMetrics(orgId, token),
    enabled: !!orgId && !!token,
    refetchInterval: 30000,
  });

  const stats = [
    { label: 'Contacts', value: metrics?.contacts_count ?? '-', icon: Users, color: 'text-blue-400' },
    { label: 'Interactions', value: metrics?.interactions_count ?? '-', icon: Mail, color: 'text-emerald-400' },
    { label: 'Active', value: metrics?.active_relationships_count ?? '-', icon: Activity, color: 'text-amber-400' },
    { label: 'Context Calls', value: metrics?.context_calls_count ?? '-', icon: Zap, color: 'text-indigo-400' },
  ];

  return (
    <div className="grid grid-cols-4 gap-3 mb-4">
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <div key={stat.label} className="bg-slate-900/50 border border-slate-800 rounded-lg p-3 flex items-center gap-3">
            <div className={`${stat.color}`}>
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xl font-bold text-white">
                {typeof stat.value === 'number' ? stat.value.toLocaleString() : stat.value}
              </p>
              <p className="text-xs text-slate-500">{stat.label}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
