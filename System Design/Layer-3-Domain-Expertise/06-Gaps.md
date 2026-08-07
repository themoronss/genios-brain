← [Native Capabilities](05-Native-Capabilities.md) · [Folder map](README.md)

---

# Gaps

---

## §6 · Gaps

| # | Gap | Detail |
|---|---|---|
| 1 | **Only two domains ship** | `sales` and `general`. Support, admin/finance, legal, engineering are all "a manifest away" — but nobody has written the manifest. The coverage model already declares `support` and `admin` requirements with no pack behind them. |
| 2 | **Capabilities are shadow-only** | `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)` and the package explicitly does not self-register. The legacy pack path is still the live one, so the 17-unit reasoning DAG is built and not in production. |
| 3 | **`golden_cases: 0`** | The expertise API reports zero golden cases per pack — *"not tracked in the engine yet — honest zero."* There is no regression corpus proving a pack edit did not break its own rules. |
| 4 | **Packs are Python literals** | They *are* data, but data that requires a repo commit to change. The registry stores `jsonb`, so a database- or file-loaded pack needs no engine change — it simply has not been built. |
| 5 | **Display metadata lives outside the manifest** | `_MATURITY` and `_DISPLAY` are hardcoded in `api/expertise_routes.py`. Two more hand-maintained lists keyed by pack id — the exact drift shape Layer 1's source registry was built to end. |
| 6 | **`_DEAL_REASON_CODES` duplicated** | Verified byte-identical to the sales pack's `signal_vocab`, hand-copied into `api/intelligence_routes.py`. A second copy of pack data outside the pack. |
| 7 | **Behavioral brain is thinly consumed** | `user_models` is fully specified and governed, but how much of it actually reaches rendering and channel choice is a Layer 5/6 question, not settled here. |

---
