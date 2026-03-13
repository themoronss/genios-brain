'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Copy, Check, Sparkles, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { DraftResponse } from '@/types';

interface DraftModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    entityName: string;
}

export function DraftModal({ open, onOpenChange, entityName }: DraftModalProps) {
    const { data: session } = useSession();
    const [userRequest, setUserRequest] = useState('');
    const [copied, setCopied] = useState(false);
    const [showContext, setShowContext] = useState(false);

    const orgId = (session?.user as any)?.org_id;
    const token = (session as any)?.accessToken;

    const draftMutation = useMutation<DraftResponse, Error, string>({
        mutationFn: (request: string) => api.draft.generate(orgId, entityName, request, token),
    });

    const handleGenerate = () => {
        if (userRequest.trim()) {
            draftMutation.mutate(userRequest);
        }
    };

    const handleCopy = () => {
        if (draftMutation.data?.draft) {
            navigator.clipboard.writeText(draftMutation.data.draft);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    const handleClose = () => {
        onOpenChange(false);
        // Reset state after modal close animation
        setTimeout(() => {
            setUserRequest('');
            draftMutation.reset();
            setShowContext(false);
        }, 200);
    };

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Sparkles className="h-5 w-5 text-indigo-600" />
                        Draft with AI for {entityName}
                    </DialogTitle>
                    <DialogDescription>
                        Tell the AI what you want to write, and it will draft a message using full relationship context.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* Input Section */}
                    {!draftMutation.data && (
                        <div className="space-y-2">
                            <label className="text-sm font-medium">What do you want to write?</label>
                            <Input
                                placeholder="e.g., Follow up on our last meeting about funding"
                                value={userRequest}
                                onChange={(e) => setUserRequest(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        handleGenerate();
                                    }
                                }}
                                autoFocus
                                maxLength={500}
                            />
                            <div className="flex justify-between items-center">
                                <p className="text-xs text-slate-500">
                                    Press Enter to generate. AI uses full relationship context.
                                </p>
                                <p className="text-xs text-slate-400">
                                    {userRequest.length}/500
                                </p>
                            </div>
                        </div>
                    )}

                    {/* Loading State */}
                    {draftMutation.isPending && (
                        <div className="flex items-center justify-center gap-3 py-8">
                            <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
                            <p className="text-slate-600">Drafting with relationship context...</p>
                        </div>
                    )}

                    {/* Error State */}
                    {draftMutation.isError && (
                        <div className="rounded-lg bg-red-50 border border-red-200 p-4">
                            <p className="text-sm font-semibold text-red-900 mb-1">Failed to generate draft</p>
                            <p className="text-sm text-red-700">
                                {draftMutation.error.message || 'Something went wrong. Please try again.'}
                            </p>
                            {draftMutation.error.message?.includes('404') && (
                                <p className="text-xs text-red-600 mt-2">
                                    💡 Tip: Make sure Gmail sync is complete and this contact is in your network.
                                </p>
                            )}
                            {draftMutation.error.message?.includes('503') && (
                                <p className="text-xs text-red-600 mt-2">
                                    💡 Tip: AI service is temporarily busy. Wait a few seconds and try again.
                                </p>
                            )}
                        </div>
                    )}

                    {/* Success State - Show Draft */}
                    {draftMutation.data && (
                        <div className="space-y-4">
                            {/* Confidence Badge */}
                            <div className="flex items-center justify-between">
                                <Badge variant="secondary">
                                    {Math.round(draftMutation.data.confidence * 100)}% Context Confidence
                                </Badge>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setShowContext(!showContext)}
                                >
                                    {showContext ? 'Hide' : 'Show'} Context Used
                                </Button>
                            </div>

                            {/* Low Confidence Warning */}
                            {draftMutation.data.confidence < 0.5 && (
                                <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-3">
                                    <p className="text-xs font-semibold text-yellow-900 mb-1">⚠️ Low Confidence Draft</p>
                                    <p className="text-xs text-yellow-700">
                                        Limited relationship data available. Review carefully before sending.
                                    </p>
                                </div>
                            )}

                            {/* Context Used (collapsible) */}
                            {showContext && (
                                <div className="rounded-lg bg-slate-50 border border-slate-200 p-3">
                                    <p className="text-xs font-medium text-slate-700 mb-2">Context given to AI:</p>
                                    <p className="text-xs text-slate-600 whitespace-pre-wrap">
                                        {draftMutation.data.context_used}
                                    </p>
                                </div>
                            )}

                            {/* Generated Draft */}
                            <div className="rounded-lg bg-white border-2 border-indigo-200 p-4">
                                <p className="text-sm font-medium text-slate-700 mb-2">Generated Draft:</p>
                                <div className="prose prose-sm max-w-none">
                                    <p className="text-slate-900 whitespace-pre-wrap leading-relaxed">
                                        {draftMutation.data.draft}
                                    </p>
                                </div>
                            </div>

                            {/* Action Buttons */}
                            <div className="flex gap-2">
                                <Button onClick={handleCopy} className="flex-1 gap-2">
                                    {copied ? (
                                        <>
                                            <Check className="h-4 w-4" />
                                            Copied!
                                        </>
                                    ) : (
                                        <>
                                            <Copy className="h-4 w-4" />
                                            Copy Draft
                                        </>
                                    )}
                                </Button>
                                <Button
                                    variant="outline"
                                    onClick={() => {
                                        draftMutation.reset();
                                        setUserRequest('');
                                    }}
                                >
                                    Generate Another
                                </Button>
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter>
                    {!draftMutation.data && (
                        <>
                            <Button variant="outline" onClick={handleClose}>
                                Cancel
                            </Button>
                            <Button
                                onClick={handleGenerate}
                                disabled={!userRequest.trim() || draftMutation.isPending}
                                className="gap-2"
                            >
                                <Sparkles className="h-4 w-4" />
                                Generate Draft
                            </Button>
                        </>
                    )}
                    {draftMutation.data && (
                        <Button variant="outline" onClick={handleClose}>
                            Close
                        </Button>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
