# 07.1 · GeniOS desktop — the whole codebase, commented out

**Written for:** Harsh and every coding agent who wires this design into the real app (`Extension/` in the dashboard repo). Rohit, to keep the reference in one place.

**What this is:** every source file of the agreed dummy, 49 files and 8,364 lines, as it stood on 22 Oct 2026. The dummy itself lives outside every GeniOS repo, at `~/Downloads/Artifacts/Product/genios-desktop-dummy`.

**It does not run from here, on purpose.** Every line starts with `// ` (Python lines with `# `), so nothing in this folder can be imported, built or executed by accident. How it was built, the design, the theme and how it connects are in [`02-HOW-IT-WAS-BUILT.md`](02-HOW-IT-WAS-BUILT.md).

**To get the files back** (into an empty folder, never into a repo by accident):

```bash
mkdir -p /tmp/genios-desktop && cd /tmp/genios-desktop
python3 - "<path to this file>" <<'PY'
import os, re, sys
text = open(sys.argv[1]).read()
for path, body in re.findall(r"^#### `([^`]+)`\n\n```[a-z]*\n(.*?)\n```", text, re.S | re.M):
    pre = "# " if path.endswith(".py") else "// "
    lines = [l[len(pre):] if l.startswith(pre) else l[len(pre.rstrip()):] for l in body.split("\n")]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    open(path, "w").write("\n".join(lines) + "\n")
PY
npm install && npm run brain & npm run dev   # then http://localhost:5199/stage.html
```

Images (`public/`: `genios-logo.png`, `genios-icon-512.png`, `apple-touch-icon.png`, `favicon-32.png`, `favicon-64.png`, `favicon.ico`) are binary, so they are not inside this file: they are in [`assets/`](assets/) next to it. Screenshots of every screen are in [`screens/`](screens/). The app icon is the white G of the GeniOS wordmark on the logo's own dark sky and green horizon.

## Contents

- **1 · The project** — How the app is built and run.
  - `package.json` (26 lines)
  - `vite.config.ts` (21 lines)
  - `tsconfig.json` (21 lines)
  - `README.md` (15 lines)
- **2 · The pages** — Three windows' worth of HTML: the drop-and-menu desktop, the panel, the popups.
  - `stage.html` (15 lines)
  - `desktop.html` (15 lines)
  - `lane.html` (15 lines)
- **3 · The drop and the menu (the agreed design)** — The card that drops from the menu bar, the GeniOS menu (Card · Goals · Pending · Account), and how real cards become what they show.
  - `src/stage/Drop.tsx` (183 lines)
  - `src/stage/MenuPanel.tsx` (317 lines)
  - `src/stage/live.ts` (123 lines)
  - `src/stage/sample.ts` (192 lines)
  - `src/stage/Stage.tsx` (155 lines)
  - `src/stage/main.tsx` (12 lines)
  - `src/stage/stage.css` (1182 lines)
- **4 · The look every part shares** — Tokens, fonts, the small parts.
  - `src/desktop/theme.css` (684 lines)
  - `src/desktop/ui.tsx` (329 lines)
- **5 · Reading and pressing cards** — The brain's routes, the web's card reader, the refusal sentences, Today's grouping.
  - `src/desktop/api.ts` (377 lines)
  - `src/desktop/cards.ts` (68 lines)
  - `src/lib/card-read.ts` (599 lines)
  - `src/lib/card-shape.ts` (176 lines)
  - `src/desktop/refusals.ts` (41 lines)
  - `src/desktop/rows.ts` (86 lines)
- **6 · The panel (Today, an opened card, This week, History, sign-in)** — The ⌘⇧G panel built on the same parts.
  - `src/desktop/main.tsx` (21 lines)
  - `src/desktop/DesktopAdvisor.tsx` (444 lines)
  - `src/desktop/panel.css` (15 lines)
  - `src/desktop/Header.tsx` (133 lines)
  - `src/desktop/Header.css` (63 lines)
  - `src/desktop/TodayView.tsx` (111 lines)
  - `src/desktop/CardRow.tsx` (77 lines)
  - `src/desktop/ScreenRow.tsx` (144 lines)
  - `src/desktop/rows.css` (189 lines)
  - `src/desktop/CardDetail.tsx` (305 lines)
  - `src/desktop/ActionBar.tsx` (234 lines)
  - `src/desktop/detail.css` (272 lines)
  - `src/desktop/SetupCard.tsx` (245 lines)
  - `src/desktop/SetupCard.css` (98 lines)
  - `src/desktop/WeekView.tsx` (129 lines)
  - `src/desktop/HistoryView.tsx` (128 lines)
  - `src/desktop/SignIn.tsx` (127 lines)
  - `src/desktop/screens.css` (159 lines)
- **7 · The popups (the lane window)** — The Rust core pushes one popup at a time; this draws it.
  - `src/lane/main.tsx` (11 lines)
  - `src/lane/Lane.tsx` (193 lines)
  - `src/lane/lane.css` (103 lines)
- **8 · Dummy only: the stand-ins** — Not part of the app: Tauri and the brain, replaced so the dummy runs in a browser.
  - `mock/tauri/core.ts` (161 lines)
  - `mock/tauri/event.ts` (23 lines)
  - `mock/tauri/window.ts` (17 lines)
  - `mock/tauri/http.ts` (12 lines)
  - `mock/brain.py` (297 lines)
  - `src/vite-env.d.ts` (1 lines)

---

## 1 · The project

How the app is built and run.

#### `package.json`

```json
// {
//   "name": "genios-desktop-dummy",
//   "private": true,
//   "version": "0.0.1",
//   "type": "module",
//   "description": "Clickable dummy of the GeniOS Mac panel and popups, with sample cards. Independent of the GeniOS repos.",
//   "scripts": {
//     "brain": "python3 mock/brain.py 8032",
//     "dev": "vite",
//     "build": "tsc --noEmit && vite build"
//   },
//   "dependencies": {
//     "@fontsource-variable/inter": "^5.1.0",
//     "@fontsource/inter": "5.1.0",
//     "lucide-react": "0.468.0",
//     "react": "19.2.0",
//     "react-dom": "19.2.0"
//   },
//   "devDependencies": {
//     "@types/react": "19.2.2",
//     "@types/react-dom": "19.2.2",
//     "@vitejs/plugin-react": "4.3.4",
//     "typescript": "5.7.3",
//     "vite": "6.4.1"
//   }
// }
```

#### `vite.config.ts`

```ts
// // The dummy: the panel (desktop.html) and the popups (lane.html) in a plain browser, with Tauri
// // replaced by mock/tauri and the brain by mock/brain.py (sample cards on :8032).
// import { defineConfig } from "vite";
// import react from "@vitejs/plugin-react";
// import { resolve } from "node:path";
//
// const at = (p: string) => resolve(__dirname, p);
//
// export default defineConfig({
//   plugins: [react()],
//   css: { postcss: { plugins: [] } },
//   server: { port: 5199, strictPort: true },
//   resolve: {
//     alias: [
//       { find: "@tauri-apps/api/core", replacement: at("mock/tauri/core.ts") },
//       { find: "@tauri-apps/api/event", replacement: at("mock/tauri/event.ts") },
//       { find: "@tauri-apps/api/window", replacement: at("mock/tauri/window.ts") },
//       { find: "@tauri-apps/plugin-http", replacement: at("mock/tauri/http.ts") },
//     ],
//   },
// });
```

#### `tsconfig.json`

```json
// {
//   "compilerOptions": {
//     "target": "ES2020",
//     "lib": ["ES2020", "DOM", "DOM.Iterable"],
//     "strict": true,
//     "skipLibCheck": true,
//     "module": "ESNext",
//     "moduleResolution": "Bundler",
//     "isolatedModules": true,
//     "noEmit": true,
//     "jsx": "react-jsx",
//     "baseUrl": ".",
//     "paths": {
//       "@tauri-apps/api/core": ["mock/tauri/core.ts"],
//       "@tauri-apps/api/event": ["mock/tauri/event.ts"],
//       "@tauri-apps/api/window": ["mock/tauri/window.ts"],
//       "@tauri-apps/plugin-http": ["mock/tauri/http.ts"]
//     }
//   },
//   "include": ["src", "mock/tauri"]
// }
```

#### `README.md`

```md
// # GeniOS desktop — dummy
//
// A clickable dummy of the Mac panel (⌘⇧G) and its popups, with sample cards. It is **independent**:
// nothing here is read by, or written to, any GeniOS repo. The real app changes only after the dummy
// is agreed, and then from one write-up in the GeniOS folder.
//
// ```bash
// npm install
// npm run brain      # sample cards on :8032 (one terminal)
// npm run dev        # the panel on :5199 (another)
// ```
//
// - Panel: http://localhost:5199/desktop.html  (`?s=setup`, `?s=empty`, `?s=offline`, `?s=signedout`)
// - Popups: http://localhost:5199/lane.html?toast=advice  (`urgent`, `reminder`, `proposal`, `brief`)
// - Sample cards come back after presses with: `curl -X POST localhost:8032/__reset`
```

---

## 2 · The pages

Three windows' worth of HTML: the drop-and-menu desktop, the panel, the popups.

#### `stage.html`

```html
// <!doctype html>
// <html lang="en">
//   <head>
//     <meta charset="UTF-8" />
//     <meta name="viewport" content="width=device-width, initial-scale=1.0" />
//     <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />
//     <link rel="icon" type="image/png" sizes="64x64" href="/favicon-64.png" />
//     <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
//     <title>GeniOS — drop and menu</title>
//   </head>
//   <body class="stage">
//     <div id="root"></div>
//     <script type="module" src="/src/stage/main.tsx"></script>
//   </body>
// </html>
```

#### `desktop.html`

```html
// <!doctype html>
// <html lang="en">
//   <head>
//     <meta charset="UTF-8" />
//     <meta name="viewport" content="width=device-width, initial-scale=1.0" />
//     <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />
//     <link rel="icon" type="image/png" sizes="64x64" href="/favicon-64.png" />
//     <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
//     <title>GeniOS</title>
//   </head>
//   <body class="panel">
//     <div id="root"></div>
//     <script type="module" src="/src/desktop/main.tsx"></script>
//   </body>
// </html>
```

#### `lane.html`

```html
// <!doctype html>
// <html lang="en">
//   <head>
//     <meta charset="UTF-8" />
//     <meta name="viewport" content="width=device-width, initial-scale=1.0" />
//     <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />
//     <link rel="icon" type="image/png" sizes="64x64" href="/favicon-64.png" />
//     <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
//     <title>GeniOS lane</title>
//   </head>
//   <body>
//     <div id="root"></div>
//     <script type="module" src="/src/lane/main.tsx"></script>
//   </body>
// </html>
```

---

## 3 · The drop and the menu (the agreed design)

The card that drops from the menu bar, the GeniOS menu (Card · Goals · Pending · Account), and how real cards become what they show.

#### `src/stage/Drop.tsx`

```tsx
// // One card of intelligence — the same card whether it drops from the menu bar or sits in the
// // GeniOS menu: where it came from, the call to action, why in one or two lines, the goal it moves,
// // and the four buttons (Done · Delegate · Later · Feedback), each opening right inside the card.
// import { useState } from "react";
// import { Bot, ChevronRight, Lock, Send, Target, Users, X } from "lucide-react";
// import type { DeskItem } from "./sample";
//
// type Panel = "delegate" | "later" | "feedback";
//
// const PEOPLE = [
//   { name: "Harsh", detail: "harsh@example.com · admin" },
//   { name: "Divya Raman", detail: "divya@example.com · member" },
// ];
// const AGENTS = [{ name: "Inbox agent", detail: "Drafts the reply; sends after you approve" }];
// const REASONS = ["Not relevant to me", "A fact is wrong", "Right card, wrong time"];
//
// export function Drop({
//   item,
//   variant = "drop",
//   onDone,
//   onShowMore,
//   onOpen,
//   onClose,
// }: {
//   item: DeskItem;
//   variant?: "drop" | "menu";
//   onDone?: () => void;
//   onShowMore?: () => void;
//   onOpen?: () => void;
//   onClose?: () => void;
// }) {
//   const [panel, setPanel] = useState<Panel | null>(null);
//   const [who, setWho] = useState<"people" | "agent">("people");
//   const [reason, setReason] = useState<string | null>(null);
//   const [note, setNote] = useState<string | null>(null);
//   const Icon = item.icon;
//   const toggle = (p: Panel) => setPanel((cur) => (cur === p ? null : p));
//   const after = (text: string) => {
//     setPanel(null);
//     setNote(text);
//   };
//
//   return (
//     <section className={`drop${variant === "menu" ? " in-menu" : ""}`} aria-label={`GeniOS: ${item.subject}`} data-drop={item.id}>
//       <span className="drop-glow" aria-hidden />
//       <span className="drop-side">
//         <span className="drop-icon" aria-hidden>
//           <Icon size={22} strokeWidth={2.2} />
//         </span>
//         <span className="drop-when">{item.when}</span>
//       </span>
//       <div className="drop-body">
//         <div className="drop-main" onClick={onOpen}>
//           <p className="drop-tags">
//             <span>
//               {item.source.tool} · {item.source.how}
//             </span>
//             <span>{item.kind}</span>
//             {item.importance !== "Normal" && (
//               <span className="drop-hot">
//                 <i aria-hidden />
//                 {item.importance}
//               </span>
//             )}
//           </p>
//           <h3 className="drop-subject">{item.subject}</h3>
//           <p className="drop-why">{item.why}</p>
//           {item.goal && (
//             <p className="drop-goal">
//               <Target size={13} strokeWidth={2} aria-hidden />
//               <span>
//                 {item.goal.name} · {item.goal.effect}
//               </span>
//             </p>
//           )}
//         </div>
//
//         {note ? (
//           <p className="drop-note">
//             {note}
//             <button type="button" onClick={() => setNote(null)}>
//               Undo
//             </button>
//           </p>
//         ) : (
//           <div className="drop-actions">
//             <button
//               type="button"
//               className="drop-btn main"
//               onClick={() => {
//                 after("Marked done");
//                 onDone?.();
//               }}
//             >
//               {item.primary}
//             </button>
//             <button type="button" className="drop-btn" aria-expanded={panel === "delegate"} onClick={() => toggle("delegate")}>
//               Delegate
//             </button>
//             <button type="button" className="drop-btn" aria-expanded={panel === "later"} onClick={() => toggle("later")}>
//               Later
//             </button>
//             <button type="button" className="drop-btn" aria-expanded={panel === "feedback"} onClick={() => toggle("feedback")}>
//               Feedback
//             </button>
//             {variant === "drop" && (
//               <button type="button" className="drop-more" onClick={onShowMore}>
//                 Show more <ChevronRight size={14} strokeWidth={2} aria-hidden />
//               </button>
//             )}
//           </div>
//         )}
//
//         {panel === "later" && (
//           <div className="drop-panel" aria-label="Later">
//             <span className="drop-panel-title">Bring it back</span>
//             <div className="drop-chips">
//               {["In 4 hours", "Tomorrow, 9:00", "In 3 days"].map((o) => (
//                 <button key={o} type="button" onClick={() => after(`Put off · ${o}`)}>
//                   {o}
//                 </button>
//               ))}
//               <button type="button" onClick={() => after("Put off · Mon 27 Oct, 9:00")}>
//                 Pick a day
//               </button>
//             </div>
//           </div>
//         )}
//
//         {panel === "delegate" && (
//           <div className="drop-panel" aria-label="Delegate">
//             <div className="drop-seg">
//               <button type="button" aria-pressed={who === "people"} onClick={() => setWho("people")}>
//                 <Users size={13} strokeWidth={2} aria-hidden /> A person
//               </button>
//               <button type="button" aria-pressed={who === "agent"} onClick={() => setWho("agent")}>
//                 <Bot size={13} strokeWidth={2} aria-hidden /> An agent
//               </button>
//             </div>
//             <ul className="drop-people">
//               {(who === "people" ? PEOPLE : AGENTS).map((p) => (
//                 <li key={p.name}>
//                   <span>
//                     {p.name}
//                     <small>{p.detail}</small>
//                   </span>
//                   <button type="button" disabled>
//                     <Lock size={12} strokeWidth={2} aria-hidden /> {who === "people" ? "Hand over" : "Ask it"}
//                   </button>
//                 </li>
//               ))}
//             </ul>
//             <span className="drop-panel-note">Handing over goes live with the next brain update.</span>
//           </div>
//         )}
//
//         {panel === "feedback" && (
//           <div className="drop-panel" aria-label="Feedback">
//             <span className="drop-panel-title">What is off?</span>
//             <div className="drop-chips">
//               {REASONS.map((r) => (
//                 <button key={r} type="button" aria-pressed={reason === r} onClick={() => setReason(r)}>
//                   {r}
//                 </button>
//               ))}
//             </div>
//             <div className="drop-say">
//               <input placeholder="In your words: what is wrong, what it should be" aria-label="Your words" />
//               <button type="button" disabled={!reason} onClick={() => after("Feedback sent · GeniOS reads it next time")}>
//                 <Send size={13} strokeWidth={2} aria-hidden /> Send
//               </button>
//             </div>
//           </div>
//         )}
//       </div>
//       {onClose && (
//         <button type="button" className="drop-close" aria-label="Dismiss" onClick={onClose}>
//           <X size={14} strokeWidth={2} />
//         </button>
//       )}
//     </section>
//   );
// }
```

#### `src/stage/MenuPanel.tsx`

```tsx
// // The GeniOS menu, under its icon in the menu bar. Close on the left; Card · Goals · Pending and
// // your account on the right. Card is the same card that dropped, with its details below; Goals are
// // your active goals, numbered, each with its own count and the cards that move it; Pending is
// // everything left today, screen and tools together, numbered, most pressing first.
// import { useState } from "react";
// import { BellOff, Calendar, ChevronDown, ChevronRight, Globe, Laptop, LogOut, Mail, Monitor, Plug, Slack, Target, X } from "lucide-react";
// import { Popover, Status, Tabs } from "../desktop/ui";
// import { Drop } from "./Drop";
// import type { DeskItem, Goal } from "./sample";
//
// export type MenuView = "card" | "goals" | "pending";
//
// const ORDER = { Now: 0, High: 1, Normal: 2 } as const;
//
// function CardView({ item, onClose }: { item: DeskItem; onClose: () => void }) {
//   const q = item.quote;
//   return (
//     <div className="m-card" aria-label="Card">
//       <Drop item={item} variant="menu" onClose={onClose} />
//       {q && (
//         <section className="m-why" aria-label="Why it came up">
//           <span className="m-label">Why it came up</span>
//           <p className="m-where">
//             {q.where} · {q.when}
//           </p>
//           <p className="m-said">
//             <span>{q.said}</span>“{q.text}”
//           </p>
//           <p className="m-caught">{q.caught}</p>
//         </section>
//       )}
//       <div className="m-facts">
//         <div>
//           <span className="m-label">Approach</span>
//           <p>{item.approach}</p>
//         </div>
//         <div>
//           <span className="m-label">Goal</span>
//           <p>{item.goal ? item.goal.name : "Not linked yet"}</p>
//         </div>
//         <div>
//           <span className="m-label">Importance</span>
//           <p>{item.importance === "Now" ? "Today" : item.importance === "High" ? "This week" : "Any time"}</p>
//         </div>
//       </div>
//     </div>
//   );
// }
//
// function GoalCard({ n, goal, cards, onPick }: { n: number; goal: Goal; cards: DeskItem[]; onPick: (item: DeskItem) => void }) {
//   const [open, setOpen] = useState(false);
//   return (
//     <article className="m-goal" aria-label={goal.name}>
//       <div className="m-goal-head">
//         <span className="m-num">{n}</span>
//         <div>
//           <h3>{goal.name}</h3>
//           <p className="m-goal-by">
//             {goal.progress}% done · {goal.by}
//           </p>
//         </div>
//         <Status tone={goal.status === "On track" ? "ink" : "accent"}>{goal.status}</Status>
//       </div>
//       <span className="m-goal-bar">
//         <span style={{ width: `${goal.progress}%` }} />
//       </span>
//       <p className="m-goal-now">{goal.now}</p>
//       <div className="m-funnel" aria-label="The count">
//         {goal.funnel.map((f) => (
//           <div key={f.label} className="m-step">
//             <b>{f.value}</b>
//             <span className="m-step-label">{f.label}</span>
//             <span className="m-step-bar">
//               <span style={{ width: `${Math.max(f.share * 100, f.share > 0 ? 3 : 0)}%` }} />
//             </span>
//             <span className="m-step-note">{f.note ?? ""}</span>
//           </div>
//         ))}
//       </div>
//       <p className="m-goal-meaning">{goal.meaning}</p>
//       <button type="button" className="m-goal-cards" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
//         <Target size={14} strokeWidth={2} aria-hidden />
//         {cards.length} card{cards.length === 1 ? "" : "s"} for this goal
//         <ChevronDown className="dx-chev" size={14} strokeWidth={2} aria-hidden />
//       </button>
//       {open && (
//         <ol className="m-goal-list">
//           {cards.map((c, i) => (
//             <li key={c.id}>
//               <button type="button" onClick={() => onPick(c)}>
//                 <span className="m-num small">{i + 1}</span>
//                 <span className="m-goal-card">
//                   {c.subject}
//                   <small>
//                     {c.source.tool} · {c.kind}
//                     {c.importance !== "Normal" ? ` · ${c.importance}` : ""}
//                   </small>
//                 </span>
//                 <ChevronRight size={14} strokeWidth={2} aria-hidden />
//               </button>
//             </li>
//           ))}
//         </ol>
//       )}
//     </article>
//   );
// }
//
// function PendingView({ items, onPick }: { items: DeskItem[]; onPick: (item: DeskItem) => void }) {
//   const sorted = [...items].sort((a, b) => ORDER[a.importance] - ORDER[b.importance]);
//   return (
//     <ol className="m-pending" aria-label="Pending">
//       {sorted.map((item, i) => (
//         <li key={item.id}>
//           <button type="button" className="m-row" onClick={() => onPick(item)}>
//             <span className="m-num">{i + 1}</span>
//             <span className="m-row-main">
//               <span className="m-row-tags">
//                 <span>
//                   {item.source.tool} · {item.source.how}
//                 </span>
//                 <span>{item.kind}</span>
//                 {item.importance !== "Normal" && (
//                   <span className="hot">
//                     <i aria-hidden />
//                     {item.importance}
//                   </span>
//                 )}
//                 <small>{item.when}</small>
//               </span>
//               <span className="m-row-subject">{item.subject}</span>
//               <span className="m-row-why">{item.why}</span>
//               {item.goal && (
//                 <span className="m-row-goal">
//                   <Target size={12} strokeWidth={2} aria-hidden />
//                   {item.goal.name}
//                 </span>
//               )}
//             </span>
//           </button>
//         </li>
//       ))}
//     </ol>
//   );
// }
//
// type Open = "code" | "api" | null;
//
// function Account() {
//   const [open, setOpen] = useState(false);
//   const [more, setMore] = useState<Open>(null);
//   const [silent, setSilent] = useState(false);
//   const [paused, setPaused] = useState(false);
//   const close = () => {
//     setOpen(false);
//     setMore(null);
//   };
//   return (
//     <Popover
//       label="Account"
//       open={open}
//       onClose={close}
//       trigger={
//         <button type="button" className="m-avatar" aria-label="Account" aria-expanded={open} onClick={() => (open ? close() : setOpen(true))}>
//           R
//         </button>
//       }
//     >
//       <div className="m-acc">
//         <div className="m-acc-head">
//           <span className="m-avatar big">R</span>
//           <div>
//             <b>Rohit</b>
//             <span>rohit@thegenios.com</span>
//             <span>Owner · GeniOS workspace</span>
//           </div>
//         </div>
//
//         <div className="m-acc-sec">
//           <span className="m-label">This Mac</span>
//           <div className="m-acc-row">
//             <Laptop size={15} strokeWidth={2} aria-hidden />
//             <span>
//               Signed in with a device code
//               <small>Approved on the website, 12 Oct</small>
//             </span>
//             <button type="button" className="m-link" onClick={() => setMore(more === "code" ? null : "code")}>
//               {more === "code" ? "Hide" : "New code"}
//             </button>
//           </div>
//           {more === "code" && (
//             <div className="m-acc-code">
//               <span className="m-code">KQ7D-M3XW</span>
//               <small>Open brain.thegenios.com/device and type this code to link another device.</small>
//             </div>
//           )}
//         </div>
//
//         <div className="m-acc-sec">
//           <span className="m-label">Screen reading</span>
//           <div className="m-acc-row">
//             <Monitor size={15} strokeWidth={2} aria-hidden />
//             <span>
//               {paused ? "Paused for 15 min" : "Reading · WhatsApp"}
//               <small>Accessibility allowed · capture on for your seat</small>
//             </span>
//             <button type="button" className="m-link" onClick={() => setPaused((p) => !p)}>
//               {paused ? "Resume" : "Pause"}
//             </button>
//           </div>
//           <div className="m-acc-row">
//             <BellOff size={15} strokeWidth={2} aria-hidden />
//             <span>Silence popups</span>
//             <button type="button" className={`m-switch${silent ? " on" : ""}`} role="switch" aria-checked={silent} aria-label="Silence popups" onClick={() => setSilent((v) => !v)}>
//               <i />
//             </button>
//           </div>
//         </div>
//
//         <div className="m-acc-sec">
//           <span className="m-label">Connected tools</span>
//           <div className="m-tools">
//             <span className="on">
//               <Mail size={13} strokeWidth={2} aria-hidden /> Gmail
//             </span>
//             <span className="on">
//               <Calendar size={13} strokeWidth={2} aria-hidden /> Calendar
//             </span>
//             <span>
//               <Slack size={13} strokeWidth={2} aria-hidden /> Slack · connect
//             </span>
//           </div>
//         </div>
//
//         <div className="m-acc-sec">
//           <span className="m-label">Server &amp; API</span>
//           <div className="m-acc-row">
//             <Plug size={15} strokeWidth={2} aria-hidden />
//             <span>
//               api.thegenios.com
//               <small>Connected · signed requests from this Mac</small>
//             </span>
//             <button type="button" className="m-link" onClick={() => setMore(more === "api" ? null : "api")}>
//               {more === "api" ? "Hide" : "Change"}
//             </button>
//           </div>
//           {more === "api" && (
//             <div className="m-acc-api">
//               <input className="dx-input" defaultValue="https://api.thegenios.com" aria-label="Server address" />
//               <input className="dx-input" placeholder="API key (optional)" aria-label="API key" />
//             </div>
//           )}
//         </div>
//
//         <div className="m-acc-foot">
//           <button type="button" className="m-link">
//             <Globe size={14} strokeWidth={2} aria-hidden /> Open GeniOS on the web
//           </button>
//           <button type="button" className="m-link">
//             <LogOut size={14} strokeWidth={2} aria-hidden /> Sign out
//           </button>
//         </div>
//       </div>
//     </Popover>
//   );
// }
//
// export function MenuPanel({
//   view,
//   onView,
//   item,
//   goals,
//   pending,
//   onPick,
//   onClose,
// }: {
//   view: MenuView;
//   onView: (v: MenuView) => void;
//   item: DeskItem;
//   goals: Goal[];
//   pending: DeskItem[];
//   onPick: (item: DeskItem) => void;
//   onClose: () => void;
// }) {
//   return (
//     <section className="menu" aria-label="GeniOS menu">
//       <header className="menu-head">
//         <button type="button" className="m-close" aria-label="Close" onClick={onClose}>
//           <X size={16} strokeWidth={2} />
//         </button>
//         <span className="menu-fill" />
//         <Tabs
//           label="GeniOS"
//           value={view}
//           onChange={onView}
//           options={[
//             { id: "card", label: "Card" },
//             { id: "goals", label: `Goals ${goals.length}` },
//             { id: "pending", label: `Pending ${pending.length}` },
//           ]}
//         />
//         <Account />
//       </header>
//       <div className="menu-body">
//         {view === "card" && <CardView item={item} onClose={() => onView("pending")} />}
//         {view === "goals" && (
//           <div className="m-goals" aria-label="Goals">
//             {goals.map((g, i) => (
//               <GoalCard key={g.id} n={i + 1} goal={g} cards={pending.filter((p) => p.goal?.name === g.name)} onPick={onPick} />
//             ))}
//           </div>
//         )}
//         {view === "pending" && <PendingView items={pending} onPick={onPick} />}
//       </div>
//     </section>
//   );
// }
```

#### `src/stage/live.ts`

```ts
// // From the brain's real cards and the screen's real follow-ups to the drop and the menu.
// //
// // The dummy draws `sample.ts`. In the app the same `DeskItem` is built here, from what the panel
// // already reads: a card through the web's reader (`cards.ts` → `readCard` / `ownCard`) and a screen
// // follow-up from the Rust core (`followups_open`). Nothing here fetches; it only reads.
// import { AlarmClock, CalendarCheck, CircleHelp, Hourglass, MessageCircle, ShieldAlert, type LucideIcon } from "lucide-react";
// import type { Followup } from "../desktop/api";
// import type { DeskCard } from "../desktop/cards";
// import { screenApp } from "../desktop/ScreenRow";
// import type { DeskItem, Importance } from "./sample";
//
// const CARD_KIND: Record<DeskCard["lane"], DeskItem["kind"]> = {
//   decision: "Decision",
//   conflict: "Decision",
//   question: "Question",
//   waiting: "Waiting",
// };
//
// const FOLLOWUP_KIND: Record<string, DeskItem["kind"]> = {
//   ask: "Ask",
//   my_promise: "Follow-up",
//   their_promise: "Waiting",
//   deadline: "Deadline",
//   risk: "Deadline",
//   next_step: "Follow-up",
// };
//
// const KIND_ICON: Record<DeskItem["kind"], LucideIcon> = {
//   "Follow-up": MessageCircle,
//   Deadline: AlarmClock,
//   Decision: CalendarCheck,
//   Ask: MessageCircle,
//   Question: CircleHelp,
//   Waiting: Hourglass,
// };
//
// /** Critical → Now (today), high → High (this week), the rest → Normal. */
// export function importanceOf(urgency: DeskCard["urgency"]): Importance {
//   return urgency === "critical" ? "Now" : urgency === "high" ? "High" : "Normal";
// }
//
// const DAY = { weekday: "short", day: "numeric", month: "short" } as const;
//
// function when(iso: string | null | undefined, now: number): string {
//   const d = iso ? new Date(iso) : null;
//   if (!d || Number.isNaN(d.getTime())) return "";
//   const m = Math.round((now - d.getTime()) / 60_000);
//   if (m < 1) return "just now";
//   if (m < 60) return `${m} min ago`;
//   if (m < 60 * 24) return `${Math.round(m / 60)} h ago`;
//   return d.toLocaleDateString([], DAY);
// }
//
// /** A brain card, as the drop and the menu show it. */
// export function cardItem(card: DeskCard): DeskItem {
//   const kind = CARD_KIND[card.lane];
//   const tool = card.tools[0] ?? { tool: "Gmail", how: "mail thread" };
//   const said = card.why.find((w) => w.kind === "said");
//   const asks = card.lane === "question" && !card.answered;
//   return {
//     id: card.id,
//     kind,
//     icon: KIND_ICON[kind],
//     source: { tool: tool.tool, how: tool.how },
//     importance: importanceOf(card.urgency),
//     subject: card.headline,
//     why: (asks ? card.question?.because : undefined) ?? card.whyNow ?? card.description,
//     approach: card.how ?? card.todo?.line ?? (asks ? "Answer in one line" : "Open the card"),
//     // The brain links no card to a goal yet (06-CARDS C1/C8): the menu says "Not linked yet".
//     goal: null,
//     quote: said
//       ? {
//           text: said.text.replace(/^“|”$/g, ""),
//           who: card.who ?? tool.tool,
//           when: said.when ?? "",
//           where: `In your mail · ${tool.tool}${card.who ? ` · thread with ${card.who}` : ""}`,
//           said: card.who ? `${card.who.split(" ")[0]} wrote` : "They wrote",
//           caught: card.whyNow ?? card.description,
//         }
//       : undefined,
//     when: card.age,
//     primary: asks ? "Answer" : "Done",
//   };
// }
//
// /** A follow-up the screen caught, as the drop and the menu show it. */
// export function followupItem(f: Followup, now = Date.now()): DeskItem {
//   const kind = FOLLOWUP_KIND[f.kind] ?? "Follow-up";
//   const app = screenApp(f);
//   const due = f.due_at ? new Date(f.due_at) : null;
//   const dueText = due && !Number.isNaN(due.getTime()) ? `due ${due.toLocaleDateString([], DAY)}` : "";
//   const late = Boolean(due && due.getTime() < now);
//   const mine = f.kind === "my_promise";
//   return {
//     id: f.id,
//     kind,
//     icon: f.kind === "risk" ? ShieldAlert : KIND_ICON[kind],
//     source: { tool: app, how: "screen" },
//     importance: late ? "Now" : due && due.getTime() - now < 3 * 86_400_000 ? "High" : "Normal",
//     subject: f.text,
//     why: [mine ? "You said you would" : f.who ? `${f.who} is waiting on this` : "Caught on your screen", dueText].filter(Boolean).join(", ") + ".",
//     approach: mine ? "Do it, then mark it done" : "Reply where it was asked",
//     goal: null,
//     quote: f.quote
//       ? {
//           text: f.quote,
//           who: mine ? `You${f.who ? `, to ${f.who}` : ""}` : (f.who ?? app),
//           when: when(f.created_at, now),
//           where: `On your screen · ${app}${f.who ? ` · with ${f.who}` : ""}`,
//           said: mine ? "You wrote" : f.who ? `${f.who.split(" ")[0]} wrote` : "It says",
//           caught: [mine ? "Your promise" : "Waiting on you", dueText].filter(Boolean).join(", ") + ".",
//         }
//       : undefined,
//     when: when(f.created_at, now),
//     primary: "Done",
//   };
// }
//
// /** Pending: every open card and screen item, most pressing first (Now, then High, then the rest). */
// export function pendingItems(cards: DeskCard[], followups: Followup[], now = Date.now()): DeskItem[] {
//   const order: Record<Importance, number> = { Now: 0, High: 1, Normal: 2 };
//   return [...cards.map(cardItem), ...followups.map((f) => followupItem(f, now))].sort((a, b) => order[a.importance] - order[b.importance]);
// }
```

#### `src/stage/sample.ts`

```ts
// // Sample data for the drop and the menu — a dummy, not anyone's real cards.
// import { AlarmClock, CalendarCheck, MessageCircle, type LucideIcon } from "lucide-react";
//
// export type Importance = "Now" | "High" | "Normal";
//
// export type DeskItem = {
//   id: string;
//   /** What kind of thing it is: the scenario tag. */
//   kind: "Follow-up" | "Deadline" | "Decision" | "Ask" | "Question" | "Waiting";
//   icon: LucideIcon;
//   source: { tool: string; how: string };
//   importance: Importance;
//   /** The call to action: what to do, as one line. */
//   subject: string;
//   /** What to do and why, in one or two lines. */
//   why: string;
//   /** How to go about it. */
//   approach: string;
//   goal: { name: string; effect: string } | null;
//   /** The words it came from: where they were read, who wrote them, and what GeniOS took them to be. */
//   quote?: { text: string; who: string; when: string; where: string; said: string; caught: string };
//   when: string;
//   primary: string;
// };
//
// export const DROPS: DeskItem[] = [
//   {
//     id: "neha-deck",
//     kind: "Follow-up",
//     icon: MessageCircle,
//     source: { tool: "WhatsApp", how: "screen" },
//     importance: "High",
//     subject: "Send Neha the investor deck",
//     why: "You told her you'd send it by Friday. She leads Monday's term-sheet call and needs it before then.",
//     approach: "Reply in the chat with the deck link",
//     goal: { name: "Close the seed round", effect: "Keeps the lead investor warm before the term sheet" },
//     quote: {
//       text: "Will send the deck by Friday",
//       who: "You, to Neha Kapoor",
//       when: "Tue, 6:40 pm",
//       where: "On your screen · WhatsApp · chat with Neha Kapoor",
//       said: "You wrote",
//       caught: "Your promise, due Fri 24 Oct. Nothing has gone to Neha since.",
//     },
//     when: "just now",
//     primary: "Done",
//   },
//   {
//     id: "dpiit",
//     kind: "Deadline",
//     icon: AlarmClock,
//     source: { tool: "startupindia.gov.in", how: "screen" },
//     importance: "Now",
//     subject: "Submit the DPIIT application today",
//     why: "The form closes at 11:59 pm tonight. Recognition unlocks the 80-IAC tax exemption.",
//     approach: "Fill 2 sections, upload the certificate",
//     goal: { name: "Get DPIIT recognition", effect: "The last step left" },
//     quote: {
//       text: "Last date: 22 Oct, 11:59 pm",
//       who: "startupindia.gov.in",
//       when: "today, 8:41 pm",
//       where: "On your screen · Chrome · the DPIIT application form",
//       said: "The page says",
//       caught: "A deadline today. Two sections of your form are still empty.",
//     },
//     when: "2 min ago",
//     primary: "Done",
//   },
//   {
//     id: "evokoa",
//     kind: "Decision",
//     icon: CalendarCheck,
//     source: { tool: "Gmail", how: "mail thread" },
//     importance: "High",
//     subject: "Confirm Thursday 4 pm with Ananya (Evokoa)",
//     why: "She proposed the pilot review slot two days ago and there is no invite yet. Their renewal moves with it.",
//     approach: "Reply, then send the invite",
//     goal: { name: "Convert the Evokoa pilot to paid", effect: "The review decides the renewal" },
//     quote: {
//       text: "Does Thursday 4 pm work for the pilot review?",
//       who: "Ananya Rao, Evokoa",
//       when: "Mon, 4:57 pm",
//       where: "In your mail · Gmail · thread with Ananya Rao",
//       said: "Ananya wrote",
//       caught: "A question waiting on you for two days. No invite has gone out.",
//     },
//     when: "5 min ago",
//     primary: "Done",
//   },
// ];
//
// export const PENDING: DeskItem[] = [
//   ...DROPS,
//   {
//     id: "kiran",
//     kind: "Ask",
//     icon: MessageCircle,
//     source: { tool: "Gmail", how: "screen" },
//     importance: "Normal",
//     subject: "Share the data-room link with Kiran",
//     why: "He asked for it this afternoon to start diligence this week.",
//     approach: "Send the Drive link, view-only",
//     goal: { name: "Close the seed round", effect: "Starts diligence" },
//     when: "1 h ago",
//     primary: "Done",
//   },
//   {
//     id: "campus",
//     kind: "Question",
//     icon: MessageCircle,
//     source: { tool: "Gmail", how: "mail thread" },
//     importance: "Normal",
//     subject: "Are you incubated on the university's campus?",
//     why: "The seed grant is open only to campus startups, and nothing in your mail says whether you are.",
//     approach: "Answer in one line",
//     goal: null,
//     when: "20 h ago",
//     primary: "Answer",
//   },
//   {
//     id: "dev",
//     kind: "Waiting",
//     icon: MessageCircle,
//     source: { tool: "Gmail", how: "mail thread" },
//     importance: "Normal",
//     subject: "Dev is waiting on the pricing sheet",
//     why: "He asked four weeks ago and nothing has gone out since. GeniOS brings it back if he writes again.",
//     approach: "Nothing to do now",
//     goal: { name: "Convert the Evokoa pilot to paid", effect: "No direct effect" },
//     when: "3 d ago",
//     primary: "Done",
//   },
// ];
//
// export type Goal = {
//   id: string;
//   name: string;
//   status: "On track" | "At risk" | "Behind";
//   by: string;
//   progress: number;
//   /** What is happening, in one line. */
//   now: string;
//   /** The goal's own count, step by step. `share` draws the bar (0–1); `note` says what it means. */
//   funnel: { value: string; label: string; share: number; note?: string }[];
//   /** The same numbers as one plain sentence. */
//   meaning: string;
// };
//
// export const GOALS: Goal[] = [
//   {
//     id: "seed",
//     name: "Close the seed round",
//     status: "On track",
//     by: "by 30 Nov",
//     progress: 62,
//     now: "Term sheet call with Neha on Monday; 2 funds in diligence",
//     funnel: [
//       { value: "14", label: "Investors reached", share: 1 },
//       { value: "6", label: "Replied", share: 6 / 14, note: "43%" },
//       { value: "3", label: "Met you", share: 3 / 14, note: "21%" },
//     ],
//     meaning: "Of the 14 investors you wrote to, 6 replied and 3 took a meeting.",
//   },
//   {
//     id: "evokoa",
//     name: "Convert the Evokoa pilot to paid",
//     status: "At risk",
//     by: "by 15 Nov",
//     progress: 40,
//     now: "Pilot review not yet scheduled; renewal waits on it",
//     funnel: [
//       { value: "6", label: "Mails to Evokoa", share: 1 },
//       { value: "2", label: "Replies", share: 2 / 6, note: "33%" },
//       { value: "1", label: "Meeting held", share: 1 / 6, note: "17%" },
//     ],
//     meaning: "You wrote to Evokoa 6 times; they replied twice and met you once.",
//   },
//   {
//     id: "dpiit",
//     name: "Get DPIIT recognition",
//     status: "Behind",
//     by: "today",
//     progress: 67,
//     now: "Two sections empty; the form closes tonight",
//     funnel: [
//       { value: "4", label: "Of 6 sections filled", share: 4 / 6, note: "67%" },
//       { value: "0", label: "Of 1 certificate uploaded", share: 0, note: "0%" },
//       { value: "1", label: "Day left", share: 1 / 30, note: "today" },
//     ],
//     meaning: "4 of the 6 sections are filled; the certificate is not uploaded yet.",
//   },
// ];
```

#### `src/stage/Stage.tsx`

```tsx
// // A Mac desktop for the dummy: the menu bar with the GeniOS icon, an app window where the thing was
// // said, the drop under the menu bar on the right, and the GeniOS menu under its icon.
// // ?board=1 lays the three drops and the menu's three views side by side to compare.
// import { useEffect, useState } from "react";
// import { BatteryFull, Search, Wifi } from "lucide-react";
// import { Drop } from "./Drop";
// import { MenuPanel, type MenuView } from "./MenuPanel";
// import { DROPS, GOALS, PENDING, type DeskItem } from "./sample";
//
// const board = new URLSearchParams(location.search).has("board");
//
// function AppWindow({ item }: { item: DeskItem }) {
//   return (
//     <div className="win" aria-hidden>
//       <div className="win-bar">
//         <i />
//         <i />
//         <i />
//         <span>{item.source.tool}</span>
//       </div>
//       <div className="win-body">
//         <div className="win-line short" />
//         <div className="win-line" />
//         <div className="win-line mid" />
//         {item.quote && <div className="win-said">{item.quote.text}</div>}
//         <div className="win-line" />
//         <div className="win-line short" />
//       </div>
//     </div>
//   );
// }
//
// function Board() {
//   const [views] = useState<MenuView[]>(["card", "goals", "pending"]);
//   return (
//     <div className="board">
//       <section>
//         <h2>Three drops</h2>
//         <div className="board-drops">
//           {DROPS.map((d) => (
//             <Drop key={d.id} item={d} />
//           ))}
//         </div>
//       </section>
//       <section>
//         <h2>The GeniOS menu: Card · Goals · Pending (open a goal's cards in the live page)</h2>
//         <div className="board-menus">
//           {views.map((v) => (
//             <MenuPanel key={v} view={v} onView={() => {}} item={DROPS[0]} goals={GOALS} pending={PENDING} onPick={() => {}} onClose={() => {}} />
//           ))}
//         </div>
//       </section>
//     </div>
//   );
// }
//
// export function Stage() {
//   const [at, setAt] = useState(0);
//   const [drop, setDrop] = useState<DeskItem | null>(null);
//   const [menu, setMenu] = useState<MenuView | null>(null);
//   const [item, setItem] = useState<DeskItem>(DROPS[0]);
//   const [now] = useState(() => new Date());
//
//   // A drop arrives a moment after the screen shows the thing it is about.
//   useEffect(() => {
//     setDrop(null);
//     const t = setTimeout(() => setDrop(DROPS[at]), 700);
//     return () => clearTimeout(t);
//   }, [at]);
//
//   if (board) return <Board />;
//   const shown = drop ?? DROPS[at];
//   const open = (view: MenuView, it: DeskItem = shown) => {
//     setItem(it);
//     setMenu(view);
//     setDrop(null);
//   };
//   return (
//     <div className="desk">
//       <header className="mbar">
//         <span className="mbar-apple"></span>
//         <b>{shown.source.tool === "startupindia.gov.in" ? "Chrome" : shown.source.tool}</b>
//         <span>File</span>
//         <span>Edit</span>
//         <span>View</span>
//         <span>Window</span>
//         <span>Help</span>
//         <span className="mbar-fill" />
//         <Wifi size={15} strokeWidth={2} aria-hidden />
//         <BatteryFull size={17} strokeWidth={2} aria-hidden />
//         <Search size={14} strokeWidth={2} aria-hidden />
//         <button
//           type="button"
//           className={`mbar-genios${menu ? " on" : ""}`}
//           aria-label="GeniOS"
//           onClick={() => (menu ? setMenu(null) : open("pending"))}
//         >
//           G
//         </button>
//         <span>
//           {now.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" })}{" "}
//           {now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
//         </span>
//       </header>
//
//       <AppWindow item={shown} />
//
//       {drop && !menu && (
//         <div className="drop-slot">
//           <Drop
//             item={drop}
//             onShowMore={() => open("card", drop)}
//             onOpen={() => open("pending", drop)}
//             onClose={() => setDrop(null)}
//           />
//         </div>
//       )}
//
//       {menu && (
//         <div className="menu-slot">
//           <MenuPanel
//             view={menu}
//             onView={setMenu}
//             item={item}
//             goals={GOALS}
//             pending={PENDING}
//             onPick={(it) => {
//               setItem(it);
//               setMenu("card");
//             }}
//             onClose={() => setMenu(null)}
//           />
//         </div>
//       )}
//
//       <nav className="dev" aria-label="Dummy controls">
//         <span>Sample data</span>
//         {DROPS.map((d, i) => (
//           <button
//             key={d.id}
//             type="button"
//             aria-pressed={at === i && !menu}
//             onClick={() => {
//               setMenu(null);
//               setAt(i);
//             }}
//           >
//             Drop {i + 1}
//           </button>
//         ))}
//         <a href="?board=1">All side by side</a>
//       </nav>
//     </div>
//   );
// }
```

#### `src/stage/main.tsx`

```tsx
// import { StrictMode } from "react";
// import { createRoot } from "react-dom/client";
// import "../desktop/theme.css";
// import "../desktop/detail.css";
// import "./stage.css";
// import { Stage } from "./Stage";
//
// createRoot(document.getElementById("root")!).render(
//   <StrictMode>
//     <Stage />
//   </StrictMode>,
// );
```

#### `src/stage/stage.css`

```css
// /* The dummy desktop, the drop (black, after Rohit's reference) and the GeniOS menu (light). */
// body.stage {
//   overflow: auto;
// }
//
// .desk {
//   position: relative;
//   /* The page is drawn at 85% (theme.css), so the desktop is 100 / 0.85 of the window tall. */
//   min-height: calc(100vh / 0.85);
//   overflow: hidden;
//   /* A quiet stone wallpaper, so the black card and the white menu read as they will on any desk. */
//   background:
//     radial-gradient(90% 70% at 80% 0%, #f1f1ee 0%, rgba(241, 241, 238, 0) 60%),
//     linear-gradient(180deg, #dcdcd8 0%, #c4c5c0 100%);
// }
//
// /* ---- The menu bar ---- */
// .mbar {
//   position: relative;
//   z-index: 5;
//   display: flex;
//   align-items: center;
//   gap: 18px;
//   height: 30px;
//   padding: 0 14px 0 16px;
//   background: rgba(255, 255, 255, 0.55);
//   backdrop-filter: blur(20px);
//   color: #0b0b0c;
//   font-size: 13.5px;
// }
// .mbar b {
//   font-weight: 560;
// }
// .mbar-apple {
//   font-family: -apple-system, sans-serif;
//   font-size: 16px;
// }
// .mbar-fill {
//   flex: 1;
// }
// .mbar-genios {
//   display: grid;
//   place-items: center;
//   width: 22px;
//   height: 20px;
//   border: 0;
//   border-radius: 5px;
//   background: transparent;
//   color: #0b0b0c;
//   font-size: 12.5px;
//   font-weight: 560;
//   outline: 1.5px solid rgba(11, 11, 12, 0.85);
//   outline-offset: -3px;
// }
// .mbar-genios.on,
// .mbar-genios:hover {
//   background: rgba(0, 0, 0, 0.08);
// }
// .mbar-genios.on {
//   background: #0a0a0b;
//   color: #ffffff;
//   outline-color: #0a0a0b;
// }
//
// /* ---- A plain app window, with the line GeniOS read ---- */
// .win {
//   position: absolute;
//   left: 8%;
//   top: 110px;
//   width: 52%;
//   max-width: 720px;
//   border-radius: 12px;
//   background: #fbfbfc;
//   box-shadow: 0 20px 60px rgba(20, 22, 28, 0.25);
//   overflow: hidden;
// }
// .win-bar {
//   display: flex;
//   align-items: center;
//   gap: 7px;
//   height: 36px;
//   padding: 0 12px;
//   background: #f0f1f4;
//   font-size: 12.5px;
//   color: #5f6572;
// }
// .win-bar i {
//   width: 11px;
//   height: 11px;
//   border-radius: 50%;
//   background: #d9dbe1;
// }
// .win-bar span {
//   margin-left: 10px;
// }
// .win-body {
//   display: grid;
//   gap: 12px;
//   padding: 22px 24px 30px;
// }
// .win-line {
//   height: 10px;
//   border-radius: 5px;
//   background: #e8e9ee;
// }
// .win-line.short {
//   width: 40%;
// }
// .win-line.mid {
//   width: 70%;
// }
// .win-said {
//   justify-self: end;
//   max-width: 70%;
//   padding: 9px 13px;
//   border-radius: 14px 14px 4px 14px;
//   background: #dfeee4;
//   font-size: 13.5px;
//   color: #1d2a22;
//   outline: 2px solid rgba(10, 10, 11, 0.7);
//   outline-offset: 3px;
// }
//
// /* ---- Palette (Rohit, 22 Oct, round 3): black and white first, dark green only as a touch ---- */
// body.stage {
//   --g-deep: #0a0a0b;
//   --g-deep-2: #131514;
//   --g-green: #3f8f68;
//   --g-gold: #d9b24c;
//   --g-gold-soft: rgba(217, 178, 76, 0.16);
//   --g-green-deep: #1d5a3e;
//   --g-white: #f7f7f5;
//   --g-white-2: rgba(247, 247, 245, 0.68);
//   --g-white-3: rgba(247, 247, 245, 0.46);
//   --g-veil: rgba(247, 247, 245, 0.07);
//   --g-rule: rgba(247, 247, 245, 0.14);
//   /* the light parts: white, black ink, the same green as the one accent */
//   --dx-page: #ffffff;
//   --dx-card: #ffffff;
//   --dx-inset: #f5f5f4;
//   --dx-inset-2: #ebebea;
//   --dx-ink: #0b0b0c;
//   --dx-ink-2: #2a2b2c;
//   --dx-mist: #6b6c6e;
//   --dx-faint: #9c9d9f;
//   --dx-line: rgba(0, 0, 0, 0.08);
//   --dx-line-strong: rgba(0, 0, 0, 0.14);
//   --dx-accent: #1d5a3e;
//   --dx-accent-soft: rgba(29, 90, 62, 0.08);
//   --dx-on-ink: #ffffff;
//   --dx-hover: rgba(0, 0, 0, 0.04);
//   --dx-shadow-1: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 8px rgba(0, 0, 0, 0.04);
//   --dx-shadow-2: 0 1px 2px rgba(0, 0, 0, 0.06), 0 10px 24px rgba(0, 0, 0, 0.08);
//   --dx-focus: 0 0 0 2px #ffffff, 0 0 0 4px rgba(11, 11, 12, 0.5);
// }
//
// /* ---- The card (dropped, or in the menu) ---- */
// .drop-slot {
//   position: absolute;
//   z-index: 6;
//   top: 30px;
//   right: 14px;
//   animation: drop-in 0.42s cubic-bezier(0.16, 1, 0.3, 1);
// }
// @keyframes drop-in {
//   from {
//     transform: translateY(-110%);
//     opacity: 0.4;
//   }
// }
// .drop {
//   position: relative;
//   display: flex;
//   gap: 14px;
//   width: 480px;
//   padding: 18px 20px 18px 18px;
//   overflow: hidden;
//   border-radius: 6px 6px 26px 26px;
//   background: var(--g-deep);
//   color: var(--g-white);
//   box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06) inset, 0 24px 50px rgba(0, 0, 0, 0.4);
// }
// .drop.in-menu {
//   width: auto;
//   border-radius: 18px;
//   box-shadow: 0 10px 30px rgba(13, 28, 20, 0.28);
// }
// .drop-glow {
//   position: absolute;
//   inset: 0;
//   pointer-events: none;
//   background:
//     radial-gradient(60% 55% at 0% 0%, rgba(217, 178, 76, 0.13), rgba(217, 178, 76, 0) 70%),
//     radial-gradient(60% 85% at 100% 120%, rgba(29, 90, 62, 0.55), rgba(29, 90, 62, 0) 72%),
//     linear-gradient(165deg, var(--g-deep) 40%, var(--g-deep-2));
// }
// .drop-side {
//   position: relative;
//   flex: none;
//   display: grid;
//   justify-items: center;
//   align-content: start;
//   gap: 8px;
//   width: 52px;
// }
// .drop-icon {
//   display: grid;
//   place-items: center;
//   width: 48px;
//   height: 48px;
//   border-radius: 15px;
//   color: #1d5a3e;
//   background: linear-gradient(160deg, #ffffff, #e9e6dc);
//   box-shadow: inset 0 -1px 0 rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(217, 178, 76, 0.35), 0 6px 16px rgba(0, 0, 0, 0.4);
// }
// .drop-when {
//   font-size: 12px;
//   line-height: 1.2;
//   text-align: center;
//   color: var(--g-white-3);
// }
// .drop-body {
//   position: relative;
//   flex: 1;
//   min-width: 0;
//   display: grid;
//   gap: 10px;
// }
// .drop-main {
//   display: grid;
//   gap: 6px;
//   padding-right: 18px;
//   cursor: pointer;
// }
// .drop.in-menu .drop-main {
//   cursor: default;
// }
// .drop-tags {
//   display: flex;
//   flex-wrap: wrap;
//   align-items: center;
//   gap: 5px;
//   font-size: 12px;
//   color: var(--g-white-2);
// }
// .drop-tags > span {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   height: 21px;
//   padding: 0 8px;
//   border-radius: 6px;
//   background: var(--g-veil);
// }
// .drop-tags .drop-hot {
//   color: var(--g-gold);
// }
// .drop-tags .drop-hot i {
//   width: 6px;
//   height: 6px;
//   border-radius: 50%;
//   background: var(--g-gold);
// }
// .drop-subject {
//   font-size: 17px;
//   font-weight: 560;
//   line-height: 1.3;
//   letter-spacing: -0.01em;
// }
// .drop-why {
//   font-size: 13.5px;
//   line-height: 1.45;
//   color: var(--g-white-2);
// }
// .drop-goal {
//   display: flex;
//   align-items: flex-start;
//   gap: 6px;
//   font-size: 12.5px;
//   line-height: 1.4;
//   color: var(--g-white-2);
// }
// .drop-goal svg {
//   flex: none;
//   margin-top: 2px;
//   color: var(--g-gold);
// }
// .drop-actions {
//   display: flex;
//   align-items: center;
//   gap: 6px;
// }
// .drop-btn {
//   height: 30px;
//   padding: 0 12px;
//   border: 1px solid var(--g-rule);
//   border-radius: 9px;
//   background: var(--g-veil);
//   color: var(--g-white);
//   font-size: 12.5px;
// }
// .drop-btn.main {
//   border-color: transparent;
//   background: var(--g-white);
//   color: var(--g-deep);
// }
// .drop-btn[aria-expanded="true"] {
//   border-color: var(--g-gold);
//   color: var(--g-gold);
//   background: var(--g-gold-soft);
// }
// .drop-btn:hover {
//   filter: brightness(1.12);
// }
// .drop-more {
//   display: inline-flex;
//   align-items: center;
//   gap: 2px;
//   margin-left: auto;
//   border: 0;
//   background: none;
//   color: var(--g-white-2);
//   font-size: 12.5px;
//   white-space: nowrap;
// }
// .drop-more:hover {
//   color: var(--g-white);
// }
// .drop-note {
//   display: flex;
//   align-items: center;
//   gap: 10px;
//   font-size: 13px;
//   color: var(--g-white);
// }
// .drop-note button {
//   border: 0;
//   background: none;
//   color: var(--g-white);
//   text-decoration: underline;
//   text-underline-offset: 3px;
//   font-size: 13px;
// }
// .drop-panel {
//   display: grid;
//   gap: 9px;
//   padding: 11px;
//   border-radius: 12px;
//   background: rgba(245, 241, 230, 0.06);
//   border: 1px solid var(--g-rule);
//   animation: dx-rise 0.16s cubic-bezier(0.16, 1, 0.3, 1);
// }
// .drop-panel-title {
//   font-size: 12.5px;
//   color: var(--g-white);
// }
// .drop-panel-note {
//   font-size: 12px;
//   color: var(--g-white-3);
// }
// .drop-chips {
//   display: flex;
//   flex-wrap: wrap;
//   gap: 6px;
// }
// .drop-chips button,
// .drop-say button {
//   height: 28px;
//   padding: 0 10px;
//   border: 1px solid var(--g-rule);
//   border-radius: 8px;
//   background: transparent;
//   color: var(--g-white);
//   font-size: 12.5px;
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
// }
// .drop-chips button:hover {
//   border-color: var(--g-white-2);
// }
// .drop-chips button[aria-pressed="true"] {
//   background: var(--g-gold);
//   border-color: var(--g-gold);
//   color: var(--g-deep);
// }
// .drop-say {
//   display: flex;
//   gap: 6px;
// }
// .drop-say input {
//   flex: 1;
//   min-width: 0;
//   height: 30px;
//   padding: 0 10px;
//   border: 1px solid var(--g-rule);
//   border-radius: 8px;
//   background: rgba(0, 0, 0, 0.2);
//   color: var(--g-white);
//   font: inherit;
//   font-size: 12.5px;
// }
// .drop-say input::placeholder {
//   color: var(--g-white-3);
// }
// .drop-say button:not(:disabled) {
//   background: var(--g-white);
//   color: var(--g-deep);
//   border-color: transparent;
// }
// .drop-say button:disabled {
//   opacity: 0.45;
// }
// .drop-seg {
//   display: flex;
//   gap: 2px;
//   padding: 2px;
//   border-radius: 9px;
//   background: rgba(0, 0, 0, 0.25);
// }
// .drop-seg button {
//   flex: 1;
//   display: inline-flex;
//   align-items: center;
//   justify-content: center;
//   gap: 6px;
//   height: 27px;
//   border: 0;
//   border-radius: 7px;
//   background: transparent;
//   color: var(--g-white-2);
//   font-size: 12.5px;
// }
// .drop-seg button[aria-pressed="true"] {
//   background: var(--g-white);
//   color: var(--g-deep);
// }
// .drop-people {
//   list-style: none;
//   padding: 0;
//   display: grid;
// }
// .drop-people li {
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   gap: 10px;
//   padding: 7px 2px;
//   font-size: 13px;
// }
// .drop-people li + li {
//   border-top: 1px solid var(--g-rule);
// }
// .drop-people li > span {
//   display: grid;
//   min-width: 0;
// }
// .drop-people small {
//   font-size: 12px;
//   color: var(--g-white-3);
// }
// .drop-people button {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   height: 26px;
//   padding: 0 9px;
//   border: 1px solid var(--g-rule);
//   border-radius: 7px;
//   background: transparent;
//   color: var(--g-white-3);
//   font-size: 12px;
// }
// .drop-close {
//   position: absolute;
//   top: 10px;
//   right: 10px;
//   display: grid;
//   place-items: center;
//   width: 24px;
//   height: 24px;
//   border: 0;
//   border-radius: 7px;
//   background: var(--g-veil);
//   color: var(--g-white-2);
// }
// .drop-close:hover {
//   background: rgba(245, 241, 230, 0.16);
//   color: var(--g-white);
// }
//
// /* ---- The GeniOS menu ---- */
// .menu-slot {
//   position: absolute;
//   z-index: 6;
//   top: 36px;
//   right: 100px;
//   animation: dx-rise 0.18s cubic-bezier(0.16, 1, 0.3, 1);
// }
// .menu {
//   width: 440px;
//   max-height: 700px;
//   display: flex;
//   flex-direction: column;
//   overflow: hidden;
//   border-radius: 16px;
//   background: var(--dx-page);
//   border: 1px solid var(--dx-line-strong);
//   box-shadow: 0 2px 6px rgba(13, 28, 20, 0.08), 0 24px 60px rgba(13, 28, 20, 0.3);
// }
// .menu-head {
//   display: flex;
//   align-items: center;
//   gap: 8px;
//   padding: 10px 10px 10px 10px;
//   border-bottom: 1px solid var(--dx-line);
// }
// .menu-fill {
//   flex: 1;
// }
// .m-close {
//   display: grid;
//   place-items: center;
//   width: 28px;
//   height: 28px;
//   border: 0;
//   border-radius: 8px;
//   background: transparent;
//   color: var(--dx-mist);
// }
// .m-close:hover {
//   background: var(--dx-hover);
//   color: var(--dx-ink);
// }
// .m-avatar {
//   display: grid;
//   place-items: center;
//   width: 30px;
//   height: 30px;
//   border: 0;
//   border-radius: 50%;
//   background: var(--g-deep);
//   color: var(--g-gold);
//   font-size: 13px;
//   flex: none;
// }
// .m-avatar[aria-expanded="true"] {
//   box-shadow: 0 0 0 2px #ffffff, 0 0 0 4px var(--g-gold);
// }
// .m-account {
//   display: grid;
//   gap: 2px;
//   padding: 8px 9px 6px;
//   font-size: 13px;
// }
// .m-account b {
//   font-weight: 560;
// }
// .m-account span {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .menu-body {
//   flex: 1;
//   min-height: 0;
//   overflow-y: auto;
//   padding: 12px;
// }
//
// .m-label {
//   font-size: 12px;
//   letter-spacing: 0.04em;
//   text-transform: uppercase;
//   color: var(--dx-mist);
// }
// .m-card {
//   display: grid;
//   gap: 10px;
// }
// .m-why {
//   display: grid;
//   gap: 5px;
//   padding: 12px 14px;
//   border-radius: 14px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line);
//   box-shadow: var(--dx-shadow-1);
// }
// .m-where {
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .m-said {
//   display: grid;
//   gap: 2px;
//   padding: 9px 11px;
//   border-left: 3px solid var(--g-gold);
//   border-radius: 4px 10px 10px 4px;
//   background: var(--dx-inset);
//   font-size: 14px;
//   color: var(--dx-ink);
// }
// .m-said span {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .m-caught {
//   font-size: 13px;
//   color: var(--dx-ink-2);
// }
// /* Approach · Goal · Importance: three lines, one each — label on the left, the one-liner on the right. */
// .m-facts {
//   display: grid;
//   padding: 2px 14px;
//   border-radius: 14px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line);
//   box-shadow: var(--dx-shadow-1);
// }
// .m-facts > div {
//   display: grid;
//   grid-template-columns: 96px minmax(0, 1fr);
//   align-items: center;
//   gap: 10px;
//   min-height: 42px;
// }
// .m-facts > div + div {
//   border-top: 1px solid var(--dx-line);
// }
// .m-facts p {
//   display: flex;
//   align-items: center;
//   gap: 7px;
//   min-width: 0;
//   font-size: 13px;
//   color: var(--dx-ink);
//   white-space: nowrap;
//   overflow: hidden;
//   text-overflow: ellipsis;
// }
// .m-dot {
//   flex: none;
//   width: 7px;
//   height: 7px;
//   border-radius: 50%;
//   background: var(--g-gold);
// }
//
// .m-num {
//   flex: none;
//   display: grid;
//   place-items: center;
//   width: 26px;
//   height: 26px;
//   border-radius: 50%;
//   background: var(--g-deep);
//   color: var(--g-white);
//   font-size: 13px;
// }
// .m-num.small {
//   width: 22px;
//   height: 22px;
//   font-size: 12px;
// }
// .m-goals {
//   display: grid;
//   gap: 10px;
// }
// .m-goal {
//   display: grid;
//   gap: 10px;
//   padding: 14px;
//   border-radius: 14px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line);
//   box-shadow: var(--dx-shadow-1);
// }
// .m-goal-head {
//   display: flex;
//   align-items: center;
//   gap: 10px;
// }
// .m-goal-head > div {
//   flex: 1;
//   min-width: 0;
// }
// .m-goal-head h3 {
//   font-size: 14.5px;
//   font-weight: 560;
// }
// .m-goal-by {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .m-goal-bar {
//   display: block;
//   height: 6px;
//   border-radius: 3px;
//   background: var(--dx-inset-2);
//   overflow: hidden;
// }
// .m-goal-bar span {
//   display: block;
//   height: 100%;
//   border-radius: 3px;
//   background: linear-gradient(90deg, #1d5a3e, #2f7a55 85%, var(--g-gold));
// }
// .m-goal-now {
//   font-size: 13px;
//   color: var(--dx-ink-2);
// }
// .m-funnel {
//   display: grid;
//   gap: 9px;
//   padding: 13px 14px;
//   border-radius: 12px;
//   background: var(--g-deep);
//   color: var(--g-white);
//   background-image: radial-gradient(70% 120% at 100% 0%, rgba(29, 90, 62, 0.45), rgba(29, 90, 62, 0) 70%);
// }
// .m-step {
//   display: grid;
//   grid-template-columns: 30px minmax(0, 1fr) 96px 36px;
//   align-items: center;
//   gap: 10px;
// }
// .m-step b {
//   font-size: 19px;
//   line-height: 1;
//   font-weight: 560;
//   color: var(--g-white);
//   font-variant-numeric: tabular-nums;
//   text-align: right;
// }
// .m-step-label {
//   font-size: 12.5px;
//   color: var(--g-white-2);
//   white-space: nowrap;
//   overflow: hidden;
//   text-overflow: ellipsis;
// }
// .m-step-bar {
//   height: 6px;
//   border-radius: 3px;
//   background: rgba(247, 247, 245, 0.1);
//   overflow: hidden;
// }
// .m-step-bar span {
//   display: block;
//   height: 100%;
//   border-radius: 3px;
//   background: linear-gradient(90deg, #b8902a, var(--g-gold));
// }
// .m-step-note {
//   font-size: 12px;
//   color: var(--g-gold);
//   text-align: right;
//   font-variant-numeric: tabular-nums;
// }
// .m-goal-meaning {
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .m-goal-cards {
//   display: flex;
//   align-items: center;
//   gap: 7px;
//   height: 32px;
//   padding: 0 10px;
//   border: 1px solid var(--dx-line-strong);
//   border-radius: 9px;
//   background: var(--dx-card);
//   color: var(--dx-ink);
//   font-size: 13px;
// }
// .m-goal-cards .dx-chev {
//   margin-left: auto;
// }
// .m-goal-cards[aria-expanded="true"] .dx-chev {
//   transform: rotate(180deg);
// }
// .m-goal-list {
//   list-style: none;
//   padding: 0;
//   display: grid;
//   gap: 6px;
// }
// .m-goal-list button {
//   width: 100%;
//   display: flex;
//   align-items: center;
//   gap: 10px;
//   padding: 9px 10px;
//   border: 0;
//   border-radius: 10px;
//   background: var(--dx-inset);
//   text-align: left;
//   color: var(--dx-ink);
// }
// .m-goal-list button:hover {
//   background: var(--dx-inset-2);
// }
// .m-goal-card {
//   flex: 1;
//   display: grid;
//   font-size: 13px;
// }
// .m-goal-card small {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
//
// .m-pending {
//   list-style: none;
//   padding: 0;
//   display: grid;
//   gap: 8px;
// }
// .m-row {
//   width: 100%;
//   display: flex;
//   gap: 11px;
//   padding: 12px 13px;
//   text-align: left;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line);
//   border-radius: 14px;
//   box-shadow: var(--dx-shadow-1);
// }
// .m-row:hover {
//   border-color: var(--dx-line-strong);
//   box-shadow: var(--dx-shadow-2);
// }
// .m-row-main {
//   flex: 1;
//   min-width: 0;
//   display: grid;
//   gap: 5px;
// }
// .m-row-tags {
//   display: flex;
//   flex-wrap: wrap;
//   align-items: center;
//   gap: 5px;
//   font-size: 12px;
//   color: var(--dx-ink-2);
// }
// .m-row-tags > span {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   height: 21px;
//   padding: 0 8px;
//   border-radius: 6px;
//   background: var(--dx-inset);
// }
// .m-row-tags .hot {
//   color: var(--dx-accent);
//   background: var(--dx-accent-soft);
// }
// .m-row-tags .hot i {
//   width: 6px;
//   height: 6px;
//   border-radius: 50%;
//   background: var(--g-gold);
// }
// .m-row-tags small {
//   margin-left: auto;
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .m-row-subject {
//   font-size: 14px;
//   font-weight: 560;
//   line-height: 1.3;
//   color: var(--dx-ink);
// }
// .m-row-why {
//   font-size: 12.5px;
//   line-height: 1.4;
//   color: var(--dx-ink-2);
//   display: -webkit-box;
//   -webkit-box-orient: vertical;
//   -webkit-line-clamp: 2;
//   overflow: hidden;
// }
// .m-row-goal {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   font-size: 12px;
//   color: var(--dx-accent);
// }
// .m-row-goal svg {
//   color: #b8902a;
// }
//
// /* ---- Dummy controls ---- */
// .dev {
//   position: fixed;
//   left: 14px;
//   bottom: 14px;
//   z-index: 9;
//   display: flex;
//   align-items: center;
//   gap: 6px;
//   padding: 6px;
//   border-radius: 10px;
//   background: rgba(255, 255, 255, 0.85);
//   box-shadow: var(--dx-shadow-2);
//   font-size: 12.5px;
// }
// .dev > span {
//   padding: 0 6px;
//   color: var(--dx-mist);
// }
// .dev button,
// .dev a {
//   height: 28px;
//   padding: 0 10px;
//   border: 1px solid var(--dx-line-strong);
//   border-radius: 7px;
//   background: var(--dx-card);
//   color: var(--dx-ink);
//   font-size: 12.5px;
//   display: inline-flex;
//   align-items: center;
//   text-decoration: none;
// }
// .dev button[aria-pressed="true"] {
//   background: var(--dx-ink);
//   color: var(--dx-on-ink);
// }
//
// /* ---- Side by side ---- */
// .board {
//   min-height: 100vh;
//   display: grid;
//   gap: 28px;
//   padding: 28px;
//   background: #e9eaee;
// }
// .board h2 {
//   font-size: 15px;
//   font-weight: 400;
//   color: var(--dx-mist);
//   margin-bottom: 12px;
// }
// .board-drops {
//   display: flex;
//   flex-wrap: wrap;
//   gap: 18px;
//   align-items: flex-start;
// }
// .board-menus {
//   display: flex;
//   flex-wrap: wrap;
//   gap: 18px;
//   align-items: flex-start;
// }
// .board .menu {
//   max-height: none;
// }
//
// /* Luxury, professional: tabs as a black pill on white; quiet tracked labels. */
// .menu .dx-tabs {
//   background: var(--dx-inset);
// }
// .menu .dx-tabs button[aria-selected="true"] {
//   background: var(--g-deep);
//   color: #ffffff;
//   box-shadow: none;
// }
// .menu .m-label {
//   letter-spacing: 0.08em;
// }
// .menu {
//   box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.04), 0 2px 6px rgba(0, 0, 0, 0.06), 0 28px 70px rgba(0, 0, 0, 0.28);
// }
//
// /* The account: who is signed in, and the settings the app has today. */
// .menu-head .dx-pop {
//   max-width: 360px;
//   padding: 0;
// }
// .m-acc {
//   width: 340px;
//   display: grid;
// }
// .m-acc-head {
//   display: flex;
//   align-items: center;
//   gap: 12px;
//   padding: 14px;
//   border-bottom: 1px solid var(--dx-line);
// }
// .m-avatar.big {
//   width: 40px;
//   height: 40px;
//   font-size: 16px;
// }
// .m-acc-head > div {
//   display: grid;
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .m-acc-head b {
//   font-size: 14px;
//   font-weight: 560;
//   color: var(--dx-ink);
// }
// .m-acc-sec {
//   display: grid;
//   gap: 8px;
//   padding: 12px 14px;
//   border-bottom: 1px solid var(--dx-line);
// }
// .m-acc-row {
//   display: flex;
//   align-items: center;
//   gap: 10px;
//   font-size: 13px;
//   color: var(--dx-ink);
// }
// .m-acc-row > svg {
//   flex: none;
//   color: var(--dx-mist);
// }
// .m-acc-row > span {
//   flex: 1;
//   min-width: 0;
//   display: grid;
// }
// .m-acc-row small {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .m-link {
//   display: inline-flex;
//   align-items: center;
//   gap: 6px;
//   padding: 0;
//   border: 0;
//   background: none;
//   font-size: 12.5px;
//   color: var(--dx-ink);
//   text-decoration: underline;
//   text-decoration-color: var(--dx-line-strong);
//   text-underline-offset: 3px;
// }
// .m-link:hover {
//   text-decoration-color: currentColor;
// }
// .m-acc-code {
//   display: grid;
//   gap: 4px;
//   padding: 10px 12px;
//   border-radius: 10px;
//   background: var(--g-deep);
//   color: var(--g-white-2);
//   font-size: 12px;
// }
// .m-code {
//   font: 560 20px var(--dx-mono);
//   letter-spacing: 0.14em;
//   color: var(--g-gold);
//   user-select: text;
// }
// .m-acc-api {
//   display: grid;
//   gap: 6px;
// }
// .m-switch {
//   position: relative;
//   width: 34px;
//   height: 20px;
//   padding: 0;
//   border: 0;
//   border-radius: 10px;
//   background: var(--dx-inset-2);
//   transition: background 0.15s;
// }
// .m-switch i {
//   position: absolute;
//   top: 2px;
//   left: 2px;
//   width: 16px;
//   height: 16px;
//   border-radius: 50%;
//   background: #ffffff;
//   box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
//   transition: transform 0.15s;
// }
// .m-switch.on {
//   background: var(--g-deep);
// }
// .m-switch.on i {
//   transform: translateX(14px);
// }
// .m-tools {
//   display: flex;
//   flex-wrap: wrap;
//   gap: 6px;
// }
// .m-tools span {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   height: 26px;
//   padding: 0 9px;
//   border-radius: 7px;
//   border: 1px dashed var(--dx-line-strong);
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .m-tools span.on {
//   border-style: solid;
//   color: var(--dx-ink);
// }
// .m-tools span.on::after {
//   content: "";
//   width: 6px;
//   height: 6px;
//   margin-left: 2px;
//   border-radius: 50%;
//   background: #2f7a55;
// }
// .m-acc-foot {
//   display: flex;
//   justify-content: space-between;
//   padding: 12px 14px;
// }
//
// /* The menu sits on the card's own dark ground (black, a faint green glow); the cards on it are white.
//    The tabs read white on it; the card that dropped stays dark, set off by a hairline. */
// .menu {
//   background:
//     radial-gradient(70% 45% at 0% 0%, rgba(217, 178, 76, 0.08), rgba(217, 178, 76, 0) 70%),
//     radial-gradient(80% 50% at 100% 100%, rgba(29, 90, 62, 0.5), rgba(29, 90, 62, 0) 72%),
//     linear-gradient(170deg, #0a0a0b 45%, #121514);
//   border-color: rgba(255, 255, 255, 0.08);
// }
// .menu-head {
//   border-bottom-color: rgba(255, 255, 255, 0.08);
// }
// .menu .m-close {
//   color: rgba(247, 247, 245, 0.7);
// }
// .menu .m-close:hover {
//   background: rgba(247, 247, 245, 0.1);
//   color: #ffffff;
// }
// .menu .dx-tabs {
//   background: rgba(247, 247, 245, 0.08);
// }
// .menu .dx-tabs button {
//   color: rgba(247, 247, 245, 0.7);
// }
// .menu .dx-tabs button:hover {
//   color: #ffffff;
// }
// .menu .dx-tabs button[aria-selected="true"] {
//   background: #ffffff;
//   color: #0b0b0c;
// }
// .menu-head .m-avatar {
//   background: #1a1c1b;
//   box-shadow: 0 0 0 1px rgba(217, 178, 76, 0.45);
// }
// .drop.in-menu {
//   box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1), 0 12px 30px rgba(0, 0, 0, 0.45);
// }
// .menu .m-why,
// .menu .m-facts,
// .menu .m-goal,
// .menu .m-row {
//   border-color: transparent;
//   box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 10px 24px rgba(0, 0, 0, 0.25);
// }
// .menu .m-row:hover {
//   box-shadow: 0 0 0 1px rgba(217, 178, 76, 0.5), 0 12px 28px rgba(0, 0, 0, 0.35);
// }
```

---

## 4 · The look every part shares

Tokens, fonts, the small parts.

#### `src/desktop/theme.css`

```css
// /* GeniOS desktop — the panel's look, in the web dashboard's tokens, light and dark.
//
//    The rules it keeps (Rohit, 22 Oct):
//    - ink and its greys carry state; burgundy only where something needs the founder;
//    - status is a small dot and a word, never a coloured block, edge or badge;
//    - nothing under 12px; labels 12–12.5px, body 13px, subjects 14.5px;
//    - white cards on a light-grey page, light-grey insets inside a card; shadows step down a level;
//    - it follows the Mac's light/dark setting.
//    Class names are `dx-` so nothing here collides with the old panel's `gx-` sheet while both exist.
//
//    Dummy, 22 Oct (Rohit): Inter only — Regular (400) for everything; a heading (a subject line) at 560,
//    just above Medium, and nothing heavier; light theme only; the whole panel about 40% smaller. */
//
// @import "@fontsource-variable/inter";
//
// :root {
//   color-scheme: light;
//   --dx-page: #f4f5f7;
//   --dx-card: #ffffff;
//   --dx-inset: #f4f5f7;
//   --dx-inset-2: #ebecf0;
//   --dx-ink: #14161c;
//   --dx-ink-2: #2b2e38;
//   --dx-mist: #5f6572;
//   --dx-faint: #8b919c;
//   --dx-line: rgba(20, 22, 30, 0.085);
//   --dx-line-strong: rgba(20, 22, 30, 0.14);
//   --dx-accent: #8a2d3b;
//   --dx-accent-soft: rgba(138, 45, 59, 0.08);
//   --dx-on-ink: #ffffff;
//   --dx-hover: rgba(20, 22, 28, 0.045);
//   --dx-press: rgba(20, 22, 28, 0.08);
//   --dx-scrim: rgba(20, 22, 28, 0.2);
//   --dx-shadow-1: 0 1px 2px rgba(20, 22, 28, 0.05), 0 1px 6px rgba(20, 22, 28, 0.035);
//   --dx-shadow-2: 0 1px 2px rgba(20, 22, 28, 0.06), 0 8px 20px rgba(20, 22, 28, 0.08);
//   --dx-shadow-pop: 0 2px 6px rgba(20, 22, 28, 0.08), 0 16px 40px rgba(20, 22, 28, 0.18);
//   --dx-focus: 0 0 0 2px var(--dx-card), 0 0 0 4px rgba(138, 45, 59, 0.5);
//   --dx-font: "Inter Variable", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
//   --dx-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
//   --dx-r-card: 12px;
//   --dx-r-ctl: 8px;
// }
//
// * {
//   box-sizing: border-box;
//   margin: 0;
// }
//
// html,
// body,
// #root {
//   height: 100%;
// }
//
// /* About 40% smaller than the first dummy: the panel takes ~40% less of the screen
//    (330 × 456 instead of 420 × 580) and everything in it is drawn at 85%. */
// html {
//   zoom: 0.85;
// }
// .panel #root {
//   width: 388px;
//   height: 536px;
//   max-height: 100%;
//   margin: 0 auto;
// }
//
// b,
// strong,
// h1,
// h2,
// h3,
// h4 {
//   font-weight: 400;
// }
//
// body {
//   font: 13px/1.45 var(--dx-font);
//   color: var(--dx-ink);
//   /* The window is transparent so the panel can have round corners; the shell paints the page. */
//   background: transparent;
//   -webkit-font-smoothing: antialiased;
//   overflow: hidden;
//   user-select: none;
//   cursor: default;
// }
//
// button,
// input,
// textarea {
//   font: inherit;
//   color: inherit;
// }
//
// button {
//   cursor: pointer;
// }
//
// ::selection {
//   background: var(--dx-accent-soft);
// }
//
// :focus-visible {
//   outline: none;
//   box-shadow: var(--dx-focus);
// }
//
// ::-webkit-scrollbar {
//   width: 10px;
//   height: 10px;
// }
// ::-webkit-scrollbar-track {
//   background: transparent;
// }
// ::-webkit-scrollbar-thumb {
//   background: var(--dx-line-strong);
//   border: 3px solid transparent;
//   border-radius: 999px;
//   background-clip: padding-box;
// }
//
// /* ---- The window ------------------------------------------------------------------------------ */
//
// .dx-shell {
//   position: relative;
//   height: 100%;
//   display: flex;
//   flex-direction: column;
//   background: var(--dx-page);
//   border: 1px solid var(--dx-line-strong);
//   border-radius: 14px;
//   overflow: hidden;
// }
//
// /* Linux without a compositor renders a transparent corner black: a square panel always renders. */
// html[data-os="linux"] body,
// html[data-os="other"] body {
//   background: var(--dx-page);
// }
// html[data-os="linux"] .dx-shell,
// html[data-os="other"] .dx-shell {
//   border: none;
//   border-radius: 0;
// }
//
// .dx-body {
//   flex: 1;
//   min-height: 0;
//   overflow-y: auto;
//   padding: 12px 14px 18px;
//   display: flex;
//   flex-direction: column;
//   gap: 12px;
// }
//
// .dx-selectable {
//   user-select: text;
//   cursor: text;
// }
//
// /* ---- Text ------------------------------------------------------------------------------------ */
//
// .dx-eyebrow {
//   font-size: 12px;
//   font-weight: 400;
//   letter-spacing: 0.06em;
//   text-transform: uppercase;
//   color: var(--dx-mist);
// }
// .dx-eyebrow b {
//   color: var(--dx-ink-2);
//   font-weight: 400;
// }
// .dx-hint {
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .dx-title {
//   font-size: 17px;
//   font-weight: 560;
//   line-height: 1.3;
//   letter-spacing: -0.01em;
//   text-wrap: balance;
// }
// .dx-lead {
//   font-size: 13.5px;
//   line-height: 1.45;
//   color: var(--dx-ink-2);
// }
// .dx-meta {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
//
// /* ---- Surfaces -------------------------------------------------------------------------------- */
//
// .dx-card {
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line);
//   border-radius: var(--dx-r-card);
//   box-shadow: var(--dx-shadow-1);
// }
// .dx-inset {
//   background: var(--dx-inset);
//   border-radius: 10px;
// }
//
// /* ---- Tags, chips, status --------------------------------------------------------------------- */
//
// .dx-tag,
// .dx-chip {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   height: 22px;
//   padding: 0 8px;
//   border-radius: 6px;
//   font-size: 12px;
//   line-height: 1;
//   white-space: nowrap;
//   max-width: 100%;
//   overflow: hidden;
//   text-overflow: ellipsis;
// }
// .dx-tag {
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line-strong);
//   color: var(--dx-mist);
// }
// .dx-tag b {
//   color: var(--dx-ink-2);
//   font-weight: 400;
// }
// .dx-tag svg {
//   flex: none;
//   color: var(--dx-ink-2);
// }
// .dx-chip {
//   background: var(--dx-inset-2);
//   color: var(--dx-ink-2);
//   font-weight: 400;
// }
//
// .dx-status {
//   display: inline-flex;
//   align-items: center;
//   gap: 6px;
//   font-size: 12px;
//   color: var(--dx-ink-2);
//   white-space: nowrap;
// }
// .dx-status i {
//   width: 7px;
//   height: 7px;
//   border-radius: 50%;
//   background: var(--dx-ink);
//   flex: none;
// }
// .dx-status.accent {
//   color: var(--dx-accent);
//   font-weight: 400;
// }
// .dx-status.accent i {
//   background: var(--dx-accent);
// }
// .dx-status.quiet {
//   color: var(--dx-mist);
// }
// .dx-status.quiet i {
//   background: transparent;
//   border: 1.5px solid var(--dx-mist);
// }
//
// /* ---- Controls -------------------------------------------------------------------------------- */
//
// .dx-btn {
//   display: inline-flex;
//   align-items: center;
//   justify-content: center;
//   gap: 6px;
//   height: 32px;
//   padding: 0 12px;
//   border-radius: var(--dx-r-ctl);
//   border: 1px solid transparent;
//   background: transparent;
//   font-size: 13px;
//   font-weight: 400;
//   white-space: nowrap;
//   transition: background 0.12s, opacity 0.12s, border-color 0.12s;
// }
// .dx-btn svg {
//   flex: none;
// }
// .dx-btn.ink {
//   background: var(--dx-ink);
//   color: var(--dx-on-ink);
// }
// .dx-btn.ink:hover:not(:disabled) {
//   opacity: 0.88;
// }
// .dx-btn.line {
//   background: var(--dx-card);
//   border-color: var(--dx-line-strong);
//   color: var(--dx-ink);
// }
// .dx-btn.line:hover:not(:disabled),
// .dx-btn.quiet:hover:not(:disabled) {
//   background: var(--dx-hover);
// }
// .dx-btn.line[aria-expanded="true"] {
//   border-color: var(--dx-ink);
// }
// .dx-btn.quiet {
//   color: var(--dx-ink-2);
// }
// .dx-btn.link {
//   height: auto;
//   padding: 0;
//   border: 0;
//   font-weight: 400;
//   color: var(--dx-ink-2);
//   text-decoration: underline;
//   text-decoration-color: var(--dx-line-strong);
//   text-underline-offset: 3px;
// }
// .dx-btn.link:hover:not(:disabled) {
//   color: var(--dx-ink);
//   text-decoration-color: currentColor;
// }
// .dx-btn.sm {
//   height: 28px;
//   padding: 0 10px;
//   font-size: 12.5px;
// }
// .dx-btn:disabled {
//   opacity: 0.45;
//   cursor: default;
// }
//
// .dx-icon-btn {
//   display: grid;
//   place-items: center;
//   width: 28px;
//   height: 28px;
//   border: 0;
//   border-radius: 7px;
//   background: transparent;
//   color: var(--dx-mist);
//   flex: none;
// }
// .dx-icon-btn:hover:not(:disabled),
// .dx-icon-btn[aria-expanded="true"] {
//   background: var(--dx-hover);
//   color: var(--dx-ink);
// }
//
// .dx-tabs {
//   display: inline-flex;
//   padding: 2px;
//   gap: 2px;
//   border-radius: 9px;
//   background: var(--dx-inset-2);
// }
// .dx-tabs button {
//   height: 26px;
//   padding: 0 10px;
//   border: 0;
//   border-radius: 7px;
//   background: transparent;
//   font-size: 12.5px;
//   font-weight: 400;
//   color: var(--dx-mist);
// }
// .dx-tabs button:hover {
//   color: var(--dx-ink);
// }
// .dx-tabs button[aria-selected="true"] {
//   background: var(--dx-card);
//   color: var(--dx-ink);
//   box-shadow: var(--dx-shadow-1);
// }
//
// .dx-input,
// .dx-textarea {
//   width: 100%;
//   padding: 8px 10px;
//   border-radius: var(--dx-r-ctl);
//   border: 1px solid var(--dx-line-strong);
//   background: var(--dx-card);
//   font-size: 13px;
//   line-height: 1.4;
//   user-select: text;
// }
// .dx-textarea {
//   resize: vertical;
//   min-height: 72px;
// }
// .dx-input::placeholder,
// .dx-textarea::placeholder {
//   color: var(--dx-faint);
// }
// .dx-input:focus,
// .dx-textarea:focus {
//   outline: none;
//   border-color: var(--dx-ink-2);
// }
//
// .dx-choice {
//   height: 28px;
//   padding: 0 10px;
//   border-radius: 7px;
//   border: 1px solid var(--dx-line-strong);
//   background: var(--dx-card);
//   font-size: 12.5px;
//   color: var(--dx-ink-2);
// }
// .dx-choice:hover {
//   border-color: var(--dx-ink-2);
// }
// .dx-choice[aria-pressed="true"] {
//   background: var(--dx-ink);
//   border-color: var(--dx-ink);
//   color: var(--dx-on-ink);
// }
//
// .dx-kbd {
//   font: 12px var(--dx-mono);
//   color: var(--dx-mist);
// }
//
// /* ---- Field rows: a label and one line, inside an inset --------------------------------------- */
//
// .dx-fields {
//   display: flex;
//   flex-direction: column;
//   background: var(--dx-inset);
//   border-radius: 10px;
//   padding: 2px 12px;
// }
// .dx-field {
//   display: grid;
//   grid-template-columns: 84px minmax(0, 1fr);
//   gap: 10px;
//   padding: 8px 0;
//   font-size: 13px;
//   line-height: 1.4;
// }
// .dx-field + .dx-field {
//   border-top: 1px solid var(--dx-line);
// }
// .dx-field > span:first-child {
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .dx-field > span:last-child {
//   color: var(--dx-ink-2);
//   overflow-wrap: anywhere;
// }
// .dx-field.muted > span:last-child {
//   color: var(--dx-mist);
// }
//
// /* ---- Layers over the panel: popover, sheet, toast -------------------------------------------- */
//
// .dx-anchor {
//   position: relative;
//   display: inline-flex;
// }
// .dx-pop {
//   position: absolute;
//   z-index: 50;
//   top: calc(100% + 6px);
//   right: 0;
//   min-width: 220px;
//   max-width: 320px;
//   padding: 5px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line-strong);
//   border-radius: 10px;
//   box-shadow: var(--dx-shadow-pop);
// }
// .dx-pop.up {
//   top: auto;
//   bottom: calc(100% + 6px);
// }
// .dx-pop.left {
//   right: auto;
//   left: 0;
// }
// .dx-pop-item {
//   display: flex;
//   align-items: center;
//   gap: 9px;
//   width: 100%;
//   height: 32px;
//   padding: 0 9px;
//   border: 0;
//   border-radius: 6px;
//   background: transparent;
//   font-size: 13px;
//   color: var(--dx-ink);
//   text-align: left;
// }
// .dx-pop-item svg {
//   flex: none;
//   color: var(--dx-mist);
// }
// .dx-pop-item:hover:not(:disabled),
// .dx-pop-item:focus-visible {
//   background: var(--dx-hover);
// }
// .dx-pop-item:disabled {
//   color: var(--dx-faint);
//   cursor: default;
// }
// .dx-pop-item .dx-kbd {
//   margin-left: auto;
// }
// .dx-pop-sep {
//   height: 1px;
//   margin: 5px 4px;
//   background: var(--dx-line);
// }
// .dx-pop-note {
//   padding: 6px 9px 8px;
//   font-size: 12.5px;
//   line-height: 1.45;
//   color: var(--dx-mist);
// }
//
// .dx-scrim {
//   position: absolute;
//   inset: 0;
//   z-index: 40;
//   background: var(--dx-scrim);
//   animation: dx-fade 0.14s ease-out;
// }
// .dx-sheet {
//   position: absolute;
//   left: 0;
//   right: 0;
//   bottom: 0;
//   z-index: 41;
//   max-height: 82%;
//   overflow-y: auto;
//   padding: 14px;
//   background: var(--dx-card);
//   border-radius: 14px 14px 0 0;
//   box-shadow: var(--dx-shadow-pop);
//   animation: dx-rise 0.18s cubic-bezier(0.16, 1, 0.3, 1);
// }
// .dx-sheet-head {
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   gap: 8px;
//   margin-bottom: 10px;
// }
// .dx-sheet-head h3 {
//   font-size: 14px;
//   font-weight: 400;
// }
//
// .dx-toast {
//   position: absolute;
//   left: 12px;
//   right: 12px;
//   bottom: 46px;
//   z-index: 60;
//   display: flex;
//   align-items: center;
//   gap: 10px;
//   padding: 10px 12px;
//   border-radius: 10px;
//   background: var(--dx-ink);
//   color: var(--dx-on-ink);
//   font-size: 13px;
//   box-shadow: var(--dx-shadow-pop);
//   animation: dx-rise 0.18s cubic-bezier(0.16, 1, 0.3, 1);
// }
// .dx-toast > span {
//   flex: 1;
//   min-width: 0;
// }
// .dx-toast button {
//   border: 0;
//   background: transparent;
//   color: var(--dx-on-ink);
//   font-weight: 400;
//   text-decoration: underline;
//   text-underline-offset: 3px;
//   padding: 0;
// }
//
// /* ---- States ---------------------------------------------------------------------------------- */
//
// .dx-notice {
//   display: flex;
//   gap: 8px;
//   align-items: flex-start;
//   padding: 9px 11px;
//   border-radius: 10px;
//   background: var(--dx-inset);
//   font-size: 12.5px;
//   line-height: 1.45;
//   color: var(--dx-ink-2);
// }
// .dx-notice svg {
//   flex: none;
//   margin-top: 1px;
//   color: var(--dx-accent);
// }
//
// .dx-empty {
//   display: flex;
//   flex-direction: column;
//   align-items: center;
//   text-align: center;
//   gap: 8px;
//   padding: 36px 20px;
// }
// .dx-empty-icon {
//   display: grid;
//   place-items: center;
//   width: 44px;
//   height: 44px;
//   border-radius: 50%;
//   background: var(--dx-inset-2);
//   color: var(--dx-ink-2);
//   margin-bottom: 4px;
// }
// .dx-empty h3 {
//   font-size: 14.5px;
//   font-weight: 400;
// }
// .dx-empty p {
//   font-size: 13px;
//   color: var(--dx-mist);
//   max-width: 280px;
// }
//
// .dx-skel {
//   border-radius: 6px;
//   background: var(--dx-inset-2);
//   animation: dx-pulse 1.4s ease-in-out infinite;
// }
//
// .dx-progress {
//   height: 6px;
//   border-radius: 3px;
//   background: var(--dx-inset-2);
//   overflow: hidden;
// }
// .dx-progress > span {
//   display: block;
//   height: 100%;
//   border-radius: 3px;
//   background: var(--dx-ink);
// }
//
// @keyframes dx-fade {
//   from {
//     opacity: 0;
//   }
// }
// @keyframes dx-rise {
//   from {
//     opacity: 0;
//     transform: translateY(8px);
//   }
// }
// @keyframes dx-pulse {
//   50% {
//     opacity: 0.55;
//   }
// }
//
// @media (prefers-reduced-motion: reduce) {
//   *,
//   *::before,
//   *::after {
//     animation: none !important;
//     transition: none !important;
//   }
// }
```

#### `src/desktop/ui.tsx`

```tsx
// // The small parts every screen of the panel is built from. Styles in theme.css.
// import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
// import {
//   Briefcase,
//   Calendar,
//   Check,
//   Database,
//   Eye,
//   FileText,
//   HardDrive,
//   Linkedin,
//   Mail,
//   MessageCircle,
//   Monitor,
//   Notebook,
//   Send,
//   Slack,
//   Users,
//   X,
//   type LucideIcon,
// } from "lucide-react";
// import "./theme.css";
//
// // ── where a thing came from ────────────────────────────────────────────────────────────────────
//
// const TOOL_ICON: Record<string, LucideIcon> = {
//   Gmail: Mail,
//   Mail,
//   Outlook: Mail,
//   Calendar,
//   "Google Calendar": Calendar,
//   Notion: Notebook,
//   HubSpot: Briefcase,
//   CRM: Database,
//   Drive: HardDrive,
//   "Google Docs": FileText,
//   Notes: FileText,
//   Slack,
//   WhatsApp: MessageCircle,
//   Telegram: Send,
//   LinkedIn: Linkedin,
//   Teams: Users,
//   Screen: Monitor,
//   "GeniOS memory": Database,
// };
//
// export const toolIcon = (tool: string): LucideIcon => TOOL_ICON[tool] ?? Eye;
//
// /** The tool a thing came from and how: “Gmail · mail thread”, “WhatsApp · your screen”. */
// export function Tag({ tool, how, icon }: { tool: string; how?: string; icon?: LucideIcon }) {
//   const Icon = icon ?? toolIcon(tool);
//   return (
//     <span className="dx-tag" title={how ? `${tool} · ${how}` : tool}>
//       <Icon size={13} strokeWidth={2} aria-hidden />
//       <b>{tool}</b>
//       {how && <> · {how}</>}
//     </span>
//   );
// }
//
// export function Chip({ children }: { children: ReactNode }) {
//   return <span className="dx-chip">{children}</span>;
// }
//
// /** A small dot and a word. Burgundy (`accent`) only when it needs the founder. */
// export function Status({ tone = "ink", children }: { tone?: "ink" | "accent" | "quiet"; children: ReactNode }) {
//   return (
//     <span className={`dx-status${tone === "ink" ? "" : ` ${tone}`}`}>
//       <i aria-hidden />
//       {children}
//     </span>
//   );
// }
//
// // ── controls ───────────────────────────────────────────────────────────────────────────────────
//
// type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
//   kind?: "ink" | "line" | "quiet" | "link";
//   small?: boolean;
//   icon?: LucideIcon;
// };
//
// export function Button({ kind = "line", small, icon: Icon, className, children, ...rest }: ButtonProps) {
//   return (
//     <button type="button" className={["dx-btn", kind, small && "sm", className].filter(Boolean).join(" ")} {...rest}>
//       {Icon && <Icon size={small ? 14 : 15} strokeWidth={2} aria-hidden />}
//       {children}
//     </button>
//   );
// }
//
// export function IconButton({ label, icon: Icon, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; icon: LucideIcon }) {
//   return (
//     <button type="button" className="dx-icon-btn" aria-label={label} title={label} {...rest}>
//       <Icon size={16} strokeWidth={2} aria-hidden />
//     </button>
//   );
// }
//
// export function Tabs<T extends string>({
//   value,
//   options,
//   onChange,
//   label,
// }: {
//   value: T;
//   options: { id: T; label: string }[];
//   onChange: (id: T) => void;
//   label: string;
// }) {
//   return (
//     <div className="dx-tabs" role="tablist" aria-label={label}>
//       {options.map((o) => (
//         <button key={o.id} type="button" role="tab" aria-selected={value === o.id} onClick={() => onChange(o.id)}>
//           {o.label}
//         </button>
//       ))}
//     </div>
//   );
// }
//
// /** One of a few answers, pressed in place (Feedback's reasons, a scope). */
// export function Choice({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
//   return (
//     <button type="button" className="dx-choice" aria-pressed={on} onClick={onClick}>
//       {children}
//     </button>
//   );
// }
//
// // ── text in boxes ──────────────────────────────────────────────────────────────────────────────
//
// export function Eyebrow({ children, count }: { children: ReactNode; count?: number }) {
//   return (
//     <span className="dx-eyebrow">
//       {children}
//       {count !== undefined && (
//         <>
//           {" "}
//           · <b>{count}</b>
//         </>
//       )}
//     </span>
//   );
// }
//
// /** Label-and-one-line rows inside a grey inset. */
// export function Fields({ children }: { children: ReactNode }) {
//   return <div className="dx-fields">{children}</div>;
// }
//
// export function Field({ label, children, muted }: { label: string; children: ReactNode; muted?: boolean }) {
//   return (
//     <div className={`dx-field${muted ? " muted" : ""}`}>
//       <span>{label}</span>
//       <span>{children}</span>
//     </div>
//   );
// }
//
// export function Notice({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
//   return (
//     <div className="dx-notice" role="status">
//       <Icon size={15} strokeWidth={2} aria-hidden />
//       <span>{children}</span>
//     </div>
//   );
// }
//
// export function Empty({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children?: ReactNode }) {
//   return (
//     <div className="dx-empty">
//       <span className="dx-empty-icon">
//         <Icon size={20} strokeWidth={1.8} aria-hidden />
//       </span>
//       <h3>{title}</h3>
//       {children}
//     </div>
//   );
// }
//
// export function Skeleton({ width = "100%", height = 12 }: { width?: number | string; height?: number }) {
//   return <span className="dx-skel" style={{ display: "block", width, height }} aria-hidden />;
// }
//
// export function Progress({ value, label }: { value: number; label: string }) {
//   const pct = Math.max(0, Math.min(100, Math.round(value)));
//   return (
//     <div className="dx-progress" role="progressbar" aria-label={label} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
//       <span style={{ width: `${pct}%` }} />
//     </div>
//   );
// }
//
// // ── layers over the panel ──────────────────────────────────────────────────────────────────────
//
// /**
//  * Closes a layer on a click outside it, or on Esc. The Esc goes no further: the panel's own Esc
//  * (back, then hide the window) checks `defaultPrevented` and leaves it alone.
//  */
// export function useDismiss<T extends HTMLElement>(open: boolean, onClose: () => void) {
//   const ref = useRef<T>(null);
//   useEffect(() => {
//     if (!open) return;
//     const down = (e: MouseEvent) => {
//       if (ref.current && !ref.current.contains(e.target as Node)) onClose();
//     };
//     const key = (e: KeyboardEvent) => {
//       if (e.key !== "Escape") return;
//       e.preventDefault();
//       onClose();
//     };
//     document.addEventListener("mousedown", down);
//     document.addEventListener("keydown", key, true);
//     return () => {
//       document.removeEventListener("mousedown", down);
//       document.removeEventListener("keydown", key, true);
//     };
//   }, [open, onClose]);
//   return ref;
// }
//
// /** A small menu under (or, with `up`, above) its trigger. */
// export function Popover({
//   open,
//   onClose,
//   trigger,
//   children,
//   up,
//   left,
//   label,
// }: {
//   open: boolean;
//   onClose: () => void;
//   trigger: ReactNode;
//   children: ReactNode;
//   up?: boolean;
//   left?: boolean;
//   label: string;
// }) {
//   const ref = useDismiss<HTMLDivElement>(open, onClose);
//   return (
//     <div className="dx-anchor" ref={ref}>
//       {trigger}
//       {open && (
//         <div className={["dx-pop", up && "up", left && "left"].filter(Boolean).join(" ")} role="menu" aria-label={label}>
//           {children}
//         </div>
//       )}
//     </div>
//   );
// }
//
// export function MenuItem({
//   icon: Icon,
//   children,
//   onClick,
//   kbd,
//   disabled,
//   checked,
// }: {
//   icon?: LucideIcon;
//   children: ReactNode;
//   onClick?: () => void;
//   kbd?: string;
//   disabled?: boolean;
//   checked?: boolean;
// }) {
//   return (
//     <button
//       type="button"
//       className="dx-pop-item"
//       role={checked === undefined ? "menuitem" : "menuitemcheckbox"}
//       aria-checked={checked}
//       disabled={disabled}
//       onClick={onClick}
//     >
//       {checked !== undefined ? (
//         <span style={{ display: "inline-grid", width: 15, flex: "none" }} aria-hidden>
//           {checked && <Check size={15} strokeWidth={2.2} />}
//         </span>
//       ) : (
//         Icon && <Icon size={15} strokeWidth={2} aria-hidden />
//       )}
//       <span>{children}</span>
//       {kbd && <span className="dx-kbd">{kbd}</span>}
//     </button>
//   );
// }
//
// export function MenuSep() {
//   return <div className="dx-pop-sep" role="separator" />;
// }
//
// export function MenuNote({ children }: { children: ReactNode }) {
//   return <p className="dx-pop-note">{children}</p>;
// }
//
// /** A sheet that rises over the panel for a longer choice (Feedback, Delegate). */
// export function Sheet({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
//   const ref = useDismiss<HTMLDivElement>(open, onClose);
//   if (!open) return null;
//   return (
//     <>
//       <div className="dx-scrim" aria-hidden />
//       <div className="dx-sheet" role="dialog" aria-label={title} ref={ref}>
//         <div className="dx-sheet-head">
//           <h3>{title}</h3>
//           <IconButton label="Close" icon={X} onClick={onClose} />
//         </div>
//         {children}
//       </div>
//     </>
//   );
// }
//
// /** One line at the foot of the panel: what just happened, and its undo. */
// export function Toast({ children, action, onAction }: { children: ReactNode; action?: string; onAction?: () => void }) {
//   return (
//     <div className="dx-toast" role="status" aria-live="polite">
//       <span>{children}</span>
//       {action && (
//         <button type="button" onClick={onAction}>
//           {action}
//         </button>
//       )}
//     </div>
//   );
// }
```

---

## 5 · Reading and pressing cards

The brain's routes, the web's card reader, the refusal sentences, Today's grouping.

#### `src/desktop/api.ts`

```ts
// // Live GeniOS engine client for the desktop advisor.
// // No mock data: every card comes from /v1/intelligence/* on the running backend.
// //
// // Requests go through Tauri's HTTP plugin (native, not the webview's fetch) so they are not
// // subject to browser CORS — the engine only sends CORS headers for the dashboard origin, which
// // would otherwise block the desktop app's cross-origin calls ("Load failed").
// //
// // Tokens never touch the webview's storage: the Rust core holds the refresh token in the
// // Keychain and the access token in memory, and hands a bearer out per request
// // (`get_access_token`). A 401 asks Rust for a refreshed token once, then gives up.
// import { invoke } from "@tauri-apps/api/core";
// import { listen, type UnlistenFn } from "@tauri-apps/api/event";
// import { fetch as tauriFetch } from "@tauri-apps/plugin-http";
//
// // ---- Auth (device sign-in; state lives in Rust) ----
//
// export type AuthState =
//   | { status: "signed_out"; reason: string | null }
//   | {
//       status: "pending";
//       user_code: string;
//       verification_uri: string;
//       verification_uri_complete: string | null;
//       expires_in: number;
//       expires_at: string;
//     }
//   | { status: "denied" }
//   | { status: "expired" }
//   | { status: "signed_in"; seat_id: string | null; device_id: string | null; email: string | null };
//
// export type AuthView = AuthState & { base_url: string };
//
// // The engine URL is not a secret; it is remembered only to prefill the sign-in screen.
// const BASE_KEY = "genios.baseUrl";
// // Pre-token builds stored the bearer here — clear it on load so no token lingers in the webview.
// const LEGACY_TOKEN_KEY = "genios.token";
// try {
//   localStorage.removeItem(LEGACY_TOKEN_KEY);
// } catch {
//   /* storage unavailable — nothing to clear */
// }
//
// export function defaultBaseUrl(): string {
//   const envBase = (import.meta.env.VITE_GENIOS_BASE as string) || "";
//   let saved = "";
//   try {
//     saved = localStorage.getItem(BASE_KEY) || "";
//   } catch {
//     /* ignore */
//   }
//   return saved || envBase || "https://squid-app-2zuqf.ondigitalocean.app";
// }
//
// export function rememberBaseUrl(baseUrl: string): void {
//   try {
//     localStorage.setItem(BASE_KEY, baseUrl.trim().replace(/\/+$/, ""));
//   } catch {
//     /* ignore */
//   }
// }
//
// export const authState = () => invoke<AuthView>("auth_state");
// export const authStart = (baseUrl: string) => invoke<AuthState>("auth_start", { baseUrl });
// export const authPollStatus = () => invoke<AuthState>("auth_poll_status");
// export const authOpenBrowser = () => invoke<void>("auth_open_browser");
// export const authCancel = () => invoke<void>("auth_cancel");
// export const signOut = () => invoke<void>("sign_out");
// export const onAuthChange = (cb: (s: AuthState) => void): Promise<UnlistenFn> =>
//   listen<AuthState>("genios://auth", (e) => cb(e.payload));
//
// // ---- Screen capture status (macOS; the Rust core owns the pipeline) ----
//
// export type CaptureStatus = {
//   state:
//     | "unsupported"
//     | "signed_out"
//     | "update_required"
//     | "needs_accessibility"
//     | "sidecar_unavailable"
//     | "off_by_policy"
//     | "paused"
//     | "idle"
//     | "starting"
//     | "capturing";
//   paused_until?: string | null;
//   last_thread_title?: string | null;
//   last_captured_at?: string | null;
//   reader_available?: boolean;
//   queue_depth?: number;
//   detail?: string | null;
//   // Screen batches the server deferred to the night (0 / absent when none).
//   catching_up?: number;
//   // The seat's daily AI-check budget (absent on older servers).
//   insight_budget?: InsightBudget | null;
//   insight_budget_exhausted?: boolean;
//   // A reader that used to see an app and now sees nothing (NFR-04). The forbidden state is
//   // silence: "it stopped finding things" and "it stopped seeing WhatsApp" look identical
//   // from the panel unless one of them says so.
//   reader_health?: string | null;
// };
//
// export type InsightBudget = { used: number; cap: number; resets_at?: string | null };
//
// // "Daily AI checks used up — resumes at 12:00 AM" once the cap is reached (and the reset is
// // still ahead); null otherwise. Same rule as the Rust core's `InsightBudget::exhausted`.
// export function budgetLine(b: InsightBudget | null | undefined, now: number = Date.now()): string | null {
//   if (!b || typeof b.used !== "number" || typeof b.cap !== "number" || !(b.cap > 0) || b.used < b.cap) return null;
//   const reset = b.resets_at ? new Date(b.resets_at) : null;
//   if (reset && !Number.isNaN(reset.getTime())) {
//     if (reset.getTime() <= now) return null;
//     return `Daily AI checks used up — resumes at ${reset.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
//   }
//   return "Daily AI checks used up";
// }
//
// // "Catching up on N screens tonight" while the server has deferred screens; null otherwise.
// export function catchingUpLine(n: number | null | undefined): string | null {
//   const c = typeof n === "number" && Number.isFinite(n) ? Math.floor(n) : 0;
//   return c > 0 ? `Catching up on ${c} screen${c === 1 ? "" : "s"} tonight` : null;
// }
//
// export const captureStatus = () => invoke<CaptureStatus>("capture_status");
// export const capturePause = (minutes: number) => invoke<void>("capture_pause", { minutes });
// export const captureResume = () => invoke<void>("capture_resume");
// export const syncNow = () => invoke<void>("sync_now");
//
// // Notes the person saw on screen (newest first, this session) and open follow-ups.
// export type RecentItem = {
//   id: string;
//   headline: string;
//   body?: string | null;
//   kind: string;
//   at: string;
//   thread_key?: string | null;
//   feedback?: string | null;
//   /// Where the note came from — the app, the person, the words on screen, and when they were
//   /// read. A row the manager cannot place is a row he cannot judge.
//   app?: string | null;
//   who?: string | null;
//   quote?: string | null;
//   said_at?: string | null;
// };
// export type Followup = {
//   id: string;
//   kind: string;
//   text: string;
//   who?: string | null;
//   app?: string | null;
//   thread_key?: string | null;
//   // The words on screen that caused it (shown under the item).
//   quote?: string | null;
//   // The person node the brain wrote it on — the panel shows it with that person's cards.
//   subject_node_id?: string | null;
//   due_at?: string | null;
//   created_at?: string | null;
// };
// export const laneRecent = () => invoke<RecentItem[]>("lane_recent");
// /** Fetch the capture policy now instead of waiting out the 15-minute timer. */
// export const captureRefreshPolicy = () => invoke<void>("capture_policy_now");
// export const followupsOpen = () => invoke<Followup[]>("followups_open");
// export const followupDone = (id: string) => invoke<void>("followup_done", { id });
// // "Already handled": the item was real and the manager did it somewhere GeniOS cannot see. It
// // closes the item like Done, and is counted apart from it — "you would have missed it" is a
// // claim about what the product caused, and this is not that.
// export const followupHandled = (id: string) => invoke<void>("followup_done", { id, handled: true });
// // Server snooze of a follow-up's nudge ("Tomorrow").
// export const followupSnooze = (id: string, preset: "1h" | "tonight" | "tomorrow") =>
//   invoke<void>("followup_snooze", { id, preset });
// // The brain's reply draft, already copied to the clipboard by the Rust core; null = no draft.
// export const followupDraft = (id: string) => invoke<string | null>("followup_draft", { id });
//
// // "This week" in the panel: the brain's weekly report for this seat (null offline).
// export type WeeklyReport = {
//   week_start: string;
//   week_end: string;
//   promises_caught: number;
//   promises_kept: number;
//   asks_flagged: number;
//   asks_answered: number;
//   deadlines_flagged: number;
//   risks_flagged: number;
//   popups_shown: number;
//   useful: number;
//   not_useful: number;
//   nudged_then_closed: number;
// };
// export const weeklyReport = () => invoke<WeeklyReport | null>("weekly_report");
// // Opens a GeniOS website page (`/dashboard/…` only), e.g. Settings → My capture.
// export const openDashboard = (path: string) => invoke<void>("open_dashboard", { path });
// export const recentFeedback = (id: string, action: "useful" | "not_useful" | "mute_chat") =>
//   invoke<void>("recent_feedback", { id, action });
// export const openAccessibilitySettings = () => invoke<void>("capture_open_accessibility_settings");
//
// class ApiError extends Error {
//   constructor(public status: number, message: string) {
//     super(message);
//   }
// }
// export { ApiError };
//
// type Bearer = { access_token: string; base_url: string };
//
// async function bearer(stale?: string): Promise<Bearer> {
//   try {
//     return await invoke<Bearer>("get_access_token", stale ? { stale } : {});
//   } catch (e) {
//     const msg = String(e);
//     throw new ApiError(msg === "signed_out" ? 401 : 0, msg === "signed_out" ? "Signed out" : msg);
//   }
// }
//
// /** One engine request with the Rust-held bearer; retries once with a refreshed token on 401. */
// async function request(path: string, init: { method?: string; body?: string } = {}): Promise<Response> {
//   const send = (b: Bearer) =>
//     tauriFetch(`${b.base_url}${path}`, {
//       method: init.method || "GET",
//       headers: {
//         Authorization: `Bearer ${b.access_token}`,
//         ...(init.body ? { "Content-Type": "application/json" } : {}),
//       },
//       body: init.body,
//     });
//   const first = await bearer();
//   let res = await send(first);
//   if (res.status === 401) res = await send(await bearer(first.access_token));
//   return res;
// }
//
// async function get<T>(path: string): Promise<T> {
//   const res = await request(path);
//   if (!res.ok) {
//     const body = await res.text().catch(() => "");
//     throw new ApiError(res.status, body || res.statusText);
//   }
//   return (await res.json()) as T;
// }
//
// // ---- Proactive "open loops" (the primary surface: what GeniOS found that needs you) ----
//
// export type OpenLoop = {
//   card_id: string;
//   signal_id: string;
//   urgency_band: string; // standard | high | critical
//   headline: string; // what to do
//   situation: string; // why / the open loop
//   score: number; // 0-100
//   state: string;
//   created_at: string;
//   expires_at: string;
//   // The signal's person node — a screen follow-up on the same person joins this row.
//   subject_node_id?: string | null;
// };
//
// /** Everything GeniOS is holding for you — the unfinished things it found, ranked. No input needed. */
// export function getOpenLoops(): Promise<OpenLoop[]> {
//   return get<{ cards: OpenLoop[] }>("/cards").then((d) => d.cards || []);
// }
//
// /** A card's "Why" carries two kinds of row, and the engine keeps them apart on purpose: a graph
//  *  reading is something observed in this tenant's data, an expertise citation is authored
//  *  doctrine. The panel knew only readings, so a card carrying a citation had `w.field` come back
//  *  undefined — and a React throw in here does not crash the app, it just empties the window. That
//  *  is the "panel vanished when I opened a card" everybody kept hitting. */
// export type GraphEvidence = { field: string; value: string; source: string };
// export type ExpertiseEvidence = {
//   statement: string;
//   artifact_id?: string | null;
//   artifact_class?: string | null;
//   source: "expertise";
// };
// export type Evidence = GraphEvidence | ExpertiseEvidence;
//
// export function isExpertise(e: Evidence): e is ExpertiseEvidence {
//   return (e as ExpertiseEvidence).statement !== undefined || e.source === "expertise";
// }
// // The subject's captured context — who they are + what's going on — surfaced from the graph.
// // A connected cross-tool meeting (Calendar), with its reconciled lifecycle state.
// export type Interaction = {
//   title: string;
//   start_at: string | null;
//   status: string | null;
//   state: string; // scheduled | past_scheduled | cancelled
//   state_label: string; // "Past scheduled · occurrence unverified"
//   source: string; // gcal
// };
// export type SubjectContext = {
//   profile: { field: string; value: string }[]; // role, company, proposed slot, focus, phone…
//   signals: { kind: string; label: string; count: number }[]; // meeting proposed, questions, next step…
//   interactions?: Interaction[]; // connected Calendar meetings (cross-tool)
//   commitments?: { text: string; due_at: string | null; status: string | null }[]; // what was said in-thread
//   freshness?: { as_of: string; age_hours: number; label: string; note: string } | null; // synced, not live
// };
// // Update-1 clarity gate: is the decisive context grounded, or must the card fail closed?
// export type Actionability = {
//   state: "actionable" | "context_incomplete";
//   missing?: string[];
//   message?: string; // what we could NOT verify
//   recommended?: string; // the context-recovery step to take instead
// };
// // card.v2 decision projection — the grounded "what to do" + separate confidences + grounding status.
// export type Decision = {
//   card_version: string;
//   recommendation: { verdict: string; objective: string; steps: string[]; avoid?: string | null };
//   confidence: { evidence: number; identity: number; situation: number; recommendation: number };
//   grounding: Record<string, string>; // situation/request/obligation/stakes/completion → grounded|missing
// };
// export type CardDetail = OpenLoop & {
//   domain: string;
//   score_block: { C: number; I: number; R: number; U: number; S: number };
//   why: Evidence[]; // the facts this was built on, each with its source (gmail / gcal / …)
//   context_tags: string[]; // e.g. ["app:gmail"]
//   context?: SubjectContext; // richer "what's going on" — profile facts + relationship signals
//   actionability?: Actionability; // clarity gate — drives the fail-closed banner
//   decision?: Decision; // card.v2 — recommendation objective/steps/avoid + separate confidences
//   actions: { type: string; label?: string; play_id?: string; effect?: string }[];
// };
//
// /** Full context for one loop — score breakdown, the evidence it stands on, and where it came from. */
// export function getCardDetail(cardId: string): Promise<CardDetail> {
//   return get<CardDetail>(`/cards/${cardId}`);
// }
//
// /** What a card button sends. Only what the card offers is ever pressed (`readCard().offers`). */
// export type CardPress =
//   | { action: "do_it_myself" | "requeue" }
//   | { action: "snooze"; snooze: string; until?: string } // the card's options (4h | tomorrow_09 | 3d), or "custom" + until
//   | { action: "wrong"; reason: string; words?: string; scope?: "file" | "kind" | "company" }
//   | { action: "answer"; words: string };
//
// /**
//  * Press a card button, as the web does (`actOnCard`), marked as pressed in the desktop app.
//  * Throws `ApiError(status, code)` when the server refuses it — status 0 when it never arrived —
//  * so the panel can say why (`refusalText`) instead of dropping the card and getting it back.
//  */
// export async function pressCard(cardId: string, press: CardPress): Promise<{ ok: boolean; state?: string }> {
//   const words = "words" in press && press.words?.trim() ? press.words.trim() : null;
//   let res: Response;
//   try {
//     res = await request(`/cards/${encodeURIComponent(cardId)}/action`, {
//       method: "POST",
//       body: JSON.stringify({
//         action: press.action,
//         reason: press.action === "wrong" ? press.reason : null,
//         snooze_option: press.action === "snooze" ? press.snooze : null,
//         custom_until: press.action === "snooze" && press.until ? press.until : null,
//         words,
//         scope: press.action === "wrong" && words ? (press.scope ?? "file") : null,
//         surface: "desktop",
//       }),
//     });
//   } catch (e) {
//     if (e instanceof ApiError) throw e; // signed out
//     throw new ApiError(0, "offline");
//   }
//   if (!res.ok) {
//     const body = await res.json().catch(() => ({}));
//     const detail = body?.detail;
//     const code = typeof detail === "string" ? detail : detail?.error || detail?.message || res.statusText;
//     throw new ApiError(res.status, String(code));
//   }
//   return res.json().catch(() => ({ ok: true }));
// }
//
// // ---- Who a card could be handed to (Delegate) ----
//
// export type Member = { id: string; name: string; email: string; role: string; status: string };
// export type Agent = { agent_id: string; name?: string | null; description?: string | null; status: string };
//
// /** The workspace's people (owner and admins only; a member is refused). */
// export function getMembers(): Promise<Member[]> {
//   return get<{ members?: Member[] }>("/api/org/me/members").then((d) => (d.members ?? []).filter((m) => m.status === "active"));
// }
//
// /** The workspace's agents. */
// export function listAgents(): Promise<Agent[]> {
//   return get<{ agents?: Agent[] }>("/v1/agents").then((d) => (d.agents ?? []).filter((a) => a.status === "active"));
// }
```

#### `src/desktop/cards.ts`

```ts
// // The cards in the panel, read the way the web Cards page reads them.
// //
// // `/cards` is the queue; `/cards/{id}` is each card's body. Both go through the web's own reader
// // (`src/lib/card-read.ts` — one reader for every screen), and every field another open card
// // repeats is left out (`ownCard`): a stock sentence, or the person's meetings that ride on every
// // card about them, is nobody's reason. A card shows only what is its own.
// import { ownCard, readCard, sharedLines, sharedTexts, type CardRead } from "../lib/card-read";
// import { getCardDetail, getOpenLoops, type CardDetail, type OpenLoop } from "./api";
//
// export type DeskCard = CardRead & {
//   /** How many of its lines read the same on another open card, and were left out. */
//   leftOut: number;
//   /** The queue row as the brain sent it — its subject node joins a screen item about the same person. */
//   loop: OpenLoop;
//   /** False until `/cards/{id}` has answered; until then the face is drawn from the queue row. */
//   loaded: boolean;
// };
//
// export type DetailCache = Map<string, { detail: CardDetail; at: number }>;
//
// /** A body older than this is fetched again on the next refresh: cards are versioned in place. */
// export const MAX_AGE_MS = 5 * 60_000;
// const PARALLEL = 4;
//
// export const loadQueue = (): Promise<OpenLoop[]> => getOpenLoops();
//
// /**
//  * The bodies `cache` lacks, or holds for longer than `maxAge`, fetched four at a time. Returns a
//  * new cache holding only the cards in `ids`. A body that fails to load stays missing — the card
//  * still shows its face, and the next refresh asks again.
//  */
// export async function fillDetails(cache: DetailCache, ids: string[], now = Date.now(), maxAge = MAX_AGE_MS): Promise<DetailCache> {
//   const next: DetailCache = new Map();
//   for (const id of ids) {
//     const hit = cache.get(id);
//     if (hit) next.set(id, hit);
//   }
//   const todo = ids.filter((id) => {
//     const hit = next.get(id);
//     return !hit || now - hit.at > maxAge;
//   });
//   let i = 0;
//   const worker = async () => {
//     while (i < todo.length) {
//       const id = todo[i++];
//       try {
//         next.set(id, { detail: await getCardDetail(id), at: Date.now() });
//       } catch {
//         /* keep the face; ask again next refresh */
//       }
//     }
//   };
//   await Promise.all(Array.from({ length: Math.min(PARALLEL, todo.length) }, worker));
//   return next;
// }
//
// /** Every open card, read, with only its own details. Fields are compared across loaded cards only. */
// export function readOpen(loops: OpenLoop[], cache: DetailCache): DeskCard[] {
//   const reads = loops.map((loop) => readCard(loop, cache.get(loop.card_id)?.detail ?? null));
//   const loaded = reads.filter((_, i) => cache.has(loops[i].card_id));
//   const texts = sharedTexts(loaded);
//   const lines = sharedLines(loaded);
//   return reads.map((read, i) => ({
//     ...ownCard(read, texts, lines),
//     loop: loops[i],
//     loaded: cache.has(loops[i].card_id),
//   }));
// }
```

#### `src/lib/card-read.ts`

```ts
// /**
//  * One card, read for a person: what `/cards`, `/cards/{id}` and `/cards/{id}/timeline` send, turned
//  * into the things the Cards page shows — where it came from, a clear headline, a short description,
//  * what to do, why (one line per point, each with its tool and date), the conversation with the
//  * person, and the buttons the server actually offers.
//  *
//  * Every field is read defensively: the live brain sends two card generations at once — the older
//  * formula/template cards (`why` = graph readings, `decision` = the request-time projection) and the
//  * expert cards (`recommended`, `why_now`, quoted lines). A field a card lacks is left out, never
//  * shown as a dash or an empty box.
//  */
//
// import { displayValue, type CardDetail, type CardTimeline, type OpenCard } from "./card-shape";
//
// // ── what a card is, read ─────────────────────────────────────────────────────────────────────
//
// export type Tool = "Gmail" | "Calendar" | "Notion" | "HubSpot" | "Drive" | "Slack" | "CRM" | "Screen" | "GeniOS";
//
// export interface ToolTag {
//   tool: Tool;
//   /** How the data came: "mail thread", "2 meetings", "your screen". */
//   how: string;
//   /** For a Calendar tag that stands on the person's meetings: those meetings' line keys. */
//   meetingKeys?: string[];
// }
//
// export interface WhyLine {
//   kind: "said" | "fact" | "meeting" | "promise" | "rule" | "reading" | "question";
//   text: string;
//   /** Where it came from, in the person's words: "Gmail", "Calendar", "Admin expertise". */
//   from: string;
//   when?: string;
// }
//
// export interface TimelineEntry {
//   at: number;
//   when: string;
//   text: string;
//   from: string;
//   upcoming: boolean;
// }
//
// export interface WrongGroup {
//   title: string;
//   reasons: { value: string; label: string }[];
// }
//
// export interface CardRead {
//   id: string;
//   headline: string;
//   description: string;
//   /** The card in three lines: what it is, why it is here now, how it gets done. */
//   what?: string;
//   whyNow?: string;
//   how?: string;
//   who?: string;
//   role?: string;
//   tools: ToolTag[];
//   /** Small tags: "Open question ×2", "Meeting proposed". */
//   signals: string[];
//   domain?: string;
//   lane: "decision" | "question" | "waiting" | "conflict";
//   laneLabel: string;
//   urgency: "critical" | "high" | "standard";
//   version?: number;
//   age: string;
//   due?: string;
//
//   todo?: {
//     line: string;
//     steps: string[];
//     who?: string;
//     forWhom?: string;
//     by?: string;
//     avoid?: string;
//   };
//   /** What was promised or is still open in the thread — the commitment the card is about. */
//   promised: { text: string; due?: string; status?: string }[];
//   why: WhyLine[];
//   ifNothing?: string;
//   doneWhen?: string;
//   otherwise?: string;
//   waitOrStop?: string;
//   window?: string;
//   incomplete?: { message?: string; next?: string };
//
//   question?: { ask: string; because?: string };
//   answered: boolean;
//
//   conversation: TimelineEntry[];
//
//   offers: {
//     done: boolean;
//     answer: boolean;
//     snooze: string[];
//     wrong: WrongGroup[];
//   };
// }
//
// // ── words ────────────────────────────────────────────────────────────────────────────────────
//
// const TOOL_OF_TAG: Record<string, Tool> = {
//   "app:gmail": "Gmail",
//   "app:googlecalendar": "Calendar",
//   "app:gcal": "Calendar",
//   "app:calendar": "Calendar",
//   "app:notion": "Notion",
//   "app:hubspot": "HubSpot",
//   "app:googledrive": "Drive",
//   "app:slack": "Slack",
//   "app:screen": "Screen",
// };
//
// const TOOL_OF_SOURCE: Record<string, string> = {
//   gmail: "Gmail",
//   calendar: "Calendar",
//   gcal: "Calendar",
//   crm: "CRM",
//   hubspot: "HubSpot",
//   notion: "Notion",
//   drive: "Drive",
//   slack: "Slack",
//   screen: "Screen",
//   graph: "GeniOS memory",
// };
//
// const WRONG_LABEL: Record<string, string> = {
//   not_relevant: "Not relevant to me",
//   wrong_facts: "A fact is wrong",
//   bad_timing: "Right card, wrong time",
//   misread_source: "It misread the mail",
//   stale_data: "It is out of date",
//   wrong_subject: "Wrong person or company",
//   bad_link: "Two things mixed up",
//   bad_reasoning: "The conclusion does not follow",
//   wrong_playbook: "Not how we do it",
//   wrong_person: "Someone else handles this",
//   badly_written: "I can't follow the card",
// };
//
// const LEGACY_WRONG: WrongGroup[] = [
//   {
//     title: "What is not right?",
//     reasons: ["not_relevant", "wrong_facts", "bad_timing"].map((value) => ({ value, label: WRONG_LABEL[value] })),
//   },
// ];
//
// const GROUP_TITLE: Record<string, string> = {
//   "the facts are wrong": "The facts are wrong",
//   "the conclusion is wrong": "The conclusion is wrong",
//   "this is not how we work": "This is not how we work",
//   "right card, wrong delivery": "Right card, wrong time or person",
// };
//
// const ROLE_WORDS: Record<string, string | undefined> = {
//   intro: "introduced to you",
//   connector: "made the introduction",
//   watched: undefined,
// };
//
// /** Sentences the projection writes when it has nothing of its own to say. Never shown as the move. */
// const GENERIC_MOVES = new Set([
//   "reply to what they actually asked",
//   "verify what's actually needed before acting",
//   "send a recap of the meeting",
//   "deliver the commitment",
// ]);
//
// const FUNCTION_WORDS = new Set(
//   "a an the to of on in at for by with and or but nor so then before after from into onto about as than that this these those which who whom whose whether if once when while until because via per your our his her their its my is are was be been will would can not plus".split(
//     " ",
//   ),
// );
//
// function str(value: unknown): string | undefined {
//   const s = displayValue(value).replace(/\s+/g, " ").trim();
//   return s ? s : undefined;
// }
//
// function nameFromEmail(email: string): string {
//   const local = email.split("@")[0] ?? email;
//   const parts = local.split(/[._-]+/).filter(Boolean);
//   return parts.length ? parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(" ") : email;
// }
//
// /**
//  * The headline as a person reads it. The brain writes the words; this only tidies what the page
//  * can tidy without changing meaning: spacing, a capital, an address shown as a name, and a line
//  * that was cut on a dangling "to", "with" or "the".
//  */
// export function clearHeadline(raw: string): string {
//   let s = (raw ?? "").replace(/\s+/g, " ").trim().replace(/^["'“”]+|["'“”]+$/g, "");
//   s = s.replace(/[\w.%+-]+@[\w-]+(\.[\w-]+)+/g, (m) => nameFromEmail(m));
//   let words = s.split(" ");
//   while (words.length > 3 && FUNCTION_WORDS.has(words[words.length - 1].toLowerCase().replace(/[.,;:]+$/, ""))) {
//     words = words.slice(0, -1);
//   }
//   s = words.join(" ").replace(/[,;:]+$/, "");
//   return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
// }
//
// const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
//
// function asDate(value: unknown): Date | null {
//   if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}/.test(value)) return null;
//   const d = new Date(value);
//   return Number.isNaN(d.getTime()) ? null : d;
// }
//
// /** "13 Sep" or "13 Sep, 3:10 pm" — never an ISO string. */
// export function day(value: unknown, withTime = false): string | undefined {
//   const d = asDate(value);
//   if (!d) return undefined;
//   const base = `${d.getDate()} ${MONTHS[d.getMonth()]}`;
//   const hasTime = typeof value === "string" && /T\d{2}:\d{2}/.test(value) && !/T00:00(:00)?/.test(value);
//   if (!withTime || !hasTime) return base;
//   return `${base}, ${d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}`;
// }
//
// export function ago(iso: string | null | undefined): string {
//   if (!iso) return "";
//   const t = new Date(iso).getTime();
//   if (Number.isNaN(t)) return "";
//   const m = Math.round((Date.now() - t) / 60_000);
//   if (m < 1) return "just now";
//   if (m < 60) return `${m}m ago`;
//   if (m < 60 * 24) return `${Math.round(m / 60)}h ago`;
//   return `${Math.round(m / 1440)}d ago`;
// }
//
// function humanField(field: string): string {
//   const s = field.replace(/^[a-z]+\./, "").replace(/[._]/g, " ").trim();
//   return s ? s.charAt(0).toUpperCase() + s.slice(1) : field;
// }
//
// /** A graph reading as one plain line, or null when it says nothing a person needs. */
// function factLine(field: string, value: unknown, who: string | undefined): { text: string; when?: string; date?: Date | null } | null {
//   const v = str(value);
//   if (!v) return null;
//   const date = asDate(value);
//   const them = who ?? "They";
//   switch (field) {
//     case "thread.last_inbound":
//       return { text: `${them} last wrote`, when: day(value, true), date };
//     case "thread.last_outbound":
//       return { text: "You last replied", when: day(value, true), date };
//     case "thread.ball_in_court":
//       return { text: v === "us" ? "The next reply is yours" : `Waiting on ${who ?? "them"}` };
//     case "commitment.action":
//       return { text: `Promised: “${v}”` };
//     case "commitment.due_at":
//       return { text: "The promise is due", when: day(value, true), date };
//     case "commitment.status":
//       return { text: `Promise: ${v.replace(/_/g, " ")}` };
//     case "meeting.start_at":
//       return { text: "Meeting", when: day(value, true), date };
//     case "meeting.status":
//       return { text: `Meeting ${v.replace(/_/g, " ")}` };
//     case "meeting.title":
//       return { text: `Meeting: ${v}` };
//     case "party.role":
//       return { text: `Role: ${v}` };
//     default:
//       return date ? { text: humanField(field), when: day(value, true), date } : { text: `${humanField(field)}: ${v}` };
//   }
// }
//
// // ── reading ──────────────────────────────────────────────────────────────────────────────────
//
// type Raw = Record<string, unknown>;
//
// function rows(value: unknown): Raw[] {
//   return Array.isArray(value) ? value.filter((r): r is Raw => Boolean(r) && typeof r === "object") : [];
// }
//
// function primaryTool(detail: Raw): string {
//   for (const t of (detail.context_tags as string[] | undefined) ?? []) if (TOOL_OF_TAG[t]) return TOOL_OF_TAG[t];
//   for (const w of rows(detail.why)) {
//     const s = typeof w.source === "string" ? TOOL_OF_SOURCE[w.source] : undefined;
//     if (s && s !== "GeniOS memory") return s;
//   }
//   return "Gmail";
// }
//
// function laneOf(card: Raw, detail: Raw): CardRead["lane"] {
//   const lane = String(detail.output_lane ?? "").toLowerCase();
//   if (card.render_mode === "question" || lane === "investigation" || lane === "question") return "question";
//   if (lane === "monitor") return "waiting";
//   if (lane === "conflict") return "conflict";
//   return "decision";
// }
//
// const LANE_LABEL: Record<CardRead["lane"], string> = {
//   decision: "Decide",
//   question: "Answer",
//   waiting: "Waiting",
//   conflict: "Two sources disagree",
// };
//
// export function readCard(card: OpenCard | Raw, detail: CardDetail | Raw | null, timeline: CardTimeline | null = null): CardRead {
//   const c = card as Raw;
//   const d = (detail ?? {}) as Raw;
//   const tl = (timeline?.card ?? {}) as Raw;
//   const ctx = (d.context ?? {}) as Raw;
//   const gold = (d.recommended && typeof d.recommended === "object" ? d.recommended : {}) as Raw;
//   const rec = ((d.decision as Raw | undefined)?.recommendation ?? {}) as Raw;
//   const tool = primaryTool(d);
//
//   const who = str(d.business_subject) ?? str(rows(ctx.profile).find((p) => p.field === "name")?.value);
//   // The engine's role words are its own ("watched", "intro"); a person reads what they mean.
//   const rawRole = str(d.relationship_role);
//   const role =
//     (rawRole && rawRole.toLowerCase() in ROLE_WORDS ? ROLE_WORDS[rawRole.toLowerCase()] : rawRole) ??
//     str(rows(ctx.profile).find((p) => p.field === "role" || p.field === "company")?.value);
//   const lane = laneOf(c, d);
//
//   // Where it came from: the tool and how — a thread, meetings, a promise in the thread.
//   const tools: ToolTag[] = [];
//   const meetings = rows(ctx.interactions);
//   const whyRows = rows(d.why).length ? rows(d.why) : rows(tl.why);
//   const mailish = whyRows.some((w) => w.source === "gmail" || w.source === "expert_check" || String(w.field ?? "").startsWith("thread."));
//   if (tool === "Gmail" || mailish) tools.push({ tool: "Gmail", how: "mail thread" });
//   else tools.push({ tool: tool as Tool, how: tool === "Calendar" ? "meeting" : "source" });
//   if (meetings.length && !tools.some((t) => t.tool === "Calendar"))
//     tools.push({ tool: "Calendar", how: meetings.length === 1 ? "1 meeting" : `${meetings.length} meetings` });
//   if (whyRows.some((w) => w.source === "crm") && !tools.some((t) => t.tool === "CRM")) tools.push({ tool: "CRM", how: "deal record" });
//
//   const signals = rows(ctx.signals)
//     .map((s) => {
//       const label = str(s.label);
//       const n = typeof s.count === "number" ? s.count : 1;
//       return label ? (n > 1 ? `${label} ×${n}` : label) : null;
//     })
//     .filter((s): s is string => Boolean(s));
//
//   // The question a held card asks, and why.
//   const headRow = whyRows.find((w) => w.sentence === "headline");
//   const ask = str(headRow?.question);
//   const because = str(headRow?.because);
//   const question =
//     lane === "question"
//       ? { ask: ask ?? clearHeadline(String(c.headline ?? "")), because: because ? because.charAt(0).toUpperCase() + because.slice(1).replace(/([^.])$/, "$1.") : undefined }
//       : undefined;
//
//   // What to do: the card's own move first; the projection only when it says something real.
//   const goldLine = str(gold.what);
//   const projected = str(rec.objective);
//   const projectedIsGeneric = !projected || GENERIC_MOVES.has(projected.toLowerCase().replace(/[.“”"]/g, "").trim());
//   // The projection's steps belong to the projection: shown only when the card has no move of its own.
//   const steps = goldLine ? [] : (Array.isArray(rec.steps) ? rec.steps : []).map((s) => str(s)).filter((s): s is string => Boolean(s));
//   let todo: CardRead["todo"];
//   if (lane !== "question") {
//     const line = goldLine ?? (!projectedIsGeneric ? projected : undefined) ?? clearHeadline(String(c.headline ?? ""));
//     todo = {
//       line,
//       steps: steps.filter((s) => s.toLowerCase() !== line.toLowerCase() && rec.verdict !== "review_source"),
//       who: str(gold.who) ? (String(gold.who).toLowerCase() === "you" ? "You" : str(gold.who)) : undefined,
//       forWhom: str(gold.for_whom),
//       by: day(gold.by_when) ?? undefined,
//       avoid: str(rec.avoid),
//     };
//   }
//
//   // What was promised: the thread's commitments, then what is still open.
//   const promised: CardRead["promised"] = rows(ctx.commitments)
//     .map((m) => ({ text: str(m.text) ?? "", due: day(m.due_at), status: str(m.status)?.replace(/_/g, " ") }))
//     .filter((m) => m.text);
//   const remains = str(d.unresolved_item);
//   if (remains) for (const part of remains.split(/;\s+/)) if (part && !promised.some((p) => p.text === part)) promised.push({ text: part });
//
//   // Why: one line per point — what was said, what the records show, the meeting, how it is handled.
//   const why: WhyLine[] = [];
//   const conversation: TimelineEntry[] = [];
//   const now = Date.now();
//   const whyNow = str(d.why_now);
//   if (whyNow) why.push({ kind: "reading", text: whyNow, from: "GeniOS" });
//   for (const w of whyRows) {
//     if (w.source === "expert_check") {
//       for (const q of Array.isArray(w.quotes) ? w.quotes : []) {
//         const t = str(q);
//         if (t) why.push({ kind: "said", text: `“${t}”`, from: tool });
//       }
//       continue;
//     }
//     if (w.source === "expertise" || w.statement !== undefined) {
//       const t = str(w.statement);
//       if (t) why.push({ kind: "rule", text: t, from: d.domain ? `${humanField(String(d.domain))} expertise` : "Expertise" });
//       continue;
//     }
//     if (typeof w.field === "string") {
//       const line = factLine(w.field, w.value, who);
//       if (!line) continue;
//       const from = TOOL_OF_SOURCE[String(w.source)] ?? tool;
//       why.push({ kind: w.field.startsWith("meeting.") ? "meeting" : w.field.startsWith("commitment.") ? "promise" : "fact", text: line.text, from, when: line.when });
//       if (line.date) conversation.push({ at: line.date.getTime(), when: day(w.value, true) ?? "", text: line.text, from, upcoming: line.date.getTime() > now });
//     }
//   }
//   for (const m of meetings) {
//     const title = str(m.title) ?? "Meeting";
//     const label = str(m.state_label);
//     why.push({ kind: "meeting", text: label ? `${title} · ${label}` : title, from: "Calendar", when: day(m.start_at, true) });
//     const date = asDate(m.start_at);
//     if (date) conversation.push({ at: date.getTime(), when: day(m.start_at, true) ?? "", text: `Meeting: ${title}`, from: "Calendar", upcoming: date.getTime() > now });
//   }
//   for (const p of rows(ctx.commitments)) {
//     const date = asDate(p.due_at);
//     const t = str(p.text);
//     if (date && t) conversation.push({ at: date.getTime(), when: day(p.due_at, true) ?? "", text: `Due: ${t}`, from: tool, upcoming: date.getTime() > now });
//   }
//   conversation.sort((a, b) => a.at - b.at);
//   const calendar = tools.find((t) => t.tool === "Calendar" && /meeting/.test(t.how) && meetings.length > 0);
//   if (calendar) calendar.meetingKeys = why.filter((w) => w.kind === "meeting" && w.from === "Calendar").map((w) => lineKey(w.kind, w.text, w.when));
//   const seen = new Set<string>();
//   const uniqueConversation = conversation.filter((e) => {
//     const k = `${e.at}|${e.text}`;
//     if (seen.has(k)) return false;
//     seen.add(k);
//     return true;
//   });
//
//   // What the server offers on this card — never a button it refuses.
//   const actions = rows(d.actions);
//   const has = (type: string) => actions.some((a) => a.type === type);
//   const wrongAction = actions.find((a) => a.type === "wrong");
//   let wrong = LEGACY_WRONG;
//   const groups = wrongAction?.reason_groups as Record<string, string[]> | undefined;
//   if (groups && typeof groups === "object") {
//     wrong = Object.entries(groups)
//       .map(([title, reasons]) => ({
//         title: GROUP_TITLE[title] ?? title,
//         reasons: (reasons ?? []).map((value) => ({ value, label: WRONG_LABEL[value] ?? humanField(value) })),
//       }))
//       .filter((g) => g.reasons.length);
//   } else if (Array.isArray(wrongAction?.reasons)) {
//     wrong = [{ title: "What is not right?", reasons: (wrongAction.reasons as string[]).map((value) => ({ value, label: WRONG_LABEL[value] ?? humanField(value) })) }];
//   }
//   const snoozeAction = actions.find((a) => a.type === "snooze");
//   const offers = {
//     done: actions.length ? has("do_it_myself") : lane !== "question",
//     answer: has("answer"),
//     snooze: (Array.isArray(snoozeAction?.options) ? (snoozeAction.options as string[]) : ["4h", "tomorrow_09", "3d"]).filter((o) => o !== "custom"),
//     wrong,
//   };
//
//   const actionability = (d.actionability ?? {}) as Raw;
//   const incomplete =
//     actionability.state === "context_incomplete" && lane !== "question"
//       ? { message: str(actionability.message), next: str(actionability.recommended) }
//       : undefined;
//
//   const urgency = String(c.urgency_band ?? tl.urgency_band ?? "standard");
//   const windowDays = typeof d.outcome_window_days === "number" ? d.outcome_window_days : undefined;
//   const description = [str(c.situation) ?? str(tl.situation)].filter(Boolean).join(" ");
//
//   return {
//     id: String(c.card_id),
//     headline: question?.ask ?? clearHeadline(String(c.headline ?? tl.headline ?? "")),
//     description: description || "",
//     what: description || undefined,
//     whyNow: whyNow ?? question?.because ?? str(d.do_nothing_consequence) ?? (remains ? remains.split(/;\s+/)[0] : undefined),
//     how: question ? "Answer the question below; GeniOS reads the thread again with your answer." : (todo?.steps[0] ?? todo?.line),
//     who,
//     role: role && role !== who ? role : undefined,
//     tools,
//     signals,
//     domain: str(d.domain ?? tl.domain),
//     lane,
//     laneLabel: LANE_LABEL[lane],
//     urgency: urgency === "critical" || urgency === "high" ? urgency : "standard",
//     age: ago(String(c.created_at ?? tl.created_at ?? "")),
//     due: todo?.by ? `by ${todo.by}` : undefined,
//     todo,
//     promised,
//     why,
//     ifNothing: str(d.do_nothing_consequence),
//     doneWhen: str(d.success_signal),
//     otherwise: str(d.alternative),
//     waitOrStop: str(d.wait_or_stop),
//     window: windowDays ? `${windowDays} day${windowDays === 1 ? "" : "s"}` : undefined,
//     incomplete,
//     question,
//     answered: String(c.headline ?? "").startsWith("Your answer is in"),
//     conversation: uniqueConversation,
//     offers,
//   };
// }
//
// /**
//  * The tools a card stands on once what every card repeats is set aside: a Calendar tag counts only
//  * this card's own meetings, and goes when it has none.
//  */
// export function ownTools(read: CardRead, shared: Set<string>): ToolTag[] {
//   return read.tools
//     .map((t) => {
//       if (!t.meetingKeys) return t;
//       const own = t.meetingKeys.filter((k) => !shared.has(k)).length;
//       return own ? { ...t, how: own === 1 ? "1 meeting" : `${own} meetings` } : null;
//     })
//     .filter((t): t is ToolTag => t !== null);
// }
//
// /** The words of a field, compared across cards: case and spacing never make two texts differ. */
// export function textKey(text: string | undefined): string {
//   return (text ?? "").toLowerCase().replace(/[“”"]/g, "").replace(/\s+/g, " ").trim();
// }
//
// /**
//  * Words that more than one open card carries in the same field. A sentence that reads the same on
//  * two different cards — a play's stock "done when", a projection's stock step, a capability's
//  * "if you do nothing" — was written for a KIND of card, not for this one, so it is not shown as this
//  * card's detail. Rohit, 22 Oct: every card's details, scenario and things must be its own.
//  */
// export function sharedTexts(reads: CardRead[]): Set<string> {
//   const seen = new Map<string, Set<string>>();
//   const note = (text: string | undefined, id: string) => {
//     const k = textKey(text);
//     if (!k) return;
//     if (!seen.has(k)) seen.set(k, new Set());
//     seen.get(k)!.add(id);
//   };
//   for (const r of reads) {
//     for (const t of [r.description, r.whyNow, r.how, r.todo?.line, r.todo?.avoid, r.ifNothing, r.doneWhen, r.otherwise, r.waitOrStop])
//       note(t, r.id);
//     for (const t of r.todo?.steps ?? []) note(t, r.id);
//   }
//   return new Set([...seen].filter(([, ids]) => ids.size > 1).map(([k]) => k));
// }
//
// /** The card with every field another open card repeats taken out — only what is this card's own. */
// export function ownCard(read: CardRead, texts: Set<string>, lines: Set<string>): CardRead & { leftOut: number } {
//   let leftOut = 0;
//   const keep = (t: string | undefined) => {
//     if (!t) return undefined;
//     if (texts.has(textKey(t))) {
//       leftOut += 1;
//       return undefined;
//     }
//     return t;
//   };
//   const why = read.why.filter((w) => {
//     const ok = w.kind === "said" || !lines.has(lineKey(w.kind, w.text, w.when));
//     if (!ok) leftOut += 1;
//     return ok;
//   });
//   const promised = read.promised.filter((p) => !lines.has(lineKey("promised", p.text)));
//   const conversation = read.conversation.filter((e) => !lines.has(lineKey("conversation", e.text, e.when)));
//   const steps = (read.todo?.steps ?? []).filter((t) => keep(t));
//   const todo = read.todo
//     ? { ...read.todo, line: keep(read.todo.line) ?? read.headline, steps, avoid: keep(read.todo.avoid) }
//     : undefined;
//   return {
//     ...read,
//     description: keep(read.description) ?? "",
//     what: texts.has(textKey(read.what)) ? undefined : read.what,
//     whyNow: keep(read.whyNow),
//     how: steps[0] ?? (todo && textKey(todo.line) !== textKey(read.headline) ? todo.line : undefined),
//     todo,
//     ifNothing: keep(read.ifNothing),
//     doneWhen: keep(read.doneWhen),
//     otherwise: keep(read.otherwise),
//     waitOrStop: keep(read.waitOrStop),
//     why,
//     promised,
//     conversation,
//     tools: ownTools(read, lines),
//     leftOut,
//   };
// }
//
// /** A line's identity across cards: the same words (and date) on two cards is the same line. */
// export function lineKey(kind: string, text: string, when?: string): string {
//   return `${kind}|${text.toLowerCase()}|${when ?? ""}`;
// }
//
// /**
//  * The lines that show up on more than one open card. A meeting, a promise, a rule or an undated
//  * record that every card repeats is not evidence for any one of them — it is what the person (or
//  * the company) carries everywhere — so a card's Why leaves it out and says how many it left.
//  */
// export function sharedLines(reads: CardRead[]): Set<string> {
//   const seen = new Map<string, Set<string>>();
//   const note = (key: string, id: string) => {
//     if (!seen.has(key)) seen.set(key, new Set());
//     seen.get(key)!.add(id);
//   };
//   for (const r of reads) {
//     for (const w of r.why) if (w.kind !== "said" && w.kind !== "reading") note(lineKey(w.kind, w.text, w.when), r.id);
//     for (const p of r.promised) note(lineKey("promised", p.text), r.id);
//     for (const e of r.conversation) note(lineKey("conversation", e.text, e.when), r.id);
//   }
//   return new Set([...seen].filter(([, ids]) => ids.size > 1).map(([key]) => key));
// }
//
// /** How many times the card was rebuilt — its version — read off its own events. */
// export function versionOf(timeline: CardTimeline | null): number | undefined {
//   if (!timeline) return undefined;
//   const rebuilt = timeline.events.filter((e) => e.kind === "card.rebuilt").length;
//   return rebuilt ? rebuilt + 1 : undefined;
// }
```

#### `src/lib/card-shape.ts`

```ts
// /**
//  * What a card IS on the wire, with no way to fetch one: the shapes `/cards`, `/cards/{id}`,
//  * `/cards/history` and `/cards/{id}/timeline` send, and the two helpers that read them safely.
//  *
//  * Kept apart from `api-cards.ts` (which fetches with the dashboard's session) so that anything can
//  * read a card the same way — the card reader (`card-read.ts`) and through it the desktop app, which
//  * fetches with its own device session.
//  */
//
// // ── Types ────────────────────────────────────────────────────────────────────
//
// export type UrgencyBand = "standard" | "high" | "critical";
//
// export type OpenCard = {
//   card_id: string;
//   signal_id: string;
//   assignee: string | null;
//   urgency_band: UrgencyBand | string;
//   headline: string;
//   situation: string;
//   score: number;
//   state: string; // queued | surfaced | snoozed | claimed
//   created_at: string;
//   expires_at: string;
//   domain?: string;
//   /** "question" on a card that asks you one thing before any move. */
//   render_mode?: string;
//   subject_node_id?: string | null;
// };
//
// /** A card's "Why" carries TWO kinds of row, and they are not interchangeable.
//  *
//  * `card_builder._why` says it plainly: a graph reading is something observed in the tenant's own
//  * data, an expertise citation is authored doctrine, and "a surface that showed the two the same
//  * way would be claiming the corpus observed something". The engine began sending citations and
//  * this type still described only readings, so `humanize(w.field)` met `undefined` and took the
//  * whole dashboard down with it — every card, not just the one carrying doctrine.
//  */
// export type GraphEvidence = { field: string; value: string; source: string };
// export type ExpertiseEvidence = {
//   statement: string;
//   artifact_id?: string | null;
//   artifact_class?: string | null;
//   statement_hash?: string | null;
//   source: "expertise";
// };
// export type Evidence = GraphEvidence | ExpertiseEvidence;
//
// /** Authored doctrine, not a reading of this tenant's data. */
// export function isExpertise(e: Evidence): e is ExpertiseEvidence {
//   return (e as ExpertiseEvidence).statement !== undefined || e.source === "expertise";
// }
//
// /**
//  * One renderable string for an evidence value, whatever the engine actually sent.
//  *
//  * ⛔ WHY THIS EXISTS. `value` is typed `string` and the engine sent objects:
//  *     {"axis": "consistency", "value_bp": 10000}
//  *     {"fact": "situation.trend", "reason": "trend_confidence_below_floor", …}
//  * React refuses an object as a child, so `{w.value}` THREW, `CardErrorBoundary` caught it, and
//  * every card carrying one rendered "This card could not be opened". Measured on the design
//  * partner's org 2026-10-04: four of five open cards, and the single card that opened was the only
//  * one whose `why` held no object. The type said `string`; TypeScript cannot check a wire payload.
//  *
//  * The engine is fixed too (`card_builder._plain_value`), and that fix only reaches cards built
//  * AFTER it ships — every card already in the queue still carries the object. This is what makes
//  * those open, and what stops the next unexpected shape from blanking a card instead of being
//  * shown imperfectly. A card the reader cannot open is worth strictly less than an ugly line.
//  */
// export function displayValue(value: unknown): string {
//   if (value === null || value === undefined) return "";
//   if (typeof value === "string") return value;
//   if (typeof value === "number" || typeof value === "boolean") return String(value);
//   if (Array.isArray(value)) return value.map(displayValue).filter(Boolean).join(", ");
//   if (typeof value === "object") {
//     return Object.entries(value as Record<string, unknown>)
//       // A flag that is FALSE is noise, not a reason — "partially resolved false" says nothing a
//       // reader wanted. Dropped here exactly as `card_builder._readable_structure` drops it, so
//       // one card does not read differently before and after the engine fix reaches it.
//       .filter(([, v]) => v !== null && v !== undefined && v !== "" && v !== false)
//       .map(([k, v]) => {
//         const label = k.replace(/_/g, " ");
//         // Integer basis points are the repo's unit for a ratio; show the percentage a reader
//         // expects, matching what the engine now sends for the same field.
//         if (/_bp$/.test(k) && typeof v === "number") {
//           return `${label.replace(/ bp$/, "")} ${v / 100}%`;
//         }
//         // A flag that is TRUE is worth naming once, not as "flag true".
//         if (v === true) return label;
//         return `${label} ${displayValue(v)}`;
//       })
//       .filter(Boolean)
//       .join(" · ");
//   }
//   return "";
// }
//
// export type CardDecision = {
//   card_version: string;
//   recommendation: { verdict: string; objective: string; steps: string[]; avoid?: string | null };
//   confidence: { evidence: number; identity: number; situation: number; recommendation: number };
//   grounding: Record<string, string>;
// };
//
// export type CardActionability = {
//   state: "actionable" | "context_incomplete";
//   missing?: string[];
//   message?: string;
//   recommended?: string;
// };
//
// export type CardDetail = OpenCard & {
//   // The connected app this card was grounded in (["app:gmail"]) — shown as its source.
//   context_tags?: string[];
//   domain: string;
//   why: Evidence[];
//   decision?: CardDecision;
//   actionability?: CardActionability;
// };
//
// export type HistoryState = "acted" | "resolved" | "expired";
//
// export type HistoryCard = {
//   card_id: string;
//   signal_id: string;
//   assignee: string | null;
//   domain: string;
//   urgency_band: UrgencyBand | string;
//   headline: string;
//   situation: string;
//   score: number;
//   state: HistoryState;
//   created_at: string;
//   expires_at: string;
//   resolved_at: string | null;
//   last_event_kind: string | null;
//   last_action: string | null;
//   last_actor: string | null;
//   last_detail: Record<string, unknown> | null;
//   last_event_at: string | null;
//   closed_at: string;
// };
//
// export type TimelineEvent = {
//   id: string;
//   kind: string;
//   cause: string | null;
//   actor_id: string | null;
//   detail: Record<string, unknown> | null;
//   occurred_at: string;
// };
//
// export type CardTimeline = {
//   card: {
//     card_id: string;
//     headline: string;
//     situation: string;
//     state: string;
//     domain: string;
//     urgency_band: string;
//     score: number;
//     why: Evidence[] | null;
//     assignee: string | null;
//     created_at: string;
//     expires_at: string;
//     resolved_at: string | null;
//     snooze_until: string | null;
//   };
//   events: TimelineEvent[];
// };
//
// /** One of the reasons the card itself offers (`actions[type=wrong].reasons`). */
// export type WrongReason = string;
// /** One of the snooze options the card offers: "4h" | "tomorrow_09" | "3d". */
// export type SnoozeOption = string;
// export type CardButton = "do_it_myself" | "snooze" | "wrong" | "requeue" | "answer";
```

#### `src/desktop/refusals.ts`

```ts
// // A refused press, said in one sentence.
// //
// // The server refuses a press with a code (`deliver/actions.py`, `api/routes.card_action`). A
// // refusal nobody sees is a silent stop — the old panel swallowed every one, so a card vanished and
// // came back on the next refresh — so the panel keeps this sentence on screen until the next press.
// // The words are the web Cards page's own (`friendlyError` in src/app/dashboard/cards/page.tsx), so
// // one refusal reads the same on both screens.
//
// /** status 0 = the request never reached GeniOS. */
// export function refusalText(status: number, code: string): string {
//   if (status === 0) return "Couldn't reach GeniOS. Check your connection and press again.";
//   if (status === 401) return "You were signed out. Sign in again to act on your cards.";
//   switch (code) {
//     case "card_not_actionable":
//     case "stale_or_unauthorized_card":
//       return "This card changed since it loaded. The list has been refreshed.";
//     case "assigned_to_different_seat":
//       return "This card is assigned to someone else.";
//     case "not_offered":
//       return "This card does not take that. Answer it, put it off, or give feedback.";
//     case "not_a_question":
//       return "This card is not a question, so it takes no answer.";
//     case "answer_says_nothing":
//       return "Write your answer first.";
//     case "answer_too_long":
//       return "That answer is too long. One or two lines is enough.";
//     case "invalid_wrong_reason":
//       return "Pick what is off.";
//     case "unknown_action":
//       return "GeniOS on this workspace does not take that yet.";
//     case "invalid_correction":
//       return "Those words could not be kept. Say in one line what is wrong and what it should be.";
//     case "owner_only":
//       return "Only the workspace owner can apply feedback to a whole kind of work or the company.";
//     case "no_kind_of_work":
//       return "This card has no kind of work to apply that to. Apply it to this thread instead.";
//   }
//   if (status === 404) return "This card has closed already.";
//   if (status >= 500) return "GeniOS had a problem taking that. Press again in a minute.";
//   return "GeniOS did not take that. Press again, or open the card on the web.";
// }
```

#### `src/desktop/rows.ts`

```ts
// // Today's list: the open cards and what was caught on your screen, grouped by what they ask of you.
// //
// // Pure, no imports but types, so `node --test` runs it as it is.
// import type { Followup } from "./api";
// import type { DeskCard } from "./cards";
//
// export type GroupId = "decision" | "conflict" | "question" | "screen" | "waiting";
//
// export type Row =
//   | { kind: "card"; key: string; card: DeskCard; also: Followup[] }
//   | { kind: "screen"; key: string; item: Followup };
//
// export type Group = { id: GroupId; title: string; hint: string; rows: Row[] };
//
// /** In the order a person works them: what needs a move, a choice, an answer; then what was caught; then what only waits. */
// export const GROUPS: readonly { id: GroupId; title: string; hint: string }[] = [
//   { id: "decision", title: "Decide", hint: "A move is yours, and the evidence holds." },
//   { id: "conflict", title: "Two sources disagree", hint: "Pick which one is right." },
//   { id: "question", title: "Answer", hint: "One fact decides the move, so GeniOS asks before it advises." },
//   { id: "screen", title: "On your screen", hint: "Asks, promises and dates caught in the apps you use." },
//   { id: "waiting", title: "Waiting", hint: "Nothing to do now. GeniOS watches and brings it back." },
// ];
//
// /** An answered question has nothing left to press until its thread is read again: it waits. */
// export function groupOf(card: DeskCard): GroupId {
//   if (card.answered) return "waiting";
//   return card.lane;
// }
//
// function endOfDay(now: number): number {
//   const d = new Date(now);
//   d.setHours(23, 59, 59, 999);
//   return d.getTime();
// }
//
// const dueAt = (f: Followup): number => {
//   const t = f.due_at ? Date.parse(f.due_at) : NaN;
//   return Number.isNaN(t) ? Number.POSITIVE_INFINITY : t;
// };
//
// /** Due today or already late. */
// export function dueToday(f: Followup, now: number): boolean {
//   return dueAt(f) <= endOfDay(now);
// }
//
// /**
//  * Cards in the brain's own order (it is ranked), each carrying the screen items about the same
//  * person (one row per real thing: a follow-up that names someone sits on that person's node, and
//  * joins the first card on it). Screen items on their own: soonest due first, undated after, newest
//  * first among those. Empty groups are left out.
//  */
// export function buildGroups(cards: DeskCard[], followups: Followup[]): Group[] {
//   const byNode = new Map<string, Followup[]>();
//   for (const f of followups) {
//     if (f.who && f.subject_node_id) byNode.set(f.subject_node_id, [...(byNode.get(f.subject_node_id) ?? []), f]);
//   }
//   const joined = new Set<string>();
//   const rows = new Map<GroupId, Row[]>(GROUPS.map((g) => [g.id, []]));
//   for (const card of cards) {
//     const node = card.loop.subject_node_id;
//     const also = (node && byNode.get(node)) || [];
//     if (node) byNode.delete(node);
//     also.forEach((f) => joined.add(f.id));
//     rows.get(groupOf(card))!.push({ kind: "card", key: card.id, card, also });
//   }
//   const created = (f: Followup) => (f.created_at ? Date.parse(f.created_at) || 0 : 0);
//   followups
//     .filter((f) => !joined.has(f.id))
//     .sort((a, b) => dueAt(a) - dueAt(b) || created(b) - created(a))
//     .forEach((item) => rows.get("screen")!.push({ kind: "screen", key: item.id, item }));
//   return GROUPS.map((g) => ({ ...g, rows: rows.get(g.id)! })).filter((g) => g.rows.length > 0);
// }
//
// /** “6 need you · 2 urgent”: what asks something of you, and how much of it is pressing. */
// export function summarize(groups: Group[], now: number): { needYou: number; urgent: number } {
//   let needYou = 0;
//   let urgent = 0;
//   for (const g of groups) {
//     if (g.id === "waiting") continue;
//     for (const r of g.rows) {
//       needYou += 1;
//       if (r.kind === "card" ? r.card.urgency !== "standard" : dueToday(r.item, now)) urgent += 1;
//     }
//   }
//   return { needYou, urgent };
// }
```

---

## 6 · The panel (Today, an opened card, This week, History, sign-in)

The ⌘⇧G panel built on the same parts.

#### `src/desktop/main.tsx`

```tsx
// import { StrictMode } from "react";
// import { createRoot } from "react-dom/client";
// import { DesktopAdvisor } from "./DesktopAdvisor";
// import "./theme.css";
//
// // The window is transparent so the panel can have round corners. Linux without a compositor
// // renders a transparent corner black, so theme.css keys off this and squares the panel there.
// function detectOs(): "macos" | "windows" | "linux" | "other" {
//   const ua = navigator.userAgent;
//   if (/Windows|Win32|Win64/i.test(ua)) return "windows";
//   if (/Mac OS X|Macintosh/i.test(ua)) return "macos";
//   if (/Linux|X11/i.test(ua)) return "linux";
//   return "other";
// }
// document.documentElement.dataset.os = detectOs();
//
// createRoot(document.getElementById("root")!).render(
//   <StrictMode>
//     <DesktopAdvisor />
//   </StrictMode>,
// );
```

#### `src/desktop/DesktopAdvisor.tsx`

```tsx
// // The GeniOS panel (⌘⇧G): what needs you today, one card at a time when you open it, this week's
// // numbers and the popups' history. Data: the brain's queue and card bodies (cards.ts, read with the
// // web's reader), the screen's follow-ups and popups from the Rust core.
// //
// // A press is never silently lost: Done, Later and the screen items' buttons wait five seconds with
// // an Undo before they are sent; a refusal brings the card back and says why until the next press.
// import { useCallback, useEffect, useMemo, useRef, useState } from "react";
// import { getCurrentWindow } from "@tauri-apps/api/window";
// import {
//   ApiError,
//   authState,
//   followupDone,
//   followupHandled,
//   followupSnooze,
//   followupsOpen,
//   laneRecent,
//   onAuthChange,
//   openDashboard,
//   pressCard,
//   recentFeedback,
//   signOut,
//   type CardPress,
//   type Followup,
//   type OpenLoop,
//   type RecentItem,
// } from "./api";
// import { ActionBar, SNOOZE_LABEL } from "./ActionBar";
// import { CardDetail } from "./CardDetail";
// import { fillDetails, loadQueue, readOpen, type DeskCard, type DetailCache } from "./cards";
// import { Header, type View } from "./Header";
// import { HistoryView } from "./HistoryView";
// import { refusalText } from "./refusals";
// import { buildGroups, summarize } from "./rows";
// import { CaptureBar, SetupCard, useCapture } from "./SetupCard";
// import { SignIn } from "./SignIn";
// import { TodayView } from "./TodayView";
// import { Toast } from "./ui";
// import { WeekView } from "./WeekView";
// import "./panel.css";
//
// const UNDO_MS = 5000;
// const REFRESH_MS = 45_000;
// const VIEW_LABEL: Record<View, string> = { today: "Today", week: "This week", history: "History" };
//
// // "Only what's on my screen": per device and person, a view choice, not a capture switch.
// const SCREEN_ONLY_KEY = "genios.screenOnly";
// function loadScreenOnly(): boolean {
//   try {
//     return localStorage.getItem(SCREEN_ONLY_KEY) === "1";
//   } catch {
//     return false;
//   }
// }
// function saveScreenOnly(on: boolean): void {
//   try {
//     localStorage.setItem(SCREEN_ONLY_KEY, on ? "1" : "0");
//   } catch {
//     /* kept for this session */
//   }
// }
//
// function loadError(e: unknown): string {
//   const status = e instanceof ApiError ? e.status : 0;
//   if (status === 0) return "GeniOS could not be reached. Check your connection; the list tries again on its own.";
//   if (status >= 500) return "GeniOS had a problem sending your cards. The list tries again on its own.";
//   return "GeniOS did not send your cards. The list tries again on its own.";
// }
//
// const hide = () => void getCurrentWindow().hide().catch(() => {});
//
// export function DesktopAdvisor() {
//   // null = still asking Rust whether a session exists (no sign-in flash).
//   const [connected, setConnected] = useState<boolean | null>(null);
//   const [reason, setReason] = useState<string | null>(null);
//   useEffect(() => {
//     authState()
//       .then((s) => setConnected(s.status === "signed_in"))
//       .catch(() => setConnected(false));
//     // A server-side sign-out (revoked device, removed seat) flips the panel at once.
//     const un = onAuthChange((s) => {
//       if (s.status === "signed_in") setConnected(true);
//       if (s.status === "signed_out") {
//         setConnected(false);
//         setReason(s.reason);
//       }
//     });
//     return () => void un.then((f) => f());
//   }, []);
//   const signedOut = useCallback((why: string | null) => {
//     setReason(why);
//     setConnected(false);
//   }, []);
//
//   if (connected === null) return <div className="dx-shell" data-tauri-drag-region />;
//   if (!connected) return <SignIn reason={reason} onDone={() => setConnected(true)} onClose={hide} />;
//   return <Panel onSignedOut={signedOut} />;
// }
//
// type Toasted = { id: string; text: string; undo?: () => void };
//
// function Panel({ onSignedOut }: { onSignedOut: (reason: string | null) => void }) {
//   const capture = useCapture();
//   const [view, setView] = useState<View>("today");
//   const [openId, setOpenId] = useState<string | null>(null);
//   const [loops, setLoops] = useState<OpenLoop[]>([]);
//   const [cache, setCache] = useState<DetailCache>(() => new Map());
//   const cacheRef = useRef(cache);
//   const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
//   const [error, setError] = useState("");
//   const [refreshing, setRefreshing] = useState(false);
//   const [screenOnly, setScreenOnly] = useState(loadScreenOnly);
//   const [followups, setFollowups] = useState<Followup[]>([]);
//   const [recent, setRecent] = useState<RecentItem[]>([]);
//   const [hidden, setHidden] = useState<Set<string>>(() => new Set());
//   const [toast, setToast] = useState<Toasted | null>(null);
//   const [refusal, setRefusal] = useState<{ id: string; text: string } | null>(null);
//   const [busy, setBusy] = useState(false);
//   const timers = useRef(new Map<string, number>());
//   const bodyRef = useRef<HTMLDivElement>(null);
//   const listScroll = useRef(0);
//
//   const load = useCallback(
//     async (soft = false) => {
//       if (!soft) setPhase((p) => (p === "ready" ? p : "loading"));
//       try {
//         const queue = await loadQueue();
//         setLoops(queue);
//         setPhase("ready");
//         setError("");
//         const next = await fillDetails(cacheRef.current, queue.map((l) => l.card_id));
//         cacheRef.current = next;
//         setCache(next);
//       } catch (e) {
//         if (e instanceof ApiError && e.status === 401) return onSignedOut(null);
//         setError(loadError(e));
//         setPhase("error");
//       }
//     },
//     [onSignedOut],
//   );
//
//   const readScreen = useCallback(
//     () =>
//       Promise.all([
//         followupsOpen()
//           .then(setFollowups)
//           .catch(() => {}),
//         laneRecent()
//           .then(setRecent)
//           .catch(() => {}),
//       ]),
//     [],
//   );
//
//   useEffect(() => {
//     void load();
//     const onFocus = () => void load(true);
//     window.addEventListener("focus", onFocus);
//     const iv = setInterval(() => void load(true), REFRESH_MS);
//     return () => {
//       window.removeEventListener("focus", onFocus);
//       clearInterval(iv);
//     };
//   }, [load]);
//
//   useEffect(() => {
//     void readScreen();
//     const iv = setInterval(() => void readScreen(), 5000);
//     return () => clearInterval(iv);
//   }, [readScreen]);
//
//   // Coming back to the panel is the moment someone has just changed a setting on the website.
//   const { refreshPolicy } = capture;
//   useEffect(() => {
//     const un = getCurrentWindow().onFocusChanged(({ payload }) => payload && refreshPolicy());
//     return () => void un.then((f) => f());
//   }, [refreshPolicy]);
//
//   const refreshAll = useCallback(async () => {
//     setRefreshing(true);
//     refreshPolicy();
//     await Promise.all([load(true), readScreen(), new Promise((r) => setTimeout(r, 400))]);
//     setRefreshing(false);
//   }, [load, readScreen, refreshPolicy]);
//
//   const cards = useMemo(() => readOpen(loops, cache).filter((c) => !hidden.has(c.id)), [loops, cache, hidden]);
//   const items = useMemo(() => followups.filter((f) => !hidden.has(f.id)), [followups, hidden]);
//   const groups = useMemo(() => buildGroups(screenOnly ? [] : cards, items), [screenOnly, cards, items]);
//   const summary = summarize(groups, Date.now());
//   const open = openId ? (cards.find((c) => c.id === openId) ?? null) : null;
//   const also = useMemo(() => {
//     for (const g of groups) for (const r of g.rows) if (r.kind === "card" && r.key === openId) return r.also;
//     return [];
//   }, [groups, openId]);
//
//   const unhide = (id: string) =>
//     setHidden((h) => {
//       const n = new Set(h);
//       n.delete(id);
//       return n;
//     });
//
//   const say = (text: string) => {
//     const id = `note-${Date.now()}`;
//     setToast({ id, text });
//     setTimeout(() => setToast((t) => (t?.id === id ? null : t)), 4000);
//   };
//
//   const refuse = (id: string, label: string, e: unknown) => {
//     if (e instanceof ApiError && e.status === 401) return onSignedOut(null);
//     const text = refusalText(e instanceof ApiError ? e.status : 0, e instanceof ApiError ? e.message : "offline");
//     setRefusal({ id, text: id === openId ? text : `“${label}”: ${text}` });
//   };
//
//   /** Take it off the list now, send it in five seconds unless Undo; a refusal brings it back. */
//   const later = (id: string, label: string, toastText: string, send: () => Promise<unknown>) => {
//     setHidden((h) => new Set(h).add(id));
//     setRefusal(null);
//     if (id === openId) setOpenId(null);
//     const fire = async () => {
//       timers.current.delete(id);
//       setToast((t) => (t?.id === id ? null : t));
//       try {
//         await send();
//       } catch (e) {
//         refuse(id, label, e);
//       } finally {
//         await Promise.all([load(true), readScreen()]);
//         unhide(id);
//       }
//     };
//     const t = window.setTimeout(() => void fire(), UNDO_MS);
//     timers.current.set(id, t);
//     setToast({
//       id,
//       text: toastText,
//       undo: () => {
//         clearTimeout(t);
//         timers.current.delete(id);
//         unhide(id);
//         setToast(null);
//       },
//     });
//   };
//
//   const press = async (card: DeskCard, p: CardPress) => {
//     if (p.action === "do_it_myself") return later(card.id, card.headline, "Marked done", () => pressCard(card.id, p));
//     if (p.action === "snooze")
//       return later(
//         card.id,
//         card.headline,
//         `Put off · ${p.until ? new Date(p.until).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" }) + ", 9:00" : (SNOOZE_LABEL[p.snooze] ?? p.snooze)}`,
//         () => pressCard(card.id, p),
//       );
//     setBusy(true);
//     setRefusal(null);
//     try {
//       await pressCard(card.id, p);
//       if (p.action === "answer") {
//         say("Answer sent. GeniOS reads the thread again with it.");
//         cacheRef.current = new Map([...cacheRef.current].filter(([k]) => k !== card.id));
//       } else {
//         say("Feedback sent. GeniOS's reasoning reads it the next time it reviews this thread.");
//         setOpenId(null);
//       }
//     } catch (e) {
//       refuse(card.id, card.headline, e);
//     } finally {
//       setBusy(false);
//       void load(true);
//     }
//   };
//
//   const itemDone = (f: Followup) => later(f.id, f.text, "Done", () => followupDone(f.id));
//   const itemHandled = (f: Followup) => later(f.id, f.text, "Marked as already handled", () => followupHandled(f.id));
//   const itemTomorrow = (f: Followup) => later(f.id, f.text, "Reminding you tomorrow", () => followupSnooze(f.id, "tomorrow"));
//
//   const rate = (id: string, action: "useful" | "not_useful" | "mute_chat") => {
//     setRecent((cur) => cur.map((r) => (r.id === id ? { ...r, feedback: action } : r)));
//     void recentFeedback(id, action)
//       .catch(() => {})
//       .finally(() => setTimeout(() => void readScreen(), 300));
//   };
//
//   const openCard = (card: DeskCard) => {
//     listScroll.current = bodyRef.current?.scrollTop ?? 0;
//     setRefusal((r) => (r?.id === card.id ? r : null));
//     setOpenId(card.id);
//   };
//   const lastOpen = useRef<string | null>(null);
//   const back = useCallback(() => setOpenId(null), []);
//
//   // Opening a card starts at its top with Back focused; Back returns to the same place in the list.
//   useEffect(() => {
//     const body = bodyRef.current;
//     if (openId) {
//       lastOpen.current = openId;
//       if (body) body.scrollTop = 0;
//       document.querySelector<HTMLElement>(".dx-back")?.focus();
//     } else if (lastOpen.current) {
//       if (body) body.scrollTop = listScroll.current;
//       document.querySelector<HTMLElement>(`[data-card="${lastOpen.current}"] .dx-row-open`)?.focus({ preventScroll: true });
//       lastOpen.current = null;
//     }
//   }, [openId]);
//
//   // A card that closed elsewhere (the web, another device) closes here too.
//   useEffect(() => {
//     if (openId && phase === "ready" && !cards.some((c) => c.id === openId) && !hidden.has(openId)) setOpenId(null);
//   }, [openId, cards, phase, hidden]);
//
//   // Keys: Esc goes back, then hides the panel (a field only loses focus); ⌘R refreshes; ↑ ↓ move.
//   useEffect(() => {
//     const onKey = (e: KeyboardEvent) => {
//       if (e.defaultPrevented) return;
//       const target = e.target as HTMLElement | null;
//       const typing = Boolean(target?.closest?.("input, textarea"));
//       if (e.key === "Escape") {
//         e.preventDefault();
//         if (typing) target?.blur();
//         else if (openId) back();
//         else hide();
//         return;
//       }
//       if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "r") {
//         e.preventDefault();
//         void refreshAll();
//         return;
//       }
//       if (typing || (e.key !== "ArrowDown" && e.key !== "ArrowUp")) return;
//       const rows = [...document.querySelectorAll<HTMLElement>(".dx-body .dx-row-open")];
//       if (!rows.length) return;
//       e.preventDefault();
//       const i = rows.indexOf(document.activeElement as HTMLElement);
//       const next = e.key === "ArrowDown" ? (i < 0 ? 0 : Math.min(i + 1, rows.length - 1)) : Math.max(i - 1, 0);
//       rows[next].focus();
//       rows[next].scrollIntoView({ block: "nearest" });
//     };
//     window.addEventListener("keydown", onKey);
//     return () => window.removeEventListener("keydown", onKey);
//   }, [openId, back, refreshAll]);
//
//   const signOutHere = async () => {
//     timers.current.forEach((t) => clearTimeout(t));
//     timers.current.clear();
//     await signOut().catch(() => {});
//     onSignedOut(null);
//   };
//
//   const status = capture.status;
//   const setupShowing = Boolean(status && (status.state === "needs_accessibility" || status.state === "off_by_policy"));
//   const openWeb = () => void openDashboard("/dashboard/cards").catch(() => {});
//
//   return (
//     <div className="dx-shell" data-tauri-drag-region>
//       <Header
//         view={view}
//         onView={(v) => {
//           setView(v);
//           setOpenId(null);
//         }}
//         back={open ? { label: VIEW_LABEL[view], onBack: back } : undefined}
//         capture={status}
//         onPause={(m) => void capture.pause(m)}
//         onResume={() => void capture.resume()}
//         screenOnly={screenOnly}
//         onScreenOnly={(on) => {
//           setScreenOnly(on);
//           saveScreenOnly(on);
//         }}
//         refreshing={refreshing}
//         onRefresh={() => void refreshAll()}
//         onOpenWeb={openWeb}
//         onSignOut={() => void signOutHere()}
//         onClose={hide}
//       />
//       <div className="dx-main">
//         <div className="dx-body" ref={bodyRef}>
//           {open ? (
//             <CardDetail
//               card={open}
//               also={also}
//               busy={busy}
//               onAnswer={(words) => void press(open, { action: "answer", words })}
//               onItemDone={itemDone}
//               onItemHandled={itemHandled}
//               onItemTomorrow={itemTomorrow}
//             />
//           ) : view === "today" ? (
//             <TodayView
//               groups={groups}
//               summary={summary}
//               phase={phase}
//               error={error}
//               notice={refusal && refusal.id !== openId ? refusal.text : null}
//               screenOnly={screenOnly}
//               hiddenTools={screenOnly ? cards.length : 0}
//               setup={<SetupCard status={status} hasItems={cards.length + items.length > 0} onAccessibility={capture.openAccessibility} onTurnOn={capture.turnOn} />}
//               onRetry={() => void load()}
//               onShowAll={() => {
//                 setScreenOnly(false);
//                 saveScreenOnly(false);
//               }}
//               onOpen={openCard}
//               onDone={(c) => void press(c, { action: "do_it_myself" })}
//               onItemDone={itemDone}
//               onItemHandled={itemHandled}
//               onItemTomorrow={itemTomorrow}
//             />
//           ) : view === "week" ? (
//             <WeekView />
//           ) : (
//             <HistoryView recent={recent} onRate={rate} />
//           )}
//         </div>
//         {toast && (
//           <Toast action={toast.undo ? "Undo" : undefined} onAction={toast.undo}>
//             {toast.text}
//           </Toast>
//         )}
//       </div>
//       {open ? (
//         <ActionBar
//           card={open}
//           busy={busy}
//           refusal={refusal?.id === open.id ? refusal.text : null}
//           onPress={(p) => void press(open, p)}
//           onOpenWeb={openWeb}
//         />
//       ) : (
//         <CaptureBar
//           status={status}
//           error={capture.error}
//           setupShowing={setupShowing && view === "today"}
//           onPause={() => void capture.pause(15)}
//           onResume={() => void capture.resume()}
//           onSync={() => void capture.sync()}
//           onAccessibility={() => void capture.openAccessibility()}
//           onTurnOn={() => void capture.turnOn()}
//         />
//       )}
//     </div>
//   );
// }
```

#### `src/desktop/panel.css`

```css
// /* The panel's frame: top bar, the scrolling page with its toast, and the foot (reading bar, or an open card's buttons). */
// .dx-main {
//   position: relative;
//   flex: 1;
//   min-height: 0;
//   display: flex;
//   flex-direction: column;
// }
// .dx-main .dx-toast {
//   bottom: 12px;
// }
// /* Nothing in the page may be wider than the page: long tags and lines shrink or wrap. */
// .dx-body > * {
//   min-width: 0;
// }
```

#### `src/desktop/Header.tsx`

```tsx
// // The top of the panel: the mark and Today / This week / History (or Back on an open card), a menu
// // for what is rarely needed, and close. Sign out sits in the menu behind a confirm: it ends this
// // Mac's session and deletes everything GeniOS kept here, so it is never one stray click.
// import { useCallback, useState } from "react";
// import { ChevronLeft, Ellipsis, Globe, LogOut, Pause, Play, RefreshCw, X } from "lucide-react";
// import type { CaptureStatus } from "./api";
// import { Button, IconButton, MenuItem, MenuSep, Popover, Tabs } from "./ui";
// import "./Header.css";
//
// export type View = "today" | "week" | "history";
//
// const VIEWS: { id: View; label: string }[] = [
//   { id: "today", label: "Today" },
//   { id: "week", label: "This week" },
//   { id: "history", label: "History" },
// ];
//
// const PAUSABLE = new Set(["capturing", "idle", "starting"]);
//
// export function Header({
//   view,
//   onView,
//   back,
//   capture,
//   onPause,
//   onResume,
//   screenOnly,
//   onScreenOnly,
//   refreshing,
//   onRefresh,
//   onOpenWeb,
//   onSignOut,
//   onClose,
// }: {
//   view: View;
//   onView: (v: View) => void;
//   /** Set while a card is open: the bar shows Back instead of the views. */
//   back?: { label: string; onBack: () => void };
//   capture: CaptureStatus | null;
//   onPause: (minutes: number) => void;
//   onResume: () => void;
//   screenOnly: boolean;
//   onScreenOnly: (on: boolean) => void;
//   refreshing: boolean;
//   onRefresh: () => void;
//   onOpenWeb: () => void;
//   onSignOut: () => void;
//   onClose: () => void;
// }) {
//   const [menu, setMenu] = useState(false);
//   const [confirming, setConfirming] = useState(false);
//   const close = useCallback(() => {
//     setMenu(false);
//     setConfirming(false);
//   }, []);
//   const run = (f: () => void) => () => {
//     close();
//     f();
//   };
//
//   return (
//     <header className="dx-head" data-tauri-drag-region>
//       {back ? (
//         <button type="button" className="dx-back" onClick={back.onBack}>
//           <ChevronLeft size={17} strokeWidth={2} aria-hidden />
//           {back.label}
//         </button>
//       ) : (
//         <>
//           <span className="dx-mark" aria-label="GeniOS" data-tauri-drag-region>
//             G
//           </span>
//           <Tabs label="View" value={view} onChange={onView} options={VIEWS} />
//         </>
//       )}
//       <span className="dx-head-fill" data-tauri-drag-region />
//       <Popover
//         label="More"
//         open={menu}
//         onClose={close}
//         trigger={<IconButton label="More" icon={Ellipsis} aria-haspopup="menu" aria-expanded={menu} onClick={() => (menu ? close() : setMenu(true))} />}
//       >
//         {confirming ? (
//           <div className="dx-confirm" role="alertdialog" aria-label="Sign out">
//             <p>
//               <b>Sign out of this Mac?</b> GeniOS stops reading your screen here and deletes what it kept on this Mac.
//             </p>
//             <div>
//               <Button small onClick={() => setConfirming(false)}>
//                 Cancel
//               </Button>
//               <Button small kind="ink" onClick={run(onSignOut)}>
//                 Sign out
//               </Button>
//             </div>
//           </div>
//         ) : (
//           <>
//             <MenuItem icon={RefreshCw} kbd="⌘R" disabled={refreshing} onClick={run(onRefresh)}>
//               {refreshing ? "Refreshing…" : "Refresh"}
//             </MenuItem>
//             {capture && PAUSABLE.has(capture.state) && (
//               <>
//                 <MenuItem icon={Pause} onClick={run(() => onPause(15))}>
//                   Pause reading for 15 min
//                 </MenuItem>
//                 <MenuItem icon={Pause} onClick={run(() => onPause(60))}>
//                   Pause reading for 1 hour
//                 </MenuItem>
//               </>
//             )}
//             {capture?.state === "paused" && (
//               <MenuItem icon={Play} onClick={run(onResume)}>
//                 Resume reading
//               </MenuItem>
//             )}
//             <MenuItem checked={screenOnly} onClick={run(() => onScreenOnly(!screenOnly))}>
//               Only what's on my screen
//             </MenuItem>
//             <MenuItem icon={Globe} onClick={run(onOpenWeb)}>
//               Open GeniOS on the web
//             </MenuItem>
//             <MenuSep />
//             <MenuItem icon={LogOut} onClick={() => setConfirming(true)}>
//               Sign out of this Mac…
//             </MenuItem>
//           </>
//         )}
//       </Popover>
//       <IconButton label="Close" icon={X} onClick={onClose} />
//     </header>
//   );
// }
```

#### `src/desktop/Header.css`

```css
// /* The panel's top bar: the mark and the three views, or Back on an open card; the menu; close. */
// .dx-head {
//   flex: none;
//   display: flex;
//   align-items: center;
//   gap: 8px;
//   height: 48px;
//   padding: 0 8px 0 12px;
//   border-bottom: 1px solid var(--dx-line);
//   background: var(--dx-page);
// }
// .dx-head-fill {
//   flex: 1;
//   align-self: stretch;
// }
// .dx-mark {
//   display: grid;
//   place-items: center;
//   width: 24px;
//   height: 24px;
//   border-radius: 7px;
//   background: var(--dx-ink);
//   color: var(--dx-on-ink);
//   font-size: 13px;
//   font-weight: 400;
//   flex: none;
// }
// .dx-back {
//   display: inline-flex;
//   align-items: center;
//   gap: 2px;
//   height: 30px;
//   padding: 0 10px 0 4px;
//   border: 0;
//   border-radius: 7px;
//   background: transparent;
//   font-size: 13px;
//   font-weight: 400;
//   color: var(--dx-ink-2);
// }
// .dx-back:hover {
//   background: var(--dx-hover);
//   color: var(--dx-ink);
// }
// .dx-confirm {
//   display: grid;
//   gap: 10px;
//   padding: 8px 9px 6px;
//   max-width: 260px;
// }
// .dx-confirm p {
//   font-size: 13px;
//   line-height: 1.45;
//   color: var(--dx-ink-2);
// }
// .dx-confirm p b {
//   color: var(--dx-ink);
// }
// .dx-confirm div {
//   display: flex;
//   justify-content: flex-end;
//   gap: 6px;
// }
```

#### `src/desktop/TodayView.tsx`

```tsx
// // Today: everything that asks something of you, grouped by what it asks, in one list.
// import { CircleAlert, Inbox, RefreshCw } from "lucide-react";
// import type { Followup } from "./api";
// import type { DeskCard } from "./cards";
// import { CardRow } from "./CardRow";
// import { ScreenRow } from "./ScreenRow";
// import type { Group } from "./rows";
// import { Button, Empty, Eyebrow, Notice, Skeleton } from "./ui";
// import "./rows.css";
//
// export function TodayView({
//   groups,
//   summary,
//   phase,
//   error,
//   notice,
//   screenOnly,
//   hiddenTools,
//   setup,
//   onRetry,
//   onShowAll,
//   onOpen,
//   onDone,
//   onItemDone,
//   onItemHandled,
//   onItemTomorrow,
// }: {
//   groups: Group[];
//   summary: { needYou: number; urgent: number };
//   phase: "loading" | "ready" | "error";
//   error: string;
//   /** A refused press on a card that is not open: kept until the next press. */
//   notice: string | null;
//   screenOnly: boolean;
//   hiddenTools: number;
//   setup: React.ReactNode;
//   onRetry: () => void;
//   onShowAll: () => void;
//   onOpen: (card: DeskCard) => void;
//   onDone: (card: DeskCard) => void;
//   onItemDone: (f: Followup) => void;
//   onItemHandled: (f: Followup) => void;
//   onItemTomorrow: (f: Followup) => void;
// }) {
//   const empty = phase === "ready" && groups.length === 0;
//   return (
//     <>
//       {setup}
//       {screenOnly && (
//         <div className="dx-notice" role="status">
//           <span>
//             Showing only what was read off your screen{hiddenTools > 0 ? ` · ${hiddenTools} from your tools hidden` : ""}.{" "}
//             <button type="button" className="dx-btn link sm" onClick={onShowAll}>
//               Show all
//             </button>
//           </span>
//         </div>
//       )}
//       {notice && <Notice icon={CircleAlert}>{notice}</Notice>}
//       {phase === "error" && (
//         <div className="dx-card" style={{ padding: 14, display: "grid", gap: 10 }} role="alert">
//           <div>Couldn't load your cards</div>
//           <div className="dx-hint">{error}</div>
//           <div>
//             <Button small icon={RefreshCw} onClick={onRetry}>
//               Try again
//             </Button>
//           </div>
//         </div>
//       )}
//       {phase === "loading" && groups.length === 0 && (
//         <div aria-label="Loading" style={{ display: "grid", gap: 8 }}>
//           {[0, 1, 2].map((i) => (
//             <div key={i} className="dx-card" style={{ padding: 14, display: "grid", gap: 8 }}>
//               <Skeleton width={120} height={20} />
//               <Skeleton width="85%" height={14} />
//               <Skeleton width="60%" />
//             </div>
//           ))}
//         </div>
//       )}
//       {empty && (
//         <Empty icon={Inbox} title="Nothing needs you right now">
//           <p>When GeniOS finds something that needs a decision or an answer, it shows up here.</p>
//         </Empty>
//       )}
//       {groups.length > 0 && (
//         <p className="dx-lead" aria-label="Summary">
//           <b>{summary.needYou}</b> need{summary.needYou === 1 ? "s" : ""} you{summary.urgent > 0 ? ` · ${summary.urgent} urgent` : ""}
//         </p>
//       )}
//       {groups.map((g) => (
//         <section key={g.id} aria-label={g.title} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr)", gap: 8 }}>
//           <div style={{ display: "grid", gap: 2 }}>
//             <Eyebrow count={g.rows.length}>{g.title}</Eyebrow>
//             <span className="dx-hint">{g.hint}</span>
//           </div>
//           <ul className="dx-rows">
//             {g.rows.map((r) =>
//               r.kind === "card" ? (
//                 <CardRow key={r.key} card={r.card} also={r.also} onOpen={onOpen} onDone={onDone} />
//               ) : (
//                 <ScreenRow key={r.key} item={r.item} onDone={onItemDone} onHandled={onItemHandled} onTomorrow={onItemTomorrow} />
//               ),
//             )}
//           </ul>
//         </section>
//       ))}
//     </>
//   );
// }
```

#### `src/desktop/CardRow.tsx`

```tsx
// // A card's face in Today: where it came from, a subject that is an action, one or two lines on
// // what to do and how, who it is about and by when. Done is the circle; the rest is one click in.
// import { Check, Eye, Hourglass, MessageCircleQuestion } from "lucide-react";
// import type { Followup } from "./api";
// import type { DeskCard } from "./cards";
// import { Skeleton, Status, Tag } from "./ui";
// import "./rows.css";
//
// const same = (a?: string, b?: string) => (a ?? "").toLowerCase().replace(/[“”".]/g, "").trim() === (b ?? "").toLowerCase().replace(/[“”".]/g, "").trim();
//
// /** The two lines under the subject: what to do and how — or, on a question, why it is asked. */
// export function faceLines(card: DeskCard): { line?: string; how?: string } {
//   if (card.lane === "question") return { line: card.question?.because ?? (card.description || undefined) };
//   if (card.lane === "waiting" || card.answered) return { line: card.whyNow ?? (card.description || undefined) };
//   const move = card.todo?.line;
//   const line = move && !same(move, card.headline) ? move : card.description || undefined;
//   const how = card.how && !same(card.how, line) && !same(card.how, card.headline) ? card.how : undefined;
//   return { line, how };
// }
//
// export function CardRow({
//   card,
//   also = [],
//   onOpen,
//   onDone,
// }: {
//   card: DeskCard;
//   also?: Followup[];
//   onOpen: (card: DeskCard) => void;
//   onDone: (card: DeskCard) => void;
// }) {
//   const { line, how } = faceLines(card);
//   const asks = card.lane === "question" && !card.answered;
//   const canDone = card.offers.done && !asks && !card.answered;
//   return (
//     <li className="dx-row" data-card={card.id}>
//       {canDone ? (
//         <button type="button" className="dx-check" aria-label={`Done: ${card.headline}`} title="Mark done" onClick={() => onDone(card)}>
//           <Check size={13} strokeWidth={2.6} aria-hidden />
//         </button>
//       ) : (
//         <span className="dx-glyph" aria-hidden>
//           {asks ? <MessageCircleQuestion size={13} strokeWidth={2.2} /> : <Hourglass size={12} strokeWidth={2.2} />}
//         </span>
//       )}
//       <div className="dx-row-main">
//         <div className="dx-row-tags">
//           {card.loaded ? card.tools.map((t) => <Tag key={t.tool} tool={t.tool} how={t.how} />) : <Skeleton width={110} height={22} />}
//           {card.age && <span className="dx-row-age">{card.age}</span>}
//         </div>
//         <h3 className="dx-row-subject">
//           <button type="button" className="dx-row-open" onClick={() => onOpen(card)}>
//             {card.headline}
//           </button>
//         </h3>
//         {line && <p className="dx-row-line">{line}</p>}
//         {how && <p className="dx-row-how">How: {how}</p>}
//         <p className="dx-row-meta">
//           {card.who && <span>{[card.who, card.role].filter(Boolean).join(" · ")}</span>}
//           {card.due && <span>{card.due}</span>}
//           {asks && <span>Answer it</span>}
//           {card.answered && <span>Your answer is in</span>}
//           {card.urgency !== "standard" && <Status tone="accent">{card.urgency === "critical" ? "Critical" : "High"}</Status>}
//         </p>
//         {also.length > 0 && (
//           <p className="dx-row-also">
//             <Eye size={13} strokeWidth={2} aria-hidden />
//             <span>
//               Also on your screen: {also[0].text}
//               {also.length > 1 ? ` and ${also.length - 1} more` : ""}
//             </span>
//           </p>
//         )}
//       </div>
//     </li>
//   );
// }
```

#### `src/desktop/ScreenRow.tsx`

```tsx
// // An item caught on the screen, in the same face as a card: where it was seen, the line, the words
// // that caused it, whose it is and by when. Done is the circle; opening it shows the other two:
// // Already handled (it was real, and done where GeniOS cannot see) and Tomorrow.
// import { useState } from "react";
// import { Check } from "lucide-react";
// import type { Followup } from "./api";
// import { Button, Tag, toolIcon } from "./ui";
// import "./rows.css";
//
// const BUNDLE_APP: Record<string, string> = {
//   "net.whatsapp.WhatsApp": "WhatsApp",
//   "desktop.WhatsApp": "WhatsApp",
//   "whatsapp.exe": "WhatsApp",
//   "com.tinyspeck.slackmacgap": "Slack",
//   "slack.exe": "Slack",
//   "com.microsoft.Outlook": "Outlook",
//   "outlook.exe": "Outlook",
//   "olk.exe": "Outlook",
//   "com.apple.mail": "Mail",
//   "com.microsoft.teams2": "Teams",
//   "ms-teams.exe": "Teams",
//   "ru.keepcoder.Telegram": "Telegram",
//   "telegram.exe": "Telegram",
//   "com.apple.Notes": "Notes",
//   "notion.id": "Notion",
//   "us.zoom.xos": "Zoom",
// };
// const HOST_APP: [RegExp, string][] = [
//   [/(^|\.)mail\.google\.com$/, "Gmail"],
//   [/(^|\.)web\.whatsapp\.com$/, "WhatsApp"],
//   [/(^|\.)slack\.com$/, "Slack"],
//   [/(^|\.)linkedin\.com$/, "LinkedIn"],
//   [/(^|\.)outlook\.(live|office|office365)\.com$/, "Outlook"],
//   [/(^|\.)teams\.microsoft\.com$/, "Teams"],
//   [/(^|\.)notion\.so$/, "Notion"],
//   [/(^|\.)calendar\.google\.com$/, "Google Calendar"],
//   [/(^|\.)docs\.google\.com$/, "Google Docs"],
//   [/(^|\.)hubspot\.com$/, "HubSpot"],
// ];
//
// /** Where it was seen, in the person's words: the chat's app, or the site it was on. */
// export function screenApp(f: Followup): string {
//   const key = f.thread_key || "";
//   if (key.startsWith("wa:")) return "WhatsApp";
//   if (key.startsWith("li:")) return "LinkedIn";
//   const m = key.match(/^doc:([^:]+):(.*)$/);
//   if (m) {
//     const [, bundle, rest] = m;
//     if (!rest.startsWith("title:")) {
//       const host = rest.split("/")[0].toLowerCase().replace(/^www\./, "");
//       const hit = HOST_APP.find(([re]) => re.test(host));
//       if (hit) return hit[1];
//       if (host) return host;
//     }
//     if (BUNDLE_APP[bundle]) return BUNDLE_APP[bundle];
//   }
//   const app = (f.app || "").trim();
//   if (!app || app === "generic") return "Screen";
//   return BUNDLE_APP[app] || app.charAt(0).toUpperCase() + app.slice(1);
// }
//
// const KIND: Record<string, string> = {
//   ask: "Asked of you",
//   my_promise: "Your promise",
//   their_promise: "They promised",
//   deadline: "Deadline",
//   risk: "Risk",
//   next_step: "Next step",
// };
//
// const DAY = { weekday: "short", day: "numeric", month: "short" } as const;
//
// function seenAt(iso: string | null | undefined, now: number): string {
//   const d = iso ? new Date(iso) : null;
//   if (!d || Number.isNaN(d.getTime())) return "";
//   return d.toDateString() === new Date(now).toDateString()
//     ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
//     : d.toLocaleDateString([], DAY);
// }
//
// /** “due today, 6:00 pm” · “due Sat 24 Oct” · “was due Tue 21 Oct” (late). */
// export function dueWords(iso: string | null | undefined, now: number): { text: string; late: boolean } | null {
//   const d = iso ? new Date(iso) : null;
//   if (!d || Number.isNaN(d.getTime())) return null;
//   const today = d.toDateString() === new Date(now).toDateString();
//   if (today) return { text: `due today, ${d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`, late: d.getTime() < now };
//   if (d.getTime() < now) return { text: `was due ${d.toLocaleDateString([], DAY)}`, late: true };
//   return { text: `due ${d.toLocaleDateString([], DAY)}`, late: false };
// }
//
// export function ScreenRow({
//   item,
//   now = Date.now(),
//   onDone,
//   onHandled,
//   onTomorrow,
// }: {
//   item: Followup;
//   now?: number;
//   onDone: (f: Followup) => void;
//   onHandled: (f: Followup) => void;
//   onTomorrow: (f: Followup) => void;
// }) {
//   const [open, setOpen] = useState(false);
//   const app = screenApp(item);
//   const due = dueWords(item.due_at, now);
//   return (
//     <li className="dx-row" data-item={item.id}>
//       <button type="button" className="dx-check" aria-label={`Done: ${item.text}`} title="Mark done" onClick={() => onDone(item)}>
//         <Check size={13} strokeWidth={2.6} aria-hidden />
//       </button>
//       <div className="dx-row-main">
//         <div className="dx-row-tags">
//           <Tag tool={app} how="screen" icon={toolIcon(app)} />
//           <span className="dx-row-age">{seenAt(item.created_at, now)}</span>
//         </div>
//         <h3 className="dx-row-subject">
//           <button type="button" className="dx-row-open" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
//             {item.text}
//           </button>
//         </h3>
//         {item.quote && <p className="dx-row-quote">“{item.quote}”</p>}
//         <p className="dx-row-meta">
//           <span>{KIND[item.kind] ?? "Follow-up"}</span>
//           {item.who && <span>{item.who}</span>}
//           {due && <span className={due.late ? "late" : undefined}>{due.text}</span>}
//         </p>
//         {open && (
//           <div className="dx-row-actions">
//             <Button small kind="ink" onClick={() => onDone(item)}>
//               Done
//             </Button>
//             <Button small onClick={() => onHandled(item)} title="It was real, and you did it somewhere GeniOS cannot see">
//               Already handled
//             </Button>
//             <Button small onClick={() => onTomorrow(item)}>
//               Tomorrow
//             </Button>
//           </div>
//         )}
//       </div>
//     </li>
//   );
// }
```

#### `src/desktop/rows.css`

```css
// /* A row in Today: a card's face, or an item caught on the screen. One look for both. */
// .dx-rows {
//   min-width: 0;
//   list-style: none;
//   padding: 0;
//   display: flex;
//   flex-direction: column;
//   gap: 8px;
// }
// .dx-row {
//   position: relative;
//   display: flex;
//   gap: 11px;
//   padding: 12px 14px 12px 12px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line);
//   border-radius: var(--dx-r-card);
//   box-shadow: var(--dx-shadow-1);
//   transition: box-shadow 0.14s, border-color 0.14s;
// }
// .dx-row:hover {
//   box-shadow: var(--dx-shadow-2);
//   border-color: var(--dx-line-strong);
// }
// .dx-row:focus-within {
//   border-color: var(--dx-line-strong);
// }
// .dx-row-main {
//   flex: 1;
//   min-width: 0;
//   display: flex;
//   flex-direction: column;
//   gap: 4px;
// }
// .dx-row-tags {
//   display: flex;
//   align-items: center;
//   gap: 5px;
//   min-width: 0;
//   overflow: hidden;
//   margin-bottom: 2px;
// }
// .dx-row-tags .dx-tag {
//   flex: none;
//   max-width: 62%;
// }
// .dx-row-tags .dx-tag + .dx-tag {
//   flex: 0 1 auto;
// }
// .dx-row-age {
//   margin-left: auto;
//   padding-left: 6px;
//   flex: none;
//   font-size: 12px;
//   color: var(--dx-mist);
//   white-space: nowrap;
// }
// .dx-row-subject {
//   font-size: 14.5px;
//   font-weight: 560;
//   line-height: 1.3;
//   letter-spacing: -0.005em;
// }
// /* The whole row opens it; the subject is the one real button, stretched over the row. */
// .dx-row-open {
//   padding: 0;
//   border: 0;
//   background: none;
//   font: inherit;
//   text-align: left;
//   color: var(--dx-ink);
// }
// .dx-row-open::after {
//   content: "";
//   position: absolute;
//   inset: 0;
//   border-radius: var(--dx-r-card);
// }
// .dx-row-open:focus-visible {
//   box-shadow: none;
// }
// .dx-row-open:focus-visible::after {
//   box-shadow: var(--dx-focus);
// }
// .dx-row-line,
// .dx-row-how {
//   font-size: 13px;
//   line-height: 1.42;
//   color: var(--dx-ink-2);
//   display: -webkit-box;
//   -webkit-box-orient: vertical;
//   -webkit-line-clamp: 2;
//   overflow: hidden;
// }
// .dx-row-how {
//   color: var(--dx-mist);
//   -webkit-line-clamp: 1;
// }
// .dx-row-quote {
//   font-size: 13px;
//   line-height: 1.42;
//   color: var(--dx-ink-2);
//   font-style: italic;
//   display: -webkit-box;
//   -webkit-box-orient: vertical;
//   -webkit-line-clamp: 2;
//   overflow: hidden;
// }
// .dx-row-meta {
//   display: flex;
//   flex-wrap: wrap;
//   align-items: center;
//   gap: 2px 10px;
//   margin-top: 2px;
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .dx-row-meta > span {
//   display: inline-flex;
//   align-items: center;
//   gap: 4px;
// }
// .dx-row-meta .late {
//   color: var(--dx-accent);
//   font-weight: 400;
// }
// .dx-row-also {
//   display: flex;
//   align-items: flex-start;
//   gap: 6px;
//   margin-top: 4px;
//   padding: 7px 9px;
//   border-radius: 8px;
//   background: var(--dx-inset);
//   font-size: 12.5px;
//   line-height: 1.4;
//   color: var(--dx-ink-2);
// }
// .dx-row-also svg {
//   flex: none;
//   margin-top: 2px;
//   color: var(--dx-mist);
// }
// .dx-row-actions {
//   position: relative;
//   z-index: 1;
//   display: flex;
//   flex-wrap: wrap;
//   gap: 6px;
//   margin-top: 6px;
// }
//
// /* Done, as on a to-do list: an empty circle that fills on hover. Above the stretched button. */
// .dx-check {
//   position: relative;
//   z-index: 1;
//   flex: none;
//   display: grid;
//   place-items: center;
//   width: 20px;
//   height: 20px;
//   margin-top: 1px;
//   padding: 0;
//   border: 1.5px solid var(--dx-faint);
//   border-radius: 50%;
//   background: var(--dx-card);
//   color: transparent;
//   transition: background 0.12s, border-color 0.12s, color 0.12s;
// }
// .dx-check:hover,
// .dx-check:focus-visible {
//   border-color: var(--dx-ink);
//   color: var(--dx-ink);
// }
// .dx-check:active {
//   background: var(--dx-ink);
//   color: var(--dx-on-ink);
// }
// .dx-glyph {
//   flex: none;
//   display: grid;
//   place-items: center;
//   width: 20px;
//   height: 20px;
//   margin-top: 1px;
//   border-radius: 50%;
//   background: var(--dx-inset-2);
//   color: var(--dx-ink-2);
// }
```

#### `src/desktop/CardDetail.tsx`

```tsx
// // An opened card, on a page of its own, in the order Rohit set (06-CARDS/02-CARD-DEFINITION):
// // recommendation · what · why · how · what doing it gets you · goal · deadline · where it came
// // from — essentials first, the rest under Show more, one tab at a time. Only this card's own
// // details: what other open cards repeat was left out by the reader (ownCard), and it says so.
// import { useState } from "react";
// import { Info, Send } from "lucide-react";
// import type { Followup } from "./api";
// import type { DeskCard } from "./cards";
// import { ScreenRow } from "./ScreenRow";
// import { Button, Chip, Eyebrow, Field, Fields, Notice, Status, Tabs, Tag } from "./ui";
// import "./detail.css";
//
// type More = "slips" | "details" | "sources";
//
// function Head({ card }: { card: DeskCard }) {
//   const asks = card.lane === "question" && !card.answered;
//   // The move itself is the recommendation's first line below: the head says only whose and by when.
//   const meta = [[card.who, card.role].filter(Boolean).join(" · "), card.due].filter(Boolean);
//   return (
//     <div className="dx-d-head">
//       <div className="dx-d-tags">
//         {card.tools.map((t) => (
//           <Tag key={t.tool} tool={t.tool} how={t.how} />
//         ))}
//         {card.domain && <Chip>{card.domain.charAt(0).toUpperCase() + card.domain.slice(1)}</Chip>}
//         {card.age && <span className="dx-meta">{card.age}</span>}
//       </div>
//       <div className="dx-d-status">
//         {card.urgency !== "standard" && <Status tone="accent">{card.urgency === "critical" ? "Critical" : "High"}</Status>}
//         <span>{card.answered ? "Waiting · your answer is in" : card.laneLabel}</span>
//       </div>
//       <h2 className="dx-title dx-selectable">{card.headline}</h2>
//       {asks && card.question?.because && <p className="dx-lead dx-selectable">Why we ask: {card.question.because}</p>}
//       {meta.length > 0 && <p className="dx-meta">{meta.join(" · ")}</p>}
//     </div>
//   );
// }
//
// function Recommendation({ card }: { card: DeskCard }) {
//   const todo = card.todo;
//   if (!todo) return null;
//   const foot = [todo.who && `${todo.who}`, todo.forWhom && `for ${todo.forWhom}`, todo.by && `by ${todo.by}`].filter(Boolean).join(" · ");
//   return (
//     <section className="dx-card dx-reco" aria-label="Recommendation">
//       <Eyebrow>Recommendation</Eyebrow>
//       <p className="dx-reco-line dx-selectable">{todo.line}</p>
//       {todo.steps.length > 0 && (
//         <ol className="dx-steps dx-selectable">
//           {todo.steps.map((s) => (
//             <li key={s}>{s}</li>
//           ))}
//         </ol>
//       )}
//       {todo.avoid && (
//         <p className="dx-reco-foot">
//           <b>Avoid:</b> {todo.avoid}
//         </p>
//       )}
//       {foot && <p className="dx-reco-foot">{foot}</p>}
//     </section>
//   );
// }
//
// function sourceLine(card: DeskCard): string {
//   const tools = card.tools.map((t) => `${t.tool} · ${t.how}`).join(", ");
//   const done = card.conversation.filter((e) => !e.upcoming);
//   const past = done[done.length - 1];
//   return [tools, past && `${past.text}, ${past.when}`].filter(Boolean).join(" — ");
// }
//
// function Slips({ card }: { card: DeskCard }) {
//   const rows = [
//     ["If you do nothing", card.ifNothing],
//     ["If it can't be done", card.otherwise],
//     ["Wait or stop", card.waitOrStop],
//   ].filter((r): r is [string, string] => Boolean(r[1]));
//   if (!rows.length) return <p className="dx-hint">This card says nothing of its own about what happens if it slips.</p>;
//   return (
//     <Fields>
//       {rows.map(([label, text]) => (
//         <Field key={label} label={label}>
//           {text}
//         </Field>
//       ))}
//     </Fields>
//   );
// }
//
// function Details({ card }: { card: DeskCard }) {
//   const said = card.why.filter((w) => w.kind === "said");
//   // "reading" is why-now, already the Why line above.
//   const records = card.why.filter((w) => w.kind === "fact" || w.kind === "meeting" || w.kind === "promise");
//   const rules = card.why.filter((w) => w.kind === "rule");
//   return (
//     <div className="dx-more">
//       {(card.who || card.role) && (
//         <Fields>
//           {card.who && <Field label="Who">{card.who}</Field>}
//           {card.role && <Field label="Role">{card.role}</Field>}
//         </Fields>
//       )}
//       {said.length > 0 && (
//         <>
//           <Eyebrow>What was said</Eyebrow>
//           {said.map((w) => (
//             <p key={w.text} className="dx-quote dx-selectable">
//               {w.text}
//             </p>
//           ))}
//         </>
//       )}
//       {records.length > 0 && (
//         <>
//           <Eyebrow>What the records show</Eyebrow>
//           <ul className="dx-lines">
//             {records.map((w, i) => (
//               <li key={`${i}-${w.text}`}>
//                 <span>{w.text}</span>
//                 <small>{[w.from, w.when].filter(Boolean).join(" · ")}</small>
//               </li>
//             ))}
//           </ul>
//         </>
//       )}
//       {card.promised.length > 0 && (
//         <>
//           <Eyebrow>What was promised</Eyebrow>
//           <ul className="dx-lines">
//             {card.promised.map((p) => (
//               <li key={p.text}>
//                 <span>{p.text}</span>
//                 {(p.due || p.status) && <small>{[p.due && `due ${p.due}`, p.status].filter(Boolean).join(" · ")}</small>}
//               </li>
//             ))}
//           </ul>
//         </>
//       )}
//       {rules.length > 0 && (
//         <>
//           <Eyebrow>How this is handled</Eyebrow>
//           <ul className="dx-lines">
//             {rules.map((w) => (
//               <li key={w.text}>
//                 <span>{w.text}</span>
//                 <small>{w.from}</small>
//               </li>
//             ))}
//           </ul>
//         </>
//       )}
//       {card.signals.length > 0 && (
//         <div className="dx-d-tags">
//           {card.signals.map((s) => (
//             <Chip key={s}>{s}</Chip>
//           ))}
//         </div>
//       )}
//       {card.leftOut > 0 && (
//         <p className="dx-hint">
//           {card.leftOut} {card.leftOut === 1 ? "line reads" : "lines read"} the same on your other cards, so {card.leftOut === 1 ? "it is" : "they are"} left
//           out here.
//         </p>
//       )}
//     </div>
//   );
// }
//
// function Sources({ card }: { card: DeskCard }) {
//   return (
//     <div className="dx-more">
//       <div className="dx-d-tags">
//         {card.tools.map((t) => (
//           <Tag key={t.tool} tool={t.tool} how={t.how} />
//         ))}
//       </div>
//       {card.conversation.length > 0 ? (
//         <ul className="dx-lines">
//           {card.conversation.map((e) => (
//             <li key={`${e.at}-${e.text}`}>
//               <span>{e.text}</span>
//               <small>{[e.from, e.when, e.upcoming && "coming up"].filter(Boolean).join(" · ")}</small>
//             </li>
//           ))}
//         </ul>
//       ) : (
//         <p className="dx-hint">No dated mail or meeting of its own on this card.</p>
//       )}
//     </div>
//   );
// }
//
// export function CardDetail({
//   card,
//   also,
//   busy,
//   onAnswer,
//   onItemDone,
//   onItemHandled,
//   onItemTomorrow,
// }: {
//   card: DeskCard;
//   also: Followup[];
//   busy: boolean;
//   onAnswer: (words: string) => void;
//   onItemDone: (f: Followup) => void;
//   onItemHandled: (f: Followup) => void;
//   onItemTomorrow: (f: Followup) => void;
// }) {
//   const [more, setMore] = useState<More | null>(null);
//   const [answer, setAnswer] = useState("");
//   const asks = card.lane === "question" && !card.answered;
//   const deadline = card.due ?? (card.window ? `within ${card.window}` : undefined);
//   return (
//     <article className="dx-detail" aria-label="Card" data-card={card.id}>
//       <Head card={card} />
//       {card.incomplete && (
//         <Notice icon={Info}>
//           {[card.incomplete.message, card.incomplete.next && `Next: ${card.incomplete.next}`].filter(Boolean).join(" ")}
//         </Notice>
//       )}
//       {asks && card.offers.answer && (
//         <section className="dx-card dx-answer" aria-label="Your answer">
//           <label htmlFor={`answer-${card.id}`}>Your answer</label>
//           <textarea
//             id={`answer-${card.id}`}
//             className="dx-textarea"
//             value={answer}
//             onChange={(e) => setAnswer(e.target.value)}
//             placeholder="One or two lines is enough."
//           />
//           <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
//             <span className="dx-hint">GeniOS reads the thread again with your answer.</span>
//             <Button kind="ink" icon={Send} disabled={busy || !answer.trim()} onClick={() => onAnswer(answer)}>
//               Send answer
//             </Button>
//           </div>
//         </section>
//       )}
//       {card.answered && (
//         <Notice icon={Info}>Your answer is in. GeniOS reads the thread again and this card turns into a move, or one more question.</Notice>
//       )}
//       {!asks && <Recommendation card={card} />}
//       {!asks && (card.what || card.whyNow || (card.how && card.how !== card.todo?.line)) && (
//         <section aria-label="What, why, how" style={{ display: "grid", gap: 6 }}>
//           <Eyebrow>What · why · how</Eyebrow>
//           <Fields>
//             {card.what && <Field label="What">{card.what}</Field>}
//             {card.whyNow && <Field label="Why">{card.whyNow}</Field>}
//             {card.how && card.how !== card.todo?.line && <Field label="How">{card.how}</Field>}
//           </Fields>
//         </section>
//       )}
//       <section aria-label="What it gets you" style={{ display: "grid", gap: 6 }}>
//         <Eyebrow>What it gets you</Eyebrow>
//         <Fields>
//           {card.doneWhen && <Field label="Done when">{card.doneWhen}</Field>}
//           <Field label="Goal" muted>
//             Not linked to a goal yet
//           </Field>
//           <Field label="Deadline" muted={!deadline}>
//             {deadline ?? "No date in the thread"}
//           </Field>
//         </Fields>
//       </section>
//       <p className="dx-meta dx-selectable" aria-label="Where it came from">
//         From {sourceLine(card)}
//       </p>
//       {also.length > 0 && (
//         <section aria-label="Also on your screen" style={{ display: "grid", gap: 8 }}>
//           <Eyebrow>Also on your screen</Eyebrow>
//           <ul className="dx-rows">
//             {also.map((f) => (
//               <ScreenRow key={f.id} item={f} onDone={onItemDone} onHandled={onItemHandled} onTomorrow={onItemTomorrow} />
//             ))}
//           </ul>
//         </section>
//       )}
//       <section aria-label="Show more" style={{ display: "grid", gap: 10 }}>
//         {more === null ? (
//           <div>
//             <Button small onClick={() => setMore("details")}>
//               Show more
//             </Button>
//           </div>
//         ) : (
//           <>
//             <Tabs
//               label="More about this card"
//               value={more}
//               onChange={setMore}
//               options={[
//                 { id: "details", label: "Details" },
//                 { id: "slips", label: "If it slips" },
//                 { id: "sources", label: "Sources" },
//               ]}
//             />
//             {more === "details" && <Details card={card} />}
//             {more === "slips" && <Slips card={card} />}
//             {more === "sources" && <Sources card={card} />}
//           </>
//         )}
//       </section>
//     </article>
//   );
// }
```

#### `src/desktop/ActionBar.tsx`

```tsx
// // The buttons at the foot of an opened card — the web Cards page's four (06-CARDS §3):
// // Done · Delegate ▾ · Later ▾ · Feedback ▾, each ▾ opening its panel above the bar. Only what the
// // server takes on this card: a question is answered in the card, never marked done. A refused
// // press stays above the buttons as a sentence until the next press.
// import { useEffect, useState } from "react";
// import { Bot, Check, ChevronDown, CircleAlert, Clock, Lock, MessageSquareQuote, Send, UserPlus, Users, type LucideIcon } from "lucide-react";
// import { getMembers, listAgents, type Agent, type CardPress, type Member } from "./api";
// import type { DeskCard } from "./cards";
// import { Button, Choice, Notice, useDismiss } from "./ui";
// import "./detail.css";
//
// export const SNOOZE_LABEL: Record<string, string> = { "4h": "In 4 hours", tomorrow_09: "Tomorrow, 9:00", "3d": "In 3 days" };
//
// type Menu = "delegate" | "later" | "feedback";
// type Scope = "file" | "kind" | "company";
// const SCOPES: [Scope, string][] = [
//   ["file", "this thread"],
//   ["kind", "this kind of work"],
//   ["company", "how we work (owner)"],
// ];
//
// // In a 330-pixel panel the four fit one row only without the menu buttons' leading icons; the ▾ says "opens".
// function MenuButton({ label, open, onClick }: { label: string; icon?: LucideIcon; open: boolean; onClick: () => void }) {
//   return (
//     <Button small aria-expanded={open} onClick={onClick}>
//       {label}
//       <ChevronDown className="dx-chev" size={14} strokeWidth={2} aria-hidden />
//     </Button>
//   );
// }
//
// /** Later: the card's own snooze options, or a day you pick (put off to 9:00 that day). */
// function LaterPanel({ options, busy, onPress }: { options: string[]; busy: boolean; onPress: (p: CardPress) => void }) {
//   const [day, setDay] = useState("");
//   return (
//     <>
//       <h4>Bring it back</h4>
//       <div className="dx-chips">
//         {options.map((o) => (
//           <Button key={o} small disabled={busy} onClick={() => onPress({ action: "snooze", snooze: o })}>
//             {SNOOZE_LABEL[o] ?? o}
//           </Button>
//         ))}
//       </div>
//       <div className="dx-day-pick">
//         <label htmlFor="later-day">On a day you pick</label>
//         <input id="later-day" type="date" className="dx-input" value={day} onChange={(e) => setDay(e.target.value)} />
//         <Button
//           small
//           disabled={busy || !day}
//           onClick={() => onPress({ action: "snooze", snooze: "custom", until: new Date(`${day}T09:00:00`).toISOString() })}
//         >
//           Put off to 9:00 that day
//         </Button>
//       </div>
//     </>
//   );
// }
//
// /** Delegate: to a person on the team or to an agent. The hand-over is locked until the brain serves it. */
// function DelegatePanel() {
//   const [who, setWho] = useState<"people" | "agent">("people");
//   const [people, setPeople] = useState<Member[] | null | "forbidden">(null);
//   const [agents, setAgents] = useState<Agent[] | null>(null);
//   useEffect(() => {
//     getMembers()
//       .then(setPeople)
//       .catch(() => setPeople("forbidden"));
//     listAgents()
//       .then(setAgents)
//       .catch(() => setAgents([]));
//   }, []);
//   return (
//     <>
//       <div className="dx-seg">
//         <button type="button" aria-pressed={who === "people"} onClick={() => setWho("people")}>
//           <Users size={14} strokeWidth={2} aria-hidden /> A person
//         </button>
//         <button type="button" aria-pressed={who === "agent"} onClick={() => setWho("agent")}>
//           <Bot size={14} strokeWidth={2} aria-hidden /> An agent
//         </button>
//       </div>
//       {who === "people" &&
//         (people === null ? (
//           <p className="dx-hint">Reading your team…</p>
//         ) : people === "forbidden" ? (
//           <p className="dx-hint">Only the workspace owner can see the team.</p>
//         ) : people.length === 0 ? (
//           <p className="dx-hint">Nobody else is on this workspace yet. Invite a teammate from Team, then hand cards to them here.</p>
//         ) : (
//           <ul className="dx-people">
//             {people.map((m) => (
//               <li key={m.id}>
//                 <span>
//                   <span>{m.name}</span>
//                   <small>
//                     {m.email} · {m.role}
//                   </small>
//                 </span>
//                 <Button small icon={Lock} disabled>
//                   Hand over
//                 </Button>
//               </li>
//             ))}
//           </ul>
//         ))}
//       {who === "agent" &&
//         (agents === null ? (
//           <p className="dx-hint">Reading your agents…</p>
//         ) : agents.length === 0 ? (
//           <p className="dx-hint">No agent is connected yet. Once one is, it can draft the reply or reschedule the meeting, and you approve before anything goes out.</p>
//         ) : (
//           <ul className="dx-people">
//             {agents.map((a) => (
//               <li key={a.agent_id}>
//                 <span>
//                   <span>{a.name ?? a.agent_id}</span>
//                   <small>{a.description ?? "Drafts and acts with your approval"}</small>
//                 </span>
//                 <Button small icon={Lock} disabled>
//                   Ask it
//                 </Button>
//               </li>
//             ))}
//           </ul>
//         ))}
//       <p className="dx-lock">
//         <Lock size={13} strokeWidth={2} aria-hidden />
//         Handing a card over goes live with the next brain update. Until then the card stays with you.
//       </p>
//     </>
//   );
// }
//
// /** Feedback: what is off, then the same thing in your words as two blanks, and how far it reaches. */
// function FeedbackPanel({ card, busy, onPress }: { card: DeskCard; busy: boolean; onPress: (p: CardPress) => void }) {
//   const [reason, setReason] = useState<string | null>(null);
//   const [wrong, setWrong] = useState("");
//   const [should, setShould] = useState("");
//   const [scope, setScope] = useState<Scope>("file");
//   const words = [wrong.trim() && `It is wrong because ${wrong.trim()}`, should.trim() && `It should be: ${should.trim()}`].filter(Boolean).join(". ");
//   return (
//     <>
//       <h4>What is off?</h4>
//       {card.offers.wrong.map((g) => (
//         <div key={g.title} className="dx-feedback-group">
//           {card.offers.wrong.length > 1 && <span className="dx-hint">{g.title}</span>}
//           <div>
//             {g.reasons.map((r) => (
//               <Choice key={r.value} on={reason === r.value} onClick={() => setReason(r.value)}>
//                 {r.label}
//               </Choice>
//             ))}
//           </div>
//         </div>
//       ))}
//       <div className="dx-feedback-words">
//         <label>
//           This card is wrong because
//           <input className="dx-input" value={wrong} onChange={(e) => setWrong(e.target.value)} placeholder="the call already happened on Monday" />
//         </label>
//         <label>
//           It should be
//           <input className="dx-input" value={should} onChange={(e) => setShould(e.target.value)} placeholder="send the recap to Neha instead" />
//         </label>
//       </div>
//       {words && (
//         <div className="dx-feedback-group">
//           <span className="dx-hint">Apply it to</span>
//           <div>
//             {SCOPES.map(([key, label]) => (
//               <Choice key={key} on={scope === key} onClick={() => setScope(key)}>
//                 {label}
//               </Choice>
//             ))}
//           </div>
//         </div>
//       )}
//       <div className="dx-feedback-send">
//         <span className="dx-hint">Your words go to GeniOS's reasoning: the next review of this thread reads them first.</span>
//         <Button kind="ink" icon={Send} disabled={busy || !reason} onClick={() => reason && onPress({ action: "wrong", reason, words, scope })}>
//           Send
//         </Button>
//       </div>
//     </>
//   );
// }
//
// export function ActionBar({
//   card,
//   busy,
//   refusal,
//   onPress,
// }: {
//   card: DeskCard;
//   busy: boolean;
//   refusal: string | null;
//   onPress: (p: CardPress) => void;
//   onOpenWeb?: () => void;
// }) {
//   const [menu, setMenu] = useState<Menu | null>(null);
//   const ref = useDismiss<HTMLDivElement>(menu !== null, () => setMenu(null));
//   const asks = card.lane === "question" && !card.answered;
//   const done = card.offers.done && !asks && !card.answered;
//   const toggle = (m: Menu) => setMenu((cur) => (cur === m ? null : m));
//   const press = (p: CardPress) => {
//     setMenu(null);
//     onPress(p);
//   };
//   return (
//     <div className="dx-bar" ref={ref}>
//       {menu && (
//         <div className="dx-bar-panel" role="dialog" aria-label={menu === "delegate" ? "Delegate" : menu === "later" ? "Later" : "Feedback"}>
//           {menu === "delegate" && <DelegatePanel />}
//           {menu === "later" && <LaterPanel options={card.offers.snooze} busy={busy} onPress={press} />}
//           {menu === "feedback" && <FeedbackPanel card={card} busy={busy} onPress={press} />}
//         </div>
//       )}
//       {refusal && <Notice icon={CircleAlert}>{refusal}</Notice>}
//       <div className="dx-bar-row">
//         {done && (
//           <Button kind="ink" small icon={Check} disabled={busy} onClick={() => press({ action: "do_it_myself" })}>
//             Done
//           </Button>
//         )}
//         {done && <MenuButton label="Delegate" icon={UserPlus} open={menu === "delegate"} onClick={() => toggle("delegate")} />}
//         {card.offers.snooze.length > 0 && <MenuButton label="Later" icon={Clock} open={menu === "later"} onClick={() => toggle("later")} />}
//         {!card.answered && (
//           <MenuButton label={asks ? "Don't ask this" : "Feedback"} icon={MessageSquareQuote} open={menu === "feedback"} onClick={() => toggle("feedback")} />
//         )}
//       </div>
//     </div>
//   );
// }
```

#### `src/desktop/detail.css`

```css
// /* An opened card: its own page, essentials first, the rest a tab at a time; buttons at the foot. */
// .dx-detail {
//   display: flex;
//   flex-direction: column;
//   gap: 12px;
// }
// .dx-d-tags {
//   display: flex;
//   flex-wrap: wrap;
//   align-items: center;
//   gap: 5px;
// }
// .dx-d-status {
//   display: flex;
//   align-items: center;
//   gap: 8px;
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .dx-d-head {
//   display: grid;
//   gap: 6px;
// }
// .dx-d-how {
//   font-size: 13px;
//   color: var(--dx-mist);
// }
// .dx-reco {
//   display: grid;
//   gap: 8px;
//   padding: 14px;
// }
// .dx-reco-line {
//   font-size: 14px;
//   font-weight: 400;
//   line-height: 1.4;
// }
// .dx-steps {
//   list-style: none;
//   padding: 0;
//   display: grid;
//   gap: 6px;
//   counter-reset: step;
// }
// .dx-steps li {
//   display: flex;
//   gap: 9px;
//   font-size: 13px;
//   line-height: 1.4;
//   color: var(--dx-ink-2);
//   counter-increment: step;
// }
// .dx-steps li::before {
//   content: counter(step);
//   flex: none;
//   display: grid;
//   place-items: center;
//   width: 20px;
//   height: 20px;
//   border-radius: 50%;
//   background: var(--dx-inset-2);
//   font-size: 12px;
//   font-weight: 400;
//   color: var(--dx-ink-2);
// }
// .dx-reco-foot {
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .dx-reco-foot b {
//   color: var(--dx-ink-2);
//   font-weight: 400;
// }
// .dx-quote {
//   padding: 8px 10px;
//   border-radius: 8px;
//   background: var(--dx-inset);
//   font-size: 13px;
//   line-height: 1.45;
//   font-style: italic;
//   color: var(--dx-ink-2);
// }
// .dx-more {
//   display: grid;
//   gap: 10px;
// }
// .dx-lines {
//   list-style: none;
//   padding: 0;
//   display: grid;
//   gap: 6px;
// }
// .dx-lines li {
//   display: grid;
//   gap: 1px;
//   padding: 8px 10px;
//   border-radius: 8px;
//   background: var(--dx-inset);
//   font-size: 13px;
//   line-height: 1.4;
//   color: var(--dx-ink-2);
// }
// .dx-lines li small {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .dx-answer {
//   display: grid;
//   gap: 8px;
//   padding: 14px;
// }
// .dx-answer label {
//   font-size: 13px;
//   font-weight: 400;
// }
//
// .dx-bar {
//   position: relative;
//   flex: none;
//   display: grid;
//   gap: 8px;
//   padding: 10px 12px 12px;
//   border-top: 1px solid var(--dx-line);
//   background: var(--dx-page);
// }
// .dx-bar-row {
//   display: flex;
//   flex-wrap: nowrap;
//   gap: 6px;
// }
// .dx-feedback {
//   display: grid;
//   gap: 12px;
// }
// .dx-feedback-group {
//   display: grid;
//   gap: 6px;
// }
// .dx-feedback-group > div {
//   display: flex;
//   flex-wrap: wrap;
//   gap: 6px;
// }
// .dx-feedback-words {
//   display: grid;
//   gap: 8px;
//   padding: 10px;
//   border-radius: 10px;
//   background: var(--dx-inset);
// }
// .dx-feedback-words label {
//   display: grid;
//   gap: 4px;
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .dx-feedback-send {
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   gap: 10px;
// }
//
// /* The four buttons' panels open above the bar, as on the web Cards page. */
// .dx-bar-panel {
//   position: absolute;
//   left: 10px;
//   right: 10px;
//   bottom: calc(100% + 6px);
//   z-index: 45;
//   display: grid;
//   gap: 10px;
//   max-height: 360px;
//   overflow-y: auto;
//   padding: 12px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line-strong);
//   border-radius: 12px;
//   box-shadow: var(--dx-shadow-pop);
//   animation: dx-rise 0.16s cubic-bezier(0.16, 1, 0.3, 1);
// }
// .dx-bar-panel h4 {
//   font-size: 13px;
//   color: var(--dx-ink);
// }
// .dx-chips {
//   display: flex;
//   flex-wrap: wrap;
//   gap: 6px;
// }
// .dx-day-pick {
//   display: flex;
//   flex-wrap: wrap;
//   align-items: center;
//   gap: 6px;
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .dx-day-pick .dx-input {
//   width: auto;
//   height: 28px;
//   padding: 0 8px;
// }
// .dx-seg {
//   display: flex;
//   gap: 2px;
//   padding: 2px;
//   border-radius: 9px;
//   background: var(--dx-inset-2);
// }
// .dx-seg button {
//   flex: 1;
//   display: inline-flex;
//   align-items: center;
//   justify-content: center;
//   gap: 6px;
//   height: 28px;
//   border: 0;
//   border-radius: 7px;
//   background: transparent;
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .dx-seg button[aria-pressed="true"] {
//   background: var(--dx-card);
//   color: var(--dx-ink);
//   box-shadow: var(--dx-shadow-1);
// }
// .dx-people {
//   list-style: none;
//   padding: 0;
//   border: 1px solid var(--dx-line);
//   border-radius: 10px;
// }
// .dx-people li {
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   gap: 10px;
//   padding: 8px 10px;
// }
// .dx-people li + li {
//   border-top: 1px solid var(--dx-line);
// }
// .dx-people li > span {
//   min-width: 0;
//   display: grid;
// }
// .dx-people small {
//   font-size: 12px;
//   color: var(--dx-mist);
//   overflow: hidden;
//   text-overflow: ellipsis;
//   white-space: nowrap;
// }
// .dx-lock {
//   display: flex;
//   gap: 6px;
//   align-items: flex-start;
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .dx-lock svg {
//   flex: none;
//   margin-top: 2px;
// }
// .dx-btn .dx-chev {
//   transition: transform 0.15s;
// }
// .dx-btn[aria-expanded="true"] .dx-chev {
//   transform: rotate(180deg);
// }
```

#### `src/desktop/SetupCard.tsx`

```tsx
// // Screen reading, said once and in the right place.
// //
// // The old panel said "Allow Accessibility … Open settings" in a strip AND in a checklist right
// // under it, and stacked every capture note as its own line (one in red). Now: one setup card on
// // Today while something is missing (readiness as a percent, the one next step and its button), and
// // one quiet bar at the foot of the panel with the reading state and, at most, one note.
// import { useCallback, useEffect, useState } from "react";
// import { Check, Circle, CircleAlert, Info } from "lucide-react";
// import {
//   budgetLine,
//   captureRefreshPolicy,
//   captureStatus,
//   capturePause,
//   captureResume,
//   catchingUpLine,
//   openAccessibilitySettings,
//   openDashboard,
//   syncNow,
//   type CaptureStatus,
// } from "./api";
// import { Button, Progress, Status } from "./ui";
// import "./SetupCard.css";
//
// /** The reading state from the Rust core (local, no network), every 5 s, and what can be done to it. */
// export function useCapture() {
//   const [status, setStatus] = useState<CaptureStatus | null>(null);
//   const [error, setError] = useState("");
//   const refresh = useCallback(() => {
//     captureStatus()
//       .then(setStatus)
//       .catch(() => setStatus(null));
//   }, []);
//   useEffect(() => {
//     refresh();
//     const iv = setInterval(refresh, 5000);
//     return () => clearInterval(iv);
//   }, [refresh]);
//   const act = useCallback(
//     (p: Promise<unknown>) =>
//       p
//         .then(() => setError(""))
//         .catch((e) => setError(typeof e === "string" ? e : "Couldn't reach GeniOS. Try again."))
//         .finally(() => setTimeout(refresh, 300)),
//     [refresh],
//   );
//   return {
//     status,
//     error,
//     refresh,
//     pause: (minutes: number) => act(capturePause(minutes)),
//     resume: () => act(captureResume()),
//     sync: () => act(syncNow()),
//     openAccessibility: () => act(openAccessibilitySettings()),
//     turnOn: () => act(openDashboard("/dashboard/settings?section=capture")),
//     /** The capture policy NOW, not after its 15-minute timer: the person may have just changed it. */
//     refreshPolicy: () => void captureRefreshPolicy().catch(() => {}),
//   };
// }
//
// const FIRST_CATCH_KEY = "gx.firstCatch";
//
// function caughtBefore(): boolean {
//   try {
//     return localStorage.getItem(FIRST_CATCH_KEY) === "1";
//   } catch {
//     return false;
//   }
// }
//
// /** What is still missing before GeniOS can help, while anything is. */
// export function SetupCard({
//   status,
//   hasItems,
//   onAccessibility,
//   onTurnOn,
// }: {
//   status: CaptureStatus | null;
//   hasItems: boolean;
//   onAccessibility: () => void;
//   onTurnOn: () => void;
// }) {
//   const [caught, setCaught] = useState(caughtBefore);
//   useEffect(() => {
//     if (!hasItems || caught) return;
//     setCaught(true);
//     try {
//       localStorage.setItem(FIRST_CATCH_KEY, "1");
//     } catch {
//       /* remembered for this session only */
//     }
//   }, [hasItems, caught]);
//   if (!status || status.state === "unsupported" || status.state === "signed_out") return null;
//
//   const steps: { label: string; done: boolean; hint?: string; action?: { label: string; run: () => void } }[] = [
//     { label: "Signed in", done: true },
//     {
//       label: "Allow Accessibility",
//       done: status.state !== "needs_accessibility",
//       hint: status.detail || "So GeniOS can read the text of the app you're in.",
//       action: { label: "Open settings", run: onAccessibility },
//     },
//     {
//       label: "Turn on screen reading",
//       done: status.state !== "off_by_policy",
//       hint: "On the website: Settings › My capture. An admin allows it once.",
//       action: { label: "Turn on", run: onTurnOn },
//     },
//     {
//       label: "Catch the first item",
//       done: caught || hasItems,
//       hint: "Open a work chat or your inbox. The first ask or promise lands here.",
//     },
//   ];
//   const next = steps.find((s) => !s.done);
//   if (!next) return null;
//   const pct = Math.round((steps.filter((s) => s.done).length / steps.length) * 100);
//   return (
//     <section className="dx-card dx-setup" aria-label="Get set up">
//       <div className="dx-setup-head">
//         <span className="dx-setup-title">Get GeniOS reading</span>
//         <span className="dx-setup-pct">{pct}% ready</span>
//       </div>
//       <Progress value={pct} label="Ready" />
//       <div className="dx-setup-next">
//         <div>
//           <div className="dx-setup-label">{next.label}</div>
//           {next.hint && <div className="dx-hint">{next.hint}</div>}
//         </div>
//         {next.action && (
//           <Button kind="ink" small onClick={next.action.run}>
//             {next.action.label}
//           </Button>
//         )}
//       </div>
//       <ul className="dx-setup-steps" aria-label="Steps">
//         {steps
//           .filter((s) => s !== next)
//           .map((s) => (
//             <li key={s.label} className={s.done ? "done" : ""}>
//               {s.done ? <Check size={13} strokeWidth={2.4} aria-label="done" /> : <Circle size={11} strokeWidth={2} aria-label="to do" />}
//               {s.label}
//             </li>
//           ))}
//       </ul>
//     </section>
//   );
// }
//
// const time = (iso?: string | null) => {
//   const d = iso ? new Date(iso) : null;
//   return d && !Number.isNaN(d.getTime()) ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";
// };
//
// /**
//  * The reading state at the foot of the panel. Silent where capture does not exist (Windows/Linux
//  * without it, signed out). While the setup card shows, its button is the only one: the bar only says.
//  */
// export function CaptureBar({
//   status,
//   error,
//   setupShowing,
//   onPause,
//   onResume,
//   onSync,
//   onAccessibility,
//   onTurnOn,
// }: {
//   status: CaptureStatus | null;
//   error?: string;
//   setupShowing: boolean;
//   onPause: () => void;
//   onResume: () => void;
//   onSync: () => void;
//   onAccessibility: () => void;
//   onTurnOn: () => void;
// }) {
//   if (!status || status.state === "unsupported" || status.state === "signed_out") return null;
//   let tone: "ink" | "accent" | "quiet" = "quiet";
//   let text = "";
//   let action: { label: string; run: () => void } | null = null;
//   switch (status.state) {
//     case "capturing":
//       tone = "ink";
//       text = status.reader_available === false ? "Watching app activity" : status.last_thread_title ? `Reading · ${status.last_thread_title}` : "Watching your work apps";
//       action = { label: "Pause", run: onPause };
//       break;
//     case "idle":
//       text = "Idle. Nothing is read while you're away";
//       break;
//     case "paused":
//       text = `Paused until ${time(status.paused_until)}`;
//       action = { label: "Resume", run: onResume };
//       break;
//     case "starting":
//       text = "Starting to read…";
//       break;
//     case "needs_accessibility":
//       tone = "accent";
//       text = "Reading needs Accessibility";
//       if (!setupShowing) action = { label: "Open settings", run: onAccessibility };
//       break;
//     case "off_by_policy":
//       text = "Screen reading is off";
//       if (!setupShowing) action = { label: "Turn on", run: onTurnOn };
//       break;
//     case "update_required":
//       tone = "accent";
//       text = status.detail || "Update GeniOS to keep reading";
//       break;
//     case "sidecar_unavailable":
//       tone = "accent";
//       text = "The reading helper is not running";
//       break;
//   }
//   // One note at most: a reader that went blind first (an unread app and an empty panel look the
//   // same otherwise), then the day's AI checks running out, then screens deferred to the night.
//   const blind = status.reader_health?.trim() || "";
//   const note = error || blind || budgetLine(status.insight_budget) || catchingUpLine(status.catching_up);
//   const warn = Boolean(error || blind);
//   return (
//     <footer className="dx-foot" aria-label="Screen reading">
//       <div className="dx-foot-row">
//         <Status tone={tone}>
//           <span title={status.detail || undefined}>{text}</span>
//         </Status>
//         {!!status.queue_depth && status.queue_depth > 0 && (
//           <button type="button" className="dx-btn link sm" onClick={onSync}>
//             Sync {status.queue_depth}
//           </button>
//         )}
//         {action && (
//           <button type="button" className="dx-btn link sm" onClick={action.run}>
//             {action.label}
//           </button>
//         )}
//       </div>
//       {note && (
//         <div className={`dx-foot-note${warn ? " warn" : ""}`}>
//           {warn ? <CircleAlert size={13} strokeWidth={2} aria-hidden /> : <Info size={13} strokeWidth={2} aria-hidden />}
//           <span>{note}</span>
//         </div>
//       )}
//     </footer>
//   );
// }
```

#### `src/desktop/SetupCard.css`

```css
// /* First run, as one card; and the reading state as one quiet bar at the foot of the panel. */
// .dx-setup {
//   display: grid;
//   gap: 10px;
//   padding: 14px;
// }
// .dx-setup-head {
//   display: flex;
//   align-items: baseline;
//   justify-content: space-between;
//   gap: 10px;
// }
// .dx-setup-title {
//   font-size: 14.5px;
//   font-weight: 400;
// }
// .dx-setup-pct {
//   font-size: 13px;
//   font-weight: 400;
//   color: var(--dx-ink-2);
//   font-variant-numeric: tabular-nums;
// }
// .dx-setup-next {
//   display: flex;
//   align-items: center;
//   gap: 12px;
//   padding: 10px 12px;
//   border-radius: 10px;
//   background: var(--dx-inset);
// }
// .dx-setup-next > div {
//   flex: 1;
//   min-width: 0;
// }
// .dx-setup-label {
//   font-size: 13.5px;
//   font-weight: 400;
//   margin-bottom: 2px;
// }
// .dx-setup-steps {
//   list-style: none;
//   padding: 0;
//   display: flex;
//   flex-wrap: wrap;
//   gap: 4px 14px;
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .dx-setup-steps li {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
// }
// .dx-setup-steps li.done {
//   color: var(--dx-ink-2);
// }
//
// .dx-foot {
//   position: relative;
//   flex: none;
//   display: grid;
//   gap: 2px;
//   padding: 8px 14px 9px;
//   border-top: 1px solid var(--dx-line);
//   background: var(--dx-page);
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .dx-foot-row {
//   display: flex;
//   align-items: center;
//   gap: 12px;
//   min-height: 20px;
// }
// .dx-foot-row .dx-status {
//   flex: 1;
//   min-width: 0;
// }
// .dx-foot-row .dx-status span {
//   overflow: hidden;
//   text-overflow: ellipsis;
// }
// .dx-foot-note {
//   display: flex;
//   align-items: flex-start;
//   gap: 6px;
//   line-height: 1.4;
// }
// .dx-foot-note svg {
//   flex: none;
//   margin-top: 1px;
// }
// .dx-foot-note.warn {
//   color: var(--dx-ink-2);
// }
// .dx-foot-note.warn svg {
//   color: var(--dx-accent);
// }
```

#### `src/desktop/WeekView.tsx`

```tsx
// // This week: the proof it was worth it. Percent rings, never "3/5"; a count that was never measured
// // says so instead of showing a zero.
// import { useEffect, useState } from "react";
// import { CalendarRange } from "lucide-react";
// import { weeklyReport, type WeeklyReport } from "./api";
// import { Empty, Skeleton } from "./ui";
// import "./screens.css";
//
// function Ring({ pct }: { pct: number }) {
//   const r = 24;
//   const c = 2 * Math.PI * r;
//   return (
//     <svg className="dx-ring" width="60" height="60" viewBox="0 0 60 60" aria-hidden>
//       <circle cx="30" cy="30" r={r} fill="none" stroke="var(--dx-inset-2)" strokeWidth="6" />
//       <circle
//         cx="30"
//         cy="30"
//         r={r}
//         fill="none"
//         stroke="var(--dx-ink)"
//         strokeWidth="6"
//         strokeLinecap="round"
//         strokeDasharray={`${(c * pct) / 100} ${c}`}
//         transform="rotate(-90 30 30)"
//       />
//       <text x="30" y="34.5" textAnchor="middle">
//         {pct}%
//       </text>
//     </svg>
//   );
// }
//
// function Share({ part, whole, label, none }: { part: number; whole: number; label: string; none: string }) {
//   return (
//     <div className="dx-card dx-stat">
//       {whole > 0 ? (
//         <div className="dx-stat-top">
//           <Ring pct={Math.round((part / whole) * 100)} />
//           <div>
//             <div className="dx-stat-label">{label}</div>
//             <div className="dx-stat-note">
//               {part} of {whole === 1 ? "the one" : `the ${whole}`} caught
//             </div>
//           </div>
//         </div>
//       ) : (
//         <>
//           <div className="dx-stat-label">{label}</div>
//           <div className="dx-stat-note">{none}</div>
//         </>
//       )}
//     </div>
//   );
// }
//
// const day = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString([], { day: "numeric", month: "short" });
//
// export function WeekView() {
//   const [r, setR] = useState<WeeklyReport | null | undefined>(undefined);
//   useEffect(() => {
//     weeklyReport()
//       .then(setR)
//       .catch(() => setR(null));
//   }, []);
//   if (r === undefined)
//     return (
//       <div className="dx-week" aria-label="Loading">
//         <Skeleton height={90} />
//         <Skeleton height={90} />
//       </div>
//     );
//   if (!r)
//     return (
//       <Empty icon={CalendarRange} title="This week's numbers did not load">
//         <p>GeniOS could not be reached. They come back on the next refresh.</p>
//       </Empty>
//     );
//   const rated = r.useful + r.not_useful;
//   const unrated = Math.max(0, r.popups_shown - rated);
//   const w = (n: number) => `${r.popups_shown ? (n / r.popups_shown) * 100 : 0}%`;
//   return (
//     <div className="dx-week" aria-label="This week">
//       <p className="dx-lead">
//         {day(r.week_start)} – {day(r.week_end)}
//       </p>
//       <div className="dx-card dx-stat dark">
//         <span className="dx-stat-big">{r.nudged_then_closed}</span>
//         <span className="dx-stat-label">Closed after a nudge</span>
//         <span className="dx-stat-note">Things that would likely have slipped, done after GeniOS brought them back.</span>
//       </div>
//       <div className="dx-week-pair">
//         <Share part={r.promises_kept} whole={r.promises_caught} label="Promises kept" none="No promise caught yet this week." />
//         <Share part={r.asks_answered} whole={r.asks_flagged} label="Asks answered" none="Nobody asked you for something yet." />
//       </div>
//       <div className="dx-card dx-stat">
//         <div className="dx-stat-label">
//           {r.popups_shown} popup{r.popups_shown === 1 ? "" : "s"} shown
//         </div>
//         {r.popups_shown > 0 && (
//           <>
//             <div className="dx-stack" aria-hidden>
//               <span style={{ width: w(r.useful) }} />
//               <span style={{ width: w(r.not_useful) }} />
//             </div>
//             <div className="dx-legend">
//               <span>
//                 <i />
//                 {r.useful} useful
//               </span>
//               <span>
//                 <i className="b" />
//                 {r.not_useful} not useful
//               </span>
//               <span>
//                 <i className="c" />
//                 {unrated} not rated
//               </span>
//             </div>
//           </>
//         )}
//       </div>
//       {(r.deadlines_flagged > 0 || r.risks_flagged > 0) && (
//         <p className="dx-hint">
//           Also flagged: {r.deadlines_flagged} deadline{r.deadlines_flagged === 1 ? "" : "s"} · {r.risks_flagged} risk{r.risks_flagged === 1 ? "" : "s"}
//         </p>
//       )}
//     </div>
//   );
// }
```

#### `src/desktop/HistoryView.tsx`

```tsx
// // History: every popup shown since GeniOS started, by day, so one that hid is never lost — each
// // with where it came from and the words on screen, and one place to say whether it helped.
// import { History as HistoryIcon } from "lucide-react";
// import type { RecentItem } from "./api";
// import { Button, Eyebrow, Tag, toolIcon } from "./ui";
// import "./screens.css";
//
// const APP_LABEL: Record<string, string> = {
//   whatsapp: "WhatsApp",
//   slack: "Slack",
//   teams: "Teams",
//   gmail: "Gmail",
//   mail: "Mail",
//   linkedin: "LinkedIn",
// };
//
// /** "wa:chat:priya" → WhatsApp, "li:msg:77" → LinkedIn, "web:app.acme.com:…" → app.acme.com. */
// export function appName(item: RecentItem): string {
//   if (item.app && item.app !== "generic") return APP_LABEL[item.app] ?? item.app;
//   const [scheme, rest] = (item.thread_key ?? "").split(":", 2);
//   if (scheme === "wa") return "WhatsApp";
//   if (scheme === "li") return "LinkedIn";
//   if (scheme === "web" && rest) return rest;
//   return "GeniOS";
// }
//
// // A popup says "asked 2 min ago" because that is true while it is on screen; History keeps the
// // row for good, so the frozen phrase goes and the row's own time stays.
// const AGO = /\s+[—-]\s+(?:asked|noted|you promised|they promised)\s+.*\bago\s*$/i;
// export const withoutFrozenTime = (text: string) => text.replace(AGO, "");
//
// const time = (iso?: string | null) => {
//   const d = iso ? new Date(iso) : null;
//   return d && !Number.isNaN(d.getTime()) ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";
// };
//
// function dayLabel(iso: string, now: number): string {
//   const d = new Date(iso);
//   const today = new Date(now);
//   const yesterday = new Date(now - 86_400_000);
//   if (d.toDateString() === today.toDateString()) return "Today";
//   if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
//   return d.toLocaleDateString([], { weekday: "long", day: "numeric", month: "short" });
// }
//
// const RATED: Record<string, string> = {
//   useful: "You marked this useful",
//   not_useful: "You marked this not useful. This chat stays quiet for 7 days",
//   mute_chat: "You muted this chat",
// };
//
// export function HistoryView({
//   recent,
//   now = Date.now(),
//   onRate,
// }: {
//   recent: RecentItem[];
//   now?: number;
//   onRate: (id: string, action: "useful" | "not_useful" | "mute_chat") => void;
// }) {
//   if (recent.length === 0)
//     return (
//       <div className="dx-empty">
//         <span className="dx-empty-icon">
//           <HistoryIcon size={20} strokeWidth={1.8} aria-hidden />
//         </span>
//         <h3>No popups yet</h3>
//         <p>Every popup GeniOS shows lands here too, so one that hid is never lost.</p>
//       </div>
//     );
//   const days = new Map<string, RecentItem[]>();
//   for (const r of [...recent].sort((a, b) => Date.parse(b.at) - Date.parse(a.at)).slice(0, 40)) {
//     const k = dayLabel(r.at, now);
//     days.set(k, [...(days.get(k) ?? []), r]);
//   }
//   return (
//     <div style={{ display: "grid", gap: 14 }} aria-label="History">
//       {[...days].map(([label, items]) => (
//         <section key={label} className="dx-day" aria-label={label}>
//           <Eyebrow>{label}</Eyebrow>
//           {items.map((r) => {
//             const app = appName(r);
//             const lines = (r.body ?? "")
//               .split("\n")
//               .map((l) => l.trim())
//               .filter(Boolean);
//             const read = r.said_at ? time(r.said_at) : "";
//             return (
//               <article key={r.id} className="dx-card dx-pop-row" data-recent={r.id}>
//                 <div className="dx-row-tags">
//                   <Tag tool={app} how={r.who ?? undefined} icon={toolIcon(app)} />
//                   <span className="dx-row-age">{time(r.at)}</span>
//                 </div>
//                 <h3 className="dx-selectable">{withoutFrozenTime(r.headline)}</h3>
//                 {lines.length > 0 && (
//                   <ul className="dx-pop-lines dx-selectable">
//                     {lines.map((l, i) => (
//                       <li key={i}>{l}</li>
//                     ))}
//                   </ul>
//                 )}
//                 {r.quote && <p className="dx-quote dx-selectable">“{r.quote}”</p>}
//                 {read && <p className="dx-meta">Read on screen at {read} · shown at {time(r.at)}</p>}
//                 {r.feedback ? (
//                   <p className="dx-meta">{RATED[r.feedback] ?? "Thanks"}</p>
//                 ) : (
//                   <div className="dx-rate">
//                     <Button small onClick={() => onRate(r.id, "useful")}>
//                       Useful
//                     </Button>
//                     <Button small onClick={() => onRate(r.id, "not_useful")}>
//                       Not useful
//                     </Button>
//                     {r.thread_key && (
//                       <Button small kind="quiet" onClick={() => onRate(r.id, "mute_chat")}>
//                         Mute this chat
//                       </Button>
//                     )}
//                   </div>
//                 )}
//               </article>
//             );
//           })}
//         </section>
//       ))}
//     </div>
//   );
// }
```

#### `src/desktop/SignIn.tsx`

```tsx
// // Device sign-in (RFC 8628): the app shows a short code, the person approves it on the GeniOS
// // website, and the Rust core receives the tokens. No password or token is ever typed here. The
// // server's address is set only under Advanced: a customer never needs to read it.
// import { useEffect, useState } from "react";
// import { X } from "lucide-react";
// import {
//   authCancel,
//   authOpenBrowser,
//   authPollStatus,
//   authStart,
//   defaultBaseUrl,
//   rememberBaseUrl,
//   type AuthState,
// } from "./api";
// import { Button, IconButton, Notice } from "./ui";
// import { CircleAlert } from "lucide-react";
// import "./Header.css";
// import "./screens.css";
//
// export function SignIn({ reason, onDone, onClose }: { reason: string | null; onDone: () => void; onClose: () => void }) {
//   const [baseUrl, setBaseUrl] = useState(defaultBaseUrl());
//   const [state, setState] = useState<AuthState>({ status: "signed_out", reason });
//   const [busy, setBusy] = useState(false);
//   const [error, setError] = useState("");
//   const [advanced, setAdvanced] = useState(false);
//   const [now, setNow] = useState(Date.now());
//
//   // The Rust poll loop owns the network cadence; this only mirrors its state (no network).
//   useEffect(() => {
//     if (state.status !== "pending") return;
//     const iv = setInterval(async () => {
//       setNow(Date.now());
//       const s = await authPollStatus().catch(() => null);
//       if (!s) return;
//       if (s.status === "signed_in") onDone();
//       else setState(s);
//     }, 1000);
//     return () => clearInterval(iv);
//   }, [state.status, onDone]);
//
//   const start = async () => {
//     setBusy(true);
//     setError("");
//     try {
//       rememberBaseUrl(baseUrl);
//       setState(await authStart(baseUrl));
//       setNow(Date.now());
//     } catch (e) {
//       setError(String(e).startsWith("offline") ? "Couldn't reach GeniOS. Check your connection." : String(e));
//     } finally {
//       setBusy(false);
//     }
//   };
//
//   const cancel = async () => {
//     await authCancel().catch(() => {});
//     setState({ status: "signed_out", reason: null });
//   };
//
//   const left = state.status === "pending" ? Math.max(0, Math.round((Date.parse(state.expires_at) - now) / 1000)) : 0;
//   const note =
//     state.status === "expired"
//       ? "That code expired before it was approved. Get a new one."
//       : state.status === "denied"
//         ? "The sign-in was turned down on the website."
//         : state.status === "signed_out"
//           ? state.reason
//           : null;
//
//   return (
//     <div className="dx-shell">
//       <header className="dx-head" data-tauri-drag-region>
//         <span className="dx-mark" aria-label="GeniOS" data-tauri-drag-region>
//           G
//         </span>
//         <span className="dx-head-fill" data-tauri-drag-region />
//         <IconButton label="Close" icon={X} onClick={onClose} />
//       </header>
//       {state.status === "pending" ? (
//         <div className="dx-signin" aria-label="Approve this device">
//           <h2>Approve this Mac</h2>
//           <p className="dx-lead">Your browser opened GeniOS. Check it shows this code, then approve.</p>
//           <div className="dx-code" aria-label="Device code">
//             {state.user_code}
//           </div>
//           <div className="dx-wait">
//             <i aria-hidden />
//             Waiting for approval · {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}
//           </div>
//           <Button kind="ink" onClick={() => authOpenBrowser().catch(() => {})}>
//             Open the browser again
//           </Button>
//           <p className="dx-hint">
//             Or go to <span className="dx-selectable">{state.verification_uri}</span> and type the code.
//           </p>
//           <div>
//             <Button kind="quiet" small onClick={cancel}>
//               Cancel
//             </Button>
//           </div>
//         </div>
//       ) : (
//         <div className="dx-signin" aria-label="Sign in">
//           <h2>Sign in to GeniOS</h2>
//           <p className="dx-lead">You approve this Mac on the GeniOS website. Your password never enters this app.</p>
//           {note && <Notice icon={CircleAlert}>{note}</Notice>}
//           {error && <Notice icon={CircleAlert}>{error}</Notice>}
//           <Button kind="ink" onClick={start} disabled={busy || !baseUrl.trim()}>
//             {busy ? "Getting a code…" : state.status === "signed_out" ? "Sign in with the browser" : "Try again"}
//           </Button>
//           {advanced ? (
//             <label className="dx-hint" style={{ display: "grid", gap: 4 }}>
//               Server address
//               <input className="dx-input" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
//             </label>
//           ) : (
//             <div>
//               <Button kind="link" small onClick={() => setAdvanced(true)}>
//                 Advanced
//               </Button>
//             </div>
//           )}
//         </div>
//       )}
//     </div>
//   );
// }
```

#### `src/desktop/screens.css`

```css
// /* This week, History and sign-in. */
// .dx-week {
//   display: grid;
//   gap: 10px;
// }
// .dx-week-pair {
//   display: grid;
//   grid-template-columns: 1fr 1fr;
//   gap: 10px;
// }
// .dx-stat {
//   display: grid;
//   gap: 8px;
//   padding: 14px;
// }
// .dx-stat-top {
//   display: flex;
//   align-items: center;
//   gap: 12px;
// }
// .dx-stat-big {
//   font-size: 30px;
//   font-weight: 400;
//   letter-spacing: -0.02em;
//   line-height: 1;
//   font-variant-numeric: tabular-nums;
// }
// .dx-stat-label {
//   font-size: 13px;
//   font-weight: 400;
// }
// .dx-stat-note {
//   font-size: 12.5px;
//   color: var(--dx-mist);
//   line-height: 1.4;
// }
// .dx-stat.dark {
//   background: var(--dx-ink);
//   border-color: var(--dx-ink);
//   color: var(--dx-on-ink);
// }
// .dx-stat.dark .dx-stat-note {
//   color: inherit;
//   opacity: 0.78;
// }
// .dx-ring text {
//   font-size: 13px;
//   font-weight: 400;
//   fill: var(--dx-ink);
// }
// .dx-stack {
//   display: flex;
//   height: 8px;
//   border-radius: 4px;
//   overflow: hidden;
//   background: var(--dx-inset-2);
// }
// .dx-stack span:first-child {
//   background: var(--dx-ink);
// }
// .dx-stack span:nth-child(2) {
//   background: var(--dx-faint);
// }
// .dx-legend {
//   display: flex;
//   flex-wrap: wrap;
//   gap: 4px 14px;
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .dx-legend i {
//   display: inline-block;
//   width: 8px;
//   height: 8px;
//   border-radius: 2px;
//   margin-right: 5px;
//   background: var(--dx-ink);
// }
// .dx-legend i.b {
//   background: var(--dx-faint);
// }
// .dx-legend i.c {
//   background: var(--dx-inset-2);
// }
//
// .dx-day {
//   display: grid;
//   gap: 8px;
// }
// .dx-pop-row {
//   display: grid;
//   gap: 5px;
//   padding: 12px 14px;
// }
// .dx-pop-row h3 {
//   font-size: 14px;
//   font-weight: 560;
//   line-height: 1.35;
// }
// .dx-pop-lines {
//   list-style: none;
//   padding: 0;
//   display: grid;
//   gap: 3px;
//   font-size: 13px;
//   color: var(--dx-ink-2);
// }
// .dx-pop-lines li::before {
//   content: "·";
//   margin-right: 7px;
//   color: var(--dx-mist);
// }
// .dx-rate {
//   display: flex;
//   flex-wrap: wrap;
//   align-items: center;
//   gap: 6px;
//   margin-top: 4px;
// }
//
// .dx-signin {
//   flex: 1;
//   display: flex;
//   flex-direction: column;
//   justify-content: center;
//   gap: 14px;
//   padding: 24px 26px 32px;
// }
// .dx-signin h2 {
//   font-size: 19px;
//   font-weight: 400;
//   letter-spacing: -0.01em;
// }
// .dx-code {
//   padding: 18px 8px;
//   border-radius: 12px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line-strong);
//   font: 400 32px var(--dx-mono);
//   letter-spacing: 0.14em;
//   text-align: center;
//   user-select: text;
// }
// .dx-wait {
//   display: flex;
//   align-items: center;
//   justify-content: center;
//   gap: 8px;
//   font-size: 12.5px;
//   color: var(--dx-mist);
//   font-variant-numeric: tabular-nums;
// }
// .dx-wait i {
//   width: 7px;
//   height: 7px;
//   border-radius: 50%;
//   background: var(--dx-ink);
//   animation: dx-pulse 1.4s ease-in-out infinite;
// }
```

---

## 7 · The popups (the lane window)

The Rust core pushes one popup at a time; this draws it.

#### `src/lane/main.tsx`

```tsx
// import { StrictMode } from "react";
// import { createRoot } from "react-dom/client";
// import { Lane } from "./Lane";
// import "../desktop/theme.css";
// import "./lane.css";
//
// createRoot(document.getElementById("root")!).render(
//   <StrictMode>
//     <Lane />
//   </StrictMode>,
// );
```

#### `src/lane/Lane.tsx`

```tsx
// // The lane: one toast at a time, pushed from Rust (`genios://lane`). The window never takes
// // focus; every decision (queue, DND, shadow mode, rate limits) is made in Rust — this only
// // renders the current toast and reports clicks.
// //
// // "Ask my agent" (P6): the proposal toast shows the exact request and waits for the person —
// // Approve / Edit (opens the website, where the fields can be typed) / Reject with a reason.
// // Nothing here ever approves on its own.
//
// import { useEffect, useRef, useState } from "react";
// import { invoke } from "@tauri-apps/api/core";
// import { listen } from "@tauri-apps/api/event";
// import { AlarmClock, Bot, CalendarClock, Eye, History, ListChecks, MessageCircle, Sun, Users, X, type LucideIcon } from "lucide-react";
// import { Button, IconButton, Status } from "../desktop/ui";
//
// type Action = { id: string; label?: string | null };
// type Toast = {
//   id: string;
//   style: "reminder" | "advice";
//   kind: string;
//   capability_id: string;
//   priority: "low" | "normal" | "high" | "critical";
//   headline: string;
//   body?: string | null;
//   actions: Action[];
//   lines: string[];
// };
//
// const DRAFT_REVIEW = "moment.draft_review";
// const PROPOSAL = "delegation.proposal";
// const REJECT = "reject_delegation";
// // Same list as the Rust side (`delegation::REJECT_REASONS`); anything else is replaced there.
// const REJECT_REASONS = ["Not needed", "Wrong details", "I'll handle it myself"];
//
// // Fallback button labels when the server sends none — the panel's words.
// const LABELS: Record<string, string> = {
//   accept: "Use new value",
//   keep: "Keep current",
//   snooze: "Later",
//   open_card: "Open",
//   delegate: "Ask my agent",
//   useful: "Useful",
//   not_useful: "Not useful",
//   mute_chat: "Mute chat",
//   done: "Done",
//   remind_tomorrow: "Tomorrow",
//   remind_1h: "In 1 hour",
// };
// // Device-only notices ("Draft copied") are information, not advice to rate.
// const NOTICE = "moment.local_notice";
//
// // Where a popup came from, in the person's words — so a note caught on the screen never reads
// // like one built from the inbox or the calendar.
// const SOURCE_KICKER: Record<string, string> = {
//   "moment.screen_insight": "On your screen",
//   "moment.chat_open": "In this chat",
//   "moment.followup": "Reminder · caught on your screen",
//   "moment.meeting_prep": "Before your meeting",
//   "moment.daily_brief": "Morning brief",
//   "moment.daily_wrap": "Evening wrap",
//   "moment.due_today": "Still due today",
//   "moment.counterparty_recall": "From your history",
//   "moment.duplicate_outreach": "From your history",
//   "moment.changed_value": "Changed since you last looked",
// };
//
// // …and an icon for each, so the source reads at a glance.
// const SOURCE_ICON: Record<string, LucideIcon> = {
//   "moment.screen_insight": Eye,
//   "moment.chat_open": MessageCircle,
//   "moment.followup": AlarmClock,
//   "moment.meeting_prep": CalendarClock,
//   "moment.daily_brief": Sun,
//   "moment.daily_wrap": ListChecks,
//   "moment.due_today": AlarmClock,
//   "moment.counterparty_recall": History,
//   "moment.duplicate_outreach": History,
//   "moment.changed_value": History,
// };
//
// function kicker(t: Toast): { text: string; icon: LucideIcon } | null {
//   if (t.capability_id === DRAFT_REVIEW) return { text: "Draft notes · copy only", icon: ListChecks };
//   if (t.capability_id === PROPOSAL) return { text: "Ask my agent · needs your approval", icon: Bot };
//   if (SOURCE_KICKER[t.capability_id]) return { text: SOURCE_KICKER[t.capability_id], icon: SOURCE_ICON[t.capability_id] ?? Eye };
//   if (t.style === "reminder") return { text: "Reminder", icon: AlarmClock };
//   if (t.kind === "delegation") return { text: "Your agent", icon: Bot };
//   if (t.kind === "team") return { text: "Team", icon: Users };
//   if (t.kind === "verify") return { text: "Needs a check", icon: Eye };
//   return null;
// }
//
// const act = (toastId: string, action: string, reason: string | null = null) =>
//   invoke("lane_action", { toastId, action, reason }).catch(() => {});
//
// export function Lane() {
//   const [toast, setToast] = useState<Toast | null>(null);
//   const [rejecting, setRejecting] = useState(false);
//   const ref = useRef<HTMLDivElement>(null);
//
//   useEffect(() => {
//     const un = listen<Toast | null>("genios://lane", (e) => setToast(e.payload));
//     invoke<Toast | null>("lane_current").then(setToast).catch(() => {});
//     return () => {
//       un.then((f) => f());
//     };
//   }, []);
//
//   // A new toast starts without the reject reasons open.
//   useEffect(() => setRejecting(false), [toast?.id]);
//
//   // Fit the window to the toast.
//   useEffect(() => {
//     if (!toast || !ref.current) return;
//     const height = Math.ceil(ref.current.getBoundingClientRect().height) + 16;
//     invoke("lane_resize", { height }).catch(() => {});
//   }, [toast, rejecting]);
//
//   if (!toast) return null;
//   const proposal = toast.capability_id === PROPOSAL;
//   const buttons = toast.actions.filter((a) => a.id !== "dismiss");
//   const k = kicker(toast);
//   // A draft review's notes are a list (one per body line); copying is the only action.
//   const lines =
//     toast.lines.length > 0
//       ? toast.lines
//       : toast.capability_id === DRAFT_REVIEW && toast.body
//         ? toast.body.split("\n")
//         : [];
//
//   const urgent = toast.priority === "high" || toast.priority === "critical";
//   return (
//     <div
//       ref={ref}
//       className={`lane-toast ${toast.style} k-${toast.kind} p-${toast.priority}`}
//       onMouseEnter={() => invoke("lane_hover", { hover: true }).catch(() => {})}
//       onMouseLeave={() => invoke("lane_hover", { hover: false }).catch(() => {})}
//     >
//       <span className="lane-close">
//         <IconButton label="Dismiss" icon={X} onClick={() => act(toast.id, "dismiss")} />
//       </span>
//       <div className="lane-main" onClick={() => !proposal && act(toast.id, "open")}>
//         {(k || urgent) && (
//           <div className="lane-kicker">
//             {k && <k.icon size={13} strokeWidth={2} aria-hidden />}
//             {k?.text}
//             {urgent && <Status tone="accent">Now</Status>}
//           </div>
//         )}
//         <div className={`lane-headline${proposal ? " lane-request" : ""}`}>{toast.headline}</div>
//         {lines.length > 0 ? (
//           <ul className="lane-lines">
//             {lines.map((l, i) => (
//               <li key={i}>{l}</li>
//             ))}
//           </ul>
//         ) : (
//           toast.body && <div className="lane-body">{toast.body}</div>
//         )}
//       </div>
//       {proposal && rejecting ? (
//         <div className="lane-actions">
//           <span className="lane-note">Reject because:</span>
//           {REJECT_REASONS.map((r) => (
//             <Button key={r} small onClick={() => act(toast.id, REJECT, r)}>
//               {r}
//             </Button>
//           ))}
//           <Button small kind="link" className="lane-end" onClick={() => setRejecting(false)}>
//             Back
//           </Button>
//         </div>
//       ) : (
//         <div className="lane-actions">
//           {buttons.map((a, i) => (
//             <Button
//               key={a.id}
//               small
//               kind={i === 0 ? "ink" : "line"}
//               onClick={() => (proposal && a.id === REJECT ? setRejecting(true) : act(toast.id, a.id))}
//             >
//               {a.label ?? LABELS[a.id] ?? a.id}
//             </Button>
//           ))}
//           {/* Screen insights carry their own "Not useful" button (P8 C6). */}
//           {toast.style === "advice" && toast.kind !== "delegation" && toast.capability_id !== NOTICE && !toast.actions.some((a) => a.id === "not_useful") && (
//             <Button small kind="link" className="lane-end" onClick={() => act(toast.id, "wrong")}>
//               Not useful
//             </Button>
//           )}
//         </div>
//       )}
//     </div>
//   );
// }
```

#### `src/lane/lane.css`

```css
// /* Popups: the panel's look (theme.css), one at a time, top-right. A source line on top, the
//    headline, one line, the buttons. No coloured edges: something urgent says "Now" with the dot. */
// body {
//   padding: 8px;
// }
//
// .lane-toast {
//   position: relative;
//   display: grid;
//   gap: 6px;
//   padding: 11px 36px 12px 14px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line-strong);
//   border-radius: 14px;
//   box-shadow: var(--dx-shadow-pop);
//   animation: lane-in 160ms ease-out;
// }
//
// .lane-main {
//   display: grid;
//   gap: 4px;
//   cursor: pointer;
// }
//
// .lane-kicker {
//   display: flex;
//   align-items: center;
//   gap: 6px;
//   font-size: 12px;
//   font-weight: 400;
//   color: var(--dx-mist);
// }
// .lane-kicker svg {
//   flex: none;
//   color: var(--dx-ink-2);
// }
// .lane-kicker .dx-status {
//   margin-left: 4px;
// }
//
// .lane-headline {
//   font-size: 14px;
//   font-weight: 560;
//   line-height: 1.35;
//   color: var(--dx-ink);
// }
// .reminder .lane-headline,
// .lane-request {
//   font-weight: 560;
// }
// .lane-request {
//   user-select: text;
// }
//
// .lane-body,
// .lane-lines {
//   font-size: 13px;
//   line-height: 1.42;
//   color: var(--dx-ink-2);
// }
// .lane-lines {
//   list-style: none;
//   padding: 0;
//   display: grid;
//   gap: 2px;
// }
// .lane-lines li::before {
//   content: "·";
//   margin-right: 7px;
//   color: var(--dx-mist);
// }
//
// .lane-actions {
//   display: flex;
//   flex-wrap: wrap;
//   align-items: center;
//   gap: 6px;
//   margin-top: 4px;
// }
// .lane-actions:empty {
//   display: none;
// }
// .lane-note {
//   width: 100%;
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
// .lane-end {
//   margin-left: auto;
// }
//
// .lane-close {
//   position: absolute;
//   top: 8px;
//   right: 8px;
// }
//
// @keyframes lane-in {
//   from {
//     opacity: 0;
//     transform: translateY(-6px);
//   }
// }
```

---

## 8 · Dummy only: the stand-ins

Not part of the app: Tauri and the brain, replaced so the dummy runs in a browser.

#### `mock/tauri/core.ts`

```ts
// // Stand-in for @tauri-apps/api/core in the render check: the Rust commands the panel and the lane
// // call, answered in their real shapes and kept in page state, so a press changes what the next read
// // returns. Every call is recorded in window.__calls for the checks to assert on.
// //
// // The scenario comes from the page's query string (?s=…): normal · setup · busy · signedout ·
// // empty · offline · paused. The cards themselves come from mock_brain.py on :8032.
//
// type Args = Record<string, unknown> | undefined;
// type Call = { cmd: string; args: Args };
//
// declare global {
//   interface Window {
//     __calls: Call[];
//     __hidden?: boolean;
//   }
// }
//
// export const BRAIN = "http://localhost:8032";
// const q = new URLSearchParams(location.search);
// export const scenario = q.get("s") ?? "normal";
// const hours = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();
//
// window.__calls = [];
//
// let capture: Record<string, unknown> = (
//   {
//     normal: { state: "capturing", reader_available: true, last_thread_title: "Neha Kapoor — WhatsApp", queue_depth: 0 },
//     setup: { state: "needs_accessibility", detail: null },
//     policy: { state: "off_by_policy" },
//     paused: { state: "paused", paused_until: new Date(Date.now() + 40 * 60_000).toISOString() },
//     busy: {
//       state: "capturing",
//       reader_available: true,
//       last_thread_title: "Kiran Shah — Gmail",
//       queue_depth: 4,
//       catching_up: 3,
//       insight_budget: { used: 40, cap: 40, resets_at: new Date(Date.now() + 5 * 3_600_000).toISOString() },
//       reader_health: "WhatsApp has shown nothing for 2 hours. Is the chat window open?",
//     },
//   } as Record<string, Record<string, unknown>>
// )[scenario] ?? { state: "capturing", reader_available: true, last_thread_title: "Neha Kapoor — WhatsApp", queue_depth: 0 };
//
// let followups = [
//   {
//     id: "f1", kind: "my_promise", text: "Send Neha the investor deck", who: "Neha Kapoor", app: "net.whatsapp.WhatsApp",
//     thread_key: "wa:chat:neha", quote: "will send the deck by Friday", subject_node_id: "n26", due_at: hours(-30), created_at: hours(40),
//   },
//   {
//     id: "f2", kind: "ask", text: "Kiran asked for the data-room link", who: "Kiran Shah", app: "generic",
//     thread_key: "doc:com.google.Chrome:mail.google.com/mail/u/0", quote: "Can you share the data-room link today?",
//     subject_node_id: null, due_at: hours(3), created_at: hours(5),
//   },
//   {
//     id: "f3", kind: "deadline", text: "DPIIT application closes", who: null, app: "generic",
//     thread_key: "doc:com.google.Chrome:startupindia.gov.in/apply", quote: "Last date: 31 Oct",
//     subject_node_id: null, due_at: hours(-200), created_at: hours(30),
//   },
// ];
// if (scenario === "empty" || scenario === "setup") followups = [];
//
// const recent = [
//   {
//     id: "r1", headline: "Morning brief", kind: "brief", at: hours(5),
//     body: "Your promise, due 6 pm: Send Neha the investor deck\nKiran asked for the data-room link\nDPIIT application closes 31 Oct",
//     thread_key: null, app: null, who: null, quote: null, feedback: null,
//   },
//   {
//     id: "r2", headline: "Neha is waiting on the deck you promised — you promised 2 days ago", kind: "followup", at: hours(2),
//     body: null, thread_key: "wa:chat:neha", app: "whatsapp", who: "Neha Kapoor", quote: "will send the deck by Friday",
//     said_at: hours(40), feedback: null,
//   },
//   {
//     id: "r3", headline: "Kiran asked for the data-room link — asked 2 min ago", kind: "ask", at: hours(1),
//     body: null, thread_key: "web:mail.google.com:x", app: "gmail", who: "Kiran Shah", quote: "Can you share the data-room link today?",
//     said_at: hours(1), feedback: "useful",
//   },
//   {
//     id: "r4", headline: "Evokoa is waiting on a confirmed time", kind: "screen", at: hours(27),
//     body: "Ananya proposed Thursday 4 pm and asked for the pilot numbers.", thread_key: "web:mail.google.com:y", app: "gmail",
//     who: "Ananya Rao", quote: "Does Thursday 4 pm work for the pilot review?", said_at: hours(28), feedback: null,
//   },
// ];
//
// const weekly = {
//   week_start: "2026-10-19", week_end: "2026-10-25", promises_caught: 5, promises_kept: 3, asks_flagged: 6, asks_answered: 4,
//   deadlines_flagged: 2, risks_flagged: 1, popups_shown: 14, useful: 6, not_useful: 2, nudged_then_closed: 3,
// };
//
// const toasts: Record<string, unknown> = {
//   advice: {
//     id: "t1", style: "advice", kind: "screen", capability_id: "moment.screen_insight", priority: "normal",
//     headline: "Kiran asked for the data-room link", body: "He asked in Gmail 2 min ago and it is still unanswered.",
//     actions: [{ id: "open_card", label: null }, { id: "snooze" }, { id: "useful" }, { id: "not_useful" }], lines: [],
//   },
//   urgent: {
//     id: "t5", style: "advice", kind: "screen", capability_id: "moment.due_today", priority: "critical",
//     headline: "The DPIIT application closes today", body: "You have not opened the form since Monday.",
//     actions: [{ id: "open_card", label: null }, { id: "snooze" }], lines: [],
//   },
//   reminder: {
//     id: "t2", style: "reminder", kind: "followup", capability_id: "moment.followup", priority: "high",
//     headline: "Your promise, due 6 pm: Send Neha the investor deck", body: null,
//     actions: [{ id: "done" }, { id: "remind_1h" }, { id: "remind_tomorrow" }], lines: [],
//   },
//   proposal: {
//     id: "t3", style: "advice", kind: "delegation", capability_id: "delegation.proposal", priority: "normal",
//     headline: "Ask my agent to send Kiran the data-room link from Drive › Fundraise › Data room", body: null,
//     actions: [{ id: "approve_delegation", label: "Approve" }, { id: "edit_delegation", label: "Edit" }, { id: "reject_delegation", label: "Reject" }],
//     lines: [],
//   },
//   brief: {
//     id: "t4", style: "advice", kind: "brief", capability_id: "moment.daily_brief", priority: "normal",
//     headline: "3 things today", body: null, actions: [{ id: "open_card", label: "Open GeniOS" }],
//     lines: ["Your promise, due 6 pm: Send Neha the investor deck", "Kiran asked for the data-room link", "DPIIT application closes 31 Oct"],
//   },
// };
//
// const pending = () => ({
//   status: "pending", user_code: "KQ7D-M3XW", verification_uri: "https://brain.thegenios.com/device",
//   verification_uri_complete: null, expires_in: 600, expires_at: new Date(Date.now() + 540_000).toISOString(),
// });
// let auth: Record<string, unknown> =
//   scenario === "signedout" ? { status: "signed_out", reason: null } : { status: "signed_in", seat_id: "s1", device_id: "d1", email: "rohit@thegenios.com" };
//
// const handlers: Record<string, (a: Record<string, unknown>) => unknown> = {
//   auth_state: () => ({ ...auth, base_url: scenario === "offline" ? "http://localhost:1" : BRAIN }),
//   auth_start: () => (auth = pending()),
//   auth_poll_status: () => auth,
//   auth_cancel: () => (auth = { status: "signed_out", reason: null }),
//   auth_open_browser: () => null,
//   sign_out: () => (auth = { status: "signed_out", reason: null }),
//   get_access_token: () => ({ access_token: "preview", base_url: scenario === "offline" ? "http://localhost:1" : BRAIN }),
//   capture_status: () => capture,
//   capture_pause: (a) => (capture = { state: "paused", paused_until: new Date(Date.now() + Number(a.minutes) * 60_000).toISOString() }),
//   capture_resume: () => (capture = { state: "capturing", reader_available: true, last_thread_title: "Neha Kapoor — WhatsApp", queue_depth: 0 }),
//   capture_policy_now: () => null,
//   sync_now: () => (capture = { ...capture, queue_depth: 0 }),
//   capture_open_accessibility_settings: () => null,
//   open_dashboard: () => null,
//   followups_open: () => followups,
//   followup_done: (a) => (followups = followups.filter((f) => f.id !== a.id)),
//   followup_snooze: (a) => (followups = followups.filter((f) => f.id !== a.id)),
//   followup_draft: () => null,
//   lane_recent: () => recent,
//   recent_feedback: (a) => {
//     const r = recent.find((x) => x.id === a.id);
//     if (r) r.feedback = String(a.action);
//     return null;
//   },
//   weekly_report: () => (scenario === "offline" ? null : weekly),
//   lane_current: () => toasts[q.get("toast") ?? "advice"] ?? null,
//   lane_action: () => null,
//   lane_hover: () => null,
//   lane_resize: () => null,
// };
//
// export async function invoke<T>(cmd: string, args?: Args): Promise<T> {
//   window.__calls.push({ cmd, args });
//   const h = handlers[cmd];
//   return (h ? h(args ?? {}) : null) as T;
// }
```

#### `mock/tauri/event.ts`

```ts
// // Stand-in for @tauri-apps/api/event: listeners kept in the page; a check pushes an event with
// // window.__emit(name, payload), the way the Rust core emits one.
// export type UnlistenFn = () => void;
// type Handler = (e: { event: string; payload: unknown }) => void;
//
// declare global {
//   interface Window {
//     __emit: (event: string, payload: unknown) => void;
//   }
// }
//
// const listeners = new Map<string, Set<Handler>>();
//
// window.__emit = (event, payload) => {
//   for (const h of listeners.get(event) ?? []) h({ event, payload });
// };
//
// export async function listen<T>(event: string, handler: (e: { event: string; payload: T }) => void): Promise<UnlistenFn> {
//   const h = handler as Handler;
//   if (!listeners.has(event)) listeners.set(event, new Set());
//   listeners.get(event)!.add(h);
//   return () => listeners.get(event)?.delete(h);
// }
```

#### `mock/tauri/window.ts`

```ts
// // Stand-in for @tauri-apps/api/window: hide() is recorded (window.__hidden) so a check can see
// // that Esc or ✕ closed the panel.
// type FocusHandler = (e: { payload: boolean }) => void;
//
// export function getCurrentWindow() {
//   return {
//     hide: async () => {
//       window.__hidden = true;
//       window.__calls.push({ cmd: "window.hide", args: undefined });
//     },
//     show: async () => {
//       window.__hidden = false;
//     },
//     setFocus: async () => {},
//     onFocusChanged: async (_handler: FocusHandler) => () => {},
//   };
// }
```

#### `mock/tauri/http.ts`

```ts
// // Stand-in for @tauri-apps/plugin-http: the webview's own fetch (mock_brain.py sends CORS for the
// // preview origin). ?s=empty answers /cards with no cards; ?s=offline fails like a dropped network.
// const scenario = new URLSearchParams(location.search).get("s") ?? "normal";
//
// export async function fetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
//   const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
//   if (scenario === "offline") throw new TypeError("error sending request: connection refused");
//   if (scenario === "empty" && /\/cards$/.test(url)) {
//     return new Response(JSON.stringify({ cards: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
//   }
//   return window.fetch(input, init);
// }
```

#### `mock/brain.py`

```python
# """Stand-in brain for the desktop app's render check, in the REAL route shapes.
#
# The cards and their details are the GeniOS-010/06-CARDS stand-in (brain `deliver/card_builder.build_draft`
# and `api/routes.get_card` shapes): a formula card, two expert cards, two question cards and a monitor card,
# with the person-level meetings and promise that the brain attaches to every card about the same node.
#
# Routes: GET /cards, GET /cards/{id}, POST /cards/{id}/action, POST /__reset.
# The action route refuses what `deliver/actions.py` refuses:
#   * `wrong` without one of the card's reasons      -> 422 invalid_wrong_reason
#   * a press a question card does not offer          -> 422 not_offered
#   * `answer` with no words                          -> 422 answer_says_nothing
#   * Done on c-f55 (handed to another seat)          -> 403 assigned_to_different_seat
# An accepted press takes the card out of /cards, as the queue does; an answer versions the question
# card ("Your answer is in; the file is read again"), which then offers only Later.
# Port 8032, CORS for http://localhost:5199 (scripts/preview/vite.preview.ts).
# """
# import json
# from datetime import datetime, timedelta, timezone
# from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
#
# ORIGIN = "http://localhost:5199"
# now = datetime.now(timezone.utc)
# iso = lambda h: (now - timedelta(hours=h)).isoformat()
#
# CARDS = [
#     {"card_id": "c-evokoa", "signal_id": "s90", "assignee": None, "domain": "admin", "urgency_band": "high",
#      "headline": "Confirm the call time with Evokoa", "subject_node_id": "n90",
#      "situation": "Evokoa proposed Thursday 4 pm for the pilot review and is waiting for your confirmation. The calendar has no invite yet.",
#      "score": 82, "state": "surfaced", "render_mode": "llm", "created_at": iso(26), "expires_at": iso(-900)},
#     {"card_id": "c-f24", "signal_id": "s24", "assignee": None, "domain": "admin", "urgency_band": "high",
#      "headline": "Upload the Phase-1 review deck to the cohort folder", "subject_node_id": "n24",
#      "situation": "The accelerator's Phase-1 review is on the 28th; the cohort folder has no deck from you yet.",
#      "score": 78, "state": "surfaced", "render_mode": "review", "created_at": iso(30), "expires_at": iso(-900)},
#     {"card_id": "c-f26", "signal_id": "s26", "assignee": None, "domain": "admin", "urgency_band": "standard",
#      "headline": "Reply to Neha to confirm Tuesday 30 Sep at 11 am IST", "subject_node_id": "n26",
#      "situation": "Neha proposed a time for the partner call and is waiting for your yes.",
#      "score": 55, "state": "surfaced", "render_mode": "review", "created_at": iso(5), "expires_at": iso(-900)},
#     {"card_id": "c-f22", "signal_id": "s22", "assignee": None, "domain": "admin", "urgency_band": "standard",
#      "headline": "Can you tell us whether you are a startup incubated on the university's campus?",
#      "subject_node_id": "n22",
#      "situation": "A university startup cell announced a seed grant; whether you qualify turns on one fact.",
#      "score": 40, "state": "surfaced", "render_mode": "question", "created_at": iso(20), "expires_at": iso(-900)},
#     {"card_id": "c-f55", "signal_id": "s55", "assignee": None, "domain": "admin", "urgency_band": "standard",
#      "headline": "Send Dev Malhotra the pricing sheet", "subject_node_id": "n55",
#      "situation": "Dev asked for pricing four weeks ago; nothing has gone out since.",
#      "score": 35, "state": "surfaced", "render_mode": "review", "created_at": iso(60), "expires_at": iso(-900)},
#     {"card_id": "c-f15", "signal_id": "s15", "assignee": None, "domain": "admin", "urgency_band": "standard",
#      "headline": "What is the next step with Cobalt Peak? We held the one we found: a fact your move rests on quotes nothing from the mail it cites.",
#      "subject_node_id": "n15", "situation": "Your outreach to Cobalt Peak has had no reply in eight weeks.",
#      "score": 30, "state": "surfaced", "render_mode": "question", "created_at": iso(80), "expires_at": iso(-900)},
# ]
#
# SHARED_MEETINGS = [
#     {"title": "Weekly founders sync", "start_at": iso(-30), "status": "confirmed", "state": "scheduled", "state_label": "Scheduled", "source": "gcal"},
#     {"title": "Investor update call", "start_at": iso(20), "status": "confirmed", "state": "past_scheduled", "state_label": "Past, not confirmed it happened", "source": "gcal"},
#     {"title": "Hiring sync", "start_at": iso(44), "status": "confirmed", "state": "past_scheduled", "state_label": "Past, not confirmed it happened", "source": "gcal"},
#     {"title": "Board prep", "start_at": iso(70), "status": "confirmed", "state": "past_scheduled", "state_label": "Past, not confirmed it happened", "source": "gcal"},
# ]
# SHARED_PROMISE = {"text": "Share the monthly update with investors", "due_at": iso(-48), "status": "open"}
#
# EXPERT_ACTIONS = [
#     {"type": "run_play", "play_id": "expert.file_review", "label": "Draft response", "artifact_ready": True},
#     {"type": "do_it_myself"}, {"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]},
#     {"type": "wrong", "reasons": ["not_relevant", "wrong_facts", "bad_timing", "misread_source", "stale_data",
#                                   "wrong_subject", "bad_link", "wrong_conclusion", "not_how_we_work",
#                                   "wrong_person", "wrong_channel"]},
# ]
# QUESTION_ACTIONS = [{"type": "answer"}, {"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]},
#                     {"type": "wrong", "reasons": ["not_relevant", "wrong_facts", "bad_timing"]}]
#
# def inference(sentence, text):
#     return {"sentence": sentence, "inference": text, "source": "expert_check"}
#
# DETAILS = {
#     "c-evokoa": {
#         "domain": "admin", "output_lane": "decision", "business_subject": "Ananya Rao", "relationship_role": "Evokoa · pilot customer",
#         "do_nothing_consequence": "The pilot review slips a week and Evokoa's renewal decision moves with it.",
#         "success_signal": "Ananya accepts a calendar invite for Thursday 4 pm.",
#         "outcome_window_days": 2, "context_tags": ["app:gmail"],
#         "actions": [{"type": "do_it_myself"}, {"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]},
#                     {"type": "wrong", "reasons": ["not_relevant", "wrong_facts", "bad_timing"]}],
#         "why": [{"field": "thread.last_inbound", "value": iso(26), "source": "gmail"},
#                 {"field": "thread.ball_in_court", "value": "us", "source": "gmail"},
#                 {"field": "commitment.action", "value": "send the invite with the meeting link once the time is fixed", "source": "gmail"},
#                 {"statement": "A proposed time left unconfirmed for two days is usually lost; confirm or counter within a day.", "source": "expertise"}],
#         "context": {"profile": [{"field": "role", "value": "Head of Operations"}, {"field": "company", "value": "Evokoa"}],
#                     "signals": [{"kind": "meeting_request", "label": "Meeting proposed", "count": 1}, {"kind": "question", "label": "Open question", "count": 1}],
#                     "interactions": [{"title": "Evokoa pilot review", "start_at": iso(-50), "status": "proposed", "state": "scheduled", "state_label": "Proposed, no invite yet", "source": "gcal"}] + SHARED_MEETINGS,
#                     "commitments": [{"text": "We will send the invite with the meeting link once the time is fixed", "due_at": iso(-20), "status": "open"}, SHARED_PROMISE],
#                     "freshness": {"label": "fresh", "note": ""}},
#         "actionability": {"state": "actionable"},
#         "decision": {"card_version": "v2", "recommendation": {"verdict": "reply", "objective": "Confirm Thursday 4 pm with Ananya and send the calendar invite with the meeting link",
#                      "steps": ["Reply in the thread: Thursday 4 pm works", "Send the calendar invite with the meeting link to Ananya", "Add the pilot numbers she asked for to the invite"], "avoid": "Proposing a new time without saying why"},
#                      "confidence": {"evidence": 0.9, "identity": None, "situation": None, "recommendation": 0.8}, "grounding": {}},
#     },
#     "c-f24": {
#         "output_lane": "decision", "lane_label": "Decision", "level": "prescriptive",
#         "business_subject": "Divya Raman", "relationship_role": "watched",
#         "why_now": "Nothing in 13 days — longer than this file has gone quiet before (11.96 days)",
#         "unresolved_item": "Divya Raman asked a question — waiting on you since 1 Sep; Divya Raman asked a question — waiting on you since 13 Sep",
#         "recommended": {"who": "you", "what": "Upload the Phase-1 review deck to the cohort folder by the twenty-eighth, and check the folder holds the unit economics sheet — if it does not, upload it and tell Divya.",
#                         "for_whom": "the programme", "by_when": "2026-09-28"},
#         "alternative": "If the deck cannot be ready by the twenty-eighth, tell Divya before the date and ask what the programme allows.",
#         "wait_or_stop": "Nothing to wait for; the moves are ours, and they are done when both are in the folder before the review.",
#         "outcome_window_days": 2, "success_signal": "Both files are in the cohort folder before the review.",
#         "do_nothing_consequence": "The review goes ahead without your deck.",
#         "confidence_vector": {"C": 8000, "I": 5600, "U": 8000}, "capability_key": "expert.file_review",
#         "context_tags": ["app:gmail"], "actions": EXPERT_ACTIONS,
#         "why": [
#             {"sentence": "headline", "evidence": [3, 7], "quotes": ["Please upload your Phase-1 review deck to the cohort folder by 28 Sep.", "Could you also add the unit economics sheet?"], "source": "expert_check"},
#             inference("situation", "the expert's reading of the file — an inference, not a quote"),
#             inference("done_when", "what done looks like, as the expert judges it — an inference, not a quote"),
#             inference("do_nothing", "what doing nothing costs, as the expert judges it — an inference, not a quote"),
#             {"window": "two days before the review", "days": 2, "from": "the programme's mail", "source": "card_lines"},
#             {"field": "thread.last_inbound", "value": "2026-09-13T10:12:00+00:00", "source": "gmail"},
#         ],
#         "context": {"profile": [{"field": "role", "value": "Programme manager"}], "signals": [{"kind": "question", "label": "Asked a question", "count": 2}],
#                     "interactions": SHARED_MEETINGS, "commitments": [SHARED_PROMISE], "freshness": {"label": "fresh", "note": ""}},
#         "actionability": {"state": "actionable"},
#         "decision": {"card_version": "v2", "recommendation": {"verdict": "reply", "objective": "Reply to what they actually asked",
#                      "steps": ["Answer their open question"], "avoid": None},
#                      "confidence": {"evidence": 0.8, "identity": None, "situation": None, "recommendation": 0.56}, "grounding": {}},
#     },
#     "c-f26": {
#         "output_lane": "decision", "lane_label": "Decision", "level": "prescriptive",
#         "business_subject": "Neha Kapoor", "relationship_role": "partner",
#         "why_now": "She proposed Tuesday 11 am two days ago; the slot is in four days.",
#         "unresolved_item": "Neha asked whether Tuesday 30 Sep at 11 am IST works — waiting on you since 24 Sep",
#         "recommended": {"who": "you", "what": "Reply to Neha to confirm Tuesday 30 Sep at 11 am IST and send the invite.", "for_whom": "Neha", "by_when": "2026-09-27"},
#         "alternative": "If Tuesday does not work, offer two other times this week.",
#         "wait_or_stop": "Stop once the invite is accepted.",
#         "outcome_window_days": 3, "success_signal": "Neha accepts the invite.",
#         "do_nothing_consequence": "The slot lapses and the call slips a week.",
#         "confidence_vector": {"C": 9000, "I": 8500, "U": 7000}, "capability_key": "expert.file_review",
#         "context_tags": ["app:gmail"], "actions": EXPERT_ACTIONS,
#         "why": [
#             {"sentence": "headline", "evidence": [12], "quotes": ["Would Tuesday 30 Sep, 11 am IST work for a call?"], "source": "expert_check"},
#             inference("situation", "the expert's reading of the file — an inference, not a quote"),
#             {"sentence": "draft", "to": "neha@cleanwave.io", "evidence": [12], "quotes": ["Would Tuesday 30 Sep, 11 am IST work for a call?"], "source": "expert_check"},
#             {"window": "before Tuesday", "days": 3, "from": "her mail", "source": "card_lines"},
#         ],
#         "context": {"profile": [], "signals": [{"kind": "meeting_request", "label": "Proposed a meeting", "count": 1}], "interactions": SHARED_MEETINGS, "commitments": [SHARED_PROMISE], "freshness": {"label": "fresh", "note": ""}},
#         "actionability": {"state": "actionable"},
#         "decision": {"card_version": "v2", "recommendation": {"verdict": "reply", "objective": "Reply to what they actually asked",
#                      "steps": ["Confirm or decline the proposed meeting"], "avoid": None},
#                      "confidence": {"evidence": 0.9, "identity": None, "situation": None, "recommendation": 0.7}, "grounding": {}},
#     },
#     "c-f22": {
#         "output_lane": "investigation", "lane_label": "Question", "level": "abstain",
#         "abstained_because": "the file asks you one question before any move — answer it on the file's card",
#         "business_subject": "University startup cell", "relationship_role": None,
#         "why_now": "The seed grant's applications close on 31 Oct.", "unresolved_item": None,
#         "recommended": None, "alternative": None, "wait_or_stop": None, "outcome_window_days": None,
#         "confidence_vector": {"C": 6000, "I": 5000, "U": 4000}, "capability_key": "expert.file_review",
#         "context_tags": ["app:gmail"], "actions": QUESTION_ACTIONS,
#         "why": [{"sentence": "headline", "question": "Are you a startup incubated on the university's campus?",
#                  "because": "the grant is open only to startups incubated on campus, and nothing in your mail says whether you are", "source": "expert_check"}],
#         "context": {"profile": [], "signals": [], "interactions": [], "commitments": [], "freshness": {"label": "fresh", "note": ""}},
#         "actionability": {"state": "context_incomplete", "missing": ["commitment.action"], "message": "We could not confirm what is being asked.",
#                           "recommended": "Open the source and review the request"},
#         "decision": {"card_version": "v2", "recommendation": {"verdict": "review_source", "objective": "Verify what's actually needed before acting",
#                      "steps": ["Open the source and review the request"], "avoid": None},
#                      "confidence": {"evidence": 0.6, "identity": None, "situation": None, "recommendation": None}, "grounding": {}},
#     },
#     "c-f55": {
#         "output_lane": "monitor", "lane_label": "Monitor", "level": "prescriptive",
#         "business_subject": "Dev Malhotra", "relationship_role": None,
#         "why_now": "Four weeks with no outbound while he waits.",
#         "unresolved_item": "Dev Malhotra asked for the pricing sheet — waiting on you since 2 Sep",
#         "recommended": None, "alternative": None, "wait_or_stop": None, "outcome_window_days": None,
#         "confidence_vector": {"C": 7000, "I": 6000, "U": 5000}, "capability_key": None,
#         "context_tags": ["app:gmail"], "actions": EXPERT_ACTIONS,
#         "why": [{"field": "thread.last_inbound", "value": "2026-09-02T08:00:00+00:00", "source": "gmail"},
#                 {"evidence_id": "ev_91c2", "source": "reasoning_trace"}],
#         "context": {"profile": [], "signals": [], "interactions": [], "commitments": [], "freshness": {"label": "fresh", "note": ""}},
#         "actionability": {"state": "actionable"},
#         "decision": {"card_version": "v2", "recommendation": {"verdict": "review", "objective": "Dev asked for pricing four weeks ago; nothing has gone out since.",
#                      "steps": [], "avoid": None},
#                      "confidence": {"evidence": 0.7, "identity": None, "situation": None, "recommendation": None}, "grounding": {}},
#     },
#     "c-f15": {
#         "output_lane": "investigation", "lane_label": "Question", "level": "abstain",
#         "abstained_because": "the file asks you one question before any move — answer it on the file's card",
#         "business_subject": "Cobalt Peak", "relationship_role": None, "why_now": "Eight weeks without a reply.",
#         "confidence_vector": {"C": 4000, "I": 7000, "U": 3000}, "capability_key": "expert.file_review",
#         "context_tags": ["app:gmail"], "actions": QUESTION_ACTIONS,
#         "why": [{"sentence": "headline", "question": "What is the next step with Cobalt Peak?",
#                  "because": "a fact your move rests on quotes nothing from the mail it cites", "source": "expert_check"}],
#         "context": {"profile": [], "signals": [], "interactions": [], "commitments": [], "freshness": {"label": "fresh", "note": ""}},
#         "actionability": {"state": "actionable"},
#         "decision": {"card_version": "v2", "recommendation": {"verdict": "review", "objective": "Your outreach to Cobalt Peak has had no reply in eight weeks.", "steps": [], "avoid": None},
#                      "confidence": {"evidence": 0.4, "identity": None, "situation": None, "recommendation": None}, "grounding": {}},
#     },
# }
#
# QUESTION_OFFERS = {"answer", "snooze", "requeue", "wrong"}
# ANSWERED_HEADLINE = "Your answer is in; the file is read again"
# STATE = {"gone": set(), "answered": set()}
#
#
# def card_row(card):
#     if card["card_id"] in STATE["answered"]:
#         return {**card, "headline": ANSWERED_HEADLINE}
#     return card
#
#
# def card_detail(card):
#     detail = {**card_row(card), **DETAILS.get(card["card_id"], {})}
#     if card["card_id"] in STATE["answered"]:
#         detail["headline"] = ANSWERED_HEADLINE
#         detail["actions"] = [{"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]}]
#     return detail
#
#
# def offered_reasons(card_id):
#     for a in DETAILS.get(card_id, {}).get("actions", []):
#         if a.get("type") == "wrong":
#             return set(a.get("reasons") or [])
#     return set()
#
#
# class H(BaseHTTPRequestHandler):
#     def _cors(self):
#         self.send_header("Access-Control-Allow-Origin", ORIGIN)
#         self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
#         self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
#
#     def do_OPTIONS(self):
#         self.send_response(204); self._cors(); self.end_headers()
#
#     def _send(self, status, body):
#         self.send_response(status)
#         self._cors(); self.send_header("Content-Type", "application/json"); self.end_headers()
#         self.wfile.write(json.dumps(body).encode())
#
#     def do_GET(self):
#         path = self.path.split("?")[0]
#         parts = path.strip("/").split("/")
#         if path == "/cards":
#             return self._send(200, {"cards": [card_row(c) for c in CARDS if c["card_id"] not in STATE["gone"]]})
#         if parts[0] == "cards" and len(parts) == 2:
#             card = next((c for c in CARDS if c["card_id"] == parts[1] and c["card_id"] not in STATE["gone"]), None)
#             if card is None:
#                 return self._send(404, {"detail": "card not found"})
#             return self._send(200, card_detail(card))
#         if parts[0] == "api" and parts[-1] == "members":
#             return self._send(200, {"members": [
#                 {"id": "m2", "name": "Harsh", "email": "harsh@example.com", "role": "admin", "status": "active"},
#                 {"id": "m3", "name": "Divya Raman", "email": "divya@example.com", "role": "member", "status": "active"}]})
#         if path == "/v1/agents":
#             return self._send(200, {"agents": [
#                 {"agent_id": "a1", "name": "Inbox agent", "description": "Drafts the reply and sends it after you approve", "status": "active"}]})
#         self._send(404, {"detail": "not in the stand-in brain"})
#
#     def do_POST(self):
#         path = self.path.split("?")[0]
#         size = int(self.headers.get("Content-Length") or 0)
#         sent = json.loads(self.rfile.read(size) or b"{}")
#         if path == "/__reset":
#             STATE["gone"].clear(); STATE["answered"].clear()
#             return self._send(200, {"ok": True})
#         parts = path.strip("/").split("/")
#         if not (parts[0] == "cards" and len(parts) == 3 and parts[2] == "action"):
#             return self._send(404, {"detail": "not in the stand-in brain"})
#         card = next((c for c in CARDS if c["card_id"] == parts[1] and c["card_id"] not in STATE["gone"]), None)
#         if card is None:
#             return self._send(422, {"detail": {"ok": False, "error": "card_not_actionable"}})
#         action = sent.get("action")
#         question = card["render_mode"] == "question"
#         if question and action not in QUESTION_OFFERS:
#             return self._send(422, {"detail": {"ok": False, "error": "not_offered", "offered": sorted(QUESTION_OFFERS)}})
#         if action == "wrong" and sent.get("reason") not in offered_reasons(card["card_id"]):
#             return self._send(422, {"detail": {"ok": False, "error": "invalid_wrong_reason",
#                                                "allowed_reasons": sorted(offered_reasons(card["card_id"]))}})
#         if action == "answer":
#             if not question:
#                 return self._send(422, {"detail": {"ok": False, "error": "not_a_question"}})
#             if not str(sent.get("words") or "").strip():
#                 return self._send(422, {"detail": {"ok": False, "error": "answer_says_nothing"}})
#             STATE["answered"].add(card["card_id"])
#             return self._send(200, {"ok": True, "state": "surfaced"})
#         if action == "do_it_myself" and card["card_id"] == "c-f55":
#             return self._send(403, {"detail": {"ok": False, "error": "assigned_to_different_seat"}})
#         if action not in ("do_it_myself", "snooze", "wrong", "requeue", "run_play"):
#             return self._send(422, {"detail": {"ok": False, "error": "unknown_action"}})
#         if action != "requeue":
#             STATE["gone"].add(card["card_id"])
#         return self._send(200, {"ok": True, "state": "snoozed" if action == "snooze" else "acted"})
#
#     def log_message(self, *a):
#         pass
#
#
# if __name__ == "__main__":
#     import sys
#     port = int(sys.argv[1]) if len(sys.argv) > 1 else 8032
#     ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
```

#### `src/vite-env.d.ts`

```ts
// /// <reference types="vite/client" />
```
