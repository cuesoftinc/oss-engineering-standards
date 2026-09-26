# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `cuelabs-system-design` skill: designs a product's system from a PRD, a
  repository, or a description, following the language-by-role pipeline
  rule. It decides the services (including when to split a processing
  service versus run worker pools), how they communicate, and who owns each
  store, and adds reusable patterns: upload tickets, claim-check, outbox,
  versioned results, and raw provider events. It writes
  `docs/system-design.md` and renders a self-contained diagram page
  (`scripts/render_design.py`, stdlib only) with Excalidraw and Mermaid copy
  buttons, a layout checker, and an artifact mode for hosts that publish
  pages.
- Multi-service pipeline canon: a repo may carry more than one non-`common`
  service when a real multi-stage pipeline exists (gateway + processing),
  with Go staying the CRUD/data owner, a processing service owning every
  decision with no persistence of its own, and a gateway service staying
  thin — expendit's `api/intake` (Node) + `api/process` (Python) is the
  reference case.
- Node API service standard (NestJS, `api/<service>`, distinct from `web`):
  folder layout, file/folder naming row, `Dockerfile.node` +
  `dockerignore.node` templates, and a NestJS 11.x version pin.
- Pub/sub (Aiven Kafka) documented as a standardized transport alongside
  gRPC and HTTP/JSON, with fleet-wide `KAFKA_BROKERS`/`KAFKA_USERNAME`/
  `KAFKA_PASSWORD`/`KAFKA_SSL_CA` env names — chosen over gRPC s2s for
  expendit/apparule/upstat's pipeline because it survives a Cloud Run
  consumer restart with zero message loss (verified against a live Aiven
  instance), where a gRPC channel can silently zombie on scale-to-zero.
  Kafka consumers must run as a Cloud Run worker pool, or as a service with
  `min-instances >= 1` and instance-based billing, since a message does not
  wake a scaled-to-zero instance.
- gRPC s2s client resilience on Cloud Run: a deadline on every call, a real
  retry policy (bounded attempts, backoff, `UNAVAILABLE` only) for
  idempotent methods, and keepalive for active calls. `waitForReady: false`
  is no longer described as a retry policy, and idle dead-connection
  detection is no longer promised.
- Serverless functions are now explicitly scoped to probe/health-check
  endpoints only; real logic always lives in a containerized `api/<service>`.
- `organization-policy.md` picked up the gRPC s2s client resilience note
  that `cloud-and-ci.md` already had (the two copies had drifted).
- `product-decisions.md`: the checklist of values each product chooses
  for itself (slug, default theme, Playwright port, service ports, data
  store, settings IA, date idiom, KYC tier contents, and more), each with a
  stable `P-nn` ID, recorded in the product's `docs/decisions.md`.
- "Shared ecosystem services" table in `organization-policy.md`: the
  observability gateway, analytics events API, identity project, and
  infrastructure are named by role and contract; the table is the only place
  a providing product is named.
- `validate_catalog.py` fails when a product name appears under `skills/`
  outside that table, or when a reference carries a dated ratification note.
- `cuelabs_standard.py init --name <product> --surface NAME=STATUS`: starts a
  new product from an empty repository by writing `.cuelabs/project.yaml`
  and, for the `cuelabs` profile, a `docs/decisions.md` seeded with the
  Standard parameters table (`assets/templates/decisions.md`). It validates
  the manifest before writing and never overwrites either file.
- "Procedure B — bootstrap a new repo" is now a full walkthrough, from
  `git init` through `init`, parameter decisions, `apply`, per-surface
  scaffolding, delivery, and `verify`; the README shows the quick start.
- Trigger evaluation cases for starting a new product.
- Bootstrapping asks before it decides: the engineering skill confirms the
  product slug, display name, profile, and surface statuses with the user
  before `init`, proposes each `P-nn` value with a reason and records it only
  once confirmed, and reports unconfirmed values as open decisions.

### Changed

- References no longer carry duplicate copies of the same canon. Each topic
  has one owner: cloud/CI, containers/deploy, and telemetry/environment live
  in `cuelabs-delivery-standard`; API conventions, docs contracts, and
  analytics live in `organization-policy.md`; the design documentation
  standard lives in `cuelabs-design-standard`; orchestration and QA loops
  live in `qa-and-orchestration.md`; changelog discipline lives in
  `repository-and-services.md`. The engineering skill keeps short summaries
  that point at the owning skill, so it still works when installed alone.
- The skills are product-agnostic, so they can bootstrap a brand-new
  product. Product names, per-product values, incident stories, dated
  ratification notes, and internal decision codes are gone from every
  reference; each rule now states its contract directly instead of pointing
  at one product's implementation. History stays in this changelog.
- Per-product values became product decisions: the marketing product slot,
  default theme, Playwright port, settings IA, date idiom, and service port
  assignments are recorded by each product (see `product-decisions.md`).
- The Playwright port rule now requires a port in 3100–3399 that no sibling
  product uses.

### Removed

- `cuelabs-design-standard/references/qa-loop.md`, an identical copy of
  `qa-and-orchestration.md`.

## [2.0.1] - 2026-07-23

### Fixed

- Audit: the root `.env.example` is seeded, never byte-compared — the canon
  fixes its variable names and section format while values and
  product-specific sections diverge per repository, so customization no
  longer reads as shared-file drift (which kept every adopter at
  "Baseline conforming: no") (#138).
- The repository's own `SECURITY.md` now carries the published reporting
  policy (private vulnerability reporting, dedicated security mailbox) (#138).
- Changelog cut into released sections — v2.0.0 shipped with all entries
  still under Unreleased; adoption docs now also state that the catalog
  repository itself is not a manifest-carrying adopter (#138).

## [2.0.0] - 2026-07-23

### Added

- Multi-skill v2 catalog with focused repository, web, mobile, delivery, and
  design skills; progressive-disclosure references; Codex UI metadata; base and
  CueLABS profiles; a project-manifest schema; trigger evaluations; official
  validation CI; and a dependency-free `audit / plan / apply / verify` tool
  (#137).
- Public adoption, compatibility, governance, and v2 migration documentation
  with one-command Codex and Cursor installation (#137).
- Baseline CLI regression coverage for installed resource resolution, manifest
  authority and validation, shared-file drift, ordered plans, path collisions,
  and idempotent application (#137).

- `SKILL.md`: fleet parity canons from the 2026-07-23 cross-repo review —
  Node 24 single-truth (CI + .nvmrc + image + README), Go single-truth
  (1.26, `app` binary, 10s health start-period), exact-pinned and
  fleet-aligned web deps with the org dependabot ignore block, the
  TEST_MODE web canon (provider/store/seed/reset naming and the
  JSON-session-snapshot rule), org lint bans + wired testing-library
  preset, the README fleet template with badge row, bottom-right
  dev indicators, and changelog-PR-ref amendment procedure (#133).

- `SKILL.md` mobile standard: the repeating-MI test canon — screens hosting
  repeating MI primitives run their wiring suites and seeded goldens under
  the platform reduced-motion flag (motion stays covered by the primitives'
  bounded-pump unit tests), and animated size/draw progress inside
  IntrinsicHeight rows is painted, never laid out (a fractional sizer at
  factor 0 reports an infinite intrinsic and crashes the row) (#131).

- `SKILL.md` mobile standard: the E2E lane canon (patrol journeys, nightly
  cadence, prove-then-revert for dispatch-only workflows) and the on-device
  IME-injection gotcha (#132).

- `SKILL.md` mobile standard: build-state hygiene at the gate — flutter
  clean, daemon stops, docker image prunes, and DerivedData purges are part
  of lane closeout (#130).

- `SKILL.md`: eight interaction-integrity locks from the mobile
  interaction-contract audit (stale siblings, fake optimism, dead controls,
  silent failures, danger ladder, MI primitives, destinations, forms) (#129).

- `SKILL.md`: eight cross-platform parity canons from the apparule
  mobile↔web adjudication — chrome-scoped alignment, canon-fact sweep
  checklist, parity scope rules, session-restore gate, danger-ladder
  additions, entity-reference affordances, unit-toggle conversion, and
  single-listing cross-client constants (#128).

- `SKILL.md` mobile standard: the canvas-first rule — every shipped screen
  has a Figma frame (design first or drop); frameless screens escape visual
  QA (#127).

- `SKILL.md`: Mobile (Flutter) implementation standard — FVM-pinned toolchain,
  official MVVM+Repository vocabulary over a feature-first tree, Riverpod 3,
  typed go_router, mock-first fake repositories with seeded assets (TEST_MODE
  parity), Figma-variable-generated ThemeExtensions, one module per Figma
  component set, very_good_analysis + alchemist/patrol testing, dev/stg/prd
  flavors with Doppler-fed dart-defines, and the Google-only Firebase auth
  flow (#120).

- `SKILL.md` web-canon sections from the 2026-07-20/21 program waves: tri-state
  theme contract (#94), double-writer coordination-ledger protocol (#95),
  unset-theme-is-design-default ruling (#96), audit-convergence sync — danger
  ladder, chart construction, micro-labels, star-badge construction (#97),
  fleet chrome naming + date idioms (#98), settings IA shapes (#99),
  review-round canons — floating-layer Y-flip, anatomy fidelity, findings-are-
  classes (#100), chart dash-normalization gotcha (#101), landing type-fidelity
  canon (#102), quiet-danger reference implementation (#104), worktree removal
  at the merge gate + the 2-build-worktree cap (#105), the FAH
  `images.unoptimized` gotcha + WebP loader canon (#106), overlay focus
  contract + named-control API (#107), SEO plumbing canon (#108),
  contrast-token canon — `-text` variants, `on-crit`, fixed-light locales
  (#109, #110), the canonical `web/src/` tree — shape is a parity item (#111),
  heavy-embed intent-gate canon (#112), legal-link canon (#113), pre-paint
  persisted-chrome init + deferred-hydration contract (#114), layout-stability
  canon (#115), and the a11y closeout canons — skip link, real `inert`, stable
  tab ids, ⌘K, `test-session` key, unique landmarks (#116).

- `templates/Dockerfile.python`, per-context `templates/dockerignore.{go,web,python}`,
  `templates/env.example`, standard-form Helm chart skeleton (`templates/helm/`),
  and cluster-agnostic terraform (`templates/terraform/`).
- Port convention (`api/common`=8080, `web`=3000, additional APIs increment from
  8081) and a per-language file & folder naming standard in `SKILL.md`.
- `SKILL.md`: the CueLABS repository standard plus bootstrap and standardize
  procedures for coding agents.
- `templates/`: canonical community-health and config templates (LICENSE,
  CODEOWNERS, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, dotfile templates stored
  without the leading dot — `gitignore`, `editorconfig`, `dockerignore.root` —
  a dependabot example, and PR/issue templates), shared byte-identically across
  CueLABS repositories.

### Changed

- Repackaged the root `SKILL.md` handbook into
  `skills/<skill-name>/SKILL.md` packages. Existing canon remains available in
  focused references, while templates now live in the primary skill's
  `assets/templates/` directory (#137).

- `SKILL.md` and shared templates: preserve canonical GitHub Actions workflows,
  defer standardized backend jobs until each backend is build-ready, reconcile
  the canonical Next.js tree, make gRPC a fleet-standard transport option, and
  add byte-identical mobile-ready Makefile + generated-client Prettier-ignore
  templates for every product (#136).

- `SKILL.md`: deploy truth reconciled by surface — websites ride Firebase
  App Hosting automatic rollouts from `main` (cuesoft-iac appHosting;
  live in ~30 min, verified), while API-service deploys stay tag-gated
  via the pending `release.yml`; the changelog discipline gains the
  append-into-existing-bucket rule (second headings forced dedup rounds
  in every repo) (#135).

- `SKILL.md`: the Recommended-versions Go row reconciled to the Go
  single-truth canon — 1.26 fleet-wide with `golang:1.26-alpine`
  (the row still framed apparule as a lone 1.26 exception; caught by
  the pass-3 sweep) (#134).

- `SKILL.md` self-consistency pass (found by the standards self-audit):
  the pre-canon Flutter tree block now points at the feature-first mobile
  standard; mobile CI described as it ships (native riverpod_lint on
  analyze, no custom_lint; coverage gate deferred; per-PR unsigned
  iOS-simulator build); the removed upstream `synthetic-package` key is
  no longer instructed; `release.yml` marked not-yet-landed; the
  byte-identical CI claim scoped to the shared web jobs with the mobile
  workflows noted; `stg` dropped from the entrypoint example; CodeQL
  documented as GitHub default setup (API-checked, not a workflow file) (#133).

- `README.md`: templates description covers the Docker/env/helm/terraform
  templates; CueLABS™ brand mark applied in README and CONTRIBUTING (#133).

- `SKILL.md` mobile standard: platform floors & flavor plumbing (iOS 15 with
  Firebase 12, flutter-tool-only builds, load-bearing flavor config naming,
  seed-bundling assertion in CI) and the safe-area contract with notched test
  surfaces — both verified on live devices (#126).

- `SKILL.md` mobile standard: goldens are authored on Linux (alchemist CI
  config normalizes text only; curve/gradient AA is platform-bound) via a
  dockerized regen script or dispatch workflow; `url_launcher` joins the
  pin ledger (#125).

- `SKILL.md` mobile standard: flavors mirror the org environment model —
  `dev` + `prod` only (the sandbox account is CueLABS production); the
  generic dev/stg/prd trio is rejected (#124).

- `SKILL.md` mobile standard: resolver-verified pin corrections from the
  skeleton wave — riverpod_lint 3.x as a native analyzer plugin (custom_lint
  retired), build_runner/freezed/intl caps, gen-l10n key removal,
  go_router_builder public mixins, AGP 9 resValues default (#123).

- `SKILL.md` mobile standard: legacy-quarantine rule — superseded code moves
  to `lib/legacy/` and is removed only after its replacement ships with an
  explicit user go (#121).

- `SKILL.md` deferral-sweep updates (2026-07-21): upstat's Floating-UI
  deviation retired (converged to Radix; bespoke layers recorded), nav-rail
  prefetch canon revised to intent-based (hover/focus `router.prefetch`),
  web manifest + `SkipLink.tsx` join the SEO canon and byte-identical
  shared-files list, transform-only rule for per-frame movers joins the
  layout-stability canon, and changelog discipline (single bucket headings,
  merged top-ups).

- `SKILL.md`: retired-system references scrubbed to current-system voice
  throughout (#103).


- Refined the production service-structure guidance (singular Go packages,
  FastAPI `lifespan`, web `src/` + route conventions) and synced the `Makefile`,
  `Dockerfile.go`, `Dockerfile.web`, and `docker-compose.example.yml` templates.

- SKILL.md: per-service internals standard (README/.gitignore/.dockerignore/
  .env.example per service), canonical Go module paths, SSR-safety and
  127.0.0.1-healthcheck gotchas, envoy-in-compose pattern, standard-form
  Helm/terraform deploy convention, scoped `.dockerignore` parity claim, and
  several accuracy fixes (docs/ list, data stores, root-layout wording).
- PR template: dropped the CI reference (the standard has no CI workflows).
