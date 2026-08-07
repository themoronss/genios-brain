← [Layer 7 — The Learning Engine (`feedback/`)](00-Overview.md) · [Folder map](README.md) · → [Precision and the Wilson Interval](02-Precision-and-Wilson-Bounds.md)

---

# The Judgment Taxonomy

---

## The judgment taxonomy — what counts, and as what

```python
TAXONOMY = {
    "run_play":            {"label": "positive_strong",     "precision": "numerator"},
    "do_it_myself":        {"label": "positive_moderate",   "precision": "numerator"},
    "wrong:not_relevant":  {"label": "negative_relevance",  "precision": "denominator"},
    "wrong:wrong_facts":   {"label": "negative_relevance",  "precision": "denominator"},
    "wrong:bad_timing":    {"label": "timing",              "precision": "none"},
    "snooze":              {"label": "timing",              "precision": "none"},
    "requeue":             {"label": "window_mgmt",         "precision": "none"},
}
```

Three classes, and the third is the interesting one:

- **Numerator** — the person acted on it. Two strengths, both count as correct.
- **Denominator** — the person said the recommendation was **wrong about the world**.
- **`"precision": "none"`** — **timing complaints and window management are excluded from
  precision entirely.**

> *"Bad timing"* and *"snooze"* say the card was **right and arrived at the wrong moment**. That
> is a **Layer 6 problem**, not a Layer 4 one. Counting them against precision would mute a
> correct rule because the delivery gate was misconfigured.

---

## The rule that shapes everything: impressions are not labels

```python
# Learning is deliberately conservative: passive impressions are observability, not labels.
# Only canonical human judgments enter confidence and eligibility calculations.
```

> Impressions remain visible for **coverage diagnostics**. Eligibility and confidence are based
> **only on labeled outcomes**, so **twelve ignored cards plus one click can never mute a rule.**

An unclicked card means the person was busy, or on holiday, or reading something else. **Treating
silence as rejection is how a system learns to say nothing.**
