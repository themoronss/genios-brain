'use client';

import { useState, useRef, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  Upload, FileText, Users, Plus, Trash2, Check, Loader2,
  Mail, Calendar, MessageSquare, Briefcase, RefreshCcw,
  Globe, Lock,
} from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';

type Tab = 'sources' | 'upload' | 'manual';

const CONTEXT_TYPES = ['Meeting', 'Phone Call', 'WhatsApp', 'In-Person', 'Conference', 'Other'];
const FILE_TAGS = ['Meeting Notes', 'Company SOP', 'Product Docs', 'Customer Conversation', 'Investor Communication'];

export default function ResourcesPage() {
  const { data: session } = useSession();
  const qc = useQueryClient();
  const orgId = (session?.user as any)?.org_id;
  const token = (session as any)?.accessToken;
  const [activeTab, setActiveTab] = useState<Tab>('sources');

  const tabs: { value: Tab; label: string; icon: React.ElementType }[] = [
    { value: 'sources', label: 'Connected Sources', icon: Globe },
    { value: 'upload', label: 'Upload Context', icon: Upload },
    { value: 'manual', label: 'Manual Context', icon: Plus },
  ];

  return (
    <DashboardLayout title="Resources">
      {/* Tab Bar */}
      <div className="flex items-center gap-1 mb-6 border-b border-border pb-0">
        {tabs.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            onClick={() => setActiveTab(value)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px
              ${activeTab === value
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'sources' && <ConnectedSourcesTab orgId={orgId} token={token} />}
      {activeTab === 'upload' && <UploadContextTab orgId={orgId} token={token} />}
      {activeTab === 'manual' && <ManualContextTab orgId={orgId} token={token} />}
    </DashboardLayout>
  );
}


// ── Tab 1: Connected Sources ────────────────────────────────────────────

function ConnectedSourcesTab({ orgId, token }: { orgId: string; token: string }) {
  const { data: accounts } = useQuery({
    queryKey: ['gmail-accounts', orgId],
    queryFn: () => api.gmail.listAccounts(orgId, token),
    enabled: !!orgId && !!token,
  });

  const { data: status } = useQuery({
    queryKey: ['connection-status', orgId],
    queryFn: () => api.org.getStatus(orgId, token),
    enabled: !!orgId && !!token,
  });

  const syncMutation = useMutation({
    mutationFn: () => api.gmail.triggerSync(orgId, token),
  });

  const comingSoon = [
    { name: 'Slack', icon: MessageSquare, desc: 'Team conversations and channel activity' },
    { name: 'Calendar', icon: Calendar, desc: 'Meeting context and scheduling patterns' },
    { name: 'HubSpot', icon: Briefcase, desc: 'CRM data and deal pipeline' },
    { name: 'WhatsApp', icon: MessageSquare, desc: 'WhatsApp chat history import' },
  ];

  return (
    <div className="space-y-4">
      {/* Gmail — Active */}
      <div className="border border-border rounded-xl p-5 bg-card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center">
              <Mail className="w-5 h-5 text-red-500" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Gmail</h3>
              <p className="text-xs text-muted-foreground">
                {status?.gmail_connected ? 'Connected' : 'Not connected'} ·{' '}
                {status?.contacts_count || 0} contacts · {status?.interactions_count || 0} interactions
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {status?.gmail_connected && (
              <>
                <span className="text-xs text-muted-foreground">
                  {status?.last_sync ? `Last sync: ${new Date(status.last_sync).toLocaleString()}` : 'Never synced'}
                </span>
                <button
                  onClick={() => syncMutation.mutate()}
                  disabled={syncMutation.isPending || status?.sync_status === 'running'}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
                >
                  <RefreshCcw className={`w-3 h-3 ${status?.sync_status === 'running' ? 'animate-spin' : ''}`} />
                  {status?.sync_status === 'running' ? 'Syncing...' : 'Sync Now'}
                </button>
              </>
            )}
            {!status?.gmail_connected && (
              <button
                onClick={() => api.gmail.connect(orgId)}
                className="px-3 py-1.5 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
              >
                Connect Gmail
              </button>
            )}
          </div>
        </div>

        {/* Connected accounts list */}
        {accounts?.accounts && accounts.accounts.length > 0 && (
          <div className="space-y-2 mt-3 pt-3 border-t border-border">
            {accounts.accounts.map((acct: any) => (
              <div key={acct.account_email} className="flex items-center justify-between text-xs">
                <span className="text-foreground">{acct.account_email}</span>
                <span className="text-muted-foreground">
                  {acct.sync_status === 'running' ? 'Syncing...' : acct.last_synced_at ? `Synced ${new Date(acct.last_synced_at).toLocaleDateString()}` : 'Pending'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Coming Soon Sources */}
      {comingSoon.map(({ name, icon: Icon, desc }) => (
        <div key={name} className="border border-border rounded-xl p-5 bg-card opacity-60">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                <Icon className="w-5 h-5 text-muted-foreground" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">{name}</h3>
                <p className="text-xs text-muted-foreground">{desc}</p>
              </div>
            </div>
            <span className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-medium bg-muted text-muted-foreground rounded-full">
              <Lock className="w-3 h-3" /> Coming Soon
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}


// ── Tab 2: Upload Context ───────────────────────────────────────────────

function UploadContextTab({ orgId, token }: { orgId: string; token: string }) {
  const qc = useQueryClient();
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedTag, setSelectedTag] = useState('Meeting Notes');
  const [uploadResult, setUploadResult] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: uploads } = useQuery({
    queryKey: ['uploads', orgId],
    queryFn: () => api.uploads.list(orgId, token),
    enabled: !!orgId && !!token,
  });

  const handleUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0 || !orgId || !token) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const result = await api.uploads.upload(orgId, files[0], selectedTag, token);
      setUploadResult(result);
      qc.invalidateQueries({ queryKey: ['uploads'] });
    } catch (err) {
      setUploadResult({ error: 'Upload failed' });
    } finally {
      setUploading(false);
    }
  }, [orgId, token, selectedTag, qc]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  }, [handleUpload]);

  return (
    <div className="space-y-6">
      {/* Tag selector */}
      <div>
        <label className="text-xs font-medium text-muted-foreground mb-2 block">File Category</label>
        <div className="flex flex-wrap gap-2">
          {FILE_TAGS.map(tag => (
            <button
              key={tag}
              onClick={() => setSelectedTag(tag)}
              className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                selectedTag === tag
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-card text-muted-foreground border-border hover:text-foreground'
              }`}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          dragOver
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-muted-foreground/50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt,.csv"
          onChange={(e) => handleUpload(e.target.files)}
          className="hidden"
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
            <p className="text-sm text-muted-foreground">Processing file...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload className="w-8 h-8 text-muted-foreground" />
            <p className="text-sm text-foreground font-medium">Drop files here or click to upload</p>
            <p className="text-xs text-muted-foreground">PDF, DOCX, TXT, CSV — Max 10MB</p>
          </div>
        )}
      </div>

      {/* Upload result */}
      {uploadResult && (
        <div className={`border rounded-xl p-4 ${uploadResult.error ? 'border-red-500/50 bg-red-500/5' : 'border-emerald-500/50 bg-emerald-500/5'}`}>
          {uploadResult.error ? (
            <p className="text-sm text-red-500">{uploadResult.error}</p>
          ) : (
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-500" />
                {uploadResult.filename} uploaded successfully
              </p>
              <p className="text-xs text-muted-foreground">
                Status: {uploadResult.status} · Entities found: {uploadResult.entities_found} · Size: {Math.round(uploadResult.size_bytes / 1024)}KB
              </p>
            </div>
          )}
        </div>
      )}

      {/* Recent uploads */}
      {uploads?.uploads && uploads.uploads.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-foreground mb-3">Recent Uploads</h3>
          <div className="space-y-2">
            {uploads.uploads.map((u: any) => (
              <div key={u.id} className="flex items-center justify-between border border-border rounded-lg p-3 bg-card">
                <div className="flex items-center gap-3">
                  <FileText className="w-4 h-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-foreground">{u.details}</p>
                    <p className="text-[10px] text-muted-foreground">{u.uploaded_at ? new Date(u.uploaded_at).toLocaleString() : ''}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


// ── Tab 3: Manual Context ───────────────────────────────────────────────

function ManualContextTab({ orgId, token }: { orgId: string; token: string }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    contact_name: '',
    contact_email: '',
    context_type: 'Meeting',
    discussion: '',
    commitments: '',
    interaction_date: '',
  });
  const [success, setSuccess] = useState(false);

  const { data: entries } = useQuery({
    queryKey: ['manual-context', orgId],
    queryFn: () => api.manualContext.list(orgId, token),
    enabled: !!orgId && !!token,
  });

  const addMutation = useMutation({
    mutationFn: () => api.manualContext.add(orgId, form, token),
    onSuccess: () => {
      setSuccess(true);
      setForm({ contact_name: '', contact_email: '', context_type: 'Meeting', discussion: '', commitments: '', interaction_date: '' });
      qc.invalidateQueries({ queryKey: ['manual-context'] });
      setTimeout(() => setSuccess(false), 3000);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.manualContext.delete(orgId, id, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['manual-context'] }),
  });

  return (
    <div className="space-y-6">
      {/* Input form */}
      <div className="border border-border rounded-xl p-5 bg-card space-y-4">
        <h3 className="text-sm font-semibold text-foreground">Add Context Entry</h3>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Contact Name *</label>
            <input
              value={form.contact_name}
              onChange={(e) => setForm(f => ({ ...f, contact_name: e.target.value }))}
              placeholder="John Smith"
              className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Email (optional)</label>
            <input
              value={form.contact_email}
              onChange={(e) => setForm(f => ({ ...f, contact_email: e.target.value }))}
              placeholder="john@company.com"
              className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground outline-none focus:border-primary"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Context Type</label>
            <select
              value={form.context_type}
              onChange={(e) => setForm(f => ({ ...f, context_type: e.target.value }))}
              className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg text-foreground outline-none focus:border-primary"
            >
              {CONTEXT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Date of Interaction</label>
            <input
              type="date"
              value={form.interaction_date}
              onChange={(e) => setForm(f => ({ ...f, interaction_date: e.target.value }))}
              className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg text-foreground outline-none focus:border-primary"
            />
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1">What was discussed? *</label>
          <textarea
            value={form.discussion}
            onChange={(e) => setForm(f => ({ ...f, discussion: e.target.value.slice(0, 500) }))}
            placeholder="Key discussion points..."
            rows={3}
            className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground outline-none focus:border-primary resize-none"
          />
          <p className="text-[10px] text-muted-foreground text-right">{form.discussion.length}/500</p>
        </div>

        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1">Commitments made (optional)</label>
          <input
            value={form.commitments}
            onChange={(e) => setForm(f => ({ ...f, commitments: e.target.value }))}
            placeholder="E.g., Send proposal by Friday"
            className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground outline-none focus:border-primary"
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => addMutation.mutate()}
            disabled={!form.contact_name || !form.discussion || addMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
          >
            {addMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Add Context
          </button>
          {success && (
            <span className="flex items-center gap-1 text-xs text-emerald-500">
              <Check className="w-3 h-3" /> Saved with authority 1.0
            </span>
          )}
        </div>
      </div>

      {/* Recent entries */}
      {entries?.entries && entries.entries.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-foreground mb-3">Recent Manual Entries</h3>
          <div className="space-y-2">
            {entries.entries.map((entry: any) => (
              <div key={entry.id} className="flex items-start justify-between border border-border rounded-lg p-4 bg-card">
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <Users className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">{entry.contact_name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 bg-muted text-muted-foreground rounded">{entry.context_type}</span>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2">{entry.discussion}</p>
                  <p className="text-[10px] text-muted-foreground">{entry.date ? new Date(entry.date).toLocaleDateString() : ''}</p>
                </div>
                <button
                  onClick={() => deleteMutation.mutate(entry.id)}
                  className="p-1.5 text-muted-foreground hover:text-red-500 transition-colors shrink-0"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
