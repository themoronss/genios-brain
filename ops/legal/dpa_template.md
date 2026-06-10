# Data Processing Agreement — DRAFT (not legal advice)

**Version: 0.1 (pre-legal-review)**

This Data Processing Agreement ("DPA") forms part of the Service Agreement
between **[LEGAL ENTITY NAME]** ("Processor", "we") and the customer
identified in the order form ("Controller", "you"). Capitalized terms
follow the definitions in GDPR Art. 4 and India DPDP Act 2023.

## 1. Subject matter and duration

1.1 We Process Customer Data on your behalf to provide GeniOS as defined
in the Service Agreement.
1.2 Duration: for the term of the Service Agreement plus 30 days for
return / deletion of Customer Data.

## 2. Nature and purpose of Processing

- Ingesting communication data from your authorized sources
  (Gmail, Calendar, Slack, Jira, Notion, HubSpot, etc.)
- Extracting entities, relationships, commitments
- Generating recommendations via LLM pipelines
- Surfacing context packs to your agents

## 3. Types of Personal Data and categories of Data Subjects

| Category | Data Subjects |
|---|---|
| Name, email, phone | Your employees, prospects, customers, contacts |
| Email content, subjects, attachments (metadata only unless extracted) | As above |
| Calendar event details | As above |
| Messages in business communication tools | As above |
| Derived classifications (contact_role, sentiment, stage) | As above |

No processing of special categories (Art. 9 GDPR) or sensitive data
under DPDP unless a separate written addendum is executed.

## 4. Instructions from Controller

4.1 We Process Customer Data only on your documented instructions
(these being: the Service Agreement + this DPA + configuration you set
through the Service).
4.2 If we believe an instruction infringes applicable data protection
law, we'll notify you.

## 5. Personnel and confidentiality

5.1 Access to Customer Data is restricted to personnel who need it to
operate the Service.
5.2 All personnel are bound by confidentiality obligations.

## 6. Sub-processors

6.1 You authorize the sub-processors listed in our Privacy Policy as at
the effective date of this DPA.
6.2 We'll give 30 days' notice of any new sub-processor; you may object
within 15 days with a reasonable basis, failing which you may terminate
the affected Service without refund for past fees.

## 7. International transfers

7.1 Where Customer Data is transferred outside the European Economic Area
or India to jurisdictions without an adequacy decision, we rely on the EU
Standard Contractual Clauses (Module Two: Controller-to-Processor) or
equivalent mechanisms, incorporated herein by reference.

## 8. Security

We implement technical and organizational measures appropriate to the
risk, including at a minimum:
- Encryption in transit (TLS 1.2+) and at rest (AES-256)
- Postgres row-level security isolating tenants
- Per-tenant encryption of OAuth refresh tokens
- Access logging retained 90 days
- Least-privilege IAM within engineering team
- Annual external pen test
- Vulnerability scanning of dependencies
- Incident response plan with 72h notification commitment

## 9. Data Subject requests

9.1 We'll promptly (within 5 business days) forward any Data Subject
request we receive about Customer Data.
9.2 Where technically possible through the Service we'll provide means
for you to respond to such requests directly (export, delete via
`POST /v1/admin/delete`).

## 10. Personal Data Breach

10.1 We'll notify you without undue delay and in any event within 72
hours of becoming aware of a Personal Data Breach affecting Customer Data.
10.2 We'll provide:
- nature of the breach, categories + approximate number of Data Subjects
  and records affected
- name of our privacy contact
- likely consequences
- measures taken or proposed

## 11. Audit rights

11.1 On reasonable written notice (≥ 30 days) and not more than annually,
you may audit our compliance with this DPA. You bear the reasonable cost
of such audit unless a material breach is found.
11.2 In lieu of direct audit, we'll share our most recent independent
audit report under NDA.

## 12. Return / deletion at end of Services

12.1 At the end of the Services, at your option, we will return a copy
of Customer Data or delete it within 30 days, retaining only backups
that age out within a further 90 days.

## 13. Liability

Liability arising under this DPA is subject to the limits in the Service
Agreement.

## 14. Governing law

[CONFIRM WITH COUNSEL]

---

## Annex 1 — Sub-processors

(See Privacy Policy s.5 for the live list.)

## Annex 2 — Technical and organizational measures

(See s.8 above; expand per vendor due-diligence questionnaires as needed.)

---
*Draft v0.1 — subject to counsel review. Do not sign.*
