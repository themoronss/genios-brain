# 01 · Navigation: the grouping

**Written for:** Harsh.

**Branch:** `rohit/nav-grouping` in `genios-brain-dashbaord`. These commits matter here:
- `db422da`: the sidebar;
- `690def6`: the Expertise page;
- `0ab7b03`: Screen under Intelligence;
- `f137d41`: Goals unlocked; the page is in `03-GOALS`.

**Files:** `src/components/layout/sidebar.tsx` and `src/app/dashboard/expertise/page.tsx`. `src/app/dashboard/moments/page.tsx` is covered in `02-DASHBOARD-HOME/04-SCREEN.md`.

**Rule from Rohit:**
- Keep every existing page. Only the grouping and the labels change.
- One item left the menu: "Needs review". Its page still opens at `/dashboard/review`.

---

## 1 · Before → after

**Before** (`origin/main`, which is also what is live):
```
Dashboard
Cards
Intelligence ▸ Brain · Graph · Context
Sources ▸ Tools · Uploads · Memory · Manual updates (locked) · Custom MCP (locked)
Needs review
Expertise
Agents
Workspace ▸ Governance ▸ Audit · … · Reports · Policies · Approvals │ Team │ Capture policy │ Documentation
Desktop ▸ Moments · My capture · Devices
```

**After** (`rohit/nav-grouping`):
```
Dashboard
Intelligence            — what the brain concluded
  ├ Cards               /dashboard/cards
  ├ Goals               /dashboard/goals                             (unlocked 22 Oct — 03-GOALS/01-GOALS-PAGE.md)
  └ Screen              /dashboard/moments                           (was Desktop ▸ Moments)
Agents        🔒        /dashboard/agents                            (locked 22 Oct — the page shows a locked panel)

Context                 — what the brain knows and reads
  Graph                 /dashboard/graph                             (was Intelligence ▸ Graph)
  Company               /dashboard/context                           (was Intelligence ▸ Context)
  Domains
    ├ Expertise         /dashboard/expertise                         (was a top-level item)
    └ Brain             /dashboard/brain                             (was Intelligence ▸ Brain)
  Sources
    ├ Tools             /dashboard/integrations
    ├ Custom tool  🔒    locked: "until connector controls are available"
    ├ Resources         /dashboard/resources                         (renamed from Uploads)
    ├ Memory            /dashboard/integrations/memory
    ├ Database     🔒    locked: "for the current release"
    ├ Manual updates 🔒  locked: "for the current release"
    └ Custom source 🔒   locked: "until connector controls are available" (was Custom MCP)

Workspace               — unchanged
Desktop                 ▸ My capture · Devices                       (Moments moved to Intelligence ▸ Screen)
```

Screenshot: `sidebar.png` (taken before Agents was locked; `agents-locked.png` shows the locked item and page).

**Why this shape (Rohit's words, condensed):**
- **Intelligence** = conclusions: cards and goals, plus Screen, because what the screen catches becomes instant actions or cards.
- **Context** = everything the brain knows: the graph, the company, the domain expertise and its brains (organisational, behavioural, adaptive, persona — "these belong to domain expertise"), and the sources it reads.
- "Needs review" left the menu. Cards is the one inbox.

## 2 · How the sidebar is built

`sidebar.tsx` holds the data; the render code did not change.

```ts
type NavChild = { label: string; href?: string; dot?: string; locked?: boolean; lockedNote?: string };
type NavItem  = { label: string; href: string; icon: LucideIcon; children?: NavChild[] };
type NavSection = { title: string; items: NavItem[] };
```

- **`navSections`:**
  - owners and admins get `[ untitled (Dashboard · Intelligence · Agents), Context, Workspace, desktopSection ]`.
  - **Intelligence starts open:** `useState({ Intelligence: true })`. Cards is the page people come for.
- **Locked items** (22 Oct, for Agents): a top-level item with `locked: true` renders its icon, its label, a lock and "Locked", with `lockedNote` as the tooltip — no link.
- **Locked children:** a child with `locked: true` has no `href`. It renders a lock icon and a "Locked" tag, and shows `lockedNote` as its tooltip. To unlock one, give it an `href` and drop `locked`.
- **`memberNavSections`:** a member seat sees `Cards · Screen · Sources (My accounts · Resources) · Desktop`. "Needs review" was removed there too, and Uploads became Resources.
  - `/dashboard/moments` is already in `MEMBER_ROUTES` (`lib/session-context.tsx`), so a member can open Screen.
- **Active state:** `activeChildHref` picks the longest matching child. Opening `/dashboard/integrations/memory` lights Memory, not Tools.

## 3 · Expertise page: locked domains and what they unlock (`690def6`)

Rohit: *"Expertise mein hi jo locked wali cheezein hain, wo bhi dikhani hain, taaki unko pata chal sake ki kya-kya unlock kiya ja sakta hai."*

**What the page shows now**, from `src/app/dashboard/expertise/page.tsx`:
- **Header chips:** "N active" and "N locked", where locked = domains not active + "coming next".
- **Order:** active domains first, then locked ones.
- **Locked domain cards:**
  - each shows a **Locked** chip, and its button reads "See what it unlocks";
  - the detail panel says "Locked for this workspace" and shows a box headed "Locked — this is what you would unlock";
  - a **Request to unlock** button calls `POST /v1/expertise/request`. The brain already records it in `domain_requests`.
- **Coming next:** `COMING_NEXT` = Marketing and Project, each with one line of what it covers and its own "Request it" button.
- **New icons:** `founder_office → Rocket`, `marketing → Megaphone`, `project → KanbanSquare`.

Screenshots: `expertise.png` and `expertise-locked.png`. Both were taken against a stand-in brain, so they show which domains are active and which are locked. They were taken before Screen moved under Intelligence, so their sidebar does not show Screen yet; `sidebar.png` shows the final nav.

### ⚠ Brain gap — this page tells the truth only after a brain fix

`GET /v1/expertise/domains` returns `"active": True` for **every** authored domain.

- **Where:** `genios_engine/api/expertise_routes.py::_corpus_domains`, line ~72, comment `# authored + present in the corpus`.
- **Real per-workspace activation:** `platform/l3_activation.activated_domains(engine, org_id)` (line ~271). The admin routes are the only thing that reads it.
- **Today:** Sales and Support show as Active for Rohit's workspace, though they are off for it.

**Fix (small, brain side):**
- In `/v1/expertise/domains`, set `active = domain_id in activated_domains(engine, org)` for the caller's org.
- Keep `authored: true` as a separate field if anything else reads it.
- The dashboard needs no change: it already reads `active`.

## 4 · Not changed, on purpose

- The pages behind each link: `Brain`, `Graph`, `Company`, `Integrations`, `Resources` and `Memory` are as they were.
- Workspace and its Governance children.
- The Agents page, until 22 Oct. Rohit first said "Agents wala section abhi ke liye chhod do"; on 22 Oct: *"Agent wale part ko lock kar do"*. Now the menu item is locked and `/dashboard/agents` shows a locked panel; agents already connected stay connected. See `../05-SCREEN/README.md` §7 and `agents-locked.png`.

## 5 · Merge notes

- `sidebar.tsx` dropped the `ClipboardCheck` import together with `reviewItem`, and added `Network` and `Building2`.
- If `main` has gained nav items since `6ddc4db`, put them in the matching group. Do not restore the old flat list.
