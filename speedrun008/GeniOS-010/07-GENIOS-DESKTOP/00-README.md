# 07 · GeniOS desktop app — start here

**Written for:** Rohit, to keep and hand over; Harsh and any coding agent who works on the Mac app next.

**State on 23 Oct 2026:** GeniOS **0.3.4** for Mac (Apple Silicon) is installable and in use.
- It reads the screen, refreshes, and shows cards, Pending and the Screen view.
- Popups stay five seconds, with a sound.
- The code is on its own branch, pushed, and **not merged**. The website and the live app are untouched.

## 1 · Where everything is

### The app

| What | Where |
|---|---|
| **The app to install** | `~/Downloads/GeniOS_0.3.4_aarch64.dmg` (25 MB, Apple Silicon). Its window and volume are titled **GeniOS 0.3.4**. |
| Older builds (do not install) | `~/Downloads/GeniOS-old-builds/` (0.3.0 – 0.3.3) |

### The code

| What | Where |
|---|---|
| The code | GitHub `themoronss/genios-brain-dashbaord`, branch **`rohit/desktop-ux`**, commit `ed2724d`, folder `Extension/` |
| The same code, on this Mac | `~/MacBook Air Professional/My Repos/genios-brain-dashbaord-desktop` (a worktree of the dashboard repo) |
| How to build the DMG | `Extension/scripts/mac-dev-dmg.sh`. It builds the app, signs it with the fixed local identity, makes the DMG, and checks it. |
| The fixed signing identity | `~/.genios-dev-signing/` ("GeniOS Local Development": a private key and its own keychain). **Keep it private, and never commit it.** If it is deleted, the next build makes a new one, and Accessibility must be allowed once more. |
| The render check | `Extension/scripts/preview/menu-check.mjs` (46 checks of the menu and popups in a browser) |

### The design and these documents

| What | Where |
|---|---|
| The agreed design (the dummy) | `~/Downloads/Artifacts/Product/genios-desktop-dummy`, outside every repo |
| These documents | GitHub `themoronss/genios-brain`, branch **`g010-desktop`**, folder `speedrun008/GeniOS-010/07-GENIOS-DESKTOP/` |

### On the Mac, while GeniOS runs

| What | Where |
|---|---|
| The app's log | `~/Library/Logs/ai.genios.desktop/GeniOS.log` |
| What it keeps on this Mac | `~/Library/Application Support/ai.genios.desktop/` holds `capture.db`, encrypted with SQLCipher. The Keychain (service `ai.genios.desktop`) holds two items: `session` and `capture-db-key`. |

### The files in this folder

| File | What it is | Size |
|---|---|---|
| `00-README.md` | This page: where everything is, and how the app works | — |
| [`01-CODEBASE.md`](01-CODEBASE.md) | The agreed **dummy**'s code (the design Rohit approved on 22 Oct), commented out | 49 files, 8,364 lines |
| [`02-HOW-IT-WAS-BUILT.md`](02-HOW-IT-WAS-BUILT.md) | The design, round by round, and every app version from 0.3.0 to 0.3.4: what was asked, what was found, what changed, how it was checked | §0 – §15 |
| [`03-APP-CODE-WINDOWS.md`](03-APP-CODE-WINDOWS.md) | The **real app**'s windows (TypeScript, React, CSS), commented out | 91 files, 15,541 lines |
| [`04-APP-CODE-CORE.md`](04-APP-CODE-CORE.md) | The **real app**'s Rust core, commented out | 71 files, 22,459 lines |
| [`05-APP-CODE-READER.md`](05-APP-CODE-READER.md) | The **real app**'s screen reader, `genios-ax` (Swift), commented out | 38 files, 4,845 lines |
| `assets/` | The logo, the app icon and the favicons | — |
| `screens/` | 31 screenshots: 01–12 the dummy, 13–31 the app | — |

Files 03, 04 and 05 are the app exactly as it is at commit `ed2724d`. Each one carries a script that writes its files back out. I ran those scripts: all **200 files came back byte-for-byte identical** to the commit. Images and `Cargo.lock` are left out; they are in the repo.

## 2 · How the app works

```
                 ┌──────────────────────── GeniOS.app ────────────────────────┐
  you ── G / ⌘⇧G │  main window (desktop.html)        lane window (lane.html)  │
                 │  the GeniOS menu: Card · Goals ·   one popup at a time,     │
                 │  Pending · Screen · Account        5 s, never takes focus   │
                 │        │  invoke / events                │                  │
                 │        └──────────► Rust core ◄──────────┘                  │
                 │   sign-in · Keychain · screen reading · popup queue · sound │
                 │        │ starts and watches                                 │
                 │        └──► genios-ax (Swift): reads the words of the app   │
                 │             in front of you through Accessibility           │
                 └────────────────────────────┬────────────────────────────────┘
                                              │ HTTPS, the device's own token
                                    the GeniOS brain (server)
```

### Two windows, one Rust core, one reader

- **Main window**, `desktop.html` → `src/desktop/main.tsx` → `src/menu/MenuApp.tsx`. It is 376 × 600 and opens from the menu-bar G or ⌘⇧G.
  - **Signed out:** device-code sign-in (`SignIn.tsx`).
  - **Signed in:** the GeniOS menu (`MenuPanel.tsx`):
    - **Pending**: the brain's open cards and the screen's follow-ups, numbered, most pressing first.
    - **Card**: the card that dropped or was picked, with Done · Delegate · Later · Feedback, Why it came up, and Approach · Goal · Importance.
    - **Goals**: the company brief's accepted goal lines.
    - **Screen**: everything about screen reading. It opens from the line under the header and closes with **Minimize**.
    - **Account**: version, popup sound, Silence popups, sample data, server, sign out.
  - **↻ Refresh** re-checks sign-in and settings and reloads. It stops spinning within 3 s.
- **Lane window**, `lane.html` → `src/lane/Lane.tsx`. It is 432 wide, at the top right, and never focused.
  - The Rust core pushes one popup at a time, drawn as the same dark card.
  - A gold line runs out over five seconds; hovering holds it.
  - Done, Later, Feedback and × slide it away. Show more opens it in the menu (`genios://show`).
  - An agent proposal keeps Approve · Edit · Reject, has no timer, and waits.
- **Rust core**, `src-tauri/src` (Tauri 2). It owns every secret, every call to the brain, screen reading and the popup queue. The windows only ask it things (`invoke`) and listen to it (events).
- **genios-ax**, `src-tauri/sidecar/genios-ax`. A small Swift program inside the app.
  - `watch` runs all the time and reports focus changes and whether Accessibility is allowed.
  - `read --frontmost` reads the window in front of you.
  - `trust --prompt` asks macOS for Accessibility.
  - It reads text only; there is no screen-capture code.

### The Rust core, by part

| Part | Lines | What it does |
|---|---|---|
| `lib.rs` | 960 | Start-up: the windows, the tray and ⌘⇧G, the services; the 31 commands the windows call |
| `auth/` | 1,393 | Device sign-in (RFC 8628), session refresh, the Keychain store with the once-per-run cache (`secret.rs`) |
| `capture/` | 6,305 | Screen reading: the genios-ax supervisor, the privacy gate (sensitive apps and sites, private windows, paused, away), timing, sessions, the encrypted store, uploads to `/v1/sessions`, policy, presence, reader health, Restart and Fix Accessibility |
| `moments/` | 7,748 | What pops up and why: reminders, follow-ups, the morning brief and evening wrap, situations, "Ask my agent", the delivery ledger (never say the same thing twice) |
| `lane/` | 1,158 | The popup window, its queue (five seconds; hover hold; quiet hours; pacing of at most 6 reminders an hour) and the popup sound |
| `slice/`, `matcher/`, `realtime/` | 1,809 | The device's slice of the graph (people and meetings), English and Hinglish matching, the brain's live event stream |
| `uia/` | 2,297 | Screen reading on Windows (UI Automation), for Windows builds |

### The commands the windows call (31)

| Group | Commands |
|---|---|
| Sign-in | `auth_start`, `auth_poll_status`, `auth_state`, `auth_open_browser`, `auth_cancel`, `get_access_token`, `sign_out` |
| Screen reading | `capture_status`, `capture_policy_now`, `capture_pause`, `capture_resume`, `sync_now`, `capture_restart_reader`, `capture_fix_accessibility`, `capture_open_accessibility_settings`, `read_screen_context`, `delivery_report` |
| Popups | `lane_current`, `lane_action`, `lane_hover`, `lane_resize`, `lane_silence`, `lane_sound`, `lane_recent`, `recent_feedback` |
| Follow-ups | `followups_open`, `followup_done`, `followup_snooze`, `followup_draft` |
| Other | `weekly_report`, `open_dashboard` |

**Events:**
- `genios://auth`: sign-in changed (core → windows).
- `genios://lane`: the popup to show (core → lane).
- `genios://show`: a popup's Show more (lane → menu).

### What it asks the brain for

| Purpose | Routes |
|---|---|
| Cards | `/cards`, `/cards/{id}`, `/cards/{id}/action` (Done, Later, Feedback, Answer; `surface: desktop`) |
| Goals and agents | `/v1/company-brief` (the goal lines), `/v1/agents` |
| Sign-in | `/v1/devices/code`, `/v1/devices/token`, `/auth/refresh`, `/auth/logout` |
| Screen reading | `/v1/capture/policy`, `/v1/capture/pause`, `/v1/presence`, `/v1/sessions` |
| The device's slice and popups | `/v1/seats/me/slice`, `/v1/stream`, `/v1/moments…`, `/v1/followups/{id}/…`, `/v1/delegations/{id}/…`, `/v1/seats/me/weekly-report` |

Every call the window makes to the brain (cards, goals, agents) gives up after 20 s. The card list loads one at a time, however often it is asked for.

### What the window remembers (this Mac only)

`genios.sound` (the popup sound), `genios.sample` (Show sample data), `genios.baseUrl` (the server typed under Advanced). No token is ever kept in the window.

### What is live, and what waits

| Part | State |
|---|---|
| Pending, Card, Done/Later (3 s Undo, then slides away), Feedback, Answer, refusals | **Live** |
| Popups (5 s, line, hover, sound), Silence popups, Pause/Resume, Screen view, Refresh, Fix Accessibility | **Live** |
| Goals | Goal **names** come from accepted goal lines in the company brief. **None are accepted yet**, so the tab reads "Goals 0". Progress and counts wait for `GET /v1/goals`. |
| The goal line on a card | "Not linked yet" until the brain links cards to goals |
| Delegate | Locked until the brain's delegate route. A popup's own "Ask my agent" works. |
| Feedback on a screen item | Locked: no route yet. Rate its popup instead. |

## 3 · Known issues and next steps

Rohit's notes on 23 Oct, and what the analysis found. None of these is being changed now.

1. **Repeated one-liners on cards.** Some lines repeat across many cards, such as "70 days since they wrote". The reader leaves out a line another *loaded* card repeats (`ownCard`). Lines that ride on many cards about the same person still get through. This is fixable in the shared reader (`src/lib/card-read.ts`) or at the brain. Rohit: "isko hum fix kar sakte hain".
2. **Goals: none created.** Nothing is wrong in the app. Accept or add goal lines in the company brief and they show here.
3. **Keychain dialogs on a new build.** Test builds are signed by the local identity, not an Apple Developer ID.
   - macOS's login Keychain ties each item to the build that last used it. The first launch of a **new** build asks once per item; there are 2 items.
   - Click **Always Allow** with the mouse. Return picks **Allow**, which is one time only.
   - After that, the same build is silent, and 0.3.4 asks each item at most once per run. Measured on 23 Oct: an item made by one build is refused to the next build without a dialog (`-25293`), and deleting it is silent.
   - A Developer ID (team) signature removes these dialogs for good.
4. **The release profile does not build on this Mac.** The proc-macro libraries in `target/release` will not load. The DMGs are the debug profile. A clean CI build, or `cargo clean`, gives the smaller release app.
5. **The older panel** (Today · This week · History) is still in the code but never opened. Remove it or keep it: Harsh's call when merging.
6. **Intel Macs.** Builds are Apple Silicon only. An Intel or universal build is one more build target.
7. **Merging.** `rohit/desktop-ux` → `main` is Harsh's to review. The docs branch `g010-desktop` → `speedrun008` is still to merge.

## 4 · To install, or to build again

**Install:**
1. Quit GeniOS.
2. Open the newest DMG in Downloads and check that its window title shows the version.
3. Drag GeniOS onto Applications and replace the old one.
4. Open GeniOS. If a Keychain dialog appears, type your Mac password and click **Always Allow**.
5. If the line under the header says "fix Accessibility", press it, then press **Fix Accessibility**.

**Build** (from `Extension/` in the code worktree):
1. Raise the version in `package.json` and `src-tauri/tauri.conf.json`.
2. Run `scripts/mac-dev-dmg.sh`.
3. Before handing it over, eject any old "GeniOS …" disk image (`ls /Volumes`). Move older DMGs to `~/Downloads/GeniOS-old-builds/`.

**Check:**
- `cargo test` in `src-tauri/`: 258 tests.
- `npx tsc --noEmit -p tsconfig.app.json`.
- `scripts/preview/menu-check.mjs`, with the stand-in brain and the preview server up (how to run it is at the top of the file).
