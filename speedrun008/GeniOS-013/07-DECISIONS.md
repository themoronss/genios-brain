# 07 · Decisions for Rohit

**Written for:** Rohit.

Each decision has a default. A step that needs a decision waits for it. If you skip a decision, the default applies, as in GeniOS-008 `03-QUESTIONS`.

---

### D1 · May L2 use unconfirmed kinds of work and goals while it reasons? — needed by Step 5

**Today.**
- A file's kind, and so its playbook, comes only from an accepted brief line.
- A goal is printed to the model as the company's goal only once it is approved.
- None of the 29 brief lines has been accepted. So 38 of 38 current dossiers have no playbook, and no work links to any goal.

**Proposed.**
- L2's own reading of the kind picks the playbook, labelled "GeniOS's reading, not confirmed".
- Proposed goals are printed with ids as "proposed, not confirmed", so works can link to them.
- Approving goals, owners, targets and deadlines stays yours. Nothing becomes `approved` or `active` without you.

**Default:** yes.

**If no:** Plane D and the goal links stay off until you accept the brief lines by hand. That is the situation today.

### D2 · Budget: the one-time onboarding pass, and the daily L2 budget — needed by Steps 3 and 5

**Today.** R-9 has $2 a day and $0.25 a call. It hit that cap every day from 22 to 28 Oct.

**Proposed.**
- A one-time onboarding budget per tenant, about $20. On 23 Oct Harsh estimated about $17 for 169 files at about $0.10 each, at today's dossier size.
- Keep $2 a day until Step 3. Then set the daily budget from the measured cost per judgment.

**Default:** as proposed.

### D3 · More goal proposals during onboarding — needed by Step 5

**Today.** At most 3 L2 goal proposals a week (GeniOS-012 D12).

**Proposed.** Up to 10 in the first week after connect, then 3 a week.

**Default:** yes.

### D4 · Capture 365 days at onboarding — optional, Step 7

**Today.** 180 days. Three ideal cards (`i6`, `s1`, `s2`) rest on mail from March and April, which is outside that window.

**Proposed.** 365 days for a new tenant's first capture.

**Cost.** Roughly doubles the first extraction run. The daily cost does not change.

**Default:** 365.

### D5 · For this org, only the work path delivers cards — needed by Step 6

**Proposed.** Once Step 6's gate passes, and after at least three days of side-by-side comparison, the legacy and compiled lanes stop delivering for this org. The old LLM decision maker and R-1 are switched off for it. All of it can be switched back with an activation row.

**Default:** yes.

### D6 · The stored-event fetcher is on by default — needed by Step 3 (Harsh's call)

**Proposed.** When L2 asks for the full text of an older mail, a fetcher reads it from our own database (`prepared_content`). This makes no Gmail call and costs nothing. It is armed by default, separately from the Gmail fetchers' switch (`GENIOS_NEED_FETCHERS`).

**Default:** yes.
