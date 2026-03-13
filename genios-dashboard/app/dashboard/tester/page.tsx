'use client';

import { useSession } from 'next-auth/react';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Copy, Check, Search, Network } from 'lucide-react';
import { api } from '@/lib/api';
import { ContextBundle } from '@/types';

export default function ContextTesterPage() {
    const { data: session } = useSession();
    const [contactName, setContactName] = useState('');
    const [copied, setCopied] = useState(false);
    const [searchSubmitted, setSearchSubmitted] = useState(false);

    const orgId = (session?.user as any)?.org_id;
    const token = (session as any)?.accessToken;

    // Only fetch if we have a name and form was submitted
    const { data: contextBundle, isLoading, error } = useQuery<ContextBundle>({
        queryKey: ['context-tester', orgId, contactName],
        queryFn: () => api.context.getBundle(orgId, contactName, token),
        enabled: !!orgId && !!token && searchSubmitted && contactName.length > 0,
    });

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (contactName.trim()) {
            setSearchSubmitted(true);
        }
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setContactName(e.target.value);
        // Reset so it doesn't auto-fetch on every keystroke
        if (searchSubmitted) setSearchSubmitted(false);
    };

    const handleCopyContext = () => {
        if (contextBundle?.context_for_agent) {
            navigator.clipboard.writeText(contextBundle.context_for_agent);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    return (
        <div className="flex flex-col min-h-[calc(100vh-4rem)]">
            {/* Tab Navigation */}
            <div className="bg-white border-b border-slate-200 px-6 py-3 flex gap-4">
                <Link
                    href="/dashboard"
                    className="px-4 py-2 font-medium text-slate-600 hover:text-slate-900 border-b-2 border-transparent hover:border-slate-200 transition"
                >
                    <Network className="h-4 w-4 inline mr-2" />
                    Relationship Graph
                </Link>
                <button className="px-4 py-2 font-medium text-slate-900 border-b-2 border-indigo-600">
                    <Search className="h-4 w-4 inline mr-2" />
                    Context Tester
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 p-8 max-w-4xl mx-auto w-full">
                <div className="mb-8">
                    <h1 className="text-3xl font-bold text-slate-900 mb-2">Context Tester</h1>
                    <p className="text-slate-600">
                        Ask about anyone in your network and see exactly what the AI agent would know about them.
                        This is the intelligence your agent will use to draft smarter, more personalized messages.
                    </p>
                </div>

                {/* Search Form */}
                <Card className="mb-8">
                    <CardHeader>
                        <CardTitle className="text-lg">Search Contact</CardTitle>
                        <CardDescription>Type a contact name to see their complete relationship context</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSearch} className="flex gap-2">
                            <Input
                                placeholder="Enter contact name (e.g., Sarah Chen, Raj Mehta)"
                                value={contactName}
                                onChange={handleInputChange}
                                className="flex-1"
                                autoFocus
                            />
                            <Button
                                type="submit"
                                disabled={!contactName.trim() || isLoading}
                                className="gap-2"
                            >
                                <Search className="h-4 w-4" />
                                {isLoading ? 'Searching...' : 'Search'}
                            </Button>
                        </form>
                    </CardContent>
                </Card>

                {/* Not Found State */}
                {error && searchSubmitted && (
                    <Card className="mb-8 border-slate-200 bg-slate-50">
                        <CardContent className="pt-8 pb-8 text-center">
                            <p className="text-4xl mb-3">🔍</p>
                            <p className="text-slate-700 font-medium">
                                No contact found for &quot;{contactName}&quot;
                            </p>
                            <p className="text-slate-500 text-sm mt-1">
                                {error instanceof Error ? error.message : 'Try a different name or spelling.'}
                            </p>
                            <p className="text-slate-400 text-xs mt-3">
                                Tip: Try a partial name — fuzzy matching will find the closest match.
                            </p>
                        </CardContent>
                    </Card>
                )}

                {/* Loading State */}
                {isLoading && (
                    <Card className="mb-8">
                        <CardContent className="pt-6">
                            <div className="flex items-center justify-center gap-3">
                                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
                                <p className="text-slate-600">Loading context...</p>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Results */}
                {!isLoading && searchSubmitted && contextBundle && (
                    <>
                        {/* Entity Info Card */}
                        {contextBundle.entity && (
                            <Card className="mb-6">
                                <CardHeader>
                                    <div className="flex items-start justify-between">
                                        <div>
                                            <CardTitle className="text-2xl">{contextBundle.entity.name}</CardTitle>
                                            <CardDescription className="mt-1">
                                                {contextBundle.entity.company && `${contextBundle.entity.company} • `}
                                                Relationship: <Badge className="ml-1">
                                                    {contextBundle.entity.relationship_stage}
                                                </Badge>
                                            </CardDescription>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-2xl font-bold text-indigo-600">
                                                {Math.round((contextBundle.confidence || 0) * 100)}%
                                            </p>
                                            <p className="text-xs text-slate-500">Confidence</p>
                                        </div>
                                    </div>
                                </CardHeader>
                            </Card>
                        )}

                        {/* Context for Agent Card - THE KEY CARD */}
                        <Card className="mb-6 border-indigo-200 bg-indigo-50">
                            <CardHeader>
                                <CardTitle className="text-lg text-indigo-900">Context for AI Agent</CardTitle>
                                <CardDescription className="text-indigo-700">
                                    This is exactly what your AI agent will see when drafting any message{contextBundle.entity && ` about ${contextBundle.entity.name}`}
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="bg-white rounded-lg p-4 border border-indigo-100 mb-4">
                                    <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">
                                        {contextBundle.context_for_agent}
                                    </p>
                                </div>
                                <Button
                                    onClick={handleCopyContext}
                                    variant="outline"
                                    className="w-full gap-2"
                                >
                                    {copied ? (
                                        <>
                                            <Check className="h-4 w-4 text-green-600" />
                                            Copied to clipboard!
                                        </>
                                    ) : (
                                        <>
                                            <Copy className="h-4 w-4" />
                                            Copy Context
                                        </>
                                    )}
                                </Button>
                            </CardContent>
                        </Card>

                        {/* Entity Details Grid */}
                        {contextBundle.entity && (
                            <Card className="mb-6">
                                <CardHeader>
                                    <CardTitle className="text-lg">Relationship Details</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        <div>
                                            <p className="text-xs text-slate-500 uppercase tracking-wide">Last Contact</p>
                                            <p className="text-lg font-semibold text-slate-900">
                                                {contextBundle.entity.last_interaction}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-slate-500 uppercase tracking-wide">Sentiment</p>
                                            <p className="text-lg font-semibold">
                                                {typeof contextBundle.entity.sentiment_trend === 'number'
                                                    ? (contextBundle.entity.sentiment_trend > 0 ? '😊' : '😐') + ` ${contextBundle.entity.sentiment_trend.toFixed(2)}`
                                                    : contextBundle.entity.sentiment_trend
                                                }
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-slate-500 uppercase tracking-wide">Interactions</p>
                                            <p className="text-lg font-semibold text-slate-900">
                                                {contextBundle.entity.interaction_count || 0}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-slate-500 uppercase tracking-wide">Open Items</p>
                                            <p className="text-lg font-semibold text-slate-900">
                                                {contextBundle.entity.open_commitments || 0}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Communication Style Card */}
                        {contextBundle.entity && contextBundle.entity.communication_style && (
                            <Card className="mb-6">
                                <CardHeader>
                                    <CardTitle className="text-lg">Communication Style</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-slate-700 flex items-start gap-2">
                                        💬
                                        <span>{contextBundle.entity.communication_style}</span>
                                    </p>
                                </CardContent>
                            </Card>
                        )}

                        {/* Topics & Commitments Grid */}
                        {contextBundle.entity && (
                            <div className="grid md:grid-cols-2 gap-6">
                                {/* Topics */}
                                {contextBundle.entity.topics_of_interest && contextBundle.entity.topics_of_interest.length > 0 && (
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="text-lg">Topics of Interest</CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="flex flex-wrap gap-2">
                                                {contextBundle.entity.topics_of_interest.map((topic) => (
                                                    <Badge key={topic} variant="secondary">
                                                        {topic}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </CardContent>
                                    </Card>
                                )}

                                {/* What Works */}
                                {contextBundle.entity.what_works && (
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="text-lg">What Works</CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <p className="text-slate-700">✅ {contextBundle.entity.what_works}</p>
                                        </CardContent>
                                    </Card>
                                )}
                            </div>
                        )}

                        {/* What to Avoid */}
                        {contextBundle.entity && contextBundle.entity.what_to_avoid && (
                            <Card className="mt-6 border-red-200 bg-red-50">
                                <CardHeader>
                                    <CardTitle className="text-lg text-red-900">What to Avoid</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-red-700">❌ {contextBundle.entity.what_to_avoid}</p>
                                </CardContent>
                            </Card>
                        )}

                        {/* Recommended Action */}
                        {contextBundle.entity && contextBundle.entity.recommended_action && (
                            <Card className="mt-6 border-green-200 bg-green-50">
                                <CardHeader>
                                    <CardTitle className="text-lg text-green-900">Recommended Next Step</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-green-700">🎯 {contextBundle.entity.recommended_action}</p>
                                </CardContent>
                            </Card>
                        )}
                    </>
                )}

                {/* Empty State */}
                {!isLoading && !searchSubmitted && (
                    <Card className="text-center py-12">
                        <CardContent>
                            <div className="text-slate-400 mb-4">🔍</div>
                            <p className="text-slate-600">
                                Search for a contact to see what your AI agent knows about them
                            </p>
                        </CardContent>
                    </Card>
                )}
            </div>
        </div>
    );
}
