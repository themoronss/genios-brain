'use client';

import { useSession } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Mail, CheckCircle, XCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import { ConnectionStatus } from '@/types';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function ConnectPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  const { data: status, isLoading } = useQuery<ConnectionStatus>({
    queryKey: ['connection-status', orgId],
    queryFn: () => api.org.getStatus(orgId, token),
    refetchInterval: (query) => {
      // Refetch every 2 seconds if ingestion is in progress
      const data = query.state.data;
      if (data && !data.ingestion_complete) {
        return 2000;
      }
      return false;
    },
    enabled: !!orgId && !!token,
  });

  useEffect(() => {
    if (status?.gmail_connected && status?.ingestion_complete) {
      router.push('/dashboard');
    }
  }, [status, router]);

  const handleConnectGmail = () => {
    if (orgId) {
      api.gmail.connect(orgId);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (status?.gmail_connected && !status.ingestion_complete) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)] px-4">
        <Card className="w-full max-w-2xl">
          <CardHeader>
            <CardTitle>Building Your Relationship Graph...</CardTitle>
            <CardDescription>
              This takes 2-5 minutes. Don't leave — you'll see results soon.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <CheckCircle className="h-5 w-5 text-green-600" />
                <span className="text-sm">Connected to Gmail</span>
              </div>
              <div className="flex items-center gap-3">
                <CheckCircle className="h-5 w-5 text-green-600" />
                <span className="text-sm">Reading email history ({status.interactions_count} messages)</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
                <span className="text-sm">Extracting contacts... {status.ingestion_progress}%</span>
              </div>
            </div>
            
            <div className="w-full bg-slate-200 rounded-full h-2.5">
              <div
                className="bg-indigo-600 h-2.5 rounded-full transition-all duration-500"
                style={{ width: `${status.ingestion_progress}%` }}
              ></div>
            </div>

            {status.contacts_count > 0 && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm font-medium text-blue-900 mb-2">Early results:</p>
                <p className="text-sm text-blue-700">
                  Found {status.contacts_count} contacts so far...
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-4rem)] px-4">
      <Card className="w-full max-w-2xl">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="p-4 bg-indigo-100 rounded-full">
              <Mail className="h-12 w-12 text-indigo-600" />
            </div>
          </div>
          <CardTitle className="text-3xl">Connect Your Gmail</CardTitle>
          <CardDescription className="text-base mt-2">
            We'll analyze your email history to build your relationship intelligence graph.
            <br />
            Takes 2-5 minutes. You can watch the progress.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <Button
            onClick={handleConnectGmail}
            size="lg"
            className="w-full"
          >
            🔗 Connect Gmail Account
          </Button>

          <div className="border-t pt-4">
            <p className="text-sm font-medium mb-3">What we'll access:</p>
            <div className="space-y-2 text-sm text-slate-600">
              <div className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                <span>Read email metadata (from, to, subject, dates)</span>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                <span>Analyze sentiment and conversation topics</span>
              </div>
              <div className="flex items-start gap-2">
                <XCircle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
                <span>Never modify or delete your emails</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
