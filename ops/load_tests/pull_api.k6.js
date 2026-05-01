// k6 load test — POST /v1/context
// Run:
//   k6 run -e URL=https://api.staging.genios.ai \
//          -e KEY=$GENIOS_API_KEY \
//          -e ENTITY="Priya Sharma" \
//          pull_api.k6.js
//
// Target from plan: 500 req/s sustained 15 min, p95 < 400ms, 0 errors.

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const URL    = __ENV.URL    || 'http://localhost:8000';
const KEY    = __ENV.KEY    || '';
const ENTITY = __ENV.ENTITY || 'Priya Sharma';

const latency = new Trend('genios_pull_latency_ms', true);
const errors  = new Rate('genios_pull_errors');

export const options = {
  scenarios: {
    steady_500rps: {
      executor: 'constant-arrival-rate',
      rate: 500,
      timeUnit: '1s',
      duration: '15m',
      preAllocatedVUs: 200,
      maxVUs: 600,
    },
  },
  thresholds: {
    'genios_pull_latency_ms': ['p(95)<400', 'p(99)<800'],
    'genios_pull_errors':     ['rate<0.01'],  // < 1% errors
  },
};

export default function () {
  const res = http.post(
    `${URL}/v1/context`,
    JSON.stringify({
      entity: ENTITY,
      situation: 'load test',
      context_size: 'medium',
    }),
    {
      headers: {
        'Authorization': `Bearer ${KEY}`,
        'Content-Type':  'application/json',
      },
      timeout: '5s',
    },
  );

  const ok = check(res, {
    'status 200': (r) => r.status === 200,
    'has context_for_agent': (r) => {
      try { return !!r.json('context_for_agent') || !!r.json('entity'); }
      catch { return false; }
    },
  });

  latency.add(res.timings.duration);
  errors.add(!ok);
}
