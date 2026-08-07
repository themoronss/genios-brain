# Read endpoints

The Executive API exposes briefs, summaries, memory, preventive views, why-not receipts,
commitment lists and commitment detail under `/v1/executive`.

Reads are organization-scoped. Query filters do not grant authority to view another tenant and do
not derive a second lifecycle state.
