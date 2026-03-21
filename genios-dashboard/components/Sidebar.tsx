'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useSession } from 'next-auth/react';
import {
  LayoutDashboard, Brain, Plug, BookOpen, FileText, Bot, Settings,
} from 'lucide-react';

const NAV_ITEMS = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', type: 'action' },
  { href: '/dashboard/tester', icon: Brain, label: 'Context', type: 'understanding' },
  { href: '/dashboard/integrations', icon: Plug, label: 'Integrations', type: 'setup' },
  { href: '/dashboard/resources', icon: BookOpen, label: 'Resources', type: 'learn', disabled: true },
  { href: '/docs', icon: FileText, label: 'Documentation', type: 'build' },
  { href: '#', icon: Bot, label: 'Agents', type: 'future', disabled: true, badge: 'Soon' },
  { href: '/dashboard/settings', icon: Settings, label: 'Settings', type: 'control' },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();
  const userEmail = (session?.user as any)?.email || '';

  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-slate-950 border-r border-slate-800 flex flex-col z-50">
      {/* Logo */}
      <div className="p-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm">G</div>
          <span className="text-white font-semibold text-lg">GeniOS</span>
        </div>
        <p className="text-xs text-slate-500 mt-1 truncate">{userEmail}</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname?.startsWith(item.href) && item.href !== '#');
          const Icon = item.icon;

          return (
            <Link
              key={item.label}
              href={item.disabled ? '#' : item.href}
              className={`
                flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors
                ${isActive
                  ? 'bg-indigo-600/20 text-indigo-400'
                  : item.disabled
                    ? 'text-slate-600 cursor-not-allowed'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                }
              `}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{item.label}</span>
              {item.badge && (
                <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-500">
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* User Profile */}
      <div className="p-3 border-t border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-indigo-600/30 flex items-center justify-center text-indigo-400 text-xs font-medium">
            {(session?.user?.name || 'U')[0].toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs text-white truncate">{session?.user?.name || 'User'}</p>
            <p className="text-[10px] text-indigo-400">Pilot</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
