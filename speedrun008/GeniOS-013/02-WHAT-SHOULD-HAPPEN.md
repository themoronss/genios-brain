# 02 · What should happen: how GeniOS should work

**Written for:** Rohit first, then Harsh and the agents.
**Source of truth:** GeniOS-008 `00-ARCHITECTURE.md` (Design Atlas v2). Nothing here changes that architecture. It describes, in plain words, how it behaves once the missing half (01 §4) is built.

---

## §1 · The principle in one sentence

**GeniOS keeps an up-to-date understanding of every piece of work, and only thinks about what changed or what is overdue.**

Everything below follows from that sentence.

---

## §2 · The piece of work: GeniOS's notebook page

A **piece of work** is one thing the company is doing or waiting on. It is the "situation" of Atlas v2, saved. Examples:
- the accelerator application (`i1`);
- the conversation with one investor (`i2`);
- an introduction channel, with one child piece of work per introduction (`f3`, `b1`, `b3`);
- a government registration (`c1`);
- a hiring offer (`h1`);
- a vendor renewal (`c2`);
- "one number everywhere": every traction figure we have told anyone (`p1`).

Each piece of work keeps one page:

| On the page | Example (the accelerator application) |
|---|---|
| What it is, and what kind of work | "Reconsideration of the accelerator application" · programme |
| Which goal it serves | "Get into an accelerator" (proposed, not yet confirmed) |
| Where it stands | waiting on them since 26 Aug · stage: reconsideration requested |
| Whose move it is | theirs |
| What is still owed, and by whom | their decision (owed by them) · our promised updates: **kept** on 11 Aug |
| What we have claimed | three traction numbers to the evaluator; they differ from what two funds were told in May |
| What should happen next, and by when | their answer, within two weeks of our next update; if not, close it |
| The latest conclusion | "A pass with the door left open. Three updates sent, none answered. The next update must carry a new, checkable fact; then stop." |
| What belongs to it | the threads, the calendar meeting, any document, from any tool |

The page is small, a few KB. It points to the mail and facts that support it; it does not copy them. The full specification is [05](05-THE-WORK-OBJECT.md).

---

## §3 · How a new mail should travel

```
new mail / event / screen moment
   │
L1 ─ keep it if it could matter; read it; note who asked, promised or claimed what
   │
L3 ─ attach it to its piece(s) of work
   │      same thread → attached by code, free
   │      new thread  → L2 decides where it belongs
   │
L2 ─ think only if something material changed:
   │      read the page + only the new mail + the playbook for this kind + the goals
   │      → propose an updated page (status, whose move, loops settled, next step and date, claims, goal)
   │      → propose the card's words (recommendation, steps, draft)
   │
L3 ─ check every proposed change against the evidence, then save it (versioned; the founder's corrections win)
   │
clock ─ every pass, find pages whose "expected by" date has passed with nothing new
   │      → ask L2 one question: "nudge, close, or ask the founder?"  (finding them costs nothing)
   │
L5 ─ one card per piece of work that needs the founder, updated in place, never repeated
   │
L4 ─ the founder approves a move → a task (for a person or an AI agent) attached to the piece of work
   │      its result comes back as new evidence and can settle the page's open loops
L6 ─ learn from what happened: what was acted on, dismissed, settled, or late
```

Compared with today (01 §3):
- mail is grouped by **work**, not by sender;
- the brain reads **the page plus what is new**, not 70,000 characters;
- **silence** wakes it, not only new mail;
- **its conclusions are saved**;
- the **cards come from the page**, not from rules.

---

## §4 · What each layer is responsible for

| Layer | Does | Never |
|---|---|---|
| **L1 Signals** (`capture/`) | Captures from every tool. Keeps anything from people involved in active work. Reads attachments it can. Extracts who asked, promised or claimed what. Says what it could not read | decides what a mail means for the company |
| **L2 Reasoning** (`reason/` + `packs/`): Plane D, what an expert knows; Plane R, how an expert thinks | Reads the page, the new evidence, the playbook and the goals. Proposes the updated page, the next move and the card's words. Asks for evidence when it needs more | saves anything itself; scores, ranks or routes; decides for a human |
| **L3 Context Graph** (`context/`): Evidence Graph + **Intelligence Graph** | Keeps the evidence. Keeps the pages, their versions, members, loops, links and claims. Checks each change L2 proposes before saving it. Runs the clock | reasons by itself |
| **L4 Executive** (`executive/`) | Turns an approved move into owned work for a person or an agent | lets a model decide |
| **L5 Delivery** (`deliver/`) | One card per piece of work that needs the founder, written from the page | adds a fact the page doesn't hold |
| **L6 Learning** (`feedback/`) | Learns from outcomes and corrections, as data | edits code or the expert knowledge |

The model rules of Atlas v2 stay as they are. The model proposes and words. Code calculates and checks. Only humans approve goals and actions.

---

## §5 · How this handles the real-world limits

| The worry | How the design answers it |
|---|---|
| "There will be many tools" | Every tool's item (a mail, a meeting, a document, a Slack message, a CRM change, a screen moment) becomes a **member** of a piece of work. The page does not care which tool an item came from. A new tool needs a connector, not a new design |
| "The context changes every day" | Only what changed is read, and the page is updated. Nothing old is re-read unless the brain asks for one specific item |
| "Reading everything at once is impossible" | It is never needed. The page *is* the summary of everything so far. Older evidence is fetched on request, from our own database, at no cost |
| "We must correlate across domains, goals, tools and agents" | All of them hang on the same key, the piece of work. Goals link to pieces of work. Members come from any tool. Agent tasks attach to the piece of work they serve |
| "Cost" | Thinking is in proportion to what **changed**, not to the size of the history. Finding silence costs nothing. Storage is about 1 MB for this org |
| "Mistakes" | Every change is a saved version, so it can be undone. The founder's correction locks a field, and code checks every change before it is saved |

---

## §6 · What the founder experiences

**Day one, after connecting:**
1. Confirm "who we are" (names, addresses, domain) with one click.
2. See the list of pieces of work GeniOS found, each with its status and whose move it is.
3. See the proposed goals, with the work behind each. Approve, edit or reject each with one click.

**Every day:**
- A **few** cards, one per piece of work that needs the founder. Each says what happened, why it matters, the recommended move, and gives a draft.
- When GeniOS is unsure of something only the founder knows (for example, whether a candidate accepted an offer), **one plain question** instead of a guess.
- Pieces of work that are simply waiting stay visible, with **no notification**, until their date passes.
- No duplicates. A card changes in place when the work moves.

**When GeniOS is wrong:** the founder corrects it once ("this is not an investor", "this is done", "snooze to Monday"). The correction is saved, wins over the model, and is never overwritten.

---

## §7 · The 20 ideal cards in this world

Every ideal card is a view of one page. The field-by-field mapping is in [05 §13](05-THE-WORK-OBJECT.md). In short:

- **Silence cards** come from the clock, when an expected-by date passes: `i1`, `i2`, `i3`, `i4`, `f3`, `f4`, `b2`, `b3`, `c1`, `h1`, `l1`.
- **Conflict cards** come from claims that contradict each other: `p1`.
- **Deadline cards** come from a stated date on the page: `f1`, `c2`.
- **Decision cards** come from a loop the founder owes: `f2`, `b1`, `s1`.
- **Question cards** come from a page that needs a fact only the founder has: `h1`, `i4`, `s2`.
- **Done items** are pages closed with evidence: `i6`.

---

## §8 · Rules that do not change

- **The architecture is GeniOS-008.** This completes it; it does not replace it.
- **The LLM is the expert. Code is memory, calculator and checker.** The founder's rule: "a company runs on patterns and analytics, not formulas".
- **A human makes a goal real.** GeniOS may use a proposed goal while reasoning, clearly labelled, but only the founder approves it.
- **Beside, not instead.** The new path runs beside the old one and is switched on per tenant with a row. It switches off the same way.
- **No names in this repo.** It is public. Private data stays in the private local copy.
