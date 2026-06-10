# Privacy Policy — DRAFT (not legal advice)

**Last updated: [DATE]**
**Version: 0.1 (pre-legal-review)**

This Privacy Policy explains how **[LEGAL ENTITY NAME]** ("we", "our",
"us") collects and processes personal data in connection with **GeniOS**
("Service"). It's aligned with the GDPR and India's DPDP Act 2023.

Contact: [PRIVACY EMAIL]
DPO / Grievance Officer: [NAME, EMAIL] (as required under DPDP s.10)

## 1. Controller / processor roles

- **We are the Controller** for account data (the email, name, company of
  the individual who signed up for GeniOS).
- **We are the Processor** for Customer Data (emails, contacts, calendar
  events, Slack messages, etc.) brought into your tenant via authorized
  integrations. You (the customer) are the Controller; our processing is
  governed by the DPA.

## 2. Data we collect as Controller

| Category | Purpose | Retention |
|---|---|---|
| Name, email, company | Account provisioning, billing, support | Until account deletion + 180 days |
| IP, user agent, timestamps | Security, fraud prevention, abuse response | 90 days |
| Payment data (via Razorpay) | Billing | Handled by Razorpay; we store only token + invoice metadata |
| Support correspondence | Responding to requests | 3 years |

## 3. Data we process as Processor

See the DPA. In summary:
- Email metadata + body from connected Gmail accounts
- Calendar events from connected Google Calendar
- Messages from connected Slack / Jira / Notion / HubSpot / etc.
- Derived: extracted entities, facts, relationships, recommendations
- Retention: for the lifetime of your active tenant, or until you
  delete via `/v1/admin/delete` or account closure

## 4. Legal bases (GDPR Art. 6)

- **Contract** — Art. 6(1)(b) — to provide the Service under the Terms
- **Legitimate interest** — Art. 6(1)(f) — security, fraud prevention,
  product improvement in aggregate
- **Consent** — Art. 6(1)(a) — cookies not strictly necessary; opt-in
  for optional beta features

## 5. Sub-processors

Up-to-date list with locations:

| Sub-processor | Role | Region |
|---|---|---|
| Supabase Inc. | Postgres database | ap-northeast-1 (Tokyo) |
| Upstash Inc. | Redis | multi-region |
| DigitalOcean | App Platform hosting | [REGION — confirm] |
| Razorpay Software Pvt. Ltd. | Payments | India |
| Groq, Inc. | LLM inference (extraction, reasoning) | USA |
| Google LLC | Gemini embeddings, Gmail/Calendar APIs | USA / global |
| Sentry (Functional Software, Inc.) | Error monitoring | EU |
| PostHog Inc. | Product analytics | EU |

We'll provide 30 days' notice of material sub-processor changes; you may
object within 15 days.

## 6. International transfers

Where data leaves your region (e.g., to Groq/Google in the US), we rely on
EU Standard Contractual Clauses or equivalent. Transfer impact assessments
available on request.

## 7. Your rights

Under GDPR / DPDP you have rights to:
- access, rectify, erase your data
- port your data
- object to or restrict processing
- withdraw consent
- complain to your supervisory authority

Exercise any of the above: [PRIVACY EMAIL]. We'll respond within 30 days.

Under DPDP specifically: grievance officer [NAME, EMAIL] handles
grievances within the statutory timeline.

## 8. Security

- TLS in transit, AES-256 at rest
- Row-level security per tenant in Postgres
- OAuth refresh tokens encrypted per-tenant
- Access logs retained 90 days
- Annual external pen test (see `/ops/audits/`)

## 9. Children's data

Service is B2B. We do not knowingly collect data from children under 18.

## 10. Retention

Account data: as long as your account is active, plus 180 days after
closure for legal recovery. Customer Data: per Section 3 above / DPA.

## 11. Changes

We'll notify you of material changes 30 days before they take effect.

## 12. Contact

- General privacy: [PRIVACY EMAIL]
- DPO / Grievance: [NAME, EMAIL] (DPDP Act compliance)
- Legal notices: [LEGAL EMAIL]
- Mailing address: [REGISTERED ADDRESS]

---
*Draft v0.1 — subject to counsel review. Do not publish.*
