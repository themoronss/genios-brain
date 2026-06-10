// k6 load test — simulate ingest burst via the extract endpoint.
// Note: real ingest goes through Gmail/Calendar connectors. This test drives
// extract_email_intelligence indirectly by hitting /v1/ingest-email (if
// available in your deploy) or a dedicated test endpoint.
//
// Plan target: 10K signals / minute burst for 5 minutes (166 signals/sec).

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const URL = __ENV.URL || 'http://localhost:8000';
const KEY = __ENV.KEY || '';

const latency = new Trend('genios_ingest_latency_ms', true);
const errors  = new Rate('genios_ingest_errors');

export const options = {
  scenarios: {
    burst_166rps: {
      executor: 'constant-arrival-rate',
      rate: 166,
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 100,
      maxVUs: 300,
    },
  },
  thresholds: {
    'genios_ingest_latency_ms': ['p(95)<90000'],  // 90s per plan
    'genios_ingest_errors':     ['rate<0.05'],    // 5% tolerance on ingest
  },
};

const SUBJECTS = [
  'Quick follow up',
  'Re: Series A term sheet',
  'Intro to Sarah',
  'Demo rescheduled',
  'Deal update',
];

export default function () {
  const subject = SUBJECTS[Math.floor(Math.random() * SUBJECTS.length)];
  const res = http.post(
    `${URL}/v1/ingest-email`,
    JSON.stringify({
      subject,
      body: 'Synthetic load-test message. ' + 'Filler content. '.repeat(20),
      sender: `loadtest-${__VU}@example.com`,
    }),
    {
      headers: {
        'Authorization': `Bearer ${KEY}`,
        'Content-Type':  'application/json',
      },
      timeout: '120s',
    },
  );

  const ok = check(res, { 'status 2xx': (r) => r.status >= 200 && r.status < 300 });
  latency.add(res.timings.duration);
  errors.add(!ok);
}
