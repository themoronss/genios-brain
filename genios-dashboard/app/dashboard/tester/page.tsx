'use client';

import { useSession } from 'next-auth/react';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { ContextBundle } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Search, Copy, Check, FlaskConical, AlertCircle,
  MessageSquare, Bookmark, TrendingUp, Target,
  ShieldAlert, Sparkles, Activity, Database,
  Clock, CheckCircle2, XCircle, ChevronDown, ChevronRight,
  BarChart3,
} from 'lucide-react';
import { DraftModal } from '@/components/DraftModal';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Tab = 'overview' | 'facts' | 'lifecycle' | 'commitments' | 'tester';

interface HealthCards {
  total_facts: number;
  avg_confidence: number;
  facts_decaying: number;
  conflicts_detected: number;
}

interface RecentEvent {
  id?: string;
  event_type: string;
  event_data?: any;
  created_at?: string;
  // Mapped fields
  description?: string;
  timestamp?: string;
}

interface Fact {
  id: string;
  entity: string;
  entity_type: string;
  type: string;
  stage: string;
  freshness: number;
  confidence: number;
  consistency: number;
  authority: number;
  composite: number;
  [key: string]: any;
}

interface Commitment {
  id: string;
  text: string;
  contact_name: string;
  company: string;
  due_date: string;
  days_overdue?: number;
  owner: string;
  status: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'overview',    label: 'Overview',        icon: <BarChart3 className="h-4 w-4" /> },
  { key: 'facts',       label: 'Active Facts',    icon: <Database className="h-4 w-4" /> },
  { key: 'lifecycle',   label: 'Lifecycle',       icon: <Activity className="h-4 w-4" /> },
  { key: 'commitments', label: 'Commitments',     icon: <Target className="h-4 w-4" /> },
  { key: 'tester',      label: 'Context Tester',  icon: <FlaskConical className="h-4 w-4" /> },
];

function scoreColor(v: number) {
  if (v >= 0.7) return 'bg-green-500';
  if (v >= 0.4) return 'bg-amber-500';
  return 'bg-red-500';
}

function eventBadgeColor(type: string) {
  const t = type.toLowerCase();
  if (t.includes('create') || t.includes('add')) return 'bg-green-500/15 text-green-600 border-green-500/30';
  if (t.includes('decay') || t.includes('conflict')) return 'bg-red-500/15 text-red-600 border-red-500/30';
  if (t.includes('update') || t.includes('merge')) return 'bg-blue-500/15 text-blue-600 border-blue-500/30';
  return 'bg-muted text-muted-foreground border-border';
}

function relativeTime(ts: string | null | undefined) {
  if (!ts) return '';
  const parsed = new Date(ts);
  if (isNaN(parsed.getTime())) return ts; // fallback to raw string if unparseable
  const diff = Date.now() - parsed.getTime();
  if (diff < 0) return 'just now';
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// ---------------------------------------------------------------------------
// Score bar component
// ---------------------------------------------------------------------------

function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${scoreColor(value)}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-muted-foreground w-8 text-right">{pct}</span>
    </div>
  );
}

// ===========================================================================
// Main Page
// ===========================================================================

export default function ContextPage() {
  const { data: session } = useSession();
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-foreground">Context</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Monitor fact health, lifecycle events, commitments, and test context bundles.
          </p>
        </div>

        {/* Tab Bar */}
        <div className="flex gap-1 border-b border-border overflow-x-auto">
          {TABS.map(({ key, label, icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
                activeTab === key
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/30'
              }`}
            >
              {icon}
              {label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && <OverviewTab orgId={orgId} token={token} />}
        {activeTab === 'facts' && <ActiveFactsTab orgId={orgId} token={token} />}
        {activeTab === 'lifecycle' && <LifecycleTab orgId={orgId} token={token} />}
        {activeTab === 'commitments' && <CommitmentsTab orgId={orgId} token={token} />}
        {activeTab === 'tester' && <ContextTesterTab orgId={orgId} token={token} />}
      </div>
    </div>
  );
}

// ===========================================================================
// Tab 1 — Overview
// ===========================================================================

function OverviewTab({ orgId, token }: { orgId: string; token: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['facts-overview', orgId],
    queryFn: () => api.facts.getOverview(orgId, token),
    enabled: !!orgId && !!token,
  });

  const health: HealthCards = data?.health_cards ?? {
    total_facts: 0, avg_confidence: 0, facts_decaying: 0, conflicts_detected: 0,
  };
  const events: RecentEvent[] = data?.recent_events ?? [];

  const avgConf = health.avg_confidence;
  const confColorClass = avgConf >= 0.7 ? 'text-green-500' : avgConf >= 0.4 ? 'text-amber-500' : 'text-red-500';
  const confBgClass = avgConf >= 0.7 ? 'bg-green-500/10 border-green-500/30' : avgConf >= 0.4 ? 'bg-amber-500/10 border-amber-500/30' : 'bg-red-500/10 border-red-500/30';

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      {/* Health Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <HealthCard label="Total Facts" value={health.total_facts} icon={<Database className="h-5 w-5 text-primary" />} />
        <div className={`bg-card border rounded-xl p-5 ${confBgClass}`}>
          <div className="flex items-center gap-2 mb-2">
            <BarChart3 className={`h-5 w-5 ${confColorClass}`} />
            <span className="text-xs text-muted-foreground uppercase tracking-wide">Avg Confidence</span>
          </div>
          <p className={`text-2xl font-bold ${confColorClass}`}>{Math.round(avgConf * 100)}%</p>
        </div>
        <HealthCard
          label="Facts Decaying"
          value={health.facts_decaying}
          icon={<Clock className="h-5 w-5 text-amber-500" />}
          subtitle="freshness < 0.60"
        />
        <HealthCard
          label="Conflicts Detected"
          value={health.conflicts_detected}
          icon={<AlertCircle className="h-5 w-5 text-red-500" />}
          subtitle="consistency < 0.40"
        />
      </div>

      {/* Activity Stream */}
      <div className="bg-card border border-border rounded-xl">
        <div className="px-5 py-4 border-b border-border flex items-center gap-2">
          <Activity className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold text-foreground text-sm">Recent Activity</h3>
        </div>
        {events.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground text-sm">No recent events.</div>
        ) : (
          <div className="divide-y divide-border">
            {events.map((ev, i) => {
              const desc = ev.description || (typeof ev.event_data === 'string' ? ev.event_data : ev.event_data?.name ? `${ev.event_data.name}${ev.event_data.company ? ` @ ${ev.event_data.company}` : ''}` : JSON.stringify(ev.event_data || ''));
              const ts = ev.timestamp || ev.created_at;
              return (
                <div key={ev.id ?? i} className="px-5 py-3 flex items-start gap-3">
                  <Badge className={`text-xs shrink-0 ${eventBadgeColor(ev.event_type)}`}>{ev.event_type}</Badge>
                  <span className="text-sm text-foreground flex-1">{desc}</span>
                  <span className="text-xs text-muted-foreground shrink-0">{relativeTime(ts)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function HealthCard({ label, value, icon, subtitle }: { label: string; value: number; icon: React.ReactNode; subtitle?: string }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs text-muted-foreground uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
      {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
    </div>
  );
}

// ===========================================================================
// Tab 2 — Active Facts
// ===========================================================================

function ActiveFactsTab({ orgId, token }: { orgId: string; token: string }) {
  const [search, setSearch] = useState('');
  const [entityType, setEntityType] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (entityType) params.set('entity_type', entityType);

  const { data, isLoading } = useQuery({
    queryKey: ['facts-list', orgId, search, entityType],
    queryFn: () => api.facts.list(orgId, token, params.toString()),
    enabled: !!orgId && !!token,
  });

  const facts: Fact[] = data?.facts ?? [];
  const entityTypes = [...new Set(facts.map((f) => f.entity_type).filter(Boolean))];

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by entity name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 bg-background border-border h-10"
          />
        </div>
        <select
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          className="h-10 rounded-md border border-border bg-background px-3 text-sm text-foreground"
        >
          <option value="">All Types</option>
          {entityTypes.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Entity</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Type</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Stage</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Freshness</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Confidence</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Consistency</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Authority</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Composite</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {facts.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">No facts found.</td></tr>
              )}
              {facts.map((f) => (
                <FactRow key={f.id} fact={f} expanded={expandedId === f.id} onToggle={() => setExpandedId(expandedId === f.id ? null : f.id)} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {data?.total != null && (
        <p className="text-xs text-muted-foreground">
          Showing {facts.length} of {data.total} facts
        </p>
      )}
    </div>
  );
}

function FactRow({ fact, expanded, onToggle }: { fact: Fact; expanded: boolean; onToggle: () => void }) {
  return (
    <>
      <tr
        onClick={onToggle}
        className="cursor-pointer hover:bg-muted/30 transition-colors"
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {expanded ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
            <span className="font-medium text-foreground">{fact.entity}</span>
          </div>
        </td>
        <td className="px-4 py-3"><Badge variant="secondary" className="text-xs">{fact.entity_type}</Badge></td>
        <td className="px-4 py-3"><Badge variant="outline" className="text-xs">{fact.stage}</Badge></td>
        <td className="px-4 py-3"><ScoreBar value={fact.freshness} /></td>
        <td className="px-4 py-3"><ScoreBar value={fact.confidence} /></td>
        <td className="px-4 py-3"><ScoreBar value={fact.consistency} /></td>
        <td className="px-4 py-3"><ScoreBar value={fact.authority} /></td>
        <td className="px-4 py-3"><ScoreBar value={fact.composite} /></td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={8} className="px-6 py-4 bg-muted/20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              {['freshness', 'confidence', 'consistency', 'authority', 'composite'].map((key) => (
                <div key={key}>
                  <span className="text-muted-foreground capitalize">{key}</span>
                  <div className="flex items-center gap-2 mt-1">
                    <div className={`w-3 h-3 rounded-full ${scoreColor(fact[key] as number)}`} />
                    <span className="font-mono font-semibold text-foreground">{((fact[key] as number) * 100).toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
            {fact.type && (
              <div className="mt-3 text-xs">
                <span className="text-muted-foreground">Fact type:</span>{' '}
                <span className="text-foreground font-medium">{fact.type}</span>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

// ===========================================================================
// Tab 3 — Lifecycle Activity
// ===========================================================================

function LifecycleTab({ orgId, token }: { orgId: string; token: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['facts-lifecycle', orgId],
    queryFn: () => api.facts.getLifecycle(orgId, token),
    enabled: !!orgId && !!token,
  });

  const events: RecentEvent[] = data?.events ?? [];

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      <div className="bg-card border border-border rounded-xl">
        {events.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground text-sm">No lifecycle events yet.</div>
        ) : (
          <div className="divide-y divide-border">
            {events.map((ev, i) => {
              const desc = ev.description || (typeof ev.event_data === 'string' ? ev.event_data : ev.event_data?.name ? `${ev.event_data.name}${ev.event_data.company ? ` @ ${ev.event_data.company}` : ''}` : JSON.stringify(ev.event_data || ''));
              const ts = ev.timestamp || ev.created_at;
              const tsDate = ts ? new Date(ts) : null;
              return (
              <div key={ev.id ?? i} className="px-5 py-4 flex items-start gap-4">
                <div className="mt-0.5 shrink-0">
                  <div className={`w-2.5 h-2.5 rounded-full ${eventBadgeColor(ev.event_type).includes('green') ? 'bg-green-500' : eventBadgeColor(ev.event_type).includes('red') ? 'bg-red-500' : 'bg-blue-500'}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className={`text-xs ${eventBadgeColor(ev.event_type)}`}>{ev.event_type}</Badge>
                    <span className="text-xs text-muted-foreground">{relativeTime(ts)}</span>
                  </div>
                  <p className="text-sm text-foreground">{desc}</p>
                  {tsDate && !isNaN(tsDate.getTime()) && (
                    <p className="text-xs text-muted-foreground mt-1">{tsDate.toLocaleString()}</p>
                  )}
                </div>
              </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ===========================================================================
// Tab 4 — Commitments
// ===========================================================================

function CommitmentsTab({ orgId, token }: { orgId: string; token: string }) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['commitments', orgId],
    queryFn: () => api.commitments.list(orgId, token),
    enabled: !!orgId && !!token,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.commitments.update(orgId, id, { status }, token),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['commitments', orgId] }),
  });

  const overdue: Commitment[] = data?.overdue ?? [];
  const open: Commitment[] = data?.open ?? [];
  const fulfilled: Commitment[] = data?.fulfilled ?? [];

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      {/* Overdue */}
      <CommitmentSection
        title="Overdue"
        items={overdue}
        borderColor="border-red-500/40"
        bgColor="bg-red-500/5"
        badgeColor="bg-red-500/15 text-red-600"
        icon={<XCircle className="h-4 w-4 text-red-500" />}
        onMarkFulfilled={(id) => updateMutation.mutate({ id, status: 'fulfilled' })}
        onDismiss={(id) => updateMutation.mutate({ id, status: 'dismissed' })}
        isPending={updateMutation.isPending}
      />

      {/* Open */}
      <CommitmentSection
        title="Open"
        items={open}
        borderColor="border-amber-500/40"
        bgColor="bg-amber-500/5"
        badgeColor="bg-amber-500/15 text-amber-600"
        icon={<Clock className="h-4 w-4 text-amber-500" />}
        onMarkFulfilled={(id) => updateMutation.mutate({ id, status: 'fulfilled' })}
        onDismiss={(id) => updateMutation.mutate({ id, status: 'dismissed' })}
        isPending={updateMutation.isPending}
      />

      {/* Fulfilled */}
      <CommitmentSection
        title="Recently Fulfilled"
        items={fulfilled}
        borderColor="border-green-500/40"
        bgColor="bg-green-500/5"
        badgeColor="bg-green-500/15 text-green-600"
        icon={<CheckCircle2 className="h-4 w-4 text-green-500" />}
        readonly
      />
    </div>
  );
}

function CommitmentSection({
  title, items, borderColor, bgColor, badgeColor, icon, onMarkFulfilled, onDismiss, readonly, isPending,
}: {
  title: string;
  items: Commitment[];
  borderColor: string;
  bgColor: string;
  badgeColor: string;
  icon: React.ReactNode;
  onMarkFulfilled?: (id: string) => void;
  onDismiss?: (id: string) => void;
  readonly?: boolean;
  isPending?: boolean;
}) {
  return (
    <div className={`border ${borderColor} rounded-xl overflow-hidden`}>
      <div className={`px-5 py-3 ${bgColor} flex items-center gap-2 border-b ${borderColor}`}>
        {icon}
        <h3 className="font-semibold text-foreground text-sm">{title}</h3>
        <Badge className={`ml-auto text-xs ${badgeColor}`}>{items.length}</Badge>
      </div>
      {items.length === 0 ? (
        <div className="p-6 text-center text-muted-foreground text-sm">None</div>
      ) : (
        <div className="divide-y divide-border">
          {items.map((c) => (
            <div key={c.id} className="px-5 py-4 space-y-2">
              <p className="text-sm font-medium text-foreground">{c.text}</p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                {c.contact_name && <span>Contact: {c.contact_name}</span>}
                {c.company && <span>Company: {c.company}</span>}
                {c.due_date && <span>Due: {c.due_date}</span>}
                {c.days_overdue != null && c.days_overdue > 0 && (
                  <span className="text-red-500 font-medium">{c.days_overdue}d overdue</span>
                )}
                {c.owner && <span>Owner: {c.owner}</span>}
              </div>
              {!readonly && (
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs gap-1 border-green-500/30 text-green-600 hover:bg-green-500/10"
                    disabled={isPending}
                    onClick={() => onMarkFulfilled?.(c.id)}
                  >
                    <CheckCircle2 className="h-3 w-3" /> Mark Fulfilled
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs gap-1"
                    disabled={isPending}
                    onClick={() => onDismiss?.(c.id)}
                  >
                    <XCircle className="h-3 w-3" /> Not a Commitment
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ===========================================================================
// Tab 5 — Context Tester (original page content)
// ===========================================================================

function ContextTesterTab({ orgId, token }: { orgId: string; token: string }) {
  const [contactName, setContactName] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [copied, setCopied] = useState(false);
  const [draftOpen, setDraftOpen] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);

  const { data: bundle, isLoading, error } = useQuery<ContextBundle>({
    queryKey: ['context-tester', orgId, submitted],
    queryFn: () => api.context.getBundle(orgId, submitted, token),
    enabled: !!orgId && !!token && submitted.length > 0,
    retry: false,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (contactName.trim()) setSubmitted(contactName.trim());
  };

  const handleCopy = () => {
    if (bundle?.context_for_agent) {
      navigator.clipboard.writeText(bundle.context_for_agent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const confidence = Math.round((bundle?.confidence || 0) * 100);

  return (
    <div className="space-y-6">

      {/* Search Box */}
      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-3">
          <FlaskConical className="h-4 w-4 text-primary" />
          <h3 className="font-semibold text-foreground text-sm">Context Tester</h3>
        </div>
        <p className="text-xs text-muted-foreground mb-4">
          Search any contact to see exactly what your AI agents will know about them.
        </p>
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Enter contact name — e.g. Mohit Jain, Flipkart..."
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              className="pl-9 bg-background border-border h-11"
              autoFocus
            />
          </div>
          <Button type="submit" disabled={!contactName.trim() || isLoading} className="gap-2 h-11 px-6">
            {isLoading ? (
              <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-foreground" />Searching...</>
            ) : (
              <><Search className="h-4 w-4" />Search</>
            )}
          </Button>
        </form>
      </div>

      {/* Error State */}
      {error && submitted && (
        <div className="bg-card border border-border rounded-xl p-8 text-center space-y-3">
          <AlertCircle className="h-10 w-10 text-muted-foreground mx-auto" />
          <p className="font-semibold text-foreground">No contact found for &quot;{submitted}&quot;</p>
          <p className="text-sm text-muted-foreground">
            {error instanceof Error ? error.message : 'Try a different name or partial spelling.'}
          </p>
          <p className="text-xs text-muted-foreground/60">Fuzzy matching is supported — try just the first name.</p>
        </div>
      )}

      {/* Empty State */}
      {!submitted && !isLoading && (
        <div className="bg-card border border-border rounded-xl p-12 text-center space-y-3">
          <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center mx-auto">
            <Search className="h-7 w-7 text-muted-foreground" />
          </div>
          <p className="font-medium text-foreground">Search for a contact</p>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto">
            Type a name above and hit Search to see the full relationship context your AI agents will use.
          </p>
        </div>
      )}

      {/* Results */}
      {!isLoading && bundle && (
        <div className="space-y-5">

          {/* Identity + Confidence Row */}
          {bundle.entity && (
            <div className="bg-card border border-border rounded-xl p-6 flex items-center justify-between gap-6">
              <div>
                <h2 className="text-xl font-bold text-foreground">{bundle.entity.name}</h2>
                {bundle.entity.company && (
                  <p className="text-sm text-muted-foreground mt-0.5">{bundle.entity.company}</p>
                )}
                <div className="flex flex-wrap gap-2 mt-3">
                  <Badge className="bg-primary/10 text-primary border-primary/20 hover:bg-primary/10">
                    {bundle.entity.relationship_stage}
                  </Badge>
                  <Badge variant="secondary">{bundle.entity.interaction_count} interactions</Badge>
                  <Badge variant="secondary">Last: {bundle.entity.last_interaction}</Badge>
                </div>
              </div>
              {/* Confidence ring */}
              <div className="text-center shrink-0">
                <div className="relative w-16 h-16">
                  <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
                    <circle cx="32" cy="32" r="26" strokeWidth="6" className="stroke-muted fill-none" />
                    <circle
                      cx="32" cy="32" r="26" strokeWidth="6"
                      className="fill-none stroke-primary transition-all duration-700"
                      strokeDasharray={`${(confidence / 100) * 163.4} 163.4`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-foreground">
                    {confidence}%
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">Confidence</p>
              </div>
            </div>
          )}

          {/* Stats Row */}
          {bundle.entity && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Sentiment', value: bundle.entity.sentiment_trend },
                { label: 'Last Contact', value: bundle.entity.last_interaction },
                { label: 'Total Emails', value: bundle.entity.interaction_count },
                { label: 'Open Items', value: Array.isArray(bundle.entity.open_commitments) ? bundle.entity.open_commitments.length : (bundle.entity.open_commitments || 0) },
              ].map(({ label, value }) => (
                <div key={label} className="bg-card border border-border rounded-xl px-4 py-4">
                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">{label}</p>
                  <p className="text-lg font-semibold text-foreground truncate">{value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Context for Agent */}
          <div className="bg-primary/5 border border-primary/20 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-primary/20">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <h3 className="font-semibold text-foreground">Context for AI Agent</h3>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowRawJson(!showRawJson)}
                  className="gap-1 h-8 text-xs border-primary/30 hover:bg-primary/10"
                >
                  {showRawJson ? 'Formatted' : 'Raw JSON'}
                </Button>
                <Button variant="outline" size="sm" onClick={handleCopy} className="gap-2 h-8 border-primary/30 hover:bg-primary/10">
                  {copied ? <><Check className="h-3.5 w-3.5 text-green-500" />Copied!</> : <><Copy className="h-3.5 w-3.5" />Copy</>}
                </Button>
              </div>
            </div>
            <div className="px-6 py-5">
              {showRawJson ? (
                <pre className="text-xs leading-relaxed text-foreground whitespace-pre-wrap font-mono overflow-x-auto">
                  {JSON.stringify(bundle, null, 2)}
                </pre>
              ) : (
                <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap font-mono">
                  {bundle.context_for_agent}
                </p>
              )}
            </div>
            <div className="px-6 py-4 border-t border-primary/20">
              <Button onClick={() => setDraftOpen(true)} className="w-full gap-2">
                <Sparkles className="h-4 w-4" />
                Draft a Message with AI
              </Button>
            </div>
          </div>

          {/* Detail cards grid */}
          {bundle.entity && (
            <div className="grid md:grid-cols-2 gap-4">
              {bundle.entity.communication_style && (
                <div className="bg-card border border-border rounded-xl p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <MessageSquare className="h-4 w-4 text-muted-foreground" />
                    <h4 className="text-sm font-semibold text-foreground">Communication Style</h4>
                  </div>
                  <p className="text-sm text-muted-foreground">{bundle.entity.communication_style}</p>
                </div>
              )}
              {bundle.entity.topics_of_interest?.length > 0 && (
                <div className="bg-card border border-border rounded-xl p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <Bookmark className="h-4 w-4 text-muted-foreground" />
                    <h4 className="text-sm font-semibold text-foreground">Topics of Interest</h4>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {bundle.entity.topics_of_interest.map((t: string) => (
                      <Badge key={t} variant="secondary">{t}</Badge>
                    ))}
                  </div>
                </div>
              )}
              {bundle.entity.what_works && (
                <div className="bg-card border border-border rounded-xl p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <TrendingUp className="h-4 w-4 text-green-500" />
                    <h4 className="text-sm font-semibold text-foreground">What Works</h4>
                  </div>
                  <p className="text-sm text-muted-foreground">{bundle.entity.what_works}</p>
                </div>
              )}
              {bundle.entity.what_to_avoid && (
                <div className="bg-card border border-destructive/30 rounded-xl p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <ShieldAlert className="h-4 w-4 text-destructive" />
                    <h4 className="text-sm font-semibold text-foreground">What to Avoid</h4>
                  </div>
                  <p className="text-sm text-muted-foreground">{bundle.entity.what_to_avoid}</p>
                </div>
              )}
            </div>
          )}

          {/* Open Commitments */}
          {bundle.entity?.open_commitments && Array.isArray(bundle.entity.open_commitments) && bundle.entity.open_commitments.length > 0 && (
            <div className="bg-card border border-amber-500/30 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <Target className="h-4 w-4 text-amber-500" />
                <h4 className="text-sm font-semibold text-foreground">Open Commitments</h4>
              </div>
              <div className="space-y-2">
                {bundle.entity.open_commitments.map((c: string, i: number) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-amber-500/5 border border-amber-500/20 rounded-xl">
                    <AlertCircle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                    <p className="text-sm text-foreground">{c}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommended Next Step */}
          {bundle.entity?.recommended_action && (
            <div className="bg-card border border-green-500/30 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-2">
                <Target className="h-4 w-4 text-green-500" />
                <h4 className="text-sm font-semibold text-foreground">Recommended Next Step</h4>
              </div>
              <p className="text-sm text-muted-foreground">{bundle.entity.recommended_action}</p>
            </div>
          )}
        </div>
      )}

      {/* Draft Modal */}
      {bundle?.entity && (
        <DraftModal
          open={draftOpen}
          onOpenChange={setDraftOpen}
          entityName={bundle.entity.name}
        />
      )}
    </div>
  );
}

// ===========================================================================
// Shared components
// ===========================================================================

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  );
}
