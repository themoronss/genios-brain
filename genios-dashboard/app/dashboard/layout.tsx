'use client';

import { useSession, signOut } from 'next-auth/react';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import Link from 'next/link';
import {
  LayoutDashboard,
  FlaskConical,
  Plug,
  Settings,
  LogOut,
  Sun,
  Moon,
  ChevronLeft,
  ChevronRight,
  BookOpen,
} from 'lucide-react';
import MrEliteChatbot from '@/components/MrEliteChatbot';

const NAV_ITEMS = [
  { label: 'Dashboard',       href: '/dashboard',              icon: LayoutDashboard },
  { label: 'Context Tester',  href: '/dashboard/tester',       icon: FlaskConical },
  { label: 'Integrations',    href: '/dashboard/integrations', icon: Plug },
  { label: 'Resources',       href: '/dashboard/resources',    icon: BookOpen },
  { label: 'Settings',        href: '/dashboard/settings',     icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (status === 'loading') return;
    if (!session) router.push('/login');
  }, [session, status, router]);

  if (status === 'loading' || !session) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
      </div>
    );
  }

  const user = session.user as any;
  const initials = (user?.name || user?.email || 'U')
    .split(' ')
    .map((s: string) => s[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      {/* ── Sidebar ──────────────────────────────────────────────────── */}
      <aside
        className={`
          flex flex-col shrink-0 h-full border-r border-border
          bg-card transition-all duration-300
          ${collapsed ? 'w-16' : 'w-56'}
        `}
      >
        {/* Logo */}
        <div className={`flex items-center h-14 border-b border-border px-4 ${collapsed ? 'justify-center' : 'gap-2'}`}>
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground font-bold text-sm shrink-0">
            G
          </div>
          {!collapsed && (
            <span className="font-semibold text-base tracking-tight text-foreground">GenIOS</span>
          )}
        </div>

        {/* Nav Items */}
        <nav className="flex-1 py-4 space-y-1 px-2">
          {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
            const isActive = pathname === href || (href !== '/dashboard' && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                title={collapsed ? label : undefined}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                  transition-colors duration-150
                  ${isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground'}
                  ${collapsed ? 'justify-center' : ''}
                `}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span>{label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Collapse toggle */}
        <div className="border-t border-border p-2">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="w-full flex items-center justify-center p-2 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>
      </aside>

      {/* ── Main Column ───────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">

        {/* ── Topbar ─────────────────────────────────────────────────── */}
        <header className="flex items-center justify-between h-14 px-6 border-b border-border bg-card shrink-0">
          {/* Org name */}
          <div className="text-sm font-medium text-muted-foreground truncate">
            {(user?.org_name || user?.email || 'My Organization')}
          </div>

          {/* Right controls */}
          <div className="flex items-center gap-3">
            {/* Dark/Light toggle */}
            {mounted && (
              <button
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="p-2 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                title="Toggle theme"
              >
                {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
            )}

            {/* Avatar */}
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-xs font-bold text-primary-foreground">
                {initials}
              </div>
              <span className="text-sm font-medium text-foreground hidden sm:block truncate max-w-[120px]">
                {user?.name || user?.email}
              </span>
            </div>

            {/* Logout */}
            <button
              onClick={() => signOut({ callbackUrl: '/login' })}
              className="p-2 rounded-lg text-muted-foreground hover:bg-accent hover:text-destructive transition-colors"
              title="Logout"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* ── Page Content ───────────────────────────────────────────── */}
        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>

      {/* Mr. Elite Chatbot — available on all dashboard pages */}
      <MrEliteChatbot />
    </div>
  );
}
