# Audits

Pen test reports + responses land here. One folder per engagement.

Structure:
```
ops/audits/
├── pen_test_scope.md          — our SOW to hand to the vendor
├── 2026-Q2-acme-pentest/      — vendor deliverable folder
│   ├── report.pdf             — findings document
│   ├── responses.md           — our per-finding remediation plan
│   └── retest.md              — evidence that fixes landed
└── ...
```

**Rule:** the audit folder is committed, reports are not. Reports go to a
separate private bucket (S3 / Supabase Storage), and this folder holds only
metadata + our response plan.
