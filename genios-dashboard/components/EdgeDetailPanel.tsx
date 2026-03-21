'use client';

import React, { useEffect, useState } from 'react';
import { X, TrendingUp, TrendingDown, Minus, Clock, MessageSquare, Tag } from 'lucide-react';

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
}

export default function EdgeDetailPanel({ contactId, contactName, orgId, onClose }: EdgeDetailPanelProps) {
  const [data, setData] = useState<EdgeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchEdgeDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/org/${orgId}/edge/${contactId}`);
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
    <div className="fixed right-0 top-0 h-full w-96 bg-white dark:bg-gray-900 shadow-2xl border-l border-gray-200 dark:border-gray-700 z-50 overflow-y-auto flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 sticky top-0 bg-white dark:bg-gray-900 z-10">
        <div>
          <h2 className="font-semibold text-gray-900 dark:text-white text-sm">Edge Detail</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">Relationship with {contactName}</p>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
          <X className="w-4 h-4" />
        </button>
      </div>

      {loading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-sm text-gray-400 animate-pulse">Loading edge details…</div>
        </div>
      )}

      {error && (
        <div className="p-4 text-sm text-red-500">{error}</div>
      )}

      {data && !loading && (
        <div className="flex-1 p-4 space-y-5">

          {/* Sentiment Trajectory */}
          <section>
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5" />
              Sentiment Trajectory
            </h3>
            {data.sentiment_trajectory.length > 0 ? (
              <div className="flex items-end gap-1 h-16">
                {data.sentiment_trajectory.slice(-12).map((pt, i) => {
                  const height = Math.max(4, ((pt.sentiment + 1) / 2) * 56);
                  return (
                    <div
                      key={i}
                      className="flex-1 rounded-t transition-all"
                      style={{ height: `${height}px`, backgroundColor: sentimentColor(pt.sentiment) }}
                      title={`${new Date(pt.date).toLocaleDateString()}: ${pt.sentiment.toFixed(2)}`}
                    />
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-gray-400">No sentiment data available</p>
            )}
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>Older</span>
              <span>Recent</span>
            </div>
          </section>

          {/* Topic Clusters */}
          <section>
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5" />
              Topic Clusters
            </h3>
            {data.topic_clusters.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {data.topic_clusters.map((t, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 text-xs rounded-full bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-700"
                  >
                    {t.topic} <span className="opacity-60">×{t.count}</span>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400">No recurring topics detected</p>
            )}
          </section>

          {/* Response Time */}
          <section>
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              Response Pattern
            </h3>
            <div className="text-sm font-medium text-gray-800 dark:text-gray-200">
              {responseLabel(data.response_time.avg_hours)}
            </div>
            {data.response_time.avg_hours && (
              <p className="text-xs text-gray-400 mt-0.5">Avg reply: {data.response_time.avg_hours.toFixed(1)}h</p>
            )}
            <div className="flex gap-3 mt-2 text-xs text-gray-500">
              <span className="text-green-600">Fast: {data.response_time.fast}</span>
              <span className="text-amber-600">Moderate: {data.response_time.moderate}</span>
              <span className="text-gray-400">Slow: {data.response_time.slow}</span>
            </div>
          </section>

          {/* Last 3 Threads */}
          <section>
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <MessageSquare className="w-3.5 h-3.5" />
              Last {data.last_3_threads.length} Threads
            </h3>
            <div className="space-y-2">
              {data.last_3_threads.map((thread, i) => (
                <div key={i} className="p-2.5 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <p className="text-xs font-medium text-gray-800 dark:text-gray-200 line-clamp-1 flex-1">
                      {thread.subject || '(no subject)'}
                    </p>
                    <span style={{ color: sentimentColor(thread.sentiment) }}>
                      {sentimentIcon(thread.sentiment)}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{thread.summary}</p>
                  <div className="flex items-center justify-between mt-1.5">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      thread.direction === 'inbound'
                        ? 'bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400'
                        : 'bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400'
                    }`}>
                      {thread.direction}
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date(thread.date).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <div className="text-xs text-gray-400 text-center pb-4">
            {data.total_interactions} total interactions
          </div>
        </div>
      )}
    </div>
  );
}
