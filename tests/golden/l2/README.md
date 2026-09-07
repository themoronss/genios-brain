# L2 golden sets

Hand-labelled fixtures for the Layer 2 model sites, in the same **replay lane** shape
`tests/golden/l1/` uses: every fixture carries the answer the model was labelled against, so what
the suite grades is OUR CODE — the gate, the authority table, the span validator, the floors —
and not any model's quality on a given afternoon.

| File | Site | Gate |
|---|---|---|
| `m4_resolution.json` | **M-4 · resolution detection** (L2.7.7-U1) | false-positive rate **< 2%**, ≥ 8 Hinglish fixtures |

## Extending `m4_resolution.json`

Append an object to `fixtures`. Only `fixture_id`, `message`, `sender`, `model_answer` and
`truth` are required; everything else has a default.

```jsonc
{
  "fixture_id": "unique_snake_case",
  "provenance": "which doc/case this fixture exists for",
  "tags": ["hinglish", "sarcasm", "partial", "negation"],   // drive the coverage assertions
  "subject": "what the situation is about",
  "sender": "priya@acme.example",
  "internal_emails": ["rohit@ourco.example"],               // who counts as US
  "obligations": [{"id": "ob_msa", "subject": "countersign the MSA",
                   "owner": "priya@acme.example"}],
  "message": "the prepared text, verbatim",
  "model_answer": {                                          // what M-4 returned. May be WRONG —
    "verdict": "RESOLVED",                                   // the traps are the point
    "certainty": "EXPLICIT_COMPLETION",
    "scope": ["ob_msa"],
    "quote": "we signed yesterday"                           // offsets computed from the message
  },                                                         // unless stated explicitly
  "truth": {"must_close": true, "why": "a completed act, reported by the owner"},
  "expect": {"decision": "apply", "verdict": "RESOLVED"}
}
```

**A golden set that only contains easy cases is not a golden set.** Roughly half of these
fixtures are near-misses built to trip the detector: intentions phrased as completions, sarcasm,
a counterparty's claim, a resolution of a different thing in the same thread, and a fabricated
quote. `truth.must_close` is the label the false-positive rate is measured against; `expect` is
the exact decision the current thresholds produce, and a fixture that changes it should be
changed deliberately.
