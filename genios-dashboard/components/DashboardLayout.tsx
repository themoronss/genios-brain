'use client';

import { useSession } from 'next-auth/react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { ConnectionStatus } from '@/types';
import Sidebar from './Sidebar';
import { Bell, RefreshCcw } from 'lucide-react';

interface DashboardLayoutProps {
  children: React.ReactNode;
  title?: string;
}

export default function DashboardLayout({ children, title = 'Dashboard' }: DashboardLayoutProps) {
  const { data: session } = useSession();
  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  const { data: status } = useQuery<ConnectionStatus>({
    queryKey: ['connection-status', orgId],
    queryFn: () => api.org.getStatus(orgId, token),
    enabled: !!orgId && !!token,
    refetchInterval: (q) => {
      const d = q.state.data as ConnectionStatus | undefined;
      return d?.sync_status === 'running' ? 3000 : 30000;
    },
  });

  const syncStatusColor = !status ? 'bg-slate-500' :
    status.sync_status === 'running' ? 'bg-orange-500' :
    status.sync_error ? 'bg-red-500' : 'bg-emerald-500';

  const syncStatusText = !status ? 'Loading...' :
    status.sync_status === 'running' ? 'Syncing...' :
    status.sync_error ? 'Sync Failed' :
    status.last_sync ? `Synced ${new Date(status.last_sync).toLocaleTimeString()}` : 'Not synced';

  return (
    <div className="min-h-screen bg-slate-950">
      <Sidebar />

      {/* Main content area */}
      <div className="ml-56">
        {/* Top Bar */}
        <header className="sticky top-0 z-40 h-14 bg-slate-950/80 backdrop-blur border-b border-slate-800 flex items-center justify-between px-6">
          {/* Left: Page Title */}
          <h1 className="text-lg font-semibold text-white">{title}</h1>

          {/* Center: Sync Status */}
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${syncStatusColor}`} />
            <span className="text-xs text-slate-400">{syncStatusText}</span>
            {status?.sync_status === 'running' && (
              <RefreshCcw className="w-3 h-3 text-orange-400 animate-spin" />
            )}
          </div>

          {/* Right: Notification + Avatar */}
          <div className="flex items-center gap-3">
            <button className="relative p-1.5 text-slate-400 hover:text-white transition-colors">
              <Bell className="w-4 h-4" />
            </button>
            <div className="w-7 h-7 rounded-full bg-indigo-600/30 flex items-center justify-center text-indigo-400 text-xs font-medium">
              {(session?.user?.name || 'U')[0].toUpperCase()}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
