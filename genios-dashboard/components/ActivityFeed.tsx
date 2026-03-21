'use client';

import { useSession } from 'next-auth/react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Mail, UserPlus, RefreshCcw, AlertTriangle, CheckCircle, Clock } from 'lucide-react';

interface ActivityEvent {
  event_type: string;
  event_data: Record<string, any>;
  created_at: string | null;
}

const EVENT_ICONS: Record<string, any> = {
  email_detected: Mail,
  contact_created: UserPlus,
  relationship_updated: RefreshCcw,
  graph_synced: CheckCircle,
  sync_started: Clock,
  sync_completed: CheckCircle,
  sync_failed: AlertTriangle,
};

const EVENT_LABELS: Record<string, string> = {
  email_detected: 'New email detected',
  contact_created: 'New contact added',
  relationship_updated: 'Relationship updated',
  graph_synced: 'Graph synced',
  sync_started: 'Sync started',
  sync_completed: 'Sync completed',
  sync_failed: 'Sync failed',
};

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function ActivityFeed() {
  const { data: session } = useSession();
  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  const { data } = useQuery<{ events: ActivityEvent[] }>({
    queryKey: ['activity-feed', orgId],
    queryFn: () => api.activity.getFeed(orgId, token),
    enabled: !!orgId && !!token,
    refetchInterval: 10000,
  });

  const events = data?.events || [];

  if (events.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-2">Activity</h3>
        <p className="text-xs text-slate-500">No activity yet. Connect Gmail to get started.</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-slate-300 mb-3">Activity</h3>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {events.slice(0, 15).map((event, i) => {
          const Icon = EVENT_ICONS[event.event_type] || Mail;
          const label = EVENT_LABELS[event.event_type] || event.event_type;
          const detail = event.event_data?.name || event.event_data?.email || event.event_data?.contact_name || '';

          return (
            <div key={i} className="flex items-start gap-2 text-xs">
              <Icon className="w-3.5 h-3.5 text-slate-500 mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <span className="text-slate-400">{label}</span>
                {detail && <span className="text-slate-500 ml-1">— {detail}</span>}
              </div>
              <span className="text-slate-600 flex-shrink-0">{formatTimeAgo(event.created_at)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
