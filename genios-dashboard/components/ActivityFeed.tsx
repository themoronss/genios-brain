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

const EVENT_CONFIG: Record<string, { icon: any; label: string; color: string; dotColor: string }> = {
  email_detected:       { icon: Mail,          label: 'New email',           color: 'text-blue-400',    dotColor: 'bg-blue-400'    },
  contact_created:      { icon: UserPlus,      label: 'Contact added',      color: 'text-emerald-400', dotColor: 'bg-emerald-400' },
  relationship_updated: { icon: RefreshCcw,    label: 'Stage changed',      color: 'text-amber-400',   dotColor: 'bg-amber-400'   },
  graph_synced:         { icon: CheckCircle,   label: 'Graph synced',       color: 'text-emerald-400', dotColor: 'bg-emerald-400' },
  sync_started:         { icon: Clock,         label: 'Sync started',       color: 'text-muted-foreground', dotColor: 'bg-muted-foreground' },
  sync_completed:       { icon: CheckCircle,   label: 'Sync completed',     color: 'text-emerald-400', dotColor: 'bg-emerald-400' },
  sync_failed:          { icon: AlertTriangle, label: 'Sync failed',        color: 'text-red-400',     dotColor: 'bg-red-400'     },
};

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
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

  return (
    <div className="mt-4">
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Recent Activity</h3>
      {events.length === 0 ? (
        <p className="text-xs text-muted-foreground py-4 text-center">No activity yet</p>
      ) : (
        <div className="space-y-0.5 max-h-72 overflow-y-auto">
          {events.slice(0, 20).map((event, i) => {
            const cfg = EVENT_CONFIG[event.event_type] || {
              icon: Mail, label: event.event_type, color: 'text-muted-foreground', dotColor: 'bg-muted-foreground',
            };
            const Icon = cfg.icon;
            const detail = event.event_data?.name || event.event_data?.contact_name || event.event_data?.email || '';
            const isFailed = event.event_type === 'sync_failed';

            return (
              <div
                key={i}
                className={`flex items-center gap-2.5 py-2 px-2 rounded-lg text-xs transition-colors hover:bg-accent/50 ${
                  isFailed ? 'bg-red-500/5' : ''
                }`}
              >
                <div className={`flex items-center justify-center w-6 h-6 rounded-lg ${isFailed ? 'bg-red-500/10' : 'bg-muted/50'} shrink-0`}>
                  <Icon className={`w-3 h-3 ${cfg.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-foreground/80 font-medium">{cfg.label}</span>
                  {detail && (
                    <span className="text-muted-foreground ml-1 truncate">
                      — {detail.length > 20 ? detail.slice(0, 20) + '…' : detail}
                    </span>
                  )}
                </div>
                <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">
                  {formatTimeAgo(event.created_at)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
