# P3 · Plane D (domain expertise) · 01 · What's exactly there

**The part:** what a professional *knows*, per department and per kind of work:
- playbooks: the stages, the typical durations, what quiet means at each stage, the moves and their steps;
- rules of thumb, each with **its conditions** (when it applies, when it breaks down, how it is misused);
- the situations each capability owns;
- the review state of all of it, and the bridge that shows it to the model.

Plane D never reasons. P4 does that, with it.

**Read at:** `speedrun008` `71c50f56`. The corpus counts come from the repo's own report, `python scripts/l2_refusal_report.py --corpus-only` (no database needed), run on 29 Oct.

---

## 1 · The corpus

| Domain | Capabilities | Situations | Still `draft` | Note |
|---|---|---|---|---|
| Admin | 59 (in 10 groups) | 34 | 4 | Live for this tenant |
| Sales | 46 | 13 | 0 | Off for this tenant |
| Customer Support | 49 | 20 | 16 | Off for this tenant |
| **Founder Office** | **6** | **2** | **2** | **All 6 capabilities "unreadable" by the compiler**; live for the pilot only |
| **All** | **160** | **69** | **22** | A card built from a `draft` situation is downgraded to an observation: "it describes, and it does not instruct" |

**Each domain has the same tree (`Domain Expertise/<Domain>/`):**
- `domain.yaml`;
- `capabilities/<NN-group>/<capability>/` holding `capability.yaml` (purpose, outcomes, failure modes, KPIs, handoffs), `objects.yaml`, `knowledge.yaml` and `situations/`;
- `playbooks/`, `heuristics/` (rules of thumb) and `objects/`;
- `registry/situation-capability-map.yaml`;
- `deferrals.yaml`: why a capability has no runtime door.

## 2 · Founder Office: the founder's own domain (STEP-11, 9 Oct)

**Its question:** "How would a seasoned chief of staff to a founder read this situation?"

**Its state:**
- `identity.status: draft`;
- `created_by: ai`, `reviewed_by: ""`, `review_status: unreviewed`, `confidence: provisional`;
- switched on for the pilot org only (`default_on: false`).

| Capability | State | What is authored |
|---|---|---|
| Investor relations | Authored (capability 160 lines, knowledge 38) | 2 situations (a live relationship, a live contact). 6 playbooks. 5 rules of thumb |
| Programme applications | Authored (166 lines) | 5 playbooks, 5 rules of thumb. No L2 situation type, so it is "read by the expert for a file whose kind of work is `program`" |
| Introductions | **Stub** (23 + 17 lines) | Only the question: "Has each introduction been followed through on both sides?" |
| Compliance | **Stub** | Only the question |
| Hiring | **Stub** | Only the question |
| Meetings | **Stub** ("Filled by STEP-11 M31") | Only the question: "Is each external meeting prepared for, and followed through after?" |

### The playbooks, as written

**Investor relations** (`playbooks/investor_relations/`):
- a warm intro to an investor;
- before an investor call;
- run an investor conversation. This one is 450 lines and has the stages first contact → first call → partner meeting → diligence → term sheet → closed or passed. Each stage has a typical duration (a labelled prior with its source), what quiet means at that stage, and what ends it;
- the wave gone silent;
- reopen after a pass;
- the conditional deferral.

**Programme applications:**
- follow an application. 520 lines, with the stages applied → under review → interview → decision → onboarding → in programme or declined;
- work back from the deadline;
- prepare for the interview;
- read the decision mail;
- documents after acceptance.

### The rules of thumb, as written

Each has: a statement; a sourced why (Graham, Dixon, Gompers et al. and others); `confidence_bp`; **applies when**; **breaks down when**; **failure modes**; limits; references.

| Investor relations | Programme applications |
|---|---|
| Investors do not chase | The deadline is the only fixed point |
| Silence reads by stage | A rejection carries a reapplication date |
| Only an offer counts | A batch is silent until it decides |
| Momentum is a parallel process | The portal is the record |
| A pass is a date, not a verdict | A programme is not an investor |

**Example: the conditions are written down.** "Silence reads by stage" applies "when an investor conversation is open, **the turn is theirs**, and the stage is known". Its failure mode reads: "Using it to excuse our own silence. **It reads their quiet, never ours.**"

**And the move that answers our silence is written too.** "Before an investor call", step 6 of 6: "**Write the same day:** thank them, confirm the next step and its date in writing, and send anything promised on the call."

## 3 · Admin: approved knowledge the founder's work needs

All of the following are `stable` and `approved`.

| Capability | What it says | Ideal cards it answers |
|---|---|---|
| Meeting operations → **follow-up coordination**, with the situation "**meeting without follow-through**" | After a meeting, the follow-up is owed and tracked | `b2` (two partner calls, no written next step), `i3` (follow-up after an investor call) |
| Contract and vendor administration → **renewal management**, with the situation "vendor relationship live" | "Auto-renewal is the default that costs the most money precisely because it requires nobody to do anything. Which agreements auto-renew, when does the notice window open, and do we still want them?" | `c2` (a tool subscription renews within the week) |
| Compliance and governance → **licence and registration** | Registrations and their upkeep | `c1` (the registration complaint) |
| Executive support → **commitment tracking**, with situations: a promise past its date, a dependency stated, blocked on someone unnamed, and others | Our and their promises | many |

## 4 · How the knowledge reaches the model today

| Path | What selects the knowledge | What is shown | What is lost |
|---|---|---|---|
| **Product: expert path** (`reason/expert/dossier.py` + `packs/compiler/playbook_reader.py`) | The **kind of work**, from Founder Office only. Investor and programme have a playbook. The rest don't: intro, hiring and compliance get "capability not authored"; partner gets "no capability for kind"; vendor gets "no playbook declares stages"; anything else is an unknown kind | Stages (typical, yours, quiet means, ends when); all move steps (up to 10 moves); claims as statement + why (up to 20); the stop rule; "not yet reviewed" labels | **Every rule's conditions** (applies when, breaks down when, failure modes): the reader does not carry them. **All of Admin** |
| **Product: compiled lane** | Capabilities and their situations, through the capability resolver and the 23 reasoning units | Situation and capability fields as numbers and codes, not words for a model | Founder Office (its capabilities are unreadable to the compiler) |
| **Notebook** (`nb/common.playbook_text`) | The kind of work, through the same reader | Stages and quiet means; **only the first step of each move**; claims as statements | Conditions; steps 2 onward (including "write the same day" after a call); all of Admin |

**Measured on the notebook build `b2`:** the 421 business situations by kind were intro 104, programme 92, event 71, other 42, partner 38, investor 29, vendor 15, compliance 13, internal 11, hiring 5, customer 1.
- **Only investor and programme (121, 29%) had any expertise behind them.**
- **300 (71%) were judged with none.**
