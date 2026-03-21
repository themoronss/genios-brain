'use client';

import React, { useEffect, useState } from 'react';
import { X, TrendingUp, TrendingDown, Minus, Clock, MessageSquare, Tag, Users } from 'lucide-react';

interface EdgeDetailPanelProps {
  contactId: string;
  contactName: string;
  orgId: string;
  onClose: () => void;
}

interface EdgeDetail {
  contact_id: string;
  contact_name: string;
  sentiment_trajectory: { date: string; sentiment: number }[];
  topic_clusters: { topic: string; count: number }[];
  response_time: { fast: number; moderate: number; slow: number; avg_hours: number | null };
  last_3_threads: { subject: string; summary: string; date: string; direction: string; sentiment: number }[];
  total_interactions: number;
  company?: string;
  company_contacts?: { name: string; email: string; entity_type: string; sentiment_avg: number; interaction_count: number }[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function EdgeDetailPanel({ contactId, contactName, orgId, onClose }: EdgeDetailPanelProps) {
  const [data, setData] = useState<EdgeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchEdgeDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/api/org/${orgId}/edge/${contactId}`);
        if (!res.ok) throw new Error('Failed to load edge details');
        const json = await res.json();
        setData(json);
      } catch (e: any) {
        setError(e.message || 'Failed to load');
      } finally {
        setLoading(false);
      }
    };
    fetchEdgeDetail();
  }, [contactId, orgId]);

  const sentimentColor = (s: number) =>
    s > 0.2 ? '#10b981' : s < -0.2 ? '#ef4444' : '#94a3b8';

  const sentimentIcon = (s: number) =>
    s > 0.2 ? <TrendingUp className="w-3 h-3" /> : s < -0.2 ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />;

  const responseLabel = (avg: number | null) => {
    if (!avg) return 'Unknown';
    if (avg < 4) return 'Fast (< 4h)';
    if (avg < 24) return 'Moderate (< 24h)';
    return 'Slow (24h+)';
  };

  return (
    <div className="absolute right-0 top-0 h-full w-96 bg-card shadow-2xl border-l border-border z-30 overflow-y-auto flex flex-col animate-in slide-in-from-right">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border sticky top-0 bg-card z-10">
        <div className="min-w-0">
          <h2 className="font-semibold text-foreground text-sm">Edge Detail</h2>
          <p className="text-xs text-muted-foreground truncate">Relationship with {contactName}</p>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-foreground transition-colors shrink-0">
          <X className="w-4 h-4" />
        </button>
      </div>

      {loading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
        </div>
      )}

      {error && (
        <div className="p-4 text-sm text-destructive bg-destructive/10 m-4 rounded-lg">{error}</div>
      )}

      {data && !loading && (
        <div className="flex-1 p-4 space-y-5">

          {/* Interaction summary strip */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-background rounded-xl p-2.5 border border-border text-center">
              <p className="text-lg font-bold text-foreground leading-none">{data.total_interactions}</p>
              <p className="text-[9px] text-muted-foreground uppercase tracking-wider mt-1">Interactions</p>
            </div>
            <div className="bg-background rounded-xl p-2.5 border border-border text-center">
              <p className="text-sm font-bold text-foreground leading-tight">
                {data.response_time.avg_hours ? `${data.response_time.avg_hours.toFixed(0)}h` : '—'}
              </p>
              <p className="text-[9px] text-muted-foreground uppercase tracking-wider mt-1">Avg Reply</p>
            </div>
            <div className="bg-background rounded-xl p-2.5 border border-border text-center">
              <p className="text-sm font-bold text-foreground leading-tight">{data.topic_clusters.length}</p>
              <p className="text-[9px] text-muted-foreground uppercase tracking-wider mt-1">Topics</p>
            </div>
          </div>

          {/* Sentiment Trajectory */}
          <section className="bg-background rounded-xl p-3 border border-border">
            <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5" />
              Sentiment Trajectory
            </h3>
            {data.sentiment_trajectory.length > 0 ? (
              <div className="relative">
                {/* Baseline indicator at sentiment=0 */}
                <div className="absolute left-0 right-0 border-t border-dashed border-muted-foreground/30"
                  style={{ bottom: '50%' }}
                />
                <div className="flex items-end gap-1 h-14 relative z-10">
                  {data.sentiment_trajectory.slice(-12).map((pt, i) => {
                    // Map -1..+1 to 4..56px
                    const height = Math.max(4, ((pt.sentiment + 1) / 2) * 52);
                    return (
                      <div
                        key={i}
                        className="flex-1 rounded-sm transition-all hover:opacity-80 cursor-default"
                        style={{
                          height: `${height}px`,
                          backgroundColor: sentimentColor(pt.sentiment),
                          opacity: 0.7 + (i / 12) * 0.3, // fade older bars
                        }}
                        title={`${new Date(pt.date).toLocaleDateString()}: ${pt.sentiment > 0 ? '+' : ''}${pt.sentiment.toFixed(2)}`}
                      />
                    );
                  })}
                </div>
                <div className="flex justify-between text-[10px] text-muted-foreground mt-1.5">
                  <span>Older</span>
                  <span className="text-muted-foreground/50">neutral</span>
                  <span>Recent</span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No sentiment data available</p>
            )}
          </section>

          {/* Topic Clusters */}
          <section className="bg-background rounded-xl p-3 border border-border">
            <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5" />
              Topic Clusters
            </h3>
            {data.topic_clusters.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {data.topic_clusters.map((t, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary border border-primary/20"
                    title={t.topic}
                  >
                    {t.topic} <span className="opacity-50 font-semibold">x{t.count}</span>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No recurring topics detected</p>
            )}
          </section>

          {/* Response Pattern */}
          <section className="bg-background rounded-xl p-3 border border-border">
            <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              Response Pattern
            </h3>
            <div className="text-sm font-semibold text-foreground">
              {responseLabel(data.response_time.avg_hours)}
            </div>
            <div className="flex gap-2.5 mt-2">
              {[
                { label: 'Fast', value: data.response_time.fast, color: 'text-emerald-500' },
                { label: 'Moderate', value: data.response_time.moderate, color: 'text-amber-500' },
                { label: 'Slow', value: data.response_time.slow, color: 'text-muted-foreground' },
              ].map(({ label, value, color }) => {
                const total = (data.response_time.fast || 0) + (data.response_time.moderate || 0) + (data.response_time.slow || 0);
                const pct = total > 0 ? (value / total) * 100 : 0;
                return (
                  <div key={label} className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-[10px] font-medium ${color}`}>{label}</span>
                      <span className="text-[10px] text-muted-foreground">{value}</span>
                    </div>
                    <div className="w-full h-1 bg-muted rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${
                        label === 'Fast' ? 'bg-emerald-500' :
                        label === 'Moderate' ? 'bg-amber-500' : 'bg-muted-foreground/50'
                      }`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Company Contacts — PDF spec: who else at that company */}
          {data.company_contacts && data.company_contacts.length > 0 && (
            <section className="bg-background rounded-xl p-3 border border-border">
              <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5" />
                Others at {data.company || 'this company'}
              </h3>
              <div className="space-y-1.5">
                {data.company_contacts.slice(0, 5).map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center text-primary text-[9px] font-bold shrink-0">
                      {(c.name || '?')[0].toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="text-foreground font-medium truncate block">{c.name}</span>
                    </div>
                    <span className="text-muted-foreground shrink-0">{c.interaction_count} msgs</span>
                    <div className="w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ backgroundColor: sentimentColor(c.sentiment_avg) }}
                    />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Last 3 Threads */}
          <section>
            <h3 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
              <MessageSquare className="w-3.5 h-3.5" />
              Recent Threads
            </h3>
            <div className="space-y-2.5">
              {data.last_3_threads.map((thread, i) => (
                <div key={i} className="p-3 rounded-xl bg-background border border-border">
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <p className="text-xs font-medium text-foreground line-clamp-1 flex-1">
                      {thread.subject || '(no subject)'}
                    </p>
                    <span style={{ color: sentimentColor(thread.sentiment) }} className="shrink-0">
                      {sentimentIcon(thread.sentiment)}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">{thread.summary}</p>
                  <div className="flex items-center justify-between mt-2">
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-md ${
                      thread.direction === 'inbound'
                        ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                        : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                    }`}>
                      {thread.direction === 'inbound' ? '← inbound' : '→ outbound'}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {new Date(thread.date).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
