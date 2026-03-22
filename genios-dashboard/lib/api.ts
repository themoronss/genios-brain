import { ContextBundle, GraphData, ConnectionStatus, DraftResponse, DashboardMetrics, ActivityEvent } from '@/types';

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
    throw new Error((data as any).detail || (data as ApiError).error || 'API request failed');
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
      apiCall<ConnectionStatus>(`/api/org/${orgId}/status`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    getGraph: (orgId: string, token: string, queryString: string = '') =>
      apiCall<GraphData>(`/api/org/${orgId}/graph${queryString}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    getContacts: (orgId: string, token: string, limit = 100, offset = 0) =>
      apiCall(`/api/org/${orgId}/contacts?limit=${limit}&offset=${offset}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    getApiKey: (orgId: string, token: string) =>
      apiCall<{api_key: string}>(`/api/org/${orgId}/apikey`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    regenerateApiKey: (orgId: string, token: string) =>
      apiCall<{api_key: string}>(`/api/org/${orgId}/apikey/regenerate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }),
    resetData: (orgId: string, token: string) =>
      apiCall(`/api/org/${orgId}/reset`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }),
  },
  context: {
    getBundle: (orgId: string, entityName: string, token: string) =>
      apiCall<ContextBundle>(`/api/org/${orgId}/context`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ entity_name: entityName }),
      }),
  },
  draft: {
    generate: (orgId: string, entityName: string, userRequest: string, token: string) =>
      apiCall<DraftResponse>('/api/generate/draft', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          org_id: orgId,
          entity_name: entityName,
          user_request: userRequest,
          draft_type: 'email'
        }),
      }),
  },
  dashboard: {
    getMetrics: (orgId: string, token: string) =>
      apiCall<DashboardMetrics>(`/dashboard/metrics?org_id=${orgId}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
  },
  activity: {
    getFeed: (orgId: string, token: string, limit = 20) =>
      apiCall<{ events: ActivityEvent[] }>(`/activity?org_id=${orgId}&limit=${limit}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
  },
  graph: {
    getStats: (orgId: string, token: string) =>
      apiCall<any>(`/v1/graph/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    exportCsv: (orgId: string) => {
      window.open(`${API_BASE}/api/org/${orgId}/graph/export`, '_blank');
    },
  },
  chat: {
    send: (orgId: string, message: string, queryType: string, history: { role: string; content: string }[]) =>
      apiCall<{ reply: string; query_type: string; context_used: boolean; entity_resolved: string | null }>(
        `/api/org/${orgId}/chat`,
        {
          method: 'POST',
          body: JSON.stringify({ message, query_type: queryType, history }),
        }
      ),
  },
  facts: {
    getOverview: (orgId: string, token: string) =>
      apiCall<any>(`/api/org/${orgId}/context/overview`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    list: (orgId: string, token: string, params?: string) =>
      apiCall<any>(`/api/org/${orgId}/facts${params ? `?${params}` : ''}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    getLifecycle: (orgId: string, token: string, limit = 50) =>
      apiCall<any>(`/api/org/${orgId}/facts/lifecycle?limit=${limit}`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
  },
  commitments: {
    list: (orgId: string, token: string) =>
      apiCall<any>(`/api/org/${orgId}/commitments`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    update: (orgId: string, commitmentId: string, data: any, token: string) =>
      apiCall<any>(`/api/org/${orgId}/commitments/${commitmentId}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify(data),
      }),
  },
  manualContext: {
    add: (orgId: string, data: any, token: string) =>
      apiCall<any>(`/api/org/${orgId}/manual-context`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify(data),
      }),
    list: (orgId: string, token: string) =>
      apiCall<any>(`/api/org/${orgId}/manual-context`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    delete: (orgId: string, entryId: string, token: string) =>
      apiCall<any>(`/api/org/${orgId}/manual-context/${entryId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }),
  },
  uploads: {
    list: (orgId: string, token: string) =>
      apiCall<any>(`/api/org/${orgId}/uploads`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    upload: async (orgId: string, file: File, tag: string, token: string) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('tag', tag);
      const res = await fetch(`${API_BASE}/api/org/${orgId}/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) throw new Error('Upload failed');
      return res.json();
    },
  },
  gmail: {
    connect: (orgId: string) => {
      window.location.href = `${API_BASE}/auth/gmail/connect?org_id=${orgId}`;
    },
    triggerSync: (orgId: string, token: string) =>
      apiCall(`/api/org/${orgId}/sync`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }),
    getSyncStatus: (orgId: string, token: string) =>
      apiCall(`/api/org/${orgId}/sync/status`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    // Update 4: Multi-account endpoints
    listAccounts: (orgId: string, token: string) =>
      apiCall<{ accounts: any[]; count: number }>(`/api/org/${orgId}/gmail/accounts`, {
        headers: { Authorization: `Bearer ${token}` },
      }),
    disconnectAccount: (orgId: string, accountEmail: string, token: string) =>
      apiCall(`/api/org/${orgId}/gmail/accounts/${encodeURIComponent(accountEmail)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }),
    syncAccount: (orgId: string, accountEmail: string, token: string) =>
      apiCall(`/api/org/${orgId}/gmail/accounts/${encodeURIComponent(accountEmail)}/sync`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }),
  },
};
