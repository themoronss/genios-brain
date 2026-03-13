'use client';

import { useSession } from 'next-auth/react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Copy, Eye, EyeOff, Check, RefreshCw } from 'lucide-react';

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
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
