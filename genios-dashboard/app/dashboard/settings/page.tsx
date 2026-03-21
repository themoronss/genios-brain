'use client';

import { useSession } from 'next-auth/react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Copy, Eye, EyeOff, Check, RefreshCw,
  Mail, Trash2, Plus, RefreshCcw, Settings, KeyRound,
  ShieldAlert, AlertTriangle, Download,
} from 'lucide-react';

function SectionCard({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-card border border-border rounded-2xl overflow-hidden ${className}`}>
      {children}
    </div>
  );
}

function SectionHeader({ icon: Icon, title, description, action }: {
  icon: React.ElementType;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-6 py-5 border-b border-border">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
          <Icon className="h-4 w-4 text-primary" />
        </div>
        <div>
          <h2 className="font-semibold text-foreground">{title}</h2>
          <p className="text-sm text-muted-foreground mt-0.5">{description}</p>
        </div>
      </div>
      {action && <div className="shrink-0 ml-4">{action}</div>}
    </div>
  );
}

export default function SettingsPage() {
  const { data: session } = useSession();
  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;
  const queryClient = useQueryClient();

  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const { data: keyData, refetch: refetchKey } = useQuery<{ api_key: string }>({
    queryKey: ['apikey', orgId],
    queryFn: () => api.org.getApiKey(orgId, token),
    enabled: !!orgId && !!token,
  });

  const regenerateMutation = useMutation({
    mutationFn: () => api.org.regenerateApiKey(orgId, token),
    onSuccess: () => { refetchKey(); showToast('API key regenerated successfully.'); },
    onError: () => showToast('Failed to regenerate API key.', 'error'),
  });

  const resetMutation = useMutation({
    mutationFn: () => api.org.resetData(orgId, token),
    onSuccess: () => {
      refetchAccounts();
      // Invalidate all dashboard caches so stale graph data is discarded
      queryClient.invalidateQueries({ queryKey: ['graph-data'] });
      queryClient.invalidateQueries({ queryKey: ['connection-status'] });
      queryClient.invalidateQueries({ queryKey: ['gmail-accounts'] });
      showToast('Graph data wiped. Accounts remain connected — click Sync to rebuild.');
    },
    onError: () => showToast('Failed to wipe graph data.', 'error'),
  });

  const { data: accountsData, refetch: refetchAccounts } = useQuery<{ accounts: any[]; count: number }>({
    queryKey: ['gmail-accounts', orgId],
    queryFn: () => api.gmail.listAccounts(orgId, token),
    enabled: !!orgId && !!token,
    refetchInterval: (query) => {
      const data = query.state.data as any;
      if (data?.accounts?.some((a: any) => a.sync_status === 'syncing' || a.sync_status === 'running')) return 3000;
      return false;
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: (email: string) => api.gmail.disconnectAccount(orgId, email, token),
    onSuccess: () => { refetchAccounts(); showToast('Account disconnected. Graph data was kept.'); },
    onError: () => showToast('Failed to disconnect account.', 'error'),
  });

  const syncAccountMutation = useMutation({
    mutationFn: (email: string) => api.gmail.syncAccount(orgId, email, token),
    onSuccess: () => { refetchAccounts(); showToast('Sync started in the background…'); },
    onError: () => showToast('Failed to start sync.', 'error'),
  });

  const handleCopy = () => {
    if (keyData?.api_key) {
      navigator.clipboard.writeText(keyData.api_key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const maskedKey = keyData?.api_key
    ? (showKey ? keyData.api_key : keyData.api_key.slice(0, 8) + '••••••••••••••••••••••••••••')
    : '••••••••••••••••••••••••••••••••';

  return (
    <div className="h-full overflow-y-auto bg-background">

      {/* Toast Notification */}
      {toast && (
        <div className={`fixed top-5 right-5 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-xl border text-sm font-medium animate-in slide-in-from-right transition-all
          ${toast.type === 'success'
            ? 'bg-card border-green-500/30 text-foreground'
            : 'bg-card border-destructive/30 text-foreground'
          }`}
        >
          {toast.type === 'success'
            ? <Check className="h-4 w-4 text-green-500 shrink-0" />
            : <AlertTriangle className="h-4 w-4 text-destructive shrink-0" />
          }
          {toast.message}
        </div>
      )}

      <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
            <Settings className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Settings</h1>
            <p className="text-sm text-muted-foreground">Manage your API keys and connected accounts.</p>
          </div>
        </div>

        {/* ─── API Key ────────────────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={KeyRound}
            title="API Key"
            description="Use this key to authenticate requests to the GenIOS context endpoint."
          />
          <div className="px-6 py-5 space-y-4">
            {/* Key Input */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  readOnly
                  value={maskedKey}
                  className="h-11 w-full rounded-xl border border-border bg-background px-4 pr-10 text-sm font-mono text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
                <button
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <Button onClick={handleCopy} variant="outline" className="gap-2 h-11 px-5 shrink-0">
                {copied ? <><Check className="h-4 w-4 text-green-500" />Copied</> : <><Copy className="h-4 w-4" />Copy</>}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              ⚠️ Never share your API key in public spaces like GitHub or client-side code.
            </p>
          </div>
        </SectionCard>

        {/* ─── Connected Accounts ─────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={Mail}
            title="Connected Gmail Accounts"
            description="Manage the email accounts feeding your relationship graph."
            action={
              <Button onClick={() => api.gmail.connect(orgId)} variant="outline" size="sm" className="gap-2">
                <Plus className="h-4 w-4" /> Connect Account
              </Button>
            }
          />
          <div className="px-6 py-5">
            {accountsData?.accounts && accountsData.accounts.length > 0 ? (
              <div className="space-y-3">
                {accountsData.accounts.map((acc, idx) => {
                  const isSyncing = acc.sync_status === 'syncing' || acc.sync_status === 'running';
                  const statusColor = isSyncing
                    ? 'bg-blue-500/10 text-blue-500 border-blue-500/20'
                    : acc.sync_status === 'completed'
                      ? 'bg-green-500/10 text-green-500 border-green-500/20'
                      : 'bg-muted text-muted-foreground border-border';

                  return (
                    <div key={idx} className="flex items-center justify-between p-4 border border-border rounded-xl bg-background gap-4">
                      {/* Account info */}
                      <div className="flex items-center gap-4 min-w-0">
                        <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center shrink-0">
                          <Mail className="h-5 w-5 text-red-500" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-foreground truncate">{acc.account_email}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge className={`text-xs px-2 py-0 border ${statusColor}`}>
                              {isSyncing ? '⏳ Syncing…' : acc.sync_status === 'completed' ? '✅ Synced' : acc.sync_status || 'Idle'}
                            </Badge>
                            {acc.last_synced_at && (
                              <span className="text-xs text-muted-foreground">
                                {new Date(acc.last_synced_at).toLocaleString()}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => syncAccountMutation.mutate(acc.account_email)}
                          disabled={isSyncing || syncAccountMutation.isPending}
                          className="gap-2"
                        >
                          <RefreshCcw className={`h-3.5 w-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
                          {isSyncing ? 'Syncing…' : 'Sync'}
                        </Button>
                        <button
                          onClick={() => {
                            if (window.confirm(`Disconnect ${acc.account_email}? Graph data will be kept.`)) {
                              disconnectMutation.mutate(acc.account_email);
                            }
                          }}
                          disabled={disconnectMutation.isPending}
                          className="p-2 rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                          title="Disconnect account"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-10 space-y-3">
                <Mail className="h-10 w-10 text-muted-foreground mx-auto" />
                <p className="text-sm text-muted-foreground">No Gmail accounts connected yet.</p>
                <Button onClick={() => api.gmail.connect(orgId)} variant="outline" size="sm" className="gap-2">
                  <Plus className="h-4 w-4" /> Connect Gmail Account
                </Button>
              </div>
            )}
          </div>
        </SectionCard>

        {/* ─── Sync Settings ──────────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={RefreshCw}
            title="Sync Settings"
            description="Configure how often GeniOS syncs your email data."
          />
          <div className="px-6 py-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Sync Interval</p>
                <p className="text-xs text-muted-foreground mt-0.5">How often to check for new emails (cron schedule).</p>
              </div>
              <select
                className="h-9 px-3 rounded-lg border border-border bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                defaultValue="24"
              >
                <option value="6">Every 6 hours</option>
                <option value="12">Every 12 hours</option>
                <option value="18">Every 18 hours</option>
                <option value="24">Every 24 hours</option>
              </select>
            </div>
          </div>
        </SectionCard>

        {/* ─── Graph Export ───────────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={Download}
            title="Export Graph Data"
            description="Download your relationship graph as a CSV file."
          />
          <div className="px-6 py-5">
            <div className="flex items-center justify-between p-4 border border-border rounded-xl">
              <div>
                <p className="text-sm font-medium text-foreground">Export all relationships</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Downloads a CSV with all contacts, scores, stages, and relationship metrics.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 shrink-0 ml-4"
                onClick={() => api.graph.exportCsv(orgId)}
              >
                <Download className="h-3.5 w-3.5" />
                Export CSV
              </Button>
            </div>
          </div>
        </SectionCard>

        {/* ─── Danger Zone ─────────────────────────────────────────────── */}
        <SectionCard>
          <SectionHeader
            icon={ShieldAlert}
            title="Danger Zone"
            description="Irreversible actions — proceed with caution."
          />
          <div className="px-6 py-5 space-y-3">
            {/* Regenerate Key */}
            <div className="flex items-center justify-between p-4 border border-border rounded-xl">
              <div>
                <p className="text-sm font-medium text-foreground">Regenerate API Key</p>
                <p className="text-xs text-muted-foreground mt-0.5">All existing integrations using the old key will immediately stop working.</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 border-destructive/30 text-destructive hover:bg-destructive/10 shrink-0 ml-4"
                disabled={regenerateMutation.isPending}
                onClick={() => {
                  if (window.confirm('Regenerate API key? All existing integrations will break immediately.')) {
                    regenerateMutation.mutate();
                  }
                }}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${regenerateMutation.isPending ? 'animate-spin' : ''}`} />
                Regenerate
              </Button>
            </div>

            {/* Wipe Graph Data */}
            <div className="flex items-center justify-between p-4 border border-destructive/20 bg-destructive/5 rounded-xl">
              <div>
                <p className="text-sm font-medium text-foreground">Wipe All Graph Data</p>
                <p className="text-xs text-muted-foreground mt-0.5">Deletes all contacts and relationships. Connected Gmail accounts are kept intact.</p>
              </div>
              <Button
                variant="destructive"
                size="sm"
                className="gap-2 shrink-0 ml-4"
                disabled={resetMutation.isPending}
                onClick={() => {
                  if (window.confirm('Wipe all graph data? This deletes all contacts and relationships but keeps your Gmail accounts connected.')) {
                    resetMutation.mutate();
                  }
                }}
              >
                <Trash2 className={`h-3.5 w-3.5 ${resetMutation.isPending ? 'animate-spin' : ''}`} />
                Wipe Data
              </Button>
            </div>
          </div>
        </SectionCard>

      </div>
    </div>
  );
}
