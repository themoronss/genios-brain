/**
 * @genios/sdk 1.0 — Official Node.js SDK for the GeniOS Context API
 *
 * Features added in 1.0 (Phase 5.6):
 *   - Retries with exp backoff on 5xx / 429 (250ms, 1s, 4s)
 *   - idempotencyKey option on feedback() / outcome()
 *   - verifyWebhookSignature() static helper
 *   - Async SSE iterable: client.stream.recommendations(...)
 *
 * Usage:
 *   import { GeniOS } from '@genios/sdk';
 *   const client = new GeniOS({ apiKey: 'gn_live_...' });
 *   const bundle = await client.context('John Smith', 'about to close a deal');
 */

import crypto from 'crypto';

const DEFAULT_BASE_URL = 'https://squid-app-2zuqf.ondigitalocean.app';
const DEFAULT_TIMEOUT_MS = 10_000;
const RETRY_BACKOFF_MS = [250, 1_000, 4_000];

export class GeniOSError extends Error {
  constructor(message: string, public status?: number) { super(message); this.name = 'GeniOSError'; }
}

export interface GeniOSOptions {
  apiKey?: string;
  baseUrl?: string;
  timeoutMs?: number;
}

export interface ContextOptions {
  agentId?: string;
  segmentId?: string;
  contextSize?: 'short' | 'medium' | 'long';
}

export interface FeedbackOptions {
  notes?: string;
  idempotencyKey?: string;
}

export interface OutcomeOptions {
  signals?: Record<string, unknown>;
  idempotencyKey?: string;
}

export interface StreamOptions {
  minPriority?: number;
  signal?: AbortSignal;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));


export interface ScopePolicy {
  connectors?:     string[] | null;
  segments?:       string[] | null;
  fact_types?:     string[] | null;
  exclude_tags?:   string[];
  max_age_days?:   number;
  min_confidence?: number;
}

class AgentsNamespace {
  constructor(private readonly client: GeniOS) {}

  // Legacy 1.x — keep
  async register(name: string, description = ''): Promise<Record<string, unknown>> {
    return this.client['_post']('/v1/agent', { agent_id: name, name: description || name });
  }

  /** Register an agent + scope policy. Server returns a new bearer key bound to it. */
  async create(input: {
    agentId: string;
    name?: string;
    description?: string;
    scope?: ScopePolicy;
  }): Promise<Record<string, unknown>> {
    return this.client['_post']('/v1/agents', {
      agent_id: input.agentId,
      name: input.name,
      description: input.description,
      scope: input.scope,
    });
  }

  async list(): Promise<Record<string, unknown>> {
    return this.client['_get']('/v1/agents');
  }

  async get(agentId: string): Promise<Record<string, unknown>> {
    return this.client['_get'](`/v1/agents/${encodeURIComponent(agentId)}`);
  }

  /** Server-derived identity for this client's bearer key. */
  async whoami(): Promise<Record<string, unknown>> {
    return this.client['_get']('/v1/agents/me');
  }

  async editScope(agentId: string, scope: ScopePolicy): Promise<Record<string, unknown>> {
    return this.client['_request']('PATCH', `/v1/agents/${encodeURIComponent(agentId)}/scope`, { scope });
  }

  async rotateKey(agentId: string, opts?: { name?: string; revokeOld?: boolean }): Promise<Record<string, unknown>> {
    return this.client['_post'](
      `/v1/agents/${encodeURIComponent(agentId)}/keys`,
      { name: opts?.name, revoke_old: opts?.revokeOld ?? false },
    );
  }

  async archive(agentId: string): Promise<Record<string, unknown>> {
    return this.client['_request']('DELETE', `/v1/agents/${encodeURIComponent(agentId)}`);
  }

  async audit(agentId: string, limit = 50): Promise<Record<string, unknown>> {
    return this.client['_get'](`/v1/agents/${encodeURIComponent(agentId)}/audit`, { limit: String(limit) });
  }

  // Per-agent connectors (Phase 6 — Inkbox / custom integrations)
  async listConnectors(agentId: string): Promise<Record<string, unknown>> {
    return this.client['_get'](`/v1/agents/${encodeURIComponent(agentId)}/connectors`);
  }

  async addConnector(
    agentId: string,
    source: string,
    metadata: Record<string, unknown> = {},
  ): Promise<Record<string, unknown>> {
    return this.client['_post'](
      `/v1/agents/${encodeURIComponent(agentId)}/connectors`,
      { source, metadata },
    );
  }

  async removeConnector(agentId: string, connectorId: string): Promise<Record<string, unknown>> {
    return this.client['_request'](
      'DELETE',
      `/v1/agents/${encodeURIComponent(agentId)}/connectors/${encodeURIComponent(connectorId)}`,
    );
  }

  // Per-agent trust list (Phase 6.5)
  async listTrust(agentId: string): Promise<Record<string, unknown>> {
    return this.client['_get'](`/v1/agents/${encodeURIComponent(agentId)}/trust`);
  }

  async addTrust(
    agentId: string,
    input: { contactId?: string; matchEmail?: string; matchPhone?: string; note?: string },
  ): Promise<Record<string, unknown>> {
    const body: Record<string, unknown> = { note: input.note };
    if (input.contactId)  body.contact_id  = input.contactId;
    if (input.matchEmail) body.match_email = input.matchEmail;
    if (input.matchPhone) body.match_phone = input.matchPhone;
    return this.client['_post'](`/v1/agents/${encodeURIComponent(agentId)}/trust`, body);
  }

  async removeTrust(agentId: string, trustId: string): Promise<Record<string, unknown>> {
    return this.client['_request'](
      'DELETE',
      `/v1/agents/${encodeURIComponent(agentId)}/trust/${encodeURIComponent(trustId)}`,
    );
  }
}


export interface IngestEmailInput {
  externalId: string;
  fromAddress: string;
  to: string[];
  sentAt: string;
  subject?: string;
  bodyText?: string;
  bodyHtml?: string;
  direction?: 'inbound' | 'outbound';
  inReplyToExternalId?: string;
  threadExternalId?: string;
}

export interface IngestCallInput {
  externalId: string;
  fromNumber: string;
  toNumber: string;
  startedAt: string;
  durationSec?: number;
  transcript?: string;
  direction?: 'inbound' | 'outbound';
}

export interface IngestSmsInput {
  externalId: string;
  fromNumber: string;
  toNumber: string;
  body: string;
  sentAt: string;
  direction?: 'inbound' | 'outbound';
}

class IngestNamespace {
  constructor(private readonly client: GeniOS) {}

  async email(input: IngestEmailInput): Promise<Record<string, unknown>> {
    const payload: Record<string, unknown> = {
      external_id: input.externalId,
      from_address: input.fromAddress,
      to: input.to,
      sent_at: input.sentAt,
      direction: input.direction ?? 'inbound',
    };
    if (input.subject !== undefined) payload.subject = input.subject;
    if (input.bodyText !== undefined) payload.body_text = input.bodyText;
    if (input.bodyHtml !== undefined) payload.body_html = input.bodyHtml;
    if (input.inReplyToExternalId !== undefined) payload.in_reply_to_external_id = input.inReplyToExternalId;
    if (input.threadExternalId !== undefined) payload.thread_external_id = input.threadExternalId;
    return this.client['_post']('/v1/ingest/email', payload);
  }

  async call(input: IngestCallInput): Promise<Record<string, unknown>> {
    const payload: Record<string, unknown> = {
      external_id: input.externalId,
      from_number: input.fromNumber,
      to_number: input.toNumber,
      started_at: input.startedAt,
      duration_sec: input.durationSec ?? 0,
      direction: input.direction ?? 'inbound',
    };
    if (input.transcript !== undefined) payload.transcript = input.transcript;
    return this.client['_post']('/v1/ingest/call', payload);
  }

  async sms(input: IngestSmsInput): Promise<Record<string, unknown>> {
    return this.client['_post']('/v1/ingest/sms', {
      external_id: input.externalId,
      from_number: input.fromNumber,
      to_number: input.toNumber,
      body: input.body,
      sent_at: input.sentAt,
      direction: input.direction ?? 'inbound',
    });
  }

  async events(limit = 50): Promise<Record<string, unknown>> {
    return this.client['_get']('/v1/ingest/events', { limit: String(limit) });
  }
}


class StreamNamespace {
  constructor(private readonly client: GeniOS) {}

  /** Async iterable of recommendation events (SSE). */
  async *recommendations(opts: StreamOptions = {}): AsyncIterable<Record<string, unknown>> {
    const url = new URL(`${this.client['baseUrl']}/v1/stream/recommendations`);
    url.searchParams.set('min_priority', String(opts.minPriority ?? 0.6));

    const res = await fetch(url.toString(), {
      headers: {
        Authorization: `Bearer ${this.client['apiKey']}`,
        Accept: 'text/event-stream',
      },
      signal: opts.signal,
    });
    if (!res.ok || !res.body) throw new GeniOSError(`SSE connect failed: ${res.status}`, res.status);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    let event: string | null = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) return;
      buf += decoder.decode(value, { stream: true });

      let idx: number;
      while ((idx = buf.indexOf('\n')) !== -1) {
        const line = buf.slice(0, idx).trimEnd();
        buf = buf.slice(idx + 1);

        if (line === '') { event = null; continue; }
        if (line.startsWith(':')) continue;         // heartbeat
        if (line.startsWith('event:')) { event = line.slice(6).trim(); continue; }
        if (line.startsWith('data:')) {
          const data = line.slice(5).trim();
          if (!data || event === 'ping') continue;
          try {
            yield JSON.parse(data) as Record<string, unknown>;
          } catch { /* bad frame, skip */ }
        }
      }
    }
  }
}


export class GeniOS {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  public readonly agents: AgentsNamespace;
  public readonly ingest: IngestNamespace;
  public readonly stream: StreamNamespace;

  constructor(options: GeniOSOptions = {}) {
    this.apiKey = options.apiKey ?? process.env.GENIOS_API_KEY ?? '';
    if (!this.apiKey) {
      throw new Error('apiKey is required. Pass it in options or set GENIOS_API_KEY env var.');
    }
    this.baseUrl = (options.baseUrl ?? process.env.GENIOS_BASE_URL ?? DEFAULT_BASE_URL).replace(/\/$/, '');
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.agents = new AgentsNamespace(this);
    this.ingest = new IngestNamespace(this);
    this.stream = new StreamNamespace(this);
  }

  // ── Public methods ──────────────────────────────────────────────────────

  async context(entity: string, situation: string, options: ContextOptions = {}): Promise<Record<string, unknown>> {
    return this._post('/v1/context', {
      entity, situation,
      ...(options.agentId && { agent_id: options.agentId }),
      ...(options.segmentId && { segment_id: options.segmentId }),
      ...(options.contextSize && { context_size: options.contextSize }),
    });
  }

  async feedback(
    recommendationId: string,
    outcome: 'acted' | 'dismissed' | 'ignored',
    options: FeedbackOptions = {},
  ): Promise<Record<string, unknown>> {
    return this._post('/v1/feedback',
      { recommendation_id: recommendationId, outcome, ...(options.notes && { notes: options.notes }) },
      options.idempotencyKey,
    );
  }

  /** DEPRECATED — prefer feedback(). Server returns a Sunset header. */
  async outcome(contextId: string, outcome: string, options: OutcomeOptions = {}): Promise<Record<string, unknown>> {
    return this._post('/v1/outcome',
      { context_id: contextId, outcome, ...(options.signals && { signals: options.signals }) },
      options.idempotencyKey,
    );
  }

  async org(): Promise<Record<string, unknown>> { return this._get('/v1/org'); }
  async syncStatus(): Promise<Record<string, unknown>> { return this._get('/v1/sync'); }

  /** Constant-time HMAC-SHA256 check against X-Genios-Signature header. */
  static verifyWebhookSignature(secret: string, body: string | Buffer, signature: string): boolean {
    const buf = Buffer.isBuffer(body) ? body : Buffer.from(body);
    const expected = crypto.createHmac('sha256', secret).update(buf).digest('hex');
    try {
      return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature || ''));
    } catch {
      return false;
    }
  }

  // ── HTTP with retries ──────────────────────────────────────────────────

  private headers(extra?: Record<string, string>): Record<string, string> {
    return {
      Authorization: `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
      ...(extra ?? {}),
    };
  }

  private async _post(path: string, body: unknown, idempotencyKey?: string): Promise<Record<string, unknown>> {
    return this._request('POST', path, body, undefined, idempotencyKey);
  }

  private async _get(path: string, params?: Record<string, string>): Promise<Record<string, unknown>> {
    return this._request('GET', path, undefined, params);
  }

  private async _request(
    method: string,
    path: string,
    body?: unknown,
    params?: Record<string, string>,
    idempotencyKey?: string,
  ): Promise<Record<string, unknown>> {
    const url = new URL(`${this.baseUrl}${path}`);
    if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));

    const headers = this.headers(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined);
    let lastErr: Error | undefined;

    for (const delay of [0, ...RETRY_BACKOFF_MS]) {
      if (delay) await sleep(delay);
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), this.timeoutMs);
      let res: Response;
      try {
        res = await fetch(url.toString(), {
          method,
          headers,
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });
      } catch (e: unknown) {
        lastErr = e as Error;
        clearTimeout(t);
        continue;
      }
      clearTimeout(t);

      if (res.ok) {
        try { return await res.json() as Record<string, unknown>; }
        catch { return { raw: await res.text() }; }
      }
      if (res.status === 429 || res.status >= 500) {
        lastErr = new GeniOSError(`${res.status} ${await res.text()}`.slice(0, 400), res.status);
        continue;
      }
      throw new GeniOSError(`${res.status} ${await res.text()}`.slice(0, 500), res.status);
    }
    throw new GeniOSError(`retries exhausted: ${lastErr?.message}`);
  }
}

// ── OpenAI function-calling tools ────────────────────────────────────────────

const _OPENAI_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'genios_get_context',
      description: 'Retrieve relationship memory for a person or company from the GeniOS brain. Call this BEFORE drafting emails or planning outreach.',
      parameters: {
        type: 'object',
        properties: {
          entity: { type: 'string', description: 'Email address, full name, or company name.' },
          situation: { type: 'string', description: 'What you are about to do.' },
        },
        required: ['entity', 'situation'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'genios_search_contacts',
      description: 'Search contacts in the GeniOS brain by name, email, or company.',
      parameters: {
        type: 'object',
        properties: {
          q: { type: 'string', description: 'Partial name, email, or company.' },
          limit: { type: 'integer', description: 'Max results (default 10).' },
        },
        required: ['q'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'genios_log_interaction',
      description: 'Log an interaction with a contact back to the GeniOS brain. Call this AFTER any outreach.',
      parameters: {
        type: 'object',
        properties: {
          entity: { type: 'string' },
          summary: { type: 'string' },
          channel: { type: 'string', enum: ['email', 'slack', 'call', 'meeting', 'other'] },
          direction: { type: 'string', enum: ['outbound', 'inbound'] },
        },
        required: ['entity', 'summary'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'genios_list_insights',
      description: 'List proactive insights the GeniOS brain generated — cooling relationships, overdue commitments, anomalies.',
      parameters: {
        type: 'object',
        properties: {
          limit: { type: 'integer', description: 'Max insights to return (default 10).' },
        },
      },
    },
  },
] as const;

// ── Anthropic tool-use tools ──────────────────────────────────────────────────

const _ANTHROPIC_TOOLS = [
  {
    name: 'genios_get_context',
    description: 'Retrieve relationship memory for a person or company from the GeniOS brain. Call this BEFORE drafting emails or planning outreach.',
    input_schema: {
      type: 'object',
      properties: {
        entity: { type: 'string', description: 'Email address, full name, or company name.' },
        situation: { type: 'string', description: 'What you are about to do.' },
      },
      required: ['entity', 'situation'],
    },
  },
  {
    name: 'genios_search_contacts',
    description: 'Search contacts in the GeniOS brain by name, email, or company.',
    input_schema: {
      type: 'object',
      properties: {
        q: { type: 'string', description: 'Partial name, email, or company.' },
        limit: { type: 'integer', description: 'Max results (default 10).' },
      },
      required: ['q'],
    },
  },
  {
    name: 'genios_log_interaction',
    description: 'Log an interaction with a contact back to the GeniOS brain. Call this AFTER any outreach.',
    input_schema: {
      type: 'object',
      properties: {
        entity: { type: 'string' },
        summary: { type: 'string' },
        channel: { type: 'string', enum: ['email', 'slack', 'call', 'meeting', 'other'] },
        direction: { type: 'string', enum: ['outbound', 'inbound'] },
      },
      required: ['entity', 'summary'],
    },
  },
  {
    name: 'genios_list_insights',
    description: 'List proactive insights the GeniOS brain generated — cooling relationships, overdue commitments, anomalies.',
    input_schema: {
      type: 'object',
      properties: {
        limit: { type: 'integer', description: 'Max insights to return (default 10).' },
      },
    },
  },
] as const;

export function asOpenAITools(): typeof _OPENAI_TOOLS {
  return _OPENAI_TOOLS;
}

export function asAnthropicTools(): typeof _ANTHROPIC_TOOLS {
  return _ANTHROPIC_TOOLS;
}

export async function handleOpenAIToolCall(
  client: GeniOS,
  toolCall: { function: { name: string; arguments: string } }
): Promise<string> {
  const name = toolCall.function.name;
  const args = JSON.parse(toolCall.function.arguments || '{}');
  return JSON.stringify(await _dispatchTool(client, name, args));
}

export async function handleAnthropicToolCall(
  client: GeniOS,
  block: { name: string; input: Record<string, unknown> }
): Promise<string> {
  return JSON.stringify(await _dispatchTool(client, block.name, block.input));
}

async function _dispatchTool(client: GeniOS, name: string, args: Record<string, unknown>): Promise<unknown> {
  if (name === 'genios_get_context') {
    return client.context(args.entity as string, args.situation as string);
  }
  if (name === 'genios_search_contacts') {
    const url = new URL(`${client['baseUrl']}/v1/contacts`);
    url.searchParams.set('q', args.q as string);
    if (args.limit) url.searchParams.set('limit', String(args.limit));
    const res = await fetch(url.toString(), { headers: client['headers']() });
    return res.json();
  }
  if (name === 'genios_log_interaction') {
    const payload: Record<string, unknown> = { entity: args.entity, summary: args.summary };
    if (args.channel) payload.channel = args.channel;
    if (args.direction) payload.direction = args.direction;
    const res = await fetch(`${client['baseUrl']}/v1/interaction`, {
      method: 'POST', headers: client['headers'](), body: JSON.stringify(payload),
    });
    return res.json();
  }
  if (name === 'genios_list_insights') {
    const url = new URL(`${client['baseUrl']}/v1/insights`);
    if (args.limit) url.searchParams.set('limit', String(args.limit));
    const res = await fetch(url.toString(), { headers: client['headers']() });
    return res.json();
  }
  return { error: `unknown tool: ${name}` };
}
