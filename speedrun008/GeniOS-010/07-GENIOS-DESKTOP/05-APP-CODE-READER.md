# 07.5 · GeniOS desktop app — the screen reader (genios-ax, Swift), commented out

**Written for:** Harsh and any coding agent working on screen reading; Rohit, to keep and hand over. `genios-ax` is the small macOS program inside GeniOS.app that reads the words of the app in front of you through Accessibility (never a picture), started and watched by the Rust core.

**What this is:** 38 source files, 4,845 lines, exactly as they stand in the dashboard repo at commit `ed2724d` (branch `rohit/desktop-ux`, GeniOS 0.3.4, 23 Oct 2026). Paths are relative to `Extension/`, except `src/lib/…`, which sits at the dashboard repo's root and is shared with the website.

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

- **1 · The package** — Swift package definition.
  - `src-tauri/sidecar/genios-ax/Package.swift` (31 lines)
- **2 · The commands** — `watch` (the long-running reader), `read --frontmost`, `trust [--prompt]`, `focus`, `snapshot`.
  - `src-tauri/sidecar/genios-ax/Sources/genios-ax/FocusCommand.swift` (42 lines)
  - `src-tauri/sidecar/genios-ax/Sources/genios-ax/ReadCommand.swift` (67 lines)
  - `src-tauri/sidecar/genios-ax/Sources/genios-ax/SnapshotCommand.swift` (85 lines)
  - `src-tauri/sidecar/genios-ax/Sources/genios-ax/TrustCommand.swift` (27 lines)
  - `src-tauri/sidecar/genios-ax/Sources/genios-ax/WatchCommand.swift` (363 lines)
  - `src-tauri/sidecar/genios-ax/Sources/genios-ax/main.swift` (30 lines)
- **3 · The reading engine** — Accessibility tree walking, the generic reader and the app readers (WhatsApp, Gmail, Slack, Teams, Outlook, LinkedIn), normalisation, pacing, the event format.
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/AX/AXSupport.swift` (158 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/AX/AXTreeSource.swift` (130 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/AppCatalog.swift` (65 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/CLI.swift` (213 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/CaptureEvent.swift` (107 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Output.swift` (28 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Pacing.swift` (95 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/GenericReader.swift` (462 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/GmailReader.swift` (60 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/LinkedInReader.swift` (44 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/OutlookReader.swift` (45 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/ReaderCapture.swift` (155 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/ReaderEngine.swift` (92 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/ScreenDoc.swift` (255 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/SlackReader.swift` (146 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/TeamsReader.swift` (51 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/ThreadScan.swift` (223 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/WhatsAppReader.swift` (277 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/TextNormalizer.swift` (50 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/TreeHash.swift` (30 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/TreeWalker.swift` (322 lines)
  - `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/URLNormalizer.swift` (58 lines)
- **4 · Tests and measuring** — Swift tests, the reader check and the measuring scripts.
  - `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/EventEncodingTests.swift` (58 lines)
  - `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/GenericReaderTests.swift` (236 lines)
  - `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/NormalizationTests.swift` (75 lines)
  - `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/PacingAndCLITests.swift` (74 lines)
  - `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/TreeWalkerTests.swift` (125 lines)
  - `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/WhatsAppReaderTests.swift` (143 lines)
  - `src-tauri/sidecar/genios-ax/scripts/check-readers.sh` (11 lines)
  - `src-tauri/sidecar/genios-ax/scripts/measure.sh` (83 lines)
  - `src-tauri/sidecar/genios-ax/scripts/reader-check/main.swift` (329 lines)

## 1 · The package

Swift package definition.

#### `src-tauri/sidecar/genios-ax/Package.swift`

```swift
// // swift-tools-version:6.0
// // genios-ax — GeniOS macOS capture sidecar (Accessibility text only, never pixels).
// // Spawned by the Tauri core (src-tauri) via tauri-plugin-shell `Command::sidecar`.
// import PackageDescription
//
// let package = Package(
//     name: "genios-ax",
//     platforms: [.macOS(.v13)],
//     products: [
//         .executable(name: "genios-ax", targets: ["genios-ax"]),
//         .library(name: "GeniosAXCore", targets: ["GeniosAXCore"]),
//     ],
//     targets: [
//         .target(
//             name: "GeniosAXCore",
//             linkerSettings: [
//                 .linkedFramework("ApplicationServices"),
//                 .linkedFramework("AppKit"),
//             ]
//         ),
//         .executableTarget(
//             name: "genios-ax",
//             dependencies: ["GeniosAXCore"]
//         ),
//         .testTarget(
//             name: "GeniosAXCoreTests",
//             dependencies: ["GeniosAXCore"]
//         ),
//     ],
//     swiftLanguageModes: [.v6]
// )
```

## 2 · The commands

`watch` (the long-running reader), `read --frontmost`, `trust [--prompt]`, `focus`, `snapshot`.

#### `src-tauri/sidecar/genios-ax/Sources/genios-ax/FocusCommand.swift`

```swift
// import Foundation
// import GeniosAXCore
// import Intents
//
// /// `genios-ax focus` — is a macOS Focus (Do Not Disturb) on? Popups stay quiet while it is.
// /// `focused` is null when the person has not allowed GeniOS to see Focus status; the app then
// /// treats Focus as off. `--prompt` asks once (macOS shows the dialog only while undetermined).
// enum FocusCommand {
//     struct Report: Encodable {
//         let schema_version = 1
//         let kind = "focus"
//         let focused: Bool?
//         let authorization: String
//     }
//
//     static func run(prompt: Bool) -> Int32 {
//         let center = INFocusStatusCenter.default
//         var status = center.authorizationStatus
//         if prompt && status == .notDetermined {
//             let done = DispatchSemaphore(value: 0)
//             center.requestAuthorization { s in
//                 status = s
//                 done.signal()
//             }
//             _ = done.wait(timeout: .now() + 60)
//         }
//         let focused: Bool? = status == .authorized ? center.focusStatus.isFocused : nil
//         let report = Report(focused: focused, authorization: name(status))
//         if let d = try? NDJSON.line(report) { StdoutWriter.write(d) }
//         return ExitCode.ok
//     }
//
//     private static func name(_ s: INFocusStatusAuthorizationStatus) -> String {
//         switch s {
//         case .authorized: return "authorized"
//         case .denied: return "denied"
//         case .restricted: return "restricted"
//         case .notDetermined: return "not_determined"
//         @unknown default: return "unknown"
//         }
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/genios-ax/ReadCommand.swift`

```swift
// import AppKit
// import ApplicationServices
// import Foundation
// import GeniosAXCore
//
// /// `genios-ax read` — one `screen_doc` NDJSON line (P1 build §3.7) for whatever app is targeted:
// /// dedicated reader when one accepts the surface (none yet), else the structured generic reader.
// @MainActor
// enum ReadCommand {
//     static func run(_ o: ReadOptions) -> Int32 {
//         guard Trust.isTrusted(prompt: o.prompt) else {
//             StdoutWriter.stderr(Trust.notTrustedMessage())
//             return ExitCode.notTrusted
//         }
//         guard let app = SnapshotCommand.resolve(o.target) else {
//             StdoutWriter.stderr("genios-ax: target app not found (\(o.target))")
//             return ExitCode.unavailable
//         }
//         AX.configureGlobalTimeout()
//         let appEl = AX.application(app.processIdentifier)
//         let bundle = app.bundleIdentifier
//
//         // Same Chromium/Electron enablement (`AXManualAccessibility`) as `watch` / `snapshot`.
//         if let e = AXEnabler.enable(app: appEl, bundleID: bundle), !e.alreadyEnabled, o.settleMs > 0 {
//             Thread.sleep(forTimeInterval: Double(o.settleMs) / 1000)
//         }
//         guard let window = AX.activeWindow(appEl) else {
//             StdoutWriter.stderr("genios-ax: no accessible window for pid \(app.processIdentifier)")
//             return ExitCode.unavailable
//         }
//         let title = AX.string(window, kAXTitleAttribute)
//         let focused = AX.element(appEl, kAXFocusedUIElementAttribute)
//         let browser = AppCatalog.isBrowser(bundle)
//         let windowFrame = AXTreeSource().read(window, childLimit: 0).attributes.frame
//
//         // Browsers: start at the page's AXWebArea so the depth budget is spent on content.
//         //
//         // SETTLED 2026-10-07 by measurement, not by argument. An earlier reading suggested rooting
//         // at the window saw 5.5× more of a Slack screen. A URL-guarded A/B on the same screen in
//         // the same second says otherwise: page-rooted 2 084 chars / 210 text nodes, window-rooted
//         // 2 084 / 213. The earlier number had been read off a different tab. Rooting here is right,
//         // and it stays.
//         let root = (browser ? focused.flatMap { AXURLLocator.webArea(ancestorsOf: $0) } : nil) ?? window
//         // A browser tab / Electron window needs the deeper Chromium budget: with the native one the
//         // walker stopped at depth 12 and handed the reader ~7% of the page's text (MEASURED
//         // 2026-10-07). An explicit --max-depth still wins.
//         var limits = ReadOptions.limits(for: bundle, explicitDepth: o.explicitDepth)
//         if o.explicitDepth { limits = o.limits }
//         let capture = ReaderCapture(source: AXTreeSource(extended: true), limits: limits, visibleRect: windowFrame)
//             .capture(root)
//         var url: String?
//         if browser {
//             url = capture.root?.firstWebAreaURL() ?? AXURLLocator.url(window: window, focused: focused)
//         }
//         let ctx = ReadContext(bundleID: bundle, url: url, windowTitle: title, draft: o.draft, now: Date())
//         let output = ScreenReaderEngine.read(capture, ctx)
//         guard var data = try? ScreenReaderEngine.encode(output, pretty: o.pretty, redact: o.redact) else {
//             return ExitCode.software
//         }
//         data.append(0x0A)
//         StdoutWriter.write(data)
//         if capture.root == nil || (capture.stats.nodes == 1 && capture.stats.axCannotComplete == 1) {
//             return ExitCode.unavailable
//         }
//         return ExitCode.ok
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/genios-ax/SnapshotCommand.swift`

```swift
// import AppKit
// import ApplicationServices
// import Foundation
// import GeniosAXCore
//
// /// `genios-ax snapshot` — one depth/node/time-limited AX tree of an app's active window.
// @MainActor
// enum SnapshotCommand {
//     struct Output: Encodable {
//         let schema_version = 1
//         let kind = "snapshot"
//         let ts: String
//         let bundle_id: String?
//         let pid: Int32
//         let app_name: String?
//         let window_title: String?
//         let url: String?
//         let ax_enable: [String: String]?
//         let limits: [String: Int]
//         let stats: WalkStats
//         let tree_hash: String
//         let root: SnapshotNode?
//     }
//
//     static func run(_ o: SnapshotOptions) -> Int32 {
//         guard Trust.isTrusted(prompt: o.prompt) else {
//             StdoutWriter.stderr(Trust.notTrustedMessage())
//             return ExitCode.notTrusted
//         }
//         guard let app = resolve(o.target) else {
//             StdoutWriter.stderr("genios-ax: target app not found (\(o.target))")
//             return ExitCode.unavailable
//         }
//         AX.configureGlobalTimeout()
//         let pid = app.processIdentifier
//         let appEl = AX.application(pid)
//
//         let enable = AXEnabler.enable(app: appEl, bundleID: app.bundleIdentifier)
//         if let e = enable, !e.alreadyEnabled, o.settleMs > 0 {
//             // Chromium builds its AX tree asynchronously after the first enable.
//             Thread.sleep(forTimeInterval: Double(o.settleMs) / 1000)
//         }
//
//         guard let window = AX.activeWindow(appEl) else {
//             StdoutWriter.stderr("genios-ax: no accessible window for pid \(pid) (app busy, windowless, or AX unsupported)")
//             return ExitCode.unavailable
//         }
//         let title = AX.string(window, kAXTitleAttribute)
//         let url = AppCatalog.isBrowser(app.bundleIdentifier)
//             ? AXURLLocator.url(window: window, focused: AX.element(appEl, kAXFocusedUIElementAttribute)) : nil
//
//         let walker = TreeWalker(source: AXTreeSource(), limits: o.limits, textMode: o.textMode)
//         let result = walker.walk(window)
//
//         let redact = o.textMode == .redacted
//         let out = Output(
//             ts: Timestamp.format(Date()), bundle_id: app.bundleIdentifier, pid: pid,
//             app_name: app.localizedName,
//             window_title: redact ? nil : title,
//             url: redact ? url.flatMap { URL(string: $0)?.host } : url,
//             ax_enable: enable?.detail,
//             limits: ["max_depth": o.limits.maxDepth, "max_nodes": o.limits.maxNodes,
//                      "max_text": o.limits.maxTextLength, "deadline_ms": o.limits.deadlineMs],
//             stats: result.stats, tree_hash: result.treeHash,
//             root: o.statsOnly ? nil : result.root)
//
//         let enc = JSONEncoder()
//         enc.outputFormatting = o.pretty ? [.sortedKeys, .prettyPrinted, .withoutEscapingSlashes] : [.sortedKeys, .withoutEscapingSlashes]
//         guard var data = try? enc.encode(out) else { return ExitCode.software }
//         data.append(0x0A)
//         StdoutWriter.write(data)
//         if result.root == nil || (result.stats.nodes == 1 && result.stats.axCannotComplete == 1) {
//             return ExitCode.unavailable
//         }
//         return ExitCode.ok
//     }
//
//     static func resolve(_ t: SnapshotTarget) -> NSRunningApplication? {
//         switch t {
//         case .frontmost: return NSWorkspace.shared.frontmostApplication
//         case .pid(let p): return NSRunningApplication(processIdentifier: p)
//         case .bundle(let b): return NSRunningApplication.runningApplications(withBundleIdentifier: b).first
//         }
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/genios-ax/TrustCommand.swift`

```swift
// import Foundation
// import GeniosAXCore
//
// /// `genios-ax trust` — machine-readable permission status for onboarding polling.
// enum TrustCommand {
//     struct Report: Encodable {
//         let schema_version = 1
//         let kind = "trust"
//         let trusted: Bool
//         let pid: Int32
//         let binary: String?
//         let responsible_pid: Int32?
//         let responsible_path: String?
//         let grant_target: String?
//     }
//
//     static func run(prompt: Bool) -> Int32 {
//         let trusted = Trust.isTrusted(prompt: prompt)
//         let r = Trust.responsibleProcess()
//         let target = r?.path.map { Trust.appBundle(containing: $0) ?? $0 }
//         let report = Report(trusted: trusted, pid: getpid(), binary: Trust.processPath(getpid()),
//                             responsible_pid: r?.pid, responsible_path: r?.path, grant_target: target)
//         if let d = try? NDJSON.line(report) { StdoutWriter.write(d) }
//         if !trusted { StdoutWriter.stderr(Trust.notTrustedMessage()) }
//         return trusted ? ExitCode.ok : ExitCode.notTrusted
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/genios-ax/WatchCommand.swift`

```swift
// import AppKit
// import ApplicationServices
// import CoreGraphics
// import Foundation
// import GeniosAXCore
//
// /// `genios-ax watch` — event-driven activity signals as NDJSON (plan §10.6 "Activity signals").
// /// Never reads element values/message text: only app identity, window title, page URL, focused role.
// @MainActor
// enum WatchCommand {
//     static var watcher: Watcher?
//
//     static func start(_ o: WatchOptions) {
//         let trusted = Trust.isTrusted(prompt: o.prompt)
//         if !trusted {
//             StdoutWriter.stderr(Trust.notTrustedMessage())
//             if !o.allowUntrusted { exit(ExitCode.notTrusted) }
//         }
//         let w = Watcher(options: o, trusted: trusted)
//         watcher = w
//         w.start()
//     }
// }
//
// /// C callback for every AXObserver; delivered on the main run loop.
// private func axObserverCallback(_ observer: AXObserver, _ element: AXUIElement, _ notification: CFString,
//                                 _ refcon: UnsafeMutableRawPointer?) {
//     guard let refcon else { return }
//     let name = notification as String
//     // Delivered on the main run loop (source added to CFRunLoopGetMain), so no actual hop occurs.
//     nonisolated(unsafe) let el = element
//     let bits = UInt(bitPattern: refcon)
//     MainActor.assumeIsolated {
//         guard let ptr = UnsafeMutableRawPointer(bitPattern: bits) else { return }
//         let w = Unmanaged<Watcher>.fromOpaque(ptr).takeUnretainedValue()
//         w.handleAX(element: el, notification: name)
//     }
// }
//
// @MainActor
// final class Watcher {
//     static let notifications = [
//         kAXFocusedWindowChangedNotification, kAXMainWindowChangedNotification, kAXTitleChangedNotification,
//         kAXFocusedUIElementChangedNotification, kAXValueChangedNotification,
//     ]
//     static let maxObservers = 32
//
//     struct Observed {
//         let observer: AXObserver
//         let app: AXUIElement
//         let bundleID: String?
//         let name: String?
//         var lastActivated: TimeInterval
//     }
//
//     struct Context: Equatable {
//         var windowTitle: String?
//         var url: String?
//     }
//
//     struct Pending {
//         var kind: EventKind
//         var element: AXUIElement
//     }
//
//     let options: WatchOptions
//     var trusted: Bool
//     var observed: [pid_t: Observed] = [:]
//     var context: [pid_t: Context] = [:]
//     var axEnabledPids = Set<pid_t>()
//     var backoff = Backoff()
//     var idle: IdleDetector
//     var valueThrottle: [pid_t: Throttle] = [:]
//     var focusThrottle: [pid_t: Throttle] = [:]
//     var pendingValue: [pid_t: Pending] = [:]
//     var pendingFocus: [pid_t: Pending] = [:]
//     var tokens: [NSObjectProtocol] = []
//     var timer: Timer?
//     var signalSources: [DispatchSourceSignal] = []
//     let selfPid = getpid()
//
//     init(options: WatchOptions, trusted: Bool) {
//         self.options = options
//         self.trusted = trusted
//         self.idle = IdleDetector(threshold: options.idleThreshold)
//     }
//
//     static func now() -> TimeInterval { ProcessInfo.processInfo.systemUptime }
//
//     // MARK: lifecycle
//
//     func start() {
//         if trusted { AX.configureGlobalTimeout() }
//         emit(CaptureEvent(kind: .watchStarted, detail: [
//             "trusted": trusted ? "true" : "false", "version": CLI.version,
//             "idle_threshold_s": String(Int(options.idleThreshold)),
//         ]))
//         subscribeWorkspace()
//         installSignalHandlers()
//         let t = Timer(timeInterval: 5, repeats: true) { _ in MainActor.assumeIsolated { self.tick() } }
//         t.tolerance = 1
//         RunLoop.main.add(t, forMode: .common)
//         timer = t
//         if let front = NSWorkspace.shared.frontmostApplication { activated(front) }
//     }
//
//     func stop(signal: Int32) {
//         emit(CaptureEvent(kind: .watchStopped, detail: ["signal": String(signal)]))
//         exit(ExitCode.ok)
//     }
//
//     private func installSignalHandlers() {
//         for sig in [SIGTERM, SIGINT, SIGHUP] {
//             signal(sig, SIG_IGN)
//             let src = DispatchSource.makeSignalSource(signal: sig, queue: .main)
//             src.setEventHandler { MainActor.assumeIsolated { self.stop(signal: sig) } }
//             src.resume()
//             signalSources.append(src)
//         }
//     }
//
//     private func subscribeWorkspace() {
//         let nc = NSWorkspace.shared.notificationCenter
//         func on(_ name: Notification.Name, _ body: @escaping @MainActor (Notification) -> Void) {
//             tokens.append(nc.addObserver(forName: name, object: nil, queue: .main) { n in
//                 nonisolated(unsafe) let note = n  // queue: .main ⇒ already on the main actor
//                 MainActor.assumeIsolated { body(note) }
//             })
//         }
//         on(NSWorkspace.didActivateApplicationNotification) { n in
//             if let app = n.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication { self.activated(app) }
//         }
//         on(NSWorkspace.didTerminateApplicationNotification) { n in
//             if let app = n.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication { self.terminated(app) }
//         }
//         on(NSWorkspace.willSleepNotification) { _ in self.emitSystem(.systemSleep) }
//         on(NSWorkspace.didWakeNotification) { _ in self.emitSystem(.systemWake) }
//         on(NSWorkspace.screensDidSleepNotification) { _ in self.emitSystem(.screensSleep) }
//         on(NSWorkspace.screensDidWakeNotification) { _ in self.emitSystem(.screensWake) }
//         on(NSWorkspace.sessionDidResignActiveNotification) { _ in self.emitSystem(.sessionInactive) }
//         on(NSWorkspace.sessionDidBecomeActiveNotification) { _ in self.emitSystem(.sessionActive) }
//
//         let dnc = DistributedNotificationCenter.default()
//         for (name, kind) in [("com.apple.screenIsLocked", EventKind.screenLocked),
//                              ("com.apple.screenIsUnlocked", EventKind.screenUnlocked)] {
//             tokens.append(dnc.addObserver(forName: Notification.Name(name), object: nil, queue: .main) { _ in
//                 MainActor.assumeIsolated { self.emitSystem(kind) }
//             })
//         }
//     }
//
//     /// 5 s housekeeping: idle transitions, parent-death detection, late trust grant.
//     private func tick() {
//         if getppid() == 1 { exit(ExitCode.ok) }  // parent (Tauri core) died → reparented to launchd
//         let anyInput = CGEventType(rawValue: ~0)!
//         let secs = CGEventSource.secondsSinceLastEventType(.combinedSessionState, eventType: anyInput)
//         switch idle.update(secondsSinceInput: secs) {
//         case .becameIdle: emitSystem(.idleStart, detail: ["idle_seconds": String(Int(secs))])
//         case .becameActive: emitSystem(.idleEnd)
//         case nil: break
//         }
//         if !trusted, Trust.isTrusted() {
//             trusted = true
//             AX.configureGlobalTimeout()
//             emit(CaptureEvent(kind: .axTrustGranted))
//             if let front = NSWorkspace.shared.frontmostApplication { activated(front) }
//         }
//     }
//
//     // MARK: apps
//
//     private func activated(_ app: NSRunningApplication) {
//         let pid = app.processIdentifier
//         guard pid != selfPid else { return }
//         if trusted {
//             attachIfNeeded(app)
//             refreshContext(pid, bundleID: app.bundleIdentifier)
//         }
//         observed[pid]?.lastActivated = Self.now()
//         emit(event(.appActivated, pid: pid, app: app))
//     }
//
//     private func terminated(_ app: NSRunningApplication) {
//         let pid = app.processIdentifier
//         detach(pid)
//         emit(CaptureEvent(kind: .appTerminated, bundleID: app.bundleIdentifier, pid: pid, appName: app.localizedName))
//         context[pid] = nil
//         axEnabledPids.remove(pid)
//         backoff.recordSuccess(pid)
//     }
//
//     private func attachIfNeeded(_ app: NSRunningApplication) {
//         let pid = app.processIdentifier
//         guard observed[pid] == nil else { return }
//         let now = Self.now()
//         guard backoff.canAttempt(pid, now: now) else { return }
//         let appEl = AX.application(pid)
//
//         if !axEnabledPids.contains(pid), let outcome = AXEnabler.enable(app: appEl, bundleID: app.bundleIdentifier) {
//             axEnabledPids.insert(pid)
//             emit(CaptureEvent(kind: .axEnabled, bundleID: app.bundleIdentifier, pid: pid,
//                               appName: app.localizedName, detail: outcome.detail))
//         }
//
//         var obs: AXObserver?
//         let cerr = AXObserverCreate(pid, axObserverCallback, &obs)
//         guard cerr == .success, let observer = obs else {
//             fail(pid, app, stage: "create", err: cerr)
//             return
//         }
//         let refcon = Unmanaged.passUnretained(self).toOpaque()
//         var failures: [String: String] = [:]
//         var cannotComplete = false
//         for n in Self.notifications {
//             let e = AXObserverAddNotification(observer, appEl, n as CFString, refcon)
//             if e != .success && e != .notificationAlreadyRegistered {
//                 failures[n] = String(e.rawValue)
//                 if e == .cannotComplete { cannotComplete = true }
//             }
//         }
//         if failures.count == Self.notifications.count || cannotComplete {
//             fail(pid, app, stage: "add_notification", err: cannotComplete ? .cannotComplete : .failure, detail: failures)
//             return
//         }
//         if !failures.isEmpty {
//             emit(CaptureEvent(kind: .observerError, bundleID: app.bundleIdentifier, pid: pid,
//                               appName: app.localizedName, detail: failures.merging(["stage": "partial"]) { a, _ in a }))
//         }
//         CFRunLoopAddSource(CFRunLoopGetMain(), AXObserverGetRunLoopSource(observer), .defaultMode)
//         observed[pid] = Observed(observer: observer, app: appEl, bundleID: app.bundleIdentifier,
//                                  name: app.localizedName, lastActivated: now)
//         backoff.recordSuccess(pid)
//         evictIfNeeded()
//     }
//
//     private func fail(_ pid: pid_t, _ app: NSRunningApplication, stage: String, err: AXError, detail: [String: String] = [:]) {
//         let delay = backoff.recordFailure(pid, now: Self.now())
//         var d = detail
//         d["stage"] = stage
//         d["ax_err"] = String(err.rawValue)
//         d["retry_in_ms"] = String(Int(delay * 1000))
//         emit(CaptureEvent(kind: .observerError, bundleID: app.bundleIdentifier, pid: pid, appName: app.localizedName, detail: d))
//         // Retry while the app stays frontmost (busy apps often become responsive shortly after launch).
//         DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
//             MainActor.assumeIsolated {
//                 guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid,
//                       let a = NSRunningApplication(processIdentifier: pid) else { return }
//                 self.attachIfNeeded(a)
//                 self.refreshContext(pid, bundleID: a.bundleIdentifier)
//             }
//         }
//     }
//
//     private func detach(_ pid: pid_t) {
//         guard let o = observed.removeValue(forKey: pid) else { return }
//         CFRunLoopRemoveSource(CFRunLoopGetMain(), AXObserverGetRunLoopSource(o.observer), .defaultMode)
//         valueThrottle[pid] = nil
//         focusThrottle[pid] = nil
//         pendingValue[pid] = nil
//         pendingFocus[pid] = nil
//     }
//
//     private func evictIfNeeded() {
//         guard observed.count > Self.maxObservers else { return }
//         let front = NSWorkspace.shared.frontmostApplication?.processIdentifier
//         if let victim = observed.filter({ $0.key != front }).min(by: { $0.value.lastActivated < $1.value.lastActivated })?.key {
//             detach(victim)
//         }
//     }
//
//     // MARK: AX notifications
//
//     func handleAX(element: AXUIElement, notification: String) {
//         guard let pid = AX.pid(of: element), let o = observed[pid] else { return }
//         switch notification {
//         case kAXFocusedWindowChangedNotification:
//             refreshContext(pid, bundleID: o.bundleID)
//             emit(event(.focusedWindowChanged, pid: pid))
//         case kAXMainWindowChangedNotification:
//             refreshContext(pid, bundleID: o.bundleID)
//             emit(event(.mainWindowChanged, pid: pid))
//         case kAXTitleChangedNotification:
//             // Only window titles (tab/thread/channel switches); element titles churn constantly.
//             guard AX.role(element) == kAXWindowRole else { return }
//             let before = context[pid]
//             refreshContext(pid, bundleID: o.bundleID)
//             guard context[pid] != before else { return }
//             emit(event(.titleChanged, pid: pid))
//         case kAXFocusedUIElementChangedNotification:
//             throttled(pid, kind: .focusedElementChanged, element: element,
//                       interval: options.focusThrottleMs, throttles: \.focusThrottle, pending: \.pendingFocus)
//         case kAXValueChangedNotification:
//             throttled(pid, kind: .valueChanged, element: element,
//                       interval: options.valueThrottleMs, throttles: \.valueThrottle, pending: \.pendingValue)
//         default:
//             break
//         }
//     }
//
//     private func throttled(_ pid: pid_t, kind: EventKind, element: AXUIElement, interval: Int,
//                            throttles: ReferenceWritableKeyPath<Watcher, [pid_t: Throttle]>,
//                            pending: ReferenceWritableKeyPath<Watcher, [pid_t: Pending]>) {
//         var t = self[keyPath: throttles][pid] ?? Throttle(minInterval: Double(interval) / 1000)
//         let now = Self.now()
//         let decision = t.offer(now: now)
//         self[keyPath: throttles][pid] = t
//         switch decision {
//         case .emitNow:
//             emit(event(kind, pid: pid, focusedRole: AX.role(element)))
//         case .coalesced:
//             self[keyPath: pending][pid] = Pending(kind: kind, element: element)
//         case .scheduleTrailing(let at):
//             self[keyPath: pending][pid] = Pending(kind: kind, element: element)
//             DispatchQueue.main.asyncAfter(deadline: .now() + max(0, at - now)) {
//                 MainActor.assumeIsolated {
//                     guard var tt = self[keyPath: throttles][pid] else { return }
//                     tt.fireTrailing(now: Self.now())
//                     self[keyPath: throttles][pid] = tt
//                     guard let p = self[keyPath: pending].removeValue(forKey: pid) else { return }
//                     self.emit(self.event(p.kind, pid: pid, focusedRole: AX.role(p.element)))
//                 }
//             }
//         }
//     }
//
//     // MARK: context + emit
//
//     private func refreshContext(_ pid: pid_t, bundleID: String?) {
//         let appEl = observed[pid]?.app ?? AX.application(pid)
//         let window = AX.activeWindow(appEl)
//         var c = Context()
//         c.windowTitle = window.flatMap { AX.string($0, kAXTitleAttribute) }
//         if AppCatalog.isBrowser(bundleID) {
//             c.url = AXURLLocator.url(window: window, focused: AX.element(appEl, kAXFocusedUIElementAttribute))
//         }
//         context[pid] = c
//     }
//
//     private func event(_ kind: EventKind, pid: pid_t, app: NSRunningApplication? = nil, focusedRole: String? = nil) -> CaptureEvent {
//         let o = observed[pid]
//         let a = app ?? (o == nil ? NSRunningApplication(processIdentifier: pid) : nil)
//         let role = focusedRole ?? (trusted ? (o?.app ?? AX.application(pid)).focusedRole : nil)
//         let c = context[pid]
//         return CaptureEvent(kind: kind, bundleID: o?.bundleID ?? a?.bundleIdentifier, pid: pid,
//                             appName: o?.name ?? a?.localizedName, windowTitle: c?.windowTitle, url: c?.url,
//                             focusedRole: role)
//     }
//
//     private func emitSystem(_ kind: EventKind, detail: [String: String]? = nil) {
//         let front = NSWorkspace.shared.frontmostApplication
//         emit(CaptureEvent(kind: kind, bundleID: front?.bundleIdentifier, pid: front?.processIdentifier,
//                           appName: front?.localizedName, detail: detail))
//     }
//
//     private func emit(_ e: CaptureEvent) {
//         guard let d = try? NDJSON.line(e) else { return }
//         StdoutWriter.write(d)
//     }
// }
//
// private extension AXUIElement {
//     var focusedRole: String? { AX.element(self, kAXFocusedUIElementAttribute).flatMap(AX.role) }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/genios-ax/main.swift`

```swift
// import Foundation
// import GeniosAXCore
//
// StdoutWriter.ignoreSIGPIPE()
//
// let command: Command
// do {
//     command = try CLI.parse(Array(CommandLine.arguments.dropFirst()))
// } catch {
//     StdoutWriter.stderr("genios-ax: \(error)\n\n\(CLI.usage)")
//     exit(ExitCode.usage)
// }
//
// switch command {
// case .help:
//     print(CLI.usage)
// case .version:
//     print(CLI.version)
// case .trust(let prompt):
//     exit(TrustCommand.run(prompt: prompt))
// case .focus(let prompt):
//     exit(FocusCommand.run(prompt: prompt))
// case .snapshot(let options):
//     exit(MainActor.assumeIsolated { SnapshotCommand.run(options) })
// case .read(let options):
//     exit(MainActor.assumeIsolated { ReadCommand.run(options) })
// case .watch(let options):
//     MainActor.assumeIsolated { WatchCommand.start(options) }
//     RunLoop.main.run()
// }
```

## 3 · The reading engine

Accessibility tree walking, the generic reader and the app readers (WhatsApp, Gmail, Slack, Teams, Outlook, LinkedIn), normalisation, pacing, the event format.

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/AX/AXSupport.swift`

```swift
// import AppKit
// import ApplicationServices
// import Darwin
//
// /// Thin, allocation-light helpers over the AXUIElement C API.
// public enum AX {
//     /// Per-call IPC timeout (plan §10.6 read limits).
//     public static let messagingTimeout: Float = 0.4
//
//     public static func configureGlobalTimeout() {
//         AXUIElementSetMessagingTimeout(AXUIElementCreateSystemWide(), messagingTimeout)
//     }
//
//     public static func application(_ pid: pid_t) -> AXUIElement {
//         let app = AXUIElementCreateApplication(pid)
//         AXUIElementSetMessagingTimeout(app, messagingTimeout)
//         return app
//     }
//
//     public static func copy(_ el: AXUIElement, _ attr: String) -> (CFTypeRef?, AXError) {
//         var v: CFTypeRef?
//         let err = AXUIElementCopyAttributeValue(el, attr as CFString, &v)
//         return (err == .success ? v : nil, err)
//     }
//
//     public static func string(_ el: AXUIElement, _ attr: String) -> String? {
//         stringValue(copy(el, attr).0)
//     }
//
//     public static func element(_ el: AXUIElement, _ attr: String) -> AXUIElement? {
//         guard let v = copy(el, attr).0, CFGetTypeID(v) == AXUIElementGetTypeID() else { return nil }
//         return (v as! AXUIElement)
//     }
//
//     public static func role(_ el: AXUIElement) -> String? { string(el, kAXRoleAttribute) }
//
//     @discardableResult
//     public static func setBool(_ el: AXUIElement, _ attr: String, _ value: Bool) -> AXError {
//         AXUIElementSetAttributeValue(el, attr as CFString, (value ? kCFBooleanTrue : kCFBooleanFalse) as CFTypeRef)
//     }
//
//     public static func pid(of el: AXUIElement) -> pid_t? {
//         var p: pid_t = 0
//         return AXUIElementGetPid(el, &p) == .success ? p : nil
//     }
//
//     /// Converts the common AX value types that carry text into a String.
//     public static func stringValue(_ v: CFTypeRef?) -> String? {
//         guard let v else { return nil }
//         let t = CFGetTypeID(v)
//         if t == CFStringGetTypeID() { return (v as! CFString) as String }
//         if t == CFAttributedStringGetTypeID() { return CFAttributedStringGetString((v as! CFAttributedString)) as String }
//         if t == CFURLGetTypeID() { return CFURLGetString((v as! CFURL)) as String }
//         return nil
//     }
//
//     public static func isAXError(_ v: CFTypeRef) -> Bool {
//         CFGetTypeID(v) == AXValueGetTypeID() && AXValueGetType(v as! AXValue) == .axError
//     }
//
//     public static func readError(_ err: AXError) -> NodeReadError? {
//         switch err {
//         case .success, .noValue, .attributeUnsupported: return nil
//         case .cannotComplete: return .cannotComplete
//         case .invalidUIElement: return .invalidElement
//         default: return .other(err.rawValue)
//         }
//     }
//
//     /// Focused window → main window → first window.
//     public static func activeWindow(_ app: AXUIElement) -> AXUIElement? {
//         if let w = element(app, kAXFocusedWindowAttribute) { return w }
//         if let w = element(app, kAXMainWindowAttribute) { return w }
//         if let ws = copy(app, kAXWindowsAttribute).0 as? [AXUIElement] { return ws.first }
//         return nil
//     }
// }
//
// // MARK: - Trust
//
// public enum Trust {
//     public static func isTrusted(prompt: Bool = false) -> Bool {
//         AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": prompt] as CFDictionary)
//     }
//
//     /// The process TCC attributes our requests to ("responsible process"). Uses the private but
//     /// long-stable `responsibility_get_pid_responsible_for_pid` via dlsym; nil if unavailable.
//     public static func responsibleProcess() -> (pid: pid_t, path: String?)? {
//         typealias Fn = @convention(c) (pid_t) -> pid_t
//         guard let sym = dlsym(UnsafeMutableRawPointer(bitPattern: -2), "responsibility_get_pid_responsible_for_pid")
//         else { return nil }
//         let fn = unsafeBitCast(sym, to: Fn.self)
//         let rpid = fn(getpid())
//         guard rpid > 0 else { return nil }
//         return (rpid, processPath(rpid))
//     }
//
//     public static func processPath(_ pid: pid_t) -> String? {
//         var buf = [CChar](repeating: 0, count: 4 * Int(MAXPATHLEN))
//         let n = proc_pidpath(pid, &buf, UInt32(buf.count))
//         guard n > 0 else { return nil }
//         return String(decoding: buf.prefix(Int(n)).map { UInt8(bitPattern: $0) }, as: UTF8.self)
//     }
//
//     /// Outermost `.app` bundle containing `path`, for a human-readable grant instruction.
//     public static func appBundle(containing path: String) -> String? {
//         guard let r = path.range(of: ".app/") else { return nil }
//         return String(path[..<r.lowerBound]) + ".app"
//     }
//
//     public static func notTrustedMessage() -> String {
//         let me = processPath(getpid()) ?? CommandLine.arguments[0]
//         var grantee = me
//         if let r = responsibleProcess(), let p = r.path, r.pid != getpid() {
//             grantee = appBundle(containing: p) ?? p
//         }
//         return """
//             genios-ax: Accessibility permission is not granted to this process.
//               Grant it in: System Settings → Privacy & Security → Accessibility → enable (or "+" add):
//                 \(grantee)
//               (macOS attributes the permission to the app that launched genios-ax; binary: \(me))
//               Then re-run. Exit code 77.
//             """
//     }
// }
//
// // MARK: - Chromium / Electron accessibility enablement
//
// public enum AXEnabler {
//     public struct Outcome: Sendable, Equatable {
//         public var manual: Int32?
//         public var enhanced: Int32?
//         public var alreadyEnabled: Bool
//
//         public var detail: [String: String] {
//             var d = ["already_enabled": alreadyEnabled ? "true" : "false"]
//             if let m = manual { d["manual_ax_err"] = String(m) }
//             if let e = enhanced { d["enhanced_ui_err"] = String(e) }
//             return d
//         }
//     }
//
//     /// Sets `AXManualAccessibility` (Chromium/Electron); falls back to `AXEnhancedUserInterface`
//     /// only for Chromium browsers when the manual attribute is rejected.
//     public static func enable(app: AXUIElement, bundleID: String?) -> Outcome? {
//         guard AppCatalog.needsManualAccessibility(bundleID) else { return nil }
//         if let v = AX.copy(app, "AXManualAccessibility").0, CFGetTypeID(v) == CFBooleanGetTypeID(),
//            CFBooleanGetValue((v as! CFBoolean)) {
//             return Outcome(manual: nil, enhanced: nil, alreadyEnabled: true)
//         }
//         let m = AX.setBool(app, "AXManualAccessibility", true)
//         var out = Outcome(manual: m.rawValue, enhanced: nil, alreadyEnabled: false)
//         if m != .success, AppCatalog.allowsEnhancedUIFallback(bundleID) {
//             out.enhanced = AX.setBool(app, "AXEnhancedUserInterface", true).rawValue
//         }
//         return out
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/AX/AXTreeSource.swift`

```swift
// import ApplicationServices
// import CoreGraphics
//
// /// Production `TreeSource`: one batched AX IPC per node
// /// (`AXUIElementCopyMultipleAttributeValues`) under the 400 ms messaging timeout.
// public struct AXTreeSource: TreeSource {
//     public typealias Element = AXUIElement
//
//     static let attributes: [String] = [
//         kAXRoleAttribute, kAXSubroleAttribute, kAXTitleAttribute, kAXDescriptionAttribute,
//         kAXValueAttribute, "AXURL", kAXPositionAttribute, kAXSizeAttribute, kAXChildrenAttribute,
//     ]
//     /// `read` (generic reader) also needs placeholder, focus and the label element — same single IPC.
//     static let extendedAttributes: [String] = attributes + [
//         "AXPlaceholderValue", kAXFocusedAttribute, kAXTitleUIElementAttribute,
//     ]
//     nonisolated(unsafe) static let cfAttributes = attributes as CFArray
//     nonisolated(unsafe) static let cfExtendedAttributes = extendedAttributes as CFArray
//
//     /// True for the reader: fetches `extendedAttributes` and resolves `AXTitleUIElement` text
//     /// (one extra IPC, only for elements that have a label element).
//     public let extended: Bool
//
//     public init(extended: Bool = false) {
//         self.extended = extended
//     }
//
//     public func read(_ element: AXUIElement, childLimit: Int) -> NodeRead<AXUIElement> {
//         var values: CFArray?
//         let names = extended ? Self.extendedAttributes : Self.attributes
//         let cf = extended ? Self.cfExtendedAttributes : Self.cfAttributes
//         let err = AXUIElementCopyMultipleAttributeValues(element, cf, AXCopyMultipleAttributeOptions(), &values)
//         guard err == .success, let arr = values as? [AnyObject], arr.count == names.count else {
//             return NodeRead(attributes: NodeAttributes(), children: [], totalChildren: 0,
//                             error: AX.readError(err) ?? .other(err.rawValue))
//         }
//         func v(_ i: Int) -> CFTypeRef? {
//             let o = arr[i] as CFTypeRef
//             return AX.isAXError(o) ? nil : o
//         }
//         var a = NodeAttributes()
//         a.role = AX.stringValue(v(0))
//         a.subrole = AX.stringValue(v(1))
//         a.title = AX.stringValue(v(2))
//         a.description = AX.stringValue(v(3))
//         // Value is fetched in the same batch; the walker drops it for secure fields before any use.
//         a.value = AX.stringValue(v(4))
//         a.url = AX.stringValue(v(5))
//         if let p = v(6), let s = v(7), CFGetTypeID(p) == AXValueGetTypeID(), CFGetTypeID(s) == AXValueGetTypeID() {
//             var pt = CGPoint.zero
//             var sz = CGSize.zero
//             if AXValueGetValue(p as! AXValue, .cgPoint, &pt), AXValueGetValue(s as! AXValue, .cgSize, &sz) {
//                 a.frame = CGRect(origin: pt, size: sz)
//             }
//         }
//         if extended {
//             a.placeholder = AX.stringValue(v(9))
//             if let f = v(10), CFGetTypeID(f) == CFBooleanGetTypeID() { a.focused = CFBooleanGetValue((f as! CFBoolean)) }
//             if let t = v(11), CFGetTypeID(t) == AXUIElementGetTypeID() {
//                 let label = t as! AXUIElement
//                 a.titleUIText = AX.string(label, kAXValueAttribute) ?? AX.string(label, kAXTitleAttribute)
//             }
//         }
//         let kids = (v(8) as? [AXUIElement]) ?? []
//         return NodeRead(attributes: a, children: Array(kids.prefix(childLimit)), totalChildren: kids.count)
//     }
// }
//
// /// Finds the current page URL of a browser window: AXWebArea `AXURL` (ancestor walk from the
// /// focused element, then bounded BFS of the window), else the address-bar text field value.
// public enum AXURLLocator {
//     public static func url(window: AXUIElement?, focused: AXUIElement?, nodeBudget: Int = 800) -> String? {
//         if let f = focused, let u = webAreaURL(ancestorsOf: f) { return u }
//         guard let window else { return nil }
//         var queue: [(AXUIElement, Bool)] = [(window, false)]  // (element, inside toolbar)
//         var head = 0
//         var addressBar: String?
//         let attrs = [kAXRoleAttribute, "AXURL", kAXChildrenAttribute] as CFArray
//         while head < queue.count, head < nodeBudget {
//             let (el, inToolbar) = queue[head]
//             head += 1
//             var values: CFArray?
//             guard AXUIElementCopyMultipleAttributeValues(el, attrs, AXCopyMultipleAttributeOptions(), &values) == .success,
//                   let arr = values as? [AnyObject], arr.count == 3 else { continue }
//             let role = AX.isAXError(arr[0] as CFTypeRef) ? nil : AX.stringValue(arr[0] as CFTypeRef)
//             if role == "AXWebArea", !AX.isAXError(arr[1] as CFTypeRef),
//                let u = AX.stringValue(arr[1] as CFTypeRef), u.hasPrefix("http") {
//                 return URLNormalizer.stripTracking(u)
//             }
//             if role == kAXTextFieldRole, inToolbar, addressBar == nil,
//                AX.string(el, kAXSubroleAttribute) != "AXSecureTextField",
//                let raw = AX.string(el, kAXValueAttribute) {
//                 addressBar = AppCatalog.urlFromAddressBar(raw)
//             }
//             if role == kAXTabGroupRole || role == kAXMenuBarRole || role == kAXScrollBarRole { continue }
//             if let kids = arr[2] as? [AXUIElement] {
//                 let tb = inToolbar || role == kAXToolbarRole
//                 for k in kids { queue.append((k, tb)) }
//             }
//         }
//         return addressBar
//     }
//
//     /// Outermost `AXWebArea` above the focused element (the page, not an iframe), for rooting a
//     /// browser read at the page so the depth budget is not spent on browser chrome.
//     public static func webArea(ancestorsOf start: AXUIElement, maxHops: Int = 40) -> AXUIElement? {
//         var el: AXUIElement? = start
//         var hops = 0
//         var found: AXUIElement?
//         while let e = el, hops < maxHops {
//             if AX.role(e) == "AXWebArea" { found = e }
//             el = AX.element(e, kAXParentAttribute)
//             hops += 1
//         }
//         return found
//     }
//
//     static func webAreaURL(ancestorsOf start: AXUIElement, maxHops: Int = 40) -> String? {
//         var el: AXUIElement? = start
//         var hops = 0
//         while let e = el, hops < maxHops {
//             if AX.role(e) == "AXWebArea", let u = AX.string(e, "AXURL"), u.hasPrefix("http") {
//                 return URLNormalizer.stripTracking(u)
//             }
//             el = AX.element(e, kAXParentAttribute)
//             hops += 1
//         }
//         return nil
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/AppCatalog.swift`

```swift
// import Foundation
//
// /// Static knowledge about target apps. Kept deliberately tight: enabling Chromium accessibility
// /// costs the target app CPU, so it is only done for apps GeniOS actually reads.
// public enum AppCatalog {
//     public static let chromiumBrowsers: Set<String> = [
//         "com.google.Chrome", "com.google.Chrome.beta", "com.google.Chrome.dev", "com.google.Chrome.canary",
//         "company.thebrowser.Browser",  // Arc
//         "com.brave.Browser", "com.brave.Browser.beta",
//         "com.microsoft.edgemac", "com.microsoft.edgemac.Beta", "com.microsoft.edgemac.Dev",
//         "org.chromium.Chromium", "com.vivaldi.Vivaldi", "com.operasoftware.Opera",
//     ]
//
//     /// Electron apps GeniOS reads (need `AXManualAccessibility`).
//     ///
//     /// Without a bundle id on this list the app's accessibility tree is never built, so the reader
//     /// gets an empty window and the product looks "switched off" for that app. Slack was the only
//     /// entry — which is why Teams desktop, a manager's main work chat on a company laptop, read as
//     /// nothing at all.
//     public static let electronTargets: Set<String> = [
//         "com.tinyspeck.slackmacgap",                      // Slack desktop
//         "com.microsoft.teams", "com.microsoft.teams2",     // Teams desktop (classic and new)
//         "com.hnc.Discord",                                 // Discord desktop
//         "notion.id", "notion.desktop",                     // Notion desktop
//     ]
//
//     /// Is this app's accessibility tree a Chromium DOM tree (browser tab or Electron app)?
//     /// Those are about twice as deep as a native window — see `ReadOptions.webLimits`.
//     public static func isChromiumTree(_ bundleID: String?) -> Bool {
//         guard let b = bundleID else { return false }
//         return chromiumBrowsers.contains(b) || electronTargets.contains(b) || otherBrowsers.contains(b)
//     }
//
//     public static let otherBrowsers: Set<String> = [
//         "com.apple.Safari", "com.apple.SafariTechnologyPreview", "org.mozilla.firefox",
//     ]
//
//     public static func isBrowser(_ bundleID: String?) -> Bool {
//         guard let b = bundleID else { return false }
//         return chromiumBrowsers.contains(b) || otherBrowsers.contains(b)
//     }
//
//     public static func needsManualAccessibility(_ bundleID: String?) -> Bool {
//         guard let b = bundleID else { return false }
//         return chromiumBrowsers.contains(b) || electronTargets.contains(b)
//     }
//
//     /// `AXEnhancedUserInterface` is a fallback only for Chromium browsers whose
//     /// `AXManualAccessibility` set failed — it can disturb window animations/tiling managers.
//     public static func allowsEnhancedUIFallback(_ bundleID: String?) -> Bool {
//         guard let b = bundleID else { return false }
//         return chromiumBrowsers.contains(b)
//     }
//
//     /// Normalises a browser address-bar value ("mail.google.com/mail/u/0/") into a URL string.
//     /// Returns nil for values that are not host-like (search terms being typed, empty).
//     public static func urlFromAddressBar(_ raw: String) -> String? {
//         let v = raw.trimmingCharacters(in: .whitespacesAndNewlines)
//         guard !v.isEmpty, !v.contains(" ") else { return nil }
//         if v.hasPrefix("http://") || v.hasPrefix("https://") { return URLNormalizer.stripTracking(v) }
//         let host = v.split(separator: "/", maxSplits: 1).first.map(String.init) ?? ""
//         guard host.contains("."), !host.hasPrefix("."), !host.hasSuffix(".") else { return nil }
//         return URLNormalizer.stripTracking("https://" + v)
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/CLI.swift`

```swift
// import Foundation
//
// public enum ExitCode {
//     public static let ok: Int32 = 0
//     public static let usage: Int32 = 64  // EX_USAGE
//     public static let unavailable: Int32 = 69  // EX_UNAVAILABLE — target app not found / unresponsive
//     public static let software: Int32 = 70  // EX_SOFTWARE
//     public static let notTrusted: Int32 = 77  // EX_NOPERM — Accessibility not granted
// }
//
// public enum SnapshotTarget: Equatable, Sendable {
//     case frontmost
//     case pid(Int32)
//     case bundle(String)
// }
//
// public struct SnapshotOptions: Equatable, Sendable {
//     public var target: SnapshotTarget = .frontmost
//     public var limits = WalkLimits()
//     public var textMode: TextMode = .full
//     public var statsOnly = false
//     public var pretty = false
//     /// Wait after first enabling Chromium/Electron accessibility so the tree can populate.
//     public var settleMs = 400
//     public var prompt = false
//     public init() {}
// }
//
// /// `genios-ax read` — one `screen_doc` (P1 build §3.7) of the target app's active window.
// public struct ReadOptions: Equatable, Sendable {
//     /// Plan §10.6 read limits: depth ≤ 12, ≤ 5k nodes, 400 ms; per-attribute text ≤ 30k chars.
//     public static let defaultLimits = WalkLimits(maxDepth: 12, maxNodes: 5000, maxTextLength: 30_000, deadlineMs: 400)
//     /// Chromium trees (a browser tab, an Electron app) are FAR deeper than a native window.
//     ///
//     /// MEASURED live 2026-10-07 through this very `read` path, one activation each:
//     ///
//     /// | surface      | depth 12 (what shipped) | depth 28 | depth 40 |
//     /// |--------------|-------------------------|----------|----------|
//     /// | Slack web    | 502 chars, truncated    | 7 274, still truncated | **9 477, complete, 54 ms** |
//     /// | Gmail inbox  | 7 702, truncated        | 8 509, complete        | 8 509 |
//     /// | ordinary page| 1 368 text nodes, trunc | 1 703, complete        | 1 703 |
//     ///
//     /// Slack's message list sits at depth 37. A web app's conversation simply is not inside 12 —
//     /// which is why "Slack par kuch nahi milta" was never a reader problem: the walker handed the
//     /// reader 502 characters of a 9 500-character screen. Nodes (5 000) and the 400 ms deadline
//     /// stay the real guards; the deepest page measured cost 250 ms / 4 840 nodes at this depth.
//     public static let webLimits = WalkLimits(maxDepth: 40, maxNodes: 5000, maxTextLength: 30_000, deadlineMs: 400)
//
//     /// The budget for one surface. `explicitDepth` ⇒ the caller passed `--max-depth` and owns it.
//     public static func limits(for bundleID: String?, explicitDepth: Bool = false) -> WalkLimits {
//         if explicitDepth { return defaultLimits }
//         return AppCatalog.isChromiumTree(bundleID) ? webLimits : defaultLimits
//     }
//     public var target: SnapshotTarget = .frontmost
//     public var limits = ReadOptions.defaultLimits
//     /// `--max-depth` was passed: the caller owns the budget and the per-surface default is skipped.
//     public var explicitDepth = false
//     /// Draft assist on: read the focused editable element into `focused_field`.
//     public var draft = false
//     /// Structure only (no captured text) — for `scripts/measure.sh`.
//     public var redact = false
//     public var pretty = false
//     public var settleMs = 400
//     public var prompt = false
//     public init() {}
// }
//
// public struct WatchOptions: Equatable, Sendable {
//     public var idleThreshold: TimeInterval = 120
//     public var valueThrottleMs = 1000
//     public var focusThrottleMs = 250
//     /// Degraded mode: without Accessibility still emit app/idle/sleep events and attach AX once granted.
//     public var allowUntrusted = false
//     public var prompt = false
//     public init() {}
// }
//
// public enum Command: Equatable, Sendable {
//     case watch(WatchOptions)
//     case snapshot(SnapshotOptions)
//     case read(ReadOptions)
//     case trust(prompt: Bool)
//     case focus(prompt: Bool)
//     case help
//     case version
// }
//
// public struct CLIError: Error, CustomStringConvertible, Equatable {
//     public let description: String
//     public init(_ d: String) { description = d }
// }
//
// public enum CLI {
//     public static let version = "0.1.0"
//
//     public static let usage = """
//         genios-ax \(version) — GeniOS capture sidecar (Accessibility text only; no screenshots)
//
//         USAGE
//           genios-ax watch    [--idle-seconds 120] [--value-throttle-ms 1000] [--allow-untrusted] [--prompt]
//           genios-ax snapshot [--frontmost | --pid N | --bundle ID] [--max-depth 12] [--max-nodes 5000]
//                              [--max-text 1000] [--deadline-ms 3000] [--settle-ms 400]
//                              [--redact | --stats-only] [--pretty] [--prompt]
//           genios-ax read     [--frontmost | --pid N | --bundle ID] [--draft] [--redact] [--pretty]
//                              [--max-depth 12] [--max-nodes 5000] [--deadline-ms 400] [--settle-ms 400] [--prompt]
//           genios-ax trust    [--prompt]
//           genios-ax focus    [--prompt]
//           genios-ax --version | --help
//
//         OUTPUT  watch: one NDJSON event per line on stdout. snapshot/trust/focus: one JSON document.
//                 read: one screen_doc NDJSON line (focused input only with --draft; never secure fields).
//         EXIT    0 ok · 64 usage · 69 app unavailable · 77 Accessibility not granted
//         """
//
//     public static func parse(_ args: [String]) throws -> Command {
//         guard let sub = args.first else { return .help }
//         var rest = Array(args.dropFirst())
//         switch sub {
//         case "-h", "--help", "help": return .help
//         case "-v", "--version", "version": return .version
//         case "trust":
//             var prompt = false
//             while let a = rest.first {
//                 rest.removeFirst()
//                 guard a == "--prompt" else { throw CLIError("trust: unknown option \(a)") }
//                 prompt = true
//             }
//             return .trust(prompt: prompt)
//         case "focus":
//             var prompt = false
//             while let a = rest.first {
//                 rest.removeFirst()
//                 guard a == "--prompt" else { throw CLIError("focus: unknown option \(a)") }
//                 prompt = true
//             }
//             return .focus(prompt: prompt)
//         case "watch":
//             var o = WatchOptions()
//             while let a = rest.first {
//                 rest.removeFirst()
//                 switch a {
//                 case "--idle-seconds": o.idleThreshold = TimeInterval(try int(a, &rest, min: 1))
//                 case "--value-throttle-ms": o.valueThrottleMs = try int(a, &rest, min: 0)
//                 case "--focus-throttle-ms": o.focusThrottleMs = try int(a, &rest, min: 0)
//                 case "--allow-untrusted": o.allowUntrusted = true
//                 case "--prompt": o.prompt = true
//                 default: throw CLIError("watch: unknown option \(a)")
//                 }
//             }
//             return .watch(o)
//         case "snapshot":
//             var o = SnapshotOptions()
//             var targets = 0
//             while let a = rest.first {
//                 rest.removeFirst()
//                 switch a {
//                 case "--frontmost": o.target = .frontmost; targets += 1
//                 case "--pid": o.target = .pid(Int32(try int(a, &rest, min: 1))); targets += 1
//                 case "--bundle":
//                     guard let v = rest.first, !v.hasPrefix("--") else { throw CLIError("--bundle needs a bundle id") }
//                     rest.removeFirst()
//                     o.target = .bundle(v); targets += 1
//                 case "--max-depth": o.limits.maxDepth = try int(a, &rest, min: 0, max: 64)
//                 case "--max-nodes": o.limits.maxNodes = try int(a, &rest, min: 1, max: 100_000)
//                 case "--max-text": o.limits.maxTextLength = try int(a, &rest, min: 1)
//                 case "--deadline-ms": o.limits.deadlineMs = try int(a, &rest, min: 0)
//                 case "--settle-ms": o.settleMs = try int(a, &rest, min: 0, max: 10_000)
//                 case "--redact": o.textMode = .redacted
//                 case "--stats-only": o.statsOnly = true; o.textMode = .redacted
//                 case "--pretty": o.pretty = true
//                 case "--prompt": o.prompt = true
//                 default: throw CLIError("snapshot: unknown option \(a)")
//                 }
//             }
//             if targets > 1 { throw CLIError("snapshot: use only one of --frontmost / --pid / --bundle") }
//             return .snapshot(o)
//         case "read":
//             var o = ReadOptions()
//             var targets = 0
//             while let a = rest.first {
//                 rest.removeFirst()
//                 switch a {
//                 case "--frontmost": o.target = .frontmost; targets += 1
//                 case "--pid": o.target = .pid(Int32(try int(a, &rest, min: 1))); targets += 1
//                 case "--bundle":
//                     guard let v = rest.first, !v.hasPrefix("--") else { throw CLIError("--bundle needs a bundle id") }
//                     rest.removeFirst()
//                     o.target = .bundle(v); targets += 1
//                 case "--draft": o.draft = true
//                 case "--redact": o.redact = true
//                 case "--pretty": o.pretty = true
//                 case "--max-depth": o.limits.maxDepth = try int(a, &rest, min: 0, max: 64); o.explicitDepth = true
//                 case "--max-nodes": o.limits.maxNodes = try int(a, &rest, min: 1, max: 100_000)
//                 case "--deadline-ms": o.limits.deadlineMs = try int(a, &rest, min: 0)
//                 case "--settle-ms": o.settleMs = try int(a, &rest, min: 0, max: 10_000)
//                 case "--prompt": o.prompt = true
//                 default: throw CLIError("read: unknown option \(a)")
//                 }
//             }
//             if targets > 1 { throw CLIError("read: use only one of --frontmost / --pid / --bundle") }
//             return .read(o)
//         default:
//             throw CLIError("unknown command \(sub)")
//         }
//     }
//
//     private static func int(_ flag: String, _ rest: inout [String], min lo: Int, max hi: Int = .max) throws -> Int {
//         guard let v = rest.first, let n = Int(v) else { throw CLIError("\(flag) needs an integer") }
//         rest.removeFirst()
//         guard n >= lo, n <= hi else { throw CLIError("\(flag) must be in \(lo)...\(hi)") }
//         return n
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/CaptureEvent.swift`

```swift
// import Foundation
//
// /// Kinds of events emitted by `genios-ax watch`. Raw values are the wire format — never rename, only add.
// public enum EventKind: String, Codable, Sendable, CaseIterable {
//     case watchStarted = "watch_started"
//     case watchStopped = "watch_stopped"
//     case axTrustGranted = "ax_trust_granted"
//     case appActivated = "app_activated"
//     case appTerminated = "app_terminated"
//     case focusedWindowChanged = "focused_window_changed"
//     case mainWindowChanged = "main_window_changed"
//     case titleChanged = "title_changed"
//     case focusedElementChanged = "focused_element_changed"
//     case valueChanged = "value_changed"
//     case idleStart = "idle_start"
//     case idleEnd = "idle_end"
//     case screenLocked = "screen_locked"
//     case screenUnlocked = "screen_unlocked"
//     case screensSleep = "screens_sleep"
//     case screensWake = "screens_wake"
//     case systemSleep = "system_sleep"
//     case systemWake = "system_wake"
//     case sessionInactive = "session_inactive"
//     case sessionActive = "session_active"
//     /// Diagnostic: result of enabling Chromium/Electron accessibility (codes only, no content).
//     case axEnabled = "ax_enabled"
//     /// Diagnostic: observer registration failure (AXError codes only).
//     case observerError = "observer_error"
// }
//
// /// One `watch` event. Encoded as a single NDJSON line; every schema key is always present
// /// (JSON `null` when unknown) so consumers can rely on a fixed shape.
// public struct CaptureEvent: Encodable, Sendable, Equatable {
//     public static let schemaVersion = 1
//
//     public var ts: Date
//     public var kind: EventKind
//     public var bundleID: String?
//     public var pid: Int32?
//     public var appName: String?
//     public var windowTitle: String?
//     public var url: String?
//     public var focusedRole: String?
//     /// Non-content diagnostics only (durations, AXError codes, flags). Omitted when nil.
//     public var detail: [String: String]?
//
//     public init(
//         ts: Date = Date(), kind: EventKind, bundleID: String? = nil, pid: Int32? = nil,
//         appName: String? = nil, windowTitle: String? = nil, url: String? = nil,
//         focusedRole: String? = nil, detail: [String: String]? = nil
//     ) {
//         self.ts = ts
//         self.kind = kind
//         self.bundleID = bundleID
//         self.pid = pid
//         self.appName = appName
//         self.windowTitle = windowTitle
//         self.url = url
//         self.focusedRole = focusedRole
//         self.detail = detail
//     }
//
//     enum CodingKeys: String, CodingKey {
//         case schemaVersion = "schema_version"
//         case ts, kind
//         case bundleID = "bundle_id"
//         case pid
//         case appName = "app_name"
//         case windowTitle = "window_title"
//         case url
//         case focusedRole = "focused_role"
//         case detail
//     }
//
//     public func encode(to encoder: any Encoder) throws {
//         var c = encoder.container(keyedBy: CodingKeys.self)
//         try c.encode(Self.schemaVersion, forKey: .schemaVersion)
//         try c.encode(Timestamp.format(ts), forKey: .ts)
//         try c.encode(kind, forKey: .kind)
//         try c.encode(bundleID, forKey: .bundleID)
//         try c.encode(pid, forKey: .pid)
//         try c.encode(appName, forKey: .appName)
//         try c.encode(windowTitle, forKey: .windowTitle)
//         try c.encode(url, forKey: .url)
//         try c.encode(focusedRole, forKey: .focusedRole)
//         try c.encodeIfPresent(detail, forKey: .detail)
//     }
// }
//
// public enum Timestamp {
//     /// ISO-8601 UTC with milliseconds, e.g. `2026-09-12T10:11:12.345Z`.
//     public static func format(_ date: Date) -> String {
//         date.formatted(Date.ISO8601FormatStyle(includingFractionalSeconds: true, timeZone: .gmt))
//     }
// }
//
// public enum NDJSON {
//     /// Encodes `value` as exactly one line of JSON terminated by `\n`.
//     /// JSON string escaping guarantees no raw newline can appear inside the line.
//     public static func line<T: Encodable>(_ value: T) throws -> Data {
//         let encoder = JSONEncoder()
//         encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
//         var data = try encoder.encode(value)
//         data.append(0x0A)
//         return data
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Output.swift`

```swift
// import Darwin
// import Foundation
//
// /// Writes whole lines to stdout with raw `write(2)` (no buffering, no ObjC exceptions).
// /// If the reader (the Tauri core) goes away, EPIPE ends the sidecar cleanly.
// public enum StdoutWriter {
//     public static func ignoreSIGPIPE() { signal(SIGPIPE, SIG_IGN) }
//
//     public static func write(_ data: Data) {
//         data.withUnsafeBytes { (buf: UnsafeRawBufferPointer) in
//             guard var p = buf.baseAddress else { return }
//             var left = buf.count
//             while left > 0 {
//                 let n = Darwin.write(STDOUT_FILENO, p, left)
//                 if n < 0 {
//                     if errno == EINTR { continue }
//                     exit(errno == EPIPE ? 0 : ExitCode.software)
//                 }
//                 p += n
//                 left -= n
//             }
//         }
//     }
//
//     public static func stderr(_ s: String) {
//         FileHandle.standardError.write(Data((s.hasSuffix("\n") ? s : s + "\n").utf8))
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Pacing.swift`

```swift
// import Foundation
//
// /// Leading-edge throttle with a single trailing emission: the first event in a window is emitted
// /// immediately; later events in the window collapse into one emission at the window's end.
// public struct Throttle: Sendable, Equatable {
//     public enum Decision: Sendable, Equatable {
//         case emitNow
//         /// Caller schedules a timer for `at` and calls `fireTrailing(now:)` then.
//         case scheduleTrailing(at: TimeInterval)
//         /// A trailing emission is already scheduled; caller just updates the pending payload.
//         case coalesced
//     }
//
//     public let minInterval: TimeInterval
//     public private(set) var lastEmit: TimeInterval?
//     public private(set) var trailingPending = false
//
//     public init(minInterval: TimeInterval) { self.minInterval = minInterval }
//
//     public mutating func offer(now: TimeInterval) -> Decision {
//         if trailingPending { return .coalesced }
//         if let last = lastEmit, now - last < minInterval {
//             trailingPending = true
//             return .scheduleTrailing(at: last + minInterval)
//         }
//         lastEmit = now
//         return .emitNow
//     }
//
//     public mutating func fireTrailing(now: TimeInterval) {
//         trailingPending = false
//         lastEmit = now
//     }
// }
//
// /// Idle state machine over `CGEventSourceSecondsSinceLastEventType` samples.
// public struct IdleDetector: Sendable, Equatable {
//     public enum Transition: Sendable, Equatable { case becameIdle, becameActive }
//
//     public let threshold: TimeInterval
//     public private(set) var isIdle = false
//
//     public init(threshold: TimeInterval = 120) { self.threshold = threshold }
//
//     public mutating func update(secondsSinceInput: TimeInterval) -> Transition? {
//         if !isIdle, secondsSinceInput >= threshold {
//             isIdle = true
//             return .becameIdle
//         }
//         if isIdle, secondsSinceInput < threshold {
//             isIdle = false
//             return .becameActive
//         }
//         return nil
//     }
// }
//
// /// Exponential backoff per key for unresponsive apps (`kAXErrorCannotComplete`).
// public struct Backoff: Sendable, Equatable {
//     public let base: TimeInterval
//     public let cap: TimeInterval
//     private var failures: [Int32: (count: Int, retryAt: TimeInterval)] = [:]
//
//     public init(base: TimeInterval = 0.5, cap: TimeInterval = 30) {
//         self.base = base
//         self.cap = cap
//     }
//
//     public static func == (l: Backoff, r: Backoff) -> Bool {
//         l.base == r.base && l.cap == r.cap && l.failures.mapValues(\.count) == r.failures.mapValues(\.count)
//     }
//
//     public func delay(forFailureCount n: Int) -> TimeInterval {
//         guard n > 0 else { return 0 }
//         return min(cap, base * pow(2, Double(n - 1)))
//     }
//
//     /// Records a failure; returns the delay before the next attempt is allowed.
//     @discardableResult
//     public mutating func recordFailure(_ key: Int32, now: TimeInterval) -> TimeInterval {
//         let n = (failures[key]?.count ?? 0) + 1
//         let d = delay(forFailureCount: n)
//         failures[key] = (n, now + d)
//         return d
//     }
//
//     public mutating func recordSuccess(_ key: Int32) { failures[key] = nil }
//
//     public func canAttempt(_ key: Int32, now: TimeInterval) -> Bool {
//         guard let f = failures[key] else { return true }
//         return now >= f.retryAt
//     }
//
//     public func failureCount(_ key: Int32) -> Int { failures[key]?.count ?? 0 }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/GenericReader.swift`

```swift
// import CoreGraphics
// import Foundation
//
// /// Tier 2 of plan §10.7: the structured generic reader. Interprets a captured AX tree by element
// /// ROLE (never by app-specific selectors) into `screen_doc` blocks, in document (reading) order:
// ///
// /// * `AXHeading` → heading; `AXStaticText` / `AXLink` runs → paragraph (a run breaks at a new line).
// /// * `AXTable` / `AXGrid` / `AXOutline` (+ `AXRow` / cells) → table (header + rows).
// /// * label → value → kv: `AXTitleUIElement` / `AXTitle` / `AXDescription` of a field, a label text
// ///   followed by a field, `<dl>` term/definition, or a short label and value on one row.
// /// * `AXList` → list, unless its items look like chat (then messages).
// /// * repeating sender / text / time groups → message; left/right alignment → incoming/outgoing.
// /// * the focused editable element → `field` + `focused_field`, ONLY in draft mode; otherwise its
// ///   content is never read. Secure fields never reach here (dropped by `ReaderCapture`).
// /// * Browsers: only content inside the page (`AXWebArea`) is read, never browser chrome.
// public struct GenericReader {
//     public let draft: Bool
//     public let browser: Bool
//
//     public init(draft: Bool, browser: Bool) {
//         self.draft = draft
//         self.browser = browser
//     }
//
//     public struct Output {
//         public var blocks: [ScreenBlock]
//         public var focused: FocusedField?
//     }
//
//     public func read(_ root: RNode) -> Output {
//         let b = Builder(draft: draft, browser: browser)
//         b.node(root, parent: [], inWeb: false)
//         return Output(blocks: b.blocks, focused: b.focused)
//     }
// }
//
// enum Roles {
//     /// Controls and chrome: never content.
//     static let skip: Set<String> = [
//         "AXButton", "AXMenuButton", "AXToolbar", "AXMenuBar", "AXMenuBarItem", "AXMenu", "AXMenuItem",
//         "AXScrollBar", "AXImage", "AXSlider", "AXIncrementor", "AXCheckBox", "AXRadioButton",
//         "AXDisclosureTriangle", "AXSplitter", "AXGrowArea", "AXBusyIndicator", "AXProgressIndicator",
//         "AXValueIndicator", "AXLevelIndicator", "AXRelevanceIndicator", "AXRuler", "AXRulerMarker",
//         "AXHandle", "AXColorWell", "AXDockItem",
//     ]
//     static let editable: Set<String> = ["AXTextField", "AXTextArea", "AXComboBox", "AXSearchField"]
//     /// Controls whose shown value is content (a `<select>` / pop-up's current choice, dates).
//     static let valueControls: Set<String> = ["AXPopUpButton", "AXDateField", "AXTimeField"]
//     static let inline: Set<String> = ["AXStaticText", "AXLink"]
//     static let tables: Set<String> = ["AXTable", "AXGrid", "AXOutline"]
//     static let lists: Set<String> = ["AXList", "AXListBox"]
// }
//
// extension RNode {
//     var isEditable: Bool { Roles.editable.contains(role) || attrs.subrole == "AXSearchField" }
//     var isField: Bool { isEditable || Roles.valueControls.contains(role) }
//     var isFocusedEditable: Bool { isEditable && attrs.focused }
// }
//
// enum ReaderText {
//     static func collapse(_ s: String) -> String {
//         s.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
//     }
//
//     static func clean(_ s: String?) -> String? {
//         guard let s else { return nil }
//         let t = collapse(s)
//         return t.isEmpty ? nil : t
//     }
//
//     /// Joins inline text pieces: no space before punctuation or where a piece already had one.
//     static func join(_ parts: [String]) -> String {
//         var out = ""
//         for p in parts where !p.isEmpty {
//             if out.isEmpty {
//                 out = p
//             } else {
//                 let glue = ".,;:!?)]}%".contains(p.first!) ? "" : " "
//                 out += glue + p
//             }
//         }
//         return out
//     }
//
//     static func stripColon(_ s: String) -> String {
//         var t = s
//         while let l = t.last, l == ":" || l == "：" || l.isWhitespace { t.removeLast() }
//         return t
//     }
//
//     static func key(_ s: String) -> String { stripColon(s).lowercased() }
//
//     static func words(_ s: String) -> Int { s.split(separator: " ").count }
//
//     /// Short, single-line, not a sentence.
//     static func isLabelish(_ s: String) -> Bool {
//         !s.isEmpty && s.count <= 40 && words(s) <= 6 && !s.contains("\n") && !".!?".contains(s.last!)
//     }
//
//     static func isNameLike(_ s: String) -> Bool {
//         guard isLabelish(s), words(s) <= 5, !isTimeLabel(s), let f = s.first else { return false }
//         return f.isLetter || "+~@".contains(f)
//     }
//
//     // Clock times ("10:42", "10:42 AM", "9 pm"), optionally after a day ("Yesterday 10:42",
//     // "12/09/2026, 10:42"), compact relative stamps ("5m", "2h ago", "just now"), read ticks.
//     private static let timeRE = try! NSRegularExpression(
//         pattern: #"^(?:(?:today|yesterday|mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+|\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?,?\s+)?(?:\d{1,2}:\d{2}(?:\s?[ap]\.?m\.?)?|\d{1,2}(?:\.\d{2})?\s?[ap]\.?m\.?|just now|now|\d{1,2}\s?(?:m|min|mins|h|hr|hrs|d)(?:\s+ago)?)\s*[✓✔]*$"#,
//         options: [.caseInsensitive])
//
//     static func isTimeLabel(_ s: String) -> Bool {
//         guard s.count <= 32 else { return false }
//         return timeRE.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil
//     }
// }
//
// private final class Builder {
//     let draft: Bool
//     let browser: Bool
//     var blocks: [ScreenBlock] = []
//     var focused: FocusedField?
//     private var textCache: [ObjectIdentifier: String] = [:]
//
//     init(draft: Bool, browser: Bool) {
//         self.draft = draft
//         self.browser = browser
//     }
//
//     // MARK: text
//
//     /// Visible text of a subtree: children's text when present, else the element's own text.
//     /// A focused editable element contributes nothing (its value is draft-only, via `field`).
//     func text(_ n: RNode) -> String {
//         if let t = textCache[ObjectIdentifier(n)] { return t }
//         var t = ""
//         if !Roles.skip.contains(n.role) && !n.isFocusedEditable {
//             let parts = n.children.map(text).filter { !$0.isEmpty }
//             t = parts.isEmpty ? (ReaderText.clean(n.attrs.value) ?? ReaderText.clean(n.attrs.title)
//                                  ?? ReaderText.clean(n.attrs.description) ?? "") : ReaderText.join(parts)
//         }
//         textCache[ObjectIdentifier(n)] = t
//         return t
//     }
//
//     /// Raw (un-collapsed) text of the last leaf — used to tell text flow ("Hello ") from labels.
//     func rawTail(_ n: RNode) -> String {
//         if let last = n.children.last { return rawTail(last) }
//         return n.attrs.value ?? n.attrs.title ?? ""
//     }
//
//     static func short(_ role: String) -> String { role.hasPrefix("AX") ? String(role.dropFirst(2)) : role }
//
//     /// Structural path (roles, no indices) so a fingerprint survives content inserted above it.
//     static func pathString(_ p: [String]) -> String { p.suffix(8).joined(separator: "/") }
//
//     func add(_ role: ScreenBlock.Role, _ path: [String], text: String? = nil, label: String? = nil, value: String? = nil) {
//         blocks.append(ScreenBlock(role: role, path: Self.pathString(path), text: text, label: label, value: value))
//     }
//
//     // MARK: walk
//
//     func node(_ n: RNode, parent: [String], inWeb: Bool) {
//         let role = n.role
//         if Roles.skip.contains(role) { return }
//         let path = parent + [Self.short(role)]
//         let web = inWeb || role == "AXWebArea"
//         if browser && !web {
//             container(n, path, web: false)  // browser chrome: only look for the page
//             return
//         }
//         if n.isField {
//             field(n, label: fieldLabel(n), path)
//             return
//         }
//         switch role {
//         case "AXHeading":
//             let t = text(n)
//             if !t.isEmpty { add(.heading, path, text: t) }
//         case _ where Roles.tables.contains(role):
//             if let t = table(n, path) { blocks.append(t) } else { container(n, path, web: web) }
//         case "AXList" where n.attrs.subrole == "AXDescriptionList":
//             let kvs = descriptionList(n, path)
//             if kvs.isEmpty { list(n, path) } else { blocks.append(contentsOf: kvs) }
//         case _ where Roles.lists.contains(role):
//             if let m = messages(n, path) { blocks.append(contentsOf: m) } else { list(n, path) }
//         case _ where Roles.inline.contains(role):
//             let t = text(n)
//             if !t.isEmpty { add(.paragraph, path, text: t) }
//         default:
//             container(n, path, web: web)
//         }
//     }
//
//     func container(_ n: RNode, _ path: [String], web: Bool) {
//         let emitting = !browser || web
//         let kids = n.children
//         if emitting {
//             if let m = messages(n, path) { blocks.append(contentsOf: m); return }
//             if let kv = labelValuePairs(n, path) { blocks.append(contentsOf: kv); return }
//         }
//         var run: [RNode] = []
//         func flush() {
//             let t = ReaderText.join(run.map(text))
//             if !t.isEmpty { add(.paragraph, path + ["Text"], text: t) }
//             run = []
//         }
//         var i = 0
//         while i < kids.count {
//             let k = kids[i]
//             guard emitting, Roles.inline.contains(k.role) else {
//                 flush()
//                 node(k, parent: path, inWeb: web)
//                 i += 1
//                 continue
//             }
//             // A label text directly before a field: it labels that field (or duplicates its own label).
//             if k.role == "AXStaticText", i + 1 < kids.count, kids[i + 1].isField {
//                 let lt = text(k)
//                 let f = kids[i + 1]
//                 let own = fieldLabel(f)
//                 if !lt.isEmpty, lt.count <= 60, own == nil || ReaderText.key(own!) == ReaderText.key(lt) {
//                     flush()
//                     field(f, label: own ?? ReaderText.stripColon(lt), path + [Self.short(f.role)])
//                     i += 2
//                     continue
//                 }
//             }
//             if let last = run.last, startsNewLine(k, after: last) { flush() }
//             run.append(k)
//             i += 1
//         }
//         flush()
//     }
//
//     func startsNewLine(_ k: RNode, after prev: RNode) -> Bool {
//         guard let a = prev.frame, let b = k.frame else { return false }
//         return b.minY >= a.maxY - 1
//     }
//
//     // MARK: fields
//
//     func fieldLabel(_ f: RNode) -> String? {
//         let a = f.attrs
//         var l = ReaderText.clean(a.titleUIText)
//         if l == nil, f.isEditable { l = ReaderText.clean(a.title) }
//         if l == nil { l = ReaderText.clean(a.description) }
//         // Pop-ups: AXTitle is usually the current choice, a label only when AXValue carries the choice.
//         if l == nil, !f.isEditable, let v = ReaderText.clean(a.value), let t = ReaderText.clean(a.title), t != v { l = t }
//         return l.map(ReaderText.stripColon).flatMap { $0.isEmpty ? nil : $0 }
//     }
//
//     func fieldValue(_ f: RNode) -> String? {
//         if f.isEditable {
//             if let v = f.attrs.value, !v.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return v }
//             let t = ReaderText.join(f.children.map(text))
//             return t.isEmpty ? nil : t
//         }
//         return ReaderText.clean(f.attrs.value) ?? ReaderText.clean(f.attrs.title)
//     }
//
//     func field(_ f: RNode, label: String?, _ path: [String]) {
//         if f.isFocusedEditable {
//             guard draft else { return }  // the composer / focused input is Draft-assist-only
//             let v = fieldValue(f).map { $0.trimmingCharacters(in: .whitespacesAndNewlines) } ?? ""
//             let l = label ?? ReaderText.clean(f.attrs.placeholder)
//             focused = FocusedField(label: l, value: v, role: f.role)
//             if !v.isEmpty { add(.field, path, label: l, value: v) }
//             return
//         }
//         guard let raw = fieldValue(f) else { return }
//         if f.role == "AXTextArea" && label == nil {
//             // Unlabelled, unfocused text area = document body: one paragraph per blank-line block.
//             for para in raw.components(separatedBy: "\n\n") {
//                 if let t = ReaderText.clean(para) { add(.paragraph, path, text: t) }
//             }
//             return
//         }
//         guard let label, let v = ReaderText.clean(raw) else { return }
//         add(.kv, path, label: label, value: v)
//     }
//
//     // MARK: label → value
//
//     func descriptionList(_ n: RNode, _ path: [String]) -> [ScreenBlock] {
//         var out: [ScreenBlock] = []
//         let kids = n.children
//         var i = 0
//         while i < kids.count {
//             if kids[i].attrs.subrole == "AXTerm", i + 1 < kids.count, kids[i + 1].attrs.subrole != "AXTerm" {
//                 let l = ReaderText.stripColon(text(kids[i]))
//                 let v = text(kids[i + 1])
//                 if !l.isEmpty, !v.isEmpty {
//                     out.append(ScreenBlock(role: .kv, path: Self.pathString(path + ["Pair"]), label: l, value: v))
//                 }
//                 i += 2
//             } else {
//                 i += 1
//             }
//         }
//         return out
//     }
//
//     /// Children that are all short label / value text pairs ("Owner  Priya Shah", "Stage:", …).
//     func labelValuePairs(_ n: RNode, _ path: [String]) -> [ScreenBlock]? {
//         let kids = n.children.filter { !text($0).isEmpty }
//         guard kids.count >= 2, kids.count % 2 == 0, kids.count <= 40 else { return nil }
//         for k in kids {
//             var budget = 8
//             guard isSimple(k, &budget) else { return nil }
//         }
//         var out: [ScreenBlock] = []
//         for i in stride(from: 0, to: kids.count, by: 2) {
//             let l = kids[i]
//             let v = kids[i + 1]
//             let lt = text(l)
//             let vt = text(v)
//             guard ReaderText.isLabelish(lt) || (lt.hasSuffix(":") && lt.count <= 40), !ReaderText.isTimeLabel(lt),
//                   vt.count <= 500 else { return nil }
//             let colon = lt.hasSuffix(":") || lt.hasSuffix("：")
//             if !colon && (rawTail(l).last?.isWhitespace ?? false) { return nil }  // text flow, not a label
//             let row = sameRow(l, v)
//             let stacked = kids.count == 2 && isStacked(l, v) && vt.count <= 120 && !vt.contains("\n")
//             guard colon || row || stacked else { return nil }
//             out.append(ScreenBlock(role: .kv, path: Self.pathString(path + ["Pair"]),
//                                    label: ReaderText.stripColon(lt), value: vt))
//         }
//         return out
//     }
//
//     func isSimple(_ n: RNode, _ budget: inout Int) -> Bool {
//         budget -= 1
//         if budget < 0 || n.isField || n.role == "AXHeading" || Roles.tables.contains(n.role) || Roles.lists.contains(n.role) {
//             return false
//         }
//         for c in n.children where !isSimple(c, &budget) { return false }
//         return true
//     }
//
//     func sameRow(_ l: RNode, _ v: RNode) -> Bool {
//         guard let a = l.frame, let b = v.frame else { return false }
//         return abs(a.midY - b.midY) <= max(4, 0.5 * min(a.height, b.height)) && b.minX - a.maxX >= 8
//     }
//
//     func isStacked(_ l: RNode, _ v: RNode) -> Bool {
//         guard let a = l.frame, let b = v.frame else { return false }
//         return b.minY >= a.maxY - 2 && b.minY - a.maxY <= max(12, a.height) && abs(a.minX - b.minX) <= 8
//     }
//
//     // MARK: lists and tables
//
//     func list(_ n: RNode, _ path: [String]) {
//         let items = n.children.map(text).filter { !$0.isEmpty }
//         guard !items.isEmpty else { return }
//         blocks.append(ScreenBlock(role: .list, path: Self.pathString(path), items: items))
//     }
//
//     func table(_ n: RNode, _ path: [String]) -> ScreenBlock? {
//         var rows: [RNode] = []
//         var columns: [RNode] = []
//         func scan(_ x: RNode, _ depth: Int) {
//             for c in x.children {
//                 switch c.role {
//                 case "AXRow": rows.append(c)
//                 case "AXColumn": columns.append(c)  // columns repeat the cells: header titles only
//                 case "AXGroup" where depth < 3: scan(c, depth + 1)
//                 default: break
//                 }
//             }
//         }
//         scan(n, 0)
//         func cells(_ r: RNode) -> [String] {
//             let kids = r.children.filter { !Roles.skip.contains($0.role) }
//             let c = kids.isEmpty ? [text(r)] : kids.map { String(text($0).prefix(500)) }
//             return Array(c.prefix(50))
//         }
//         var all = rows.map(cells)
//         var header: [String] = []
//         let titles = columns.map { ReaderText.clean($0.attrs.title) ?? ReaderText.clean($0.attrs.description) ?? "" }
//         if !titles.isEmpty, titles.allSatisfy({ !$0.isEmpty }) {
//             header = titles
//         } else if let first = rows.first,
//                   first.children.contains(where: { ($0.attrs.subrole ?? $0.role).contains("Header") }) || n.role != "AXOutline" && all.count >= 2 {
//             // Header row: cells marked as headers, else (tables/grids only, not outlines) the first row.
//             header = all.removeFirst()
//         }
//         let body = all.filter { $0.contains { !$0.isEmpty } }
//         guard header.contains(where: { !$0.isEmpty }) || !body.isEmpty else { return nil }
//         return ScreenBlock(role: .table, path: Self.pathString(path), header: header, rows: body)
//     }
//
//     // MARK: chat
//
//     struct Unit {
//         let text: String
//         let frame: CGRect?
//     }
//
//     /// Text units of one repeated child: single-child wrappers are unwrapped first.
//     func units(_ k: RNode) -> (units: [Unit], frame: CGRect?) {
//         var u = k
//         while u.children.count == 1, !Roles.inline.contains(u.role) { u = u.children[0] }
//         if u.children.isEmpty || Roles.inline.contains(u.role) {
//             let t = text(u)
//             return (t.isEmpty ? [] : [Unit(text: t, frame: u.frame)], u.frame ?? k.frame)
//         }
//         let list = u.children.compactMap { c -> Unit? in
//             let t = text(c)
//             return t.isEmpty ? nil : Unit(text: t, frame: c.frame)
//         }
//         return (list, u.frame ?? k.frame)
//     }
//
//     func hasStructure(_ n: RNode) -> Bool {
//         n.isField || n.role == "AXHeading" || Roles.tables.contains(n.role) || n.children.contains(where: hasStructure)
//     }
//
//     /// Repeating sender / text / time groups → messages. Needs ≥ 2 groups carrying a time stamp,
//     /// in at least half of the groups, and ≥ 80 % of the text-bearing children shaped like a message.
//     func messages(_ n: RNode, _ path: [String]) -> [ScreenBlock]? {
//         let kids = n.children.map { ($0, units($0)) }.filter { !$0.1.units.isEmpty }
//         guard kids.count >= 2 else { return nil }
//         let cands = kids.filter { (1...6).contains($0.1.units.count) && !hasStructure($0.0) }
//         guard cands.count * 10 >= kids.count * 8 else { return nil }
//         let timed = cands.filter { $0.1.units.contains { ReaderText.isTimeLabel($0.text) } }
//         guard timed.count >= 2, timed.count * 2 >= cands.count else { return nil }
//
//         let box = n.frame
//         var out: [ScreenBlock] = []
//         for (_, u) in cands {
//             let time = u.units.last { ReaderText.isTimeLabel($0.text) }
//             var others = u.units.filter { !ReaderText.isTimeLabel($0.text) }
//             guard !others.isEmpty else { continue }
//             let frames = u.units.compactMap(\.frame)
//             let bubble = frames.count == u.units.count ? frames.dropFirst().reduce(frames[0]) { $0.union($1) } : u.frame
//             let outgoing = direction(bubble, in: box)
//             // Day separators ("Today", "Monday"): one short centred unit without a time.
//             if time == nil, others.count == 1, outgoing == nil, others[0].text.count <= 24 { continue }
//             var sender: String?
//             if outgoing != true, others.count >= 2, ReaderText.isNameLike(others[0].text) {
//                 sender = others.removeFirst().text
//             }
//             var b = ScreenBlock(role: .message, path: Self.pathString(path + ["Message"]))
//             b.sender = sender
//             b.ts = nil  // no date context: ISO or nothing (§3.7)
//             b.tsLabel = time?.text
//             b.text = others.map(\.text).joined(separator: "\n")
//             b.isOutgoing = outgoing
//             out.append(b)
//         }
//         return out.isEmpty ? nil : out
//     }
//
//     /// true = right-aligned (mine), false = left-aligned (theirs), nil = full width / unknown.
//     func direction(_ f: CGRect?, in box: CGRect?) -> Bool? {
//         guard let f, let c = box, f.width > 0, c.width > 0 else { return nil }
//         let left = f.minX - c.minX
//         let right = c.maxX - f.maxX
//         if left - right > 0.1 * c.width { return true }
//         if right - left > 0.1 * c.width { return false }
//         return nil
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/GmailReader.swift`

```swift
// import Foundation
//
// /// Dedicated reader for Gmail on the web (`mail.google.com`).
// ///
// /// A mail thread IS a conversation — the brain already treats it as one: `mail.google.com` is in
// /// `followups.py`'s CHAT_HOSTS so that mail is judged per thread, and `capture/session.rs` lists
// /// it in `FRAGMENT_ROUTED_HOSTS` because Gmail routes the open thread in the URL FRAGMENT
// /// (`#inbox/FMfcgz…`), not the path. Without that, every mail a manager opens shares one key and
// /// the per-thread work/personal verdict, "Mute chat" and the topic cap all land on the whole
// /// mailbox instead of the mail.
// ///
// /// So the key comes off the fragment and nothing is read without one. `#inbox` alone is the INBOX
// /// LIST — a screen of other people's subject lines, not a conversation — and reading it would
// /// turn one mailbox view into a fake thread. Returning nil there hands it to the generic reader,
// /// which is what should describe a list.
// ///
// /// NOT MEASURED YET on a real tree (no Accessibility recording of Gmail on this machine). The
// /// structure it relies on is `ThreadScan`'s two invariants, so a redesign costs a sender name at
// /// worst; `scripts/check-readers.sh` fails if this surface ends up served by the generic reader.
// public struct GmailReader: DedicatedReader {
//     public let id = "gmail"
//     public init() {}
//
//     static let hosts: Set<String> = ["mail.google.com", "inbox.google.com"]
//     /// Gmail's own thread ids: a long opaque run, `FMfcgz…` / `thread-f:…`.
//     static let minThreadID = 8
//     /// Fragment segments that are a MAILBOX, never a thread.
//     static let mailboxes: Set<String> = [
//         "inbox", "starred", "snoozed", "sent", "drafts", "all", "spam", "trash", "important",
//         "chats", "scheduled", "imp", "category", "search", "label", "settings", "advanced-search",
//     ]
//
//     public func accepts(_ ctx: ReadContext) -> Bool {
//         guard let h = ThreadScan.host(ctx.url) else { return false }
//         return Self.hosts.contains(h)
//     }
//
//     public func read(_ root: RNode, _ ctx: ReadContext) -> (any ReaderLine)? {
//         ThreadScan.read(root, ctx, app: id, threadKey: Self.threadKey(ctx.url),
//                         // Gmail puts the sender on a link ("Priya Shah <priya@acme.com>") in the
//                         // message header, and on static text in the compact view.
//                         senderRoles: ["AXLink", "AXStaticText", "AXButton", "AXHeading"])
//     }
//
//     /// `gm:thread:<id>` from `#inbox/FMfcgz…`, or nil for a mailbox view.
//     ///
//     /// The LAST fragment segment is the thread; the ones before it are the mailbox and any label
//     /// path (`#label/Clients/FMfcgz…`, `#search/priya/FMfcgz…`). A segment that is itself a known
//     /// mailbox name is never a thread, which is what keeps `#inbox` and `#category/updates` out.
//     static func threadKey(_ url: String?) -> String? {
//         guard let f = ThreadScan.fragment(url) else { return nil }
//         let parts = f.split(separator: "/").map(String.init).filter { !$0.isEmpty }
//         guard let last = parts.last else { return nil }
//         let lower = last.lowercased()
//         guard !mailboxes.contains(lower), last.count >= minThreadID else { return nil }
//         // A thread id is one opaque token. A search phrase ("priya+pricing") is not.
//         guard !last.contains("+"), !last.contains("%20"), !last.contains(" ") else { return nil }
//         return "gm:thread:" + last
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/LinkedInReader.swift`

```swift
// import Foundation
//
// /// Dedicated reader for LinkedIn messaging (`linkedin.com/messaging/thread/<id>`).
// ///
// /// The thread key is `li:conv:<id>`, which is NOT a choice made here — it is the format the rest
// /// of the system already expects. `tests/fixtures/thread_reads/linkedin_priya.json` carries
// /// `"thread_key": "li:conv:abc"` for `/messaging/thread/abc/`, and `capture/thread_source.rs`
// /// asserts it. A reader that emitted anything else would split one conversation in two: the
// /// fixture's history under one key and everything read live under another.
// ///
// /// The conversation is in the PATH, so nothing is scraped off the screen for the key — the defect
// /// `capture/session.rs` documents for `web.whatsapp.com`, where one URL serves every chat, does
// /// not arise here.
// ///
// /// LinkedIn is where cold outreach arrives, and a measured card-quality defect is still open
// /// (cold outreach being read as an `ask` the manager owes an answer to). That is judged on the
// /// server in `reason/moments/screen_insight.py`, not here — this reader's job is to report what
// /// is on screen, including the messages a human would ignore.
// ///
// /// NOT MEASURED YET against a live tree; the fixture above is an expected OUTPUT, not a recorded
// /// AX tree.
// public struct LinkedInReader: DedicatedReader {
//     public let id = "linkedin"
//     public init() {}
//
//     public func accepts(_ ctx: ReadContext) -> Bool {
//         guard let h = ThreadScan.host(ctx.url) else { return false }
//         return h == "linkedin.com" || h.hasSuffix(".linkedin.com")
//     }
//
//     public func read(_ root: RNode, _ ctx: ReadContext) -> (any ReaderLine)? {
//         ThreadScan.read(root, ctx, app: id, threadKey: Self.threadKey(ctx.url),
//                         senderRoles: ["AXLink", "AXHeading", "AXStaticText", "AXButton"])
//     }
//
//     /// `li:conv:<id>` from `/messaging/thread/<id>/`, matching the fixture exactly.
//     ///
//     /// `/messaging` alone is the conversation LIST and is refused: reading it would fold every
//     /// correspondent into one thread.
//     static func threadKey(_ url: String?) -> String? {
//         guard let id = ThreadScan.segment(url, after: "thread"), id.count >= 2 else { return nil }
//         return "li:conv:" + id
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/OutlookReader.swift`

```swift
// import Foundation
//
// /// Dedicated reader for Outlook — the web client (`outlook.office.com`, `outlook.live.com`) and the
// /// Mac app, which is the same Chromium tree in the "New Outlook" and an AppKit tree in the old one.
// ///
// /// Outlook routes the open mail in the PATH (`/mail/id/AAQk…`, `/mail/inbox/id/AAQk…`), so unlike
// /// Gmail the key needs nothing off the screen and nothing from the fragment. A mailbox view
// /// (`/mail/inbox`) carries no `id` segment and is refused, the same way Gmail's `#inbox` is: a
// /// list of other people's subject lines is not a conversation.
// ///
// /// NOT MEASURED YET on a real tree. It rests on `ThreadScan`'s invariants rather than a recorded
// /// layout; the old AppKit Outlook puts its messages in an `AXTable`, which is why the list roles
// /// stay wide.
// public struct OutlookReader: DedicatedReader {
//     public let id = "outlook"
//     public init() {}
//
//     static let bundles: Set<String> = [
//         "com.microsoft.outlook", "com.microsoft.office.outlook", "outlook.exe",
//     ]
//     static let hostSuffixes = ["outlook.office.com", "outlook.office365.com", "outlook.live.com",
//                                "outlook.com"]
//
//     public func accepts(_ ctx: ReadContext) -> Bool {
//         if let b = ctx.bundleID, Self.bundles.contains(b.lowercased()) { return true }
//         guard let h = ThreadScan.host(ctx.url) else { return false }
//         return Self.hostSuffixes.contains(where: { h == $0 || h.hasSuffix("." + $0) })
//     }
//
//     public func read(_ root: RNode, _ ctx: ReadContext) -> (any ReaderLine)? {
//         ThreadScan.read(root, ctx, app: id, threadKey: Self.threadKey(ctx),
//                         senderRoles: ["AXLink", "AXStaticText", "AXButton", "AXHeading"])
//     }
//
//     /// `ol:mail:<id>` from the `id` path segment.
//     ///
//     /// The desktop app has no URL at all. Rather than invent a key — which would put every mail
//     /// the app shows under one thread, the exact defect `FRAGMENT_ROUTED_HOSTS` exists to stop —
//     /// it is refused, and the generic reader describes the screen instead. Keying the desktop app
//     /// needs a measured tree to find a stable per-mail identifier, and that is owed, not guessed.
//     static func threadKey(_ ctx: ReadContext) -> String? {
//         guard let id = ThreadScan.segment(ctx.url, after: "id"), id.count >= 8 else { return nil }
//         return "ol:mail:" + id
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/ReaderCapture.swift`

```swift
// import CoreGraphics
// import Foundation
//
// /// One captured element for the reader (plan §10.7). Secure fields and offscreen subtrees never
// /// become `RNode`s, so nothing downstream can read them.
// public final class RNode {
//     public let attrs: NodeAttributes
//     public internal(set) var children: [RNode]
//     public let depth: Int
//
//     public init(_ attrs: NodeAttributes, depth: Int = 0, children: [RNode] = []) {
//         self.attrs = attrs
//         self.depth = depth
//         self.children = children
//     }
//
//     public var role: String { attrs.role ?? "" }
//     /// Frame with a real size (AX reports zero frames for many invisible wrappers).
//     var frame: CGRect? { attrs.frame.flatMap { $0.width > 0 && $0.height > 0 ? $0 : nil } }
//
//     /// URL of the first `AXWebArea` (breadth-first), tracking params stripped.
//     public func firstWebAreaURL(maxNodes: Int = 2000) -> String? {
//         var queue: [RNode] = [self]
//         var head = 0
//         while head < queue.count, head < maxNodes {
//             let n = queue[head]
//             head += 1
//             if n.role == "AXWebArea", let u = n.attrs.url, u.hasPrefix("http") { return URLNormalizer.stripTracking(u) }
//             queue.append(contentsOf: n.children)
//         }
//         return nil
//     }
// }
//
// public struct CaptureResult {
//     public var root: RNode?
//     public var stats: WalkStats
//
//     public init(root: RNode?, stats: WalkStats) {
//         self.root = root
//         self.stats = stats
//     }
// }
//
// /// Captures the visible AX tree for the reader under the same hard limits as `snapshot`
// /// (§10.6: depth ≤ 12, ≤ 5k nodes, 400 ms). Document order; child index paths are not kept.
// public struct ReaderCapture<Source: TreeSource> {
//     public let source: Source
//     public let limits: WalkLimits
//     /// Content outside this rect (normally the window frame) is not read. Nil ⇒ the root's frame.
//     public let visibleRect: CGRect?
//     private let now: () -> UInt64
//
//     public init(source: Source, limits: WalkLimits = ReadOptions.defaultLimits, visibleRect: CGRect? = nil,
//                 now: @escaping () -> UInt64 = { DispatchTime.now().uptimeNanoseconds }) {
//         self.source = source
//         self.limits = limits
//         self.visibleRect = visibleRect
//         self.now = now
//     }
//
//     public func capture(_ root: Source.Element) -> CaptureResult {
//         var st = State(start: now(), visible: visibleRect.flatMap { $0.width > 0 && $0.height > 0 ? $0 : nil })
//         var node: RNode?
//         if case .node(let n) = visit(root, depth: 0, state: &st) { node = n }
//         st.stats.elapsedMs = Double(now() &- st.start) / 1_000_000
//         st.stats.truncatedBy = ["depth", "nodes", "deadline"].filter { st.truncatedBy.contains($0) }
//         return CaptureResult(root: node, stats: st.stats)
//     }
//
//     private struct State {
//         let start: UInt64
//         var visible: CGRect?
//         var stats = WalkStats()
//         var truncatedBy = Set<String>()
//     }
//
//     private enum Visit {
//         case node(RNode)
//         /// Read but not kept (secure field, offscreen): siblings continue.
//         case skipped
//         /// A limit was hit: stop reading siblings.
//         case stop
//     }
//
//     private func visit(_ element: Source.Element, depth: Int, state: inout State) -> Visit {
//         if state.stats.nodes >= limits.maxNodes {
//             state.truncatedBy.insert("nodes")
//             return .stop
//         }
//         if limits.deadlineMs > 0, now() &- state.start > UInt64(limits.deadlineMs) * 1_000_000 {
//             state.truncatedBy.insert("deadline")
//             return .stop
//         }
//         let remaining = limits.maxNodes - state.stats.nodes - 1
//         let read = source.read(element, childLimit: depth < limits.maxDepth ? max(0, remaining) : 0)
//         let index = state.stats.nodes
//         state.stats.nodes += 1
//         state.stats.depthReached = max(state.stats.depthReached, depth)
//         if let err = read.error {
//             state.stats.axErrors += 1
//             if err == .cannotComplete { state.stats.axCannotComplete += 1 }
//         }
//
//         var a = read.attributes
//         // Password fields: dropped whole — value, label, placeholder never leave this function.
//         if a.isSecure { return .skipped }
//         if let f = a.frame, f.width > 0, f.height > 0 {
//             if depth == 0, state.visible == nil { state.visible = f }
//             if depth > 0, let v = state.visible, !f.intersects(v) { return .skipped }
//         }
//         a.title = clamp(a.title)
//         a.description = clamp(a.description)
//         a.value = clamp(a.value)
//         a.placeholder = clamp(a.placeholder)
//         a.titleUIText = clamp(a.titleUIText)
//         countText(a, depth: depth, index: index, state: &state)
//
//         let node = RNode(a, depth: depth)
//         if read.totalChildren > 0 && depth >= limits.maxDepth {
//             state.truncatedBy.insert("depth")
//             return .node(node)
//         }
//         var kids: [RNode] = []
//         loop: for child in read.children {
//             switch visit(child, depth: depth + 1, state: &state) {
//             case .node(let c): kids.append(c)
//             case .skipped: continue
//             case .stop: break loop
//             }
//         }
//         if read.children.count < read.totalChildren { state.truncatedBy.insert("nodes") }
//         node.children = kids
//         return .node(node)
//     }
//
//     private func clamp(_ s: String?) -> String? {
//         guard let s, !s.isEmpty else { return nil }
//         return s.count > limits.maxTextLength ? String(s.prefix(limits.maxTextLength)) : s
//     }
//
//     private func countText(_ a: NodeAttributes, depth: Int, index: Int, state: inout State) {
//         let fields = [a.title, a.description, a.value].compactMap { $0 }
//         guard !fields.isEmpty else { return }
//         state.stats.textNodes += 1
//         state.stats.maxTextDepth = max(state.stats.maxTextDepth ?? 0, depth)
//         if fields.map({ TextNormalizer.normalize($0).count }).max() ?? 0 >= limits.longTextThreshold {
//             state.stats.longTextNodes += 1
//             if state.stats.firstLongTextDepth == nil {
//                 state.stats.firstLongTextDepth = depth
//                 state.stats.firstLongTextNodeIndex = index
//             }
//         }
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/ReaderEngine.swift`

```swift
// import Foundation
//
// /// What `read` knows about the surface besides the tree.
// public struct ReadContext: Sendable {
//     public var bundleID: String?
//     /// Page URL for browsers (AXWebArea `AXURL`, else the address bar). Nil ⇒ taken from the tree.
//     public var url: String?
//     public var windowTitle: String?
//     /// Draft assist on: the focused editable element may be read (`--draft`).
//     public var draft: Bool
//     public var now: Date
//
//     public init(bundleID: String?, url: String? = nil, windowTitle: String? = nil, draft: Bool = false, now: Date = Date()) {
//         self.bundleID = bundleID
//         self.url = url
//         self.windowTitle = windowTitle
//         self.draft = draft
//         self.now = now
//     }
//
//     public var isBrowser: Bool { AppCatalog.isBrowser(bundleID) }
// }
//
// /// Tier 1 of plan §10.7 — DISPATCH HOOK for dedicated readers (Gmail, WhatsApp, LinkedIn, Slack,
// /// Outlook, Google Calendar) emitting a §3.6 `thread_read`. WhatsApp (native) ships first; they are written from
// /// real trees recorded by `scripts/measure.sh` once Accessibility is granted. Add one by
// /// implementing this protocol and listing it in `ReaderRegistry.dedicated`; returning nil from
// /// `read` falls back to the generic reader.
// public protocol DedicatedReader: Sendable {
//     var id: String { get }
//     func accepts(_ ctx: ReadContext) -> Bool
//     func read(_ root: RNode, _ ctx: ReadContext) -> (any ReaderLine)?
// }
//
// public enum ReaderRegistry {
//     /// Consulted in order before the generic reader.
//     /// Order matters only where two could accept the same surface; today none overlap.
//     ///
//     /// `CalendarReader` is deliberately absent: a calendar is not a conversation, and
//     /// `capture/session.rs` already excludes `calendar.google.com` from the conversation
//     /// surfaces. Events belong in a `ScreenDoc`, which the generic reader already produces.
//     public static let dedicated: [any DedicatedReader] = [
//         WhatsAppReader(), SlackReader(), GmailReader(), OutlookReader(), TeamsReader(),
//         LinkedInReader(),
//     ]
// }
//
// public struct ReaderOutput {
//     /// `generic` or the dedicated reader's id.
//     public var reader: String
//     public var line: any ReaderLine
//
//     public var doc: ScreenDoc? { line as? ScreenDoc }
// }
//
// public enum ScreenReaderEngine {
//     public static func read(_ capture: CaptureResult, _ ctx: ReadContext,
//                             dedicated: [any DedicatedReader] = ReaderRegistry.dedicated) -> ReaderOutput {
//         if let root = capture.root {
//             for d in dedicated where d.accepts(ctx) {
//                 if let line = d.read(root, ctx) { return ReaderOutput(reader: d.id, line: line) }
//             }
//         }
//         return ReaderOutput(reader: "generic", line: genericDoc(capture, ctx))
//     }
//
//     public static func genericDoc(_ capture: CaptureResult, _ ctx: ReadContext) -> ScreenDoc {
//         let url = (ctx.url ?? capture.root?.firstWebAreaURL()).map(URLNormalizer.stripTracking)
//         let out = capture.root.map { GenericReader(draft: ctx.draft, browser: ctx.isBrowser).read($0) }
//         var (blocks, cappedBy) = ScreenDocRules.cap(out?.blocks ?? [])
//         for i in blocks.indices { blocks[i].fp = ScreenDocRules.fingerprint(blocks[i]) }
//         let focused = ctx.draft ? out?.focused : nil
//         var counts: [String: Int] = [:]
//         for b in blocks { counts[b.role.rawValue, default: 0] += 1 }
//         let title = ReaderText.clean(ctx.windowTitle)
//         return ScreenDoc(
//             ts: Timestamp.format(ctx.now), bundleID: ctx.bundleID, url: url,
//             threadKey: ScreenDocRules.threadKey(bundleID: ctx.bundleID, url: url, title: title),
//             title: title, blocks: blocks, focusedField: focused, treeHash: ScreenDocRules.treeHash(blocks),
//             stats: ReadStats(walk: capture.stats, blocks: blocks.count, chars: blocks.reduce(0) { $0 + $1.content.count },
//                              blockCounts: counts, cappedBy: cappedBy, axEmpty: blocks.isEmpty && focused == nil,
//                              reader: "generic"))
//     }
//
//     /// One NDJSON line (no trailing newline).
//     public static func encode(_ output: ReaderOutput, pretty: Bool = false, redact: Bool = false) throws -> Data {
//         let enc = JSONEncoder()
//         enc.outputFormatting = pretty ? [.sortedKeys, .prettyPrinted, .withoutEscapingSlashes] : [.sortedKeys, .withoutEscapingSlashes]
//         let line: any ReaderLine = redact ? output.line.redacted() : output.line
//         return try enc.encode(line)
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/ScreenDoc.swift`

```swift
// import CryptoKit
// import Foundation
//
// /// One reader output line (a generic `screen_doc`, or later a dedicated reader's `thread_read`).
// /// `redacted()` keeps roles/structure and replaces every captured string (for `--redact` / measure.sh).
// public protocol ReaderLine: Encodable {
//     func redacted() -> Self
// }
//
// /// One `screen_doc` block (P1 build §3.7). Flat on the wire: `role` + the fields that role uses.
// public struct ScreenBlock: Sendable, Equatable, Encodable {
//     public enum Role: String, Sendable, Encodable {
//         case heading, paragraph, kv, table, list, message, field
//     }
//
//     public var role: Role
//     /// Structural role path (e.g. `WebArea/Group/Pair`) — part of the fingerprint.
//     public var path: String
//     public var text: String?
//     public var label: String?
//     public var value: String?
//     public var header: [String]?
//     public var rows: [[String]]?
//     public var items: [String]?
//     public var sender: String?
//     /// Message time, ISO-8601 or nil — never a screen label (§3.7). The generic reader always sends nil.
//     public var ts: String?
//     /// Message time as shown on screen ("10:42 AM", "Yesterday") — the generic reader has no date context.
//     public var tsLabel: String?
//     public var isOutgoing: Bool?
//     /// Reader-side fingerprint (the core recomputes its own).
//     public var fp: String = ""
//
//     public init(role: Role, path: String, text: String? = nil, label: String? = nil, value: String? = nil,
//                 header: [String]? = nil, rows: [[String]]? = nil, items: [String]? = nil) {
//         self.role = role
//         self.path = path
//         self.text = text
//         self.label = label
//         self.value = value
//         self.header = header
//         self.rows = rows
//         self.items = items
//     }
//
//     /// The text this block stands for (hash, fingerprint, 30k-char cap). Mirrors the core's
//     /// `block_content` (src/capture/session.rs).
//     public var content: String {
//         switch role {
//         case .kv, .field: return "\(label ?? ""): \(value ?? "")"
//         case .table: return ([header ?? []] + (rows ?? [])).map { $0.joined(separator: "\t") }.joined(separator: "\n")
//         case .list: return (items ?? []).joined(separator: "\n")
//         case .message: return "\(sender ?? ""): \(text ?? "")"
//         case .heading, .paragraph: return text ?? ""
//         }
//     }
//
//     enum K: String, CodingKey {
//         case fp, role, path, text, label, value, header, rows, items, sender, ts
//         case tsLabel = "ts_label", isOutgoing = "is_outgoing"
//     }
//
//     public func encode(to encoder: any Encoder) throws {
//         var c = encoder.container(keyedBy: K.self)
//         if !fp.isEmpty { try c.encode(fp, forKey: .fp) }
//         try c.encode(role, forKey: .role)
//         try c.encode(path, forKey: .path)
//         switch role {
//         case .heading, .paragraph:
//             try c.encode(text ?? "", forKey: .text)
//         case .kv, .field:
//             try c.encode(label, forKey: .label)
//             try c.encode(value ?? "", forKey: .value)
//         case .table:
//             try c.encode(header ?? [], forKey: .header)
//             try c.encode(rows ?? [], forKey: .rows)
//         case .list:
//             try c.encode(items ?? [], forKey: .items)
//         case .message:
//             try c.encode(sender, forKey: .sender)
//             try c.encode(ts, forKey: .ts)
//             try c.encodeIfPresent(tsLabel, forKey: .tsLabel)
//             try c.encode(text ?? "", forKey: .text)
//             try c.encode(isOutgoing, forKey: .isOutgoing)
//         }
//     }
// }
//
// public struct FocusedField: Sendable, Equatable, Encodable {
//     public var label: String?
//     public var value: String
//     public var role: String
//
//     enum K: String, CodingKey { case label, value, role }
//     public func encode(to encoder: any Encoder) throws {
//         var c = encoder.container(keyedBy: K.self)
//         try c.encode(label, forKey: .label)
//         try c.encode(value, forKey: .value)
//         try c.encode(role, forKey: .role)
//     }
// }
//
// /// Read health, count-only (also the per-app `ax_empty` telemetry of plan §10.7).
// public struct ReadStats: Sendable, Equatable, Encodable {
//     public var walk: WalkStats
//     public var blocks: Int
//     public var chars: Int
//     public var blockCounts: [String: Int]
//     /// Subset of `blocks`, `rows`, `items`, `chars`.
//     public var cappedBy: [String]
//     public var axEmpty: Bool
//     public var reader: String
//
//     enum CodingKeys: String, CodingKey {
//         case walk, blocks, chars, reader
//         case blockCounts = "block_counts", cappedBy = "capped_by", axEmpty = "ax_empty"
//     }
// }
//
// /// One `screen_doc` line (schema v1, P1 build §3.7).
// public struct ScreenDoc: Sendable, Encodable, ReaderLine {
//     public var ts: String
//     public var bundleID: String?
//     public var url: String?
//     public var threadKey: String?
//     public var title: String?
//     public var blocks: [ScreenBlock]
//     public var focusedField: FocusedField?
//     public var treeHash: String
//     public var stats: ReadStats
//
//     enum K: String, CodingKey {
//         case schemaVersion = "schema_version", kind, ts, app, url, title, blocks, stats
//         case bundleID = "bundle_id", threadKey = "thread_key", focusedField = "focused_field", treeHash = "tree_hash"
//     }
//
//     public func encode(to encoder: any Encoder) throws {
//         var c = encoder.container(keyedBy: K.self)
//         try c.encode(1, forKey: .schemaVersion)
//         try c.encode("screen_doc", forKey: .kind)
//         try c.encode("generic", forKey: .app)
//         try c.encode(ts, forKey: .ts)
//         try c.encode(bundleID, forKey: .bundleID)
//         try c.encode(url, forKey: .url)
//         try c.encode(threadKey, forKey: .threadKey)
//         try c.encode(title, forKey: .title)
//         try c.encode(blocks, forKey: .blocks)
//         try c.encode(focusedField, forKey: .focusedField)
//         try c.encode(treeHash, forKey: .treeHash)
//         try c.encode(stats, forKey: .stats)
//     }
//
//     /// Structure only: every captured string becomes `<n>` (its length), times `<time>`, the URL
//     /// its host, the thread key drops path/title; no title, no fingerprints.
//     public func redacted() -> ScreenDoc {
//         func r(_ s: String?) -> String? { s.map { "<\($0.count)>" } }
//         var d = self
//         d.blocks = blocks.map { b in
//             var x = b
//             x.fp = ""
//             x.text = r(b.text)
//             x.label = r(b.label)
//             x.value = r(b.value)
//             x.header = b.header?.map { "<\($0.count)>" }
//             x.rows = b.rows?.map { $0.map { "<\($0.count)>" } }
//             x.items = b.items?.map { "<\($0.count)>" }
//             x.sender = r(b.sender)
//             x.ts = b.ts.map { _ in "<time>" }
//             x.tsLabel = b.tsLabel.map { _ in "<time>" }
//             return x
//         }
//         d.focusedField = focusedField.map { FocusedField(label: r($0.label), value: "<\($0.value.count)>", role: $0.role) }
//         let host = url.flatMap { URLComponents(string: $0) }.flatMap { c in c.host.map { "\(c.scheme ?? "https")://\($0)" } }
//         d.url = host
//         d.threadKey = threadKey.map { k in
//             let b = bundleID ?? "unknown"
//             if let h = host.flatMap({ URLComponents(string: $0)?.host }) { return "doc:\(b):\(h)" }
//             return k.contains(":title:") ? "doc:\(b):title:<redacted>" : k
//         }
//         d.title = nil
//         return d
//     }
// }
//
// // MARK: - Caps, fingerprints, hash, thread key
//
// public enum ScreenDocRules {
//     public static let maxChars = 30_000
//     public static let maxBlocks = 500
//     public static let maxRows = 200
//     public static let maxItems = 200
//
//     /// Per-read caps (plan §10.7, same numbers as the core's `cap_blocks`): ≤ 500 blocks,
//     /// ≤ 200 table rows / list items, ≤ 30k chars (the block that crosses it is cut when it is text).
//     public static func cap(_ blocks: [ScreenBlock]) -> (blocks: [ScreenBlock], cappedBy: [String]) {
//         var capped = Set<String>()
//         var out: [ScreenBlock] = []
//         var total = 0
//         if blocks.count > maxBlocks { capped.insert("blocks") }
//         for var b in blocks.prefix(maxBlocks) {
//             if let rows = b.rows, rows.count > maxRows { b.rows = Array(rows.prefix(maxRows)); capped.insert("rows") }
//             if let items = b.items, items.count > maxItems { b.items = Array(items.prefix(maxItems)); capped.insert("items") }
//             let n = b.content.count
//             if total + n > maxChars {
//                 capped.insert("chars")
//                 let room = maxChars - total
//                 if let t = b.text, [.heading, .paragraph, .message].contains(b.role) {
//                     let fixed = n - t.count
//                     if room > fixed {
//                         b.text = String(t.prefix(room - fixed))
//                         out.append(b)
//                         total += b.content.count
//                     }
//                 }
//                 break
//             }
//             out.append(b)
//             total += n
//         }
//         return (out, ["blocks", "rows", "items", "chars"].filter { capped.contains($0) })
//     }
//
//     public static func fingerprint(_ b: ScreenBlock) -> String {
//         var h = SHA256()
//         h.update(data: Data(TextNormalizer.normalize(b.content).lowercased().utf8))
//         h.update(data: [0x1F])
//         h.update(data: Data(b.role.rawValue.utf8))
//         h.update(data: [0x1F])
//         h.update(data: Data(b.path.utf8))
//         return "sha256:" + h.finalize().map { String(format: "%02x", $0) }.joined()
//     }
//
//     /// Hash over normalised emitted content (role + text, document order): relative-time churn,
//     /// tracking params and structure-only changes do not change it.
//     public static func treeHash(_ blocks: [ScreenBlock]) -> String {
//         var h = TreeHasher()
//         for b in blocks { h.add(b.role.rawValue + "\u{1F}" + b.content) }
//         return "sha256:" + h.finalize()
//     }
//
//     /// bundle id + host + path (no query/fragment) for web pages; bundle id + window title for
//     /// native apps. A suggestion: the core derives its own key the same way.
//     public static func threadKey(bundleID: String?, url: String?, title: String?) -> String? {
//         let b = bundleID ?? "unknown"
//         if let url, let c = URLComponents(string: url), let scheme = c.scheme?.lowercased(),
//            scheme == "http" || scheme == "https", let host = c.host?.lowercased(), !host.isEmpty {
//             var path = c.path
//             while path.hasSuffix("/") { path.removeLast() }
//             return "doc:\(b):\(host.trimmingCharacters(in: CharacterSet(charactersIn: ".")))\(path)"
//         }
//         guard let title else { return nil }
//         let t = TextNormalizer.normalize(title).lowercased()
//         return t.isEmpty ? nil : "doc:\(b):title:\(t)"
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/SlackReader.swift`

```swift
// import CryptoKit
// import Foundation
//
// /// Dedicated reader for Slack — the web client (`app.slack.com`) and the desktop app, which is the
// /// same Chromium tree.
// ///
// /// MEASURED live 2026-10-07 on an open channel (`app.slack.com/client/T…/C…`). The message list is
// /// an `AXList` whose rows are `AXGroup`s, and every row that is a message carries a clock:
// ///
// ///     AXList
// ///       └ AXGroup                       one message
// ///           ├ AXButton      7–16 ch     the sender's name
// ///           ├ AXLink        19–20 ch    the permalink (NOT the name — measured, never name-like)
// ///           ├ AXStaticText  "10:42 AM"  the time
// ///           └ AXStaticText  × n         the body, one node per line
// ///
// /// A page has other `AXList`s (the sidebar, and a bulleted list INSIDE a message at depth 25), so
// /// the list is chosen by evidence: the one with the most rows that carry a clock. Slack shows every
// /// message left-aligned, so direction cannot be seen — `sender` is reported as written and whether
// /// it is the manager is decided where the manager's own names are known.
// public struct SlackReader: DedicatedReader {
//     public let id = "slack"
//     public init() {}
//
//     static let bundles: Set<String> = ["com.tinyspeck.slackmacgap", "slack.exe"]
//     /// "10:42 AM", "10.42", "22:05" — and nothing longer.
//     static let clock = try! NSRegularExpression(pattern: #"^\d{1,2}[:.]\d{2}(\s?[AaPp]\.?[Mm]\.?)?$"#)
//     /// A row needs a body; a sender name is at most this long.
//     static let maxName = 60
//
//     public func accepts(_ ctx: ReadContext) -> Bool {
//         if let b = ctx.bundleID, Self.bundles.contains(b.lowercased()) { return true }
//         guard let host = Self.host(ctx.url) else { return false }
//         return host == "app.slack.com" || host.hasSuffix(".slack.com")
//     }
//
//     public func read(_ root: RNode, _ ctx: ReadContext) -> (any ReaderLine)? {
//         guard let list = Self.messageList(root) else { return nil }
//         var msgs: [ThreadRead.Message] = []
//         for row in list.children {
//             if let m = Self.message(row) { msgs.append(m) }
//         }
//         guard !msgs.isEmpty else { return nil }
//         let key = Self.threadKey(ctx.url) ?? "slack:unknown"
//         let blob = msgs.map { ($0.sender ?? "") + "|" + $0.text }.joined(separator: "\n")
//         let hash = SHA256.hash(data: Data(blob.utf8)).map { String(format: "%02x", $0) }.joined()
//         return ThreadRead(ts: Timestamp.format(ctx.now), bundleID: ctx.bundleID, app: id,
//                           threadKey: key, title: ReaderText.clean(ctx.windowTitle), messages: msgs,
//                           draft: ctx.draft ? Self.composer(root) : nil, treeHash: "sha256:" + hash)
//     }
//
//     // ── structure ───────────────────────────────────────────────────────────────────────────────
//
//     static func host(_ url: String?) -> String? {
//         guard let u = url, let c = URLComponents(string: u), let h = c.host else { return nil }
//         return h.lowercased()
//     }
//
//     /// `slack:<team>/<channel>` from `/client/T…/C…`; the channel is in the PATH, so the key needs
//     /// nothing scraped off the screen.
//     static func threadKey(_ url: String?) -> String? {
//         guard let u = url, let c = URLComponents(string: u) else { return nil }
//         let parts = c.path.split(separator: "/").map(String.init)
//         guard let i = parts.firstIndex(of: "client"), parts.count > i + 1 else { return nil }
//         return "slack:" + parts[(i + 1)...].prefix(2).joined(separator: "/")
//     }
//
//     static func walk(_ n: RNode, _ f: (RNode) -> Void) {
//         f(n)
//         for c in n.children { walk(c, f) }
//     }
//
//     /// Every label on this node, cleaned, most specific first.
//     static func labels(_ n: RNode) -> [String] {
//         [n.attrs.description, n.attrs.value, n.attrs.title].compactMap(ReaderText.clean)
//     }
//
//     static func label(_ n: RNode) -> String { labels(n).first ?? "" }
//
//     static func isClock(_ s: String) -> Bool {
//         let t = s.trimmingCharacters(in: .whitespaces)
//         return clock.firstMatch(in: t, range: NSRange(t.startIndex..., in: t)) != nil
//     }
//
//     /// The `AXList` that is the conversation: the one with the most clock-bearing rows. The sidebar
//     /// has no clocks; a bulleted list inside a message has no clocks of its own.
//     static func messageList(_ root: RNode) -> RNode? {
//         var best: (RNode, Int)?
//         walk(root) { n in
//             guard n.role == "AXList" else { return }
//             let timed = n.children.filter { row in
//                 var hit = false
//                 walk(row) { if !hit, isClock(label($0)) { hit = true } }
//                 return hit
//             }.count
//             if timed >= 1, best == nil || timed > best!.1 { best = (n, timed) }
//         }
//         return best?.0
//     }
//
//     /// One row → one message, or nil (a day separator, the "new messages" marker, a join notice).
//     static func message(_ row: RNode) -> ThreadRead.Message? {
//         var sender: String?
//         var clockSeen = false
//         var body: [String] = []
//         walk(row) { n in
//             let s = label(n)
//             guard !s.isEmpty else { return }
//             if isClock(s) {
//                 clockSeen = true
//                 return
//             }
//             if !clockSeen {
//                 // Before the clock sits the row header: the permalink (an AXLink) and the
//                 // sender's name on a BUTTON. Only the button may become the sender — MEASURED
//                 // 2026-10-07, a row can open with a wrapper group carrying 45 characters of its
//                 // own, and taking "the first label" made that the sender's name.
//                 // (A link after the clock is different: that is something the sender wrote — a
//                 // doc, a Meet link — and it belongs in the body.)
//                 if sender == nil, n.role == "AXButton", s.count <= maxName { sender = s }
//                 return
//             }
//             // After the clock everything the sender put in the message counts, links included.
//             if n.role == "AXStaticText" || n.role == "AXGroup" || n.role == "AXLink" { body.append(s) }
//         }
//         let text = body.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
//         // The clock is already required: `body` is only collected AFTER one is seen, so a row
//         // without a clock — a day separator, "Ujjwal joined the channel" — arrives here empty.
//         // Re-checking `clockSeen` here looked like a rule and was dead; a dead rule hides which
//         // line actually protects you.
//         guard !text.isEmpty else { return nil }
//         // Slack is flat — no left/right. Who is "me" is decided where the manager's names are known.
//         return ThreadRead.Message(sender: sender, text: text, isOutgoing: false)
//     }
//
//     /// The composer's own text (Draft assist only).
//     static func composer(_ root: RNode) -> String? {
//         var v: String?
//         walk(root) { n in
//             guard v == nil, n.isEditable else { return }
//             guard let s = ReaderText.clean(n.attrs.value) else { return }
//             if s != ReaderText.clean(n.attrs.placeholder) { v = s }
//         }
//         return v
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/TeamsReader.swift`

```swift
// import Foundation
//
// /// Dedicated reader for Microsoft Teams — the web client (`teams.microsoft.com`, `teams.live.com`)
// /// and the desktop app, which `AppCatalog.electronTargets` already enables AX on.
// ///
// /// Teams routes the open chat in the URL FRAGMENT (`#/conversations/19:abc…`), which is why
// /// `capture/session.rs` lists both hosts in `FRAGMENT_ROUTED_HOSTS`. The key comes off the
// /// fragment; a Teams screen without one — the activity feed, calendar, files — is refused.
// ///
// /// NOT MEASURED YET on a real tree. Teams nests heavily, so `ThreadScan.dedupe` is doing real
// /// work here: the paragraph group and its line children would otherwise both be collected and
// /// every message would read twice.
// public struct TeamsReader: DedicatedReader {
//     public let id = "teams"
//     public init() {}
//
//     static let bundles: Set<String> = [
//         "com.microsoft.teams", "com.microsoft.teams2", "com.microsoft.skype.teams",
//         "ms-teams.exe", "teams.exe",
//     ]
//     static let hostSuffixes = ["teams.microsoft.com", "teams.live.com", "teams.microsoft.us"]
//
//     public func accepts(_ ctx: ReadContext) -> Bool {
//         if let b = ctx.bundleID, Self.bundles.contains(b.lowercased()) { return true }
//         guard let h = ThreadScan.host(ctx.url) else { return false }
//         return Self.hostSuffixes.contains(where: { h == $0 || h.hasSuffix("." + $0) })
//     }
//
//     public func read(_ root: RNode, _ ctx: ReadContext) -> (any ReaderLine)? {
//         ThreadScan.read(root, ctx, app: id, threadKey: Self.threadKey(ctx.url),
//                         senderRoles: ["AXButton", "AXLink", "AXStaticText", "AXHeading"])
//     }
//
//     /// `tm:conv:<id>` from `#/conversations/19:abc…`.
//     ///
//     /// Teams' own conversation ids already carry a prefix (`19:`, `48:`), so they are taken as
//     /// they are — rewriting them would make the device's key disagree with the one the brain sees
//     /// in a Graph payload for the same chat.
//     static func threadKey(_ url: String?) -> String? {
//         guard let f = ThreadScan.fragment(url) else { return nil }
//         let parts = f.split(separator: "/").map(String.init).filter { !$0.isEmpty }
//         // "conversations/<id>" and "chat/<id>" are both in use; take the segment after either.
//         for anchor in ["conversations", "chat", "channel"] {
//             if let i = parts.firstIndex(of: anchor), parts.count > i + 1 {
//                 let id = parts[i + 1]
//                 if id.count >= 4 { return "tm:conv:" + id }
//             }
//         }
//         return nil
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/ThreadScan.swift`

```swift
// import CryptoKit
// import Foundation
//
// /// What every conversation surface has in common, so four readers do not re-derive it four times.
// ///
// /// WHY THIS IS STRUCTURAL AND NOT A LAYOUT RECIPE. `SlackReader` and `WhatsAppReader` were written
// /// from trees recorded live with `scripts/measure.sh`. Gmail, Outlook, Teams and the LinkedIn
// /// client have not been recorded on this machine, and the WhatsApp reader is the standing warning
// /// about what happens when you write one from a guess: it looked finished, shipped, and returned
// /// nothing for months because the roles it expected were not the roles on screen.
// ///
// /// So nothing here hardcodes a path, a depth or an index. It looks for the two things a message
// /// list cannot not have:
// ///
// ///   1. a container whose rows carry a CLOCK — every chat and mail client stamps a time on each
// ///      message, and no sidebar, toolbar or navigation list does;
// ///   2. inside a row, the header (sender) sits BEFORE the clock and the body AFTER it.
// ///
// /// Both are invariants of the product, not of the markup, which is why this survives a redesign.
// /// A reader built on it returns nil rather than guessing when the evidence is absent, and the
// /// generic reader takes over — `scripts/check-readers.sh` has an alarm that fails if a surface a
// /// reader claims is being served by the generic one.
// ///
// /// STILL OWED: a measured pass per app (`scripts/measure.sh` with that app in front) to confirm
// /// the sender lands on the role each client uses for it. Until then `senderRoles` is deliberately
// /// wide and the body is deliberately greedy, so a wrong guess costs a missing sender, never a
// /// missing message.
// enum ThreadScan {
//
//     /// "10:42 AM", "10.42", "22:05", "4:05 pm" — and nothing longer.
//     static let clock = try! NSRegularExpression(pattern: #"^\d{1,2}[:.]\d{2}(\s?[AaPp]\.?[Mm]\.?)?$"#)
//
//     /// A time that also carries a date, which mail clients put on each message:
//     /// "Tue, 7 Oct, 10:42", "Oct 7, 2026, 10:42 AM", "7 October 2026 at 10:42".
//     static let stampedClock = try! NSRegularExpression(
//         pattern: #"\d{1,2}[:.]\d{2}(\s?[AaPp]\.?[Mm]\.?)?"#)
//
//     /// A sender name is at most this long; past it the label is a sentence, not a name.
//     static let maxName = 80
//     /// Rows beyond this are not read — a long mail thread is still a thread, not a corpus.
//     static let maxRows = 300
//
//     static func walk(_ n: RNode, _ f: (RNode) -> Void) {
//         f(n)
//         for c in n.children { walk(c, f) }
//     }
//
//     /// Every label on this node, cleaned, most specific first.
//     static func labels(_ n: RNode) -> [String] {
//         [n.attrs.description, n.attrs.value, n.attrs.title].compactMap(ReaderText.clean)
//     }
//
//     static func label(_ n: RNode) -> String { labels(n).first ?? "" }
//
//     static func isClock(_ s: String) -> Bool {
//         let t = s.trimmingCharacters(in: .whitespaces)
//         guard !t.isEmpty, t.count <= 40 else { return false }
//         if clock.firstMatch(in: t, range: NSRange(t.startIndex..., in: t)) != nil { return true }
//         // A mail client's stamp: a date AND a time. Requiring a digit-colon-digit keeps "Tuesday"
//         // and "Yesterday" out — those are day separators, not message times.
//         guard t.count >= 8, t.rangeOfCharacter(from: .decimalDigits) != nil else { return false }
//         return stampedClock.firstMatch(in: t, range: NSRange(t.startIndex..., in: t)) != nil
//     }
//
//     static func host(_ url: String?) -> String? {
//         guard let u = url, let c = URLComponents(string: u), let h = c.host else { return nil }
//         return h.lowercased()
//     }
//
//     /// The path segment after `after`, when there is one: `/messaging/thread/abc/` → "abc".
//     static func segment(_ url: String?, after: String) -> String? {
//         guard let u = url, let c = URLComponents(string: u) else { return nil }
//         let parts = c.path.split(separator: "/").map(String.init)
//         guard let i = parts.firstIndex(of: after), parts.count > i + 1 else { return nil }
//         let v = parts[i + 1]
//         return v.isEmpty ? nil : v
//     }
//
//     /// The URL fragment, undecorated: `#inbox/FMfcgz` → "inbox/FMfcgz".
//     static func fragment(_ url: String?) -> String? {
//         guard let u = url, let i = u.firstIndex(of: "#") else { return nil }
//         let f = String(u[u.index(after: i)...]).trimmingCharacters(in: CharacterSet(charactersIn: "/"))
//         return f.isEmpty ? nil : f
//     }
//
//     /// Does `row` contain a clock anywhere inside it?
//     static func timed(_ row: RNode) -> Bool {
//         var hit = false
//         walk(row) { if !hit, isClock(label($0)) { hit = true } }
//         return hit
//     }
//
//     /// The container that is the conversation: the one with the most clock-bearing rows.
//     ///
//     /// Chosen by EVIDENCE, not by role alone, because a page has several lists and tables — the
//     /// sidebar, the folder tree, a bulleted list inside one message. None of those stamps a time
//     /// on its rows; a message list stamps one on every row.
//     static func messageList(_ root: RNode, roles: Set<String> = ["AXList", "AXTable", "AXOutline", "AXGroup"]) -> RNode? {
//         var best: (RNode, Int)?
//         walk(root) { n in
//             guard roles.contains(n.role), n.children.count >= 1 else { return }
//             let hits = n.children.prefix(maxRows).filter(timed).count
//             // A COST GUARD, and labelled as one rather than left looking like a protection.
//             //
//             // Correctness does not rest here: `message` collects a body only AFTER it has seen a
//             // clock, so a clockless container chosen by mistake yields no messages and `read`
//             // returns nil either way. What this saves is walking the subtree of up to `maxRows`
//             // rows of a folder list on every non-conversation page the URL happens to match.
//             //
//             // Saying so matters because the mutation that deletes this line is an EQUIVALENT
//             // mutant — it cannot be caught, and `scripts/check-readers.sh` would have carried it
//             // as a permanent "SURVIVED" that looks like missing coverage. `SlackReader` records
//             // the same lesson from the other direction: a dead rule hides which line protects you.
//             guard hits >= 1 else { return }
//             if best == nil || hits > best!.1 { best = (n, hits) }
//         }
//         return best?.0
//     }
//
//     /// One row → one message, or nil (a day separator, an unread marker, a join notice).
//     ///
//     /// `senderRoles` is which roles may carry the sender's name. Each client puts it on a
//     /// different one (Slack a button, mail clients a link or static text), and a role that is not
//     /// listed simply never becomes the sender — the message still arrives, unattributed, which is
//     /// the safe direction. `moments/focus.rs` is built to render an unattributable message with no
//     /// speaker prefix rather than guessing.
//     static func message(_ row: RNode, senderRoles: Set<String>,
//                         bodyRoles: Set<String> = ["AXStaticText", "AXGroup", "AXLink", "AXHeading", "AXCell"]) -> ThreadRead.Message? {
//         var sender: String?
//         var clockSeen = false
//         var body: [String] = []
//         walk(row) { n in
//             let s = label(n)
//             guard !s.isEmpty else { return }
//             if isClock(s) {
//                 clockSeen = true
//                 return
//             }
//             if !clockSeen {
//                 // The row header, which holds more than the sender: MEASURED on Slack 2026-10-07
//                 // a row opens with a wrapper carrying 45 characters of its own ("Message from
//                 // Priya Shah, unread, press to open"), and mail clients put an avatar label and
//                 // an unread marker in there too.
//                 //
//                 // Two filters, and PROXIMITY is the load-bearing one. Only a listed role may
//                 // become the sender, and among those the one NEAREST the clock wins — because
//                 // the header reads [noise…, sender, clock] in every client that stamps a time.
//                 // Taking the first eligible label instead made the wrapper the sender's name,
//                 // which is the same defect, found by the same trap, twice.
//                 //
//                 // The trade-off, stated because it is not free: a client that puts something
//                 // AFTER the sender and before the clock (a permalink, say — Slack does exactly
//                 // this, which is why `SlackReader` keeps its own stricter rule of AXButton only)
//                 // would hand that over instead. Narrowing `senderRoles` per app is the lever,
//                 // and a measured tree per app is what tells us where to set it.
//                 if senderRoles.contains(n.role), s.count <= maxName { sender = s }
//                 return
//             }
//             if bodyRoles.contains(n.role) { body.append(s) }
//         }
//         let text = dedupe(body).joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
//         // The clock is already required: `body` is only collected after one is seen, so a row
//         // without a clock arrives here empty.
//         guard !text.isEmpty else { return nil }
//         return ThreadRead.Message(sender: sender, text: text, isOutgoing: false)
//     }
//
//     /// Drops a piece that is already contained in the one before it.
//     ///
//     /// A web tree nests text: an `AXGroup` carrying the whole paragraph and the `AXStaticText`
//     /// children carrying each line both match `bodyRoles`, so without this every message reads
//     /// twice. That duplication is exactly what `screen_insight`'s `_is_paste` then rejected as a
//     /// pasted quote, so the card went missing rather than reading oddly.
//     static func dedupe(_ parts: [String]) -> [String] {
//         var out: [String] = []
//         for p in parts {
//             if let last = out.last, last.contains(p) || p.contains(last) {
//                 if p.count > last.count { out[out.count - 1] = p }
//                 continue
//             }
//             out.append(p)
//         }
//         return out
//     }
//
//     /// The composer's own text (Draft assist only).
//     static func composer(_ root: RNode) -> String? {
//         var v: String?
//         walk(root) { n in
//             guard v == nil, n.isEditable else { return }
//             guard let s = ReaderText.clean(n.attrs.value) else { return }
//             if s != ReaderText.clean(n.attrs.placeholder) { v = s }
//         }
//         return v
//     }
//
//     /// `sha256:…` over what was actually read, so an unchanged screen is recognised as unchanged.
//     static func treeHash(_ msgs: [ThreadRead.Message]) -> String {
//         let blob = msgs.map { ($0.sender ?? "") + "|" + $0.text }.joined(separator: "\n")
//         return "sha256:" + SHA256.hash(data: Data(blob.utf8)).map { String(format: "%02x", $0) }.joined()
//     }
//
//     /// Assemble the line every one of these readers returns, or nil when there is no conversation
//     /// on screen — an inbox list, a calendar, a settings page. Returning nil hands the surface to
//     /// the generic reader, which is the honest outcome.
//     static func read(_ root: RNode, _ ctx: ReadContext, app: String, threadKey: String?,
//                      senderRoles: Set<String>, listRoles: Set<String>? = nil) -> (any ReaderLine)? {
//         // No key means the URL does not say WHICH conversation is open, so anything read here
//         // would land on a shared key — one verdict for a whole mailbox. That defect is documented
//         // in `capture/session.rs` (FRAGMENT_ROUTED_HOSTS); refusing to read is the fix.
//         guard let key = threadKey else { return nil }
//         let list = listRoles.map { messageList(root, roles: $0) } ?? messageList(root)
//         guard let list else { return nil }
//         var msgs: [ThreadRead.Message] = []
//         for row in list.children.prefix(maxRows) {
//             if let m = message(row, senderRoles: senderRoles) { msgs.append(m) }
//         }
//         guard !msgs.isEmpty else { return nil }
//         return ThreadRead(ts: Timestamp.format(ctx.now), bundleID: ctx.bundleID, app: app,
//                           threadKey: key, title: ReaderText.clean(ctx.windowTitle), messages: msgs,
//                           draft: ctx.draft ? composer(root) : nil, treeHash: treeHash(msgs))
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/Reader/WhatsAppReader.swift`

```swift
// import CryptoKit
// import Foundation
//
// /// One `thread_read` line (P1 build §3.6), emitted by a dedicated reader. Same wire shape the Rust
// /// core parses (`capture/thread_source.rs` `ThreadRead` / `ReadMessage`).
// public struct ThreadRead: Sendable, Encodable, ReaderLine {
//     public struct Message: Sendable, Equatable, Encodable {
//         /// The other person's name as shown, or "self" for the manager's own message.
//         public var sender: String?
//         public var text: String
//         public var isOutgoing: Bool
//
//         enum K: String, CodingKey { case sender, ts, text, isOutgoing = "is_outgoing", replyTo = "reply_to" }
//
//         public func encode(to encoder: any Encoder) throws {
//             var c = encoder.container(keyedBy: K.self)
//             try c.encode(sender, forKey: .sender)
//             try c.encodeNil(forKey: .ts)
//             try c.encode(text, forKey: .text)
//             try c.encode(isOutgoing, forKey: .isOutgoing)
//             try c.encodeNil(forKey: .replyTo)
//         }
//     }
//
//     public var ts: String
//     public var bundleID: String?
//     public var app: String
//     public var threadKey: String
//     public var title: String?
//     public var messages: [Message]
//     public var draft: String?
//     public var treeHash: String
//
//     enum K: String, CodingKey {
//         case schemaVersion = "schema_version", kind, ts, app, url, title, participants, messages, draft
//         case bundleID = "bundle_id", threadKey = "thread_key", scrolledUp = "scrolled_up", treeHash = "tree_hash"
//     }
//
//     private struct Participant: Encodable {
//         var name: String?
//         var isSelf: Bool?
//         enum K: String, CodingKey { case name, isSelf = "self" }
//         func encode(to encoder: any Encoder) throws {
//             var c = encoder.container(keyedBy: K.self)
//             try c.encodeIfPresent(name, forKey: .name)
//             try c.encodeIfPresent(isSelf, forKey: .isSelf)
//         }
//     }
//
//     public func encode(to encoder: any Encoder) throws {
//         var c = encoder.container(keyedBy: K.self)
//         try c.encode(1, forKey: .schemaVersion)
//         try c.encode("thread_read", forKey: .kind)
//         try c.encode(ts, forKey: .ts)
//         try c.encode(bundleID, forKey: .bundleID)
//         try c.encode(app, forKey: .app)
//         try c.encodeNil(forKey: .url)
//         try c.encode(threadKey, forKey: .threadKey)
//         try c.encode(title, forKey: .title)
//         var parts: [Participant] = []
//         if let t = title { parts.append(Participant(name: t, isSelf: nil)) }
//         parts.append(Participant(name: nil, isSelf: true))
//         try c.encode(parts, forKey: .participants)
//         try c.encode(messages, forKey: .messages)
//         try c.encode(draft, forKey: .draft)
//         try c.encode(false, forKey: .scrolledUp)
//         try c.encode(treeHash, forKey: .treeHash)
//     }
//
//     /// Structure only (`--redact`): every captured string becomes `<n>` (its length).
//     public func redacted() -> ThreadRead {
//         func r(_ s: String) -> String { "<\(s.count)>" }
//         var t = self
//         t.title = title.map(r)
//         // The prefix is the reader's, not WhatsApp's: this type is shared (SlackReader emits it
//         // too), and hardcoding "wa:" made a Slack thread print as a WhatsApp one.
//         t.threadKey = (threadKey.split(separator: ":").first.map { $0 + ":" } ?? "") + "<redacted>"
//         t.messages = messages.map {
//             Message(sender: $0.sender.map { $0 == "self" ? "self" : r($0) }, text: r($0.text), isOutgoing: $0.isOutgoing)
//         }
//         t.draft = draft.map(r)
//         return t
//     }
// }
//
// /// Dedicated reader for the native WhatsApp app (Catalyst).
// ///
// /// Its AX tree (measured 2026-09-14, re-measured live 2026-10-07) exposes the OPEN chat as a group
// /// described "Messages in chat with <name>" and each visible message as an `AXButton` labelled
// /// "message, <text>, <time>, Received from <name>" / "Your message, <text>, <time>, Sent to <name>"
// /// (media: "Photo, <time>, …"). Every WhatsApp chat so gets its own thread key (`wa:<name>`) — the
// /// generic reader only ever saw the window title "WhatsApp" and the chat list. The chat list on
// /// the left is never read. No open chat (or no parseable message) → nil → the generic reader.
// public struct WhatsAppReader: DedicatedReader {
//     public let id = "whatsapp"
//     public init() {}
//
//     static let bundles: Set<String> = ["net.whatsapp.WhatsApp", "desktop.WhatsApp"]
//     static let chatPrefix = "Messages in chat with "
//     static let media = ["Voice message", "Photo", "Video", "Audio", "Document", "Sticker", "GIF", "Contact", "Location"]
//     static let statuses = [", Read", ", Delivered", ", Sent", ", Pending", ", Seen", ", Played", ", Edited"]
//
//     /// VoiceOver reads a number contact digit group by digit group ("+ 9 1,6 3 9 5,3 2 7,1 1 5"):
//     /// such a name becomes the number itself ("+916395327115"). Real names are left as they are.
//     static func person(_ s: String) -> String {
//         let t = s.trimmingCharacters(in: .whitespaces)
//         guard t.range(of: #"^\+?[\d\s,]{6,}$"#, options: .regularExpression) != nil else { return t }
//         return t.filter { $0 == "+" || $0.isNumber }
//     }
//
//     public func accepts(_ ctx: ReadContext) -> Bool {
//         ctx.bundleID.map { Self.bundles.contains($0) } ?? false
//     }
//
//     public func read(_ root: RNode, _ ctx: ReadContext) -> (any ReaderLine)? {
//         guard let (group, name) = Self.chatGroup(root) else { return nil }
//         // The group NAMES the open chat; it does not necessarily contain it. MEASURED 2026-10-07:
//         // the message buttons sit in a sibling subtree, so scoping the search to the group found
//         // zero messages and the reader fell through to the generic one. Inside the group first
//         // (the 2026-09-14 shape), the window second — and the chat list on the left cannot leak
//         // in either way, because a list row carries no "Received from" / "Sent to" label and
//         // `parse` is what admits a message, not where it was found.
//         var msgs: [ThreadRead.Message] = []
//         Self.collect(group, into: &msgs)
//         if msgs.isEmpty { Self.collect(root, into: &msgs, bubbleOnly: true) }
//         guard !msgs.isEmpty else { return nil }
//         let draft = ctx.draft ? Self.composer(root) : nil
//         let blob = msgs.map { ($0.isOutgoing ? "o|" : "i|") + ($0.sender ?? "") + "|" + $0.text }.joined(separator: "\n")
//         let hash = SHA256.hash(data: Data(blob.utf8)).map { String(format: "%02x", $0) }.joined()
//         return ThreadRead(ts: Timestamp.format(ctx.now), bundleID: ctx.bundleID, app: id,
//                           threadKey: "wa:" + name.lowercased(), title: name, messages: msgs, draft: draft,
//                           treeHash: "sha256:" + hash)
//     }
//
//     /// Without the bidi marks WhatsApp puts around names and labels (U+200E …), whitespace collapsed.
//     static func clean(_ s: String?) -> String {
//         let kept = (s ?? "").unicodeScalars.filter {
//             !(0x200E...0x200F).contains($0.value) && !(0x202A...0x202E).contains($0.value)
//                 && !(0x2066...0x2069).contains($0.value)
//         }
//         return String(String.UnicodeScalarView(kept)).split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
//     }
//
//     /// The element's label as VoiceOver would read it (description, else value, else title).
//     static func text(_ n: RNode) -> String {
//         for s in [n.attrs.description, n.attrs.value, n.attrs.title] {
//             let c = clean(s)
//             if !c.isEmpty { return c }
//         }
//         return ""
//     }
//
//     /// Roles a message bubble can arrive as.
//     ///
//     /// MEASURED on a live tree, 2026-10-07 (WhatsApp 2.26.x, macOS 15): a message is an
//     /// **`AXButton`**, not an `AXStaticText`. The reader had been written against `AXStaticText`
//     /// only. A role is never what decides a message, though — [`parse`] is, and it requires
//     /// "Received from" / "Sent to", so a toolbar button can never become a message.
//     static let messageRoles: Set<String> = ["AXStaticText", "AXButton"]
//
//     /// Every label VoiceOver may have put a message on, most specific first.
//     ///
//     /// MEASURED, same tree: the message label lives on `AXValue` while `AXDescription` holds the
//     /// bare message text. [`text`] returns the FIRST non-empty of description → value → title, so
//     /// it returned the bare text, `parse` found no "Received from" / "Sent to" in it and returned
//     /// nil — for every message in every chat. Native WhatsApp, the one surface with a dedicated
//     /// reader, was silently served by the GENERIC reader, which skips buttons entirely
//     /// (`Roles.skip`) and therefore shipped the chat LIST instead of the open conversation.
//     /// Reading one attribute and stopping is the bug; every label is tried now.
//     static func labels(_ n: RNode) -> [String] {
//         [n.attrs.description, n.attrs.value, n.attrs.title].map(clean).filter { !$0.isEmpty }
//     }
//
//     /// Is this the label of a BUBBLE in the open chat, rather than a row in the chat list?
//     ///
//     /// A bubble's label starts with its own prefix — MEASURED live 2026-10-07, all four messages
//     /// on screen: "Your message, …" ×2, "Photo, …", "message, …". A chat-list row starts with the
//     /// chat's NAME instead ("Priya Shah, message, See you, 10:02 AM, Received from Priya Shah" —
//     /// the shape measured 2026-09-14). That difference is the only safe way to search the whole
//     /// window without the list on the left leaking into the open conversation.
//     static func isBubbleLabel(_ l: String) -> Bool {
//         l.hasPrefix("Your message, ") || l.hasPrefix("message, ") || media.contains { l.hasPrefix($0) }
//     }
//
//     /// This node as a message, from whichever of its labels carries one. `bubbleOnly` additionally
//     /// demands [`isBubbleLabel`] — used when searching outside the chat group.
//     static func message(_ n: RNode, bubbleOnly: Bool = false) -> ThreadRead.Message? {
//         guard messageRoles.contains(n.role) else { return nil }
//         for l in labels(n) {
//             if bubbleOnly && !isBubbleLabel(l) { continue }
//             if let m = parse(l) { return m }
//         }
//         return nil
//     }
//
//     /// Every message under `n`, in document order.
//     ///
//     /// A bubble that parses is NOT descended into: WhatsApp repeats the same label on the button
//     /// and on the text inside it, and walking both would count one message twice.
//     static func collect(_ n: RNode, into out: inout [ThreadRead.Message], bubbleOnly: Bool = false) {
//         if let m = message(n, bubbleOnly: bubbleOnly) {
//             out.append(m)
//             return
//         }
//         for c in n.children { collect(c, into: &out, bubbleOnly: bubbleOnly) }
//     }
//
//     static func walk(_ n: RNode, _ f: (RNode) -> Void) {
//         f(n)
//         for c in n.children { walk(c, f) }
//     }
//
//     /// The open chat's message group and the chat's name.
//     static func chatGroup(_ root: RNode) -> (RNode, String)? {
//         var found: (RNode, String)?
//         walk(root) { n in
//             guard found == nil, n.role == "AXGroup" else { return }
//             let t = text(n)
//             guard t.hasPrefix(chatPrefix) else { return }
//             let name = String(t.dropFirst(chatPrefix.count)).trimmingCharacters(in: .whitespaces)
//             if !name.isEmpty { found = (n, name) }
//         }
//         return found
//     }
//
//     /// The composer's own text (Draft assist only), never its placeholder.
//     static func composer(_ root: RNode) -> String? {
//         var v: String?
//         walk(root) { n in
//             guard v == nil, n.role == "AXTextArea" else { return }
//             let s = clean(n.attrs.value)
//             if !s.isEmpty, s != clean(n.attrs.placeholder), s != clean(n.attrs.description), s != "Type a message" {
//                 v = s
//             }
//         }
//         return v
//     }
//
//     /// "message, <text>, <time>, Received from <name>" → incoming from <name>; "Your message, <text>,
//     /// <time>, Sent to <name>[, Read]" → the manager's own; media without text → "[Photo]". Anything
//     /// else (date separators, the encryption notice, system lines) → nil.
//     static func parse(_ raw: String) -> ThreadRead.Message? {
//         var s = clean(raw)
//         for _ in 0..<2 {
//             for st in statuses where s.hasSuffix(st) { s = String(s.dropLast(st.count)) }
//         }
//         var outgoing: Bool
//         var sender: String?
//         if let r = s.range(of: ", Received from ", options: .backwards) {
//             outgoing = false
//             sender = person(String(s[r.upperBound...]))
//             s = String(s[..<r.lowerBound])
//         } else if let r = s.range(of: ", Sent to ", options: .backwards) {
//             outgoing = true
//             sender = "self"
//             s = String(s[..<r.lowerBound])
//         } else {
//             return nil
//         }
//         if let r = s.range(of: #",\s*\d{1,2}:\d{2}(\s?[AaPp]\.?[Mm]\.?)?$"#, options: .regularExpression) {
//             s = String(s[..<r.lowerBound])
//         }
//         if s.hasPrefix("Your message, ") {
//             outgoing = true
//             sender = "self"
//             s = String(s.dropFirst("Your message, ".count))
//         } else if s.hasPrefix("message, ") {
//             s = String(s.dropFirst("message, ".count))
//         } else if let m = media.first(where: { s == $0 || s.hasPrefix($0 + ", ") }) {
//             let caption = s == m ? "" : String(s.dropFirst(m.count + 2))
//             s = caption.isEmpty ? "[\(m)]" : "[\(m)] \(caption)"
//         }
//         let text = s.trimmingCharacters(in: .whitespaces)
//         guard !text.isEmpty, text != "message" else { return nil }
//         return ThreadRead.Message(sender: sender, text: text, isOutgoing: outgoing)
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/TextNormalizer.swift`

```swift
// import Foundation
//
// /// Normalises visible text before hashing so that cosmetic churn (relative timestamps,
// /// tracking params, invisible marks, whitespace) does not look like new content.
// /// Used only for change detection — never alters text that is captured/uploaded.
// public enum TextNormalizer {
//     public static let relativeTimeToken = "<t>"
//
//     private static let unit =
//         "(?:s|secs?|seconds?|m|mins?|minutes?|h|hrs?|hours?|d|days?|w|wks?|weeks?|mos?|months?|y|yrs?|years?)"
//
//     private static let relativeTimePatterns: [NSRegularExpression] = [
//         // "5 min ago", "2 hours ago", "an hour ago", "a few seconds ago", "about 3 weeks ago", "5m ago"
//         #"\b(?:about\s+|over\s+|almost\s+)?(?:\d+|a|an|one|a\s+few|few)\s*\#(unit)\s+ago\b"#,
//         // "just now", "moments ago", "a moment ago"
//         #"\b(?:just\s+now|moments?\s+ago|a\s+moment\s+ago)\b"#,
//         // "in 5 min", "in an hour" (calendar countdowns)
//         #"\bin\s+(?:\d+|a|an|one)\s*(?:mins?|minutes?|h|hrs?|hours?|d|days?)\b"#,
//         // compact chat/feed stamps: "5m", "3h", "2d", "1w", "4mo", "1y"
//         #"(?<![\w:.,/$€£₹])\d{1,3}(?:mo|m|h|d|w|y)(?!\w)"#,
//         // day words that roll over at midnight
//         #"\b(?:today|yesterday)\b"#,
//     ].map { try! NSRegularExpression(pattern: $0, options: [.caseInsensitive]) }
//
//     private static let whitespace = try! NSRegularExpression(pattern: #"\s+"#)
//
//     /// Zero-width, bidi and BOM scalars (WhatsApp/Slack sprinkle LRM/RLM around names and times).
//     private static let invisible: Set<UInt32> = [
//         0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF,
//         0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069,
//     ]
//
//     public static func normalize(_ input: String) -> String {
//         var s = input.precomposedStringWithCanonicalMapping
//         if s.unicodeScalars.contains(where: { invisible.contains($0.value) }) {
//             var scalars = String.UnicodeScalarView()
//             scalars.append(contentsOf: s.unicodeScalars.filter { !invisible.contains($0.value) })
//             s = String(scalars)
//         }
//         // NBSP / narrow NBSP (macOS time formatting) → plain space.
//         s = s.replacingOccurrences(of: "\u{00A0}", with: " ").replacingOccurrences(of: "\u{202F}", with: " ")
//         s = URLNormalizer.stripTrackingInText(s)
//         for re in relativeTimePatterns {
//             s = re.stringByReplacingMatches(
//                 in: s, range: NSRange(s.startIndex..., in: s), withTemplate: relativeTimeToken)
//         }
//         s = whitespace.stringByReplacingMatches(in: s, range: NSRange(s.startIndex..., in: s), withTemplate: " ")
//         return s.trimmingCharacters(in: .whitespaces)
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/TreeHash.swift`

```swift
// import CryptoKit
// import Foundation
//
// /// Stable hash over normalised visible text (document order). Identical hash ⇒ skip re-read/upload.
// /// Structure/role changes that do not change visible text do not change the hash.
// public struct TreeHasher: Sendable {
//     private var hasher = SHA256()
//     private var empty = true
//
//     public init() {}
//
//     /// Feeds one text fragment; empty-after-normalisation fragments are ignored.
//     public mutating func add(_ text: String) {
//         let n = TextNormalizer.normalize(text)
//         guard !n.isEmpty else { return }
//         if !empty { hasher.update(data: [0x1E]) }  // record separator between fragments
//         hasher.update(data: Data(n.utf8))
//         empty = false
//     }
//
//     public func finalize() -> String {
//         hasher.finalize().map { String(format: "%02x", $0) }.joined()
//     }
//
//     public static func hash<S: Sequence>(_ texts: S) -> String where S.Element == String {
//         var h = TreeHasher()
//         for t in texts { h.add(t) }
//         return h.finalize()
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/TreeWalker.swift`

```swift
// import CoreGraphics
// import Foundation
//
// // MARK: - Source abstraction (AX in production, synthetic trees in tests)
//
// public enum NodeReadError: Sendable, Equatable {
//     /// `kAXErrorCannotComplete` — app busy/unresponsive (messaging timeout hit).
//     case cannotComplete
//     /// Element vanished (`kAXErrorInvalidUIElement`).
//     case invalidElement
//     case other(Int32)
//
//     public var code: String {
//         switch self {
//         case .cannotComplete: return "cannot_complete"
//         case .invalidElement: return "invalid_element"
//         case .other(let c): return "ax_\(c)"
//         }
//     }
// }
//
// public struct NodeAttributes: Sendable, Equatable {
//     public var role: String?
//     public var subrole: String?
//     public var title: String?
//     public var description: String?
//     public var value: String?
//     public var url: String?
//     public var frame: CGRect?
//     /// Reader-only (`AXTreeSource(extended: true)`): `AXPlaceholderValue`.
//     public var placeholder: String?
//     /// Reader-only: text of the element's `AXTitleUIElement` (the visible label of a form field).
//     public var titleUIText: String?
//     /// Reader-only: `AXFocused`.
//     public var focused: Bool
//
//     public init(
//         role: String? = nil, subrole: String? = nil, title: String? = nil, description: String? = nil,
//         value: String? = nil, url: String? = nil, frame: CGRect? = nil,
//         placeholder: String? = nil, titleUIText: String? = nil, focused: Bool = false
//     ) {
//         self.role = role
//         self.subrole = subrole
//         self.title = title
//         self.description = description
//         self.value = value
//         self.url = url
//         self.frame = frame
//         self.placeholder = placeholder
//         self.titleUIText = titleUIText
//         self.focused = focused
//     }
//
//     /// Password fields: value must never be read into the tree, hash, or stats.
//     public var isSecure: Bool { subrole == "AXSecureTextField" || role == "AXSecureTextField" }
// }
//
// public struct NodeRead<Element> {
//     public var attributes: NodeAttributes
//     /// At most `childLimit` children, in document order.
//     public var children: [Element]
//     /// Total children the element reports (may exceed `children.count`).
//     public var totalChildren: Int
//     public var error: NodeReadError?
//
//     public init(attributes: NodeAttributes, children: [Element], totalChildren: Int, error: NodeReadError? = nil) {
//         self.attributes = attributes
//         self.children = children
//         self.totalChildren = totalChildren
//         self.error = error
//     }
// }
//
// public protocol TreeSource {
//     associatedtype Element
//     /// Reads one element. Must return at most `childLimit` children (0 ⇒ none, but still report `totalChildren`).
//     func read(_ element: Element, childLimit: Int) -> NodeRead<Element>
// }
//
// // MARK: - Output model
//
// public struct SnapshotNode: Codable, Sendable, Equatable {
//     public var role: String?
//     public var subrole: String?
//     public var title: String?
//     public var description: String?
//     public var value: String?
//     public var url: String?
//     /// Redacted mode: total characters of text fields instead of the text itself.
//     public var textLength: Int?
//     /// True when any text field was cut to `maxTextLength`.
//     public var textTruncated: Bool?
//     /// Children reported by the element but not included (depth/node/deadline limits).
//     public var omittedChildren: Int?
//     public var error: String?
//     public var children: [SnapshotNode]?
//
//     public init() {}
//
//     enum CodingKeys: String, CodingKey {
//         case role, subrole, title, description, value, url
//         case textLength = "text_length"
//         case textTruncated = "text_truncated"
//         case omittedChildren = "omitted_children"
//         case error, children
//     }
// }
//
// public enum TextMode: String, Sendable, Equatable, CaseIterable {
//     /// Text included (truncated to `maxTextLength`).
//     case full
//     /// Structure only; text replaced by `text_length`.
//     case redacted
// }
//
// public struct WalkLimits: Sendable, Equatable {
//     public var maxDepth: Int
//     public var maxNodes: Int
//     public var maxTextLength: Int
//     public var deadlineMs: Int
//     /// Normalised text at least this long counts as "long text" (proxy for message bodies in stats).
//     public var longTextThreshold: Int
//
//     public init(maxDepth: Int = 12, maxNodes: Int = 5000, maxTextLength: Int = 1000, deadlineMs: Int = 3000, longTextThreshold: Int = 40) {
//         self.maxDepth = maxDepth
//         self.maxNodes = maxNodes
//         self.maxTextLength = maxTextLength
//         self.deadlineMs = deadlineMs
//         self.longTextThreshold = longTextThreshold
//     }
// }
//
// public struct WalkStats: Codable, Sendable, Equatable {
//     public var depthReached = 0
//     public var nodes = 0
//     public var truncated: Bool { !truncatedBy.isEmpty }
//     /// Subset of `depth`, `nodes`, `deadline`.
//     public var truncatedBy: [String] = []
//     public var elapsedMs: Double = 0
//     public var axErrors = 0
//     public var axCannotComplete = 0
//     public var textNodes = 0
//     public var longTextNodes = 0
//     public var firstLongTextDepth: Int?
//     public var firstLongTextNodeIndex: Int?
//     public var maxTextDepth: Int?
//
//     public init() {}
//
//     enum CodingKeys: String, CodingKey {
//         case depthReached = "depth_reached", nodes, truncated
//         case truncatedBy = "truncated_by", elapsedMs = "elapsed_ms"
//         case axErrors = "ax_errors", axCannotComplete = "ax_cannot_complete"
//         case textNodes = "text_nodes", longTextNodes = "long_text_nodes"
//         case firstLongTextDepth = "first_long_text_depth", firstLongTextNodeIndex = "first_long_text_node_index"
//         case maxTextDepth = "max_text_depth"
//     }
//
//     public init(from decoder: any Decoder) throws {
//         let c = try decoder.container(keyedBy: CodingKeys.self)
//         depthReached = try c.decode(Int.self, forKey: .depthReached)
//         nodes = try c.decode(Int.self, forKey: .nodes)
//         truncatedBy = try c.decode([String].self, forKey: .truncatedBy)
//         elapsedMs = try c.decode(Double.self, forKey: .elapsedMs)
//         axErrors = try c.decode(Int.self, forKey: .axErrors)
//         axCannotComplete = try c.decode(Int.self, forKey: .axCannotComplete)
//         textNodes = try c.decode(Int.self, forKey: .textNodes)
//         longTextNodes = try c.decode(Int.self, forKey: .longTextNodes)
//         firstLongTextDepth = try c.decodeIfPresent(Int.self, forKey: .firstLongTextDepth)
//         firstLongTextNodeIndex = try c.decodeIfPresent(Int.self, forKey: .firstLongTextNodeIndex)
//         maxTextDepth = try c.decodeIfPresent(Int.self, forKey: .maxTextDepth)
//     }
//
//     public func encode(to encoder: any Encoder) throws {
//         var c = encoder.container(keyedBy: CodingKeys.self)
//         try c.encode(depthReached, forKey: .depthReached)
//         try c.encode(nodes, forKey: .nodes)
//         try c.encode(truncated, forKey: .truncated)
//         try c.encode(truncatedBy, forKey: .truncatedBy)
//         try c.encode((elapsedMs * 10).rounded() / 10, forKey: .elapsedMs)
//         try c.encode(axErrors, forKey: .axErrors)
//         try c.encode(axCannotComplete, forKey: .axCannotComplete)
//         try c.encode(textNodes, forKey: .textNodes)
//         try c.encode(longTextNodes, forKey: .longTextNodes)
//         try c.encode(firstLongTextDepth, forKey: .firstLongTextDepth)
//         try c.encode(firstLongTextNodeIndex, forKey: .firstLongTextNodeIndex)
//         try c.encode(maxTextDepth, forKey: .maxTextDepth)
//     }
// }
//
// public struct WalkResult: Sendable {
//     public var root: SnapshotNode?
//     public var stats: WalkStats
//     public var treeHash: String
// }
//
// // MARK: - Walker
//
// /// Depth-first, document-order walk with hard depth / node / time limits.
// /// Offscreen text (frame outside the root frame) is kept in the tree but excluded from the hash.
// public struct TreeWalker<Source: TreeSource> {
//     public let source: Source
//     public let limits: WalkLimits
//     public let textMode: TextMode
//     private let now: () -> UInt64
//
//     /// - Parameter now: monotonic clock in nanoseconds (injectable for tests).
//     public init(source: Source, limits: WalkLimits = WalkLimits(), textMode: TextMode = .full,
//                 now: @escaping () -> UInt64 = { DispatchTime.now().uptimeNanoseconds }) {
//         self.source = source
//         self.limits = limits
//         self.textMode = textMode
//         self.now = now
//     }
//
//     public func walk(_ root: Source.Element) -> WalkResult {
//         var state = State(start: now())
//         let node = visit(root, depth: 0, state: &state)
//         state.stats.elapsedMs = Double(now() &- state.start) / 1_000_000
//         state.stats.truncatedBy = ["depth", "nodes", "deadline"].filter { state.truncatedBy.contains($0) }
//         return WalkResult(root: node, stats: state.stats, treeHash: state.hasher.finalize())
//     }
//
//     private struct State {
//         let start: UInt64
//         var stats = WalkStats()
//         var hasher = TreeHasher()
//         var truncatedBy = Set<String>()
//         var visibleRect: CGRect?
//     }
//
//     private func visit(_ element: Source.Element, depth: Int, state: inout State) -> SnapshotNode? {
//         if state.stats.nodes >= limits.maxNodes {
//             state.truncatedBy.insert("nodes")
//             return nil
//         }
//         if limits.deadlineMs > 0, now() &- state.start > UInt64(limits.deadlineMs) * 1_000_000 {
//             state.truncatedBy.insert("deadline")
//             return nil
//         }
//         let remaining = limits.maxNodes - state.stats.nodes - 1
//         let childLimit = depth < limits.maxDepth ? max(0, remaining) : 0
//         let read = source.read(element, childLimit: childLimit)
//         let nodeIndex = state.stats.nodes
//         state.stats.nodes += 1
//         state.stats.depthReached = max(state.stats.depthReached, depth)
//
//         var node = SnapshotNode()
//         if let err = read.error {
//             state.stats.axErrors += 1
//             if err == .cannotComplete { state.stats.axCannotComplete += 1 }
//             node.error = err.code
//         }
//
//         var a = read.attributes
//         if a.isSecure { a.value = nil }
//         if depth == 0 { state.visibleRect = a.frame.flatMap { $0.width > 0 && $0.height > 0 ? $0 : nil } }
//         node.role = a.role
//         node.subrole = a.subrole
//
//         let fields = [a.title, a.description, a.value].map { $0.flatMap { $0.isEmpty ? nil : $0 } }
//         let textChars = fields.reduce(0) { $0 + ($1?.count ?? 0) }
//         if textChars > 0 {
//             state.stats.textNodes += 1
//             state.stats.maxTextDepth = max(state.stats.maxTextDepth ?? 0, depth)
//             let visible = isVisible(a.frame, in: state.visibleRect)
//             var longest = 0
//             for f in fields.compactMap({ $0 }) {
//                 if visible { state.hasher.add(f) }
//                 longest = max(longest, TextNormalizer.normalize(f).count)
//             }
//             if longest >= limits.longTextThreshold {
//                 state.stats.longTextNodes += 1
//                 if state.stats.firstLongTextDepth == nil {
//                     state.stats.firstLongTextDepth = depth
//                     state.stats.firstLongTextNodeIndex = nodeIndex
//                 }
//             }
//         }
//
//         switch textMode {
//         case .full:
//             var cut = false
//             node.title = truncate(fields[0], &cut)
//             node.description = truncate(fields[1], &cut)
//             node.value = truncate(fields[2], &cut)
//             node.url = a.url.map(URLNormalizer.stripTracking)
//             if cut { node.textTruncated = true }
//         case .redacted:
//             if textChars > 0 { node.textLength = textChars }
//         }
//
//         if read.totalChildren > 0 && depth >= limits.maxDepth {
//             state.truncatedBy.insert("depth")
//             node.omittedChildren = read.totalChildren
//             return node
//         }
//         var children: [SnapshotNode] = []
//         for child in read.children {
//             guard let c = visit(child, depth: depth + 1, state: &state) else { break }
//             children.append(c)
//         }
//         if read.totalChildren > children.count {
//             if read.children.count < read.totalChildren { state.truncatedBy.insert("nodes") }
//             node.omittedChildren = read.totalChildren - children.count
//         }
//         if !children.isEmpty { node.children = children }
//         return node
//     }
//
//     private func truncate(_ s: String?, _ cut: inout Bool) -> String? {
//         guard let s else { return nil }
//         guard s.count > limits.maxTextLength else { return s }
//         cut = true
//         return String(s.prefix(limits.maxTextLength)) + "…"
//     }
//
//     private func isVisible(_ frame: CGRect?, in rect: CGRect?) -> Bool {
//         guard let frame, let rect, frame.width > 0, frame.height > 0 else { return true }
//         return frame.intersects(rect)
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Sources/GeniosAXCore/URLNormalizer.swift`

```swift
// import Foundation
//
// /// Strips click/campaign tracking parameters from URLs. Keeps the fragment (Gmail thread ids
// /// live there) and every non-tracking query item, preserving their original encoding.
// public enum URLNormalizer {
//     static let exactParams: Set<String> = [
//         "fbclid", "gclid", "dclid", "gbraid", "wbraid", "msclkid", "yclid", "twclid", "ttclid",
//         "igshid", "igsh", "si", "mkt_tok", "_ga", "_gl", "spm", "vero_id", "s_cid", "ref_src", "ref_url",
//         // LinkedIn
//         "trk", "trkinfo", "trackingid", "lipi", "midtoken", "midsig", "eid", "otptoken",
//     ]
//     static let prefixParams = ["utm_", "mc_", "_hs", "hsa_", "pk_", "oly_", "matomo_"]
//
//     public static func isTrackingParam(_ name: String) -> Bool {
//         let n = name.lowercased()
//         return exactParams.contains(n) || prefixParams.contains(where: { n.hasPrefix($0) })
//     }
//
//     /// Returns `url` without tracking params and with a lower-cased host. Non-URLs and URLs
//     /// without tracking params are returned unchanged (byte-for-byte).
//     public static func stripTracking(_ url: String) -> String {
//         guard var c = URLComponents(string: url), c.scheme != nil, c.host != nil else { return url }
//         let hostNeedsLowering = c.host.map { $0 != $0.lowercased() } ?? false
//         let items = c.percentEncodedQueryItems ?? []
//         let kept = items.filter { !isTrackingParam($0.name) }
//         guard kept.count != items.count || hostNeedsLowering else { return url }
//         c.percentEncodedQueryItems = kept.isEmpty ? nil : kept
//         if hostNeedsLowering { c.host = c.host?.lowercased() }
//         return c.string ?? url
//     }
//
//     private static let urlInText = try! NSRegularExpression(
//         pattern: #"https?://[^\s<>"'`]+"#, options: [.caseInsensitive])
//     private static let trailingPunctuation: Set<Character> = [".", ",", ";", ":", "!", "?", ")", "]", "}"]
//
//     /// Applies `stripTracking` to every http(s) URL embedded in free text.
//     public static func stripTrackingInText(_ text: String) -> String {
//         guard text.contains("://") else { return text }
//         let ns = text as NSString
//         let matches = urlInText.matches(in: text, range: NSRange(location: 0, length: ns.length))
//         guard !matches.isEmpty else { return text }
//         var out = ""
//         var cursor = 0
//         for m in matches {
//             out += ns.substring(with: NSRange(location: cursor, length: m.range.location - cursor))
//             var raw = ns.substring(with: m.range)
//             var tail = ""
//             while let last = raw.last, trailingPunctuation.contains(last) {
//                 tail = String(last) + tail
//                 raw.removeLast()
//             }
//             out += stripTracking(raw) + tail
//             cursor = m.range.location + m.range.length
//         }
//         out += ns.substring(from: cursor)
//         return out
//     }
// }
```

## 4 · Tests and measuring

Swift tests, the reader check and the measuring scripts.

#### `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/EventEncodingTests.swift`

```swift
// import Foundation
// import Testing
// @testable import GeniosAXCore
//
// @Suite("NDJSON event encoding")
// struct EventEncodingTests {
//     let fixed = Date(timeIntervalSince1970: 1_789_216_272.345)  // 2026-09-12T12:31:12.345Z
//
//     func decode(_ data: Data) throws -> [String: Any] {
//         try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
//     }
//
//     @Test func singleLineTerminatedByNewline() throws {
//         let e = CaptureEvent(ts: fixed, kind: .titleChanged, bundleID: "com.example.chat", pid: 42,
//                              appName: "Chat", windowTitle: "Line one\nLine two\r\u{2028}", url: "https://x.test/a/b")
//         let data = try NDJSON.line(e)
//         #expect(data.last == 0x0A)
//         #expect(data.dropLast().contains(0x0A) == false)
//         #expect(data.dropLast().contains(0x0D) == false)
//         let obj = try decode(data)
//         #expect(obj["window_title"] as? String == "Line one\nLine two\r\u{2028}")
//         #expect(String(decoding: data, as: UTF8.self).contains("https://x.test/a/b"))  // slashes unescaped
//     }
//
//     @Test func fixedSchemaAllKeysPresent() throws {
//         let obj = try decode(NDJSON.line(CaptureEvent(ts: fixed, kind: .idleStart)))
//         let expected: Set = ["schema_version", "ts", "kind", "bundle_id", "pid", "app_name",
//                              "window_title", "url", "focused_role"]
//         #expect(Set(obj.keys) == expected)
//         #expect(obj["schema_version"] as? Int == 1)
//         #expect(obj["kind"] as? String == "idle_start")
//         #expect(obj["bundle_id"] is NSNull)
//         #expect(obj["pid"] is NSNull)
//     }
//
//     @Test func timestampIsUTCMillis() throws {
//         #expect(Timestamp.format(fixed) == "2026-09-12T12:31:12.345Z")
//     }
//
//     @Test func detailOnlyWhenPresent() throws {
//         let obj = try decode(NDJSON.line(CaptureEvent(ts: fixed, kind: .observerError, detail: ["ax_err": "-25204"])))
//         #expect((obj["detail"] as? [String: String])?["ax_err"] == "-25204")
//     }
//
//     @Test func deterministicKeyOrder() throws {
//         let e = CaptureEvent(ts: fixed, kind: .appActivated, bundleID: "b", pid: 1, appName: "A")
//         #expect(try NDJSON.line(e) == NDJSON.line(e))
//         let s = String(decoding: try NDJSON.line(e), as: UTF8.self)
//         #expect(s.hasPrefix(#"{"app_name":"A","bundle_id":"b""#))
//     }
//
//     @Test func kindRawValuesAreSnakeCase() {
//         for k in EventKind.allCases {
//             #expect(k.rawValue == k.rawValue.lowercased())
//             #expect(!k.rawValue.contains(" "))
//         }
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/GenericReaderTests.swift`

```swift
// import CoreGraphics
// import Foundation
// import Testing
// @testable import GeniosAXCore
//
// // Synthetic trees only (no AX, no real content). Shapes follow standard macOS / Chromium AX roles;
// // no app-specific selectors.
//
// func ax(_ role: String, _ kids: [FakeNode] = [], sub: String? = nil, title: String? = nil, desc: String? = nil,
//         value: String? = nil, url: String? = nil, frame: CGRect? = nil, titleUI: String? = nil,
//         focused: Bool = false, placeholder: String? = nil) -> FakeNode {
//     FakeNode(NodeAttributes(role: role, subrole: sub, title: title, description: desc, value: value, url: url,
//                             frame: frame, placeholder: placeholder, titleUIText: titleUI, focused: focused), kids)
// }
//
// func txt(_ s: String, _ frame: CGRect? = nil) -> FakeNode { ax("AXStaticText", value: s, frame: frame) }
// func R(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> CGRect { CGRect(x: x, y: y, width: w, height: h) }
//
// let fixedNow = Date(timeIntervalSince1970: 1_789_622_523)  // 2026-09-17T05:22:03Z
//
// func readDoc(_ tree: FakeNode, bundle: String = "com.google.Chrome", url: String? = nil, title: String? = nil,
//              draft: Bool = false, limits: WalkLimits = ReadOptions.defaultLimits,
//              clock: @escaping () -> UInt64 = { 0 }) -> ScreenDoc {
//     let cap = ReaderCapture(source: FakeSource(), limits: limits, now: clock).capture(tree)
//     let ctx = ReadContext(bundleID: bundle, url: url, windowTitle: title, draft: draft, now: fixedNow)
//     return ScreenReaderEngine.read(cap, ctx, dedicated: []).doc!
// }
//
// func json(_ d: ScreenDoc, redact: Bool = false) -> String {
//     String(decoding: try! ScreenReaderEngine.encode(ReaderOutput(reader: "generic", line: d), redact: redact), as: UTF8.self)
// }
//
// /// CRM record page in Chrome: toolbar (address bar) + page with heading, kv in 5 shapes, a table.
// func crmPage(stage: String = "Negotiation") -> FakeNode {
//     ax("AXWindow", [
//         ax("AXToolbar", [ax("AXTextField", value: "crm.example.com/deals/42"), ax("AXButton", title: "Reload")]),
//         ax("AXGroup", [ax("AXWebArea", [
//             ax("AXHeading", [txt("Acme renewal")]),
//             ax("AXGroup", [txt("Owner", R(20, 140, 80, 20)), txt("Priya Shah", R(200, 140, 120, 20))]),
//             ax("AXGroup", [txt("Stage"), ax("AXPopUpButton", value: stage)]),
//             ax("AXGroup", [txt("Amount"), ax("AXTextField", value: "₹5L", titleUI: "Amount")]),
//             ax("AXTextField", desc: "Email", value: "priya@acme.example"),
//             ax("AXList", [ax("AXGroup", [txt("Close date")], sub: "AXTerm"),
//                           ax("AXGroup", [txt("2026-09-30")], sub: "AXDefinition")], sub: "AXDescriptionList"),
//             ax("AXTable", [
//                 ax("AXRow", [ax("AXCell", [txt("Invoice")]), ax("AXCell", [txt("Due")]), ax("AXCell", [txt("Status")])]),
//                 ax("AXRow", [ax("AXCell", [txt("INV-9")]), ax("AXCell", [txt("2026-09-20")]), ax("AXCell", [txt("Unpaid")])]),
//                 ax("AXRow", [ax("AXCell", [txt("INV-10")]), ax("AXCell", [txt("2026-10-20")]),
//                              ax("AXCell", [txt("Paid"), ax("AXButton", title: "Edit")])]),
//                 ax("AXColumn", [ax("AXCell", [txt("Invoice")])]),
//             ]),
//             ax("AXButton", title: "Save"),
//             ax("AXGroup", [txt("Renewal is due at the end of the quarter. "), ax("AXLink", [txt("See contract")], title: "See contract"), txt(".")]),
//         ], url: "https://crm.example.com/deals/42?utm_source=mail", frame: R(0, 80, 1200, 720))]),
//     ], title: "Acme — Deal", frame: R(0, 0, 1200, 800))
// }
//
// /// Native chat app: 2 incoming (left), 2 outgoing (right), a centred day separator, a focused composer.
// func chatWindow(draftText: String = "draft reply here", stamp: String = "10:42 AM") -> FakeNode {
//     ax("AXWindow", [
//         ax("AXGroup", [txt("Chats")]),
//         ax("AXScrollArea", [ax("AXGroup", [
//             ax("AXGroup", [ax("AXGroup", [txt("Priya"), txt("Can we close this week?"), txt(stamp)], frame: R(310, 10, 300, 60))]),
//             ax("AXGroup", [txt("Priya"), txt("Sending the order form"), txt("10:43 AM")], frame: R(310, 80, 300, 40)),
//             ax("AXGroup", [txt("Yes, today works"), txt("10:45 AM")], frame: R(620, 130, 370, 40)),
//             ax("AXStaticText", value: "Today", frame: R(600, 200, 100, 20)),
//             ax("AXGroup", [txt("Will send by 5 pm"), txt("10:46 AM ✓✓")], frame: R(620, 230, 370, 40)),
//         ], frame: R(300, 0, 700, 700))], frame: R(300, 0, 700, 700)),
//         ax("AXTextArea", value: draftText, frame: R(300, 720, 700, 60), focused: true, placeholder: "Type a message"),
//     ], title: "Team chat", frame: R(0, 0, 1000, 800))
// }
//
// @Suite("Generic reader → screen_doc")
// struct GenericReaderTests {
//     @Test func crmRecordPageKvAndTable() {
//         let d = readDoc(crmPage(), title: "Acme — Deal")
//         #expect(d.url == "https://crm.example.com/deals/42")
//         #expect(d.threadKey == "doc:com.google.Chrome:crm.example.com/deals/42")
//         #expect(d.blocks.map(\.role) == [.heading, .kv, .kv, .kv, .kv, .kv, .table, .paragraph])
//         #expect(d.blocks[0].text == "Acme renewal")
//         let kv = d.blocks.filter { $0.role == .kv }.map { "\($0.label!)=\($0.value!)" }
//         #expect(kv == ["Owner=Priya Shah", "Stage=Negotiation", "Amount=₹5L", "Email=priya@acme.example", "Close date=2026-09-30"])
//         let t = d.blocks[6]
//         #expect(t.header == ["Invoice", "Due", "Status"])
//         #expect(t.rows == [["INV-9", "2026-09-20", "Unpaid"], ["INV-10", "2026-10-20", "Paid"]])
//         #expect(d.blocks[7].text == "Renewal is due at the end of the quarter. See contract.")
//         let j = json(d)
//         #expect(!j.contains("Reload") && !j.contains("Save") && !j.contains("\"Edit\""))  // controls, browser chrome
//         #expect(j.contains("\"focused_field\":null") && j.contains("\"kind\":\"screen_doc\"") && j.contains("\"app\":\"generic\""))
//         #expect(d.blocks.allSatisfy { $0.fp.hasPrefix("sha256:") })
//         #expect(!d.stats.axEmpty && d.stats.blockCounts["kv"] == 5)
//     }
//
//     @Test func chatMessagesIncomingVsOutgoing() {
//         let d = readDoc(chatWindow(), bundle: "com.example.chat", title: "Team chat")
//         let m = d.blocks.filter { $0.role == .message }
//         #expect(m.count == 4)
//         #expect(m.map(\.isOutgoing) == [false, false, true, true])
//         #expect(m[0].sender == "Priya" && m[0].text == "Can we close this week?" && m[0].tsLabel == "10:42 AM")
//         #expect(m.allSatisfy { $0.ts == nil })
//         let j = json(d)
//         #expect(j.contains("\"ts\":null") && j.contains("\"ts_label\":\"10:42 AM\""))
//         #expect(m[2].sender == nil && m[2].text == "Yes, today works")
//         #expect(m[3].tsLabel == "10:46 AM ✓✓")
//         #expect(d.threadKey == "doc:com.example.chat:title:team chat")
//         #expect(d.url == nil)
//     }
//
//     @Test func focusedComposerOnlyWithDraft() {
//         let off = readDoc(chatWindow(), bundle: "com.example.chat")
//         #expect(off.focusedField == nil)
//         #expect(!off.blocks.contains { $0.role == .field })
//         #expect(!json(off).contains("draft reply here"))
//
//         let on = readDoc(chatWindow(), bundle: "com.example.chat", draft: true)
//         #expect(on.focusedField == FocusedField(label: "Type a message", value: "draft reply here", role: "AXTextArea"))
//         #expect(on.blocks.contains { $0.role == .field && $0.value == "draft reply here" })
//     }
//
//     @Test func docPageHeadingsAndParagraphsInReadingOrder() {
//         let tree = ax("AXWindow", [ax("AXWebArea", [
//             ax("AXHeading", [txt("Q3 plan")]),
//             ax("AXGroup", [txt("We will ship "), ax("AXLink", [txt("the lane")]), txt(" by October.")]),
//             ax("AXHeading", [txt("Risks")]),
//             txt("Hiring is slow.", R(20, 300, 200, 20)),
//             txt("Budget is fixed.", R(20, 330, 200, 20)),
//             txt("Offscreen tail", R(20, 5000, 200, 20)),
//         ], url: "https://docs.example.com/q3/")], title: "Q3 plan", frame: R(0, 0, 1000, 800))
//         let d = readDoc(tree, bundle: "com.apple.Safari")
//         #expect(d.blocks.map(\.role) == [.heading, .paragraph, .heading, .paragraph, .paragraph])
//         #expect(d.blocks.compactMap(\.text) == ["Q3 plan", "We will ship the lane by October.", "Risks", "Hiring is slow.", "Budget is fixed."])
//         #expect(!json(d).contains("Offscreen"))
//         #expect(d.threadKey == "doc:com.apple.Safari:docs.example.com/q3")
//     }
//
//     @Test func secureFieldAlwaysDropped() {
//         let tree = ax("AXWindow", [ax("AXGroup", [
//             txt("Password"),
//             ax("AXTextField", sub: "AXSecureTextField", value: "synthetic-secret", titleUI: "Password", focused: true, placeholder: "pw"),
//         ])], frame: R(0, 0, 800, 600))
//         for draft in [false, true] {
//             let d = readDoc(tree, bundle: "com.example.app", title: "Sign in", draft: draft)
//             let j = json(d)
//             #expect(!j.contains("synthetic-secret"))
//             #expect(d.focusedField == nil)
//             #expect(!d.blocks.contains { $0.role == .kv || $0.role == .field })
//         }
//     }
//
//     @Test func capsRespected() {
//         // 300-row table → 200 rows.
//         let rows = (0..<300).map { i in ax("AXRow", [ax("AXCell", [txt("r\(i)")])]) }
//         let t = readDoc(ax("AXWindow", [ax("AXTable", [ax("AXRow", [ax("AXCell", [txt("H")])])] + rows)]), bundle: "com.example.app", title: "T",
//                         limits: WalkLimits(maxDepth: 12, maxNodes: 5000, maxTextLength: 30_000, deadlineMs: 0))
//         #expect(t.blocks[0].rows?.count == 200)
//         #expect(t.stats.cappedBy.contains("rows"))
//
//         // 50 × 1 000-char paragraphs → ≤ 30k chars.
//         let paras = (0..<50).map { i in ax("AXGroup", [txt(String(format: "%03d", i) + String(repeating: "x", count: 997))]) }
//         let p = readDoc(ax("AXWindow", paras), bundle: "com.example.app", title: "P")
//         #expect(p.stats.chars == 30_000)
//         #expect(p.blocks.count == 30)
//         #expect(p.stats.cappedBy == ["chars"])
//
//         // Node / depth / deadline limits of the capture.
//         let wide = ax("AXWindow", (0..<100).map { i in ax("AXGroup", (0..<100).map { j in txt("m\(i)-\(j)") }) })
//         let w = readDoc(wide, bundle: "com.example.app", title: "W", limits: WalkLimits(maxDepth: 12, maxNodes: 5000, maxTextLength: 30_000, deadlineMs: 0))
//         #expect(w.stats.walk.nodes == 5000 && w.stats.walk.truncatedBy == ["nodes"])
//         let deep = readDoc(chain(20), bundle: "com.example.app", title: "D")
//         #expect(deep.stats.walk.depthReached == 12 && deep.stats.walk.truncatedBy == ["depth"])
//         var clock: UInt64 = 0
//         let slow = readDoc(wide, bundle: "com.example.app", title: "S", clock: { clock += 1_000_000; return clock })
//         #expect(slow.stats.walk.truncatedBy == ["deadline"] && slow.stats.walk.nodes <= 401)  // +1 ms per node ⇒ ~400 nodes in 400 ms
//     }
//
//     @Test func treeHashStable() {
//         let a = readDoc(crmPage(), title: "Acme — Deal")
//         let b = readDoc(crmPage(), title: "Acme — Deal")
//         #expect(a.treeHash == b.treeHash && a.treeHash.hasPrefix("sha256:"))
//         #expect(a.blocks.map(\.fp) == b.blocks.map(\.fp))
//         #expect(readDoc(crmPage(stage: "Closed won")).treeHash != a.treeHash)
//         // Relative-time churn does not change the hash; the composer value does not either without --draft.
//         let c1 = readDoc(chatWindow(draftText: "a", stamp: "5 min ago"), bundle: "com.example.chat")
//         let c2 = readDoc(chatWindow(draftText: "b", stamp: "6 min ago"), bundle: "com.example.chat")
//         #expect(c1.treeHash == c2.treeHash)
//     }
//
//     @Test func redactedKeepsStructureOnly() {
//         let j = json(readDoc(crmPage(), title: "Acme — Deal"), redact: true)
//         for leak in ["Negotiation", "Acme", "INV-9", "Priya", "deals/42", "sha256:"] where leak != "sha256:" || j.contains("\"fp\"") {
//             #expect(!j.contains(leak), "leaked \(leak)")
//         }
//         #expect(j.contains("\"role\":\"kv\"") && j.contains("\"url\":\"https://crm.example.com\""))
//         #expect(j.contains("\"thread_key\":\"doc:com.google.Chrome:crm.example.com\""))
//     }
//
//     @Test func dedicatedReaderHookDispatches() {
//         struct Line: ReaderLine { var kind = "thread_read"; func redacted() -> Line { self } }
//         struct Fake: DedicatedReader {
//             let id = "fake-gmail"
//             func accepts(_ ctx: ReadContext) -> Bool { ctx.url?.contains("mail.example.com") == true }
//             func read(_ root: RNode, _ ctx: ReadContext) -> (any ReaderLine)? { Line() }
//         }
//         let cap = ReaderCapture(source: FakeSource()).capture(crmPage())
//         let hit = ScreenReaderEngine.read(cap, ReadContext(bundleID: "com.google.Chrome", url: "https://mail.example.com/x"), dedicated: [Fake()])
//         #expect(hit.reader == "fake-gmail" && hit.doc == nil)
//         let miss = ScreenReaderEngine.read(cap, ReadContext(bundleID: "com.google.Chrome"), dedicated: [Fake()])
//         #expect(miss.reader == "generic" && miss.doc != nil)
//         #expect(ReaderRegistry.dedicated.map(\.id) == ["whatsapp"])   // native WhatsApp ships first
//     }
//
//     @Test func parseRead() throws {
//         guard case .read(let o) = try CLI.parse(["read", "--bundle", "com.google.Chrome", "--draft", "--pretty"]) else {
//             Issue.record("wrong command"); return
//         }
//         #expect(o.target == .bundle("com.google.Chrome") && o.draft && o.pretty && !o.redact)
//         guard case .read(let d) = try CLI.parse(["read"]) else { Issue.record("wrong command"); return }
//         #expect(d.target == .frontmost && !d.draft)
//         #expect(d.limits.maxDepth == 12 && d.limits.maxNodes == 5000 && d.limits.deadlineMs == 400)
//         #expect(throws: CLIError.self) { try CLI.parse(["read", "--pid", "1", "--frontmost"]) }
//         #expect(throws: CLIError.self) { try CLI.parse(["read", "--bogus"]) }
//     }
//
//     /// Cross-language contract: the Rust core parses this exact file (thread_source.rs tests).
//     /// Regenerate with GENIOS_AX_WRITE_GOLDEN=1.
//     @Test func goldenLineSharedWithRustCore() throws {
//         let line = json(readDoc(crmPage(), title: "Acme — Deal", draft: true)) + "\n"
//         var dir = URL(fileURLWithPath: #filePath)
//         for _ in 0..<5 { dir.deleteLastPathComponent() }
//         let file = dir.appendingPathComponent("tests/fixtures/screen_docs/sidecar_crm_read.json")
//         if ProcessInfo.processInfo.environment["GENIOS_AX_WRITE_GOLDEN"] == "1" {
//             try line.write(to: file, atomically: true, encoding: .utf8)
//         }
//         #expect(try String(contentsOf: file, encoding: .utf8) == line)
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/NormalizationTests.swift`

```swift
// import Testing
// @testable import GeniosAXCore
//
// // All fixtures are synthetic.
// @Suite("Text + URL normalisation and tree hash")
// struct NormalizationTests {
//     let t = TextNormalizer.relativeTimeToken
//
//     @Test(arguments: [
//         "5 min ago", "2 hours ago", "an hour ago", "a few seconds ago", "about 3 weeks ago",
//         "1 day ago", "10m ago", "just now", "Just now", "moments ago", "Yesterday", "today",
//         "3h", "2d", "1w", "4mo", "in 5 min", "in an hour",
//     ])
//     func relativeTimesCollapse(_ phrase: String) {
//         #expect(TextNormalizer.normalize(phrase) == t)
//         #expect(TextNormalizer.normalize("Sent \(phrase) by Alex") == "Sent \(t) by Alex")
//     }
//
//     @Test func absoluteTimesAndNumbersKept() {
//         #expect(TextNormalizer.normalize("Meeting at 10:30 AM") == "Meeting at 10:30 AM")
//         #expect(TextNormalizer.normalize("Budget $5m approved") == "Budget $5m approved")
//         #expect(TextNormalizer.normalize("Order 12345") == "Order 12345")
//         #expect(TextNormalizer.normalize("v2.3d build") == "v2.3d build")
//     }
//
//     @Test func whitespaceAndInvisibleMarks() {
//         #expect(TextNormalizer.normalize("  a\u{00A0}\u{00A0}b\n\tc\u{200E} ") == "a b c")
//         #expect(TextNormalizer.normalize("\u{200F}Priya\u{200F}: hi") == "Priya: hi")
//         #expect(TextNormalizer.normalize("10:30\u{202F}PM") == "10:30 PM")
//         #expect(TextNormalizer.normalize("Cafe\u{0301}") == "Café")  // NFC
//     }
//
//     @Test func trackingParamsStripped() {
//         #expect(URLNormalizer.stripTracking("https://Example.COM/p?id=7&utm_source=x&utm_medium=y&fbclid=abc")
//                 == "https://example.com/p?id=7")
//         #expect(URLNormalizer.stripTracking("https://www.linkedin.com/in/someone?trk=feed&lipi=zz&trackingId=q")
//                 == "https://www.linkedin.com/in/someone")
//         #expect(URLNormalizer.stripTracking("https://x.test/a?gclid=1#frag") == "https://x.test/a#frag")
//     }
//
//     @Test func nonTrackingURLsUntouched() {
//         let gmail = "https://mail.google.com/mail/u/0/#inbox/FMfcgzSYNTHETIC"
//         #expect(URLNormalizer.stripTracking(gmail) == gmail)
//         let enc = "https://x.test/s?q=a%20b&page=2"
//         #expect(URLNormalizer.stripTracking(enc) == enc)
//         #expect(URLNormalizer.stripTracking("not a url") == "not a url")
//     }
//
//     @Test func trackingStrippedInsideText() {
//         let s = "see https://x.test/a?ref=ok&utm_campaign=z. thanks"
//         #expect(URLNormalizer.stripTrackingInText(s) == "see https://x.test/a?ref=ok. thanks")
//         #expect(TextNormalizer.normalize("(https://x.test/?utm_source=a)") == "(https://x.test/)")
//     }
//
//     @Test func addressBarValues() {
//         #expect(AppCatalog.urlFromAddressBar("mail.google.com/mail/u/0/") == "https://mail.google.com/mail/u/0/")
//         #expect(AppCatalog.urlFromAddressBar("https://a.test/?utm_source=q") == "https://a.test/")
//         #expect(AppCatalog.urlFromAddressBar("how to write swift") == nil)
//         #expect(AppCatalog.urlFromAddressBar("") == nil)
//     }
//
//     @Test func treeHashIgnoresCosmeticChurn() {
//         let a = TreeHasher.hash(["Alex", "5 min ago", "Lunch at noon? https://x.test/m?utm_source=a", ""])
//         let b = TreeHasher.hash(["Alex ", "12 min ago", "Lunch  at noon? https://x.test/m", "   "])
//         #expect(a == b)
//         #expect(a.count == 64)
//     }
//
//     @Test func treeHashSeesRealChanges() {
//         let base = TreeHasher.hash(["Alex", "Lunch at noon?"])
//         #expect(base != TreeHasher.hash(["Alex", "Lunch at one?"]))
//         #expect(base != TreeHasher.hash(["Lunch at noon?", "Alex"]))  // order matters
//         #expect(TreeHasher.hash(["ab", "c"]) != TreeHasher.hash(["a", "bc"]))  // fragment boundaries matter
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/PacingAndCLITests.swift`

```swift
// import Testing
// @testable import GeniosAXCore
//
// @Suite("Throttle, idle, backoff, CLI")
// struct PacingAndCLITests {
//     @Test func throttleLeadingThenSingleTrailing() {
//         var t = Throttle(minInterval: 1.0)
//         #expect(t.offer(now: 10.0) == .emitNow)
//         #expect(t.offer(now: 10.2) == .scheduleTrailing(at: 11.0))
//         #expect(t.offer(now: 10.5) == .coalesced)
//         t.fireTrailing(now: 11.0)
//         #expect(t.offer(now: 11.5) == .scheduleTrailing(at: 12.0))
//         t.fireTrailing(now: 12.0)
//         #expect(t.offer(now: 13.1) == .emitNow)
//     }
//
//     @Test func idleTransitionsOnce() {
//         var d = IdleDetector(threshold: 120)
//         #expect(d.update(secondsSinceInput: 5) == nil)
//         #expect(d.update(secondsSinceInput: 120) == .becameIdle)
//         #expect(d.update(secondsSinceInput: 300) == nil)
//         #expect(d.update(secondsSinceInput: 1) == .becameActive)
//         #expect(d.update(secondsSinceInput: 2) == nil)
//     }
//
//     @Test func backoffDoublesAndCaps() {
//         var b = Backoff(base: 0.5, cap: 30)
//         #expect(b.recordFailure(7, now: 0) == 0.5)
//         #expect(!b.canAttempt(7, now: 0.4))
//         #expect(b.canAttempt(7, now: 0.5))
//         #expect(b.recordFailure(7, now: 1) == 1.0)
//         #expect(b.recordFailure(7, now: 2) == 2.0)
//         for _ in 0..<10 { b.recordFailure(7, now: 3) }
//         #expect(b.delay(forFailureCount: b.failureCount(7)) == 30)
//         b.recordSuccess(7)
//         #expect(b.canAttempt(7, now: 3))
//         #expect(b.canAttempt(8, now: 0))
//     }
//
//     @Test func parseSnapshot() throws {
//         let c = try CLI.parse(["snapshot", "--pid", "123", "--max-depth", "8", "--max-nodes", "2000", "--stats-only"])
//         guard case .snapshot(let o) = c else { Issue.record("wrong command"); return }
//         #expect(o.target == .pid(123))
//         #expect(o.limits.maxDepth == 8)
//         #expect(o.limits.maxNodes == 2000)
//         #expect(o.statsOnly && o.textMode == .redacted)
//     }
//
//     @Test func parseDefaultsMatchPlan() throws {
//         guard case .snapshot(let o) = try CLI.parse(["snapshot"]) else { Issue.record("wrong command"); return }
//         #expect(o.target == .frontmost)
//         #expect(o.limits.maxDepth == 12 && o.limits.maxNodes == 5000)
//         guard case .watch(let w) = try CLI.parse(["watch"]) else { Issue.record("wrong command"); return }
//         #expect(w.idleThreshold == 120 && !w.allowUntrusted)
//         #expect(AX.messagingTimeout == 0.4)
//     }
//
//     @Test func parseErrors() throws {
//         #expect(throws: CLIError.self) { try CLI.parse(["snapshot", "--pid"]) }
//         #expect(throws: CLIError.self) { try CLI.parse(["snapshot", "--pid", "1", "--frontmost"]) }
//         #expect(throws: CLIError.self) { try CLI.parse(["snapshot", "--max-depth", "999"]) }
//         #expect(throws: CLIError.self) { try CLI.parse(["bogus"]) }
//         #expect(try CLI.parse([]) == .help)
//         #expect(try CLI.parse(["trust", "--prompt"]) == .trust(prompt: true))
//     }
//
//     @Test func chromiumTargets() {
//         #expect(AppCatalog.needsManualAccessibility("com.google.Chrome"))
//         #expect(AppCatalog.needsManualAccessibility("com.tinyspeck.slackmacgap"))
//         #expect(!AppCatalog.needsManualAccessibility("com.apple.Safari"))
//         #expect(!AppCatalog.allowsEnhancedUIFallback("com.tinyspeck.slackmacgap"))
//         #expect(AppCatalog.isBrowser("com.apple.Safari") && !AppCatalog.isBrowser("net.whatsapp.WhatsApp"))
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/TreeWalkerTests.swift`

```swift
// import CoreGraphics
// import Testing
// @testable import GeniosAXCore
//
// /// Synthetic in-memory tree (no AX, no real content).
// final class FakeNode {
//     var attrs: NodeAttributes
//     var children: [FakeNode]
//     var error: NodeReadError?
//     init(_ attrs: NodeAttributes = NodeAttributes(role: "AXGroup"), _ children: [FakeNode] = [], error: NodeReadError? = nil) {
//         self.attrs = attrs
//         self.children = children
//         self.error = error
//     }
// }
//
// final class FakeSource: TreeSource {
//     var reads = 0
//     var maxChildLimitSeen = 0
//     var valueReadsOfSecure = 0
//     func read(_ e: FakeNode, childLimit: Int) -> NodeRead<FakeNode> {
//         reads += 1
//         maxChildLimitSeen = max(maxChildLimitSeen, childLimit)
//         return NodeRead(attributes: e.attrs, children: Array(e.children.prefix(childLimit)),
//                         totalChildren: e.children.count, error: e.error)
//     }
// }
//
// func chain(_ depth: Int) -> FakeNode {
//     var n = FakeNode(NodeAttributes(role: "AXStaticText", value: "leaf"))
//     for _ in 0..<depth { n = FakeNode(NodeAttributes(role: "AXGroup"), [n]) }
//     return n
// }
//
// @Suite("Tree walker limits")
// struct TreeWalkerTests {
//     @Test func depthLimitEnforced() {
//         let src = FakeSource()
//         let r = TreeWalker(source: src, limits: WalkLimits(maxDepth: 12)).walk(chain(20))
//         #expect(r.stats.depthReached == 12)
//         #expect(r.stats.nodes == 13)
//         #expect(r.stats.truncatedBy == ["depth"])
//         #expect(r.stats.truncated)
//         #expect(src.reads == 13)
//     }
//
//     @Test func nodeLimitEnforcedOnWideTree() {
//         let wide = FakeNode(NodeAttributes(role: "AXWindow"),
//                             (0..<100).map { i in FakeNode(NodeAttributes(role: "AXGroup"),
//                                 (0..<100).map { j in FakeNode(NodeAttributes(role: "AXStaticText", value: "m\(i)-\(j)")) }) })
//         let src = FakeSource()
//         let r = TreeWalker(source: src, limits: WalkLimits(maxNodes: 5000)).walk(wide)
//         #expect(r.stats.nodes == 5000)
//         #expect(src.reads == 5000)
//         #expect(r.stats.truncatedBy == ["nodes"])
//         #expect(src.maxChildLimitSeen <= 4999)
//         #expect((r.root?.omittedChildren ?? 0) > 0)
//     }
//
//     @Test func smallTreeNotTruncated() {
//         let tree = FakeNode(NodeAttributes(role: "AXWindow", title: "W"), [
//             FakeNode(NodeAttributes(role: "AXStaticText", value: "hello there")),
//             FakeNode(NodeAttributes(role: "AXButton", description: "Send")),
//         ])
//         let r = TreeWalker(source: FakeSource()).walk(tree)
//         #expect(!r.stats.truncated)
//         #expect(r.stats.nodes == 3)
//         #expect(r.stats.textNodes == 3)
//         #expect(r.root?.children?.count == 2)
//         #expect(r.root?.omittedChildren == nil)
//         #expect(r.treeHash == TreeHasher.hash(["W", "hello there", "Send"]))
//     }
//
//     @Test func deadlineStopsWalk() {
//         var t: UInt64 = 0
//         let clock = { () -> UInt64 in t += 1_000_000; return t }  // +1 ms per clock read
//         let r = TreeWalker(source: FakeSource(), limits: WalkLimits(maxDepth: 64, deadlineMs: 10), now: clock).walk(chain(50))
//         #expect(r.stats.truncatedBy == ["deadline"])
//         #expect(r.stats.nodes < 51)
//     }
//
//     @Test func textTruncationAndRedaction() {
//         let long = String(repeating: "x", count: 50)
//         let tree = FakeNode(NodeAttributes(role: "AXStaticText", value: long))
//         let full = TreeWalker(source: FakeSource(), limits: WalkLimits(maxTextLength: 10)).walk(tree)
//         #expect(full.root?.value == String(repeating: "x", count: 10) + "…")
//         #expect(full.root?.textTruncated == true)
//         #expect(full.stats.longTextNodes == 1)
//         #expect(full.stats.firstLongTextDepth == 0)
//
//         let red = TreeWalker(source: FakeSource(), textMode: .redacted).walk(tree)
//         #expect(red.root?.value == nil)
//         #expect(red.root?.textLength == 50)
//         #expect(red.treeHash == full.treeHash)  // hash is over full text regardless of output mode
//     }
//
//     @Test func secureFieldValueNeverUsed() {
//         let tree = FakeNode(NodeAttributes(role: "AXWindow"), [
//             FakeNode(NodeAttributes(role: "AXTextField", subrole: "AXSecureTextField", value: "synthetic-secret")),
//         ])
//         let r = TreeWalker(source: FakeSource()).walk(tree)
//         #expect(r.root?.children?.first?.value == nil)
//         #expect(r.stats.textNodes == 0)
//         #expect(r.treeHash == TreeHasher.hash([String]()))
//     }
//
//     @Test func offscreenTextExcludedFromHashOnly() {
//         let win = CGRect(x: 0, y: 0, width: 800, height: 600)
//         let tree = FakeNode(NodeAttributes(role: "AXWindow", frame: win), [
//             FakeNode(NodeAttributes(role: "AXStaticText", value: "visible", frame: CGRect(x: 10, y: 10, width: 100, height: 20))),
//             FakeNode(NodeAttributes(role: "AXStaticText", value: "scrolled away", frame: CGRect(x: 10, y: -900, width: 100, height: 20))),
//         ])
//         let r = TreeWalker(source: FakeSource()).walk(tree)
//         #expect(r.treeHash == TreeHasher.hash(["visible"]))
//         #expect(r.root?.children?.count == 2)
//     }
//
//     @Test func errorsCounted() {
//         let tree = FakeNode(NodeAttributes(role: "AXWindow"), [FakeNode(NodeAttributes(), error: .cannotComplete)])
//         let r = TreeWalker(source: FakeSource()).walk(tree)
//         #expect(r.stats.axErrors == 1)
//         #expect(r.stats.axCannotComplete == 1)
//         #expect(r.root?.children?.first?.error == "cannot_complete")
//     }
// }
```

#### `src-tauri/sidecar/genios-ax/Tests/GeniosAXCoreTests/WhatsAppReaderTests.swift`

```swift
// import Foundation
// import Testing
// @testable import GeniosAXCore
//
// // A synthetic WhatsApp-shaped tree: the structure measured on the native app (2026-09-14, text
// // redacted); every name and message here is made up.
//
// private let lrm = "\u{200E}"
//
// private func waTree(_ messages: [String], chat: String? = "Priya Shah") -> FakeNode {
//     let chatList = ax("AXGroup", [
//         ax("AXButton", desc: "Priya Shah, \(lrm)message, See you, 10:02 AM, \(lrm)Received from Priya Shah"),
//         ax("AXButton", desc: "Ops Team, \(lrm)Your message, done, 9:00 AM, \(lrm)Sent to Ops Team"),
//     ])
//     var conversation: [FakeNode] = [
//         ax("AXGroup", [ax("AXStaticText", desc: "\(lrm)Messages and calls are end-to-end encrypted.")]),
//     ]
//     if let chat {
//         conversation.append(ax("AXGroup", [ax("AXHeading")] + messages.map { ax("AXStaticText", desc: $0) },
//                                desc: "\(lrm)Messages in chat with \(chat)"))
//     }
//     conversation.append(ax("AXTextArea", desc: "\(lrm)Type a message", value: "\(lrm)Type a message"))
//     let openChat = ax("AXGroup", [
//         ax("AXGroup", [ax("AXButton", desc: "\(chat ?? "") \(lrm)last seen today at 7:12 PM")]),
//         ax("AXGroup", conversation),
//     ])
//     return ax("AXWindow", [ax("AXGroup", [ax("AXGroup", [chatList, openChat])], sub: "iOSContentGroup")],
//               sub: "AXStandardWindow", title: "\(lrm)WhatsApp")
// }
//
// private func readWA(_ tree: FakeNode, draft: Bool = false) -> ReaderOutput {
//     let cap = ReaderCapture(source: FakeSource(), limits: ReadOptions.defaultLimits, now: { 0 }).capture(tree)
//     let ctx = ReadContext(bundleID: "net.whatsapp.WhatsApp", windowTitle: "\(lrm)WhatsApp", draft: draft, now: fixedNow)
//     return ScreenReaderEngine.read(cap, ctx)
// }
//
// @Test func whatsappOpenChatBecomesItsOwnThreadRead() throws {
//     let out = readWA(waTree([
//         "\(lrm)Photo, 9:41 AM, \(lrm)Received from Priya Shah",
//         "\(lrm)message, Can you send the revised quote, by Friday?, 10:02 AM, \(lrm)Received from Priya Shah",
//         "\(lrm)Your message, Sure, sending by Thursday 5 pm, 10:05 AM, \(lrm)Sent to Priya Shah, Read",
//     ]))
//     #expect(out.reader == "whatsapp")
//     let t = try #require(out.line as? ThreadRead)
//     #expect(t.threadKey == "wa:priya shah" && t.title == "Priya Shah" && t.app == "whatsapp")
//     #expect(t.messages.map(\.text) == ["[Photo]", "Can you send the revised quote, by Friday?", "Sure, sending by Thursday 5 pm"])
//     #expect(t.messages.map(\.isOutgoing) == [false, false, true])
//     #expect(t.messages.map { $0.sender ?? "" } == ["Priya Shah", "Priya Shah", "self"])
//     #expect(t.draft == nil, "the composer is read only with Draft assist on")
//     let json = String(decoding: try ScreenReaderEngine.encode(out), as: UTF8.self)
//     #expect(json.contains("\"kind\":\"thread_read\"") && json.contains("\"thread_key\":\"wa:priya shah\""))
//     #expect(json.contains("\"is_outgoing\":true") && json.contains("\"schema_version\":1"))
//     #expect(!json.contains("Ops Team") && !json.contains("See you"), "the chat list is never read")
// }
//
// @Test func whatsappGroupChatKeepsEachSenderAndItsOwnKey() throws {
//     let t = try #require(readWA(waTree([
//         "\(lrm)message, Please approve the vendor invoice today, 5:50 PM, \(lrm)Received from Suresh Kumar",
//         "\(lrm)message, +1, 17:51, \(lrm)Received from Neha",
//     ], chat: "Ops Team")).line as? ThreadRead)
//     #expect(t.threadKey == "wa:ops team")
//     #expect(t.messages.map { $0.sender ?? "" } == ["Suresh Kumar", "Neha"])
//     #expect(t.messages.map(\.text) == ["Please approve the vendor invoice today", "+1"])
// }
//
// @Test func whatsappWithNoOpenChatFallsBackToTheGenericReader() {
//     #expect(readWA(waTree([], chat: nil)).reader == "generic")
//     #expect(readWA(waTree(["\(lrm)Today"])).reader == "generic", "no parseable message → generic")
// }
//
// @Test func whatsappParseSkipsSystemLinesAndRedactsEverything() throws {
//     #expect(WhatsAppReader.parse("\(lrm)Messages and calls are end-to-end encrypted.") == nil)
//     #expect(WhatsAppReader.parse("Today") == nil)
//     #expect(WhatsAppReader.parse("\(lrm)Voice message, 0:14, 9:00 AM, \(lrm)Received from Ravi")?.text == "[Voice message] 0:14")
//     let out = readWA(waTree(["\(lrm)message, the secret plan, 10:02 AM, \(lrm)Received from Priya Shah"]))
//     let red = String(decoding: try ScreenReaderEngine.encode(out, redact: true), as: UTF8.self)
//     #expect(!red.contains("secret") && !red.contains("Priya") && !red.contains("priya"))
// }
//
// @Test func whatsappNumberContactsAndEditedMessagesReadCleanly() {
//     let m = WhatsAppReader.parse("\(lrm)message, Hi sir, society se, 7:24 PM, \(lrm)Received from + 9 1,6 3 9 5,3 2 7,1 1 5, Edited")
//     #expect(m?.sender == "+916395327115" && m?.text == "Hi sir, society se" && m?.isOutgoing == false)
//     #expect(WhatsAppReader.person("Priya Shah") == "Priya Shah")
//     #expect(WhatsAppReader.parse("\(lrm)Your message, ok done, 7:30 PM, \(lrm)Sent to Ravi, Edited, Read")?.text == "ok done")
// }
//
//
// // ─── The tree as it actually is, measured live on 2026-10-07 ────────────────────────────────────
// //
// // Three things were wrong at once, and each alone was enough to kill the reader:
// //   1. a message is an `AXButton`, not an `AXStaticText`;
// //   2. its label is on `AXValue` while `AXDescription` holds the bare text, and `text()` returned
// //      the first non-empty attribute — so `parse` never saw "Received from" / "Sent to";
// //   3. the bubbles are NOT inside the "Messages in chat with …" group.
// // Every message below is invented; only the SHAPE is from the measurement.
//
// private func waTree2026_10(chat: String = "Deepika Rao") -> FakeNode {
//     // Chat list: rows carry a direction label too, but they start with the CHAT NAME.
//     let chatList = ax("AXGroup", [
//         ax("AXButton", desc: "Priya Shah, \(lrm)message, See you, 10:02 AM, \(lrm)Received from Priya Shah"),
//         ax("AXButton", desc: "Ops Team, \(lrm)Your message, done, 9:00 AM, \(lrm)Sent to Ops Team"),
//     ])
//     // The group only NAMES the chat — no messages under it.
//     let namer = ax("AXGroup", [ax("AXHeading")], desc: "\(lrm)Messages in chat with \(chat)")
//     // The bubbles: label on VALUE, bare text on DESCRIPTION, as measured.
//     let bubble = { (desc: String, value: String) in ax("AXButton", desc: desc, value: value) }
//     let bubbles = ax("AXGroup", [
//         bubble("ok", "\(lrm)Your message, ok, 11:02 AM, \(lrm)Sent to \(chat), Read"),
//         bubble("SOW bhej raha hoon", "\(lrm)Your message, SOW bhej raha hoon, 11:03 AM, \(lrm)Sent to \(chat), Delivered"),
//         bubble("invoice", "\(lrm)Photo, invoice, 11:40 AM, \(lrm)Received from \(chat)"),
//         bubble("quote ka kya hua?", "\(lrm)message, quote ka kya hua?, 11:41 AM, \(lrm)Received from \(chat)"),
//     ])
//     return ax("AXWindow", [ax("AXGroup", [ax("AXGroup", [chatList, namer, bubbles])], sub: "iOSContentGroup")],
//               sub: "AXStandardWindow", title: "\(lrm)WhatsApp")
// }
//
// @Test func theLiveTreeOfOctober2026IsReadAsAThread() {
//     let out = readWA(waTree2026_10())
//     #expect(out.reader == "whatsapp", "the dedicated reader must fire — it had been falling through to generic")
//     let t = out.line as? ThreadRead
//     #expect(t?.threadKey == "wa:deepika rao")
//     #expect(t?.title == "Deepika Rao")
//     // Four bubbles, right order, right direction — and NOTHING from the chat list on the left.
//     #expect(t?.messages.count == 4)
//     #expect(t?.messages.map(\.isOutgoing) == [true, true, false, false])
//     #expect(t?.messages.map(\.sender) == ["self", "self", "Deepika Rao", "Deepika Rao"])
//     #expect(t?.messages.map(\.text) == ["ok", "SOW bhej raha hoon", "[Photo] invoice", "quote ka kya hua?"])
//     #expect(t?.messages.contains { $0.text.contains("See you") } == false, "a chat-list row is not a message")
//     #expect(t?.messages.contains { $0.sender == "Ops Team" } == false, "another chat must never leak in")
// }
//
// @Test func aChatListRowIsNeverMistakenForTheOpenChat() {
//     // Only the list is on screen (no open chat): nothing to read, so the generic reader takes it.
//     let listOnly = ax("AXWindow", [ax("AXGroup", [
//         ax("AXButton", desc: "Priya Shah, \(lrm)message, See you, 10:02 AM, \(lrm)Received from Priya Shah"),
//     ])], title: "\(lrm)WhatsApp")
//     #expect(readWA(listOnly).reader == "generic")
//     // The prefix rule, stated once: a bubble starts with its own prefix, a row with a name.
//     #expect(WhatsAppReader.isBubbleLabel("Your message, ok, 11:02 AM, Sent to X"))
//     #expect(WhatsAppReader.isBubbleLabel("message, hi, 11:02 AM, Received from X"))
//     #expect(WhatsAppReader.isBubbleLabel("Photo, 11:02 AM, Received from X"))
//     #expect(!WhatsAppReader.isBubbleLabel("Priya Shah, message, See you, 10:02 AM, Received from Priya Shah"))
// }
```

#### `src-tauri/sidecar/genios-ax/scripts/check-readers.sh`

```bash
# #!/usr/bin/env bash
# # Compiles the reader sources together with scripts/reader-check/main.swift and runs it.
# # Works with the Command Line Tools alone — `swift test` needs Xcode's `Testing` module.
# set -euo pipefail
# pkg="$(cd "$(dirname "$0")/.." && pwd)"
# out="$(mktemp -d)"
# trap 'rm -rf "$out"' EXIT
# # shellcheck disable=SC2046
# swiftc -O $(find "$pkg/Sources/GeniosAXCore" -name '*.swift') "$pkg/scripts/reader-check/main.swift" \
#   -framework ApplicationServices -framework AppKit -o "$out/reader-check"
# "$out/reader-check"
```

#### `src-tauri/sidecar/genios-ax/scripts/measure.sh`

```bash
# #!/usr/bin/env bash
# # genios-ax live measurement — run AFTER granting Accessibility (the dedicated readers for
# # Gmail / LinkedIn / Slack / WhatsApp are built from what this records).
# #
# #   1. System Settings → Privacy & Security → Accessibility → enable the app you run this from
# #      (Terminal.app, or VS Code copied to /Applications — see SPIKE_RESULTS.md "Accessibility trust").
# #   2. scripts/measure.sh [out-dir]          (default: fixtures/live/<timestamp>/ next to this script)
# #   3. For each target it asks you to put the page/chat in front, then records:
# #        <name>.stats.json       snapshot --stats-only                 counts only (d12 / 5k limits)
# #        <name>.stats-deep.json  snapshot --stats-only, d40 / 20k      where the text really lives
# #        <name>.structure.json   snapshot --redact                     roles/subroles tree, text → length
# #        <name>.read.json        read --redact                         screen_doc shape, every string → <n>
# #      No message text, names, titles or URL paths are written (URL → host only).
# #
# # Env: GENIOS_AX=/path/to/genios-ax to use a prebuilt binary (default: swift build -c release).
# set -euo pipefail
#
# here="$(cd "$(dirname "$0")" && pwd)"
# pkg="$(cd "$here/.." && pwd)"
# out="${1:-$pkg/fixtures/live/$(date +%Y%m%d-%H%M%S)}"
#
# bin="${GENIOS_AX:-}"
# if [[ -z "$bin" ]]; then
#   swift build -c release --package-path "$pkg" >&2
#   bin="$pkg/.build/release/genios-ax"
# fi
#
# if ! "$bin" trust >/dev/null; then
#   echo "measure: Accessibility is not granted to the app running this script (exit 77)." >&2
#   "$bin" trust >&2 || true
#   exit 77
# fi
# mkdir -p "$out"
#
# # name | bundle id | what to put in front
# # A manager on a company laptop mostly has NO desktop app — the work is in browser tabs. Every
# # web surface here is one the Admin and Sales packs need, and none of them has ever been
# # measured: that is why only native WhatsApp has a dedicated reader.
# targets=(
#   "chrome-whatsapp|com.google.Chrome|Chrome: open ONE chat on web.whatsapp.com (messages both ways)"
#   "chrome-gmail|com.google.Chrome|Chrome: open one Gmail THREAD (mail.google.com/…/#inbox/<id>) in the front tab"
#   "chrome-slack|com.google.Chrome|Chrome: open one Slack channel on app.slack.com (messages both ways)"
#   "chrome-teams|com.google.Chrome|Chrome: open one Teams chat on teams.microsoft.com"
#   "chrome-outlook|com.google.Chrome|Chrome: open one Outlook web mail thread (outlook.office.com/mail/…)"
#   "chrome-linkedin|com.google.Chrome|Chrome: open one LinkedIn conversation (linkedin.com/messaging/thread/…)"
#   "chrome-gcal|com.google.Chrome|Chrome: open one Google Calendar event with guests (calendar.google.com)"
#   "chrome-crm|com.google.Chrome|Chrome: open one CRM record page (a deal or contact with fields + a table)"
#   "whatsapp|net.whatsapp.WhatsApp|WhatsApp desktop: open one chat with a few messages both ways"
#   "slack|com.tinyspeck.slackmacgap|Slack desktop: open one channel with messages (and a thread if possible)"
#   "teams|com.microsoft.teams2|Teams desktop: open one chat with messages both ways (skip if not installed)"
#   "outlook|com.microsoft.Outlook|Outlook desktop: open one mail thread (skip if not installed)"
# )
#
# for t in "${targets[@]}"; do
#   IFS='|' read -r name bundle hint <<<"$t"
#   echo
#   echo "== $name — $hint"
#   read -r -p "   Press Enter when it is in front (s = skip): " ans </dev/tty
#   [[ "$ans" == "s" ]] && { echo "   skipped"; continue; }
#   # Give focus back to the target so Chrome's focused tab / web area is the one measured.
#   osascript -e "tell application id \"$bundle\" to activate" >/dev/null 2>&1 || true
#   sleep 1
#   run() {  # run <file> <args…> — keeps going on 69 (app busy/windowless), records the exit code
#     local file="$1"; shift
#     local code=0
#     "$bin" "$@" >"$out/$file" 2>"$out/$file.err" || code=$?
#     [[ -s "$out/$file.err" ]] || rm -f "$out/$file.err"
#     echo "   $file  exit=$code  $(wc -c <"$out/$file" | tr -d ' ') bytes"
#   }
#   run "$name.stats.json"      snapshot --bundle "$bundle" --stats-only
#   run "$name.stats-deep.json" snapshot --bundle "$bundle" --stats-only --max-depth 40 --max-nodes 20000 --deadline-ms 5000
#   run "$name.structure.json"  snapshot --bundle "$bundle" --redact --pretty
#   run "$name.read.json"       read --bundle "$bundle" --redact --pretty
#   for i in 1 2 3; do             # read latency samples (redacted; only stats kept)
#     "$bin" read --bundle "$bundle" --redact 2>/dev/null \
#       | sed -n 's/.*"elapsed_ms":\([0-9.]*\).*/\1/p' >>"$out/$name.read-ms.txt" || true
#   done
# done
#
# echo
# echo "Recorded (redacted, no text) in: $out"
# echo "Look at: stats.first_long_text_depth / nodes / truncated_by / elapsed_ms, read.stats.block_counts,"
# echo "ax_empty, and whether message rows appear as role=message. Then write the dedicated readers."
```

#### `src-tauri/sidecar/genios-ax/scripts/reader-check/main.swift`

```swift
// // READER CHECK — runs where `swift test` cannot.
// //
// // Why this file exists: every test in Tests/ imports `Testing`, which ships with Xcode. On a
// // machine with only the Command Line Tools `swift test` fails to build, so the reader tests had
// // never run — and that is how the WhatsApp reader sat dead for weeks while looking healthy
// // (it returned nil, the engine fell back to the generic reader, and nothing said a word).
// //
// // Run:  ./scripts/check-readers.sh
// //
// // Every tree below is synthetic; only the SHAPE comes from a live measurement, and the dates in
// // the comments say when it was measured. If a reader stops matching its measured shape, this
// // fails — loudly, before a manager ever sees a page where a conversation should have been.
//
// import Foundation
//
// final class N {
//     var a: NodeAttributes
//     var k: [N]
//     init(_ a: NodeAttributes, _ k: [N] = []) { self.a = a; self.k = k }
// }
// struct Src: TreeSource {
//     func read(_ e: N, childLimit: Int) -> NodeRead<N> {
//         NodeRead(attributes: e.a, children: Array(e.k.prefix(childLimit)), totalChildren: e.k.count)
//     }
// }
// func ax(_ role: String, _ k: [N] = [], desc: String? = nil, value: String? = nil,
//         title: String? = nil, frame: CGRect? = nil) -> N {
//     N(NodeAttributes(role: role, title: title, description: desc, value: value, frame: frame), k)
// }
//
// var failures = 0
// func check(_ ok: Bool, _ what: String) {
//     print((ok ? "  PASS  " : "  FAIL  ") + what)
//     if !ok { failures += 1 }
// }
// func readTree(_ tree: N, bundle: String?, url: String? = nil, title: String? = nil) -> ReaderOutput {
//     let cap = ReaderCapture(source: Src(), limits: ReadOptions.limits(for: bundle), now: { 0 }).capture(tree)
//     return ScreenReaderEngine.read(cap, ReadContext(bundleID: bundle, url: url, windowTitle: title, now: Date()))
// }
// func messages(_ out: ReaderOutput) -> [[String: Any]] {
//     guard let data = try? ScreenReaderEngine.encode(out),
//           let j = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [] }
//     return (j["messages"] as? [[String: Any]]) ?? []
// }
// /// `m[i]["sender"]` traps when a broken reader returns fewer messages than expected — and a trap
// /// prints no verdict at all, which is how a caught regression looked like a clean run.
// func at(_ m: [[String: Any]], _ i: Int, _ k: String) -> String? {
//     guard i < m.count else { return nil }
//     return m[i][k] as? String
// }
//
// func field(_ out: ReaderOutput, _ k: String) -> String? {
//     guard let data = try? ScreenReaderEngine.encode(out),
//           let j = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
//     return j[k] as? String
// }
//
// // ── WhatsApp, native (measured 2026-10-07) ──────────────────────────────────────────────────────
// // A message is an AXButton; its VoiceOver label is on AXValue while AXDescription holds the bare
// // text; the bubbles are NOT inside the "Messages in chat with …" group; a chat-list row carries a
// // direction label too but starts with the CHAT NAME instead of a bubble prefix.
// print("WhatsApp (native) — measured 2026-10-07")
// let lrm = "\u{200E}"
// do {
//     let chat = "Deepika Rao"
//     let list = ax("AXGroup", [
//         ax("AXButton", desc: "Priya Shah, \(lrm)message, See you, 10:02 AM, \(lrm)Received from Priya Shah"),
//         ax("AXButton", desc: "Ops Team, \(lrm)Your message, done, 9:00 AM, \(lrm)Sent to Ops Team")])
//     let namer = ax("AXGroup", [ax("AXHeading")], desc: "\(lrm)Messages in chat with \(chat)")
//     let bubbles = ax("AXGroup", [
//         ax("AXButton", desc: "ok", value: "\(lrm)Your message, ok, 11:02 AM, \(lrm)Sent to \(chat), Read"),
//         ax("AXButton", desc: "SOW bhej raha hoon", value: "\(lrm)Your message, SOW bhej raha hoon, 11:03 AM, \(lrm)Sent to \(chat), Delivered"),
//         ax("AXButton", desc: "invoice", value: "\(lrm)Photo, invoice, 11:40 AM, \(lrm)Received from \(chat)"),
//         ax("AXButton", desc: "quote ka kya hua?", value: "\(lrm)message, quote ka kya hua?, 11:41 AM, \(lrm)Received from \(chat)")])
//     let out = readTree(ax("AXWindow", [ax("AXGroup", [list, namer, bubbles])], title: "\(lrm)WhatsApp"),
//                        bundle: "net.whatsapp.WhatsApp")
//     check(out.reader == "whatsapp", "the dedicated reader fires (got \(out.reader))")
//     check(field(out, "thread_key") == "wa:deepika rao", "one thread per chat")
//     let m = messages(out)
//     check(m.count == 4, "4 bubbles, no chat-list rows (got \(m.count))")
//     check(m.map { $0["is_outgoing"] as? Bool } == [true, true, false, false], "direction is a fact here")
//     check(m.map { $0["sender"] as? String } == ["self", "self", chat, chat], "senders")
//     check(m.compactMap { $0["text"] as? String } == ["ok", "SOW bhej raha hoon", "[Photo] invoice", "quote ka kya hua?"],
//           "text, with media named")
//     check(!m.contains { ($0["text"] as? String)?.contains("See you") == true }, "another chat never leaks in")
//     // Only the chat list on screen: nothing to read, so the generic reader takes it.
//     check(readTree(ax("AXWindow", [list], title: "WhatsApp"), bundle: "net.whatsapp.WhatsApp").reader == "generic",
//           "a chat list alone is not a conversation")
// }
//
// // ── Slack, web and desktop (measured 2026-10-07, app.slack.com/client/T…/C…) ─────────────────────
// // The message list is an AXList whose rows are AXGroups: AXButton = sender, AXLink = permalink
// // (never the name), AXStaticText = the clock, then the body. The sidebar is an AXOutline of rows
// // with no clock; a bulleted list inside a message is a nested AXList with no clock of its own.
// print("\nSlack (web + desktop) — measured 2026-10-07")
// do {
//     // `body` entries starting with "link:" become an AXLink AFTER the clock — something the
//     // sender wrote, not the row's permalink.
//     // `lead` is the wrapper group label a real row can open with (measured: 45 characters before
//     // the sender's button) — the reason the sender must come off a BUTTON and not off "the first
//     // label in the row".
//     func row(_ sender: String, _ clock: String, _ body: [String], lead: String? = nil) -> N {
//         ax("AXGroup", (lead.map { [ax("AXGroup", desc: $0)] } ?? [])
//             + [ax("AXButton", desc: sender), ax("AXLink", desc: "https://slack.com/archives/x"),
//                        ax("AXStaticText", desc: clock)]
//             + body.map { $0.hasPrefix("link:") ? ax("AXLink", desc: String($0.dropFirst(5)))
//                                                : ax("AXStaticText", desc: $0) })
//     }
//     let sidebar = ax("AXOutline", (1...3).map { ax("AXRow", [ax("AXStaticText", desc: "#channel-\($0)")]) })
//     // An AXList that is NOT the conversation, and it comes FIRST in document order — so the
//     // message list has to be chosen by the clocks in it, not by being the first list found.
//     let saved = ax("AXList", (1...4).map { ax("AXGroup", [ax("AXStaticText", desc: "saved item \($0)")]) })
//     let msgs = ax("AXList", [
//         ax("AXGroup", [ax("AXPopUpButton", desc: "Today")]),                       // a day separator
//         // A system row: real text, no clock. Slack writes these, and they are nobody's message.
//         ax("AXGroup", [ax("AXStaticText", desc: "Ujjwal joined the channel")]),
//         row("Vanshika Pandita", "9:02 AM", ["Welcome to the bootcamp.", "Guidelines are attached.",
//                                             "link:meet.google.com/pxp-tdig-mgq"]),
//         row("Birajit", "3:31 PM", ["Trying to join but no one is accepting the join request"],
//             lead: "replied to a thread · 2 replies · last reply today"),
//         row("Ujjwal", "3:32 PM", ["Can you pull me in the call"]),
//         // A bulleted list INSIDE a message: a second AXList, with no clock of its own (measured
//         // at depth 25). The message list has to be chosen by evidence, not by being first.
//         ax("AXGroup", [ax("AXList", (1...3).map { ax("AXGroup", [ax("AXStaticText", desc: "point \($0)")]) })])])
//     let tree = ax("AXWindow", [ax("AXGroup", [sidebar, saved, msgs])], title: "Slack")
//     let out = readTree(tree, bundle: "com.google.Chrome", url: "https://app.slack.com/client/T08HUEZEKV4/C0C751NJRKM")
//     check(out.reader == "slack", "the dedicated reader fires (got \(out.reader))")
//     check(field(out, "thread_key") == "slack:T08HUEZEKV4/C0C751NJRKM", "the channel is the key, from the URL path")
//     let m = messages(out)
//     check(m.count == 3, "3 messages; the day separator is not one (got \(m.count))")
//     check(m.map { $0["sender"] as? String } == ["Vanshika Pandita", "Birajit", "Ujjwal"], "senders")
//     check(at(m, 0, "text")?.contains("Welcome to the bootcamp") == true, "multi-line body is kept")
//     check(!m.contains { ($0["text"] as? String)?.contains("#channel-") == true }, "the sidebar is not a conversation")
//     check(!m.contains { ($0["text"] as? String)?.contains("slack.com/archives") == true }, "the permalink is not text")
//     check(at(m, 0, "text")?.contains("meet.google.com/pxp-tdig-mgq") == true,
//           "a link the sender WROTE is kept — it is usually the actionable part")
//     check(!m.contains { ($0["text"] as? String)?.contains("point 1") == true },
//           "a bulleted list inside a message is not a second conversation")
//     check(!m.contains { ($0["text"] as? String)?.contains("joined the channel") == true },
//           "a row with no clock is not a message")
//     check(!m.contains { ($0["text"] as? String)?.contains("saved item") == true },
//           "a list without clocks is not the conversation, even when it comes first")
//     check(at(m, 1, "sender") == "Birajit",
//           "a wrapper label before the sender's button is not the sender")
//     // The desktop app is the same tree, reached by bundle id instead of a URL.
//     check(readTree(tree, bundle: "com.tinyspeck.slackmacgap", title: "Slack").reader == "slack",
//           "the desktop app uses the same reader")
// }
//
// // ── Gmail / Outlook / Teams / LinkedIn (STRUCTURAL, not measured) ───────────────────────────────
// // These four are built on `ThreadScan`'s two invariants rather than a recorded tree — a container
// // whose rows carry a clock, and a row whose sender sits before that clock. The trees below are
// // written to those invariants, in the nesting a web client actually produces (a paragraph group
// // whose children are the lines), which is what `ThreadScan.dedupe` has to survive.
// //
// // NOT a substitute for `scripts/measure.sh` on each app. What these prove is that the reader
// // fires, keys the thread the way the REST OF THE SYSTEM already expects, reads every message
// // once, and refuses a list view. What they cannot prove is that the sender lands on the role each
// // client really uses — that is owed, and until then a wrong role costs a missing sender name, not
// // a missing message.
// print("\nGmail / Outlook / Teams / LinkedIn — structural")
//
// /// One message row: header (sender, then clock), then a nested body the way a web tree nests it.
// func row(_ sender: String, _ clock: String, _ lines: [String], senderRole: String = "AXLink") -> N {
//     ax("AXGroup", [
//         // MEASURED on Slack 2026-10-07: a row opens with a WRAPPER that carries 45 characters of
//         // its own, before the sender's node. "The first label before the clock" made that the
//         // sender's name. Only a listed role may become the sender, and this trap is what proves
//         // the rule is still doing the work.
//         ax("AXGroup", [ax("AXStaticText", desc: "Message from \(sender), unread, press to open")]),
//         ax("AXGroup", [ax(senderRole, desc: sender), ax("AXStaticText", desc: clock)]),
//         // The paragraph group carries the whole body AND its children carry each line. Both match
//         // `bodyRoles`, so without `dedupe` every message reads twice.
//         ax("AXGroup", lines.map { ax("AXStaticText", desc: $0) }, desc: lines.joined(separator: " ")),
//     ])
// }
//
// do {
//     let thread = ax("AXList", [
//         row("Priya Shah", "10:02 AM", ["Thanks for the deck.", "Can we talk pricing this week?"]),
//         row("Harsh Tripathi", "10:10 AM", ["Sure — Thursday 4pm?"]),
//     ])
//     // A sidebar: rows, but no clocks. It must never win the evidence contest.
//     let sidebar = ax("AXList", [ax("AXGroup", [ax("AXStaticText", desc: "Inbox")]),
//                                 ax("AXGroup", [ax("AXStaticText", desc: "Sent")])])
//     let page = ax("AXWindow", [ax("AXGroup", [sidebar, thread])], title: "Pricing — Priya Shah")
//
//     // Gmail: the thread is in the FRAGMENT, and a mailbox view is not a conversation.
//     let gm = readTree(page, bundle: "com.google.Chrome",
//                       url: "https://mail.google.com/mail/u/0/#inbox/FMfcgzQbfvLXrTgVdKWqNJ", title: "Pricing")
//     check(gm.reader == "gmail", "Gmail: the dedicated reader fires (got \(gm.reader))")
//     check(field(gm, "thread_key") == "gm:thread:FMfcgzQbfvLXrTgVdKWqNJ", "Gmail: one key per mail thread")
//     let gmm = messages(gm)
//     check(gmm.count == 2, "Gmail: two messages (got \(gmm.count))")
//     check(at(gmm, 0, "sender") == "Priya Shah", "Gmail: sender comes off the row header")
//     check(at(gmm, 0, "text") == "Thanks for the deck. Can we talk pricing this week?",
//           "Gmail: the body reads ONCE, not twice (got \(at(gmm, 0, "text") ?? "nil"))")
//     check(readTree(page, bundle: "com.google.Chrome",
//                    url: "https://mail.google.com/mail/u/0/#inbox").reader == "generic",
//           "Gmail: the inbox LIST is not a thread")
//     check(readTree(page, bundle: "com.google.Chrome",
//                    url: "https://mail.google.com/mail/u/0/#search/priya+pricing").reader == "generic",
//           "Gmail: a search phrase is not a thread id")
//     check(GmailReader.threadKey("https://mail.google.com/mail/u/0/#label/Clients/FMfcgzAbcdefgh")
//             == "gm:thread:FMfcgzAbcdefgh", "Gmail: a label path still keys on the thread")
//
//     // Outlook: the mail is in the PATH; the desktop app has no URL and is refused rather than
//     // keyed wrongly.
//     let ol = readTree(page, bundle: "com.google.Chrome",
//                       url: "https://outlook.office.com/mail/inbox/id/AAQkADAwATM0MDAAZS0z", title: "Pricing")
//     check(ol.reader == "outlook", "Outlook: the dedicated reader fires (got \(ol.reader))")
//     check(field(ol, "thread_key") == "ol:mail:AAQkADAwATM0MDAAZS0z", "Outlook: one key per mail")
//     check(messages(ol).count == 2, "Outlook: two messages")
//     check(readTree(page, bundle: "com.google.Chrome",
//                    url: "https://outlook.office.com/mail/inbox").reader == "generic",
//           "Outlook: the mailbox view is not a thread")
//     check(OutlookReader().accepts(ReadContext(bundleID: "com.microsoft.Outlook", now: Date())),
//           "Outlook: the desktop app is claimed")
//     check(readTree(page, bundle: "com.microsoft.Outlook").reader == "generic",
//           "Outlook desktop: no URL ⇒ no invented key, the generic reader takes it")
//
//     // Teams: the chat is in the FRAGMENT.
//     let tm = readTree(page, bundle: "com.google.Chrome",
//                       url: "https://teams.microsoft.com/#/conversations/19:abc123@thread.v2", title: "Priya")
//     check(tm.reader == "teams", "Teams: the dedicated reader fires (got \(tm.reader))")
//     check(field(tm, "thread_key") == "tm:conv:19:abc123@thread.v2",
//           "Teams: the id is taken as-is so it matches a Graph payload")
//     check(messages(tm).count == 2, "Teams: two messages")
//     check(readTree(page, bundle: "com.google.Chrome",
//                    url: "https://teams.microsoft.com/#/activity").reader == "generic",
//           "Teams: the activity feed is not a conversation")
//
//     // LinkedIn: the key format is NOT a choice here — the fixture and thread_source.rs fix it.
//     let li = readTree(page, bundle: "com.google.Chrome",
//                       url: "https://www.linkedin.com/messaging/thread/abc/", title: "Priya Shah")
//     check(li.reader == "linkedin", "LinkedIn: the dedicated reader fires (got \(li.reader))")
//     check(field(li, "thread_key") == "li:conv:abc",
//           "LinkedIn: li:conv:<id>, matching tests/fixtures/thread_reads/linkedin_priya.json")
//     check(messages(li).count == 2, "LinkedIn: two messages")
//     check(readTree(page, bundle: "com.google.Chrome",
//                    url: "https://www.linkedin.com/messaging/").reader == "generic",
//           "LinkedIn: the conversation list is not a conversation")
//     check(readTree(page, bundle: "com.google.Chrome",
//                    url: "https://www.linkedin.com/feed/").reader == "generic",
//           "LinkedIn: the feed is not a conversation")
//
//     // THE SENDER FILTERS, both of them, with the clock on the far side of the trap.
//     //
//     // Proximity alone is not enough: whatever sits between the sender and the clock is what
//     // proximity hands over. These two rows put a badge and a snippet there — the shapes a mail
//     // client actually produces — so the role filter and the length cap each have to hold.
//     let trapped = ax("AXWindow", [ax("AXList", [
//         // A verified badge on an AXImage, AFTER the name. Not a sender role ⇒ never the sender.
//         ax("AXGroup", [
//             ax("AXGroup", [ax("AXLink", desc: "Priya Shah"),
//                            ax("AXImage", desc: "Verified account badge"),
//                            ax("AXStaticText", desc: "10:02 AM")]),
//             ax("AXGroup", [ax("AXStaticText", desc: "Thanks for the deck.")]),
//         ]),
//         // A snippet preview on a sender ROLE, after the name — too long to be a name.
//         ax("AXGroup", [
//             ax("AXGroup", [ax("AXLink", desc: "Rahul Mehta"),
//                            ax("AXStaticText", desc: "Re: pricing — I had a look at the deck last night and wanted to check a few of the numbers before Thursday"),
//                            ax("AXStaticText", desc: "10:10 AM")]),
//             ax("AXGroup", [ax("AXStaticText", desc: "Thursday works.")]),
//         ]),
//     ])], title: "Pricing")
//     let tr = messages(readTree(trapped, bundle: "com.google.Chrome",
//                                url: "https://mail.google.com/mail/u/0/#inbox/FMfcgzQbfvLXrTgVdKWqNJ"))
//     check(at(tr, 0, "sender") == "Priya Shah",
//           "a badge between the name and the clock is not the sender (got \(at(tr, 0, "sender") ?? "nil"))")
//     check(at(tr, 1, "sender") == "Rahul Mehta",
//           "a snippet longer than a name is not the sender (got \(at(tr, 1, "sender") ?? "nil"))")
//
//     // NO CLOCK ANYWHERE ⇒ no conversation, whatever the URL says.
//     //
//     // This is the whole weight-bearing invariant: a clock on every row is what separates a
//     // message list from a sidebar, a folder tree or a settings page. Without it there is nothing
//     // to find, and a reader that pressed on would hand the first container with children to the
//     // brain as if it were a chat.
//     let clockless = ax("AXWindow", [ax("AXGroup", [
//         ax("AXList", [ax("AXGroup", [ax("AXStaticText", desc: "Compose")]),
//                       ax("AXGroup", [ax("AXStaticText", desc: "Inbox")]),
//                       ax("AXGroup", [ax("AXStaticText", desc: "Snoozed")]),
//                       ax("AXGroup", [ax("AXStaticText", desc: "Sent")])]),
//         ax("AXGroup", [ax("AXStaticText", desc: "Settings")]),
//     ])], title: "Inbox")
//     for (name, url) in [("Gmail", "https://mail.google.com/mail/u/0/#inbox/FMfcgzQbfvLXrTgVdKWqNJ"),
//                         ("Outlook", "https://outlook.office.com/mail/inbox/id/AAQkADAwATM0MDAAZS0z"),
//                         ("Teams", "https://teams.microsoft.com/#/conversations/19:abc123@thread.v2"),
//                         ("LinkedIn", "https://www.linkedin.com/messaging/thread/abc/")] {
//         check(readTree(clockless, bundle: "com.google.Chrome", url: url).reader == "generic",
//               "\(name): a thread URL with no timed rows on screen is still not a conversation")
//     }
//
//     // A calendar is not a thread, and nothing claims it.
//     check(!ReaderRegistry.dedicated.contains {
//         $0.accepts(ReadContext(bundleID: "com.google.Chrome",
//                                url: "https://calendar.google.com/calendar/u/0/r", now: Date()))
//     }, "a calendar is not a conversation and no reader claims it")
// }
//
// // ── THE FALL-BACK ALARM ─────────────────────────────────────────────────────────────────────────
// // A surface GeniOS claims to understand must never be served by the generic reader. This is the
// // check that was missing: the WhatsApp reader returned nil for weeks and the only symptom was a
// // manager getting the chat list instead of the chat.
// print("\nNo claimed surface falls back to the generic reader")
// do {
//     let claimed: [(String, String?, String?)] = [
//         ("WhatsApp desktop", "net.whatsapp.WhatsApp", nil),
//         ("Slack desktop", "com.tinyspeck.slackmacgap", nil),
//         ("Slack web", "com.google.Chrome", "https://app.slack.com/client/T1/C1"),
//         ("Gmail web", "com.google.Chrome", "https://mail.google.com/mail/u/0/#inbox/FMfcgz12345678"),
//         ("Outlook web", "com.google.Chrome", "https://outlook.office.com/mail/id/AAQkADAwATM0"),
//         ("Outlook desktop", "com.microsoft.Outlook", nil),
//         ("Teams web", "com.google.Chrome", "https://teams.microsoft.com/#/conversations/19:abc"),
//         ("Teams desktop", "com.microsoft.teams2", nil),
//         ("LinkedIn web", "com.google.Chrome", "https://www.linkedin.com/messaging/thread/2-abc/"),
//     ]
//     for (name, bundle, url) in claimed {
//         let accepted = ReaderRegistry.dedicated.contains {
//             $0.accepts(ReadContext(bundleID: bundle, url: url, now: Date()))
//         }
//         check(accepted, "\(name) has a reader that accepts it")
//     }
// }
//
// print(failures == 0 ? "\nALL PASS" : "\n\(failures) FAILED")
// exit(failures == 0 ? 0 : 1)
```
