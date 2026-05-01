/**
 * Lightweight smoke test for SDK 1.0 features (runs with plain Node, no test framework).
 * Use: node tests/verify.mjs  (after `npm run build`)
 */
import assert from 'node:assert';
import crypto from 'node:crypto';
import { GeniOS, GeniOSError } from '../dist/index.js';

// ── 1. Constructor validation ──
assert.throws(() => new GeniOS({}), /apiKey is required/);
console.log('✓ constructor requires apiKey');

// ── 2. Webhook signature verify ──
const secret = 'shhh';
const body = Buffer.from('{"event":"recommendation"}');
const sig = crypto.createHmac('sha256', secret).update(body).digest('hex');
assert.strictEqual(GeniOS.verifyWebhookSignature(secret, body, sig), true);
assert.strictEqual(GeniOS.verifyWebhookSignature(secret, body, 'deadbeef'), false);
assert.strictEqual(GeniOS.verifyWebhookSignature('wrong', body, sig), false);
console.log('✓ verifyWebhookSignature (valid / invalid / wrong-secret)');

// ── 3. Retry behaviour via mocked fetch ──
const origFetch = globalThis.fetch;
let calls = 0;
globalThis.fetch = async () => {
  calls++;
  if (calls < 3) return new Response('down', { status: 503 });
  return new Response('{"ok":true}', { status: 200 });
};

try {
  const client = new GeniOS({ apiKey: 'x', baseUrl: 'http://test.local', timeoutMs: 500 });
  const out = await client.context('a', 'b');
  assert.deepStrictEqual(out, { ok: true });
  assert.strictEqual(calls, 3, `expected 3 calls, got ${calls}`);
  console.log('✓ retries 2x 503 → success on 3rd call');
} finally {
  globalThis.fetch = origFetch;
}

// ── 4. No retry on 4xx (except 429) ──
calls = 0;
globalThis.fetch = async () => { calls++; return new Response('bad', { status: 400 }); };
try {
  const client = new GeniOS({ apiKey: 'x', baseUrl: 'http://test.local', timeoutMs: 500 });
  await assert.rejects(() => client.context('a', 'b'), GeniOSError);
  assert.strictEqual(calls, 1, `expected 1 call, got ${calls}`);
  console.log('✓ no retry on 400');
} finally {
  globalThis.fetch = origFetch;
}

// ── 5. Idempotency header sent on feedback ──
let captured;
globalThis.fetch = async (url, opts) => {
  captured = opts;
  return new Response('{"ok":true}', { status: 200 });
};
try {
  const client = new GeniOS({ apiKey: 'x', baseUrl: 'http://test.local' });
  await client.feedback('rec-1', 'acted', { idempotencyKey: 'abc-123' });
  assert.strictEqual(captured.headers['Idempotency-Key'], 'abc-123');
  console.log('✓ feedback sets Idempotency-Key header');
} finally {
  globalThis.fetch = origFetch;
}

console.log('\n5/5 SDK 1.0 smoke tests passed.');
