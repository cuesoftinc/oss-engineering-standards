# Mobile Flutter implementation standard

## Contents

- Toolchain, architecture, state, navigation, and data
- Mock-first development and interaction-integrity locks
- Cross-platform parity and canvas-first delivery
- Design system, quality, flavors, and platform floors
- Safe areas, build hygiene, E2E, quarantine, and authentication

## Canon

This is the org canon for every product with a mobile surface. The
product's `docs/mobile-implementation.md` carries its full contract on top
of it.

- **Toolchain**: current stable Flutter pinned via FVM — `.fvmrc` is the
  single source of truth (CI reads it), mirrored as a hard
  `environment: flutter:` pin in pubspec. Current pin: Flutter 3.44.7 /
  Dart 3.12 (Android floor API 24; iOS floor per "Platform floors" below;
  SwiftPM is the iOS dependency default — the CocoaPods registry goes
  read-only in December 2026).
- **Architecture**: the official Flutter MVVM + Repository vocabulary
  (Views ↔ 1:1 ViewModels; abstract repositories are the single source
  of truth and never reference each other; services are stateless
  single-source wrappers; unidirectional flow; immutable models;
  use-cases only when EARNED, in `<feature>/domain/`). Organization is
  FEATURE-FIRST: `lib/src/features/<feature>/{presentation,domain,data}`
  + `src/{app,routing,core}` — core/ui is the design system.
- **State/DI**: Riverpod 3 with codegen (`@riverpod` ViewModels,
  ConsumerWidgets; riverpod_lint 3.x is a NATIVE analyzer plugin —
  installed via analysis_options `plugins:`, diagnostics in plain
  `flutter analyze`; custom_lint is retired for it and cannot
  co-resolve with the modern codegen stack). DI = Riverpod provider
  overrides per environment — no second DI container. Pin notes
  (resolver-verified): build_runner ≤2.15.1 with riverpod_generator 4.0.4;
  freezed rides its analyzer-12 compat release; intl pins exactly to the
  SDK's flutter_localizations; gen-l10n's `synthetic-package` key is
  removed upstream; go_router_builder 4.4 mixes in PUBLIC `$Route` mixins;
  AGP 9 defaults `buildFeatures.resValues` OFF (enable before flavor
  resValue use).
- **Navigation**: go_router + go_router_builder typed routes
  (accepted in maintenance mode — first-party; revisit on a successor);
  StatefulShellRoute for the tab shell; one top-level auth `redirect`
  off the session provider.
- **Data**: one configured Dio in core/data; per-feature `*ApiService`;
  freezed domain models, json_serializable API models (separate —
  the Go API drifts from UI shapes). Codegen output (`.g.dart`,
  `.freezed.dart`) is COMMITTED with a CI codegen-fresh check;
  generated l10n is gitignored (regenerates on pub get).
- **MOCK-FIRST (TEST_MODE parity)**: every repository is abstract with
  `*Remote` and `*Fake` implementations; fakes read seeded narrative
  JSON from dev-flavor-scoped `assets/seed/dev/`; per-flavor entrypoints
  (`main_dev.dart`/`main.dart`) pick the provider-override set. API wiring
  lands LAST behind unchanged repository interfaces.
- **Interaction-integrity locks (lock the class, not the instance)**:
  (1) STALE SIBLINGS — under an always-mounted shell (StatefulShellRoute +
  Riverpod pause), mutations MUST go through a per-domain facade owning a
  DECLARED invalidation fan-out; ban ad-hoc ref.invalidate in screens/VMs;
  lock = the two-surface contract test (one container, keep-alive listeners
  on every declared derivation, mutate once, assert all rebuild) + fakes
  persist state through the key-value store so restart tests pass.
  (2) FAKE OPTIMISM — await-then-invalidate is NOT optimistic: mutate local
  state synchronously, reconcile, rollback+toast on error; body switches use
  skipLoadingOnRefresh; lock = the pending-future morph test (Completer that
  never resolves; assert the morph landed, no skeleton). (3) DEAD CONTROLS —
  null handler ⇒ affordance hidden/disabled, enforced per core/ui component
  with null-callback tests + a per-screen traversal asserting every enabled
  tappable has a handler. (4) SILENT FAILURES — unawaited_futures +
  discarded_futures at ERROR severity; a shared runAction
  (await→catch→toast→rollback, input preserved); every fake carries a
  failNext seam with one failure-path test per mutating surface.
  (5) DANGER LADDER — irreversible transitions are callable only from
  confirm sheets born DISARMED (reason=null, CTA disabled); arming tests,
  never defect-encoding tests. (6) MI PRIMITIVES — every design-system
  microinteraction exists ONCE as a named core/ui primitive; an MI-registry
  conformance test maps screen→active-MIs from the contract and asserts the
  primitive is instantiated — a screen cannot ship with an MI
  active-but-absent. (7) DESTINATIONS — exhaustive kind→route mapping tests
  (no silent enum fallthroughs); interstitial exits go(), never push().
  (8) FORMS — one shared parser/validator per input class; in-flight guards
  supersede, never wedge; Completer-driven state-machine tests cover
  input-during-flight.
- **Cross-platform parity canons**: (1) CHROME ALIGNMENT — header-bar titles
  are true bar-width centered (on the bar, never the between-actions flex
  remainder) on EVERY platform rendering the AppBar master, web included;
  desktop-dashboard in-content page titles stay left-aligned — centering
  rules are chrome-scoped, never page-scoped. A mobile chrome ruling extends
  to web exactly where web renders the same chrome component and stops at
  platform-idiom boundaries. (2) CANON-FACT SWEEPS — when a product-fact
  changes, sweep ALL clients + docs + canvas text + copy-locking tests +
  metadata (page meta, PWA manifest, OG image + alt) + brand-asset
  GENERATOR scripts; taglines encoding product mechanics get validated
  against the ratified contract at write time. (3) PARITY SCOPE — `pages.md`
  Part C (mobile) rows without an explicit "= B" sibling are
  platform-scoped by contract; never manufacture a web twin; parity is
  adjudicated on narrative, not chrome. (4) SESSION-RESTORE GATE —
  tri-state auth everywhere; nothing routes or paints auth-dependent
  surfaces until restore resolves; failed restore reads signed out (resolve
  null, never reject past the boundary); a signed-in user never sees the
  auth screen. (5) DANGER LADDER — the row rung is a first-class
  quiet-danger Button kind; the armed rung's typed-confirm token is
  product-ratified; a Figma kind-axis addition creates a
  due-on-first-use obligation for every sibling platform.
  (6) ENTITY REFERENCES — every avatar/username on a social surface
  navigates to its canonical page platform-idiomatically; new
  list/row/card components MUST expose the nav affordance in their
  prop contract even if the first consumer doesn't wire it (exempt:
  confirm dialogs, chat bubbles, marketing mocks, staff queues).
  (7) UNIT TOGGLES are display-only over canonical units — always
  convert display↔canonical on flip; never a toggle wired to state
  but not conversion. (8) CROSS-CLIENT CONSTANTS (advisory ranges, QC
  tables) live in ONE canonical doc listing that every client asserts
  against in tests — no per-client drift.
- **Canvas-first rule**: NO screen ships without a Figma frame — a
  frameless screen is either DESIGNED FIRST (frames ratified, then
  implemented) or DROPPED if unnecessary to the ratified flow. "Restyled
  legacy" without a frame is how off-canon visuals survive QA: convergence
  passes can only pixel-judge what the canvas holds, so docs-only screens
  escape visual parity.
- **Design system**: Material 3 + one ThemeExtension per token group,
  GENERATED from the product's Figma variables (tokens JSON in-repo is
  the reviewed artifact; Dart output never hand-edited); light+dark
  from the same token set; fonts bundled (no runtime fetching). One
  module per Figma component set, constructor params mirror the
  variant axes (the web component canon carried over) — each set
  golden-tested.
- **Quality**: very_good_analysis (+ riverpod_lint), strict casts/
  inference/raw-types; tests mirror lib/src (unit = ViewModels/repos/
  services with mocktail + ProviderContainer overrides; widget = every
  screen over fakes; golden = alchemist — golden_toolkit is
  discontinued. GOLDENS ARE AUTHORED ON LINUX: alchemist's ci config
  only platform-normalizes TEXT (obscured fonts); curve/gradient/
  shadow anti-aliasing is platform-bound, so macOS-generated goldens
  fail Linux CI with small deterministic diffs (~0.02–1.6%). Regenerate
  via the repo's dockerized script or the mobile-goldens dispatch
  workflow — never bump tolerances to paper over platform drift; E2E =
  patrol smoke journeys, nightly not per-PR).
  **Repeating-MI test canon**: once a screen hosts a REPEATING MI primitive
  (pulse/typing/shimmer), `pumpAndSettle` never terminates on it —
  wiring/transition suites and seeded screen goldens for such screens run
  under the platform reduced-motion flag
  (`FakeAccessibilityFeatures(disableAnimations: true)` / a
  `disableAnimations` MediaQuery wrapper), which every MI primitive must
  honor per `design.md`'s accessibility & motion rules (same anatomy,
  static); the MOTION itself is covered by the primitive's own
  bounded-pump unit tests. Corollary: animated size/draw progress inside
  IntrinsicHeight-measured rows must be PAINTED, never laid out — a
  FractionallySizedBox at heightFactor 0 reports an infinite max
  intrinsic (child ÷ 0) and crashes the row on frame one (for example an
  animated connector drawn inside timeline rows).
  CI: format check, codegen-fresh, `analyze --fatal-infos` (riverpod_lint
  diagnostics ride the native analyze — no custom_lint), `flutter test`
  (coverage gate deferred to a later wave), plus an unsigned iOS-simulator
  dev-flavor build on every PR; an apk/ipa release matrix lands with the
  deploy phase.
- **Hygiene**: flavors mirror the ORG ENVIRONMENT MODEL, not the
  generic trio — CueLABS has one real environment (the sandbox account
  IS production), so mobile ships exactly `dev` (fakes, ".dev" suffix) +
  `prod` (bare id, sandbox Firebase, Doppler stg config); add flavors only
  when a ratified environment exists (applicationIdSuffix + iOS schemes,
  `appFlavor` constant, flavor-scoped assets); secrets via
  `--dart-define-from-file=env/<flavor>.json` generated from Doppler,
  gitignored — never envied/obfuscation as security; gen-l10n outputs
  into `lib/` (the `synthetic-package` key is removed upstream — do not
  write it into l10n.yaml);
  native projects live INSIDE the flutter root; icons/splash via
  flutter_launcher_icons + flutter_native_splash per flavor;
  `version: x.y.z+build` — humans own x.y.z, CI stamps build number.
- **Platform floors & flavor plumbing**: iOS floor is 15 (Firebase iOS SDK
  12 requires it — the Flutter floor of 13 does NOT build once firebase
  packages join). The pbxproj `IPHONEOS_DEPLOYMENT_TARGET` is the single
  source: flutter_tools rewrites the generated SwiftPM package's platform
  from it on every build — raw `xcodebuild` BYPASSES that rewrite (and all
  flavor/asset plumbing); always build through the flutter tool. iOS
  flavors: the scheme/config NAMING is load-bearing — the tool derives the
  flavor from the build configuration name (`Debug-dev` → flavor `dev`),
  and flavor-scoped assets bundle ONLY when a flavor is carried, so a
  schemeless build ships fakes with EMPTY seed stores. CI carries an
  unsigned iOS simulator-build lane with a bundled-seed assertion.
- **Safe-area contract**: screen chrome insets via MediaQuery.viewPadding —
  fixed at CHROME altitude (the shared top-bar paints behind the status
  bar, content rows inset below), never per-screen hacks; immersive
  full-bleed screens keep media edge-to-edge but inset their over-media bar
  CONTENT. Test lock: a notched-MediaQuery helper asserting no content in
  the top inset under BOTH platform profiles (iOS notch ~59px, Android
  punch-hole ~39px), wired into every screen suite, plus one notched golden
  per chrome kind. Plain test surfaces are notchless — without this, inset
  bugs ship invisibly.
- **Build-state hygiene at the gate**: every mobile lane's closeout runs
  `flutter clean` in its worktree, stops gradle/dart daemons, and
  `docker image prune`s golden-container images it pulled; device-install
  sessions purge Xcode DerivedData when done. Host build state
  (DerivedData, gradle caches, docker images/buildkit, flutter build dirs)
  is treated like worktrees: cleaned at the GATE, never left to accumulate
  until the disk fills.
- **Mobile E2E lane canon**: patrol_finders over the SDK's
  integration_test; smoke journeys assert USER-VISIBLE outcomes only
  (screens reached, data shown); the lane runs nightly + workflow_dispatch,
  NEVER per-PR (cost); runner shape: ubuntu + KVM enable + temurin
  (AGP-matched) + flutter-action (.fvmrc pin) +
  reactivecircus/android-emulator-runner (default target — no Play services
  with fakes). New dispatch-only workflows are PROVEN pre-merge via a TEMP
  branch-push trigger commit, reverted once green — never merged unproven.
  GOTCHA: never use enterText/IME injection in ON-DEVICE integration tests
  — the live binding never registers TestTextInput, so injected text rides
  a debug path that silently fails to commit against the real IME; drive
  pointer gestures instead (typed-entry coverage stays in widget tests).
- **Legacy quarantine (carried from web)**: superseded mobile code is NEVER
  deleted up front — it moves structure-preserved into `lib/legacy/`
  (assets to `assets/legacy/`, replaced native trees to `legacy/<name>/`),
  excluded from pubspec assets, analysis, CI scope, and builds; actual
  removal requires BOTH the shipped replacement AND an explicit user
  removal go.
- **Auth (Google-only, carried to mobile)**: Google sign-in ONLY via
  Firebase — `flutterfire configure` per flavor against the shared identity
  project (see the engineering skill's "Shared ecosystem services");
  google_sign_in 7.x flow (`GoogleSignIn.instance.initialize` →
  `authenticate()` → `signInWithCredential`; silent restore via
  `attemptLightweightAuthentication()`); tokens at rest in
  flutter_secure_storage; wrapped in an abstract auth_repository with
  a fake for TEST_MODE. Password/SMS/OTP flows are forbidden.
