# P3 · Plane D · 05 · How it will be done at production level

**Owner:** Harsh and the agents Harsh assigns for the code. The founder (and, for other tenants, a named reviewer) for the knowledge. Rohit approves each domain's activation per tenant.
**Rule:** each step first passes in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)).

---

## 1 · Where the knowledge lives

- **The YAML stays the source of truth** (`Domain Expertise/`), with one schema for every domain (`_schema`, `_tools/validate.py`).
- **The index (P3-1) is compiled from it** by the existing compiler (`genios_engine/packs/compiler`) into a table: `expertise_items`, with id, domain, kind, about-tags, review state, version and text.
- The table is rebuilt on deploy. It is never edited by hand, and never by a model.

## 2 · One bridge for every reasoning path

- **One module**, `packs/compiler/expertise_view.py`, replaces the per-path renderers (the expert dossier's playbook block, the notebook's `playbook_text`).
- **It selects** by the situation's kind, stage and events (P3-1).
- **It renders whole** (P3-2), within a size budget, with ids the model must cite (P4-5).
- **The playbook reader** carries a rule's conditions, not only its statement and why.

## 3 · Activation per tenant and per department

- Domains are switched on per tenant by the existing rows (`platform/l3_activation`), never by a global flag.
- Founder Office is the default for a founder tenant. Admin's founder-relevant items (follow-up, renewals, registration, commitments) are selected for it through the index, whichever domain wrote them.
- A department's domain (Sales, Support, Finance …) comes on with that department.

## 4 · Review as a workflow, not a hope

- **A review is an item state.** The validator refuses `stable` without `reviewed_by` and `reviewed_at` matching the current bytes. The check already exists and must stay strict.
- **A review sheet per capability**, as a page or a pull request, where the reviewer accepts, edits or rejects each line.
- **A rejected line** is excluded from the index.
- **An unreviewed line** is shown to the model labelled as such, and a card that rests mainly on unreviewed knowledge says so.
- **The daily health report lists what is waiting for review,** with the reviewer named. That stops "approved but never flipped" from happening again.

## 5 · Knowledge is tested like code

- Every item carries its golden cases (P3-6). CI runs them on every change to the YAML or the bridge.
- A change that makes an item fire where it must not, or stay silent where it must speak, fails the build.

## 6 · Monitoring: does each piece of knowledge earn its place?

**Per item, per week:**
- how often it was selected;
- how often the model cited it;
- how often its conditions failed the check (P4-5);
- how often the founder's verdict on the resulting card was good or bad (P5, L6).

An item that is never selected, or always contradicted, is reviewed.

## 7 · Size and cost

- **Size:** the founder's full investor and programme knowledge renders in about 6,000 characters. Selecting by events keeps a dossier's expertise block to the items that apply, typically 2–5.
- **Cost:** the block sits in the cached part of the prompt where the same items repeat across situations.

## 8 · What must never happen

- **A rule shown without its conditions.**
- **A move cut to its first step without the cut being counted.**
- **Knowledge chosen by one key from one domain** while approved knowledge elsewhere applies.
- **A model deciding a review state.**
- **A YAML change that skips its golden cases.**
