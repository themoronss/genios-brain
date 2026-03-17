'use client';

import { useSession } from 'next-auth/react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Copy, Eye, EyeOff, Check, RefreshCw, Mail, Trash2, Plus, RefreshCcw } from 'lucide-react';
import { formatDate } from '@/lib/utils';

export default function SettingsPage() {
  const { data: session } = useSession();
  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: keyData, refetch } = useQuery<{api_key: string}>({
    queryKey: ['apikey', orgId],
    queryFn: () => api.org.getApiKey(orgId, token),
    enabled: !!orgId && !!token,
  });

  const regenerateMutation = useMutation({
    mutationFn: () => api.org.regenerateApiKey(orgId, token),
    onSuccess: () => {
      refetch();
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => api.org.resetData(orgId, token),
    onSuccess: () => {
      alert("Graph data wiped successfully! Your connected accounts were kept intact.");
      refetchAccounts();
    },
  });

  // Fetch connected accounts
  const { data: accountsData, refetch: refetchAccounts } = useQuery<{ accounts: any[]; count: number }>({
    queryKey: ['gmail-accounts', orgId],
    queryFn: () => api.gmail.listAccounts(orgId, token),
    enabled: !!orgId && !!token,
    refetchInterval: (query) => {
      // Poll if any account is syncing
      const data = query.state.data;
      if (data?.accounts?.some(acc => acc.sync_status === 'syncing' || acc.sync_status === 'idle')) {
        return 3000;
      }
      return false;
    },
  });

  // Disconnect account mutation
  const disconnectMutation = useMutation({
    mutationFn: (accountEmail: string) => api.gmail.disconnectAccount(orgId, accountEmail, token),
    onSuccess: () => {
      refetchAccounts();
    },
  });

  // Sync specific account mutation
  const syncAccountMutation = useMutation({
    mutationFn: (accountEmail: string) => api.gmail.syncAccount(orgId, accountEmail, token),
    onSuccess: () => {
      alert("Sync triggered for this account. It will run in the background.");
      refetchAccounts();
    },
    onError: () => {
      alert("Failed to trigger sync. Please try again.");
    }
  });

  const handleCopy = () => {
    if (keyData?.api_key) {
      navigator.clipboard.writeText(keyData.api_key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Settings</h1>
      
      <Card>
        <CardHeader>
          <CardTitle>API Keys</CardTitle>
          <CardDescription>
            Use this API key to authenticate your requests to the GeniOS context endpoint.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Live API Key</label>
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <input
                  type={showKey ? 'text' : 'password'}
                  readOnly
                  value={keyData?.api_key || '••••••••••••••••••••••••••••••••'}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <Button onClick={handleCopy} variant="outline" className="w-24 gap-2 border-indigo-200 text-indigo-700 hover:bg-indigo-50 hover:text-indigo-800">
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? 'Copied' : 'Copy'}
              </Button>
            </div>
            <p className="text-xs text-slate-500">
              Do not share your API key in publicly accessible areas such as GitHub, client-side code, and so forth.
            </p>
          </div>

          <div className="pt-4 border-t border-slate-100">
            <h3 className="text-sm font-medium text-slate-900 mb-2">Danger Zone</h3>
            <div className="flex flex-col gap-3 items-start">
              <Button 
                variant="destructive" 
                onClick={() => {
                  if(confirm("Are you sure you want to regenerate your API key? Any existing integrations will immediately stop working.")) {
                    regenerateMutation.mutate();
                  }
                }}
                disabled={regenerateMutation.isPending}
                className="gap-2"
              >
                <RefreshCw className={`h-4 w-4 ${regenerateMutation.isPending ? 'animate-spin' : ''}`} />
                Regenerate API Key
              </Button>

              <Button 
                variant="destructive" 
                onClick={() => {
                  if(confirm("Are you sure you want to wipe all graph data? This will delete all generated contacts and relationships, but will KEEP your Gmail accounts connected. You can sync again afterwards.")) {
                    resetMutation.mutate();
                  }
                }}
                disabled={resetMutation.isPending}
                className="gap-2 bg-red-100 text-red-700 hover:bg-red-200 border-none"
              >
                <Trash2 className={`h-4 w-4 ${resetMutation.isPending ? 'animate-spin' : ''}`} />
                Wipe All Graph Data
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Connected Accounts Card */}
      <Card className="mt-8">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Connected Gmail Accounts</CardTitle>
              <CardDescription>
                Manage the email accounts that feed your relationship graph.
              </CardDescription>
            </div>
            <Button onClick={() => api.gmail.connect(orgId)} className="gap-2" variant="outline">
              <Plus className="h-4 w-4" />
              Connect Account
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {accountsData?.accounts && accountsData.accounts.length > 0 ? (
            <div className="space-y-4">
              {accountsData.accounts.map((acc, idx) => (
                <div key={idx} className="flex items-center justify-between p-4 border rounded-lg bg-slate-50">
                  <div className="flex items-center gap-4">
                    <div className="p-2 bg-indigo-100 rounded-lg text-indigo-600">
                      <Mail className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="font-medium text-slate-900">{acc.account_email}</h4>
                      <p className="text-sm text-slate-500">
                        Status: <span className="capitalize">{acc.sync_status || 'idle'}</span>
                      </p>
                      {acc.last_synced_at && (
                        <p className="text-xs text-slate-400">
                          Last sync: {new Date(acc.last_synced_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => syncAccountMutation.mutate(acc.account_email)}
                      disabled={syncAccountMutation.isPending || acc.sync_status === 'syncing'}
                      className="gap-2"
                    >
                      <RefreshCcw className={`h-4 w-4 ${acc.sync_status === 'syncing' ? 'animate-spin' : ''}`} />
                      Sync
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        if (confirm(`Are you sure you want to disconnect ${acc.account_email}? Your graph data will be kept.`)) {
                          disconnectMutation.mutate(acc.account_email);
                        }
                      }}
                      disabled={disconnectMutation.isPending}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="h-5 w-5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-slate-500">
              No Gmail accounts connected.
            </div>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
