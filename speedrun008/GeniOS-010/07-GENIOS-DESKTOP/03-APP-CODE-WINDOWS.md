# 07.3 · GeniOS desktop app — the windows (TypeScript, React, CSS), commented out

**Written for:** Harsh and any coding agent working on the Mac app; Rohit, to keep and hand over. This is the part you see: the GeniOS menu (main window) and the popups (lane window), plus how they read cards and call the Rust core.

**What this is:** 91 source files, 15,541 lines, exactly as they stand in the dashboard repo at commit `ed2724d` (branch `rohit/desktop-ux`, GeniOS 0.3.4, 23 Oct 2026). Paths are relative to `Extension/`, except `src/lib/…`, which sits at the dashboard repo's root and is shared with the website.

**It does not run from here, on purpose.** Every line starts with `// ` (shell, Python, TOML and YAML lines with `# `), so nothing in this file can be imported, built or executed by accident. What the code does, and where everything is, is in [`00-README.md`](00-README.md). How it was built, step by step, is in [`02-HOW-IT-WAS-BUILT.md`](02-HOW-IT-WAS-BUILT.md).

**To get the files back** (into an empty folder, never into a repo by accident):

```bash
mkdir -p /tmp/genios-app && cd /tmp/genios-app
python3 - "<path to this file>" <<'PY'
import os, re, sys
text = open(sys.argv[1]).read()
for path, body in re.findall(r"^#### `([^`]+)`\n\n```[a-z]*\n(.*?)\n```", text, re.S | re.M):
    pre = "# " if path.rsplit(".", 1)[-1].lstrip(".") in ("py", "sh", "toml", "yaml", "yml", "gitignore") or path.endswith(".gitignore") else "// "
    lines = [l[len(pre):] if l.startswith(pre) else l[len(pre.rstrip()):] for l in body.split("\n")]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    open(path, "w").write("\n".join(lines) + "\n")
PY
```

## Contents

- **1 · The project** — How the windows are built: the pages, Vite, TypeScript, the scripts in package.json.
  - `package.json` (33 lines)
  - `vite.config.ts` (37 lines)
  - `tsconfig.json` (4 lines)
  - `tsconfig.app.json` (21 lines)
  - `desktop.html` (12 lines)
  - `lane.html` (12 lines)
  - `index.html` (16 lines)
- **2 · The GeniOS menu (main window)** — Sign-in gate, Card · Goals · Pending, the Screen view and its line, Refresh, the account (sound, version), the card that drops (Drop), and how brain cards and screen follow-ups become what the menu shows.
  - `src/desktop/main.tsx` (23 lines)
  - `src/menu/MenuApp.tsx` (533 lines)
  - `src/menu/MenuPanel.tsx` (790 lines)
  - `src/menu/Drop.tsx` (310 lines)
  - `src/menu/live.ts` (123 lines)
  - `src/menu/sample.ts` (196 lines)
  - `src/menu/menu.css` (1445 lines)
- **3 · The popups (lane window)** — One popup at a time, pushed by the Rust core: the drop with its four buttons, the five-second line, hover hold, slide-away.
  - `src/lane/main.tsx` (14 lines)
  - `src/lane/Lane.tsx` (201 lines)
  - `src/lane/lane.css` (22 lines)
- **4 · Sign-in, the brain's routes, and the shared parts** — Device-code sign-in; every call to the brain and to the Rust core; the refusal sentences; the parts and tokens the menu still uses from the older panel.
  - `src/desktop/ActionBar.tsx` (234 lines)
  - `src/desktop/ScreenRow.tsx` (144 lines)
  - `src/desktop/SetupCard.tsx` (245 lines)
  - `src/desktop/SignIn.tsx` (172 lines)
  - `src/desktop/api.ts` (402 lines)
  - `src/desktop/cards.ts` (68 lines)
  - `src/desktop/refusals.ts` (41 lines)
  - `src/desktop/ui.tsx` (329 lines)
  - `src/desktop/Header.css` (63 lines)
  - `src/desktop/SetupCard.css` (98 lines)
  - `src/desktop/detail.css` (272 lines)
  - `src/desktop/rows.css` (189 lines)
  - `src/desktop/screens.css` (159 lines)
  - `src/desktop/theme.css` (684 lines)
- **5 · The website's card reader (shared)** — One reader for every screen: the menu reads cards exactly the way the website's Cards page does.
  - `src/lib/card-read.ts` (599 lines)
  - `src/lib/card-shape.ts` (176 lines)
- **6 · The older panel (in the code, no longer opened)** — Today · This week · History · an opened card. Since 0.3.0 the main window opens the menu instead; nothing here is loaded by the app (checked by following every import from desktop/main.tsx and lane/main.tsx). Kept for reference and for its previews.
  - `src/desktop/CardDetail.tsx` (305 lines)
  - `src/desktop/CardRow.preview.tsx` (37 lines)
  - `src/desktop/CardRow.tsx` (77 lines)
  - `src/desktop/DesktopAdvisor.tsx` (444 lines)
  - `src/desktop/Header.preview.tsx` (50 lines)
  - `src/desktop/Header.tsx` (133 lines)
  - `src/desktop/HistoryView.tsx` (128 lines)
  - `src/desktop/ScreenRow.preview.tsx` (34 lines)
  - `src/desktop/SetupCard.preview.tsx` (29 lines)
  - `src/desktop/TodayView.tsx` (111 lines)
  - `src/desktop/WeekView.tsx` (129 lines)
  - `src/desktop/api.preview.tsx` (47 lines)
  - `src/desktop/cards.preview.tsx` (39 lines)
  - `src/desktop/panel.css` (15 lines)
  - `src/desktop/refusals.test.ts` (32 lines)
  - `src/desktop/rows.test.ts` (55 lines)
  - `src/desktop/rows.ts` (86 lines)
  - `src/desktop/theme.preview.tsx` (57 lines)
  - `src/desktop/ui.preview.tsx` (116 lines)
- **7 · The studio simulator (index.html, not part of the Mac app)** — The product-video surface that shares this Vite project.
  - `src/main.tsx` (10 lines)
  - `src/App.tsx` (974 lines)
  - `src/scenarios.ts` (453 lines)
  - `src/types.ts` (128 lines)
  - `src/styles.css` (2595 lines)
  - `src/vite-env.d.ts` (1 lines)
- **8 · Building and checking** — The DMG script with the fixed local signature, the older signing and reader-build scripts, and the browser preview harness (stand-ins for the Rust core and the brain) the render checks run on.
  - `scripts/mac-dev-dmg.sh` (71 lines)
  - `scripts/sign-macos.sh` (36 lines)
  - `scripts/build-sidecar.sh` (68 lines)
  - `scripts/preview/.gitignore` (1 lines)
  - `scripts/preview/check.mjs` (238 lines)
  - `scripts/preview/checks/actions.mjs` (58 lines)
  - `scripts/preview/checks/boot.mjs` (12 lines)
  - `scripts/preview/checks/detail-order.mjs` (35 lines)
  - `scripts/preview/checks/face.mjs` (39 lines)
  - `scripts/preview/checks/header.mjs` (47 lines)
  - `scripts/preview/checks/history.mjs` (25 lines)
  - `scripts/preview/checks/lane.mjs` (28 lines)
  - `scripts/preview/checks/press.mjs` (26 lines)
  - `scripts/preview/checks/reads.mjs` (19 lines)
  - `scripts/preview/checks/renders.mjs` (13 lines)
  - `scripts/preview/checks/screen-rows.mjs` (30 lines)
  - `scripts/preview/checks/setup.mjs` (44 lines)
  - `scripts/preview/checks/signin.mjs` (22 lines)
  - `scripts/preview/checks/today.mjs` (50 lines)
  - `scripts/preview/checks/tokens.mjs` (38 lines)
  - `scripts/preview/checks/ui.mjs` (33 lines)
  - `scripts/preview/checks/week.mjs` (20 lines)
  - `scripts/preview/gallery.html` (12 lines)
  - `scripts/preview/gallery.tsx` (34 lines)
  - `scripts/preview/menu-check.mjs` (234 lines)
  - `scripts/preview/mock_brain.py` (290 lines)
  - `scripts/preview/tauri-mock/app.ts` (4 lines)
  - `scripts/preview/tauri-mock/core.ts` (176 lines)
  - `scripts/preview/tauri-mock/event.ts` (28 lines)
  - `scripts/preview/tauri-mock/http.ts` (12 lines)
  - `scripts/preview/tauri-mock/window.ts` (17 lines)
  - `scripts/preview/tsconfig.json` (4 lines)
  - `scripts/preview/vite.preview.mjs` (25 lines)

## 1 · The project

How the windows are built: the pages, Vite, TypeScript, the scripts in package.json.

#### `package.json`

```json
// {
//   "name": "genios-executive-surface",
//   "private": true,
//   "version": "0.3.4",
//   "type": "module",
//   "scripts": {
//     "dev": "vite --host 0.0.0.0",
//     "build": "tsc --noEmit -p tsconfig.app.json && vite build",
//     "preview": "vite preview --host 0.0.0.0",
//     "app:dev": "tauri dev",
//     "app:build": "tauri build --debug",
//     "app:release": "tauri build && ./scripts/sign-macos.sh",
//     "tauri": "tauri",
//     "sidecar": "./scripts/build-sidecar.sh"
//   },
//   "dependencies": {
//     "@fontsource-variable/inter": "^5.1.0",
//     "@tauri-apps/api": "^2.11.1",
//     "@tauri-apps/plugin-global-shortcut": "^2.3.2",
//     "@tauri-apps/plugin-http": "^2.5.9",
//     "lucide-react": "^0.468.0",
//     "react": "^19.0.0",
//     "react-dom": "^19.0.0"
//   },
//   "devDependencies": {
//     "@tauri-apps/cli": "^2.11.4",
//     "@types/react": "^19.0.0",
//     "@types/react-dom": "^19.0.0",
//     "@vitejs/plugin-react": "^4.3.4",
//     "typescript": "~5.7.2",
//     "vite": "^6.0.5"
//   }
// }
```

#### `vite.config.ts`

```ts
// import { defineConfig } from "vite";
// import react from "@vitejs/plugin-react";
// import { resolve } from "node:path";
//
// // Two entry points share one Vite project:
// //   index.html   — the studio simulator (product-video surface)
// //   desktop.html — the Tauri floating advisor, wired to the live GeniOS engine
// export default defineConfig({
//   plugins: [react()],
//   // Tauri expects a fixed dev port and should not clear the terminal it runs in.
//   clearScreen: false,
//   server: {
//     port: 5173,
//     strictPort: true,
//     // The panel reads cards with the web's own reader (../src/lib/card-read.ts).
//     fs: { allow: [resolve(__dirname, "..")] },
//   },
//   envPrefix: ["VITE_", "TAURI_ENV_"],
//   // This project sits inside the dashboard repo, and PostCSS config discovery walks
//   // *upward* — so Vite would find the dashboard's Tailwind postcss.config.mjs and then
//   // fail to resolve @tailwindcss/postcss, which is installed in the parent's
//   // node_modules, not ours. An inline config stops the search. Nothing here uses
//   // Tailwind: desktop.css and styles.css are plain CSS.
//   css: {
//     postcss: { plugins: [] },
//   },
//   build: {
//     rollupOptions: {
//       input: {
//         main: resolve(__dirname, "index.html"),
//         desktop: resolve(__dirname, "desktop.html"),
//         // P3 lane window: one toast at a time, never focused.
//         lane: resolve(__dirname, "lane.html"),
//       },
//     },
//   },
// });
```

#### `tsconfig.json`

```json
// {
//   "files": [],
//   "references": [{ "path": "./tsconfig.app.json" }]
// }
```

#### `tsconfig.app.json`

```json
// {
//   "compilerOptions": {
//     "target": "ES2020",
//     "useDefineForClassFields": true,
//     "lib": ["ES2020", "DOM", "DOM.Iterable"],
//     "allowJs": false,
//     "skipLibCheck": true,
//     "esModuleInterop": true,
//     "allowSyntheticDefaultImports": true,
//     "strict": true,
//     "forceConsistentCasingInFileNames": true,
//     "module": "ESNext",
//     "moduleResolution": "Bundler",
//     "resolveJsonModule": true,
//     "isolatedModules": true,
//     "noEmit": true,
//     "jsx": "react-jsx"
//   },
//   "include": ["src"],
//   "exclude": ["src/**/*.test.ts"]
// }
```

#### `desktop.html`

```html
// <!doctype html>
// <html lang="en">
//   <head>
//     <meta charset="UTF-8" />
//     <meta name="viewport" content="width=device-width, initial-scale=1.0" />
//     <title>GeniOS</title>
//   </head>
//   <body>
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
//     <title>GeniOS lane</title>
//   </head>
//   <body>
//     <div id="root"></div>
//     <script type="module" src="/src/lane/main.tsx"></script>
//   </body>
// </html>
```

#### `index.html`

```html
// <!doctype html>
// <html lang="en">
//   <head>
//     <meta charset="UTF-8" />
//     <meta name="viewport" content="width=device-width, initial-scale=1.0" />
//     <meta
//       name="description"
//       content="A local, simulated GeniOS Executive Surface for product demonstrations."
//     />
//     <title>GeniOS Executive Surface</title>
//   </head>
//   <body>
//     <div id="root"></div>
//     <script type="module" src="/src/main.tsx"></script>
//   </body>
// </html>
```

## 2 · The GeniOS menu (main window)

Sign-in gate, Card · Goals · Pending, the Screen view and its line, Refresh, the account (sound, version), the card that drops (Drop), and how brain cards and screen follow-ups become what the menu shows.

#### `src/desktop/main.tsx`

```tsx
// import { StrictMode } from "react";
// import { createRoot } from "react-dom/client";
// import { MenuApp } from "../menu/MenuApp";
// import "./theme.css";
// import "../menu/menu.css";
//
// // The window is transparent so the menu can have round corners. Linux without a compositor
// // renders a transparent corner black, so theme.css keys off this and squares the panel there.
// function detectOs(): "macos" | "windows" | "linux" | "other" {
//   const ua = navigator.userAgent;
//   if (/Windows|Win32|Win64/i.test(ua)) return "windows";
//   if (/Mac OS X|Macintosh/i.test(ua)) return "macos";
//   if (/Linux|X11/i.test(ua)) return "linux";
//   return "other";
// }
// document.documentElement.dataset.os = detectOs();
// document.body.classList.add("genios", "genios-main");
//
// createRoot(document.getElementById("root")!).render(
//   <StrictMode>
//     <MenuApp />
//   </StrictMode>,
// );
```

#### `src/menu/MenuApp.tsx`

```tsx
// // The GeniOS menu, live: the main window of the app.
// //
// // Pending is the brain's open cards (read with the web's reader) and the screen's follow-ups (the
// // Rust core), together, most pressing first. Card is the one picked, or the one a popup's
// // "Show more" sent here. Goals are the company brief's accepted goal lines; their progress and
// // counts wait for `GET /v1/goals`. "Show sample data" in the account swaps in the agreed dummy's
// // example cards and goals, labelled as such, so every part can be seen before the brain sends it.
// //
// // A press is never silently lost: Done and Later wait three seconds with Undo, then send, and the
// // card slides away; a refusal brings the item back and says why, until the next press. A sent item
// // stays off the list for ten minutes, so a brain that has not caught up yet cannot put it back.
// //
// // Refresh (the header's ↻) checks sign-in, fetches the capture policy, starts a fresh screen reader
// // when it is not reading (a new process asks macOS about Accessibility again), and reloads
// // everything. It spins three seconds at most: the cards keep loading behind it, and one load runs
// // at a time however often Refresh, the timer and the window's focus ask. Coming back to the window
// // does the sign-in and Accessibility part on its own.
// import { useCallback, useEffect, useMemo, useRef, useState } from "react";
// import { listen } from "@tauri-apps/api/event";
// import { invoke } from "@tauri-apps/api/core";
// import { getCurrentWindow } from "@tauri-apps/api/window";
// import { getVersion } from "@tauri-apps/api/app";
// import {
//   ApiError,
//   authState,
//   captureFixAccessibility,
//   captureRefreshPolicy,
//   captureRestartReader,
//   followupDone,
//   followupSnooze,
//   followupsOpen,
//   getBriefGoals,
//   laneRecent,
//   laneSound,
//   listAgents,
//   onAuthChange,
//   openAccessibilitySettings,
//   openDashboard,
//   pressCard,
//   signOut,
//   syncNow,
//   type CardPress,
//   type Followup,
//   type OpenLoop,
//   type RecentItem,
// } from "../desktop/api";
// import { SNOOZE_LABEL } from "../desktop/ActionBar";
// import { fillDetails, loadQueue, readOpen, type DeskCard, type DetailCache } from "../desktop/cards";
// import { refusalText } from "../desktop/refusals";
// import { useCapture } from "../desktop/SetupCard";
// import { SignIn } from "../desktop/SignIn";
// import type { DropActions } from "./Drop";
// import { KIND_ICON, pendingItems } from "./live";
// import { MenuPanel, type MenuView } from "./MenuPanel";
// import { GOALS, PENDING, type DeskItem, type Goal } from "./sample";
//
// const UNDO_MS = 3000;
// /** A sent item stays off the list this long, whatever a lagging queue says. */
// const GONE_MS = 10 * 60_000;
// /** Refresh spins this long at most; a slower brain finishes behind it. */
// const REFRESH_SPIN_MS = 3000;
// const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
// const REFRESH_MS = 45_000;
// const SAMPLE_KEY = "genios.sample";
// const SOUND_KEY = "genios.sound";
//
// function loadText(key: string, fallback: string): string {
//   try {
//     return localStorage.getItem(key) ?? fallback;
//   } catch {
//     return fallback;
//   }
// }
// function saveText(key: string, value: string) {
//   try {
//     localStorage.setItem(key, value);
//   } catch {
//     /* kept for this session */
//   }
// }
//
// const hide = () => void getCurrentWindow().hide().catch(() => {});
//
// function loadFlag(key: string): boolean {
//   try {
//     return localStorage.getItem(key) === "1";
//   } catch {
//     return false;
//   }
// }
// function saveFlag(key: string, on: boolean) {
//   try {
//     localStorage.setItem(key, on ? "1" : "0");
//   } catch {
//     /* kept for this session */
//   }
// }
//
// /** A popup's item, as the lane sends it on "Show more" (the icon is a component, so it travels as the kind). */
// export type ShownItem = Omit<DeskItem, "icon">;
//
// export function MenuApp() {
//   const [connected, setConnected] = useState<boolean | null>(null);
//   const [reason, setReason] = useState<string | null>(null);
//   const [advanced, setAdvanced] = useState(false);
//   useEffect(() => {
//     authState()
//       .then((s) => setConnected(s.status === "signed_in"))
//       .catch(() => setConnected(false));
//     const un = onAuthChange((s) => {
//       if (s.status === "signed_in") setConnected(true);
//       if (s.status === "signed_out") {
//         setConnected(false);
//         setReason(s.reason);
//       }
//     });
//     return () => void un.then((f) => f());
//   }, []);
//   const signedOut = useCallback((why: string | null, openAdvanced = false) => {
//     setReason(why);
//     setAdvanced(openAdvanced);
//     setConnected(false);
//   }, []);
//
//   if (connected === null) return <div className="menu" data-tauri-drag-region />;
//   if (!connected)
//     return (
//       <SignIn
//         reason={reason}
//         advancedOpen={advanced}
//         onDone={() => {
//           setAdvanced(false);
//           setConnected(true);
//         }}
//         onClose={hide}
//       />
//     );
//   return <Live onSignedOut={signedOut} />;
// }
//
// function Live({ onSignedOut }: { onSignedOut: (why: string | null, openAdvanced?: boolean) => void }) {
//   const capture = useCapture();
//   const [view, setView] = useState<MenuView>("pending");
//   const [picked, setPicked] = useState<DeskItem | null>(null);
//   const [loops, setLoops] = useState<OpenLoop[]>([]);
//   const [cache, setCache] = useState<DetailCache>(() => new Map());
//   const cacheRef = useRef(cache);
//   const [followups, setFollowups] = useState<Followup[]>([]);
//   const [goalLines, setGoalLines] = useState<Goal[]>([]);
//   const [agents, setAgents] = useState<{ name: string; detail: string }[]>([]);
//   const [loading, setLoading] = useState(true);
//   const [notice, setNotice] = useState<string | null>(null);
//   // Off the list until (ms): Infinity while its Undo runs, then ten minutes once it was sent.
//   const [hidden, setHidden] = useState<Map<string, number>>(() => new Map());
//   const [recent, setRecent] = useState<RecentItem[]>([]);
//   const [refreshing, setRefreshing] = useState(false);
//   const [checking, setChecking] = useState(false);
//   const [flash, setFlash] = useState<string | null>(null);
//   const [sound, setSound] = useState(() => loadText(SOUND_KEY, "mac"));
//   const [version, setVersion] = useState("");
//   const [sample, setSample] = useState(() => loadFlag(SAMPLE_KEY));
//   const [silent, setSilent] = useState(false);
//   const [who, setWho] = useState<{ email: string | null; baseUrl: string }>({ email: null, baseUrl: "" });
//   const timers = useRef(new Map<string, number>());
//   const inflight = useRef<Promise<void> | null>(null);
//
//   // One load at a time: a press, the 45 s timer and the window's focus share the one running.
//   const load = useCallback((): Promise<void> => {
//     if (inflight.current) return inflight.current;
//     const run = loadOnce().finally(() => {
//       inflight.current = null;
//     });
//     inflight.current = run;
//     return run;
//     // eslint-disable-next-line react-hooks/exhaustive-deps
//   }, [onSignedOut]);
//
//   const loadOnce = async () => {
//     try {
//       const queue = await loadQueue();
//       setLoops(queue);
//       const next = await fillDetails(cacheRef.current, queue.map((l) => l.card_id));
//       cacheRef.current = next;
//       setCache(next);
//       setNotice((n) => (n?.startsWith("GeniOS could not") ? null : n));
//     } catch (e) {
//       if (e instanceof ApiError && e.status === 401) return onSignedOut(null);
//       setNotice("GeniOS could not be reached. The list tries again on its own.");
//     } finally {
//       setLoading(false);
//     }
//     followupsOpen()
//       .then(setFollowups)
//       .catch(() => {});
//     getBriefGoals()
//       .then((g) => setGoalLines(g.map((x) => ({ id: x.id, name: x.name }))))
//       .catch(() => {});
//   };
//
//   useEffect(() => {
//     void load();
//     const iv = setInterval(() => void load(), REFRESH_MS);
//     const onFocus = () => void load();
//     window.addEventListener("focus", onFocus);
//     authState()
//       .then((s) => setWho({ email: s.status === "signed_in" ? s.email : null, baseUrl: s.base_url }))
//       .catch(() => {});
//     invoke<boolean>("lane_silence", {})
//       .then(setSilent)
//       .catch(() => {});
//     // The Rust core starts on the Mac's alert sound; tell it what this person picked.
//     laneSound(loadText(SOUND_KEY, "mac"))
//       .then(setSound)
//       .catch(() => {});
//     getVersion()
//       .then(setVersion)
//       .catch(() => {});
//     listAgents()
//       .then((a) => setAgents(a.map((x) => ({ name: x.name ?? x.agent_id, detail: x.description ?? "Drafts and acts with your approval" }))))
//       .catch(() => {});
//     return () => {
//       clearInterval(iv);
//       window.removeEventListener("focus", onFocus);
//     };
//   }, [load]);
//
//   // The screen's follow-ups and this session's popups are local (no network): read them often.
//   useEffect(() => {
//     const read = () => {
//       followupsOpen()
//         .then(setFollowups)
//         .catch(() => {});
//       laneRecent()
//         .then(setRecent)
//         .catch(() => {});
//     };
//     read();
//     const iv = setInterval(read, 5000);
//     return () => clearInterval(iv);
//   }, []);
//
//   /** A fresh screen reader (it asks macOS again), then the status a moment later. */
//   const recheckReader = useCallback(async () => {
//     setChecking(true);
//     await captureRestartReader().catch(() => {});
//     setTimeout(capture.refresh, 1200);
//     setTimeout(() => {
//       capture.refresh();
//       setChecking(false);
//     }, 3000);
//   }, [capture.refresh]);
//
//   /** Fix Accessibility: GeniOS's old entry removed, macOS asked again, the pane opened. */
//   const fixAccess = useCallback(async () => {
//     setChecking(true);
//     await captureFixAccessibility().catch(() => {});
//     capture.refresh();
//     setTimeout(() => {
//       capture.refresh();
//       setChecking(false);
//     }, 2500);
//   }, [capture.refresh]);
//
//   // Back in the window (from the browser, from System Settings): is this Mac still signed in, and
//   // was Accessibility just allowed?
//   const stateRef = useRef(capture.status?.state);
//   stateRef.current = capture.status?.state;
//   useEffect(() => {
//     const onBack = () => {
//       if (document.visibilityState === "hidden") return;
//       authState()
//         .then((s) => s.status === "signed_out" && onSignedOut(s.reason))
//         .catch(() => {});
//       if (stateRef.current === "needs_accessibility" || stateRef.current === "sidecar_unavailable") void recheckReader();
//     };
//     window.addEventListener("focus", onBack);
//     document.addEventListener("visibilitychange", onBack);
//     return () => {
//       window.removeEventListener("focus", onBack);
//       document.removeEventListener("visibilitychange", onBack);
//     };
//   }, [onSignedOut, recheckReader]);
//
//   const refreshAll = async () => {
//     setRefreshing(true);
//     setNotice(null);
//     try {
//       const s = await authState().catch(() => null);
//       if (s?.status === "signed_out") return onSignedOut(s.reason);
//       if (s) setWho({ email: s.status === "signed_in" ? s.email : null, baseUrl: s.base_url });
//       await captureRefreshPolicy().catch(() => {});
//       const st = stateRef.current;
//       if (st && st !== "capturing" && st !== "paused" && st !== "off_by_policy") void recheckReader();
//       const [f, r, quiet] = await Promise.allSettled([followupsOpen(), laneRecent(), invoke<boolean>("lane_silence", {})]);
//       if (f.status === "fulfilled") setFollowups(f.value);
//       if (r.status === "fulfilled") setRecent(r.value);
//       if (quiet.status === "fulfilled") setSilent(quiet.value);
//       capture.refresh();
//       const cardsIn = await Promise.race([load().then(() => true), wait(REFRESH_SPIN_MS).then(() => false)]);
//       const at = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
//       setFlash(cardsIn ? `Refreshed · ${at}` : `Refreshed · ${at} · cards are still coming in`);
//       setTimeout(() => setFlash(null), 3000);
//     } finally {
//       setRefreshing(false);
//     }
//   };
//
//   // A popup's "Show more": open that item in the Card view.
//   useEffect(() => {
//     const un = listen<ShownItem>("genios://show", (e) => {
//       setPicked({ ...e.payload, icon: KIND_ICON[e.payload.kind] ?? KIND_ICON.Decision });
//       setView("card");
//     });
//     return () => void un.then((f) => f());
//   }, []);
//
//   // Esc closes the menu (a layer that is open takes its own Esc first).
//   useEffect(() => {
//     const onKey = (e: KeyboardEvent) => {
//       if (e.key === "Escape" && !e.defaultPrevented) hide();
//     };
//     window.addEventListener("keydown", onKey);
//     return () => window.removeEventListener("keydown", onKey);
//   }, []);
//
//   const cards = useMemo(() => readOpen(loops, cache), [loops, cache]);
//   const cardsById = useMemo(() => new Map(cards.map((c) => [c.id, c])), [cards]);
//   const followupsById = useMemo(() => new Map(followups.map((f) => [f.id, f])), [followups]);
//   const pending = useMemo(
//     () => (sample ? PENDING : pendingItems(cards, followups)).filter((i) => !((hidden.get(i.id) ?? 0) > Date.now())),
//     [sample, cards, followups, hidden],
//   );
//   const goals = sample ? GOALS : goalLines;
//
//   const hideUntil = (id: string, until: number) => setHidden((h) => new Map(h).set(id, until));
//   const unhide = (id: string) =>
//     setHidden((h) => {
//       const n = new Map(h);
//       n.delete(id);
//       return n;
//     });
//
//   const refuse = (label: string, e: unknown) => {
//     if (e instanceof ApiError && e.status === 401) return onSignedOut(null);
//     setNotice(`“${label}”: ${refusalText(e instanceof ApiError ? e.status : 0, e instanceof ApiError ? e.message : "offline")}`);
//   };
//
//   /** Off the list now; sent in three seconds unless Undo; a refusal brings it back and says why. */
//   const later = (id: string, label: string, note: string, send: () => Promise<unknown>): string => {
//     setNotice(null);
//     hideUntil(id, Infinity);
//     const t = window.setTimeout(async () => {
//       timers.current.delete(id);
//       try {
//         await send();
//         hideUntil(id, Date.now() + GONE_MS);
//       } catch (e) {
//         refuse(label, e);
//         unhide(id);
//       }
//       void load();
//     }, UNDO_MS);
//     timers.current.set(id, t);
//     return note;
//   };
//   const undo = (id: string) => () => {
//     const t = timers.current.get(id);
//     if (t) clearTimeout(t);
//     timers.current.delete(id);
//     unhide(id);
//   };
//   /** Sent at once (an answer, feedback): nothing to undo. */
//   const now = (label: string, send: () => Promise<unknown>) => {
//     setNotice(null);
//     send()
//       .catch((e) => refuse(label, e))
//       .finally(() => void load());
//   };
//
//   const delegate = { people: [] as { name: string; detail: string }[], agents };
//
//   const actionsFor = (item: DeskItem): DropActions | null => {
//     if (sample)
//       return {
//         primary: () => "Marked done · sample, nothing was sent",
//         later: { options: [{ id: "4h", label: "In 4 hours" }, { id: "tomorrow_09", label: "Tomorrow, 9:00" }, { id: "3d", label: "In 3 days" }], pick: true, onPick: () => "Put off · sample, nothing was sent" },
//         feedback: { reasons: [{ id: "not_relevant", label: "Not relevant to me" }, { id: "wrong_facts", label: "A fact is wrong" }, { id: "bad_timing", label: "Right card, wrong time" }], onSend: () => "Feedback noted · sample, nothing was sent" },
//         answer: item.kind === "Question" ? () => "Answer noted · sample, nothing was sent" : undefined,
//         delegate: { people: [{ name: "Harsh", detail: "harsh@example.com · admin" }], agents: [{ name: "Inbox agent", detail: "Drafts the reply; sends after you approve" }] },
//       };
//     const card: DeskCard | undefined = cardsById.get(item.id);
//     if (card) {
//       const asks = card.lane === "question" && !card.answered;
//       const press = (p: CardPress) => () => pressCard(card.id, p);
//       return {
//         primary: card.offers.done && !asks ? () => later(card.id, card.headline, "Marked done", press({ action: "do_it_myself" })) : undefined,
//         later: card.offers.snooze.length
//           ? {
//               options: card.offers.snooze.map((o) => ({ id: o, label: SNOOZE_LABEL[o] ?? o })),
//               pick: true,
//               onPick: (id, until) =>
//                 later(
//                   card.id,
//                   card.headline,
//                   `Put off · ${until ? new Date(until).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" }) + ", 9:00" : (SNOOZE_LABEL[id] ?? id)}`,
//                   press({ action: "snooze", snooze: id, until }),
//                 ),
//             }
//           : undefined,
//         feedback: card.answered
//           ? null
//           : {
//               reasons: card.offers.wrong.flatMap((g) => g.reasons.map((r) => ({ id: r.value, label: r.label }))),
//               onSend: (reason, words) => {
//                 now(card.headline, press({ action: "wrong", reason, words, scope: "file" }));
//                 return "Feedback sent · GeniOS reads it the next time it reviews this thread";
//               },
//             },
//         feedbackLockedWhy: "Your answer is in. Feedback opens again when the thread is read.",
//         answer:
//           asks && card.offers.answer
//             ? (words) => {
//                 now(card.headline, press({ action: "answer", words }));
//                 return "Answer sent · GeniOS reads the thread again with it";
//               }
//             : undefined,
//         delegate,
//         undo: undo(card.id),
//       };
//     }
//     const f = followupsById.get(item.id);
//     if (f)
//       return {
//         primary: () => later(f.id, f.text, "Done", () => followupDone(f.id)),
//         later: {
//           options: [
//             { id: "1h", label: "In 1 hour" },
//             { id: "tonight", label: "Tonight" },
//             { id: "tomorrow", label: "Tomorrow" },
//           ],
//           onPick: (id) => later(f.id, f.text, `Reminding you ${id === "1h" ? "in an hour" : id}`, () => followupSnooze(f.id, id as "1h" | "tonight" | "tomorrow")),
//         },
//         feedback: null,
//         feedbackLockedWhy: "Feedback on a screen item comes with the next update. Rate its popup in the toast.",
//         delegate,
//         undo: undo(f.id),
//       };
//     // An item a popup sent that is not (or no longer) on the list: its buttons were in the popup.
//     return null;
//   };
//
//   // A pressed card keeps its buttons while its note and Undo show and it slides away, even once
//   // the send went through and the reloaded list no longer has it.
//   const shown = useRef<{ id: string; actions: DropActions } | null>(null);
//   let pickedActions = picked ? actionsFor(picked) : null;
//   if (picked && !pickedActions && shown.current?.id === picked.id && hidden.has(picked.id)) pickedActions = shown.current.actions;
//   if (picked && pickedActions) shown.current = { id: picked.id, actions: pickedActions };
//
//   const status = capture.status;
//   return (
//     <MenuPanel
//       view={view}
//       onView={setView}
//       item={picked}
//       actions={pickedActions}
//       goals={goals}
//       pending={pending}
//       loading={loading && !sample}
//       notice={notice}
//       flash={flash}
//       refreshing={refreshing}
//       onRefresh={() => void refreshAll()}
//       sample={sample}
//       onPick={(it) => {
//         setPicked(it);
//         setView("card");
//       }}
//       onClose={hide}
//       onCloseCard={() => {
//         setPicked(null);
//         setView("pending");
//       }}
//       screen={{
//         status,
//         recent,
//         followups: followups.length,
//         checking,
//         onPause: () => void capture.pause(15),
//         onResume: () => void capture.resume(),
//         onAccessibility: () => void openAccessibilitySettings().catch(() => {}),
//         onCheckAgain: () => void recheckReader(),
//         onFix: () => void fixAccess(),
//         onSync: () => void syncNow().then(capture.refresh, () => {}),
//         onTurnOn: () => void openDashboard("/dashboard/settings?section=capture").catch(() => {}),
//       }}
//       account={{
//         email: who.email,
//         baseUrl: who.baseUrl,
//         version,
//         sound,
//         onSound: (choice) => {
//           setSound(choice);
//           saveText(SOUND_KEY, choice);
//           laneSound(choice, true)
//             .then(setSound)
//             .catch(() => {});
//         },
//         capture: status,
//         silent,
//         sample,
//         onPause: () => void capture.pause(15),
//         onResume: () => void capture.resume(),
//         onAccessibility: () => void openAccessibilitySettings().catch(() => {}),
//         onSilent: (on) => {
//           setSilent(on);
//           invoke<boolean>("lane_silence", { on })
//             .then(setSilent)
//             .catch(() => {});
//         },
//         onSample: (on) => {
//           setSample(on);
//           saveFlag(SAMPLE_KEY, on);
//           setPicked(null);
//         },
//         onTools: () => void openDashboard("/dashboard/integrations").catch(() => {}),
//         onOpenWeb: () => void openDashboard("/dashboard/cards").catch(() => {}),
//         onSignInAgain: () => void signOut().finally(() => onSignedOut(null)),
//         onChangeServer: () => void signOut().finally(() => onSignedOut(null, true)),
//         onSignOut: () => void signOut().finally(() => onSignedOut(null)),
//       }}
//     />
//   );
// }
```

#### `src/menu/MenuPanel.tsx`

```tsx
// // The GeniOS menu (the main window). Close on the left; Card · Goals · Pending and the account on
// // the right. Card is the card that dropped (or the one picked), with why it came up and its approach,
// // goal and importance; Goals are the active goals, numbered, with their counts and their cards;
// // Pending is everything left today, screen and tools together, numbered, most pressing first.
// // Under the header, always, one line says whether GeniOS is reading the screen and what it read
// // last; it opens Screen: what it is reading, what it noticed, how it works, and Accessibility.
// import { useEffect, useRef, useState } from "react";
// import { BellOff, ChevronDown, ChevronRight, ChevronUp, FlaskConical, Globe, Laptop, LogOut, Monitor, Plug, RefreshCw, Target, Volume2, X } from "lucide-react";
// import { budgetLine, catchingUpLine, type CaptureStatus, type RecentItem } from "../desktop/api";
// import { Popover, Status, Tabs } from "../desktop/ui";
// import { Drop, type DropActions } from "./Drop";
// import type { DeskItem, Goal } from "./sample";
//
// export type MenuView = "card" | "goals" | "pending" | "screen";
//
// export type ScreenInfo = {
//   status: CaptureStatus | null;
//   /** Popups shown this session, newest first: one that came and went is still here. */
//   recent: RecentItem[];
//   followups: number;
//   checking: boolean;
//   onPause: () => void;
//   onResume: () => void;
//   onAccessibility: () => void;
//   /** A fresh reader asks macOS again (after Accessibility was changed in Settings). */
//   onCheckAgain: () => void;
//   /** Removes GeniOS's Accessibility entry (an older build's), asks macOS again, opens Settings. */
//   onFix: () => void;
//   onSync: () => void;
//   onTurnOn: () => void;
// };
//
// /** The account's "Popup sound" choices, as the Rust core names them. */
// export const SOUNDS = [
//   { id: "mac", label: "Mac alert sound" },
//   { id: "Glass", label: "Glass" },
//   { id: "Pop", label: "Pop" },
//   { id: "Ping", label: "Ping" },
//   { id: "Purr", label: "Purr" },
//   { id: "off", label: "Off" },
// ];
//
// export type AccountInfo = {
//   email: string | null;
//   baseUrl: string;
//   /** This app's version, so an install can be checked at a glance. */
//   version: string;
//   sound: string;
//   onSound: (choice: string) => void;
//   capture: CaptureStatus | null;
//   silent: boolean;
//   sample: boolean;
//   onPause: () => void;
//   onResume: () => void;
//   onAccessibility: () => void;
//   onSilent: (on: boolean) => void;
//   onSample: (on: boolean) => void;
//   onTools: () => void;
//   onOpenWeb: () => void;
//   onSignInAgain: () => void;
//   onChangeServer: () => void;
//   onSignOut: () => void;
// };
//
// const IMPORTANCE = { Now: "Today", High: "This week", Normal: "Any time" } as const;
//
// function CardView({ item, actions, onClose, onGone }: { item: DeskItem | null; actions: DropActions | null; onClose: () => void; onGone: () => void }) {
//   if (!item || !actions)
//     return (
//       <div className="m-empty">
//         <h3>Nothing open</h3>
//         <p>Pick one from Pending, or wait for the next card to drop.</p>
//       </div>
//     );
//   const q = item.quote;
//   return (
//     <div className="m-card" aria-label="Card">
//       <Drop key={item.id} item={item} actions={actions} variant="menu" onClose={onClose} onGone={onGone} />
//       {q && (
//         <section className="m-why" aria-label="Why it came up">
//           <span className="m-label">Why it came up</span>
//           <p className="m-where">{[q.where, q.when].filter(Boolean).join(" · ")}</p>
//           <p className="m-said">
//             <span>{q.said}</span>“{q.text}”
//           </p>
//           {q.caught && <p className="m-caught">{q.caught}</p>}
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
//           <p>{IMPORTANCE[item.importance]}</p>
//         </div>
//       </div>
//     </div>
//   );
// }
//
// function GoalCard({ n, goal, cards, onPick }: { n: number; goal: Goal; cards: DeskItem[]; onPick: (item: DeskItem) => void }) {
//   const [open, setOpen] = useState(false);
//   const measured = goal.progress !== undefined;
//   return (
//     <article className="m-goal" aria-label={goal.name}>
//       <div className="m-goal-head">
//         <span className="m-num">{n}</span>
//         <div>
//           <h3>{goal.name}</h3>
//           {measured && (
//             <p className="m-goal-by">
//               {goal.progress}% done{goal.by ? ` · ${goal.by}` : ""}
//             </p>
//           )}
//         </div>
//         {goal.status && <Status tone={goal.status === "On track" ? "ink" : "accent"}>{goal.status}</Status>}
//       </div>
//       {measured ? (
//         <span className="m-goal-bar">
//           <span style={{ width: `${goal.progress}%` }} />
//         </span>
//       ) : (
//         <p className="m-goal-meaning">Progress, due date and counts show here when the brain serves goals.</p>
//       )}
//       {goal.now && <p className="m-goal-now">{goal.now}</p>}
//       {goal.funnel && (
//         <div className="m-funnel" aria-label="The count">
//           {goal.funnel.map((f) => (
//             <div key={f.label} className="m-step">
//               <b>{f.value}</b>
//               <span className="m-step-label">{f.label}</span>
//               <span className="m-step-bar">
//                 <span style={{ width: `${Math.max(f.share * 100, f.share > 0 ? 3 : 0)}%` }} />
//               </span>
//               <span className="m-step-note">{f.note ?? ""}</span>
//             </div>
//           ))}
//         </div>
//       )}
//       {goal.meaning && <p className="m-goal-meaning">{goal.meaning}</p>}
//       <button type="button" className="m-goal-cards" aria-expanded={open} onClick={() => setOpen((o) => !o)} disabled={cards.length === 0}>
//         <Target size={14} strokeWidth={2} aria-hidden />
//         {cards.length ? `${cards.length} card${cards.length === 1 ? "" : "s"} for this goal` : "No card is linked to this goal yet"}
//         {cards.length > 0 && <ChevronDown className="dx-chev" size={14} strokeWidth={2} aria-hidden />}
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
// function PendingView({ items, loading, onPick }: { items: DeskItem[]; loading: boolean; onPick: (item: DeskItem) => void }) {
//   if (!items.length)
//     return (
//       <div className="m-empty">
//         <h3>{loading ? "Reading your cards…" : "Nothing needs you right now"}</h3>
//         {!loading && <p>When GeniOS finds something that needs you, it drops in at the top right and waits here.</p>}
//       </div>
//     );
//   return (
//     <ol className="m-pending" aria-label="Pending">
//       {items.map((item, i) => (
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
//               {item.why && <span className="m-row-why">{item.why}</span>}
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
// function reading(c: CaptureStatus | null): { text: string; sub: string; action?: "pause" | "resume" | "settings" } {
//   if (!c || c.state === "unsupported") return { text: "Not available on this computer", sub: "Screen reading runs on macOS" };
//   switch (c.state) {
//     case "capturing":
//       return { text: c.last_thread_title ? `Reading · ${c.last_thread_title}` : "Watching your work apps", sub: "Accessibility allowed · on for your seat", action: "pause" };
//     case "paused":
//       return {
//         text: `Paused until ${c.paused_until ? new Date(c.paused_until).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "later"}`,
//         sub: "Nothing is read while paused",
//         action: "resume",
//       };
//     case "idle":
//       return { text: "Idle", sub: "Nothing is read while you're away", action: "pause" };
//     case "needs_accessibility":
//       return { text: "Needs Accessibility", sub: c.detail || "Allow it so GeniOS can read the app you're in", action: "settings" };
//     case "off_by_policy":
//       return { text: "Off for your seat", sub: "Turn it on at the website: Settings › My capture" };
//     case "update_required":
//       return { text: "Update GeniOS to keep reading", sub: c.detail || "" };
//     case "sidecar_unavailable":
//       return { text: "The reading helper is not running", sub: "Quit and open GeniOS again" };
//     default:
//       return { text: "Starting…", sub: "" };
//   }
// }
//
// function useNow(ms: number) {
//   const [now, setNow] = useState(Date.now());
//   useEffect(() => {
//     const iv = setInterval(() => setNow(Date.now()), ms);
//     return () => clearInterval(iv);
//   }, [ms]);
//   return now;
// }
//
// function ago(iso: string | null | undefined, now: number): string {
//   const t = iso ? Date.parse(iso) : NaN;
//   if (Number.isNaN(t)) return "";
//   const s = Math.max(0, Math.round((now - t) / 1000));
//   if (s < 10) return "just now";
//   if (s < 60) return `${s} s ago`;
//   if (s < 3600) return `${Math.round(s / 60)} min ago`;
//   if (s < 86_400) return `${Math.round(s / 3600)} h ago`;
//   return new Date(t).toLocaleDateString([], { day: "numeric", month: "short" });
// }
//
// const clock = (iso: string | null | undefined) =>
//   iso ? new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "later";
//
// type Tone = "on" | "warn" | "off";
//
// /** The one line under the header. */
// function stripOf(c: CaptureStatus | null): { tone: Tone; text: string } | null {
//   if (!c) return { tone: "off", text: "Checking screen reading…" };
//   switch (c.state) {
//     case "capturing":
//       return { tone: "on", text: c.last_thread_title ? `Reading your screen · ${c.last_thread_title}` : "Reading your screen" };
//     case "starting":
//       return { tone: "off", text: "Screen reading is starting…" };
//     case "idle":
//       return { tone: "off", text: "Screen reading waits · you're away or locked" };
//     case "paused":
//       return { tone: "off", text: `Screen reading paused until ${clock(c.paused_until)}` };
//     case "needs_accessibility":
//       return { tone: "warn", text: "Not reading your screen · fix Accessibility" };
//     case "off_by_policy":
//       return { tone: "off", text: "Screen reading is off for your seat" };
//     case "sidecar_unavailable":
//       return { tone: "warn", text: "The screen reader stopped · restart it" };
//     case "update_required":
//       return { tone: "warn", text: "Update GeniOS to keep reading" };
//     default:
//       return null;
//   }
// }
//
// /** The line under the header. Pressed, it opens Screen; with Screen open it stays on top as
//  *  Minimize, and pressing it again goes back to the view it came from. */
// function ScreenStrip({ c, open = false, onPress }: { c: CaptureStatus | null; open?: boolean; onPress: () => void }) {
//   const now = useNow(5000);
//   const s = stripOf(c);
//   if (!s) return null;
//   const when = c?.state === "capturing" ? ago(c.last_captured_at, now) : "";
//   return (
//     <button
//       type="button"
//       className={`m-strip ${s.tone}${open ? " open" : ""}`}
//       onClick={onPress}
//       aria-expanded={open}
//       aria-label={open ? "Minimize screen reading" : "Screen reading: details"}
//     >
//       <i aria-hidden />
//       <span className="m-strip-text">{s.text}</span>
//       {open ? (
//         <span className="m-strip-min">
//           Minimize <ChevronUp size={14} strokeWidth={2} aria-hidden />
//         </span>
//       ) : (
//         <>
//           {when && <span className="m-strip-when">{when}</span>}
//           <ChevronRight size={14} strokeWidth={2} aria-hidden />
//         </>
//       )}
//     </button>
//   );
// }
//
// /** Screen: everything about screen reading, in one place. */
// function ScreenView({ s }: { s: ScreenInfo }) {
//   const now = useNow(5000);
//   const c = s.status;
//   const state = c?.state ?? "starting";
//   const head: { title: string; sub: string } = (() => {
//     switch (state) {
//       case "capturing":
//         return { title: "Reading your screen", sub: "Accessibility is allowed. GeniOS reads the app in front of you as you work." };
//       case "needs_accessibility":
//         return {
//           title: "Not reading · Accessibility is off",
//           sub: "If Settings already shows GeniOS switched on, that entry was made for an older GeniOS, and macOS refuses this one. Fix Accessibility removes it and asks again.",
//         };
//       case "paused":
//         return { title: `Paused until ${clock(c?.paused_until)}`, sub: "Nothing is read while paused." };
//       case "idle":
//         return { title: "Waiting for you", sub: "You're away or the screen is locked, so nothing is read. It starts again when you're back." };
//       case "off_by_policy":
//         return { title: "Off for your seat", sub: "Turn it on at the website: Settings › My capture." };
//       case "sidecar_unavailable":
//         return { title: "The screen reader stopped", sub: "Press Restart reader. If it stays stopped, quit GeniOS and open it again." };
//       case "update_required":
//         return { title: "Update GeniOS to keep reading", sub: c?.detail || "This version is too old for your GeniOS server." };
//       case "unsupported":
//         return { title: "Not available on this computer", sub: "Screen reading runs on macOS." };
//       default:
//         return { title: "Starting…", sub: "Asking macOS for the app in front of you." };
//     }
//   })();
//   const tone: Tone = state === "capturing" ? "on" : ["needs_accessibility", "sidecar_unavailable", "update_required"].includes(state) ? "warn" : "off";
//   const allowed = c ? c.state !== "needs_accessibility" && c.state !== "unsupported" : false;
//   const notes = [c?.reader_health?.trim(), budgetLine(c?.insight_budget), catchingUpLine(c?.catching_up)].filter(Boolean) as string[];
//   const queue = c?.queue_depth ?? 0;
//   const b = c?.insight_budget;
//
//   // Not allowed yet: the steps come right under the status, not at the bottom.
//   const access = (
//     <section className="m-scr-sec" aria-label="Accessibility">
//       <span className="m-label">Accessibility</span>
//       {allowed ? (
//         <p className="m-scr-ok">Allowed on this Mac. You can change it in System Settings › Privacy &amp; Security › Accessibility.</p>
//       ) : (
//         <ol className="m-scr-steps">
//           <li>Press Fix Accessibility. GeniOS removes its old entry, macOS asks again, and Settings opens at Privacy &amp; Security › Accessibility.</li>
//           <li>Switch GeniOS on in that list. If macOS shows its own window first, press Open System Settings there.</li>
//           <li>Come back here. It starts reading within a few seconds; or press Check again.</li>
//         </ol>
//       )}
//     </section>
//   );
//
//   return (
//     <div className="m-scr" aria-label="Screen reading">
//       <section className={`m-scr-head ${tone}`}>
//         <div className="m-scr-title">
//           <i aria-hidden />
//           <h3>{head.title}</h3>
//         </div>
//         <p>{head.sub}</p>
//         <div className="m-scr-btns">
//           {state === "needs_accessibility" && (
//             <>
//               <button type="button" className="m-solid" disabled={s.checking} onClick={s.onFix}>
//                 {s.checking ? "Asking macOS…" : "Fix Accessibility"}
//               </button>
//               <button type="button" className="m-link" disabled={s.checking} onClick={s.onCheckAgain}>
//                 Check again
//               </button>
//             </>
//           )}
//           {(state === "capturing" || state === "idle" || state === "starting") && (
//             <>
//               <button type="button" className="m-solid" onClick={s.onPause}>
//                 Pause 15 min
//               </button>
//               <button type="button" className="m-link" disabled={s.checking} onClick={s.onCheckAgain}>
//                 {s.checking ? "Restarting…" : "Restart reader"}
//               </button>
//             </>
//           )}
//           {state === "paused" && (
//             <button type="button" className="m-solid" onClick={s.onResume}>
//               Resume now
//             </button>
//           )}
//           {state === "sidecar_unavailable" && (
//             <button type="button" className="m-solid" disabled={s.checking} onClick={s.onCheckAgain}>
//               {s.checking ? "Restarting…" : "Restart reader"}
//             </button>
//           )}
//           {state === "off_by_policy" && (
//             <button type="button" className="m-solid" onClick={s.onTurnOn}>
//               Turn on at the website
//             </button>
//           )}
//         </div>
//       </section>
//       {!allowed && access}
//
//       <section className="m-facts" aria-label="Right now">
//         <div>
//           <span className="m-label">Reading</span>
//           <p title={c?.last_thread_title ?? undefined}>{c?.last_thread_title || (allowed ? "Nothing yet · open a chat, email or doc" : "Nothing · not allowed yet")}</p>
//         </div>
//         <div>
//           <span className="m-label">Last read</span>
//           <p>{ago(c?.last_captured_at, now) || "Not yet"}</p>
//         </div>
//         <div>
//           <span className="m-label">To send</span>
//           <p>
//             {queue > 0 ? `${queue} waiting` : "All sent"}
//             {queue > 0 && (
//               <button type="button" className="m-link" onClick={s.onSync}>
//                 Send now
//               </button>
//             )}
//           </p>
//         </div>
//         <div>
//           <span className="m-label">Found</span>
//           <p>
//             {s.recent.length} popup{s.recent.length === 1 ? "" : "s"} · {s.followups} follow-up{s.followups === 1 ? "" : "s"} open
//           </p>
//         </div>
//         {b && typeof b.used === "number" && typeof b.cap === "number" && b.cap > 0 && (
//           <div>
//             <span className="m-label">AI checks</span>
//             <p>
//               {b.used} of {b.cap} today
//             </p>
//           </div>
//         )}
//       </section>
//       {notes.map((n) => (
//         <p key={n} className="menu-notice">
//           {n}
//         </p>
//       ))}
//
//       <section className="m-scr-sec" aria-label="What it noticed">
//         <span className="m-label">What it noticed · this session</span>
//         {s.recent.length ? (
//           <ul className="m-scr-list">
//             {s.recent.slice(0, 8).map((r) => (
//               <li key={r.id}>
//                 <b>{r.headline}</b>
//                 <small>{[r.app, r.who, ago(r.at, now)].filter(Boolean).join(" · ")}</small>
//               </li>
//             ))}
//           </ul>
//         ) : (
//           <p className="m-scr-none">Nothing yet. Every popup that comes and goes is kept here.</p>
//         )}
//       </section>
//
//       <section className="m-scr-sec" aria-label="How it works">
//         <span className="m-label">How it works</span>
//         <ol className="m-scr-steps">
//           <li>It reads the words in the app in front of you: chats, email, documents and websites. It never takes a picture of your screen.</li>
//           <li>It skips what is private: password managers, Terminal and code editors, banking and payment sites, private windows. Nothing is read while paused, away or locked.</li>
//           <li>What it read goes to your GeniOS, which looks for promises, asks, deadlines and risks.</li>
//           <li>When something needs you, a card drops for five seconds. Follow-ups wait in Pending; the popups are listed above.</li>
//         </ol>
//       </section>
//
//       {allowed && access}
//     </div>
//   );
// }
//
// function Account({ a }: { a: AccountInfo }) {
//   const [open, setOpen] = useState(false);
//   const [confirm, setConfirm] = useState<"signout" | "again" | "server" | null>(null);
//   const close = () => {
//     setOpen(false);
//     setConfirm(null);
//   };
//   const r = reading(a.capture);
//   const initial = (a.email ?? "G").charAt(0).toUpperCase();
//   const name = a.email ? a.email.split("@")[0].replace(/[._-]+/g, " ").replace(/\b\w/g, (m) => m.toUpperCase()) : "Signed in";
//   const ask = (what: "signout" | "again" | "server") => setConfirm(what);
//   const run = (f: () => void) => () => {
//     close();
//     f();
//   };
//   return (
//     <Popover
//       label="Account"
//       open={open}
//       onClose={close}
//       trigger={
//         <button type="button" className="m-avatar" aria-label="Account" aria-expanded={open} onClick={() => (open ? close() : setOpen(true))}>
//           {initial}
//         </button>
//       }
//     >
//       <div className="m-acc">
//         <div className="m-acc-head">
//           <span className="m-avatar big">{initial}</span>
//           <div>
//             <b>{name}</b>
//             <span>{a.email ?? "—"}</span>
//             <span>Signed in on this Mac{a.version ? ` · GeniOS ${a.version}` : ""}</span>
//           </div>
//         </div>
//
//         {confirm ? (
//           <div className="m-acc-sec m-confirm">
//             <p>
//               {confirm === "signout"
//                 ? "Sign out of this Mac? GeniOS stops reading your screen here and deletes what it kept on this Mac."
//                 : confirm === "again"
//                   ? "Sign in again with a new device code? This Mac signs out first; you approve the new code on the website."
//                   : "Change the server? This Mac signs out first; set the address under Advanced on the sign-in screen."}
//             </p>
//             <div>
//               <button type="button" className="m-link" onClick={() => setConfirm(null)}>
//                 Cancel
//               </button>
//               <button
//                 type="button"
//                 className="m-solid"
//                 onClick={run(confirm === "signout" ? a.onSignOut : confirm === "again" ? a.onSignInAgain : a.onChangeServer)}
//               >
//                 {confirm === "signout" ? "Sign out" : "Continue"}
//               </button>
//             </div>
//           </div>
//         ) : (
//           <>
//             <div className="m-acc-sec">
//               <span className="m-label">This Mac</span>
//               <div className="m-acc-row">
//                 <Laptop size={15} strokeWidth={2} aria-hidden />
//                 <span>
//                   Signed in with a device code
//                   <small>Approved on the GeniOS website</small>
//                 </span>
//                 <button type="button" className="m-link" onClick={() => ask("again")}>
//                   New code
//                 </button>
//               </div>
//             </div>
//
//             <div className="m-acc-sec">
//               <span className="m-label">Screen reading</span>
//               <div className="m-acc-row">
//                 <Monitor size={15} strokeWidth={2} aria-hidden />
//                 <span>
//                   {r.text}
//                   <small>{r.sub}</small>
//                 </span>
//                 {r.action === "pause" && (
//                   <button type="button" className="m-link" onClick={a.onPause}>
//                     Pause
//                   </button>
//                 )}
//                 {r.action === "resume" && (
//                   <button type="button" className="m-link" onClick={a.onResume}>
//                     Resume
//                   </button>
//                 )}
//                 {r.action === "settings" && (
//                   <button type="button" className="m-link" onClick={a.onAccessibility}>
//                     Open settings
//                   </button>
//                 )}
//               </div>
//               <div className="m-acc-row">
//                 <Volume2 size={15} strokeWidth={2} aria-hidden />
//                 <span>
//                   Popup sound
//                   <small>Plays once when a popup drops</small>
//                 </span>
//                 <select className="m-select" aria-label="Popup sound" value={a.sound} onChange={(e) => a.onSound(e.target.value)}>
//                   {SOUNDS.map((s) => (
//                     <option key={s.id} value={s.id}>
//                       {s.label}
//                     </option>
//                   ))}
//                 </select>
//               </div>
//               <div className="m-acc-row">
//                 <BellOff size={15} strokeWidth={2} aria-hidden />
//                 <span>Silence popups</span>
//                 <button
//                   type="button"
//                   className={`m-switch${a.silent ? " on" : ""}`}
//                   role="switch"
//                   aria-checked={a.silent}
//                   aria-label="Silence popups"
//                   onClick={() => a.onSilent(!a.silent)}
//                 >
//                   <i />
//                 </button>
//               </div>
//             </div>
//
//             <div className="m-acc-sec">
//               <span className="m-label">Connected tools</span>
//               <div className="m-acc-row">
//                 <Plug size={15} strokeWidth={2} aria-hidden />
//                 <span>
//                   Gmail, Calendar and the rest
//                   <small>Connected and managed on the website</small>
//                 </span>
//                 <button type="button" className="m-link" onClick={a.onTools}>
//                   Manage
//                 </button>
//               </div>
//             </div>
//
//             <div className="m-acc-sec">
//               <span className="m-label">Server &amp; API</span>
//               <div className="m-acc-row">
//                 <Globe size={15} strokeWidth={2} aria-hidden />
//                 <span>
//                   {a.baseUrl.replace(/^https?:\/\//, "")}
//                   <small>Signed requests from this Mac</small>
//                 </span>
//                 <button type="button" className="m-link" onClick={() => ask("server")}>
//                   Change
//                 </button>
//               </div>
//             </div>
//
//             <div className="m-acc-sec">
//               <div className="m-acc-row">
//                 <FlaskConical size={15} strokeWidth={2} aria-hidden />
//                 <span>
//                   Show sample data
//                   <small>See every part with example cards and goals</small>
//                 </span>
//                 <button
//                   type="button"
//                   className={`m-switch${a.sample ? " on" : ""}`}
//                   role="switch"
//                   aria-checked={a.sample}
//                   aria-label="Show sample data"
//                   onClick={() => a.onSample(!a.sample)}
//                 >
//                   <i />
//                 </button>
//               </div>
//             </div>
//
//             <div className="m-acc-foot">
//               <button type="button" className="m-link" onClick={run(a.onOpenWeb)}>
//                 <Globe size={14} strokeWidth={2} aria-hidden /> Open GeniOS on the web
//               </button>
//               <button type="button" className="m-link" onClick={() => ask("signout")}>
//                 <LogOut size={14} strokeWidth={2} aria-hidden /> Sign out
//               </button>
//             </div>
//           </>
//         )}
//       </div>
//     </Popover>
//   );
// }
//
// export function MenuPanel({
//   view,
//   onView,
//   item,
//   actions,
//   goals,
//   pending,
//   loading,
//   notice,
//   flash,
//   refreshing,
//   sample,
//   account,
//   screen,
//   onPick,
//   onClose,
//   onCloseCard,
//   onRefresh,
// }: {
//   view: MenuView;
//   onView: (v: MenuView) => void;
//   item: DeskItem | null;
//   actions: DropActions | null;
//   goals: Goal[];
//   pending: DeskItem[];
//   loading: boolean;
//   notice: string | null;
//   /** A passing line, e.g. "Refreshed · 10:42 pm". */
//   flash: string | null;
//   refreshing: boolean;
//   sample: boolean;
//   account: AccountInfo;
//   screen: ScreenInfo;
//   onPick: (item: DeskItem) => void;
//   onClose: () => void;
//   onCloseCard: () => void;
//   onRefresh: () => void;
// }) {
//   // Where Minimize goes back to: the view Screen was opened from.
//   const back = useRef<MenuView>("pending");
//   const openScreen = () => {
//     back.current = view === "screen" ? back.current : view;
//     onView("screen");
//   };
//   return (
//     <section className="menu" aria-label="GeniOS menu" data-tauri-drag-region>
//       <header className="menu-head" data-tauri-drag-region>
//         <button type="button" className="m-close" aria-label="Close" onClick={onClose}>
//           <X size={16} strokeWidth={2} />
//         </button>
//         <button
//           type="button"
//           className={`m-refresh${refreshing ? " spin" : ""}`}
//           aria-label="Refresh"
//           title="Refresh: sign-in, screen reading and your cards"
//           disabled={refreshing}
//           onClick={onRefresh}
//         >
//           <RefreshCw size={15} strokeWidth={2} />
//         </button>
//         <span className="menu-fill" data-tauri-drag-region />
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
//         <Account a={account} />
//       </header>
//       {view === "screen" ? (
//         <ScreenStrip c={screen.status} open onPress={() => onView(back.current)} />
//       ) : (
//         <ScreenStrip c={screen.status} onPress={openScreen} />
//       )}
//       {sample && <p className="menu-sample">Sample data · not your cards</p>}
//       {notice && <p className="menu-notice">{notice}</p>}
//       {flash && <p className="menu-flash">{flash}</p>}
//       <div className="menu-body">
//         {view === "card" && <CardView item={item} actions={actions} onClose={onCloseCard} onGone={onCloseCard} />}
//         {view === "goals" &&
//           (goals.length ? (
//             <div className="m-goals" aria-label="Goals">
//               {goals.map((g, i) => (
//                 <GoalCard key={g.id} n={i + 1} goal={g} cards={pending.filter((p) => p.goal?.name === g.name)} onPick={onPick} />
//               ))}
//             </div>
//           ) : (
//             <div className="m-empty">
//               <h3>{loading ? "Reading your goals…" : "No goals yet"}</h3>
//               {!loading && <p>Goals come from your company brief on the website. Accept or add one there and it shows here.</p>}
//             </div>
//           ))}
//         {view === "pending" && <PendingView items={pending} loading={loading} onPick={onPick} />}
//         {view === "screen" && <ScreenView s={screen} />}
//       </div>
//     </section>
//   );
// }
```

#### `src/menu/Drop.tsx`

```tsx
// // One card of intelligence — the same card whether it drops from the menu bar (the lane window) or
// // sits in the GeniOS menu: where it came from, the call to action, why in one or two lines, the goal
// // it moves, and the four buttons (Done · Delegate · Later · Feedback), each opening inside the card.
// //
// // What each button does is the caller's (`DropActions`): a brain card presses `/cards/{id}/action`,
// // a screen item calls the Rust core, a popup answers the lane. A button the caller cannot honour is
// // shown locked with one line saying why, never a press that would be refused.
// import { useEffect, useRef, useState } from "react";
// import { Bot, ChevronRight, Lock, Send, Target, Users, X } from "lucide-react";
// import type { DeskItem } from "./sample";
//
// type Panel = "delegate" | "later" | "feedback";
//
// export type Choice = { id: string; label: string };
//
// export type DropActions = {
//   /** Done (or Answer's send on a question). Returns the line to show after it, e.g. "Marked done". */
//   primary?: () => string | void;
//   /** The card's own Later options; `pick` adds "Pick a day" (custom, 9:00 that day). */
//   later?: { options: Choice[]; pick?: boolean; onPick: (id: string, until?: string) => string | void };
//   /** What is off: the card's own reasons, and your words. `null` = locked, with `lockedWhy`. */
//   feedback?: { reasons: Choice[]; words?: boolean; onSend: (reason: string, words: string) => string | void } | null;
//   feedbackLockedWhy?: string;
//   /** Delegate: the team and agents to show; the hand-over itself is locked until the brain serves it.
//    *  `ask` is a popup's own "Ask my agent" (the agent drafts it; you approve before it goes). */
//   delegate?: { people: { name: string; detail: string }[]; agents: { name: string; detail: string }[]; ask?: () => void };
//   /** A question is answered in the card. */
//   answer?: (words: string) => string | void;
//   /** Undo for the line Done / Later left. */
//   undo?: () => void;
//   /** Replace the four buttons (an agent's proposal: Approve · Edit · Reject). */
//   custom?: { buttons: (Choice & { main?: boolean })[]; onPress: (id: string) => void };
// };
//
// /** How long a done or put-off card stays, with Undo, before it slides away. */
// export const GONE_AFTER_MS = 3000;
// const SLIDE_MS = 320;
//
// export function Drop({
//   item,
//   actions,
//   variant = "drop",
//   leaving: leavingNow = false,
//   countdown,
//   onShowMore,
//   onOpen,
//   onClose,
//   onGone,
// }: {
//   item: DeskItem;
//   actions: DropActions;
//   variant?: "drop" | "menu";
//   /** The caller is taking it away now (a popup the person pressed). */
//   leaving?: boolean;
//   /** A popup's time on screen: a line along the top that runs out over `ms`. `held` (the pointer
//    *  is on it) keeps it full; a new `round` starts it again. */
//   countdown?: { ms: number; held: boolean; round: number };
//   onShowMore?: () => void;
//   onOpen?: () => void;
//   onClose?: () => void;
//   /** Called once the card has slid away after Done or Later (Undo stops it). */
//   onGone?: () => void;
// }) {
//   const [panel, setPanel] = useState<Panel | null>(null);
//   const [who, setWho] = useState<"people" | "agent">("people");
//   const [reason, setReason] = useState<string | null>(null);
//   const [words, setWords] = useState("");
//   const [day, setDay] = useState("");
//   const [answer, setAnswer] = useState("");
//   const [note, setNote] = useState<{ text: string; undo: boolean } | null>(null);
//   const [leaving, setLeaving] = useState(false);
//   const Icon = item.icon;
//
//   // Done or Later: the line and its Undo stay three seconds, then the card slides away. The
//   // callback is read through a ref: the menu re-renders every few seconds, and a new function
//   // each time must not start the three seconds over.
//   const gone = useRef(onGone);
//   gone.current = onGone;
//   useEffect(() => {
//     if (!note?.undo) return;
//     const t1 = setTimeout(() => setLeaving(true), GONE_AFTER_MS);
//     const t2 = setTimeout(() => gone.current?.(), GONE_AFTER_MS + SLIDE_MS);
//     return () => {
//       clearTimeout(t1);
//       clearTimeout(t2);
//     };
//   }, [note]);
//   const toggle = (p: Panel) => setPanel((cur) => (cur === p ? null : p));
//   const after = (text: string | void, undo: boolean) => {
//     setPanel(null);
//     if (text) setNote({ text, undo });
//   };
//   const asks = Boolean(actions.answer);
//
//   return (
//     <section
//       className={`drop${variant === "menu" ? " in-menu" : ""}${leaving || leavingNow ? " leaving" : ""}`}
//       aria-label={`GeniOS: ${item.subject}`}
//       data-drop={item.id}
//     >
//       <span className="drop-glow" aria-hidden />
//       {countdown && (
//         <span className="drop-timer" aria-hidden>
//           <i
//             key={countdown.round}
//             className={countdown.held ? "held" : undefined}
//             style={{ animationDuration: `${countdown.ms}ms` }}
//             onAnimationEnd={() => setLeaving(true)}
//           />
//         </span>
//       )}
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
//           {item.lines?.length ? (
//             <ul className="drop-lines">
//               {item.lines.map((l, i) => (
//                 <li key={i}>{l}</li>
//               ))}
//             </ul>
//           ) : (
//             item.why && <p className="drop-why">{item.why}</p>
//           )}
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
//         {asks && !note && (
//           <div className="drop-say">
//             <input value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Your answer, in one line" aria-label="Your answer" />
//             <button type="button" disabled={!answer.trim()} onClick={() => after(actions.answer?.(answer), false)}>
//               <Send size={13} strokeWidth={2} aria-hidden /> Send
//             </button>
//           </div>
//         )}
//
//         {note ? (
//           <p className="drop-note">
//             {note.text}
//             {note.undo && actions.undo && (
//               <button
//                 type="button"
//                 onClick={() => {
//                   actions.undo?.();
//                   setNote(null);
//                 }}
//               >
//                 Undo
//               </button>
//             )}
//           </p>
//         ) : actions.custom ? (
//           <div className="drop-actions">
//             {actions.custom.buttons.map((b) => (
//               <button key={b.id} type="button" className={`drop-btn${b.main ? " main" : ""}`} onClick={() => actions.custom?.onPress(b.id)}>
//                 {b.label}
//               </button>
//             ))}
//           </div>
//         ) : (
//           <div className="drop-actions">
//             {actions.primary && !asks && (
//               <button type="button" className="drop-btn main" onClick={() => after(actions.primary?.(), true)}>
//                 {item.primary}
//               </button>
//             )}
//             <button type="button" className="drop-btn" aria-expanded={panel === "delegate"} onClick={() => toggle("delegate")}>
//               Delegate
//             </button>
//             {actions.later && (
//               <button type="button" className="drop-btn" aria-expanded={panel === "later"} onClick={() => toggle("later")}>
//                 Later
//               </button>
//             )}
//             <button type="button" className="drop-btn" aria-expanded={panel === "feedback"} onClick={() => toggle("feedback")}>
//               Feedback
//             </button>
//             {variant === "drop" && onShowMore && (
//               <button type="button" className="drop-more" onClick={onShowMore}>
//                 Show more <ChevronRight size={14} strokeWidth={2} aria-hidden />
//               </button>
//             )}
//           </div>
//         )}
//
//         {panel === "later" && actions.later && (
//           <div className="drop-panel" aria-label="Later">
//             <span className="drop-panel-title">Bring it back</span>
//             <div className="drop-chips">
//               {actions.later.options.map((o) => (
//                 <button key={o.id} type="button" onClick={() => after(actions.later?.onPick(o.id), true)}>
//                   {o.label}
//                 </button>
//               ))}
//             </div>
//             {actions.later.pick && (
//               <div className="drop-say">
//                 <input type="date" value={day} onChange={(e) => setDay(e.target.value)} aria-label="A day you pick" />
//                 <button
//                   type="button"
//                   disabled={!day}
//                   onClick={() => after(actions.later?.onPick("custom", new Date(`${day}T09:00:00`).toISOString()), true)}
//                 >
//                   Put off to 9:00 that day
//                 </button>
//               </div>
//             )}
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
//             {(who === "people" ? actions.delegate?.people : actions.delegate?.agents)?.length ? (
//               <ul className="drop-people">
//                 {(who === "people" ? actions.delegate!.people : actions.delegate!.agents).map((p) => (
//                   <li key={p.name}>
//                     <span>
//                       {p.name}
//                       <small>{p.detail}</small>
//                     </span>
//                     <button type="button" disabled>
//                       <Lock size={12} strokeWidth={2} aria-hidden /> {who === "people" ? "Hand over" : "Ask it"}
//                     </button>
//                   </li>
//                 ))}
//               </ul>
//             ) : (
//               <span className="drop-panel-note">
//                 {who === "people" ? "Your team shows here for the workspace owner." : "No agent is connected yet."}
//               </span>
//             )}
//             {who === "agent" && actions.delegate?.ask && (
//               <div className="drop-chips">
//                 <button type="button" onClick={() => actions.delegate?.ask?.()}>
//                   <Bot size={13} strokeWidth={2} aria-hidden /> Ask my agent
//                 </button>
//               </div>
//             )}
//             <span className="drop-panel-note">Handing over goes live with the next brain update.</span>
//           </div>
//         )}
//
//         {panel === "feedback" &&
//           (actions.feedback ? (
//             <div className="drop-panel" aria-label="Feedback">
//               <span className="drop-panel-title">What is off?</span>
//               <div className="drop-chips">
//                 {actions.feedback.reasons.map((r) => (
//                   <button key={r.id} type="button" aria-pressed={reason === r.id} onClick={() => setReason(r.id)}>
//                     {r.label}
//                   </button>
//                 ))}
//               </div>
//               <div className="drop-say">
//                 {actions.feedback.words !== false && (
//                   <input value={words} onChange={(e) => setWords(e.target.value)} placeholder="In your words: what is wrong, what it should be" aria-label="Your words" />
//                 )}
//                 <button type="button" disabled={!reason} onClick={() => reason && after(actions.feedback?.onSend(reason, words), false)}>
//                   <Send size={13} strokeWidth={2} aria-hidden /> Send
//                 </button>
//               </div>
//             </div>
//           ) : (
//             <div className="drop-panel" aria-label="Feedback">
//               <span className="drop-panel-note">
//                 <Lock size={12} strokeWidth={2} aria-hidden /> {actions.feedbackLockedWhy ?? "Feedback on this kind of item comes with the next update."}
//               </span>
//             </div>
//           ))}
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

#### `src/menu/live.ts`

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
// const CARD_KIND: Record<DeskCard["lane"], string> = {
//   decision: "Decision",
//   conflict: "Decision",
//   question: "Question",
//   waiting: "Waiting",
// };
//
// const FOLLOWUP_KIND: Record<string, string> = {
//   ask: "Ask",
//   my_promise: "Follow-up",
//   their_promise: "Waiting",
//   deadline: "Deadline",
//   risk: "Deadline",
//   next_step: "Follow-up",
// };
//
// export const KIND_ICON: Record<string, LucideIcon> = {
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
//     icon: KIND_ICON[kind] ?? CalendarCheck,
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
//     icon: f.kind === "risk" ? ShieldAlert : (KIND_ICON[kind] ?? MessageCircle),
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

#### `src/menu/sample.ts`

```ts
// // The shape the drop and the menu draw (`DeskItem`, `Goal`), and the sample data shown when
// // "Show sample data" is on in the account — never anyone's real cards.
// import { AlarmClock, CalendarCheck, MessageCircle, type LucideIcon } from "lucide-react";
//
// export type Importance = "Now" | "High" | "Normal";
//
// export type DeskItem = {
//   id: string;
//   /** What kind of thing it is: the scenario tag (Follow-up, Deadline, Decision, Ask, Question, Waiting, Brief…). */
//   kind: string;
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
//   /** A list instead of the why line (a morning brief). */
//   lines?: string[];
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
// /** A goal. The brain serves only its name today (`/v1/company-brief`); the rest waits for `GET /v1/goals`. */
// export type Goal = {
//   id: string;
//   name: string;
//   status?: "On track" | "At risk" | "Behind";
//   by?: string;
//   progress?: number;
//   /** What is happening, in one line. */
//   now?: string;
//   /** The goal's own count, step by step. `share` draws the bar (0–1); `note` says what it means. */
//   funnel?: { value: string; label: string; share: number; note?: string }[];
//   /** The same numbers as one plain sentence. */
//   meaning?: string;
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

#### `src/menu/menu.css`

```css
// /* The GeniOS menu (main window) and the drop (the lane window): the agreed design, 22 Oct.
//    Black and white first; dark green and golden yellow as touches; Inter (theme.css), 400, headings 560.
//    The tokens sit on `.genios` (the body of both windows). Mirrors speedrun008/GeniOS-010/07-GENIOS-DESKTOP. */
//
// /* ---- Palette (Rohit, 22 Oct, round 3): black and white first, dark green only as a touch ---- */
// .genios {
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
//
// .drop.in-menu {
//   width: auto;
//   border-radius: 18px;
//   box-shadow: 0 10px 30px rgba(13, 28, 20, 0.28);
// }
//
// .drop-glow {
//   position: absolute;
//   inset: 0;
//   pointer-events: none;
//   background:
//     radial-gradient(60% 55% at 0% 0%, rgba(217, 178, 76, 0.13), rgba(217, 178, 76, 0) 70%),
//     radial-gradient(60% 85% at 100% 120%, rgba(29, 90, 62, 0.55), rgba(29, 90, 62, 0) 72%),
//     linear-gradient(165deg, var(--g-deep) 40%, var(--g-deep-2));
// }
//
// .drop-side {
//   position: relative;
//   flex: none;
//   display: grid;
//   justify-items: center;
//   align-content: start;
//   gap: 8px;
//   width: 52px;
// }
//
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
//
// .drop-when {
//   font-size: 12px;
//   line-height: 1.2;
//   text-align: center;
//   color: var(--g-white-3);
// }
//
// .drop-body {
//   position: relative;
//   flex: 1;
//   min-width: 0;
//   display: grid;
//   gap: 10px;
// }
//
// .drop-main {
//   display: grid;
//   gap: 6px;
//   padding-right: 18px;
//   cursor: pointer;
// }
//
// .drop.in-menu .drop-main {
//   cursor: default;
// }
//
// .drop-tags {
//   display: flex;
//   flex-wrap: wrap;
//   align-items: center;
//   gap: 5px;
//   font-size: 12px;
//   color: var(--g-white-2);
// }
//
// .drop-tags > span {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   height: 21px;
//   padding: 0 8px;
//   border-radius: 6px;
//   background: var(--g-veil);
// }
//
// .drop-tags .drop-hot {
//   color: var(--g-gold);
// }
//
// .drop-tags .drop-hot i {
//   width: 6px;
//   height: 6px;
//   border-radius: 50%;
//   background: var(--g-gold);
// }
//
// .drop-subject {
//   font-size: 17px;
//   font-weight: 560;
//   line-height: 1.3;
//   letter-spacing: -0.01em;
// }
//
// .drop-why {
//   font-size: 13.5px;
//   line-height: 1.45;
//   color: var(--g-white-2);
// }
//
// .drop-goal {
//   display: flex;
//   align-items: flex-start;
//   gap: 6px;
//   font-size: 12.5px;
//   line-height: 1.4;
//   color: var(--g-white-2);
// }
//
// .drop-goal svg {
//   flex: none;
//   margin-top: 2px;
//   color: var(--g-gold);
// }
//
// .drop-actions {
//   display: flex;
//   align-items: center;
//   gap: 6px;
// }
//
// .drop-btn {
//   height: 30px;
//   padding: 0 12px;
//   border: 1px solid var(--g-rule);
//   border-radius: 9px;
//   background: var(--g-veil);
//   color: var(--g-white);
//   font-size: 12.5px;
// }
//
// .drop-btn.main {
//   border-color: transparent;
//   background: var(--g-white);
//   color: var(--g-deep);
// }
//
// .drop-btn[aria-expanded="true"] {
//   border-color: var(--g-gold);
//   color: var(--g-gold);
//   background: var(--g-gold-soft);
// }
//
// .drop-btn:hover {
//   filter: brightness(1.12);
// }
//
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
//
// .drop-more:hover {
//   color: var(--g-white);
// }
//
// .drop-note {
//   display: flex;
//   align-items: center;
//   gap: 10px;
//   font-size: 13px;
//   color: var(--g-white);
// }
//
// .drop-note button {
//   border: 0;
//   background: none;
//   color: var(--g-white);
//   text-decoration: underline;
//   text-underline-offset: 3px;
//   font-size: 13px;
// }
//
// .drop-panel {
//   display: grid;
//   gap: 9px;
//   padding: 11px;
//   border-radius: 12px;
//   background: rgba(245, 241, 230, 0.06);
//   border: 1px solid var(--g-rule);
//   animation: dx-rise 0.16s cubic-bezier(0.16, 1, 0.3, 1);
// }
//
// .drop-panel-title {
//   font-size: 12.5px;
//   color: var(--g-white);
// }
//
// .drop-panel-note {
//   font-size: 12px;
//   color: var(--g-white-3);
// }
//
// .drop-chips {
//   display: flex;
//   flex-wrap: wrap;
//   gap: 6px;
// }
//
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
//
// .drop-chips button:hover {
//   border-color: var(--g-white-2);
// }
//
// .drop-chips button[aria-pressed="true"] {
//   background: var(--g-gold);
//   border-color: var(--g-gold);
//   color: var(--g-deep);
// }
//
// .drop-say {
//   display: flex;
//   gap: 6px;
// }
//
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
//
// .drop-say input::placeholder {
//   color: var(--g-white-3);
// }
//
// .drop-say button:not(:disabled) {
//   background: var(--g-white);
//   color: var(--g-deep);
//   border-color: transparent;
// }
//
// .drop-say button:disabled {
//   opacity: 0.45;
// }
//
// .drop-seg {
//   display: flex;
//   gap: 2px;
//   padding: 2px;
//   border-radius: 9px;
//   background: rgba(0, 0, 0, 0.25);
// }
//
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
//
// .drop-seg button[aria-pressed="true"] {
//   background: var(--g-white);
//   color: var(--g-deep);
// }
//
// .drop-people {
//   list-style: none;
//   padding: 0;
//   display: grid;
// }
//
// .drop-people li {
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   gap: 10px;
//   padding: 7px 2px;
//   font-size: 13px;
// }
//
// .drop-people li + li {
//   border-top: 1px solid var(--g-rule);
// }
//
// .drop-people li > span {
//   display: grid;
//   min-width: 0;
// }
//
// .drop-people small {
//   font-size: 12px;
//   color: var(--g-white-3);
// }
//
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
//
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
//
// .drop-close:hover {
//   background: rgba(245, 241, 230, 0.16);
//   color: var(--g-white);
// }
//
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
//
// .menu-head {
//   display: flex;
//   align-items: center;
//   gap: 8px;
//   padding: 10px 10px 10px 10px;
//   border-bottom: 1px solid var(--dx-line);
// }
//
// .menu-fill {
//   flex: 1;
// }
//
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
//
// .m-close:hover {
//   background: var(--dx-hover);
//   color: var(--dx-ink);
// }
//
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
//
// .m-avatar[aria-expanded="true"] {
//   box-shadow: 0 0 0 2px #ffffff, 0 0 0 4px var(--g-gold);
// }
//
// .m-account {
//   display: grid;
//   gap: 2px;
//   padding: 8px 9px 6px;
//   font-size: 13px;
// }
//
// .m-account b {
//   font-weight: 560;
// }
//
// .m-account span {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
//
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
//
// .m-card {
//   display: grid;
//   gap: 10px;
// }
//
// .m-why {
//   display: grid;
//   gap: 5px;
//   padding: 12px 14px;
//   border-radius: 14px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line);
//   box-shadow: var(--dx-shadow-1);
// }
//
// .m-where {
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
//
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
//
// .m-said span {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
//
// .m-caught {
//   font-size: 13px;
//   color: var(--dx-ink-2);
// }
//
// /* Approach · Goal · Importance: three lines, one each — label on the left, the one-liner on the right. */
// .m-facts {
//   display: grid;
//   padding: 2px 14px;
//   border-radius: 14px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line);
//   box-shadow: var(--dx-shadow-1);
// }
//
// .m-facts > div {
//   display: grid;
//   grid-template-columns: 96px minmax(0, 1fr);
//   align-items: center;
//   gap: 10px;
//   min-height: 42px;
// }
//
// .m-facts > div + div {
//   border-top: 1px solid var(--dx-line);
// }
//
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
//
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
//
// .m-num.small {
//   width: 22px;
//   height: 22px;
//   font-size: 12px;
// }
//
// .m-goals {
//   display: grid;
//   gap: 10px;
// }
//
// .m-goal {
//   display: grid;
//   gap: 10px;
//   padding: 14px;
//   border-radius: 14px;
//   background: var(--dx-card);
//   border: 1px solid var(--dx-line);
//   box-shadow: var(--dx-shadow-1);
// }
//
// .m-goal-head {
//   display: flex;
//   align-items: center;
//   gap: 10px;
// }
//
// .m-goal-head > div {
//   flex: 1;
//   min-width: 0;
// }
//
// .m-goal-head h3 {
//   font-size: 14.5px;
//   font-weight: 560;
// }
//
// .m-goal-by {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
//
// .m-goal-bar {
//   display: block;
//   height: 6px;
//   border-radius: 3px;
//   background: var(--dx-inset-2);
//   overflow: hidden;
// }
//
// .m-goal-bar span {
//   display: block;
//   height: 100%;
//   border-radius: 3px;
//   background: linear-gradient(90deg, #1d5a3e, #2f7a55 85%, var(--g-gold));
// }
//
// .m-goal-now {
//   font-size: 13px;
//   color: var(--dx-ink-2);
// }
//
// .m-funnel {
//   display: grid;
//   gap: 9px;
//   padding: 13px 14px;
//   border-radius: 12px;
//   background: var(--g-deep);
//   color: var(--g-white);
//   background-image: radial-gradient(70% 120% at 100% 0%, rgba(29, 90, 62, 0.45), rgba(29, 90, 62, 0) 70%);
// }
//
// .m-step {
//   display: grid;
//   grid-template-columns: 30px minmax(0, 1fr) 96px 36px;
//   align-items: center;
//   gap: 10px;
// }
//
// .m-step b {
//   font-size: 19px;
//   line-height: 1;
//   font-weight: 560;
//   color: var(--g-white);
//   font-variant-numeric: tabular-nums;
//   text-align: right;
// }
//
// .m-step-label {
//   font-size: 12.5px;
//   color: var(--g-white-2);
//   white-space: nowrap;
//   overflow: hidden;
//   text-overflow: ellipsis;
// }
//
// .m-step-bar {
//   height: 6px;
//   border-radius: 3px;
//   background: rgba(247, 247, 245, 0.1);
//   overflow: hidden;
// }
//
// .m-step-bar span {
//   display: block;
//   height: 100%;
//   border-radius: 3px;
//   background: linear-gradient(90deg, #b8902a, var(--g-gold));
// }
//
// .m-step-note {
//   font-size: 12px;
//   color: var(--g-gold);
//   text-align: right;
//   font-variant-numeric: tabular-nums;
// }
//
// .m-goal-meaning {
//   font-size: 12.5px;
//   color: var(--dx-mist);
// }
//
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
//
// .m-goal-cards .dx-chev {
//   margin-left: auto;
// }
//
// .m-goal-cards[aria-expanded="true"] .dx-chev {
//   transform: rotate(180deg);
// }
//
// .m-goal-list {
//   list-style: none;
//   padding: 0;
//   display: grid;
//   gap: 6px;
// }
//
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
//
// .m-goal-list button:hover {
//   background: var(--dx-inset-2);
// }
//
// .m-goal-card {
//   flex: 1;
//   display: grid;
//   font-size: 13px;
// }
//
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
//
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
//
// .m-row:hover {
//   border-color: var(--dx-line-strong);
//   box-shadow: var(--dx-shadow-2);
// }
//
// .m-row-main {
//   flex: 1;
//   min-width: 0;
//   display: grid;
//   gap: 5px;
// }
//
// .m-row-tags {
//   display: flex;
//   flex-wrap: wrap;
//   align-items: center;
//   gap: 5px;
//   font-size: 12px;
//   color: var(--dx-ink-2);
// }
//
// .m-row-tags > span {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   height: 21px;
//   padding: 0 8px;
//   border-radius: 6px;
//   background: var(--dx-inset);
// }
//
// .m-row-tags .hot {
//   color: var(--dx-accent);
//   background: var(--dx-accent-soft);
// }
//
// .m-row-tags .hot i {
//   width: 6px;
//   height: 6px;
//   border-radius: 50%;
//   background: var(--g-gold);
// }
//
// .m-row-tags small {
//   margin-left: auto;
//   font-size: 12px;
//   color: var(--dx-mist);
// }
//
// .m-row-subject {
//   font-size: 14px;
//   font-weight: 560;
//   line-height: 1.3;
//   color: var(--dx-ink);
// }
//
// .m-row-why {
//   font-size: 12.5px;
//   line-height: 1.4;
//   color: var(--dx-ink-2);
//   display: -webkit-box;
//   -webkit-box-orient: vertical;
//   -webkit-line-clamp: 2;
//   overflow: hidden;
// }
//
// .m-row-goal {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   font-size: 12px;
//   color: var(--dx-accent);
// }
//
// .m-row-goal svg {
//   color: #b8902a;
// }
//
// /* Luxury, professional: tabs as a black pill on white; quiet tracked labels. */
// .menu .dx-tabs {
//   background: var(--dx-inset);
// }
//
// .menu .dx-tabs button[aria-selected="true"] {
//   background: var(--g-deep);
//   color: #ffffff;
//   box-shadow: none;
// }
//
// .menu .m-label {
//   letter-spacing: 0.08em;
// }
//
// .menu {
//   box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.04), 0 2px 6px rgba(0, 0, 0, 0.06), 0 28px 70px rgba(0, 0, 0, 0.28);
// }
//
// /* The account: who is signed in, and the settings the app has today. */
// .menu-head .dx-pop {
//   max-width: 360px;
//   padding: 0;
// }
//
// .m-acc {
//   width: 340px;
//   display: grid;
// }
//
// .m-acc-head {
//   display: flex;
//   align-items: center;
//   gap: 12px;
//   padding: 14px;
//   border-bottom: 1px solid var(--dx-line);
// }
//
// .m-avatar.big {
//   width: 40px;
//   height: 40px;
//   font-size: 16px;
// }
//
// .m-acc-head > div {
//   display: grid;
//   font-size: 12px;
//   color: var(--dx-mist);
// }
//
// .m-acc-head b {
//   font-size: 14px;
//   font-weight: 560;
//   color: var(--dx-ink);
// }
//
// .m-acc-sec {
//   display: grid;
//   gap: 8px;
//   padding: 12px 14px;
//   border-bottom: 1px solid var(--dx-line);
// }
//
// .m-acc-row {
//   display: flex;
//   align-items: center;
//   gap: 10px;
//   font-size: 13px;
//   color: var(--dx-ink);
// }
//
// .m-acc-row > svg {
//   flex: none;
//   color: var(--dx-mist);
// }
//
// .m-acc-row > span {
//   flex: 1;
//   min-width: 0;
//   display: grid;
// }
//
// .m-acc-row small {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
//
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
//
// .m-link:hover {
//   text-decoration-color: currentColor;
// }
//
// .m-acc-code {
//   display: grid;
//   gap: 4px;
//   padding: 10px 12px;
//   border-radius: 10px;
//   background: var(--g-deep);
//   color: var(--g-white-2);
//   font-size: 12px;
// }
//
// .m-code {
//   font: 560 20px var(--dx-mono);
//   letter-spacing: 0.14em;
//   color: var(--g-gold);
//   user-select: text;
// }
//
// .m-acc-api {
//   display: grid;
//   gap: 6px;
// }
//
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
//
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
//
// .m-switch.on {
//   background: var(--g-deep);
// }
//
// .m-switch.on i {
//   transform: translateX(14px);
// }
//
// .m-tools {
//   display: flex;
//   flex-wrap: wrap;
//   gap: 6px;
// }
//
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
//
// .m-tools span.on {
//   border-style: solid;
//   color: var(--dx-ink);
// }
//
// .m-tools span.on::after {
//   content: "";
//   width: 6px;
//   height: 6px;
//   margin-left: 2px;
//   border-radius: 50%;
//   background: #2f7a55;
// }
//
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
//
// .menu-head {
//   border-bottom-color: rgba(255, 255, 255, 0.08);
// }
//
// .menu .m-close {
//   color: rgba(247, 247, 245, 0.7);
// }
//
// .menu .m-close:hover {
//   background: rgba(247, 247, 245, 0.1);
//   color: #ffffff;
// }
//
// .menu .dx-tabs {
//   background: rgba(247, 247, 245, 0.08);
// }
//
// .menu .dx-tabs button {
//   color: rgba(247, 247, 245, 0.7);
// }
//
// .menu .dx-tabs button:hover {
//   color: #ffffff;
// }
//
// .menu .dx-tabs button[aria-selected="true"] {
//   background: #ffffff;
//   color: #0b0b0c;
// }
//
// .menu-head .m-avatar {
//   background: #1a1c1b;
//   box-shadow: 0 0 0 1px rgba(217, 178, 76, 0.45);
// }
//
// .drop.in-menu {
//   box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1), 0 12px 30px rgba(0, 0, 0, 0.45);
// }
//
// .menu .m-why,
// .menu .m-facts,
// .menu .m-goal,
// .menu .m-row {
//   border-color: transparent;
//   box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 10px 24px rgba(0, 0, 0, 0.25);
// }
//
// .menu .m-row:hover {
//   box-shadow: 0 0 0 1px rgba(217, 178, 76, 0.5), 0 12px 28px rgba(0, 0, 0, 0.35);
// }
//
// /* ---- In the app: the menu fills its window; the drop fills the lane window's width ---- */
// html,
// body,
// #root {
//   height: 100%;
// }
// body.genios {
//   background: transparent;
// }
// .genios-main .menu {
//   width: 100%;
//   height: 100%;
//   max-height: none;
// }
// .genios-lane .drop {
//   width: 100%;
// }
// .drop-lines {
//   list-style: none;
//   padding: 0;
//   display: grid;
//   gap: 3px;
//   font-size: 13px;
//   line-height: 1.42;
//   color: var(--g-white-2);
// }
// .drop-lines li::before {
//   content: "·";
//   margin-right: 7px;
// }
// .m-empty {
//   display: grid;
//   gap: 6px;
//   justify-items: center;
//   text-align: center;
//   padding: 48px 24px;
//   color: var(--g-white-2);
// }
// .m-empty h3 {
//   font-size: 15px;
//   font-weight: 560;
//   color: var(--g-white);
// }
// .m-empty p {
//   font-size: 13px;
//   max-width: 300px;
// }
// .menu-sample,
// .menu-notice {
//   margin: 10px 12px 0;
//   padding: 8px 11px;
//   border-radius: 10px;
//   font-size: 12.5px;
// }
// .menu-sample {
//   background: var(--g-gold-soft);
//   color: var(--g-gold);
//   border: 1px solid rgba(217, 178, 76, 0.35);
// }
// .menu-notice {
//   background: #ffffff;
//   color: var(--dx-ink);
// }
// .m-confirm p {
//   font-size: 13px;
//   line-height: 1.45;
//   color: var(--dx-ink-2);
// }
// .m-confirm div {
//   display: flex;
//   justify-content: flex-end;
//   align-items: center;
//   gap: 14px;
// }
// .m-solid {
//   height: 28px;
//   padding: 0 12px;
//   border: 0;
//   border-radius: 8px;
//   background: var(--g-deep);
//   color: #ffffff;
//   font-size: 12.5px;
// }
// .m-goal-cards:disabled {
//   cursor: default;
//   color: var(--dx-mist);
// }
//
// /* Done or Later: after three seconds the card slides away to the right. */
// .drop.leaving {
//   animation: drop-leave 0.32s cubic-bezier(0.4, 0, 1, 1) forwards;
//   pointer-events: none;
// }
// @keyframes drop-leave {
//   to {
//     transform: translateX(60px);
//     opacity: 0;
//   }
// }
// .m-refresh {
//   display: grid;
//   place-items: center;
//   width: 28px;
//   height: 28px;
//   border: 0;
//   border-radius: 8px;
//   background: transparent;
//   color: rgba(247, 247, 245, 0.7);
// }
// .m-refresh:hover:not(:disabled) {
//   background: rgba(247, 247, 245, 0.1);
//   color: #ffffff;
// }
// .m-refresh.spin svg {
//   animation: m-spin 0.8s linear infinite;
// }
// @keyframes m-spin {
//   to {
//     transform: rotate(360deg);
//   }
// }
// .menu-flash {
//   margin: 10px 12px 0;
//   padding: 7px 11px;
//   border-radius: 10px;
//   background: rgba(247, 247, 245, 0.08);
//   color: rgba(247, 247, 245, 0.75);
//   font-size: 12.5px;
// }
//
// /* A popup's five seconds: a gold line along the top runs out from the right; held while hovered. */
// .drop-timer {
//   position: absolute;
//   top: 0;
//   left: 18px;
//   right: 18px;
//   height: 3px;
//   overflow: hidden;
//   border-radius: 0 0 3px 3px;
//   background: rgba(247, 247, 245, 0.08);
// }
// .drop-timer i {
//   display: block;
//   height: 100%;
//   background: linear-gradient(90deg, var(--g-gold), #e8cd7e);
//   transform-origin: left center;
//   animation-name: drop-timer;
//   animation-timing-function: linear;
//   animation-fill-mode: forwards;
// }
// .drop-timer i.held {
//   animation: none;
// }
// @keyframes drop-timer {
//   from {
//     transform: scaleX(1);
//   }
//   to {
//     transform: scaleX(0);
//   }
// }
//
// /* ---- Screen reading: the line under the header, and the Screen view ---- */
// .m-strip {
//   display: flex;
//   align-items: center;
//   gap: 9px;
//   margin: 10px 12px 0;
//   padding: 8px 11px;
//   border: 1px solid rgba(247, 247, 245, 0.1);
//   border-radius: 10px;
//   background: rgba(247, 247, 245, 0.06);
//   color: var(--g-white-2);
//   font-size: 12.5px;
//   text-align: left;
// }
// .m-strip:hover {
//   border-color: rgba(247, 247, 245, 0.22);
//   color: var(--g-white);
// }
// .m-strip > i,
// .m-scr-title > i {
//   flex: none;
//   width: 8px;
//   height: 8px;
//   border-radius: 50%;
//   background: var(--g-white-3);
// }
// .m-strip.on > i,
// .m-scr-head.on .m-scr-title > i {
//   background: #4fb985;
//   box-shadow: 0 0 0 0 rgba(79, 185, 133, 0.55);
//   animation: m-pulse 2s ease-out infinite;
// }
// .m-strip.warn,
// .m-scr-head.warn {
//   border-color: rgba(217, 178, 76, 0.45);
// }
// .m-strip.warn {
//   background: var(--g-gold-soft);
//   color: var(--g-gold);
// }
// .m-strip.warn > i,
// .m-scr-head.warn .m-scr-title > i {
//   background: var(--g-gold);
// }
// .m-strip-text {
//   flex: 1;
//   min-width: 0;
//   white-space: nowrap;
//   overflow: hidden;
//   text-overflow: ellipsis;
// }
// .m-strip-when {
//   flex: none;
//   color: var(--g-white-3);
// }
// @keyframes m-pulse {
//   70% {
//     box-shadow: 0 0 0 6px rgba(79, 185, 133, 0);
//   }
//   100% {
//     box-shadow: 0 0 0 0 rgba(79, 185, 133, 0);
//   }
// }
// .m-scr {
//   display: grid;
//   gap: 10px;
// }
// .m-scr-head,
// .m-scr-sec {
//   display: grid;
//   gap: 7px;
//   padding: 13px 14px;
//   border-radius: 14px;
//   background: var(--dx-card);
//   border: 1px solid transparent;
//   box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 10px 24px rgba(0, 0, 0, 0.25);
//   color: var(--dx-ink-2);
// }
// .m-scr-title {
//   display: flex;
//   align-items: center;
//   gap: 9px;
// }
// .m-scr-title h3 {
//   font-size: 15px;
//   font-weight: 560;
//   color: var(--dx-ink);
// }
// .m-scr-head p,
// .m-scr-ok,
// .m-scr-none {
//   font-size: 13px;
//   line-height: 1.45;
//   color: var(--dx-mist);
// }
// .m-scr-btns {
//   display: flex;
//   align-items: center;
//   gap: 14px;
//   margin-top: 3px;
// }
// .m-scr-btns:empty {
//   display: none;
// }
// .m-scr .m-facts p .m-link {
//   margin-left: auto;
// }
// .m-scr-list {
//   list-style: none;
//   padding: 0;
//   display: grid;
// }
// .m-scr-list li {
//   display: grid;
//   gap: 2px;
//   padding: 8px 0;
// }
// .m-scr-list li + li {
//   border-top: 1px solid var(--dx-line);
// }
// .m-scr-list b {
//   font-weight: 400;
//   font-size: 13px;
//   color: var(--dx-ink);
// }
// .m-scr-list small {
//   font-size: 12px;
//   color: var(--dx-mist);
// }
// .m-scr-steps {
//   padding-left: 18px;
//   display: grid;
//   gap: 6px;
//   font-size: 13px;
//   line-height: 1.45;
//   color: var(--dx-ink-2);
// }
// .m-scr-steps li::marker {
//   color: var(--dx-accent);
// }
//
// .m-select {
//   height: 26px;
//   padding: 0 6px;
//   border: 1px solid var(--dx-line-strong);
//   border-radius: 7px;
//   background: var(--dx-card);
//   color: var(--dx-ink);
//   font: inherit;
//   font-size: 12.5px;
// }
//
// /* Screen open: the line stays on top as Minimize. */
// .m-strip.open {
//   border-color: rgba(247, 247, 245, 0.22);
// }
// .m-strip-min {
//   flex: none;
//   display: inline-flex;
//   align-items: center;
//   gap: 4px;
//   color: var(--g-white);
// }
```

## 3 · The popups (lane window)

One popup at a time, pushed by the Rust core: the drop with its four buttons, the five-second line, hover hold, slide-away.

#### `src/lane/main.tsx`

```tsx
// import { StrictMode } from "react";
// import { createRoot } from "react-dom/client";
// import { Lane } from "./Lane";
// import "../desktop/theme.css";
// import "../menu/menu.css";
// import "./lane.css";
//
// document.body.classList.add("genios", "genios-lane");
//
// createRoot(document.getElementById("root")!).render(
//   <StrictMode>
//     <Lane />
//   </StrictMode>,
// );
```

#### `src/lane/Lane.tsx`

```tsx
// // The lane: one drop at a time, pushed from Rust (`genios://lane`). The window never takes focus;
// // every decision (queue, quiet hours, shadow mode, rate limits) is made in Rust — this draws the
// // current popup as the agreed drop and reports presses.
// //
// // The four buttons map onto what the popup offers: Done (its "done", else it is dismissed) ·
// // Delegate (its "Ask my agent" when offered) · Later (its reminders) · Feedback (useful / not useful /
// // mute chat). Show more opens the GeniOS menu on this item. "Ask my agent" proposals keep their own
// // Approve · Edit · Reject; nothing here ever approves on its own.
// import { useEffect, useRef, useState } from "react";
// import { invoke } from "@tauri-apps/api/core";
// import { emitTo, listen } from "@tauri-apps/api/event";
// import { AlarmClock, Bot, CalendarClock, Eye, History, ListChecks, MessageCircle, Sun, Users, type LucideIcon } from "lucide-react";
// import { Drop, type DropActions } from "../menu/Drop";
//
// /** A popup's five seconds — the same as the Rust queue's `POPUP_SHOW_MS`, which hides it. */
// const POPUP_MS = 5000;
// /** The slide-away after a press, before the press is reported (and the next popup comes). */
// const SLIDE_MS = 320;
// import type { DeskItem } from "../menu/sample";
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
// const LATER: Record<string, string> = { snooze: "Snooze", remind_1h: "In 1 hour", remind_tonight: "Tonight", remind_tomorrow: "Tomorrow" };
// const FEEDBACK: Record<string, string> = { useful: "Useful", not_useful: "Not useful", mute_chat: "Mute this chat" };
//
// // Where a popup came from, in the person's words.
// const SOURCE: Record<string, { tool: string; how: string; kind: string; icon: LucideIcon }> = {
//   "moment.screen_insight": { tool: "Screen", how: "what you're reading", kind: "Insight", icon: Eye },
//   "moment.chat_open": { tool: "Chat", how: "screen", kind: "In this chat", icon: MessageCircle },
//   "moment.followup": { tool: "Reminder", how: "screen", kind: "Follow-up", icon: AlarmClock },
//   "moment.meeting_prep": { tool: "Calendar", how: "next meeting", kind: "Before your meeting", icon: CalendarClock },
//   "moment.daily_brief": { tool: "GeniOS", how: "morning", kind: "Brief", icon: Sun },
//   "moment.daily_wrap": { tool: "GeniOS", how: "evening", kind: "Wrap", icon: ListChecks },
//   "moment.due_today": { tool: "GeniOS", how: "today", kind: "Deadline", icon: AlarmClock },
//   "moment.counterparty_recall": { tool: "History", how: "your history", kind: "Recall", icon: History },
//   "moment.duplicate_outreach": { tool: "History", how: "your history", kind: "Already sent", icon: History },
//   "moment.changed_value": { tool: "History", how: "since you looked", kind: "Changed", icon: History },
//   [PROPOSAL]: { tool: "Your agent", how: "needs your approval", kind: "Ask my agent", icon: Bot },
//   [DRAFT_REVIEW]: { tool: "Draft notes", how: "copy only", kind: "Draft", icon: ListChecks },
// };
//
// function sourceOf(t: Toast) {
//   return (
//     SOURCE[t.capability_id] ??
//     (t.style === "reminder"
//       ? { tool: "Reminder", how: "screen", kind: "Reminder", icon: AlarmClock }
//       : t.kind === "team"
//         ? { tool: "Team", how: "your team", kind: "Team", icon: Users }
//         : { tool: "GeniOS", how: "screen", kind: "Insight", icon: Eye })
//   );
// }
//
// export function toItem(t: Toast): DeskItem {
//   const src = sourceOf(t);
//   const lines = t.lines.length ? t.lines : t.capability_id === DRAFT_REVIEW && t.body ? t.body.split("\n").filter(Boolean) : undefined;
//   const done = t.actions.find((a) => a.id === "done");
//   return {
//     id: t.id,
//     kind: src.kind,
//     icon: src.icon,
//     source: { tool: src.tool, how: src.how },
//     importance: t.priority === "critical" ? "Now" : t.priority === "high" ? "High" : "Normal",
//     subject: t.headline,
//     why: lines ? "" : (t.body ?? ""),
//     approach: "",
//     goal: null,
//     when: "just now",
//     primary: done?.label ?? "Done",
//     lines,
//   };
// }
//
// const act = (toastId: string, action: string, reason: string | null = null) =>
//   invoke("lane_action", { toastId, action, reason }).catch(() => {});
//
// export function Lane() {
//   const [toast, setToast] = useState<Toast | null>(null);
//   const [rejecting, setRejecting] = useState(false);
//   const [held, setHeld] = useState(false);
//   const [round, setRound] = useState(0);
//   const [leavingId, setLeavingId] = useState<string | null>(null);
//   const ref = useRef<HTMLDivElement>(null);
//
//   useEffect(() => {
//     const un = listen<Toast | null>("genios://lane", (e) => setToast(e.payload));
//     invoke<Toast | null>("lane_current").then(setToast).catch(() => {});
//     return () => void un.then((f) => f());
//   }, []);
//
//   // A new popup starts without the reject reasons open, with its full five seconds.
//   useEffect(() => {
//     setRejecting(false);
//     setHeld(false);
//   }, [toast?.id]);
//
//   // Fit the window to the drop — it grows when a button opens its panel inside the card.
//   useEffect(() => {
//     const el = ref.current;
//     if (!toast || !el) return;
//     // theme.css draws the page at 85% (CSS zoom); the window wants points. An engine that applies the
//     // zoom to rects already returns points; one that does not returns layout pixels to scale.
//     const fit = () => {
//       const visual = el.getBoundingClientRect().height;
//       const zoom = parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
//       const points = Math.abs(visual - el.offsetHeight) < 1 && zoom !== 1 ? el.offsetHeight * zoom : visual;
//       void invoke("lane_resize", { height: Math.ceil(points) + 12 }).catch(() => {});
//     };
//     fit();
//     const ro = new ResizeObserver(fit);
//     ro.observe(el);
//     return () => ro.disconnect();
//   }, [toast, rejecting]);
//
//   if (!toast) return null;
//   const item = toItem(toast);
//   const has = (id: string) => toast.actions.some((a) => a.id === id);
//   const label = (id: string, fallback: string) => toast.actions.find((a) => a.id === id)?.label ?? fallback;
//   const proposal = toast.capability_id === PROPOSAL;
//   // Done, Later, Feedback and × slide the popup away, then report the press.
//   const press = (action: string, reason: string | null = null) => {
//     setLeavingId(toast.id);
//     setTimeout(() => void act(toast.id, action, reason), SLIDE_MS);
//   };
//   const later = toast.actions.filter((a) => a.id in LATER).map((a) => ({ id: a.id, label: a.label ?? LATER[a.id] }));
//   const feedback = toast.actions.filter((a) => a.id in FEEDBACK).map((a) => ({ id: a.id, label: a.label ?? FEEDBACK[a.id] }));
//
//   const actions: DropActions = proposal
//     ? rejecting
//       ? {
//           custom: {
//             buttons: [...REJECT_REASONS.map((r) => ({ id: r, label: r })), { id: "__back", label: "Back" }],
//             onPress: (id) => (id === "__back" ? setRejecting(false) : act(toast.id, REJECT, id)),
//           },
//         }
//       : {
//           custom: {
//             buttons: toast.actions.filter((a) => a.id !== "dismiss").map((a, i) => ({ id: a.id, label: a.label ?? a.id, main: i === 0 })),
//             onPress: (id) => (id === REJECT ? setRejecting(true) : act(toast.id, id)),
//           },
//         }
//     : {
//         primary: () => press(has("done") ? "done" : "dismiss"),
//         later: later.length ? { options: later, onPick: (id) => press(id) } : undefined,
//         feedback: feedback.length
//           ? { reasons: feedback, words: false, onSend: (id) => press(id) }
//           : toast.style === "advice" && toast.capability_id !== DRAFT_REVIEW
//             ? { reasons: [{ id: "wrong", label: label("wrong", "Not right") }], words: false, onSend: () => press("wrong") }
//             : null,
//         feedbackLockedWhy: "This popup takes no feedback.",
//         delegate: { people: [], agents: [], ask: has("delegate") ? () => void act(toast.id, "delegate") : undefined },
//       };
//
//   const showMore = () => {
//     const { icon: _icon, ...shown } = item;
//     void emitTo("main", "genios://show", shown).catch(() => {});
//     void act(toast.id, "open");
//   };
//
//   return (
//     <div
//       ref={ref}
//       onMouseEnter={() => {
//         setHeld(true);
//         void invoke("lane_hover", { hover: true }).catch(() => {});
//       }}
//       onMouseLeave={() => {
//         // Rust starts the five seconds again when the pointer leaves; so does the line.
//         setHeld(false);
//         setRound((r) => r + 1);
//         void invoke("lane_hover", { hover: false }).catch(() => {});
//       }}
//     >
//       <Drop
//         key={toast.id}
//         item={item}
//         actions={actions}
//         leaving={leavingId === toast.id}
//         countdown={proposal ? undefined : { ms: POPUP_MS, held, round }}
//         onShowMore={proposal ? undefined : showMore}
//         onOpen={proposal ? undefined : () => void act(toast.id, "open")}
//         onClose={() => press("dismiss")}
//       />
//     </div>
//   );
// }
```

#### `src/lane/lane.css`

```css
// /* The lane window: one drop at a time, top-right, never focused. The drop's look is menu.css. */
// body.genios-lane {
//   padding: 0 8px 8px;
//   overflow: hidden;
// }
// .genios-lane .drop {
//   animation: lane-drop 0.42s cubic-bezier(0.16, 1, 0.3, 1);
// }
// @keyframes lane-drop {
//   from {
//     transform: translateY(-40px);
//     opacity: 0;
//   }
// }
// .lane-reasons {
//   display: flex;
//   flex-wrap: wrap;
//   gap: 6px;
//   align-items: center;
//   font-size: 12.5px;
//   color: var(--g-white-2);
// }
```

## 4 · Sign-in, the brain's routes, and the shared parts

Device-code sign-in; every call to the brain and to the Rust core; the refusal sentences; the parts and tokens the menu still uses from the older panel.

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

#### `src/desktop/SignIn.tsx`

```tsx
// // Device sign-in (RFC 8628): the app shows a short code, the person approves it on the GeniOS
// // website, and the Rust core receives the tokens. No password or token is ever typed here. The
// // server's address is set only under Advanced: a customer never needs to read it.
// import { useCallback, useEffect, useRef, useState } from "react";
// import { RefreshCw, X } from "lucide-react";
// import {
//   authCancel,
//   authOpenBrowser,
//   authPollStatus,
//   authStart,
//   authState,
//   defaultBaseUrl,
//   onAuthChange,
//   rememberBaseUrl,
//   type AuthState,
// } from "./api";
// import { Button, IconButton, Notice } from "./ui";
// import { CircleAlert } from "lucide-react";
// import "./Header.css";
// import "./screens.css";
//
// export function SignIn({
//   reason,
//   onDone,
//   onClose,
//   advancedOpen = false,
// }: {
//   reason: string | null;
//   onDone: () => void;
//   onClose: () => void;
//   /** Open with the server address showing (the account's "Change server"). */
//   advancedOpen?: boolean;
// }) {
//   const [baseUrl, setBaseUrl] = useState(defaultBaseUrl());
//   const [state, setState] = useState<AuthState>({ status: "signed_out", reason });
//   const [busy, setBusy] = useState(false);
//   const [error, setError] = useState("");
//   const [advanced, setAdvanced] = useState(advancedOpen);
//   const [now, setNow] = useState(Date.now());
//
//   // Sign-in finishes in the Rust core (it polls the server and keeps the session). The screen
//   // follows it four ways, so it can never be left showing a code that was already approved:
//   // the core's auth event, a one-second mirror of its state, the window coming back into view
//   // (a hidden window's timers can stall), and Refresh.
//   const done = useRef(onDone);
//   done.current = onDone;
//   const [checking, setChecking] = useState(false);
//   const [hint, setHint] = useState("");
//   const check = useCallback(async (said = false) => {
//     if (said) setChecking(true);
//     const s = await authState().catch(() => null);
//     if (said) setChecking(false);
//     if (s?.status === "signed_in") return done.current();
//     if (s && s.status !== "signed_out") setState(s);
//     if (said) setHint("Not approved yet. Approve the code on the website, then press Refresh.");
//   }, []);
//
//   useEffect(() => {
//     const un = onAuthChange((s) => s.status === "signed_in" && done.current());
//     const onShow = () => void check();
//     window.addEventListener("focus", onShow);
//     document.addEventListener("visibilitychange", onShow);
//     return () => {
//       void un.then((f) => f());
//       window.removeEventListener("focus", onShow);
//       document.removeEventListener("visibilitychange", onShow);
//     };
//   }, [check]);
//
//   useEffect(() => {
//     if (state.status !== "pending") return;
//     const iv = setInterval(async () => {
//       setNow(Date.now());
//       const s = await authPollStatus().catch(() => null);
//       if (!s) return;
//       if (s.status === "signed_in") done.current();
//       else setState(s);
//     }, 1000);
//     return () => clearInterval(iv);
//   }, [state.status]);
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
//           <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
//             <Button small icon={RefreshCw} disabled={checking} onClick={() => void check(true)}>
//               {checking ? "Checking…" : "I've approved it · Refresh"}
//             </Button>
//             <Button kind="quiet" small onClick={cancel}>
//               Cancel
//             </Button>
//           </div>
//           {hint && <p className="dx-hint">{hint}</p>}
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
// /** Refresh: a fresh screen reader, so an Accessibility grant made in Settings is seen now. */
// export const captureRestartReader = () => invoke<void>("capture_restart_reader");
// /** Fix Accessibility: remove GeniOS's entry (an older build's), ask macOS again, open the pane. */
// export const captureFixAccessibility = () => invoke<void>("capture_fix_accessibility");
// /** The popup's sound: `mac` (the Mac's alert sound), Glass, Pop, Ping, Purr or off. `preview` plays it once. */
// export const laneSound = (choice?: string, preview = false) =>
//   invoke<string>("lane_sound", choice ? { choice, preview } : {});
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
// /** A brain request that has not answered in this long is given up (the next refresh asks again). */
// const REQUEST_TIMEOUT_MS = 20_000;
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
//       signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
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
// export type Agent = { agent_id: string; name?: string | null; description?: string | null; status: string };
//
// export type Member = { id: string; name: string; email: string; role: string; status: string };
//
// /** The team lives behind an org-scoped route (`/api/org/{org}/members`) the desktop session cannot
//  *  address yet; Delegate says so instead of listing a team it cannot see. */
// export function getMembers(): Promise<Member[]> {
//   return Promise.reject(new ApiError(403, "the desktop app does not read the team yet"));
// }
//
// /** The workspace's agents. */
// export function listAgents(): Promise<Agent[]> {
//   return get<{ agents?: Agent[] }>("/v1/agents").then((d) => (d.agents ?? []).filter((a) => a.status === "active"));
// }
//
// // ---- Goals (the GeniOS menu) ----
//
// /** A goal as the brain serves it today: an accepted line of the company brief's goals section. */
// export type BriefGoal = { id: string; name: string };
//
// /** `/v1/company-brief` → its accepted goal lines. Progress, due dates and counts wait for `GET /v1/goals`. */
// export function getBriefGoals(): Promise<BriefGoal[]> {
//   return get<{ lines?: { line_id: string; section: string; text: string }[] }>("/v1/company-brief").then((b) =>
//     (b.lines ?? []).filter((l) => l.section === "goals").map((l) => ({ id: l.line_id, name: l.text })),
//   );
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
// import { ownCard, readCard, sharedLines, sharedTexts, type CardRead } from "../../../src/lib/card-read";
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

## 5 · The website's card reader (shared)

One reader for every screen: the menu reads cards exactly the way the website's Cards page does.

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

## 6 · The older panel (in the code, no longer opened)

Today · This week · History · an opened card. Since 0.3.0 the main window opens the menu instead; nothing here is loaded by the app (checked by following every import from desktop/main.tsx and lane/main.tsx). Kept for reference and for its previews.

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

#### `src/desktop/CardRow.preview.tsx`

```tsx
// // Every open card's face, read from the stand-in brain; presses recorded in window.__rows.
// import { useEffect, useState } from "react";
// import { fillDetails, loadQueue, readOpen, type DeskCard } from "./cards";
// import { CardRow } from "./CardRow";
//
// // One log for every preview on the page: the gallery loads them all.
// const w = window as unknown as { __rows?: string[] };
// const said: string[] = (w.__rows ??= []);
//
// function Faces() {
//   const [cards, setCards] = useState<DeskCard[] | null>(null);
//   useEffect(() => {
//     void (async () => {
//       const loops = await loadQueue();
//       setCards(readOpen(loops, await fillDetails(new Map(), loops.map((l) => l.card_id))));
//     })();
//   }, []);
//   return (
//     <div className="dx-shell" id="faces">
//       <div className="dx-body">
//         <ul className="dx-rows">
//           {(cards ?? []).map((c) => (
//             <CardRow
//               key={c.id}
//               card={c}
//               also={c.id === "c-f26" ? [{ id: "f1", kind: "my_promise", text: "Send Neha the investor deck", who: "Neha Kapoor" }] : []}
//               onOpen={(x) => said.push(`open ${x.id}`)}
//               onDone={(x) => said.push(`done ${x.id}`)}
//             />
//           ))}
//         </ul>
//       </div>
//     </div>
//   );
// }
//
// export const previews = { faces: () => <Faces /> };
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

#### `src/desktop/Header.preview.tsx`

```tsx
// // The top bar, live, with every callback recorded in window.__header for checks/header.mjs.
// import { useState } from "react";
// import type { CaptureStatus } from "./api";
// import { Header, type View } from "./Header";
//
// const said: string[] = [];
// (window as unknown as { __header: string[] }).__header = said;
//
// function Bar({ back, capture }: { back?: boolean; capture: CaptureStatus }) {
//   const [view, setView] = useState<View>("today");
//   const [screenOnly, setScreenOnly] = useState(false);
//   const [state, setState] = useState(capture);
//   return (
//     <div className="dx-shell" id="bar">
//       <Header
//         view={view}
//         onView={(v) => {
//           said.push(`view ${v}`);
//           setView(v);
//         }}
//         back={back ? { label: "Today", onBack: () => said.push("back") } : undefined}
//         capture={state}
//         onPause={(m) => {
//           said.push(`pause ${m}`);
//           setState({ state: "paused", paused_until: new Date(Date.now() + m * 60_000).toISOString() });
//         }}
//         onResume={() => {
//           said.push("resume");
//           setState({ state: "capturing" });
//         }}
//         screenOnly={screenOnly}
//         onScreenOnly={(on) => {
//           said.push(`screen-only ${on}`);
//           setScreenOnly(on);
//         }}
//         refreshing={false}
//         onRefresh={() => said.push("refresh")}
//         onOpenWeb={() => said.push("web")}
//         onSignOut={() => said.push("sign-out")}
//         onClose={() => said.push("close")}
//       />
//       <div className="dx-body" />
//     </div>
//   );
// }
//
// export const previews = {
//   header: () => <Bar capture={{ state: "capturing", reader_available: true, last_thread_title: "Neha Kapoor — WhatsApp" }} />,
//   "header-back": () => <Bar back capture={{ state: "paused", paused_until: new Date(Date.now() + 1_800_000).toISOString() }} />,
// };
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

#### `src/desktop/ScreenRow.preview.tsx`

```tsx
// // The screen's open follow-ups (from the Tauri stand-in), each in the row face; presses recorded.
// import { useEffect, useState } from "react";
// import { followupsOpen, type Followup } from "./api";
// import { ScreenRow } from "./ScreenRow";
//
// // One log for every preview on the page: the gallery loads them all.
// const w = window as unknown as { __rows?: string[] };
// const said: string[] = (w.__rows ??= []);
//
// function Items() {
//   const [items, setItems] = useState<Followup[]>([]);
//   useEffect(() => {
//     void followupsOpen().then(setItems);
//   }, []);
//   return (
//     <div className="dx-shell" id="items">
//       <div className="dx-body">
//         <ul className="dx-rows">
//           {items.map((f) => (
//             <ScreenRow
//               key={f.id}
//               item={f}
//               onDone={(x) => said.push(`done ${x.id}`)}
//               onHandled={(x) => said.push(`handled ${x.id}`)}
//               onTomorrow={(x) => said.push(`tomorrow ${x.id}`)}
//             />
//           ))}
//         </ul>
//       </div>
//     </div>
//   );
// }
//
// export const previews = { "screen-items": () => <Items /> };
```

#### `src/desktop/SetupCard.preview.tsx`

```tsx
// // The setup card over the reading bar, live against the Tauri stand-in (?s= picks the state).
// import { useCapture, CaptureBar, SetupCard } from "./SetupCard";
//
// // A workspace past setup has caught something already; a first run has not.
// const hasItems = ["normal", "busy", "paused"].includes(new URLSearchParams(location.search).get("s") ?? "normal");
//
// function Reading() {
//   const c = useCapture();
//   const setup = Boolean(c.status && ["needs_accessibility", "off_by_policy"].includes(c.status.state));
//   return (
//     <div className="dx-shell" id="reading">
//       <div className="dx-body">
//         <SetupCard status={c.status} hasItems={hasItems} onAccessibility={c.openAccessibility} onTurnOn={c.turnOn} />
//       </div>
//       <CaptureBar
//         status={c.status}
//         error={c.error}
//         setupShowing={setup}
//         onPause={() => c.pause(15)}
//         onResume={c.resume}
//         onSync={c.sync}
//         onAccessibility={c.openAccessibility}
//         onTurnOn={c.turnOn}
//       />
//     </div>
//   );
// }
//
// export const previews = { setup: () => <Reading /> };
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

#### `src/desktop/api.preview.tsx`

```tsx
// // pressCard against the stand-in brain: what each press sends, and what a refusal throws.
// import { useEffect, useState } from "react";
// import { ApiError, pressCard, type CardPress } from "./api";
//
// const PRESSES: [string, CardPress][] = [
//   ["c-evokoa", { action: "wrong", reason: "" }],
//   ["c-f55", { action: "do_it_myself" }],
//   ["c-f22", { action: "do_it_myself" }],
//   ["c-f22", { action: "answer", words: "  " }],
//   ["c-f22", { action: "answer", words: " Yes, incubated at the campus cell since March. " }],
//   ["c-f26", { action: "snooze", snooze: "tomorrow_09" }],
//   ["c-evokoa", { action: "wrong", reason: "bad_timing", words: "the call already happened" }],
// ];
//
// // Once per page: StrictMode runs an effect twice, and a press is not idempotent.
// let run: Promise<string[]> | null = null;
//
// async function pressAll(): Promise<string[]> {
//   const out: string[] = [];
//   for (const [id, press] of PRESSES) {
//     try {
//       const r = await pressCard(id, press);
//       out.push(`${id} ${press.action} ok ${r.state ?? ""}`);
//     } catch (e) {
//       out.push(e instanceof ApiError ? `${id} ${press.action} refused ${e.status} ${e.message}` : `${id} ${press.action} threw ${String(e)}`);
//     }
//   }
//   return out;
// }
//
// function Presses() {
//   const [rows, setRows] = useState<string[] | null>(null);
//   useEffect(() => {
//     run ??= pressAll();
//     void run.then(setRows);
//   }, []);
//   if (!rows) return <p>Pressing…</p>;
//   return (
//     <ol id="presses" style={{ font: "13px -apple-system, sans-serif", background: "#fff", color: "#111", padding: 16 }}>
//       {rows.map((r, i) => (
//         <li key={i}>{r}</li>
//       ))}
//     </ol>
//   );
// }
//
// export const previews = { presses: () => <Presses /> };
```

#### `src/desktop/cards.preview.tsx`

```tsx
// // The reader's output for every open card, as plain rows — what `checks/reads.mjs` asserts on.
// import { useEffect, useState } from "react";
// import { fillDetails, loadQueue, readOpen, type DeskCard } from "./cards";
//
// function ReadDump() {
//   const [cards, setCards] = useState<DeskCard[] | null>(null);
//   useEffect(() => {
//     void (async () => {
//       const loops = await loadQueue();
//       const cache = await fillDetails(new Map(), loops.map((l) => l.card_id));
//       setCards(readOpen(loops, cache));
//     })();
//   }, []);
//   if (!cards) return <p>Reading…</p>;
//   return (
//     <div id="reads" style={{ font: "13px -apple-system, sans-serif", padding: 12, background: "#fff", color: "#111" }}>
//       {cards.map((c) => (
//         <section key={c.id} data-card={c.id} data-lane={c.lane} style={{ marginBottom: 12 }}>
//           <b data-f="headline">{c.headline}</b>
//           <div data-f="who">{[c.who, c.role].filter(Boolean).join(" · ")}</div>
//           <div data-f="todo">{c.todo?.line}</div>
//           <div data-f="due">{c.due}</div>
//           <ul data-f="why">
//             {c.why.map((w, i) => (
//               <li key={i}>
//                 {w.text} · {w.from}
//                 {w.when ? ` · ${w.when}` : ""}
//               </li>
//             ))}
//           </ul>
//           <div data-f="left-out">{c.leftOut}</div>
//           <div data-f="offers">{JSON.stringify(c.offers)}</div>
//         </section>
//       ))}
//     </div>
//   );
// }
//
// export const previews = { reads: () => <ReadDump /> };
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

#### `src/desktop/refusals.test.ts`

```ts
// // node --test Extension/src/desktop/refusals.test.ts
// import { test } from "node:test";
// import assert from "node:assert/strict";
// import { refusalText } from "./refusals.ts";
//
// test("every code the action route sends reads as its own sentence", () => {
//   const codes = [
//     "card_not_actionable", "stale_or_unauthorized_card", "assigned_to_different_seat", "not_offered",
//     "not_a_question", "answer_says_nothing", "answer_too_long", "invalid_wrong_reason", "unknown_action",
//     "invalid_correction", "owner_only", "no_kind_of_work",
//   ];
//   const fallback = refusalText(422, "something_new");
//   for (const code of codes) {
//     const s = refusalText(422, code);
//     assert.notEqual(s, fallback, `${code} falls through to the generic sentence`);
//     assert.match(s, /^[A-Z].*\.$/, `${code}: one sentence`);
//     assert.ok(!s.includes("_"), `${code}: no engine words`);
//   }
// });
//
// test("a press that never arrived, a sign-out, a closed card and a server fault are told apart", () => {
//   assert.match(refusalText(0, "offline"), /reach GeniOS/);
//   assert.match(refusalText(401, "Signed out"), /signed out/);
//   assert.match(refusalText(404, "card not found"), /closed/);
//   assert.match(refusalText(503, "Service Unavailable"), /a minute/);
//   assert.equal(refusalText(403, "assigned_to_different_seat"), "This card is assigned to someone else.");
// });
//
// test("an unknown code never shows the code itself", () => {
//   const s = refusalText(422, "brand_new_code");
//   assert.ok(!s.includes("brand_new_code"));
// });
```

#### `src/desktop/rows.test.ts`

```ts
// // node --test Extension/src/desktop/rows.test.ts
// import { test } from "node:test";
// import assert from "node:assert/strict";
// import { buildGroups, summarize, type Group } from "./rows.ts";
// import type { Followup } from "./api";
// import type { DeskCard } from "./cards";
//
// const NOW = Date.parse("2026-10-22T10:00:00");
// const card = (id: string, lane: DeskCard["lane"], extra: Partial<DeskCard> = {}, node: string | null = null) =>
//   ({ id, lane, answered: false, urgency: "standard", loop: { card_id: id, subject_node_id: node }, ...extra }) as unknown as DeskCard;
// const item = (id: string, extra: Partial<Followup> = {}): Followup => ({ id, kind: "ask", text: id, ...extra });
// const ids = (g: Group) => g.rows.map((r) => r.key);
//
// test("groups come in the order a person works them, empty ones left out", () => {
//   const groups = buildGroups(
//     [card("w", "waiting"), card("q", "question"), card("d1", "decision"), card("d2", "decision")],
//     [item("s1")],
//   );
//   assert.deepEqual(groups.map((g) => g.id), ["decision", "question", "screen", "waiting"]);
//   assert.deepEqual(ids(groups[0]), ["d1", "d2"], "the brain's ranked order is kept");
// });
//
// test("an answered question waits", () => {
//   const groups = buildGroups([card("q", "question", { answered: true })], []);
//   assert.deepEqual(groups.map((g) => g.id), ["waiting"]);
// });
//
// test("a screen item about someone joins the first card on that person, once", () => {
//   const groups = buildGroups(
//     [card("a", "decision", {}, "n26"), card("b", "decision", {}, "n26")],
//     [item("f1", { who: "Neha", subject_node_id: "n26" }), item("f2", { who: null, subject_node_id: "n26" })],
//   );
//   const [decide, screen] = groups;
//   assert.equal(decide.rows[0].kind === "card" && decide.rows[0].also.map((f) => f.id).join(), "f1");
//   assert.equal(decide.rows[1].kind === "card" && decide.rows[1].also.length, 0);
//   assert.deepEqual(ids(screen), ["f2"], "an item that names no one stands on its own");
// });
//
// test("screen items: soonest due first, undated after, newest first among those", () => {
//   const groups = buildGroups([], [
//     item("later", { due_at: "2026-10-30T09:00:00" }),
//     item("old-undated", { created_at: "2026-10-20T09:00:00" }),
//     item("late", { due_at: "2026-10-21T09:00:00" }),
//     item("new-undated", { created_at: "2026-10-22T09:00:00" }),
//   ]);
//   assert.deepEqual(ids(groups[0]), ["late", "later", "new-undated", "old-undated"]);
// });
//
// test("the summary counts what asks something of you, and what is pressing", () => {
//   const groups = buildGroups(
//     [card("d", "decision", { urgency: "high" }), card("q", "question"), card("w", "waiting", { urgency: "critical" })],
//     [item("today", { due_at: "2026-10-22T18:00:00" }), item("next-week", { due_at: "2026-10-29T18:00:00" })],
//   );
//   assert.deepEqual(summarize(groups, NOW), { needYou: 4, urgent: 2 });
// });
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

#### `src/desktop/theme.preview.tsx`

```tsx
// // Every token in use, on its own surface: what checks/tokens.mjs measures in light and dark.
// import "./theme.css";
//
// function Sheet() {
//   return (
//     <div className="dx-shell" id="sheet">
//       <div className="dx-body">
//         <span className="dx-eyebrow">
//           Decide · <b>3</b>
//         </span>
//         <span className="dx-hint">A move is yours, and the evidence holds.</span>
//         <div className="dx-card" style={{ padding: 14, display: "grid", gap: 6 }}>
//           <span className="dx-title" data-t="ink">Confirm the call time with Evokoa</span>
//           <span className="dx-lead">Confirm Thursday 4 pm with Ananya and send the invite.</span>
//           <span className="dx-meta" data-t="mist">Ananya Rao · Evokoa · by 24 Oct</span>
//           <div className="dx-fields">
//             <div className="dx-field">
//               <span>Why</span>
//               <span>The pilot review slips a week.</span>
//             </div>
//             <div className="dx-field muted">
//               <span>Goal</span>
//               <span>Not linked to a goal yet</span>
//             </div>
//           </div>
//           <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
//             <span className="dx-tag">
//               <b>Gmail</b> · mail thread
//             </span>
//             <span className="dx-chip">Admin</span>
//             <span className="dx-status accent">
//               <i /> High
//             </span>
//             <span className="dx-status">
//               <i /> Reading
//             </span>
//             <span className="dx-status quiet">
//               <i /> Paused
//             </span>
//           </div>
//           <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
//             <button className="dx-btn ink">Done</button>
//             <button className="dx-btn line">Later</button>
//             <button className="dx-btn quiet">Feedback</button>
//             <button className="dx-btn link">Open on web</button>
//           </div>
//           <div className="dx-notice">This card is assigned to someone else.</div>
//           <div className="dx-progress">
//             <span style={{ width: "50%" }} />
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// }
//
// export const previews = { tokens: () => <Sheet /> };
```

#### `src/desktop/ui.preview.tsx`

```tsx
// // Every small part, live: what checks/ui.mjs presses and measures.
// import { useState } from "react";
// import { CircleAlert, Clock, Ellipsis, Inbox, LogOut, RefreshCw } from "lucide-react";
// import {
//   Button,
//   Chip,
//   Choice,
//   Empty,
//   Eyebrow,
//   Field,
//   Fields,
//   IconButton,
//   MenuItem,
//   MenuNote,
//   MenuSep,
//   Notice,
//   Popover,
//   Progress,
//   Sheet,
//   Skeleton,
//   Status,
//   Tabs,
//   Tag,
//   Toast,
// } from "./ui";
//
// // The panel's Esc listens on window and leaves an Esc a layer has taken (defaultPrevented).
// const escapes: boolean[] = [];
// window.addEventListener("keydown", (e) => e.key === "Escape" && escapes.push(e.defaultPrevented));
// (window as unknown as { __escapes: boolean[] }).__escapes = escapes;
//
// function Parts() {
//   const [menu, setMenu] = useState(true);
//   const [sheet, setSheet] = useState(false);
//   const [tab, setTab] = useState<"today" | "week" | "history">("today");
//   const [pick, setPick] = useState("bad_timing");
//   return (
//     <div className="dx-shell" id="parts">
//       <div className="dx-body">
//         <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
//           <Tabs
//             label="View"
//             value={tab}
//             onChange={setTab}
//             options={[
//               { id: "today", label: "Today" },
//               { id: "week", label: "This week" },
//               { id: "history", label: "History" },
//             ]}
//           />
//           <Popover
//             label="More"
//             open={menu}
//             onClose={() => setMenu(false)}
//             trigger={<IconButton label="More" icon={Ellipsis} aria-expanded={menu} onClick={() => setMenu((o) => !o)} />}
//           >
//             <MenuItem icon={RefreshCw} kbd="⌘R">
//               Refresh
//             </MenuItem>
//             <MenuItem checked>Only what's on my screen</MenuItem>
//             <MenuSep />
//             <MenuItem icon={LogOut}>Sign out of this Mac…</MenuItem>
//             <MenuNote>Reading pauses while you are away.</MenuNote>
//           </Popover>
//         </div>
//         <Eyebrow count={3}>Decide</Eyebrow>
//         <div className="dx-card" style={{ padding: 14, display: "grid", gap: 8 }}>
//           <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
//             <Tag tool="Gmail" how="mail thread" />
//             <Tag tool="WhatsApp" how="your screen" />
//             <Chip>Admin</Chip>
//             <Status tone="accent">High</Status>
//             <Status tone="quiet">Paused</Status>
//           </div>
//           <Fields>
//             <Field label="Why">The pilot review slips a week.</Field>
//             <Field label="Goal" muted>
//               Not linked to a goal yet
//             </Field>
//           </Fields>
//           <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
//             <Choice on={pick === "bad_timing"} onClick={() => setPick("bad_timing")}>
//               Right card, wrong time
//             </Choice>
//             <Choice on={pick === "wrong_facts"} onClick={() => setPick("wrong_facts")}>
//               A fact is wrong
//             </Choice>
//           </div>
//           <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
//             <Button kind="ink">Done</Button>
//             <Button icon={Clock}>Later</Button>
//             <Button kind="quiet" onClick={() => setSheet(true)}>
//               Feedback
//             </Button>
//             <Button kind="link" small>
//               Open on web
//             </Button>
//             <Button disabled>Delegate</Button>
//           </div>
//           <Notice icon={CircleAlert}>This card is assigned to someone else.</Notice>
//           <Progress value={67} label="Ready" />
//           <Skeleton width="60%" />
//         </div>
//         <Empty icon={Inbox} title="Nothing needs you right now">
//           <p>When GeniOS finds something that needs a decision or an answer, it shows up here.</p>
//         </Empty>
//       </div>
//       <Sheet open={sheet} title="What is off?" onClose={() => setSheet(false)}>
//         <p className="dx-hint">Your words go to GeniOS's reasoning.</p>
//       </Sheet>
//       <Toast action="Undo">Marked done</Toast>
//     </div>
//   );
// }
//
// export const previews = { ui: () => <Parts /> };
```

## 7 · The studio simulator (index.html, not part of the Mac app)

The product-video surface that shares this Vite project.

#### `src/main.tsx`

```tsx
// import { StrictMode } from "react";
// import { createRoot } from "react-dom/client";
// import { App } from "./App";
// import "./styles.css";
//
// createRoot(document.getElementById("root")!).render(
//   <StrictMode>
//     <App />
//   </StrictMode>,
// );
```

#### `src/App.tsx`

```tsx
// import {
//   Activity,
//   AlertTriangle,
//   ArrowLeft,
//   ArrowRight,
//   ArrowUpRight,
//   AtSign,
//   Bell,
//   Bot,
//   BriefcaseBusiness,
//   CalendarDays,
//   Check,
//   CheckCircle2,
//   ChevronDown,
//   ChevronRight,
//   Circle,
//   Clock3,
//   Code2,
//   Command,
//   FileText,
//   Inbox,
//   LayoutPanelLeft,
//   Mail,
//   Menu,
//   MessageSquare,
//   MoreHorizontal,
//   Paperclip,
//   Pause,
//   Play,
//   Plus,
//   Search,
//   Send,
//   ShieldCheck,
//   Sparkles,
//   UserRound,
//   Users,
//   X,
//   Zap,
// } from "lucide-react";
// import { useEffect, useMemo, useState } from "react";
// import { scenarios, toDeliveryObject } from "./scenarios";
// import type {
//   ActionId,
//   DemoScenario,
//   IntelligenceAction,
//   IntelligenceCard,
//   SceneKind,
//   SurfaceMode,
// } from "./types";
//
// const SURFACES: Array<{ id: SurfaceMode; label: string }> = [
//   { id: "popover", label: "Popover" },
//   { id: "sidebar", label: "Sidebar" },
//   { id: "tray", label: "Tray" },
// ];
//
// const typeLabels: Record<IntelligenceCard["type"], string> = {
//   forgotten_commitment: "Forgotten commitment",
//   important_change: "Important change",
//   risk: "Risk",
//   opportunity: "Opportunity",
//   decision_required: "Decision required",
//   recommended_action: "Recommended action",
//   conflict: "Conflict",
//   upcoming_situation: "Upcoming situation",
// };
//
// function confidenceLabel(value: number) {
//   return `${(value / 10000).toFixed(2)} confidence`;
// }
//
// function surfaceLabel(mode: SurfaceMode) {
//   return SURFACES.find((surface) => surface.id === mode)?.label ?? mode;
// }
//
// export function App() {
//   const [scenarioIndex, setScenarioIndex] = useState(0);
//   const [surface, setSurface] = useState<SurfaceMode>(scenarios[0].defaultSurface);
//   const [playing, setPlaying] = useState(false);
//   const [presentation, setPresentation] = useState(false);
//   const [actionView, setActionView] = useState<ActionId | null>(null);
//   const [feedbackOpen, setFeedbackOpen] = useState(false);
//   const [toast, setToast] = useState<string | null>(null);
//   const scenario = scenarios[scenarioIndex];
//
//   const chooseScenario = (index: number) => {
//     const next = scenarios[index];
//     setScenarioIndex(index);
//     setSurface(next.defaultSurface);
//     setActionView(null);
//     setFeedbackOpen(false);
//     setToast(null);
//   };
//
//   const stepScenario = (direction: 1 | -1) => {
//     const next = (scenarioIndex + direction + scenarios.length) % scenarios.length;
//     chooseScenario(next);
//   };
//
//   useEffect(() => {
//     if (!playing) return;
//     const timer = window.setInterval(() => {
//       setScenarioIndex((current) => {
//         const next = (current + 1) % scenarios.length;
//         setSurface(scenarios[next].defaultSurface);
//         setActionView(null);
//         setFeedbackOpen(false);
//         return next;
//       });
//     }, 8000);
//     return () => window.clearInterval(timer);
//   }, [playing]);
//
//   useEffect(() => {
//     const onKeyDown = (event: KeyboardEvent) => {
//       if (event.key >= "1" && event.key <= String(scenarios.length)) {
//         chooseScenario(Number(event.key) - 1);
//       }
//       if (event.key.toLowerCase() === "f") setPresentation((value) => !value);
//       if (event.key === "Escape") {
//         setPresentation(false);
//         setActionView(null);
//         setFeedbackOpen(false);
//       }
//     };
//     window.addEventListener("keydown", onKeyDown);
//     return () => window.removeEventListener("keydown", onKeyDown);
//   });
//
//   useEffect(() => {
//     if (!toast) return;
//     const timer = window.setTimeout(() => setToast(null), 3200);
//     return () => window.clearTimeout(timer);
//   }, [toast]);
//
//   const handleAction = (action: IntelligenceAction) => {
//     if (action.id === "dismiss") {
//       setFeedbackOpen(true);
//       return;
//     }
//     if (action.id === "snooze") {
//       setToast("Queued quietly. GeniOS will re-evaluate the context before showing it again.");
//       setSurface("tray");
//       return;
//     }
//     setActionView(action.id);
//   };
//
//   return (
//     <div className={`app ${presentation ? "is-presentation" : ""}`}>
//       {!presentation && (
//         <StudioBar
//           playing={playing}
//           scenarioIndex={scenarioIndex}
//           surface={surface}
//           onPlay={() => setPlaying((value) => !value)}
//           onStep={stepScenario}
//           onSurface={setSurface}
//           onPresentation={() => setPresentation(true)}
//         />
//       )}
//
//       <main className="stage">
//         <BrowserFrame scenario={scenario}>
//           <IntelligenceSurface
//             actionView={actionView}
//             feedbackOpen={feedbackOpen}
//             scenario={scenario}
//             scenarioIndex={scenarioIndex}
//             surface={surface}
//             onAction={handleAction}
//             onActionClose={() => setActionView(null)}
//             onFeedbackClose={() => setFeedbackOpen(false)}
//             onFeedback={(message) => {
//               setFeedbackOpen(false);
//               setSurface("tray");
//               setToast(message);
//             }}
//             onScenario={chooseScenario}
//             onSurface={setSurface}
//             onToast={setToast}
//           />
//         </BrowserFrame>
//       </main>
//
//       {!presentation && (
//         <ScenarioDock
//           active={scenarioIndex}
//           onChoose={chooseScenario}
//           playing={playing}
//         />
//       )}
//
//       {presentation && (
//         <button className="presentation-exit" onClick={() => setPresentation(false)}>
//           Exit presentation <span>F</span>
//         </button>
//       )}
//
//       {toast && (
//         <div className="toast" role="status">
//           <CheckCircle2 size={16} />
//           <span>{toast}</span>
//         </div>
//       )}
//     </div>
//   );
// }
//
// type StudioBarProps = {
//   playing: boolean;
//   scenarioIndex: number;
//   surface: SurfaceMode;
//   onPlay: () => void;
//   onStep: (direction: 1 | -1) => void;
//   onSurface: (mode: SurfaceMode) => void;
//   onPresentation: () => void;
// };
//
// function StudioBar({
//   playing,
//   scenarioIndex,
//   surface,
//   onPlay,
//   onStep,
//   onSurface,
//   onPresentation,
// }: StudioBarProps) {
//   return (
//     <header className="studio-bar">
//       <div className="studio-identity">
//         <Wordmark />
//         <span className="studio-divider" />
//         <div>
//           <strong>Executive Surface</strong>
//           <span>Local product simulator</span>
//         </div>
//       </div>
//
//       <div className="studio-status">
//         <span className="status-dot" />
//         Simulated intelligence
//         <span className="studio-count">
//           {String(scenarioIndex + 1).padStart(2, "0")} / {String(scenarios.length).padStart(2, "0")}
//         </span>
//       </div>
//
//       <div className="studio-tools">
//         <div className="surface-switcher" aria-label="Surface preview">
//           {SURFACES.map((item) => (
//             <button
//               className={surface === item.id ? "active" : ""}
//               key={item.id}
//               onClick={() => onSurface(item.id)}
//             >
//               {item.label}
//             </button>
//           ))}
//         </div>
//         <button className="icon-button" aria-label="Previous scenario" onClick={() => onStep(-1)}>
//           <ArrowLeft size={15} />
//         </button>
//         <button className="play-button" onClick={onPlay}>
//           {playing ? <Pause size={14} /> : <Play size={14} fill="currentColor" />}
//           {playing ? "Pause" : "Play demo"}
//         </button>
//         <button className="icon-button" aria-label="Next scenario" onClick={() => onStep(1)}>
//           <ArrowRight size={15} />
//         </button>
//         <button className="text-button" onClick={onPresentation}>
//           Present <ArrowUpRight size={13} />
//         </button>
//       </div>
//     </header>
//   );
// }
//
// function ScenarioDock({
//   active,
//   onChoose,
//   playing,
// }: {
//   active: number;
//   onChoose: (index: number) => void;
//   playing: boolean;
// }) {
//   return (
//     <nav className="scenario-dock" aria-label="Demo scenarios">
//       {scenarios.map((scenario, index) => (
//         <button
//           className={active === index ? "active" : ""}
//           key={scenario.id}
//           onClick={() => onChoose(index)}
//         >
//           <span className="scenario-number">{String(index + 1).padStart(2, "0")}</span>
//           <span>
//             <strong>{scenario.label}</strong>
//             <small>{scenario.application}</small>
//           </span>
//           {active === index && <span className={`dock-progress ${playing ? "running" : ""}`} />}
//         </button>
//       ))}
//     </nav>
//   );
// }
//
// function Wordmark({ compact = false }: { compact?: boolean }) {
//   return (
//     <span className={`wordmark ${compact ? "compact" : ""}`} aria-label="GeniOS">
//       <b>G</b>eni<b>OS</b>
//     </span>
//   );
// }
//
// function BrowserFrame({ scenario, children }: { scenario: DemoScenario; children: React.ReactNode }) {
//   return (
//     <section className="browser-frame" aria-label={`${scenario.application} demo scene`}>
//       <div className="browser-titlebar">
//         <div className="traffic-lights" aria-hidden="true">
//           <i />
//           <i />
//           <i />
//         </div>
//         <div className="browser-nav">
//           <ArrowLeft size={14} />
//           <ArrowRight size={14} />
//           <Circle size={13} />
//         </div>
//         <div className="address-bar">
//           <ShieldCheck size={12} />
//           <span>{scenario.url}</span>
//         </div>
//         <div className="browser-actions">
//           <div className="extension-pill">
//             <Zap size={12} fill="currentColor" />
//             <span>{scenarios.length}</span>
//           </div>
//           <MoreHorizontal size={16} />
//         </div>
//       </div>
//       <BrowserScene scenario={scenario} />
//       {children}
//     </section>
//   );
// }
//
// function AppIcon({ scene, size = 17 }: { scene: SceneKind; size?: number }) {
//   if (scene === "gmail") return <Mail size={size} />;
//   if (scene === "crm") return <BriefcaseBusiness size={size} />;
//   if (scene === "calendar") return <CalendarDays size={size} />;
//   return <Code2 size={size} />;
// }
//
// function BrowserScene({ scenario }: { scenario: DemoScenario }) {
//   if (scenario.scene === "gmail") return <GmailScene scenario={scenario} />;
//   if (scenario.scene === "crm") return <CrmScene scenario={scenario} />;
//   if (scenario.scene === "calendar") return <CalendarScene scenario={scenario} />;
//   return <CodeScene scenario={scenario} />;
// }
//
// function SceneHeader({ scenario }: { scenario: DemoScenario }) {
//   return (
//     <div className="scene-header">
//       <div className="scene-app">
//         <span className={`app-mark ${scenario.scene}`}>
//           <AppIcon scene={scenario.scene} size={18} />
//         </span>
//         <strong>{scenario.application}</strong>
//       </div>
//       <div className="scene-search">
//         <Search size={14} />
//         <span>Search {scenario.application}</span>
//       </div>
//       <div className="scene-user">
//         <Bell size={16} />
//         <span>RS</span>
//       </div>
//     </div>
//   );
// }
//
// function GmailScene({ scenario }: { scenario: DemoScenario }) {
//   const data = scenario.sceneData;
//   return (
//     <div className="scene gmail-scene">
//       <SceneHeader scenario={scenario} />
//       <aside className="scene-sidebar">
//         <button className="compose-button"><Plus size={16} /> Compose</button>
//         <SceneNav icon={<Inbox size={15} />} label="Inbox" count="12" active />
//         <SceneNav icon={<Clock3 size={15} />} label="Snoozed" />
//         <SceneNav icon={<Send size={15} />} label="Sent" />
//         <SceneNav icon={<FileText size={15} />} label="Drafts" count="3" />
//         <div className="nav-section-label">Labels</div>
//         <SceneNav icon={<Circle size={8} fill="currentColor" />} label="Investors" />
//         <SceneNav icon={<Circle size={8} fill="currentColor" />} label="Customers" />
//       </aside>
//       <div className="mail-list">
//         <div className="mail-list-tools">
//           <span><Check size={13} /></span>
//           <span><ChevronDown size={12} /></span>
//           <span><Circle size={12} /></span>
//           <small>1–24 of 24</small>
//         </div>
//         {[
//           ["314 Capital", "Re: GeniOS — Q2 progress and next steps", "12 Apr", true],
//           ["Maya · Northstar", "Quarterly review — final agenda", "10:42", false],
//           ["Priya Shah", "NeonFund renewal plan and open owners", "09:18", false],
//           ["Notion", "Your workspace summary is ready", "Yesterday", false],
//           ["Linear", "6 issues moved to In review", "Yesterday", false],
//         ].map(([sender, subject, time, active]) => (
//           <div className={`mail-row ${active ? "active" : ""}`} key={String(sender)}>
//             <span className="mail-avatar">{String(sender).slice(0, 1)}</span>
//             <span className="mail-copy">
//               <strong>{sender}</strong>
//               <span>{subject}</span>
//             </span>
//             <time>{time}</time>
//           </div>
//         ))}
//       </div>
//       <article className="mail-reader">
//         <div className="reader-toolbar">
//           <ArrowLeft size={15} />
//           <span />
//           <MoreHorizontal size={16} />
//         </div>
//         <div className="reader-content">
//           <div className="reader-label">Investors</div>
//           <h1>{data.subject}</h1>
//           <div className="sender-line">
//             <span className="contact-avatar">{data.avatar}</span>
//             <div><strong>{data.contact}</strong><small>to me</small></div>
//             <time>12 Apr, 16:20</time>
//           </div>
//           <p>Rohit — great speaking today. The intelligence layer you’re building is an interesting direction.</p>
//           <p>{data.preview}</p>
//           <p>Looking forward to the next update.</p>
//           <p className="mail-signoff">Best,<br />Maya</p>
//           <div className="reply-box"><span>Reply</span><Paperclip size={15} /></div>
//         </div>
//       </article>
//     </div>
//   );
// }
//
// function SceneNav({
//   icon,
//   label,
//   count,
//   active = false,
// }: {
//   icon: React.ReactNode;
//   label: string;
//   count?: string;
//   active?: boolean;
// }) {
//   return (
//     <div className={`scene-nav ${active ? "active" : ""}`}>
//       {icon}<span>{label}</span>{count && <small>{count}</small>}
//     </div>
//   );
// }
//
// function CrmScene({ scenario }: { scenario: DemoScenario }) {
//   const data = scenario.sceneData;
//   return (
//     <div className="scene crm-scene">
//       <SceneHeader scenario={scenario} />
//       <aside className="scene-sidebar crm-nav">
//         <div className="nav-section-label">Workspace</div>
//         <SceneNav icon={<Activity size={15} />} label="Overview" />
//         <SceneNav icon={<BriefcaseBusiness size={15} />} label="Companies" active />
//         <SceneNav icon={<UserRound size={15} />} label="Contacts" />
//         <SceneNav icon={<Inbox size={15} />} label="Deals" count="18" />
//         <div className="nav-section-label">Revenue</div>
//         <SceneNav icon={<Activity size={15} />} label="Forecast" />
//         <SceneNav icon={<FileText size={15} />} label="Reports" />
//       </aside>
//       <main className="crm-main">
//         <div className="crumbs">Companies <ChevronRight size={12} /> {data.accountName}</div>
//         <div className="account-heading">
//           <span className="account-logo">A</span>
//           <div><h1>{data.accountName}</h1><p>{data.accountMeta}</p></div>
//           <span className="risk-chip"><AlertTriangle size={12} /> Renewal at risk</span>
//           <button>Actions <ChevronDown size={12} /></button>
//         </div>
//         <div className="metric-grid">
//           {data.supporting.map((item) => (
//             <div className="crm-metric" key={item.label}>
//               <span>{item.label}</span><strong>{item.value}</strong>
//             </div>
//           ))}
//           <div className="crm-metric"><span>Owner</span><strong>Priya Shah</strong></div>
//         </div>
//         <div className="crm-columns">
//           <section className="crm-panel">
//             <header><strong>Account activity</strong><button>All activity <ChevronDown size={12} /></button></header>
//             <div className="activity-item danger"><span /><div><strong>Priority support ticket breached SLA</strong><p>Permissions issue remains unresolved</p><small>2 days ago · Intercom</small></div></div>
//             <div className="activity-item"><span /><div><strong>Renewal email opened</strong><p>No reply received</p><small>6 days ago · Gmail</small></div></div>
//             <div className="activity-item"><span /><div><strong>Champion changed role</strong><p>Elena Torres moved to Platform Operations</p><small>12 days ago · CRM</small></div></div>
//           </section>
//           <section className="crm-panel compact-panel">
//             <header><strong>Renewal plan</strong></header>
//             <div className="plan-row"><CheckCircle2 size={14} /><span>Usage review complete</span></div>
//             <div className="plan-row open"><Circle size={14} /><span>Resolve support blockers</span></div>
//             <div className="plan-row open"><Circle size={14} /><span>Map economic buyer</span></div>
//             <div className="plan-row open"><Circle size={14} /><span>Confirm commercial path</span></div>
//           </section>
//         </div>
//       </main>
//     </div>
//   );
// }
//
// function CalendarScene({ scenario }: { scenario: DemoScenario }) {
//   const data = scenario.sceneData;
//   const times = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"];
//   return (
//     <div className="scene calendar-scene">
//       <SceneHeader scenario={scenario} />
//       <aside className="scene-sidebar calendar-nav">
//         <button className="compose-button"><Plus size={16} /> Create</button>
//         <div className="mini-month">
//           <strong>August 2026</strong>
//           <div className="month-grid month-labels">{["M", "T", "W", "T", "F", "S", "S"].map((day, i) => <span key={`${day}-${i}`}>{day}</span>)}</div>
//           <div className="month-grid">{Array.from({ length: 28 }, (_, i) => <span className={i === 8 ? "today" : ""} key={i}>{i + 1}</span>)}</div>
//         </div>
//         <div className="nav-section-label">My calendars</div>
//         <SceneNav icon={<Circle size={8} fill="currentColor" />} label="Rohit" active />
//         <SceneNav icon={<Circle size={8} fill="currentColor" />} label="Company" />
//         <SceneNav icon={<Circle size={8} fill="currentColor" />} label="Design partners" />
//       </aside>
//       <main className="calendar-main">
//         <div className="calendar-toolbar"><h1>Sunday, 9 August</h1><div><button>Today</button><button><ChevronDown size={12} /> Day</button></div></div>
//         <div className="day-grid">
//           {times.map((time) => <div className="time-row" key={time}><time>{time}</time><span /></div>)}
//           <div className="calendar-event muted-event"><small>10:00</small><strong>Product standup</strong><span>Team</span></div>
//           <div className="calendar-event active-event"><small>14:30 · 45 min</small><strong>{data.subject}</strong><span>{data.contact}</span><em>{data.status}</em></div>
//           <div className="calendar-now"><span>14:06</span><i /></div>
//         </div>
//       </main>
//     </div>
//   );
// }
//
// function CodeScene({ scenario }: { scenario: DemoScenario }) {
//   return (
//     <div className="scene code-scene">
//       <div className="code-rail">
//         <div className="code-mark"><Code2 size={18} /></div>
//         <FileText size={19} className="active" />
//         <Search size={19} />
//         <Activity size={19} />
//         <BriefcaseBusiness size={19} />
//       </div>
//       <aside className="file-tree">
//         <div className="file-title">EXPLORER <MoreHorizontal size={14} /></div>
//         <div className="repo-name"><ChevronDown size={12} /> GENIOS-API</div>
//         <div className="tree-row folder"><ChevronDown size={12} /> src</div>
//         <div className="tree-row folder indent"><ChevronDown size={12} /> auth</div>
//         <div className="tree-row indent-2 active"><FileText size={12} /> scope-policy.ts</div>
//         <div className="tree-row indent-2"><FileText size={12} /> oauth-client.ts</div>
//         <div className="tree-row folder indent"><ChevronRight size={12} /> delivery</div>
//         <div className="tree-row folder indent"><ChevronRight size={12} /> tests</div>
//         <div className="tree-row"><FileText size={12} /> package.json</div>
//         <div className="code-focus"><span className="status-dot" /><div><strong>Focus mode</strong><small>38 min remaining</small></div></div>
//       </aside>
//       <main className="editor-area">
//         <div className="editor-tabs"><span className="active"><FileText size={12} /> scope-policy.ts <X size={11} /></span><span><FileText size={12} /> oauth-client.ts</span></div>
//         <div className="editor-breadcrumbs">src <ChevronRight size={11} /> auth <ChevronRight size={11} /> scope-policy.ts</div>
//         <pre className="code-content" aria-label="Code editor preview"><code>{`import { policy } from "../governance";
//
// export function validateWorkspaceScope(
//   requestedScopes: string[],
//   environment: Environment,
// ) {
//   const required = policy.for(environment);
//
//   if (environment === "production") {
//     return requestedScopes.every((scope) =>
//       required.includes(scope),
//     );
//   }
//
//   return true;
// }
//
// export const releaseGate = {
//   check: validateWorkspaceScope,
//   // PR #284 changes the required assertion
//   requiredScope: "read:workspace",
// };`}</code></pre>
//         <div className="code-statusbar"><span>main*</span><span>Ln 21, Col 3</span><span>TypeScript</span><span>UTF-8</span></div>
//       </main>
//       <div className="code-top-meta"><span>PR #284</span><span>41 / 42 checks</span><span>{scenario.sceneData.status}</span></div>
//     </div>
//   );
// }
//
// type IntelligenceSurfaceProps = {
//   actionView: ActionId | null;
//   feedbackOpen: boolean;
//   scenario: DemoScenario;
//   scenarioIndex: number;
//   surface: SurfaceMode;
//   onAction: (action: IntelligenceAction) => void;
//   onActionClose: () => void;
//   onFeedbackClose: () => void;
//   onFeedback: (message: string) => void;
//   onScenario: (index: number) => void;
//   onSurface: (surface: SurfaceMode) => void;
//   onToast: (message: string) => void;
// };
//
// function IntelligenceSurface({
//   actionView,
//   feedbackOpen,
//   scenario,
//   scenarioIndex,
//   surface,
//   onAction,
//   onActionClose,
//   onFeedbackClose,
//   onFeedback,
//   onScenario,
//   onSurface,
//   onToast,
// }: IntelligenceSurfaceProps) {
//   return (
//     <>
//       <button
//         className={`tray-trigger ${surface === "tray" ? "active" : ""}`}
//         aria-label="Open GeniOS intelligence tray"
//         onClick={() => onSurface(surface === "tray" ? scenario.defaultSurface : "tray")}
//       >
//         <Zap size={18} fill="currentColor" />
//         <span>{scenarios.length}</span>
//       </button>
//
//       {surface === "popover" && (
//         <IntelligencePanel
//           card={scenario.card}
//           variant="popover"
//           onAction={onAction}
//           onClose={() => onSurface("tray")}
//         />
//       )}
//
//       {surface === "sidebar" && (
//         <IntelligencePanel
//           card={scenario.card}
//           variant="sidebar"
//           onAction={onAction}
//           onClose={() => onSurface("tray")}
//         />
//       )}
//
//       {surface === "tray" && (
//         <IntelligenceTray
//           active={scenarioIndex}
//           onClose={() => onSurface(scenario.defaultSurface)}
//           onOpen={(index) => {
//             onScenario(index);
//             onSurface(scenarios[index].defaultSurface);
//           }}
//         />
//       )}
//
//       {actionView && (
//         <ActionPreview
//           action={actionView}
//           scenario={scenario}
//           onClose={onActionClose}
//           onComplete={(message) => {
//             onActionClose();
//             onToast(message);
//           }}
//         />
//       )}
//
//       {feedbackOpen && (
//         <DismissDialog
//           onClose={onFeedbackClose}
//           onFeedback={onFeedback}
//         />
//       )}
//     </>
//   );
// }
//
// function IntelligencePanel({
//   card,
//   variant,
//   onAction,
//   onClose,
// }: {
//   card: IntelligenceCard;
//   variant: "popover" | "sidebar";
//   onAction: (action: IntelligenceAction) => void;
//   onClose: () => void;
// }) {
//   const [evidenceOpen, setEvidenceOpen] = useState(false);
//   const delivery = card.deliveryContext;
//   const isDeferred = delivery.gateVerdict === "DEFER";
//   const primaryActions = card.suggestedActions.slice(0, variant === "sidebar" ? 2 : 2);
//
//   return (
//     <aside className={`intelligence-panel ${variant}`} aria-label="GeniOS intelligence">
//       <header className="intelligence-header">
//         <div className="intelligence-brand"><Wordmark compact /><span><i /> Live context</span></div>
//         <div className="panel-controls">
//           <button aria-label="More options"><MoreHorizontal size={17} /></button>
//           <button aria-label="Close" onClick={onClose}><X size={16} /></button>
//         </div>
//       </header>
//
//       <div className="intelligence-body">
//         <div className="card-meta-row">
//           <span className={`priority-mark ${card.priority}`}><i />{typeLabels[card.type]}</span>
//           <span>{confidenceLabel(card.confidenceBp)}</span>
//         </div>
//
//         <h2>{card.title}</h2>
//         <p className="card-summary">{card.summary}</p>
//
//         <div className={`why-now ${isDeferred ? "deferred" : ""}`}>
//           {isDeferred ? <Clock3 size={14} /> : <Sparkles size={14} />}
//           <div>
//             <strong>{isDeferred ? "Queued, not interrupted" : "Why you’re seeing this now"}</strong>
//             <span>{isDeferred ? delivery.notBefore : delivery.reason}</span>
//           </div>
//         </div>
//
//         {variant === "sidebar" && (
//           <div className="context-strip">
//             <span>Current context</span>
//             <strong>{delivery.entity}</strong>
//             <small>{delivery.application} · {delivery.location}</small>
//           </div>
//         )}
//
//         <section className="why-section">
//           <div className="micro-heading">Why this matters</div>
//           <ul>
//             {card.whyItMatters.map((reason) => <li key={reason}><Check size={12} />{reason}</li>)}
//           </ul>
//         </section>
//
//         <section className="recommendation-box">
//           <div className="micro-heading">Recommended</div>
//           <p>{card.recommendation}</p>
//           <div className="recommendation-meta"><Clock3 size={12} /> {card.urgency} <span /> Deadline {card.deadline}</div>
//         </section>
//
//         <button className="evidence-toggle" onClick={() => setEvidenceOpen((value) => !value)}>
//           <span><ShieldCheck size={14} /> Evidence from {card.sourceContext.length} sources</span>
//           <ChevronDown size={14} className={evidenceOpen ? "rotate" : ""} />
//         </button>
//
//         {evidenceOpen && (
//           <div className="evidence-list">
//             {card.evidence.map((evidence) => (
//               <div key={evidence.label}>
//                 <span className="evidence-source">{evidence.source}</span>
//                 <strong>{evidence.label}</strong>
//                 <p>{evidence.value}</p>
//                 <time>{evidence.observedAt}</time>
//               </div>
//             ))}
//             <p className="consequence"><AlertTriangle size={13} /> If ignored: {card.doNothingConsequence}</p>
//           </div>
//         )}
//
//         <div className="suggested-actions">
//           {primaryActions.map((action) => (
//             <button
//               className={action.emphasis === "primary" ? "primary" : "secondary"}
//               key={action.id}
//               onClick={() => onAction(action)}
//             >
//               {action.id === "view_advice" ? <Sparkles size={14} /> : action.id.includes("agent") ? <Bot size={14} /> : <ArrowUpRight size={14} />}
//               {action.label}
//             </button>
//           ))}
//         </div>
//
//         <div className="quiet-actions">
//           {card.availableActions.slice(0, 5).map((action) => (
//             <button key={action.id} onClick={() => onAction(action)}>{action.label}</button>
//           ))}
//         </div>
//       </div>
//
//       <footer className="intelligence-footer">
//         <span><ShieldCheck size={12} /> {card.visibility} evidence</span>
//         <span>Trace {card.traceId.replace("tr_", "")}</span>
//       </footer>
//     </aside>
//   );
// }
//
// function IntelligenceTray({
//   active,
//   onClose,
//   onOpen,
// }: {
//   active: number;
//   onClose: () => void;
//   onOpen: (index: number) => void;
// }) {
//   const deferredCount = scenarios.filter((item) => item.card.deliveryContext.gateVerdict === "DEFER").length;
//   return (
//     <aside className="intelligence-tray" aria-label="GeniOS intelligence tray">
//       <header className="tray-header">
//         <div><Wordmark compact /><span>Intelligence tray</span></div>
//         <button onClick={onClose} aria-label="Close tray"><X size={16} /></button>
//       </header>
//       <div className="tray-title">
//         <div><span className="micro-heading">Today</span><h2>{scenarios.length} things worth your attention</h2></div>
//         <span className="tray-quiet"><Clock3 size={12} /> {deferredCount} queued quietly</span>
//       </div>
//       <div className="tray-list">
//         {scenarios.map((scenario, index) => {
//           const card = scenario.card;
//           const deferred = card.deliveryContext.gateVerdict === "DEFER";
//           return (
//             <button className={active === index ? "active" : ""} key={scenario.id} onClick={() => onOpen(index)}>
//               <span className={`tray-item-icon ${card.priority}`}><AppIcon scene={scenario.scene} size={15} /></span>
//               <span className="tray-item-copy">
//                 <small>{card.domain} · {confidenceLabel(card.confidenceBp)}</small>
//                 <strong>{card.title}</strong>
//                 <span>{deferred ? card.deliveryContext.notBefore : card.recommendation}</span>
//               </span>
//               <span className="tray-item-state">{deferred ? "Queued" : card.urgency}<ChevronRight size={13} /></span>
//             </button>
//           );
//         })}
//       </div>
//       <footer className="tray-footer">
//         <span><ShieldCheck size={13} /> Ranked by business value, not recency</span>
//         <button>Delivery preferences</button>
//       </footer>
//     </aside>
//   );
// }
//
// function ActionPreview({
//   action,
//   scenario,
//   onClose,
//   onComplete,
// }: {
//   action: ActionId;
//   scenario: DemoScenario;
//   onClose: () => void;
//   onComplete: (message: string) => void;
// }) {
//   const card = scenario.card;
//   const isAdvice = action === "view_advice";
//   const isAgent = action === "delegate_agent";
//   const isHuman = action === "delegate_human";
//   const isSchedule = action === "schedule" || action === "book_call" || action === "review_change";
//
//   let title = "Action prepared";
//   let subtitle = "GeniOS has prepared the next step without executing it.";
//   if (isAdvice) {
//     title = "What GeniOS advises";
//     subtitle = "A context-specific course of action grounded in the evidence available now.";
//   } else if (isAgent) {
//     title = "Agent task ready";
//     subtitle = "The agent receives scoped context; sending still requires your approval.";
//   } else if (isHuman) {
//     title = "Human handoff ready";
//     subtitle = "Ownership, evidence, and the expected outcome travel together.";
//   } else if (isSchedule) {
//     title = "Choose the execution window";
//     subtitle = "Scheduling changes delivery timing, not company knowledge.";
//   }
//
//   return (
//     <div className="action-scrim" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
//       <section className="action-preview" role="dialog" aria-modal="true" aria-label={title}>
//         <header>
//           <div className="action-status">{isAdvice ? <Sparkles size={16} /> : <CheckCircle2 size={16} />}<span>{isAdvice ? "Contextual advice · Evidence-backed" : "Prepared · Approval required"}</span></div>
//           <button onClick={onClose} aria-label="Close action preview"><X size={16} /></button>
//         </header>
//         <div className="action-heading"><span className="micro-heading">Next action</span><h2>{title}</h2><p>{subtitle}</p></div>
//
//         {isAdvice && (
//           <div className="advice-preview">
//             <div className="advice-context"><span>Situation</span><strong>{card.situation}</strong><small>{confidenceLabel(card.confidenceBp)} · {card.urgency}</small></div>
//             <div className="advice-steps">
//               {card.advice.steps.map((step, index) => (
//                 <div key={step}><span>{String(index + 1).padStart(2, "0")}</span><p>{step}</p></div>
//               ))}
//             </div>
//             <div className="advice-avoid"><AlertTriangle size={14} /><span><strong>Avoid</strong>{card.advice.avoid}</span></div>
//             <div className="source-note"><ShieldCheck size={13} /> Advice only. GeniOS has not drafted, sent, assigned, or executed anything.</div>
//           </div>
//         )}
//
//         {(isAgent || isHuman) && (
//           <div className="task-preview">
//             <div className="task-owner"><span className="agent-avatar">{isAgent ? <Bot size={18} /> : "PS"}</span><div><small>{isAgent ? "Suggested agent" : "Suggested owner"}</small><strong>{isAgent ? card.agentName : "Priya Shah"}</strong></div><span className="permission-chip">Scoped</span></div>
//             <div className="task-grid">
//               <div><span>Objective</span><strong>{card.recommendation}</strong></div>
//               <div><span>Evidence</span><strong>{card.sourceContext.length} approved sources</strong></div>
//               <div><span>Deadline</span><strong>{card.deadline}</strong></div>
//               <div><span>Approval</span><strong>Required before external action</strong></div>
//             </div>
//             <div className="task-constraint"><ShieldCheck size={14} /><span><strong>Boundary</strong>The assignee can prepare work, but cannot send, discount, or widen source access.</span></div>
//           </div>
//         )}
//
//         {isSchedule && (
//           <div className="schedule-options">
//             {["In 30 minutes", "Today at 16:00", "Tomorrow at 10:00"].map((time, index) => (
//               <button className={index === 0 ? "active" : ""} key={time}><Clock3 size={15} /><span><strong>{time}</strong><small>{index === 0 ? "Best context fit" : "GeniOS will revalidate before delivery"}</small></span>{index === 0 && <Check size={14} />}</button>
//             ))}
//           </div>
//         )}
//
//         {!isAdvice && !isAgent && !isHuman && !isSchedule && (
//           <div className="task-preview">
//             <div className="task-constraint"><UserRound size={14} /><span><strong>Assigned to you</strong>GeniOS will monitor the outcome and stop reminding you when a success event is observed.</span></div>
//           </div>
//         )}
//
//         <footer>
//           <button className="cancel-action" onClick={onClose}>Cancel</button>
//           <button className="confirm-action" onClick={() => onComplete(isAdvice ? "Advice acknowledged. No action was executed." : "Action accepted. GeniOS will track the outcome.")}>
//             {isAdvice ? "Understood" : isAgent || isHuman ? "Approve handoff" : isSchedule ? "Confirm time" : "Mark as mine"}
//             <ArrowRight size={14} />
//           </button>
//         </footer>
//       </section>
//     </div>
//   );
// }
//
// function DismissDialog({
//   onClose,
//   onFeedback,
// }: {
//   onClose: () => void;
//   onFeedback: (message: string) => void;
// }) {
//   const options = [
//     ["Already handled", "GeniOS will look for the completion signal."],
//     ["Not relevant", "This will inform future relevance checks."],
//     ["Wrong assumption", "Flag the evidence chain for review."],
//     ["Don’t remind me", "Suppress this specific recommendation."],
//   ];
//   return (
//     <div className="action-scrim" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
//       <section className="dismiss-dialog" role="dialog" aria-modal="true" aria-label="Dismiss intelligence">
//         <header><div><span className="micro-heading">Feedback</span><h2>What should GeniOS learn?</h2></div><button onClick={onClose}><X size={16} /></button></header>
//         <p>Dismissal has meaning. Choose the closest reason so future delivery gets quieter and more useful.</p>
//         <div className="dismiss-options">
//           {options.map(([label, detail]) => (
//             <button key={label} onClick={() => onFeedback(`${label} recorded as feedback. This insight moved to the tray.`)}>
//               <span><strong>{label}</strong><small>{detail}</small></span><ChevronRight size={14} />
//             </button>
//           ))}
//         </div>
//       </section>
//     </div>
//   );
// }
//
// export function ContractInspector({ scenario }: { scenario: DemoScenario }) {
//   const delivery = useMemo(() => toDeliveryObject(scenario), [scenario]);
//   return <pre>{JSON.stringify(delivery, null, 2)}</pre>;
// }
```

#### `src/scenarios.ts`

```ts
// import type { DemoScenario, DeliveryObject } from "./types";
//
// export const scenarios: DemoScenario[] = [
//   {
//     id: "apex-inbound",
//     label: "High-fit inbound",
//     scene: "gmail",
//     application: "Gmail",
//     url: "mail.google.com/mail/u/0/#inbox/apex-labs",
//     defaultSurface: "popover",
//     trigger: "Opened a new enterprise enquiry from Apex Labs",
//     sceneData: {
//       accountName: "Apex Labs",
//       accountMeta: "Inbound · Enterprise",
//       subject: "Enterprise plan and rollout timeline",
//       preview: "We are evaluating GeniOS for our revenue and support teams. Could we review deployment and pricing this week?",
//       contact: "Nina Kapoor",
//       avatar: "NK",
//       status: "Replied 19 minutes ago",
//       supporting: [
//         { label: "Fit", value: "Top 8%" },
//         { label: "Intent", value: "High" },
//         { label: "Potential", value: "$72k ARR" },
//       ],
//     },
//     card: {
//       schemaVersion: "intelligence-card.v1",
//       id: "intel_sales_apex_priority",
//       traceId: "tr_sales_apex_019",
//       orgId: "genios_demo",
//       visibility: "org",
//       type: "opportunity",
//       priority: "high",
//       domain: "Sales",
//       title: "Apex Labs should be first in today’s queue",
//       summary: "This inbound account matches your strongest enterprise customers and is showing unusually high buying intent.",
//       situation: "High-fit enterprise lead waiting for a first response",
//       whyItMatters: [
//         "Company profile matches 4 of your 5 highest-LTV customers",
//         "Pricing and security pages were viewed twice",
//         "A deployment conversation was requested this week",
//       ],
//       evidence: [
//         { label: "Customer fit", value: "Enterprise SaaS, 180 employees, multi-team use case", source: "CRM", observedAt: "Now" },
//         { label: "Buying intent", value: "Pricing and security pages viewed twice", source: "Website", observedAt: "Today" },
//         { label: "Direct request", value: "Asked to review deployment and pricing this week", source: "Gmail", observedAt: "19 min ago" },
//       ],
//       recommendation: "Reply within two hours and lead with the multi-team rollout path, not a generic product tour.",
//       advice: {
//         steps: [
//           "Prioritize Apex ahead of lower-fit inbound leads today.",
//           "Frame the first conversation around revenue and support workflows across teams.",
//           "Confirm decision process, security owner, and target rollout date on the first call.",
//         ],
//         avoid: "Do not send the standard self-serve sequence; the account is showing enterprise buying behavior.",
//       },
//       doNothingConsequence: "A high-intent account may cool while it is actively comparing alternatives.",
//       confidenceBp: 8900,
//       urgency: "Within 2 hours",
//       deadline: "Today, 13:00",
//       agentName: "Hermes Agent",
//       suggestedActions: [
//         { id: "view_advice", label: "View advice", emphasis: "primary" },
//         { id: "delegate_agent", label: "Assign to Hermes Agent", emphasis: "secondary" },
//       ],
//       availableActions: [
//         { id: "do_myself", label: "Take ownership" },
//         { id: "schedule", label: "Schedule" },
//         { id: "snooze", label: "Snooze" },
//         { id: "dismiss", label: "Dismiss" },
//       ],
//       deliveryContext: {
//         application: "Gmail",
//         location: "Apex Labs enquiry",
//         entity: "Apex Labs",
//         reason: "You opened the new enquiry while the response window is still strong.",
//         contextFitBp: 9600,
//         interruptionCostBp: 900,
//         gateVerdict: "SEND",
//       },
//       expiration: "Today, 17:00",
//       sourceContext: [
//         { source: "Gmail", detail: "Enterprise enquiry", access: "participants" },
//         { source: "CRM", detail: "Account fit and ownership", access: "org" },
//         { source: "Website", detail: "Account-level intent", access: "org" },
//       ],
//     },
//   },
//   {
//     id: "globex-deal-risk",
//     label: "Deal cooling",
//     scene: "crm",
//     application: "CRM",
//     url: "app.hubspot.com/contacts/47120/deal/globex",
//     defaultSurface: "sidebar",
//     trigger: "Opened the Globex opportunity record",
//     sceneData: {
//       accountName: "Globex Corporation",
//       accountMeta: "Enterprise · $96k pipeline",
//       subject: "Security review and commercial proposal",
//       preview: "The proposal has been viewed three times, but the agreed security follow-up did not happen and procurement is still unmapped.",
//       contact: "Daniel Wu",
//       avatar: "DW",
//       status: "No reply in 11 days",
//       supporting: [
//         { label: "Stage", value: "Proposal" },
//         { label: "Close date", value: "28 Aug" },
//         { label: "Health", value: "58 / 100" },
//       ],
//     },
//     card: {
//       schemaVersion: "intelligence-card.v1",
//       id: "intel_sales_globex_cooling",
//       traceId: "tr_sales_globex_011",
//       orgId: "genios_demo",
//       visibility: "org",
//       type: "risk",
//       priority: "critical",
//       domain: "Sales",
//       title: "Globex is cooling after the proposal",
//       summary: "The proposal is being reviewed, but momentum has stalled because the promised security follow-up and procurement mapping are missing.",
//       situation: "$96k opportunity stalled at proposal stage",
//       whyItMatters: [
//         "Proposal opened three times without a reply",
//         "The agreed security follow-up is six days overdue",
//         "No procurement stakeholder is mapped",
//       ],
//       evidence: [
//         { label: "Engagement", value: "Proposal viewed three times by two stakeholders", source: "CRM", observedAt: "4 days" },
//         { label: "Commitment", value: "Security follow-up promised for 3 Aug", source: "Gmail", observedAt: "6 days overdue" },
//         { label: "Buying process", value: "Procurement owner is still unknown", source: "CRM", observedAt: "Now" },
//       ],
//       recommendation: "Re-open the deal around the missing security decision and map procurement before discussing price.",
//       advice: {
//         steps: [
//           "Acknowledge the missed security follow-up and close that gap first.",
//           "Ask the champion to identify procurement and the final security approver.",
//           "Reset the close plan with named owners and dates before revising commercials.",
//         ],
//         avoid: "Do not use a generic ‘just checking in’ message or offer a discount before the buying process is clear.",
//       },
//       doNothingConsequence: "The deal may slip silently while forecast confidence remains overstated.",
//       confidenceBp: 8400,
//       urgency: "Today",
//       deadline: "Today, 16:00",
//       agentName: "Hermes Agent",
//       suggestedActions: [
//         { id: "view_advice", label: "View advice", emphasis: "primary" },
//         { id: "delegate_agent", label: "Assign to Hermes Agent", emphasis: "secondary" },
//       ],
//       availableActions: [
//         { id: "open_crm", label: "Open close plan" },
//         { id: "do_myself", label: "Take ownership" },
//         { id: "snooze", label: "Snooze" },
//         { id: "dismiss", label: "Dismiss" },
//       ],
//       deliveryContext: {
//         application: "CRM",
//         location: "Globex opportunity",
//         entity: "Globex Corporation",
//         reason: "The opportunity record is open and the unresolved decision path is visible.",
//         contextFitBp: 9400,
//         interruptionCostBp: 1200,
//         gateVerdict: "SEND",
//       },
//       expiration: "Tomorrow, 12:00",
//       sourceContext: [
//         { source: "CRM", detail: "Deal, proposal, stakeholders", access: "org" },
//         { source: "Gmail", detail: "Security follow-up thread", access: "participants" },
//         { source: "Calendar", detail: "No next meeting", access: "private" },
//       ],
//     },
//   },
//   {
//     id: "neonfund-support-risk",
//     label: "Escalation risk",
//     scene: "gmail",
//     application: "Support Inbox",
//     url: "app.intercom.com/a/inbox/neonfund-4821",
//     defaultSurface: "popover",
//     trigger: "Opened NeonFund’s latest support escalation",
//     sceneData: {
//       accountName: "NeonFund",
//       accountMeta: "Priority customer · Support",
//       subject: "Escalation: permissions issue still unresolved",
//       preview: "We have repeated the same troubleshooting steps twice. We need a clear owner and resolution timeline today.",
//       contact: "Elena Torres",
//       avatar: "ET",
//       status: "SLA breached 2h ago",
//       supporting: [
//         { label: "Priority", value: "Urgent" },
//         { label: "Open", value: "8 days" },
//         { label: "Sentiment", value: "Negative" },
//       ],
//     },
//     card: {
//       schemaVersion: "intelligence-card.v1",
//       id: "intel_support_neonfund_escalation",
//       traceId: "tr_support_neonfund_4821",
//       orgId: "genios_demo",
//       visibility: "org",
//       type: "risk",
//       priority: "critical",
//       domain: "Customer Support",
//       title: "NeonFund’s support pattern now threatens trust",
//       summary: "The customer has repeated the same issue across three conversations, the SLA is breached, and no single resolution owner is visible.",
//       situation: "Priority escalation unresolved for eight days",
//       whyItMatters: [
//         "The same permissions issue has reopened twice",
//         "Customer sentiment shifted from neutral to negative",
//         "No accountable resolution owner is visible",
//       ],
//       evidence: [
//         { label: "Recurrence", value: "Same permissions issue across 3 conversations", source: "Support", observedAt: "8 days" },
//         { label: "SLA", value: "Priority response window breached", source: "Support", observedAt: "2h ago" },
//         { label: "Sentiment", value: "Latest reply requests escalation and named ownership", source: "Gmail", observedAt: "12 min ago" },
//       ],
//       recommendation: "Name one owner now, acknowledge the repeated failure, and give the customer a verified resolution checkpoint today.",
//       advice: {
//         steps: [
//           "Assign one accountable owner across support and engineering.",
//           "Acknowledge the repeated troubleshooting failure before offering another step.",
//           "Give NeonFund a verified checkpoint today, even if the final fix needs longer.",
//         ],
//         avoid: "Do not send another generic troubleshooting checklist or split ownership across multiple responders.",
//       },
//       doNothingConsequence: "The issue may become a relationship escalation instead of a contained support incident.",
//       confidenceBp: 9300,
//       urgency: "Now",
//       deadline: "Today, 12:30",
//       agentName: "Lyzr Agent",
//       suggestedActions: [
//         { id: "view_advice", label: "View advice", emphasis: "primary" },
//         { id: "delegate_agent", label: "Assign to Lyzr Agent", emphasis: "secondary" },
//       ],
//       availableActions: [
//         { id: "do_myself", label: "Take ownership" },
//         { id: "schedule", label: "Set checkpoint" },
//         { id: "snooze", label: "Snooze" },
//         { id: "dismiss", label: "Dismiss" },
//       ],
//       deliveryContext: {
//         application: "Support Inbox",
//         location: "NeonFund escalation",
//         entity: "NeonFund",
//         reason: "The escalation is open and the SLA has already been breached.",
//         contextFitBp: 9800,
//         interruptionCostBp: 600,
//         gateVerdict: "SEND",
//       },
//       expiration: "Today, 14:00",
//       sourceContext: [
//         { source: "Support", detail: "Ticket history and SLA", access: "org" },
//         { source: "Gmail", detail: "Customer replies", access: "participants" },
//         { source: "CRM", detail: "Account owner", access: "org" },
//       ],
//     },
//   },
//   {
//     id: "northstar-support-opportunity",
//     label: "Support opportunity",
//     scene: "crm",
//     application: "Customer Support",
//     url: "app.zendesk.com/agent/organizations/northstar",
//     defaultSurface: "sidebar",
//     trigger: "Opened Northstar’s support history",
//     sceneData: {
//       accountName: "Northstar Labs",
//       accountMeta: "Growth account · Healthy",
//       subject: "Support history and enablement readiness",
//       preview: "Three advanced workflow questions were resolved quickly, satisfaction is high, and usage expanded to a second team.",
//       contact: "Jordan Kim",
//       avatar: "JK",
//       status: "Expansion signal",
//       supporting: [
//         { label: "CSAT", value: "4.9 / 5" },
//         { label: "Usage", value: "+38%" },
//         { label: "Teams", value: "2 active" },
//       ],
//     },
//     card: {
//       schemaVersion: "intelligence-card.v1",
//       id: "intel_support_northstar_enablement",
//       traceId: "tr_support_northstar_038",
//       orgId: "genios_demo",
//       visibility: "org",
//       type: "opportunity",
//       priority: "medium",
//       domain: "Customer Support",
//       title: "Northstar is ready for proactive enablement",
//       summary: "Advanced support questions, strong satisfaction, and second-team adoption indicate that targeted enablement can prevent future friction and support expansion.",
//       situation: "Healthy customer showing advanced adoption signals",
//       whyItMatters: [
//         "Advanced workflow questions appeared three times",
//         "All recent issues were resolved with high satisfaction",
//         "Usage expanded to a second team this month",
//       ],
//       evidence: [
//         { label: "Question pattern", value: "3 advanced workflow questions in 21 days", source: "Support", observedAt: "21 days" },
//         { label: "Customer sentiment", value: "Average CSAT 4.9 across recent resolutions", source: "Support", observedAt: "This month" },
//         { label: "Adoption", value: "A second team became active; usage up 38%", source: "Product", observedAt: "This month" },
//       ],
//       recommendation: "Offer a focused admin enablement session before the same questions become recurring friction.",
//       advice: {
//         steps: [
//           "Group the three advanced questions into one enablement agenda.",
//           "Invite the new team’s admin, not only the original champion.",
//           "Use the session to identify the next adoption blocker and owner.",
//         ],
//         avoid: "Do not treat each future question as an isolated ticket; the pattern points to an enablement need.",
//       },
//       doNothingConsequence: "Repeated advanced questions may become avoidable support load and slow broader adoption.",
//       confidenceBp: 8100,
//       urgency: "This week",
//       deadline: "15 Aug",
//       agentName: "Lyzr Agent",
//       suggestedActions: [
//         { id: "view_advice", label: "View advice", emphasis: "primary" },
//         { id: "delegate_agent", label: "Assign to Lyzr Agent", emphasis: "secondary" },
//       ],
//       availableActions: [
//         { id: "schedule", label: "Schedule session" },
//         { id: "do_myself", label: "Own follow-up" },
//         { id: "snooze", label: "Snooze" },
//         { id: "dismiss", label: "Dismiss" },
//       ],
//       deliveryContext: {
//         application: "Customer Support",
//         location: "Northstar organization",
//         entity: "Northstar Labs",
//         reason: "You are reviewing the support pattern while the adoption signal is current.",
//         contextFitBp: 9000,
//         interruptionCostBp: 1900,
//         gateVerdict: "SEND",
//       },
//       expiration: "16 Aug, 18:00",
//       sourceContext: [
//         { source: "Support", detail: "Questions and CSAT", access: "org" },
//         { source: "Product", detail: "Team-level adoption", access: "org" },
//         { source: "CRM", detail: "Account ownership", access: "org" },
//       ],
//     },
//   },
//   {
//     id: "orion-approval",
//     label: "Approval bottleneck",
//     scene: "calendar",
//     application: "Admin Workspace",
//     url: "linear.app/genios/issue/OPS-214/orion-pricing-approval",
//     defaultSurface: "tray",
//     trigger: "Approval is valid, but you are currently in a meeting",
//     sceneData: {
//       accountName: "Orion proposal",
//       accountMeta: "Admin · Commercial approval",
//       subject: "Orion pricing approval checkpoint",
//       preview: "The proposal is complete, but the exception has no final approver and the customer expects it today.",
//       contact: "Finance + Sales",
//       avatar: "OP",
//       status: "Decision due at 15:00",
//       supporting: [
//         { label: "Status", value: "Blocked" },
//         { label: "Waiting", value: "19 hours" },
//         { label: "Value", value: "$54k ARR" },
//       ],
//     },
//     card: {
//       schemaVersion: "intelligence-card.v1",
//       id: "intel_admin_orion_approval",
//       traceId: "tr_admin_orion_214",
//       orgId: "genios_demo",
//       visibility: "org",
//       type: "decision_required",
//       priority: "high",
//       domain: "Admin",
//       title: "One approval is holding the Orion proposal",
//       summary: "Sales, finance, and the policy record disagree on who can approve the pricing exception, so the completed proposal has been blocked for 19 hours.",
//       situation: "Commercial approval has no accountable decision owner",
//       whyItMatters: [
//         "The customer expects the final proposal today",
//         "Finance review is complete but final authority is unclear",
//         "Three internal hand-offs have produced no decision",
//       ],
//       evidence: [
//         { label: "Workflow", value: "Proposal waiting in approval for 19 hours", source: "Admin", observedAt: "Now" },
//         { label: "Policy", value: "Exception requires VP-level commercial authority", source: "Policy", observedAt: "Current" },
//         { label: "Commitment", value: "Customer expects final terms by 15:00", source: "CRM", observedAt: "Yesterday" },
//       ],
//       recommendation: "Name the authorized approver, present the exception and downside in one decision note, and close the approval by 15:00.",
//       advice: {
//         steps: [
//           "Route the decision to the VP-level commercial approver defined by policy.",
//           "Present the requested exception, revenue impact, and downside in one note.",
//           "Record approve or decline by 15:00 and return ownership to sales immediately.",
//         ],
//         avoid: "Do not continue forwarding the request between finance and sales without naming decision authority.",
//       },
//       doNothingConsequence: "The customer commitment will be missed even though the proposal work is already complete.",
//       confidenceBp: 9000,
//       urgency: "After current meeting",
//       deadline: "Today, 15:00",
//       agentName: "Hermes Agent",
//       suggestedActions: [
//         { id: "view_advice", label: "View advice", emphasis: "primary" },
//         { id: "delegate_agent", label: "Assign to Hermes Agent", emphasis: "secondary" },
//       ],
//       availableActions: [
//         { id: "do_myself", label: "Take decision" },
//         { id: "schedule", label: "Set checkpoint" },
//         { id: "snooze", label: "Snooze" },
//         { id: "dismiss", label: "Dismiss" },
//       ],
//       deliveryContext: {
//         application: "Admin Workspace",
//         location: "Orion approval",
//         entity: "Orion proposal",
//         reason: "The approval matters now, but the current meeting makes interruption costly.",
//         contextFitBp: 8800,
//         interruptionCostBp: 9300,
//         gateVerdict: "DEFER",
//         notBefore: "Current meeting ends · 14:20",
//       },
//       expiration: "Today, 15:00",
//       sourceContext: [
//         { source: "Admin", detail: "Approval workflow", access: "org" },
//         { source: "Policy", detail: "Commercial authority", access: "org" },
//         { source: "CRM", detail: "Customer commitment", access: "org" },
//       ],
//     },
//   },
// ];
//
// export function toDeliveryObject(scenario: DemoScenario): DeliveryObject {
//   const { card, defaultSurface } = scenario;
//   return {
//     schemaVersion: "delivery-object.v1",
//     executionId: `exec_${card.id}`,
//     idempotencyKey: `exec_${card.id}:rohit:browser:${card.deadline}`,
//     recipient: "Rohit",
//     destination: "browser_extension",
//     channel: defaultSurface,
//     priorityBp:
//       card.priority === "critical"
//         ? 9500
//         : card.priority === "high"
//           ? 8200
//           : card.priority === "medium"
//             ? 6200
//             : 3500,
//     gateVerdict: card.deliveryContext.gateVerdict,
//     notBefore: card.deliveryContext.notBefore,
//     payload: card,
//   };
// }
```

#### `src/types.ts`

```ts
// export type IntelligenceType =
//   | "forgotten_commitment"
//   | "important_change"
//   | "risk"
//   | "opportunity"
//   | "decision_required"
//   | "recommended_action"
//   | "conflict"
//   | "upcoming_situation";
//
// export type Priority = "critical" | "high" | "medium" | "low";
// export type GateVerdict = "SEND" | "DEFER" | "SUPPRESS";
// export type SurfaceMode = "popover" | "tray" | "sidebar";
// export type SceneKind = "gmail" | "crm" | "calendar" | "code";
//
// export type ActionId =
//   | "view_advice"
//   | "book_call"
//   | "delegate_human"
//   | "delegate_agent"
//   | "do_myself"
//   | "open_crm"
//   | "review_change"
//   | "schedule"
//   | "snooze"
//   | "dismiss";
//
// export type IntelligenceAction = {
//   id: ActionId;
//   label: string;
//   emphasis?: "primary" | "secondary" | "quiet";
// };
//
// export type IntelligenceEvidence = {
//   label: string;
//   value: string;
//   source: string;
//   observedAt: string;
// };
//
// export type SourceContext = {
//   source: string;
//   detail: string;
//   access: "org" | "participants" | "private";
// };
//
// export type DeliveryContext = {
//   application: string;
//   location: string;
//   entity: string;
//   reason: string;
//   contextFitBp: number;
//   interruptionCostBp: number;
//   gateVerdict: GateVerdict;
//   notBefore?: string;
// };
//
// /**
//  * Presentation contract consumed by every GeniOS surface.
//  * Mock data uses this today; the real Delivery API can provide it later.
//  */
// export type IntelligenceCard = {
//   schemaVersion: "intelligence-card.v1";
//   id: string;
//   traceId: string;
//   orgId: string;
//   visibility: "org" | "participants" | "private";
//   type: IntelligenceType;
//   priority: Priority;
//   domain: string;
//   title: string;
//   summary: string;
//   situation: string;
//   whyItMatters: string[];
//   evidence: IntelligenceEvidence[];
//   recommendation: string;
//   advice: {
//     steps: string[];
//     avoid: string;
//   };
//   doNothingConsequence: string;
//   confidenceBp: number;
//   urgency: string;
//   deadline: string;
//   agentName: "Hermes Agent" | "Lyzr Agent";
//   suggestedActions: IntelligenceAction[];
//   availableActions: IntelligenceAction[];
//   deliveryContext: DeliveryContext;
//   expiration: string;
//   sourceContext: SourceContext[];
// };
//
// /** Internal Layer 5.2 handoff shown here so the prototype preserves the Atlas boundary. */
// export type DeliveryObject = {
//   schemaVersion: "delivery-object.v1";
//   executionId: string;
//   idempotencyKey: string;
//   recipient: string;
//   destination: "browser_extension";
//   channel: SurfaceMode;
//   priorityBp: number;
//   gateVerdict: GateVerdict;
//   notBefore?: string;
//   payload: IntelligenceCard;
// };
//
// export type SceneData = {
//   accountName: string;
//   accountMeta: string;
//   subject: string;
//   preview: string;
//   contact: string;
//   avatar: string;
//   status: string;
//   supporting: Array<{ label: string; value: string }>;
// };
//
// export type DemoScenario = {
//   id: string;
//   label: string;
//   scene: SceneKind;
//   application: string;
//   url: string;
//   defaultSurface: SurfaceMode;
//   trigger: string;
//   card: IntelligenceCard;
//   sceneData: SceneData;
// };
```

#### `src/styles.css`

```css
// @import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Orbitron:wght@500;700;800&display=swap");
//
// :root {
//   font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
//   color: #14161c;
//   background: #e8e9ed;
//   font-synthesis: none;
//   text-rendering: optimizeLegibility;
//   -webkit-font-smoothing: antialiased;
//   --paper: #ffffff;
//   --canvas: #f4f5f7;
//   --rail: #f7f7f8;
//   --surface: #ececf1;
//   --ink: #14161c;
//   --ink-soft: #2b2e38;
//   --mist: #6b7280;
//   --faint: #9aa0ab;
//   --line: rgba(20, 22, 30, 0.09);
//   --line-strong: rgba(20, 22, 30, 0.16);
//   --accent: #8a2d3b;
//   --accent-soft: rgba(138, 45, 59, 0.08);
//   --success: #2f9e55;
//   --success-soft: rgba(47, 158, 85, 0.1);
//   --warn: #df7a32;
//   --warn-soft: rgba(223, 122, 50, 0.1);
//   --error: #b3261e;
//   --error-soft: rgba(179, 38, 30, 0.08);
//   --overlay-shadow: 0 30px 80px -25px rgba(20, 22, 28, 0.34), 0 8px 24px rgba(20, 22, 28, 0.08);
//   --frame-shadow: 0 30px 80px -34px rgba(20, 22, 28, 0.38), 0 2px 6px rgba(20, 22, 28, 0.08);
// }
//
// * {
//   box-sizing: border-box;
// }
//
// html,
// body,
// #root {
//   width: 100%;
//   min-width: 900px;
//   height: 100%;
//   min-height: 700px;
//   margin: 0;
//   overflow: hidden;
// }
//
// button,
// input {
//   font: inherit;
// }
//
// button {
//   color: inherit;
// }
//
// button:focus-visible {
//   outline: 2px solid var(--accent);
//   outline-offset: 2px;
// }
//
// .app {
//   position: relative;
//   width: 100%;
//   height: 100%;
//   background:
//     radial-gradient(circle at 20% -10%, rgba(255, 255, 255, 0.96), transparent 34%),
//     radial-gradient(circle at 88% 105%, rgba(138, 45, 59, 0.07), transparent 28%),
//     #e8e9ed;
// }
//
// .app::before {
//   position: absolute;
//   inset: 0;
//   content: "";
//   pointer-events: none;
//   opacity: 0.14;
//   background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.16'/%3E%3C/svg%3E");
// }
//
// .studio-bar {
//   position: absolute;
//   z-index: 80;
//   top: 0;
//   left: 0;
//   right: 0;
//   height: 66px;
//   display: grid;
//   grid-template-columns: 1fr auto 1fr;
//   align-items: center;
//   padding: 0 28px;
//   border-bottom: 1px solid rgba(20, 22, 30, 0.08);
//   background: rgba(247, 247, 248, 0.84);
//   backdrop-filter: blur(18px);
// }
//
// .studio-identity,
// .studio-tools,
// .studio-status,
// .studio-identity > div,
// .intelligence-brand,
// .studio-tools > button,
// .studio-status {
//   display: flex;
//   align-items: center;
// }
//
// .studio-identity {
//   gap: 14px;
// }
//
// .studio-divider {
//   width: 1px;
//   height: 25px;
//   background: var(--line-strong);
// }
//
// .studio-identity > div {
//   align-items: flex-start;
//   flex-direction: column;
//   line-height: 1.2;
// }
//
// .studio-identity strong {
//   font-size: 12px;
//   font-weight: 600;
// }
//
// .studio-identity span:not(.studio-divider) {
//   margin-top: 3px;
//   color: var(--faint);
//   font-size: 9px;
//   letter-spacing: 0.04em;
//   text-transform: uppercase;
// }
//
// .wordmark {
//   font-family: "Orbitron", "Inter", sans-serif;
//   font-size: 18px;
//   font-weight: 500;
//   letter-spacing: 0.015em;
//   white-space: nowrap;
// }
//
// .wordmark b {
//   font-weight: 800;
// }
//
// .wordmark.compact {
//   font-size: 15px;
// }
//
// .studio-status {
//   height: 30px;
//   gap: 7px;
//   padding: 0 10px;
//   border: 1px solid var(--line);
//   border-radius: 8px;
//   color: var(--mist);
//   background: rgba(255, 255, 255, 0.68);
//   font-size: 10px;
//   font-weight: 500;
// }
//
// .status-dot {
//   display: inline-block;
//   width: 6px;
//   height: 6px;
//   border-radius: 999px;
//   background: var(--success);
//   box-shadow: 0 0 0 4px var(--success-soft);
// }
//
// .studio-count {
//   margin-left: 6px;
//   padding-left: 9px;
//   border-left: 1px solid var(--line);
//   color: var(--ink-soft);
//   font-variant-numeric: tabular-nums;
// }
//
// .studio-tools {
//   justify-content: flex-end;
//   gap: 7px;
// }
//
// .surface-switcher {
//   display: flex;
//   margin-right: 6px;
//   padding: 3px;
//   border: 1px solid var(--line);
//   border-radius: 9px;
//   background: rgba(255, 255, 255, 0.7);
// }
//
// .surface-switcher button {
//   height: 26px;
//   padding: 0 10px;
//   border: 0;
//   border-radius: 6px;
//   color: var(--mist);
//   background: transparent;
//   font-size: 10px;
//   font-weight: 500;
//   cursor: pointer;
// }
//
// .surface-switcher button.active {
//   color: white;
//   background: var(--ink);
// }
//
// .icon-button,
// .play-button,
// .text-button {
//   height: 32px;
//   justify-content: center;
//   gap: 6px;
//   border-radius: 8px;
//   cursor: pointer;
// }
//
// .icon-button {
//   width: 32px;
//   padding: 0;
//   border: 1px solid var(--line);
//   background: rgba(255, 255, 255, 0.72);
// }
//
// .play-button {
//   padding: 0 13px;
//   border: 1px solid var(--ink);
//   color: white;
//   background: var(--ink);
//   font-size: 10px;
//   font-weight: 600;
// }
//
// .text-button {
//   padding: 0 11px;
//   border: 1px solid var(--line-strong);
//   background: rgba(255, 255, 255, 0.72);
//   font-size: 10px;
//   font-weight: 500;
// }
//
// .stage {
//   position: absolute;
//   inset: 0;
//   display: flex;
//   align-items: center;
//   justify-content: center;
//   padding: 82px 25px 112px;
//   transition: padding 300ms ease;
// }
//
// .browser-frame {
//   position: relative;
//   width: min(1500px, 100%);
//   height: 100%;
//   min-height: 560px;
//   overflow: hidden;
//   border: 1px solid rgba(20, 22, 30, 0.18);
//   border-radius: 14px;
//   background: var(--paper);
//   box-shadow: var(--frame-shadow);
// }
//
// .browser-titlebar {
//   position: relative;
//   z-index: 30;
//   height: 43px;
//   display: grid;
//   grid-template-columns: 78px 78px minmax(280px, 660px) 1fr;
//   align-items: center;
//   gap: 8px;
//   padding: 0 14px;
//   border-bottom: 1px solid var(--line);
//   background: #f5f5f6;
// }
//
// .traffic-lights {
//   display: flex;
//   align-items: center;
//   gap: 7px;
// }
//
// .traffic-lights i {
//   width: 10px;
//   height: 10px;
//   border: 1px solid rgba(0, 0, 0, 0.08);
//   border-radius: 999px;
//   background: #ff5f57;
// }
//
// .traffic-lights i:nth-child(2) {
//   background: #febc2e;
// }
//
// .traffic-lights i:nth-child(3) {
//   background: #28c840;
// }
//
// .browser-nav,
// .browser-actions {
//   display: flex;
//   align-items: center;
//   gap: 14px;
//   color: #727680;
// }
//
// .address-bar {
//   height: 27px;
//   display: flex;
//   align-items: center;
//   gap: 7px;
//   padding: 0 12px;
//   overflow: hidden;
//   border: 1px solid rgba(20, 22, 30, 0.07);
//   border-radius: 8px;
//   color: #7a7f89;
//   background: white;
//   font-size: 10px;
//   white-space: nowrap;
// }
//
// .address-bar span {
//   overflow: hidden;
//   text-overflow: ellipsis;
// }
//
// .browser-actions {
//   justify-content: flex-end;
// }
//
// .extension-pill {
//   display: flex;
//   align-items: center;
//   gap: 5px;
//   color: var(--accent);
// }
//
// .extension-pill span {
//   min-width: 14px;
//   height: 14px;
//   display: grid;
//   place-items: center;
//   border-radius: 5px;
//   color: white;
//   background: var(--accent);
//   font-size: 8px;
//   font-weight: 600;
// }
//
// .scene {
//   position: absolute;
//   inset: 43px 0 0;
//   overflow: hidden;
//   color: #3e424b;
//   background: #fff;
// }
//
// .scene-header {
//   position: absolute;
//   top: 0;
//   left: 0;
//   right: 0;
//   height: 54px;
//   display: grid;
//   grid-template-columns: 180px minmax(280px, 540px) 1fr;
//   align-items: center;
//   gap: 24px;
//   padding: 0 18px;
//   border-bottom: 1px solid rgba(20, 22, 30, 0.07);
//   background: rgba(255, 255, 255, 0.98);
// }
//
// .scene-app,
// .scene-search,
// .scene-user {
//   display: flex;
//   align-items: center;
// }
//
// .scene-app {
//   gap: 10px;
//   color: #292d35;
//   font-size: 13px;
// }
//
// .app-mark {
//   width: 29px;
//   height: 29px;
//   display: grid;
//   place-items: center;
//   border: 1px solid var(--line);
//   border-radius: 8px;
//   color: #b2483f;
//   background: white;
// }
//
// .app-mark.crm {
//   color: #e46e36;
// }
//
// .app-mark.calendar {
//   color: #4976bf;
// }
//
// .scene-search {
//   height: 33px;
//   gap: 8px;
//   padding: 0 12px;
//   border-radius: 9px;
//   color: #90949c;
//   background: #f1f3f5;
//   font-size: 10px;
// }
//
// .scene-user {
//   justify-content: flex-end;
//   gap: 15px;
//   color: #777b84;
// }
//
// .scene-user span {
//   width: 28px;
//   height: 28px;
//   display: grid;
//   place-items: center;
//   border-radius: 999px;
//   color: white;
//   background: #30343c;
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .scene-sidebar {
//   position: absolute;
//   top: 54px;
//   bottom: 0;
//   left: 0;
//   width: 176px;
//   padding: 15px 10px;
//   border-right: 1px solid rgba(20, 22, 30, 0.07);
//   background: #f8f9fa;
// }
//
// .compose-button {
//   width: 116px;
//   height: 36px;
//   display: flex;
//   align-items: center;
//   gap: 8px;
//   margin: 0 4px 13px;
//   padding: 0 13px;
//   border: 1px solid rgba(20, 22, 30, 0.08);
//   border-radius: 11px;
//   background: white;
//   box-shadow: 0 2px 6px rgba(20, 22, 28, 0.07);
//   font-size: 10px;
//   font-weight: 500;
// }
//
// .scene-nav {
//   height: 30px;
//   display: flex;
//   align-items: center;
//   gap: 9px;
//   padding: 0 10px;
//   border-radius: 8px;
//   color: #737781;
//   font-size: 10px;
// }
//
// .scene-nav.active {
//   color: #252932;
//   background: #eceef1;
//   font-weight: 600;
// }
//
// .scene-nav small {
//   margin-left: auto;
//   font-size: 9px;
// }
//
// .nav-section-label {
//   margin: 19px 10px 7px;
//   color: #9da1aa;
//   font-size: 8px;
//   font-weight: 600;
//   letter-spacing: 0.08em;
//   text-transform: uppercase;
// }
//
// .mail-list {
//   position: absolute;
//   top: 54px;
//   bottom: 0;
//   left: 176px;
//   width: 300px;
//   border-right: 1px solid rgba(20, 22, 30, 0.07);
//   background: white;
// }
//
// .mail-list-tools,
// .reader-toolbar {
//   height: 39px;
//   display: flex;
//   align-items: center;
//   gap: 10px;
//   padding: 0 13px;
//   border-bottom: 1px solid rgba(20, 22, 30, 0.07);
//   color: #858a93;
// }
//
// .mail-list-tools small {
//   margin-left: auto;
//   font-size: 8px;
// }
//
// .mail-row {
//   min-height: 62px;
//   display: grid;
//   grid-template-columns: 27px 1fr auto;
//   align-items: center;
//   gap: 9px;
//   padding: 8px 11px;
//   border-bottom: 1px solid rgba(20, 22, 30, 0.06);
//   background: #fafbfc;
// }
//
// .mail-row.active {
//   border-left: 2px solid #b2483f;
//   background: white;
// }
//
// .mail-avatar {
//   width: 25px;
//   height: 25px;
//   display: grid;
//   place-items: center;
//   border-radius: 999px;
//   color: #6c7079;
//   background: #eaebee;
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .mail-copy {
//   min-width: 0;
//   display: flex;
//   flex-direction: column;
//   gap: 4px;
// }
//
// .mail-copy strong,
// .mail-copy span {
//   overflow: hidden;
//   text-overflow: ellipsis;
//   white-space: nowrap;
// }
//
// .mail-copy strong {
//   color: #353943;
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .mail-copy span {
//   color: #777c86;
//   font-size: 8px;
// }
//
// .mail-row time {
//   align-self: start;
//   margin-top: 4px;
//   color: #a1a5ad;
//   font-size: 7px;
// }
//
// .mail-reader {
//   position: absolute;
//   top: 54px;
//   bottom: 0;
//   left: 476px;
//   right: 0;
//   background: white;
// }
//
// .reader-toolbar {
//   justify-content: flex-start;
// }
//
// .reader-toolbar span {
//   flex: 1;
// }
//
// .reader-content {
//   width: min(620px, 80%);
//   margin: 0 auto;
//   padding: 34px 8px;
// }
//
// .reader-label {
//   display: inline-flex;
//   padding: 4px 7px;
//   border-radius: 5px;
//   color: #777b84;
//   background: #f0f1f3;
//   font-size: 7px;
//   font-weight: 600;
//   text-transform: uppercase;
// }
//
// .reader-content h1 {
//   margin: 10px 0 22px;
//   color: #2a2e36;
//   font-size: 20px;
//   font-weight: 500;
//   letter-spacing: -0.025em;
// }
//
// .sender-line {
//   display: grid;
//   grid-template-columns: 31px 1fr auto;
//   align-items: center;
//   gap: 10px;
//   margin-bottom: 24px;
// }
//
// .contact-avatar {
//   width: 31px;
//   height: 31px;
//   display: grid;
//   place-items: center;
//   border-radius: 999px;
//   color: white;
//   background: #6f727a;
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .sender-line div {
//   display: flex;
//   flex-direction: column;
//   gap: 2px;
// }
//
// .sender-line strong {
//   font-size: 10px;
// }
//
// .sender-line small,
// .sender-line time {
//   color: #92969e;
//   font-size: 8px;
// }
//
// .reader-content > p {
//   max-width: 560px;
//   color: #575b64;
//   font-size: 11px;
//   line-height: 1.75;
// }
//
// .mail-signoff {
//   margin-top: 20px;
// }
//
// .reply-box {
//   height: 54px;
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   margin-top: 30px;
//   padding: 0 17px;
//   border: 1px solid rgba(20, 22, 30, 0.1);
//   border-radius: 9px;
//   color: #999da5;
//   font-size: 10px;
// }
//
// .crm-main,
// .calendar-main {
//   position: absolute;
//   top: 54px;
//   right: 0;
//   bottom: 0;
//   left: 176px;
//   overflow: hidden;
//   padding: 20px 25px;
//   background: #f7f8fa;
// }
//
// .crumbs {
//   display: flex;
//   align-items: center;
//   gap: 5px;
//   color: #92969f;
//   font-size: 8px;
// }
//
// .account-heading {
//   display: flex;
//   align-items: center;
//   gap: 12px;
//   margin-top: 17px;
// }
//
// .account-logo {
//   width: 43px;
//   height: 43px;
//   display: grid;
//   place-items: center;
//   border: 1px solid rgba(20, 22, 30, 0.08);
//   border-radius: 10px;
//   color: white;
//   background: #343840;
//   font-size: 17px;
//   font-weight: 600;
// }
//
// .account-heading > div {
//   flex: 1;
// }
//
// .account-heading h1,
// .calendar-toolbar h1 {
//   margin: 0;
//   color: #22262e;
//   font-size: 18px;
//   font-weight: 500;
//   letter-spacing: -0.025em;
// }
//
// .account-heading p {
//   margin: 4px 0 0;
//   color: #8a8e97;
//   font-size: 9px;
// }
//
// .account-heading > button,
// .crm-panel header button,
// .calendar-toolbar button {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   border: 1px solid rgba(20, 22, 30, 0.1);
//   border-radius: 7px;
//   color: #60646d;
//   background: white;
//   font-size: 9px;
// }
//
// .account-heading > button {
//   height: 30px;
//   padding: 0 11px;
// }
//
// .risk-chip {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   padding: 5px 8px;
//   border: 1px solid rgba(179, 38, 30, 0.15);
//   border-radius: 7px;
//   color: var(--error);
//   background: var(--error-soft);
//   font-size: 8px;
//   font-weight: 600;
// }
//
// .metric-grid {
//   display: grid;
//   grid-template-columns: repeat(4, 1fr);
//   gap: 10px;
//   margin-top: 23px;
// }
//
// .crm-metric {
//   min-height: 70px;
//   display: flex;
//   flex-direction: column;
//   justify-content: space-between;
//   padding: 13px;
//   border: 1px solid rgba(20, 22, 30, 0.08);
//   border-radius: 9px;
//   background: white;
// }
//
// .crm-metric span {
//   color: #999da5;
//   font-size: 8px;
//   text-transform: uppercase;
// }
//
// .crm-metric strong {
//   color: #343840;
//   font-size: 13px;
//   font-weight: 500;
// }
//
// .crm-columns {
//   display: grid;
//   grid-template-columns: 1.4fr 0.8fr;
//   gap: 12px;
//   margin-top: 14px;
// }
//
// .crm-panel {
//   min-height: 260px;
//   overflow: hidden;
//   border: 1px solid rgba(20, 22, 30, 0.08);
//   border-radius: 10px;
//   background: white;
// }
//
// .crm-panel header {
//   height: 46px;
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   padding: 0 15px;
//   border-bottom: 1px solid rgba(20, 22, 30, 0.07);
// }
//
// .crm-panel header strong {
//   font-size: 10px;
// }
//
// .crm-panel header button {
//   padding: 4px 7px;
// }
//
// .activity-item {
//   display: grid;
//   grid-template-columns: 8px 1fr;
//   gap: 10px;
//   padding: 14px 16px;
//   border-bottom: 1px solid rgba(20, 22, 30, 0.06);
// }
//
// .activity-item > span {
//   width: 7px;
//   height: 7px;
//   margin-top: 3px;
//   border-radius: 999px;
//   background: #7f838c;
// }
//
// .activity-item.danger > span {
//   background: var(--error);
// }
//
// .activity-item div {
//   display: flex;
//   flex-direction: column;
//   gap: 4px;
// }
//
// .activity-item strong,
// .plan-row {
//   font-size: 9px;
//   font-weight: 500;
// }
//
// .activity-item p {
//   margin: 0;
//   color: #777b85;
//   font-size: 8px;
// }
//
// .activity-item small {
//   color: #a1a5ad;
//   font-size: 7px;
// }
//
// .plan-row {
//   display: flex;
//   align-items: center;
//   gap: 8px;
//   padding: 13px 15px;
//   border-bottom: 1px solid rgba(20, 22, 30, 0.06);
//   color: var(--success);
// }
//
// .plan-row.open {
//   color: #9a9ea6;
// }
//
// .calendar-nav {
//   padding-top: 15px;
// }
//
// .mini-month {
//   padding: 7px 8px 12px;
// }
//
// .mini-month strong {
//   display: block;
//   margin-bottom: 10px;
//   color: #4a4e57;
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .month-grid {
//   display: grid;
//   grid-template-columns: repeat(7, 1fr);
//   gap: 5px 2px;
//   text-align: center;
// }
//
// .month-grid span {
//   height: 16px;
//   display: grid;
//   place-items: center;
//   border-radius: 999px;
//   color: #767a83;
//   font-size: 7px;
// }
//
// .month-labels span {
//   color: #a2a6ae;
//   font-weight: 600;
// }
//
// .month-grid span.today {
//   color: white;
//   background: #4a74ba;
// }
//
// .calendar-main {
//   padding: 0;
//   background: white;
// }
//
// .calendar-toolbar {
//   height: 61px;
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   padding: 0 20px;
//   border-bottom: 1px solid rgba(20, 22, 30, 0.08);
// }
//
// .calendar-toolbar div {
//   display: flex;
//   gap: 6px;
// }
//
// .calendar-toolbar button {
//   height: 28px;
//   padding: 0 10px;
// }
//
// .day-grid {
//   position: absolute;
//   top: 61px;
//   right: 0;
//   bottom: 0;
//   left: 0;
//   padding-top: 10px;
// }
//
// .time-row {
//   height: 52px;
//   display: grid;
//   grid-template-columns: 56px 1fr;
// }
//
// .time-row time {
//   padding-right: 9px;
//   color: #9b9fa7;
//   font-size: 7px;
//   text-align: right;
// }
//
// .time-row span {
//   border-top: 1px solid rgba(20, 22, 30, 0.06);
// }
//
// .calendar-event {
//   position: absolute;
//   left: 70px;
//   width: min(380px, 40%);
//   display: flex;
//   flex-direction: column;
//   padding: 8px 10px;
//   border-left: 3px solid #747983;
//   border-radius: 7px;
//   color: #484c55;
//   background: #eef0f2;
// }
//
// .calendar-event small,
// .calendar-event span,
// .calendar-event em {
//   font-size: 7px;
// }
//
// .calendar-event strong {
//   margin: 4px 0;
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .calendar-event span {
//   color: #838791;
// }
//
// .muted-event {
//   top: 64px;
//   height: 42px;
// }
//
// .active-event {
//   top: 298px;
//   height: 78px;
//   border-color: #4e76b8;
//   color: #29476f;
//   background: #eaf1fb;
// }
//
// .active-event em {
//   margin-top: auto;
//   color: #4e76b8;
//   font-style: normal;
//   font-weight: 600;
// }
//
// .calendar-now {
//   position: absolute;
//   top: 283px;
//   left: 22px;
//   right: 0;
//   display: flex;
//   align-items: center;
//   color: #b2483f;
//   font-size: 7px;
// }
//
// .calendar-now i {
//   flex: 1;
//   height: 1px;
//   margin-left: 8px;
//   background: #b2483f;
// }
//
// .code-scene {
//   display: grid;
//   grid-template-columns: 48px 190px 1fr;
//   color: #c8cbd3;
//   background: #181a1f;
// }
//
// .code-rail {
//   display: flex;
//   align-items: center;
//   flex-direction: column;
//   gap: 22px;
//   padding-top: 18px;
//   border-right: 1px solid #2a2d34;
//   color: #747984;
//   background: #1c1f24;
// }
//
// .code-rail svg.active {
//   color: white;
// }
//
// .code-mark {
//   width: 31px;
//   height: 31px;
//   display: grid;
//   place-items: center;
//   margin-bottom: 3px;
//   border-radius: 8px;
//   color: white;
//   background: #30343d;
// }
//
// .file-tree {
//   position: relative;
//   padding: 13px 8px;
//   border-right: 1px solid #2a2d34;
//   background: #202329;
// }
//
// .file-title,
// .repo-name,
// .tree-row,
// .code-focus,
// .editor-tabs,
// .editor-breadcrumbs,
// .code-statusbar,
// .code-top-meta {
//   display: flex;
//   align-items: center;
// }
//
// .file-title {
//   justify-content: space-between;
//   padding: 0 6px 12px;
//   color: #a7abb4;
//   font-size: 8px;
// }
//
// .repo-name {
//   gap: 3px;
//   padding: 5px 2px;
//   color: #e1e3e8;
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .tree-row {
//   height: 25px;
//   gap: 5px;
//   padding: 0 5px;
//   border-radius: 5px;
//   color: #aeb2bb;
//   font-size: 9px;
// }
//
// .tree-row.active {
//   color: white;
//   background: #333741;
// }
//
// .tree-row.indent {
//   padding-left: 16px;
// }
//
// .tree-row.indent-2 {
//   padding-left: 31px;
// }
//
// .code-focus {
//   position: absolute;
//   right: 10px;
//   bottom: 14px;
//   left: 10px;
//   gap: 10px;
//   padding: 10px;
//   border: 1px solid #343842;
//   border-radius: 8px;
//   background: #25282f;
// }
//
// .code-focus div {
//   display: flex;
//   flex-direction: column;
//   gap: 3px;
// }
//
// .code-focus strong {
//   color: #e1e3e7;
//   font-size: 8px;
// }
//
// .code-focus small {
//   color: #777c87;
//   font-size: 7px;
// }
//
// .editor-area {
//   position: relative;
//   min-width: 0;
//   background: #181a1f;
// }
//
// .editor-tabs {
//   height: 37px;
//   border-bottom: 1px solid #292c33;
//   background: #202329;
// }
//
// .editor-tabs span {
//   height: 100%;
//   display: flex;
//   align-items: center;
//   gap: 6px;
//   padding: 0 12px;
//   border-right: 1px solid #292c33;
//   color: #858a94;
//   font-size: 8px;
// }
//
// .editor-tabs span.active {
//   border-top: 1px solid #8a2d3b;
//   color: #d7dae0;
//   background: #181a1f;
// }
//
// .editor-breadcrumbs {
//   height: 30px;
//   gap: 5px;
//   padding: 0 13px;
//   color: #858a94;
//   font-size: 8px;
// }
//
// .code-content {
//   margin: 0;
//   padding: 14px 20px 60px 58px;
//   color: #c7cad1;
//   font-family: "SFMono-Regular", Consolas, monospace;
//   font-size: clamp(9px, 0.75vw, 12px);
//   line-height: 1.75;
//   counter-reset: line;
// }
//
// .code-content code {
//   white-space: pre-wrap;
// }
//
// .code-content code::first-line {
//   color: #c98d99;
// }
//
// .code-statusbar {
//   position: absolute;
//   right: 0;
//   bottom: 0;
//   left: 0;
//   height: 23px;
//   gap: 18px;
//   padding: 0 11px;
//   color: #d5d7db;
//   background: #74243a;
//   font-size: 7px;
// }
//
// .code-top-meta {
//   position: absolute;
//   top: 7px;
//   right: 15px;
//   gap: 7px;
// }
//
// .code-top-meta span {
//   padding: 4px 7px;
//   border: 1px solid #343842;
//   border-radius: 5px;
//   color: #9ea3ad;
//   background: #22252b;
//   font-size: 7px;
// }
//
// .tray-trigger {
//   position: absolute;
//   z-index: 45;
//   right: 20px;
//   bottom: 20px;
//   width: 45px;
//   height: 45px;
//   display: grid;
//   place-items: center;
//   border: 1px solid rgba(255, 255, 255, 0.24);
//   border-radius: 13px;
//   color: white;
//   background: var(--ink);
//   box-shadow: 0 15px 38px -12px rgba(20, 22, 28, 0.55);
//   cursor: pointer;
//   transition: transform 180ms ease, background 180ms ease;
// }
//
// .tray-trigger:hover,
// .tray-trigger.active {
//   transform: translateY(-2px);
//   background: var(--accent);
// }
//
// .tray-trigger span {
//   position: absolute;
//   top: -6px;
//   right: -6px;
//   min-width: 18px;
//   height: 18px;
//   display: grid;
//   place-items: center;
//   padding: 0 4px;
//   border: 2px solid white;
//   border-radius: 999px;
//   color: white;
//   background: var(--accent);
//   font-size: 8px;
//   font-weight: 600;
// }
//
// .intelligence-panel,
// .intelligence-tray {
//   z-index: 40;
//   overflow: hidden;
//   border: 1px solid rgba(20, 22, 30, 0.14);
//   background: rgba(255, 255, 255, 0.98);
//   box-shadow: var(--overlay-shadow);
//   backdrop-filter: blur(20px);
//   animation: surface-in 480ms cubic-bezier(0.16, 1, 0.3, 1) both;
// }
//
// .intelligence-panel.popover {
//   position: absolute;
//   top: 68px;
//   right: 24px;
//   width: 410px;
//   max-height: calc(100% - 94px);
//   overflow-y: auto;
//   border-radius: 14px;
// }
//
// .intelligence-panel.sidebar {
//   position: absolute;
//   top: 43px;
//   right: 0;
//   bottom: 0;
//   width: 372px;
//   overflow-y: auto;
//   border-width: 0 0 0 1px;
//   border-radius: 0;
//   box-shadow: -24px 0 54px -36px rgba(20, 22, 28, 0.4);
//   animation-name: sidebar-in;
// }
//
// @keyframes surface-in {
//   from { opacity: 0; transform: translateY(14px) scale(0.985); }
//   to { opacity: 1; transform: translateY(0) scale(1); }
// }
//
// @keyframes sidebar-in {
//   from { opacity: 0; transform: translateX(36px); }
//   to { opacity: 1; transform: translateX(0); }
// }
//
// .intelligence-header {
//   position: sticky;
//   z-index: 2;
//   top: 0;
//   height: 49px;
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   padding: 0 15px 0 17px;
//   border-bottom: 1px solid var(--line);
//   background: rgba(255, 255, 255, 0.94);
//   backdrop-filter: blur(18px);
// }
//
// .intelligence-brand {
//   gap: 11px;
// }
//
// .intelligence-brand > span {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   padding-left: 10px;
//   border-left: 1px solid var(--line-strong);
//   color: var(--faint);
//   font-size: 8px;
//   font-weight: 500;
//   letter-spacing: 0.04em;
//   text-transform: uppercase;
// }
//
// .intelligence-brand i {
//   width: 5px;
//   height: 5px;
//   border-radius: 999px;
//   background: var(--success);
//   box-shadow: 0 0 0 3px var(--success-soft);
// }
//
// .panel-controls {
//   display: flex;
//   gap: 2px;
// }
//
// .panel-controls button,
// .tray-header button,
// .action-preview header button,
// .dismiss-dialog header > button {
//   width: 29px;
//   height: 29px;
//   display: grid;
//   place-items: center;
//   padding: 0;
//   border: 0;
//   border-radius: 7px;
//   color: var(--mist);
//   background: transparent;
//   cursor: pointer;
// }
//
// .panel-controls button:hover,
// .tray-header button:hover,
// .action-preview header button:hover,
// .dismiss-dialog header > button:hover {
//   background: var(--surface);
// }
//
// .intelligence-body {
//   padding: 18px 19px 14px;
// }
//
// .card-meta-row {
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   color: var(--faint);
//   font-size: 8px;
//   font-variant-numeric: tabular-nums;
//   letter-spacing: 0.02em;
// }
//
// .priority-mark {
//   display: inline-flex;
//   align-items: center;
//   gap: 6px;
//   color: var(--ink-soft);
//   font-weight: 600;
//   letter-spacing: 0.06em;
//   text-transform: uppercase;
// }
//
// .priority-mark i {
//   width: 6px;
//   height: 6px;
//   border-radius: 999px;
//   background: var(--warn);
// }
//
// .priority-mark.critical i {
//   background: var(--error);
// }
//
// .priority-mark.medium i {
//   background: var(--success);
// }
//
// .intelligence-body h2,
// .tray-title h2,
// .action-heading h2,
// .dismiss-dialog h2 {
//   margin: 12px 0 0;
//   color: var(--ink);
//   font-size: 23px;
//   font-weight: 400;
//   letter-spacing: -0.035em;
//   line-height: 1.12;
// }
//
// .card-summary {
//   margin: 10px 0 0;
//   color: var(--mist);
//   font-size: 11px;
//   line-height: 1.6;
// }
//
// .why-now {
//   display: flex;
//   align-items: flex-start;
//   gap: 9px;
//   margin-top: 15px;
//   padding: 10px 11px;
//   border: 1px solid rgba(138, 45, 59, 0.12);
//   border-radius: 9px;
//   color: var(--accent);
//   background: var(--accent-soft);
// }
//
// .why-now.deferred {
//   border-color: rgba(20, 22, 30, 0.1);
//   color: var(--ink-soft);
//   background: var(--surface);
// }
//
// .why-now svg {
//   flex: 0 0 auto;
//   margin-top: 1px;
// }
//
// .why-now div {
//   display: flex;
//   flex-direction: column;
//   gap: 3px;
// }
//
// .why-now strong {
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .why-now span {
//   color: var(--mist);
//   font-size: 8px;
//   line-height: 1.45;
// }
//
// .context-strip {
//   display: grid;
//   grid-template-columns: 1fr auto;
//   gap: 3px 10px;
//   margin-top: 14px;
//   padding: 11px 0;
//   border-top: 1px solid var(--line);
//   border-bottom: 1px solid var(--line);
// }
//
// .context-strip > span {
//   grid-column: 1 / -1;
//   color: var(--faint);
//   font-size: 8px;
//   text-transform: uppercase;
// }
//
// .context-strip strong {
//   font-size: 10px;
//   font-weight: 600;
// }
//
// .context-strip small {
//   color: var(--mist);
//   font-size: 8px;
// }
//
// .why-section {
//   margin-top: 18px;
// }
//
// .micro-heading {
//   color: var(--faint);
//   font-size: 8px;
//   font-weight: 600;
//   letter-spacing: 0.09em;
//   text-transform: uppercase;
// }
//
// .why-section ul {
//   display: grid;
//   gap: 8px;
//   margin: 10px 0 0;
//   padding: 0;
//   list-style: none;
// }
//
// .why-section li {
//   display: flex;
//   align-items: flex-start;
//   gap: 8px;
//   color: var(--ink-soft);
//   font-size: 9px;
//   line-height: 1.4;
// }
//
// .why-section li svg {
//   flex: 0 0 auto;
//   margin-top: 1px;
//   color: var(--success);
// }
//
// .recommendation-box {
//   margin-top: 18px;
//   padding: 13px 14px;
//   border: 1px solid var(--line);
//   border-radius: 10px;
//   background: var(--canvas);
// }
//
// .recommendation-box p {
//   margin: 7px 0 0;
//   color: var(--ink);
//   font-size: 11px;
//   font-weight: 500;
//   line-height: 1.5;
// }
//
// .recommendation-meta {
//   display: flex;
//   align-items: center;
//   gap: 6px;
//   margin-top: 10px;
//   color: var(--mist);
//   font-size: 8px;
// }
//
// .recommendation-meta > span {
//   width: 3px;
//   height: 3px;
//   margin: 0 2px;
//   border-radius: 999px;
//   background: var(--faint);
// }
//
// .evidence-toggle {
//   width: 100%;
//   height: 37px;
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   margin-top: 9px;
//   padding: 0 2px;
//   border: 0;
//   border-bottom: 1px solid var(--line);
//   color: var(--mist);
//   background: transparent;
//   font-size: 9px;
//   cursor: pointer;
// }
//
// .evidence-toggle span {
//   display: flex;
//   align-items: center;
//   gap: 7px;
// }
//
// .evidence-toggle svg {
//   transition: transform 180ms ease;
// }
//
// .evidence-toggle svg.rotate {
//   transform: rotate(180deg);
// }
//
// .evidence-list {
//   padding: 4px 0 8px;
// }
//
// .evidence-list > div {
//   position: relative;
//   display: grid;
//   grid-template-columns: 1fr auto;
//   gap: 3px 12px;
//   padding: 10px 0;
//   border-bottom: 1px solid var(--line);
// }
//
// .evidence-source {
//   grid-column: 1 / -1;
//   color: var(--accent);
//   font-size: 7px;
//   font-weight: 600;
//   text-transform: uppercase;
// }
//
// .evidence-list strong {
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .evidence-list p {
//   grid-column: 1 / 2;
//   margin: 0;
//   color: var(--mist);
//   font-size: 8px;
//   line-height: 1.45;
// }
//
// .evidence-list time {
//   grid-column: 2;
//   grid-row: 2 / 4;
//   color: var(--faint);
//   font-size: 7px;
// }
//
// .evidence-list .consequence {
//   display: flex;
//   align-items: flex-start;
//   gap: 6px;
//   margin: 9px 0 0;
//   padding: 9px;
//   border-radius: 7px;
//   color: var(--error);
//   background: var(--error-soft);
// }
//
// .evidence-list .consequence svg {
//   flex: 0 0 auto;
// }
//
// .suggested-actions {
//   display: grid;
//   grid-template-columns: 1fr 1fr;
//   gap: 7px;
//   margin-top: 14px;
// }
//
// .suggested-actions button {
//   min-height: 36px;
//   display: inline-flex;
//   align-items: center;
//   justify-content: center;
//   gap: 7px;
//   padding: 0 10px;
//   border-radius: 8px;
//   font-size: 9px;
//   font-weight: 600;
//   cursor: pointer;
// }
//
// .suggested-actions button.primary {
//   border: 1px solid var(--ink);
//   color: white;
//   background: var(--ink);
// }
//
// .suggested-actions button.secondary {
//   border: 1px solid var(--line-strong);
//   color: var(--ink-soft);
//   background: white;
// }
//
// .quiet-actions {
//   display: flex;
//   align-items: center;
//   justify-content: center;
//   flex-wrap: wrap;
//   gap: 2px;
//   margin-top: 8px;
// }
//
// .quiet-actions button {
//   padding: 5px 7px;
//   border: 0;
//   border-radius: 6px;
//   color: var(--mist);
//   background: transparent;
//   font-size: 8px;
//   cursor: pointer;
// }
//
// .quiet-actions button:hover {
//   color: var(--ink);
//   background: var(--surface);
// }
//
// .intelligence-footer {
//   min-height: 35px;
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   padding: 0 17px;
//   border-top: 1px solid var(--line);
//   color: var(--faint);
//   background: var(--rail);
//   font-size: 7px;
// }
//
// .intelligence-footer span {
//   display: flex;
//   align-items: center;
//   gap: 5px;
// }
//
// .intelligence-tray {
//   position: absolute;
//   top: 68px;
//   right: 24px;
//   width: 455px;
//   max-height: calc(100% - 94px);
//   border-radius: 14px;
// }
//
// .tray-header {
//   height: 49px;
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   padding: 0 14px 0 17px;
//   border-bottom: 1px solid var(--line);
// }
//
// .tray-header > div {
//   display: flex;
//   align-items: center;
//   gap: 10px;
// }
//
// .tray-header > div > span {
//   padding-left: 10px;
//   border-left: 1px solid var(--line-strong);
//   color: var(--faint);
//   font-size: 8px;
//   letter-spacing: 0.06em;
//   text-transform: uppercase;
// }
//
// .tray-title {
//   display: flex;
//   align-items: flex-end;
//   justify-content: space-between;
//   gap: 16px;
//   padding: 18px 19px 14px;
// }
//
// .tray-title h2 {
//   max-width: 270px;
//   margin-top: 7px;
//   font-size: 18px;
// }
//
// .tray-quiet {
//   display: inline-flex;
//   align-items: center;
//   gap: 5px;
//   padding: 5px 7px;
//   border-radius: 6px;
//   color: var(--mist);
//   background: var(--surface);
//   font-size: 7px;
//   white-space: nowrap;
// }
//
// .tray-list {
//   padding: 0 9px 8px;
// }
//
// .tray-list > button {
//   position: relative;
//   width: 100%;
//   min-height: 75px;
//   display: grid;
//   grid-template-columns: 34px 1fr auto;
//   align-items: center;
//   gap: 10px;
//   padding: 10px;
//   overflow: hidden;
//   border: 1px solid transparent;
//   border-bottom-color: var(--line);
//   border-radius: 9px;
//   background: transparent;
//   text-align: left;
//   cursor: pointer;
// }
//
// .tray-list > button:hover,
// .tray-list > button.active {
//   border-color: var(--line);
//   background: var(--canvas);
// }
//
// .tray-list > button.active::before {
//   position: absolute;
//   top: 10px;
//   bottom: 10px;
//   left: 0;
//   width: 2px;
//   border-radius: 999px;
//   background: var(--accent);
//   content: "";
// }
//
// .tray-item-icon {
//   width: 32px;
//   height: 32px;
//   display: grid;
//   place-items: center;
//   border: 1px solid var(--line);
//   border-radius: 9px;
//   color: var(--ink-soft);
//   background: white;
// }
//
// .tray-item-icon.critical {
//   color: var(--error);
//   background: var(--error-soft);
// }
//
// .tray-item-copy {
//   min-width: 0;
//   display: flex;
//   flex-direction: column;
//   gap: 3px;
// }
//
// .tray-item-copy small {
//   color: var(--faint);
//   font-size: 7px;
// }
//
// .tray-item-copy strong {
//   overflow: hidden;
//   color: var(--ink);
//   font-size: 10px;
//   font-weight: 600;
//   text-overflow: ellipsis;
//   white-space: nowrap;
// }
//
// .tray-item-copy > span {
//   overflow: hidden;
//   color: var(--mist);
//   font-size: 8px;
//   text-overflow: ellipsis;
//   white-space: nowrap;
// }
//
// .tray-item-state {
//   display: flex;
//   align-items: center;
//   gap: 2px;
//   color: var(--faint);
//   font-size: 7px;
//   white-space: nowrap;
// }
//
// .tray-footer {
//   height: 41px;
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   padding: 0 16px;
//   border-top: 1px solid var(--line);
//   color: var(--faint);
//   background: var(--rail);
//   font-size: 7px;
// }
//
// .tray-footer span {
//   display: flex;
//   align-items: center;
//   gap: 5px;
// }
//
// .tray-footer button {
//   border: 0;
//   color: var(--ink-soft);
//   background: transparent;
//   font-size: 7px;
//   font-weight: 600;
// }
//
// .action-scrim {
//   position: absolute;
//   z-index: 70;
//   inset: 43px 0 0;
//   display: grid;
//   place-items: center;
//   padding: 24px;
//   background: rgba(20, 22, 28, 0.42);
//   backdrop-filter: blur(3px);
//   animation: fade-in 180ms ease both;
// }
//
// @keyframes fade-in {
//   from { opacity: 0; }
//   to { opacity: 1; }
// }
//
// .action-preview,
// .dismiss-dialog {
//   width: min(530px, 100%);
//   overflow: hidden;
//   border: 1px solid rgba(20, 22, 30, 0.16);
//   border-radius: 14px;
//   background: white;
//   box-shadow: var(--overlay-shadow);
//   animation: modal-in 320ms cubic-bezier(0.16, 1, 0.3, 1) both;
// }
//
// @keyframes modal-in {
//   from { opacity: 0; transform: translateY(18px) scale(0.98); }
//   to { opacity: 1; transform: none; }
// }
//
// .action-preview > header {
//   height: 47px;
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   padding: 0 13px 0 17px;
//   border-bottom: 1px solid var(--line);
// }
//
// .action-status {
//   display: flex;
//   align-items: center;
//   gap: 7px;
//   color: var(--success);
//   font-size: 8px;
//   font-weight: 600;
//   letter-spacing: 0.03em;
//   text-transform: uppercase;
// }
//
// .action-heading {
//   padding: 19px 21px 15px;
// }
//
// .action-heading h2 {
//   margin-top: 8px;
//   font-size: 21px;
// }
//
// .action-heading p,
// .dismiss-dialog > p {
//   margin: 7px 0 0;
//   color: var(--mist);
//   font-size: 10px;
//   line-height: 1.55;
// }
//
// .advice-preview,
// .task-preview,
// .schedule-options {
//   margin: 0 21px 19px;
//   overflow: hidden;
//   border: 1px solid var(--line);
//   border-radius: 10px;
//   background: var(--canvas);
// }
//
// .advice-context {
//   min-height: 60px;
//   display: grid;
//   grid-template-columns: 1fr auto;
//   gap: 4px 12px;
//   align-items: center;
//   padding: 10px 13px;
//   border-bottom: 1px solid var(--line);
//   background: white;
// }
//
// .advice-context span {
//   grid-column: 1 / -1;
//   color: var(--faint);
//   font-size: 7px;
//   letter-spacing: 0.06em;
//   text-transform: uppercase;
// }
//
// .advice-context strong {
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .advice-context small {
//   color: var(--mist);
//   font-size: 7px;
// }
//
// .advice-steps {
//   display: grid;
//   gap: 1px;
//   background: var(--line);
// }
//
// .advice-steps > div {
//   min-height: 54px;
//   display: grid;
//   grid-template-columns: 28px 1fr;
//   align-items: center;
//   gap: 8px;
//   padding: 9px 12px;
//   background: white;
// }
//
// .advice-steps span {
//   color: var(--accent);
//   font-size: 8px;
//   font-variant-numeric: tabular-nums;
// }
//
// .advice-steps p {
//   margin: 0;
//   color: var(--ink-soft);
//   font-size: 9px;
//   line-height: 1.5;
// }
//
// .advice-avoid {
//   display: flex;
//   align-items: flex-start;
//   gap: 8px;
//   margin: 9px;
//   padding: 9px;
//   border-radius: 8px;
//   color: var(--error);
//   background: var(--error-soft);
// }
//
// .advice-avoid svg {
//   flex: 0 0 auto;
// }
//
// .advice-avoid > span {
//   display: flex;
//   flex-direction: column;
//   gap: 3px;
//   color: var(--mist);
//   font-size: 8px;
//   line-height: 1.4;
// }
//
// .advice-avoid strong {
//   color: var(--error);
// }
//
// .source-note {
//   min-height: 33px;
//   display: flex;
//   align-items: center;
//   gap: 6px;
//   padding: 0 12px;
//   color: var(--mist);
//   font-size: 7px;
// }
//
// .task-preview {
//   padding: 14px;
// }
//
// .task-owner {
//   display: grid;
//   grid-template-columns: 34px 1fr auto;
//   align-items: center;
//   gap: 10px;
//   padding-bottom: 13px;
//   border-bottom: 1px solid var(--line);
// }
//
// .agent-avatar {
//   width: 34px;
//   height: 34px;
//   display: grid;
//   place-items: center;
//   border-radius: 9px;
//   color: white;
//   background: var(--ink);
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .task-owner > div {
//   display: flex;
//   flex-direction: column;
//   gap: 3px;
// }
//
// .task-owner small,
// .task-grid span {
//   color: var(--faint);
//   font-size: 7px;
//   text-transform: uppercase;
// }
//
// .task-owner strong {
//   font-size: 10px;
//   font-weight: 600;
// }
//
// .permission-chip {
//   padding: 4px 6px;
//   border: 1px solid rgba(47, 158, 85, 0.16);
//   border-radius: 6px;
//   color: var(--success);
//   background: var(--success-soft);
//   font-size: 7px;
//   font-weight: 600;
// }
//
// .task-grid {
//   display: grid;
//   grid-template-columns: 1fr 1fr;
//   gap: 1px;
//   margin-top: 1px;
//   overflow: hidden;
//   border-radius: 8px;
//   background: var(--line);
// }
//
// .task-grid > div {
//   min-height: 66px;
//   display: flex;
//   flex-direction: column;
//   gap: 6px;
//   padding: 10px;
//   background: white;
// }
//
// .task-grid strong {
//   color: var(--ink-soft);
//   font-size: 8px;
//   font-weight: 500;
//   line-height: 1.45;
// }
//
// .task-constraint {
//   display: flex;
//   align-items: flex-start;
//   gap: 8px;
//   margin-top: 12px;
//   padding: 10px;
//   border-radius: 8px;
//   color: var(--accent);
//   background: var(--accent-soft);
// }
//
// .task-constraint svg {
//   flex: 0 0 auto;
// }
//
// .task-constraint span {
//   display: flex;
//   flex-direction: column;
//   gap: 3px;
//   color: var(--mist);
//   font-size: 8px;
//   line-height: 1.4;
// }
//
// .task-constraint strong {
//   color: var(--accent);
//   font-size: 8px;
// }
//
// .schedule-options {
//   display: grid;
//   gap: 1px;
//   padding: 5px;
//   background: var(--surface);
// }
//
// .schedule-options button {
//   min-height: 53px;
//   display: grid;
//   grid-template-columns: 24px 1fr auto;
//   align-items: center;
//   gap: 8px;
//   padding: 0 10px;
//   border: 1px solid transparent;
//   border-radius: 8px;
//   color: var(--mist);
//   background: white;
//   text-align: left;
//   cursor: pointer;
// }
//
// .schedule-options button.active {
//   border-color: var(--line-strong);
//   color: var(--ink);
// }
//
// .schedule-options button > span {
//   display: flex;
//   flex-direction: column;
//   gap: 3px;
// }
//
// .schedule-options strong {
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .schedule-options small {
//   color: var(--faint);
//   font-size: 7px;
// }
//
// .action-preview > footer {
//   height: 54px;
//   display: flex;
//   align-items: center;
//   justify-content: flex-end;
//   gap: 7px;
//   padding: 0 16px;
//   border-top: 1px solid var(--line);
//   background: var(--rail);
// }
//
// .cancel-action,
// .confirm-action {
//   min-height: 33px;
//   padding: 0 12px;
//   border-radius: 8px;
//   font-size: 9px;
//   font-weight: 600;
//   cursor: pointer;
// }
//
// .cancel-action {
//   border: 1px solid var(--line-strong);
//   background: white;
// }
//
// .confirm-action {
//   display: flex;
//   align-items: center;
//   gap: 7px;
//   border: 1px solid var(--ink);
//   color: white;
//   background: var(--ink);
// }
//
// .dismiss-dialog {
//   width: min(420px, 100%);
//   padding-bottom: 12px;
// }
//
// .dismiss-dialog header {
//   display: flex;
//   align-items: flex-start;
//   justify-content: space-between;
//   padding: 19px 17px 0 20px;
// }
//
// .dismiss-dialog h2 {
//   margin-top: 7px;
//   font-size: 20px;
// }
//
// .dismiss-dialog > p {
//   padding: 0 20px;
// }
//
// .dismiss-options {
//   display: grid;
//   gap: 5px;
//   padding: 14px 12px 0;
// }
//
// .dismiss-options button {
//   min-height: 55px;
//   display: flex;
//   align-items: center;
//   justify-content: space-between;
//   padding: 0 12px;
//   border: 1px solid var(--line);
//   border-radius: 9px;
//   background: white;
//   text-align: left;
//   cursor: pointer;
// }
//
// .dismiss-options button:hover {
//   border-color: var(--line-strong);
//   background: var(--canvas);
// }
//
// .dismiss-options button > span {
//   display: flex;
//   flex-direction: column;
//   gap: 3px;
// }
//
// .dismiss-options strong {
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .dismiss-options small {
//   color: var(--mist);
//   font-size: 8px;
// }
//
// .toast {
//   position: absolute;
//   z-index: 100;
//   right: 28px;
//   bottom: 25px;
//   max-width: 430px;
//   min-height: 43px;
//   display: flex;
//   align-items: center;
//   gap: 9px;
//   padding: 9px 13px;
//   border: 1px solid rgba(255, 255, 255, 0.14);
//   border-radius: 10px;
//   color: white;
//   background: var(--ink);
//   box-shadow: var(--overlay-shadow);
//   font-size: 9px;
//   animation: toast-in 320ms cubic-bezier(0.16, 1, 0.3, 1) both;
// }
//
// .toast svg {
//   flex: 0 0 auto;
//   color: #76d091;
// }
//
// @keyframes toast-in {
//   from { opacity: 0; transform: translateY(10px); }
//   to { opacity: 1; transform: translateY(0); }
// }
//
// .scenario-dock {
//   position: absolute;
//   z-index: 75;
//   bottom: 17px;
//   left: 50%;
//   display: grid;
//   grid-template-columns: repeat(5, minmax(132px, 1fr));
//   gap: 3px;
//   padding: 4px;
//   border: 1px solid rgba(20, 22, 30, 0.13);
//   border-radius: 12px;
//   background: rgba(255, 255, 255, 0.82);
//   box-shadow: 0 18px 44px -28px rgba(20, 22, 28, 0.5);
//   backdrop-filter: blur(18px);
//   transform: translateX(-50%);
// }
//
// .scenario-dock button {
//   position: relative;
//   min-height: 58px;
//   display: grid;
//   grid-template-columns: 26px 1fr;
//   align-items: center;
//   gap: 8px;
//   padding: 7px 10px;
//   overflow: hidden;
//   border: 0;
//   border-radius: 8px;
//   color: var(--mist);
//   background: transparent;
//   text-align: left;
//   cursor: pointer;
// }
//
// .scenario-dock button:hover {
//   background: var(--canvas);
// }
//
// .scenario-dock button.active {
//   color: white;
//   background: var(--ink);
// }
//
// .scenario-number {
//   color: var(--faint);
//   font-size: 8px;
//   font-variant-numeric: tabular-nums;
// }
//
// .scenario-dock button.active .scenario-number {
//   color: rgba(255, 255, 255, 0.55);
// }
//
// .scenario-dock button > span:nth-child(2) {
//   min-width: 0;
//   display: flex;
//   flex-direction: column;
//   gap: 3px;
// }
//
// .scenario-dock strong,
// .scenario-dock small {
//   overflow: hidden;
//   text-overflow: ellipsis;
//   white-space: nowrap;
// }
//
// .scenario-dock strong {
//   font-size: 9px;
//   font-weight: 600;
// }
//
// .scenario-dock small {
//   color: var(--faint);
//   font-size: 7px;
// }
//
// .scenario-dock button.active small {
//   color: rgba(255, 255, 255, 0.5);
// }
//
// .dock-progress {
//   position: absolute;
//   right: 0;
//   bottom: 0;
//   left: 0;
//   height: 2px;
//   background: rgba(255, 255, 255, 0.16);
// }
//
// .dock-progress.running::after {
//   display: block;
//   width: 100%;
//   height: 100%;
//   background: white;
//   content: "";
//   transform-origin: left;
//   animation: scenario-progress 8s linear both;
// }
//
// @keyframes scenario-progress {
//   from { transform: scaleX(0); }
//   to { transform: scaleX(1); }
// }
//
// .is-presentation .stage {
//   padding: 20px;
// }
//
// .is-presentation .browser-frame {
//   width: min(1600px, 100%);
// }
//
// .presentation-exit {
//   position: absolute;
//   z-index: 90;
//   top: 29px;
//   left: 50%;
//   height: 29px;
//   display: flex;
//   align-items: center;
//   gap: 7px;
//   padding: 0 9px;
//   border: 1px solid rgba(255, 255, 255, 0.12);
//   border-radius: 8px;
//   color: rgba(255, 255, 255, 0.75);
//   background: rgba(20, 22, 28, 0.72);
//   font-size: 8px;
//   opacity: 0;
//   cursor: pointer;
//   transform: translateX(-50%);
//   transition: opacity 160ms ease;
// }
//
// .presentation-exit span {
//   padding: 2px 4px;
//   border-radius: 4px;
//   background: rgba(255, 255, 255, 0.1);
// }
//
// .presentation-exit:hover {
//   opacity: 1;
// }
//
// @media (max-width: 1180px) {
//   .studio-bar {
//     grid-template-columns: 1fr auto;
//   }
//
//   .studio-status {
//     display: none;
//   }
//
//   .scenario-dock {
//     grid-template-columns: repeat(5, 120px);
//   }
//
//   .mail-list {
//     width: 230px;
//   }
//
//   .mail-reader {
//     left: 406px;
//   }
//
//   .metric-grid {
//     grid-template-columns: repeat(2, 1fr);
//   }
// }
//
// @media (max-height: 780px) {
//   .stage {
//     padding-top: 75px;
//     padding-bottom: 89px;
//   }
//
//   .scenario-dock {
//     bottom: 10px;
//   }
//
//   .scenario-dock button {
//     min-height: 50px;
//   }
//
//   .intelligence-panel.popover,
//   .intelligence-tray {
//     top: 57px;
//     max-height: calc(100% - 71px);
//   }
//
//   .intelligence-body {
//     padding-top: 14px;
//   }
//
//   .intelligence-body h2 {
//     font-size: 20px;
//   }
// }
//
// @media (prefers-reduced-motion: reduce) {
//   *,
//   *::before,
//   *::after {
//     scroll-behavior: auto !important;
//     animation-duration: 0.01ms !important;
//     animation-iteration-count: 1 !important;
//     transition-duration: 0.01ms !important;
//   }
// }
```

#### `src/vite-env.d.ts`

```ts
// /// <reference types="vite/client" />
```

## 8 · Building and checking

The DMG script with the fixed local signature, the older signing and reader-build scripts, and the browser preview harness (stand-ins for the Rust core and the brain) the render checks run on.

#### `scripts/mac-dev-dmg.sh`

```bash
# #!/bin/zsh
# # The installable test app, signed with a FIXED local identity, in a DMG named by its version.
# #
# # Why: an ad-hoc signed build (tauri's "-") gets a new code hash every time, and macOS ties the
# # Accessibility grant to that hash — so each new install met an old entry and was refused, while
# # Settings showed GeniOS switched on (22 Oct 2026: tccd held 85a8e081…, the app ran as dc5c9727…).
# # Signed with one certificate, every build has the same designated requirement
# #   identifier "ai.genios.desktop" and certificate leaf = H"…"
# # and the grant given once holds for every later build. The identity is local to this Mac
# # (~/.genios-dev-signing, its own keychain, never the login keychain, never in the repo); it is
# # created on the first run. It is not an Apple Developer ID: Gatekeeper does not know it, which
# # does not matter for a DMG built and opened on the same Mac.
# #
# # The volume is "GeniOS <version>", so an old disk image left mounted can't be mistaken for it.
# #
# # Usage: scripts/mac-dev-dmg.sh   (from Extension/; prints the DMG's path)
# set -euo pipefail
# cd "$(dirname "$0")/.."
#
# SIGN="$HOME/.genios-dev-signing"
# KC="$SIGN/genios-dev.keychain-db"
# NAME="GeniOS Local Development"
#
# if [[ ! -f "$KC" ]]; then
#   mkdir -p "$SIGN" && chmod 700 "$SIGN"
#   openssl rand -hex 24 > "$SIGN/keychain.pass" && chmod 600 "$SIGN/keychain.pass"
#   cat > "$SIGN/cert.cnf" <<CNF
# [req]
# distinguished_name = dn
# x509_extensions = ext
# prompt = no
# [dn]
# CN = $NAME
# [ext]
# basicConstraints = critical,CA:false
# keyUsage = critical,digitalSignature
# extendedKeyUsage = critical,codeSigning
# CNF
#   openssl req -x509 -newkey rsa:2048 -nodes -keyout "$SIGN/key.pem" -out "$SIGN/cert.pem" -days 3650 -config "$SIGN/cert.cnf" 2>/dev/null
#   chmod 600 "$SIGN/key.pem"
#   P12PASS=$(openssl rand -hex 16)
#   openssl pkcs12 -export -inkey "$SIGN/key.pem" -in "$SIGN/cert.pem" -name "$NAME" -out "$SIGN/id.p12" -passout "pass:$P12PASS"
#   security create-keychain -p "$(cat "$SIGN/keychain.pass")" "$KC"
#   security set-keychain-settings "$KC"
#   security unlock-keychain -p "$(cat "$SIGN/keychain.pass")" "$KC"
#   security import "$SIGN/id.p12" -k "$KC" -P "$P12PASS" -T /usr/bin/codesign >/dev/null
#   security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$(cat "$SIGN/keychain.pass")" "$KC" >/dev/null
#   rm -f "$SIGN/id.p12"
# fi
#
# VERSION=$(node -p "require('./package.json').version")
# npx tauri build --debug --bundles app
#
# APP=src-tauri/target/debug/bundle/macos/GeniOS.app
# security unlock-keychain -p "$(cat "$SIGN/keychain.pass")" "$KC"
# ID=$(security find-identity -p codesigning "$KC" | awk -v n="\"$NAME\"" 'index($0, n) {print $2; exit}')
# [[ -n "$ID" ]] || { echo "no signing identity in $KC" >&2; exit 1; }
# codesign --force --deep --options runtime --keychain "$KC" --sign "$ID" "$APP"
# codesign --verify --deep --strict "$APP"
#
# OUT=src-tauri/target/debug/bundle/dmg
# mkdir -p "$OUT"
# DMG="$OUT/GeniOS_${VERSION}_aarch64.dmg"
# STAGE=$(mktemp -d)
# cp -R "$APP" "$STAGE/"
# ln -s /Applications "$STAGE/Applications"
# rm -f "$DMG"
# hdiutil create -quiet -volname "GeniOS $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
# rm -rf "$STAGE"
# hdiutil verify -quiet "$DMG"
# echo "$DMG"
```

#### `scripts/sign-macos.sh`

```bash
# #!/usr/bin/env bash
# # Ad-hoc sign the built macOS bundle.
# #
# # Without this, the .app carries only the linker's signature: its code identity
# # reads `app-<hash>` instead of ai.genios.desktop and no resources are sealed.
# # macOS then refuses the Accessibility grant even though System Settings shows
# # the toggle on, because TCC matches on code identity, not on Info.plist.
# #
# # Usage: scripts/sign-macos.sh [path/to/GeniOS.app]
# set -euo pipefail
#
# # Windows and Linux bundles are built from this same script set.
# [ "$(uname)" = "Darwin" ] || exit 0
#
# APP="${1:-src-tauri/target/release/bundle/macos/GeniOS.app}"
# [ -d "$APP" ] || { echo "sign-macos: no bundle at $APP" >&2; exit 1; }
#
# codesign --force --deep --sign - "$APP"
# codesign --verify --deep --strict "$APP"
#
# desc=$(codesign -dv --verbose=2 "$APP" 2>&1)
# id=$(printf '%s\n' "$desc" | sed -n 's/^Identifier=//p')
# want=$(/usr/libexec/PlistBuddy -c "print :CFBundleIdentifier" "$APP/Contents/Info.plist")
#
# # A linker-signed bundle seals no resources and reports `app-<hash>` as its
# # identity, so TCC never matches it. That is the state this script exists to
# # prevent; fail loudly rather than ship a build whose grant silently won't hold.
# case "$desc" in
#   *linker-signed*) echo "sign-macos: still linker-signed — codesign did not take" >&2; exit 1 ;;
# esac
# if [ "$id" != "$want" ]; then
#   echo "sign-macos: identity is '$id', expected '$want' — the Accessibility grant will not hold" >&2
#   exit 1
# fi
#
# echo "sign-macos: $APP signed as $id"
```

#### `scripts/build-sidecar.sh`

```bash
# #!/usr/bin/env bash
# # Build the genios-ax sidecar (release) and put it where Tauri's `bundle.externalBin`
# # (tauri.macos.conf.json → "binaries/genios-ax") expects it:
# #     src-tauri/binaries/genios-ax-<target-triple>          (gitignored)
# #
# # Usage:
# #   scripts/build-sidecar.sh                 # $TAURI_ENV_TARGET_TRIPLE (set by `tauri dev/build`), else host
# #   scripts/build-sidecar.sh <triple>        # aarch64-apple-darwin | x86_64-apple-darwin | universal-apple-darwin
# #   scripts/build-sidecar.sh --all           # all three (release builds / CI)
# #
# # Works with Command Line Tools only (no Xcode): each arch is built with `--triple`, and the
# # universal binary is `lipo -create`d (SPIKE_RESULTS.md "Build"). No-op on non-macOS hosts.
# set -euo pipefail
#
# root="$(cd "$(dirname "$0")/.." && pwd)"
# pkg="$root/src-tauri/sidecar/genios-ax"
# out="$root/src-tauri/binaries"
# scratch="$root/src-tauri/target/genios-ax"
#
# if [[ "$(uname -s)" != "Darwin" ]]; then
#   echo "build-sidecar: genios-ax is macOS-only; nothing to do on $(uname -s)"
#   exit 0
# fi
#
# host="$(rustc -vV | sed -n 's/^host: //p')"
# want="${1:-${TAURI_ENV_TARGET_TRIPLE:-$host}}"
#
# swift_triple() {
#   case "$1" in
#     aarch64-apple-darwin) echo "arm64-apple-macosx13.0" ;;
#     x86_64-apple-darwin) echo "x86_64-apple-macosx13.0" ;;
#     *) return 1 ;;
#   esac
# }
#
# # build_arch <rust-triple> → prints the built binary path
# build_arch() {
#   local st
#   st="$(swift_triple "$1")"
#   swift build -c release --package-path "$pkg" --triple "$st" --scratch-path "$scratch/$1" >&2
#   echo "$(swift build -c release --package-path "$pkg" --triple "$st" --scratch-path "$scratch/$1" --show-bin-path)/genios-ax"
# }
#
# place() { # <src> <rust-triple>
#   install -m 0755 "$1" "$out/genios-ax-$2"
#   echo "build-sidecar: $out/genios-ax-$2 ($(lipo -archs "$out/genios-ax-$2"))"
# }
#
# mkdir -p "$out"
# case "$want" in
#   --all | universal-apple-darwin)
#     arm="$(build_arch aarch64-apple-darwin)"
#     x86="$(build_arch x86_64-apple-darwin)"
#     lipo -create "$arm" "$x86" -output "$out/genios-ax-universal-apple-darwin"
#     chmod 0755 "$out/genios-ax-universal-apple-darwin"
#     echo "build-sidecar: $out/genios-ax-universal-apple-darwin ($(lipo -archs "$out/genios-ax-universal-apple-darwin"))"
#     if [[ "$want" == "--all" ]]; then
#       place "$arm" aarch64-apple-darwin
#       place "$x86" x86_64-apple-darwin
#     fi
#     ;;
#   aarch64-apple-darwin | x86_64-apple-darwin)
#     place "$(build_arch "$want")" "$want"
#     ;;
#   *)
#     echo "build-sidecar: target $want is not macOS; nothing to do"
#     ;;
# esac
```

#### `scripts/preview/.gitignore`

```
# out/
```

#### `scripts/preview/check.mjs`

```js
// #!/usr/bin/env node
// // The render check: the panel, its parts and the toasts drawn in Chromium with Tauri swapped for
// // the stand-ins (tauri-mock/) and the brain for mock_brain.py, then asserted on. Exit code only:
// // 0 when every selected check passed, 1 when one failed, 2 when the check could not run at all.
// //
// //   node Extension/scripts/preview/check.mjs [--only a,b] [--out dir] [--keep]
// //
// // Each check is one file in checks/ — `export default { name, run(t) }` — added by the unit it
// // verifies. `--keep` leaves the brain (:8032) and the app (:5199) running to look at by hand.
// import { spawn } from "node:child_process";
// import { createRequire } from "node:module";
// import { mkdirSync, readdirSync } from "node:fs";
// import { homedir } from "node:os";
// import { dirname, join, resolve } from "node:path";
// import { fileURLToPath, pathToFileURL } from "node:url";
//
// const HERE = dirname(fileURLToPath(import.meta.url));
// const EXT = resolve(HERE, "../..");
// const BRAIN = "http://localhost:8032";
// const APP = "http://localhost:5199";
//
// const argv = process.argv.slice(2);
// const flag = (name) => {
//   const i = argv.indexOf(name);
//   return i >= 0 ? argv[i + 1] : undefined;
// };
// const only = (flag("--only") ?? "").split(",").map((s) => s.trim()).filter(Boolean);
// const OUT = resolve(flag("--out") ?? join(HERE, "out"));
// const keep = argv.includes("--keep");
// mkdirSync(OUT, { recursive: true });
//
// function loadPlaywright() {
//   const places = [
//     process.env.PLAYWRIGHT_DIR && join(process.env.PLAYWRIGHT_DIR, "/"),
//     join(EXT, "package.json"),
//     join(homedir(), ".claude/skills/gstack/node_modules/"),
//   ].filter(Boolean);
//   for (const p of places) {
//     try {
//       return createRequire(p)("playwright");
//     } catch {
//       /* next place */
//     }
//   }
//   return null;
// }
//
// const playwright = loadPlaywright();
// if (!playwright) {
//   console.error("playwright not found (PLAYWRIGHT_DIR, Extension/node_modules, ~/.claude/skills/gstack). The check did not run.");
//   process.exit(2);
// }
//
// const up = async (url) => {
//   try {
//     const r = await fetch(url, { signal: AbortSignal.timeout(800) });
//     return r.status < 500;
//   } catch {
//     return false;
//   }
// };
// async function waitUp(url, what) {
//   for (let i = 0; i < 80; i++) {
//     if (await up(url)) return;
//     await new Promise((r) => setTimeout(r, 250));
//   }
//   throw new Error(`${what} did not start (${url})`);
// }
//
// const children = [];
// if (!(await up(`${BRAIN}/cards`))) {
//   children.push(spawn("python3", [join(HERE, "mock_brain.py"), "8032"], { stdio: "ignore" }));
// }
// if (!(await up(`${APP}/desktop.html`))) {
//   children.push(
//     spawn(process.execPath, [join(EXT, "node_modules/vite/bin/vite.js"), "--config", join(HERE, "vite.preview.mjs"), "--logLevel", "error"], {
//       cwd: EXT,
//       stdio: ["ignore", "ignore", "inherit"],
//     }),
//   );
// }
// const stop = () => children.forEach((c) => c.kill());
// process.on("exit", () => keep || stop());
//
// let failures = 0;
// let browser;
// try {
//   await waitUp(`${BRAIN}/cards`, "the stand-in brain");
//   await waitUp(`${APP}/desktop.html`, "the preview server");
//   browser = await playwright.chromium.launch();
//
//   // Warm the dependency optimiser once, so no check sees Vite reload the page under it.
//   for (const page of ["desktop.html", "lane.html", "scripts/preview/gallery.html"]) {
//     const p = await browser.newPage();
//     await p.goto(`${APP}/${page}`, { waitUntil: "networkidle" }).catch(() => {});
//     await p.close();
//   }
//
//   const files = readdirSync(join(HERE, "checks")).filter((f) => f.endsWith(".mjs")).sort();
//   const checks = [];
//   for (const f of files) checks.push((await import(pathToFileURL(join(HERE, "checks", f)).href)).default);
//   const known = new Set(checks.map((c) => c.name));
//   const missing = only.filter((n) => !known.has(n));
//   if (missing.length) throw new Error(`no check named ${missing.join(", ")} (known: ${[...known].join(", ")})`);
//   const selected = only.length ? checks.filter((c) => only.includes(c.name)) : checks;
//
//   for (const check of selected) {
//     const pages = [];
//     const posts = [];
//     const reset = await fetch(`${BRAIN}/__reset`, { method: "POST" });
//     if (!reset.ok) throw new Error("the server on :8032 is not this stand-in brain (no /__reset)");
//
//     const open = async (url, { colorScheme = "light", width = 420, height = 580 } = {}) => {
//       const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 2, colorScheme });
//       page.errors = [];
//       page.on("pageerror", (e) => page.errors.push(String(e)));
//       page.on("console", (m) => {
//         if (m.type() === "error" && !/Failed to load resource|favicon/i.test(m.text())) page.errors.push(`console: ${m.text()}`);
//       });
//       page.on("response", async (r) => {
//         if (r.request().method() !== "POST" || !r.url().startsWith(BRAIN)) return;
//         let sent = {};
//         try {
//           sent = JSON.parse(r.request().postData() || "{}");
//         } catch {
//           /* not JSON */
//         }
//         posts.push({ url: r.url(), status: r.status(), sent, got: await r.text().catch(() => "") });
//       });
//       await page.goto(url, { waitUntil: "networkidle" });
//       await page.waitForTimeout(350);
//       pages.push(page);
//       return page;
//     };
//
//     const t = {
//       APP,
//       BRAIN,
//       posts,
//       panel: (s = "normal", o) => open(`${APP}/desktop.html?s=${s}`, o),
//       gallery: (p, o = {}) => open(`${APP}/scripts/preview/gallery.html?p=${p}&s=${o.s ?? "normal"}&w=${o.width ?? 420}&h=${o.height ?? 580}`, o),
//       lane: (toast, o = {}) => open(`${APP}/lane.html?toast=${toast}`, { width: 396, height: 280, ...o }),
//       calls: (page) => page.evaluate(() => window.__calls),
//       shot: (page, name) => page.screenshot({ path: join(OUT, `${check.name}-${name}.png`) }),
//       wait: (ms) => new Promise((r) => setTimeout(r, ms)),
//       ok(cond, msg) {
//         if (!cond) throw new Error(msg);
//       },
//       text: (page, sel = "#root") => page.locator(sel).first().innerText(),
//       /** Words that must not reach a person: engine names, an unread value, a server address. */
//       async noWords(page, patterns, sel = "#root") {
//         const text = await page.locator(sel).first().innerText();
//         const hit = patterns.filter((p) => p.test(text));
//         if (hit.length) throw new Error(`shows ${hit.join(", ")}`);
//       },
//       /** Every visible piece of text at `min` px or more. */
//       async fontFloor(page, min = 12, sel = "#root") {
//         const small = await page.evaluate(
//           ({ min, sel }) => {
//             const out = [];
//             for (const el of document.querySelectorAll(`${sel} *`)) {
//               const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
//               if (!own || !el.getClientRects().length) continue;
//               const size = parseFloat(getComputedStyle(el).fontSize);
//               if (size < min) out.push(`${size}px “${el.textContent.trim().slice(0, 28)}”`);
//             }
//             return [...new Set(out)];
//           },
//           { min, sel },
//         );
//         if (small.length) throw new Error(`${small.length} text styles under ${min}px: ${small.slice(0, 6).join(" · ")}`);
//       },
//       /** Ink and greys carry state; the only hue is burgundy (where the founder is needed). */
//       async palette(page, sel = "#root") {
//         const bad = await page.evaluate((sel) => {
//           const parse = (c) => {
//             const m = c.match(/rgba?\(([^)]+)\)/);
//             if (!m) return null;
//             const [r, g, b, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
//             return { r: r / 255, g: g / 255, b: b / 255, a };
//           };
//           const hsl = ({ r, g, b }) => {
//             const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
//             if (max === min) return { h: 0, s: 0, l };
//             const d = max - min;
//             const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
//             const h = max === r ? ((g - b) / d + (g < b ? 6 : 0)) * 60 : max === g ? ((b - r) / d + 2) * 60 : ((r - g) / d + 4) * 60;
//             return { h, s, l };
//           };
//           const out = new Map();
//           for (const el of document.querySelectorAll(`${sel}, ${sel} *`)) {
//             if (!el.getClientRects().length) continue;
//             const cs = getComputedStyle(el);
//             const props = ["color", "backgroundColor"];
//             if (parseFloat(cs.borderTopWidth) > 0) props.push("borderTopColor");
//             if (parseFloat(cs.borderLeftWidth) > 0) props.push("borderLeftColor");
//             for (const prop of props) {
//               const c = parse(cs[prop]);
//               if (!c || c.a < 0.08) continue;
//               const { h, s, l } = hsl(c);
//               // A grey with a slight hue (the web's cool ink, rgb 20 22 30) is still a grey: judge by chroma.
//               const chroma = Math.max(c.r, c.g, c.b) - Math.min(c.r, c.g, c.b);
//               const neutral = chroma < 0.1 || s < 0.2 || l > 0.94 || l < 0.06;
//               const burgundy = h >= 330 || h <= 12;
//               if (!neutral && !burgundy) out.set(cs[prop], `${prop} ${cs[prop]} on ${el.tagName.toLowerCase()}.${[...el.classList].join(".")}`);
//             }
//           }
//           return [...out.values()];
//         }, sel);
//         if (bad.length) throw new Error(`${bad.length} colours outside ink, greys and burgundy: ${bad.slice(0, 5).join(" · ")}`);
//       },
//     };
//
//     const started = Date.now();
//     try {
//       await check.run(t);
//       const errors = pages.flatMap((p) => p.errors);
//       if (errors.length) throw new Error(`page errors: ${errors.slice(0, 3).join(" | ")}`);
//       console.log(`PASS  ${check.name.padEnd(14)} ${((Date.now() - started) / 1000).toFixed(1)}s`);
//     } catch (e) {
//       failures += 1;
//       console.log(`FAIL  ${check.name.padEnd(14)} ${String(e.message ?? e).split("\n")[0]}`);
//       await pages.at(-1)?.screenshot({ path: join(OUT, `${check.name}-FAILED.png`) }).catch(() => {});
//     }
//     for (const p of pages) await p.close().catch(() => {});
//   }
// } catch (e) {
//   console.error(`could not run: ${e.message ?? e}`);
//   await browser?.close();
//   if (!keep) stop();
//   process.exit(2);
// }
//
// await browser?.close();
// if (keep) console.log(`kept running: ${APP}/desktop.html · ${APP}/scripts/preview/gallery.html?p=… · brain ${BRAIN}`);
// else stop();
// console.log(`${failures ? "FAILED" : "OK"} · screenshots in ${OUT}`);
// process.exit(failures ? 1 : 0);
```

#### `scripts/preview/checks/actions.mjs`

```js
// // The buttons, end to end against the stand-in brain: Done waits five seconds with Undo, then lands;
// // a refusal brings the card back and says why; Later sends its option; Feedback sends a reason;
// // a question takes an answer and never offers Done.
// const posts = (t, action) => t.posts.filter((p) => p.sent.action === action);
//
// export default {
//   name: "actions",
//   async run(t) {
//     const page = await t.panel("normal");
//     const row = (id) => page.locator(`[data-card="${id}"]`);
//     await row("c-evokoa").locator(".dx-tag").first().waitFor({ timeout: 8000 });
//
//     await row("c-evokoa").getByRole("button", { name: /^Done/ }).click();
//     t.ok((await row("c-evokoa").count()) === 0, "Done did not take the card off the list");
//     await page.getByRole("button", { name: "Undo" }).click();
//     await row("c-evokoa").waitFor();
//     await t.wait(5600);
//     t.ok(posts(t, "do_it_myself").length === 0, "Undo still sent the press");
//
//     await row("c-evokoa").getByRole("button", { name: /^Done/ }).click();
//     await t.wait(5800);
//     const done = posts(t, "do_it_myself");
//     t.ok(done.length === 1 && done[0].status === 200 && done[0].sent.surface === "desktop", "Done did not land from the desktop");
//     t.ok((await row("c-evokoa").count()) === 0, "a done card came back");
//
//     await row("c-f55").locator(".dx-row-open").click();
//     await page.getByRole("button", { name: "Done", exact: true }).click();
//     await t.wait(5800);
//     await row("c-f55").waitFor({ timeout: 4000 });
//     t.ok((await t.text(page)).includes("This card is assigned to someone else."), "a refused Done does not say why");
//
//     await row("c-f26").locator(".dx-row-open").click();
//     await page.getByRole("button", { name: "Later" }).click();
//     await page.getByRole("menuitem", { name: "Tomorrow, 9:00" }).click();
//     await t.wait(5800);
//     const later = posts(t, "snooze");
//     t.ok(later.length === 1 && later[0].sent.snooze_option === "tomorrow_09" && later[0].status === 200, "Later did not send its option");
//
//     await row("c-f24").locator(".dx-row-open").click();
//     await page.getByRole("button", { name: "Feedback" }).click();
//     await page.getByRole("button", { name: "Not relevant to me" }).click();
//     await page.getByRole("button", { name: "Send", exact: true }).click();
//     await page.getByText("Feedback sent.").waitFor({ timeout: 4000 });
//     const wrong = posts(t, "wrong");
//     t.ok(wrong.length === 1 && wrong[0].sent.reason === "not_relevant" && wrong[0].status === 200, "Feedback did not send its reason");
//
//     await row("c-f22").locator(".dx-row-open").click();
//     const card = page.getByRole("article", { name: "Card" });
//     t.ok((await page.getByRole("button", { name: "Done", exact: true }).count()) === 0, "a question offers Done");
//     await card.getByRole("textbox").fill("Yes, incubated at the campus cell since March.");
//     await page.getByRole("button", { name: "Send answer" }).click();
//     await page.getByText("Your answer is in.").waitFor({ timeout: 6000 });
//     const answer = posts(t, "answer");
//     t.ok(answer.length === 1 && answer[0].status === 200 && answer[0].sent.words === "Yes, incubated at the campus cell since March.", "the answer did not land");
//     t.ok(t.posts.every((p) => p.status < 300 || p.url.includes("c-f55")), `a press was refused: ${t.posts.filter((p) => p.status >= 300).map((p) => p.got).join(" | ")}`);
//     await t.shot(page, "answered");
//   },
// };
```

#### `scripts/preview/checks/boot.mjs`

```js
// // The three pages load and draw something, with no page error.
// export default {
//   name: "boot",
//   async run(t) {
//     const panel = await t.panel("normal");
//     t.ok((await panel.locator("#root > *").count()) > 0, "the panel drew nothing");
//     const lane = await t.lane("advice");
//     t.ok((await lane.locator("#root > *").count()) > 0, "the lane drew nothing");
//     const gallery = await t.gallery("__none__");
//     t.ok(/No preview named/.test(await t.text(gallery, "body")), "the gallery did not answer an unknown part");
//   },
// };
```

#### `scripts/preview/checks/detail-order.mjs`

```js
// // An opened card: its own page in Rohit's order — recommendation, what · why · how, what it gets
// // you (goal, deadline), where it came from — the rest under Show more; only its own details.
// export default {
//   name: "detail-order",
//   async run(t) {
//     for (const colorScheme of ["light", "dark"]) {
//       const page = await t.panel("normal", { colorScheme });
//       await page.locator('[data-card="c-evokoa"] .dx-row-open').click();
//       const card = page.getByRole("article", { name: "Card" });
//       await card.waitFor({ timeout: 8000 });
//       await t.fontFloor(page);
//       await t.palette(page);
//       await t.shot(page, colorScheme);
//     }
//     const page = await t.panel("normal");
//     await page.locator('[data-card="c-f24"] .dx-row-open').click();
//     const card = page.getByRole("article", { name: "Card" });
//     await card.waitFor();
//     const order = await card.locator(":scope > section[aria-label], :scope > p[aria-label]").evaluateAll((s) => s.map((x) => x.getAttribute("aria-label")));
//     const want = ["Recommendation", "What, why, how", "What it gets you", "Where it came from", "Show more"];
//     t.ok(JSON.stringify(order) === JSON.stringify(want), `order: ${order.join(" · ")}`);
//     const text = await card.innerText();
//     const move = "Upload the Phase-1 review deck to the cohort folder by the twenty-eighth";
//     t.ok(text.split(move).length - 1 === 1, "the move is said more than once before Show more");
//     t.ok(text.includes("Divya Raman") && text.includes("by 28 Sep") && text.includes("Not linked to a goal yet"), "who, deadline or goal is missing");
//     await page.getByRole("button", { name: "Show more" }).click();
//     const details = await card.innerText();
//     t.ok(details.includes("Please upload your Phase-1 review deck to the cohort folder by 28 Sep."), "Details does not quote the mail");
//     t.ok(!details.includes("Weekly founders sync"), "a meeting every card carries is shown as this card's detail");
//     await t.noWords(page, [/undefined/, /expert_check/, /card_lines/, /reasoning_trace/, /\bnull\b/]);
//     await page.getByRole("tab", { name: "If it slips" }).click();
//     t.ok((await card.innerText()).includes("The review goes ahead without your deck."), "If it slips does not say what doing nothing costs");
//     await t.shot(page, "show-more");
//   },
// };
```

#### `scripts/preview/checks/face.mjs`

```js
// // A card's face: where it came from, its own subject and move, who and by when; a question asks
// // for an answer instead of offering Done; the circle marks done and the rest of the row opens.
// export default {
//   name: "face",
//   async run(t) {
//     for (const colorScheme of ["light", "dark"]) {
//       const page = await t.gallery("faces", { colorScheme, height: 1500 });
//       await page.locator('[data-card="c-f24"] .dx-tag').first().waitFor({ timeout: 8000 });
//       await t.fontFloor(page);
//       await t.palette(page);
//       await t.noWords(page, [/undefined/, /expert_check/, /card_lines/, /reasoning_trace/, /\bnull\b/]);
//       await t.shot(page, colorScheme);
//     }
//     const page = await t.gallery("faces", { height: 1500 });
//     const row = (id) => page.locator(`[data-card="${id}"]`);
//     await row("c-f24").locator(".dx-tag").first().waitFor();
//     for (const id of ["c-evokoa", "c-f24", "c-f26", "c-f22", "c-f55", "c-f15"]) {
//       t.ok((await row(id).locator(".dx-tag").count()) > 0, `${id}: no tool tag`);
//     }
//     const f24 = await row("c-f24").innerText();
//     t.ok(f24.includes("Upload the Phase-1 review deck to the cohort folder by the twenty-eighth"), "the Phase-1 face does not say its own move");
//     t.ok(f24.includes("Divya Raman") && f24.includes("by 28 Sep"), "the Phase-1 face does not say who and by when");
//     const evokoa = await row("c-evokoa").innerText();
//     t.ok(evokoa.includes("How: Reply in the thread: Thursday 4 pm works"), "the Evokoa face does not say how");
//     t.ok(evokoa.includes("Ananya Rao") && evokoa.includes("High"), "the Evokoa face does not say who, or that it is pressing");
//     t.ok((await row("c-f22").getByRole("button", { name: /^Done/ }).count()) === 0, "a question offers Done");
//     t.ok((await row("c-f22").innerText()).includes("Answer it"), "a question does not ask for an answer");
//     t.ok((await row("c-f26").innerText()).includes("Also on your screen: Send Neha the investor deck"), "a screen item about the same person is not shown with the card");
//     await row("c-evokoa").getByRole("button", { name: /^Done/ }).click();
//     await t.wait(100);
//     // A click anywhere on the row opens it: the subject's button is stretched over the row.
//     const box = await row("c-f24").locator(".dx-row-line").boundingBox();
//     await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
//     await row("c-f26").getByRole("button", { name: /^Reply to Neha/ }).focus();
//     await page.keyboard.press("Enter");
//     const said = await page.evaluate(() => window.__rows.slice());
//     t.ok(JSON.stringify(said) === JSON.stringify(["done c-evokoa", "open c-f24", "open c-f26"]), `presses: ${JSON.stringify(said)}`);
//   },
// };
```

#### `scripts/preview/checks/header.mjs`

```js
// // The top bar: views switch; the menu pauses and resumes reading and flips screen-only; Sign out
// // asks first and does nothing until confirmed; close and Back report; light and dark measured.
// export default {
//   name: "header",
//   async run(t) {
//     for (const colorScheme of ["light", "dark"]) {
//       const page = await t.gallery("header", { colorScheme, height: 360 });
//       await page.locator("#bar").waitFor({ timeout: 8000 });
//       await page.getByRole("button", { name: "More" }).click();
//       await t.fontFloor(page);
//       await t.palette(page);
//       await t.shot(page, `menu-${colorScheme}`);
//     }
//     const page = await t.gallery("header", { height: 360 });
//     await page.locator("#bar").waitFor();
//     const said = () => page.evaluate(() => window.__header.slice());
//     await page.getByRole("tab", { name: "This week" }).click();
//     const more = page.getByRole("button", { name: "More" });
//     await more.click();
//     await page.getByRole("menuitem", { name: "Pause reading for 15 min" }).click();
//     await more.click();
//     t.ok(await page.getByRole("menuitem", { name: "Resume reading" }).isVisible(), "after a pause the menu does not offer Resume");
//     await page.getByRole("menuitem", { name: "Resume reading" }).click();
//     await more.click();
//     await page.getByRole("menuitemcheckbox", { name: "Only what's on my screen" }).click();
//     await more.click();
//     await page.getByRole("menuitem", { name: "Sign out of this Mac…" }).click();
//     t.ok(await page.getByRole("alertdialog", { name: "Sign out" }).isVisible(), "Sign out did not ask first");
//     t.ok(!(await said()).includes("sign-out"), "Sign out acted before it was confirmed");
//     await t.shot(page, "confirm");
//     await page.getByRole("button", { name: "Cancel" }).click();
//     t.ok(!(await said()).includes("sign-out"), "Cancel signed out");
//     await page.getByRole("menuitem", { name: "Sign out of this Mac…" }).click();
//     await page.getByRole("button", { name: "Sign out", exact: true }).click();
//     await page.getByRole("button", { name: "Close" }).click();
//     const want = ["view week", "pause 15", "resume", "screen-only true", "sign-out", "close"];
//     const got = await said();
//     t.ok(JSON.stringify(got) === JSON.stringify(want), `got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
//
//     const back = await t.gallery("header-back", { height: 360 });
//     await back.locator("#bar").waitFor();
//     t.ok((await back.getByRole("tab").count()) === 0, "an open card still shows the view tabs");
//     await back.getByRole("button", { name: "Today" }).click();
//     t.ok((await back.evaluate(() => window.__header.slice())).join() === "back", "Back did not report");
//     await t.shot(back, "back");
//   },
// };
```

#### `scripts/preview/checks/history.mjs`

```js
// // History: by day, each popup with where it came from and the words on screen; a rating lands once.
// export default {
//   name: "history",
//   async run(t) {
//     for (const colorScheme of ["light", "dark"]) {
//       const page = await t.panel("normal", { colorScheme });
//       await page.getByRole("tab", { name: "History" }).click();
//       await page.getByLabel("History", { exact: true }).waitFor({ timeout: 8000 });
//       await t.fontFloor(page);
//       await t.palette(page);
//       await t.shot(page, colorScheme);
//     }
//     const page = await t.panel("normal");
//     await page.getByRole("tab", { name: "History" }).click();
//     const days = await page.locator(".dx-day").evaluateAll((s) => s.map((x) => x.getAttribute("aria-label")));
//     t.ok(days[0] === "Today" && days.includes("Yesterday"), `days: ${days.join(", ")}`);
//     const r2 = page.locator('[data-recent="r2"]');
//     const text = await r2.innerText();
//     t.ok(text.includes("WhatsApp") && text.includes("“will send the deck by Friday”") && !/ago\b/.test(text), "a popup does not say where it came from, or keeps a frozen 'ago'");
//     await r2.getByRole("button", { name: "Useful", exact: true }).click();
//     await r2.getByText("You marked this useful").waitFor();
//     const rated = (await t.calls(page)).filter((c) => c.cmd === "recent_feedback");
//     t.ok(rated.length === 1 && rated[0].args.action === "useful", "the rating did not reach the core");
//   },
// };
```

#### `scripts/preview/checks/lane.mjs`

```js
// // Popups: the panel's look in light and dark, a source line on top, the first button the main one,
// // no coloured edge (an urgent one says "Now"); a press reaches the Rust core; Reject asks why.
// export default {
//   name: "lane",
//   async run(t) {
//     for (const colorScheme of ["light", "dark"]) {
//       for (const toast of ["advice", "urgent", "reminder", "proposal", "brief"]) {
//         const page = await t.lane(toast, { colorScheme });
//         await page.locator(".lane-toast").waitFor({ timeout: 8000 });
//         await t.fontFloor(page);
//         await t.palette(page);
//         await t.shot(page, `${toast}-${colorScheme}`);
//       }
//     }
//     const urgent = await t.lane("urgent");
//     t.ok((await urgent.locator(".lane-kicker").innerText()).includes("Now"), "an urgent popup does not say Now");
//     const advice = await t.lane("advice");
//     t.ok((await advice.locator(".lane-kicker").innerText()).includes("On your screen"), "a screen popup does not say where it came from");
//     await advice.getByRole("button", { name: "Later" }).click();
//     const sent = (await t.calls(advice)).filter((c) => c.cmd === "lane_action").map((c) => c.args.action);
//     t.ok(sent.join() === "snooze", `Later sent ${sent.join()}`);
//     const proposal = await t.lane("proposal");
//     await proposal.getByRole("button", { name: "Reject" }).click();
//     await proposal.getByRole("button", { name: "Wrong details" }).click();
//     const rejected = (await t.calls(proposal)).find((c) => c.cmd === "lane_action");
//     t.ok(rejected?.args.action === "reject_delegation" && rejected?.args.reason === "Wrong details", "Reject did not send its reason");
//   },
// };
```

#### `scripts/preview/checks/press.mjs`

```js
// // What a press sends, and what a refusal does: refusals throw with the server's code (never
// // swallowed), every press says it came from the desktop, an answer and feedback carry their words.
// export default {
//   name: "press",
//   async run(t) {
//     const page = await t.gallery("presses");
//     await page.locator("#presses").waitFor({ timeout: 8000 });
//     const rows = (await t.text(page, "#presses")).split("\n");
//     const want = [
//       "c-evokoa wrong refused 422 invalid_wrong_reason",
//       "c-f55 do_it_myself refused 403 assigned_to_different_seat",
//       "c-f22 do_it_myself refused 422 not_offered",
//       "c-f22 answer refused 422 answer_says_nothing",
//       "c-f22 answer ok",
//       "c-f26 snooze ok snoozed",
//       "c-evokoa wrong ok acted",
//     ];
//     want.forEach((w, i) => t.ok((rows[i] ?? "").startsWith(w), `press ${i + 1}: got “${rows[i]}”, want “${w}”`));
//     t.ok(t.posts.length === want.length && t.posts.every((p) => p.sent.surface === "desktop"), "a press did not say it came from the desktop");
//     const answer = t.posts[4].sent;
//     t.ok(answer.words === "Yes, incubated at the campus cell since March.", `the answer was sent as “${answer.words}”`);
//     const feedback = t.posts[6].sent;
//     t.ok(feedback.reason === "bad_timing" && feedback.words === "the call already happened" && feedback.scope === "file", "feedback lost its reason, words or scope");
//     t.ok(t.posts[5].sent.snooze_option === "tomorrow_09", "Later did not send its option");
//   },
// };
```

#### `scripts/preview/checks/reads.mjs`

```js
// // The web's reader, run inside the app against the stand-in brain: an expert card reads as its own
// // move, with its quote and its person; nothing on any card says "undefined" or an engine name.
// export default {
//   name: "reads",
//   async run(t) {
//     const page = await t.gallery("reads", { height: 2400 });
//     await page.locator("#reads").waitFor({ timeout: 8000 });
//     await t.noWords(page, [/undefined/, /expert_check/, /card_lines/, /reasoning_trace/, /\bnull\b/], "#reads");
//     const card = (id, f) => page.locator(`[data-card="${id}"] [data-f="${f}"]`).innerText();
//     t.ok((await card("c-f24", "who")).includes("Divya Raman"), "the Phase-1 card does not say who it is about");
//     t.ok((await card("c-f24", "todo")).startsWith("Upload the Phase-1 review deck"), "the Phase-1 card's move is not its own");
//     t.ok((await card("c-f24", "why")).includes("Please upload your Phase-1 review deck"), "the Phase-1 card's quote is missing");
//     t.ok((await card("c-f24", "due")).includes("28 Sep"), "the Phase-1 card's deadline is missing");
//     t.ok((await card("c-evokoa", "who")).includes("Ananya Rao"), "the Evokoa card does not say who it is about");
//     t.ok(!(await card("c-evokoa", "why")).includes("Weekly founders sync"), "a meeting every card carries is shown as this card's reason");
//     t.ok((await page.locator('[data-card="c-f22"]').getAttribute("data-lane")) === "question", "the campus question is not read as a question");
//     t.ok((await card("c-f22", "offers")).includes('"answer":true'), "the campus question does not offer an answer");
//   },
// };
```

#### `scripts/preview/checks/renders.mjs`

```js
// // Signed in, the panel shows the brain's cards and the screen's items; signed out, the sign-in.
// export default {
//   name: "renders",
//   async run(t) {
//     const page = await t.panel("normal");
//     await page.getByText("Confirm the call time with Evokoa").first().waitFor({ timeout: 8000 });
//     t.ok((await t.text(page)).includes("Kiran asked for the data-room link"), "the screen's follow-ups are missing");
//     await t.shot(page, "today");
//     const out = await t.panel("signedout");
//     t.ok(/Sign in/.test(await t.text(out)), "signed out, the panel does not offer sign-in");
//     await t.shot(out, "signin");
//   },
// };
```

#### `scripts/preview/checks/screen-rows.mjs`

```js
// // A screen item: the app it was seen in, the words that caused it, whose and by when (a late one
// // says so); opening shows Done, Already handled and Tomorrow.
// export default {
//   name: "screen-rows",
//   async run(t) {
//     for (const colorScheme of ["light", "dark"]) {
//       const page = await t.gallery("screen-items", { colorScheme });
//       await page.locator("[data-item]").first().waitFor({ timeout: 8000 });
//       await t.fontFloor(page);
//       await t.palette(page);
//       await t.shot(page, colorScheme);
//     }
//     const page = await t.gallery("screen-items");
//     const row = (id) => page.locator(`[data-item="${id}"]`);
//     await row("f1").waitFor();
//     const f1 = await row("f1").innerText();
//     t.ok(f1.includes("WhatsApp") && f1.includes("your screen") && f1.includes("“will send the deck by Friday”"), "the WhatsApp item does not say where and what");
//     t.ok(f1.includes("Your promise") && f1.includes("Neha Kapoor"), "the WhatsApp item does not say whose");
//     t.ok((await row("f2").innerText()).includes("Gmail"), "a Gmail tab is not named Gmail");
//     t.ok((await row("f3").innerText()).includes("startupindia.gov.in"), "a site is not named by its host");
//     t.ok((await row("f2").locator(".late").count()) === 1, "a late ask does not say so");
//     t.ok((await row("f3").locator(".late").count()) === 0, "a deadline still ahead reads as late");
//     await row("f2").getByRole("button", { name: "Kiran asked for the data-room link", exact: true }).click();
//     await row("f2").getByRole("button", { name: "Already handled" }).click();
//     await row("f2").getByRole("button", { name: "Tomorrow" }).click();
//     await row("f1").getByRole("button", { name: /^Done/ }).click();
//     const said = await page.evaluate(() => window.__rows.slice());
//     t.ok(JSON.stringify(said) === JSON.stringify(["handled f2", "tomorrow f2", "done f1"]), `presses: ${JSON.stringify(said)}`);
//   },
// };
```

#### `scripts/preview/checks/setup.mjs`

```js
// // First run is one card with one button; the foot of the panel says the reading state once, with at
// // most one note; Pause, Resume, Sync and the setup buttons reach the Rust core.
// export default {
//   name: "setup",
//   async run(t) {
//     const calls = async (page) => (await t.calls(page)).map((c) => c.cmd);
//
//     const access = await t.gallery("setup", { s: "setup" });
//     await access.getByLabel("Get set up").waitFor({ timeout: 8000 });
//     const text = await t.text(access);
//     t.ok(/\d+% ready/.test(text) && !/\d\/\d/.test(text), "readiness is not a percent");
//     t.ok((await access.getByRole("button", { name: "Open settings" }).count()) === 1, "Open settings is offered more than once");
//     await access.getByRole("button", { name: "Open settings" }).click();
//     t.ok((await calls(access)).includes("capture_open_accessibility_settings"), "Open settings did not reach the core");
//     await t.fontFloor(access);
//     await t.palette(access);
//     await t.shot(access, "accessibility");
//
//     const policy = await t.gallery("setup", { s: "policy", colorScheme: "dark" });
//     await policy.getByLabel("Get set up").waitFor();
//     await policy.getByRole("button", { name: "Turn on" }).click();
//     const opened = (await t.calls(policy)).find((c) => c.cmd === "open_dashboard");
//     t.ok(opened?.args?.path === "/dashboard/settings?section=capture", "Turn on did not open the capture settings");
//     await t.palette(policy);
//     await t.shot(policy, "policy-dark");
//
//     const busy = await t.gallery("setup", { s: "busy" });
//     const bar = busy.getByLabel("Screen reading");
//     await bar.waitFor();
//     t.ok((await busy.getByLabel("Get set up").count()) === 0, "a set-up workspace still shows the setup card");
//     t.ok((await bar.locator(".dx-foot-note").count()) === 1, "the bar stacks more than one note");
//     t.ok((await bar.innerText()).includes("WhatsApp has shown nothing"), "a blind reader is not the note shown");
//     await bar.getByRole("button", { name: "Sync 4" }).click();
//     await bar.getByRole("button", { name: "Pause" }).click();
//     await t.wait(500);
//     t.ok((await bar.innerText()).includes("Paused until"), "Pause did not pause");
//     await bar.getByRole("button", { name: "Resume" }).click();
//     await t.wait(500);
//     t.ok((await bar.innerText()).includes("Reading"), "Resume did not resume");
//     const got = await calls(busy);
//     t.ok(["sync_now", "capture_pause", "capture_resume"].every((c) => got.includes(c)), `the bar's buttons did not reach the core: ${got.join(", ")}`);
//     await t.shot(busy, "busy");
//   },
// };
```

#### `scripts/preview/checks/signin.mjs`

```js
// // Sign-in: no server address in sight until Advanced; the code screen shows the code and the wait.
// export default {
//   name: "signin",
//   async run(t) {
//     for (const colorScheme of ["light", "dark"]) {
//       const page = await t.panel("signedout", { colorScheme });
//       await page.getByRole("button", { name: "Sign in with the browser" }).waitFor({ timeout: 8000 });
//       await t.noWords(page, [/ondigitalocean/, /squid-app/, /localhost/]);
//       await t.fontFloor(page);
//       await t.palette(page);
//       await t.shot(page, colorScheme);
//     }
//     const page = await t.panel("signedout");
//     await page.getByRole("button", { name: "Advanced" }).click();
//     t.ok(await page.getByLabel("Server address").isVisible(), "Advanced does not show the server address");
//     await page.getByRole("button", { name: "Sign in with the browser" }).click();
//     await page.getByLabel("Device code").waitFor({ timeout: 5000 });
//     t.ok((await page.getByLabel("Device code").innerText()).includes("KQ7D-M3XW"), "the code is not shown");
//     t.ok(/Waiting for approval · \d+:\d\d/.test(await t.text(page)), "the wait is not shown");
//     await t.shot(page, "code");
//   },
// };
```

#### `scripts/preview/checks/today.mjs`

```js
// // Today in the real panel: grouped by what it asks, a summary, nothing wider than the panel, the
// // empty and unreachable states say what to do, screen-only says what it hides; the keyboard works.
// export default {
//   name: "today",
//   async run(t) {
//     for (const colorScheme of ["light", "dark"]) {
//       const page = await t.panel("normal", { colorScheme });
//       await page.locator('[data-card="c-f24"] .dx-tag').first().waitFor({ timeout: 8000 });
//       await t.fontFloor(page);
//       await t.palette(page);
//       await t.noWords(page, [/undefined/, /expert_check/, /card_lines/, /reasoning_trace/, /\bnull\b/]);
//       await t.shot(page, colorScheme);
//     }
//     const page = await t.panel("normal");
//     await page.locator('[data-card="c-f24"] .dx-tag').first().waitFor();
//     const groups = await page.locator(".dx-body section[aria-label]").evaluateAll((s) => s.map((x) => x.getAttribute("aria-label")));
//     t.ok(JSON.stringify(groups) === JSON.stringify(["Decide", "Answer", "On your screen", "Waiting"]), `groups: ${groups.join(", ")}`);
//     t.ok(/\d+ needs? you/.test(await t.text(page)), "no summary line");
//     const wide = await page.evaluate(() => {
//       const edge = document.querySelector(".dx-body").getBoundingClientRect().right;
//       return [...document.querySelectorAll(".dx-row")].filter((r) => r.getBoundingClientRect().right > edge + 0.5).length;
//     });
//     t.ok(wide === 0, `${wide} rows are wider than the panel`);
//
//     // Keyboard: ↓ to the first row, Enter opens it, Esc back to the same row, Esc again hides.
//     await page.keyboard.press("ArrowDown");
//     await page.keyboard.press("Enter");
//     await page.getByRole("article", { name: "Card" }).waitFor();
//     await page.keyboard.press("Escape");
//     await page.locator('[data-card="c-evokoa"]').waitFor();
//     t.ok(await page.evaluate(() => document.activeElement?.closest("[data-card]")?.getAttribute("data-card")) === "c-evokoa", "Back did not return to the row");
//     await page.keyboard.press("Escape");
//     t.ok(await page.evaluate(() => window.__hidden === true), "Esc on the list did not hide the panel");
//
//     // Only what's on my screen.
//     await page.getByRole("button", { name: "More" }).click();
//     await page.getByRole("menuitemcheckbox", { name: "Only what's on my screen" }).click();
//     const only = await page.locator(".dx-body section[aria-label]").evaluateAll((s) => s.map((x) => x.getAttribute("aria-label")));
//     t.ok(only.join() === "On your screen", `screen-only shows ${only.join(", ")}`);
//     t.ok(/6 from your tools hidden/.test(await t.text(page)), "screen-only does not say what it hides");
//     await page.getByRole("button", { name: "Show all" }).click();
//
//     const empty = await t.panel("empty");
//     await empty.getByText("Nothing needs you right now").waitFor({ timeout: 8000 });
//     const off = await t.panel("offline");
//     await off.getByText("Couldn't load your cards").waitFor({ timeout: 8000 });
//     t.ok(await off.getByRole("button", { name: "Try again" }).isVisible(), "the error offers no way to try again");
//     await t.shot(off, "offline");
//   },
// };
```

#### `scripts/preview/checks/tokens.mjs`

```js
// // The tokens, in light and in dark: no text under 12px, no colour outside ink, greys and burgundy,
// // the dark scheme really dark, and body text readable on its surface.
// export default {
//   name: "tokens",
//   async run(t) {
//     const seen = {};
//     for (const colorScheme of ["light", "dark"]) {
//       const page = await t.gallery("tokens", { colorScheme });
//       await page.locator("#sheet").waitFor({ timeout: 8000 });
//       await t.fontFloor(page);
//       await t.palette(page);
//       const m = await page.evaluate(() => {
//         const rgb = (c) => c.match(/[\d.]+/g).slice(0, 3).map(Number);
//         const lum = ([r, g, b]) => {
//           const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
//           return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
//         };
//         const ratio = (a, b) => {
//           const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((p, q) => q - p);
//           return (x + 0.05) / (y + 0.05);
//         };
//         const card = getComputedStyle(document.querySelector(".dx-card")).backgroundColor;
//         const page = getComputedStyle(document.querySelector(".dx-shell")).backgroundColor;
//         return {
//           page,
//           pageLum: lum(rgb(page)),
//           ink: ratio(getComputedStyle(document.querySelector('[data-t="ink"]')).color, card),
//           mist: ratio(getComputedStyle(document.querySelector('[data-t="mist"]')).color, card),
//         };
//       });
//       t.ok(m.ink >= 7, `${colorScheme}: ink on a card is ${m.ink.toFixed(1)}:1 (want 7)`);
//       t.ok(m.mist >= 4.5, `${colorScheme}: grey text on a card is ${m.mist.toFixed(1)}:1 (want 4.5)`);
//       seen[colorScheme] = m;
//       await t.shot(page, colorScheme);
//     }
//     t.ok(seen.light.pageLum > 0.8 && seen.dark.pageLum < 0.05, `the page is ${seen.light.page} in light and ${seen.dark.page} in dark`);
//   },
// };
```

#### `scripts/preview/checks/ui.mjs`

```js
// // The small parts: measured in light and dark; a menu closes on Esc (and keeps that Esc from the
// // panel) and on a click outside; a sheet closes on Esc; tabs move.
// export default {
//   name: "ui",
//   async run(t) {
//     for (const colorScheme of ["light", "dark"]) {
//       const page = await t.gallery("ui", { colorScheme });
//       await page.locator("#parts").waitFor({ timeout: 8000 });
//       await t.fontFloor(page);
//       await t.palette(page);
//       await t.shot(page, colorScheme);
//     }
//     const page = await t.gallery("ui");
//     await page.locator("#parts").waitFor();
//     t.ok(await page.getByRole("menu", { name: "More" }).isVisible(), "the menu did not open");
//     await page.keyboard.press("Escape");
//     t.ok(!(await page.getByRole("menu").isVisible().catch(() => false)), "Esc did not close the menu");
//     const escapes = await page.evaluate(() => window.__escapes);
//     t.ok(escapes.length === 1 && escapes[0] === true, "the menu's Esc also reached the panel");
//     await page.getByRole("button", { name: "More" }).click();
//     t.ok(await page.getByRole("menu").isVisible(), "the menu did not reopen");
//     await page.mouse.click(30, 400);
//     t.ok(!(await page.getByRole("menu").isVisible().catch(() => false)), "a click outside did not close the menu");
//     await page.getByRole("button", { name: "Feedback" }).click();
//     t.ok(await page.getByRole("dialog", { name: "What is off?" }).isVisible(), "the sheet did not open");
//     await page.keyboard.press("Escape");
//     t.ok(!(await page.getByRole("dialog").isVisible().catch(() => false)), "Esc did not close the sheet");
//     await page.getByRole("tab", { name: "History" }).click();
//     t.ok((await page.getByRole("tab", { name: "History" }).getAttribute("aria-selected")) === "true", "the tabs did not move");
//     await page.getByRole("button", { name: "A fact is wrong" }).click();
//     t.ok((await page.getByRole("button", { name: "A fact is wrong" }).getAttribute("aria-pressed")) === "true", "a choice did not take");
//   },
// };
```

#### `scripts/preview/checks/week.mjs`

```js
// // This week: percents and counts, never a fraction.
// export default {
//   name: "week",
//   async run(t) {
//     for (const colorScheme of ["light", "dark"]) {
//       const page = await t.panel("normal", { colorScheme });
//       await page.getByRole("tab", { name: "This week" }).click();
//       await page.getByLabel("This week", { exact: true }).waitFor({ timeout: 8000 });
//       const text = await t.text(page, ".dx-body");
//       t.ok(!/\b\d+\s*\/\s*\d+\b/.test(text), "a fraction is shown");
//       t.ok(text.includes("60%") && text.includes("67%") && text.includes("Closed after a nudge"), "the week's numbers are missing");
//       await t.fontFloor(page);
//       await t.palette(page);
//       await t.shot(page, colorScheme);
//     }
//     const off = await t.panel("offline");
//     await off.getByRole("tab", { name: "This week" }).click();
//     await off.getByText("This week's numbers did not load").waitFor({ timeout: 8000 });
//   },
// };
```

#### `scripts/preview/gallery.html`

```html
// <!doctype html>
// <html lang="en">
//   <head>
//     <meta charset="UTF-8" />
//     <meta name="viewport" content="width=device-width, initial-scale=1.0" />
//     <title>GeniOS parts</title>
//   </head>
//   <body>
//     <div id="root"></div>
//     <script type="module" src="./gallery.tsx"></script>
//   </body>
// </html>
```

#### `scripts/preview/gallery.tsx`

```tsx
// // One page that draws any part of the panel on its own: gallery.html?p=<name>[&w=420&h=580].
// //
// // Each part ships a sibling `<Part>.preview.tsx` exporting `previews: { name: () => ReactNode }` —
// // the part drawn the way the panel will use it, fed by the real reader against the stand-in brain.
// // That lets a part be checked bottom-up, before the panel that wires them together exists.
// import { StrictMode, type ReactNode } from "react";
// import { createRoot } from "react-dom/client";
//
// type Previews = Record<string, () => ReactNode>;
//
// const modules = import.meta.glob<{ previews: Previews }>("../../src/**/*.preview.tsx", { eager: true });
// const all: Previews = Object.assign({}, ...Object.values(modules).map((m) => m.previews));
//
// const q = new URLSearchParams(location.search);
// const name = q.get("p") ?? "";
// const width = Number(q.get("w") ?? 420);
// const height = Number(q.get("h") ?? 580);
// document.documentElement.dataset.os = "macos";
//
// const Preview = all[name];
//
// createRoot(document.getElementById("root")!).render(
//   <StrictMode>
//     <div id="frame" style={{ width, height, position: "relative" }}>
//       {Preview ? (
//         <Preview />
//       ) : (
//         <p id="missing">
//           No preview named “{name}”. Known: {Object.keys(all).sort().join(", ") || "none yet"}.
//         </p>
//       )}
//     </div>
//   </StrictMode>,
// );
```

#### `scripts/preview/menu-check.mjs`

```js
// // The GeniOS menu and popups (0.3.1–0.3.4), checked in Chromium against the stand-ins: the
// // screen-reading line and the Screen view (Minimize, Fix Accessibility, Check again), Refresh
// // (stops by ~3 s with a slow brain; one card load at a time), Done → Undo → slides away at 3 s and
// // stays gone, the popup's five-second line (half at 2.5 s, held on hover, none on an agent
// // proposal), the account's popup sound and version. Exit 0 = every check passed.
// //
// // Run from Extension/, with the stand-in brain and the preview server up:
// //   python3 scripts/preview/mock_brain.py 8032 &
// //   node node_modules/vite/bin/vite.js --config scripts/preview/vite.preview.mjs &
// //   node scripts/preview/menu-check.mjs /tmp/menu-shots
// // Playwright is taken from PLAYWRIGHT_DIR (a folder whose node_modules has it).
// import { createRequire } from "node:module";
// const require = createRequire((process.env.PLAYWRIGHT_DIR ?? `${process.env.HOME}/.claude/skills/gstack`) + "/node_modules/");
// const { chromium } = require("playwright");
// const OUT = process.argv[2] ?? ".";
// const B = "http://localhost:5199";
// const fails = [];
// const ok = (c, m) => { if (!c) fails.push(m); console.log((c ? "PASS " : "FAIL ") + m); };
// const browser = await chromium.launch();
// const page = async (url, w = 376, h = 640) => {
//   const p = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
//   const errs = [];
//   p.on("pageerror", (e) => errs.push(String(e)));
//   await p.goto(B + url);
//   await p.waitForTimeout(1200);
//   return { p, errs };
// };
//
// // 1. The line under the header says it is reading, and what, and when.
// {
//   const { p, errs } = await page("/desktop.html?s=normal");
//   const strip = p.locator(".m-strip");
//   ok(await strip.isVisible(), "screen line visible on Pending");
//   const t = await strip.innerText();
//   ok(/Reading your screen · Neha Kapoor — WhatsApp/.test(t), `screen line text: ${t.replace(/\n/g, " ")}`);
//   ok(/s ago|just now/.test(t), "screen line says when");
//   await p.screenshot({ path: `${OUT}/01-pending-with-screen-line.png` });
//   await strip.click();
//   await p.waitForTimeout(300);
//   ok(await p.getByRole("heading", { name: "Reading your screen" }).isVisible(), "Screen view title");
//   ok(await p.getByText("How it works").isVisible(), "Screen view: how it works");
//   ok((await p.locator(".m-scr-list li").count()) === 4, "Screen view lists this session's popups");
//   ok(await p.getByText("7 of 40 today").isVisible(), "Screen view: AI checks");
//   await p.screenshot({ path: `${OUT}/02-screen-view.png`, fullPage: true });
//   await p.locator(".m-scr").evaluate((el) => el.closest(".menu-body").scrollTo(0, 9999));
//   await p.screenshot({ path: `${OUT}/03-screen-view-bottom.png` });
//   // Refresh
//   await p.getByRole("button", { name: "Refresh" }).click();
//   await p.waitForTimeout(400);
//   ok(await p.locator(".menu-flash").isVisible(), "Refresh shows Refreshed · time");
//   await p.screenshot({ path: `${OUT}/04-refreshed.png` });
//   ok(errs.length === 0, `no page errors (${errs.join(" | ")})`);
//   await p.close();
// }
//
// // 1c. Screen open: the line stays on top as Minimize, and goes back to where it was opened from.
// {
//   const { p, errs } = await page("/desktop.html?s=normal");
//   await p.locator(".m-strip").click();
//   await p.waitForTimeout(300);
//   const min = p.getByRole("button", { name: "Minimize screen reading" });
//   ok(await min.isVisible(), "Screen view has Minimize at the top");
//   ok(/Minimize/.test(await min.innerText()), "it says Minimize");
//   await p.screenshot({ path: `${OUT}/15-screen-minimize.png` });
//   await min.click();
//   await p.waitForTimeout(300);
//   ok((await p.locator(".m-scr").count()) === 0 && (await p.locator(".m-row").count()) > 0, "Minimize goes back to Pending");
//   await p.locator(".m-row").first().click();
//   await p.waitForTimeout(300);
//   await p.locator(".m-strip").click();
//   await p.waitForTimeout(300);
//   await p.getByRole("button", { name: "Minimize screen reading" }).click();
//   await p.waitForTimeout(300);
//   ok((await p.locator(".drop.in-menu").count()) === 1, "opened from a card, Minimize goes back to that card");
//   ok(errs.length === 0, `no page errors (${errs.join(" | ")})`);
//   await p.close();
// }
//
// // 1b. Account: popup sound (choosing one plays it once) and the version.
// {
//   const { p, errs } = await page("/desktop.html?s=normal");
//   await p.getByRole("button", { name: "Account" }).click();
//   await p.waitForTimeout(300);
//   ok(await p.getByText(/GeniOS preview/).isVisible(), "account shows the app version");
//   const sel = p.getByRole("combobox", { name: "Popup sound" });
//   ok((await sel.inputValue()) === "mac", "popup sound starts on the Mac alert sound");
//   await sel.selectOption("Glass");
//   await p.waitForTimeout(200);
//   const calls = await p.evaluate(() => window.__calls.filter((c) => c.cmd === "lane_sound").map((c) => c.args));
//   const last = calls[calls.length - 1];
//   ok(last && last.choice === "Glass" && last.preview === true, `choosing Glass sets and previews it (${JSON.stringify(last)})`);
//   await p.screenshot({ path: `${OUT}/14-account-sound.png` });
//   await p.reload();
//   await p.waitForTimeout(1200);
//   const boot = await p.evaluate(() => window.__calls.filter((c) => c.cmd === "lane_sound").map((c) => c.args));
//   ok(boot.some((a) => a.choice === "Glass" && !a.preview), "after a restart the pick is sent again, silently");
//   ok(errs.length === 0, `no page errors (${errs.join(" | ")})`);
//   await p.close();
// }
//
// // 2. Accessibility off: the line warns; Screen has the steps; Check again restarts the reader.
// {
//   const { p, errs } = await page("/desktop.html?s=setup");
//   const t = await p.locator(".m-strip").innerText();
//   ok(/Not reading your screen · fix Accessibility/.test(t), `warn line: ${t}`);
//   ok(await p.locator(".m-strip.warn").count() === 1, "warn tone");
//   await p.screenshot({ path: `${OUT}/05-setup-line.png` });
//   await p.locator(".m-strip").click();
//   await p.waitForTimeout(300);
//   ok(await p.getByText(/that entry was made for an older GeniOS/).isVisible(), "says why a switched-on entry can still fail");
//   await p.screenshot({ path: `${OUT}/06-setup-screen.png`, fullPage: true });
//   await p.getByRole("button", { name: /Check again/ }).click();
//   await p.waitForTimeout(3600);
//   ok(window_calls(await p.evaluate(() => window.__calls.map((c) => c.cmd))).includes("capture_restart_reader"), "Check again restarts the reader");
//   ok(await p.getByRole("heading", { name: "Reading your screen" }).isVisible(), "after the grant: Reading your screen");
//   await p.screenshot({ path: `${OUT}/07-setup-after-check.png` });
//   ok(errs.length === 0, `no page errors (${errs.join(" | ")})`);
//   await p.close();
// }
// function window_calls(c) { return c; }
//
// // 2b. Fix Accessibility: removes the old entry and asks macOS again (the Rust command), then reads.
// {
//   const { p, errs } = await page("/desktop.html?s=setup");
//   await p.locator(".m-strip").click();
//   await p.getByRole("button", { name: "Fix Accessibility" }).click();
//   await p.waitForTimeout(3000);
//   const calls = await p.evaluate(() => window.__calls.map((c) => c.cmd));
//   ok(calls.includes("capture_fix_accessibility"), "Fix Accessibility calls capture_fix_accessibility");
//   ok(await p.getByRole("heading", { name: "Reading your screen" }).isVisible(), "after Fix: Reading your screen");
//   ok(errs.length === 0, `no page errors (${errs.join(" | ")})`);
//   await p.close();
// }
//
// // 2c. Refresh with a slow brain: it stops spinning by ~3 s, and one card load runs however often it is pressed.
// {
//   const { p, errs } = await page("/desktop.html?s=normal");
//   let queue = 0;
//   await p.route(/\/cards(\?.*)?$/, async (r) => {
//     queue++;
//     await new Promise((res) => setTimeout(res, 12000));
//     await r.continue().catch(() => {});
//   });
//   const btn = p.getByRole("button", { name: "Refresh" });
//   const t0 = Date.now();
//   await btn.click();
//   await p.waitForSelector(".m-refresh:not(.spin)", { timeout: 8000 });
//   const spun = Date.now() - t0;
//   ok(spun < 3800, `Refresh spins ${spun} ms with a slow brain (max ~3 s)`);
//   ok(/cards are still coming in/.test(await p.locator(".menu-flash").innerText()), "says the cards are still coming in");
//   await p.screenshot({ path: `${OUT}/13-refresh-slow-brain.png` });
//   await p.waitForTimeout(200);
//   await btn.click();
//   await p.waitForTimeout(3400);
//   await btn.click();
//   await p.waitForTimeout(500);
//   ok(queue === 1, `three presses while it loads: ${queue} card-list request(s), not 3`);
//   ok(errs.length === 0, `no page errors (${errs.join(" | ")})`);
//   await p.close();
// }
//
// // 3. Done in the Card view: note + Undo, then after 3 s it slides away and Pending no longer has it.
// {
//   const { p, errs } = await page("/desktop.html?s=normal");
//   const before = await p.locator(".m-row").count();
//   await p.locator(".m-row").first().click();
//   await p.waitForTimeout(300);
//   const subject = (await p.locator(".drop-subject").innerText()).trim();
//   // Record, in the page, when Done was pressed and when the card took the leaving class.
//   await p.evaluate(() => {
//     window.__t = {};
//     document.querySelector(".drop .drop-btn.main").addEventListener("click", () => (window.__t.press = performance.now()), { capture: true });
//     new MutationObserver(() => {
//       if (!window.__t.leave && document.querySelector(".drop.leaving")) window.__t.leave = performance.now();
//     }).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["class"] });
//   });
//   await p.locator(".drop .drop-btn.main").click();
//   await p.waitForTimeout(400);
//   ok(await p.locator(".drop-note").isVisible(), "Done leaves a note with Undo");
//   await p.screenshot({ path: `${OUT}/08-done-note.png` });
//   await p.waitForTimeout(3200);
//   const at = await p.evaluate(() => (window.__t.leave ? Math.round(window.__t.leave - window.__t.press) : -1));
//   ok(at >= 2950 && at <= 3300, `slides away at 3 s (${at} ms after Done)`);
//   await p.waitForTimeout(300);
//   ok(await p.locator(".m-row").first().isVisible(), "back on Pending");
//   const after = await p.locator(".m-row").count();
//   const still = await p.locator(".m-row", { hasText: subject.slice(0, 30) }).count();
//   ok(after === before - 1 && still === 0, `the done card is gone (${before} → ${after}, '${subject.slice(0, 30)}' rows: ${still})`);
//   await p.waitForTimeout(6000);
//   const later = await p.locator(".m-row", { hasText: subject.slice(0, 30) }).count();
//   ok(later === 0, "it does not come back after the send and reload");
//   await p.screenshot({ path: `${OUT}/10-done-gone.png` });
//   ok(errs.length === 0, `no page errors (${errs.join(" | ")})`);
//   await p.close();
// }
//
// // 4. Popup: the gold line runs out over 5 s; hover holds it full; a press slides it away.
// {
//   const { p, errs } = await page("/lane.html?toast=reminder", 432, 260);
//   ok((await p.locator(".drop-timer i").count()) === 1, "popup has the countdown line");
//   await p.waitForTimeout(1300);
//   const w = async () => p.locator(".drop-timer i").evaluate((el) => el.getBoundingClientRect().width / el.parentElement.getBoundingClientRect().width);
//   const mid = await w();
//   ok(mid > 0.3 && mid < 0.7, `about half left at ~2.5 s (${mid.toFixed(2)})`);
//   await p.screenshot({ path: `${OUT}/11-popup-countdown.png` });
//   await p.locator(".drop").hover();
//   await p.waitForTimeout(600);
//   const held = await w();
//   ok(held > 0.98, `hover holds it full (${held.toFixed(2)})`);
//   await p.mouse.move(5, 250);
//   await p.waitForTimeout(5300);
//   ok((await p.locator(".drop.leaving").count()) === 1, "after 5 s the popup slides away");
//   await p.screenshot({ path: `${OUT}/12-popup-ended.png` });
//   ok(errs.length === 0, `no page errors (${errs.join(" | ")})`);
//   await p.close();
// }
// {
//   const { p } = await page("/lane.html?toast=proposal", 432, 260);
//   ok((await p.locator(".drop-timer").count()) === 0, "an agent proposal has no countdown (it waits for Approve)");
//   await p.close();
// }
// {
//   const { p } = await page("/lane.html?toast=reminder", 432, 260);
//   await p.locator(".drop .drop-btn.main").click();
//   await p.waitForTimeout(80);
//   ok((await p.locator(".drop.leaving").count()) === 1, "Done slides the popup away");
//   await p.waitForTimeout(400);
//   const calls = await p.evaluate(() => window.__calls.filter((c) => c.cmd === "lane_action").map((c) => c.args.action));
//   ok(calls.includes("done"), `then reports done (${calls})`);
//   await p.close();
// }
// await browser.close();
// console.log(fails.length ? `\n${fails.length} FAILED` : "\nALL PASS");
// process.exit(fails.length ? 1 : 0);
```

#### `scripts/preview/mock_brain.py`

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

#### `scripts/preview/tauri-mock/app.ts`

```ts
// // Stand-in for @tauri-apps/api/app in the render check: the version the app's config says.
// export async function getVersion(): Promise<string> {
//   return "preview";
// }
```

#### `scripts/preview/tauri-mock/core.ts`

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
//     normal: { state: "capturing", reader_available: true, last_thread_title: "Neha Kapoor — WhatsApp", last_captured_at: new Date(Date.now() - 12_000).toISOString(), queue_depth: 0, insight_budget: { used: 7, cap: 40 } },
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
// let silenced = false;
// let sound = "mac";
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
//   // A fresh reader asks macOS again: in the setup scenario, the grant was just made in Settings.
//   // Fix Accessibility: the old entry removed, macOS asked again, switched on in Settings.
//   capture_fix_accessibility: () => {
//     capture = { state: "capturing", reader_available: true, last_thread_title: null, last_captured_at: null, queue_depth: 0 };
//     return null;
//   },
//   capture_restart_reader: () => {
//     if (capture.state === "needs_accessibility")
//       capture = { state: "capturing", reader_available: true, last_thread_title: null, last_captured_at: null, queue_depth: 0 };
//     return null;
//   },
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
//   lane_silence: (a) => (a.on === undefined ? silenced : (silenced = Boolean(a.on))),
//   lane_sound: (a) => (a.choice === undefined ? sound : (sound = String(a.choice))),
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

#### `scripts/preview/tauri-mock/event.ts`

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
//
// /** emitTo(window, event, payload): in the preview every window is this page. */
// export async function emitTo(_target: string, event: string, payload: unknown): Promise<void> {
//   window.__emit(event, payload);
// }
```

#### `scripts/preview/tauri-mock/http.ts`

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

#### `scripts/preview/tauri-mock/window.ts`

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

#### `scripts/preview/tsconfig.json`

```json
// {
//   "extends": "../../tsconfig.app.json",
//   "include": ["gallery.tsx", "tauri-mock/*.ts", "../../src/vite-env.d.ts"]
// }
```

#### `scripts/preview/vite.preview.mjs`

```js
// // The app's own Vite config, served for the render check: same pages, same plugins, with
// // @tauri-apps/* replaced by the stand-ins in tauri-mock/ so the panel and the lane run in a plain
// // browser against mock_brain.py. Port 5199 (the stand-in brain allows that origin).
// import { defineConfig, mergeConfig } from "vite";
// import { fileURLToPath } from "node:url";
// import base from "../../vite.config.ts";
//
// const at = (p) => fileURLToPath(new URL(p, import.meta.url));
//
// export default mergeConfig(
//   base,
//   defineConfig({
//     root: at("../.."),
//     server: { port: 5199, strictPort: true, fs: { allow: [at("../../..")] } },
//     resolve: {
//       alias: [
//         { find: "@tauri-apps/api/core", replacement: at("./tauri-mock/core.ts") },
//         { find: "@tauri-apps/api/event", replacement: at("./tauri-mock/event.ts") },
//         { find: "@tauri-apps/api/window", replacement: at("./tauri-mock/window.ts") },
//         { find: "@tauri-apps/api/app", replacement: at("./tauri-mock/app.ts") },
//         { find: "@tauri-apps/plugin-http", replacement: at("./tauri-mock/http.ts") },
//       ],
//     },
//   }),
// );
```
