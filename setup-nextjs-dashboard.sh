#!/bin/bash

#############################################################################
#
# GeniOS Context Brain - Week 4 Dashboard Setup Script
#
# This script creates a complete Next.js dashboard from scratch
# Compatible with FastAPI backend at http://localhost:8000
#
# Usage: bash setup-nextjs-dashboard.sh
#
#############################################################################

set -e  # Exit on error

echo "🚀 GeniOS Context Brain - Week 4 Dashboard Setup"
echo "================================================"
echo ""

# Configuration
PROJECT_NAME="genios-dashboard"
BACKEND_URL="http://localhost:8000"

# Check if project already exists
if [ -d "$PROJECT_NAME" ]; then
    echo "❌ Directory '$PROJECT_NAME' already exists!"
    echo "   Please remove it first: rm -rf $PROJECT_NAME"
    exit 1
fi

echo "📦 Step 1/10: Creating Next.js project..."
npx create-next-app@latest $PROJECT_NAME --typescript --tailwind --eslint --app --no-src-dir --import-alias "@/*" --use-npm --yes

cd $PROJECT_NAME

echo "✅ Next.js project created"
echo ""

echo "📦 Step 2/10: Installing dependencies..."
npm install next-auth@4.24.5 --legacy-peer-deps
npm install react-force-graph-2d --legacy-peer-deps
npm install @tanstack/react-query --legacy-peer-deps
npm install lucide-react --legacy-peer-deps
npm install class-variance-authority clsx tailwind-merge --legacy-peer-deps
npm install @radix-ui/react-slot @radix-ui/react-tooltip @radix-ui/react-dialog --legacy-peer-deps
npm install date-fns --legacy-peer-deps
echo "✅ Dependencies installed"
echo ""

echo "📦 Step 3/10: Setting up environment..."
cat > .env.local <<'ENV'
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=genios-secret-key-replace-in-production
ENV
echo "✅ Environment variables created"
echo ""

echo "📦 Step 4/10: Creating TypeScript types..."
mkdir -p types
cat > types/index.ts <<'TYPES'
export interface User {
  id: string;
  org_id: string;
  email: string;
  name: string;
  token?: string;
}

export interface Contact {
  id: string;
  name: string;
  email: string;
  company: string | null;
  relationship_stage: 'ACTIVE' | 'WARM' | 'DORMANT' | 'COLD' | 'AT_RISK';
  last_interaction_at: string;
  interaction_count: number;
  sentiment_avg: number;
}

export interface GraphNode {
  id: string;
  name: string;
  company: string | null;
  relationship_stage: string;
  last_interaction_days: number;
  sentiment_avg: number;
  interaction_count: number;
  email: string;
}

export interface GraphLink {
  source: string;
  target: string;
  strength: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface EntityDetails {
  name: string;
  company: string | null;
  relationship_stage: string;
  last_interaction: string;
  sentiment_trend: string;
  communication_style: string;
  topics_of_interest: string[];
  open_commitments: string[];
  interaction_count: number;
}

export interface ContextBundle {
  entity: EntityDetails | null;
  context_for_agent: string;
  confidence: number;
  error?: string;
}

export interface ConnectionStatus {
  gmail_connected: boolean;
  last_sync: string | null;
  contacts_count: number;
  interactions_count: number;
  ingestion_complete: boolean;
  ingestion_progress: number;
}
TYPES
echo "✅ TypeScript types created"
echo ""

echo "📦 Step 5/10: Creating API client..."
mkdir -p lib
cat > lib/api.ts <<'API'
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ApiError {
  error: string;
}

async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error((data as ApiError).error || 'API request failed');
  }

  return data as T;
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      apiCall('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    register: (name: string, email: string, password: string) =>
      apiCall('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ name, email, password }),
      }),
  },
  org: {
    getStatus: (orgId: string, token: string) =>
      apiCall(`/api/org/${orgId}/status`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    getGraph: (orgId: string, token: string) =>
      apiCall(`/api/org/${orgId}/graph`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    getContacts: (orgId: string, token: string, limit = 100, offset = 0) =>
      apiCall(`/api/org/${orgId}/contacts?limit=${limit}&offset=${offset}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
  },
  context: {
    getBundle: (orgId: string, entityName: string, token: string) =>
      apiCall('/v1/context', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ org_id: orgId, entity_name: entityName }),
      }),
  },
  gmail: {
    connect: (orgId: string) => {
      window.location.href = `${API_BASE}/auth/gmail/connect?org_id=${orgId}`;
    },
  },
};
API

cat > lib/utils.ts <<'UTILS'
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getStageColor(stage: string): string {
  switch (stage.toUpperCase()) {
    case 'ACTIVE':
      return '#10b981'; // green-500
    case 'WARM':
      return '#f59e0b'; // amber-500
    case 'DORMANT':
      return '#f97316'; // orange-500
    case 'COLD':
      return '#ef4444'; // red-500
    case 'AT_RISK':
      return '#dc2626'; // red-600
    default:
      return '#6b7280'; // gray-500
  }
}

export function getDaysAgo(dateString: string): number {
  const date = new Date(dateString);
  const now = new Date();
  const diffTime = Math.abs(now.getTime() - date.getTime());
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays;
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
UTILS
echo "✅ API client created"
echo ""

echo "📦 Step 6/10: Creating NextAuth configuration..."
cat > lib/auth.ts <<'AUTH'
import { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null;
        }

        try {
          const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password
            })
          });

          const user = await res.json();

          if (res.ok && user) {
            return {
              id: user.org_id,
              email: user.email,
              name: user.name,
              org_id: user.org_id,
              token: user.token
            };
          }
        } catch (error) {
          console.error('Auth error:', error);
        }

        return null;
      }
    })
  ],
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.org_id = (user as any).org_id;
        token.accessToken = (user as any).token;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as any).org_id = token.org_id;
        (session as any).accessToken = token.accessToken;
      }
      return session;
    }
  },
  secret: process.env.NEXTAUTH_SECRET,
};
AUTH

mkdir -p app/api/auth/\[...nextauth\]
cat > app/api/auth/\[...nextauth\]/route.ts <<'NEXTAUTH_ROUTE'
import NextAuth from "next-auth";
import { authOptions } from "@/lib/auth";

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
NEXTAUTH_ROUTE
echo "✅ NextAuth configuration created"
echo ""

echo "📦 Step 7/10: Creating UI components..."
mkdir -p components/ui

# Button component
cat > components/ui/button.tsx <<'BUTTON'
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
BUTTON

# Input component
cat > components/ui/input.tsx <<'INPUT'
import * as React from "react"
import { cn } from "@/lib/utils"

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
INPUT

# Card component
cat > components/ui/card.tsx <<'CARD'
import * as React from "react"
import { cn } from "@/lib/utils"

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border bg-card text-card-foreground shadow-sm",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "text-2xl font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"

export { Card, CardHeader, CardTitle, CardDescription, CardContent }
CARD

# Badge component
cat > components/ui/badge.tsx <<'BADGE'
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
BADGE

echo "✅ UI components created"
echo ""

echo "📦 Step 8/10: Creating relationship graph component..."
cat > components/RelationshipGraph.tsx <<'GRAPH'
'use client';

import React, { useRef, useCallback, useState } from 'react';
import dynamic from 'next/dynamic';
import { getStageColor } from '@/lib/utils';
import { GraphData, GraphNode } from '@/types';

// Dynamic import to avoid SSR issues
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
});

interface RelationshipGraphProps {
  data: GraphData;
  onNodeClick: (node: GraphNode) => void;
}

export default function RelationshipGraph({ data, onNodeClick }: RelationshipGraphProps) {
  const graphRef = useRef<any>();
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);

  const handleNodeClick = useCallback(
    (node: any) => {
      onNodeClick(node as GraphNode);
    },
    [onNodeClick]
  );

  const handleNodeHover = useCallback((node: any) => {
    setHoveredNode(node as GraphNode);
  }, []);

  const nodeCanvasObject = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.name;
    const fontSize = 12 / globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;
    const textWidth = ctx.measureText(label).width;
    const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);

    // Draw node circle
    const nodeSize = 5;
    ctx.fillStyle = getStageColor(node.relationship_stage);
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI);
    ctx.fill();

    // Draw border for hovered node
    if (hoveredNode && hoveredNode.id === node.id) {
      ctx.strokeStyle = '#000';
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    }

    // Draw label
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y + nodeSize + 2, bckgDimensions[0], bckgDimensions[1]);
    ctx.fillStyle = '#000';
    ctx.fillText(label, node.x, node.y + nodeSize + 2 + bckgDimensions[1] / 2);
  }, [hoveredNode]);

  return (
    <div className="w-full h-full">
      <ForceGraph2D
        ref={graphRef}
        graphData={data}
        nodeCanvasObject={nodeCanvasObject}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 5, 0, 2 * Math.PI);
          ctx.fill();
        }}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        linkColor={() => '#e5e7eb'}
        linkWidth={1}
        backgroundColor="#ffffff"
        cooldownTicks={100}
        onEngineStop={() => {
          if (graphRef.current) {
            graphRef.current.zoomToFit(400, 50);
          }
        }}
      />
    </div>
  );
}
GRAPH

echo "✅ Relationship graph component created"
echo ""

echo "📦 Step 9/10: Creating page components..."

# Root layout
cat > app/layout.tsx <<'LAYOUT'
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "GeniOS Context Brain",
  description: "Relationship Intelligence for Founders",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
LAYOUT

# Providers
cat > app/providers.tsx <<'PROVIDERS'
'use client';

import { SessionProvider } from 'next-auth/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000, // 1 minute
      },
    },
  }));

  return (
    <SessionProvider>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </SessionProvider>
  );
}
PROVIDERS

# Homepage (redirect to dashboard)
cat > app/page.tsx <<'HOME'
'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';

export default function Home() {
  const router = useRouter();
  const { data: session, status } = useSession();

  useEffect(() => {
    if (status === 'loading') return;
    
    if (session) {
      router.push('/dashboard');
    } else {
      router.push('/login');
    }
  }, [session, status, router]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
    </div>
  );
}
HOME

# Login page
mkdir -p app/login
cat > app/login/page.tsx <<'LOGIN'
'use client';

import { useState } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import Link from 'next/link';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await signIn('credentials', {
      email,
      password,
      redirect: false,
    });

    if (result?.error) {
      setError('Invalid email or password');
      setLoading(false);
    } else {
      router.push('/dashboard');
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-50">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">GeniOS Context Brain</CardTitle>
          <CardDescription className="text-center">
            Sign in to your account
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="text-sm font-medium">Email</label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="mt-1"
              />
            </div>
            <div>
              <label htmlFor="password" className="text-sm font-medium">Password</label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="mt-1"
              />
            </div>
            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                {error}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm">
            Don't have an account?{' '}
            <Link href="/register" className="text-indigo-600 hover:underline">
              Register
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
LOGIN

# Register page
mkdir -p app/register
cat > app/register/page.tsx <<'REGISTER'
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import Link from 'next/link';
import { api } from '@/lib/api';

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await api.auth.register(name, email, password);
      
      // Auto login after registration
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false,
      });

      if (result?.error) {
        setError('Registration successful, but login failed. Please try logging in.');
      } else {
        router.push('/dashboard/connect');
      }
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-50">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">Create Account</CardTitle>
          <CardDescription className="text-center">
            Get started with GeniOS Context Brain
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="name" className="text-sm font-medium">Full Name</label>
              <Input
                id="name"
                type="text"
                placeholder="John Doe"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="mt-1"
              />
            </div>
            <div>
              <label htmlFor="email" className="text-sm font-medium">Email</label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="mt-1"
              />
            </div>
            <div>
              <label htmlFor="password" className="text-sm font-medium">Password</label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="mt-1"
              />
            </div>
            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                {error}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Creating account...' : 'Create Account'}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm">
            Already have an account?{' '}
            <Link href="/login" className="text-indigo-600 hover:underline">
              Sign in
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
REGISTER

# Dashboard layout
mkdir -p app/dashboard
cat > app/dashboard/layout.tsx <<'DASH_LAYOUT'
'use client';

import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { signOut } from 'next-auth/react';
import { Button } from '@/components/ui/button';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === 'loading') return;
    if (!session) {
      router.push('/login');
    }
  }, [session, status, router]);

  if (status === 'loading' || !session) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-slate-900">
                GeniOS Context Brain
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-slate-600">{session.user?.name}</span>
              <Button variant="outline" size="sm" onClick={() => signOut()}>
                Logout
              </Button>
            </div>
          </div>
        </div>
      </nav>
      <main>{children}</main>
    </div>
  );
}
DASH_LAYOUT

# Connect Gmail page
mkdir -p app/dashboard/connect
cat > app/dashboard/connect/page.tsx <<'CONNECT'
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
    refetchInterval: (data) => {
      // Refetch every 2 seconds if ingestion is in progress
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
CONNECT

# Main dashboard page (graph)
cat > app/dashboard/page.tsx <<'DASHBOARD'
'use client';

import { useSession } from 'next-auth/react';
import { useQuery } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { GraphData, GraphNode, ContextBundle, ConnectionStatus } from '@/types';
import RelationshipGraph from '@/components/RelationshipGraph';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { X, Copy, Check } from 'lucide-react';
import { formatDate, getStageColor } from '@/lib/utils';

export default function DashboardPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [copied, setCopied] = useState(false);
  
  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;

  const { data: status } = useQuery<ConnectionStatus>({
    queryKey: ['connection-status', orgId],
    queryFn: () => api.org.getStatus(orgId, token),
    enabled: !!orgId && !!token,
  });

  useEffect(() => {
    if (status && !status.gmail_connected) {
      router.push('/dashboard/connect');
    }
  }, [status, router]);

  const { data: graphData, isLoading: graphLoading } = useQuery<GraphData>({
    queryKey: ['graph-data', orgId],
    queryFn: () => api.org.getGraph(orgId, token),
    enabled: !!orgId && !!token && !!status?.gmail_connected,
  });

  const { data: contextBundle, isLoading: contextLoading } = useQuery<ContextBundle>({
    queryKey: ['context', orgId, selectedNode?.name],
    queryFn: () => api.context.getBundle(orgId, selectedNode!.name, token),
    enabled: !!orgId && !!token && !!selectedNode,
  });

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
    setCopied(false);
  };

  const handleClosePanel = () => {
    setSelectedNode(null);
  };

  const handleCopyContext = () => {
    if (contextBundle?.context_for_agent) {
      navigator.clipboard.writeText(contextBundle.context_for_agent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (graphLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Loading your relationship graph...</p>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>No Contacts Yet</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600 mb-4">
              Your relationship graph is empty. Make sure Gmail sync has completed.
            </p>
            <Button onClick={() => router.push('/dashboard/connect')}>
              Check Connection Status
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const stageCounts = graphData.nodes.reduce((acc, node) => {
    acc[node.relationship_stage] = (acc[node.relationship_stage] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="h-[calc(100vh-4rem)] relative">
      {/* Header with stats */}
      <div className="absolute top-4 left-4 z-10 bg-white rounded-lg shadow-lg p-4">
        <h2 className="text-lg font-semibold mb-3">Relationship Graph</h2>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getStageColor('ACTIVE') }}></div>
            <span className="text-sm">Active ({stageCounts['ACTIVE'] || 0})</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getStageColor('WARM') }}></div>
            <span className="text-sm">Warm ({stageCounts['WARM'] || 0})</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getStageColor('DORMANT') }}></div>
            <span className="text-sm">Dormant ({stageCounts['DORMANT'] || 0})</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getStageColor('COLD') }}></div>
            <span className="text-sm">Cold ({stageCounts['COLD'] || 0})</span>
          </div>
        </div>
      </div>

      {/* Graph */}
      <RelationshipGraph data={graphData} onNodeClick={handleNodeClick} />

      {/* Detail Panel */}
      {selectedNode && (
        <div className="absolute top-0 right-0 h-full w-full md:w-96 bg-white shadow-2xl overflow-y-auto z-20 animate-in slide-in-from-right">
          <div className="sticky top-0 bg-white border-b z-10 p-4">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-semibold">{selectedNode.name}</h2>
                {selectedNode.company && (
                  <p className="text-sm text-slate-600">{selectedNode.company}</p>
                )}
              </div>
              <Button variant="ghost" size="icon" onClick={handleClosePanel}>
                <X className="h-5 w-5" />
              </Button>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <Badge
                style={{
                  backgroundColor: getStageColor(selectedNode.relationship_stage),
                  color: 'white',
                  border: 'none',
                }}
              >
                {selectedNode.relationship_stage}
              </Badge>
              <span className="text-sm text-slate-600">
                {selectedNode.interaction_count} interactions
              </span>
            </div>
          </div>

          <div className="p-4 space-y-6">
            {contextLoading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
              </div>
            ) : contextBundle ? (
              <>
                {/* Context Paragraph */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-sm uppercase text-slate-600">
                      Context Paragraph
                    </h3>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCopyContext}
                      className="h-8"
                    >
                      {copied ? (
                        <>
                          <Check className="h-3 w-3 mr-1" />
                          Copied
                        </>
                      ) : (
                        <>
                          <Copy className="h-3 w-3 mr-1" />
                          Copy
                        </>
                      )}
                    </Button>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-4 text-sm leading-relaxed">
                    {contextBundle.context_for_agent}
                  </div>
                  {contextBundle.confidence && (
                    <p className="text-xs text-slate-500 mt-2">
                      Confidence: {(contextBundle.confidence * 100).toFixed(0)}%
                    </p>
                  )}
                </div>

                {/* Entity Details */}
                {contextBundle.entity && (
                  <>
                    {contextBundle.entity.topics_of_interest.length > 0 && (
                      <div>
                        <h3 className="font-semibold text-sm uppercase text-slate-600 mb-2">
                          Topics of Interest
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {contextBundle.entity.topics_of_interest.map((topic, idx) => (
                            <Badge key={idx} variant="secondary">
                              {topic}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {contextBundle.entity.open_commitments.length > 0 && (
                      <div>
                        <h3 className="font-semibold text-sm uppercase text-slate-600 mb-2">
                          Open Commitments
                        </h3>
                        <div className="space-y-2">
                          {contextBundle.entity.open_commitments.map((commitment, idx) => (
                            <div key={idx} className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm">
                              ⚠️ {commitment}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div>
                      <h3 className="font-semibold text-sm uppercase text-slate-600 mb-2">
                        Stats
                      </h3>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-slate-600">Last interaction:</span>
                          <span className="font-medium">{contextBundle.entity.last_interaction}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-600">Sentiment trend:</span>
                          <span className="font-medium">{contextBundle.entity.sentiment_trend}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-600">Total interactions:</span>
                          <span className="font-medium">{contextBundle.entity.interaction_count}</span>
                        </div>
                        {contextBundle.entity.communication_style && (
                          <div className="flex justify-between">
                            <span className="text-slate-600">Communication style:</span>
                            <span className="font-medium">{contextBundle.entity.communication_style}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </>
            ) : (
              <div className="text-center py-8 text-slate-600">
                No context available for this contact.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
DASHBOARD

echo "✅ Page components created"
echo ""

echo "📦 Step 10/10: Updating Tailwind configuration..."
cat > tailwind.config.ts <<'TAILWIND'
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "in": {
          "0%": { transform: "translateX(100%)" },
          "100%": { transform: "translateX(0)" },
        },
      },
      animation: {
        "in": "in 0.3s ease-out",
        "slide-in-from-right": "in 0.3s ease-out",
      },
    },
  },
  plugins: [],
};
export default config;
TAILWIND

cat > app/globals.css <<'GLOBALS'
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --card: 0 0% 100%;
  --card-foreground: 222.2 84% 4.9%;
  --popover: 0 0% 100%;
  --popover-foreground: 222.2 84% 4.9%;
  --primary: 221.2 83.2% 53.3%;
  --primary-foreground: 210 40% 98%;
  --secondary: 210 40% 96.1%;
  --secondary-foreground: 222.2 47.4% 11.2%;
  --muted: 210 40% 96.1%;
  --muted-foreground: 215.4 16.3% 46.9%;
  --accent: 210 40% 96.1%;
  --accent-foreground: 222.2 47.4% 11.2%;
  --destructive: 0 84.2% 60.2%;
  --destructive-foreground: 210 40% 98%;
  --border: 214.3 31.8% 91.4%;
  --input: 214.3 31.8% 91.4%;
  --ring: 221.2 83.2% 53.3%;
  --radius: 0.5rem;
}

* {
  box-sizing: border-box;
  padding: 0;
  margin: 0;
}

html,
body {
  max-width: 100vw;
  overflow-x: hidden;
}

body {
  color: rgb(var(--foreground-rgb));
  background: rgb(var(--background-start-rgb));
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
GLOBALS

echo "✅ Tailwind configuration updated"
echo ""

echo "═══════════════════════════════════════════════════════"
echo "✨ Next.js Dashboard Setup Complete!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "📂 Project location: ./$PROJECT_NAME"
echo ""
echo "🚀 Next steps:"
echo ""
echo "1. Start the Next.js development server:"
echo "   cd $PROJECT_NAME"
echo "   npm run dev"
echo ""
echo "2. Open browser to: http://localhost:3000"
echo ""
echo "3. Make sure your FastAPI backend is running at http://localhost:8000"
echo ""
echo "📋 Backend endpoints needed (add to FastAPI):"
echo "   - POST /auth/login"
echo "   - POST /auth/register"
echo "   - GET  /api/org/{org_id}/status"
echo "   - GET  /api/org/{org_id}/graph"
echo "   - GET  /api/org/{org_id}/contacts"
echo ""
echo "   (Context endpoint /v1/context already exists!)"
echo ""
echo "📚 See WEEK4_DASHBOARD_SPEC.md for full API specifications"
echo ""
echo "═══════════════════════════════════════════════════════"
